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
            "children": [
                {
                    "id": "office-base",
                    "name": "Office Base",
                    "type": "Office",
                    "children": [],
                }
            ],
        }
    ],
}

TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"


def count_id_occurrences(tree: dict, node_id: str) -> int:
    count = 1 if tree.get("id") == node_id else 0
    for child in tree.get("children", []):
        if isinstance(child, dict):
            count += count_id_occurrences(child, node_id)
    return count


def find_tree_node(tree: dict, node_id: str) -> dict | None:
    if tree.get("id") == node_id:
        return tree
    for child in tree.get("children", []):
        if isinstance(child, dict):
            found = find_tree_node(child, node_id)
            if found is not None:
                return found
    return None


def build_graph_with_paths(
    payloads: list[dict[str, object]],
    *,
    enforce_export_gate: bool = False,
) -> object:
    tmp_path = TEST_TMP_ROOT / f"build-graph-{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=True)
    try:
        base_path = tmp_path / "base.json"
        graph_path = tmp_path / "graph.json"
        nodes_path = tmp_path / "nodes.json"
        edges_path = tmp_path / "edges.json"
        validity_report_path = tmp_path / "node_validity_report.json"
        base_path.write_text(json.dumps(BASE_GRAPH), encoding="utf-8")
        return build_graph(
            payloads,
            base_graph_path=base_path,
            graph_output_path=graph_path,
            nodes_output_path=nodes_path,
            edges_output_path=edges_path,
            validity_report_output_path=validity_report_path,
            enforce_export_gate=enforce_export_gate,
        )
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


