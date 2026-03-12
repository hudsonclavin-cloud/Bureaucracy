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

    parent_by_child = build_parent_index(edge_registry.values())
    nodes = node_registry.values()
    for node in nodes:
        parent_id = parent_by_child.get(node["id"])
        if parent_id and parent_id != node["id"]:
            node["parentId"] = parent_id

    export_edges = split_hierarchical_edges(edge_registry.values(), parent_by_child)

    nodes_path = Path(nodes_output_path)
    edges_path = Path(edges_output_path)
    nodes_path.parent.mkdir(parents=True, exist_ok=True)
    edges_path.parent.mkdir(parents=True, exist_ok=True)

    with nodes_path.open("w", encoding="utf-8") as handle:
        json.dump(nodes, handle, indent=2)

    with edges_path.open("w", encoding="utf-8") as handle:
        json.dump(export_edges, handle, indent=2)

    return BuildResult(
        nodes=nodes,
        edges=export_edges,
        nodes_path=nodes_path,
        edges_path=edges_path,
    )


def main() -> None:
    result = build_graph(payloads=[])
    print(f"Wrote {len(result.nodes)} nodes to {result.nodes_path}")
    print(f"Wrote {len(result.edges)} edges to {result.edges_path}")


if __name__ == "__main__":
    main()
