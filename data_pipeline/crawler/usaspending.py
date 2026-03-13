from __future__ import annotations

import json
import os
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.processors.normalize_nodes import generate_node_id, normalize_name


BASE_URL = "https://api.usaspending.gov/api/v2/"
TOP_TIER_ENDPOINT = "references/toptier_agencies/"
SPENDING_BY_AWARD_ENDPOINT = "search/spending_by_award/"
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
    def __init__(self, *, request_delay: float = 0.35, timeout: int = 30) -> None:
        self.request_delay = request_delay
        self.timeout = timeout

    def fetch_top_tier_agencies(self, *, limit: int = 25) -> list[dict[str, Any]]:
        url = urljoin(BASE_URL, TOP_TIER_ENDPOINT)
        payload = request_json(url, timeout=self.timeout)
        results = payload.get("results") if isinstance(payload, dict) else payload
        if not isinstance(results, list):
            return []
        return sorted(results, key=agency_priority)[:limit]

    def fetch_spending_by_award(
        self,
        agency: dict[str, Any],
        *,
        limit: int = 25,
        fiscal_year: int | None = None,
    ) -> list[dict[str, Any]]:
        fiscal_year = fiscal_year or date.today().year
        agency_name = normalize_name(
            agency.get("agency_name")
            or agency.get("toptier_agency_name")
            or agency.get("name")
            or ""
        )

        filters: dict[str, Any] = {
            "time_period": [
                {
                    "start_date": f"{fiscal_year}-01-01",
                    "end_date": f"{fiscal_year}-12-31",
                }
            ],
        }

        top_tier_code = agency.get("agency_id") or agency.get("toptier_code")
        if top_tier_code:
            filters["agencies"] = [
                {
                    "type": "awarding",
                    "tier": "toptier",
                    "name": agency_name,
                    "toptier_code": str(top_tier_code),
                }
            ]
        elif agency_name:
            filters["agencies"] = [{"type": "awarding", "tier": "toptier", "name": agency_name}]

        payload = {
            "filters": filters,
            "fields": [
                "Award ID",
                "Recipient Name",
                "Recipient UEI",
                "Award Amount",
                "Awarding Agency",
                "Funding Agency",
                "recipient_name",
                "Place of Performance State Code",
                "Place of Performance City Code",
                "NAICS Description",
            ],
            "page": 1,
            "limit": limit,
            "sort": "Award Amount",
            "order": "desc",
            "subawards": False,
        }

        url = urljoin(BASE_URL, SPENDING_BY_AWARD_ENDPOINT)
        data = request_json(url, payload=payload, timeout=self.timeout)
        results = data.get("results") if isinstance(data, dict) else data
        if not isinstance(results, list):
            return []
        return results

    def build_records(
        self,
        *,
        limit_agencies: int = 20,
        awards_per_agency: int = 25,
        fiscal_year: int | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

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
            sampled_award_total = 0.0
            direct_budget = agency.get("agency_total_obligated_amount")
            agency_node = {
                "id": agency_id,
                "name": agency_name,
                "type": "Agency",
                "desc": agency.get("abbreviation") or "Top-tier federal agency from USAspending.",
                "budget": str(direct_budget or "") or None,
                "annual_budget": str(direct_budget or "") or None,
                "budget_source": "USAspending" if direct_budget else None,
                "budget_year": str(fiscal_year or date.today().year),
                "color": "#4a8ac8",
            }
            nodes.append(agency_node)

            try:
                award_results = self.fetch_spending_by_award(
                    agency,
                    limit=awards_per_agency,
                    fiscal_year=fiscal_year,
                )
            except (HTTPError, URLError, TimeoutError, ValueError):
                award_results = []

            for award in award_results:
                contractor_name = normalize_name(
                    award.get("Recipient Name")
                    or award.get("recipient_name")
                    or award.get("Award Recipient Name")
                    or ""
                )
                if not contractor_name:
                    continue

                contract_amount = award.get("Award Amount") or award.get("generated_internal_id")
                try:
                    sampled_award_total += float(str(contract_amount).replace(",", ""))
                except (TypeError, ValueError):
                    pass
                industry = award.get("NAICS Description") or award.get("naics_description")
                location = award.get("Place of Performance State Code") or award.get("place_of_performance_code")
                contractor_desc_bits = [f"Top USAspending contractor connected to {agency_name}."]
                if industry:
                    contractor_desc_bits.append(f"Industry: {industry}.")
                if location:
                    contractor_desc_bits.append(f"Location: {location}.")
                if contract_amount:
                    contractor_desc_bits.append(f"Contract amount: {contract_amount}.")

                contractor_id = generate_node_id(contractor_name, prefix="contractor")
                nodes.append(
                    {
                        "id": contractor_id,
                        "name": contractor_name,
                        "type": "Corporation",
                        "desc": " ".join(contractor_desc_bits),
                        "color": "#4ac88a",
                        "industry": industry,
                        "location": location,
                    }
                )
                edges.append(
                    {
                        "source": agency_id,
                        "target": contractor_id,
                        "type": "contracts_with",
                    }
                )

            if not direct_budget and sampled_award_total > 0:
                sample_budget = f"${sampled_award_total:,.0f}"
                agency_node["budget"] = sample_budget
                agency_node["annual_budget"] = sample_budget
                agency_node["budget_source"] = "USAspending sampled obligations"

            time.sleep(self.request_delay)

        return nodes, edges


def crawl(
    *,
    limit_agencies: int = 20,
    awards_per_agency: int = 25,
    fiscal_year: int | None = None,
) -> dict[str, list[dict[str, Any]]]:
    crawler = USASpendingCrawler()
    nodes, edges = crawler.build_records(
        limit_agencies=limit_agencies,
        awards_per_agency=awards_per_agency,
        fiscal_year=fiscal_year,
    )
    return {"nodes": nodes, "edges": edges}


if __name__ == "__main__":
    print(json.dumps(crawl(limit_agencies=5, awards_per_agency=5), indent=2))
