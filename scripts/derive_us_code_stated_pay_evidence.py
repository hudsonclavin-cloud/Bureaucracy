#!/usr/bin/env python
"""Derive pay evidence for an office whose salary a section of the U.S. Code
states in dollars: the President, 3 U.S.C. 102.

    python scripts/derive_us_code_stated_pay_evidence.py --dry-run
    python scripts/derive_us_code_stated_pay_evidence.py    # writes data/verification/us_code_stated_pay_evidence.json

Reads one committed section (GPO's rendering of the 2024 edition on
www.govinfo.gov), re-finds the sentence in its operative text, and writes one
record per reviewed row. See `data_pipeline/verification/us_code_stated_pay.py`.
Every record is validated against its own node by
`financial_evidence.validate_record` before it is written. Nothing here fetches.
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
from data_pipeline.verification.us_code_stated_pay import (  # noqa: E402
    DEFAULT_PAY_EVIDENCE_PATH,
    STATED_RATE_ROWS,
    Unreadable,
    build_records,
)

DEFAULT_BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--out", type=Path, default=DEFAULT_PAY_EVIDENCE_PATH)
    parser.add_argument("--read-on", default=date.today().isoformat(), help="the date the sections are read against (default: today)")
    parser.add_argument("--dry-run", action="store_true", help="report what would be written and write nothing")
    args = parser.parse_args((argv or sys.argv)[1:])

    node_map, _ = index_tree(load_base_graph(args.base_graph))
    read_year = int(str(args.read_on)[:4])
    try:
        records, report = build_records(node_map, read_year=read_year, read_on=str(args.read_on))
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
            rejected.append(f"{node_id}: classified {state!r}; a reviewed identification is a proxy and nothing more")
            continue
        out["financialEvidenceStatus"] = state
        for key, value in record.items():
            out.setdefault(key, value)
        validated[node_id] = out

    report["validated"] = len(validated)
    report["rejected"] = rejected
    report["conflicts"] = fe.detect_conflicts(validated.values())
    report["double_counted"] = fe.double_counted(validated.values())

    for name, section in report["sections"].items():
        print(f"section: {name}  {section['url']}  fetched {section['fetched_at']}")
    print(f"reviewed rows {report['reviewedRows']}  priced {report['priced']}  validated {report['validated']}")
    for node_id, record in sorted(records.items()):
        print(f"    PRICED   {node_id}  {record['rateText']}  ({record['statute']}, {record['edition']})")
        print(f"             not published: {record['notPublished']}")
    for node_id, reason in report["refused"].items():
        print(f"    refused: {node_id} — {reason}")
    for line in rejected[:20]:
        print(f"  REJECTED {line}")
    print("Every record is scoped 'proxy': the section names the office and which node of this graph that office is "
          "stays a reviewed identification. Basic pay is not the node's cost, and nothing here writes a source URL onto a node.")

    if args.dry_run:
        return 0
    if not validated:
        print("nothing validated; refusing to write an empty evidence file")
        return 1
    store = {
        "_note": (
            "Derived by scripts/derive_us_code_stated_pay_evidence.py from committed sections of the United States "
            "Code that state an office's salary in dollars: 3 U.S.C. 102 for the President ($400,000 a year; the "
            "$50,000 expense allowance in the same sentence is not compensation and is not published). One record per "
            f"reviewed row ({len(STATED_RATE_ROWS)}), each re-found in the section's operative text on every run. "
            "Basic pay is not the node's cost. Regenerate by re-running the script; never edit by hand."
        ),
        "source": {"kind": "us_code_stated_rate", "sections": report["sections"], "readOn": str(args.read_on)},
        "report": report,
        "nodes": validated,
    }
    write_json_file(args.out, store)
    print(f"wrote {len(validated)} records -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
