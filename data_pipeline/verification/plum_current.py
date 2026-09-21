"""Evidence for the graph's position nodes from OPM's CURRENT PLUM export.

`positions.py` reads the archive of the PREVIOUS administration's reported
positions (January 2021 - January 2025). This module reads the live
counterpart: the export the PLUM Data page serves from `escs.opm.gov`
(`/escs-net/api/pbpub/download-data`), committed verbatim at
`tests/fixtures/opm/plum/escs_pbpub_download-data.csv` with the `.meta.json`
its fetch wrote (docs/NETWORK_ACCESS.md §12). Its digest is recomputed from
the bytes on disk before anything is read, the refusal `pay_tables` and
`gs_pay` make, because a `documentSha256` on a record is a claim that this
figure came out of that file.

What a record says is exactly what the export says: for a position node
whose parent organisation answers to one (Agency, Organization) group of the
export, the export lists a position of this title in that organisation, with
the status, appointment type, pay plan and the "Level, Grade, or Pay" cell it
gives. Nothing here is a claim about who holds the post: the export's two
name columns and its unique-ID column are **never read** -- not read and
declined, never materialised. `READ_COLUMNS` is the whole of what is taken
off each row, by header index, and `tests/test_plum_current.py` plants a
sentinel in the three incumbent columns and asserts it appears nowhere in
what this module returns or writes.

Rows and what they are:

- `Position Status` is `Filled`, `Vacant` or `Historical`. Only the first
  two are read. A `Vacant` row is still a listed position -- the export
  says the post exists and is unfilled. A `Historical` row is a past
  incumbency and is counted, never read.
- A row is an incumbency, not a position. Identical duplicate rows for one
  position -- the same (Agency, Organization, Position Title, Pay Plan,
  Level, Grade, or Pay) -- are one listing (`rowsListed` keeps the count).
  Only AFTER that fold does the archive's rule apply: two listed titles
  that collapse onto one key identify neither.
- The "Level, Grade, or Pay" cell holds three different things -- a General
  Schedule grade, an Executive Schedule level, or a rate of basic pay --
  and `positions.split_level_grade_pay` separates them exactly as it does
  for the archive. A rate is published only where every listed row of the
  title prints the same figure.

Matching is the archive's, reused rather than re-implemented: the canonical
name key, one name to one node or nothing, never across organisations
(`positions.match_organisations`, `archive_title_keys`,
`position_name_alternatives`). One rule is added, and it is the export's own
filing read back rather than a guess: the export names twelve units
`EXECUTIVE OFFICE OF THE PRESIDENT - <unit>`. Where the whole name matches
nothing, the half before " - " must name exactly one organisation and the
half after it exactly one organisation beneath that one -- the same scoping
`headcounts.py` applies to a FedScope sub-agency row. The archive printed
the same form and `positions.py` never reached those units. HTML entities
the file carries (`&amp;`, `&#039;`) are unescaped for KEYS only; every
published string is the file's own.

No negative records. The export is not complete for career positions, so a
position absent from it is not evidence of anything.

Two fields are published, and `evidence.EVIDENCE_OWNED_FIELDS` withdraws both
on every build:

- `positionCurrentListing`, with `verificationMethod:
  listed_in_opm_current_plum_export` where no method exists and the export's
  URL in `sourceUrls`. It is a second, independent official document beside
  the archive, so a post listed in both reaches `verified` on the existing
  confidence arithmetic (0.4 + 0.3 for one official URL, +0.1 for a second);
  a post with only this one is `partial`. Placement
  (`listed_under_organization_in_opm_current_plum_export`) only when the
  organisation the export files the title under IS the node's parent in the
  published tree, checked off the tree.
- `positionCurrentPay`, where the row prints a rate of basic pay: the figure
  the export states for the one listing under this title now, validated by
  `financial_evidence.validate_record`, `scopeMatch: proxy` and graded
  `partial` deliberately -- a row is an incumbency, and what one listed
  person is paid is not what the post pays whoever holds it. Never $0. Tied
  to the listing: published only while `positionCurrentListing` still reports
  the same figure, withdrawn with it. It writes no `sourceUrls`,
  `sourceTypes`, `lastVerified` or `verificationMethod`, and it is never a
  cost.
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Mapping

from data_pipeline.exporter.build_graph import canonical_name_key
from data_pipeline.processors.normalize_nodes import verify_node_sources
from data_pipeline.verification.pay_tables import Unreadable, federal_fiscal_year_of
from data_pipeline.verification.positions import (
    CURRENT_PLUM_SOURCE,
    STATUS_LISTED,
    archive_title_keys,
    organisation_name_keys,
    position_name_alternatives,
    split_level_grade_pay,
)

SOURCE = CURRENT_PLUM_SOURCE
SOURCE_TYPE = "opm_plum_current_export"
METHOD = "listed_in_opm_current_plum_export"
PLACEMENT_METHOD = "listed_under_organization_in_opm_current_plum_export"
PAY_SOURCE = "opm_plum_current_export"
PAY_SOURCE_TYPE = "opm_plum_current_export"
PAY_METHOD = "rate_of_basic_pay_stated_in_opm_current_plum_export"
EDITION_LABEL = "OPM PLUM Reporting current export"

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "opm" / "plum"
DEFAULT_EXPORT_CSV = FIXTURE_DIR / "escs_pbpub_download-data.csv"
DEFAULT_EVIDENCE_PATH = Path(__file__).resolve().parents[2] / "data" / "verification" / "plum_current_evidence.json"

#: The export's columns this module reads, and the field each becomes. This
#: is the whole of what is taken off a row: the reader projects by header
#: index onto these names and nothing else is materialised. The three
#: incumbent columns are not named here, not read, and not declined -- they
#: never exist in memory.
READ_COLUMNS = {
    "Agency": "agency",
    "Organization": "organization",
    "Position Title": "title",
    "Position Status": "status",
    "Appointment Type": "appointmentType",
    "Level, Grade, or Pay": "level",
    "Pay Plan": "payPlan",
}
LIVE_STATUSES = ("Filled", "Vacant")
HISTORICAL_STATUS = "Historical"
#: The key identical duplicate rows for one position are folded on.
DEDUP_KEY = ("agency", "organization", "title", "payPlan", "level")
LISTING_FIELDS = ("appointmentType", "payPlan", "level")
_SCOPED_AGENCY = re.compile(r"^(?P<parent>.+?)\s+-\s+(?P<unit>.+)$")


def unescape(text: Any) -> str:
    """The file's HTML entities resolved, for keys only."""
    return html.unescape(str(text or ""))


