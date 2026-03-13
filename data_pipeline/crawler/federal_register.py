from __future__ import annotations

import re
from typing import Any
from urllib.error import HTTPError, URLError

from data_pipeline.crawler.common import clamp, request_json


API_URL = "https://www.federalregister.gov/api/v1/documents.json"
ENTITY_PATTERN = re.compile(
    r"\b("
    r"Office of [A-Z][A-Za-z&,\- ]+|"
    r"Bureau of [A-Z][A-Za-z&,\- ]+|"
    r"Division of [A-Z][A-Za-z&,\- ]+|"
    r"Department of [A-Z][A-Za-z&,\- ]+|"
    r"[A-Z][A-Za-z&,\- ]+ Administration|"
    r"[A-Z][A-Za-z&,\- ]+ Commission|"
    r"[A-Z][A-Za-z&,\- ]+ Agency|"
    r"Director of [A-Z][A-Za-z&,\- ]+|"
    r"Administrator of [A-Z][A-Za-z&,\- ]+"
    r")\b"
)
PARENT_PATTERN = re.compile(r"(Department of [A-Z][A-Za-z&,\- ]+|[A-Z][A-Za-z&,\- ]+ Agency)")


def discover_candidates(*, per_page: int = 100) -> dict[str, list[dict[str, Any]]]:
    params = {
        "conditions[term]": "office OR bureau OR delegation OR reorganization OR agency",
        "order": "newest",
        "per_page": per_page,
    }

    try:
        payload = request_json(API_URL, params=params)
    except (HTTPError, URLError, TimeoutError, ValueError):
        return {"candidates": []}

    results = payload.get("results") or []
    candidates: list[dict[str, Any]] = []

    for result in results:
        title = str(result.get("title") or "")
        summary = str(result.get("abstract") or result.get("action") or "")
        source_url = str(result.get("html_url") or result.get("pdf_url") or API_URL)
        source_text = f"{title}. {summary}"
        parent_match = PARENT_PATTERN.search(source_text)
        possible_parent = parent_match.group(1).strip() if parent_match else None

        for match in ENTITY_PATTERN.finditer(source_text):
            name = match.group(1).strip(" ,.;:")
            candidates.append(
                {
                    "name": name,
                    "type": None,
                    "possibleParent": possible_parent,
                    "parentName": possible_parent,
                    "desc": f"Organizational entity referenced in the Federal Register: {title}",
                    "sourceUrl": source_url,
                    "sourceUrls": [source_url],
                    "sourceType": "federal_register",
                    "sourceTypes": ["federal_register"],
                    "discoveryMethod": "federal_register_notice_parse",
                    "confidenceEstimate": clamp(0.58 if possible_parent else 0.48),
                }
            )

    return {"candidates": candidates}


if __name__ == "__main__":
    print(discover_candidates())
