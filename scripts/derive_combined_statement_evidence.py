"""Derive the Combined Statement's FY2025 net outlays for the reviewed accounts.

    python scripts/derive_combined_statement_evidence.py --dry-run   # what would apply; writes nothing
    python scripts/derive_combined_statement_evidence.py             # writes data/verification/combined_statement_evidence.json

Reads the Legislative Branch chapter (c01) of the Combined Statement of
Receipts, Outlays, and Balances, Part Three, as both its XLSX export and its
PDF, and the September 2025 Monthly Treasury Statement, Table 5, all verbatim
and with every digest recomputed from the bytes. The chapter's own total must
equal the statement's Legislative Branch line to the cent (the scale rule the
owner granted on 2026-10-21, CURATION.md Sec 22.7) before anything is read.

Each record is one reviewed row of `combined_statement.REVIEWED_ROWS`: every
account the chapter prints for the unit, each figure the one printed cell the
chapter gives it (and found verbatim in the PDF), summed where there are two.
It is a sourced figure of another kind -- a completed year's net outlays -- and
never the cost: the exporter stamps it beside the estimate under its own
heading (CURATION.md Sec 22.8).
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.exporter.build_graph import DEFAULT_BASE_GRAPH, index_tree, load_base_graph  # noqa: E402
from data_pipeline.json_io import write_json_file  # noqa: E402
from data_pipeline.verification.combined_statement import (  # noqa: E402
    DEFAULT_EVIDENCE_PATH,
    build_records,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--out", type=Path, default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv[1:] if argv else None)

    node_map, parent_map = index_tree(load_base_graph(args.base_graph))
    records, report = build_records(node_map, parent_map)
    scale = report["scale"]
    print(f"scale: {scale['chapterTotal']['label']} {scale['chapterTotal']['amountRaw']} = "
          f"{scale['statementLine']['label']} {scale['statementLine']['amountRaw']} "
          f"({scale['statementLine']['recordDate']})")
    print(f"{report['published']} of {report['rowsReviewed']} reviewed rows publish:")
    for node_id, record in sorted(records.items()):
        mark = "  [filed in another Treasury section]" if record["treasurySection"]["filedInAnotherSection"] else ""
        print(f"  {node_id:44s} ${record['amount']:>16,.2f}  {record['componentCount']} account(s){mark}")
        if record["componentCount"] > 1:
            for component in record["components"]:
                print(f"      {component['printed']:>16s}  {component['account']}")
    for reason, ids in sorted(report["refused"].items()):
        print(f"  refused, {reason}: {ids}")
    print("\nA completed year's net outlays as the Treasury prints them for the account(s). Published")
    print("beside the estimate under its own heading, never as the cost.")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0
    store = {
        "_note": (
            "Derived by scripts/derive_combined_statement_evidence.py from the Combined Statement's "
            "Legislative Branch chapter (c01, XLSX and PDF) and the September 2025 Monthly Treasury Statement, "
            "committed verbatim under tests/fixtures/ with their digests. Each record is one reviewed row: every "
            "account the chapter prints for the unit, summed. It is not a cost and the exporter never writes it "
            "into one."
        ),
        "source": {"kind": "combined_statement",
                   "derivedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
        "report": report,
        "nodes": records,
    }
    write_json_file(args.out, store)
    print(f"\nwrote {len(records)} records -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