# --------------------------------------------------------------------------
# Reading the export


def load_plum_export(csv_path: str | Path = DEFAULT_EXPORT_CSV) -> dict[str, Any]:
    """The export as served, folded and grouped, or `Unreadable`.

    The sibling `.meta.json` must record a 200 with a sha256, and the bytes
    on disk must hash to it: an edited file is refused rather than re-hashed,
    for the reason `gs_pay._load_fixture` gives. Only `READ_COLUMNS` are
    taken off each row. `Historical` rows are counted and dropped; `Filled`
    and `Vacant` rows are folded on `DEDUP_KEY`, each fold carrying how many
    rows it stands for and the statuses and appointment types they carried.
    """
    path = Path(csv_path)
    meta_path = path.with_name(path.name + ".meta.json")
    if not meta_path.exists():
        raise Unreadable(f"{path.name} has no .meta.json beside it; an export with no record of its fetch cannot be cited")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    recorded = str(meta.get("sha256") or "").lower()
    if not recorded:
        raise Unreadable(f"{meta_path.name} records no sha256; the fetch it describes served nothing")
    if digest != recorded:
        raise Unreadable(
            f"{path.name} does not match the digest its fetch recorded ({digest} vs {recorded}); "
            "the committed file is not the file that was served"
        )
    url = str(meta.get("final_url") or meta.get("url") or "")
    fetched_at = str(meta.get("fetched_at") or "")
    if not url or not fetched_at:
        raise Unreadable(f"{meta_path.name} is missing the url or the fetch time")
    if meta.get("error") or int(meta.get("status") or 0) != 200:
        raise Unreadable(f"{meta_path.name} records a fetch that did not serve the file")

    status_counts: Counter[str] = Counter()
    folded: dict[tuple[str, ...], dict[str, Any]] = {}
    raw_rows = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = [h.strip() for h in next(reader, [])]
        missing = [column for column in READ_COLUMNS if column not in header]
        if missing:
            raise Unreadable(f"{path.name} lacks the column(s) {missing}; this is not the PLUM export")
        index = {field: header.index(column) for column, field in READ_COLUMNS.items()}
        width = max(index.values()) + 1
        for cells in reader:
            if len(cells) < width:
                continue
            raw_rows += 1
            row = {field: cells[position].strip() for field, position in index.items()}
            if not row["agency"] or not row["title"]:
                continue
            status_counts[row["status"]] += 1
            if row["status"] not in LIVE_STATUSES:
                continue
            key = tuple(row[field] for field in DEDUP_KEY)
            fold = folded.get(key)
            if fold is None:
                fold = {field: row[field] for field in DEDUP_KEY}
                fold["rowsListed"] = 0
                fold["statusCounts"] = Counter()
                fold["appointmentTypeCounts"] = Counter()
                folded[key] = fold
            fold["rowsListed"] += 1
            fold["statusCounts"][row["status"]] += 1
            fold["appointmentTypeCounts"][row["appointmentType"]] += 1
    rows = list(folded.values())
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault((row["agency"], row["organization"]), []).append(row)
    return {
        "url": url,
        "fetched_at": fetched_at,
        "sha256": digest,
        "file": path.name,
        "rows_in_file": raw_rows,
        "status_counts": dict(status_counts.most_common()),
        "historical_rows": status_counts.get(HISTORICAL_STATUS, 0),
        "live_rows": sum(status_counts.get(s, 0) for s in LIVE_STATUSES),
        "rows": rows,
        "groups": groups,
    }


