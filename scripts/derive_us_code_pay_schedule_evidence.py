#!/usr/bin/env python
"""Derive pay evidence for elected offices from Schedule 6 of the annual
pay-adjustment order, as the U.S. Code prints it.

    python scripts/derive_us_code_pay_schedule_evidence.py --dry-run
    python scripts/derive_us_code_pay_schedule_evidence.py    # writes data/verification/us_code_pay_schedule_evidence.json

Reads one committed file: `tests/fixtures/uscode/pay_schedules_5_usc_5332.html`,
the Office of the Law Revision Counsel's reproduction of the order's schedules
in the note to 5 U.S.C. 5332. Schedule 6 states the annual rate for the Vice
President, for Senators and Members, and for each chamber's leadership.

This closes the two gaps `data_pipeline/verification/congressional_pay.py`
records in its own docstring as unreachable: the House's Speaker and
Majority/Minority Leaders, and the Vice President. See
`data_pipeline/verification/us_code_pay_schedules.py` for what it does not
price, and why each refusal is a decision rather than an oversight.

Every record is validated against its own node by
`financial_evidence.validate_record` before it is written. Nothing here
fetches.
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
from data_pipeline.verification.us_code_pay_schedules import (  # noqa: E402
    DEFAULT_PAY_EVIDENCE_PATH,
    DEFAULT_SCHEDULE_HTML,
    Unreadable,
    build_records,
    load_pay_schedules,
)

DEFAULT_BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"


def _relative(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--schedules", type=Path, default=DEFAULT_SCHEDULE_HTML,
                        help="verbatim 5 U.S.C. 5332 page (its .meta.json sibling supplies URL, fetch time and digest)")
    parser.add_argument("--out", type=Path, default=DEFAULT_PAY_EVIDENCE_PATH)
    parser.add_argument("--dry-run", action="store_true", help="report what would be written and write nothing")
    args = parser.parse_args((argv or sys.argv)[1:])

    try:
        loaded = load_pay_schedules(args.schedules)
    except Unreadable as error:
        print(f"refused: {error}")
        return 1
    schedules = loaded["schedules"]

    node_map, _ = index_tree(load_base_graph(args.base_graph))
    records, report = build_records(
        node_map, schedules, url=loaded["url"], sha256=loaded["sha256"], retrieved_at=loaded["fetched_at"]
    )

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
            rejected.append(
                f"{node_id}: classified {state!r}; which node a schedule row names is a reviewed "
                "identification, so nothing here is more than a proxy"
            )
            continue
        out["financialEvidenceStatus"] = state
        validated[node_id] = out

    report["validated"] = len(validated)
    report["rejected"] = rejected
    report["conflicts"] = fe.detect_conflicts(validated.values())
    report["double_counted"] = fe.double_counted(validated.values())

    print(f"5 U.S.C. 5332 note, schedules {', '.join(report['schedulesRead'])}, year {report['year']}, fetched {loaded['fetched_at']}")
    print(f"  the column's mark sits once, on its first figure: {report['headMarked']}")
    print("Schedule 6 rows:")
    for row in report["schedule6Rows"]:
        print(f"    {row['printed']:>10s}  {row['office']}")
    print(f"considered {report['considered']}  priced {report['priced']}  validated {report['validated']}")
    for office in report["pricedOffices"]:
        print(f"    PRICED   {office}")
    for office, reason in report["notPriced"].items():
        print(f"    not priced: {office} — {reason}")
    if report["refused"]:
        print("  refused:")
        for reason, count in report["refused"].items():
            print(f"    {count:5d}  {reason}")
    for line in rejected[:20]:
        print(f"  REJECTED {line}")
    if report["conflicts"]:
        print(f"  conflicts: {len(report['conflicts'])}")
    if report["double_counted"]:
        print(f"  double counted: {len(report['double_counted'])}")

    # Corroboration, reported and never published as a second claim: the same
    # document carries the schedules two other modules price from, and this is
    # the only place the three can be compared against one another.
    if "5" in schedules:
        print("Schedule 5 (Executive Schedule), for comparison with OPM's Salary Table 2026-EX:")
        for row in report.get("schedule5Rows", []):
            print(f"    {row['printed']:>10s}  {row['office']}")
    if "7" in schedules:
        print("Schedule 7 (Judicial Salaries), for comparison with uscourts.gov's own table:")
        for row in report.get("schedule7Rows", []):
            print(f"    {row['printed']:>10s}  {row['office']}")
        print(f"  priced from Schedule 7: {report['schedule7Priced']} — {report['schedule7Reason']}")
    print("Every record is scoped 'proxy'. Basic pay is not the node's cost, and nothing here writes a source URL onto a node.")

    if args.dry_run:
        return 0
    if not validated:
        print("nothing validated; refusing to write an empty evidence file")
        return 1

    store = {
        "_note": (
            "Derived by scripts/derive_us_code_pay_schedule_evidence.py from one source: the note to "
            f"5 U.S.C. 5332, fetched {loaded['fetched_at']} from {loaded['url']}, which reproduces the annual "
            "pay-adjustment order's schedules verbatim. Schedule 6 states the rate for the Vice President and "
            "for each chamber's elected offices. A record is written only for the four curated nodes a reviewed "
            "table identifies: the Vice President, the Speaker of the House, and the House Majority and Minority "
            "Leaders — the offices congressional_pay.py records as unreachable from senate.gov. Not priced: the "
            "three Senate leadership roles Schedule 6 also names (already priced from senate.gov's own footnote; "
            "the two sources agree), the Vice President's separate Senate-leadership node (one officer, one "
            "salary, priced once), no Senator's or Member's seat (none is curated as its own position node), and "
            "nothing at all from Schedule 7 (every judicial tier it names is already priced from uscourts.gov, "
            "reaches only nodes stating a multiplicity, or reaches no post node). Basic pay is not the node's "
            "cost. Regenerate by re-running the script; never edit by hand."
        ),
        "source": {
            "kind": "us_code_pay_schedules",
            "url": loaded["url"],
            "fetched_at": loaded["fetched_at"],
            "sha256": loaded["sha256"],
            "file": _relative(Path(loaded["file"])),
            "year": report["year"],
            "schedule": report["source"] if "source" in report else "Schedule 6",
        },
        "report": report,
        "nodes": validated,
    }
    write_json_file(args.out, store)
    print(f"wrote {_relative(args.out)}  ({len(validated)} nodes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
