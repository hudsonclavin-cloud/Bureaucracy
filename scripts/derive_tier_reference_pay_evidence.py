"""Derive pay evidence for posts whose pay a statute sets BY REFERENCE to an
Executive Schedule level, joined to OPM's Salary Table No. 2026-EX.

    python scripts/derive_tier_reference_pay_evidence.py --dry-run
    python scripts/derive_tier_reference_pay_evidence.py    # writes data/verification/tier_reference_pay_evidence.json

Reads committed files and fetches nothing: 31 U.S.C. 703 (the Comptroller
General "is equal to the rate for level II"; the Deputy, level III),
5 U.S.C. 403 (an Inspector General's pay is "the rate payable for level III
... plus 3 percent"), 5 U.S.C. 401 (which establishments' Inspectors General
that covers, by name), and OPM's table, which prices the levels.

**No document states any of these figures for these posts.** A GAO record's
figure is the level's printed rate; an Inspector General's is arithmetic on
it -- $209,600 plus 3 percent -- and the record carries that arithmetic in
the open, the count of documents it rests on, and what that count is worth on
this project's own source scale, beside an explicit
`documentsStatingTheFigure: 0`. See
`data_pipeline/verification/tier_reference_pay.py`.

Every record is validated against its own node by
`financial_evidence.validate_record` before it is written.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.exporter.build_graph import index_tree, load_base_graph  # noqa: E402
from data_pipeline.json_io import write_json_file  # noqa: E402
from data_pipeline.verification import financial_evidence as fe  # noqa: E402
from data_pipeline.verification.pay_tables import (  # noqa: E402
    DEFAULT_PAY_TABLE_HTML,
    federal_fiscal_year_of,
    load_executive_schedule,
)
from data_pipeline.verification.tier_reference_pay import (  # noqa: E402
    DEFAULT_PAY_EVIDENCE_PATH,
    STRENGTH_SCALE,
    Unreadable,
    build_records,
    document_strength_percent,
)

DEFAULT_BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"


def _relative(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--table", type=Path, default=DEFAULT_PAY_TABLE_HTML,
                        help="verbatim OPM Salary Table No. 2026-EX page")
    parser.add_argument("--out", type=Path, default=DEFAULT_PAY_EVIDENCE_PATH)
    parser.add_argument("--dry-run", action="store_true", help="report what would be written and write nothing")
    args = parser.parse_args((argv or sys.argv)[1:])

    try:
        loaded = load_executive_schedule(args.table)
    except Exception as error:  # pay_tables raises its own Unreadable
        print(f"refused: {error}")
        return 1
    fiscal_year = federal_fiscal_year_of(date.fromisoformat(str(loaded["table"]["effective"])))

    node_map, parent_map = index_tree(load_base_graph(args.base_graph))
    try:
        records, report = build_records(node_map, parent_map, loaded, fiscal_year=fiscal_year)
    except Unreadable as error:
        print(f"refused: {error}")
        return 1

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
                f"{node_id}: classified {state!r}; no document here states this figure for this post, "
                "so nothing from this source may be more than a proxy"
            )
            continue
        out["financialEvidenceStatus"] = state
        # Everything the exporter publishes rides on the record; the validator
        # returns its own projection, so the module's fields are re-attached.
        for key, value in record.items():
            out.setdefault(key, value)
        validated[node_id] = out

    report["validated"] = len(validated)
    report["rejected"] = rejected
    report["conflicts"] = fe.detect_conflicts(validated.values())
    report["double_counted"] = fe.double_counted(validated.values())

    print(f"{loaded['table']['table']}, {loaded['table']['effectiveText']}, fetched {loaded['fetched_at']}")
    print(f"establishments 5 U.S.C. 401(1) names: {len(report['establishments'])}")
    print(f"Inspector General nodes considered: {report['inspectorGeneralNodesConsidered']}   "
          f"priced {report['priced']} ({report['pricedByReviewedRow']} GAO rows, "
          f"{report['pricedInspectorsGeneral']} Inspectors General of an establishment)   validated {report['validated']}")
    for node_id, record in sorted(records.items()):
        print(f"    PRICED   {node_id}  {record['rateText']}")
        print(f"             {record['derivation']}")
    for node_id, reason in report["refused"].items():
        print(f"    refused: {node_id} — {reason}")
    kinds: dict[str, int] = {}
    for reason in report["notPriced"].values():
        key = reason.split(": ", 1)[1][:60] if ": " in reason else reason[:60]
        kinds[key] = kinds.get(key, 0) + 1
    print(f"not priced: {len(report['notPriced'])} Inspector General nodes, none of them an establishment's")
    for key, count in sorted(kinds.items(), key=lambda kv: -kv[1]):
        print(f"    {count:>3}  {key}…")
    for line in rejected[:20]:
        print(f"  REJECTED {line}")
    print(
        f"A GAO record rests on 2 official documents ({document_strength_percent(2)}%), an Inspector General's on 3 "
        f"({document_strength_percent(3)}%), on {STRENGTH_SCALE}; 0 of them state the figure for the post."
    )
    print("Every record is scoped 'proxy'. Basic pay is not the node's cost, and nothing here writes a source URL onto a node.")

    if args.dry_run:
        return 0
    if not validated:
        print("nothing validated; not writing")
        return 1
    write_json_file(args.out, {
        "_note": (
            "Derived by scripts/derive_tier_reference_pay_evidence.py from committed U.S. Code sections and "
            "OPM's Salary Table No. 2026-EX. No document states these figures for these posts: a statute sets "
            "each post's pay by reference to an Executive Schedule level (the Inspector General Act adds 3 "
            "percent) and the table prices the level. Never a cost; never a source that the post exists."
        ),
        "source": report["source"],
        "report": report,
        "nodes": validated,
    })
    print(f"wrote {len(validated)} records -> {_relative(args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
