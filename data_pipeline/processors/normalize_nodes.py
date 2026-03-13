from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, Iterable


DEFAULT_NODE = {
    "id": "",
    "name": "Unnamed Node",
    "type": "Organization",
    "desc": "",
    "employees": None,
    "budget": None,
    "color": "#666666",
    "sourceUrls": [],
    "sourceTypes": [],
    "confidenceScore": 0.0,
    "verificationStatus": "unverified",
    "lastVerified": None,
    "sourceCount": 0,
    "founded_date": None,
    "jurisdiction": None,
    "official_website": None,
    "parent_agency": None,
    "related_agencies": [],
    "annual_budget": None,
    "budget_source": None,
    "budget_year": None,
    "created_year": None,
    "restructured_year": None,
    "merged_into": None,
    "renamed_from": None,
    "children": [],
}

TYPE_COLORS = {
    "branch": "#c8a84a",
    "department": "#c84a4a",
    "agency": "#4a8ac8",
    "bureau": "#4a8ac8",
    "office": "#888888",
    "division": "#888888",
    "corporation": "#4ac88a",
    "position": "#888888",
    "role": "#888888",
    "staff": "#888888",
    "employee": "#888888",
    "person": "#8a4ac8",
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


def coerce_nullable_number(value: Any) -> int | float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return value

    text = str(value).strip()
    if not text:
        return None

    normalized = re.sub(r"[^0-9.\-]", "", text)
    if not normalized:
        return None

    try:
        number = float(normalized)
    except ValueError:
        return None

    if number.is_integer():
        return int(number)
    return number


def normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, Iterable):
        values = [str(item) for item in value if item is not None]
    else:
        values = [str(value)]

    seen: set[str] = set()
    normalized: list[str] = []
    for item in values:
        cleaned = item.strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)
    return normalized


def get_first_text(*values: Any) -> str:
    for value in values:
        text = str(value).strip() if value is not None else ""
        if text:
            return text
    return ""


def classify_source_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if host.endswith(".gov") or host.endswith(".mil"):
        return "official_site"
    if "wikidata.org" in host:
        return "wikidata"
    if "wikipedia.org" in host:
        return "wikipedia"
    if "federalregister.gov" in host:
        return "historical_documentation"
    if "house.gov" in host or "senate.gov" in host or "congress.gov" in host or "govinfo.gov" in host:
        return "legislative_reference"
    return "unknown"


def verify_node_sources(node: dict[str, Any]) -> dict[str, Any]:
    source_urls = normalize_string_list(node.get("sourceUrls"))
    if not source_urls and node.get("source"):
        source_urls = normalize_string_list(node.get("source"))

    inferred_types = [classify_source_url(url) for url in source_urls]
    explicit_types = normalize_string_list(node.get("sourceTypes"))
    source_types = normalize_string_list([*explicit_types, *inferred_types])
    source_count = len(source_urls)

    confidence = 0.0 if source_count == 0 else 0.4
    if "official_site" in source_types:
        confidence += 0.3
    if "wikidata" in source_types:
        confidence += 0.2
    if len(set(source_types)) >= 2 or source_count >= 2:
        confidence += 0.2
    if "historical_documentation" in source_types:
        confidence += 0.1
    if "legislative_reference" in source_types:
        confidence += 0.1

    confidence = round(max(0.0, min(confidence, 1.0)), 2)
    if confidence >= 0.8:
        verification_status = "verified"
    elif confidence >= 0.5:
        verification_status = "partial"
    else:
        verification_status = "unverified"

    last_verified = node.get("lastVerified")
    if source_count > 0:
        last_verified = (
            str(last_verified).strip()
            if last_verified
            else datetime.now(timezone.utc).date().isoformat()
        )

    node["sourceUrls"] = source_urls
    node["sourceTypes"] = source_types
    node["sourceCount"] = source_count
    node["confidenceScore"] = confidence
    node["verificationStatus"] = verification_status
    node["lastVerified"] = last_verified
    return node


