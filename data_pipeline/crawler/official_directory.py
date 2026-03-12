from __future__ import annotations

import os
import re
from html.parser import HTMLParser
from typing import Any
from urllib.request import Request, urlopen


USER_AGENT = os.environ.get("BUREAUCRACY_PIPELINE_UA", "bureaucracy-data-pipeline/1.0")
DEFAULT_DIRECTORY_SOURCES = (
    {
        "agencyName": "Department of Energy",
        "directoryUrl": "https://www.energy.gov/organization-chart",
    },
    {
        "agencyName": "NASA",
        "directoryUrl": "https://www.nasa.gov/organization/",
    },
    {
        "agencyName": "Department of State",
        "directoryUrl": "https://www.state.gov/bureaus-offices-reporting-directly-to-the-secretary/",
    },
)
ORG_KEYWORDS = ("office", "bureau", "division", "directorate", "administration", "service", "center")
NOISE_PATTERNS = (
    "privacy",
    "cookie",
    "accessibility",
    "subscribe",
    "linkedin",
    "facebook",
    "instagram",
    "youtube",
    "contact",
)


class TextFragmentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.fragments: list[str] = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text:
            self.fragments.append(text)


def request_text(url: str, *, timeout: int = 30) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
        method="GET",
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def looks_like_org_unit(text: str) -> bool:
    lowered = text.lower()
    if len(text) < 8 or len(text) > 120:
        return False
    if any(noise in lowered for noise in NOISE_PATTERNS):
        return False
    return any(keyword in lowered for keyword in ORG_KEYWORDS)


def normalize_fragment(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" -\u2013\u2014")


def extract_directory_records(html: str, *, agency_name: str, directory_url: str, max_records: int = 150) -> list[dict[str, Any]]:
    parser = TextFragmentParser()
    parser.feed(html)

    seen: set[str] = set()
    records: list[dict[str, Any]] = []
    for fragment in parser.fragments:
        normalized = normalize_fragment(fragment)
        if not looks_like_org_unit(normalized):
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        records.append(
            {
                "officeName": normalized,
                "agencyName": agency_name,
                "directoryUrl": directory_url,
                "sourceUrl": directory_url,
                "description": f"Organizational unit discovered from the official directory for {agency_name}.",
            }
        )
        if len(records) >= max_records:
            break
    return records


def crawl(
    *,
    sources: list[dict[str, str]] | None = None,
    max_records_per_source: int = 150,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for source in sources or list(DEFAULT_DIRECTORY_SOURCES):
        directory_url = str(source.get("directoryUrl") or source.get("url") or "").strip()
        agency_name = str(source.get("agencyName") or source.get("agency") or "").strip()
        if not directory_url or not agency_name:
            continue
        try:
            html = request_text(directory_url)
        except Exception:  # noqa: BLE001
            continue
        records.extend(
            extract_directory_records(
                html,
                agency_name=agency_name,
                directory_url=directory_url,
                max_records=max_records_per_source,
            )
        )
    return records
