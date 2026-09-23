#!/usr/bin/env python
"""Derive pay evidence from the Executive Schedule as the U.S. Code sets it.

    python scripts/derive_schedule_pay_evidence.py --dry-run
    python scripts/derive_schedule_pay_evidence.py   # writes data/verification/schedule_pay_evidence.json

Reads two committed documents and joins them, exactly as
`derive_pay_evidence.py` does -- but the level half comes from CURRENT LAW
rather than from an archive of the previous administration:

- `tests/fixtures/uscode/exec_schedule_53{12..16}.html`, 5 U.S.C. 5312-5316 as
  served by uscode.house.gov, which says which positions Congress placed at
  which Executive Schedule level and nothing about what a level pays;
- `tests/fixtures/opm/pay/executive_schedule_2026.html`, OPM's Salary Table
  No. 2026-EX, which says what each level pays and names no post at all.

Every digest is recomputed from the bytes on disk before either is read.

The claim is therefore "current law places this post at Level N, and OPM's
table effective January 2026 prints Level N at $X" -- not what the post's
holder receives, not the unit's cost, and not evidence that the node exists as
this graph draws it. `scopeMatch` is `proxy` and every record is graded
`partial`, the same deliberate downgrade `judicial_pay.py` and
`congressional_pay.py` make: `financial_evidence.classify` grades an exact
scope `verified`, and a rate of basic pay is not a measurement of what
`resolved_total_amount` measures everywhere else.

Matching is canonical-key EQUALITY and nothing looser. The statute prints both
"Secretary of the Army" and "Under Secretary of the Army"; a containment test
prices the second from the first. A statutory title reaching more than one node
prices neither -- "General Counsel" names 84 nodes here.

Nothing fetches. Every record is validated against its own node by
`financial_evidence.validate_record` before it is written.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.exporter.build_graph import index_tree, load_base_graph  # noqa: E402
from data_pipeline.json_io import write_json_file  # noqa: E402
from data_pipeline.verification import financial_evidence as fe  # noqa: E402
from data_pipeline.verification.pay_tables import (  # noqa: E402
    DEFAULT_PAY_TABLE_HTML,
    Unreadable as TableUnreadable,
    federal_fiscal_year_of,
    load_executive_schedule,
)
from data_pipeline.verification.statutory_schedule import (  # noqa: E402
    DEFAULT_EVIDENCE_PATH,
    FIXTURE_DIR,
    METHOD,
    SOURCE,
    Unreadable as ScheduleUnreadable,
    build_records,
    load_schedule,
    match_positions,
    match_reviewed_rows,
    match_scoped_positions,
)
from datetime import date  # noqa: E402

DEFAULT_BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--statute-dir", type=Path, default=FIXTURE_DIR)
    parser.add_argument("--pay-table", type=Path, default=DEFAULT_PAY_TABLE_HTML)
    parser.add_argument("--out", type=Path, default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument("--dry-run", action="store_true", help="report and write nothing")
    args = parser.parse_args((argv or sys.argv)[1:])

    try:
        loaded = load_executive_schedule(args.pay_table)
    except TableUnreadable as error:
        print(f"refused: the salary table is not readable: {error}")
        return 1
    try:
        schedule = load_schedule(args.statute_dir)
    except ScheduleUnreadable as error:
        print(f"refused: the statute is not readable: {error}")
        return 1
    table = loaded["table"]

    node_map, _ = index_tree(load_base_graph(args.base_graph))
    matching = match_positions(node_map, schedule)
    # The second route, for the titles the Code writes as "<office>,
    # <organisation>". Run after the first and handed what it took, so a node
    # can never be priced twice from two readings of the same statute.
    scoped = match_scoped_positions(node_map, schedule, already_matched=matching["matched"])
    matching["matched"].update(scoped["matched"])
    for reason, items in scoped["refusals"].items():
        matching["refusals"].setdefault(reason, []).extend(items)
    # The third route: reviewed identifications with a second statute behind
    # each, re-adjudicated on every run and never over a node another route
    # already priced.
    reviewed = match_reviewed_rows(node_map, schedule, already_matched=matching["matched"])
    matching["matched"].update(reviewed["matched"])
    for reason, items in reviewed["refusals"].items():
        matching["refusals"].setdefault(reason, []).extend(items)
    fiscal_year = federal_fiscal_year_of(date.fromisoformat(str(table["effective"])))
    records, report = build_records(
        matching["matched"], table,
        table_url=loaded["url"], table_sha256=loaded["sha256"],
        retrieved_at=loaded["fetched_at"], fiscal_year=fiscal_year,
    )
    report["matchRefusals"] = {k: len(v) for k, v in matching["refusals"].items()}
    report["scopedMatches"] = len(scoped["matched"])
    report["reviewedMatches"] = len(reviewed["matched"])
    report["reviewedRows"] = sorted(reviewed["matched"])
    report["ambiguousStatutoryTitles"] = schedule["ambiguous"]
    report["statutoryPositions"] = schedule["positions"]

    validated: dict[str, dict] = {}
    rejected: list[str] = []
    for node_id, record in sorted(records.items()):
        node = node_map.get(node_id)
        if node is None:
            rejected.append(f"{node_id}: not in the base graph")
            continue
        try:
            out = fe.validate_record(record, node)
        except fe.Rejected as error:
            rejected.append(str(error))
            continue
        state = fe.classify(out)
        if state != "partial":
            rejected.append(f"{node_id}: classified {state!r}; a rank is a proxy for a post and nothing more")
            continue
        out["financialEvidenceStatus"] = state
        # validate_record returns the checked record; the level half is this
        # module's own and rides through unchanged.
        out["levelClaim"] = record["levelClaim"]
        out["rateText"] = record["rateText"]
        out["effectiveText"] = record["effectiveText"]
        out["table"] = record["table"]
        out["tableFootnotes"] = record["tableFootnotes"]
        validated[node_id] = out

    report["validated"] = len(validated)
    report["rejected"] = rejected
    report["conflicts"] = fe.detect_conflicts(validated.values())
    report["double_counted"] = fe.double_counted(validated.values())

    print(f"statute       : {schedule['positions']} positions across 5 sections; "
          f"{len(schedule['index'])} distinct titles, {len(schedule['ambiguous'])} ambiguous")
    print(f"salary table  : {table['table']}  {table['effectiveText']}")
    print(f"matched nodes : {report['matched']} "
          f"({report['matched'] - report['scopedMatches'] - report['reviewedMatches']} by whole name, "
          f"{report['scopedMatches']} scoped to their organisation, "
          f"{report['reviewedMatches']} by a reviewed identification a second statute backs)   priced {report['priced']}   "
          f"validated {report['validated']}")
    print(f"  by level    : {report['priced_by_level']}")
    for reason, count in sorted(report["matchRefusals"].items()):
        print(f"  refused, {reason}: {count}")
    for reason, count in sorted(report["refused"].items()):
        print(f"  refused, {reason}: {count}")
    for line in rejected[:20]:
        print(f"  REJECTED {line}")
    for key, citations in sorted(report["ambiguousStatutoryTitles"].items()):
        print(f"  ambiguous in the Code, priced for nobody: {key!r} at {', '.join(citations)}")
    if report["conflicts"]:
        print(f"  conflicts: {len(report['conflicts'])}")
    if report["double_counted"]:
        print(f"  double counted: {len(report['double_counted'])}")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0
    store = {
        "_note": (
            "Derived by scripts/derive_schedule_pay_evidence.py. The LEVEL is 5 U.S.C. 5312-5316 as "
            "served by uscode.house.gov (current law, committed verbatim with its digests under "
            "tests/fixtures/uscode/); the RATE is OPM's Salary Table No. 2026-EX (committed likewise). "
            "Two documents, each stating half, and neither stating what the post's holder actually "
            "receives, what it costs to run the unit, or that the unit exists as this graph draws it. "
            "Every record is scopeMatch proxy and graded partial: the table names a rank, not a post."
        ),
        "source": {"kind": SOURCE, "method": METHOD,
                   "statute": "5 U.S.C. §§5312-5316",
                   "table": table["table"], "effective": table["effective"]},
        "report": report,
        "nodes": validated,
    }
    write_json_file(args.out, store)
    print(f"\nwrote {len(validated)} records -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
