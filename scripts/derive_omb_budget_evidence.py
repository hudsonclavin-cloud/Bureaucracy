"""Derive budget authority and outlays from OMB's Public Budget Database.

    python scripts/derive_omb_budget_evidence.py --dry-run   # what would apply; writes nothing
    python scripts/derive_omb_budget_evidence.py             # writes data/verification/omb_budget_evidence.json

Reads the package committed at `tests/fixtures/omb/` (verbatim, digest
recomputed from the bytes before anything is read) and matches OMB's agencies
and bureaus to organisations by canonical-name equality, scoped so that a
bureau only reaches a node beneath its own agency's node.

**Only the last COMPLETED fiscal year is published.** The later columns of this
file are the President's request, not history, and the boundary is parsed out
of the package's own user's guide on every run rather than hard-coded -- so a
newer package cannot silently move an estimate into a field that reads as fact.

What it produces is NOT a cost and is never written into one. OMB's own guide
says its totals are "generally consistent with" the Monthly Treasury Statement
and then says why they are not identical; the period is a year that has ended,
where the graph's anchor is the year to date. The exporter stamps this beside
the cost under its own heading, the way `usaspendingOutlays` and
`auditedNetCost` are stamped.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.exporter.build_graph import DEFAULT_BASE_GRAPH, load_base_graph  # noqa: E402
from data_pipeline.json_io import write_json_file  # noqa: E402
from data_pipeline.verification.omb_budget import (  # noqa: E402
    DEFAULT_PACKAGE,
    SOURCE,
    build_records,
    load_database,
)

DEFAULT_OUT = PROJECT_ROOT / "data" / "verification" / "omb_budget_evidence.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv[1:] if argv else None)

    database = load_database(args.fixture)
    records, stats = build_records(database, load_base_graph(args.base_graph))

    print(f"  package             : {database['package']}")
    print(f"  last ACTUAL year    : FY{database['lastActualYear']}  "
          f"(the guide calls FY{database['firstEstimateYear']} the current year and "
          f"FY{database['budgetYear']} the budget year, both estimates)")
    print(f"  agencies            : {stats['agencies_matched']} matched of {stats['agencies']}")
    print(f"  bureaus             : {stats['bureaus_matched']} matched of {stats['bureaus']}")
    print(f"  records             : {len(records)}")
    for key in ("refused_agency_name_reaches_no_single_organisation",
                "refused_bureau_name_reaches_no_single_organisation",
                "refused_bureau_name_used_by_several_agencies",
                "refused_its_agency_matched_no_node",
                "refused_zero_on_both_measures"):
        print(f"  {key:56s}: {stats[key]}")
    disagreements = stats["refused_node_sits_outside_its_agencys_subtree"]
    print(f"  refused, OMB files it under a different parent than the graph: {len(disagreements)}")
    for item in disagreements:
        print(f"      OMB files {item['bureau']!r} under {item['agency']!r}; "
              f"the graph puts {item['nodeId']} elsewhere")
    print(f"  document sha256     : {database['sha256'][:16]}...")
    print("\nThis is a completed fiscal year on OMB's own basis, which its guide calls")
    print("'generally consistent with' the Monthly Treasury Statement and not identical to it.")
    print("It is published beside the cost, under its own heading, and never as the cost.")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0

    store = {
        "_note": (
            "Derived by scripts/derive_omb_budget_evidence.py from OMB's Public Budget Database, "
            "committed verbatim under tests/fixtures/omb/ with its digest. Each record carries the "
            "budget authority and outlays OMB reports for a unit in the last COMPLETED fiscal year; "
            "the estimate boundary is parsed from the package's own user's guide on every run, so an "
            "estimated year can never be published as an actual one. Figures are the publisher's "
            "thousands converted to dollars, and the publisher states that detail below millions is "
            "not available, so a figure is exact to the million and no further. It is not this "
            "graph's cost: different period, and OMB's own guide calls its totals only 'generally "
            "consistent with' the Monthly Treasury Statement."
        ),
        "source": {"kind": SOURCE, "package": database["package"],
                   "fiscalYear": database["lastActualYear"],
                   "url": database["url"], "documentSha256": database["sha256"],
                   "fetchedAt": database["fetchedAt"],
                   "derivedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "fixture": str(Path(args.fixture).relative_to(PROJECT_ROOT))},
        "report": {k: v for k, v in stats.items()},
        "nodes": records,
    }
    write_json_file(args.out, store)
    print(f"\nwrote {len(records)} records -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
