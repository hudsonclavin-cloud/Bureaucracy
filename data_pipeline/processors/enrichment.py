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
LEADERSHIP_PAGE_PATHS = (
    "",
    "leadership",
    "about/leadership",
    "about/organization",
    "organization",
    "organization-chart",
    "org-chart",
    "about",
)
SIGNIFICANT_WORDS = {"and", "of", "the", "for", "to", "on", "in", "u", "s"}
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
LEADERSHIP_TITLE_PATTERN = re.compile(
    r"\b("
    + "|".join(re.escape(title) for title in sorted(LEADERSHIP_TITLES, key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)
REPORTS_TO_PATTERN = re.compile(
    r"\b(reports to|within the|under the|part of the)\s+([A-Z][A-Za-z0-9&,'\- ]+)",
    re.IGNORECASE,
)


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


def normalize_host_path(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def significant_acronym(text: Any) -> str | None:
    words = re.findall(r"[A-Za-z]+", normalize_name(text))
    letters = [word[0].upper() for word in words if word.casefold() not in SIGNIFICANT_WORDS]
    if len(letters) >= 2:
        return "".join(letters)
    return None


def alias_keys(value: Any) -> list[str]:
    name = normalize_name(value)
    if not name:
        return []
    variants = {normalize_key(name)}
    stripped = re.sub(r"^(u\.s\.|us)\s+", "", name, flags=re.IGNORECASE).strip()
    if stripped:
        variants.add(normalize_key(stripped))
    acronym = significant_acronym(name)
    if acronym:
        variants.add(acronym.casefold())
    return [variant for variant in variants if variant]


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
        if len(label) < 6 and not label.isupper():
            continue
        if label in lowered_text:
            matches.append(label)
    return normalize_string_list(matches)


def increment_metric(stats: dict[str, Any], metric_name: str, key: str, amount: int = 1) -> None:
    if not key:
        return
    bucket = stats.setdefault(metric_name, {})
    bucket[key] = int(bucket.get(key, 0)) + amount


def extract_leadership_position_nodes(
    node: dict[str, Any],
    html_blocks: list[tuple[str, str]],
    add_relationship: Any,
    *,
    source_label: str,
) -> list[dict[str, Any]]:
    positions: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    for tag_name, text in html_blocks:
        if tag_name not in {"title", "h1", "h2", "h3", "h4", "li", "td", "th"}:
            continue
        if len(text) > 180:
            continue
        for title_match in LEADERSHIP_TITLE_PATTERN.finditer(text):
            title = next(
                known_title
                for known_title in LEADERSHIP_TITLES
                if known_title.casefold() == title_match.group(1).casefold()
            )
            lowered_title = title.casefold()
            if lowered_title in seen_titles:
                continue
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
            add_relationship(source_id=position_id, target_id=node["id"], edge_type="reports_to", source_label=source_label)
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
        for key in alias_keys(node.get("name")):
            index.setdefault(key, node)
    return index


def ancestor_chain(node: dict[str, Any], working_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    ancestors: list[dict[str, Any]] = []
    visited: set[str] = set()
    current = node
    while current:
        parent_id = str(current.get("parentId") or "").strip()
        if not parent_id or parent_id in visited:
            break
        visited.add(parent_id)
        parent_node = working_by_id.get(parent_id)
        if not parent_node:
            break
        ancestors.append(parent_node)
        current = parent_node
    return ancestors


def maybe_parent_budget(
    node: dict[str, Any],
    *,
    working_by_id: dict[str, dict[str, Any]],
    budget_by_name: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    for parent_node in ancestor_chain(node, working_by_id):
        for key in alias_keys(parent_node.get("name")):
            budget_record = budget_by_name.get(key)
            if budget_record:
                return budget_record, str(parent_node.get("id") or "").strip() or None, "usaspending_parent"
    parent_agency = normalize_name(node.get("parent_agency"))
    if parent_agency:
        for key in alias_keys(parent_agency):
            budget_record = budget_by_name.get(key)
            if budget_record:
                parent_node = working_by_id.get(generate_node_id(parent_agency), {})
                return budget_record, str(parent_node.get("id") or "").strip() or None, "usaspending_parent"
    return None, None, None


def official_url_variants(
    node: dict[str, Any],
    official_website: str,
    directory_matches: list[dict[str, Any]],
) -> list[str]:
    base_urls = [official_website, *node.get("sourceUrls", [])]
    for record in directory_matches:
        base_urls.extend(
            [
                record.get("sourceUrl"),
                record.get("directoryUrl"),
            ]
        )
    seen: set[str] = set()
    variants: list[str] = []
    for base_url in base_urls:
        cleaned = str(base_url or "").strip()
        if not cleaned or classify_source_url(cleaned) != "official_site":
            continue
        root = normalize_host_path(cleaned)
        candidates = [cleaned]
        if root:
            root_with_slash = root if root.endswith("/") else f"{root}/"
            candidates.extend(urljoin(root_with_slash, path) for path in LEADERSHIP_PAGE_PATHS if path)
        for candidate in candidates:
            normalized_candidate = str(candidate).strip()
            if not normalized_candidate or normalized_candidate in seen:
                continue
            seen.add(normalized_candidate)
            variants.append(normalized_candidate)
    return variants


def add_text_relationships(
    *,
    node: dict[str, Any],
    text: str,
    name_to_id: dict[str, str],
    name_lookup: dict[str, str],
    add_relationship: Any,
    source_label: str,
) -> list[str]:
    related_names: list[str] = []
    related = extract_related_agencies(text, name_lookup, node["name"])
    if related:
        related_names.extend(related)
        for related_name in related:
            related_id = name_to_id.get(normalize_key(related_name))
            if not related_id:
                continue
            if COLLABORATION_PATTERN.search(text):
                add_relationship(
                    source_id=node["id"],
                    target_id=related_id,
                    edge_type="collaborates_with",
                    source_label=source_label,
                )
            if REGULATES_PATTERN.search(text):
                add_relationship(
                    source_id=node["id"],
                    target_id=related_id,
                    edge_type="regulates",
                    source_label=source_label,
                )

    for match in REPORTS_TO_PATTERN.finditer(text):
        parent_name = normalize_name(match.group(2))
        parent_id = name_to_id.get(normalize_key(parent_name))
        if not parent_id:
            continue
        add_relationship(source_id=node["id"], target_id=parent_id, edge_type="reports_to", source_label=source_label)
        add_relationship(source_id=parent_id, target_id=node["id"], edge_type="oversees", source_label=source_label)
    return related_names


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
) -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, Any]]:
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
        "enriched_nodes_by_source": {},
        "relationships_by_type": {},
        "relationships_by_source": {},
        "leadership_positions_by_source": {},
        "budgets_linked_by_source": {},
        "verification_score_changes_by_source": {},
        "fetch_failures_by_source": {},
    }

    def add_relationship(*, source_id: str | None, target_id: str | None, edge_type: str, source_label: str) -> bool:
        if not source_id or not target_id or source_id == target_id:
            return False
        added = edge_registry.add({"source": source_id, "target": target_id, "type": edge_type})
        if not added:
            return False
        increment_metric(stats, "relationships_by_type", added["type"])
        increment_metric(stats, "relationships_by_source", source_label)
        return True

    high_value_nodes = sorted(working_by_id.values(), key=node_priority)
    http_budget = 0

    for node in high_value_nodes:
        updates: dict[str, Any] = {}
        before_score = float(node.get("confidenceScore") or 0.0)
        name_key = normalize_key(node.get("name"))
        source_labels: set[str] = set()

        wikidata_matches = wikidata_by_name.get(name_key, [])
        if wikidata_matches:
            source_labels.add("wikidata")
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
            source_labels.add("official_directory")
            first = directory_matches[0]
            updates["official_website"] = updates.get("official_website") or first.get("directoryUrl") or first.get("sourceUrl")
            updates["parent_agency"] = updates.get("parent_agency") or normalize_name(first.get("agencyName"))
            updates["desc"] = updates.get("desc") or first.get("description") or node.get("desc")
            updates["sourceUrls"] = normalize_string_list([*node.get("sourceUrls", []), first.get("sourceUrl") or first.get("directoryUrl")])
            updates["sourceTypes"] = normalize_string_list([*node.get("sourceTypes", []), "official_site"])
            structural_parent_id = str(node.get("parentId") or "").strip() or name_to_id.get(normalize_key(first.get("agencyName")))
            if node.get("id") and structural_parent_id:
                add_relationship(
                    source_id=node["id"],
                    target_id=structural_parent_id,
                    edge_type="reports_to",
                    source_label="official_directory",
                )
                add_relationship(
                    source_id=structural_parent_id,
                    target_id=node["id"],
                    edge_type="oversees",
                    source_label="official_directory",
                )

        federal_matches = federal_by_name.get(name_key, [])
        history_text = " ".join(
            str(match.get("description") or match.get("title") or "")
            for match in federal_matches[:4]
        )
        if history_text:
            source_labels.add("federal_register")
            updates.update({key: value for key, value in infer_history_fields(history_text).items() if value})
            updates["sourceUrls"] = normalize_string_list(
                [*node.get("sourceUrls", []), *[match.get("sourceUrl") or match.get("documentUrl") for match in federal_matches]]
            )
            updates["sourceTypes"] = normalize_string_list([*node.get("sourceTypes", []), "historical_documentation"])
            related_from_history = add_text_relationships(
                node=node,
                text=history_text,
                name_to_id=name_to_id,
                name_lookup=name_lookup,
                add_relationship=add_relationship,
                source_label="federal_register",
            )
            if related_from_history:
                updates["related_agencies"] = normalize_string_list([*node.get("related_agencies", []), *related_from_history])
            for match in federal_matches:
                parent_name = normalize_name(match.get("departmentName") or match.get("agencyName"))
                parent_id = str(node.get("parentId") or "").strip() or name_to_id.get(normalize_key(parent_name))
                if parent_id:
                    if CREATED_PATTERN.search(str(match.get("description") or "")):
                        add_relationship(source_id=node["id"], target_id=parent_id, edge_type="created_by", source_label="federal_register")
                    add_relationship(source_id=node["id"], target_id=parent_id, edge_type="reports_to", source_label="federal_register")
                    add_relationship(source_id=parent_id, target_id=node["id"], edge_type="oversees", source_label="federal_register")

        budget_record = budget_by_name.get(name_key)
        if budget_record:
            updates["annual_budget"] = budget_record.get("budget")
            updates["budget_source"] = "USAspending"
            updates["budget_year"] = budget_record.get("budget_year") or budget_record.get("fiscal_year")
            source_labels.add("usaspending_direct")
            stats["budgets_linked"] += 1
            increment_metric(stats, "budgets_linked_by_source", "usaspending_direct")
        else:
            budget_record = None
            for key in alias_keys(node.get("name")):
                budget_record = budget_by_name.get(key)
                if budget_record:
                    break
            if budget_record:
                updates["annual_budget"] = budget_record.get("budget")
                updates["budget_source"] = "USAspending"
                updates["budget_year"] = budget_record.get("budget_year") or budget_record.get("fiscal_year")
                source_labels.add("usaspending_direct")
                stats["budgets_linked"] += 1
                increment_metric(stats, "budgets_linked_by_source", "usaspending_direct")
            else:
                parent_budget_record, parent_budget_node_id, budget_source_label = maybe_parent_budget(
                    {**node, **updates},
                    working_by_id=working_by_id,
                    budget_by_name=budget_by_name,
                )
                if parent_budget_record:
                    updates["annual_budget"] = updates.get("annual_budget") or parent_budget_record.get("budget")
                    updates["budget_source"] = "USAspending (parent budget)"
                    updates["budget_year"] = parent_budget_record.get("budget_year") or parent_budget_record.get("fiscal_year")
                    if parent_budget_node_id:
                        add_relationship(source_id=parent_budget_node_id, target_id=node["id"], edge_type="funds", source_label=budget_source_label or "usaspending_parent")
                    source_labels.add(budget_source_label or "usaspending_parent")
                    stats["budgets_linked"] += 1
                    increment_metric(stats, "budgets_linked_by_source", budget_source_label or "usaspending_parent")

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
                html_blocks: list[tuple[str, str]] = []
                for url in official_url_variants({**node, **updates}, official_website, directory_matches):
                    try:
                        html_blocks.extend(parse_text_blocks(request_text(url, timeout=http_timeout)))
                    except (HTTPError, URLError, TimeoutError, ValueError):
                        increment_metric(stats, "fetch_failures_by_source", "official_http")
                        continue
                if html_blocks:
                    source_labels.add("official_http")
                    block_text = " ".join(text for _, text in html_blocks[:18])
                    if len(block_text) > len(str(node.get("desc") or "")):
                        updates["desc"] = block_text[:500]
                    related = add_text_relationships(
                        node=node,
                        text=block_text,
                        name_to_id=name_to_id,
                        name_lookup=name_lookup,
                        add_relationship=add_relationship,
                        source_label="official_http",
                    )
                    if related:
                        updates["related_agencies"] = normalize_string_list([*node.get("related_agencies", []), *related])
                    leadership_nodes = extract_leadership_position_nodes(
                        {**node, **updates, "sourceUrls": normalize_string_list([*node.get("sourceUrls", []), official_website])},
                        html_blocks,
                        add_relationship,
                        source_label="official_http",
                    )
                    for leadership_node in leadership_nodes:
                        if leadership_node["id"] not in working_by_id and leadership_node["id"] not in enriched_nodes:
                            enriched_nodes[leadership_node["id"]] = leadership_node
                            stats["leadership_positions_added"] += 1
                            increment_metric(stats, "leadership_positions_by_source", "official_http")
            except Exception:  # noqa: BLE001
                increment_metric(stats, "fetch_failures_by_source", "official_http")

        if updates:
            merged = merge_node(dict(node), normalize_node({**node, **updates}))
            merged = verify_node_sources(merged)
            enriched_nodes[merged["id"]] = merged
            stats["nodes_enriched"] += 1
            for source_label in sorted(source_labels):
                increment_metric(stats, "enriched_nodes_by_source", source_label)
            if float(merged.get("confidenceScore") or 0.0) > before_score:
                stats["verification_score_changes"] += 1
                for source_label in sorted(source_labels):
                    increment_metric(stats, "verification_score_changes_by_source", source_label)

    stats["relationships_added"] = len(edge_registry.values())

    return (
        sorted(enriched_nodes.values(), key=lambda item: (item.get("parentId") or "", item["name"])),
        edge_registry.values(),
        stats,
    )
