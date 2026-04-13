from __future__ import annotations

import json
import unittest
from copy import deepcopy

from data_pipeline.processors.budget_reconciliation import (
    build_budget_vs_actual_report,
    reconcile_nodes,
)


class BudgetReconciliationTests(unittest.TestCase):
    def test_build_report_includes_only_trusted_org_nodes_and_computes_variance(self) -> None:
        nodes = [
            {
                "id": "dept-energy",
                "name": "Department of Energy",
                "type": "Department",
                "annual_budget": "100.5",
                "rollup_total_amount": 125.75,
                "budget_source": "USAspending",
                "budget_year": "2026",
                "budget_as_of": "2026-02-28",
            },
            {
                "id": "office-grid",
                "name": "Office of Grid Deployment",
                "type": "Office",
                "annual_budget": "55",
                "rollup_total_amount": 60,
            },
        ]

        report = build_budget_vs_actual_report(nodes)

        self.assertEqual(report["summary"]["nodes_seen"], 2)
        self.assertEqual(report["summary"]["trusted_org_nodes_seen"], 1)
        self.assertEqual(report["summary"]["rows_emitted"], 1)
        self.assertEqual(report["summary"]["complete_rows"], 1)
        self.assertEqual(report["summary"]["budget_only_rows"], 0)
        self.assertEqual(report["summary"]["actual_only_rows"], 0)
        self.assertEqual(report["summary"]["unavailable_rows"], 0)

        row = report["rows"][0]
        self.assertEqual(row["id"], "dept-energy")
        self.assertEqual(row["name"], "Department of Energy")
        self.assertEqual(row["type"], "Department")
        self.assertEqual(row["budget_amount"], 100.5)
        self.assertEqual(row["actual_amount"], 125.75)
        self.assertEqual(row["variance_amount"], 25.25)
        self.assertAlmostEqual(row["variance_percent"], 25.12, places=2)
        self.assertEqual(row["budget_source"], "USAspending")
        self.assertEqual(row["budget_year"], "2026")
        self.assertEqual(row["budget_as_of"], "2026-02-28")
        self.assertEqual(row["actual_source"], "Treasury rollup")
        self.assertEqual(row["reconciliation_status"], "complete")
        self.assertTrue(row["availability"]["complete"])

    def test_build_report_marks_partial_and_missing_data_conservatively(self) -> None:
        nodes = [
            {
                "id": "agency-alpha",
                "name": "Agency Alpha",
                "type": "Agency",
                "budget": "$1,200",
                "budget_source": "USAspending",
            },
            {
                "id": "dept-beta",
                "name": "Department Beta",
                "type": "Department",
                "rollup_total_amount": "3000",
                "budget_as_of": "2026-02-28",
            },
            {
                "id": "office-gamma",
                "name": "Office Gamma",
                "type": "Office",
                "budget": "400",
            },
        ]

        report = reconcile_nodes(nodes)

        self.assertEqual(report["summary"]["rows_emitted"], 2)
        self.assertEqual(report["summary"]["budget_only_rows"], 1)
        self.assertEqual(report["summary"]["actual_only_rows"], 1)
        self.assertEqual(report["summary"]["incomplete_rows"], 2)
        self.assertEqual(report["summary"]["missing_budget_rows"], 1)
        self.assertEqual(report["summary"]["missing_actual_rows"], 1)

        rows_by_id = {row["id"]: row for row in report["rows"]}
        self.assertEqual(rows_by_id["agency-alpha"]["reconciliation_status"], "budget_only")
        self.assertEqual(rows_by_id["agency-alpha"]["budget_amount"], 1200.0)
        self.assertIsNone(rows_by_id["agency-alpha"]["actual_amount"])
        self.assertEqual(rows_by_id["dept-beta"]["reconciliation_status"], "actual_only")
        self.assertIsNone(rows_by_id["dept-beta"]["budget_amount"])
        self.assertEqual(rows_by_id["dept-beta"]["actual_amount"], 3000.0)

    def test_report_is_serializable_and_does_not_mutate_inputs(self) -> None:
        nodes = [
            {
                "id": "agency-delta",
                "name": "Agency Delta",
                "type": "Agency",
                "annual_budget": 50,
                "rollup_total_amount": 40,
                "budget_source": "Treasury MTS Table 5",
            }
        ]
        original = deepcopy(nodes)

        report = build_budget_vs_actual_report(nodes)
        json.dumps(report)

        self.assertEqual(nodes, original)
        self.assertEqual(report["summary"]["reconciled_rows"], 1)
        self.assertEqual(report["rows"][0]["variance_amount"], -10.0)


if __name__ == "__main__":
    unittest.main()
