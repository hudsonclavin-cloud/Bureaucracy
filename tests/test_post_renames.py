"""The posts renamed to a title a committed official document prints
(`scripts/rename_posts_to_printed_titles.py`, `data/curation/post_renames.json`,
since 2026-10-07).

Pinned in both directions: every row applies to the names it was written
against and is idempotent on the curated file; a doctored fixture, a stale
name, a moved node, a changed qualifier, a wrong singular, a class over-counted
and every static refusal each leave the node alone.
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from data_pipeline.exporter.build_graph import DEFAULT_BASE_GRAPH, index_tree, load_base_graph
from scripts import rename_posts_to_printed_titles as writer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEA = "exec-dept-defense-sf-senior-enlisted-advisor"
USTR = (
    "exec-eop-ustr-deputy-ustr-wto-multilateral-affairs",
    "exec-eop-ustr-deputy-ustr-americas",
    "exec-eop-ustr-deputy-ustr-asia",
)
NOTE = "tests/fixtures/uscode/pay_schedules_5_usc_5332.html"
SCHEDULE = "tests/fixtures/uscode/exec_schedule_5314.html"
COMPOSING = "tests/fixtures/uscode/ustr_19_usc_2171_govinfo2024.html"
EXPORT = "tests/fixtures/opm/plum/escs_pbpub_download-data.csv"
#: The rows licensed by a title OPM's current PLUM export prints (2026-10-08).
EXPORT_ROWS = {
    "exec-dept-doe-sc-associate-director-advanced-scientific-computing-research":
        "Associate Director, Office of Advanced Scientific Computing Research",
    "exec-dept-doe-sc-associate-director-basic-energy-sciences": "Associate Director, Office of Basic Energy Sciences",
    "exec-dept-doe-sc-associate-director-biological-environmental-research":
        "Associate Director, Office of Biological and Environmental Research",
    "exec-dept-doe-sc-associate-director-fusion-energy-sciences": "Associate Director, Office of Fusion Energy Sciences",
    "exec-dept-doe-sc-associate-director-high-energy-physics": "Associate Director, Office of High Energy Physics",
    "exec-dept-doe-sc-associate-director-nuclear-physics": "Associate Director, Office of Nuclear Physics",
    "exec-dept-dhs-cisa-executive-assistant-director-emergency-communications":
        "Executive Assistant Director for Emergency Communications",
    "exec-dept-treasury-bep-director-bep": "Director, Bureau of Engraving and Printing",
    "exec-dept-treasury-fiscal-commissioner-fiscal-service": "Commissioner, Bureau of the Fiscal Service",
}
BEP = "exec-dept-treasury-bep-director-bep"


def _rows():
    return writer.load_table(writer.DEFAULT_TABLE)


def _unrenamed_tree(rows=None):
    """The real curated file with every row's node set back to the name the
    row was written against -- the state the writer acted on."""
    tree = copy.deepcopy(load_base_graph(DEFAULT_BASE_GRAPH))
    node_map, _ = index_tree(tree)
    for row in rows or _rows():
        node = node_map[row["id"]]
        node["name"] = row["from"]
        for key in ("nameSource", "nameSourceDetail", "nameMatchedText"):
            node.pop(key, None)
    return tree


def _by_id(results):
    return {r["id"]: r for r in results}


class _TempFixtures:
    """A project root holding copies of the three fixtures, so a test can
    doctor one without touching the committed bytes."""

    def __enter__(self):
        self.dir = Path(tempfile.mkdtemp())
        for rel in (NOTE, SCHEDULE, COMPOSING, EXPORT):
            for suffix in ("", ".meta.json"):
                source = PROJECT_ROOT / (rel + suffix)
                target = self.dir / (rel + suffix)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        return self

    def __exit__(self, *exc):
        shutil.rmtree(self.dir, ignore_errors=True)

    def doctor(self, rel, old, new, *, fix_digest=True):
        path = self.dir / rel
        raw = path.read_text(encoding="utf-8")
        assert old in raw, old
        path.write_text(raw.replace(old, new), encoding="utf-8")
        if fix_digest:
            meta_path = self.dir / (rel + ".meta.json")
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            meta_path.write_text(json.dumps(meta), encoding="utf-8")


class TableTests(unittest.TestCase):
    def test_the_table_names_the_rows_the_owner_decided(self):
        rows = _by_id(_rows())
        self.assertEqual({SEA, *USTR, *EXPORT_ROWS}, set(rows))
        for node_id, proposed in EXPORT_ROWS.items():
            self.assertEqual(writer.LICENCE_CURRENT_EXPORT, rows[node_id]["licence"])
            self.assertEqual(proposed, rows[node_id]["to"])
            self.assertEqual(EXPORT, rows[node_id]["fixture"])
        self.assertEqual("Chief Master Sergeant of the Space Force", rows[SEA]["to"])
        for node_id in USTR:
            row = rows[node_id]
            self.assertEqual("Deputy United States Trade Representatives (3)", row["printed"])
            self.assertEqual("Deputy United States Trade Representative", row["singular"])
            # Only the abbreviation is spelled out; the qualifier is the graph's own.
            self.assertEqual(row["from"].split(" — ", 1)[1], row["to"].split(" — ", 1)[1])

    def test_the_curated_file_carries_every_rename_and_a_rerun_is_a_no_op(self):
        tree = copy.deepcopy(load_base_graph(DEFAULT_BASE_GRAPH))
        node_map, _ = index_tree(tree)
        for row in _rows():
            self.assertEqual(row["to"], node_map[row["id"]]["name"])
        results = writer.adjudicate(tree, _rows(), apply=True)
        self.assertEqual({"already_applied"}, {r["reason"] for r in results})
        self.assertEqual(load_base_graph(DEFAULT_BASE_GRAPH), tree)


class ApplyTests(unittest.TestCase):
    def test_every_row_applies_to_the_name_it_was_written_against(self):
        tree = _unrenamed_tree()
        results = _by_id(writer.adjudicate(tree, _rows(), apply=True))
        node_map, _ = index_tree(tree)
        for row in _rows():
            with self.subTest(row["id"]):
                self.assertTrue(results[row["id"]]["applied"], results[row["id"]])
                node = node_map[row["id"]]
                self.assertEqual(row["to"], node["name"])
                self.assertEqual(writer.NAME_SOURCES[row["licence"]], node["nameSource"])
                self.assertEqual(row["printed"], node["nameMatchedText"])
                expected_host = ("https://escs.opm.gov/" if row["licence"] == writer.LICENCE_CURRENT_EXPORT
                                 else "https://uscode.house.gov/")
                self.assertTrue(node["nameSourceDetail"].startswith(expected_host))
                # It only renames: type, children and description are untouched.
                self.assertEqual("Position", node["type"])
                self.assertEqual([], node.get("children") or [])

    def test_a_dry_run_decides_and_writes_nothing(self):
        tree = _unrenamed_tree()
        before = copy.deepcopy(tree)
        results = writer.adjudicate(tree, _rows(), apply=False)
        self.assertTrue(all(r["applied"] for r in results))
        self.assertEqual(before, tree)

    def test_it_never_reparents_retypes_or_removes(self):
        tree = _unrenamed_tree()
        before_map, before_parents = index_tree(copy.deepcopy(tree))
        writer.adjudicate(tree, _rows(), apply=True)
        after_map, after_parents = index_tree(tree)
        self.assertEqual(set(before_map), set(after_map))
        self.assertEqual(before_parents, after_parents)
        self.assertEqual({k: v.get("type") for k, v in before_map.items()},
                         {k: v.get("type") for k, v in after_map.items()})


class RefusalTests(unittest.TestCase):
    def _one(self, row_id, mutate_row=None, mutate_tree=None, project_root=writer.PROJECT_ROOT, rows=None):
        rows = copy.deepcopy(rows or _rows())
        tree = _unrenamed_tree(rows)
        if mutate_tree:
            mutate_tree(index_tree(tree)[0], tree)
        if mutate_row:
            mutate_row(next(r for r in rows if r["id"] == row_id))
        before = copy.deepcopy(tree)
        result = _by_id(writer.adjudicate(tree, rows, apply=True, project_root=project_root))[row_id]
        self.assertFalse(result["applied"], result)
        self.assertEqual(index_tree(before)[0][row_id]["name"], index_tree(tree)[0][row_id]["name"])
        return result["reason"]

    def test_a_stale_current_name_refuses_the_row(self):
        def rename(node_map, _tree):
            node_map[SEA]["name"] = "Senior Enlisted Leader"
        self.assertEqual("curated_name_has_changed", self._one(SEA, mutate_tree=rename))

    def test_a_moved_node_refuses_the_row(self):
        def move(node_map, _tree):
            node = node_map[USTR[1]]
            node_map["exec-eop-ustr"]["children"].remove(node)
            node_map["exec-dept-defense-sf"]["children"].append(node)
        self.assertEqual("node_has_moved", self._one(USTR[1], mutate_tree=move))

    def test_a_node_that_is_not_a_post_refuses_the_row(self):
        def retype(node_map, _tree):
            node_map[SEA]["type"] = "Office"
        self.assertEqual("node_is_not_a_post", self._one(SEA, mutate_tree=retype))

    def test_a_sibling_collision_refuses_the_row(self):
        def twin(node_map, _tree):
            node_map["exec-dept-defense-sf"]["children"].append(
                {"id": "twin", "name": "Chief Master Sergeant of the Space Force", "type": "Position", "children": []})
        self.assertEqual("proposed_name_collides_with_a_sibling", self._one(SEA, mutate_tree=twin))

    def test_static_refusals(self):
        self.assertEqual("rename_is_a_no_op",
                         self._one(SEA, mutate_row=lambda r: r.update(to="Senior Enlisted Advisor (USSF)", printed="Senior Enlisted Advisor (USSF)")))
        self.assertEqual("proposed_name_too_short", self._one(SEA, mutate_row=lambda r: r.update(to="Sergeant")))
        self.assertEqual("proposed_name_is_generic", self._one(SEA, mutate_row=lambda r: r.update(to="Chief of Staff")))
        self.assertEqual("row_states_no_basis", self._one(SEA, mutate_row=lambda r: r.update(basis="")))
        self.assertEqual("unknown_licence", self._one(SEA, mutate_row=lambda r: r.update(licence="a_hunch")))
        self.assertEqual("row_is_incomplete", self._one(SEA, mutate_row=lambda r: r.pop("printed")))

    def test_the_footnote_must_print_the_title_and_the_name_must_be_it(self):
        self.assertEqual("document_does_not_print_the_title",
                         self._one(SEA, mutate_row=lambda r: r.update(printed="Chief Master Sergeant of the Orbital Force",
                                                                     to="Chief Master Sergeant of the Orbital Force")))
        self.assertEqual("proposed_name_is_not_the_printed_title",
                         self._one(SEA, mutate_row=lambda r: r.update(to="Chief Master Sergeant, Space Force")))

    def test_a_doctored_footnote_refuses_the_row(self):
        with _TempFixtures() as fx:
            fx.doctor(NOTE, "Chief Master Sergeant of the Space Force", "Chief Master Sergeant of the Orbital Force")
            self.assertEqual("document_does_not_print_the_title", self._one(SEA, project_root=fx.dir))
        with _TempFixtures() as fx:
            # The same edit with the digest left alone: the bytes are not the
            # bytes that were served, and nothing is read from them.
            fx.doctor(NOTE, "Chief Master Sergeant of the Space Force", "Chief Master Sergeant of the Orbital Force",
                      fix_digest=False)
            self.assertEqual("document_unreadable", self._one(SEA, project_root=fx.dir))

    def test_a_doctored_schedule_or_composing_section_refuses_the_row(self):
        with _TempFixtures() as fx:
            fx.doctor(SCHEDULE, "Deputy United States Trade Representatives (3)", "Deputy Trade Envoys (3)")
            self.assertEqual("document_does_not_print_the_title", self._one(USTR[0], project_root=fx.dir))
        with _TempFixtures() as fx:
            fx.doctor(COMPOSING, "There shall be in the Office three Deputy United States Trade Representatives",
                      "There shall be in the Office two Deputy United States Trade Representatives")
            self.assertEqual("composing_quote_not_in_operative_text", self._one(USTR[0], project_root=fx.dir))
        with _TempFixtures() as fx:
            fx.doctor(SCHEDULE, "Deputy United States Trade Representatives (3)", "Deputy Trade Envoys (3)",
                      fix_digest=False)
            self.assertEqual("document_unreadable", self._one(USTR[0], project_root=fx.dir))

    def test_the_counted_class_rules(self):
        # The singular must be the class title's plural less one trailing "s".
        self.assertEqual("singular_is_not_the_class_titles_singular",
                         self._one(USTR[2], mutate_row=lambda r: r.update(singular="Deputy Trade Representative")))
        # The class title must state a count.
        self.assertEqual("printed_title_states_no_count",
                         self._one(USTR[2], mutate_row=lambda r: r.update(printed="Deputy United States Trade Representatives")))
        # The proposed name must begin with the singular, whole.
        self.assertEqual("proposed_name_does_not_begin_with_the_singular",
                         self._one(USTR[2], mutate_row=lambda r: r.update(to="Deputy U.S. Trade Representative — Asia")))
        # The rename may change only the office half: the qualifier is the node's own.
        self.assertEqual("qualifier_is_not_the_nodes_own",
                         self._one(USTR[2], mutate_row=lambda r: r.update(to="Deputy United States Trade Representative — Asia & Pacific")))
        self.assertEqual("qualifier_is_not_the_nodes_own",
                         self._one(USTR[2], mutate_row=lambda r: r.update(to="Deputy United States Trade Representative for Asia")))
        # A counted-class rename needs the section that composes the class.
        self.assertEqual("row_names_no_composing_section",
                         self._one(USTR[2], mutate_row=lambda r: r.pop("composedBy")))

    def test_more_rows_than_the_class_counts_refuses_them_all(self):
        rows = _rows()
        extra = dict(next(r for r in rows if r["id"] == USTR[0]), id="exec-eop-ustr-chief-of-staff",
                     **{"from": "Chief of Staff", "to": "Deputy United States Trade Representative — Staff"})
        rows = rows + [extra]
        tree = _unrenamed_tree(rows[:-1])
        results = _by_id(writer.adjudicate(tree, rows, apply=False))
        for node_id in USTR + ("exec-eop-ustr-chief-of-staff",):
            self.assertEqual("more_rows_than_the_class_counts", results[node_id]["reason"])
        self.assertTrue(results[SEA]["applied"])


class CurrentExportLicenceTests(unittest.TestCase):
    """The third licence, since 2026-10-08: a title OPM's committed current
    PLUM export prints on one live listing, pinned in both directions."""

    def _one(self, row_id, mutate_row=None, project_root=writer.PROJECT_ROOT):
        rows = copy.deepcopy(_rows())
        tree = _unrenamed_tree(rows)
        if mutate_row:
            mutate_row(next(r for r in rows if r["id"] == row_id))
        before = copy.deepcopy(tree)
        result = _by_id(writer.adjudicate(tree, rows, apply=True, project_root=project_root))[row_id]
        if not result["applied"]:
            self.assertEqual(index_tree(before)[0][row_id]["name"], index_tree(tree)[0][row_id]["name"])
        return result

    def test_every_export_row_applies_and_cites_the_committed_export(self):
        for node_id in EXPORT_ROWS:
            with self.subTest(node_id):
                result = self._one(node_id)
                self.assertTrue(result["applied"], result)
                self.assertEqual(writer.LICENCE_CURRENT_EXPORT, result["licence"])
                meta = json.loads((PROJECT_ROOT / (EXPORT + ".meta.json")).read_text(encoding="utf-8"))
                self.assertEqual(meta["sha256"], result["sha256"])

    def test_the_casing_is_the_reviewers_but_the_words_are_the_exports(self):
        def recase(row):
            row["to"] = row["to"].upper()
        self.assertTrue(self._one(BEP, recase)["applied"])

        def other_words(row):
            row["to"] = "Director, Bureau of Engraving"
        self.assertEqual("proposed_name_is_not_the_printed_title", self._one(BEP, other_words)["reason"])

    def test_a_title_the_export_does_not_print_under_that_filing_refuses(self):
        def other_title(row):
            row["printed"] = "DIRECTOR, BUREAU OF ENGRAVING"
            row["to"] = "Director, Bureau of Engraving"
        self.assertEqual("document_does_not_print_the_title", self._one(BEP, other_title)["reason"])

        def other_organization(row):
            row["organization"] = "GENERAL COUNSEL"
        self.assertEqual("document_does_not_print_the_title", self._one(BEP, other_organization)["reason"])

        def other_agency(row):
            row["agency"] = "DEPARTMENT OF COMMERCE"
        self.assertEqual("document_does_not_print_the_title", self._one(BEP, other_agency)["reason"])

        def no_filing(row):
            row.pop("organization")
        self.assertEqual("row_is_incomplete", self._one(BEP, no_filing)["reason"])

    def test_a_doctored_export_refuses_the_row(self):
        with _TempFixtures() as fixtures:
            fixtures.doctor(EXPORT, "DIRECTOR, BUREAU OF ENGRAVING AND PRINTING", "DIRECTOR, BUREAU OF PRINTING",
                            fix_digest=False)
            self.assertEqual("document_unreadable", self._one(BEP, project_root=fixtures.dir)["reason"])
        with _TempFixtures() as fixtures:
            # A re-hashed edit is read, and the title it no longer prints refuses.
            fixtures.doctor(EXPORT, "DIRECTOR, BUREAU OF ENGRAVING AND PRINTING", "DIRECTOR, BUREAU OF PRINTING")
            self.assertEqual("document_does_not_print_the_title", self._one(BEP, project_root=fixtures.dir)["reason"])

    def _synthetic(self, lines):
        """A project root holding a small export of the committed file's shape,
        with a person's name planted in every incumbent column."""
        directory = Path(tempfile.mkdtemp())
        path = directory / EXPORT
        path.parent.mkdir(parents=True, exist_ok=True)
        header = ('Agency,Organization,Position Title,Position Status,Appointment Type,Expiration Date,'
                  '"Level, Grade, or Pay",Duty Location,First Name,Last Name,Individual Unique ID,Pay Plan,Tenure,Begin Date,Vacate Date')
        body = ("\ufeff" + header + "\r\n" + "\r\n".join(lines) + "\r\n").encode("utf-8")
        path.write_bytes(body)
        (directory / (EXPORT + ".meta.json")).write_text(json.dumps({
            "fetched_at": "2026-09-21T03:02:16Z", "url": "https://escs.opm.gov/escs-net/api/pbpub/download-data",
            "final_url": "https://escs.opm.gov/escs-net/api/pbpub/download-data", "status": 200,
            "sha256": hashlib.sha256(body).hexdigest(), "error": None}), encoding="utf-8")
        return directory

    @staticmethod
    def _line(status, level, plan="ES"):
        return ('DEPARTMENT OF THE TREASURY,BUREAU OF ENGRAVING AND PRINTING,"DIRECTOR, BUREAU OF ENGRAVING AND PRINTING",'
                f'{status},CA,,"{level}","Washington, DC",SENTINELNAME,SENTINELNAME,SENTINELNAME9,{plan},5.0,01/21/2025,')

    def test_a_historical_row_alone_licenses_nothing(self):
        root = self._synthetic([self._line("Historical", "$228,000")])
        try:
            self.assertEqual("document_does_not_print_the_title", self._one(BEP, project_root=root)["reason"])
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_a_title_listed_on_two_listings_licenses_nothing(self):
        root = self._synthetic([self._line("Filled", "$228,000"), self._line("Vacant", "$197,200")])
        try:
            self.assertEqual("export_lists_the_title_more_than_once", self._one(BEP, project_root=root)["reason"])
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_one_listing_folded_from_several_rows_licenses_and_no_name_is_read(self):
        root = self._synthetic([self._line("Filled", "$228,000"), self._line("Filled", "$228,000")])
        try:
            rows = copy.deepcopy(_rows())
            tree = _unrenamed_tree(rows)
            results = writer.adjudicate(tree, rows, apply=True, project_root=root)
            result = _by_id(results)[BEP]
            self.assertTrue(result["applied"], result)
            self.assertNotIn("SENTINELNAME", json.dumps(results))
            self.assertNotIn("SENTINELNAME", json.dumps(index_tree(tree)[0][BEP]))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_the_static_refusals_hold_for_this_licence_too(self):
        def stale(row):
            row["from"] = "Director, Bureau of Engraving & Printing (old)"
        self.assertEqual("curated_name_has_changed", self._one(BEP, stale)["reason"])

        def moved(row):
            row["parentId"] = "exec-dept-treasury"
        self.assertEqual("node_has_moved", self._one(BEP, moved)["reason"])


class NoPersonTests(unittest.TestCase):
    def test_the_writer_reads_no_persons_name(self):
        source = (PROJECT_ROOT / "scripts" / "rename_posts_to_printed_titles.py").read_text(encoding="utf-8")
        for marker in ("First Name", "Last Name", "Individual Unique ID", "NameColumnValue", "whitehouse"):
            self.assertNotIn(marker, source)
        # The current export is read only through plum_current's READ_COLUMNS
        # projection; the writer opens no CSV of its own.
        self.assertIn("load_plum_export", source)
        self.assertNotIn("import csv", source)


if __name__ == "__main__":
    unittest.main()
