"""Candidate official sites for Congress's committees, from Congress's own
committee pages.

The page-label verifier (evidence.py) can only read a page it has been
given, and the placement pass can only check an edge whose parent has a
page. No committee has one in official_sites.json, so the 223 committee
and subcommittee nodes are never reached by that method. Each chamber
publishes a page that links every current committee to its own site;
those links are the candidates this module proposes. It proposes only —
nothing here is evidence: a URL in official_sites.json is a page to
fetch, never a claim about the node (CLAUDE.md, "Invariants").

Both pages are fetched verbatim and committed (tests/fixtures/directories/,
each with a .meta.json carrying URL and fetch time), and the parsers read
exactly the structure those files have:

- https://www.house.gov/committees — one Drupal body field,
  ``<div class="field field--name-field-page-body ...">``, holding a
  ``<section>`` with two ``<div class="col-xs-16 col-sm-8"><ul>`` columns;
  each committee is one ``<li data-list-item-id="..."><a
  href="https://judiciary.house.gov/">Judiciary</a></li>``. Standing
  committees are listed by their bare name ("Agriculture", "Ways and
  Means"); the select and joint committees in full ("Permanent Select
  Committee on Intelligence", "Joint Committee on the Library"). No
  subcommittee is named.
- https://www.senate.gov/committees/ — one ``<table id="listOfCommittees">``
  whose ``<thead>`` columns are Committee | Chair | Ranking Member | Total
  Members | Subcommittees:; each ``<tbody><tr>`` starts with ``<td><a
  target="&quot;blank&quot;" href="http://www.judiciary.senate.gov/">
  Judiciary</a></td>`` and its last cell is a ``<ul>`` of the committee's
  subcommittees, each linked to the Senate's own membership page. The
  committee links are ``http://``, as the page prints them.

A bare listed name is read as "Committee on <name>" — that is what the
list's heading says it is and what the curated graph calls it — and the
chamber's key function (``committee_key`` from congress.py for the Senate,
``house_committee_key`` here for the House) reduces both sides to one key.
One listed name to one node, or nothing: a name two nodes answer to, or a
node two names reach, is reported as ambiguous and proposes nothing. A
renamed committee ("Oversight and Government Reform" against the graph's
"Oversight & Accountability") is a miss, reported for curation, never a
near match.

A candidate URL is kept exactly as the page links it, whitespace stripped.
It is proposed only when it is ``https`` and its host is under ``.gov``
(the hosts seen are ``*.house.gov``, ``*.senate.gov``, ``www.senate.gov``
and ``www.jct.gov``); every other link is reported with the node it would
have reached and why it was refused. The Senate's committee links all fail
the scheme rule, so by default the Senate proposes nothing and the report
carries all twenty; ``require_https=False`` proposes them as printed.
"""

from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from data_pipeline.exporter.build_graph import canonical_name_key
from data_pipeline.verification.congress import SENATE_ID_PREFIX, committee_key

HOUSE_ID_PREFIX = "leg-house-cmte-"
HOUSE_COMMITTEES_URL = "https://www.house.gov/committees"
SENATE_COMMITTEES_URL = "https://www.senate.gov/committees/"
HOUSE_BODY_CLASS = "field--name-field-page-body"
SENATE_TABLE_ID = "listOfCommittees"
SENATE_FIRST_COLUMN = "Committee"

REJECT_NOT_HTTPS = "not_https"
REJECT_HOST_NOT_GOV = "host_not_gov"
REJECT_NO_LINK = "no_link"


def house_committee_key(name: Any) -> str:
    """"House Committee on Permanent Select Committee on Intelligence" (a
    curation artifact) and "Permanent Select Committee on Intelligence" (the
    House's own name) are one key; "House Committee on Ways & Means" and
    "Committee on Ways and Means" likewise. Mirrors ``committee_key`` for
    the other chamber, which is left as it is."""
    key = canonical_name_key(name)
    if key.startswith("house "):
        key = key[len("house "):]
    for prefix in (
        "committee on select committee",
        "committee on permanent select committee",
        "committee on special committee",
        "committee on joint ",
    ):
        if key.startswith(prefix):
            key = key[len("committee on "):]
    if key.startswith("committee on the "):
        key = "committee on " + key[len("committee on the "):]
    return key.strip()


