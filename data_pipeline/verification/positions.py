"""Evidence for the graph's position nodes from OPM's PLUM archive.

The Office of Personnel Management's PLUM Reporting programme (the
machine-readable successor of the printed Plum Book) lists the executive
branch's policy and supporting positions by agency and organisation, with
each position's title, status, appointment type and pay plan. The current
export (reported "as of June 15, 2026") is served by escs.opm.gov, which
this environment's proxy refuses; what www.opm.gov itself serves — and what
is committed here, verbatim, in tests/fixtures/opm/plum/ — is the **archive
of the previous administration's reported positions**, the file the PLUM
Archive page labels "Biden Administration (January 21, 2021 - January 20,
2025)". Every record derived from it says so: `edition` carries that label
as the page states it, `checkedAt` the file's fetch time. Nothing here is a
claim about the present.

What a record says is exactly what the archive says: for a position node
whose parent organisation answers to one (AgencyName, OrganizationName)
group of the archive, the archive lists a position of this title in that
organisation, with the status, appointment type, pay plan and level it
gives. A row of the archive is an incumbency, not a position — the same
title recurs once per holder, past holders carrying an IncumbentVacateDate
— so a record counts the incumbencies, reads `status` off the standing rows
(those with no vacate date) and publishes null, with the counts, wherever
the rows disagree.

No negative records. The archive is neither current nor complete for
career positions: a position absent from it is not evidence of anything.

Matching, in the project's convention (directories.py): the canonical name
key, one name to one node or nothing, nothing fuzzy.

- AgencyName to an organisation node of the curated graph, tolerating only
  "department of X" <-> "department of the X" and the upper case (the key
  folds case).
- OrganizationName, when it names something other than the agency, to a
  node beneath the matched agency node — scoped the way directories.py
  scopes a qualified entry — so the same-named offices of different
  departments stay apart.
- A position node's name to the group's PositionTitle values, after these
  and only these normalisations: a trailing ", <parent organisation name or
  acronym>" qualifier is stripped ("Administrator, NASA"); "A / B / C" is
  split into alternatives and any may match ("Director / Administrator /
  Chair"); a leading "the" is tolerated (the key already drops it). Never
  across organisations. A title several graph positions under the same
  organisation share matches nothing, as does a name whose alternatives
  answer to two listed titles, or a listed title that several distinct
  archive spellings collapse onto.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from data_pipeline.exporter.build_graph import canonical_name_key
from data_pipeline.processors.normalize_nodes import verify_node_sources

PLUM_SOURCE = "opm_plum_archive"
PLUM_METHOD = "listed_in_opm_plum_archive"
PLUM_PLACEMENT_METHOD = "listed_under_organization_in_opm_plum_archive"
PLUM_SOURCE_TYPE = "opm_plum_archive"
STATUS_LISTED = "listed"
DEFAULT_EDITION = "Biden administration archive"

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "opm" / "plum"
DEFAULT_ARCHIVE_CSV = FIXTURE_DIR / "plum-archive-biden-administration.csv"
DEFAULT_ARCHIVE_PAGE = FIXTURE_DIR / "opm_plum_archive_page.html"
DEFAULT_POSITION_EVIDENCE_PATH = Path(__file__).resolve().parents[2] / "data" / "verification" / "position_evidence.json"

# The archive's columns this module reads, and the field each becomes.
ROW_FIELDS = {
    "AgencyName": "agency",
    "OrganizationName": "organization",
    "PositionTitle": "title",
    "PositionStatus": "status",
    "AppointmentTypeDescription": "appointmentType",
    "PaymentPlanDescription": "payPlan",
    "LevelGradePay": "level",
}
LISTING_FIELDS = ("appointmentType", "payPlan", "level")

_PARENTHETICAL = re.compile(r"\(([^)]*)\)")
_SLASH_ALTERNATIVES = re.compile(r"\s+/\s+")


# --------------------------------------------------------------------------
# Reading the archive


def load_plum_archive(csv_path: str | Path = DEFAULT_ARCHIVE_CSV) -> dict[str, Any]:
    """The archive as served, grouped by (AgencyName, OrganizationName).

    Returns {"url", "fetched_at", "file", "rows", "groups"}; the URL and the
    fetch time come from the sibling .meta.json the fixture fetch wrote, and
    without one no record can carry a date. Values are stripped of the
    whitespace the file pads some of them with ("$225,700 "); nothing else
    is rewritten — an HTML entity the file carries ("&amp;") stays as served.
    """
    path = Path(csv_path)
    meta_path = path.with_name(path.name + ".meta.json")
    meta: dict[str, Any] = {}
    if meta_path.exists():
        try:
            loaded = json.loads(meta_path.read_text(encoding="utf-8"))
            meta = loaded if isinstance(loaded, dict) else {}
        except (OSError, json.JSONDecodeError):
            meta = {}
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            row = {field: str(raw.get(column) or "").strip() for column, field in ROW_FIELDS.items()}
            if not row["agency"] or not row["title"]:
                continue
            # A row with a vacate date is a past incumbency; one without is
            # the position's listing as it stood when the archive closed.
            row["vacated"] = bool(str(raw.get("IncumbentVacateDate") or "").strip())
            rows.append(row)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault((row["agency"], row["organization"]), []).append(row)
    return {
        "url": meta.get("final_url") or meta.get("url") or None,
        "fetched_at": meta.get("fetched_at") or None,
        "file": path.name,
        "rows": rows,
        "groups": groups,
    }


def summarize_archive(archive: dict[str, Any]) -> dict[str, Any]:
    rows = archive.get("rows") or []
    return {
        "rows": len(rows),
        "agencies": len({r["agency"] for r in rows}),
        "organizations": len(archive.get("groups") or {}),
        "organization_names": len({r["organization"] for r in rows}),
        "titles": len({r["title"] for r in rows}),
        "appointment_types": dict(Counter(r["appointmentType"] for r in rows).most_common()),
        "position_status": dict(Counter(r["status"] for r in rows).most_common()),
    }


def read_archive_edition(page_path: str | Path | None, csv_name: str) -> dict[str, Any] | None:
    """What the saved PLUM Archive page says the file is: the link's text and
    the period printed after it — `Biden Administration (January 21, 2021 -
    January 20, 2025)` — read off the one <li> whose link ends in the CSV's
    name. None when the page is absent or does not link the file; the
    caller then falls back to DEFAULT_EDITION, which claims no dates."""
    if page_path is None:
        return None
    path = Path(page_path)
    if not path.exists():
        return None
    try:
        html = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    pattern = re.compile(
        r"<a\b[^>]*href=\"[^\"]*" + re.escape(csv_name) + r"\"[^>]*>(?P<text>[^<]*)</a>\s*(?P<tail>\([^)]*\))?",
        re.IGNORECASE,
    )
    match = pattern.search(html)
    if not match:
        return None
    label = " ".join(match.group("text").split())
    tail = match.group("tail")
    period = " ".join(tail.strip("()").split()) if tail else None
    edition: dict[str, Any] = {"label": label, "period": period, "edition": f"{label} ({period})" if period else label}
    if period:
        start, end = _parse_period(period)
        if start and end:
            edition["periodStart"], edition["periodEnd"] = start, end
    return edition


def _parse_period(period: str) -> tuple[str | None, str | None]:
    parts = [p.strip() for p in re.split(r"\s[-–—]\s", period) if p.strip()]
    if len(parts) != 2:
        return None, None
    out: list[str | None] = []
    for part in parts:
        try:
            out.append(datetime.strptime(part, "%B %d, %Y").date().isoformat())
        except ValueError:
            out.append(None)
    return out[0], out[1]


# --------------------------------------------------------------------------
# Name keys


def organisation_name_keys(name: Any) -> set[str]:
    """The keys an archive agency or organisation name answers to: the
    canonical key, and the same with "department of the X" written as
    "department of X" (the archive prints DEPARTMENT OF THE TREASURY; a
    curated file may not) or the reverse. Nothing else."""
    key = canonical_name_key(name)
    if not key:
        return set()
    keys = {key}
    if key.startswith("department of the "):
        keys.add("department of " + key[len("department of the "):])
    elif key.startswith("department of "):
        keys.add("department of the " + key[len("department of "):])
    return keys


def parent_qualifier_keys(parent_name: Any) -> set[str]:
    """The keys a trailing qualifier may carry to be the parent: the parent's
    name (with the department tolerance) or the acronym its curated name
    gives in parentheses — "Department of Energy (DOE)" answers to DOE."""
    keys = organisation_name_keys(parent_name)
    for match in _PARENTHETICAL.finditer(str(parent_name or "")):
        inner = canonical_name_key(match.group(1))
        if inner:
            keys.add(inner)
    return keys


def strip_parent_qualifier(name: Any, parent_name: Any) -> tuple[str, str | None]:
    """"Administrator, NASA" under NASA is "Administrator"; "Chair,
    Agriculture, Nutrition, and Forestry" under a committee of another name
    is left whole. The tail after a comma is a qualifier only when it is
    the parent's own name or acronym; the earliest such comma wins."""
    text = str(name or "").strip()
    if "," not in text:
        return text, None
    qualifiers = parent_qualifier_keys(parent_name)
    for index, char in enumerate(text):
        if char != ",":
            continue
        core, tail = text[:index].strip(), text[index + 1:].strip()
        if core and tail and canonical_name_key(tail) in qualifiers:
            return core, tail
    return text, None


