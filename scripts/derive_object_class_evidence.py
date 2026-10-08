#!/usr/bin/env python
"""Where each matched agency's money goes, FY2025, by object class.

    python scripts/derive_object_class_evidence.py --dry-run   # report; writes nothing
    python scripts/derive_object_class_evidence.py             # writes data/verification/object_class_evidence.json

Reads the same phase-2 crosswalk `derive_usaspending_evidence.py` reads, takes
only its toptier keys that `usaspending.py`'s own name rule (or its reviewed
aliases) applies, and reads each agency's three committed object-class
fixtures under `tests/fixtures/usaspending/object_class/`. The exporter
stamps `spendingByKind` beside the cost and never in it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.exporter.build_graph import index_tree, load_base_graph  # noqa: E402
from data_pipeline.json_io import write_json_file  # noqa: E402
from data_pipeline.verification.object_class import DEFAULT_EVIDENCE_PATH, SOURCE, build_records  # noqa: E402
from data_pipeline.verification.usaspending import DEFAULT_CROSSWALK_PATH, load_crosswalk, now_iso  # noqa: E402

DEFAULT_BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--crosswalk", type=Path, default=DEFAULT_CROSSWALK_PATH)
    parser.add_argument("--out", type=Path, default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args((argv or sys.argv)[1:])
    node_map, _ = index_tree(load_base_graph(args.base_graph))
    records, report = build_records(node_map, load_crosswalk(args.crosswalk))
    print(f"  matched {report['matched']}, applied {report['applied']}, staff pay ${report['staffPayTotal']:,.2f}")
    for node_id, reason in report["refused"].items():
        print(f"  refused {node_id}: {reason}")
    for record in sorted(records.values(), key=lambda r: -r["staffPay"]["amount"]):
        print(f"  {record['nodeId']:70s} staff ${record['staffPay']['amount']:>16,.2f} "
              f"({record['staffPay']['share']:.1%} of ${record['totalObligations']:,.0f})")
    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0
    write_json_file(args.out, {
        "_note": ("Derived by scripts/derive_object_class_evidence.py from USAspending's FY2025 object-class "
                  "breakdowns, committed verbatim under tests/fixtures/usaspending/object_class/ with their "
                  "digests, for the toptier agencies usaspending.py applies. Obligations by what the money was "
                  "spent on; never the node's cost."),
        "source": {"kind": SOURCE, "derivedAt": now_iso()},
        "report": report,
        "nodes": records,
    })
    print(f"\nwrote {len(records)} records -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
