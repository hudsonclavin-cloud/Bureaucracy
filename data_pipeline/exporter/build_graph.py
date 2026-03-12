from __future__ import annotations

from copy import deepcopy
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.processors.normalize_edges import EdgeRegistry
from data_pipeline.processors.normalize_nodes import (
    NodeRegistry,
    load_existing_node_ids,
    merge_node,
    verify_node_sources,
)


DEFAULT_BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"
DEFAULT_GRAPH_OUTPUT = DEFAULT_OUTPUT_DIR / "graph.json"
DEFAULT_NODES_OUTPUT = DEFAULT_OUTPUT_DIR / "expanded_nodes.json"
DEFAULT_EDGES_OUTPUT = DEFAULT_OUTPUT_DIR / "expanded_edges.json"
HIERARCHICAL_RELATIONSHIPS = {"reports_to", "subsidiary_of"}


@dataclass
class BuildResult:
    nodes: list[dict[str, Any]]
    edges: list[dict[str, str]]
    graph: dict[str, Any]
    graph_path: Path
    nodes_path: Path
    edges_path: Path
    validation: dict[str, Any]


def iter_payload_items(payloads: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    for payload in payloads:
        if isinstance(payload, dict):
            yield payload


def count_payload_nodes(payloads: Iterable[dict[str, Any]]) -> int:
    total = 0
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        total += sum(1 for node in payload.get("nodes", []) if isinstance(node, dict))
    return total


def format_pipeline_summary(summary: dict[str, int]) -> str:
    return "\n".join(
        [
            "PIPELINE SUMMARY",
            "----------------",
            f"Initial node count: {summary['initial_node_count']}",
            f"Raw nodes loaded: {summary['raw_nodes_loaded']}",
            f"After normalization: {summary['nodes_after_normalization']}",
            f"After merge: {summary['nodes_after_merge']}",
            f"Nodes removed missing parent: {summary['nodes_removed_missing_parent']}",
            f"Nodes reattached to root: {summary['nodes_reattached_to_root']}",
            f"Nodes removed structural errors: {summary['nodes_removed_structural_errors']}",
            f"Final node count: {summary['final_node_count']}",
        ]
    )


def build_parent_index(edges: list[dict[str, str]]) -> dict[str, str]:
    parent_by_child: dict[str, str] = {}
    for edge in edges:
        if edge["type"] not in HIERARCHICAL_RELATIONSHIPS:
            continue
        parent_by_child.setdefault(edge["source"], edge["target"])
    return parent_by_child


def split_hierarchical_edges(edges: list[dict[str, str]], parent_by_child: dict[str, str]) -> list[dict[str, str]]:
    exported_edges: list[dict[str, str]] = []
    for edge in edges:
        if edge["type"] in HIERARCHICAL_RELATIONSHIPS and parent_by_child.get(edge["source"]) == edge["target"]:
            continue
        exported_edges.append(edge)
    return exported_edges


def load_base_graph(base_graph_path: str | Path) -> dict[str, Any]:
    path = Path(base_graph_path)
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, dict):
            return payload
    return {
        "id": "root",
        "name": "Root",
        "type": "Foundation",
        "color": "#c8a84a",
        "desc": "Root of the graph.",
        "children": [],
    }


def walk_tree(root: dict[str, Any]) -> Iterable[tuple[dict[str, Any], dict[str, Any] | None]]:
    stack: list[tuple[dict[str, Any], dict[str, Any] | None]] = [(root, None)]
    while stack:
        current, parent = stack.pop()
        yield current, parent
        children = [child for child in current.get("children", []) if isinstance(child, dict)]
        stack.extend((child, current) for child in reversed(children))


