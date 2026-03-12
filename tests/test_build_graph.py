from __future__ import annotations

import json
import tempfile
import unittest
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


class BuildGraphTests(unittest.TestCase):
    def test_build_graph_attaches_related_orphans_to_root_and_drops_unrelated_nodes(self) -> None:
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

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            base_path = tmp_path / "base.json"
            nodes_path = tmp_path / "nodes.json"
            edges_path = tmp_path / "edges.json"
            base_path.write_text(json.dumps(BASE_GRAPH), encoding="utf-8")

            result = build_graph(
                payloads,
                base_graph_path=base_path,
                nodes_output_path=nodes_path,
                edges_output_path=edges_path,
            )

        exported_ids = {node["id"] for node in result.nodes}
        self.assertIn("contractor-acme", exported_ids)
        self.assertNotIn("floating-node", exported_ids)

        contractor = next(node for node in result.nodes if node["id"] == "contractor-acme")
        self.assertTrue(contractor["attachToRoot"])
        self.assertEqual(result.validation["attached_to_root"], 1)
        self.assertEqual(result.validation["dropped_orphan_nodes"], 1)

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

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            base_path = tmp_path / "base.json"
            nodes_path = tmp_path / "nodes.json"
            edges_path = tmp_path / "edges.json"
            base_path.write_text(json.dumps(BASE_GRAPH), encoding="utf-8")

            result = build_graph(
                payloads,
                base_graph_path=base_path,
                nodes_output_path=nodes_path,
                edges_output_path=edges_path,
            )

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

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            base_path = tmp_path / "base.json"
            nodes_path = tmp_path / "nodes.json"
            edges_path = tmp_path / "edges.json"
            base_path.write_text(json.dumps(BASE_GRAPH), encoding="utf-8")

            result = build_graph(
                payloads,
                base_graph_path=base_path,
                nodes_output_path=nodes_path,
                edges_output_path=edges_path,
            )

        advisor = next(node for node in result.nodes if node["id"] == "special-advisor")
        self.assertTrue(advisor["attachToRoot"])
        self.assertEqual(result.validation["attached_to_root"], 1)
        self.assertEqual(result.validation["dropped_orphan_nodes"], 0)

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

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            base_path = tmp_path / "base.json"
            nodes_path = tmp_path / "nodes.json"
            edges_path = tmp_path / "edges.json"
            base_path.write_text(json.dumps(BASE_GRAPH), encoding="utf-8")

            result = build_graph(
                payloads,
                base_graph_path=base_path,
                nodes_output_path=nodes_path,
                edges_output_path=edges_path,
            )

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

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            base_path = tmp_path / "base.json"
            nodes_path = tmp_path / "nodes.json"
            edges_path = tmp_path / "edges.json"
            base_path.write_text(json.dumps(BASE_GRAPH), encoding="utf-8")

            result = build_graph(
                payloads,
                base_graph_path=base_path,
                nodes_output_path=nodes_path,
                edges_output_path=edges_path,
            )

        office = next(node for node in result.nodes if node["id"] == "office-gamma")
        self.assertEqual(office["verificationStatus"], "verified")
        self.assertEqual(office["sourceCount"], 2)
        self.assertGreater(office["confidenceScore"], 0.8)
        self.assertIn("verification_status_counts", result.validation)


if __name__ == "__main__":
    unittest.main()