def listed_committee_key(listed_name: Any, key_fn) -> str:
    """The pages list a standing committee by its bare name under a heading
    that says "Committee"; a name without the word is "Committee on <name>".
    Select, special and joint committees are listed in full and keyed as
    they are."""
    if "committee" in canonical_name_key(listed_name).split():
        return key_fn(listed_name)
    return key_fn(f"Committee on {listed_name}")


class HouseCommitteeListParser(HTMLParser):
    """``li > a`` inside the page's body field, and nothing outside it."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict[str, str]] = []
        self._body_depth = 0
        self._in_li = False
        self._href: str | None = None
        self._text: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {k: (v or "") for k, v in attrs}
        if tag == "div":
            if self._body_depth:
                self._body_depth += 1
            elif HOUSE_BODY_CLASS in attributes.get("class", "").split():
                self._body_depth = 1
            return
        if not self._body_depth:
            return
        if tag == "li":
            self._in_li = True
        elif tag == "a" and self._in_li and self._text is None:
            self._href = attributes.get("href", "")
            self._text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "div" and self._body_depth:
            self._body_depth -= 1
        elif tag == "li":
            self._in_li = False
        elif tag == "a" and self._text is not None:
            name = " ".join("".join(self._text).split())
            if name:
                self.links.append({"name": name, "href": (self._href or "").strip()})
            self._href, self._text = None, None

    def handle_data(self, data: str) -> None:
        if self._text is not None:
            self._text.append(data)


class SenateCommitteeTableParser(HTMLParser):
    """The first link of the first cell of each body row of the committee
    table; the header row's column texts, so a reshaped table is noticed."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict[str, str]] = []
        self.columns: list[str] = []
        self._in_table = False
        self._in_thead = False
        self._cell = -1
        self._row_done = False
        self._href: str | None = None
        self._text: list[str] | None = None
        self._th: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {k: (v or "") for k, v in attrs}
        if tag == "table":
            self._in_table = attributes.get("id") == SENATE_TABLE_ID
            return
        if not self._in_table:
            return
        if tag == "thead":
            self._in_thead = True
        elif tag == "th" and self._in_thead:
            self._th = []
        elif tag == "tr":
            self._cell, self._row_done = -1, False
        elif tag == "td":
            self._cell += 1
        elif tag == "a" and self._cell == 0 and not self._row_done and self._text is None:
            self._href = attributes.get("href", "")
            self._text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "table":
            self._in_table = False
        elif not self._in_table:
            return
        elif tag == "thead":
            self._in_thead = False
        elif tag == "th" and self._th is not None:
            self.columns.append(" ".join("".join(self._th).split()))
            self._th = None
        elif tag == "a" and self._text is not None:
            name = " ".join("".join(self._text).split())
            if name:
                self.links.append({"name": name, "href": (self._href or "").strip()})
            self._row_done = True
            self._href, self._text = None, None

    def handle_data(self, data: str) -> None:
        if self._text is not None:
            self._text.append(data)
        elif self._th is not None:
            self._th.append(data)


def parse_house_committees(html: str) -> list[dict[str, str]]:
    parser = HouseCommitteeListParser()
    parser.feed(html)
    parser.close()
    return parser.links


def parse_senate_committees(html: str) -> tuple[list[dict[str, str]], list[str]]:
    parser = SenateCommitteeTableParser()
    parser.feed(html)
    parser.close()
    return parser.links, parser.columns


def candidate_host(url: str) -> str | None:
    try:
        return (urlsplit(url).hostname or "").casefold() or None
    except ValueError:
        return None


def refusal_reason(url: str, *, require_https: bool = True) -> str | None:
    """None when the link may be proposed; else why it may not."""
    if not url:
        return REJECT_NO_LINK
    host = candidate_host(url)
    if not host or not host.endswith(".gov"):
        return REJECT_HOST_NOT_GOV
    scheme = urlsplit(url).scheme.casefold()
    if scheme != "https" and (require_https or scheme != "http"):
        return REJECT_NOT_HTTPS
    return None


def _is_type(node: dict[str, Any], type_name: str) -> bool:
    return str(node.get("type") or "").casefold() == type_name


