from __future__ import annotations

import unittest

from data_pipeline.discovery.source_discovery import discover_candidates, promote_candidates


class SourceDiscoveryTests(unittest.TestCase):
    def test_discover_candidates_builds_review_queue_records(self) -> None:
        candidates = discover_candidates(
            wikidata_records=[
                {
                    "label": "Office of Advanced Reactors",
                    "description": "Oversees advanced reactor programs.",
                    "parentName": "Department of Energy",
                    "officialWebsite": "https://www.energy.gov/ne/office-advanced-reactors",
                    "wikidataId": "Q999",
                    "countryLabel": "United States",
                }
            ],
            advisory_committee_records=[
                {
                    "committeeName": "Advanced Reactor Advisory Committee",
                    "parentAgency": "Department of Energy",
                    "chair": "Jane Doe",
                    "members": ["A", "B", "C"],
                    "sourceUrl": "https://www.energy.gov/advisory/advanced-reactor-advisory-committee",
                }
            ],
            org_chart_records=[
                {
                    "agencyName": "NASA",
                    "officeName": "Office of Space Technology",
                    "parentAgency": "NASA",
                    "pageUrl": "https://www.nasa.gov/organization/",
                    "description": "NASA organization chart office listing.",
                }
            ],
            existing_nodes=[
                {
                    "id": "department-of-energy",
                    "name": "Department of Energy",
                    "type": "Cabinet Department",
                    "children": [],
                },
                {
                    "id": "office-of-clean-energy-demonstrations",
                    "name": "Office of Clean Energy Demonstrations",
                    "type": "Office",
                    "parentId": "department-of-energy",
                    "children": [],
                },
            ],
        )

        self.assertGreaterEqual(len(candidates), 7)
        self.assertTrue(any(item["name"] == "Advanced Reactor Advisory Committee" for item in candidates))
        self.assertIn("confidenceEstimate", candidates[0])
        self.assertIn("discoveryMethod", candidates[0])
        self.assertIn("description", candidates[0])
        self.assertTrue(any(item["name"] == "Director" and item["possibleParent"] == "Office of Clean Energy Demonstrations" for item in candidates))
        self.assertTrue(any(item["name"] == "Office of Space Technology" for item in candidates))
        self.assertTrue(any(item.get("wikidataId") == "Q999" for item in candidates))

    def test_discover_candidates_dedupes_existing_entities(self) -> None:
        candidates = discover_candidates(
            org_chart_records=[
                {
                    "agencyName": "Department of Energy",
                    "officeName": "Office of Nuclear Energy",
                    "parentAgency": "Department of Energy",
                    "pageUrl": "https://www.energy.gov/org-chart",
                }
            ],
            existing_nodes=[
                {
                    "id": "office-of-nuclear-energy",
                    "name": "Office of Nuclear Energy",
                    "type": "Office",
                    "parentId": "department-of-energy",
                    "children": [],
                },
                {
                    "id": "department-of-energy",
                    "name": "Department of Energy",
                    "type": "Cabinet Department",
                    "children": [],
                },
            ],
        )

        self.assertFalse(any(item["name"] == "Office of Nuclear Energy" for item in candidates))
        self.assertTrue(any(item["name"] == "Director" and item["possibleParent"] == "Office of Nuclear Energy" for item in candidates))

    def test_promote_candidates_adds_high_confidence_nodes_and_merges_duplicates(self) -> None:
        candidates = [
            {
                "id": "department-of-energy-office-of-cybersecurity",
                "name": "Office of Cybersecurity",
                "type": "Office",
                "parentId": "department-of-energy",
                "possibleParent": "Department of Energy",
                "desc": "Official office listing.",
                "sourceUrls": [
                    "https://www.energy.gov/organization-chart",
                    "https://www.wikidata.org/wiki/Q123",
                ],
                "sourceTypes": ["official_site", "wikidata"],
                "confidenceScore": 0.9,
                "verificationStatus": "verified",
                "lastVerified": "2026-03-12",
            },
            {
                "id": "candidate-office-of-nuclear-energy",
                "name": "Office of Nuclear Energy",
                "type": "Office",
                "parentId": "department-of-energy",
                "possibleParent": "Department of Energy",
                "desc": "Duplicate office with new sources.",
                "sourceUrls": [
                    "https://www.energy.gov/ne/office-of-nuclear-energy",
                    "https://www.wikidata.org/wiki/Q456",
                ],
                "sourceTypes": ["official_site", "wikidata"],
                "confidenceScore": 0.9,
                "verificationStatus": "verified",
                "lastVerified": "2026-03-12",
            },
        ]
        existing_nodes = [
            {
                "id": "department-of-energy",
                "name": "Department of Energy",
                "type": "Cabinet Department",
                "children": [],
            },
            {
                "id": "office-of-nuclear-energy",
                "name": "Office of Nuclear Energy",
                "type": "Office",
                "parentId": "department-of-energy",
                "sourceUrls": ["https://www.energy.gov/ne"],
                "children": [],
            },
        ]

        promoted, stats = promote_candidates(candidates, existing_nodes=existing_nodes)

        self.assertEqual(stats["promoted_new_nodes"], 1)
        self.assertEqual(stats["merged_duplicates"], 1)
        self.assertTrue(any(item["id"] == "department-of-energy-office-of-cybersecurity" for item in promoted))
        merged = next(item for item in promoted if item["id"] == "office-of-nuclear-energy")
        self.assertIn("https://www.wikidata.org/wiki/Q456", merged["sourceUrls"])


if __name__ == "__main__":
    unittest.main()
