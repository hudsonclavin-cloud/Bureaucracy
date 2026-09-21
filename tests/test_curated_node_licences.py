"""Adding a node to the curated file, and the two ways that goes wrong.

`scripts/add_curated_nodes.py` is one of the few writers of the curated file,
and a wrong row there is expensive: a node added for a unit that already exists
under another name is a duplicate this repository has had to merge before, and
a node added beside a unit the Treasury reports jointly with it silently starts
dividing a measured figure.

The `government_manual_entry` licence is the third, and the only one that
licenses the PLACEMENT as well as the name. A Treasury line and a page label
each say a unit of this name exists and neither says what it sits under, so on
those rows the parent is the row author's assertion; the Government Manual
prints a hierarchy, so it can be checked, and is.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT, PROJECT_ROOT / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from add_curated_nodes import (  # noqa: E402
    LICENCE_MANUAL,
    LICENCES,
    STRUCTURE_SOURCE,
    jointly_measured_names,
    main as add_main,
    manual_chain,
    manual_entries_by_key,
    manual_files_it_under,
)
from data_pipeline.verification.govman import read_manual  # noqa: E402

PUBLISHED = PROJECT_ROOT / "output" / "graph.json"


class SourceUnreachable(Exception):
    """The writer could not reach a source it re-verifies a row against.

    A `treasury_statement_line` row is re-checked against the CURRENT
    statement on every run, by design, so these tests reach the network. When
    the host does not answer, the writer exits nonzero and the row is neither
    applied nor refused -- nothing was learned. Reporting that as a failed
    rule would be the exact confusion this project refuses everywhere else:
    "the check failed" and "the check could not be made" are different
    claims. Measured on 2026-09-21, api.fiscaldata.treasury.gov answered two
    calls in two seconds and timed out on the next two.
    """


def run_table(rows, extra=()):
    """Dry-run the writer over a scratch table; returns its JSON report."""
    import contextlib
    import io

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "table.json"
        path.write_text(json.dumps({"nodes": rows}), encoding="utf-8")
        buffer = io.StringIO()
        errors = io.StringIO()
        try:
            # The "could not reach ..." line goes to stderr, so both streams
            # are captured; reading only stdout reported an unanswered host as
            # a failed rule.
            with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(errors):
                add_main(["add", "--dry-run", "--json", "--table", str(path), *extra])
        except SystemExit:
            printed = buffer.getvalue() + errors.getvalue()
            if "could not reach" in printed:
                said = [line for line in printed.strip().splitlines() if "could not reach" in line]
                raise SourceUnreachable(said[-1].strip()) from None
            raise
        # --json prints the report and then a human line after it.
        report, _end = json.JSONDecoder().raw_decode(buffer.getvalue().lstrip())
        return report


class LicenceRegistrationTests(unittest.TestCase):
    def test_the_manual_licence_is_registered_with_its_own_structure_source(self):
        self.assertIn(LICENCE_MANUAL, LICENCES)
        self.assertEqual(STRUCTURE_SOURCE[LICENCE_MANUAL], "named_in_the_us_government_manual")


class ManualPlacementTests(unittest.TestCase):
    def setUp(self):
        self.manual = read_manual()
        self.index = manual_entries_by_key(self.manual)

    def entity(self, name):
        from data_pipeline.exporter.build_graph import canonical_name_key

        hits = self.index[canonical_name_key(name)]
        self.assertEqual(len(hits), 1, name)
        return hits[0]

    def test_the_manual_prints_a_chain_above_each_entry(self):
        chain = manual_chain(self.manual, self.entity("Gallaudet University"))
        self.assertEqual(chain[:2], ["Federally Aided Corporations", "Department of Education"])

    def test_the_chain_is_what_licenses_a_parent(self):
        ok, _ = manual_files_it_under(self.manual, self.entity("Gallaudet University"),
                                      "Department of Education (ED)")
        self.assertTrue(ok, "canonical_name_key drops the parenthetical, so this must match")
        wrong, chain = manual_files_it_under(self.manual, self.entity("Gallaudet University"),
                                             "Department of Justice (DOJ)")
        self.assertFalse(wrong)
        self.assertIn("Department of Education", chain)


class WriterRefusalTests(unittest.TestCase):
    """Both directions, against the real Manual and the real curated file."""

    def row(self, **over):
        base = {"id": "test-scratch-node", "parentId": "exec-dept-ed",
                "name": "Gallaudet University", "type": "Federally Chartered Corporation",
                "licence": LICENCE_MANUAL, "basis": "a test row", "addedOn": "2026-09-20"}
        base.update(over)
        return base

    def only(self, report):
        self.assertEqual(len(report["results"]), 1)
        return report["results"][0]

    def test_a_good_row_is_added_and_cites_the_manual_entry(self):
        item = self.only(run_table([self.row()]))
        self.assertTrue(item["added"], item)
        self.assertTrue(str(item["detail"]).startswith("https://www.govinfo.gov/app/details/"))

    def test_a_parent_the_manual_does_not_support_is_refused(self):
        item = self.only(run_table([self.row(parentId="exec-dept-doj")]))
        self.assertFalse(item["added"])
        self.assertEqual(item["reason"], "manual_files_it_elsewhere")
        self.assertIn("Department of Education", item["detail"])

    def test_a_name_the_manual_does_not_carry_is_refused(self):
        item = self.only(run_table([self.row(name="Department of Widget Affairs")]))
        self.assertFalse(item["added"])
        self.assertEqual(item["reason"], "manual_does_not_name_one_such_unit")

    def test_a_more_specific_parent_inside_the_licensed_region_is_allowed(self):
        # The Manual files this under "Joint Service Schools" under "Defense
        # Agencies" under "Department of Defense". The proposed parent is the
        # graph's "Defense Agencies & Field Activities", whose name matches
        # none of those, so the walk goes up to the Department of Defense —
        # which the Manual's chain does name — and the row is allowed under the
        # looser "within" rule rather than refused.
        #
        # Deliberately a unit still absent from the curated file: CURATION.md
        # §13.6 leaves the Defense Acquisition University unsure, so it is not
        # added and this test cannot be invalidated by its own subject being
        # added, which is what happened to the Defense Commissary Agency.
        item = self.only(run_table([self.row(
            id="test-scratch-within", parentId="exec-dept-defense-agencies",
            name="Defense Acquisition University", type="Defense Agency")]))
        self.assertTrue(item["added"], item)

    def test_a_unit_the_treasury_reports_jointly_is_refused(self):
        # There is no Treasury row for the Bureau of Indian Education; there is
        # one combined row for it and the Bureau of Indian Affairs, already
        # measured on the BIA node. A separate node would take an apportioned
        # share out of a pool reported for the two of them together.
        if not PUBLISHED.exists():
            self.skipTest("output/graph.json is not built")
        item = self.only(run_table([self.row(
            id="test-scratch-bie", parentId="exec-dept-doi",
            name="Bureau of Indian Education", type="Bureau")]))
        self.assertFalse(item["added"])
        self.assertEqual(item["reason"], "treasury_reports_it_jointly_with_an_existing_node")
        self.assertIn("exec-dept-doi-bia", item["detail"])

    def test_the_committed_table_is_idempotent(self):
        try:
            report = run_table(json.loads((PROJECT_ROOT / "data" / "curation" / "new_nodes.json").read_text())["nodes"])
        except SourceUnreachable as unreachable:
            self.skipTest(f"a source this table is re-checked against did not answer: {unreachable}")
        self.assertEqual(report["added"], 0, "every committed row is already in the curated file")


class JointRowTests(unittest.TestCase):
    def setUp(self):
        if not PUBLISHED.exists():
            self.skipTest("output/graph.json is not built")
        self.joint = jointly_measured_names(PUBLISHED)

    def test_the_joint_index_finds_the_indian_education_case(self):
        from data_pipeline.exporter.build_graph import canonical_name_key

        key = canonical_name_key("Bureau of Indian Education")
        self.assertIn(key, self.joint)
        row, node_id = self.joint[key]
        self.assertEqual(row, "Bureau of Indian Affairs and Bureau of Indian Education")
        self.assertEqual(node_id, "exec-dept-doi-bia")

    def test_a_units_own_name_is_never_in_its_own_joint_index(self):
        # The index is for the OTHER halves of a joint row: a node must not
        # refuse itself.
        from data_pipeline.exporter.build_graph import canonical_name_key

        graph = json.loads(PUBLISHED.read_text(encoding="utf-8"))
        stack, names = [graph], {}
        while stack:
            node = stack.pop()
            if node.get("id"):
                names[str(node["id"])] = canonical_name_key(node.get("name"))
            stack.extend([c for c in (node.get("children") or []) if isinstance(c, dict)])
        for key, (_row, node_id) in self.joint.items():
            self.assertNotEqual(key, names.get(node_id))


if __name__ == "__main__":
    unittest.main()