def summarize_export(export: dict[str, Any]) -> dict[str, Any]:
    rows = export.get("rows") or []
    return {
        "rows_in_file": export.get("rows_in_file"),
        "status_counts": export.get("status_counts"),
        "historical_rows_not_read": export.get("historical_rows"),
        "live_rows": export.get("live_rows"),
        "listings_after_dedup": len(rows),
        "folded_duplicates": sum(1 for r in rows if r["rowsListed"] > 1),
        "agencies": len({r["agency"] for r in rows}),
        "organizations": len(export.get("groups") or {}),
        "titles": len({r["title"] for r in rows}),
        "pay_plans": dict(Counter(r["payPlan"] for r in rows).most_common()),
    }


def edition_label(fetched_at: Any) -> str:
    """The label a listing carries in place of the archive's edition: the
    export's own name and the date it was fetched, the only date the file
    states about itself. Nothing about who reported it or when."""
    when = str(fetched_at or "")[:10]
    return f"{EDITION_LABEL} (fetched {when})" if when else EDITION_LABEL


# --------------------------------------------------------------------------
# Name keys


def export_agency_keys(agency: Any) -> set[str]:
    return organisation_name_keys(unescape(agency))


def split_scoped_agency(agency: Any) -> tuple[str, str] | None:
    """("EXECUTIVE OFFICE OF THE PRESIDENT", "WHITE HOUSE OFFICE") for the
    export's own `<parent> - <unit>` form, else None."""
    match = _SCOPED_AGENCY.match(unescape(agency).strip())
    if not match:
        return None
    parent, unit = match.group("parent").strip(), match.group("unit").strip()
    if not parent or not unit:
        return None
    return parent, unit


def export_title_keys(title: Any, organisation_name: Any) -> list[str]:
    return archive_title_keys(unescape(title), unescape(organisation_name))


def agency_unit_name(agency: Any) -> str:
    """The name of the unit an agency string denotes: the whole string, or
    the unit half of the export's scoped form."""
    scoped = split_scoped_agency(agency)
    return scoped[1] if scoped else unescape(agency)


# --------------------------------------------------------------------------
# Matching


def _is_position(node: Mapping[str, Any]) -> bool:
    return "position" in str(node.get("type") or "").casefold()


def _is_organisation(node: Mapping[str, Any]) -> bool:
    return not _is_position(node) and not node.get("synthetic")


def _ancestors_of(node_id: str, parent_map: Mapping[str, str | None]) -> list[str]:
    chain: list[str] = []
    current = parent_map.get(node_id)
    while current:
        chain.append(current)
        current = parent_map.get(current)
    return chain


