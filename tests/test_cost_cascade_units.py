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
    summarize_scaled_official,
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
    def test_mixed_units_imply_the_missing_figures_at_the_reported_rate(self) -> None:
        tree = _run(
            [
                {"id": "a", "name": "A", "budget": "$10B", "children": []},
                {"id": "b", "name": "B", "employees": "2,500", "children": []},
                {"id": "c", "name": "C", "children": [{"id": "c1", "name": "C1", "children": []}]},
            ]
        )
        bases = {child["id"]: child["cost_basis"] for child in tree["children"]}
        # Dollars are the best evidence present: a keeps its budget weight, the
        # others are implied at a's rate per node ($10B per node): b = 1 node,
        # c = 2 nodes, so 10 : 10 : 20.
        self.assertEqual(bases, {"a": "budget_weight", "b": "implied_budget_weight", "c": "implied_budget_weight"})
        amounts = {child["id"]: child["resolved_total_amount"] for child in tree["children"]}
        self.assertAlmostEqual(amounts["a"], TOTAL / 4, places=2)
        self.assertAlmostEqual(amounts["b"], TOTAL / 4, places=2)
        self.assertAlmostEqual(amounts["c"], TOTAL / 2, places=2)
        self.assertEqual(tree["child_cost_basis"], "dollars")
        self.assertTrue(tree["child_cost_basis_implied"])
        self.assertNotIn("child_cost_basis_downgraded", tree)

    def test_a_reported_budget_is_never_discarded_for_an_unreported_sibling(self) -> None:
        tree = _run(
            [
                {"id": "big", "name": "Big", "budget": "~$1.4T", "children": []},
                {"id": "small", "name": "Small", "budget": "~$27M", "children": []},
                {"id": "many", "name": "Many", "children": [{"id": f"m{i}", "name": f"M{i}", "children": []} for i in range(50)]},
            ]
        )
        amounts = {child["id"]: child["resolved_total_amount"] for child in tree["children"]}
        # Under size-only weighting "many" (51 nodes) took 96% of the total.
        # Implied at the reported rate the ratio stays 1.4T : 27M : 51 * rate.
        self.assertGreater(amounts["big"], amounts["many"])
        self.assertGreater(amounts["many"], amounts["small"])
        expected_ratio = 1.4e12 / 27e6
        self.assertAlmostEqual(amounts["big"] / amounts["small"], expected_ratio, delta=expected_ratio * 0.01)
        # The implied rate is the geometric mean of the reported per-node
        # rates, so "many" sits between the two reported siblings per node.
        per_node_many = amounts["many"] / 51
        self.assertGreater(per_node_many, amounts["small"])
        self.assertLess(per_node_many, amounts["big"])

    def test_headcounts_beat_size_when_no_sibling_reports_dollars(self) -> None:
        tree = _run(
            [
                {"id": "a", "name": "A", "employees": "3,000", "children": []},
                {"id": "b", "name": "B", "children": [{"id": "b1", "name": "B1", "children": []}]},
            ]
        )
        bases = {child["id"]: child["cost_basis"] for child in tree["children"]}
        self.assertEqual(bases, {"a": "employee_weight", "b": "implied_employee_weight"})
        amounts = {child["id"]: child["resolved_total_amount"] for child in tree["children"]}
        # 3,000 per node: a = 3,000, b = 2 nodes * 3,000 = 6,000.
        self.assertAlmostEqual(amounts["a"], TOTAL / 3, places=2)
        self.assertAlmostEqual(amounts["b"], TOTAL * 2 / 3, places=2)

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
        self.assertEqual(report["summary"]["mixed_weight_sibling_sets_implied"], 1)
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
        self.assertEqual(parse_cost_amount("£2bn"), 2e9)
        self.assertEqual(parse_cost_amount("3.5mn"), 3.5e6)
        self.assertEqual(parse_cost_amount("1tn"), 1e12)

    def test_a_parenthetical_year_is_not_the_figure(self) -> None:
        self.assertEqual(parse_cost_amount("1,200 (2023 est.)"), 1200.0)
        # A bare year is still a number when nothing else was written.
        self.assertEqual(parse_cost_amount("2023"), 2023.0)

    def test_plus_joined_figures_are_summed_and_alternatives_keep_the_largest(self) -> None:
        self.assertEqual(parse_cost_amount("~750,000 civilian + 1.3M active military"), 2.05e6)
        self.assertEqual(parse_cost_amount("~2.9 million civilian + 1.4 million active military"), 4.3e6)
        self.assertEqual(parse_cost_amount("~14,000 federal + 95,000 contractor"), 109000.0)
        # A semicolon separates alternative readings, not parts of one total.
        self.assertEqual(parse_cost_amount("~$14B (admin); ~$1.4T (benefits)"), 1.4e12)


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


