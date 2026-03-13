from __future__ import annotations

import json
import shutil
import unittest
import uuid
from pathlib import Path

from data_pipeline.run_pipeline import run_pipeline


BASE_GRAPH = {
    "id": "root",
    "name": "Root",
    "type": "Foundation",
    "color": "#c8a84a",
    "children": [
        {
            "id": "department-of-energy",
            "name": "Department of Energy",
            "type": "Department",
            "children": [],
        }
    ],
}

TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"


class RunPipelineTests(unittest.TestCase):
    def test_run_pipeline_writes_graph_candidates_and_stats(self) -> None:
        tmp_path = TEST_TMP_ROOT / f"run-pipeline-{uuid.uuid4().hex}"
        tmp_path.mkdir(parents=True, exist_ok=True)
        try:
            base_graph_path = tmp_path / "base.json"
            graph_output_path = tmp_path / "graph.json"
            candidate_output_path = tmp_path / "candidate_nodes.json"
            nodes_output_path = tmp_path / "expanded_nodes.json"
            edges_output_path = tmp_path / "expanded_edges.json"
            stats_output_path = tmp_path / "pipeline_stats.json"
            enrichment_stats_output_path = tmp_path / "enrichment_stats.json"
            base_graph_path.write_text(json.dumps(BASE_GRAPH), encoding="utf-8")

            stats = run_pipeline(
                base_graph_path=base_graph_path,
                candidate_output_path=candidate_output_path,
                graph_output_path=graph_output_path,
                nodes_output_path=nodes_output_path,
                edges_output_path=edges_output_path,
                stats_output_path=stats_output_path,
                enrichment_stats_output_path=enrichment_stats_output_path,
                direct_payload_fetchers=[
                    lambda: {
                        "nodes": [
                            {
                                "id": "contractor-acme",
                                "name": "Acme Corp",
                                "type": "Corporation",
                                "sourceUrls": ["https://www.usaspending.gov/recipient/acme"],
                            }
                        ],
                        "edges": [
                            {
                                "source": "department-of-energy",
                                "target": "contractor-acme",
                                "type": "contracts_with",
                            }
                        ],
                    }
                ],
                discovery_fetchers={
                    "wikidata_records": lambda: [
                        {
                            "label": "Office of Grid Deployment",
                            "parentName": "Department of Energy",
                            "officialWebsite": "https://www.energy.gov/gdo/office-grid-deployment",
                            "wikidataId": "Q999",
                            "description": "Office discovered via Wikidata.",
                            "countryLabel": "United States",
                        }
                    ],
                    "official_directory_records": lambda: [],
                    "federal_register_records": lambda: [],
                },
            )

            graph = json.loads(graph_output_path.read_text(encoding="utf-8"))
            candidates = json.loads(candidate_output_path.read_text(encoding="utf-8"))
            saved_stats = json.loads(stats_output_path.read_text(encoding="utf-8"))

            self.assertTrue(graph_output_path.exists())
            self.assertTrue(candidate_output_path.exists())
            self.assertTrue(stats_output_path.exists())
            self.assertTrue(enrichment_stats_output_path.exists())
            self.assertGreaterEqual(stats["new_nodes_added"], 1)
            self.assertEqual(saved_stats["nodes_after"], stats["nodes_after"])
            self.assertTrue(any(node["name"] == "Office of Grid Deployment" for node in candidates))
            department = next(child for child in graph["children"] if child["id"] == "department-of-energy")
            self.assertTrue(any(child["id"] == "department-of-energy-office-of-grid-deployment" for child in department["children"]))
            self.assertIn("verification_breakdown", stats)
            self.assertIn("discovery_sources_used", stats)
            self.assertIn("wikidata_records", stats["discovery_sources_used"])
            self.assertIn("direct_payload_counts", stats)
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
