from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.processors.normalize_nodes import generate_node_id, normalize_name


BASE_URL = "https://api.usaspending.gov/api/v2/"
TOP_TIER_ENDPOINT = "references/toptier_agencies/"
USER_AGENT = os.environ.get("BUREAUCRACY_PIPELINE_UA", "bureaucracy-data-pipeline/1.0")
HIGH_VALUE_AGENCY_KEYWORDS = (
    "department of defense",
    "department of energy",
    "department of state",
    "department of justice",
    "department of the treasury",
    "department of homeland security",
    "department of transportation",
    "department of health and human services",
    "department of veterans affairs",
    "department of agriculture",
    "department of commerce",
    "department of labor",
    "department of the interior",
    "department of education",
    "environmental protection agency",
    "national aeronautics and space administration",
    "nasa",
    "general services administration",
    "social security administration",
)


def agency_priority(agency: dict[str, Any]) -> tuple[int, float, str]:
    agency_name = normalize_name(
        agency.get("agency_name")
        or agency.get("toptier_agency_name")
        or agency.get("name")
        or ""
    ).casefold()
    priority_rank = 1
    if any(keyword in agency_name for keyword in HIGH_VALUE_AGENCY_KEYWORDS):
        priority_rank = 0
    amount = agency.get("agency_total_obligated_amount") or 0
    try:
        numeric_amount = float(str(amount).replace(",", ""))
    except (TypeError, ValueError):
        numeric_amount = 0.0
    return priority_rank, -numeric_amount, agency_name


def request_json(url: str, *, payload: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any]:
    body = None
    method = "GET"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }

    if payload is not None:
        method = "POST"
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(url, data=body, headers=headers, method=method)
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class USASpendingCrawler:
    def __init__(self, *, timeout: int = 30) -> None:
        self.timeout = timeout

    def fetch_top_tier_agencies(self, *, limit: int = 25) -> list[dict[str, Any]]:
        url = urljoin(BASE_URL, TOP_TIER_ENDPOINT)
        payload = request_json(url, timeout=self.timeout)
        results = payload.get("results") if isinstance(payload, dict) else payload
        if not isinstance(results, list):
            return []
        return sorted(results, key=agency_priority)[:limit]

    def build_records(
        self,
        *,
        limit_agencies: int = 100,
        fiscal_year: int | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        nodes: list[dict[str, Any]] = []

        for agency in self.fetch_top_tier_agencies(limit=limit_agencies):
            agency_name = normalize_name(
                agency.get("agency_name")
                or agency.get("toptier_agency_name")
                or agency.get("name")
                or ""
            )
            if not agency_name:
                continue

            agency_id = generate_node_id(agency_name)
            direct_budget = agency.get("agency_total_obligated_amount")
            top_tier_source_url = urljoin(BASE_URL, TOP_TIER_ENDPOINT)
            nodes.append({
                "id": agency_id,
                "name": agency_name,
                "type": "Agency",
                "desc": agency.get("abbreviation") or "Top-tier federal agency from USAspending.",
                "budget": str(direct_budget or "") or None,
                "annual_budget": str(direct_budget or "") or None,
                "budget_source": "USAspending" if direct_budget else None,
                "budget_year": str(fiscal_year or date.today().year),
                "color": "#4a8ac8",
                "sourceUrls": [top_tier_source_url],
                "sourceTypes": ["usaspending_direct"] if direct_budget else [],
            })

        return nodes, []


def crawl(
    *,
    limit_agencies: int = 100,
    fiscal_year: int | None = None,
) -> dict[str, list[dict[str, Any]]]:
    crawler = USASpendingCrawler()
    nodes, edges = crawler.build_records(
        limit_agencies=limit_agencies,
        fiscal_year=fiscal_year,
    )
    return {"nodes": nodes, "edges": edges}


if __name__ == "__main__":
    print(json.dumps(crawl(limit_agencies=5), indent=2))
