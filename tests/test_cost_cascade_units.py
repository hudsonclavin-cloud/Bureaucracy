"""The cost cascade must only sum weights that share a unit.

The committed graph once split the Treasury total among siblings by adding a
dollar budget (1.2e10), a headcount (2,500) and a subtree size (163) into one
denominator: the sibling with the dollar figure took essentially everything and
120 published nodes read "≈ $0". These tests pin the rules that stop that.
"""

from __future__ import annotations

import json
import shutil
import unittest
import uuid
from pathlib import Path

from data_pipeline.exporter.build_graph import (
    annotate_resolved_costs,
    build_graph,
    parse_cost_amount,
)
from data_pipeline.processors.normalize_nodes import generate_node_id, normalize_name


TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
TOTAL = 1_000_000.0


def _tree(children: list[dict]) -> dict:
    return {"id": "root", "name": "Root", "type": "Foundation", "children": children}


def _run(children: list[dict]) -> dict:
    tree = _tree(children)
    annotate_resolved_costs(tree, budget_summary={"government_total_outlay_amount": TOTAL})
    return tree


class SiblingWeightUnitTests(unittest.TestCase):
    def test_mixed_units_fall_back_to_subtree_size_for_the_whole_set(self) -> None:
        tree = _run(
            [
                {"id": "a", "name": "A", "budget": "$10B", "children": []},
                {"id": "b", "name": "B", "employees": "2,500", "children": []},
                {"id": "c", "name": "C", "children": [{"id": "c1", "name": "C1", "children": []}]},
            ]
        )
        bases = {child["id"]: child["cost_basis"] for child in tree["children"]}
        self.assertEqual(set(bases.values()), {"subtree_weight"})
        amounts = {child["id"]: child["resolved_total_amount"] for child in tree["children"]}
        # a and b are single nodes, c is two: 1:1:2 of the total.
        self.assertAlmostEqual(amounts["a"], TOTAL / 4, places=2)
        self.assertAlmostEqual(amounts["b"], TOTAL / 4, places=2)
        self.assertAlmostEqual(amounts["c"], TOTAL / 2, places=2)
        self.assertEqual(tree["child_cost_basis"], "subtree")
        self.assertTrue(tree["child_cost_basis_downgraded"])

    def test_uniform_dollar_units_keep_the_budget_weighting(self) -> None:
        tree = _run(
            [
                {"id": "a", "name": "A", "budget": "~$800M", "children": []},
                {"id": "b", "name": "B", "budget": "~$200M", "children": []},
            ]
        )
        amounts = {child["id"]: child["resolved_total_amount"] for child in tree["children"]}
        self.assertAlmostEqual(amounts["a"], TOTAL * 0.8, places=2)
        self.assertAlmostEqual(amounts["b"], TOTAL * 0.2, places=2)
        self.assertEqual({c["cost_basis"] for c in tree["children"]}, {"budget_weight"})
        self.assertEqual(tree["child_cost_basis"], "dollars")
        self.assertNotIn("child_cost_basis_downgraded", tree)

    def test_uniform_headcounts_keep_the_employee_weighting(self) -> None:
        tree = _run(
            [
                {"id": "a", "name": "A", "employees": "~7,000 (staff)", "children": []},
                {"id": "b", "name": "B", "employees": "3,000", "children": []},
            ]
        )
        amounts = {child["id"]: child["resolved_total_amount"] for child in tree["children"]}
        self.assertAlmostEqual(amounts["a"], TOTAL * 0.7, places=2)
        self.assertEqual({c["cost_basis"] for c in tree["children"]}, {"employee_weight"})

    def test_a_share_below_one_cent_is_unavailable_not_zero(self) -> None:
        tree = _run(
            [
                {"id": "big", "name": "Big", "employees": "1000000000", "children": []},
                {
                    "id": "tiny",
                    "name": "Tiny",
                    "employees": "1",
                    "children": [{"id": "tiny-child", "name": "Tiny child", "children": []}],
                },
            ]
        )
        tiny = next(child for child in tree["children"] if child["id"] == "tiny")
        self.assertIsNone(tiny["resolved_total_amount"])
        self.assertEqual(tiny["cost_status"], "unavailable")
        self.assertEqual(tiny["cost_validation"], "allocation_below_precision")
        self.assertEqual(tiny["costVerificationReason"], "missing_cost")
        # The refusal reaches descendants as an explicit status, not an absence.
        grandchild = tiny["children"][0]
        self.assertIsNone(grandchild["resolved_total_amount"])
        self.assertEqual(grandchild["cost_status"], "unavailable")
        self.assertEqual(grandchild["cost_validation"], "allocation_below_precision")
        big = next(child for child in tree["children"] if child["id"] == "big")
        self.assertGreater(big["resolved_total_amount"], 0)

    def test_without_an_anchor_every_node_still_carries_a_cost_status(self) -> None:
        tree = _tree([{"id": "a", "name": "A", "children": [{"id": "a1", "name": "A1", "children": []}]}])
        annotate_resolved_costs(tree, budget_summary=None)
        grandchild = tree["children"][0]["children"][0]
        self.assertIsNone(grandchild["resolved_total_amount"])
        self.assertEqual(grandchild["cost_status"], "unavailable")
        self.assertEqual(grandchild["cost_validation"], "missing_cost")

    def test_a_budget_string_is_not_a_cost_source_for_an_allocated_figure(self) -> None:
        tree = _run(
            [
                {"id": "a", "name": "A", "budget": "~$800M", "children": []},
                {"id": "b", "name": "B", "budget": "~$200M", "children": []},
            ]
        )
        for child in tree["children"]:
            self.assertEqual(child["cost_status"], "allocated")
            self.assertEqual(child["costSourceCount"], 0)
            self.assertEqual(child["costConfidenceScore"], 0.2)
        self.assertEqual(tree["costSourceCount"], 1)
        self.assertEqual(tree["costVerificationStatus"], "verified")

    def test_summary_reports_the_downgrades_and_precision_refusals(self) -> None:
        tree = _tree(
            [
                {"id": "a", "name": "A", "budget": "$10B", "children": []},
                {"id": "b", "name": "B", "employees": "2,500", "children": []},
            ]
        )
        report = annotate_resolved_costs(tree, budget_summary={"government_total_outlay_amount": TOTAL})
        self.assertEqual(report["summary"]["mixed_weight_sibling_sets_downgraded"], 1)
        self.assertEqual(report["summary"]["allocations_below_precision"], 0)