def index_tree(root: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    node_map: dict[str, dict[str, Any]] = {}
    parent_map: dict[str, str] = {}
    for node, parent in walk_tree(root):
        node_id = str(node.get("id") or "").strip()
        if not node_id:
            continue
        node_map[node_id] = node
        if parent and parent.get("id"):
            parent_map[node_id] = str(parent["id"])
    return node_map, parent_map


def safe_attach_child(
    parent: dict[str, Any],
    child: dict[str, Any],
    *,
    parent_map: dict[str, str],
) -> bool:
    parent_id = str(parent.get("id") or "").strip()
    child_id = str(child.get("id") or "").strip()
    if not parent_id or not child_id or parent_id == child_id:
        return False
    if any(str(existing.get("id") or "") == child_id for existing in parent.get("children", [])):
        parent_map[child_id] = parent_id
        return True

    cursor_id = parent_id
    while cursor_id:
        if cursor_id == child_id:
            return False
        cursor_id = parent_map.get(cursor_id, "")

    parent.setdefault("children", []).append(child)
    parent_map[child_id] = parent_id
    return True


def build_graph_tree(
    *,
    base_graph_path: str | Path,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, str]],
) -> dict[str, Any]:
    root = deepcopy(load_base_graph(base_graph_path))
    node_map, parent_map = index_tree(root)
    root_id = str(root.get("id") or "root")

    for node in nodes:
        normalized_node = dict(node)
        normalized_node["children"] = []
        node_id = normalized_node["id"]
        existing = node_map.get(node_id)
        if existing:
            merge_node(existing, normalized_node)
        else:
            node_map[node_id] = normalized_node

    for node in nodes:
        node_id = node["id"]
        attached_node = node_map[node_id]
        parent_id = str(node.get("parentId") or "").strip()
        if parent_id and parent_id in node_map and parent_id != node_id:
            if safe_attach_child(node_map[parent_id], attached_node, parent_map=parent_map):
                attached_node["parentId"] = parent_id
                attached_node.pop("attachToRoot", None)
            continue
        if node.get("attachToRoot") and node_id != root_id:
            safe_attach_child(root, attached_node, parent_map=parent_map)

    root["relationships"] = list(edges)
    return root


def validate_and_prepare_graph(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, str]],
    *,
    existing_ids: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, Any]]:
    node_ids = {node["id"] for node in nodes}
    all_known_ids = node_ids | set(existing_ids)
    kept_nodes: list[dict[str, Any]] = []
    kept_edges: list[dict[str, str]] = []

    relationship_counts: dict[str, int] = {}
    related_node_ids: set[str] = set()
    orphaned_parent_ids = 0
    orphan_nodes_detected = 0
    dropped_edges_missing_source = 0
    dropped_edges_missing_target = 0
    verification_status_counts: dict[str, int] = {}
    structural_error_nodes_removed = 0

    for edge in edges:
        relationship_counts[edge["type"]] = relationship_counts.get(edge["type"], 0) + 1
        source_known = edge["source"] in all_known_ids
        target_known = edge["target"] in all_known_ids
        if not source_known:
            dropped_edges_missing_source += 1
            continue
        if not target_known:
            dropped_edges_missing_target += 1
            continue
        kept_edges.append(edge)
        related_node_ids.add(edge["source"])
        related_node_ids.add(edge["target"])

    parent_by_child = build_parent_index(kept_edges)
    root_attached_missing_parent_nodes = 0
    explicitly_root_attached_nodes = 0

    for node in nodes:
        prepared = verify_node_sources(dict(node))
        parent_id = parent_by_child.get(prepared["id"]) or prepared.get("parentId")
        if parent_id:
            if parent_id == prepared["id"] or parent_id not in all_known_ids:
                orphaned_parent_ids += 1
                orphan_nodes_detected += 1
                prepared.pop("parentId", None)
            else:
                prepared["parentId"] = parent_id
        else:
            prepared.pop("parentId", None)

        explicitly_attached_to_root = False
        if "attachToRoot" in prepared:
            prepared["attachToRoot"] = bool(prepared["attachToRoot"])
            explicitly_attached_to_root = prepared["attachToRoot"]
            if explicitly_attached_to_root:
                explicitly_root_attached_nodes += 1

        if "parentId" not in prepared:
            if prepared["id"] in related_node_ids or explicitly_attached_to_root:
                prepared["attachToRoot"] = True
            else:
                prepared["attachToRoot"] = True
                root_attached_missing_parent_nodes += 1

        kept_nodes.append(prepared)
        status = prepared.get("verificationStatus", "unverified")
        verification_status_counts[status] = verification_status_counts.get(status, 0) + 1

    validation = {
        "initial_node_count": len(nodes),
        "input_node_count": len(nodes),
        "input_edge_count": len(edges),
        "exported_node_count": len(kept_nodes),
        "exported_edge_count": len(kept_edges),
        "nodes_removed_missing_parent": 0,
        "nodes_reattached_to_root": sum(1 for node in kept_nodes if node.get("attachToRoot")),
        "nodes_removed_structural_errors": structural_error_nodes_removed,
        "final_node_count": len(kept_nodes),
        "orphan_nodes_detected": orphan_nodes_detected,
        "recovered_orphan_nodes": root_attached_missing_parent_nodes,
        "root_attached_missing_parent_nodes": root_attached_missing_parent_nodes,
        "dropped_edges_missing_source": dropped_edges_missing_source,
        "dropped_edges_missing_target": dropped_edges_missing_target,
        "orphaned_parent_ids": orphaned_parent_ids,
        "attached_to_root": sum(1 for node in kept_nodes if node.get("attachToRoot")),
        "explicitly_root_attached_nodes": explicitly_root_attached_nodes,
        "relationship_counts": relationship_counts,
        "verification_status_counts": verification_status_counts,
        "verified_node_count": verification_status_counts.get("verified", 0),
        "average_confidence_score": round(
            sum(float(node.get("confidenceScore") or 0.0) for node in kept_nodes) / max(len(kept_nodes), 1),
            2,
        ),
    }
    return kept_nodes, kept_edges, validation


