"""Derive audited net cost from Treasury's Statement of Net Cost.

    python scripts/derive_net_cost_evidence.py --dry-run   # what would apply; writes nothing
    python scripts/derive_net_cost_evidence.py             # writes data/verification/net_cost_evidence.json

Reads the committed API response at
`tests/fixtures/treasury/net_cost/` (verbatim, digest recomputed from the bytes
before it is read) and matches each reporting entity to an organisation by
canonical-name equality -- one row to one node or nothing.

What it produces is NOT a cost and is never written into one. Audited net cost
is accrual accounting for a fiscal year that has ended; the graph's measured
figure is the Monthly Treasury Statement's net outlays for the year to date.
Different basis, different period. The exporter stamps this beside the cost
under its own heading, the way `usaspendingOutlays` is stamped.
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
from data_pipeline.verification.net_cost import (  # noqa: E402
    DEFAULT_FIXTURE,
    SOURCE,
    build_records,
    load_statement,
)

DEFAULT_OUT = PROJECT_ROOT / "data" / "verification" / "net_cost_evidence.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv[1:] if argv else None)

    node_map, _ = index_tree(load_base_graph(args.base_graph))
    statement = load_statement(args.fixture)
    records, report = build_records(node_map, statement)

    print(f"  statement           : FY{report['fiscal_year']}, {report['rows_considered']} reporting entities")
    print(f"  applied             : {report['applied']}")
    for reason, count in sorted(report["refused"].items()):
        print(f"  refused, {reason:34s}: {count}")
        for detail in report["refused_detail"][reason][:6]:
            print(f"      {detail}")
    print(f"  document sha256     : {report['documentSha256'][:16]}...")
    print("\nAudited net cost is accrual accounting for a fiscal year that has ENDED, and the")
    print("graph's measured figure is net outlays for the year to date. Different basis and")
    print("different period: it is published beside the cost, under its own heading, never as it.")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0

    store = {
        "_note": (
            "Derived by scripts/derive_net_cost_evidence.py from Treasury's Statement of Net Cost, "
            "committed verbatim under tests/fixtures/treasury/net_cost/ with its digest. Each record "
            "is an AUDITED figure -- the only cost in this project checked by somebody outside the "
            "reporting agency -- on an accrual basis for a fiscal year that has ended. It is not the "
            "unit's outlays and not the same period as the graph's anchor, so the exporter stamps it "
            "beside the cost and never over it. Rows that name no unit of government ('Total', 'All "
            "other entities') are refused rather than matched to the nearest node."
        ),
        "source": {"kind": SOURCE, "derivedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "fixture": str(args.fixture.relative_to(PROJECT_ROOT))},
        "report": report,
        "nodes": records,
    }
    write_json_file(args.out, store)
    print(f"\nwrote {len(records)} records -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
