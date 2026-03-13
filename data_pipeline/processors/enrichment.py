from __future__ import annotations

import re
from collections import defaultdict
from html.parser import HTMLParser
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from data_pipeline.processors.normalize_edges import EdgeRegistry
from data_pipeline.processors.normalize_nodes import (
    classify_source_url,
    generate_node_id,
    merge_node,
    normalize_name,
    normalize_node,
    normalize_string_list,
    verify_node_sources,
)


USER_AGENT = "bureaucracy-data-pipeline/1.0"
LEADERSHIP_TITLES = (
    "Secretary",
    "Deputy Secretary",
    "Director",
    "Administrator",
    "Assistant Secretary",
    "Chief Officer",
    "Chief Information Officer",
    "Chief Financial Officer",
    "Chair",
    "Commissioner",
)
CREATED_PATTERN = re.compile(r"\b(created|established|formed|set up)\b", re.IGNORECASE)
RESTRUCTURED_PATTERN = re.compile(r"\b(reorgani[sz]ed|restructured|delegation|realigned)\b", re.IGNORECASE)
MERGED_PATTERN = re.compile(r"\b(merged into|consolidated into)\s+([A-Z][A-Za-z0-9&,'\- ]+)", re.IGNORECASE)
RENAMED_PATTERN = re.compile(r"\bformerly known as\s+([A-Z][A-Za-z0-9&,'\- ]+)", re.IGNORECASE)
YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")
COLLABORATION_PATTERN = re.compile(
    r"\b(collaborat(?:e|es|ing)|joint|in coordination with|works with)\b",
    re.IGNORECASE,
)
REGULATES_PATTERN = re.compile(r"\b(regulat(?:e|es|ing|ion)|oversight of)\b", re.IGNORECASE)


class TextBlockParser(HTMLParser):
    TRACKED_TAGS = {"title", "h1", "h2", "h3", "h4", "p", "li", "td", "th"}

    def __init__(self) -> None:
        super().__init__()
        self.active_tag: str | None = None
        self.parts: list[str] = []
        self.blocks: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.TRACKED_TAGS:
            self._flush()
            self.active_tag = tag

    def handle_endtag(self, tag: str) -> None:
        if tag == self.active_tag:
            self._flush()
            self.active_tag = None

    def handle_data(self, data: str) -> None:
        if self.active_tag:
            self.parts.append(data)

    def close(self) -> None:
        self._flush()
        super().close()

    def _flush(self) -> None:
        if not self.active_tag or not self.parts:
            self.parts = []
            return
        text = re.sub(r"\s+", " ", " ".join(self.parts)).strip()
        if text:
            self.blocks.append((self.active_tag, text))
        self.parts = []


def request_text(url: str, *, timeout: int = 10) -> str:
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


def parse_text_blocks(html: str) -> list[tuple[str, str]]:
    parser = TextBlockParser()
    parser.feed(html)
    parser.close()
    return parser.blocks


def normalize_key(value: Any) -> str:
    return normalize_name(value).casefold()


def node_priority(node: dict[str, Any]) -> tuple[int, str]:
    type_name = normalize_key(node.get("type"))
    if "department" in type_name:
        rank = 0
    elif "agency" in type_name:
        rank = 1
    elif "bureau" in type_name:
        rank = 2
    elif "office" in type_name or "division" in type_name:
        rank = 3
    elif "position" in type_name or "role" in type_name:
        rank = 4
    else:
        rank = 5
    return rank, normalize_name(node.get("name"))


def choose_official_website(node: dict[str, Any], wikidata_records: dict[str, list[dict[str, Any]]]) -> str | None:
    if node.get("official_website"):
        return str(node["official_website"]).strip()

    for source_url in node.get("sourceUrls", []) or []:
        if classify_source_url(source_url) == "official_site":
            return source_url

    for record in wikidata_records.get(normalize_key(node.get("name")), []):
        website = str(record.get("officialWebsite") or record.get("website") or "").strip()
        if website:
            return website
    return None


def record_index(records: Iterable[dict[str, Any]], *keys: str) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if not isinstance(record, dict):
            continue
        for key in keys:
            value = record.get(key)
            normalized = normalize_key(value)
            if normalized:
                index[normalized].append(record)
    return index


