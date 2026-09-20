"""OMB's Public Budget Database: a completed year, beside the cost and never as it.

This source is the most dangerous one this project has read, for a reason none
of the others share: **most of its columns are the future.** The FY2027 package
carries year columns out to 2031, and everything from the current fiscal year
onward is the President's request. A projection published beside figures this
project calls measured would be the worst single thing any source here could
do, so the estimate boundary is parsed out of the package's own user's guide on
every run -- by the module, and again, independently, by the gate -- and these
tests pin both parsers against the committed bytes.

The other three hazards are pinned here too: the unit is the publisher's
(thousands, and precise only to the million, both quoted on every record); the
figure is OMB's basis, which its own guide calls merely "generally consistent
with" the Monthly Treasury Statement; and a bureau is matched only beneath its
own agency's node, which is what keeps "Legislative Branch" from reaching a
Senate appropriations subcommittee.
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.exporter.build_graph import (  # noqa: E402
    DEFAULT_BASE_GRAPH,
    canonical_name_key,
    load_base_graph,
)
from data_pipeline.verification.evidence import EVIDENCE_OWNED_FIELDS  # noqa: E402
from data_pipeline.verification.omb_budget import (  # noqa: E402
    DEFAULT_PACKAGE,
    MEMBER_OUTLAYS,
    QUOTE_PRECISION,
    QUOTE_TREASURY,
    QUOTE_TREASURY_DIFFERENCES,
    QUOTE_UNITS,
    THOUSAND,
    apply_omb_budget_evidence,
    build_records,
    estimate_boundary,
    guide_text,
    load_database,
    load_omb_budget_evidence,
    totals_for_year,
)

PUBLISHED = PROJECT_ROOT / "output" / "graph.json"


def published_nodes():
    if not PUBLISHED.exists():
        return []
    graph = json.loads(PUBLISHED.read_text(encoding="utf-8"))
    out, stack = [], [graph]
    while stack:
        node = stack.pop()
        out.append(node)
        stack.extend([c for c in (node.get("children") or []) if isinstance(c, dict)])
    return out


class FixtureIntegrityTests(unittest.TestCase):
    def test_the_package_matches_its_fetch_record(self):
        meta = json.loads(DEFAULT_PACKAGE.with_suffix(DEFAULT_PACKAGE.suffix + ".meta.json").read_text())
        self.assertEqual(hashlib.sha256(DEFAULT_PACKAGE.read_bytes()).hexdigest(), meta["sha256"])
        self.assertTrue(str(meta["url"]).startswith("https://www.govinfo.gov/"))
        self.assertEqual(meta["status"], 200)

    def test_a_tampered_package_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy_path = Path(tmp) / DEFAULT_PACKAGE.name
            body = bytearray(DEFAULT_PACKAGE.read_bytes())
            body[-64] ^= 0xFF
            copy_path.write_bytes(bytes(body))
            meta = DEFAULT_PACKAGE.with_suffix(DEFAULT_PACKAGE.suffix + ".meta.json").read_text()
            (Path(tmp) / (DEFAULT_PACKAGE.name + ".meta.json")).write_text(meta)
            with self.assertRaises(ValueError):
                load_database(copy_path)


class EstimateBoundaryTests(unittest.TestCase):
    """The single most important property of this source."""

    def setUp(self):
        self.database = load_database()

    def test_the_boundary_is_read_from_the_guide_not_assumed(self):
        self.assertEqual(self.database["budgetYear"], 2027)
        self.assertEqual(self.database["firstEstimateYear"], 2026)
        self.assertEqual(self.database["lastActualYear"], 2025)

    def test_the_guide_really_prints_that_sentence(self):
        archive = zipfile.ZipFile(DEFAULT_PACKAGE)
        text = guide_text(archive.read("BUDGET-2027-DB/pdf/BUDGET-2027-DB-4.pdf"))
        self.assertIn("Budget estimates for the current fiscal year", text)
        self.assertIn("the budget year", text)

    def test_the_guide_states_the_boundary_twice_and_both_are_read(self):
        archive = zipfile.ZipFile(DEFAULT_PACKAGE)
        text = guide_text(archive.read("BUDGET-2027-DB/pdf/BUDGET-2027-DB-4.pdf"))
        self.assertIn("Estimated amounts, in thousands of dollars, for FY", text)
        self.assertEqual(estimate_boundary(text), (2026, 2027))

    def test_a_guide_whose_two_statements_disagree_is_refused(self):
        # The narrative and the per-file field tables are written in different
        # parts of the document. If they disagree, the package is not read at
        # all: every other check would pass happily on a projection.
        with self.assertRaises(ValueError):
            estimate_boundary(
                "Budget estimates for the current fiscal year ( 2026), the budget year ( 2027). "
                "Estimated amounts, in thousands of dollars, for FY 2024 through FY 2031")

    def test_a_guide_with_no_field_table_is_refused(self):
        with self.assertRaises(ValueError):
            estimate_boundary(
                "Budget estimates for the current fiscal year ( 2026), the budget year ( 2027).")

    def test_a_guide_that_states_no_boundary_raises(self):
        with self.assertRaises(ValueError):
            estimate_boundary("a document that says nothing about estimates at all")

    def test_no_record_is_ever_for_an_estimated_year(self):
        records, _ = build_records(self.database, load_base_graph(DEFAULT_BASE_GRAPH))
        self.assertTrue(records)
        for node_id, record in records.items():
            self.assertEqual(record["fiscalYear"], 2025, node_id)
            self.assertLess(record["fiscalYear"], self.database["firstEstimateYear"])
            self.assertTrue(record["fiscalYearIsActual"])


class UnitsTests(unittest.TestCase):
    def setUp(self):
        self.database = load_database()

    def test_the_publisher_states_the_unit_in_its_own_guide(self):
        archive = zipfile.ZipFile(DEFAULT_PACKAGE)
        text = guide_text(archive.read("BUDGET-2027-DB/pdf/BUDGET-2027-DB-4.pdf"))
        for quote in (QUOTE_UNITS, QUOTE_PRECISION, QUOTE_TREASURY, QUOTE_TREASURY_DIFFERENCES):
            self.assertIn(quote, text, f"the guide no longer prints: {quote[:60]!r}")

    def test_the_arithmetic_corroborates_thousands(self):
        # Corroborates; it does not replace the publisher's statement.
        rows = self.database["tables"][MEMBER_OUTLAYS]
        agency, _, _, _ = totals_for_year(rows, self.database["lastActualYear"])
        total = sum(agency.values()) * THOUSAND
        self.assertGreater(total, 6.0e12, "FY2025 outlays should be several trillion dollars")
        self.assertLess(total, 8.0e12)


class MatchingTests(unittest.TestCase):
    def setUp(self):
        self.database = load_database()
        self.records, self.stats = build_records(self.database, load_base_graph(DEFAULT_BASE_GRAPH))

    def test_the_join_is_scoped_and_unambiguous(self):
        self.assertGreater(len(self.records), 100)
        self.assertGreater(self.stats["bureaus_matched"], 50)
        self.assertGreater(self.stats["agencies_matched"], 50)

    def test_a_bureau_name_several_agencies_use_claims_nothing(self):
        # This database restates history onto the current account structure, so
        # "Bureau of Labor Statistics" appears under Commerce as well as Labor.
        self.assertGreater(self.stats["refused_bureau_name_used_by_several_agencies"], 0)

    def test_the_one_placement_disagreement_is_refused_not_resolved(self):
        refused = self.stats["refused_node_sits_outside_its_agencys_subtree"]
        names = {r["bureau"] for r in refused}
        self.assertIn("Pension Benefit Guaranty Corporation", names)
        for item in refused:
            self.assertNotIn(item["nodeId"], self.records,
                             "a unit OMB files under a different parent must not be published")

    def test_no_committee_or_court_is_ever_matched(self):
        # Without the type guard OMB's agency "Legislative Branch" reaches the
        # Senate Appropriations Subcommittee on the Legislative Branch.
        node_map = {}
        stack = [load_base_graph(DEFAULT_BASE_GRAPH)]
        while stack:
            node = stack.pop()
            if node.get("id"):
                node_map[node["id"]] = node
            stack.extend([c for c in (node.get("children") or []) if isinstance(c, dict)])
        for node_id in self.records:
            type_text = str(node_map[node_id].get("type") or "").casefold()
            for word in ("committee", "subcommittee", "caucus", "position", "court"):
                self.assertNotIn(word, type_text, f"{node_id} is a {type_text}")

    def test_every_record_names_the_node_it_sits_on(self):
        node_map = {}
        stack = [load_base_graph(DEFAULT_BASE_GRAPH)]
        while stack:
            node = stack.pop()
            if node.get("id"):
                node_map[node["id"]] = node
            stack.extend([c for c in (node.get("children") or []) if isinstance(c, dict)])
        for node_id, record in self.records.items():
            quoted = record["listedBureau"] if record["level"] == "bureau" else record["listedAgency"]
            self.assertEqual(canonical_name_key(quoted),
                             canonical_name_key(node_map[node_id].get("name")))

    def test_a_cgac_code_is_published_only_where_there_is_exactly_one(self):
        for node_id, record in self.records.items():
            count = record["cgacAgencyCodeCount"]
            if count == 1:
                self.assertTrue(record["cgacAgencyCode"], node_id)
            else:
                self.assertIsNone(record["cgacAgencyCode"],
                                  f"{node_id}: {count} codes, so none identifies the unit")
        multi = [r for r in self.records.values() if (r["cgacAgencyCodeCount"] or 0) > 1]
        self.assertTrue(multi, "the Treasury alone carries nine codes; this rule must be doing work")

    def test_every_record_declares_which_rows_it_summed(self):
        for node_id, record in self.records.items():
            self.assertIn("on-budget and off-budget", record["rowSelection"], node_id)

    def test_a_measure_the_package_does_not_carry_is_absent_not_zero(self):
        # The two member files do not cover the same units: the Farm Credit
        # Administration has outlay rows and no budget-authority rows, and
        # defaulting the missing one to 0.0 published a figure that does not
        # exist. The gate caught it; this pins the fix.
        for node_id, record in self.records.items():
            for field in ("outlays", "budgetAuthority"):
                value = record[field]
                self.assertTrue(value is None or value != 0,
                                f"{node_id}.{field} is zero, which is never published here")
            self.assertTrue(record["outlays"] is not None or record["budgetAuthority"] is not None)


class ApplyTests(unittest.TestCase):
    def tree(self):
        return {"id": "root", "name": "Root", "type": "Branch", "children": [
            {"id": "agency", "name": "Department of Energy", "type": "Department",
             "cost_status": "allocated", "resolved_total_amount": 5.0, "children": []}]}

    def record(self, **over):
        base = {"source": "omb_public_budget_database", "nodeName": "Department of Energy",
                "level": "agency", "listedAgency": "Department of Energy", "listedBureau": None,
                "cgacAgencyCode": "089", "fiscalYear": 2025, "fiscalYearIsActual": True,
                "outlays": 1000.0, "budgetAuthority": 2000.0,
                "unitsQuote": QUOTE_UNITS, "precisionNote": QUOTE_PRECISION,
                "treasuryQuote": QUOTE_TREASURY, "package": "BUDGET-2027-DB",
                "documentSha256": "x", "url": "https://www.govinfo.gov/x"}
        base.update(over)
        return {"agency": base}

    def test_a_block_is_published_beside_the_cost(self):
        tree = self.tree()
        stats = apply_omb_budget_evidence(tree, self.record())
        node = tree["children"][0]
        self.assertEqual(stats["applied"], 1)
        self.assertEqual(node["ombBudget"]["outlays"], 1000.0)
        self.assertEqual(node["ombBudget"]["fiscalYear"], 2025)

    def test_nothing_writes_a_cost_or_a_source(self):
        tree = self.tree()
        apply_omb_budget_evidence(tree, self.record())
        node = tree["children"][0]
        self.assertEqual(node["resolved_total_amount"], 5.0)
        self.assertEqual(node["cost_status"], "allocated")
        for field in ("sourceUrls", "sourceTypes", "lastVerified", "verificationMethod"):
            self.assertNotIn(field, node,
                             "a budget account is not evidence that a unit exists")

    def test_an_estimated_year_is_refused(self):
        tree = self.tree()
        stats = apply_omb_budget_evidence(tree, self.record(fiscalYearIsActual=False, fiscalYear=2027))
        self.assertEqual(stats["estimated_year_refused"], 1)
        self.assertNotIn("ombBudget", tree["children"][0])

    def test_a_renamed_node_keeps_nothing(self):
        tree = self.tree()
        tree["children"][0]["name"] = "Department of Widgets"
        stats = apply_omb_budget_evidence(tree, self.record())
        self.assertEqual(stats["stale_name"], 1)
        self.assertNotIn("ombBudget", tree["children"][0])

    def test_a_post_keeps_nothing(self):
        tree = self.tree()
        tree["children"][0]["type"] = "Position"
        stats = apply_omb_budget_evidence(tree, self.record())
        self.assertEqual(stats["is_a_post"], 1)
        self.assertNotIn("ombBudget", tree["children"][0])

    def test_a_figure_equal_to_the_measured_cost_is_refused(self):
        tree = self.tree()
        tree["children"][0]["cost_status"] = "official"
        tree["children"][0]["resolved_total_amount"] = 1000.0
        stats = apply_omb_budget_evidence(tree, self.record())
        self.assertEqual(stats["equals_the_measured_cost"], 1)
        self.assertNotIn("ombBudget", tree["children"][0])

    def test_the_field_is_withdrawn_by_the_evidence_sweep(self):
        self.assertIn("ombBudget", EVIDENCE_OWNED_FIELDS)


class GateMirrorTests(unittest.TestCase):
    def test_the_gates_independent_reader_agrees_with_the_module(self):
        from scripts.validate_published_graph import omb_database

        last_actual, measures, digest = omb_database()
        database = load_database()
        self.assertEqual(last_actual, database["lastActualYear"])
        self.assertEqual(digest, database["sha256"])
        agency, bureau, counts, _cgac = measures["outlays"]
        mine_agency, mine_bureau, _, mine_counts = totals_for_year(database["tables"][MEMBER_OUTLAYS], last_actual)
        self.assertEqual(len(agency), len(mine_agency))
        self.assertEqual(len(bureau), len(mine_bureau))
        for key, value in list(mine_agency.items())[:60]:
            self.assertAlmostEqual(agency[key], value, places=2, msg=key)

    def test_the_gate_does_not_import_the_module_it_checks(self):
        source = (PROJECT_ROOT / "scripts" / "validate_published_graph.py").read_text(encoding="utf-8")
        start = source.index("def omb_database")
        body = source[start:source.index("\n# A post listed", start)]
        self.assertEqual([l for l in body.splitlines() if "import" in l and "data_pipeline" in l], [])


class PublishedGraphTests(unittest.TestCase):
    def setUp(self):
        self.nodes = published_nodes()
        if not self.nodes:
            self.skipTest("output/graph.json is not built")
        self.carrying = [n for n in self.nodes if isinstance(n.get("ombBudget"), dict)]

    def test_the_block_is_published_and_only_on_organisations(self):
        self.assertGreater(len(self.carrying), 100)
        for node in self.carrying:
            type_text = str(node.get("type") or "").casefold()
            for word in ("position", "role", "office holder"):
                self.assertNotIn(word, type_text)

    def test_every_published_block_is_the_last_completed_year(self):
        for node in self.carrying:
            self.assertEqual(node["ombBudget"]["fiscalYear"], 2025, node.get("id"))

    def test_no_published_block_became_a_cost(self):
        for node in self.carrying:
            block = node["ombBudget"]
            amount = node.get("resolved_total_amount")
            if str(node.get("cost_status") or "") == "official" and isinstance(amount, (int, float)):
                self.assertNotEqual(round(float(amount), 2), round(float(block["outlays"] or -1), 2))

    def test_every_block_quotes_the_publisher_on_its_unit_and_precision(self):
        for node in self.carrying:
            self.assertTrue(node["ombBudget"]["unitsQuote"].strip())
            self.assertTrue(node["ombBudget"]["precisionNote"].strip())

    def test_the_evidence_file_and_the_graph_agree(self):
        records = load_omb_budget_evidence()
        self.assertTrue(records)
        published = {n["id"]: n["ombBudget"] for n in self.carrying if n.get("id")}
        for node_id, block in published.items():
            self.assertIn(node_id, records)
            self.assertEqual(block["outlays"], records[node_id]["outlays"])


class GateCorruptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not PUBLISHED.exists():
            raise unittest.SkipTest("output/graph.json is not built")
        cls.graph = json.loads(PUBLISHED.read_text(encoding="utf-8"))

    def run_gate(self, graph):
        from scripts.validate_published_graph import main as gate_main

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "graph.json"
            path.write_text(json.dumps(graph), encoding="utf-8")
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = gate_main(["gate", str(path)])
            return code, buffer.getvalue()

    def corrupt(self, mutate, level="agency"):
        graph = copy.deepcopy(self.graph)
        stack = [graph]
        while stack:
            node = stack.pop()
            block = node.get("ombBudget")
            if isinstance(block, dict) and block.get("level") == level and block.get("outlays"):
                mutate(node)
                return graph
            stack.extend([c for c in (node.get("children") or []) if isinstance(c, dict)])
        self.fail(f"no {level}-level OMB block in the published graph")

    def assert_refused(self, mutate, because, level="agency"):
        code, output = self.run_gate(self.corrupt(mutate, level))
        self.assertEqual(code, 1, f"the gate accepted a graph where {because}")
        self.assertIn("FAIL  an OMB budget figure is a completed year the package really prints", output)

    def test_the_untouched_graph_passes(self):
        code, output = self.run_gate(copy.deepcopy(self.graph))
        self.assertIn("ok    an OMB budget figure is a completed year the package really prints", output)
        self.assertEqual(code, 0, output[-2000:])

    def test_a_year_moved_into_the_estimates(self):
        self.assert_refused(lambda n: n["ombBudget"].update(fiscalYear=2026),
                            "a projection is published as an actual")

    def test_an_altered_outlay_figure(self):
        self.assert_refused(lambda n: n["ombBudget"].update(outlays=12345678.0),
                            "the figure is not what the package prints")

    def test_an_altered_budget_authority_figure(self):
        self.assert_refused(lambda n: n["ombBudget"].update(budgetAuthority=999.0),
                            "the figure is not what the package prints")

    def test_an_agency_swapped_for_another_real_one(self):
        self.assert_refused(lambda n: n["ombBudget"].update(listedAgency="Department of Energy"),
                            "the block names a unit that is not this node")

    def test_an_agency_block_carrying_a_bureau_name(self):
        self.assert_refused(lambda n: n["ombBudget"].update(listedBureau="Internal Revenue Service"),
                            "the panel would print one unit's name beside another's figures")

    def test_a_bureau_block_naming_no_bureau(self):
        self.assert_refused(lambda n: n["ombBudget"].update(listedBureau=None),
                            "a bureau block names no bureau", level="bureau")

    def test_a_node_that_is_a_post(self):
        self.assert_refused(lambda n: n.update(type="Position"),
                            "a post carries a budget account")

    def test_the_units_quote_removed(self):
        self.assert_refused(lambda n: n["ombBudget"].update(unitsQuote=""),
                            "the block does not say how its unit is known")

    def test_the_precision_note_removed(self):
        self.assert_refused(lambda n: n["ombBudget"].update(precisionNote=""),
                            "the block does not state its precision")

    def test_an_altered_document_digest(self):
        self.assert_refused(lambda n: n["ombBudget"].update(documentSha256="0" * 64),
                            "the block cannot be tied to the committed bytes")

    def test_the_row_selection_removed(self):
        self.assert_refused(lambda n: n["ombBudget"].update(rowSelection=""),
                            "the figure's selection rule is undeclared")

    def test_a_cgac_code_invented_for_a_multi_code_agency(self):
        # The CGAC column is per ACCOUNT. OMB's "Agency" groups several
        # Treasury entities: the Department of the Treasury carries nine codes
        # and the Legislative Branch twenty-two, so any single code published
        # for them is an identifier the file never assigns to the unit. The
        # first version took the first one seen.
        graph = copy.deepcopy(self.graph)
        stack = [graph]
        while stack:
            node = stack.pop()
            block = node.get("ombBudget")
            if isinstance(block, dict) and (block.get("cgacAgencyCodeCount") or 0) > 1:
                block["cgacAgencyCode"] = "020"
                code, output = self.run_gate(graph)
                self.assertEqual(code, 1)
                self.assertIn("FAIL  an OMB budget figure is a completed year the package really prints", output)
                return
            stack.extend([c for c in (node.get("children") or []) if isinstance(c, dict)])
        self.skipTest("no multi-code agency in the published graph")

    def test_a_falsified_cgac_code_count(self):
        graph = copy.deepcopy(self.graph)
        stack = [graph]
        while stack:
            node = stack.pop()
            block = node.get("ombBudget")
            if isinstance(block, dict) and (block.get("cgacAgencyCodeCount") or 0) > 1:
                block["cgacAgencyCodeCount"] = 1
                code, output = self.run_gate(graph)
                self.assertEqual(code, 1)
                return
            stack.extend([c for c in (node.get("children") or []) if isinstance(c, dict)])
        self.skipTest("no multi-code agency in the published graph")

    def test_a_url_off_govinfo(self):
        self.assert_refused(lambda n: n["ombBudget"].update(url="https://example.com/budget"),
                            "the citation does not point at the package")


if __name__ == "__main__":
    unittest.main()
