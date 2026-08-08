from __future__ import annotations

import unittest

from data_pipeline.validators.node_requirements import NodeRequirements, generate_audit_report


class NodeRequirementsTests(unittest.TestCase):
    def test_generate_audit_report_flags_missing_data_and_placeholder_names(self) -> None:
        report = generate_audit_report(
            [
                {
                    "id": "node-1",
                    "name": "Unnamed Node",
                    "type": "",
                    "resolved_total_amount": None,
                    "cost_status": None,
                    "cost_validation": None,
                    "costVerificationStatus": "unverified",
                    "costConfidenceScore": 0.0,
                    "verificationStatus": "unverified",
                    "confidenceScore": 0.1,
                    "sourceCount": 0,
                    "sourceUrls": [],
                    "proofStatus": "unproven",
                }
            ]
        )

        self.assertEqual(report["summary"]["total_nodes"], 1)
        self.assertEqual(report["summary"]["nodes_with_errors"], 1)
        self.assertGreaterEqual(report["summary"]["severity_counts"]["error"], 2)
        self.assertIn("placeholder_name", report["summary"]["issue_counts"])
        self.assertIn("missing_cost", report["summary"]["issue_counts"])
        self.assertIn("missing_source_urls", report["summary"]["issue_counts"])

        finding = report["nodes"][0]
        self.assertTrue(finding["has_errors"])
        self.assertIn("placeholder_name", finding["issue_codes"])
        self.assertIn("missing_cost", finding["issue_codes"])
        self.assertIn("missing_source_urls", finding["issue_codes"])
        self.assertIn("low_confidence", finding["issue_codes"])

    def test_generate_audit_report_marks_allocated_and_scaled_official_as_warnings_only(self) -> None:
        report = generate_audit_report(
            [
                {
                    "id": "agency-alpha",
                    "name": "Agency Alpha",
                    "type": "Agency",
                    "resolved_total_amount": 123456.78,
                    "cost_status": "allocated",
                    "cost_validation": "estimated_from_parent",
                    "costVerificationStatus": "unverified",
                    "costConfidenceScore": 0.35,
                    "verificationStatus": "partial",
                    "confidenceScore": 0.62,
                    "sourceCount": 2,
                    "sourceUrls": ["https://example.gov/alpha"],
                    "proofStatus": "proven",
                },
                {
                    "id": "office-beta",
                    "name": "Office Beta",
                    "type": "Office",
                    "resolved_total_amount": 98765.43,
                    "cost_status": "scaled_official",
                    "cost_validation": "scaled_to_parent_total",
                    "costVerificationStatus": "partial",
                    "costConfidenceScore": 0.72,
                    "verificationStatus": "verified",
                    "confidenceScore": 0.92,
                    "sourceCount": 1,
                    "sourceUrls": ["https://example.gov/beta"],
                    "proofStatus": "proven",
                },
            ]
        )

        self.assertEqual(report["summary"]["total_nodes"], 2)
        self.assertEqual(report["summary"]["nodes_with_errors"], 0)
        self.assertEqual(report["summary"]["warning_only_nodes"], 2)
        self.assertEqual(report["summary"]["cost_status_counts"]["allocated"], 1)
        self.assertEqual(report["summary"]["cost_status_counts"]["scaled_official"], 1)
        self.assertEqual(report["summary"]["cost_verification_status_counts"]["unverified"], 1)
        self.assertEqual(report["summary"]["cost_verification_status_counts"]["partial"], 1)

        allocated = report["nodes"][0]
        scaled = report["nodes"][1]
        self.assertTrue(allocated["has_warnings"])
        self.assertFalse(allocated["has_errors"])
        self.assertTrue(allocated["is_warning_only"])
        self.assertIn("estimated_cost", allocated["issue_codes"])

        self.assertTrue(scaled["has_warnings"])
        self.assertFalse(scaled["has_errors"])
        self.assertTrue(scaled["is_warning_only"])
        self.assertIn("estimated_cost", scaled["issue_codes"])

    def test_generate_audit_report_flags_suspicious_exact_values_without_rejecting(self) -> None:
        report = generate_audit_report(
            [
                {
                    "id": "node-3",
                    "name": "Finance Office",
                    "type": "Office",
                    "resolved_total_amount": 1000,
                    "cost_status": "official",
                    "cost_validation": "matched_official_rollup",
                    "costVerificationStatus": "verified",
                    "costConfidenceScore": 0.95,
                    "verificationStatus": "verified",
                    "confidenceScore": 0.88,
                    "sourceCount": 1,
                    "sourceUrls": ["https://example.gov/finance"],
                    "proofStatus": "proven",
                }
            ]
        )

        finding = report["nodes"][0]
        self.assertFalse(finding["has_errors"])
        self.assertIn("suspicious_exact_cost_value", finding["issue_codes"])
        self.assertEqual(report["summary"]["nodes_with_errors"], 0)
        self.assertEqual(report["summary"]["nodes_with_warnings"], 1)

    def test_audit_node_keeps_missing_cost_status_explicit(self) -> None:
        auditor = NodeRequirements()
        finding = auditor.audit_node(
            {
                "id": "node-4",
                "name": "Policy Team",
                "type": "Team",
                "resolved_total_amount": 25000,
                "cost_status": "",
                "cost_validation": "review_pending",
                "costVerificationStatus": "unverified",
                "costConfidenceScore": 0.0,
                "verificationStatus": "verified",
                "confidenceScore": 0.8,
                "sourceCount": 1,
                "sourceUrls": ["https://example.gov/policy"],
                "proofStatus": "proven",
            }
        )

        self.assertIn("unavailable_cost_status", finding["issue_codes"])
        self.assertTrue(finding["has_errors"])
        self.assertTrue(finding["has_warnings"])
        self.assertIn("cost_unverified", finding["issue_codes"])

    def test_audit_flags_cost_unverified_separately_from_entity_verification(self) -> None:
        auditor = NodeRequirements()
        finding = auditor.audit_node(
            {
                "id": "node-5",
                "name": "Operations Office",
                "type": "Office",
                "resolved_total_amount": 42000,
                "cost_status": "allocated",
                "cost_validation": "estimated_from_parent",
                "costVerificationStatus": "unverified",
                "costConfidenceScore": 0.35,
                "verificationStatus": "verified",
                "confidenceScore": 0.91,
                "sourceCount": 2,
                "sourceUrls": ["https://example.gov/ops", "https://www.wikidata.org/wiki/Q5"],
                "proofStatus": "proven",
            }
        )

        self.assertEqual(finding["verificationStatus"], "verified")
        self.assertEqual(finding["costVerificationStatus"], "unverified")
        self.assertIn("cost_unverified", finding["issue_codes"])
        self.assertIn("low_cost_confidence", finding["issue_codes"])


if __name__ == "__main__":
    unittest.main()