class ScaledOfficialSummaryTests(unittest.TestCase):
    """A capped node publishes below its own Treasury line. The panel says so
    per node; this is the total, and it must not count the same money twice.

    A first version summed every node with cost_status scaled_official and
    reported $1.01T withheld against a real figure of $259B — a capped
    department and its capped bureaus are the same dollars.
    """

    def _tree(self):
        return {
            "id": "root", "cost_status": "root_total", "resolved_total_amount": 1000.0,
            "children": [
                {   # capped department: line 500, published 400
                    "id": "dept", "cost_status": "scaled_official",
                    "rollup_total_amount": 500.0, "resolved_total_amount": 400.0,
                    "children": [
                        {   # capped bureau INSIDE it — the same money, must not be added
                            "id": "bureau", "cost_status": "scaled_official",
                            "rollup_total_amount": 300.0, "resolved_total_amount": 240.0,
                            "children": [],
                        },
                    ],
                },
                {   # a second, independent capped branch: counted
                    "id": "agency", "cost_status": "scaled_official",
                    "rollup_total_amount": 200.0, "resolved_total_amount": 180.0, "children": [],
                },
                {   # measured in full, and an estimate: neither is a cap
                    "id": "measured", "cost_status": "official",
                    "rollup_total_amount": 100.0, "resolved_total_amount": 100.0, "children": [],
                },
                {"id": "guess", "cost_status": "allocated", "resolved_total_amount": 50.0, "children": []},
            ],
        }

    def test_only_the_top_most_capped_node_in_a_branch_is_counted(self) -> None:
        summary = summarize_scaled_official(self._tree())
        self.assertEqual(summary["top_most_nodes"], 2)          # dept and agency, not bureau
        self.assertEqual(summary["reported_total"], 700.0)      # 500 + 200, not 1000
        self.assertEqual(summary["published_total"], 580.0)     # 400 + 180
        self.assertEqual(summary["withheld_total"], 120.0)
        self.assertAlmostEqual(summary["published_share_of_reported"], 580.0 / 700.0, places=6)

    def test_a_graph_with_nothing_capped_reports_nothing(self) -> None:
        summary = summarize_scaled_official({"id": "root", "cost_status": "root_total", "children": [
            {"id": "a", "cost_status": "official", "rollup_total_amount": 10.0, "resolved_total_amount": 10.0, "children": []},
        ]})
        self.assertEqual(summary["top_most_nodes"], 0)
        self.assertEqual(summary["withheld_total"], 0.0)
        self.assertIsNone(summary["published_share_of_reported"])

    def test_a_cap_without_a_usable_line_is_not_counted(self) -> None:
        """No line means nothing to be capped against; counting it would make
        the withheld figure a subtraction from zero."""
        summary = summarize_scaled_official({"id": "root", "children": [
            {"id": "a", "cost_status": "scaled_official", "rollup_total_amount": None, "resolved_total_amount": 5.0, "children": []},
            {"id": "b", "cost_status": "scaled_official", "rollup_total_amount": 0, "resolved_total_amount": 5.0, "children": []},
        ]})
        self.assertEqual(summary["top_most_nodes"], 0)
