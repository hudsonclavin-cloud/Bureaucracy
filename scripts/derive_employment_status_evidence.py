#!/usr/bin/env python
"""Derive the employer claim for the posts of DOE's sixteen contractor-operated
national laboratories.

    python scripts/derive_employment_status_evidence.py --dry-run
    python scripts/derive_employment_status_evidence.py    # writes data/verification/employment_status_evidence.json

Reads three committed documents (NETL's page on its operating model, DOE's
index of its laboratories, and 48 CFR part 970 as GPO prints it), recomputes
each digest from the bytes, re-finds every quote, re-checks the reviewed
laboratory table against DOE's index, and writes one record per Position
directly under one of the sixteen laboratory nodes. NETL's posts are federal
and get nothing. See `data_pipeline/verification/employment_status.py`.
Nothing here fetches.
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
from data_pipeline.verification.employment_status import (  # noqa: E402
    DEFAULT_EVIDENCE_PATH,
    Unreadable,
    build_records,
)

DEFAULT_BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--out", type=Path, default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument("--read-on", default=date.today().isoformat(), help="the date the documents are read against (default: today)")
    parser.add_argument("--dry-run", action="store_true", help="report what would be written and write nothing")
    args = parser.parse_args((argv or sys.argv)[1:])

    node_map, parent_map = index_tree(load_base_graph(args.base_graph))
    try:
        records, report = build_records(node_map, parent_map, read_on=str(args.read_on))
    except Unreadable as error:
        print(f"refused: {error}")
        return 1

    for role, info in report["documents"].items():
        print(f"document ({role}): {info['url']} sha256 {info['sha256'][:12]}")
    print(f"DOE's index labels {len(report['laboratoryLabels'])} laboratories")
    print(f"reviewed contractor-operated laboratories: {report['reviewedLaboratories']}, refused: {len(report['laboratoriesRefused'])}")
    for lab_id, reason in report["laboratoriesRefused"].items():
        print(f"  refused {lab_id}: {reason}")
    print(f"posts with the block: {report['postsWithTheBlock']}; refused: {len(report['postsRefused'])}; NETL posts left alone: {report['netlPostsLeftAlone']}")
    for post_id, reason in report["postsRefused"].items():
        print(f"  refused {post_id}: {reason}")
    if args.dry_run:
        return 0
    payload = {
        "_note": (
            "Written by scripts/derive_employment_status_evidence.py from three committed documents; "
            "see data_pipeline/verification/employment_status.py. Not evidence that a post exists, "
            "never a cost and never a rate of pay."
        ),
        "report": report,
        "nodes": records,
    }
    write_json_file(args.out, payload)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
