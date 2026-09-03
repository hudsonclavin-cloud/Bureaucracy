"""Existence evidence for curated nodes.

The base graph names 5,170 units and positions and carries no source for any
of them. This module is the one route by which a curated node earns a source
without a human: an official .gov/.mil page is fetched on a date, the node's
name is looked for in its text, and the outcome — confirmed, not found, or
fetch failed — is recorded in a sidecar file keyed by node id.

Three rules hold throughout:

* The curated file is never written. Evidence lives in
  data/verification/evidence.json and is merged onto nodes at build time.
* Nothing is claimed that was not fetched. A record carries the URL that
  was fetched, the moment it was fetched, and the text that matched.
* A failed check is recorded as a failed check. The exporter stamps the
  date without a URL, which the site renders as checked-and-failed
  ("UNVERIFIED") rather than never-checked ("NO SOURCE RECORDED").
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from data_pipeline.crawler.official_directory import TextFragmentParser
from data_pipeline.exporter.build_graph import canonical_name_key, index_tree
from data_pipeline.json_io import load_json_file
from data_pipeline.processors.normalize_nodes import classify_source_url, verify_node_sources


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVIDENCE_PATH = PROJECT_ROOT / "data" / "verification" / "evidence.json"
DEFAULT_SITES_PATH = PROJECT_ROOT / "data" / "verification" / "official_sites.json"

CONFIRMED = "confirmed"
NOT_FOUND = "not_found"
FETCH_FAILED = "fetch_failed"
METHOD = "name_on_official_page"

Fetcher = Callable[[str], str]


def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()


def load_evidence(path: str | Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    payload = load_json_file(path, default_factory=dict)
    if not isinstance(payload, dict):
        return {}
    records = payload.get("nodes") if isinstance(payload.get("nodes"), dict) else payload
    return {str(k): v for k, v in records.items() if isinstance(v, dict) and not str(k).startswith("_")}


def load_official_sites(path: str | Path | None) -> dict[str, list[str]]:
    """node id -> candidate official URLs. A candidate is something to fetch,
    not a claim: the file says so in its own `_note`."""
    if path is None:
        return {}
    payload = load_json_file(path, default_factory=dict)
    if not isinstance(payload, dict):
        return {}
    sites: dict[str, list[str]] = {}
    for node_id, value in payload.items():
        if str(node_id).startswith("_"):
            continue
        urls = value if isinstance(value, list) else [value]
        cleaned = [str(u).strip() for u in urls if isinstance(u, str) and u.strip().startswith("http")]
        if cleaned:
            sites[str(node_id)] = cleaned
    return sites


def candidate_urls(
    node_id: str, parent_map: dict[str, str], sites: dict[str, list[str]]
) -> tuple[list[str], str | None, int]:
    """The node's own official site, else the nearest ancestor's.

    Returns (urls, id of the node whose site was used, how many levels up
    it was found). A department's About page plausibly lists its bureaus;
    a chamber's homepage does not list every subcommittee, so callers cap
    the distance rather than record hundreds of "not found" checks that
    never had a chance."""
    current: str | None = node_id
    distance = 0
    while current:
        if current in sites:
            return list(sites[current]), current, distance
        current = parent_map.get(current)
        distance += 1
    return [], None, distance


def page_text(html: str) -> str:
    parser = TextFragmentParser()
    parser.feed(html)
    return " ".join(parser.fragments)


def find_name(name: str, text: str) -> str | None:
    """The fragment of the page text that names the node, or None.

    Comparison is on canonical keys (case, punctuation, "&" vs "and", "U.S."
    spelling and a trailing acronym do not matter), and the whole name has
    to be there: an acronym alone matches far too much."""
    key = canonical_name_key(name)
    # A three-letter key would match an acronym anywhere on the page; that is
    # not evidence that the unit is what the page is about.
    if not key or len(key) < 4:
        return None
    canonical_text = canonical_name_key(text)
    if not canonical_text:
        return None
    # canonical_name_key strips parentheticals, so a "(DOE)" in the name is
    # already gone; word-bounded search on the canonical text.
    match = re.search(r"(?<![a-z0-9])" + re.escape(key) + r"(?![a-z0-9])", canonical_text)
    if not match:
        return None
    start = max(0, match.start() - 40)
    end = min(len(canonical_text), match.end() + 40)
    return canonical_text[start:end].strip()


def verify_node(
    node: dict[str, Any],
    urls: list[str],
    *,
    fetch: Fetcher,
    now: str | None = None,
    site_from: str | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """Fetch each candidate URL and look for the node's name.

    The record is the outcome of the checks that were actually made. Every
    URL that named the node is kept (two official pages are two sources);
    the first failure reason is kept when none did."""
    checked_at = now or utc_now_iso()
    confirmed: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    for url in urls:
        if classify_source_url(url) != "official_site":
            failures.append({"url": url, "reason": "not_an_official_host"})
            continue
        try:
            html = fetch(url)
        except Exception as error:  # noqa: BLE001 — every failure is evidence of a failed fetch
            failures.append({"url": url, "reason": f"{error.__class__.__name__}: {error}"[:200]})
            continue
        matched = find_name(str(node.get("name") or ""), html if "<" not in html else page_text(html))
        if matched:
            confirmed.append({"url": url, "matchedText": matched})
        else:
            failures.append({"url": url, "reason": "name_not_on_page"})
    record: dict[str, Any] = {
        "name": node.get("name"),
        "checkedAt": checked_at,
        "method": METHOD,
        "siteFrom": site_from,
    }
    if confirmed:
        record["status"] = CONFIRMED
        record["sources"] = confirmed
    elif urls and all(f["reason"] == "name_not_on_page" for f in failures):
        record["status"] = NOT_FOUND
    else:
        record["status"] = FETCH_FAILED
    if failures:
        record["failures"] = failures
    return record


def apply_evidence_to_tree(root: dict[str, Any], evidence: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Stamp evidence onto the nodes it names. Returns counts.

    A confirmed record adds its URLs as sources and its check time as
    lastVerified, and verify_node_sources then scores the node like any
    other. A failed record stamps the check time only: the node was looked
    for and not found, and the site must say that rather than "no source
    recorded". Names and types are never touched."""
    stats = {"confirmed": 0, "not_found": 0, "fetch_failed": 0, "unknown_node": 0, "urls_added": 0}
    if not evidence:
        return stats
    node_map, _ = index_tree(root)
    for node_id, record in evidence.items():
        node = node_map.get(node_id)
        if node is None:
            stats["unknown_node"] += 1
            continue
        status = str(record.get("status") or "")
        checked_at = str(record.get("checkedAt") or "").strip()
        if status == CONFIRMED:
            urls = [str(s.get("url")) for s in record.get("sources", []) if isinstance(s, dict) and s.get("url")]
            existing = [str(u) for u in (node.get("sourceUrls") or [])]
            for url in urls:
                if url not in existing:
                    existing.append(url)
                    stats["urls_added"] += 1
            node["sourceUrls"] = existing
            types = [str(t) for t in (node.get("sourceTypes") or [])]
            if "official_site" not in types:
                types.append("official_site")
            node["sourceTypes"] = types
            if checked_at and (not node.get("lastVerified") or checked_at > str(node.get("lastVerified"))):
                node["lastVerified"] = checked_at
            node["verificationMethod"] = METHOD
            node.pop("verificationFailure", None)
            stats["confirmed"] += 1
        elif status in (NOT_FOUND, FETCH_FAILED):
            stats[status] += 1
            # A failed check never removes a source another route recorded.
            if not node.get("sourceUrls") and checked_at:
                node["lastVerified"] = checked_at
                node["verificationFailure"] = status
        else:
            stats["unknown_node"] += 0  # unrecognised status: ignored, never applied
            continue
        verify_node_sources(node)
    return stats