def archive_title_keys(title: Any, organisation_name: Any) -> list[str]:
    """The keys an archive title answers to: its own, and — when the tail
    after a comma is the organisation the archive already files the row
    under — the key of what is left.

    The archive prints "COMMISSIONER, UNITED STATES CUSTOMS AND BORDER
    PROTECTION" as a row of the organisation U.S. Customs and Border
    Protection, and "DEPUTY DIRECTOR, CYBERSECURITY AND INFRASTRUCTURE
    SECURITY AGENCY" as a row of CISA. That tail is the same redundancy
    `strip_parent_qualifier` already removes from the curated side of the
    comparison ("Administrator, NASA" under NASA); removing it from this
    side is not a guess about which post is meant but the archive's own
    filing read back. Nothing else is stripped: "CHIEF COUNSEL FOR
    CYBERSECURITY AND INFRASTRUCTURE SECURITY AGENCY" has no comma and is
    left whole, and "CHIEF (EXECUTIVE ASSISTANT COMMISSIONER), UNITED
    STATES BORDER PATROL" keeps a core no curated name answers to rather
    than being talked into one.

    Both keys are returned, so a title that matched before still matches;
    the caller indexes the row under each and its existing refusals decide
    what a collision means.
    """
    keys: list[str] = []
    for text in (title, strip_parent_qualifier(title, organisation_name)[0]):
        key = canonical_name_key(text)
        if key and key not in keys:
            keys.append(key)
    return keys


