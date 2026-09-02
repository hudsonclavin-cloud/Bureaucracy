from __future__ import annotations

import json
import os
import re
import sys
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


USER_AGENT = os.environ.get("BUREAUCRACY_PIPELINE_UA", "bureaucracy-data-pipeline/1.0")
BASE_URL = "https://www.federalregister.gov/api/v1/documents.json"
SEARCH_TERMS = ("office", "bureau", "division", "directorate")
# Title-case tokens joined by a few connectors, at most eight words, and the
# match may not run on into a lower-case word. The earlier unbounded character
# class captured from "Office of" to the next full stop, so "Office of
# Management and Budget for Review and Approval" and 169-character abstract
# fragments were emitted as organisational units.
UNIT_KEYWORDS = r"(?:Office|Bureau|Division|Directorate|Administration|Service|Center)"
UNIT_PATTERN = re.compile(
    rf"\b({UNIT_KEYWORDS}\s+(?:of|for)\s+(?:the\s+)?"
    # A connector followed by another unit keyword starts the next unit
    # ("Bureau of X and Office of Y" is two units).
    rf"[A-Z][A-Za-z0-9&'\-]*(?:\s+(?:(?:and|of|the|for|&)\s+)?(?!{UNIT_KEYWORDS}\b)[A-Z][A-Za-z0-9&'\-]*(?:\s+\([A-Z][A-Za-z0-9&'\-]*\))?){{0,7}})"
    r"(?![A-Za-z0-9])",
)
TRAILING_CONNECTORS = re.compile(r"\s+(?:and|of|the|for|&)$", re.IGNORECASE)
MAX_UNIT_NAME_LENGTH = 80


def request_json(url: str, *, params: dict[str, Any], timeout: int = 30) -> dict[str, Any]:
    query = urlencode(params, doseq=True)
    request = Request(
        f"{url}?{query}",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
        method="GET",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def extract_units(text: str) -> list[str]:
    units: list[str] = []
    for match in UNIT_PATTERN.findall(text or ""):
        unit = TRAILING_CONNECTORS.sub("", match.strip())
        # A name that keeps going after "for" is a sentence, not a unit.
        unit = re.split(r"\s+for\s+(?=[A-Z])", unit, maxsplit=1)[0]
        if len(unit) <= MAX_UNIT_NAME_LENGTH and unit not in units:
            units.append(unit)
    return units


def crawl(
    *,
    pages: int = 3,
    per_page: int = 100,
    timeout: int = 30,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for term in SEARCH_TERMS:
        for page in range(1, pages + 1):
            try:
                payload = request_json(
                    BASE_URL,
                    params={
                        "per_page": per_page,
                        "page": page,
                        "order": "newest",
                        "conditions[term]": term,
                    },
                    timeout=timeout,
                )
            except (OSError, ValueError, TimeoutError) as error:
                # Say so: a silent break made an outage look like an empty page.
                print(f"warning: federal register fetch failed for term={term} page={page}: {error}", file=sys.stderr)
                break

            results = payload.get("results", [])
            if not isinstance(results, list) or not results:
                break

            for document in results:
                agencies = document.get("agencies") or []
                agency_name = ""
                if isinstance(agencies, list) and agencies:
                    agency_name = str(agencies[0].get("name") or "").strip()

                title = str(document.get("title") or "").strip()
                abstract = str(document.get("abstract") or "").strip()
                source_url = str(document.get("html_url") or document.get("pdf_url") or "").strip()
                for unit_name in extract_units(f"{title}. {abstract}"):
                    dedupe_key = (unit_name.casefold(), agency_name.casefold())
                    if dedupe_key in seen:
                        continue
                    seen.add(dedupe_key)
                    records.append(
                        {
                            "officeName": unit_name,
                            "agencyName": agency_name,
                            "departmentName": agency_name,
                            "documentUrl": source_url,
                            "sourceUrl": source_url,
                            "description": abstract or title,
                        }
                    )
    return records