def match_listed_committees(
    listed: list[dict[str, str]],
    node_map: dict[str, dict[str, Any]],
    *,
    id_prefix: str,
    key_fn,
    require_https: bool = True,
) -> tuple[dict[str, list[str]], dict[str, Any]]:
    """One listed name to one committee node, or nothing; the link proposed
    only when the scheme and host rules allow it."""
    graph_committees = {i: n for i, n in node_map.items() if i.startswith(id_prefix) and _is_type(n, "committee")}
    by_key: dict[str, list[str]] = {}
    for node_id, node in graph_committees.items():
        by_key.setdefault(key_fn(node.get("name")), []).append(node_id)
    report: dict[str, Any] = {
        "listed": len(listed), "listed_names": [entry["name"] for entry in listed],
        "matched": 0, "matches": [], "not_in_graph": [], "graph_not_listed": [], "ambiguous": [],
        "rejected_urls": [], "hosts": sorted({h for e in listed if (h := candidate_host(e["href"]))}),
    }
    reached: dict[str, list[dict[str, str]]] = {}
    for entry in listed:
        candidates = by_key.get(listed_committee_key(entry["name"], key_fn), [])
        if len(candidates) > 1:
            report["ambiguous"].append({"name": entry["name"], "nodes": sorted(candidates)})
        elif not candidates:
            report["not_in_graph"].append(entry["name"])
        else:
            reached.setdefault(candidates[0], []).append(entry)
    proposals: dict[str, list[str]] = {}
    for node_id in sorted(reached):
        entries = reached[node_id]
        if len(entries) > 1:
            report["ambiguous"].append({"node": node_id, "names": [e["name"] for e in entries]})
            continue
        entry = entries[0]
        reason = refusal_reason(entry["href"], require_https=require_https)
        if reason:
            report["rejected_urls"].append({"name": entry["name"], "node_id": node_id, "url": entry["href"], "reason": reason})
            continue
        proposals[node_id] = [entry["href"]]
        report["matches"].append({"name": entry["name"], "node_id": node_id, "url": entry["href"]})
    report["matched"] = len(proposals)
    for node_id, node in graph_committees.items():
        if node_id not in reached:
            report["graph_not_listed"].append({"id": node_id, "name": node.get("name")})
    return proposals, report


def _read_meta(html_path: Path) -> dict[str, Any]:
    meta_path = html_path.with_name(html_path.name + ".meta.json")
    if not meta_path.exists():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def load_congress_site_proposals(
    house_html_path: str | Path,
    senate_html_path: str | Path,
    node_map: dict[str, dict[str, Any]],
    *,
    require_https: bool = True,
) -> tuple[dict[str, list[str]], dict[str, Any]]:
    """``{node_id: [url]}`` from both chambers' committee pages, and a report
    saying per chamber what was listed, matched, missed, refused and where
    the links point; the pages' fetch times from their meta sidecars."""
    house_path, senate_path = Path(house_html_path), Path(senate_html_path)
    house_meta, senate_meta = _read_meta(house_path), _read_meta(senate_path)
    house_listed = parse_house_committees(house_path.read_text(encoding="utf-8"))
    senate_listed, senate_columns = parse_senate_committees(senate_path.read_text(encoding="utf-8"))
    house_proposals, house_report = match_listed_committees(
        house_listed, node_map, id_prefix=HOUSE_ID_PREFIX, key_fn=house_committee_key, require_https=require_https,
    )
    senate_proposals, senate_report = match_listed_committees(
        senate_listed, node_map, id_prefix=SENATE_ID_PREFIX, key_fn=committee_key, require_https=require_https,
    )
    house_report.update({
        "url": house_meta.get("final_url") or house_meta.get("url") or HOUSE_COMMITTEES_URL,
        "fetched_at": house_meta.get("fetched_at"), "file": house_path.name,
    })
    senate_report.update({
        "url": senate_meta.get("final_url") or senate_meta.get("url") or SENATE_COMMITTEES_URL,
        "fetched_at": senate_meta.get("fetched_at"), "file": senate_path.name, "columns": senate_columns,
        "table_as_expected": bool(senate_columns) and senate_columns[0] == SENATE_FIRST_COLUMN,
    })
    proposals = {**house_proposals, **senate_proposals}
    report = {
        "house": house_report, "senate": senate_report, "require_https": require_https,
        "proposed": len(proposals), "hosts": sorted(set(house_report["hosts"]) | set(senate_report["hosts"])),
    }
    return proposals, report
