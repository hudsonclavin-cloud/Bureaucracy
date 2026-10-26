"""The government's own lists, reconciled against the graph: every entry a node
or a recorded disposition, and the gap as one number.

`docs/DEFINITION_OF_DONE.md` criterion 4(a) is done when every unit on five
official lists -- the Government Manual's entries, the Federal Register agency
directory, USAspending's toptier agencies, the House Clerk's and the Senate's
committee lists, the current Plum Book's agencies -- "is either a node, or
recorded in CURATION.md as deliberately not one (scaffolding, a grouping, out
of scope)", and every curated committee name a complete list does not carry is
"resolved: renamed, superseded, or kept with the reason".

`data/curation/list_dispositions.json` is the reviewed record. Each row names a
list, the entry exactly as the list prints it, a disposition from the closed
vocabulary below and the basis in words; some kinds need a node id (the unit
the entry names under another wording, the post it is carried as, the parent
it sits beneath) or a quote re-found in the list's own text. The table
PROPOSES and the lists DECIDE, as every reviewed table here does: on each run
the five lists are re-read from the committed fixtures, matched to the graph by
each list's own matcher (the same functions the evidence modules use), and a
row is refused when its entry is not on the list, when the entry now reaches a
node (a stale disposition), when its node is missing or of the wrong kind,
when its kind is unknown or its required field absent, or when its quote is
not in the entry's description. `scripts/report_list_reconciliation.py`
renders `docs/LIST_RECONCILIATION.md` from the result.

The vocabulary, and what each kind claims:

- `scaffolding` -- the list's own grouping heading ("Bureaus", "Lower
  Courts", "Defense Agencies"), not a unit.
- `distinct_from_the_graphs_unit` -- the list's unit and the graph's are
  different things with different populations (a civilian military department
  and the uniformed service).
- `carried_as_a_post` -- the graph carries the office as its head's post
  (an Office of Inspector General as the Inspector General).
- `names_a_node_under_another_wording` -- a node under a wording the list's
  matcher does not fold; the node id is required and the entry must still
  fail the matcher, or the row is stale.
- `carried_outside_the_lists_scope` -- the node exists, outside the subtree
  the list's matcher is scoped to (a joint committee under the Senate's list).
- `predecessor_of_a_node` -- a former unit whose functions a node now holds.
- `former_body` -- a body that no longer exists; where the list's own text
  says so the row quotes it, otherwise the basis is the reviewer's statement
  and the report says which.
- `unit_beneath_a_node_not_drawn` -- a live office the graph draws coarser
  than the list; the parent node is required.
- `umbrella_body_drawn_as_its_members` -- a statutory umbrella the graph
  draws as its member units.
- `body_outside_the_graphs_scope` -- an advisory committee, interagency
  council, temporary commission or special inspector general: a reviewer's
  scope decision, recorded for the owner to overturn.
- `non_federal_or_international_body` -- a body that is not a unit of the
  federal government (an international organisation, an interstate compact,
  a federally chartered private corporation).
- `carried_in_a_jointly_measured_node` -- a real unit the Treasury reports on
  one Table 5 line together with a unit the graph already draws (the Bureau of
  Indian Education with the Bureau of Indian Affairs). A node of its own would
  take an apportioned share out of a pool the statement measures for the two
  together, so the graph carries it in that node; the node is required. It is
  a statement about how the money is reported, not about where the unit sits.
- `fund_or_account_not_a_unit` -- an appropriation account or trust fund a
  list reports beside its agencies.
- `unit_the_list_names_not_added` -- a real unit the graph lacks, recorded
  with the route that would add it; counted separately as "addable", never
  as reconciled.
- `unsure` -- counted as unresolved.

For a curated committee name a complete list does not carry:
`kept_the_committees_own_wording`, `former_seat_kept_as_a_record`,
`successor_is_a_sibling_merge_lead`.

Nothing here writes to the graph or to any evidence file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from data_pipeline.exporter.build_graph import DEFAULT_BASE_GRAPH, canonical_name_key, index_tree, is_post_node, load_base_graph

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = PROJECT_ROOT / "tests" / "fixtures"
DEFAULT_TABLE = PROJECT_ROOT / "data" / "curation" / "list_dispositions.json"

LIST_GOVMAN = "government_manual"
LIST_FR = "federal_register_directory"
LIST_TOPTIER = "usaspending_toptier"
LIST_SENATE = "senate_committee_list"
LIST_HOUSE = "house_clerk_committee_list"
LIST_PLUM = "plum_current_agencies"
LISTS = (LIST_GOVMAN, LIST_FR, LIST_TOPTIER, LIST_SENATE, LIST_HOUSE, LIST_PLUM)
LIST_LABELS = {
    LIST_GOVMAN: "United States Government Manual, agency entries",
    LIST_FR: "Federal Register agency directory",
    LIST_TOPTIER: "USAspending toptier agencies",
    LIST_SENATE: "Senate committee list (committees and subcommittees)",
    LIST_HOUSE: "House Clerk committee list (committees and subcommittees)",
    LIST_PLUM: "OPM's current Plum Book export, agencies",
}

#: kind -> (needs node id, needs parent node id, node must be a post, counted as)
KIND_UNRESOLVED = "unresolved"
KIND_ADDABLE = "addable"
KIND_RECONCILED = "reconciled"
KINDS = {
    "scaffolding": (False, False, False, KIND_RECONCILED),
    "distinct_from_the_graphs_unit": (False, False, False, KIND_RECONCILED),
    "carried_as_a_post": (True, False, True, KIND_RECONCILED),
    "names_a_node_under_another_wording": (True, False, False, KIND_RECONCILED),
    "carried_outside_the_lists_scope": (True, False, False, KIND_RECONCILED),
    "predecessor_of_a_node": (True, False, False, KIND_RECONCILED),
    "former_body": (False, False, False, KIND_RECONCILED),
    "unit_beneath_a_node_not_drawn": (False, True, False, KIND_RECONCILED),
    "umbrella_body_drawn_as_its_members": (False, False, False, KIND_RECONCILED),
    "body_outside_the_graphs_scope": (False, False, False, KIND_RECONCILED),
    "non_federal_or_international_body": (False, False, False, KIND_RECONCILED),
    "carried_in_a_jointly_measured_node": (True, False, False, KIND_RECONCILED),
    "fund_or_account_not_a_unit": (False, False, False, KIND_RECONCILED),
    "unit_the_list_names_not_added": (False, False, False, KIND_ADDABLE),
    "unsure": (False, False, False, KIND_UNRESOLVED),
}
CURATED_NAME_KINDS = ("kept_the_committees_own_wording", "former_seat_kept_as_a_record", "successor_is_a_sibling_merge_lead")
#: Kinds whose row may quote the list's own text; the quote is re-found.
QUOTABLE_KINDS = ("former_body", "predecessor_of_a_node")

SENATE_FIXTURE_DIR = FIXTURES / "directories" / "senate"
HOUSE_FIXTURE = FIXTURES / "directories" / "house" / "committees.xlsx"
FR_FIXTURE = FIXTURES / "directories" / "federal_register_agencies.json"
TOPTIER_FIXTURE = FIXTURES / "usaspending" / "toptier_agencies.json"


def load_table(path: str | Path = DEFAULT_TABLE) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("the dispositions table is not an object")
    data.setdefault("entries", [])
    data.setdefault("curatedNames", [])
    return data


def _collapse(text: Any) -> str:
    return " ".join(str(text or "").split())


def _organisations(node_map: dict[str, dict[str, Any]], root_id: str) -> dict[str, dict[str, Any]]:
    return {i: n for i, n in node_map.items() if i != root_id and not is_post_node(n)}


# --------------------------------------------------------------------------
# The lists, each read by its own module and matched by its own matcher
# --------------------------------------------------------------------------

def govman_list(node_map, root_id, alias_table) -> dict[str, Any]:
    from data_pipeline.verification import govman

    manual = govman.read_manual()
    orgs = _organisations(node_map, root_id)
    matched, stats = govman.match_organisations(manual, orgs, alias_table=alias_table)
    reached: set[str] = set()
    for value in matched.values():
        if isinstance(value, dict):
            for key in ("entityId", "entity_id", "id"):
                if value.get(key) is not None:
                    reached.add(str(value[key]))
    entries, unmatched = [], {}
    for entity in manual.get("entities") or []:
        name = _collapse(entity.get("name"))
        entries.append(name)
        if str(entity.get("entityId")) not in reached:
            unmatched[name] = {"entityId": entity.get("entityId"), "parentEntityId": entity.get("parentId"), "description": ""}
    return {"id": LIST_GOVMAN, "version": f"edition {manual.get('edition')}", "sha256": manual.get("sha256"),
            "entries": entries, "matched": len(entries) - len(unmatched), "unmatched": unmatched}


def federal_register_list(graph, node_map, parent_map) -> dict[str, Any]:
    from data_pipeline.verification import directories

    payload = json.loads(FR_FIXTURE.read_text(encoding="utf-8"))
    rows = payload.get("data") or []
    records, _report = directories.match_federal_register(rows, node_map, parent_map, root_id=str(graph.get("id")), fetched_at=payload.get("fetched_at"))
    reached = {str(r.get("entryId")) for r in records.values() if isinstance(r, dict)}
    entry_node = {str(r.get("entryId")): node_id for node_id, r in records.items() if isinstance(r, dict)}
    names_by_id = {str(r.get("id")): _collapse(r.get("name")) for r in rows}
    entries, unmatched = [], {}
    for row in rows:
        name = _collapse(row.get("name"))
        entries.append(name)
        if str(row.get("id")) not in reached:
            parent_id = row.get("parent_id")
            unmatched[name] = {
                "entryId": row.get("id"),
                "parent": names_by_id.get(str(parent_id)) if parent_id is not None else None,
                "parentNodeId": entry_node.get(str(parent_id)) if parent_id is not None else None,
                "site": _collapse(row.get("agency_url")),
                "description": _collapse(row.get("description")),
            }
    return {"id": LIST_FR, "version": f"fetched {str(payload.get('fetched_at') or '')[:10]}", "sha256": payload.get("body_sha256"),
            "entries": entries, "matched": len(entries) - len(unmatched), "unmatched": unmatched}


def toptier_list(node_map, root_id) -> dict[str, Any]:
    from data_pipeline.verification import usaspending

    payload = json.loads(TOPTIER_FIXTURE.read_text(encoding="utf-8"))
    rows = payload.get("results") or []
    orgs = _organisations(node_map, root_id)
    keys = {canonical_name_key(n.get("name")) for n in orgs.values()}
    alias_keys = {canonical_name_key(v.get("apiName")) for node_id, v in getattr(usaspending, "USASPENDING_NAME_ALIASES", {}).items()
                  if isinstance(v, dict) and node_id in orgs}
    entries, unmatched = [], {}
    for row in rows:
        name = _collapse(row.get("agency_name"))
        entries.append(name)
        key = canonical_name_key(name)
        if key not in keys and key not in alias_keys:
            unmatched[name] = {"toptierCode": row.get("toptier_code"), "outlayAmount": row.get("outlay_amount"), "description": ""}
    return {"id": LIST_TOPTIER, "version": f"{len(rows)} agencies as committed", "sha256": None,
            "entries": entries, "matched": len(entries) - len(unmatched), "unmatched": unmatched}


def committee_list(list_id: str, node_map, parent_map) -> dict[str, Any]:
    from data_pipeline.verification import congress

    if list_id == LIST_SENATE:
        committees = congress.load_senate_committees(SENATE_FIXTURE_DIR)
        _records, report = congress.match_senate(committees, node_map, parent_map)
    else:
        committees = congress.load_house_committees(HOUSE_FIXTURE)
        _records, report = congress.match_house(committees, node_map, parent_map)
    entries: list[str] = []
    for committee in committees:
        entries.append(_collapse(committee.get("name")))
        for sub in committee.get("subcommittees") or []:
            entries.append(f"{_collapse(committee.get('name'))} :: {_collapse(sub.get('name'))}")
    unmatched: dict[str, Any] = {}
    for name in report.get("committees_not_in_graph") or []:
        unmatched[_collapse(name)] = {"kind": "committee", "description": ""}
    for item in report.get("subcommittees_not_in_graph") or []:
        unmatched[f"{_collapse(item.get('committee'))} :: {_collapse(item.get('subcommittee'))}"] = {"kind": "subcommittee", "description": ""}
    curated: dict[str, Any] = {}
    for item in report.get("graph_committees_not_in_list") or []:
        curated[str(item.get("id"))] = {"name": _collapse(item.get("name")), "kind": "committee"}
    for item in report.get("subcommittees_not_in_list") or []:
        curated[str(item.get("id"))] = {"name": _collapse(item.get("name")), "kind": "subcommittee", "committee": _collapse(item.get("committee"))}
    return {"id": list_id, "version": f"{len(committees)} committees as committed", "sha256": None,
            "entries": entries, "matched": len(entries) - len(unmatched), "unmatched": unmatched, "curatedNamesNotInList": curated}


def plum_list(graph, node_map, parent_map, alias_table) -> dict[str, Any]:
    from data_pipeline.verification import plum_current

    export = plum_current.load_plum_export()
    result = plum_current.match_organisations(export["groups"], node_map, parent_map, root_id=str(graph.get("id")), alias_table=alias_table)
    agency_matches: dict[str, str] = {}
    for part in result:
        if isinstance(part, dict) and part and all(isinstance(k, str) for k in part) and all(isinstance(v, str) for v in part.values()):
            agency_matches.update(part)
    live: dict[str, int] = {}
    for (agency, _org), rows in export["groups"].items():
        live[agency] = live.get(agency, 0) + sum(int(r.get("rowsListed") or 1) for r in rows)
    entries = sorted(live)
    unmatched = {a: {"liveRows": live[a], "description": ""} for a in entries if a not in agency_matches}
    return {"id": LIST_PLUM, "version": f"fetched {str(export.get('fetched_at') or '')[:10]}", "sha256": export.get("sha256"),
            "entries": entries, "matched": len(entries) - len(unmatched), "unmatched": unmatched}


def collect_lists(graph: dict[str, Any], *, base_graph_path: str | Path = DEFAULT_BASE_GRAPH) -> dict[str, dict[str, Any]]:
    """Every list, its entries, and the entries that reach no node by the
    list's own matcher."""
    from data_pipeline.verification.aliases import load_alias_table

    node_map, parent_map = index_tree(graph)
    root_id = str(graph.get("id"))
    alias_table = load_alias_table(load_base_graph(base_graph_path))
    lists = [
        govman_list(node_map, root_id, alias_table),
        federal_register_list(graph, node_map, parent_map),
        toptier_list(node_map, root_id),
        committee_list(LIST_SENATE, node_map, parent_map),
        committee_list(LIST_HOUSE, node_map, parent_map),
        plum_list(graph, node_map, parent_map, alias_table),
    ]
    return {item["id"]: item for item in lists}


