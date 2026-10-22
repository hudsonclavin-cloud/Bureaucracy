"""The explained blank: an organisation left with only an estimate names the
money documents this project holds and says whether any prints its name.

Both directions are pinned: the module stamps exactly the documents and the
name hits the committed fixtures give; the gate re-derives every universe with
its own readers (stdlib only), the two agree name for name, and every
corruption of a block is refused.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT, PROJECT_ROOT / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import validate_published_graph as gate  # noqa: E402
from data_pipeline.exporter.build_graph import SHARED_DOCUMENT_BLOCKS, MINIMAL_GRAPH_FIELDS, index_tree  # noqa: E402
from data_pipeline.verification import cost_no_document as cnd  # noqa: E402

PUBLISHED = PROJECT_ROOT / "output" / "graph.json"
RECORD_DATE = "2026-08-31"


def org(node_id, name, **fields):
    return {"id": node_id, "name": name, "type": "Division", "children": [], "cost_status": "allocated",
            "resolved_total_amount": 100.0, **fields}


def tree(*children):
    return {"id": "the-constitution-of-the-united-states", "name": "Root", "type": "Foundation",
            "__budgetSummary": {"record_date": RECORD_DATE},
            "children": [{"id": "branch", "name": "A Branch", "type": "Branch", "cost_status": "official",
                          "resolved_total_amount": 1000.0, "children": list(children)}]}


class UniverseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = cnd.document_universes(RECORD_DATE)
        cls.mirror = gate.cost_no_document_universes({"__budgetSummary": {"record_date": RECORD_DATE}})

    def test_seven_documents_in_the_declared_order(self):
        self.assertEqual([u["id"] for u in self.module], [
            "monthly_treasury_statement", "treasury_combined_statement_c01", "omb_public_budget_database",
            "usaspending_agency_lists", "treasury_statement_of_net_cost", "house_statement_of_disbursements",
            "senate_secretary_report"])
        self.assertEqual([u["id"] for u in self.mirror], [u["id"] for u in self.module])

    def test_the_gate_s_universes_equal_the_module_s_name_for_name(self):
        for ours, theirs in zip(self.module, self.mirror):
            with self.subTest(document=ours["id"]):
                self.assertEqual(ours["version"], theirs["version"])
                self.assertEqual(ours["sha256"], theirs["sha256"])
                self.assertEqual(ours["names"], theirs["names"])
                self.assertEqual(gate.COST_NO_DOCUMENT_LABELS[ours["id"]], ours["document"])
        self.assertEqual(gate.COST_NO_DOCUMENT_KIND_NONE, cnd.KIND_NONE)
        self.assertEqual(gate.COST_NO_DOCUMENT_KIND_NAMED, cnd.KIND_NAMED)
        self.assertEqual(gate.COST_NO_DOCUMENT_SOURCED_FIGURES, cnd.SOURCED_FIGURES_BESIDE)

    def test_the_universes_carry_what_the_documents_print(self):
        by_id = {u["id"]: u for u in self.module}
        self.assertIn("department of veterans affairs", by_id["monthly_treasury_statement"]["names"])
        self.assertIn("board of veterans appeals", by_id["omb_public_budget_database"]["names"])
        self.assertIn("government accountability office", by_id["usaspending_agency_lists"]["names"])
        self.assertIn("department of transportation", by_id["treasury_statement_of_net_cost"]["names"])
        self.assertIn("office of the speaker", by_id["house_statement_of_disbursements"]["names"])
        self.assertIn("agriculture nutrition and forestry", by_id["senate_secretary_report"]["names"])
        self.assertNotIn("fiscal year 2026 clerk of the house", by_id["house_statement_of_disbursements"]["names"],
                         "the year prefix is the file's, not the unit's")

    def test_the_field_is_in_the_viewer_copy_and_its_documents_are_shared(self):
        self.assertIn(cnd.FIELD, MINIMAL_GRAPH_FIELDS)
        self.assertIn(cnd.FIELD, SHARED_DOCUMENT_BLOCKS)


class ApplyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.universes = cnd.document_universes(RECORD_DATE)

    def _apply(self, root):
        return cnd.apply_cost_no_document(root, universes=self.universes, index_tree=index_tree)

    def test_a_bare_estimate_is_explained_and_a_named_one_says_where(self):
        root = tree(org("x", "An Office Nobody Prints"), org("bva", "Board of Veterans Appeals (BVA)"))
        stats = self._apply(root)
        nodes, _ = index_tree(root)
        blank = nodes["x"][cnd.FIELD]
        self.assertEqual(blank["kind"], cnd.KIND_NONE)
        self.assertEqual(blank["namedIn"], [])
        self.assertEqual(len(blank["documents"]), 7)
        named = nodes["bva"][cnd.FIELD]
        self.assertEqual(named["kind"], cnd.KIND_NAMED)
        self.assertEqual([h["document"] for h in named["namedIn"]], ["omb_public_budget_database"])
        self.assertEqual(stats["stamped"], 2)  # the branch is measured and takes no blank
        self.assertEqual(stats["kinds"][cnd.KIND_NAMED], 1)

    def test_never_where_a_figure_or_another_rule_stands(self):
        root = tree(
            org("m", "Measured Unit", cost_status="official"),
            org("s", "Sourced Unit", ombBudget={"amount": 1.0}),
            org("c", "A Committee", type="Committee"),
            org("sub", "A Subcommittee", type="Subcommittee"),
            org("p", "A Post", type="Position", cost_status="unavailable"),
            org("l", "A Line", type="Treasury accounting line"),
            org("old", "Old Unit", lifecycle="superseded"),
            org("neg", "Negative Pool Unit", cost_status="unavailable", cost_validation="treasury_pool_negative"),
            org("ok", "Plain Unit"),
        )
        self._apply(root)
        nodes, _ = index_tree(root)
        for node_id in ("m", "s", "c", "sub", "p", "l", "old", "neg"):
            self.assertNotIn(cnd.FIELD, nodes[node_id], node_id)
        self.assertIn(cnd.FIELD, nodes["ok"])

    def test_the_field_is_cleared_before_it_is_recomputed(self):
        root = tree(org("s", "Sourced Unit", ombBudget={"amount": 1.0}, **{cnd.FIELD: {"kind": cnd.KIND_NONE}}))
        self._apply(root)
        self.assertNotIn(cnd.FIELD, index_tree(root)[0]["s"], "a unit that gained a figure loses the blank")


class GateTests(unittest.TestCase):
    def _nodes(self):
        root = tree(org("x", "An Office Nobody Prints"), org("bva", "Board of Veterans Appeals (BVA)"), org("m", "Measured Unit", cost_status="official"))
        cnd.apply_cost_no_document(root, index_tree=index_tree)
        nodes = [n for n, _ in gate.walk(root)]
        return root, {n["id"]: n for n in nodes}, nodes

    def test_what_the_module_stamps_passes(self):
        root, _, nodes = self._nodes()
        self.assertEqual(gate.cost_no_document_violations(nodes, root, gate.label), [])

    def test_a_bare_estimate_without_a_block_is_refused_once_the_pass_has_run(self):
        root, by_id, nodes = self._nodes()
        del by_id["x"][cnd.FIELD]
        self.assertTrue(any("carries no costNoDocument block" in v for v in gate.cost_no_document_violations(nodes, root, gate.label)))
        del by_id["bva"][cnd.FIELD]
        self.assertEqual(gate.cost_no_document_violations(nodes, root, gate.label), [], "a graph the pass never ran over owes nothing")

    def test_each_corruption_is_refused(self):
        cases = {
            "not an object": lambda n: n["x"].__setitem__(cnd.FIELD, "yes"),
            "on a measured node": lambda n: n["m"].__setitem__(cnd.FIELD, dict(n["x"][cnd.FIELD], name="Measured Unit")),
            "on a post": lambda n: n["x"].__setitem__("type", "Position"),
            "on a committee": lambda n: n["x"].__setitem__("type", "Committee"),
            "beside a sourced figure": lambda n: n["x"].__setitem__("ombBudget", {"amount": 1.0}),
            "another node's name": lambda n: n["x"][cnd.FIELD].__setitem__("name", "Something Else"),
            "a kind the documents do not support": lambda n: n["x"][cnd.FIELD].__setitem__("kind", cnd.KIND_NAMED),
            "a named kind with the hit dropped": lambda n: n["bva"][cnd.FIELD].__setitem__("namedIn", []),
            "an invented hit": lambda n: n["x"][cnd.FIELD].__setitem__("namedIn", [{"document": "omb_public_budget_database", "printed": "An Office Nobody Prints"}]),
            "a document dropped": lambda n: n["x"][cnd.FIELD]["documents"].pop(),
            "a document's digest changed": lambda n: n["x"][cnd.FIELD]["documents"][0].__setitem__("sha256", "0" * 64),
            "a document's version changed": lambda n: n["x"][cnd.FIELD]["documents"][2].__setitem__("version", "package BUDGET-2099-DB"),
            "a document's count changed": lambda n: n["x"][cnd.FIELD]["documents"][0].__setitem__("namesChecked", 1),
            "a document relabelled": lambda n: n["x"][cnd.FIELD]["documents"][0].__setitem__("document", "a paraphrase"),
            "an extra key on the block": lambda n: n["x"][cnd.FIELD].__setitem__("sentence", "a paraphrase"),
            "an extra key on a document": lambda n: n["x"][cnd.FIELD]["documents"][0].__setitem__("note", "x"),
            "no documents": lambda n: n["x"][cnd.FIELD].__setitem__("documents", None),
        }
        for name, corrupt in cases.items():
            with self.subTest(case=name):
                root, by_id, nodes = self._nodes()
                corrupt(by_id)
                self.assertNotEqual(gate.cost_no_document_violations(nodes, root, gate.label), [], name)

    @unittest.skipUnless(PUBLISHED.is_file(), "no published graph")
    def test_the_published_graph_passes_and_leaves_no_bare_estimate(self):
        graph = json.loads(PUBLISHED.read_text(encoding="utf-8"))
        nodes = [n for n, _ in gate.walk(graph)]
        self.assertEqual(gate.cost_no_document_violations(nodes, graph, gate.label), [])
        bare = [n["id"] for n in nodes if gate.cost_no_document_takes_block(n) and not isinstance(n.get(cnd.FIELD), dict)
                and n["id"] != "the-constitution-of-the-united-states"]
        self.assertEqual(bare, [])
        blanks = [n for n in nodes if isinstance(n.get(cnd.FIELD), dict)]
        self.assertGreater(len(blanks), 300)


if __name__ == "__main__":
    unittest.main()
