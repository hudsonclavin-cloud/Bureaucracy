from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

from data_pipeline.processors.normalize_nodes import classify_source_url, normalize_name


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_PATH = PROJECT_ROOT / "output" / "pipeline_state.json"
DEFAULT_FRONTIER_OUTPUT = PROJECT_ROOT / "output" / "frontier_targets.json"
OFFICIAL_FRONTIER_SUFFIXES = (
    "",
    "leadership",
    "about",
    "about/leadership",
    "about/organization",
    "organization",
    "organization-chart",
    "org-chart",
    "bureaus",
    "offices",
)
KNOWN_OFFICIAL_SOURCES = {
    "department of energy": "https://www.energy.gov/organization-chart",
    "nasa": "https://www.nasa.gov/organization/",
    "department of state": "https://www.state.gov/bureaus-offices-reporting-directly-to-the-secretary/",
}
HIGH_VALUE_TYPE_RANK = {
    "cabinet department": 0,
    "department": 0,
    "branch": 0,
    "agency": 1,
    "component agency": 1,
    "defense agency": 1,
    "bureau": 2,
    "office": 3,
    "regional office": 3,
    "area office": 3,
    "division": 4,
    "directorate": 4,
    "position": 6,
    "person": 7,
}


def load_pipeline_state(path: str | Path = DEFAULT_STATE_PATH) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return {
            "version": 1,
            "runCount": 0,
            "lastRunAt": None,
            "frontier": {},
            "entities": {},
        }
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        payload.setdefault("version", 1)
        payload.setdefault("runCount", 0)
        payload.setdefault("lastRunAt", None)
        payload.setdefault("frontier", {})
        payload.setdefault("entities", {})
        return payload
    return {
        "version": 1,
        "runCount": 0,
        "lastRunAt": None,
        "frontier": {},
        "entities": {},
    }


def write_pipeline_state(state: dict[str, Any], path: str | Path = DEFAULT_STATE_PATH) -> Path:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
    return state_path


def normalize_official_url(url: str) -> str:
    parsed = urlparse(str(url).strip())
    normalized_path = parsed.path.rstrip("/")
    if not normalized_path:
        normalized_path = ""
    return f"{parsed.scheme}://{parsed.netloc}{normalized_path}"


def is_official_url(url: str) -> bool:
    return classify_source_url(url) == "official_site"


def node_priority(node: dict[str, Any]) -> tuple[int, float, str]:
    type_key = normalize_name(node.get("type")).casefold()
    priority_rank = HIGH_VALUE_TYPE_RANK.get(type_key, 5)
    confidence = float(node.get("confidenceScore") or 0.0)
    return priority_rank, confidence, normalize_name(node.get("name")).casefold()


