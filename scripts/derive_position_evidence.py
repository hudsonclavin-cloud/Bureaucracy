#!/usr/bin/env python
"""Derive position evidence from OPM's PLUM archive, exactly as fetched.

    python scripts/derive_position_evidence.py --dry-run
    python scripts/derive_position_evidence.py            # writes data/verification/position_evidence.json

Reads the PLUM archive CSV committed verbatim in tests/fixtures/opm/plum/ —
OPM's archive of the PREVIOUS administration's reported positions, the file
the PLUM Archive page labels "Biden Administration (January 21, 2021 -
January 20, 2025)"; the current export (reported as of June 15, 2026) is
served by escs.opm.gov, which this environment's proxy refuses, so it is not
here (tests/fixtures/opm/README.md §1). Matches the archive's agencies and
organisations to the curated graph's organisation nodes and each matched
organisation's position titles to the position nodes beneath it — by
canonical name, one name to one node or nothing, never across organisations
— and writes one record per matched position saying what the archive lists:
title, agency, organisation, status, appointment type, pay plan, level,
dated by the file's fetch time and labelled with the archive's own edition.

No negative records are written. The archive is neither current nor
complete for career positions, so a position absent from it is not evidence
of anything; the report counts the absences and says nothing about them.
Nothing here fetches.
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
from data_pipeline.verification.positions import (  # noqa: E402
    DEFAULT_ARCHIVE_CSV,
    DEFAULT_ARCHIVE_PAGE,
    DEFAULT_EDITION,
    DEFAULT_POSITION_EVIDENCE_PATH,
    load_plum_archive,
    match_positions,
    read_archive_edition,
)

DEFAULT_BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"


def _relative(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE_CSV, help="verbatim PLUM archive CSV (its .meta.json sibling supplies URL and fetch time)")
    parser.add_argument("--archive-page", type=Path, default=DEFAULT_ARCHIVE_PAGE, help="saved PLUM Archive page, read for the file's stated edition")
    parser.add_argument("--out", type=Path, default=DEFAULT_POSITION_EVIDENCE_PATH)
    parser.add_argument("--dry-run", action="store_true", help="report the matches; write nothing")
    args = parser.parse_args((argv or sys.argv)[1:])

    root = load_base_graph(args.base_graph)
    node_map, parent_map = index_tree(root)
    archive = load_plum_archive(args.archive)
    edition = read_archive_edition(args.archive_page, args.archive.name)
    records, report = match_positions(archive, node_map, parent_map, root_id=str(root.get("id") or ""), edition=edition)

    print(f"archive {_relative(args.archive)}  fetched {archive.get('fetched_at')}  url {archive.get('url')}")
    print(f"edition (as the archive page states it): {report['edition']}" + ("" if edition else f"  [page not read; default label '{DEFAULT_EDITION}' claims no dates]"))
    print(f"rows {report['rows']}  agencies {report['agencies']}  organisations {report['organizations']} "
          f"({report['organization_names']} distinct names)  titles {report['titles']}")
    print(f"appointment types: {report['appointment_types']}")
    print(f"position status: {report['position_status']}")
    print(f"agencies matched {report['agencies_matched']}  unmatched {len(report['agencies_unmatched'])}  ambiguous {len(report['agencies_ambiguous'])}")
    print("  unmatched agencies sample:", report["agencies_unmatched"][:25])
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
          f"unmatched {report['positions_unmatched']}  shared title {len(report['positions_shared_title'])}  "
          f"alternatives ambiguous {len(report['positions_ambiguous_alternatives'])}  archive title ambiguous {len(report['positions_title_ambiguous_in_archive'])}")
    for item in report["samples"]:
        print("  match:", item)
    for item in report["positions_shared_title"][:10]:
        print("  shared title:", item)
    for item in report["positions_ambiguous_alternatives"][:10]:
        print("  alternatives ambiguous:", item)
    for item in report["positions_title_ambiguous_in_archive"][:10]:
        print("  archive title ambiguous:", item)
    print("  unmatched positions sample:", [f"{p['name']} (under {p['listed_under']})" for p in report["positions_unmatched_sample"][:20]])
    print("No negative records: a position the archive lacks is not evidence of anything — the archive is neither current nor complete for career positions.")
    if args.dry_run:
        return 0
    store = {
        "_note": (
            "Derived by scripts/derive_position_evidence.py from OPM's PLUM archive CSV as fetched on "
            f"{archive.get('fetched_at')} — the archive of the PREVIOUS administration's reported positions, "
            f"labelled by OPM's PLUM Archive page '{report['edition']}', not the current PLUM export (reported as of "
            "June 15, 2026, served by escs.opm.gov and unreachable from the pipeline's network). Each record says what "
            "the archive lists for the position node — title, agency, organisation, status, appointment type, pay plan, "
            "level — and nothing else; checkedAt is the file's fetch time. No record is written for a position the archive "
            "lacks: the archive is neither current nor complete for career positions, so absence is not evidence. "
            "Regenerate by re-running the script; never edit by hand."
        ),
        "source": {
            "kind": "opm_plum_archive",
            "url": archive.get("url"),
            "fetched_at": archive.get("fetched_at"),
            "file": _relative(args.archive),
            "edition": report["edition"],
            "period": report.get("period"),
            "edition_from": _relative(args.archive_page) if edition else None,
        },
        "report": report,
        "nodes": records,
    }
    write_json_file(args.out, store)
    print(f"wrote {len(records)} records -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