def match_organisations(
    groups: Mapping[tuple[str, str], list[dict[str, Any]]],
    node_map: Mapping[str, dict[str, Any]],
    parent_map: Mapping[str, str | None],
    *,
    root_id: str,
) -> tuple[dict[str, str], dict[tuple[str, str], str], dict[str, Any]]:
    """Agency -> node id, (Agency, Organization) -> node id, and a report.

    `positions.match_organisations`, with one more route for the agency:
    where the whole name answers to nothing and it is of the export's own
    `<parent> - <unit>` form, the parent half must name exactly one
    organisation and the unit half exactly one organisation beneath it. A
    name answering to several nodes, a node answering to several names, and
    the same for groups, match nothing.
    """
    by_key: dict[str, list[str]] = {}
    for node_id, node in node_map.items():
        if node_id == root_id or not _is_organisation(node):
            continue
        key = canonical_name_key(node.get("name"))
        if key:
            by_key.setdefault(key, []).append(node_id)

    report: dict[str, Any] = {
        "agencies": 0, "agencies_matched": 0, "agencies_matched_by_scoped_prefix": 0,
        "agencies_unmatched": [], "agencies_ambiguous": [],
        "organizations": len(groups), "organizations_of_agency": 0, "organizations_matched": 0,
        "organizations_under_unmatched_agency": 0, "organizations_unmatched": [], "organizations_ambiguous": [],
    }
    agency_names = sorted({agency for agency, _ in groups})
    report["agencies"] = len(agency_names)
    agency_candidates: dict[str, set[str]] = {}
    scoped_agencies: set[str] = set()
    for agency in agency_names:
        found: set[str] = set()
        for key in export_agency_keys(agency):
            found.update(by_key.get(key, []))
        if not found:
            scoped = split_scoped_agency(agency)
            if scoped:
                parents: set[str] = set()
                for key in organisation_name_keys(scoped[0]):
                    parents.update(by_key.get(key, []))
                if len(parents) == 1:
                    parent_id = next(iter(parents))
                    for key in organisation_name_keys(scoped[1]):
                        found.update(n for n in by_key.get(key, []) if parent_id in _ancestors_of(n, parent_map))
                    if found:
                        scoped_agencies.add(agency)
        agency_candidates[agency] = found
    claimed: Counter[str] = Counter()
    for found in agency_candidates.values():
        if len(found) == 1:
            claimed.update(found)
    agency_nodes: dict[str, str] = {}
    for agency, found in agency_candidates.items():
        if len(found) == 1 and claimed[next(iter(found))] == 1:
            agency_nodes[agency] = next(iter(found))
            report["agencies_matched"] += 1
            if agency in scoped_agencies:
                report["agencies_matched_by_scoped_prefix"] += 1
        elif len(found) > 1 or (found and claimed[next(iter(found))] > 1):
            report["agencies_ambiguous"].append({"name": agency, "nodes": sorted(found)})
        else:
            report["agencies_unmatched"].append(agency)

    group_candidates: dict[tuple[str, str], set[str]] = {}
    for agency, organization in groups:
        agency_node = agency_nodes.get(agency)
        if agency_node is None:
            report["organizations_under_unmatched_agency"] += 1
            continue
        org_keys = organisation_name_keys(unescape(organization))
        agency_keys = organisation_name_keys(agency_unit_name(agency)) | export_agency_keys(agency)
        if not org_keys or org_keys & agency_keys:
            group_candidates[(agency, organization)] = {agency_node}
            report["organizations_of_agency"] += 1
            continue
        found = set()
        for key in org_keys:
            found.update(n for n in by_key.get(key, []) if agency_node in _ancestors_of(n, parent_map))
        group_candidates[(agency, organization)] = found
    # Several groups may legitimately be the agency node itself -- the export
    # files the USPTO's rows under both "PATENT AND TRADEMARK OFFICE" and
    # "UNITED STATES PATENT AND TRADEMARK OFFICE" -- so those do not count
    # against each other; only groups naming a sub-unit must be one to one.
    of_agency = {group for group, found in group_candidates.items() if found == {agency_nodes[group[0]]}}
    claimed = Counter()
    for group, found in group_candidates.items():
        if len(found) == 1 and group not in of_agency:
            claimed.update(found)
    group_nodes: dict[tuple[str, str], str] = {}
    for group, found in group_candidates.items():
        if group in of_agency:
            group_nodes[group] = next(iter(found))
            report["organizations_matched"] += 1
        elif len(found) == 1 and claimed[next(iter(found))] == 1:
            group_nodes[group] = next(iter(found))
            report["organizations_matched"] += 1
        elif len(found) > 1 or (found and claimed[next(iter(found))] > 1):
            report["organizations_ambiguous"].append({"agency": group[0], "organization": group[1], "nodes": sorted(found)})
        else:
            report["organizations_unmatched"].append({"agency": group[0], "organization": group[1]})
    return agency_nodes, group_nodes, report


def _single_or_counts(counts: Counter[str]) -> tuple[str | None, dict[str, int] | None]:
    counts = Counter({k: v for k, v in counts.items() if k})
    if not counts:
        return None, None
    if len(counts) == 1:
        return next(iter(counts)), None
    return None, dict(counts.most_common())


def describe_listing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """What the export's folded rows for one title say, said once: each of
    status, appointment type, pay plan and the pay cell is a single value or
    null with its counts beside it, and a rate is published only where every
    row prints the same figure."""
    out: dict[str, Any] = {
        "rows": len(rows),
        "rowsListed": sum(int(r.get("rowsListed") or 1) for r in rows),
    }
    statuses: Counter[str] = Counter()
    types: Counter[str] = Counter()
    for r in rows:
        statuses.update(r.get("statusCounts") or {})
        types.update(r.get("appointmentTypeCounts") or {})
    status, status_counts = _single_or_counts(statuses)
    out["positionStatus"] = status
    if status_counts:
        out["positionStatusCounts"] = status_counts
    appointment, appointment_counts = _single_or_counts(types)
    out["appointmentType"] = appointment
    if appointment_counts:
        out["appointmentTypeCounts"] = appointment_counts
    for field in ("payPlan", "level"):
        value, counts = _single_or_counts(Counter(r[field] for r in rows))
        out[field] = value
        if counts:
            out[f"{field}Counts"] = counts
    level, pay, pay_text = split_level_grade_pay(out.get("level"))
    out["payLevel"] = level
    out["reportedPay"] = pay
    out["reportedPayText"] = pay_text
    out["payPlanAndLevelOnOneRow"] = bool(
        out.get("payPlan") and out.get("level")
        and any(r["payPlan"] == out["payPlan"] and r["level"] == out["level"] for r in rows)
    )
    return out