def position_name_alternatives(name: Any, parent_name: Any) -> list[str]:
    """The canonical keys a curated position name may answer to, after the
    qualifier is stripped and "A / B / C" is split; the key already drops a
    leading "the". Order is the name's; duplicates and empties are dropped."""
    core, _ = strip_parent_qualifier(name, parent_name)
    keys: list[str] = []
    for part in _SLASH_ALTERNATIVES.split(core):
        key = canonical_name_key(part)
        if key and key not in keys:
            keys.append(key)
    return keys


# --------------------------------------------------------------------------
# Matching


def _is_position(node: dict[str, Any]) -> bool:
    return "position" in str(node.get("type") or "").casefold()


def _is_organisation(node: dict[str, Any]) -> bool:
    return not _is_position(node) and not node.get("synthetic")


def _ancestors_of(node_id: str, parent_map: dict[str, str | None]) -> list[str]:
    chain: list[str] = []
    current = parent_map.get(node_id)
    while current:
        chain.append(current)
        current = parent_map.get(current)
    return chain


def match_organisations(
    groups: dict[tuple[str, str], list[dict[str, Any]]],
    node_map: dict[str, dict[str, Any]],
    parent_map: dict[str, str | None],
    *,
    root_id: str,
) -> tuple[dict[str, str], dict[tuple[str, str], str], dict[str, Any]]:
    """AgencyName -> node id, (AgencyName, OrganizationName) -> node id, and
    a report. An agency name that answers to several nodes, a node that
    answers to several agency names, and the same for groups, match nothing."""
    by_key: dict[str, list[str]] = {}
    for node_id, node in node_map.items():
        if node_id == root_id or not _is_organisation(node):
            continue
        key = canonical_name_key(node.get("name"))
        if key:
            by_key.setdefault(key, []).append(node_id)

    report: dict[str, Any] = {
        "agencies": 0, "agencies_matched": 0, "agencies_unmatched": [], "agencies_ambiguous": [],
        "organizations": len(groups), "organizations_of_agency": 0, "organizations_matched": 0,
        "organizations_under_unmatched_agency": 0, "organizations_unmatched": [], "organizations_ambiguous": [],
    }

    agency_names = sorted({agency for agency, _ in groups})
    report["agencies"] = len(agency_names)
    agency_candidates: dict[str, set[str]] = {}
    for agency in agency_names:
        found: set[str] = set()
        for key in organisation_name_keys(agency):
            found.update(by_key.get(key, []))
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
        org_keys = organisation_name_keys(organization)
        if not org_keys or org_keys & organisation_name_keys(agency):
            # The organisation is the agency itself (or unnamed): the group
            # is the agency node's own.
            group_candidates[(agency, organization)] = {agency_node}
            report["organizations_of_agency"] += 1
            continue
        found = set()
        for key in org_keys:
            found.update(n for n in by_key.get(key, []) if agency_node in _ancestors_of(n, parent_map))
        group_candidates[(agency, organization)] = found
    claimed = Counter()
    for found in group_candidates.values():
        if len(found) == 1:
            claimed.update(found)
    group_nodes: dict[tuple[str, str], str] = {}
    for group, found in group_candidates.items():
        if len(found) == 1 and claimed[next(iter(found))] == 1:
            group_nodes[group] = next(iter(found))
            report["organizations_matched"] += 1
        elif len(found) > 1 or (found and claimed[next(iter(found))] > 1):
            report["organizations_ambiguous"].append({"agency": group[0], "organization": group[1], "nodes": sorted(found)})
        else:
            report["organizations_unmatched"].append({"agency": group[0], "organization": group[1]})
    return agency_nodes, group_nodes, report


