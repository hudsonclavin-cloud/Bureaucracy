from __future__ import annotations

import unittest

from data_pipeline.processors.normalize_edges import normalize_edge
from data_pipeline.processors.normalize_nodes import normalize_node, verify_node_sources


class NormalizerTests(unittest.TestCase):
    def test_normalize_node_preserves_description_aliases_and_unknown_fields(self) -> None:
        node = normalize_node(
            {
                "name": "Deputy Director",
                "type": "Role",
                "description": "Leads the office when the director is absent.",
                "bio": "Career civil servant.",
                "customField": {"source": "imported"},
            }
        )

        self.assertEqual(node["type"], "Role")
        self.assertEqual(node["desc"], "Leads the office when the director is absent.")
        self.assertEqual(node["description"], "Leads the office when the director is absent.")
        self.assertEqual(node["bio"], "Career civil servant.")
        self.assertEqual(node["customField"], {"source": "imported"})

    def test_normalize_node_preserves_attach_to_root_flag(self) -> None:
        node = normalize_node(
            {
                "name": "Acme Corp",
                "type": "Corporation",
                "attachToRoot": True,
            }
        )

        self.assertTrue(node["attachToRoot"])
        self.assertEqual(node["id"], "acme-corp")

    def test_normalize_edge_rejects_self_loop(self) -> None:
        edge = normalize_edge(
            {
                "source": "same-node",
                "target": "same-node",
                "type": "contracts_with",
            }
        )

        self.assertIsNone(edge)

    def test_normalize_edge_normalizes_unknown_relationship_to_manages(self) -> None:
        edge = normalize_edge(
            {
                "source": "alpha",
                "target": "beta",
                "type": "custom relationship",
            }
        )

        self.assertEqual(edge["type"], "manages")

    def test_verify_node_sources_scores_official_and_wikidata_sources(self) -> None:
        node = verify_node_sources(
            {
                "id": "office-nuclear-energy",
                "sourceUrls": [
                    "https://energy.gov/ne",
                    "https://www.wikidata.org/wiki/Q123",
                ],
            }
        )

        self.assertEqual(node["sourceCount"], 2)
        self.assertEqual(node["verificationStatus"], "verified")
        self.assertGreaterEqual(node["confidenceScore"], 0.9)
        self.assertIn("official_site", node["sourceTypes"])
        self.assertIn("wikidata", node["sourceTypes"])

    def test_verify_node_sources_uses_official_website_and_sets_proof_fields(self) -> None:
        node = verify_node_sources(
            {
                "id": "agency-alpha",
                "official_website": "https://www.energy.gov/agency-alpha",
                "sourceTypes": ["official_http", "usaspending_direct"],
            }
        )

        self.assertEqual(node["sourceCount"], 1)
        self.assertTrue(node["existsProven"])
        self.assertEqual(node["proofStatus"], "proven")
        self.assertEqual(node["proofReason"], "official_source_recorded")
        self.assertEqual(node["proofSourceCount"], 2)
        self.assertIn("official_site", node["proofSourceTypes"])
        self.assertIn("official_financial_record", node["proofSourceTypes"])

    def test_verify_node_sources_keeps_non_official_website_as_metadata_only(self) -> None:
        node = verify_node_sources(
            {
                "id": "agency-beta",
                "official_website": "https://example.com/agency-beta",
                "sourceTypes": ["wikidata"],
            }
        )

        self.assertEqual(node["official_website"], "https://example.com/agency-beta")
        self.assertEqual(node["sourceCount"], 0)
        self.assertEqual(node["proofSourceCount"], 1)
        self.assertNotIn("official_site", node["sourceTypes"])
        self.assertNotIn("official_site", node["proofSourceTypes"])
        self.assertEqual(node["proofStatus"], "unproven")


if __name__ == "__main__":
    unittest.main()
