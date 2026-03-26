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

    def test_enrich_nodes_attaches_treasury_rollup_outlays(self) -> None:
        existing_nodes = [
            {
                "id": "department-of-energy",
                "name": "Department of Energy",
                "type": "Department",
                "children": [],
            },
            {
                "id": "department-of-defense",
                "name": "Department of Defense (DoD)",
                "type": "Department",
                "children": [],
            }
        ]

        enriched_nodes, edges, stats = enrich_nodes(
            existing_nodes=existing_nodes,
            direct_payload_nodes=[],
            treasury_outlay_payload={
                "outlayRows": [
                    {
                        "name": "Department of Energy",
                        "originalName": "Total--Department of Energy",
                        "rollup_total_amount": 987654321.0,
                        "amount_kind": "fytd_net_outlays",
                        "budget_year": "2026",
                        "budget_as_of": "2026-02-28",
                        "source_system": "Treasury Fiscal Data",
                        "budget_source": "Treasury MTS Table 5",
                        "allocation_basis": "treasury_rollup",
                        "sourceUrls": ["https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/outlays-of-the-u-s-government"],
                        "sourceTypes": ["official_site"],
                        "sequence_level": 2,
                        "print_order": 100,
                    },
                    {
                        "name": "Department of Defense--Military Programs",
                        "originalName": "Department of Defense--Military Programs",
                        "rollup_total_amount": 393327577008.87,
                        "amount_kind": "fytd_net_outlays",
                        "budget_year": "2026",
                        "budget_as_of": "2026-02-28",
                        "source_system": "Treasury Fiscal Data",
                        "budget_source": "Treasury MTS Table 5",
                        "allocation_basis": "treasury_rollup",
                        "sourceUrls": ["https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/outlays-of-the-u-s-government"],
                        "sourceTypes": ["official_site"],
                        "sequence_level": 2,
                        "print_order": 200,
                    }
                ],
                "budgetSummary": {
                    "government_total_outlay_amount": 3102409296183.04,
                },
            },
            max_http_nodes=0,
        )

        department = next(node for node in enriched_nodes if node["id"] == "department-of-energy")
        defense = next(node for node in enriched_nodes if node["id"] == "department-of-defense")
        self.assertEqual(department["rollup_total_amount"], 987654321.0)
        self.assertEqual(department["amount_kind"], "fytd_net_outlays")
        self.assertEqual(department["budget_as_of"], "2026-02-28")
        self.assertEqual(department["source_system"], "Treasury Fiscal Data")
        self.assertEqual(department["allocation_basis"], "treasury_rollup")
        self.assertIn("fiscaldata.treasury.gov", "".join(department["sourceUrls"]))
        self.assertEqual(defense["rollup_total_amount"], 393327577008.87)
        self.assertEqual(edges, [])
        self.assertEqual(stats["budgets_linked_by_source"]["treasury_outlays"], 2)


if __name__ == "__main__":
    unittest.main()
