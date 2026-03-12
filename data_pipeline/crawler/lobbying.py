from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.processors.normalize_nodes import generate_node_id, normalize_name


USER_AGENT = os.environ.get("BUREAUCRACY_PIPELINE_UA", "bureaucracy-data-pipeline/1.0")
LDA_API_KEY = os.environ.get("LDA_API_KEY")
BASE_URLS = (
    "https://lda.senate.gov/api/v1/",
    "https://lda.senate.gov/api/",
)


def request_json(url: str, *, params: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any]:
    query = f"?{urlencode(params)}" if params else ""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    if LDA_API_KEY:
        headers["Authorization"] = f"Token {LDA_API_KEY}"

    request = Request(f"{url}{query}", headers=headers, method="GET")
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class LobbyingCrawler:
    def __init__(self, *, request_delay: float = 0.5, timeout: int = 30) -> None:
        self.request_delay = request_delay
        self.timeout = timeout

    def fetch_filings(self, *, year: int, pages: int = 5, page_size: int = 50) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        params = {
            "filing_year": year,
            "page_size": page_size,
        }

        for base_url in BASE_URLS:
            endpoint = f"{base_url}filings/"
            collected: list[dict[str, Any]] = []
            try:
                for page in range(1, pages + 1):
                    payload = request_json(
                        endpoint,
                        params={**params, "page": page},
                        timeout=self.timeout,
                    )
                    batch = payload.get("results") or payload.get("filings") or []
                    if not isinstance(batch, list) or not batch:
                        break
                    collected.extend(batch)
                    time.sleep(self.request_delay)
                if collected:
                    return collected
            except (HTTPError, URLError, TimeoutError, ValueError):
                continue

        return results

    def build_records(self, *, year: int, pages: int = 5, page_size: int = 50) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        for filing in self.fetch_filings(year=year, pages=pages, page_size=page_size):
            client_name = normalize_name(
                filing.get("client", {}).get("name")
                or filing.get("client_name")
                or filing.get("registrant", {}).get("name")
                or ""
            )
            if not client_name:
                continue

            client_id = generate_node_id(client_name, prefix="corporation")
            nodes.append(
                {
                    "id": client_id,
                    "name": client_name,
                    "type": "Corporation",
                    "desc": "Corporate entity discovered through lobbying disclosure filings.",
                    "color": "#4ac88a",
                }
            )

            government_entities = (
                filing.get("government_entities")
                or filing.get("government_entity")
                or filing.get("government_entities_details")
                or []
            )
            if not isinstance(government_entities, list):
                continue

            for entity in government_entities:
                agency_name = normalize_name(
                    entity.get("name")
                    or entity.get("government_entity_name")
                    or entity.get("agency_name")
                    or ""
                )
                if not agency_name:
                    continue

                agency_id = generate_node_id(agency_name)
                issue_text = normalize_name(entity.get("issue_description") or entity.get("specific_issues") or "")
                desc = "Government lobbying target discovered through Senate LDA filings."
                if issue_text and issue_text != DEFAULT_ISSUE_TEXT:
                    desc = f"{desc} Filing issue: {issue_text}."

                nodes.append(
                    {
                        "id": agency_id,
                        "name": agency_name,
                        "type": "Agency",
                        "desc": desc,
                        "color": "#4a8ac8",
                    }
                )
                edges.append(
                    {
                        "source": client_id,
                        "target": agency_id,
                        "type": "lobbies",
                    }
                )

        return nodes, edges


DEFAULT_ISSUE_TEXT = "Unnamed Node"


def crawl(*, year: int, pages: int = 5, page_size: int = 50) -> dict[str, list[dict[str, Any]]]:
    crawler = LobbyingCrawler()
    nodes, edges = crawler.build_records(year=year, pages=pages, page_size=page_size)
    return {"nodes": nodes, "edges": edges}


if __name__ == "__main__":
    print(json.dumps(crawl(year=2025, pages=1, page_size=10), indent=2))
