"""Evidence from the government's own structured directories.

The page-label method (evidence.py) reads an organisation's official page
and looks for its name as a label. It is honest and it is nearly at its
ceiling: 71 organisations have a page of their own, twelve of the largest
hosts refuse robots.txt and are refused in turn by this project's policy,
and the 520 edges that hang under curated groupings have no page to read.

The government also publishes machine-readable lists of itself. The first
used here is the Federal Register's agency directory
(https://www.federalregister.gov/api/v1/agencies.json): every agency that
publishes in the Register, with its name, its parent agency and its own
site. It is fetched verbatim and committed (tests/fixtures/directories/),
and the records derived from it say exactly what the directory says — the
name as listed, the parent as listed, the entry's page — so a claim can be
audited against the file and against the live directory.

Two claims, both weaker than a page and both stated as themselves:

- existence: "the Federal Register's agency directory lists it" —
  `verificationMethod: listed_in_federal_register_agency_directory`, and the
  entry's page as the source URL;
- placement: "the directory files it under <parent>, its parent here" —
  `placementMethod: listed_under_parent_in_federal_register_agency_directory`,
  only when the directory's parent is the node the published tree gives it.
  When the directory files a unit under a *different* parent, that is
  recorded and published as a disagreement, never resolved either way.

Matching is by the project's canonical name key, with one rule the
directory needs: it writes departments as "Energy Department", the curated
file as "Department of Energy (DOE)". Nothing else is inferred; an entry
that matches two nodes, or a node two entries, matches nothing.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from data_pipeline.exporter.build_graph import canonical_name_key
from data_pipeline.json_io import load_json_file
from data_pipeline.processors.normalize_nodes import verify_node_sources

FR_SOURCE = "federal_register_agency_directory"
FR_METHOD = "listed_in_federal_register_agency_directory"
FR_PLACEMENT_METHOD = "listed_under_parent_in_federal_register_agency_directory"
FR_SOURCE_TYPE = "federal_register_directory"
FR_AGENCY_PAGE = "https://www.federalregister.gov/agencies/{slug}"
FR_DIRECTORY_URL = "https://www.federalregister.gov/api/v1/agencies.json"
DEFAULT_DIRECTORY_EVIDENCE_PATH = Path(__file__).resolve().parents[2] / "data" / "verification" / "directory_evidence.json"

STATUS_LISTED = "listed"
STATUS_DISAGREES = "disagrees"


def federal_register_name_keys(name: Any) -> set[str]:
    """The canonical keys a directory name may answer to. "Energy
    Department" is the curated file's "Department of Energy"; "Army
    Department" its "Department of the Army"."""
    key = canonical_name_key(name)
    keys = {key}
    if key.endswith(" department"):
        rest = key[: -len(" department")].strip()
        if rest:
            keys.add(f"department of {rest}")
            keys.add(f"department of the {rest}")
    return {k for k in keys if k}


def load_directory_file(path: str | Path) -> dict[str, Any]:
    """A verbatim fetch: {"fetched_at", "url", "data": [...]}; a bare list is
    accepted with no fetch time, and then no record can carry a date."""
    payload = load_json_file(path, default_factory=dict)
    if isinstance(payload, list):
        return {"fetched_at": None, "url": None, "data": payload}
    if not isinstance(payload, dict):
        return {"fetched_at": None, "url": None, "data": []}
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("results"), list):
        data = data["results"]
    return {"fetched_at": payload.get("fetched_at"), "url": payload.get("url"), "data": data if isinstance(data, list) else []}


