from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


DEFAULT_NODE = {
    "id": "",
    "name": "Unnamed Node",
    "type": "Organization",
    "desc": "",
    "employees": None,
    "budget": None,
    "color": "#666666",
    "children": [],
}

TYPE_COLORS = {
    "branch": "#FFD166",
    "department": "#F94144",
    "agency": "#4D96FF",
    "bureau": "#4D96FF",
    "office": "#F8961E",
    "division": "#B0B0B0",
    "corporation": "#06D6A0",
    "position": "#B0B0B0",
    "person": "#9B5DE5",
}

ACRONYMS = {
    "Usa": "USA",
    "U S": "U.S.",
    "Fdic": "FDIC",
    "Sec": "SEC",
    "Doe": "DOE",
    "Dod": "DoD",
    "Hud": "HUD",
    "Nasa": "NASA",
    "Usps": "USPS",
}


def normalize_name(value: Any) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"[_/]+", " ", text).strip()
    text = re.sub(r"\s+", " ", text)
    if not text:
        return DEFAULT_NODE["name"]

    if text.isupper():
        text = text.title()
    elif text == text.lower():
        text = text.title()

    for source, target in ACRONYMS.items():
        text = text.replace(source, target)
    return text


def generate_node_id(value: str, *, prefix: str | None = None) -> str:
    base = normalize_name(value).lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    if not base:
        base = "node"
    if prefix:
        return f"{prefix}-{base}"
    return base


def infer_color(node_type: Any, explicit_color: Any = None) -> str:
    if isinstance(explicit_color, str) and explicit_color:
        return explicit_color

    type_key = normalize_name(node_type).lower()
    for keyword, color in TYPE_COLORS.items():
        if keyword in type_key:
            return color
    return DEFAULT_NODE["color"]


def coerce_nullable_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_node(raw_node: dict[str, Any], *, fallback_type: str = "Organization") -> dict[str, Any]:
    node = deepcopy(DEFAULT_NODE)
    node.update(raw_node or {})

    node["name"] = normalize_name(node.get("name"))
    node_type = normalize_name(node.get("type") or fallback_type)
    node["type"] = node_type
    node["id"] = str(node.get("id") or generate_node_id(node["name"]))
    node["desc"] = str(node.get("desc") or "").strip()
    node["employees"] = coerce_nullable_text(node.get("employees"))
    node["budget"] = coerce_nullable_text(node.get("budget"))
    node["color"] = infer_color(node_type, node.get("color"))
    node["children"] = [
        normalize_node(child, fallback_type=fallback_type)
        for child in node.get("children", [])
        if isinstance(child, dict)
    ]

    for field_name in ("parentId", "parent", "industry", "location", "source"):
        if field_name in raw_node and raw_node[field_name] is not None:
            node[field_name] = raw_node[field_name]

    return node


def merge_node(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    for key in ("name", "type", "color"):
        if incoming.get(key):
            existing[key] = incoming[key]

    if incoming.get("desc") and len(incoming["desc"]) > len(existing.get("desc", "")):
        existing["desc"] = incoming["desc"]

    for key in ("employees", "budget", "industry", "location"):
        if incoming.get(key) and not existing.get(key):
            existing[key] = incoming[key]

    if incoming.get("parentId") and not existing.get("parentId"):
        existing["parentId"] = incoming["parentId"]

    seen_children = {child["id"] for child in existing.get("children", []) if child.get("id")}
    for child in incoming.get("children", []):
        if child["id"] not in seen_children:
            existing.setdefault("children", []).append(child)
            seen_children.add(child["id"])
    return existing


def iter_tree_nodes(root: dict[str, Any]) -> Iterable[dict[str, Any]]:
    stack = [root]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(current.get("children", [])))


def load_existing_node_ids(base_graph_path: str | Path) -> set[str]:
    path = Path(base_graph_path)
    if not path.exists():
        return set()

    with path.open("r", encoding="utf-8") as handle:
        root = json.load(handle)
    return {node.get("id", "") for node in iter_tree_nodes(root) if node.get("id")}


@dataclass
class NodeRegistry:
    existing_ids: set[str] = field(default_factory=set)
    node_index: dict[str, dict[str, Any]] = field(default_factory=dict)

    def add(self, raw_node: dict[str, Any], *, fallback_type: str = "Organization") -> dict[str, Any]:
        normalized = normalize_node(raw_node, fallback_type=fallback_type)
        node_id = normalized["id"]
        existing = self.node_index.get(node_id)
        if existing:
            return merge_node(existing, normalized)

        self.node_index[node_id] = normalized
        self.existing_ids.add(node_id)
        return normalized

    def add_many(self, nodes: Iterable[dict[str, Any]], *, fallback_type: str = "Organization") -> list[dict[str, Any]]:
        return [self.add(node, fallback_type=fallback_type) for node in nodes if isinstance(node, dict)]

    def values(self) -> list[dict[str, Any]]:
        return list(self.node_index.values())
