from __future__ import annotations

import unittest

from data_pipeline.discovery.source_discovery import discover_candidates


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


if __name__ == "__main__":
    unittest.main()