def extract_related_agencies(text: str, name_index: dict[str, str], self_name: str) -> list[str]:
    matches: list[str] = []
    lowered_text = normalize_name(text)
    for known_name in name_index:
        if known_name == normalize_key(self_name):
            continue
        label = name_index[known_name]
        if len(label) < 6:
            continue
        if label in lowered_text:
            matches.append(label)
    return normalize_string_list(matches)


def build_relationship(
    registry: EdgeRegistry,
    *,
    source_id: str | None,
    target_id: str | None,
    edge_type: str,
) -> bool:
    if not source_id or not target_id or source_id == target_id:
        return False
    return bool(registry.add({"source": source_id, "target": target_id, "type": edge_type}))


def extract_leadership_position_nodes(
    node: dict[str, Any],
    html_blocks: list[tuple[str, str]],
    edge_registry: EdgeRegistry,
) -> list[dict[str, Any]]:
    positions: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    for _, text in html_blocks:
        for title in LEADERSHIP_TITLES:
            lowered_title = title.casefold()
            if lowered_title in text.casefold() and lowered_title not in seen_titles:
                seen_titles.add(lowered_title)
                position_name = f"{title} of {node['name']}"
                position_id = generate_node_id(position_name, prefix="position")
                positions.append(
                    normalize_node(
                        {
                            "id": position_id,
                            "name": position_name,
                            "type": "Position",
                            "parentId": node["id"],
                            "parent_agency": node["name"],
                            "desc": f"Leadership role identified from the official leadership pages for {node['name']}.",
                            "sourceUrls": node.get("sourceUrls", []),
                            "sourceTypes": [*node.get("sourceTypes", []), "official_site"],
                            "official_website": node.get("official_website"),
                        }
                    )
                )
                build_relationship(edge_registry, source_id=position_id, target_id=node["id"], edge_type="reports_to")
    return positions


def infer_history_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    years = YEAR_PATTERN.findall(text)
    full_years = re.findall(r"\b(?:19|20)\d{2}\b", text)
    if CREATED_PATTERN.search(text) and full_years:
        fields["created_year"] = full_years[0]
    if RESTRUCTURED_PATTERN.search(text) and full_years:
        fields["restructured_year"] = full_years[-1]

    merged_match = MERGED_PATTERN.search(text)
    if merged_match:
        fields["merged_into"] = normalize_name(merged_match.group(2))

    renamed_match = RENAMED_PATTERN.search(text)
    if renamed_match:
        fields["renamed_from"] = normalize_name(renamed_match.group(1))

    return fields


def build_budget_index(usaspending_payload: dict[str, list[dict[str, Any]]] | None) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    if not isinstance(usaspending_payload, dict):
        return index
    for node in usaspending_payload.get("nodes", []):
        if not isinstance(node, dict):
            continue
        if normalize_key(node.get("type")) != "agency":
            continue
        budget = node.get("budget")
        if not budget:
            continue
        index[normalize_key(node.get("name"))] = node
    return index


def maybe_parent_budget(
    node: dict[str, Any],
    *,
    working_by_id: dict[str, dict[str, Any]],
    budget_by_name: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None]:
    parent_id = str(node.get("parentId") or "").strip()
    parent_node = working_by_id.get(parent_id) if parent_id else None
    if parent_node:
        budget_record = budget_by_name.get(normalize_key(parent_node.get("name")))
        if budget_record:
            return budget_record, str(parent_node.get("id") or "").strip() or None
    parent_agency = normalize_name(node.get("parent_agency"))
    if parent_agency:
        budget_record = budget_by_name.get(normalize_key(parent_agency))
        if budget_record:
            return budget_record, working_by_id.get(generate_node_id(parent_agency), {}).get("id")
    return None, None