def _single_or_counts(values: list[str]) -> tuple[str | None, dict[str, int] | None]:
    counts = Counter(v for v in values if v)
    if not counts:
        return None, None
    if len(counts) == 1:
        return next(iter(counts)), None
    return None, dict(counts.most_common())


_LISTED_RATE = re.compile(r"^\s*\$\s*([0-9][0-9,]*)(?:\.\d{2})?\s*$")


def split_level_grade_pay(value: Any) -> tuple[str | None, float | None, str | None]:
    """The archive's LevelGradePay column holds two different kinds of thing.

    For an Executive Schedule row it is a level ("IV"), for a General
    Schedule row a grade ("15"), and for 983 rows a rate of basic pay
    ("$225,700 "). A dollar amount published under a heading that reads
    "Level" is the wrong claim about the right number, so the two are split
    here: the rank as printed, and the rate as a number beside the text the
    archive actually shows. Anything that is not unambiguously a dollar
    figure stays a rank — nothing is inferred from the pay plan, which the
    panel prints separately.

    Returns (payLevel, reportedPay, reportedPayText).
    """
    text = str(value or "").strip()
    if not text:
        return None, None, None
    match = _LISTED_RATE.match(text)
    if not match:
        return text, None, None
    try:
        amount = float(match.group(1).replace(",", ""))
    except ValueError:
        return text, None, None
    return None, (amount if amount > 0 else None), text


