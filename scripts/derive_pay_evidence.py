#!/usr/bin/env python
"""Derive pay evidence from OPM's Executive Schedule salary table.

    python scripts/derive_pay_evidence.py --dry-run
    python scripts/derive_pay_evidence.py          # writes data/verification/pay_evidence.json

Reads two committed files and joins them:

- `tests/fixtures/opm/pay/executive_schedule_2026.html`, OPM's Salary Table
  No. 2026-EX as fetched on 2026-09-11, which says what each Executive
  Schedule level pays and nothing about which posts are at which level;
- `data/verification/position_evidence.json`, derived from the PLUM archive of
  the PREVIOUS administration (January 21, 2021 - January 20, 2025), which says
  which posts the archive reported at which level and nothing about what a
  level pays.

Neither document says what a position pays its current holder, and this script
does not conclude that it does. Every record it writes carries both halves with
their own dates, is scoped `proxy` because the table names a rank rather than
the unit, and is therefore graded `partial` by
`financial_evidence.classify` — there is no route by which one becomes
`verified`.

A rate is published only where the archive gives **both** an `EX` pay plan and
a level the table prints. The archive files General Schedule grades in the same
column as Executive Schedule levels, and two of its rows carry a Roman numeral
on a pay plan that is not the Executive Schedule at all, so the numeral alone
settles nothing.

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
from data_pipeline.verification.pay_tables import (  # noqa: E402
    DEFAULT_PAY_EVIDENCE_PATH,
    DEFAULT_PAY_TABLE_HTML,
    Unreadable,
    build_records,
    load_executive_schedule,
)
from data_pipeline.verification.positions import (  # noqa: E402
    DEFAULT_POSITION_EVIDENCE_PATH,
    load_position_evidence,
)

DEFAULT_BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"


def _relative(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--pay-table", type=Path, default=DEFAULT_PAY_TABLE_HTML,
                        help="verbatim salary table (its .meta.json sibling supplies URL, fetch time and digest)")
    parser.add_argument("--positions", type=Path, default=DEFAULT_POSITION_EVIDENCE_PATH,
                        help="position evidence, which supplies the level each post was reported at")
    parser.add_argument("--out", type=Path, default=DEFAULT_PAY_EVIDENCE_PATH)
    parser.add_argument("--dry-run", action="store_true", help="report what would be written and write nothing")
    args = parser.parse_args((argv or sys.argv)[1:])

    try:
        loaded = load_executive_schedule(args.pay_table)
    except Unreadable as error:
        print(f"refused: {error}")
        return 1
    table = loaded["table"]

    listings = load_position_evidence(args.positions)
    if not listings:
        print(f"no position evidence at {_relative(args.positions)}; nothing can be priced")
        return 1

    records, report = build_records(
        listings, table,
        url=loaded["url"], sha256=loaded["sha256"], retrieved_at=loaded["fetched_at"],
    )

    # Bind every record to its node and let the red-teamed validator refuse it.
    # This is the whole reason the records go through `financial_evidence`
    # rather than being stamped straight onto the graph: the module's checks
    # were written against 178 attacks, and a producer that skipped them would
    # be a second, unreviewed path to the same fields.
    node_map, _ = index_tree(load_base_graph(args.base_graph))
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
        validated[node_id] = out

    report["validated"] = len(validated)
    report["rejected"] = rejected
    conflicts = fe.detect_conflicts(validated.values())
    duplicates = fe.double_counted(validated.values())
    report["conflicts"] = conflicts
    report["double_counted"] = duplicates

    print(f"table {report['table']}  {report['effectiveText']}  fetched {loaded['fetched_at']}")
    print(f"  levels: " + "  ".join(f"{k} ${v:,.0f}" for k, v in report["levels"].items()))
    for note in report["footnotes"]:
        print(f"  footnote carried: {note}")
    print(f"listings considered {report['listings_considered']}  priced {report['priced']}  validated {report['validated']}")
    print(f"  by level: {report['priced_by_level']}")
    print("  refused:")
    for reason, count in report["refused"].items():
        print(f"    {count:5d}  {reason}")
    for line in rejected[:20]:
        print(f"  REJECTED {line}")
    if conflicts:
        print(f"  conflicts: {len(conflicts)}")
    if duplicates:
        print(f"  double counted: {len(duplicates)}")
    print("Every record is a proxy: the table names a rank, not a unit, so none of these is ever 'verified'.")
    print("The level is the previous administration's archive; the rate is effective January 2026. Neither says what the post pays now.")

    if args.dry_run:
        return 0
    if not validated:
        print("nothing validated; refusing to write an empty evidence file")
        return 1

    store = {
        "_note": (
            "Derived by scripts/derive_pay_evidence.py by joining two documents, neither of which says what a "
            f"position pays its current holder. The RATE is OPM's {report['table']} ({report['effectiveText']}), "
            f"fetched {loaded['fetched_at']}, which states what each Executive Schedule level pays and names no "
            "post. The LEVEL is data/verification/position_evidence.json, derived from the PLUM archive of the "
            "PREVIOUS administration (January 21, 2021 - January 20, 2025), which reports which posts were listed "
            "at which level and states no rate. Each record therefore carries both halves with their own dates in "
            "'levelClaim', is scoped 'proxy' because the table names a rank rather than the unit, and is graded "
            "'partial' — no record here is ever 'verified'. A rate is published only where the archive gives both "
            "an 'EX' pay plan and a level this table prints: the archive files General Schedule grades in the same "
            "column, and two of its rows carry a Roman numeral on a pay plan that is not the Executive Schedule. "
            "Basic pay is not the node's cost — it excludes benefits and is not a share of federal outlays, which "
            "is what resolved_total_amount means everywhere else in this graph. The table's own footnotes ride on "
            "every record because a pay freeze for the Vice President and certain senior political appointees means "
            "a level's table rate is not necessarily what was payable. Regenerate by re-running the script; never "
            "edit by hand."
        ),
        "source": {
            "kind": "opm_executive_schedule",
            "url": loaded["url"],
            "fetched_at": loaded["fetched_at"],
            "sha256": loaded["sha256"],
            "file": _relative(Path(loaded["file"])),
            "table": report["table"],
            "effective": report["effective"],
            "effectiveText": report["effectiveText"],
            "footnotes": report["footnotes"],
        },
        "levelSource": {
            "kind": "opm_plum_archive",
            "file": _relative(args.positions),
        },
        "report": report,
        "nodes": validated,
    }
    write_json_file(args.out, store)
    print(f"wrote {len(validated)} records -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