class BuildGraphTests(unittest.TestCase):
    def test_build_graph_keeps_related_orphans_and_drops_unplaceable_ones(self) -> None:
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
        self.assertNotIn("floating-node", exported_ids)

        contractor = next(node for node in result.nodes if node["id"] == "contractor-acme")
        self.assertTrue(contractor["attachToRoot"])
        self.assertEqual(result.validation["nodes_removed_missing_parent"], 0)
        self.assertEqual(result.validation["root_attached_missing_parent_nodes"], 1)
        self.assertEqual(result.validation["nodes_reattached_to_root"], 1)

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

    def test_build_graph_does_not_duplicate_existing_nested_node_at_root(self) -> None:
        payloads = [
            {
                "nodes": [
                    {"id": "office-base", "name": "Office Base", "type": "Office"},
                ],
                "edges": [],
            }
        ]

        result = build_graph_with_paths(payloads)

        self.assertEqual(count_id_occurrences(result.graph, "office-base"), 1)
        agency = find_tree_node(result.graph, "agency-alpha")
        self.assertTrue(any(child["id"] == "office-base" for child in agency["children"]))
        office = next(node for node in result.nodes if node["id"] == "office-base")
        self.assertNotIn("attachToRoot", office)
        self.assertNotIn("office-base", {child.get("id") for child in result.graph["children"]})

    def test_build_graph_does_not_duplicate_base_subtree_on_reports_to_edge(self) -> None:
        payloads = [
            {
                "nodes": [
                    {"id": "agency-alpha", "name": "Agency Alpha", "type": "Agency"},
                    {"id": "new-parent", "name": "New Parent", "type": "Agency"},
                ],
                "edges": [
                    {"source": "agency-alpha", "target": "new-parent", "type": "reports_to"},
                ],
            }
        ]

        result = build_graph_with_paths(payloads)

        self.assertEqual(count_id_occurrences(result.graph, "agency-alpha"), 1)
        self.assertEqual(count_id_occurrences(result.graph, "office-base"), 1)
        self.assertEqual(count_id_occurrences(result.graph, "new-parent"), 1)
        # The base placement stays authoritative for nodes already in the tree.
        self.assertIn("agency-alpha", {child.get("id") for child in result.graph["children"]})
        agency = find_tree_node(result.graph, "agency-alpha")
        self.assertNotIn("parentId", agency)
        # The hierarchical edge survives as an exported relationship instead.
        self.assertIn(
            {"source": "agency-alpha", "target": "new-parent", "type": "reports_to"},
            result.edges,
        )

    def test_build_graph_reports_to_cycle_falls_back_to_root(self) -> None:
        payloads = [
            {
                "nodes": [
                    {"id": "cyc-a", "name": "Cycle A", "type": "Agency"},
                    {"id": "cyc-b", "name": "Cycle B", "type": "Agency"},
                ],
                "edges": [
                    {"source": "cyc-a", "target": "cyc-b", "type": "reports_to"},
                    {"source": "cyc-b", "target": "cyc-a", "type": "reports_to"},
                ],
            }
        ]

        result = build_graph_with_paths(payloads)

        self.assertEqual(count_id_occurrences(result.graph, "cyc-a"), 1)
        self.assertEqual(count_id_occurrences(result.graph, "cyc-b"), 1)
        self.assertEqual(result.validation["cycle_fallback_root_attachments"], 1)
        # The cluster stays reachable from the root.
        root_child_ids = {child.get("id") for child in result.graph["children"]}
        self.assertIn("cyc-b", root_child_ids)
        cycle_root = find_tree_node(result.graph, "cyc-b")
        self.assertTrue(any(child["id"] == "cyc-a" for child in cycle_root["children"]))

    def test_build_graph_duplicate_hierarchical_edges_keep_primary_parent(self) -> None:
        payloads = [
            {
                "nodes": [
                    {"id": "office-multi", "name": "Office Multi", "type": "Office"},
                    {"id": "parent-two", "name": "Parent Two", "type": "Agency"},
                ],
                "edges": [
                    {"source": "office-multi", "target": "agency-alpha", "type": "reports_to"},
                    {"source": "office-multi", "target": "parent-two", "type": "reports_to"},
                ],
            }
        ]

        result = build_graph_with_paths(payloads)

        office = next(node for node in result.nodes if node["id"] == "office-multi")
        self.assertEqual(office["parentId"], "agency-alpha")
        exported_pairs = [(edge["source"], edge["target"]) for edge in result.edges]
        self.assertIn(("office-multi", "parent-two"), exported_pairs)
        self.assertNotIn(("office-multi", "agency-alpha"), exported_pairs)
        self.assertEqual(result.validation["relationship_counts"]["reports_to"], 2)
        self.assertEqual(result.validation["input_edge_count"], 2)

    def test_build_graph_falls_back_to_valid_secondary_parent_edge(self) -> None:
        payloads = [
            {
                "nodes": [
                    {"id": "office-fallback", "name": "Office Fallback", "type": "Office"},
                ],
                "edges": [
                    {"source": "office-fallback", "target": "ghost-parent", "type": "reports_to"},
                    {"source": "office-fallback", "target": "agency-alpha", "type": "reports_to"},
                ],
            }
        ]

        result = build_graph_with_paths(payloads)

        office = next(node for node in result.nodes if node["id"] == "office-fallback")
        # The primary edge target is unknown, so the kept secondary edge supplies the parent.
        self.assertEqual(office["parentId"], "agency-alpha")
        self.assertNotIn("attachToRoot", office)
        self.assertEqual(result.validation["orphaned_parent_ids"], 1)
        self.assertEqual(result.validation["dropped_edges_missing_target"], 1)
        exported_pairs = [(edge["source"], edge["target"]) for edge in result.edges]
        self.assertNotIn(("office-fallback", "agency-alpha"), exported_pairs)
        agency = find_tree_node(result.graph, "agency-alpha")
        self.assertTrue(any(child["id"] == "office-fallback" for child in agency["children"]))

    def test_build_graph_counts_hierarchical_edges_in_validation_stats(self) -> None:
        payloads = [
            {
                "nodes": [
                    {"id": "office-ghost", "name": "Office Ghost", "type": "Office"},
                ],
                "edges": [
                    {"source": "office-ghost", "target": "ghost-parent", "type": "reports_to"},
                ],
            }
        ]

        result = build_graph_with_paths(payloads)

        self.assertEqual(result.validation["input_edge_count"], 1)
        self.assertEqual(result.validation["relationship_counts"]["reports_to"], 1)
        self.assertEqual(result.validation["dropped_edges_missing_target"], 1)
        self.assertEqual(result.validation["orphaned_parent_ids"], 1)
        office = next(node for node in result.nodes if node["id"] == "office-ghost")
        self.assertTrue(office["attachToRoot"])
        self.assertNotIn("parentId", office)


if __name__ == "__main__":
    unittest.main()