def normalize_node(raw_node: dict[str, Any], *, fallback_type: str = "Organization") -> dict[str, Any]:
    node = dict(raw_node or {})
    for key, value in DEFAULT_NODE.items():
        node.setdefault(key, deepcopy(value))

    node["name"] = normalize_name(node.get("name"))
    node_type = normalize_name(node.get("type") or fallback_type)
    node["type"] = node_type
    node["id"] = str(node.get("id") or generate_node_id(node["name"]))
    node["desc"] = get_first_text(
        node.get("desc"),
        node.get("description"),
        node.get("summary"),
        node.get("details"),
        node.get("bio"),
    )
    node["employees"] = coerce_nullable_number(node.get("employees"))
    node["budget"] = coerce_nullable_text(node.get("budget"))
    node["color"] = infer_color(node_type, node.get("color"))
    node["children"] = [
        normalize_node(child, fallback_type=fallback_type)
        for child in node.get("children", [])
        if isinstance(child, dict)
    ]

    for field_name in (
        "parentId",
        "parent",
        "industry",
        "location",
        "source",
        "attachToRoot",
        "founded_date",
        "jurisdiction",
        "official_website",
        "parent_agency",
        "related_agencies",
        "annual_budget",
        "budget_source",
        "budget_year",
        "created_year",
        "restructured_year",
        "merged_into",
        "renamed_from",
        "sourceType",
        "sourceUrl",
        "possibleParent",
        "discoveryMethod",
        "discoveryConfidenceEstimate",
        "wikidataId",
        "description",
        "summary",
        "details",
        "bio",
    ):
        if field_name in raw_node and raw_node[field_name] is not None:
            node[field_name] = raw_node[field_name]

    source_urls = normalize_string_list(raw_node.get("sourceUrls") or raw_node.get("sourceUrl") or raw_node.get("sources"))
    if raw_node.get("source") and isinstance(raw_node.get("source"), str) and "://" in str(raw_node.get("source")):
        source_urls = normalize_string_list([*source_urls, raw_node["source"]])
    node["sourceUrls"] = source_urls
    node["sourceTypes"] = normalize_string_list(raw_node.get("sourceTypes") or raw_node.get("sourceType"))
    node["sourceCount"] = int(raw_node.get("sourceCount") or 0)
    node["confidenceScore"] = float(raw_node.get("confidenceScore") or 0.0)
    node["verificationStatus"] = str(raw_node.get("verificationStatus") or "unverified")
    node["lastVerified"] = coerce_nullable_text(raw_node.get("lastVerified"))
    node["founded_date"] = coerce_nullable_text(node.get("founded_date"))
    node["jurisdiction"] = coerce_nullable_text(node.get("jurisdiction"))
    node["official_website"] = coerce_nullable_text(node.get("official_website")) or (
        source_urls[0] if source_urls and classify_source_url(source_urls[0]) == "official_site" else None
    )
    node["parent_agency"] = coerce_nullable_text(node.get("parent_agency"))
    node["related_agencies"] = normalize_string_list(node.get("related_agencies"))
    node["annual_budget"] = coerce_nullable_text(node.get("annual_budget"))
    node["budget_source"] = coerce_nullable_text(node.get("budget_source"))
    node["budget_year"] = coerce_nullable_text(node.get("budget_year"))
    node["created_year"] = coerce_nullable_text(node.get("created_year"))
    node["restructured_year"] = coerce_nullable_text(node.get("restructured_year"))
    node["merged_into"] = coerce_nullable_text(node.get("merged_into"))
    node["renamed_from"] = coerce_nullable_text(node.get("renamed_from"))
    return verify_node_sources(node)


def merge_node(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    for key in ("name", "type", "color"):
        if incoming.get(key):
            existing[key] = incoming[key]

    incoming_desc = get_first_text(
        incoming.get("desc"),
        incoming.get("description"),
        incoming.get("summary"),
        incoming.get("details"),
        incoming.get("bio"),
    )
    existing_desc = get_first_text(
        existing.get("desc"),
        existing.get("description"),
        existing.get("summary"),
        existing.get("details"),
        existing.get("bio"),
    )
    if incoming_desc and len(incoming_desc) > len(existing_desc):
        existing["desc"] = incoming_desc

    for key in (
        "employees",
        "budget",
        "industry",
        "location",
        "founded_date",
        "jurisdiction",
        "official_website",
        "parent_agency",
        "annual_budget",
        "budget_source",
        "budget_year",
        "created_year",
        "restructured_year",
        "merged_into",
        "renamed_from",
    ):
        if incoming.get(key) and not existing.get(key):
            existing[key] = incoming[key]

    if incoming.get("parentId") and not existing.get("parentId"):
        existing["parentId"] = incoming["parentId"]

    existing["sourceUrls"] = normalize_string_list([*existing.get("sourceUrls", []), *incoming.get("sourceUrls", [])])
    existing["sourceTypes"] = normalize_string_list([*existing.get("sourceTypes", []), *incoming.get("sourceTypes", [])])
    existing["related_agencies"] = normalize_string_list(
        [*existing.get("related_agencies", []), *incoming.get("related_agencies", [])]
    )
    if incoming.get("lastVerified"):
        existing["lastVerified"] = incoming["lastVerified"]

    seen_children = {child["id"] for child in existing.get("children", []) if child.get("id")}
    for child in incoming.get("children", []):
        if child["id"] not in seen_children:
            existing.setdefault("children", []).append(child)
            seen_children.add(child["id"])

    handled_keys = {
        "id",
        "name",
        "type",
        "color",
        "desc",
        "employees",
        "budget",
        "industry",
        "location",
        "parentId",
        "children",
        "sourceUrls",
        "sourceTypes",
        "sourceCount",
        "confidenceScore",
        "verificationStatus",
        "lastVerified",
    }
    for key, value in incoming.items():
        if key in handled_keys:
            continue
        if key not in existing or existing.get(key) in (None, "", [], {}):
            existing[key] = deepcopy(value)

    return verify_node_sources(existing)


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
