"""Behaviour tests for the validation layer.

These pin BOTH directions of every scorer. A validator that only ever accepts is
not a validator, and three times this week one ran happily while being wrong:
the eight-name trusted-type allowlist, the proof gate reading fields no
normalizer populated, and the cost gate rejecting everything for want of a
budgetSummary. Each had passing tests. Every assertion here names a specific
verdict rather than merely asserting that nothing raised.
"""

from __future__ import annotations

import unittest

from data_pipeline.exporter.build_graph import annotate_resolved_costs
from data_pipeline.processors.normalize_nodes import verify_node_sources
from data_pipeline.validators.cost_validator import CostValidator
from data_pipeline.validators.node_requirements import NodeRequirements


class VerificationScoringTests(unittest.TestCase):
    def test_gov_source_counts_as_official_proof(self) -> None:
        node = verify_node_sources({"id": "x", "sourceUrls": ["https://www.energy.gov/gdo"]})

        self.assertTrue(node["existsProven"])
        self.assertGreaterEqual(node["proofSourceCount"], 1)
        self.assertIn("official_site", node["sourceTypes"])
        self.assertEqual(node["proofReason"], "official_source_recorded")

    def test_wikidata_alone_is_not_official_proof(self) -> None:
        node = verify_node_sources({"id": "x", "sourceUrls": ["https://www.wikidata.org/wiki/Q999"]})

        self.assertNotIn("official_site", node["sourceTypes"])
        self.assertFalse(node["existsProven"])
        self.assertNotEqual(node["proofReason"], "official_source_recorded")

    def test_no_sources_proves_nothing_and_invents_no_timestamp(self) -> None:
        node = verify_node_sources({"id": "x"})

        self.assertFalse(node["existsProven"])
        self.assertEqual(node["confidenceScore"], 0.0)
        self.assertEqual(node["sourceCount"], 0)
        self.assertEqual(node["verificationStatus"], "unverified")
        # A verification date on something never verified would be a fabricated
        # claim, and a more convincing one than the status string.
        self.assertIsNone(node["lastVerified"])

    def test_blank_and_whitespace_urls_do_not_count_as_sources(self) -> None:
        node = verify_node_sources({"id": "x", "sourceUrls": ["", "   ", "\t\n"]})

        self.assertEqual(node["sourceCount"], 0)
        self.assertEqual(node["sourceUrls"], [])
        self.assertFalse(node["existsProven"])
        self.assertEqual(node["confidenceScore"], 0.0)
        self.assertIsNone(node["lastVerified"])


def _costed_node(**overrides: object) -> dict[str, object]:
    node = {
        "id": "agency-alpha",
        "name": "Agency Alpha",
        "resolved_total_amount": 1234567.89,
        "cost_status": "root_total",
        "costVerificationStatus": "verified",
        "costConfidenceScore": 0.9,
        "costSourceCount": 1,
        "sourceTypes": ["official_financial_record"],
        "proofStatus": "proven",
    }
    node.update(overrides)
    return node


