from __future__ import annotations

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
)


DEFAULT_BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"
DEFAULT_NODES_OUTPUT = DEFAULT_OUTPUT_DIR / "expanded_nodes.json"
DEFAULT_EDGES_OUTPUT = DEFAULT_OUTPUT_DIR / "expanded_edges.json"
HIERARCHICAL_RELATIONSHIPS = {"reports_to", "subsidiary_of"}


@dataclass
class BuildResult:
    nodes: list[dict[str, Any]]
    edges: list[dict[str, str]]
    nodes_path: Path
    edges_path: Path
    validation: dict[str, Any]


def iter_payload_items(payloads: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    for payload in payloads:
        if isinstance(payload, dict):
            yield payload


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
    dropped_edges_missing_source = 0
    dropped_edges_missing_target = 0

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
    dropped_orphan_nodes = 0

    for node in nodes:
        prepared = dict(node)
        parent_id = parent_by_child.get(prepared["id"]) or prepared.get("parentId")
        if parent_id:
            if parent_id == prepared["id"] or parent_id not in all_known_ids:
                orphaned_parent_ids += 1
                prepared.pop("parentId", None)
            else:
                prepared["parentId"] = parent_id
        else:
            prepared.pop("parentId", None)

        explicitly_attached_to_root = False
        if "attachToRoot" in prepared:
            prepared["attachToRoot"] = bool(prepared["attachToRoot"])
            explicitly_attached_to_root = prepared["attachToRoot"]

        if "parentId" not in prepared:
            if prepared["id"] in related_node_ids:
                prepared["attachToRoot"] = True
            elif explicitly_attached_to_root:
                prepared["attachToRoot"] = True
            else:
                dropped_orphan_nodes += 1
                continue

        kept_nodes.append(prepared)

    validation = {
        "input_node_count": len(nodes),
        "input_edge_count": len(edges),
        "exported_node_count": len(kept_nodes),
        "exported_edge_count": len(kept_edges),
        "dropped_orphan_nodes": dropped_orphan_nodes,
        "dropped_edges_missing_source": dropped_edges_missing_source,
        "dropped_edges_missing_target": dropped_edges_missing_target,
        "orphaned_parent_ids": orphaned_parent_ids,
        "attached_to_root": sum(1 for node in kept_nodes if node.get("attachToRoot")),
        "relationship_counts": relationship_counts,
    }
    return kept_nodes, kept_edges, validation


def build_graph(
    payloads: Iterable[dict[str, Any]],
    *,
    base_graph_path: str | Path = DEFAULT_BASE_GRAPH,
    nodes_output_path: str | Path = DEFAULT_NODES_OUTPUT,
    edges_output_path: str | Path = DEFAULT_EDGES_OUTPUT,
) -> BuildResult:
    existing_ids = load_existing_node_ids(base_graph_path)
    node_registry = NodeRegistry(existing_ids=set(existing_ids))
    edge_registry = EdgeRegistry()

    for payload in iter_payload_items(payloads):
        node_registry.add_many(payload.get("nodes", []))
        edge_registry.add_many(payload.get("edges", []))

    raw_edges = edge_registry.values()
    parent_by_child = build_parent_index(raw_edges)
    nodes = node_registry.values()
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

    nodes_path = Path(nodes_output_path)
    edges_path = Path(edges_output_path)
    nodes_path.parent.mkdir(parents=True, exist_ok=True)
    edges_path.parent.mkdir(parents=True, exist_ok=True)

    with nodes_path.open("w", encoding="utf-8") as handle:
        json.dump(export_nodes, handle, indent=2)

    with edges_path.open("w", encoding="utf-8") as handle:
        json.dump(export_edges, handle, indent=2)

    return BuildResult(
        nodes=export_nodes,
        edges=export_edges,
        nodes_path=nodes_path,
        edges_path=edges_path,
        validation=validation,
    )


def main() -> None:
    result = build_graph(payloads=[])
    print(f"Wrote {len(result.nodes)} nodes to {result.nodes_path}")
    print(f"Wrote {len(result.edges)} edges to {result.edges_path}")
    print(json.dumps(result.validation, indent=2))


if __name__ == "__main__":
    main()
