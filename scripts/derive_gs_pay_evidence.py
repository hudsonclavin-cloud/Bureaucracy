#!/usr/bin/env python
"""Derive pay RANGES from OPM's General Schedule, SES and SL/ST salary tables.

    python scripts/derive_gs_pay_evidence.py --dry-run
    python scripts/derive_gs_pay_evidence.py          # writes data/verification/grade_pay_evidence.json

Reads four committed fixtures and one evidence file, and joins them:

- `tests/fixtures/opm/pay/general_schedule_2026.pdf`, OPM's Salary Table
  2026-GS as the publisher renders it to PDF -- the rendering that prints the
  currency mark, once, on grade 1 -- and `general_schedule_2026.html`, the same
  table as a web page, which must agree with it on all 150 figures or nothing
  is read;
- `senior_executive_service_2026.html` and `senior_level_2026.html`, Salary
  Tables No. 2026-ES and 2026-SL/ST, each a two-row statement of a pay
  system's minimum and maximum;
- `data/verification/position_evidence.json`, derived from the PLUM archive of
  the PREVIOUS administration (January 21, 2021 - January 20, 2025), which
  says which posts were filed on which pay plan and, for the General Schedule,
  at which grade -- and states no rate for these.

No table states a rate for any post. A GS grade is ten steps; a pay system is
a band. So every record here is a RANGE with a minimum and a maximum, scoped
`proxy` because the table names a grade or a system rather than the unit, and
graded `partial` by `financial_evidence.classify` -- there is no route by which
one becomes `verified`. A GS range is BASE pay, before the locality adjustment
the table does not state, and the record says so in words. Where the archive
itself prints a rate for a post, that rate wins and no range is written.

Each bound of each range is validated against its own node by
`financial_evidence.validate_record` before anything is written. Nothing here
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
from data_pipeline.verification.gs_pay import (  # noqa: E402
    DEFAULT_EVIDENCE_PATH,
    DEFAULT_GS_HTML,
    DEFAULT_GS_PDF,
    DEFAULT_SES_HTML,
    DEFAULT_SLST_HTML,
    KINDS,
    Unreadable,
    build_records,
    load_all_tables,
)
from data_pipeline.verification.plum_current import (  # noqa: E402
    DEFAULT_EVIDENCE_PATH as DEFAULT_PLUM_CURRENT_EVIDENCE_PATH,
    combine_listings,
    load_current_listings,
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
    parser.add_argument("--gs-pdf", type=Path, default=DEFAULT_GS_PDF, help="verbatim GS table, PDF rendering (cited)")
    parser.add_argument("--gs-html", type=Path, default=DEFAULT_GS_HTML, help="verbatim GS table, HTML rendering (corroborates)")
    parser.add_argument("--ses-html", type=Path, default=DEFAULT_SES_HTML, help="verbatim SES structure table")
    parser.add_argument("--slst-html", type=Path, default=DEFAULT_SLST_HTML, help="verbatim SL/ST structure table")
    parser.add_argument("--positions", type=Path, default=DEFAULT_POSITION_EVIDENCE_PATH,
                        help="position evidence, which supplies the pay plan and grade each post was reported on")
    parser.add_argument("--current-listings", type=Path, default=DEFAULT_PLUM_CURRENT_EVIDENCE_PATH,
                        help="current PLUM export evidence; where it lists a post its pay plan and grade are used instead of the archive's")
    parser.add_argument("--out", type=Path, default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument("--dry-run", action="store_true", help="report what would be written and write nothing")
    args = parser.parse_args((argv or sys.argv)[1:])

    try:
        tables = load_all_tables(gs_pdf=args.gs_pdf, gs_html=args.gs_html, ses_html=args.ses_html, slst_html=args.slst_html)
    except Unreadable as error:
        print(f"refused: {error}")
        return 1

    archive_listings = load_position_evidence(args.positions)
    current_listings = load_current_listings(args.current_listings)
    listings, listing_stats = combine_listings(archive_listings, current_listings)
    if not listings:
        print(f"no position evidence at {_relative(args.positions)} or {_relative(args.current_listings)}; nothing can be ranged")
        return 1
    print(f"listings: {listing_stats['from_current']} from the current export, {listing_stats['from_archive']} from the archive; "
          f"{listing_stats['either_reports_a_rate']} refused because a listing states a rate")

    records, report = build_records(listings, tables)

    # Every bound of every record is bound to its node and handed to the
    # red-teamed validator. A producer that skipped it would be a second,
    # unreviewed path to the same fields.
    node_map, _ = index_tree(load_base_graph(args.base_graph))
    validated: dict[str, dict] = {}
    rejected: list[str] = []
    for node_id, record in sorted(records.items()):
        node = node_map.get(node_id)
        if node is None:
            rejected.append(f"{node_id}: not in the base graph")
            continue
        bounds_out: dict[str, dict] = {}
        try:
            for name, bound in record["bounds"].items():
                out = fe.validate_record(bound, node)
                state = fe.classify(out)
                if state != "partial":
                    raise fe.Rejected(f"{node_id}: {name} classified {state!r}; a grade or a pay system is a proxy for a post and nothing more")
                out["financialEvidenceStatus"] = state
                bounds_out[name] = out
        except fe.Rejected as error:
            rejected.append(str(error))
            continue
        kept = dict(record)
        kept["bounds"] = bounds_out
        validated[node_id] = kept

    report["validated"] = len(validated)
    report["rejected"] = rejected

    for kind in KINDS:
        table = report["tables"][kind]
        print(f"{kind:28s} {table['table']}  {table['effectiveText']}  fetched {table['retrievedAt']}")
    gs = tables["general_schedule_grade"]["table"]
    print("  GS grades: " + "  ".join(f"{g} ${r['minimum']:,.0f}-${r['maximum']:,.0f}" for g, r in gs["grades"].items()))
    for kind in ("senior_executive_service", "senior_level"):
        for row in tables[kind]["table"]["rows"]:
            print(f"  {kind}: {row['label']}  ${row['minimum']:,.0f}-${row['maximum']:,.0f}")
        for note in tables[kind]["table"]["footnotes"]:
            print(f"  footnote carried: {note}")
    print(f"listings considered {report['listings_considered']}  ranged {report['ranged']}  validated {report['validated']}")
    print(f"  by kind: {report['ranged_by_kind']}")
    print(f"  GS by grade: {report['ranged_by_grade']}")
    print("  refused:")
    for reason, count in report["refused"].items():
        print(f"    {count:5d}  {reason}")
    for line in rejected[:20]:
        print(f"  REJECTED {line}")
    print("Every record is a range and a proxy: the table names a grade or a pay system, not a unit, so none is ever 'verified'.")
    print("A GS range is base pay before locality; the pay plan is the previous administration's archive; the table is effective January 2026.")

    if args.dry_run:
        return 0
    if not validated:
        print("nothing validated; refusing to write an empty evidence file")
        return 1

    store = {
        "_note": (
            "Derived by scripts/derive_gs_pay_evidence.py by joining OPM's 2026 salary tables to "
            "data/verification/position_evidence.json, which is derived from the PLUM archive of the PREVIOUS "
            "administration (January 21, 2021 - January 20, 2025). No table here states a rate for any post: "
            "Salary Table 2026-GS prints ten steps per grade, and Salary Tables No. 2026-ES and 2026-SL/ST print "
            "a pay system's minimum and maximum, so every record is a RANGE, scoped 'proxy' because the table "
            "names a grade or a system rather than the unit, and graded 'partial' - no record here is ever "
            "'verified'. A General Schedule range is BASE pay before the locality adjustment the table does not "
            "state. The GS record cites the PDF rendering, the one that prints the currency mark (on grade 1, "
            "once per column, which is the fourth and narrowest scale rule financial_evidence grants); the HTML "
            "rendering is committed beside it and must agree on all 150 figures. Where the archive itself prints "
            "a rate for a post, that rate wins and no range is written. Basic pay is not the node's cost. "
            "Regenerate by re-running the script; never edit by hand."
        ),
        "sources": report["tables"],
        "listingSource": {
            "kind": "opm_plum_archive_or_current_export",
            "file": _relative(args.positions),
            "current_export_file": _relative(args.current_listings),
            "rule": "the current export's listing supplies the pay plan and grade where it lists the post; the archive's "
                    "otherwise; each record's listingClaim.source names which",
            **listing_stats,
        },
        "report": report,
        "nodes": validated,
    }
    write_json_file(args.out, store)
    print(f"wrote {len(validated)} records -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
