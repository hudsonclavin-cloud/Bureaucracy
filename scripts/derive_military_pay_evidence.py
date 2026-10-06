"""Derive military basic-pay evidence from Schedule 8 of the annual pay-adjustment
order, joined to the statutes that fix a post's grade.

    python scripts/derive_military_pay_evidence.py --dry-run
    python scripts/derive_military_pay_evidence.py    # writes data/verification/military_pay_evidence.json

Reads committed files and fetches nothing: the note to 5 U.S.C. 5332
(Executive Order 14368 with Schedule 8, "Pay of the Uniformed Services"),
37 U.S.C. 201 (general/admiral is pay grade O-10), and the Title 10 and Title
14 sections that fix the grade of seventeen posts in so many words.

**No document states any of these ANNUAL figures.** Schedule 8 prints basic pay
by the month; the figure published is twelve times the monthly rate, arithmetic
the record carries in the open beside the monthly figure as printed and the
count of documents it rests on. The senior enlisted advisers are priced from the
schedule's own footnote, which names each post and prints its monthly rate. See
`data_pipeline/verification/military_pay.py`.

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
from data_pipeline.verification.military_pay import (  # noqa: E402
    DEFAULT_PAY_EVIDENCE_PATH,
    STRENGTH_SCALE,
    Unreadable,
    build_records,
    document_strength_percent,
    load_schedule_8,
)
from data_pipeline.verification.pay_tables import federal_fiscal_year_of  # noqa: E402
from data_pipeline.verification.us_code_pay_schedules import DEFAULT_SCHEDULE_HTML  # noqa: E402

DEFAULT_BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"


def _relative(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--schedule", type=Path, default=DEFAULT_SCHEDULE_HTML,
                        help="verbatim note to 5 U.S.C. 5332 carrying Schedule 8")
    parser.add_argument("--out", type=Path, default=DEFAULT_PAY_EVIDENCE_PATH)
    parser.add_argument("--dry-run", action="store_true", help="report what would be written and write nothing")
    args = parser.parse_args((argv or sys.argv)[1:])

    try:
        loaded = load_schedule_8(args.schedule)
    except Unreadable as error:
        print(f"refused: {error}")
        return 1
    schedule = loaded["schedule"]
    fiscal_year = federal_fiscal_year_of(date(int(schedule["year"]), 1, 1))

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
                f"{node_id}: classified {state!r}; no document here states this annual figure for this post, "
                "so nothing from this source may be more than a proxy"
            )
            continue
        out["financialEvidenceStatus"] = state
        for key, value in record.items():
            out.setdefault(key, value)
        validated[node_id] = out

    report["validated"] = len(validated)
    report["rejected"] = rejected
    report["conflicts"] = fe.detect_conflicts(validated.values())
    report["double_counted"] = fe.double_counted(validated.values())

    print(f"{schedule['label']} {schedule['effective']}, fetched {loaded['fetched_at']}")
    print(f"officer rows read in the Over 20–Over 40 block: {', '.join(report['officerRowsRead'])}; "
          f"flat (one figure in every populated cell): {', '.join(report['flatOfficerRows']) or 'none'}")
    print(f"cap footnote prints {report['capFootnote']['monthlyAsPrinted']} per month; the O-10 row prints "
          f"${schedule['officerRows']['O-10']['flatAmountRaw']}")
    print(f"senior enlisted footnote: {report['seniorEnlistedFootnote']['monthlyAsPrinted']} per month for "
          f"{len(report['seniorEnlistedFootnote']['items'])} printed items; unmatched titles: "
          f"{', '.join(report['footnoteTitlesUnmatched']) or 'none'}")
    print(f"grade rows {report['gradeRows']}   priced {report['priced']} ({report['pricedByGrade']} by a grade a "
          f"statute fixes, {report['pricedByFootnote']} named in the footnote)   validated {report['validated']}")
    for node_id, record in sorted(records.items()):
        print(f"    PRICED   {node_id}  {record['rateText']} a year ({record['monthly']['text']})")
        print(f"             {record['derivation'][:220]}")
    for node_id, reason in report["refused"].items():
        print(f"    refused: {node_id} — {reason}")
    for node_id, reason in report["notPriced"].items():
        print(f"    not priced: {node_id} — {reason[:160]}")
    for line in rejected[:20]:
        print(f"  REJECTED {line}")
    print(
        f"A grade-route record rests on 3 official documents ({document_strength_percent(3)}%), a footnote-route "
        f"record on 1 ({document_strength_percent(1)}%), on {STRENGTH_SCALE}; 0 of them state the annual figure "
        "(Schedule 8 prints monthly rates, and the annual figure is twelve times the printed one)."
    )
    print("Every record is scoped 'proxy'. Basic pay is not the node's cost, and nothing here writes a source URL onto a node.")

    if args.dry_run:
        return 0
    if not validated:
        print("nothing validated; not writing")
        return 1
    write_json_file(args.out, {
        "_note": (
            "Derived by scripts/derive_military_pay_evidence.py from the committed note to 5 U.S.C. 5332 "
            "(Executive Order 14368, Schedule 8: Pay of the Uniformed Services), 37 U.S.C. 201 and the Title 10 "
            "and Title 14 sections that fix each post's grade. No document states these annual figures: Schedule 8 "
            "prints monthly basic pay, and each figure is twelve times the printed monthly rate, arithmetic the "
            "record carries in the open. Never a cost; never a source that the post exists."
        ),
        "source": report["source"],
        "report": report,
        "nodes": validated,
    })
    print(f"wrote {len(validated)} records -> {_relative(args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
