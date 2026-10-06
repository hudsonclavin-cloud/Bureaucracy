"""The cost-coverage inventory: every node in exactly one class, and the
committed document equal to what the script renders from the published graph.

The claim the document makes is that the classes partition the graph -- a node
is measured, or an estimate, or a salary, or a post nothing prices, or a unit
with no figure and a stated reason -- so that "every node is accounted for" is
checkable. It is checked here against the published graph, and the committed
copy is compared byte for byte so a stale one fails.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from data_pipeline.verification.pay_documents import PAY_FIELDS
from scripts.report_cost_coverage import CLASSES, classify, collect, render, walk
from scripts.report_unpriced_positions import collect as collect_unpriced

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GRAPH = PROJECT_ROOT / "output" / "graph.json"
DOC = PROJECT_ROOT / "docs" / "COST_COVERAGE.md"


def _graph():
    if not GRAPH.exists():
        return None
    return json.loads(GRAPH.read_text(encoding="utf-8"))


class PartitionTests(unittest.TestCase):
    def test_every_node_lands_in_exactly_one_known_class(self):
        graph = _graph()
        if graph is None:
            self.skipTest("no published graph")
        rows = collect(graph)
        self.assertEqual(rows.get("other", []), [], "a node fell outside every class")
        counted = sum(len(v) for v in rows.values())
        self.assertEqual(counted, sum(1 for _ in walk(graph)))
        self.assertTrue(set(rows) <= set(CLASSES))

    def test_measured_is_the_gates_definition(self):
        graph = _graph()
        if graph is None:
            self.skipTest("no published graph")
        rows = collect(graph)
        measured = {r["id"] for r in rows["measured"]} | {r["id"] for r in rows["measured_treasury_line"]}
        expected = {
            str(n.get("id"))
            for n, _ in walk(graph)
            if str(n.get("cost_status") or "") in ("official", "root_total")
        }
        self.assertEqual(measured, expected)

    def test_the_unpriced_posts_are_the_unpriced_reports_own(self):
        graph = _graph()
        if graph is None:
            self.skipTest("no published graph")
        rows = collect(graph)
        here = {r["id"] for cls in UNPRICED_POST_CLASSES for r in rows.get(cls, [])}
        groups, positions, priced, _ = collect_unpriced(graph)
        there = {row["id"] for group in groups.values() for row in group}
        self.assertEqual(here, there)
        self.assertEqual(len(rows["salary"]), priced)
        self.assertEqual(len(rows["salary"]) + len(here), positions)

    def test_a_salary_node_carries_a_pay_field_and_an_unpriced_post_none(self):
        graph = _graph()
        if graph is None:
            self.skipTest("no published graph")
        by_id = {str(n.get("id")): n for n, _ in walk(graph)}
        rows = collect(graph)
        for row in rows["salary"]:
            self.assertTrue(any(isinstance(by_id[row["id"]].get(f), dict) for f in PAY_FIELDS), row["id"])
        for cls in UNPRICED_POST_CLASSES:
            for row in rows.get(cls, []):
                self.assertFalse(any(isinstance(by_id[row["id"]].get(f), dict) for f in PAY_FIELDS), row["id"])

    def test_classify_in_both_directions(self):
        self.assertEqual(classify({"type": "Bureau", "cost_status": "official"}), "measured")
        self.assertEqual(classify({"type": "Treasury accounting line", "cost_status": "official"}), "measured_treasury_line")
        self.assertEqual(classify({"type": "Position", "cost_status": "unavailable", "positionStatutoryPay": {"amount": 1.0}}), "salary")
        self.assertEqual(classify({"type": "Position", "cost_status": "unavailable", "representsPosts": {"count": 2}}), "post_multiplicity")
        self.assertEqual(classify({"type": "Position", "cost_status": "unavailable", "positionListing": {}}), "post_listed_no_rate")
        self.assertEqual(classify({"type": "Position", "cost_status": "unavailable"}), "post_unreached")
        self.assertEqual(classify({"type": "Position", "cost_status": "unavailable"}, True), "post_beneath_replaced_unit")
        self.assertEqual(classify({"type": "Position", "cost_status": "unavailable", "positionEmployer": {"federallyPaid": False}}), "post_not_federally_paid")
        # A priced post beneath a replaced unit is still a salary: the figure exists.
        self.assertEqual(classify({"type": "Position", "positionTierPay": {"minimum": 1.0}}, True), "salary")
        self.assertEqual(classify({"type": "Subcommittee", "cost_status": "allocated"}), "estimate_committee")
        self.assertEqual(classify({"type": "Bureau", "cost_status": "allocated", "ombBudget": {}}), "estimate_beside_sourced_figure")
        self.assertEqual(classify({"type": "Bureau", "cost_status": "allocated"}), "estimate")
        self.assertEqual(classify({"type": "Office", "cost_status": "unavailable", "cost_validation": "treasury_pool_negative"}), "negative_pool")
        self.assertEqual(classify({"type": "VISN", "cost_status": "unavailable", "cost_validation": "unit_superseded"}), "superseded")
        self.assertEqual(classify({"type": "Office", "cost_status": "unavailable", "cost_validation": "allocation_below_precision"}), "below_precision")
        # A post is a post before it is anything else: an estimate on one is a
        # defect upstream, and this report must not file it as an organisation.
        self.assertEqual(classify({"type": "Position", "cost_status": "allocated"}), "post_unreached")
        self.assertEqual(classify({"type": "Office", "cost_status": "unavailable"}), "other")


UNPRICED_POST_CLASSES = (
    "post_multiplicity", "post_listed_no_rate", "post_unreached",
    "post_beneath_replaced_unit", "post_not_federally_paid",
)


class DocumentTests(unittest.TestCase):
    def test_the_committed_document_is_what_the_graph_renders(self):
        graph = _graph()
        if graph is None or not DOC.exists():
            self.skipTest("no published graph or no committed document")
        self.assertEqual(DOC.read_text(encoding="utf-8"), render(collect(graph)))

    def test_the_document_names_every_class_that_has_a_node(self):
        graph = _graph()
        if graph is None:
            self.skipTest("no published graph")
        rows = collect(graph)
        text = render(rows)
        for cls, (heading, _, _) in CLASSES.items():
            if rows.get(cls):
                self.assertIn(heading, text)
        self.assertNotIn("Unclassified", text)


if __name__ == "__main__":
    unittest.main()
