from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

from data_pipeline.processors.normalize_nodes import (
    generate_node_id,
    infer_color,
    iter_tree_nodes,
    normalize_name,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"
DEFAULT_CORPORATE_GRAPH = PROJECT_ROOT / "data_expansion" / "corporate_expansion.json"
DEFAULT_EXPANDED_NODES = PROJECT_ROOT / "output" / "expanded_nodes.json"
ROOT_NODE_ID = "the-constitution-of-the-united-states"

INFERRED_PARENT_KEYWORDS = {
    "nuclear energy": "Department of Energy",
    "fossil energy": "Department of Energy",
    "renewable energy": "Department of Energy",
    "medicare": "Department of Health and Human Services",
    "medicaid": "Department of Health and Human Services",
    "food and drug": "Department of Health and Human Services",
    "army": "Department of Defense",
    "air force": "Department of Defense",
    "navy": "Department of Defense",
    "cybersecurity": "Department of Homeland Security",
    "immigration": "Department of Homeland Security",
    "civil rights": "Department of Justice",
    "forest service": "Department of Agriculture",
    "foreign service": "Department of State",
    "tax": "Department of the Treasury",
    "internal revenue": "Department of the Treasury",
}


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def unique_strings(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = str(value or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        ordered.append(cleaned)
    return ordered


def candidate_key(name: str, parent_id: str | None) -> str:
    normalized_name = generate_node_id(name)
    return f"{normalized_name}::{parent_id or '__root__'}"


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def flatten_flexible_nodes(payload: Any) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                nodes.extend(flatten_flexible_nodes(item))
        return nodes

    if not isinstance(payload, dict):
        return nodes

    if payload.get("id"):
        nodes.append(payload)

    for child in payload.get("children", []) or []:
        nodes.extend(flatten_flexible_nodes(child))

    for key in ("nodes",):
        for item in payload.get(key, []) or []:
            nodes.extend(flatten_flexible_nodes(item))

    return nodes


def infer_candidate_type(name: str, declared_type: Any = None) -> str:
    if declared_type:
        return normalize_name(declared_type)
    lowered = normalize_name(name).lower()
    if "department" in lowered:
        return "Department"
    if "bureau" in lowered:
        return "Bureau"
    if "division" in lowered:
        return "Division"
    if "committee" in lowered or "subcommittee" in lowered:
        return "Office"
    if any(
        token in lowered
        for token in (
            "director",
            "administrator",
            "secretary",
            "commissioner",
            "chief",
            "chair",
            "inspector general",
        )
    ):
        return "Position"
    if "office" in lowered or "council" in lowered:
        return "Office"
    if any(token in lowered for token in ("agency", "administration", "service", "commission")):
        return "Agency"
    return "Office"


@dataclass
class ReferenceNodeIndex:
    by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_name: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    existing_keys: set[str] = field(default_factory=set)

    @classmethod
    def load(
        cls,
        *,
        base_graph_path: Path = DEFAULT_BASE_GRAPH,
        corporate_graph_path: Path = DEFAULT_CORPORATE_GRAPH,
        expanded_nodes_path: Path = DEFAULT_EXPANDED_NODES,
    ) -> "ReferenceNodeIndex":
        index = cls()

        base_graph = load_json(base_graph_path)
        if isinstance(base_graph, dict):
            for node in iter_tree_nodes(base_graph):
                index._add_existing_node(node)

        corporate_graph = load_json(corporate_graph_path)
        for node in flatten_flexible_nodes(corporate_graph):
            index._add_existing_node(node)

        expanded_nodes = load_json(expanded_nodes_path)
        if isinstance(expanded_nodes, list):
            for node in expanded_nodes:
                if isinstance(node, dict):
                    index._add_existing_node(node)

        return index

    def _add_existing_node(self, raw_node: dict[str, Any], parent_id: str | None = None) -> None:
        node_id = str(raw_node.get("id") or "").strip()
        name = normalize_name(raw_node.get("name"))
        if not node_id or not name:
            return

        node = {
            "id": node_id,
            "name": name,
            "type": normalize_name(raw_node.get("type") or "Organization"),
            "parentId": raw_node.get("parentId") or parent_id,
        }
        self.by_id[node_id] = node
        self.by_name.setdefault(name.lower(), []).append(node)
        self.existing_keys.add(candidate_key(name, node.get("parentId")))

        for child in raw_node.get("children", []) or []:
            if isinstance(child, dict):
                self._add_existing_node(child, node_id)

    def resolve_parent(self, name: str | None) -> dict[str, Any] | None:
        if not name:
            return None

        normalized = normalize_name(name)
        exact = self.by_name.get(normalized.lower())
        if exact:
            return exact[0]

        best_node: dict[str, Any] | None = None
        best_score = 0.0
        for candidate_name, nodes in self.by_name.items():
            score = SequenceMatcher(a=normalized.lower(), b=candidate_name).ratio()
            if score > best_score:
                best_node = nodes[0]
                best_score = score
        return best_node if best_score >= 0.84 else None

    def infer_parent_from_keywords(self, text: str) -> dict[str, Any] | None:
        lowered = normalize_name(text).lower()
        for keyword, parent_name in INFERRED_PARENT_KEYWORDS.items():
            if keyword in lowered:
                return self.resolve_parent(parent_name)
        return None


def verify_node_sources(source_urls: Iterable[str], source_types: Iterable[str]) -> tuple[float, str]:
    urls = unique_strings(source_urls)
    types = {str(item or "").strip().lower() for item in source_types if str(item or "").strip()}

    score = 0.4
    if any(url.endswith(".gov") or ".gov/" in url or url.endswith(".mil") or ".mil/" in url for url in urls):
        score += 0.3
    if "wikidata" in types:
        score += 0.2

    additional = max(0, len(types) - (1 if "wikidata" in types else 0))
    score += min(0.3, additional * 0.1)
    score = clamp(score)

    if score >= 0.8:
        status = "verified"
    elif score >= 0.5:
        status = "partial"
    else:
        status = "unverified"
    return score, status


def normalize_candidate(raw_candidate: dict[str, Any], references: ReferenceNodeIndex) -> dict[str, Any] | None:
    if not isinstance(raw_candidate, dict):
        return None

    name = normalize_name(raw_candidate.get("name"))
    if not name or name == "Unnamed Node":
        return None

    declared_parent = normalize_name(
        raw_candidate.get("parentName")
        or raw_candidate.get("possibleParent")
        or raw_candidate.get("parent")
        or ""
    )
    desc = str(raw_candidate.get("desc") or "").strip()
    node_type = infer_candidate_type(name, raw_candidate.get("type"))
    source_urls = unique_strings(raw_candidate.get("sourceUrls") or [raw_candidate.get("sourceUrl")])
    source_types = unique_strings(raw_candidate.get("sourceTypes") or [raw_candidate.get("sourceType")])
    discovery_methods = unique_strings(
        raw_candidate.get("discoveryMethods") or [raw_candidate.get("discoveryMethod")]
    )

    parent_node = references.resolve_parent(declared_parent) if declared_parent else None
    if not parent_node:
        parent_node = references.infer_parent_from_keywords(" ".join(filter(None, [name, desc, declared_parent])))

    confidence_estimate = clamp(float(raw_candidate.get("confidenceEstimate") or 0.45))
    verification_score, verification_status = verify_node_sources(source_urls, source_types)
    confidence_score = clamp(max(confidence_estimate, verification_score))
    last_verified = datetime.now(tz=timezone.utc).isoformat()

    parent_id = parent_node["id"] if parent_node else None
    node_id_seed = f"{name} {parent_id}" if parent_id else name

    primary_source_url = source_urls[0] if source_urls else ""
    primary_source_type = source_types[0] if source_types else "discovery"
    primary_discovery_method = discovery_methods[0] if discovery_methods else "source_scan"

    return {
        "id": generate_node_id(node_id_seed),
        "name": name,
        "type": node_type,
        "parentId": parent_id,
        "parentName": parent_node["name"] if parent_node else declared_parent or None,
        "possibleParent": parent_node["name"] if parent_node else declared_parent or None,
        "attachToRoot": not bool(parent_id),
        "desc": desc,
        "employees": None,
        "budget": None,
        "color": infer_color(node_type, raw_candidate.get("color")),
        "sourceUrl": primary_source_url,
        "sourceUrls": source_urls,
        "sourceType": primary_source_type,
        "sourceTypes": source_types,
        "discoveryMethod": primary_discovery_method,
        "discoveryMethods": discovery_methods,
        "confidenceEstimate": confidence_estimate,
        "confidenceScore": confidence_score,
        "verificationStatus": verification_status,
        "lastVerified": last_verified,
        "children": [],
    }


@dataclass
class CandidateRegistry:
    references: ReferenceNodeIndex
    items: dict[str, dict[str, Any]] = field(default_factory=dict)
    merges: int = 0

    def add(self, raw_candidate: dict[str, Any]) -> dict[str, Any] | None:
        normalized = normalize_candidate(raw_candidate, self.references)
        if not normalized:
            return None

        key = candidate_key(normalized["name"], normalized.get("parentId"))
        existing = self.items.get(key)
        if existing:
            self.merges += 1
            existing["sourceUrls"] = unique_strings([*existing["sourceUrls"], *normalized["sourceUrls"]])
            existing["sourceTypes"] = unique_strings([*existing["sourceTypes"], *normalized["sourceTypes"]])
            existing["discoveryMethods"] = unique_strings([*existing["discoveryMethods"], *normalized["discoveryMethods"]])
            existing["confidenceEstimate"] = max(existing["confidenceEstimate"], normalized["confidenceEstimate"])
            existing["desc"] = max((existing["desc"], normalized["desc"]), key=len)
            score, status = verify_node_sources(existing["sourceUrls"], existing["sourceTypes"])
            existing["confidenceScore"] = max(existing["confidenceScore"], score)
            existing["verificationStatus"] = status
            existing["lastVerified"] = normalized["lastVerified"]
            existing["sourceUrl"] = existing["sourceUrls"][0] if existing["sourceUrls"] else existing["sourceUrl"]
            existing["sourceType"] = existing["sourceTypes"][0] if existing["sourceTypes"] else existing["sourceType"]
            existing["discoveryMethod"] = (
                existing["discoveryMethods"][0] if existing["discoveryMethods"] else existing["discoveryMethod"]
            )
            return existing

        self.items[key] = normalized
        return normalized

    def add_many(self, candidates: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        added: list[dict[str, Any]] = []
        for candidate in candidates:
            normalized = self.add(candidate)
            if normalized:
                added.append(normalized)
        return added

    def values(self) -> list[dict[str, Any]]:
        return list(self.items.values())


def promote_candidates(
    candidates: Iterable[dict[str, Any]],
    references: ReferenceNodeIndex,
    *,
    promotion_threshold: float = 0.7,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], int]:
    promoted_nodes: list[dict[str, Any]] = []
    promoted_edges: list[dict[str, str]] = []
    existing_keys = set(references.existing_keys)
    skipped_duplicates = 0

    for candidate in candidates:
        key = candidate_key(candidate["name"], candidate.get("parentId"))
        if candidate.get("confidenceScore", 0.0) < promotion_threshold:
            continue
        if key in existing_keys:
            skipped_duplicates += 1
            continue

        existing_keys.add(key)
        promoted_nodes.append(
            {
                "id": candidate["id"],
                "name": candidate["name"],
                "type": candidate["type"],
                "desc": candidate["desc"],
                "employees": candidate.get("employees"),
                "budget": candidate.get("budget"),
                "color": candidate["color"],
                "children": [],
                "parentId": candidate.get("parentId"),
                "sourceUrls": candidate["sourceUrls"],
                "sourceTypes": candidate["sourceTypes"],
                "confidenceScore": candidate["confidenceScore"],
                "verificationStatus": candidate["verificationStatus"],
                "lastVerified": candidate["lastVerified"],
                "attachToRoot": candidate.get("attachToRoot", False),
            }
        )
        if candidate.get("parentId"):
            promoted_edges.append(
                {
                    "source": candidate["id"],
                    "target": candidate["parentId"],
                    "type": "reports_to",
                }
            )

    return promoted_nodes, promoted_edges, skipped_duplicates
