from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.processors.normalize_nodes import generate_node_id, normalize_name
from data_pipeline.crawler.common import clamp


SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = os.environ.get("BUREAUCRACY_PIPELINE_UA", "bureaucracy-data-pipeline/1.0")

AGENCY_HIERARCHY_QUERY = """
SELECT ?agency ?agencyLabel ?parent ?parentLabel WHERE {{
  ?agency wdt:P31/wdt:P279* wd:Q327333 .
  OPTIONAL {{ ?agency wdt:P749 ?parent . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
LIMIT {limit}
"""

OFFICE_HOLDER_QUERY = """
SELECT ?agency ?agencyLabel ?position ?positionLabel ?person ?personLabel WHERE {{
  ?agency wdt:P31/wdt:P279* wd:Q327333 .
  ?agency wdt:P2388 ?position .
  OPTIONAL {{
    ?person p:P39 ?statement .
    ?statement ps:P39 ?position .
  }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
LIMIT {limit}
"""

SUBUNIT_QUERY = """
SELECT ?office ?officeLabel ?parent ?parentLabel WHERE {{
  ?office wdt:P361 ?parent .
  ?parent wdt:P31/wdt:P279* wd:Q327333 .
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
LIMIT {limit}
"""


def run_sparql(query: str, *, timeout: int = 45) -> dict[str, Any]:
    params = urlencode({"query": query, "format": "json"})
    request = Request(
        f"{SPARQL_ENDPOINT}?{params}",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/sparql-results+json",
        },
        method="GET",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def extract_label(binding: dict[str, Any], key: str) -> str:
    value = binding.get(key, {}).get("value", "")
    return normalize_name(value)


def classify_parent_type(name: str) -> str:
    lowered = name.lower()
    if "branch" in lowered:
        return "Branch"
    if "department" in lowered:
        return "Department"
    if "bureau" in lowered:
        return "Bureau"
    if "office" in lowered:
        return "Office"
    return "Agency"


