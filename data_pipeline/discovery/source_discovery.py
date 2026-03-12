from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from data_pipeline.processors.normalize_nodes import merge_node, normalize_node, generate_node_id, normalize_name


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "output" / "candidate_nodes.json"
LEADERSHIP_POSITION_TEMPLATES = (
    "Director",
    "Deputy Director",
    "Chief of Staff",
    "Division Chief",
    "Program Manager",
)
OFFICE_LIKE_KEYWORDS = (
    "office",
    "division",
    "bureau",
    "agency",
    "directorate",
    "regional office",
)
SUPPORTED_MAJOR_AGENCIES = {
    "department of energy": "DOE",
    "department of defense": "DoD",
    "nasa": "NASA",
    "national aeronautics and space administration": "NASA",
    "department of state": "State Department",
    "u.s. department of state": "State Department",
}


@dataclass
class CandidateNode:
    name: str
    possibleParent: str | None
    sourceUrl: str
    discoveryMethod: str
    confidenceEstimate: float
    description: str | None = None
    wikidataId: str | None = None


def classify_source_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if host.endswith(".gov") or host.endswith(".mil"):
        return "official_site"
    if "wikidata.org" in host:
        return "wikidata"
    if "federalregister.gov" in host:
        return "federal_register"
    if "faca" in host or "advisory" in host:
        return "advisory_directory"
    return "unknown"


def estimate_candidate_confidence(source_url: str, discovery_method: str) -> float:
    confidence = 0.28
    source_kind = classify_source_url(source_url)
    if source_kind == "official_site":
        confidence += 0.35
    elif source_kind == "wikidata":
        confidence += 0.2
    elif source_kind == "federal_register":
        confidence += 0.25
    elif source_kind == "advisory_directory":
        confidence += 0.22

    if "org_chart" in discovery_method:
        confidence += 0.18
    elif "leadership" in discovery_method:
        confidence += 0.04
    elif "wikidata" in discovery_method:
        confidence += 0.12
    elif "advisory" in discovery_method:
        confidence += 0.16
    elif "register" in discovery_method:
        confidence += 0.08

    return round(max(0.0, min(confidence, 1.0)), 2)


def normalize_candidate_name(value: Any) -> str:
    return normalize_name(value).strip()


def normalize_candidate_parent(value: Any) -> str | None:
    parent = normalize_candidate_name(value)
    return parent or None


def normalize_candidate_key(name: str, possible_parent: str | None) -> tuple[str, str | None]:
    return (normalize_candidate_name(name).casefold(), possible_parent.casefold() if possible_parent else None)


def build_candidate_node(
    *,
    name: str,
    possible_parent: str | None,
    source_url: str,
    discovery_method: str,
    description: str | None = None,
    wikidata_id: str | None = None,
    confidence_override: float | None = None,
) -> CandidateNode | None:
    cleaned_name = normalize_candidate_name(name)
    cleaned_parent = normalize_candidate_parent(possible_parent)
    cleaned_url = str(source_url or "").strip()
    cleaned_description = str(description or "").strip() or None
    cleaned_wikidata_id = str(wikidata_id or "").strip() or None
    if not cleaned_name or not cleaned_url:
        return None

    confidence = (
        round(max(0.0, min(confidence_override, 1.0)), 2)
        if confidence_override is not None
        else estimate_candidate_confidence(cleaned_url, discovery_method)
    )

    return CandidateNode(
        name=cleaned_name,
        possibleParent=cleaned_parent,
        sourceUrl=cleaned_url,
        discoveryMethod=discovery_method,
        confidenceEstimate=confidence,
        description=cleaned_description,
        wikidataId=cleaned_wikidata_id,
    )


def load_records(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("records", "results", "nodes", "items"):
            if isinstance(payload.get(key), list):
                return [item for item in payload[key] if isinstance(item, dict)]
    return []


def iter_tree_nodes(root: dict[str, Any]) -> Iterable[dict[str, Any]]:
    stack = [root]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed([child for child in current.get("children", []) if isinstance(child, dict)]))


