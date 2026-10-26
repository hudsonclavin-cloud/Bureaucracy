"""The government's own lists reconciled against the graph: every unmatched
entry of the five lists carries an accepted disposition or is counted in the
gap, the dispositions re-adjudicate against the committed lists in both
directions, and the committed document is what the script renders."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT, PROJECT_ROOT / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from data_pipeline.verification import list_dispositions as ld  # noqa: E402
from scripts.report_list_reconciliation import distinct_addable, gap_terms, render  # noqa: E402

GRAPH = PROJECT_ROOT / "output" / "graph.json"
DOC = PROJECT_ROOT / "docs" / "LIST_RECONCILIATION.md"


class _Shared:
    graph = None
    lists = None
    table = None
    result = None

    @classmethod
    def load(cls):
        if cls.graph is None:
            if not GRAPH.exists():
                raise unittest.SkipTest("no published graph")
            cls.graph = json.loads(GRAPH.read_text(encoding="utf-8"))
            cls.lists = ld.collect_lists(cls.graph)
            cls.table = ld.load_table()
            cls.result = ld.adjudicate(cls.graph, cls.table, cls.lists)


class ListTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _Shared.load()

    def test_the_five_lists_are_read_and_the_counts_add_up(self):
        self.assertEqual(set(_Shared.lists), set(ld.LISTS))
        for list_id, item in _Shared.lists.items():
            with self.subTest(list=list_id):
                self.assertGreater(len(item["entries"]), 0)
                self.assertEqual(item["matched"] + len(item["unmatched"]), len(item["entries"]))
                for entry in item["unmatched"]:
                    self.assertIn(entry, item["entries"])

    def test_every_row_is_accepted_and_every_unmatched_entry_disposed(self):
        self.assertEqual(_Shared.result["refused"], [], _Shared.result["refused"])
        for item in _Shared.result["lists"]:
            with self.subTest(list=item["id"]):
                undisposed = [e for e in item["unresolved"] if e not in item["rows"]]
                self.assertEqual(undisposed, [], "an unmatched entry with no disposition at all")
                self.assertEqual(item["curatedUnresolved"], [])

    def test_the_gap_is_one_number_and_small(self):
        terms = gap_terms(_Shared.result)
        self.assertEqual(terms["gap"], terms["unresolvedEntries"] + terms["addableUnits"] + terms["curatedUnresolved"])
        self.assertLessEqual(terms["unresolvedEntries"], 3, "the two §13.6 unknowns, on two lists")
        self.assertEqual(terms["curatedUnresolved"], 0)
        # one unit named by three lists counts once
        addable = distinct_addable(_Shared.result)
        self.assertEqual(len(addable), terms["addableUnits"])
        # one unit named by two lists counts once (Amtrak did until it was
        # disposed of as non-federal; the rule is pinned on a synthetic result)
        synthetic = {"lists": [
            {"id": "a", "addable": ["X Agency"], "rows": {"X Agency": {"unitKey": "x"}}},
            {"id": "b", "addable": ["Y :: X Agency Inc"], "rows": {"Y :: X Agency Inc": {"unitKey": "x"}}},
        ]}
        self.assertEqual({k: len(v) for k, v in distinct_addable(synthetic).items()}, {"x": 2})

    def test_the_vocabulary_is_closed_and_every_kind_declares_its_count(self):
        for kind, spec in ld.KINDS.items():
            self.assertIn(spec[3], (ld.KIND_RECONCILED, ld.KIND_ADDABLE, ld.KIND_UNRESOLVED), kind)
        self.assertEqual(ld.KINDS["unsure"][3], ld.KIND_UNRESOLVED)
        self.assertEqual(ld.KINDS["unit_the_list_names_not_added"][3], ld.KIND_ADDABLE)
        for row in _Shared.table["entries"]:
            self.assertIn(row["disposition"], ld.KINDS)
        for row in _Shared.table["curatedNames"]:
            self.assertIn(row["disposition"], ld.CURATED_NAME_KINDS)


class ReAdjudicationTests(unittest.TestCase):
    """The table proposes and the lists decide: each corruption is refused."""

    @classmethod
    def setUpClass(cls):
        _Shared.load()

    def _run(self, mutate):
        table = copy.deepcopy(_Shared.table)
        mutate(table)
        return ld.adjudicate(_Shared.graph, table, _Shared.lists)

    def _row(self, table, list_id, kind=None, has=None):
        for row in table["entries"]:
            if row["list"] == list_id and (kind is None or row["disposition"] == kind) and (has is None or has in row):
                return row
        raise AssertionError(f"no row for {list_id} {kind} {has}")

    def test_an_entry_the_list_does_not_print_is_refused(self):
        def mutate(table):
            self._row(table, ld.LIST_GOVMAN)["entry"] = "Ministry of Silly Walks"
        refused = self._run(mutate)["refused"]
        self.assertTrue(any("does not print this entry" in r["reason"] for r in refused), refused)

    def test_a_disposition_for_an_entry_that_reaches_a_node_is_stale(self):
        def mutate(table):
            table["entries"].append({"list": ld.LIST_GOVMAN, "entry": "Department of Energy", "disposition": "scaffolding", "basis": "x"})
        refused = self._run(mutate)["refused"]
        self.assertTrue(any("stale" in r["reason"] for r in refused), refused)

    def test_an_unknown_kind_a_missing_basis_and_a_duplicate_are_refused(self):
        def unknown(table):
            self._row(table, ld.LIST_FR)["disposition"] = "vibes"
        def no_basis(table):
            self._row(table, ld.LIST_FR)["basis"] = ""
        def duplicate(table):
            table["entries"].append(dict(self._row(table, ld.LIST_FR)))
        self.assertTrue(any("vocabulary" in r["reason"] for r in self._run(unknown)["refused"]))
        self.assertTrue(any("no basis" in r["reason"] for r in self._run(no_basis)["refused"]))
        self.assertTrue(any("second row" in r["reason"] for r in self._run(duplicate)["refused"]))

    def test_a_node_that_is_missing_or_of_the_wrong_kind_is_refused(self):
        def missing(table):
            self._row(table, ld.LIST_FR, "names_a_node_under_another_wording")["nodeId"] = "no-such-node"
        def post_for_org(table):
            self._row(table, ld.LIST_FR, "names_a_node_under_another_wording")["nodeId"] = "exec-dept-dol-inspector-general"
        def org_for_post(table):
            self._row(table, ld.LIST_PLUM, "carried_as_a_post")["nodeId"] = "exec-dept-dol"
        def no_node(table):
            del self._row(table, ld.LIST_FR, "predecessor_of_a_node")["nodeId"]
        self.assertTrue(any("not in the graph" in r["reason"] for r in self._run(missing)["refused"]))
        self.assertTrue(any("which is a post" in r["reason"] for r in self._run(post_for_org)["refused"]))
        self.assertTrue(any("not a post" in r["reason"] for r in self._run(org_for_post)["refused"]))
        self.assertTrue(any("needs nodeId" in r["reason"] for r in self._run(no_node)["refused"]))

    def test_a_parent_the_list_contradicts_is_refused_unless_the_row_disputes_it(self):
        def wrong_parent(table):
            row = self._row(table, ld.LIST_FR, "unit_beneath_a_node_not_drawn")
            # pick a row whose directory parent reaches a node and point it elsewhere
            for r in table["entries"]:
                if r["list"] == ld.LIST_FR and r["disposition"] == "unit_beneath_a_node_not_drawn" and r["entry"] == "Advocacy and Outreach Office":
                    row = r
            row["parentNodeId"] = "exec-dept-doe"
        def disputed_without_saying_so(table):
            for r in table["entries"]:
                if r["list"] == ld.LIST_FR and r["entry"] == "National Civilian Community Corps":
                    r["basis"] = "An AmeriCorps programme."
        def no_parent(table):
            del self._row(table, ld.LIST_FR, "unit_beneath_a_node_not_drawn")["parentNodeId"]
        self.assertTrue(any("not the node the list's own parent entry reaches" in r["reason"] for r in self._run(wrong_parent)["refused"]))
        self.assertTrue(any("parentOverridesList needs a basis" in r["reason"] for r in self._run(disputed_without_saying_so)["refused"]))
        self.assertTrue(any("needs parentNodeId" in r["reason"] for r in self._run(no_parent)["refused"]))

    def test_a_quote_the_list_does_not_print_is_refused_and_so_is_a_quote_on_the_wrong_kind(self):
        def bad_quote(table):
            self._row(table, ld.LIST_FR, "former_body", has="quote")["quote"] = "The Commission lives on forever."
        def quote_on_scaffolding(table):
            self._row(table, ld.LIST_GOVMAN, "scaffolding")["quote"] = "Bureaus"
        self.assertTrue(any("quote is not in the list's own text" in r["reason"] for r in self._run(bad_quote)["refused"]))
        self.assertTrue(any("takes no quote" in r["reason"] for r in self._run(quote_on_scaffolding)["refused"]))

    def test_a_curated_name_row_is_refused_for_a_renamed_node_or_a_wrong_list(self):
        def renamed(table):
            table["curatedNames"][0]["name"] = "Something Else"
        def wrong_list(table):
            table["curatedNames"][0]["list"] = ld.LIST_GOVMAN
        def unknown_kind(table):
            table["curatedNames"][0]["disposition"] = "shrug"
        self.assertTrue(any("another name" in r["reason"] for r in self._run(renamed)["refused"]))
        self.assertTrue(any("reconciled against the two committee lists" in r["reason"] for r in self._run(wrong_list)["refused"]))
        self.assertTrue(any("curated-name vocabulary" in r["reason"] for r in self._run(unknown_kind)["refused"]))

    def test_removing_a_row_moves_its_entry_into_the_gap(self):
        before = gap_terms(_Shared.result)["gap"]
        def drop(table):
            table["entries"] = [r for r in table["entries"] if not (r["list"] == ld.LIST_GOVMAN and r["entry"] == "Bureaus")]
        after = gap_terms(self._run(drop))["gap"]
        self.assertEqual(after, before + 1)


class DocumentTests(unittest.TestCase):
    def test_the_committed_document_is_what_the_script_renders(self):
        _Shared.load()
        if not DOC.exists():
            self.skipTest("no committed document")
        self.assertEqual(DOC.read_text(encoding="utf-8"), render(_Shared.result))
        self.assertIn("criterion 4(a) gap:", render(_Shared.result))


if __name__ == "__main__":
    unittest.main()