class WikidataCrawler:
    def __init__(self, *, request_delay: float = 1.0) -> None:
        self.request_delay = request_delay

    def fetch_bindings(self, query_template: str, *, limit: int) -> list[dict[str, Any]]:
        payload = run_sparql(query_template.format(limit=limit))
        return payload.get("results", {}).get("bindings", [])

    def build_records(
        self,
        *,
        hierarchy_limit: int = 500,
        office_holder_limit: int = 250,
        subunit_limit: int = 500,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        hierarchy_rows = self.fetch_bindings(AGENCY_HIERARCHY_QUERY, limit=hierarchy_limit)
        time.sleep(self.request_delay)
        subunit_rows = self.fetch_bindings(SUBUNIT_QUERY, limit=subunit_limit)
        time.sleep(self.request_delay)
        office_rows = self.fetch_bindings(OFFICE_HOLDER_QUERY, limit=office_holder_limit)

        for row in hierarchy_rows:
            agency_name = extract_label(row, "agencyLabel")
            parent_name = extract_label(row, "parentLabel")
            if not agency_name:
                continue

            agency_id = generate_node_id(agency_name)
            nodes.append(
                {
                    "id": agency_id,
                    "name": agency_name,
                    "type": "Agency",
                    "desc": "Federal agency discovered through Wikidata organizational hierarchy.",
                    "color": "#4a8ac8",
                }
            )

            if parent_name:
                parent_id = generate_node_id(parent_name)
                nodes.append(
                    {
                        "id": parent_id,
                        "name": parent_name,
                        "type": classify_parent_type(parent_name),
                        "desc": "Parent government organization from Wikidata.",
                        "color": "#c8a84a" if "branch" in parent_name.lower() else "#c84a4a",
                    }
                )
                edges.append(
                    {
                        "source": agency_id,
                        "target": parent_id,
                        "type": "reports_to",
                    }
                )

        for row in subunit_rows:
            office_name = extract_label(row, "officeLabel")
            parent_name = extract_label(row, "parentLabel")
            if not office_name or not parent_name:
                continue

            office_type = "Office"
            lowered = office_name.lower()
            if "bureau" in lowered:
                office_type = "Bureau"
            elif "division" in lowered:
                office_type = "Division"

            office_id = generate_node_id(office_name)
            parent_id = generate_node_id(parent_name)
            nodes.append(
                {
                    "id": office_id,
                    "name": office_name,
                    "type": office_type,
                    "desc": f"{office_type} discovered as part of {parent_name} via Wikidata.",
                    "color": "#888888" if office_type == "Office" else "#4a8ac8",
                }
            )
            nodes.append(
                {
                    "id": parent_id,
                    "name": parent_name,
                    "type": classify_parent_type(parent_name),
                    "desc": "Parent organization from Wikidata.",
                }
            )
            edges.append(
                {
                    "source": office_id,
                    "target": parent_id,
                    "type": "reports_to",
                }
            )

        for row in office_rows:
            agency_name = extract_label(row, "agencyLabel")
            position_name = extract_label(row, "positionLabel")
            person_name = extract_label(row, "personLabel")
            if not agency_name or not position_name:
                continue

            agency_id = generate_node_id(agency_name)
            position_id = generate_node_id(position_name, prefix="position")
            nodes.append(
                {
                    "id": position_id,
                    "name": position_name,
                    "type": "Position",
                    "desc": f"Leadership position associated with {agency_name} from Wikidata.",
                    "color": "#888888",
                }
            )
            edges.append(
                {
                    "source": position_id,
                    "target": agency_id,
                    "type": "reports_to",
                }
            )

            if person_name:
                person_id = generate_node_id(person_name, prefix="person")
                nodes.append(
                    {
                        "id": person_id,
                        "name": person_name,
                        "type": "Person",
                        "desc": f"Office holder connected to {position_name} via Wikidata.",
                        "color": "#8a4ac8",
                    }
                )
                edges.append(
                    {
                        "source": person_id,
                        "target": position_id,
                        "type": "manages",
                    }
                )

        return nodes, edges


def crawl(
    *,
    hierarchy_limit: int = 500,
    office_holder_limit: int = 250,
    subunit_limit: int = 500,
) -> dict[str, list[dict[str, Any]]]:
    crawler = WikidataCrawler()
    nodes, edges = crawler.build_records(
        hierarchy_limit=hierarchy_limit,
        office_holder_limit=office_holder_limit,
        subunit_limit=subunit_limit,
    )
    return {"nodes": nodes, "edges": edges}


def discover_candidates(
    *,
    hierarchy_limit: int = 800,
    office_holder_limit: int = 400,
    subunit_limit: int = 800,
) -> dict[str, list[dict[str, Any]]]:
    crawler = WikidataCrawler()
    nodes: list[dict[str, Any]] = []

    hierarchy_rows = crawler.fetch_bindings(AGENCY_HIERARCHY_QUERY, limit=hierarchy_limit)
    time.sleep(crawler.request_delay)
    subunit_rows = crawler.fetch_bindings(SUBUNIT_QUERY, limit=subunit_limit)
    time.sleep(crawler.request_delay)
    office_rows = crawler.fetch_bindings(OFFICE_HOLDER_QUERY, limit=office_holder_limit)

    for row in hierarchy_rows:
        agency_name = extract_label(row, "agencyLabel")
        parent_name = extract_label(row, "parentLabel")
        if not agency_name:
            continue
        nodes.append(
            {
                "id": generate_node_id(agency_name),
                "name": agency_name,
                "type": "Agency",
                "possibleParent": parent_name or "Executive Branch",
                "parentName": parent_name or "Executive Branch",
                "desc": "Government organization discovered from Wikidata agency hierarchy.",
                "sourceUrl": SPARQL_ENDPOINT,
                "sourceUrls": [SPARQL_ENDPOINT],
                "sourceType": "wikidata",
                "sourceTypes": ["wikidata"],
                "discoveryMethod": "sparql_agency_hierarchy",
                "confidenceEstimate": clamp(0.82 if parent_name else 0.74),
            }
        )

    for row in subunit_rows:
        office_name = extract_label(row, "officeLabel")
        parent_name = extract_label(row, "parentLabel")
        if not office_name:
            continue

        nodes.append(
            {
                "id": generate_node_id(office_name),
                "name": office_name,
                "type": "Bureau" if "bureau" in office_name.lower() else "Office",
                "possibleParent": parent_name or None,
                "parentName": parent_name or None,
                "desc": "Sub-agency or office discovered from Wikidata part-of relationships.",
                "sourceUrl": SPARQL_ENDPOINT,
                "sourceUrls": [SPARQL_ENDPOINT],
                "sourceType": "wikidata",
                "sourceTypes": ["wikidata"],
                "discoveryMethod": "sparql_subunit_hierarchy",
                "confidenceEstimate": clamp(0.8 if parent_name else 0.68),
            }
        )

    for row in office_rows:
        agency_name = extract_label(row, "agencyLabel")
        position_name = extract_label(row, "positionLabel")
        person_name = extract_label(row, "personLabel")
        if position_name:
            nodes.append(
                {
                    "id": generate_node_id(position_name, prefix="position"),
                    "name": position_name,
                    "type": "Position",
                    "possibleParent": agency_name or None,
                    "parentName": agency_name or None,
                    "desc": "Leadership position discovered from Wikidata office-holder data.",
                    "sourceUrl": SPARQL_ENDPOINT,
                    "sourceUrls": [SPARQL_ENDPOINT],
                    "sourceType": "wikidata",
                    "sourceTypes": ["wikidata"],
                    "discoveryMethod": "sparql_office_holders",
                    "confidenceEstimate": clamp(0.79 if agency_name else 0.7),
                }
            )
        if person_name and position_name:
            nodes.append(
                {
                    "id": generate_node_id(person_name, prefix="person"),
                    "name": person_name,
                    "type": "Person",
                    "possibleParent": position_name,
                    "parentName": position_name,
                    "desc": "Office holder discovered from Wikidata office-holder data.",
                    "sourceUrl": SPARQL_ENDPOINT,
                    "sourceUrls": [SPARQL_ENDPOINT],
                    "sourceType": "wikidata",
                    "sourceTypes": ["wikidata"],
                    "discoveryMethod": "sparql_office_holders",
                    "confidenceEstimate": 0.73,
                }
            )

    return {"candidates": nodes}


if __name__ == "__main__":
    print(json.dumps(crawl(hierarchy_limit=25, office_holder_limit=10, subunit_limit=25), indent=2))