# --------------------------------------------------------------------------
# Adjudication
# --------------------------------------------------------------------------

def adjudicate(graph: dict[str, Any], table: dict[str, Any], lists: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Every row re-checked against the lists and the graph; every unmatched
    entry assigned its accepted row or counted unresolved."""
    if lists is None:
        lists = collect_lists(graph)
    node_map, parent_map = index_tree(graph)
    root_id = str(graph.get("id"))
    accepted: dict[str, dict[str, dict[str, Any]]] = {list_id: {} for list_id in LISTS}
    refused: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in table.get("entries") or []:
        list_id = str(row.get("list") or "")
        entry = _collapse(row.get("entry"))
        kind = str(row.get("disposition") or "")
        why = None
        if list_id not in lists:
            why = f"names a list this project does not hold: {list_id!r}"
        elif kind not in KINDS:
            why = f"disposition {kind!r} is not in the vocabulary"
        elif entry not in lists[list_id]["unmatched"]:
            why = ("the entry now reaches a node by the list's own matcher; the row is stale"
                   if entry in lists[list_id]["entries"] else "the list does not print this entry")
        elif (list_id, entry) in seen:
            why = "a second row for the same entry"
        elif not _collapse(row.get("basis")):
            why = "no basis"
        else:
            needs_node, needs_parent, must_be_post, _ = KINDS[kind]
            node_id = str(row.get("nodeId") or "")
            parent_id = str(row.get("parentNodeId") or "")
            if needs_node and not node_id:
                why = f"{kind} needs nodeId"
            elif node_id and node_id not in node_map:
                why = f"nodeId {node_id!r} is not in the graph"
            elif node_id and must_be_post and not is_post_node(node_map[node_id]):
                why = f"{kind} names {node_id!r}, which is not a post"
            elif node_id and not must_be_post and is_post_node(node_map[node_id]):
                why = f"{kind} names {node_id!r}, which is a post"
            elif needs_parent and not parent_id:
                why = f"{kind} needs parentNodeId"
            elif parent_id and (parent_id not in node_map or is_post_node(node_map[parent_id]) or parent_id == root_id):
                why = f"parentNodeId {parent_id!r} is not an organisation in the graph"
            elif (parent_id and lists[list_id]["unmatched"][entry].get("parentNodeId")
                  and not _descends_from(parent_id, lists[list_id]["unmatched"][entry]["parentNodeId"], parent_map)
                  and row.get("parentOverridesList") is not True):
                why = ("parentNodeId is not the node the list's own parent entry reaches, nor beneath it "
                       f"({lists[list_id]['unmatched'][entry]['parentNodeId']!r}); a row that disputes the list's parent says so with parentOverridesList")
            elif row.get("parentOverridesList") is True and "disputes" not in _collapse(row.get("basis")).casefold():
                why = "parentOverridesList needs a basis that says the row disputes the list's parent"
            elif row.get("quote") is not None:
                quote = _collapse(row.get("quote"))
                description = lists[list_id]["unmatched"][entry].get("description") or ""
                if kind not in QUOTABLE_KINDS:
                    why = f"{kind} takes no quote"
                elif not quote or quote not in description:
                    why = "the quote is not in the list's own text for this entry"
        if why:
            refused.append({"list": list_id, "entry": entry, "disposition": kind, "reason": why})
            continue
        seen.add((list_id, entry))
        accepted[list_id][entry] = dict(row)
    curated_accepted: dict[str, dict[str, dict[str, Any]]] = {LIST_SENATE: {}, LIST_HOUSE: {}}
    for row in table.get("curatedNames") or []:
        list_id = str(row.get("list") or "")
        node_id = str(row.get("nodeId") or "")
        kind = str(row.get("disposition") or "")
        why = None
        if list_id not in curated_accepted:
            why = f"curated names are reconciled against the two committee lists, not {list_id!r}"
        elif kind not in CURATED_NAME_KINDS:
            why = f"disposition {kind!r} is not in the curated-name vocabulary"
        elif node_id not in (lists[list_id].get("curatedNamesNotInList") or {}):
            why = ("the node now reaches the list, or is not a curated name the list lacks" if node_id in node_map else f"nodeId {node_id!r} is not in the graph")
        elif _collapse(row.get("name")) != lists[list_id]["curatedNamesNotInList"][node_id]["name"]:
            why = "the row was written against another name for this node"
        elif not _collapse(row.get("basis")):
            why = "no basis"
        elif node_id in curated_accepted[list_id]:
            why = "a second row for the same node"
        if why:
            refused.append({"list": list_id, "entry": node_id, "disposition": kind, "reason": why})
            continue
        curated_accepted[list_id][node_id] = dict(row)
    per_list = []
    gap = 0
    addable_total = 0
    for list_id in LISTS:
        item = lists[list_id]
        unmatched = item["unmatched"]
        by_kind: dict[str, int] = {}
        unresolved, addable = [], []
        for entry in unmatched:
            row = accepted[list_id].get(entry)
            if row is None:
                unresolved.append(entry)
                continue
            kind = row["disposition"]
            by_kind[kind] = by_kind.get(kind, 0) + 1
            counted = KINDS[kind][3]
            if counted == KIND_UNRESOLVED:
                unresolved.append(entry)
            elif counted == KIND_ADDABLE:
                addable.append(entry)
        curated = item.get("curatedNamesNotInList") or {}
        curated_unresolved = [nid for nid in curated if nid not in curated_accepted.get(list_id, {})]
        curated_by_kind: dict[str, int] = {}
        for row in curated_accepted.get(list_id, {}).values():
            curated_by_kind[row["disposition"]] = curated_by_kind.get(row["disposition"], 0) + 1
        gap += len(unresolved) + len(curated_unresolved)
        addable_total += len(addable)
        per_list.append({
            "id": list_id, "label": LIST_LABELS[list_id], "version": item["version"], "sha256": item.get("sha256"),
            "entries": len(item["entries"]), "matched": item["matched"], "unmatched": len(unmatched),
            "disposed": len(unmatched) - len([e for e in unmatched if accepted[list_id].get(e) is None]),
            "byKind": dict(sorted(by_kind.items(), key=lambda kv: -kv[1])),
            "unresolved": sorted(unresolved), "addable": sorted(addable),
            "curatedNamesNotInList": len(curated), "curatedByKind": dict(sorted(curated_by_kind.items(), key=lambda kv: -kv[1])),
            "curatedUnresolved": sorted(curated_unresolved),
            "rows": accepted[list_id], "curatedRows": curated_accepted.get(list_id, {}), "context": unmatched, "curatedContext": curated,
        })
    return {"lists": per_list, "refused": refused, "gap": gap, "addable": addable_total,
            "kinds": list(KINDS), "curatedNameKinds": list(CURATED_NAME_KINDS)}


def _descends_from(node_id: str, ancestor_id: str, parent_map: dict[str, str]) -> bool:
    cursor: str | None = node_id
    while cursor:
        if cursor == ancestor_id:
            return True
        cursor = parent_map.get(cursor)
    return False
