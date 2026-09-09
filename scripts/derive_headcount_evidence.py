#!/usr/bin/env python
"""Derive headcount evidence from OPM's FedScope employment table.

    python scripts/derive_headcount_evidence.py --dry-run
    python scripts/derive_headcount_evidence.py            # writes data/verification/headcount_evidence.json

Reads the March 2025 FedScope employment summary exactly as fetched
(tests/fixtures/opm/fedscope/fedscope_employment_summary_2025-03.zip, in
place; its .meta.json supplies the URL and fetch time), matches the table's
agency and sub-agency names to the curated graph's organisations by
canonical name — one name to one node, or nothing — and writes one record
per node saying what the table says: the name as listed, the codes, the
civilian headcount for March 2025 and September 2024, and the population
the data dictionary says the table covers. Then it compares the table's
count with the curated `employees` figure the cost cascade weights by, and
prints the distribution. Nothing here fetches.
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
from data_pipeline.verification.headcounts import (  # noqa: E402
    COVERAGE_SOURCE,
    COVERAGE_STATEMENT,
    DEFAULT_FEDSCOPE_ZIP,
    DEFAULT_HEADCOUNT_EVIDENCE_PATH,
    FEDSCOPE_MEMBER_PREFIX,
    SNAPSHOT_CAVEAT,
    compare_with_curated,
    load_fedscope_agency_subagency,
    load_fedscope_meta,
    match_fedscope,
)

DEFAULT_BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"


def _relative(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path)


def _fmt(n: int | float | None) -> str:
    return "—" if n is None else f"{n:,.0f}"


def print_report(report: dict, comparison: dict, records: dict) -> None:
    print(f"fedscope {report.get('file')}  fetched {report.get('fetched_at')}  period {report['period']}  previous {report['previous_period']}")
    print(f"coverage ({COVERAGE_SOURCE}): {COVERAGE_STATEMENT}")
    print(f"rows {report['rows']} (+{len(report['suppressed_rows'])} suppressed '10_OR_LESS' row(s))  agencies {report['agencies']}  "
          f"total employees {report['total_employees']:,}  agency total rows found {report['agency_total_rows_found']}")
    print(f"matched: agencies {report['agencies_matched']}  sub-agencies {report['subagencies_matched']}  records {len(records)}  "
          f"employees reaching a node {report['matched_employees']:,} of {report['total_employees']:,}")
    print(f"ambiguous: agencies {len(report['ambiguous_agencies'])}  sub-agencies {len(report['ambiguous_subagencies'])};  "
          f"unmatched: agencies {len(report['unmatched_agencies'])}  sub-agencies {len(report['unmatched_subagencies'])};  "
          f"self-named rows carried by the agency record {len(report['self_named_rows'])};  headquarters rows {len(report['headquarters_rows'])};  "
          f"listed under an agency the graph files them outside of {len(report['scoped_out'])}")
    for item in report["ambiguous_agencies"]:
        print("  ambiguous agency:", item)
    for item in report["ambiguous_subagencies"]:
        print("  ambiguous sub-agency:", item)
    for item in report["scoped_out"]:
        print(f"  filed elsewhere: {item['listedName']} ({item['employees']:,}) under {item['agencyListedName']} in the table; "
              f"the graph has {item['nodesElsewhere']} outside {item['agencyNode']}")
    for item in report["node_answers_to_agency_and_subagency"]:
        print("  agency node named again by a sub-agency row (not stamped twice):", item)
    for item in report["agencies_listed_separately_beneath"]:
        print(f"  {item['listedName']} ({item['employees']:,}): the table lists {item['beneath']} as agencies of their own; the graph files them beneath it")
    for item in report["matched_outside_executive_branch"]:
        print(f"  outside the stated coverage (Executive Branch): {item['node']} '{item['listedName']}' {item['employees']:,} under {item['branch']}")
    print("  20 largest unmatched by headcount:")
    for item in report["largest_unmatched"]:
        where = f" under {item['agencyListedName']}" if item["kind"] == "subagency" else ""
        print(f"    {item['employees']:>8,}  {item['kind']:9} {item['listedName']}{where}")
    print(f"curated vs OPM: {comparison['compared']} matched nodes carry a curated figure; {comparison['no_curated_figure']} carry none (the table would supply one)")
    cum = comparison["cumulative"]
    print(f"  within 10%: {cum['within_10pct']}   within 25%: {cum['within_25pct']}   within 2x: {cum['within_2x']}   beyond 2x: {cum['beyond_2x']}   "
          f"(OPM lower on {comparison['opm_lower']}, higher on {comparison['opm_higher']}; curated sum {comparison['curated_sum']:,.0f} vs OPM {comparison['opm_sum']:,})")
    print("  15 largest discrepancies (node, curated, OPM, OPM/curated):")
    for row in comparison["largest_discrepancies"]:
        print(f"    {row['node']:55} {_fmt(row['curated']):>12} {row['opm']:>10,} {row['ratio']:>8.3f}   curated text: {row['curatedText']!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--fedscope", type=Path, default=DEFAULT_FEDSCOPE_ZIP, help="verbatim FedScope employment summary ZIP (read in place)")
    parser.add_argument("--period", default=None, help="period to publish, e.g. 2025-03 (default: the latest in the table)")
    parser.add_argument("--out", type=Path, default=DEFAULT_HEADCOUNT_EVIDENCE_PATH)
    parser.add_argument("--dry-run", action="store_true", help="report the matches; write nothing")
    args = parser.parse_args((argv or sys.argv)[1:])

    root = load_base_graph(args.base_graph)
    node_map, parent_map = index_tree(root)
    periods = load_fedscope_agency_subagency(args.fedscope)
    meta = load_fedscope_meta(args.fedscope)
    records, report = match_fedscope(
        periods, node_map, parent_map, root_id=str(root.get("id") or ""), period=args.period,
        url=meta.get("url"), fetched_at=meta.get("fetched_at"), file=_relative(args.fedscope),
    )
    comparison = compare_with_curated(records, node_map)
    print_report(report, comparison, records)
    if args.dry_run:
        return 0
    store = {
        "_note": (
            "Derived by scripts/derive_headcount_evidence.py from OPM's FedScope employment summary table, read verbatim "
            "from the committed ZIP; each record says what the table lists for the node — the name, the codes, the civilian "
            "headcount for the period and the one before, and the population the data dictionary says the table covers — "
            "and nothing else. checkedAt is the dataset's fetch time. Regenerate by re-running the script; never edit by hand."
        ),
        "source": {
            "kind": "opm_fedscope_employment_summary", "url": meta.get("url"), "fetched_at": meta.get("fetched_at"), "sha256": meta.get("sha256"),
            "file": _relative(args.fedscope), "member": f"{FEDSCOPE_MEMBER_PREFIX}_202503_and_202409.txt",
            "period": report["period"], "previous_period": report["previous_period"],
            "coverage": COVERAGE_STATEMENT, "coverage_source": COVERAGE_SOURCE, "snapshot_caveat": SNAPSHOT_CAVEAT,
        },
        "report": {k: v for k, v in report.items() if k not in ("unmatched_subagencies",)} | {
            "unmatched_subagencies": report["unmatched_subagencies"][:120],
            "comparison": {k: v for k, v in comparison.items() if k != "rows"} | {"rows": comparison["rows"]},
        },
        "nodes": records,
    }
    write_json_file(args.out, store)
    print(f"wrote {len(records)} records -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
