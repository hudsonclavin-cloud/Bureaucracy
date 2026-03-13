from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


USER_AGENT = os.environ.get("BUREAUCRACY_PIPELINE_UA", "bureaucracy-data-pipeline/1.0")
BASE_URL = "https://www.federalregister.gov/api/v1/documents.json"
SEARCH_TERMS = ("office", "bureau", "division", "directorate")
UNIT_PATTERN = re.compile(
    r"\b((?:Office|Bureau|Division|Directorate|Administration|Service|Center)\s+(?:of|for)\s+[A-Z][A-Za-z0-9&,\-()' ]+)",
)


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
    return [match.strip() for match in UNIT_PATTERN.findall(text or "")]


def crawl(
    *,
    pages: int = 3,
    per_page: int = 100,
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
                )
            except Exception:  # noqa: BLE001
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
