from __future__ import annotations

import unittest
from unittest.mock import patch

from data_pipeline.processors.enrichment import enrich_nodes


class EnrichmentTests(unittest.TestCase):
    def test_enrich_nodes_extracts_leadership_positions_from_official_pages(self) -> None:
        existing_nodes = [
            {
                "id": "department-of-energy",
                "name": "Department of Energy",
                "type": "Department",
                "sourceUrls": ["https://www.energy.gov"],
                "children": [],
            }
        ]
        leadership_html = """
        <html>
          <body>
            <h1>Leadership</h1>
            <li>Secretary</li>
            <li>Deputy Secretary - Jane Doe</li>
            <li>Chief Financial Officer</li>
          </body>
        </html>
        """

        with patch("data_pipeline.processors.enrichment.request_text", return_value=leadership_html):
            enriched_nodes, edges, stats = enrich_nodes(
                existing_nodes=existing_nodes,
                direct_payload_nodes=[],
                max_http_nodes=1,
                http_timeout=1,
            )

        leadership_names = {node["name"] for node in enriched_nodes if node["type"] == "Position"}
        edge_types = {edge["type"] for edge in edges}

        self.assertIn("Secretary of Department of Energy", leadership_names)
        self.assertIn("Deputy Secretary of Department of Energy", leadership_names)
        self.assertGreaterEqual(stats["leadership_positions_added"], 2)
        self.assertGreaterEqual(stats["leadership_positions_by_source"]["official_http"], 2)
        self.assertIn("reports_to", edge_types)
        self.assertGreaterEqual(stats["relationships_by_type"]["reports_to"], 2)

    def test_enrich_nodes_links_parent_budget_and_extracts_relationships(self) -> None:
        existing_nodes = [
            {
                "id": "department-of-energy",
                "name": "Department of Energy",
                "type": "Department",
                "children": [],
            },
            {
                "id": "nasa",
                "name": "NASA",
                "type": "Agency",
                "children": [],
            },
            {
                "id": "office-of-grid-deployment",
                "name": "Office of Grid Deployment",
                "type": "Office",
                "parentId": "department-of-energy",
                "children": [],
            },
        ]

        enriched_nodes, edges, stats = enrich_nodes(
            existing_nodes=existing_nodes,
            direct_payload_nodes=[],
            official_directory_records=[
                {
                    "officeName": "Office of Grid Deployment",
                    "agencyName": "Department of Energy",
                    "sourceUrl": "https://www.energy.gov/gdo",
                    "directoryUrl": "https://www.energy.gov/organization-chart",
                    "description": "Office of Grid Deployment within the Department of Energy.",
                }
            ],
            federal_register_records=[
                {
                    "officeName": "Office of Grid Deployment",
                    "agencyName": "Department of Energy",
                    "departmentName": "Department of Energy",
                    "sourceUrl": "https://www.federalregister.gov/documents/example",
                    "description": "The Office of Grid Deployment was created in 2024 and collaborates with NASA.",
                }
            ],
            usaspending_payload={
                "nodes": [
                    {
                        "id": "department-of-energy",
                        "name": "Department of Energy",
                        "type": "Agency",
                        "budget": "123456789",
                        "budget_year": "2025",
                    }
                ]
            },
            max_http_nodes=0,
        )

        office = next(node for node in enriched_nodes if node["id"] == "office-of-grid-deployment")
        edge_types = {edge["type"] for edge in edges}

        self.assertEqual(office["annual_budget"], "123456789")
        self.assertEqual(office["budget_source"], "USAspending (parent budget)")
        self.assertIn("NASA", office["related_agencies"])
        self.assertIn("created_by", edge_types)
        self.assertIn("funds", edge_types)
        self.assertIn("collaborates_with", edge_types)
        self.assertEqual(stats["budgets_linked_by_source"]["usaspending_parent"], 1)
        self.assertGreaterEqual(stats["relationships_by_source"]["federal_register"], 1)


if __name__ == "__main__":
    unittest.main()