class ParseCostAmountTests(unittest.TestCase):
    def test_magnitude_suffix_needs_a_word_boundary(self) -> None:
        self.assertEqual(parse_cost_amount("~2,000 total staff"), 2000.0)
        self.assertEqual(parse_cost_amount("~4,000 military"), 4000.0)
        self.assertEqual(parse_cost_amount("~300 troops"), 300.0)

    def test_attached_suffixes_still_scale(self) -> None:
        self.assertEqual(parse_cost_amount("$60B"), 60e9)
        self.assertEqual(parse_cost_amount("~$1.4T"), 1.4e12)
        self.assertEqual(parse_cost_amount("1.3M active"), 1.3e6)
        self.assertEqual(parse_cost_amount("$5 million"), 5e6)

    def test_a_parenthetical_year_is_not_the_figure(self) -> None:
        self.assertEqual(parse_cost_amount("1,200 (2023 est.)"), 1200.0)
        # A bare year is still a number when nothing else was written.
        self.assertEqual(parse_cost_amount("2023"), 2023.0)

    def test_compound_strings_keep_the_largest_component(self) -> None:
        # Pinned so a future change to this rule is deliberate: the exporter
        # weights DoD by its 1.3M active military, the larger of the two.
        self.assertEqual(parse_cost_amount("~750,000 civilian + 1.3M active military"), 1.3e6)


class CuratedNameTests(unittest.TestCase):
    def test_normalize_name_keeps_slashes(self) -> None:
        self.assertEqual(normalize_name("Deputy Director / COO"), "Deputy Director / COO")
        # Underscores still become spaces (and an all-lowercase name is title-cased, as before).
        self.assertEqual(normalize_name("some_slug_name"), "Some Slug Name")
        self.assertEqual(generate_node_id("Deputy Director / COO"), "deputy-director-coo")

    def test_rebuilding_over_the_previous_output_preserves_curated_names(self) -> None:
        tmp_path = TEST_TMP_ROOT / f"cascade-{uuid.uuid4().hex}"
        tmp_path.mkdir(parents=True, exist_ok=True)
        try:
            base_graph_path = tmp_path / "base.json"
            base_graph_path.write_text(
                json.dumps(
                    {
                        "id": "root",
                        "name": "Root",
                        "type": "Foundation",
                        "children": [
                            {
                                "id": "gpo",
                                "name": "Government Publishing Office",
                                "type": "Agency",
                                "children": [
                                    {"id": "gpo-coo", "name": "Deputy Director / COO", "type": "Position", "children": []}
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            paths = dict(
                base_graph_path=base_graph_path,
                graph_output_path=tmp_path / "graph.json",
                nodes_output_path=tmp_path / "expanded_nodes.json",
                edges_output_path=tmp_path / "expanded_edges.json",
                validity_report_output_path=tmp_path / "node_validity_report.json",
                enforce_export_gate=True,
            )
            summary = {"government_total_outlay_amount": 1000, "record_date": "2026-06-30"}
            first = build_graph([{"nodes": [], "edges": [], "budgetSummary": summary}], **paths)
            self.assertNotIn("reused_from_previous_build", first.graph["__budgetSummary"])
            self.assertFalse(first.validation["budget_summary_reused_from_previous_build"])

            # Second build: no fresh Treasury summary, previous graph re-fed.
            second = build_graph([{"nodes": [], "edges": []}], **paths)
            coo = second.graph["children"][0]["children"][0]
            self.assertEqual(coo["name"], "Deputy Director / COO")
            self.assertEqual(coo["type"], "Position")
            # The carried-over anchor keeps the figure but says where it came from.
            self.assertTrue(second.graph["__budgetSummary"]["reused_from_previous_build"])
            self.assertTrue(second.validation["budget_summary_reused_from_previous_build"])
            self.assertEqual(second.graph["resolved_total_amount"], 1000)
            self.assertEqual(second.graph["cost_status"], "root_total")

            # Third build with a fresh summary: the tag does not stick.
            third = build_graph([{"nodes": [], "edges": [], "budgetSummary": dict(summary)}], **paths)
            self.assertNotIn("reused_from_previous_build", third.graph["__budgetSummary"])
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
