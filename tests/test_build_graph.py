from __future__ import annotations

import json
import shutil
import unittest
import uuid
from pathlib import Path

from data_pipeline.exporter.build_graph import build_graph


BASE_GRAPH = {
    "id": "root",
    "name": "Root",
    "type": "Foundation",
    "color": "#c8a84a",
    "children": [
        {
            "id": "agency-alpha",
            "name": "Agency Alpha",
            "type": "Agency",
            "color": "#4a8ac8",
            "children": [],
        }
    ],
}

TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"


def build_graph_with_paths(payloads: list[dict[str, object]]) -> object:
    tmp_path = TEST_TMP_ROOT / f"build-graph-{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=True)
    try:
        base_path = tmp_path / "base.json"
        graph_path = tmp_path / "graph.json"
        nodes_path = tmp_path / "nodes.json"
        edges_path = tmp_path / "edges.json"
        base_path.write_text(json.dumps(BASE_GRAPH), encoding="utf-8")
        return build_graph(
            payloads,
            base_graph_path=base_path,
            graph_output_path=graph_path,
            nodes_output_path=nodes_path,
            edges_output_path=edges_path,
        )
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


class BuildGraphTests(unittest.TestCase):
    def test_build_graph_attaches_related_and_unrelated_orphans_to_root(self) -> None:
        payloads = [
            {
                "nodes": [
                    {"id": "contractor-acme", "name": "Acme", "type": "Corporation"},
                    {"id": "floating-node", "name": "Floating", "type": "Corporation"},
                ],
                "edges": [
                    {"source": "agency-alpha", "target": "contractor-acme", "type": "contracts_with"},
                ],
            }
        ]

        result = build_graph_with_paths(payloads)

        exported_ids = {node["id"] for node in result.nodes}
        self.assertIn("contractor-acme", exported_ids)
        self.assertIn("floating-node", exported_ids)

        contractor = next(node for node in result.nodes if node["id"] == "contractor-acme")
        floating = next(node for node in result.nodes if node["id"] == "floating-node")
        self.assertTrue(contractor["attachToRoot"])
        self.assertTrue(floating["attachToRoot"])
        self.assertEqual(result.validation["attached_to_root"], 2)
        self.assertEqual(result.validation["nodes_removed_missing_parent"], 0)
        self.assertEqual(result.validation["root_attached_missing_parent_nodes"], 1)
        self.assertEqual(result.validation["nodes_reattached_to_root"], 2)

    def test_build_graph_keeps_hierarchical_parent_references(self) -> None:
        payloads = [
            {
                "nodes": [
                    {"id": "office-beta", "name": "Office Beta", "type": "Office"},
                ],
                "edges": [
                    {"source": "office-beta", "target": "agency-alpha", "type": "reports_to"},
                ],
            }
        ]

        result = build_graph_with_paths(payloads)

        office = next(node for node in result.nodes if node["id"] == "office-beta")
        self.assertEqual(office["parentId"], "agency-alpha")
        self.assertNotIn("attachToRoot", office)
        self.assertEqual(result.edges, [])

    def test_build_graph_keeps_explicit_root_attachments_without_edges(self) -> None:
        payloads = [
            {
                "nodes": [
                    {
                        "id": "special-advisor",
                        "name": "Special Advisor",
                        "type": "Position",
                        "attachToRoot": True,
                    },
                ],
                "edges": [],
            }
        ]

        result = build_graph_with_paths(payloads)

        advisor = next(node for node in result.nodes if node["id"] == "special-advisor")
        self.assertTrue(advisor["attachToRoot"])
        self.assertEqual(result.validation["attached_to_root"], 1)
        self.assertEqual(result.validation["nodes_removed_structural_errors"], 0)

    def test_build_graph_drops_edges_with_unknown_endpoints(self) -> None:
        payloads = [
            {
                "nodes": [
                    {"id": "contractor-acme", "name": "Acme", "type": "Corporation"},
                ],
                "edges": [
                    {"source": "agency-alpha", "target": "contractor-acme", "type": "contracts_with"},
                    {"source": "missing-source", "target": "contractor-acme", "type": "contracts_with"},
                    {"source": "agency-alpha", "target": "missing-target", "type": "contracts_with"},
                ],
            }
        ]

        result = build_graph_with_paths(payloads)

        self.assertEqual(len(result.edges), 1)
        self.assertEqual(result.validation["dropped_edges_missing_source"], 1)
        self.assertEqual(result.validation["dropped_edges_missing_target"], 1)

    def test_build_graph_exports_verification_metadata(self) -> None:
        payloads = [
            {
                "nodes": [
                    {
                        "id": "office-gamma",
                        "name": "Office Gamma",
                        "type": "Office",
                        "sourceUrls": [
                            "https://www.energy.gov/ne/office-gamma",
                            "https://www.wikidata.org/wiki/Q456",
                        ],
                    },
                ],
                "edges": [
                    {"source": "office-gamma", "target": "agency-alpha", "type": "reports_to"},
                ],
            }
        ]

        result = build_graph_with_paths(payloads)

        office = next(node for node in result.nodes if node["id"] == "office-gamma")
        self.assertEqual(office["verificationStatus"], "verified")
        self.assertEqual(office["sourceCount"], 2)
        self.assertGreater(office["confidenceScore"], 0.8)
        self.assertIn("verification_status_counts", result.validation)
        self.assertIn("verified_node_count", result.validation)
        self.assertIn("pipeline_summary", result.validation)
        self.assertEqual(result.validation["pipeline_summary"]["final_node_count"], len(result.nodes))
        self.assertIn("relationships", result.graph)


if __name__ == "__main__":
    unittest.main()
