from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


ALLOWED_RELATIONSHIPS = {
    "reports_to",
    "contracts_with",
    "subsidiary_of",
    "lobbies",
    "funds",
    "manages",
}


def normalize_relationship(value: Any) -> str:
    relationship = str(value or "manages").strip().lower().replace(" ", "_")
    if relationship not in ALLOWED_RELATIONSHIPS:
        return "manages"
    return relationship


def normalize_edge(raw_edge: dict[str, Any]) -> dict[str, str] | None:
    if not isinstance(raw_edge, dict):
        return None

    source = str(raw_edge.get("source") or "").strip()
    target = str(raw_edge.get("target") or "").strip()
    relationship = normalize_relationship(raw_edge.get("relationship") or raw_edge.get("type"))

    if not source or not target or source == target:
        return None

    return {
        "source": source,
        "target": target,
        "relationship": relationship,
    }


def edge_key(edge: dict[str, str]) -> str:
    return f"{edge['source']}::{edge['target']}::{edge['relationship']}"


@dataclass
class EdgeRegistry:
    edge_index: set[str] = field(default_factory=set)
    edges: list[dict[str, str]] = field(default_factory=list)

    def add(self, raw_edge: dict[str, Any]) -> dict[str, str] | None:
        normalized = normalize_edge(raw_edge)
        if not normalized:
            return None

        key = edge_key(normalized)
        if key in self.edge_index:
            return None

        self.edge_index.add(key)
        self.edges.append(normalized)
        return normalized

    def add_many(self, raw_edges: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
        added = []
        for edge in raw_edges:
            normalized = self.add(edge)
            if normalized:
                added.append(normalized)
        return added

    def values(self) -> list[dict[str, str]]:
        return list(self.edges)
