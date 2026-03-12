from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "output" / "candidate_nodes.json"


@dataclass
class CandidateNode:
    name: str
    possibleParent: str | None
    sourceUrl: str
    discoveryMethod: str
    confidenceEstimate: float


def classify_source_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if host.endswith(".gov") or host.endswith(".mil"):
        return "official_site"
    if "wikidata.org" in host:
        return "wikidata"
    if "federalregister.gov" in host:
        return "federal_register"
    return "unknown"


def estimate_candidate_confidence(source_url: str, discovery_method: str) -> float:
    confidence = 0.35
    source_kind = classify_source_url(source_url)
    if source_kind == "official_site":
        confidence += 0.35
    elif source_kind == "wikidata":
        confidence += 0.2
    elif source_kind == "federal_register":
        confidence += 0.25

    if "org_chart" in discovery_method or "leadership" in discovery_method:
        confidence += 0.15
    elif "wikidata" in discovery_method:
        confidence += 0.1
    elif "register" in discovery_method:
        confidence += 0.08

    return round(max(0.0, min(confidence, 1.0)), 2)


def build_candidate_node(
    *,
    name: str,
    possible_parent: str | None,
    source_url: str,
    discovery_method: str,
) -> CandidateNode | None:
    cleaned_name = str(name or "").strip()
    cleaned_url = str(source_url or "").strip()
    if not cleaned_name or not cleaned_url:
        return None

    return CandidateNode(
        name=cleaned_name,
        possibleParent=str(possible_parent).strip() or None if possible_parent is not None else None,
        sourceUrl=cleaned_url,
        discoveryMethod=discovery_method,
        confidenceEstimate=estimate_candidate_confidence(cleaned_url, discovery_method),
    )


def discover_from_wikidata(records: Iterable[dict[str, Any]]) -> list[CandidateNode]:
    candidates: list[CandidateNode] = []
    for record in records:
        candidate = build_candidate_node(
            name=record.get("name") or record.get("label"),
            possible_parent=record.get("possibleParent") or record.get("parentName"),
            source_url=record.get("sourceUrl") or record.get("url") or "https://www.wikidata.org/",
            discovery_method="wikidata_entity_scan",
        )
        if candidate:
            candidates.append(candidate)
    return candidates


def discover_from_official_directory(records: Iterable[dict[str, Any]]) -> list[CandidateNode]:
    candidates: list[CandidateNode] = []
    for record in records:
        candidate = build_candidate_node(
            name=record.get("officeName") or record.get("name") or record.get("title"),
            possible_parent=record.get("agencyName") or record.get("possibleParent"),
            source_url=record.get("sourceUrl") or record.get("directoryUrl") or record.get("url"),
            discovery_method="official_directory_leadership_scan",
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
        )
        if candidate:
            candidates.append(candidate)
    return candidates


def dedupe_candidates(candidates: Iterable[CandidateNode]) -> list[CandidateNode]:
    deduped: dict[tuple[str, str | None, str], CandidateNode] = {}
    for candidate in candidates:
        key = (
            candidate.name.casefold(),
            candidate.possibleParent.casefold() if candidate.possibleParent else None,
            candidate.sourceUrl,
        )
        existing = deduped.get(key)
        if not existing or candidate.confidenceEstimate > existing.confidenceEstimate:
            deduped[key] = candidate
    return sorted(deduped.values(), key=lambda item: (-item.confidenceEstimate, item.name))


def discover_candidates(
    *,
    wikidata_records: Iterable[dict[str, Any]] = (),
    official_directory_records: Iterable[dict[str, Any]] = (),
    federal_register_records: Iterable[dict[str, Any]] = (),
) -> list[dict[str, Any]]:
    candidates = [
        *discover_from_wikidata(wikidata_records),
        *discover_from_official_directory(official_directory_records),
        *discover_from_federal_register(federal_register_records),
    ]
    return [asdict(candidate) for candidate in dedupe_candidates(candidates)]


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
    sample_candidates = discover_candidates()
    path = write_review_queue(sample_candidates)
    print(f"Wrote {len(sample_candidates)} candidate nodes to {path}")


if __name__ == "__main__":
    main()