def describe_listing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """What the archive's rows for one title say, said once: status off the
    standing rows (no vacate date); appointment type, pay plan and level off
    the standing rows when there are any, else off every incumbency; each
    null, with its counts beside it, wherever the rows disagree."""
    standing = [r for r in rows if not r["vacated"]]
    out: dict[str, Any] = {"incumbencies": len(rows), "standing": len(standing)}
    status, status_counts = _single_or_counts([r["status"] for r in standing])
    out["status"] = status
    if status_counts:
        out["statusCounts"] = status_counts
    basis = standing or rows
    out["valuesFrom"] = "standing_listings" if standing else "past_incumbencies"
    for field in LISTING_FIELDS:
        value, counts = _single_or_counts([r[field] for r in basis])
        out[field] = value
        if counts:
            out[f"{field}Counts"] = counts
    # Only when the rows agree on one value: a title whose incumbencies were
    # paid differently has no one rate, and `levelCounts` beside it already
    # says the rows disagreed.
    level, pay, pay_text = split_level_grade_pay(out.get("level"))
    out["payLevel"] = level
    out["reportedPay"] = pay
    out["reportedPayText"] = pay_text
    # Each field above is aggregated on its own, and `_single_or_counts`
    # ignores blanks — so a title whose rows are (payPlan EX, no level) and
    # (no payPlan, level IV) reports EX and IV although no single row says a
    # post on the Executive Schedule sits at level IV. Nothing may price a
    # rank off a pair the archive never printed together, so the pair is
    # recorded rather than inferred. No title in the committed archive is
    # currently in that position; the field exists so that a later archive
    # cannot introduce one silently.
    out["payPlanAndLevelOnOneRow"] = bool(
        out.get("payPlan") and out.get("level")
        and any(r["payPlan"] == out["payPlan"] and r["level"] == out["level"] for r in basis)
    )
    return out


