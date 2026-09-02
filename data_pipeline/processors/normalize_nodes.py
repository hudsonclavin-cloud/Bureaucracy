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
    "children": [],
}

SOURCE_TYPE_ALIASES = {
    "official_http": "official_site",
    "official_directory": "official_site",
    "usaspending_direct": "official_financial_record",
    "usaspending_parent": "official_financial_record",
    "treasury_outlays": "official_financial_record",
    "federal_register": "historical_documentation",
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
    # Underscores are slug residue; a slash is punctuation people write in
    # names ("Deputy Director / COO") and must survive normalisation.
    text = re.sub(r"_+", " ", text).strip()
    text = re.sub(r"\s+", " ", text)
    if not text:
        return DEFAULT_NODE["name"]

    if text.isupper() or text == text.lower():
        text = text.title()
        # Restore acronyms flattened by title-casing; match whole words only so
        # names like "Homeland Security" or "Hudson" are never rewritten.
        for source, target in ACRONYMS.items():
            text = re.sub(rf"\b{re.escape(source)}\b", target, text)
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


NUMBER_TOKEN_PATTERN = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
MAGNITUDE_SUFFIX_PATTERN = re.compile(r"(thousand|million|billion|trillion|[kmbt])\b", re.IGNORECASE)
MAGNITUDE_MULTIPLIERS = {
    "k": 1_000,
    "thousand": 1_000,
    "m": 1_000_000,
    "million": 1_000_000,
    "b": 1_000_000_000,
    "billion": 1_000_000_000,
    "t": 1_000_000_000_000,
    "trillion": 1_000_000_000_000,
}


def coerce_nullable_number(value: Any) -> int | float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return value

    text = str(value).strip()
    if not text:
        return None

    match = NUMBER_TOKEN_PATTERN.search(text)
    if not match:
        return None

    try:
        number = float(match.group().replace(",", ""))
    except ValueError:
        return None

    magnitude = MAGNITUDE_SUFFIX_PATTERN.match(text[match.end():].lstrip())
    if magnitude:
        number = round(number * MAGNITUDE_MULTIPLIERS[magnitude.group(1).lower()], 6)

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
    return "unknown"


def is_official_source_url(url: Any) -> bool:
    text = coerce_nullable_text(url)
    return bool(text and classify_source_url(text) == "official_site")


def verify_node_sources(node: dict[str, Any]) -> dict[str, Any]:
    source_urls = normalize_string_list(node.get("sourceUrls"))
    if not source_urls and node.get("source"):
        source_urls = normalize_string_list(node.get("source"))
    if is_official_source_url(node.get("official_website")):
        source_urls = normalize_string_list([*source_urls, node.get("official_website")])

    inferred_types = [classify_source_url(url) for url in source_urls]
    explicit_types = normalize_string_list(node.get("sourceTypes"))
    source_types = normalize_string_list([*explicit_types, *inferred_types])
    source_count = len(source_urls)

    confidence = 0.0 if source_count == 0 else 0.4
    if "official_site" in source_types:
        confidence += 0.3
    if "wikidata" in source_types:
        confidence += 0.2
    additional_sources = max(0, source_count - 1)
    confidence += min(0.3, additional_sources * 0.1)

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

    # Proof fields, read by build_graph.annotate_proof_tree. Scored off an
    # alias-expanded view of the source types so the confidence scoring above
    # keeps seeing exactly the types it was tuned against.
    aliased_source_types = normalize_string_list(
        [*source_types, *[SOURCE_TYPE_ALIASES.get(source_type, source_type) for source_type in source_types]]
    )
    proof_source_types = normalize_string_list(
        [
            source_type
            for source_type in aliased_source_types
            if source_type not in {"unknown", "candidate_discovery", "wikipedia"}
        ]
    )
    proof_source_count = len(proof_source_types)

    exists_proven = False
    proof_status = "unproven"
    proof_reason = "no_evidence_recorded" if proof_source_count == 0 and source_count == 0 else "insufficient_direct_proof"
    # A type label is a claim about a URL; with no URL recorded it proves
    # nothing. And "official_site" in particular must be earned by a .gov/.mil
    # URL that is actually present, not asserted alongside an unrelated one.
    url_backed_types = normalize_string_list(
        [*inferred_types, *[SOURCE_TYPE_ALIASES.get(source_type, source_type) for source_type in inferred_types]]
    )
    if source_count == 0:
        proof_reason = "no_evidence_recorded"
    elif (
        "official_site" in url_backed_types
        or "official_financial_record" in aliased_source_types
        or "legislative_reference" in aliased_source_types
    ):
        exists_proven = True
        proof_status = "proven"
        proof_reason = "official_source_recorded"
    elif "historical_documentation" in aliased_source_types and source_count >= 1:
        exists_proven = True
        proof_status = "proven"
        proof_reason = "historical_documentation_recorded"
    elif "wikidata" in aliased_source_types and proof_source_count >= 2:
        exists_proven = True
        proof_status = "proven"
        proof_reason = "multi_source_corroborated"

    node["sourceUrls"] = source_urls
    node["sourceTypes"] = source_types
    node["sourceCount"] = source_count
    node["confidenceScore"] = confidence
    node["verificationStatus"] = verification_status
    node["lastVerified"] = last_verified
    node["proofSourceCount"] = proof_source_count
    node["proofSourceTypes"] = proof_source_types
    node["existsProven"] = bool(exists_proven)
    node["parentProven"] = bool(node.get("parentProven"))
    node["proofStatus"] = proof_status
    node["proofReason"] = proof_reason
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
    node["color"] = infer_color(node_type, raw_node.get("color"))
    node["children"] = [
        normalize_node(child, fallback_type=fallback_type)
        for child in node.get("children", [])
        if isinstance(child, dict)
    ]

    for field_name in ("parentId", "parent", "industry", "location", "source", "attachToRoot"):
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
    return verify_node_sources(node)


def merge_node(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    for key in ("name", "type"):
        if incoming.get(key):
            existing[key] = incoming[key]

    # Normalized nodes always carry a color, so only let the incoming one win
    # when it says something (i.e. is not the fallback gray) or fills a gap.
    incoming_color = incoming.get("color")
    if incoming_color and (incoming_color != DEFAULT_NODE["color"] or not existing.get("color")):
        existing["color"] = incoming_color

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

    for key in ("employees", "budget", "industry", "location"):
        if incoming.get(key) and not existing.get(key):
            existing[key] = incoming[key]

    if incoming.get("parentId") and not existing.get("parentId"):
        existing["parentId"] = incoming["parentId"]

    existing["sourceUrls"] = normalize_string_list([*existing.get("sourceUrls", []), *incoming.get("sourceUrls", [])])
    existing["sourceTypes"] = normalize_string_list([*existing.get("sourceTypes", []), *incoming.get("sourceTypes", [])])
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
