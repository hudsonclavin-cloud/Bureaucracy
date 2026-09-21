#!/usr/bin/env python
"""Derive position evidence from OPM's CURRENT PLUM export, exactly as fetched.

    python scripts/derive_plum_current_evidence.py --dry-run
    python scripts/derive_plum_current_evidence.py            # writes data/verification/plum_current_evidence.json

Reads the PLUM Reporting export committed verbatim at
tests/fixtures/opm/plum/escs_pbpub_download-data.csv -- the file OPM's PLUM
Data page serves from escs.opm.gov, fetched 2026-09-21 (docs/NETWORK_ACCESS.md
§12) -- recomputes its digest before reading a row, and matches its agencies
and organisations to the curated graph's organisation nodes and each matched
organisation's position titles to the position nodes beneath it: by canonical
name, one name to one node or nothing, never across organisations, exactly as
scripts/derive_position_evidence.py does for the archive of the previous
administration. Only `Filled` and `Vacant` rows are read; `Historical` rows
are counted and never read. The two name columns and the unique-ID column are
never read at all.

Two kinds of record are written: one listing per matched position saying what
the export lists (title, agency, organisation, status, appointment type, pay
plan, level or rate), and -- where the row prints a rate of basic pay -- one
financial-evidence record per position, validated against its node by
`financial_evidence.validate_record`, scoped `proxy` and graded `partial`
because a row is an incumbency and its figure is what the one listing under
this title is paid, not what the office pays. Zero is never written.

No negative records. The export is not complete for career positions, so a
position absent from it is not evidence of anything. Nothing here fetches.
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
from data_pipeline.verification.aliases import load_alias_table  # noqa: E402
from data_pipeline.verification.plum_current import (  # noqa: E402
    DEFAULT_EVIDENCE_PATH,
    DEFAULT_EXPORT_CSV,
    READ_COLUMNS,
    Unreadable,
    build_pay_records,
    load_plum_export,
    match_positions,
)

DEFAULT_BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"


def _relative(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--export", type=Path, default=DEFAULT_EXPORT_CSV,
                        help="verbatim PLUM export CSV (its .meta.json sibling supplies URL, fetch time and digest)")
    parser.add_argument("--out", type=Path, default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument("--dry-run", action="store_true", help="report the matches; write nothing")
    args = parser.parse_args((argv or sys.argv)[1:])

    try:
        export = load_plum_export(args.export)
    except Unreadable as error:
        print(f"refused: {error}")
        return 1
    root = load_base_graph(args.base_graph)
    node_map, parent_map = index_tree(root)
    # The reviewed alternative names the export may file an agency under.
    alias_table = load_alias_table(node_map=node_map, parent_map=parent_map)
    records, report = match_positions(export, node_map, parent_map, root_id=str(root.get("id") or ""),
                                      alias_table=alias_table)

    pay_records, pay_report = build_pay_records(records)
    validated: dict[str, dict] = {}
    rejected: list[str] = []
    for node_id, record in sorted(pay_records.items()):
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
            rejected.append(f"{node_id}: classified {state!r}; a row of the export is one listing's figure and nothing more")
            continue
        out["financialEvidenceStatus"] = state
        validated[node_id] = out
    pay_report["validated"] = len(validated)
    pay_report["rejected"] = rejected
    report["pay"] = pay_report
    placements = sum(1 for r in records.values() if (r.get("placement") or {}).get("status") == "listed")

    print(f"export {_relative(args.export)}  fetched {export['fetched_at']}  url {export['url']}")
    print(f"sha256 {export['sha256']}  (recomputed from the bytes on disk and equal to the fetch record)")
    print(f"columns read: {list(READ_COLUMNS)}  -- the name and unique-ID columns are never read")
    print(f"rows in file {report['rows_in_file']}  status {report['status_counts']}  historical rows not read {report['historical_rows_not_read']}")
    print(f"live rows {report['live_rows']}  listings after folding identical rows {report['listings_after_dedup']} "
          f"({report['folded_duplicates']} folds)  agencies {report['agencies']}  organisations {report['organizations']}  titles {report['titles']}")
    print(f"pay plans: {report['pay_plans']}")
    print(f"agencies matched {report['agencies_matched']} (of which {report['agencies_matched_by_scoped_prefix']} by the export's own "
          f"'<parent> - <unit>' form, {report['agencies_matched_by_alias']} through the reviewed alias table)  "
          f"unmatched {len(report['agencies_unmatched'])}  ambiguous {len(report['agencies_ambiguous'])}")
    print("  unmatched agencies by live rows:")
    for item in report["unmatched_agencies_top"][:25]:
        print(f"    {item['rows']:5d}  {item['agency']}")
    for item in report["agencies_ambiguous"][:10]:
        print("  ambiguous agency:", item)
    print(f"organisations matched {report['organizations_matched']} (of which the agency itself {report['organizations_of_agency']})  "
          f"unmatched {len(report['organizations_unmatched'])}  ambiguous {len(report['organizations_ambiguous'])}  "
          f"under an unmatched agency {report['organizations_under_unmatched_agency']}")
    print("  unmatched organisations sample:", [f"{o['agency']} / {o['organization']}" for o in report["organizations_unmatched"][:20]])
    for item in report["organizations_ambiguous"][:10]:
        print("  ambiguous organisation:", item)
    print(f"positions in graph {report['positions_in_graph']}  under a matched agency node {report['positions_under_matched_agency_node']}  "
          f"under a matched organisation {report['positions_under_matched_organization']}  matched {report['positions_matched']}  "
          f"with a rate printed {report['positions_with_a_rate']}  under an aliased agency {report['positions_under_an_aliased_agency']}  placements {placements}  "
          f"unmatched {report['positions_unmatched']}  shared title {len(report['positions_shared_title'])}  "
          f"alternatives ambiguous {len(report['positions_ambiguous_alternatives'])}  export title ambiguous {len(report['positions_title_ambiguous_in_export'])}")
    print(f"  matched by pay plan: {report['positions_by_pay_plan']}")
    for item in report["samples"]:
        print("  match:", item)
    for item in report["positions_title_ambiguous_in_export"][:10]:
        print("  export title ambiguous:", item)
    print("  unmatched titles, most frequent:", report["unmatched_titles_top"][:20])
    print(f"pay: {pay_report['priced']} rates built, {pay_report['validated']} validated, refused {pay_report['refused']}")
    for line in rejected[:20]:
        print(f"  REJECTED {line}")
    print("Every rate is a proxy graded partial: a row of the export is an incumbency, and its figure is what the one listing "
          "under this title is paid, not what the office pays. Nothing here is a cost.")
    print("No negative records: a position the export lacks is not evidence of anything.")
    if args.dry_run:
        return 0
    if not records:
        print("nothing matched; refusing to write an empty evidence file")
        return 1
    store = {
        "_note": (
            "Derived by scripts/derive_plum_current_evidence.py from OPM's CURRENT PLUM Reporting export "
            f"(escs.opm.gov, fetched {export['fetched_at']}, sha256 {export['sha256']}), the live counterpart of the "
            "previous administration's archive that position_evidence.json is derived from. Only Filled and Vacant "
            "rows are read; Historical rows are counted and never read; the two name columns and the unique-ID column "
            "are never read at all. Identical rows for one position are folded before matching. Each listing record "
            "says what the export lists for the position node and nothing else; exportFetchedAt is the file's fetch "
            "time. Each pay record is the rate of basic pay the export prints for the one listing under the title, "
            "validated by financial_evidence.validate_record, scoped proxy and graded partial: a row is an incumbency "
            "and its figure is not what the office pays. Zero is never written; nothing here is a cost. No record is "
            "written for a position the export lacks. Regenerate by re-running the script; never edit by hand."
        ),
        "source": {
            "kind": "opm_plum_current_export",
            "url": export["url"],
            "fetched_at": export["fetched_at"],
            "sha256": export["sha256"],
            "file": _relative(args.export),
            "columns_read": list(READ_COLUMNS),
        },
        "report": report,
        "nodes": records,
        "pay": validated,
    }
    write_json_file(args.out, store)
    print(f"wrote {len(records)} listings and {len(validated)} pay records -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
