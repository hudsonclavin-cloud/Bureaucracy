#!/usr/bin/env python
"""USAspending File A gross outlays for the organisations the phase-2
crosswalk names, read out of the committed fixtures and validated.

    python scripts/derive_usaspending_evidence.py --dry-run   # what would be applied and refused; writes nothing
    python scripts/derive_usaspending_evidence.py             # writes data/verification/usaspending_evidence.json

Reads `data/audit/nominations/cost-cost-usaspending.jsonl` (the proposals),
`tests/fixtures/usaspending/` (the API's own lists, verbatim, digests checked)
and the publisher's Data Dictionary crosswalk (the scale statement). A
proposal becomes a record only where the API's name and the graph's reduce
to the same canonical key; the rest are reported as awaiting review with
the confidence the proposer gave them. Nothing here touches the graph: the
exporter applies the records, beside the Treasury figure and never over it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.exporter.build_graph import index_tree, load_base_graph  # noqa: E402
from data_pipeline.json_io import write_json_file  # noqa: E402
from data_pipeline.verification.usaspending import (  # noqa: E402
    BASIS,
    DEFAULT_CROSSWALK_PATH,
    DEFAULT_EVIDENCE_PATH,
    SOURCE,
    Unreadable,
    build_records,
    load_crosswalk,
    load_dictionary,
    now_iso,
)

DEFAULT_BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"


def print_report(report: dict, records: dict) -> None:
    print(f"  crosswalk identifiers : {report['crosswalk_identifiers']}")
    print(f"  applied               : {report['applied']}  {report['applied_by_level']}")
    for reason, count in report["refused"].items():
        print(f"  refused, {reason:34s}: {count}")
        for item in report["refused_detail"][reason][:12]:
            print(f"      {item['nodeId']}  key={item['key']}  confidence={item['confidence']}  {item.get('detail') or ''}"[:160])
    print(f"  dictionary            : {report['dictionary']['file']}  sha256 {report['dictionary']['sha256'][:12]}...  "
          f"{report['dictionary']['element']} -> {report['dictionary']['field']}")
    states = {}
    for record in records.values():
        states[record.get("financialEvidenceStatus")] = states.get(record.get("financialEvidenceStatus"), 0) + 1
    print(f"  financialEvidenceStatus: {states}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--crosswalk", type=Path, default=DEFAULT_CROSSWALK_PATH)
    parser.add_argument("--out", type=Path, default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument("--dry-run", action="store_true", help="report; write nothing")
    args = parser.parse_args((argv or sys.argv)[1:])

    root = load_base_graph(args.base_graph)
    node_map, _ = index_tree(root)
    try:
        dictionary = load_dictionary()
    except Unreadable as error:
        print(f"refused: {error}")
        return 1
    crosswalk = load_crosswalk(args.crosswalk)
    records, report = build_records(node_map, crosswalk, dictionary=dictionary)
    print_report(report, records)
    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0
    store = {
        "_note": (
            f"Derived by scripts/derive_usaspending_evidence.py from USAspending's own agency and bureau lists, "
            f"committed verbatim under tests/fixtures/usaspending/ with their digests, for the organisations the "
            f"phase-2 crosswalk ({args.crosswalk.relative_to(PROJECT_ROOT) if args.crosswalk.is_relative_to(PROJECT_ROOT) else args.crosswalk}) "
            f"names by a key the API prints for the same canonical name. Each record is File A {BASIS} -- "
            f"gross, fiscal-year-to-date as of the fetch, and a different measure from the Monthly Treasury "
            f"Statement's net line the graph publishes as a node's cost; the exporter stamps it beside that "
            f"figure and never over it. A proposed key whose name the API spells differently is not applied "
            f"and is listed under report.refused_detail.awaiting_review_name_not_equal with its confidence."
        ),
        "source": {"kind": SOURCE, "basis": BASIS, "derivedAt": now_iso(), "fixtures": "tests/fixtures/usaspending/"},
        "dictionary": dictionary,
        "report": report,
        "nodes": records,
    }
    write_json_file(args.out, store)
    print(f"\nwrote {len(records)} records -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
