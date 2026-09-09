"""Evidence from Congress's own committee lists.

The Senate publishes one XML file per committee
(https://www.senate.gov/general/committee_membership/committee_memberships_<CODE>.xml)
naming the committee and each of its subcommittees. Unlike a web page, the
set of files is the complete list of the Senate's committees and each file
the complete list of a committee's subcommittees, so absence from it is
evidence: a curated subcommittee the Senate's list does not carry under
its committee is a checked negative, named as such — "not in the official
list" — never a page's silence and never a fuzzy match to the nearest
current name. The names the list carries and the graph lacks are reported
for curation.

The files are fetched verbatim and committed (tests/fixtures/directories/
senate/, each with a .meta.json carrying URL, fetch time and hash). The
House Clerk's equivalent could not be fetched from the pipeline's network
(proxy refusal, recorded in the README); house.gov/committees lists the
committees only, so no House evidence is derived yet.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from data_pipeline.exporter.build_graph import canonical_name_key

SENATE_SOURCE = "senate_committee_list"
SENATE_METHOD = "listed_in_senate_committee_list"
SENATE_PLACEMENT_METHOD = "listed_under_committee_in_senate_committee_list"
STATUS_LISTED = "listed"
STATUS_DISAGREES = "disagrees"
STATUS_NOT_IN_LIST = "not_in_list"
SENATE_ID_PREFIX = "leg-senate-cmte-"


def load_senate_committees(directory: str | Path) -> list[dict[str, Any]]:
    """One record per committee XML, with its meta sidecar's URL and time."""
    out: list[dict[str, Any]] = []
    for xml_path in sorted(Path(directory).glob("committee_memberships_*.xml")):
        meta_path = xml_path.with_name(xml_path.name + ".meta.json")
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        try:
            root = ET.parse(xml_path).getroot()
        except ET.ParseError:
            continue
        committees = root.find(".//committees")
        if committees is None:
            continue
        name = (committees.findtext("committee_name") or "").strip()
        code = (committees.findtext("committee_code") or "").strip()
        if not name:
            continue
        subs = [
            {"name": (s.findtext("subcommittee_name") or "").strip(), "code": (s.findtext("committee_code") or "").strip()}
            for s in committees.findall("subcommittee")
            if (s.findtext("subcommittee_name") or "").strip()
        ]
        out.append({
            "name": name, "code": code, "subcommittees": subs,
            "url": meta.get("final_url") or meta.get("url") or None,
            "fetched_at": meta.get("fetched_at"), "file": xml_path.name,
        })
    return out


def committee_key(name: Any) -> str:
    """"Senate Committee on Select Committee on Ethics" (a curation artifact)
    and "Select Committee on Ethics" (the Senate's own name) are one key;
    "Committee on the Budget" and "Committee on Budget" likewise."""
    key = canonical_name_key(name)
    if key.startswith("senate "):
        key = key[len("senate "):]
    for prefix in ("committee on select committee", "committee on special committee", "committee on joint "):
        if key.startswith(prefix):
            key = key[len("committee on "):]
    if key.startswith("committee on the "):
        key = "committee on " + key[len("committee on the "):]
    return key.strip()


def subcommittee_key(name: Any) -> str:
    key = canonical_name_key(name)
    if key.startswith("subcommittee on "):
        key = key[len("subcommittee on "):]
    if key.startswith("the "):
        key = key[len("the "):]
    return key.strip()


def _is_type(node: dict[str, Any], type_name: str) -> bool:
    return str(node.get("type") or "").casefold() == type_name


def match_senate(
    committees: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
    parent_map: dict[str, str | None],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    graph_committees = {i: n for i, n in node_map.items() if i.startswith(SENATE_ID_PREFIX) and _is_type(n, "committee")}
    by_key: dict[str, list[str]] = {}
    for node_id, node in graph_committees.items():
        by_key.setdefault(committee_key(node.get("name")), []).append(node_id)
    report: dict[str, Any] = {
        "source": SENATE_SOURCE, "committees_in_list": len(committees), "committees_matched": 0,
        "committees_not_in_graph": [], "graph_committees_not_in_list": [], "ambiguous": [],
        "subcommittees_matched": 0, "subcommittees_not_in_list": [], "subcommittees_not_in_graph": [], "placements_disagree": [],
    }
    records: dict[str, dict[str, Any]] = {}
    matched_committee_ids: set[str] = set()
    for committee in committees:
        key = committee_key(committee["name"])
        candidates = by_key.get(key, [])
        if len(candidates) != 1:
            if len(candidates) > 1:
                report["ambiguous"].append({"name": committee["name"], "nodes": candidates})
            else:
                report["committees_not_in_graph"].append(committee["name"])
            continue
        node_id = candidates[0]
        matched_committee_ids.add(node_id)
        report["committees_matched"] += 1
        records[node_id] = {
            "source": SENATE_SOURCE, "status": STATUS_LISTED, "listedName": committee["name"], "code": committee["code"],
            "url": committee.get("url"), "checkedAt": committee.get("fetched_at"),
        }
        # The committee's subcommittees in the graph, and in the list.
        graph_subs = {
            i: n for i, n in node_map.items()
            if parent_map.get(i) == node_id and _is_type(n, "subcommittee")
        }
        sub_by_key: dict[str, list[str]] = {}
        for sid, snode in graph_subs.items():
            sub_by_key.setdefault(subcommittee_key(snode.get("name")), []).append(sid)
        listed_keys = {subcommittee_key(s["name"]): s for s in committee["subcommittees"]}
        for skey, sub in listed_keys.items():
            found = sub_by_key.get(skey, [])
            if len(found) == 1:
                sid = found[0]
                records[sid] = {
                    "source": SENATE_SOURCE, "status": STATUS_LISTED, "listedName": sub["name"], "code": sub["code"],
                    "url": committee.get("url"), "checkedAt": committee.get("fetched_at"),
                    "parentListedName": committee["name"],
                    "placement": {"status": STATUS_LISTED, "parentId": node_id, "parentListedName": committee["name"]},
                }
                report["subcommittees_matched"] += 1
            elif len(found) > 1:
                report["ambiguous"].append({"name": sub["name"], "nodes": found})
            else:
                report["subcommittees_not_in_graph"].append({"committee": committee["name"], "subcommittee": sub["name"]})
        for sid, snode in graph_subs.items():
            if sid in records:
                continue
            # The list is complete for this committee: a name it does not carry
            # is a checked negative, with the list's names beside it.
            records[sid] = {
                "source": SENATE_SOURCE, "status": STATUS_NOT_IN_LIST, "listedUnder": committee["name"],
                "url": committee.get("url"), "checkedAt": committee.get("fetched_at"),
                "listedSubcommittees": [s["name"] for s in committee["subcommittees"]],
            }
            report["subcommittees_not_in_list"].append({"id": sid, "name": snode.get("name"), "committee": committee["name"]})
    for node_id, node in graph_committees.items():
        if node_id not in matched_committee_ids:
            report["graph_committees_not_in_list"].append({"id": node_id, "name": node.get("name")})
            if committees:
                records[node_id] = {
                    "source": SENATE_SOURCE, "status": STATUS_NOT_IN_LIST, "listedUnder": "the Senate's committee list",
                    "url": committees[0].get("url"), "checkedAt": committees[0].get("fetched_at"),
                    "listedSubcommittees": [c["name"] for c in committees],
                }
    return records, report