def build_graph(
    payloads: Iterable[dict[str, Any]],
    *,
    base_graph_path: str | Path = DEFAULT_BASE_GRAPH,
    graph_output_path: str | Path = DEFAULT_GRAPH_OUTPUT,
    nodes_output_path: str | Path = DEFAULT_NODES_OUTPUT,
    edges_output_path: str | Path = DEFAULT_EDGES_OUTPUT,
) -> BuildResult:
    payload_list = list(iter_payload_items(payloads))
    raw_nodes_loaded = count_payload_nodes(payload_list)
    existing_ids = load_existing_node_ids(base_graph_path)
    node_registry = NodeRegistry(existing_ids=set(existing_ids))
    edge_registry = EdgeRegistry()
    normalized_node_count = 0

    for payload in payload_list:
        normalized_nodes = node_registry.add_many(payload.get("nodes", []))
        normalized_node_count += len(normalized_nodes)
        edge_registry.add_many(payload.get("edges", []))

    raw_edges = edge_registry.values()
    parent_by_child = build_parent_index(raw_edges)
    nodes = node_registry.values()
    merged_node_count = len(nodes)
    for node in nodes:
        parent_id = parent_by_child.get(node["id"])
        if parent_id and parent_id != node["id"]:
            node["parentId"] = parent_id

    export_edges = split_hierarchical_edges(raw_edges, parent_by_child)
    export_nodes, export_edges, validation = validate_and_prepare_graph(
        nodes,
        export_edges,
        existing_ids=existing_ids,
    )
    pipeline_summary = {
        "initial_node_count": raw_nodes_loaded,
        "raw_nodes_loaded": raw_nodes_loaded,
        "nodes_after_normalization": normalized_node_count,
        "nodes_after_merge": merged_node_count,
        "nodes_removed_missing_parent": validation["nodes_removed_missing_parent"],
        "nodes_reattached_to_root": validation["nodes_reattached_to_root"],
        "nodes_removed_structural_errors": validation["nodes_removed_structural_errors"],
        "final_node_count": len(export_nodes),
    }
    validation["pipeline_summary"] = pipeline_summary

    graph_path = Path(graph_output_path)
    nodes_path = Path(nodes_output_path)
    edges_path = Path(edges_output_path)
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    nodes_path.parent.mkdir(parents=True, exist_ok=True)
    edges_path.parent.mkdir(parents=True, exist_ok=True)

    graph = build_graph_tree(
        base_graph_path=base_graph_path,
        nodes=export_nodes,
        edges=export_edges,
    )

    with graph_path.open("w", encoding="utf-8") as handle:
        json.dump(graph, handle, indent=2)

    with nodes_path.open("w", encoding="utf-8") as handle:
        json.dump(export_nodes, handle, indent=2)

    with edges_path.open("w", encoding="utf-8") as handle:
        json.dump(export_edges, handle, indent=2)

    return BuildResult(
        nodes=export_nodes,
        edges=export_edges,
        graph=graph,
        graph_path=graph_path,
        nodes_path=nodes_path,
        edges_path=edges_path,
        validation=validation,
    )


def main() -> None:
    result = build_graph(payloads=[])
    print(format_pipeline_summary(result.validation["pipeline_summary"]))
    print(f"Wrote graph to {result.graph_path}")
    print(f"Wrote {len(result.nodes)} nodes to {result.nodes_path}")
    print(f"Wrote {len(result.edges)} edges to {result.edges_path}")
    print(json.dumps(result.validation, indent=2))


if __name__ == "__main__":
    main()
