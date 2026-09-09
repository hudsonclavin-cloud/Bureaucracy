#!/usr/bin/env python
"""Derive evidence records from a verbatim official directory.

    python scripts/derive_directory_evidence.py --dry-run
    python scripts/derive_directory_evidence.py            # writes data/verification/directory_evidence.json

Reads the Federal Register agency directory exactly as fetched
(tests/fixtures/directories/federal_register_agencies.json by default),
matches its entries to the curated graph's organisations by canonical name
— one entry to one node, or nothing — and writes one record per node saying
what the directory says: the name as listed, the parent as listed, the
entry's page. The exporter applies them beside the page evidence. Nothing
here fetches; the directory's own fetch time is the record's date.
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
from data_pipeline.verification.congress import load_senate_committees, match_senate  # noqa: E402
from data_pipeline.verification.directories import (  # noqa: E402
    DEFAULT_DIRECTORY_EVIDENCE_PATH,
    FR_DIRECTORY_URL,
    load_directory_file,
    match_federal_register,
)

DEFAULT_BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"
DEFAULT_FR = PROJECT_ROOT / "tests" / "fixtures" / "directories" / "federal_register_agencies.json"
DEFAULT_SENATE = PROJECT_ROOT / "tests" / "fixtures" / "directories" / "senate"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--federal-register", type=Path, default=DEFAULT_FR, help="verbatim agencies.json fetch")
    parser.add_argument("--senate-dir", type=Path, default=DEFAULT_SENATE, help="directory of verbatim Senate committee XML + meta files; pass an empty dir to skip")
    parser.add_argument("--out", type=Path, default=DEFAULT_DIRECTORY_EVIDENCE_PATH)
    parser.add_argument("--dry-run", action="store_true", help="report the matches; write nothing")
    args = parser.parse_args((argv or sys.argv)[1:])

    root = load_base_graph(args.base_graph)
    node_map, parent_map = index_tree(root)
    directory = load_directory_file(args.federal_register)
    records, report = match_federal_register(
        directory["data"], node_map, parent_map,
        root_id=str(root.get("id") or ""), fetched_at=directory.get("fetched_at"),
        directory_url=directory.get("url") or FR_DIRECTORY_URL,
    )
    print(f"directory {args.federal_register}  fetched {directory.get('fetched_at')}  entries {report['entries']}")
    print(f"matched {report['matched']}  unmatched {len(report['unmatched_entries'])}  ambiguous {len(report['ambiguous_entries'])}  "
          f"top-level {report['top_level_entries']}  placements listed {report['placements_listed']}  "
          f"disagree {len(report['placements_disagree'])}  parent unmatched {report['placements_parent_unmatched']}")
    for item in report["ambiguous_entries"][:20]:
        print("  ambiguous:", item)
    for item in report["placements_disagree"]:
        print("  disagrees:", item)
    print("  unmatched sample:", report["unmatched_entries"][:40])
    senate = load_senate_committees(args.senate_dir) if args.senate_dir.exists() else []
    senate_records, senate_report = match_senate(senate, node_map, parent_map)
    print(f"senate list: {senate_report['committees_in_list']} committees; matched {senate_report['committees_matched']}; "
          f"subcommittees matched {senate_report['subcommittees_matched']}; curated names not in the list {len(senate_report['subcommittees_not_in_list'])}; "
          f"list names not in the graph {len(senate_report['subcommittees_not_in_graph'])}; committees not in graph {len(senate_report['committees_not_in_graph'])}")
    for item in senate_report["subcommittees_not_in_list"][:80]:
        print("  not in list:", item)
    for item in senate_report["subcommittees_not_in_graph"][:80]:
        print("  not in graph:", item)
    for item in senate_report["graph_committees_not_in_list"]:
        print("  committee not in list:", item)
    overlap = set(records) & set(senate_records)
    assert not overlap, f"a node in two directories: {sorted(overlap)[:5]}"
    records = {**records, **senate_records}
    if args.dry_run:
        return 0
    store = {
        "_note": (
            "Derived by scripts/derive_directory_evidence.py from a verbatim fetch of the Federal Register agency "
            "directory; each record says what the directory lists for the node — name, parent, page — and nothing "
            "else. checkedAt is the directory's fetch time. Regenerate by re-running the script; never edit by hand."
        ),
        "sources": [
            {"kind": "federal_register_agency_directory", "file": str(args.federal_register.relative_to(PROJECT_ROOT)) if args.federal_register.is_relative_to(PROJECT_ROOT) else str(args.federal_register),
             "url": directory.get("url") or FR_DIRECTORY_URL, "fetched_at": directory.get("fetched_at")},
            {"kind": "senate_committee_list", "dir": str(args.senate_dir.relative_to(PROJECT_ROOT)) if args.senate_dir.is_relative_to(PROJECT_ROOT) else str(args.senate_dir),
             "files": len(senate), "fetched_at": max((c.get("fetched_at") or "" for c in senate), default=None)},
        ],
        "report": {k: v for k, v in report.items() if k not in ("unmatched_entries",)} | {"unmatched_sample": report["unmatched_entries"][:60]},
        "senate_report": senate_report,
        "nodes": records,
    }
    write_json_file(args.out, store)
    print(f"wrote {len(records)} records -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
