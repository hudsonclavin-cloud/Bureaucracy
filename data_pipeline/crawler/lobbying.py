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
BASE_URL = "https://lda.senate.gov/api/v1/"
# Anonymous LDA API access is throttled to 15 requests per minute.
ANONYMOUS_REQUEST_DELAY = 4.0
RATE_LIMIT_DEFAULT_WAIT = 30.0
RATE_LIMIT_MAX_WAIT = 120.0


def clean_name(value: Any) -> str:
    """Normalize a display name, returning '' (rather than the 'Unnamed Node'
    placeholder normalize_name produces) when the raw value is missing/blank."""
    text = "" if value is None else str(value)
    if not text.strip():
        return ""
    return normalize_name(text)


def rate_limit_wait(error: HTTPError) -> float:
    headers = getattr(error, "headers", None)
    raw = headers.get("Retry-After", "") if headers else ""
    try:
        wait = float(raw or RATE_LIMIT_DEFAULT_WAIT)
    except (TypeError, ValueError):
        wait = RATE_LIMIT_DEFAULT_WAIT
    return min(max(wait, 1.0), RATE_LIMIT_MAX_WAIT)


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
        if not LDA_API_KEY:
            # Honor the 15 requests/minute anonymous rate limit.
            request_delay = max(request_delay, ANONYMOUS_REQUEST_DELAY)
        self.request_delay = request_delay
        self.timeout = timeout

    def fetch_filings(self, *, year: int, pages: int = 5, page_size: int = 50) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        endpoint = f"{BASE_URL}filings/"
        params = {
            "filing_year": year,
            "page_size": page_size,
        }

        page = 1
        retried_rate_limit = False
        while page <= pages:
            try:
                payload = request_json(
                    endpoint,
                    params={**params, "page": page},
                    timeout=self.timeout,
                )
            except HTTPError as error:
                if error.code == 429 and not retried_rate_limit:
                    # Back off once and retry the same page.
                    retried_rate_limit = True
                    time.sleep(rate_limit_wait(error))
                    continue
                print(f"warning: lobbying filings fetch stopped at page {page}: {error}", file=sys.stderr)
                break
            except (URLError, TimeoutError, ValueError, OSError) as error:
                # Keep the pages already collected on transient failures.
                print(f"warning: lobbying filings fetch stopped at page {page}: {error}", file=sys.stderr)
                break

            batch = payload.get("results") or payload.get("filings") or []
            if not isinstance(batch, list) or not batch:
                break
            collected.extend(batch)
            page += 1
            if page <= pages:
                time.sleep(self.request_delay)

        return collected

    def build_records(self, *, year: int, pages: int = 5, page_size: int = 50) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        for filing in self.fetch_filings(year=year, pages=pages, page_size=page_size):
            client_name = clean_name(
                (filing.get("client") or {}).get("name")
                or filing.get("client_name")
                or (filing.get("registrant") or {}).get("name")
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

            # In the LDA v1 schema, government entities are nested inside each
            # lobbying activity, and the issue text is the activity description.
            for activity in filing.get("lobbying_activities") or []:
                if not isinstance(activity, dict):
                    continue
                government_entities = activity.get("government_entities")
                if not isinstance(government_entities, list):
                    continue
                issue_text = clean_name(activity.get("description") or "")

                for entity in government_entities:
                    if not isinstance(entity, dict):
                        continue
                    agency_name = clean_name(
                        entity.get("name")
                        or entity.get("government_entity_name")
                        or entity.get("agency_name")
                        or ""
                    )
                    if not agency_name:
                        continue

                    agency_id = generate_node_id(agency_name)
                    desc = "Government lobbying target discovered through Senate LDA filings."
                    if issue_text:
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


def crawl(*, year: int, pages: int = 5, page_size: int = 50) -> dict[str, list[dict[str, Any]]]:
    crawler = LobbyingCrawler()
    nodes, edges = crawler.build_records(year=year, pages=pages, page_size=page_size)
    return {"nodes": nodes, "edges": edges}


if __name__ == "__main__":
    print(json.dumps(crawl(year=2025, pages=1, page_size=10), indent=2))