def match_positions(
    export: Mapping[str, Any],
    node_map: Mapping[str, dict[str, Any]],
    parent_map: Mapping[str, str | None],
    *,
    root_id: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Records keyed by position node id, and a report of every count and
    refusal. No record is written for a position the export lacks."""
    groups: Mapping[tuple[str, str], list[dict[str, Any]]] = export.get("groups") or {}
    agency_nodes, group_nodes, report = match_organisations(groups, node_map, parent_map, root_id=root_id)
    report = {"source": SOURCE, "url": export.get("url"), "fetched_at": export.get("fetched_at"),
              "sha256": export.get("sha256"), **summarize_export(export), **report}
    positions = {i: n for i, n in node_map.items() if _is_position(n)}
    matched_agency_ids = set(agency_nodes.values())
    node_groups = {node_id: group for group, node_id in group_nodes.items()}
    report.update({
        "positions_in_graph": len(positions),
        "positions_under_matched_agency_node": sum(1 for i in positions if parent_map.get(i) in matched_agency_ids),
        "positions_under_matched_organization": sum(1 for i in positions if parent_map.get(i) in node_groups),
        "positions_matched": 0,
        "positions_with_a_rate": 0,
        "positions_by_pay_plan": {},
        "positions_shared_title": [],
        "positions_ambiguous_alternatives": [],
        "positions_title_ambiguous_in_export": [],
        "positions_unmatched": 0,
        "positions_unmatched_sample": [],
        "unmatched_titles_top": [],
        "unmatched_agencies_top": [],
        "samples": [],
    })
    unmatched_titles: Counter[str] = Counter()
    records: dict[str, dict[str, Any]] = {}
    label = edition_label(export.get("fetched_at"))
    # Every group's rows, by the node the group reached: two groups that are
    # both the agency itself feed one index, so a title is looked up once.
    rows_by_org: dict[str, list[dict[str, Any]]] = {}
    for group, org_id in group_nodes.items():
        rows_by_org.setdefault(org_id, []).extend(groups[group])
    report["positions_title_in_several_groups"] = []
    for org_id, org_rows in sorted(rows_by_org.items()):
        org_node = node_map[org_id]
        children = [i for i in positions if parent_map.get(i) == org_id]
        if not children:
            continue
        titles: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for row in org_rows:
            for key in export_title_keys(row["title"], row["organization"]):
                titles.setdefault(key, {}).setdefault(row["title"], []).append(row)
        alternatives = {i: position_name_alternatives(positions[i].get("name"), org_node.get("name")) for i in children}
        shared = Counter(k for keys in alternatives.values() for k in keys)
        for node_id in sorted(children):
            keys = alternatives[node_id]
            if any(shared[k] > 1 for k in keys):
                report["positions_shared_title"].append({"id": node_id, "name": positions[node_id].get("name"), "organization": org_id})
                continue
            hits = [k for k in keys if k in titles]
            if not hits:
                report["positions_unmatched"] += 1
                unmatched_titles[str(positions[node_id].get("name") or "")] += 1
                if len(report["positions_unmatched_sample"]) < 40:
                    report["positions_unmatched_sample"].append({"id": node_id, "name": positions[node_id].get("name"), "listed_under": org_node.get("name")})
                continue
            if len(hits) > 1:
                report["positions_ambiguous_alternatives"].append({"id": node_id, "name": positions[node_id].get("name"), "titles": sorted(next(iter(titles[k])) for k in hits)})
                continue
            spellings = titles[hits[0]]
            if len(spellings) > 1:
                report["positions_title_ambiguous_in_export"].append({"id": node_id, "name": positions[node_id].get("name"), "titles": sorted(spellings)})
                continue
            listed_title, rows = next(iter(spellings.items()))
            # The rows of one title must all sit in one (Agency, Organization)
            # group: a title filed under both of the USPTO's two spellings of
            # itself would otherwise be published under one of them by chance.
            filings = {(r["agency"], r["organization"]) for r in rows}
            if len(filings) != 1:
                report["positions_title_in_several_groups"].append({"id": node_id, "name": positions[node_id].get("name"), "groups": sorted(filings)})
                continue
            agency, organization = next(iter(filings))
            agency_node_name = node_map[agency_nodes[agency]].get("name")
            record: dict[str, Any] = {
                "source": SOURCE,
                "method": METHOD,
                "edition": label,
                "listedTitle": listed_title,
                "agency": agency,
                "organization": organization,
                "agencyMatchedBy": "scoped_prefix" if split_scoped_agency(agency) and not (export_agency_keys(agency) & {canonical_name_key(agency_node_name)}) else "name",
                **describe_listing(rows),
                "exportFetchedAt": export.get("fetched_at"),
                "url": export.get("url"),
                "documentSha256": export.get("sha256"),
                "placement": {"status": STATUS_LISTED, "parentId": org_id, "parentListedName": organization},
            }
            if len(keys) > 1:
                record["matchedAlternative"] = hits[0]
            records[node_id] = record
            report["positions_matched"] += 1
            plan = str(record.get("payPlan") or "?")
            report["positions_by_pay_plan"][plan] = report["positions_by_pay_plan"].get(plan, 0) + 1
            if record.get("reportedPay") is not None:
                report["positions_with_a_rate"] += 1
            if len(report["samples"]) < 15:
                report["samples"].append({"id": node_id, "name": positions[node_id].get("name"), "listedTitle": listed_title,
                                          "positionStatus": record["positionStatus"], "payPlan": record["payPlan"]})
    report["unmatched_titles_top"] = unmatched_titles.most_common(25)
    live_by_agency: Counter[str] = Counter()
    for (agency, _), rows in groups.items():
        live_by_agency[agency] += sum(int(r.get("rowsListed") or 1) for r in rows)
    report["unmatched_agencies_top"] = [
        {"agency": a, "rows": live_by_agency[a]} for a in sorted(report["agencies_unmatched"], key=lambda a: -live_by_agency[a])[:30]
    ]
    return records, report


# --------------------------------------------------------------------------
# Pay records, in the shape financial_evidence.validate_record checks


def build_pay_records(records: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """One financial-evidence record per listing whose pay cell prints a rate.

    The caller validates each against its node. `scopeMatch` is `proxy` on
    every record: the export's row is an incumbency and its figure is what
    the one listing under this title is paid, not what the office pays.
    """
    out: dict[str, dict[str, Any]] = {}
    refusals: Counter[str] = Counter()
    for node_id, record in sorted(records.items()):
        pay = record.get("reportedPay")
        text = str(record.get("reportedPayText") or "")
        if pay is None:
            # A printed "$0.00" is a rate of zero: never published as a figure
            # (an uncompensated arrangement is a fact about one row, not about
            # the post), and named as its own refusal rather than "no rate".
            if text:
                refusals["rate_is_zero"] += 1
            elif record.get("levelCounts"):
                refusals["rows_print_different_figures"] += 1
            else:
                refusals["no_rate_printed"] += 1
            continue
        if not isinstance(pay, (int, float)) or isinstance(pay, bool) or float(pay) <= 0:
            refusals["rate_is_zero_or_not_a_number"] += 1
            continue
        fetched = str(record.get("exportFetchedAt") or "")[:10]
        try:
            as_of = date.fromisoformat(fetched)
        except ValueError:
            refusals["export_undated"] += 1
            continue
        digits = re.sub(r"[^0-9,]", "", text.split(".")[0])
        quote = (
            f"{record.get('listedTitle')}; {record.get('agency')}; {record.get('organization')}; "
            f"Pay Plan {record.get('payPlan') or ''}; Level, Grade, or Pay {text}; "
            f"Position Status {record.get('positionStatus') or ', '.join(sorted((record.get('positionStatusCounts') or {}).keys()))}"
        )
        out[node_id] = {
            "nodeId": node_id,
            "financialEvidenceStatus": "partial",
            "costBasis": "basic_pay",
            "amount": float(pay),
            "amountRaw": digits,
            "units": "usd",
            "normalizedMultiplier": 1,
            "unitsEvidence": quote,
            "quote": quote,
            "fiscalYear": federal_fiscal_year_of(as_of),
            "periodCoverage": "annual_rate",
            "periodAsOf": as_of.isoformat(),
            "amountScope": str(record.get("listedTitle") or ""),
            "scopeMatch": "proxy",
            "rollupRole": "line",
            "sourceType": PAY_SOURCE_TYPE,
            "sourceUrl": str(record.get("url") or ""),
            "documentSha256": str(record.get("documentSha256") or ""),
            "retrievedAt": str(record.get("exportFetchedAt") or ""),
            "locator": {
                "table": "PLUM Reporting export (download-data)",
                "row": f"{record.get('agency')} / {record.get('organization')} / {record.get('listedTitle')}",
                "column": "Level, Grade, or Pay",
            },
            "listedTitle": record.get("listedTitle"),
            "agency": record.get("agency"),
            "organization": record.get("organization"),
            "payPlan": record.get("payPlan"),
            "positionStatus": record.get("positionStatus"),
            "rateText": text,
        }
    return out, {"priced": len(out), "refused": dict(sorted(refusals.items()))}


# --------------------------------------------------------------------------
# Loading and applying


def load_evidence(path: str | Path | None = DEFAULT_EVIDENCE_PATH) -> dict[str, Any]:
    """{"nodes": listings by node id, "pay": validated pay records by node id},
    or empty. A missing file is not an error."""
    empty: dict[str, Any] = {"nodes": {}, "pay": {}}
    if path is None:
        return empty
    try:
        loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty
    if not isinstance(loaded, dict):
        return empty
    nodes = loaded.get("nodes") if isinstance(loaded.get("nodes"), dict) else {}
    pay = loaded.get("pay") if isinstance(loaded.get("pay"), dict) else {}
    return {
        "nodes": {str(k): v for k, v in nodes.items() if isinstance(v, dict)},
        "pay": {str(k): v for k, v in pay.items() if isinstance(v, dict)},
    }


def load_current_listings(path: str | Path | None = DEFAULT_EVIDENCE_PATH) -> dict[str, dict[str, Any]]:
    return load_evidence(path)["nodes"]


def listed_title_still_names(node_name: Any, parent_names: Any, listed_title: Any) -> bool:
    """The archive's rename guard, with the export's entities resolved first."""
    from data_pipeline.verification.positions import listed_title_still_names as _archive_rule

    names = [parent_names] if parent_names is None or isinstance(parent_names, str) else list(parent_names)
    return _archive_rule(node_name, [unescape(n) if n else n for n in names], unescape(listed_title))


def apply_current_listing(
    root: dict[str, Any],
    records: Mapping[str, Mapping[str, Any]],
    *,
    index_tree: Any = None,
) -> dict[str, Any]:
    """Stamp the export's listing onto the position nodes it names.

    Beside any other claim and never over it: `positionCurrentListing`
    always; the export's URL in `sourceUrls`/`evidenceUrls` with
    `sourceTypes: opm_plum_current_export`; `verificationMethod` only where
    none exists; placement only when the organisation the export files the
    title under is the node's parent in the published tree and nothing has
    already verified the edge.
    """
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, parent_map = index_tree(root)
    stats = {"listed": 0, "unknown_node": 0, "not_a_position": 0, "stale_name": 0, "undated": 0,
             "placements_listed": 0, "placements_stale_parent": 0, "urls_added": 0, "with_a_rate": 0}
    for node_id, record in records.items():
        node = node_map.get(node_id)
        if node is None:
            stats["unknown_node"] += 1
            continue
        if not _is_position(node):
            stats["not_a_position"] += 1
            continue
        url = str(record.get("url") or "").strip()
        fetched = str(record.get("exportFetchedAt") or "").strip()
        digest = str(record.get("documentSha256") or "").strip().lower()
        if record.get("source") != SOURCE or not url or not fetched or not re.fullmatch(r"[0-9a-f]{64}", digest):
            stats["undated"] += 1
            continue
        placement = record.get("placement") if isinstance(record.get("placement"), dict) else None
        parent = node_map.get(str(parent_map.get(node_id) or ""))
        recorded_parent = node_map.get(str((placement or {}).get("parentId") or ""))
        parent_names = [(parent or {}).get("name"), (recorded_parent or {}).get("name"), record.get("organization")]
        if not listed_title_still_names(node.get("name"), parent_names, record.get("listedTitle")):
            stats["stale_name"] += 1
            continue
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
        if SOURCE_TYPE not in types:
            types.append(SOURCE_TYPE)
        node["sourceTypes"] = types
        block: dict[str, Any] = {
            "source": SOURCE,
            "method": METHOD,
            "edition": record.get("edition") or edition_label(fetched),
            "listedTitle": record.get("listedTitle"),
            "agency": record.get("agency"),
            "organization": record.get("organization"),
            "positionStatus": record.get("positionStatus"),
            "appointmentType": record.get("appointmentType"),
            "payPlan": record.get("payPlan"),
            "level": record.get("level"),
            "payLevel": record.get("payLevel"),
            "reportedPay": record.get("reportedPay"),
            "reportedPayText": record.get("reportedPayText"),
            "payPlanAndLevelOnOneRow": bool(record.get("payPlanAndLevelOnOneRow")),
            "rows": record.get("rows"),
            "rowsListed": record.get("rowsListed"),
            "exportFetchedAt": fetched,
            # The generic listing tie pay_tables/gs_pay read: the date the
            # document was obtained, the same thing positionListing.checkedAt is.
            "checkedAt": fetched,
            "url": url,
            "documentSha256": digest,
        }
        for field in ("positionStatusCounts", "appointmentTypeCounts", "payPlanCounts", "levelCounts"):
            if record.get(field):
                block[field] = record[field]
        node["positionCurrentListing"] = block
        if not node.get("lastVerified") or fetched > str(node.get("lastVerified")):
            node["lastVerified"] = fetched
            node["evidenceVerifiedAt"] = fetched
        if not node.get("verificationMethod"):
            node["verificationMethod"] = METHOD
        stats["listed"] += 1
        if record.get("reportedPay") is not None:
            stats["with_a_rate"] += 1
        if placement and placement.get("status") == STATUS_LISTED:
            if str(placement.get("parentId") or "") != str(parent_map.get(node_id) or ""):
                stats["placements_stale_parent"] += 1
            elif node.get("placementVerified") is not True:
                node["placementVerified"] = True
                node["placementUrl"] = url
                node["placementVerifiedAt"] = fetched
                node["placementParentId"] = parent_map.get(node_id)
                node["placementMatchedText"] = record.get("listedTitle")
                node["placementMethod"] = PLACEMENT_METHOD
                node.pop("placementCheckable", None)
                stats["placements_listed"] += 1
        verify_node_sources(node)
    return stats


def apply_current_pay(
    root: dict[str, Any],
    records: Mapping[str, Mapping[str, Any]],
    *,
    index_tree: Any = None,
) -> dict[str, Any]:
    """Stamp `positionCurrentPay` where the published current listing still
    reports the very figure the record carries.

    A record is refused on an unknown node, a non-post, a node standing for
    several posts, a node with no current listing, a listing whose figure or
    printed text differs, a zero, and a record that never went through
    `financial_evidence.validate_record` (no `unitsEvidenceKind`).
    """
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, _ = index_tree(root)
    stats = {"priced": 0, "unknown_node": 0, "not_a_position": 0, "stands_for_many_posts": 0,
             "no_listing_published": 0, "listing_reports_a_different_figure": 0, "zero_refused": 0,
             "not_validated": 0}
    for node_id, record in sorted(records.items()):
        node = node_map.get(node_id)
        if node is None:
            stats["unknown_node"] += 1
            continue
        if not _is_position(node):
            stats["not_a_position"] += 1
            continue
        if node.get("representsPosts"):
            stats["stands_for_many_posts"] += 1
            continue
        listing = node.get("positionCurrentListing")
        if not isinstance(listing, Mapping):
            stats["no_listing_published"] += 1
            continue
        amount = record.get("amount")
        if not isinstance(amount, (int, float)) or isinstance(amount, bool) or float(amount) <= 0:
            stats["zero_refused"] += 1
            continue
        if listing.get("reportedPay") != amount or str(listing.get("reportedPayText") or "") != str(record.get("rateText") or ""):
            stats["listing_reports_a_different_figure"] += 1
            continue
        if not str(record.get("unitsEvidenceKind") or ""):
            stats["not_validated"] += 1
            continue
        node["positionCurrentPay"] = {
            "source": PAY_SOURCE,
            "sourceLabel": "OPM's current PLUM Reporting export",
            "method": PAY_METHOD,
            "amount": float(amount),
            "rateText": record.get("rateText"),
            "payPlan": record.get("payPlan"),
            "listedTitle": record.get("listedTitle"),
            "agency": record.get("agency"),
            "organization": record.get("organization"),
            "positionStatus": record.get("positionStatus"),
            "costBasis": record.get("costBasis"),
            "scopeMatch": record.get("scopeMatch"),
            "financialEvidenceStatus": record.get("financialEvidenceStatus"),
            "amountScope": record.get("amountScope"),
            "quote": record.get("quote"),
            "unitsEvidenceKind": record.get("unitsEvidenceKind"),
            "exportFetchedAt": record.get("retrievedAt"),
            "url": str(record.get("sourceUrl") or ""),
            "documentSha256": record.get("documentSha256"),
            "checkedAt": record.get("retrievedAt"),
        }
        stats["priced"] += 1
        # Deliberately NOT written: sourceUrls, evidenceUrls, sourceTypes,
        # lastVerified, verificationMethod. The listing above already carries
        # the document as a source of the post's existence; the rate is a
        # second claim from the same row and must not count a second time.
    return stats


# --------------------------------------------------------------------------
# Listings for the pay-table joins (pay_tables.py, gs_pay.py)


def listing_claim_from_current(record: Mapping[str, Any]) -> dict[str, Any]:
    """A current-export record in the shape the pay-table deriver reads a
    listing in: the fields `pay_tables.level_claim` / `gs_pay.listing_claim`
    take, with `source` naming this document."""
    return {
        "source": SOURCE,
        "edition": record.get("edition") or edition_label(record.get("exportFetchedAt")),
        "period": None,
        "listedTitle": record.get("listedTitle"),
        "payPlan": record.get("payPlan"),
        "payLevel": record.get("payLevel"),
        "reportedPay": record.get("reportedPay"),
        "reportedPayText": record.get("reportedPayText"),
        "payPlanAndLevelOnOneRow": bool(record.get("payPlanAndLevelOnOneRow")),
        "url": record.get("url"),
        "checkedAt": record.get("exportFetchedAt"),
        "valuesFrom": "current_export",
    }


def combine_listings(
    archive: Mapping[str, Mapping[str, Any]],
    current: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    """One listing per node for the salary-table joins: the current export's
    where it lists the post, else the archive's.

    The current export is the present and the archive is a period that
    ended, so where both list a post the current listing supplies the pay
    plan and level. A rate stated by EITHER listing marks the chosen one
    `anyListingReportsRate`, which both derivers refuse: a table rate or
    range beside a stated rate is two figures for one post.
    """
    out: dict[str, dict[str, Any]] = {}
    stats = {"from_current": 0, "from_archive": 0, "either_reports_a_rate": 0}
    for node_id in sorted(set(archive) | set(current)):
        archive_listing = archive.get(node_id)
        current_listing = current.get(node_id)
        if current_listing is not None:
            chosen = listing_claim_from_current(current_listing)
            stats["from_current"] += 1
        else:
            chosen = dict(archive_listing or {})
            stats["from_archive"] += 1
        rate_stated = any(
            isinstance(l, Mapping) and l.get("reportedPay") is not None for l in (archive_listing, current_listing)
        )
        if rate_stated:
            chosen["anyListingReportsRate"] = True
            stats["either_reports_a_rate"] += 1
        out[node_id] = chosen
    return out, stats
