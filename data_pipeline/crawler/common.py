from __future__ import annotations

import json
import os
import re
from html.parser import HTMLParser
from typing import Any, Iterable
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


USER_AGENT = os.environ.get("BUREAUCRACY_PIPELINE_UA", "bureaucracy-data-pipeline/1.0")

ENTITY_KEYWORDS = (
    "department",
    "agency",
    "bureau",
    "office",
    "division",
    "administration",
    "commission",
    "committee",
    "subcommittee",
    "service",
    "council",
    "director",
    "secretary",
    "administrator",
    "commissioner",
    "chief",
    "chair",
    "inspector general",
    "under secretary",
    "assistant secretary",
)


def request_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 45,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    query = f"?{urlencode(params)}" if params else ""
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    if headers:
        request_headers.update(headers)

    request = Request(
        f"{url}{query}",
        data=body,
        headers=request_headers,
        method="POST" if body is not None else "GET",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def request_text(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: int = 45,
    headers: dict[str, str] | None = None,
) -> str:
    query = f"?{urlencode(params)}" if params else ""
    request_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    if headers:
        request_headers.update(headers)

    request = Request(f"{url}{query}", headers=request_headers, method="GET")
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def split_env_list(name: str, defaults: Iterable[str]) -> list[str]:
    raw = os.environ.get(name, "")
    if not raw.strip():
        return list(defaults)
    values = [item.strip() for item in raw.split(",")]
    return [item for item in values if item]


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def unique_strings(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def is_official_government_url(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    return host.endswith(".gov") or host.endswith(".mil")


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def looks_like_entity(text: str) -> bool:
    cleaned = normalize_whitespace(text)
    if len(cleaned) < 4 or len(cleaned) > 180:
        return False
    lowered = cleaned.lower()
    if any(keyword in lowered for keyword in ENTITY_KEYWORDS):
        return True
    return bool(re.match(r"^(office|bureau|division|committee|subcommittee|director|administrator)\b", lowered))


def infer_type_from_name(name: str) -> str:
    lowered = normalize_whitespace(name).lower()
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
            "secretary",
            "administrator",
            "commissioner",
            "chief",
            "chair",
            "inspector general",
            "under secretary",
            "assistant secretary",
        )
    ):
        return "Position"
    if "office" in lowered or "council" in lowered:
        return "Office"
    if any(token in lowered for token in ("agency", "administration", "service", "commission")):
        return "Agency"
    return "Office"


class StructuredHtmlParser(HTMLParser):
    TRACKED_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "li", "td", "th", "p"}

    def __init__(self) -> None:
        super().__init__()
        self._active_tag: str | None = None
        self._parts: list[str] = []
        self.blocks: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.TRACKED_TAGS:
            self._flush()
            self._active_tag = tag

    def handle_endtag(self, tag: str) -> None:
        if tag == self._active_tag:
            self._flush()
            self._active_tag = None

    def handle_data(self, data: str) -> None:
        if self._active_tag:
            self._parts.append(data)

    def close(self) -> None:
        self._flush()
        super().close()

    def _flush(self) -> None:
        if not self._parts or not self._active_tag:
            self._parts = []
            return
        text = normalize_whitespace(" ".join(self._parts))
        if text:
            self.blocks.append((self._active_tag, text))
        self._parts = []


def parse_html_blocks(html: str) -> list[tuple[str, str]]:
    parser = StructuredHtmlParser()
    parser.feed(html)
    parser.close()
    return parser.blocks


def build_candidate(
    *,
    name: str,
    source_url: str,
    source_type: str,
    discovery_method: str,
    possible_parent: str | None = None,
    desc: str = "",
    candidate_type: str | None = None,
    confidence_estimate: float = 0.5,
) -> dict[str, Any]:
    return {
        "name": normalize_whitespace(name),
        "type": candidate_type or infer_type_from_name(name),
        "parentName": normalize_whitespace(possible_parent or "") or None,
        "possibleParent": normalize_whitespace(possible_parent or "") or None,
        "desc": normalize_whitespace(desc),
        "sourceUrl": source_url,
        "sourceUrls": [source_url] if source_url else [],
        "sourceType": source_type,
        "sourceTypes": [source_type] if source_type else [],
        "discoveryMethod": discovery_method,
        "confidenceEstimate": clamp(confidence_estimate),
    }


def extract_html_candidates(
    html: str,
    *,
    source_url: str,
    source_type: str,
    discovery_method: str,
    default_parent: str | None = None,
    desc_prefix: str = "",
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for tag, text in parse_html_blocks(html):
        if not looks_like_entity(text):
            continue
        confidence = 0.45
        if tag in {"h1", "h2", "h3"}:
            confidence += 0.18
        elif tag in {"li", "th", "td"}:
            confidence += 0.1
        desc = f"{desc_prefix} {text}".strip()
        candidates.append(
            build_candidate(
                name=text,
                source_url=source_url,
                source_type=source_type,
                discovery_method=discovery_method,
                possible_parent=default_parent,
                desc=desc,
                confidence_estimate=confidence,
            )
        )
    return candidates
