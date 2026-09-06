from __future__ import annotations

import os
import unittest
from unittest import mock

from data_pipeline.discovery.source_discovery import (
    build_candidate_node,
    discover_candidates,
    iter_tree_nodes,
    normalize_candidate_parent,
    promote_candidates,
)


class SourceDiscoveryTests(unittest.TestCase):
    def test_discover_candidates_builds_review_queue_records(self) -> None:
        # Template leadership positions are opt-in (PIPELINE_ENABLE_TEMPLATE_LEADERSHIP);
        # this fixture asserts on them, so it opts in explicitly.
        with mock.patch.dict(os.environ, {"PIPELINE_ENABLE_TEMPLATE_LEADERSHIP": "1"}):
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
        with mock.patch.dict(os.environ, {"PIPELINE_ENABLE_TEMPLATE_LEADERSHIP": "1"}):
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

    def test_parentless_and_nameless_candidates_are_handled(self) -> None:
        self.assertIsNone(normalize_candidate_parent(None))
        self.assertIsNone(normalize_candidate_parent(""))
        self.assertIsNone(normalize_candidate_parent("   "))

        # A record without a name must be dropped, not coined "Unnamed Node".
        self.assertIsNone(
            build_candidate_node(
                name="",
                possible_parent="Department of Energy",
                source_url="https://www.energy.gov/listing",
                discovery_method="federal_register_listing_scan",
            )
        )

        candidates = discover_candidates(
            federal_register_records=[
                {
                    "officeName": "Office of Deep Sea Studies",
                    "departmentName": "",
                    "documentUrl": "https://www.federalregister.gov/agencies/deep-sea",
                }
            ],
            existing_nodes=[],
        )
        record = next(item for item in candidates if item["name"] == "Office of Deep Sea Studies")
        self.assertIsNone(record["possibleParent"])
        self.assertNotIn("unnamed-node", record["id"])

    def test_dedupe_matches_offices_nested_in_base_graph_tree(self) -> None:
        base_root = {
            "id": "root",
            "name": "Federal Government",
            "type": "Branch",
            "children": [
                {
                    "id": "department-of-energy",
                    "name": "Department of Energy",
                    "type": "Cabinet Department",
                    "children": [
                        {
                            "id": "office-of-science",
                            "name": "Office of Science",
                            "type": "Office",
                            "children": [],
                        }
                    ],
                }
            ],
        }
        candidates = discover_candidates(
            org_chart_records=[
                {
                    "agencyName": "Department of Energy",
                    "officeName": "Office of Science",
                    "parentAgency": "Department of Energy",
                    "pageUrl": "https://www.energy.gov/org-chart",
                }
            ],
            existing_nodes=list(iter_tree_nodes(base_root)),
        )

        # The nested office carries no parentId in the base graph, but the
        # tree walk must still index it so it is not re-discovered.
        self.assertFalse(any(item["name"] == "Office of Science" for item in candidates))

    def test_promote_merges_rediscovered_nested_office_instead_of_duplicating(self) -> None:
        base_root = {
            "id": "root",
            "name": "Federal Government",
            "type": "Branch",
            "children": [
                {
                    "id": "department-of-energy",
                    "name": "Department of Energy",
                    "type": "Cabinet Department",
                    "children": [
                        {
                            "id": "office-of-science",
                            "name": "Office of Science",
                            "type": "Office",
                            "sourceUrls": ["https://www.energy.gov/science"],
                            "children": [],
                        }
                    ],
                }
            ],
        }
        candidates = [
            {
                "id": "department-of-energy-office-of-science",
                "name": "Office of Science",
                "type": "Office",
                "possibleParent": "Department of Energy",
                "desc": "Rediscovered office.",
                "sourceUrls": ["https://www.energy.gov/science/org-chart"],
                "confidenceScore": 0.9,
                "discoveryConfidenceEstimate": 0.81,
            }
        ]

        promoted, stats = promote_candidates(
            candidates,
            existing_nodes=list(iter_tree_nodes(base_root)),
        )

        self.assertEqual(stats["merged_duplicates"], 1)
        self.assertEqual(stats["promoted_new_nodes"], 0)
        merged = promoted[0]
        self.assertEqual(merged["id"], "office-of-science")
        self.assertEqual(merged["parentId"], "department-of-energy")

    def test_bare_name_merges_collapse_into_one_record_per_base_node(self) -> None:
        base_root = {
            "id": "root",
            "name": "Federal Government",
            "type": "Branch",
            "children": [
                {
                    "id": "department-of-energy",
                    "name": "Department of Energy",
                    "type": "Cabinet Department",
                    "children": [
                        {
                            "id": "office-of-science",
                            "name": "Office of Science",
                            "type": "Office",
                            "children": [],
                        }
                    ],
                },
                {"id": "nasa", "name": "NASA", "type": "Independent Agency", "children": []},
            ],
        }
        # Same office rediscovered twice with differing claimed parents: both
        # must merge into the single base node, never emit duplicate ids.
        candidates = [
            {
                "id": "a1",
                "name": "Office of Science",
                "type": "Office",
                "parentId": "nasa",
                "sourceUrls": ["https://www.nasa.gov/x"],
                "discoveryConfidenceEstimate": 0.81,
            },
            {
                "id": "a2",
                "name": "Office of Science",
                "type": "Office",
                "sourceUrls": ["https://www.energy.gov/y"],
                "discoveryConfidenceEstimate": 0.81,
            },
        ]

        promoted, stats = promote_candidates(
            candidates,
            existing_nodes=list(iter_tree_nodes(base_root)),
        )

        self.assertEqual(stats["merged_duplicates"], 2)
        self.assertEqual(len(promoted), 1)
        merged = promoted[0]
        self.assertEqual(merged["id"], "office-of-science")
        self.assertEqual(merged["parentId"], "department-of-energy")
        self.assertIn("https://www.nasa.gov/x", merged["sourceUrls"])
        self.assertIn("https://www.energy.gov/y", merged["sourceUrls"])

    def test_single_gov_source_candidate_stays_in_review_queue(self) -> None:
        existing_nodes = [
            {
                "id": "department-of-energy",
                "name": "Department of Energy",
                "type": "Cabinet Department",
                "children": [],
            }
        ]
        candidates = discover_candidates(
            official_directory_records=[
                {
                    "officeName": "Fragment Office Of Something",
                    "agencyName": "Department of Energy",
                    "directoryUrl": "https://www.energy.gov/leadership",
                }
            ],
            existing_nodes=existing_nodes,
        )
        target = next(item for item in candidates if item["name"] == "Fragment Office Of Something")
        # The URL-derived confidenceScore is exactly 0.7 for a single .gov
        # source; the promotion gate must use the discovery estimate instead.
        self.assertGreaterEqual(float(target["confidenceScore"]), 0.7)
        self.assertLess(float(target["discoveryConfidenceEstimate"]), 0.7)

        promoted, stats = promote_candidates([target], existing_nodes=existing_nodes)

        self.assertEqual(promoted, [])
        self.assertEqual(stats["candidates_below_threshold"], 1)
        self.assertEqual(stats["promoted_new_nodes"], 0)


if __name__ == "__main__":
    unittest.main()
