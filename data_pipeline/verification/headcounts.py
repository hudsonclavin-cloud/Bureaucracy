"""Official headcounts for the graph's organisations, from OPM's FedScope.

The curated file carries an `employees` string on 178 organisations
("~74,000", "~450,000 active duty", "~14,000 federal + 95,000 contractor")
with no source, and the cost cascade weights its estimates by that number
wherever no sibling reports a dollar figure (`get_node_weight`,
`employee_weight`). The government publishes its own count: OPM's FedScope
employment data, a snapshot of the federal civilian workforce by agency and
sub-agency, fetched verbatim and committed (tests/fixtures/opm/fedscope/,
README there). This module reads the March 2025 summary table — which also
carries the September 2024 snapshot — matches its agency and sub-agency
names to the curated organisations, and derives one record per node saying
exactly what the table says: the name as listed, the codes, the count, the
period, the earlier period's count, and the population the table covers in
the data dictionary's own words. Nothing is fetched; the dataset's fetch
time is the record's date.

What the count is, in the dictionary's words (COVERAGE_STATEMENT): federal
*civilian* employees in the *Executive Branch*, "excluding some agencies
such as the U.S. Postal Service and intelligence agencies", in an active
pay status. So the uniformed services are outside it by the word
"civilian", the other two branches by the phrase "Executive Branch" (the
file nonetheless carries a "JUDICIAL BRANCH" agency consisting of the Tax
Court, and the Government Printing Office), and the Postal Service and the
intelligence agencies by name. A curated figure that counts soldiers or
contractors will not agree with it, and the comparison this module reports
is meant to show exactly that.

Matching is by the project's canonical name key with two tolerances and no
others: "Department of X" and "Department of the X" are one key, and a
sub-agency name is scoped beneath the node its agency matched — the same
rule the Federal Register qualifier gets in directories.py — so the seven
"OFFICE OF THE INSPECTOR GENERAL" rows stay apart, and an unscoped name that
several nodes share matches nothing. One name to one node or nothing.

A sub-agency row that is the agency itself — 62 agencies have a single row
named as the agency ("SZ00 SOCIAL SECURITY ADMINISTRATION"), and the
Department of Energy has such a row beside FERC — is carried by the agency
record and never stamped a second time. The table has no total rows: the
sum of its sub-agency rows is the dataset's total, and `agency_totals`
checks for a self-named row equal to the sum of the others before summing.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from data_pipeline.exporter.build_graph import canonical_name_key, parse_cost_amount

FEDSCOPE_SOURCE = "opm_fedscope_employment"
FEDSCOPE_MEMBER_PREFIX = "Status Employment by Agency and SubAgency"
SUPPRESSED_CODE = "10_OR_LESS"
LEVEL_AGENCY = "agency"
LEVEL_SUBAGENCY = "subagency"
STATUS_LISTED = "listed"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FEDSCOPE_ZIP = PROJECT_ROOT / "tests" / "fixtures" / "opm" / "fedscope" / "fedscope_employment_summary_2025-03.zip"
DEFAULT_HEADCOUNT_EVIDENCE_PATH = PROJECT_ROOT / "data" / "verification" / "headcount_evidence.json"

# The data dictionary's own words (fedscope_employment_summary_2025-03_data_dictionary.pdf,
# "(Preliminary) March 2025 Employment Dataset", Overview). Quoted, not paraphrased,
# because every record carries it and the site will print it.
COVERAGE_STATEMENT = (
    "EHRI includes data related to Federal civilian employees in the Executive Branch excluding some agencies "
    "such as the U.S. Postal Service and intelligence agencies. The Employment dataset only includes Federal "
    "employees in an active pay status."
)
COVERAGE_SOURCE = "OPM, (Preliminary) March 2025 Employment Dataset data dictionary, Overview"
# The same document's caveat about the snapshot itself.
SNAPSHOT_CAVEAT = (
    "The March 2025 does not reflect expected Federal workforce reshaping activities. Employees on administrative "
    "leave pending resignation, retirement, or release are identified as current employees."
)


def period_label(datecode: Any) -> str:
    """"202503" -> "2025-03"; anything else is returned as written."""
    text = str(datecode or "").strip()
    if len(text) == 6 and text.isdigit():
        return f"{text[:4]}-{text[4:]}"
    return text


def load_fedscope_agency_subagency(zip_path: str | Path, member: str | None = None) -> dict[str, list[dict[str, Any]]]:
    """Rows of the agency/sub-agency table, keyed by period ("2025-03").

    Read from the ZIP in place, never extracted. Each row: agency_code,
    agency_name, subagency_code, subagency_name, employees (int), datecode.
    A row whose EMPCOUNT is not an integer is an error in the source and
    raises, never a zero.
    """
    with zipfile.ZipFile(zip_path) as archive:
        name = member
        if name is None:
            candidates = [n for n in archive.namelist() if Path(n).name.startswith(FEDSCOPE_MEMBER_PREFIX)]
            if len(candidates) != 1:
                raise ValueError(f"expected one '{FEDSCOPE_MEMBER_PREFIX}*' member in {zip_path}, found {candidates}")
            name = candidates[0]
        text = archive.read(name).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    required = {"DATECODE", "AGY", "AGYT", "AGYSUB", "AGYSUBT", "EMPCOUNT"}
    missing = required - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"{name}: missing columns {sorted(missing)}")
    periods: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for line_number, row in enumerate(reader, start=2):
        datecode = str(row.get("DATECODE") or "").strip()
        count_text = str(row.get("EMPCOUNT") or "").strip()
        if not datecode:
            continue
        try:
            employees = int(count_text.replace(",", ""))
        except ValueError as exc:
            raise ValueError(f"{name} line {line_number}: EMPCOUNT {count_text!r} is not a count") from exc
        periods[period_label(datecode)].append({
            "datecode": datecode,
            "agency_code": str(row.get("AGY") or "").strip(),
            "agency_name": str(row.get("AGYT") or "").strip(),
            "subagency_code": str(row.get("AGYSUB") or "").strip(),
            "subagency_name": str(row.get("AGYSUBT") or "").strip(),
            "employees": employees,
        })
    return dict(periods)


def load_fedscope_meta(zip_path: str | Path) -> dict[str, Any]:
    """The sibling .meta.json a verbatim fetch leaves: url, fetched_at, sha256."""
    path = Path(zip_path)
    meta_path = path.with_name(path.name + ".meta.json")
    if not meta_path.exists():
        return {"url": None, "fetched_at": None, "sha256": None, "file": path.name}
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"url": None, "fetched_at": None, "sha256": None, "file": path.name}
    if not isinstance(meta, dict):
        return {"url": None, "fetched_at": None, "sha256": None, "file": path.name}
    return {
        "url": meta.get("final_url") or meta.get("url") or None,
        "fetched_at": meta.get("fetched_at") or None,
        "sha256": meta.get("sha256") or None,
        "file": meta.get("file") or path.name,
    }


def headcount_name_keys(name: Any) -> set[str]:
    """The canonical keys a FedScope name answers to: itself, and — the one
    rewrite this source needs — "department of X" for "department of the X"
    and back ("DEPARTMENT OF TREASURY" / "Department of the Treasury",
    "DEPARTMENT OF INTERIOR" / "Department of the Interior"). Upper case is
    the canonical key's business. Nothing else: an abbreviated name
    ("NAT AERONAUTICS AND SPACE ADMINISTRATION", "DEPARTMENT OF HOUSING AND
    URBAN DEVELOPM") stays unmatched and is reported."""
    key = canonical_name_key(name)
    if not key:
        return set()
    keys = {key}
    if key.startswith("department of the "):
        keys.add("department of " + key[len("department of the "):])
    elif key.startswith("department of "):
        keys.add("department of the " + key[len("department of "):])
    # The table truncates a leading "NATIONAL" to fit its column: "NAT
    # AERONAUTICS AND SPACE ADMINISTRATION", "NAT ARCHIVES AND RECORDS
    # ADMINISTRATION", "NAT FOUNDATION ON ARTS AND HUMANITIES". Expanding it
    # is not a guess about which unit is meant; it is undoing an abbreviation
    # the file itself makes, and it matters because an agency that fails to
    # match leaves its sub-rows with no scope to be checked against.
    if key.startswith("nat "):
        keys.add("national " + key[len("nat "):])
    return {k for k in keys if k}


def agency_totals(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per-agency totals for one period, as the sum of the agency's
    sub-agency rows.

    The table prints no total row (the March 2025 file: every row is a
    sub-agency, and the rows sum to the dataset's total, 2,289,472). The
    check is still made: a row named as its agency whose count equals the
    sum of the agency's other rows would be a total row, and then the total
    is that row, not the sum plus it. A row named as its agency that is not
    a total (Energy's "DN00 DEPARTMENT OF ENERGY", 15,891 beside FERC's
    1,581) is the agency's own element and is reported as `self_named_row`.
    """
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    names: dict[str, str] = {}
    for row in rows:
        grouped[row["agency_code"]].append(row)
        names.setdefault(row["agency_code"], row["agency_name"])
    totals: dict[str, dict[str, Any]] = {}
    for code, agency_rows in grouped.items():
        agency_keys = headcount_name_keys(names[code])
        self_named = [r for r in agency_rows if headcount_name_keys(r["subagency_name"]) & agency_keys]
        total_row = None
        for candidate in self_named:
            others = sum(r["employees"] for r in agency_rows if r is not candidate)
            if len(agency_rows) > 1 and candidate["employees"] == others:
                total_row = candidate
                break
        counted = [r for r in agency_rows if r is not total_row]
        totals[code] = {
            "code": code,
            "name": names[code],
            "employees": sum(r["employees"] for r in counted),
            "rows": len(agency_rows),
            "components": [
                {"subagencyCode": r["subagency_code"], "listedName": r["subagency_name"], "employees": r["employees"]}
                for r in sorted(counted, key=lambda r: (-r["employees"], r["subagency_code"]))
            ],
            "total_row": (
                {"subagencyCode": total_row["subagency_code"], "listedName": total_row["subagency_name"], "employees": total_row["employees"]}
                if total_row else None
            ),
            "self_named_row": (
                {"subagencyCode": self_named[0]["subagency_code"], "listedName": self_named[0]["subagency_name"], "employees": self_named[0]["employees"]}
                if self_named and self_named[0] is not total_row else None
            ),
        }
    return totals


def _is_organisation(node: dict[str, Any]) -> bool:
    return "position" not in str(node.get("type") or "").casefold() and not node.get("synthetic")


def _ancestors(node_id: str, parent_map: dict[str, str | None]) -> list[str]:
    chain: list[str] = []
    current = parent_map.get(node_id)
    while current:
        chain.append(current)
        current = parent_map.get(current)
    return chain


def _branch_of(node_id: str, parent_map: dict[str, str | None], root_id: str) -> str | None:
    chain = _ancestors(node_id, parent_map)
    if not chain:
        return None
    if chain[-1] != root_id:
        return None
    return chain[-2] if len(chain) >= 2 else node_id


def match_fedscope(
    periods: dict[str, list[dict[str, Any]]],
    node_map: dict[str, dict[str, Any]],
    parent_map: dict[str, str | None],
    *,
    root_id: str,
    period: str | None = None,
    url: str | None = None,
    fetched_at: str | None = None,
    file: str | None = None,
    coverage: str = COVERAGE_STATEMENT,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Records keyed by node id, and a report of what did not match and why.

    `period` defaults to the latest in the table; the period before it, if
    the table carries one, supplies each record's `previous`.
    """
    if not periods:
        return {}, {"source": FEDSCOPE_SOURCE, "period": None, "error": "no rows"}
    period = period or max(periods)
    earlier = sorted(p for p in periods if p < period)
    previous_period = earlier[-1] if earlier else None
    rows = [r for r in periods[period] if r["agency_code"] != SUPPRESSED_CODE]
    suppressed = [r for r in periods[period] if r["agency_code"] == SUPPRESSED_CODE]
    previous_rows = [r for r in periods.get(previous_period, []) if r["agency_code"] != SUPPRESSED_CODE] if previous_period else []
    totals = agency_totals(rows)
    previous_totals = agency_totals(previous_rows) if previous_rows else {}
    previous_by_sub = {r["subagency_code"]: r for r in previous_rows}

    # Organisation nodes by every key they answer to; a key several nodes
    # share identifies none of them unless a scope tells them apart.
    by_key: dict[str, list[str]] = defaultdict(list)
    for node_id, node in node_map.items():
        if node_id == root_id or not _is_organisation(node):
            continue
        for key in headcount_name_keys(node.get("name")):
            by_key[key].append(node_id)
    ambiguous_keys = {k for k, ids in by_key.items() if len(ids) > 1}

    def candidates_for(name: str) -> tuple[set[str], bool]:
        found: set[str] = set()
        shared = False
        for key in headcount_name_keys(name):
            found.update(by_key.get(key, []))
            if key in ambiguous_keys:
                shared = True
        return found, shared

    executive_branch = next(
        (str(c.get("id")) for c in node_map.get(root_id, {}).get("children", []) if canonical_name_key(c.get("name")) == "executive branch"),
        None,
    )

    report: dict[str, Any] = {
        "source": FEDSCOPE_SOURCE, "url": url, "fetched_at": fetched_at, "file": file,
        "period": period, "previous_period": previous_period,
        "rows": len(rows), "suppressed_rows": [{"listedName": r["subagency_name"], "employees": r["employees"]} for r in suppressed],
        "agencies": len(totals), "agencies_matched": 0, "subagencies_matched": 0,
        "total_employees": sum(r["employees"] for r in periods[period]),
        "agency_total_rows_found": sum(1 for t in totals.values() if t["total_row"]),
        "ambiguous_agencies": [], "ambiguous_subagencies": [], "unmatched_agencies": [], "unmatched_subagencies": [],
        "self_named_rows": [], "headquarters_rows": [], "scoped_out": [], "node_answers_to_agency_and_subagency": [],
        "unscoped_refused": [], "agency_is_one_other_unit": [], "record_below_its_subtree": [],
        "agencies_listed_separately_beneath": [], "matched_outside_executive_branch": [],
        "ambiguous_names_in_graph": sorted(ambiguous_keys)[:40],
    }

    # Agencies first: one name to one node, one node to one agency.
    agency_node: dict[str, str] = {}
    node_agencies: dict[str, list[str]] = defaultdict(list)
    for code, total in totals.items():
        found, shared = candidates_for(total["name"])
        if len(found) == 1 and not shared:
            node_agencies[next(iter(found))].append(code)
        elif len(found) > 1 or shared:
            report["ambiguous_agencies"].append({"agencyCode": code, "listedName": total["name"], "nodes": sorted(found), "employees": total["employees"]})
        else:
            report["unmatched_agencies"].append({"agencyCode": code, "listedName": total["name"], "employees": total["employees"], "rows": total["rows"]})
    for node_id, codes in node_agencies.items():
        if len(codes) == 1:
            agency_node[codes[0]] = node_id
        else:
            for code in codes:
                report["ambiguous_agencies"].append({
                    "agencyCode": code, "listedName": totals[code]["name"], "nodes": [node_id],
                    "employees": totals[code]["employees"], "reason": "node answers to several agencies",
                })

    # Sub-agencies, scoped beneath the agency's node when it has one.
    sub_candidates: dict[str, tuple[dict[str, Any], str]] = {}
    node_subrows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        code = row["agency_code"]
        parent_node = agency_node.get(code)
        agency_keys = headcount_name_keys(totals[code]["name"])
        self_named = bool(headcount_name_keys(row["subagency_name"]) & agency_keys)
        tokens = canonical_name_key(row["subagency_name"]).split()
        if "headquarters" in tokens or "hq" in tokens:
            report["headquarters_rows"].append({"agencyCode": code, "agencyListedName": totals[code]["name"], "subagencyCode": row["subagency_code"],
                                                "listedName": row["subagency_name"], "employees": row["employees"], "agencyMatched": parent_node})
        if self_named and parent_node:
            # The agency's own element, or its only row: the agency record
            # carries this count already.
            report["self_named_rows"].append({"agencyCode": code, "subagencyCode": row["subagency_code"], "listedName": row["subagency_name"],
                                              "employees": row["employees"], "carriedBy": parent_node, "agencyRows": totals[code]["rows"]})
            continue
        found, shared = candidates_for(row["subagency_name"])
        if parent_node:
            scoped = {n for n in found if parent_node in _ancestors(n, parent_map)}
            if found and not scoped:
                report["scoped_out"].append({"agencyCode": code, "agencyListedName": totals[code]["name"], "agencyNode": parent_node,
                                             "subagencyCode": row["subagency_code"], "listedName": row["subagency_name"],
                                             "employees": row["employees"], "nodesElsewhere": sorted(found)})
                continue
            found = scoped
        elif found:
            # The agency this row belongs to matched no node, so nothing
            # verifies that the node answering to the row's name is the unit
            # the row describes — a name being unique in the graph is not
            # evidence of placement. Refused, whether or not it is shared.
            # This is what stamped a civilians-only Marine Corps count on the
            # uniformed service and three NASA centres on nodes nothing tied
            # to NASA, while NASA's own node got nothing.
            report["unscoped_refused"].append({"agencyCode": code, "agencyListedName": totals[code]["name"],
                                               "subagencyCode": row["subagency_code"], "listedName": row["subagency_name"],
                                               "employees": row["employees"], "nodes": sorted(found),
                                               "reason": "its agency matched no node, so the placement is unverified"})
            continue
        if len(found) == 1:
            node_id = next(iter(found))
            node_subrows[node_id].append(row)
            sub_candidates[row["subagency_code"]] = (row, node_id)
        elif len(found) > 1:
            report["ambiguous_subagencies"].append({"agencyCode": code, "subagencyCode": row["subagency_code"], "listedName": row["subagency_name"],
                                                    "employees": row["employees"], "nodes": sorted(found), "reason": "several nodes beneath the agency"})
        else:
            report["unmatched_subagencies"].append({"agencyCode": code, "agencyListedName": totals[code]["name"], "agencyMatched": parent_node,
                                                    "subagencyCode": row["subagency_code"], "listedName": row["subagency_name"], "employees": row["employees"]})

    records: dict[str, dict[str, Any]] = {}
    base_record = {"source": FEDSCOPE_SOURCE, "status": STATUS_LISTED, "period": period, "coverage": coverage,
                   "coverageSource": COVERAGE_SOURCE, "url": url, "checkedAt": fetched_at, "file": file}

    for code, node_id in agency_node.items():
        total = totals[code]
        # An "agency" whose whole table entry is one row for a different unit
        # is not a count of the agency. FedScope files the U.S. Tax Court
        # alone under an agency it calls "JUDICIAL BRANCH" (165 people) and
        # the Bureau of Consumer Financial Protection alone under "FEDERAL
        # RESERVE SYSTEM" (1,661): stamping either on the node its name
        # matches would publish one small unit's staff as a whole branch's,
        # and the second would publish one agency's staff as another's. The
        # name matched; the number does not describe the unit, and no caveat
        # makes "the Federal Reserve employs 1,661" true.
        if total["rows"] == 1 and not total["self_named_row"] and not total["total_row"]:
            only = (total["components"] or [{}])[0]
            report["agency_is_one_other_unit"].append({
                "agencyCode": code, "agencyListedName": total["name"], "node": node_id,
                "employees": total["employees"], "onlyRow": only,
                "reason": "the agency's whole entry is one row for a unit of another name",
            })
            continue
        previous = previous_totals.get(code)
        record: dict[str, Any] = {
            **base_record, "level": LEVEL_AGENCY, "listedName": total["name"], "agencyCode": code, "subagencyCode": None,
            "employees": total["employees"], "subagencyRows": total["rows"], "components": total["components"],
            "previous": {"period": previous_period, "employees": previous["employees"]} if previous else None,
        }
        if previous and previous["name"] != total["name"]:
            record["previous"]["listedName"] = previous["name"]
        if total["self_named_row"]:
            record["selfNamedRow"] = total["self_named_row"]
        if total["total_row"]:
            record["totalRow"] = total["total_row"]
        records[node_id] = record
        report["agencies_matched"] += 1

    for sub_code, (row, node_id) in sub_candidates.items():
        if len(node_subrows[node_id]) != 1:
            report["ambiguous_subagencies"].append({"agencyCode": row["agency_code"], "subagencyCode": sub_code, "listedName": row["subagency_name"],
                                                    "employees": row["employees"], "nodes": [node_id], "reason": "node answers to several sub-agencies"})
            continue
        if node_id in records:
            # An agency's node named again by a sub-agency row of some other
            # agency: the agency record stands; the count is not stamped twice.
            report["node_answers_to_agency_and_subagency"].append({"node": node_id, "agencyCode": row["agency_code"], "subagencyCode": sub_code,
                                                                   "listedName": row["subagency_name"], "employees": row["employees"]})
            continue
        code = row["agency_code"]
        total = totals[code]
        previous = previous_by_sub.get(sub_code)
        record = {
            **base_record, "level": LEVEL_SUBAGENCY, "listedName": row["subagency_name"], "agencyCode": code,
            "agencyListedName": total["name"], "agencyMatched": agency_node.get(code), "subagencyCode": sub_code,
            "employees": row["employees"], "agencyEmployees": total["employees"], "agencySubagencyRows": total["rows"],
            "previous": {"period": previous_period, "employees": previous["employees"]} if previous else None,
        }
        if previous and previous["subagency_name"] != row["subagency_name"]:
            record["previous"]["listedName"] = previous["subagency_name"]
        if total["rows"] == 1:
            record["wholeAgency"] = True
        records[node_id] = record
        report["subagencies_matched"] += 1

    # Facts about where the matches sit in the tree, for the panel and the
    # curation: an agency the table lists apart from one the graph files
    # beneath it (the three military departments under Defense), and a
    # matched node the graph files outside the Executive Branch the
    # dictionary says the table covers.
    for node_id, record in records.items():
        if record["level"] != LEVEL_AGENCY:
            continue
        beneath = [
            {"agencyCode": other["agencyCode"], "listedName": other["listedName"], "nodeId": other_id, "employees": other["employees"]}
            for other_id, other in records.items()
            if other["level"] == LEVEL_AGENCY and other_id != node_id and node_id in _ancestors(other_id, parent_map)
        ]
        if beneath:
            record["agenciesListedSeparatelyBeneath"] = sorted(beneath, key=lambda b: -b["employees"])
            report["agencies_listed_separately_beneath"].append({"node": node_id, "listedName": record["listedName"], "employees": record["employees"],
                                                                 "beneath": [b["agencyCode"] for b in record["agenciesListedSeparatelyBeneath"]]})
    for node_id, record in records.items():
        branch = _branch_of(node_id, parent_map, root_id)
        if executive_branch and branch != executive_branch:
            record["outsideStatedCoverage"] = True
            record["treeBranch"] = branch
            report["matched_outside_executive_branch"].append({"node": node_id, "listedName": record["listedName"], "employees": record["employees"], "branch": branch})

    report["unmatched_agencies"].sort(key=lambda a: -a["employees"])
    report["unmatched_subagencies"].sort(key=lambda a: -a["employees"])
    report["largest_unmatched"] = sorted(
        [{"kind": "agency", **a} for a in report["unmatched_agencies"]]
        + [{"kind": "subagency", **s} for s in report["unmatched_subagencies"]],
        key=lambda e: -e["employees"],
    )[:20]
    # A record that its own descendants' records already exceed does not cover
    # the unit it names: FedScope files the Army, the Navy and the Air Force
    # as agencies of their own, so the row set behind "DEPARTMENT OF DEFENSE"
    # is a fraction of the department the graph shows. The number stays — it
    # is what the table says — but it is marked, so nothing weights a
    # sibling set by a figure that is missing most of its own subtree.
    for node_id, record in records.items():
        beneath = sum(
            other["employees"] for other_id, other in records.items()
            if other_id != node_id and node_id in _ancestors(other_id, parent_map)
        )
        if beneath > record["employees"]:
            record["subtreeRecordsExceedIt"] = beneath
            report["record_below_its_subtree"].append({
                "node": node_id, "listedName": record["listedName"],
                "employees": record["employees"], "beneath": beneath,
            })

    report["matched_employees"] = sum(r["employees"] for r in records.values() if r["level"] == LEVEL_AGENCY) + sum(
        r["employees"] for r in records.values() if r["level"] == LEVEL_SUBAGENCY and not r.get("agencyMatched")
    )
    return records, report


def compare_with_curated(records: dict[str, dict[str, Any]], node_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The curated `employees` figure against the table's, parsed the way the
    cascade parses it (parse_cost_amount: "~74,000" -> 74000; "~750,000
    civilian + 1.3M active military" -> 2,050,000), so the comparison is of
    the number the cascade actually weights by."""
    compared: list[dict[str, Any]] = []
    no_curated: list[dict[str, Any]] = []
    for node_id, record in records.items():
        node = node_map.get(node_id) or {}
        raw = node.get("employees")
        curated = parse_cost_amount(raw)
        opm = record["employees"]
        if curated is None or curated <= 0:
            no_curated.append({"node": node_id, "name": node.get("name"), "opm": opm, "curatedText": raw if raw not in (None, "") else None})
            continue
        ratio = opm / curated if curated else None
        factor = max(ratio, 1 / ratio) if ratio and ratio > 0 else float("inf")
        compared.append({
            "node": node_id, "name": node.get("name"), "curated": curated, "curatedText": raw, "opm": opm,
            "listedName": record["listedName"], "level": record["level"], "ratio": round(ratio, 4) if ratio is not None else None,
            "factor": round(factor, 4) if factor != float("inf") else None, "direction": "opm_higher" if ratio and ratio > 1 else "opm_lower" if ratio and ratio < 1 else "equal",
        })
    bands = {"within_10pct": 0, "10_to_25pct": 0, "25pct_to_2x": 0, "beyond_2x": 0}
    for row in compared:
        factor = row["factor"] if row["factor"] is not None else float("inf")
        if factor <= 1.10:
            bands["within_10pct"] += 1
        elif factor <= 1.25:
            bands["10_to_25pct"] += 1
        elif factor <= 2.0:
            bands["25pct_to_2x"] += 1
        else:
            bands["beyond_2x"] += 1
    largest = sorted(compared, key=lambda r: -(r["factor"] if r["factor"] is not None else float("inf")))[:15]
    curated_sum = sum(r["curated"] for r in compared)
    opm_sum = sum(r["opm"] for r in compared)
    return {
        "compared": len(compared), "bands": bands,
        "cumulative": {"within_10pct": bands["within_10pct"], "within_25pct": bands["within_10pct"] + bands["10_to_25pct"],
                       "within_2x": bands["within_10pct"] + bands["10_to_25pct"] + bands["25pct_to_2x"], "beyond_2x": bands["beyond_2x"]},
        "opm_lower": sum(1 for r in compared if r["direction"] == "opm_lower"), "opm_higher": sum(1 for r in compared if r["direction"] == "opm_higher"),
        "curated_sum": curated_sum, "opm_sum": opm_sum,
        "largest_discrepancies": largest,
        "no_curated_figure": len(no_curated), "no_curated_figure_nodes": sorted(no_curated, key=lambda r: -r["opm"]),
        "rows": sorted(compared, key=lambda r: -r["opm"]),
    }


def load_headcount_evidence(path: str | Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    records = payload.get("nodes") if isinstance(payload.get("nodes"), dict) else {}
    return {str(k): v for k, v in records.items() if isinstance(v, dict)}


def listed_name_still_names(node_name: Any, listed_name: Any) -> bool:
    """Whether a record earned under `listed_name` still names the node as it
    is now called — the check an exporter must make before stamping, so a
    rename in the curated file cannot inherit another unit's count."""
    key = canonical_name_key(node_name)
    return bool(key) and key in headcount_name_keys(listed_name)
