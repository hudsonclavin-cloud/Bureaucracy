from __future__ import annotations

import unittest

from data_pipeline.validators.cost_validator import CostValidator


class CostValidatorTests(unittest.TestCase):
    def test_rejects_allocated_unverified_costs(self) -> None:
        result = CostValidator().validate_node_cost(
            {
                "id": "office-alpha",
                "name": "Office Alpha",
                "resolved_total_amount": 125000.0,
                "cost_status": "allocated",
                "cost_validation": "estimated_from_parent",
                "costVerificationStatus": "unverified",
                "costConfidenceScore": 0.35,
                "costSourceCount": 0,
                "sourceTypes": [],
                "proofStatus": "proven",
            }
        )

        self.assertFalse(result["export_allowed"])
        self.assertIn("non_authoritative_cost_status", result["blocking_issue_codes"])
        self.assertIn("cost_not_verified", result["blocking_issue_codes"])

    def test_allows_scaled_official_partial_costs_with_financial_source(self) -> None:
        result = CostValidator().validate_node_cost(
            {
                "id": "agency-alpha",
                "name": "Agency Alpha",
                "resolved_total_amount": 250000.0,
                "cost_status": "scaled_official",
                "cost_validation": "scaled_to_parent_total",
                "costVerificationStatus": "partial",
                "costConfidenceScore": 0.72,
                "costSourceCount": 1,
                "sourceTypes": ["treasury_outlays"],
                "proofStatus": "proven",
            }
        )

        self.assertTrue(result["export_allowed"])
        self.assertEqual(result["blocking_issue_codes"], [])

    def test_allows_trusted_base_graph_exception(self) -> None:
        result = CostValidator().validate_node_cost(
            {
                "id": "agency-base",
                "name": "Agency Base",
                "resolved_total_amount": None,
                "cost_status": "unavailable",
                "costVerificationStatus": "unverified",
                "costConfidenceScore": 0.0,
                "costSourceCount": 0,
                "sourceTypes": [],
                "proofStatus": "baseline",
            },
            trusted_exception=True,
        )

        self.assertTrue(result["export_allowed"])
        self.assertTrue(result["exception_applied"])
        self.assertEqual(result["exception_reason"], "trusted_base_graph_exception")


if __name__ == "__main__":
    unittest.main()