def load_existing_graph_nodes(base_graph_path: str | Path = DEFAULT_BASE_GRAPH) -> list[dict[str, Any]]:
    path = Path(base_graph_path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        return list(iter_tree_nodes(payload))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def build_existing_candidate_indexes(
    existing_nodes: Iterable[dict[str, Any]],
) -> tuple[set[str], set[tuple[str, str | None]], dict[str, str | None]]:
    existing_ids: set[str] = set()
    existing_name_parent_keys: set[tuple[str, str | None]] = set()
    parent_name_by_id: dict[str, str | None] = {}

    for node in existing_nodes:
        node_id = str(node.get("id") or "").strip()
        if node_id:
            existing_ids.add(node_id)

    for node in existing_nodes:
        node_id = str(node.get("id") or "").strip()
        parent_id = str(node.get("parent") or node.get("parentId") or "").strip() or None
        parent_name = None
        if parent_id:
            parent_name = parent_name_by_id.get(parent_id)
        parent_name_by_id[node_id] = parent_name

    name_lookup = {
        str(node.get("id") or "").strip(): normalize_candidate_name(node.get("name"))
        for node in existing_nodes
        if node.get("id")
    }
    for node in existing_nodes:
        node_name = normalize_candidate_name(node.get("name"))
        parent_id = str(node.get("parent") or node.get("parentId") or "").strip() or None
        parent_name = name_lookup.get(parent_id) if parent_id else None
        existing_name_parent_keys.add(normalize_candidate_key(node_name, parent_name))

    return existing_ids, existing_name_parent_keys, name_lookup


def build_existing_node_maps(
    existing_nodes: Iterable[dict[str, Any]],
) -> tuple[dict[str, str], dict[tuple[str, str | None], dict[str, Any]]]:
    name_to_id: dict[str, str] = {}
    name_parent_to_node: dict[tuple[str, str | None], dict[str, Any]] = {}
    for raw_node in existing_nodes:
        if not isinstance(raw_node, dict):
            continue
        node = normalize_node(raw_node)
        node_name = normalize_candidate_name(node.get("name"))
        node_id = str(node.get("id") or "").strip()
        parent_id = str(node.get("parentId") or node.get("parent") or "").strip() or None
        if node_name and node_id:
            name_to_id.setdefault(node_name.casefold(), node_id)
            name_parent_to_node[(node_name.casefold(), parent_id)] = node
    return name_to_id, name_parent_to_node


def infer_candidate_type(name: str, description: str | None = None) -> str:
    lowered_name = normalize_candidate_name(name).lower()
    lowered_description = str(description or "").lower()
    combined = f"{lowered_name} {lowered_description}".strip()
    if any(token in combined for token in ("office", "directorate", "administration", "service", "center")):
        return "Office"
    if "bureau" in combined:
        return "Bureau"
    if "division" in combined:
        return "Division"
    if any(token in combined for token in ("director", "chief", "manager", "administrator", "secretary", "advisor", "chair")):
        return "Role"
    if any(token in combined for token in ("committee", "commission", "board", "council")):
        return "Organization"
    return "Organization"


def resolve_parent_id(
    possible_parent: str | None,
    *,
    name_to_id: dict[str, str],
) -> str | None:
    if not possible_parent:
        return None
    return name_to_id.get(normalize_candidate_name(possible_parent).casefold())


def candidate_to_node_record(
    candidate: CandidateNode,
    *,
    parent_name_to_id: dict[str, str],
) -> dict[str, Any]:
    parent_id = resolve_parent_id(candidate.possibleParent, name_to_id=parent_name_to_id)
    source_urls = [candidate.sourceUrl]
    if candidate.wikidataId:
        source_urls.append(f"https://www.wikidata.org/wiki/{candidate.wikidataId}")
    source_types = [classify_source_url(url) for url in source_urls]
    source_types.append("candidate_discovery")
    node_id_seed = f"{parent_id or candidate.possibleParent or ''} {candidate.name}".strip()
    node = normalize_node(
        {
            "id": generate_node_id(node_id_seed or candidate.name),
            "name": candidate.name,
            "type": infer_candidate_type(candidate.name, candidate.description),
            "parentId": parent_id,
            "desc": candidate.description or f"Candidate discovered via {candidate.discoveryMethod}.",
            "description": candidate.description or f"Candidate discovered via {candidate.discoveryMethod}.",
            "sourceUrls": source_urls,
            "sourceTypes": source_types,
            "attachToRoot": parent_id is None,
        }
    )
    node["possibleParent"] = candidate.possibleParent
    node["discoveryMethod"] = candidate.discoveryMethod
    node["sourceUrl"] = candidate.sourceUrl
    node["wikidataId"] = candidate.wikidataId
    node["description"] = node["desc"]
    node["discoveryConfidenceEstimate"] = candidate.confidenceEstimate
    node["isCandidate"] = True
    return node


def node_name_parent_key(node: dict[str, Any]) -> tuple[str, str | None]:
    name = normalize_candidate_name(node.get("name")).casefold()
    parent_id = str(node.get("parentId") or "").strip() or None
    return name, parent_id


def is_duplicate_node(
    name: str,
    parent_id: str | None,
    existing_name_parent_pairs: set[tuple[str, str | None]],
) -> bool:
    key = (normalize_candidate_name(name).casefold(), str(parent_id or "").strip() or None)
    return key in existing_name_parent_pairs


def promote_candidates(
    candidates: Iterable[dict[str, Any]],
    *,
    existing_nodes: Iterable[dict[str, Any]],
    min_confidence_score: float = 0.7,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    existing_name_to_id, existing_name_parent_to_node = build_existing_node_maps(existing_nodes)
    existing_keys = set(existing_name_parent_to_node.keys())
    promoted_by_key: dict[tuple[str, str | None], dict[str, Any]] = {}
    stats = {
        "candidates_reviewed": 0,
        "candidates_below_threshold": 0,
        "promoted_new_nodes": 0,
        "merged_duplicates": 0,
    }

    for raw_candidate in candidates:
        if not isinstance(raw_candidate, dict):
            continue
        stats["candidates_reviewed"] += 1
        candidate = normalize_node(raw_candidate)
        parent_id = str(candidate.get("parentId") or "").strip() or None
        if not parent_id and candidate.get("possibleParent"):
            parent_id = resolve_parent_id(candidate.get("possibleParent"), name_to_id=existing_name_to_id)
            if parent_id:
                candidate["parentId"] = parent_id
                candidate.pop("attachToRoot", None)
        if float(candidate.get("confidenceScore") or 0.0) < min_confidence_score:
            stats["candidates_below_threshold"] += 1
            continue

        key = node_name_parent_key(candidate)
        duplicate = existing_name_parent_to_node.get(key)
        if duplicate:
            merged_candidate = dict(candidate)
            merged_candidate["id"] = duplicate["id"]
            merged_candidate["parentId"] = duplicate.get("parentId")
            promoted_by_key[key] = merge_node(dict(duplicate), merged_candidate)
            stats["merged_duplicates"] += 1
            continue

        if key in promoted_by_key:
            promoted_by_key[key] = merge_node(promoted_by_key[key], candidate)
            stats["merged_duplicates"] += 1
            continue

        promoted_by_key[key] = candidate
        existing_keys.add(key)
        existing_name_to_id.setdefault(normalize_candidate_name(candidate["name"]).casefold(), candidate["id"])
        stats["promoted_new_nodes"] += 1

    return sorted(promoted_by_key.values(), key=lambda item: (item.get("parentId") or "", item["name"])), stats


def is_us_federal_record(record: dict[str, Any]) -> bool:
    us_markers = {
        "united states",
        "united states of america",
        "u.s.",
        "us",
        "usa",
        "q30",
    }
    candidate_values = [
        record.get("country"),
        record.get("countryLabel"),
        record.get("countryCode"),
        record.get("jurisdiction"),
        record.get("jurisdictionLabel"),
        record.get("locatedIn"),
        record.get("location"),
    ]
    normalized_values = {str(value).strip().lower() for value in candidate_values if value}
    if not normalized_values:
        return True
    return any(value in us_markers or "united states" in value for value in normalized_values)


def discover_from_wikidata(records: Iterable[dict[str, Any]]) -> list[CandidateNode]:
    candidates: list[CandidateNode] = []
    for record in records:
        if not is_us_federal_record(record):
            continue
        wikidata_id = (
            record.get("wikidataId")
            or record.get("id")
            or record.get("entityId")
            or record.get("qid")
        )
        official_website = record.get("officialWebsite") or record.get("website")
        source_url = (
            official_website
            or record.get("sourceUrl")
            or record.get("url")
            or (f"https://www.wikidata.org/wiki/{wikidata_id}" if wikidata_id else "")
        )
        parent_name = (
            record.get("parentOrganization")
            or record.get("parentOrganizationLabel")
            or record.get("parentName")
            or record.get("agencyName")
        )
        candidate = build_candidate_node(
            name=record.get("name") or record.get("label"),
            possible_parent=parent_name,
            source_url=source_url,
            discovery_method="wikidata_government_entity_scan",
            description=record.get("description"),
            wikidata_id=wikidata_id,
        )
        if candidate:
            candidates.append(candidate)
    return candidates


def discover_from_advisory_committees(records: Iterable[dict[str, Any]]) -> list[CandidateNode]:
    candidates: list[CandidateNode] = []
    for record in records:
        members = record.get("members")
        member_count = len(members) if isinstance(members, list) else None
        description_parts = [str(record.get("description") or "").strip()]
        chair = str(record.get("chair") or "").strip()
        if chair:
            description_parts.append(f"Chair: {chair}.")
        if member_count:
            description_parts.append(f"Members listed: {member_count}.")
        candidate = build_candidate_node(
            name=record.get("committeeName") or record.get("name") or record.get("title"),
            possible_parent=record.get("parentAgency") or record.get("agencyName"),
            source_url=record.get("sourceUrl") or record.get("url") or record.get("committeeUrl"),
            discovery_method="federal_advisory_committee_scan",
            description=" ".join(part for part in description_parts if part),
        )
        if candidate:
            candidates.append(candidate)
    return candidates


def discover_from_agency_org_charts(records: Iterable[dict[str, Any]]) -> list[CandidateNode]:
    candidates: list[CandidateNode] = []
    for record in records:
        agency_name = normalize_candidate_name(record.get("agency") or record.get("agencyName"))
        if not agency_name:
            continue
        if agency_name.casefold() not in SUPPORTED_MAJOR_AGENCIES:
            continue
        discovery_suffix = SUPPORTED_MAJOR_AGENCIES[agency_name.casefold()].lower().replace(" ", "_")
        candidate = build_candidate_node(
            name=record.get("officeName") or record.get("divisionName") or record.get("name") or record.get("title"),
            possible_parent=record.get("parentOffice") or record.get("parentAgency") or agency_name,
            source_url=record.get("sourceUrl") or record.get("pageUrl") or record.get("url"),
            discovery_method=f"agency_org_chart_scan_{discovery_suffix}",
            description=record.get("description"),
        )
        if candidate:
            candidates.append(candidate)
    return candidates


def is_office_like_node(node: dict[str, Any]) -> bool:
    node_type = normalize_candidate_name(node.get("type")).lower()
    return any(keyword in node_type for keyword in OFFICE_LIKE_KEYWORDS)


def discover_leadership_positions(existing_nodes: Iterable[dict[str, Any]]) -> list[CandidateNode]:
    candidates: list[CandidateNode] = []
    for node in existing_nodes:
        if not is_office_like_node(node):
            continue
        office_name = normalize_candidate_name(node.get("name"))
        if not office_name:
            continue
        for title in LEADERSHIP_POSITION_TEMPLATES:
            candidate = build_candidate_node(
                name=title,
                possible_parent=office_name,
                source_url=f"generated://leadership/{generate_node_id(office_name)}",
                discovery_method="leadership_template_expansion",
                description=f"Template-generated leadership position under {office_name}.",
                confidence_override=0.24,
            )
            if candidate:
                candidates.append(candidate)
    return candidates


def dedupe_candidates(
    candidates: Iterable[CandidateNode],
    *,
    existing_node_ids: set[str] | None = None,
    existing_name_parent_keys: set[tuple[str, str | None]] | None = None,
) -> list[CandidateNode]:
    existing_node_ids = existing_node_ids or set()
    existing_name_parent_keys = existing_name_parent_keys or set()
    deduped: dict[tuple[str, str | None], CandidateNode] = {}

    for candidate in candidates:
        key = normalize_candidate_key(candidate.name, candidate.possibleParent)
        candidate_parent_qualified_id = (
            generate_node_id(f"{candidate.possibleParent} {candidate.name}")
            if candidate.possibleParent
            else generate_node_id(candidate.name)
        )
        if key in existing_name_parent_keys:
            continue
        if candidate_parent_qualified_id in existing_node_ids:
            continue

        existing = deduped.get(key)
        if not existing or candidate.confidenceEstimate > existing.confidenceEstimate:
            deduped[key] = candidate
    return sorted(deduped.values(), key=lambda item: (-item.confidenceEstimate, item.possibleParent or "", item.name))


def discover_candidates(
    *,
    wikidata_records: Iterable[dict[str, Any]] = (),
    advisory_committee_records: Iterable[dict[str, Any]] = (),
    org_chart_records: Iterable[dict[str, Any]] = (),
    official_directory_records: Iterable[dict[str, Any]] = (),
    federal_register_records: Iterable[dict[str, Any]] = (),
    existing_nodes: Iterable[dict[str, Any]] | None = None,
    base_graph_path: str | Path = DEFAULT_BASE_GRAPH,
) -> list[dict[str, Any]]:
    if existing_nodes is None:
        existing_nodes = load_existing_graph_nodes(base_graph_path)
    existing_node_list = [node for node in existing_nodes if isinstance(node, dict)]
    existing_ids, existing_name_parent_keys, _ = build_existing_candidate_indexes(existing_node_list)
    existing_name_to_id, _ = build_existing_node_maps(existing_node_list)

    candidates = [
        *discover_from_wikidata(wikidata_records),
        *discover_from_advisory_committees(advisory_committee_records),
        *discover_from_agency_org_charts(org_chart_records),
        *discover_from_official_directory(official_directory_records),
        *discover_from_federal_register(federal_register_records),
        *discover_leadership_positions(existing_node_list),
    ]
    deduped_candidates = dedupe_candidates(
        candidates,
        existing_node_ids=existing_ids,
        existing_name_parent_keys=existing_name_parent_keys,
    )
    return [
        {
            **candidate_to_node_record(candidate, parent_name_to_id=existing_name_to_id),
            **asdict(candidate),
        }
        for candidate in deduped_candidates
    ]


def discover_from_official_directory(records: Iterable[dict[str, Any]]) -> list[CandidateNode]:
    candidates: list[CandidateNode] = []
    for record in records:
        candidate = build_candidate_node(
            name=record.get("officeName") or record.get("name") or record.get("title"),
            possible_parent=record.get("agencyName") or record.get("possibleParent"),
            source_url=record.get("sourceUrl") or record.get("directoryUrl") or record.get("url"),
            discovery_method="official_directory_leadership_scan",
            description=record.get("description"),
        )
        if candidate:
            candidates.append(candidate)
    return candidates


def discover_from_federal_register(records: Iterable[dict[str, Any]]) -> list[CandidateNode]:
    candidates: list[CandidateNode] = []
    for record in records:
        candidate = build_candidate_node(
            name=record.get("officeName") or record.get("agencyName") or record.get("name"),
            possible_parent=record.get("departmentName") or record.get("possibleParent"),
            source_url=record.get("sourceUrl") or record.get("documentUrl") or record.get("url"),
            discovery_method="federal_register_listing_scan",
            description=record.get("description"),
        )
        if candidate:
            candidates.append(candidate)
    return candidates


def write_review_queue(
    candidates: Iterable[dict[str, Any]],
    *,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(list(candidates), handle, indent=2)
    return path


def main() -> None:
    existing_nodes = load_existing_graph_nodes(DEFAULT_BASE_GRAPH)
    candidates = discover_candidates(existing_nodes=existing_nodes)
    path = write_review_queue(candidates)
    print(f"Wrote {len(candidates)} candidate nodes to {path}")


if __name__ == "__main__":
    main()