def enrich_nodes(
    *,
    existing_nodes: Iterable[dict[str, Any]],
    direct_payload_nodes: Iterable[dict[str, Any]],
    wikidata_records: Iterable[dict[str, Any]] = (),
    official_directory_records: Iterable[dict[str, Any]] = (),
    federal_register_records: Iterable[dict[str, Any]] = (),
    usaspending_payload: dict[str, list[dict[str, Any]]] | None = None,
    max_http_nodes: int = 18,
    http_timeout: int = 10,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, int]]:
    existing_by_id = {
        str(node.get("id") or "").strip(): normalize_node(node)
        for node in existing_nodes
        if isinstance(node, dict) and node.get("id")
    }
    working_by_id = dict(existing_by_id)
    for node in direct_payload_nodes:
        if not isinstance(node, dict) or not node.get("id"):
            continue
        normalized = normalize_node(node)
        node_id = normalized["id"]
        if node_id in working_by_id:
            working_by_id[node_id] = merge_node(working_by_id[node_id], normalized)
        else:
            working_by_id[node_id] = normalized

    name_to_id = {normalize_key(node.get("name")): node_id for node_id, node in working_by_id.items()}
    name_lookup = {normalize_key(node.get("name")): normalize_name(node.get("name")) for node in working_by_id.values()}
    wikidata_by_name = record_index(wikidata_records, "label", "name", "agencyName", "parentName")
    directory_by_name = record_index(official_directory_records, "officeName", "agencyName")
    federal_by_name = record_index(federal_register_records, "officeName", "agencyName", "departmentName")
    budget_by_name = build_budget_index(usaspending_payload)
    edge_registry = EdgeRegistry()

    enriched_nodes: dict[str, dict[str, Any]] = {}
    stats = {
        "nodes_enriched": 0,
        "relationships_added": 0,
        "leadership_positions_added": 0,
        "budgets_linked": 0,
        "verification_score_changes": 0,
    }

    high_value_nodes = sorted(working_by_id.values(), key=node_priority)
    http_budget = 0

    for node in high_value_nodes:
        updates: dict[str, Any] = {}
        before_score = float(node.get("confidenceScore") or 0.0)
        name_key = normalize_key(node.get("name"))

        wikidata_matches = wikidata_by_name.get(name_key, [])
        if wikidata_matches:
          first = wikidata_matches[0]
          updates["official_website"] = updates.get("official_website") or first.get("officialWebsite") or first.get("website")
          updates["jurisdiction"] = updates.get("jurisdiction") or first.get("countryLabel") or "United States"
          updates["desc"] = updates.get("desc") or first.get("description") or node.get("desc")
          if first.get("parentName") and not node.get("parent_agency"):
              updates["parent_agency"] = normalize_name(first.get("parentName"))
          source_urls = [*node.get("sourceUrls", []), f"https://www.wikidata.org/wiki/{first.get('wikidataId')}"] if first.get("wikidataId") else [*node.get("sourceUrls", [])]
          updates["sourceUrls"] = normalize_string_list(source_urls)
          updates["sourceTypes"] = normalize_string_list([*node.get("sourceTypes", []), "wikidata"])

        directory_matches = directory_by_name.get(name_key, [])
        if directory_matches:
            first = directory_matches[0]
            updates["official_website"] = updates.get("official_website") or first.get("directoryUrl") or first.get("sourceUrl")
            updates["parent_agency"] = updates.get("parent_agency") or normalize_name(first.get("agencyName"))
            updates["desc"] = updates.get("desc") or first.get("description") or node.get("desc")
            updates["sourceUrls"] = normalize_string_list([*node.get("sourceUrls", []), first.get("sourceUrl") or first.get("directoryUrl")])
            updates["sourceTypes"] = normalize_string_list([*node.get("sourceTypes", []), "official_site"])
            if node.get("id") and name_to_id.get(normalize_key(first.get("agencyName"))):
                build_relationship(
                    edge_registry,
                    source_id=node["id"],
                    target_id=name_to_id.get(normalize_key(first.get("agencyName"))),
                    edge_type="reports_to",
                )
                build_relationship(
                    edge_registry,
                    source_id=name_to_id.get(normalize_key(first.get("agencyName"))),
                    target_id=node["id"],
                    edge_type="oversees",
                )

        federal_matches = federal_by_name.get(name_key, [])
        history_text = " ".join(
            str(match.get("description") or match.get("title") or "")
            for match in federal_matches[:4]
        )
        if history_text:
            updates.update({key: value for key, value in infer_history_fields(history_text).items() if value})
            updates["sourceUrls"] = normalize_string_list(
                [*node.get("sourceUrls", []), *[match.get("sourceUrl") or match.get("documentUrl") for match in federal_matches]]
            )
            updates["sourceTypes"] = normalize_string_list([*node.get("sourceTypes", []), "historical_documentation"])
            for match in federal_matches:
                parent_name = normalize_name(match.get("departmentName") or match.get("agencyName"))
                parent_id = name_to_id.get(normalize_key(parent_name))
                if parent_id:
                    if CREATED_PATTERN.search(str(match.get("description") or "")):
                        build_relationship(edge_registry, source_id=node["id"], target_id=parent_id, edge_type="created_by")
                    if RESTRUCTURED_PATTERN.search(str(match.get("description") or "")):
                        build_relationship(edge_registry, source_id=parent_id, target_id=node["id"], edge_type="oversees")

        budget_record = budget_by_name.get(name_key)
        if budget_record:
            updates["annual_budget"] = budget_record.get("budget")
            updates["budget_source"] = "USAspending"
            updates["budget_year"] = budget_record.get("budget_year") or budget_record.get("fiscal_year")
            stats["budgets_linked"] += 1
        else:
            parent_budget_record, parent_budget_node_id = maybe_parent_budget(
                {**node, **updates},
                working_by_id=working_by_id,
                budget_by_name=budget_by_name,
            )
            if parent_budget_record:
                updates["budget_source"] = "USAspending (parent budget)"
                updates["budget_year"] = parent_budget_record.get("budget_year") or parent_budget_record.get("fiscal_year")
                if parent_budget_node_id:
                    build_relationship(edge_registry, source_id=parent_budget_node_id, target_id=node["id"], edge_type="funds")
                stats["budgets_linked"] += 1

        official_website = choose_official_website({**node, **updates}, wikidata_by_name)
        if official_website:
            updates["official_website"] = official_website
            updates["sourceUrls"] = normalize_string_list([*node.get("sourceUrls", []), official_website])
            updates["sourceTypes"] = normalize_string_list([*node.get("sourceTypes", []), "official_site"])

        should_fetch = (
            official_website
            and http_budget < max_http_nodes
            and any(keyword in normalize_key(node.get("type")) for keyword in ("department", "agency", "bureau", "office"))
        )
        if should_fetch:
            http_budget += 1
            try:
                url_variants = [
                    official_website,
                    urljoin(official_website if official_website.endswith("/") else f"{official_website}/", "leadership"),
                    urljoin(official_website if official_website.endswith("/") else f"{official_website}/", "about/leadership"),
                    urljoin(official_website if official_website.endswith("/") else f"{official_website}/", "about/organization"),
                ]
                html_blocks: list[tuple[str, str]] = []
                seen_urls: set[str] = set()
                for url in url_variants:
                    normalized_url = str(url).strip()
                    if not normalized_url or normalized_url in seen_urls:
                        continue
                    seen_urls.add(normalized_url)
                    try:
                        html_blocks.extend(parse_text_blocks(request_text(normalized_url, timeout=http_timeout)))
                    except (HTTPError, URLError, TimeoutError, ValueError):
                        continue
                if html_blocks:
                    block_text = " ".join(text for _, text in html_blocks[:18])
                    if len(block_text) > len(str(node.get("desc") or "")):
                        updates["desc"] = block_text[:500]
                    related = extract_related_agencies(block_text, name_lookup, node["name"])
                    if related:
                        updates["related_agencies"] = normalize_string_list([*node.get("related_agencies", []), *related])
                        for related_name in related:
                            related_id = name_to_id.get(normalize_key(related_name))
                            if related_id:
                                if COLLABORATION_PATTERN.search(block_text):
                                    build_relationship(edge_registry, source_id=node["id"], target_id=related_id, edge_type="collaborates_with")
                                if REGULATES_PATTERN.search(block_text):
                                    build_relationship(edge_registry, source_id=node["id"], target_id=related_id, edge_type="regulates")
                    leadership_nodes = extract_leadership_position_nodes(
                        {**node, **updates, "sourceUrls": normalize_string_list([*node.get("sourceUrls", []), official_website])},
                        html_blocks,
                        edge_registry,
                    )
                    for leadership_node in leadership_nodes:
                        if leadership_node["id"] not in working_by_id and leadership_node["id"] not in enriched_nodes:
                            enriched_nodes[leadership_node["id"]] = leadership_node
                            stats["leadership_positions_added"] += 1
            except Exception:  # noqa: BLE001
                pass

        if updates:
            merged = merge_node(dict(node), normalize_node({**node, **updates}))
            merged = verify_node_sources(merged)
            enriched_nodes[merged["id"]] = merged
            stats["nodes_enriched"] += 1
            if float(merged.get("confidenceScore") or 0.0) > before_score:
                stats["verification_score_changes"] += 1

    for edge in edge_registry.values():
        stats["relationships_added"] += 1

    return (
        sorted(enriched_nodes.values(), key=lambda item: (item.get("parentId") or "", item["name"])),
        edge_registry.values(),
        stats,
    )