def match_positions(
    archive: dict[str, Any],
    node_map: dict[str, dict[str, Any]],
    parent_map: dict[str, str | None],
    *,
    root_id: str,
    edition: dict[str, Any] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Records keyed by position node id, and a report of every count and
    refusal. No record is written for a position the archive lacks."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = archive.get("groups") or {}
    agency_nodes, group_nodes, report = match_organisations(groups, node_map, parent_map, root_id=root_id)
    report = {"source": PLUM_SOURCE, "url": archive.get("url"), "fetched_at": archive.get("fetched_at"),
              "edition": (edition or {}).get("edition") or DEFAULT_EDITION, "period": (edition or {}).get("period"),
              **summarize_archive(archive), **report}

    positions = {i: n for i, n in node_map.items() if _is_position(n)}
    matched_agency_ids = set(agency_nodes.values())
    node_groups: dict[str, tuple[str, str]] = {node_id: group for group, node_id in group_nodes.items()}
    report.update({
        "positions_in_graph": len(positions),
        "positions_under_matched_agency_node": sum(1 for i in positions if parent_map.get(i) in matched_agency_ids),
        "positions_under_matched_organization": sum(1 for i in positions if parent_map.get(i) in node_groups),
        "positions_matched": 0,
        "positions_shared_title": [],
        "positions_ambiguous_alternatives": [],
        "positions_title_ambiguous_in_archive": [],
        "positions_unmatched": 0,
        "positions_unmatched_sample": [],
        "samples": [],
    })

    records: dict[str, dict[str, Any]] = {}
    edition_label = report["edition"]
    for group, org_id in sorted(group_nodes.items(), key=lambda kv: kv[1]):
        agency, organization = group
        org_node = node_map[org_id]
        children = [i for i in positions if parent_map.get(i) == org_id]
        if not children:
            continue
        # The archive's titles in this group, by key; a key that several
        # distinct spellings collapse onto identifies none of them.
        titles: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for row in groups[group]:
            for key in archive_title_keys(row["title"], organization):
                titles.setdefault(key, {}).setdefault(row["title"], []).append(row)
        # The graph's names, by key; a key two siblings share names neither.
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
                if len(report["positions_unmatched_sample"]) < 40:
                    report["positions_unmatched_sample"].append({"id": node_id, "name": positions[node_id].get("name"), "listed_under": organization})
                continue
            if len(hits) > 1:
                report["positions_ambiguous_alternatives"].append({"id": node_id, "name": positions[node_id].get("name"), "titles": sorted(next(iter(titles[k])) for k in hits)})
                continue
            key = hits[0]
            spellings = titles[key]
            if len(spellings) > 1:
                report["positions_title_ambiguous_in_archive"].append({"id": node_id, "name": positions[node_id].get("name"), "titles": sorted(spellings)})
                continue
            listed_title, rows = next(iter(spellings.items()))
            record: dict[str, Any] = {
                "source": PLUM_SOURCE,
                "edition": edition_label,
                "listedTitle": listed_title,
                "listedAgency": agency,
                "listedOrganization": organization,
                **describe_listing(rows),
                "url": archive.get("url"),
                "checkedAt": archive.get("fetched_at"),
                "placement": {"status": STATUS_LISTED, "parentId": org_id, "parentListedName": organization},
            }
            if edition and edition.get("period"):
                record["period"] = edition["period"]
                if edition.get("periodStart") and edition.get("periodEnd"):
                    record["periodStart"], record["periodEnd"] = edition["periodStart"], edition["periodEnd"]
            if len(keys) > 1:
                record["matchedAlternative"] = key
            records[node_id] = record
            report["positions_matched"] += 1
            if len(report["samples"]) < 15:
                report["samples"].append({"id": node_id, "name": positions[node_id].get("name"), "listedTitle": listed_title,
                                          "appointmentType": record["appointmentType"], "status": record["status"]})
    return records, report


# --------------------------------------------------------------------------
# Applying (the proposal for the exporter; not wired here)


def load_position_evidence(path: str | Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict) or not isinstance(payload.get("nodes"), dict):
        return {}
    return {str(k): v for k, v in payload["nodes"].items() if isinstance(v, dict)}


def listed_title_still_names(node_name: Any, parent_names: Any, listed_title: Any) -> bool:
    """A rename in the curated file must not inherit a listing made for the
    old name: the title must still be one the name answers to.

    The test is the *name's*, so it is made against every name the position's
    organisation has answered to — the parent the tree gives the node now,
    the parent the record was made under, and the archive's own spelling of
    it — because the trailing qualifier a curated position name carries
    ("Administrator, NASA") names that organisation, and only the curated
    spelling carries the acronym. A re-parenting is the placement's
    business, not the name's: evidence.py draws the same line between
    `existence_stale_name` and `placements_stale_parent`. Judged against the
    new parent alone, a move would be charged to the name check for a name
    that never changed — and only for the names that happen to carry a
    qualifier, which is no rule at all.
    """
    names = [parent_names] if parent_names is None or isinstance(parent_names, str) else list(parent_names)
    names = names or [None]
    keys = {k for name in names for k in archive_title_keys(listed_title, name)}
    if not keys:
        return False
    return any(k in position_name_alternatives(node_name, name) for name in names for k in keys)


def apply_position_evidence(
    root: dict[str, Any],
    records: dict[str, dict[str, Any]],
    *,
    index_tree=None,
) -> dict[str, Any]:
    """Stamp the archive's listing onto the position nodes it names.

    Intended to run after apply_directory_evidence, beside any other claim
    and never over it: `positionListing` always; the archive's URL added to
    `sourceUrls`/`evidenceUrls` with `sourceTypes: opm_plum_archive`;
    `verificationMethod: listed_in_opm_plum_archive` only where no method
    exists; placement only when the organisation the archive files the
    title under is the node's parent in the published tree and nothing has
    already verified the edge. Withdrawal is the page module's, so
    `positionListing` must join EVIDENCE_OWNED_FIELDS and the two methods the
    gate's allowlists before this is wired — the parent session's change.
    """
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, parent_map = index_tree(root)
    stats = {"listed": 0, "unknown_node": 0, "not_a_position": 0, "stale_name": 0, "placements_listed": 0,
             "placements_stale_parent": 0, "urls_added": 0, "undated": 0}
    for node_id, record in records.items():
        node = node_map.get(node_id)
        if node is None:
            stats["unknown_node"] += 1
            continue
        if not _is_position(node):
            stats["not_a_position"] += 1
            continue
        url = str(record.get("url") or "").strip()
        checked_at = str(record.get("checkedAt") or "").strip()
        if record.get("source") != PLUM_SOURCE or not url or not checked_at:
            stats["undated"] += 1
            continue
        placement = record.get("placement") if isinstance(record.get("placement"), dict) else None
        parent = node_map.get(str(parent_map.get(node_id) or ""))
        recorded_parent = node_map.get(str((placement or {}).get("parentId") or ""))
        parent_names = [(parent or {}).get("name"), (recorded_parent or {}).get("name"), record.get("listedOrganization")]
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
        if PLUM_SOURCE_TYPE not in types:
            types.append(PLUM_SOURCE_TYPE)
        node["sourceTypes"] = types
        node["positionListing"] = {
            "source": PLUM_SOURCE,
            "edition": record.get("edition") or DEFAULT_EDITION,
            "period": record.get("period"),
            "listedTitle": record.get("listedTitle"),
            "listedAgency": record.get("listedAgency"),
            "listedOrganization": record.get("listedOrganization"),
            "appointmentType": record.get("appointmentType"),
            "status": record.get("status"),
            "payPlan": record.get("payPlan"),
            "level": record.get("level"),
            "payLevel": record.get("payLevel"),
            "reportedPay": record.get("reportedPay"),
            "reportedPayText": record.get("reportedPayText"),
            # Whether one archive row carried this pay plan and this level
            # together. Published rather than kept in the evidence file so the
            # exporter and the release gate can both check it: pay_tables
            # refuses a pair the archive never printed on one row, and a rule
            # only the deriver can see is a rule a stale or hand-edited
            # evidence file walks straight past.
            "payPlanAndLevelOnOneRow": record.get("payPlanAndLevelOnOneRow"),
            "incumbencies": record.get("incumbencies"),
            "standing": record.get("standing"),
            # Which rows the type, pay plan and level were read off: with no
            # standing listing they come from a past incumbency, and the
            # panel must not present those as the position's own.
            "valuesFrom": record.get("valuesFrom"),
            "url": url,
            "checkedAt": checked_at,
        }
        for field in ("statusCounts", "appointmentTypeCounts", "payPlanCounts", "levelCounts"):
            if record.get(field):
                node["positionListing"][field] = record[field]
        if not node.get("lastVerified") or checked_at > str(node.get("lastVerified")):
            node["lastVerified"] = checked_at
            node["evidenceVerifiedAt"] = checked_at
        if not node.get("verificationMethod"):
            node["verificationMethod"] = PLUM_METHOD
        stats["listed"] += 1
        if placement and placement.get("status") == STATUS_LISTED:
            if str(placement.get("parentId") or "") != str(parent_map.get(node_id) or ""):
                stats["placements_stale_parent"] += 1
            elif node.get("placementVerified") is not True:
                node["placementVerified"] = True
                node["placementUrl"] = url
                node["placementVerifiedAt"] = checked_at
                node["placementParentId"] = parent_map.get(node_id)
                # The text that names *this* node in the source, as everywhere
                # else this field is used (evidence.py stamps the label found
                # on the parent's page, and the gate checks it names the node):
                # here that is the archive's title, not the organisation it is
                # filed under — which `positionListing.listedOrganization`
                # already carries.
                node["placementMatchedText"] = record.get("listedTitle")
                node["placementMethod"] = PLUM_PLACEMENT_METHOD
                node.pop("placementCheckable", None)
                stats["placements_listed"] += 1
        verify_node_sources(node)
    return stats
