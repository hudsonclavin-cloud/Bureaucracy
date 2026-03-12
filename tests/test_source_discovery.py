from __future__ import annotations

import unittest

from data_pipeline.discovery.source_discovery import discover_candidates


class SourceDiscoveryTests(unittest.TestCase):
    def test_discover_candidates_builds_review_queue_records(self) -> None:
        candidates = discover_candidates(
            wikidata_records=[
                {
                    "label": "Office of Advanced Reactors",
                    "parentName": "Department of Energy",
                    "url": "https://www.wikidata.org/wiki/Q999",
                }
            ],
            official_directory_records=[
                {
                    "officeName": "Office of Clean Energy Demonstrations",
                    "agencyName": "Department of Energy",
                    "directoryUrl": "https://www.energy.gov/oced",
                }
            ],
        )

        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0]["name"], "Office of Clean Energy Demonstrations")
        self.assertIn("confidenceEstimate", candidates[0])
        self.assertIn("discoveryMethod", candidates[0])


if __name__ == "__main__":
    unittest.main()