def candidate_official_urls(node: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    normalized_name = normalize_name(node.get("name")).casefold()
    if normalized_name in KNOWN_OFFICIAL_SOURCES:
        urls.append(normalize_official_url(KNOWN_OFFICIAL_SOURCES[normalized_name]))
    official_website = str(node.get("official_website") or "").strip()
    if official_website and is_official_url(official_website):
        urls.append(normalize_official_url(official_website))
    for source_url in node.get("sourceUrls", []) or []:
        cleaned = str(source_url or "").strip()
        if cleaned and is_official_url(cleaned):
            urls.append(normalize_official_url(cleaned))
    deduped: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return deduped


def build_frontier_targets(
    existing_nodes: Iterable[dict[str, Any]],
    *,
    state: dict[str, Any] | None = None,
    limit: int = 80,
) -> list[dict[str, Any]]:
    prior_frontier = (state or {}).get("frontier", {})
    ranked_nodes = sorted(existing_nodes, key=node_priority)
    candidates: dict[str, dict[str, Any]] = {}

    for node in ranked_nodes:
        type_key = normalize_name(node.get("type")).casefold()
        if type_key in {"position", "person", "role", "staff"}:
            continue
        node_name = normalize_name(node.get("name"))
        if not node_name:
            continue

        base_urls = candidate_official_urls(node)
        if not base_urls:
            continue

        base_priority, confidence, _ = node_priority(node)
        frontier_boost = 0.0
        if float(node.get("confidenceScore") or 0.0) < 0.8:
            frontier_boost += 0.18
        if str(node.get("verificationStatus") or "").lower() != "verified":
            frontier_boost += 0.12

        for base_url in base_urls:
            frontier_entry = prior_frontier.get(base_url, {})
            score_adjustment = frontier_boost + min(0.2, float(frontier_entry.get("failureCount") or 0) * -0.04)
            for suffix in OFFICIAL_FRONTIER_SUFFIXES:
                url = normalize_official_url(urljoin(f"{base_url}/", suffix)) if suffix else base_url
                existing = candidates.get(url)
                priority_score = max(
                    0.0,
                    1.35 - base_priority * 0.18 + score_adjustment + (0.15 if suffix else 0.0) + (0.08 if confidence < 0.75 else 0.0),
                )
                payload = {
                    "agencyName": node_name,
                    "directoryUrl": url,
                    "sourceNodeId": node.get("id"),
                    "sourceNodeType": node.get("type"),
                    "priority": round(priority_score, 3),
                    "reason": "revisit_low_confidence" if confidence < 0.8 else "official_frontier_scan",
                }
                if not existing or payload["priority"] > existing["priority"]:
                    candidates[url] = payload

    return sorted(
        candidates.values(),
        key=lambda item: (-float(item["priority"]), normalize_name(item["agencyName"]).casefold(), item["directoryUrl"]),
    )[:limit]


def update_pipeline_state(
    state: dict[str, Any],
    *,
    frontier_targets: Iterable[dict[str, Any]],
    frontier_metrics: Iterable[dict[str, Any]],
    promoted_nodes: Iterable[dict[str, Any]],
    enriched_nodes: Iterable[dict[str, Any]],
    timestamp: str | None = None,
) -> dict[str, Any]:
    next_state = dict(state or {})
    next_state.setdefault("version", 1)
    next_state["runCount"] = int(next_state.get("runCount", 0)) + 1
    next_state["lastRunAt"] = timestamp or datetime.now(tz=timezone.utc).isoformat()
    frontier_store = dict(next_state.get("frontier") or {})
    entity_store = dict(next_state.get("entities") or {})

    for target in frontier_targets:
        url = str(target.get("directoryUrl") or "").strip()
        if not url:
            continue
        entry = dict(frontier_store.get(url) or {})
        entry["agencyName"] = target.get("agencyName")
        entry["sourceNodeId"] = target.get("sourceNodeId")
        entry["sourceNodeType"] = target.get("sourceNodeType")
        entry["priority"] = float(target.get("priority") or 0.0)
        entry["lastQueuedAt"] = next_state["lastRunAt"]
        entry["timesQueued"] = int(entry.get("timesQueued", 0)) + 1
        frontier_store[url] = entry

    for metric in frontier_metrics:
        url = str(metric.get("directoryUrl") or "").strip()
        if not url:
            continue
        entry = dict(frontier_store.get(url) or {})
        success = bool(metric.get("success"))
        entry["lastCrawledAt"] = next_state["lastRunAt"]
        entry["lastRecordCount"] = int(metric.get("recordCount") or 0)
        if success:
            entry["lastSuccessAt"] = next_state["lastRunAt"]
            entry["failureCount"] = 0
        else:
            entry["lastFailureAt"] = next_state["lastRunAt"]
            entry["failureCount"] = int(entry.get("failureCount", 0)) + 1
            if metric.get("error"):
                entry["lastError"] = str(metric.get("error"))
        frontier_store[url] = entry

    for node in [*promoted_nodes, *enriched_nodes]:
        node_id = str(node.get("id") or "").strip()
        if not node_id:
            continue
        entry = dict(entity_store.get(node_id) or {})
        entry["name"] = node.get("name")
        entry["type"] = node.get("type")
        entry["lastSeenAt"] = next_state["lastRunAt"]
        entry["timesSeen"] = int(entry.get("timesSeen", 0)) + 1
        entry["verificationStatus"] = node.get("verificationStatus")
        entry["confidenceScore"] = float(node.get("confidenceScore") or 0.0)
        entry["sourceCount"] = int(node.get("sourceCount") or len(node.get("sourceUrls", []) or []))
        entity_store[node_id] = entry

    next_state["frontier"] = frontier_store
    next_state["entities"] = entity_store
    return next_state


def write_frontier_targets(targets: Iterable[dict[str, Any]], path: str | Path = DEFAULT_FRONTIER_OUTPUT) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(list(targets), handle, indent=2)
    return output_path