class CostValidationTests(unittest.TestCase):
    def test_verified_root_total_is_allowed_on_its_own_evidence(self) -> None:
        result = CostValidator().validate_node_cost(_costed_node())

        self.assertTrue(result["export_allowed"])
        self.assertEqual(result["blocking_issue_codes"], [])
        self.assertFalse(result["exception_applied"])

    def test_allocated_cost_without_trust_is_rejected(self) -> None:
        result = CostValidator().validate_node_cost(
            _costed_node(cost_status="allocated", costVerificationStatus="unverified")
        )

        self.assertFalse(result["export_allowed"])
        self.assertIn("non_authoritative_cost_status", result["blocking_issue_codes"])
        self.assertIn("cost_not_verified", result["blocking_issue_codes"])

    def test_allocated_cost_passes_for_a_trusted_id_and_records_the_exception(self) -> None:
        validator = CostValidator()
        node = _costed_node(
            id="leg-senate",
            cost_status="allocated",
            costVerificationStatus="unverified",
            proofStatus="baseline",
        )
        trusted_ids = {"leg-senate"}

        self.assertTrue(validator.is_trusted_exception_node(node, trusted_ids))
        result = validator.validate_node_cost(node, trusted_exception=True)

        self.assertTrue(result["export_allowed"])
        # The exception must be recorded, not silently granted: a waived node and
        # a node that passed on merit are different claims.
        self.assertTrue(result["exception_applied"])
        self.assertEqual(result["exception_reason"], "trusted_base_graph_exception")
        self.assertIn("non_authoritative_cost_status", result["blocking_issue_codes"])

    def test_missing_amount_is_waived_but_reported_when_trusted(self) -> None:
        """Policy, stated plainly: a curated base-graph node is published even
        without a cost (8dab251 trusts the base graph by id), so the exception
        waives the missing amount. What it must never do is hide it."""
        validator = CostValidator()
        node = _costed_node(resolved_total_amount=None)

        untrusted = validator.validate_node_cost(node)
        self.assertFalse(untrusted["export_allowed"])
        self.assertIn("missing_cost", untrusted["blocking_issue_codes"])

        trusted = validator.validate_node_cost(node, trusted_exception=True)
        self.assertTrue(trusted["export_allowed"])
        self.assertIn("missing_cost", trusted["blocking_issue_codes"])
        self.assertTrue(trusted["exception_applied"])
        self.assertEqual(trusted["exception_reason"], "trusted_base_graph_exception")


class NodeRequirementsTrustTests(unittest.TestCase):
    def test_trusted_id_is_exempt_whatever_its_type(self) -> None:
        """DEC-1 regression: trust is by identity, never by a type allowlist.

        The previous predicate also required the type to appear in an eight-name
        list, which matched 152 of the base graph's 5,170 nodes and dropped
        'United States Senate' because its type is 'Chamber'.
        """
        requirements = NodeRequirements()
        trusted_ids = {"leg-senate", "agency-alpha"}

        for node_type in ("Chamber", "Agency", "Subcommittee", "", "Wholly Invented Type"):
            with self.subTest(node_type=node_type):
                self.assertTrue(
                    requirements.is_trusted_exception_node(
                        {"id": "leg-senate", "name": "United States Senate", "type": node_type},
                        trusted_ids,
                    )
                )

        self.assertFalse(
            requirements.is_trusted_exception_node(
                {"id": "crawled-node", "name": "Crawled", "type": "Agency"}, trusted_ids
            )
        )


def _two_level_tree() -> dict[str, object]:
    return {
        "id": "root",
        "name": "Root",
        "type": "Foundation",
        "children": [
            {"id": "child-a", "name": "Child A", "type": "Department", "children": []},
            {"id": "child-b", "name": "Child B", "type": "Department", "children": []},
        ],
    }


class CostCascadeTests(unittest.TestCase):
    def test_budget_summary_anchors_the_root_and_reaches_children(self) -> None:
        tree = _two_level_tree()

        annotate_resolved_costs(tree, budget_summary={"government_total_outlay_amount": 3_000_000_000_000})

        self.assertEqual(tree["cost_status"], "root_total")
        self.assertEqual(tree["resolved_total_amount"], 3_000_000_000_000)
        for child in tree["children"]:
            self.assertIsNotNone(child["resolved_total_amount"])
            self.assertEqual(child["cost_status"], "allocated")

    def test_without_a_budget_summary_nothing_receives_a_cost(self) -> None:
        """The exact condition the publication guard exists for.

        With no Treasury total the cascade has nothing to apportion, so
        CostValidator blocks every node on missing_cost and the export gate
        prunes the whole tree. Pinned here so the guard can never be silently
        orphaned by a change to the cascade.
        """
        tree = _two_level_tree()

        annotate_resolved_costs(tree, budget_summary=None)

        self.assertEqual(tree["cost_status"], "unavailable")
        for child in tree["children"]:
            self.assertIsNone(child.get("resolved_total_amount"))


if __name__ == "__main__":
    unittest.main()
