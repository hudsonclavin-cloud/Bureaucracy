from __future__ import annotations

import os
import re
import sys
from http.client import HTTPException
from html.parser import HTMLParser
from typing import Any
from urllib.request import Request, urlopen


# A site owner who sees this in their logs can find out what it is and who
# to complain to. Override with BUREAUCRACY_PIPELINE_UA.
USER_AGENT = os.environ.get(
    "BUREAUCRACY_PIPELINE_UA",
    "bureaucracy-data-pipeline/1.0 (+https://github.com/hudsonclavin-cloud/Bureaucracy)",
)
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
# Anchored pattern (mirrors federal_register.UNIT_PATTERN): the fragment must
# BE an org-unit name, not merely contain a keyword somewhere in menu/JS text.
ORG_UNIT_PATTERN = re.compile(
    r"^(?:Office|Bureau|Division|Directorate|Administration|Service|Center)\s+(?:of|for)\s+[A-Z0-9]"
)
# Non-content containers whose text must never be harvested as org units.
SKIP_TAGS = {
    "script",
    "style",
    "noscript",
    "template",
    "head",
    "title",
    "nav",
    "header",
    "footer",
    "form",
    "button",
    "select",
    "svg",
}
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
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
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
    return bool(ORG_UNIT_PATTERN.match(text))


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
    timeout: int = 30,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for source in sources or list(DEFAULT_DIRECTORY_SOURCES):
        directory_url = str(source.get("directoryUrl") or source.get("url") or "").strip()
        agency_name = str(source.get("agencyName") or source.get("agency") or "").strip()
        if not directory_url or not agency_name:
            continue
        try:
            html = request_text(directory_url, timeout=timeout)
        except (OSError, ValueError, TimeoutError, HTTPException) as error:
            print(f"warning: official directory fetch failed for {directory_url}: {error}", file=sys.stderr)
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
