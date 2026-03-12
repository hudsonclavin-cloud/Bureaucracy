from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from data_pipeline.processors.normalize_nodes import generate_node_id, normalize_name


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

    candidates = [
        *discover_from_wikidata(wikidata_records),
        *discover_from_advisory_committees(advisory_committee_records),
        *discover_from_agency_org_charts(org_chart_records),
        *discover_from_official_directory(official_directory_records),
        *discover_from_federal_register(federal_register_records),
        *discover_leadership_positions(existing_node_list),
    ]
    return [asdict(candidate) for candidate in dedupe_candidates(
        candidates,
        existing_node_ids=existing_ids,
        existing_name_parent_keys=existing_name_parent_keys,
    )]


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
