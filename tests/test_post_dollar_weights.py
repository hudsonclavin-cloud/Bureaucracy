"""A post takes no weight in a split by dollar figures, and keeps it elsewhere.

Since 2026-10-21 (the owner's decision), a sibling set the cascade divides by a
dollar class -- curated budgets, Combined Statement figures, a chamber's
payouts -- gives a post no weight. Before, a post was implied at its siblings'
dollar rate and then published nothing, so its share of real money was
withheld from the units beside it and shown as nobody's: $117.6bn of the
Department of Veterans Affairs' pool sat on sixteen posts. In a headcount or
subtree-size split a post still counts, because the organisation really is
that many people or nodes. Both directions are pinned here, in the cascade and
in the gate.
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
from data_pipeline.exporter.build_graph import (  # noqa: E402
    POST_UNWEIGHTED_BASIS,
    annotate_resolved_costs,
)

TOTAL = 1_000_000.0
PUBLISHED = PROJECT_ROOT / "output" / "graph.json"


def tree(children):
    return {"id": "root", "name": "Root", "type": "Foundation", "children": [
        {"id": "agency", "name": "An Agency", "type": "Agency", "children": children}]}


def run(children):
    root = tree(children)
    annotate_resolved_costs(root, budget_summary={"government_total_outlay_amount": TOTAL})
    found = {}
    stack = [root]
    while stack:
        node = stack.pop()
        found[node["id"]] = node
        stack.extend(node.get("children") or [])
    return found


def bureau(node_id, **fields):
    return {"id": node_id, "name": node_id, "type": "Bureau", "children": [], **fields}


def post(node_id):
    return {"id": node_id, "name": node_id, "type": "Position", "children": []}


class CascadeTests(unittest.TestCase):
    def test_a_dollar_split_gives_the_units_the_whole_pool(self):
        nodes = run([bureau("a", budget="$300"), bureau("b", budget="$100"), post("p1"), post("p2")])
        self.assertAlmostEqual(nodes["a"]["resolved_total_amount"], 750_000.0, places=2)
        self.assertAlmostEqual(nodes["b"]["resolved_total_amount"], 250_000.0, places=2)
        for node_id in ("p1", "p2"):
            self.assertEqual(nodes[node_id]["cost_basis"], POST_UNWEIGHTED_BASIS)
            self.assertEqual(nodes[node_id]["cost_validation"], "post_is_not_a_budget_unit")
            self.assertIsNone(nodes[node_id].get("resolved_total_amount"))
        self.assertNotIn("child_cost_basis_implied", nodes["agency"])

    def test_a_unit_without_a_figure_is_still_implied_beside_unweighted_posts(self):
        nodes = run([bureau("a", budget="$300"), bureau("c"), post("p1")])
        self.assertEqual(nodes["c"]["cost_basis"], "implied_budget_weight")
        self.assertEqual(nodes["p1"]["cost_basis"], POST_UNWEIGHTED_BASIS)
        shown = nodes["a"]["resolved_total_amount"] + nodes["c"]["resolved_total_amount"]
        self.assertAlmostEqual(shown, TOTAL, places=2)
        self.assertTrue(nodes["agency"].get("child_cost_basis_implied"))

    def test_a_post_listed_last_is_not_handed_the_remainder(self):
        nodes = run([post("p0"), bureau("a", budget="$1"), bureau("b", budget="$2"), post("p9")])
        self.assertAlmostEqual(
            nodes["a"]["resolved_total_amount"] + nodes["b"]["resolved_total_amount"], TOTAL, places=2)
        self.assertEqual(nodes["p9"]["cost_validation"], "post_is_not_a_budget_unit")

    def test_a_headcount_split_keeps_the_post_s_weight(self):
        nodes = run([bureau("a", employees="300"), bureau("b", employees="100"), post("p1")])
        self.assertEqual(nodes["p1"]["cost_basis"], "implied_employee_weight")
        shown = nodes["a"]["resolved_total_amount"] + nodes["b"]["resolved_total_amount"]
        self.assertLess(shown, TOTAL)

    def test_a_subtree_split_keeps_the_post_s_weight(self):
        nodes = run([bureau("a"), bureau("b"), post("p1")])
        self.assertEqual(nodes["p1"]["cost_basis"], "subtree_weight")
        self.assertAlmostEqual(nodes["a"]["resolved_total_amount"], TOTAL / 3, places=2)


class GateTests(unittest.TestCase):
    def check(self, nodes, child_cost_basis):
        parent = {"id": "agency", "child_cost_basis": child_cost_basis}
        tree_parents = {n["id"]: "agency" for n in nodes}
        return gate.post_dollar_weight_violations([parent, *nodes], tree_parents, lambda n: n["id"])

    @staticmethod
    def node(node_id, basis, type_="Position", amount=None):
        return {"id": node_id, "type": type_, "cost_basis": basis, "resolved_total_amount": amount,
                "cost_status": "unavailable" if amount is None else "allocated"}

    def test_an_unweighted_post_under_a_dollar_parent_passes(self):
        nodes = [self.node("a", "budget_weight", "Bureau", 10.0), self.node("p", POST_UNWEIGHTED_BASIS)]
        self.assertEqual(self.check(nodes, "dollars"), [])

    def test_a_post_keeping_its_weight_in_a_headcount_split_passes(self):
        nodes = [self.node("a", "employee_weight", "Bureau", 10.0), self.node("p", "implied_employee_weight")]
        self.assertEqual(self.check(nodes, "employees"), [])

    def test_each_corruption_is_refused(self):
        cases = {
            "a post implied in a dollar split": ("dollars", [self.node("p", "implied_budget_weight")]),
            "a post implied beside Combined Statement figures": (
                "combined_statement", [self.node("p", "implied_combined_statement_weight")]),
            "a post implied beside payouts": ("disbursements", [self.node("p", "implied_disbursement_weight")]),
            "the no-weight basis in a headcount split": ("employees", [self.node("p", POST_UNWEIGHTED_BASIS)]),
            "the no-weight basis on a unit": ("dollars", [self.node("u", POST_UNWEIGHTED_BASIS, "Bureau")]),
            "the no-weight basis beside a figure": ("dollars", [self.node("p", POST_UNWEIGHTED_BASIS, amount=5.0)]),
        }
        for name, (cls, nodes) in cases.items():
            with self.subTest(case=name):
                self.assertNotEqual(self.check(nodes, cls), [], name)

    @unittest.skipUnless(PUBLISHED.is_file(), "no published graph")
    def test_the_published_graph_passes_and_withholds_nothing_from_a_dollar_split(self):
        graph = json.loads(PUBLISHED.read_text(encoding="utf-8"))
        nodes, parents, stack = [], {}, [(graph, None)]
        while stack:
            node, parent = stack.pop()
            nodes.append(node)
            parents[node["id"]] = parent
            stack.extend((child, node["id"]) for child in node.get("children") or [])
        self.assertEqual(gate.post_dollar_weight_violations(nodes, parents, lambda n: n["id"]), [])
        by_id = {n["id"]: n for n in nodes}
        # The Department of Labor divides its pool by curated budgets, so its
        # measured net total is carried by its children to the cent: the
        # measured lines, the receipts and the unlined units, no post. (The VA
        # was the example until 2026-10-22, when the Total--Benefits Programs
        # alias measured the VBA and left the NCA and the BVA with no dollar
        # figure, so that set fell back to a subtree split, where posts count.)
        dol = by_id["exec-dept-dol"]
        self.assertEqual(dol.get("child_cost_basis"), "dollars")
        shown = sum(c["resolved_total_amount"] for c in dol["children"]
                    if c.get("resolved_total_amount") is not None)
        self.assertAlmostEqual(shown, dol["resolved_total_amount"], places=1)
        self.assertEqual(sum(1 for n in nodes if n.get("cost_basis") == POST_UNWEIGHTED_BASIS), 68)


if __name__ == "__main__":
    unittest.main()