def load_directory_evidence(path: str | Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    payload = load_json_file(path, default_factory=dict)
    if not isinstance(payload, dict):
        return {}
    records = payload.get("nodes") if isinstance(payload.get("nodes"), dict) else {}
    return {str(k): v for k, v in records.items() if isinstance(v, dict)}


def _is_organisation(node: dict[str, Any]) -> bool:
    return "position" not in str(node.get("type") or "").casefold() and not node.get("synthetic")


def match_federal_register(
    entries: list[dict[str, Any]],
    node_map: dict[str, dict[str, Any]],
    parent_map: dict[str, str | None],
    *,
    root_id: str,
    fetched_at: str | None,
    directory_url: str | None = FR_DIRECTORY_URL,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Records keyed by node id, and a report of what did not match and why."""
    # Organisation nodes by canonical key; a key several nodes share
    # identifies none of them.
    by_key: dict[str, list[str]] = {}
    for node_id, node in node_map.items():
        if node_id == root_id or not _is_organisation(node):
            continue
        key = canonical_name_key(node.get("name"))
        if key:
            by_key.setdefault(key, []).append(node_id)
    ambiguous_node_keys = {k for k, ids in by_key.items() if len(ids) > 1}

    valid = [e for e in entries if isinstance(e, dict) and e.get("name") and e.get("id") is not None]
    by_entry_id = {str(e["id"]): e for e in valid}
    # Entry -> candidate node ids (across its keys), and node -> entries.
    entry_nodes: dict[str, set[str]] = {}
    node_entries: dict[str, set[str]] = {}
    for entry in valid:
        found: set[str] = set()
        for key in federal_register_name_keys(entry["name"]):
            if key in ambiguous_node_keys:
                continue
            found.update(by_key.get(key, []))
        entry_nodes[str(entry["id"])] = found
        for node_id in found:
            node_entries.setdefault(node_id, set()).add(str(entry["id"]))

    report: dict[str, Any] = {
        "source": FR_SOURCE, "directory_url": directory_url, "fetched_at": fetched_at,
        "entries": len(valid), "matched": 0, "unmatched_entries": [], "ambiguous_entries": [],
        "ambiguous_names_in_graph": sorted(ambiguous_node_keys)[:40],
        "placements_listed": 0, "placements_disagree": [], "placements_parent_unmatched": 0, "top_level_entries": 0,
    }
    entry_to_node: dict[str, str] = {}
    for entry in valid:
        eid = str(entry["id"])
        nodes = entry_nodes.get(eid, set())
        if len(nodes) != 1:
            if len(nodes) > 1:
                report["ambiguous_entries"].append({"name": entry["name"], "nodes": sorted(nodes)})
            else:
                report["unmatched_entries"].append(entry["name"])
            continue
        node_id = next(iter(nodes))
        if len(node_entries.get(node_id, set())) != 1:
            report["ambiguous_entries"].append({"name": entry["name"], "nodes": [node_id], "reason": "node answers to several entries"})
            continue
        entry_to_node[eid] = node_id

    records: dict[str, dict[str, Any]] = {}
    for eid, node_id in entry_to_node.items():
        entry = by_entry_id[eid]
        slug = str(entry.get("slug") or "").strip()
        record: dict[str, Any] = {
            "source": FR_SOURCE,
            "status": STATUS_LISTED,
            "entryId": entry.get("id"),
            "listedName": entry.get("name"),
            "url": FR_AGENCY_PAGE.format(slug=slug) if slug else (entry.get("url") or None),
            "agencyUrl": entry.get("agency_url") or None,
            "directoryUrl": directory_url,
            "checkedAt": fetched_at,
        }
        parent_eid = entry.get("parent_id")
        if parent_eid is None:
            report["top_level_entries"] += 1
        else:
            parent_entry = by_entry_id.get(str(parent_eid))
            record["parentListedName"] = parent_entry.get("name") if parent_entry else None
            parent_node = entry_to_node.get(str(parent_eid))
            if parent_node is None:
                report["placements_parent_unmatched"] += 1
            elif parent_map.get(node_id) == parent_node:
                record["placement"] = {"status": STATUS_LISTED, "parentId": parent_node, "parentListedName": record["parentListedName"]}
                report["placements_listed"] += 1
            else:
                record["placement"] = {
                    "status": STATUS_DISAGREES, "directoryParentId": parent_node,
                    "parentListedName": record["parentListedName"], "treeParentId": parent_map.get(node_id),
                }
                report["placements_disagree"].append({"id": node_id, "directory_parent": parent_node, "tree_parent": parent_map.get(node_id)})
        records[node_id] = record
        report["matched"] += 1
    report["unmatched_entries"] = report["unmatched_entries"][:400]
    return records, report


def listed_name_still_names(node_name: Any, listed_name: Any) -> bool:
    key = canonical_name_key(node_name)
    return bool(key) and key in federal_register_name_keys(listed_name)


def apply_directory_evidence(
    root: dict[str, Any],
    records: dict[str, dict[str, Any]],
    *,
    index_tree=None,
) -> dict[str, Any]:
    """Stamp directory listings onto the nodes they name.

    Runs after apply_evidence_to_tree, which has already withdrawn every
    field this module owns (they are in EVIDENCE_OWNED_FIELDS) and every URL
    it recorded in evidenceUrls; a page-based claim on the same node is kept
    and the directory is added beside it, never over it.
    """
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, parent_map = index_tree(root)
    stats = {"listed": 0, "unknown_node": 0, "stale_name": 0, "placements_listed": 0,
             "placements_disagree": 0, "placements_stale_parent": 0, "urls_added": 0}
    for node_id, record in records.items():
        node = node_map.get(node_id)
        if node is None:
            stats["unknown_node"] += 1
            continue
        if str(record.get("status") or "") != STATUS_LISTED or not record.get("url"):
            continue
        if not listed_name_still_names(node.get("name"), record.get("listedName")):
            stats["stale_name"] += 1
            continue
        url = str(record["url"])
        urls = [str(u) for u in (node.get("sourceUrls") or [])]
        if url not in urls:
            urls.append(url)
            stats["urls_added"] += 1
        node["sourceUrls"] = urls
        mine = [str(u) for u in (node.get("evidenceUrls") or [])]
        if url not in mine:
            mine.append(url)
        node["evidenceUrls"] = mine
        types = [str(t) for t in (node.get("sourceTypes") or [])]
        if FR_SOURCE_TYPE not in types:
            types.append(FR_SOURCE_TYPE)
        node["sourceTypes"] = types
        node["directoryListing"] = {
            "source": FR_SOURCE, "listedName": record.get("listedName"), "url": url,
            "agencyUrl": record.get("agencyUrl"), "parentListedName": record.get("parentListedName"),
            "checkedAt": record.get("checkedAt"),
        }
        checked_at = str(record.get("checkedAt") or "").strip()
        if checked_at and (not node.get("lastVerified") or checked_at > str(node.get("lastVerified"))):
            node["lastVerified"] = checked_at
            node["evidenceVerifiedAt"] = checked_at
        if not node.get("verificationMethod"):
            node["verificationMethod"] = FR_METHOD
        stats["listed"] += 1

        placement = record.get("placement") if isinstance(record.get("placement"), dict) else None
        if placement and placement.get("status") == STATUS_LISTED:
            if str(placement.get("parentId") or "") != str(parent_map.get(node_id) or ""):
                stats["placements_stale_parent"] += 1
            elif node.get("placementVerified") is not True:
                node["placementVerified"] = True
                node["placementUrl"] = url
                node["placementVerifiedAt"] = checked_at or None
                node["placementParentId"] = parent_map.get(node_id)
                node["placementMatchedText"] = record.get("listedName")
                node["placementMethod"] = FR_PLACEMENT_METHOD
                node.pop("placementCheckable", None)
                stats["placements_listed"] += 1
        elif placement and placement.get("status") == STATUS_DISAGREES:
            if str(placement.get("treeParentId") or "") == str(parent_map.get(node_id) or ""):
                node["placementDirectoryDisagreement"] = {
                    "source": FR_SOURCE, "listedUnder": placement.get("parentListedName"),
                    "directoryParentId": placement.get("directoryParentId"), "url": url, "checkedAt": checked_at or None,
                }
                stats["placements_disagree"] += 1
            else:
                stats["placements_stale_parent"] += 1
        verify_node_sources(node)
    return stats
