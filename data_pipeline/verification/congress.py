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

The House Clerk publishes the same thing as one spreadsheet
(https://clerk.house.gov/Committees/ExcelCommitteeData): every committee
and subcommittee of the current Congress with its code, its type
(Standing, Select, Joint, Subcommittee), its parent's code and, for a
committee, its website. It is read with the standard library alone
(an .xlsx is a zip of XML) and matched by exactly the rules the Senate's
files are — one key to one node or nothing — so the two chambers publish
the same kind of claim under the same gate. clerk.house.gov refused the
pipeline's proxy on 2026-09-08 (recorded in the fixtures README) and
answered on 2026-09-13; the spreadsheet is committed verbatim with its
meta sidecar.

The files are fetched verbatim and committed (tests/fixtures/directories/
senate/ and house/, each with a .meta.json carrying URL, fetch time and
hash).
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

from data_pipeline.exporter.build_graph import canonical_name_key

SENATE_SOURCE = "senate_committee_list"
SENATE_METHOD = "listed_in_senate_committee_list"
SENATE_PLACEMENT_METHOD = "listed_under_committee_in_senate_committee_list"
HOUSE_SOURCE = "house_clerk_committee_list"
HOUSE_METHOD = "listed_in_house_clerk_committee_list"
HOUSE_PLACEMENT_METHOD = "listed_under_committee_in_house_clerk_committee_list"
STATUS_LISTED = "listed"
STATUS_DISAGREES = "disagrees"
STATUS_NOT_IN_LIST = "not_in_list"
SENATE_ID_PREFIX = "leg-senate-cmte-"
HOUSE_ID_PREFIX = "leg-house-cmte-"
SENATE_LIST_LABEL = "the Senate's committee list"
HOUSE_LIST_LABEL = "the House Clerk's committee list"
HOUSE_COMMITTEE_TYPES = ("standing", "select", "joint")


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


_SHEET_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def read_xlsx_rows(path: str | Path) -> list[list[str]]:
    """The first worksheet of an .xlsx as rows of cell text, standard library
    only. Shared strings and inline strings are both read; a cell with
    neither is its raw value. Nothing is typed or trimmed beyond
    whitespace at the ends."""
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            for item in ET.fromstring(archive.read("xl/sharedStrings.xml")).iter(_SHEET_NS + "si"):
                shared.append("".join(t.text or "" for t in item.iter(_SHEET_NS + "t")))
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    rows: list[list[str]] = []
    for row in sheet.iter(_SHEET_NS + "row"):
        cells: list[str] = []
        for cell in row.findall(_SHEET_NS + "c"):
            value = cell.find(_SHEET_NS + "v")
            if cell.get("t") == "s" and value is not None and value.text is not None:
                text = shared[int(value.text)]
            elif cell.get("t") == "inlineStr" or cell.find(_SHEET_NS + "is") is not None:
                text = "".join(t.text or "" for t in cell.iter(_SHEET_NS + "t"))
            else:
                text = value.text if value is not None and value.text is not None else ""
            cells.append(" ".join(str(text).split()))
        rows.append(cells)
    return rows


def load_house_committees(xlsx_path: str | Path) -> list[dict[str, Any]]:
    """The Clerk's spreadsheet as the same shape the Senate loader returns:
    one record per committee (Standing, Select, Joint) carrying its
    subcommittees by the parent-code column, plus the website the Clerk
    lists. The meta sidecar supplies the URL and the fetch time; without
    one the list has no date and nothing is returned."""
    xlsx_path = Path(xlsx_path)
    meta_path = xlsx_path.with_name(xlsx_path.name + ".meta.json")
    if not xlsx_path.exists() or not meta_path.exists():
        return []
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    url = meta.get("final_url") or meta.get("url") or None
    fetched_at = meta.get("fetched_at")
    if not url or not fetched_at:
        return []
    rows = read_xlsx_rows(xlsx_path)
    if not rows:
        return []
    header = [h.strip().casefold() for h in rows[0]]
    try:
        col = {name: header.index(name) for name in ("committee name", "committee code", "committee type", "parent committee")}
    except ValueError:
        return []
    site_col = header.index("website") if "website" in header else None

    def cell(row: list[str], index: int | None) -> str:
        return row[index].strip() if index is not None and index < len(row) else ""

    committees: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    subs: list[tuple[str, dict[str, str]]] = []
    for row in rows[1:]:
        name, code, kind, parent = (cell(row, col[k]) for k in ("committee name", "committee code", "committee type", "parent committee"))
        if not name or not code:
            continue
        if kind.casefold() in HOUSE_COMMITTEE_TYPES and not parent:
            committees[code] = {
                "name": name, "code": code, "kind": kind, "subcommittees": [],
                "website": cell(row, site_col) or None,
                "url": url, "fetched_at": fetched_at, "file": xlsx_path.name,
            }
            order.append(code)
        elif parent:
            subs.append((parent, {"name": name, "code": code}))
    for parent, sub in subs:
        if parent in committees:
            committees[parent]["subcommittees"].append(sub)
    return [committees[code] for code in order]


def committee_key(name: Any) -> str:
    """"Senate Committee on Select Committee on Ethics" (a curation artifact)
    and "Select Committee on Ethics" (the Senate's own name) are one key;
    "Committee on the Budget" and "Committee on Budget" likewise; and the
    House's "House Committee on Permanent Select Committee on Intelligence"
    folds onto the Clerk's "Permanent Select Committee on Intelligence" by
    the same rule."""
    key = canonical_name_key(name)
    for chamber in ("senate ", "house "):
        if key.startswith(chamber):
            key = key[len(chamber):]
            break
    for prefix in ("committee on permanent select committee", "committee on select committee",
                   "committee on special committee", "committee on joint "):
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


def match_committee_list(
    committees: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
    parent_map: dict[str, str | None],
    *,
    source: str,
    id_prefix: str,
    list_label: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """One chamber's complete list against the graph's committees under one
    id prefix. Listed → a record naming the list's spelling; a subcommittee
    the list carries under a committee the graph also has → placed by the
    list's own structure; a curated name the list does not carry → a checked
    negative with the list's names beside it. Never a nearest-name guess."""
    graph_committees = {i: n for i, n in node_map.items() if i.startswith(id_prefix) and _is_type(n, "committee")}
    by_key: dict[str, list[str]] = {}
    for node_id, node in graph_committees.items():
        by_key.setdefault(committee_key(node.get("name")), []).append(node_id)
    report: dict[str, Any] = {
        "source": source, "committees_in_list": len(committees), "committees_matched": 0,
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
            "source": source, "status": STATUS_LISTED, "listedName": committee["name"], "code": committee["code"],
            "url": committee.get("url"), "checkedAt": committee.get("fetched_at"),
        }
        if committee.get("website"):
            records[node_id]["agencyUrl"] = committee["website"]
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
                    "source": source, "status": STATUS_LISTED, "listedName": sub["name"], "code": sub["code"],
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
                "source": source, "status": STATUS_NOT_IN_LIST, "listedUnder": committee["name"],
                "url": committee.get("url"), "checkedAt": committee.get("fetched_at"),
                "listedSubcommittees": [s["name"] for s in committee["subcommittees"]],
            }
            report["subcommittees_not_in_list"].append({"id": sid, "name": snode.get("name"), "committee": committee["name"]})
    for node_id, node in graph_committees.items():
        if node_id not in matched_committee_ids:
            report["graph_committees_not_in_list"].append({"id": node_id, "name": node.get("name")})
            if committees:
                records[node_id] = {
                    "source": source, "status": STATUS_NOT_IN_LIST, "listedUnder": list_label,
                    "url": committees[0].get("url"), "checkedAt": committees[0].get("fetched_at"),
                    "listedSubcommittees": [c["name"] for c in committees],
                }
    return records, report


def match_senate(
    committees: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
    parent_map: dict[str, str | None],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    return match_committee_list(committees, node_map, parent_map, source=SENATE_SOURCE, id_prefix=SENATE_ID_PREFIX, list_label=SENATE_LIST_LABEL)


def match_house(
    committees: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
    parent_map: dict[str, str | None],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    return match_committee_list(committees, node_map, parent_map, source=HOUSE_SOURCE, id_prefix=HOUSE_ID_PREFIX, list_label=HOUSE_LIST_LABEL)
