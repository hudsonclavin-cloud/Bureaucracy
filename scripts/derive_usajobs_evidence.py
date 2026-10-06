#!/usr/bin/env python
"""Derive vacancy LISTINGS from committed USAJOBS announcements.

    python scripts/derive_usajobs_evidence.py --dry-run
    python scripts/derive_usajobs_evidence.py          # writes data/verification/usajobs_evidence.json

Reads the announcements committed under `tests/fixtures/usajobs/` (each with
the `.meta.json` its fetch wrote; the digest is recomputed from the bytes
before a field is read) and the reviewed table
`data_pipeline/verification/usajobs.VACANCY_FAMILIES`, which names the
curated title family each set of announcements lists.

A family is listed only when every committed announcement for it still prints
what its reviewed row says -- title, department, agency, hiring organisation,
series -- and every one states the same pay plan and grade, and there are at
least two of them: one posting is one vacancy. Each member of a listed family
(read off the base graph by the family's membership rule) gets a listing
record in the shape `gs_pay` reads a PLUM listing in. Run
`scripts/derive_gs_pay_evidence.py` afterwards: it is what turns a listing
into OPM's base General Schedule range for the grade.

Read from each announcement: the title, department, agency, hiring
organisation, open and close dates, locations, pay scale and grade, and
series. Never read: the salary (the duty station's locality range) and the
agency contact (a named person), which is outside the part of the page this
module is ever handed. Nothing here fetches.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.exporter.build_graph import load_base_graph  # noqa: E402
from data_pipeline.json_io import write_json_file  # noqa: E402
from data_pipeline.verification.usajobs import (  # noqa: E402
    DEFAULT_EVIDENCE_PATH,
    FIXTURE_DIR,
    SOURCE,
    build_listings,
)

DEFAULT_BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--fixtures", type=Path, default=FIXTURE_DIR, help="committed announcements and their .meta.json files")
    parser.add_argument("--out", type=Path, default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument("--dry-run", action="store_true", help="report what would be written and write nothing")
    args = parser.parse_args((argv or sys.argv)[1:])

    records, report = build_listings(load_base_graph(args.base_graph), fixture_dir=args.fixtures)

    for family, entry in report["families"].items():
        print(f"{family}: {entry['verdict']}; {entry['members']} member node(s); "
              f"announcements {', '.join(entry['announcements']) or 'none'}")
        for note in entry["notes"]:
            print(f"  {note}")
    for declined in report["declined"]:
        print(f"{declined['family']}: declined -- {declined['reason']}")
    any_record = next(iter(records.values()), None)
    if any_record is not None:
        print(f"  listing: {any_record['payPlan']}-{any_record['payLevel']} from {any_record['announcementCount']} announcements")
        for item in any_record["announcements"]:
            print(f"    {item['id']}  {item['openDate']}  {item['payScaleAndGrade']}  {item['hiringOrganization']} "
                  f"({', '.join(item['locations'])})  \"{item['title']}\"")
    print(f"listed {report['listed']} node(s)")
    print("A vacancy listing states a title family's pay plan and grade; it is not evidence that any node exists, "
          "and no announcement's salary is read.")

    if args.dry_run:
        return 0
    store = {
        "_note": (
            "Derived by scripts/derive_usajobs_evidence.py from USAJOBS vacancy announcements committed under "
            "tests/fixtures/usajobs/ (digests recomputed before reading) and the reviewed table "
            "data_pipeline/verification/usajobs.VACANCY_FAMILIES. A family is listed only when at least two "
            "announcements list it and every one states the same pay plan and grade. A listing says which pay plan "
            "and grade the announcements state for a title family; it names no node, verifies nothing, and carries "
            "no salary: the announcements' salaries are locality ranges for one duty station and are never read, "
            "and the agency contact is never read. Regenerate by re-running the script; never edit by hand."
        ),
        "source": SOURCE,
        "report": report,
        "nodes": records,
    }
    write_json_file(args.out, store)
    print(f"wrote {len(records)} records -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
