#!/usr/bin/env python
"""Derive congressional pay evidence from the Senate's own salary schedule.

    python scripts/derive_congressional_pay_evidence.py --dry-run
    python scripts/derive_congressional_pay_evidence.py          # writes data/verification/congressional_pay_evidence.json

Reads one committed file:
`tests/fixtures/congress/senate_salaries_since_1789.html`, senate.gov's own
year-by-year base-salary table, whose footnote states the rate paid to three
named Senate leadership roles: the President Pro Tempore, the Majority
Leader, the Minority Leader. See
`data_pipeline/verification/congressional_pay.py` for exactly what this does
and does not price — deliberately not the House's own leadership, and not any
"Member of Congress" seat, since no such position node is curated.

Every record is validated against its own node by
`financial_evidence.validate_record` before it is written. Nothing here
fetches.
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
from data_pipeline.verification import financial_evidence as fe  # noqa: E402
from data_pipeline.verification.congressional_pay import (  # noqa: E402
    DEFAULT_PAY_EVIDENCE_PATH,
    DEFAULT_TABLE_HTML,
    Unreadable,
    build_records,
    load_senate_salary_table,
)

DEFAULT_BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"


def _relative(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE_HTML,
                        help="verbatim senate.gov salary page (its .meta.json sibling supplies URL, fetch time and digest)")
    parser.add_argument("--out", type=Path, default=DEFAULT_PAY_EVIDENCE_PATH)
    parser.add_argument("--dry-run", action="store_true", help="report what would be written and write nothing")
    args = parser.parse_args((argv or sys.argv)[1:])

    try:
        loaded = load_senate_salary_table(args.table)
    except Unreadable as error:
        print(f"refused: {error}")
        return 1
    table = loaded["table"]

    node_map, _ = index_tree(load_base_graph(args.base_graph))
    records, report = build_records(node_map, table, url=loaded["url"], sha256=loaded["sha256"], retrieved_at=loaded["fetched_at"])

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
            rejected.append(f"{node_id}: classified {state!r}; a shared leadership rate is a proxy and nothing more")
            continue
        out["financialEvidenceStatus"] = state
        validated[node_id] = out

    report["validated"] = len(validated)
    report["rejected"] = rejected
    conflicts = fe.detect_conflicts(validated.values())
    duplicates = fe.double_counted(validated.values())
    report["conflicts"] = conflicts
    report["double_counted"] = duplicates

    print(f"table: Senate Salaries (1789 to Present), year {report['year']}, fetched {loaded['fetched_at']}")
    print(f"  base rate ${report['baseRate']:,.0f}  leadership rate ${report['leadershipRate']:,.0f}")
    print(f"  footnote: {report['footnote']}")
    print(f"considered {report['considered']}  priced {report['priced']}  validated {report['validated']}")
    print("  refused:")
    for reason, count in report["refused"].items():
        print(f"    {count:5d}  {reason}")
    for line in rejected[:20]:
        print(f"  REJECTED {line}")
    if conflicts:
        print(f"  conflicts: {len(conflicts)}")
    if duplicates:
        print(f"  double counted: {len(duplicates)}")
    print("Every record is scoped 'proxy': the footnote names three roles together, not one role per line, so none of these is 'verified'.")
    print("Not priced: the House's own leadership (no fetched source this session could reach), and no base 'Member of Congress' seat (no such position node is curated).")

    if args.dry_run:
        return 0
    if not validated:
        print("nothing validated; refusing to write an empty evidence file")
        return 1

    store = {
        "_note": (
            "Derived by scripts/derive_congressional_pay_evidence.py from a single source: the Senate's own "
            f"year-by-year salary table (senate.gov/senators/SenateSalariesSince1789.htm), fetched "
            f"{loaded['fetched_at']} from {loaded['url']}. Its footnote names three Senate leadership roles — "
            "President Pro Tempore, Majority Leader, Minority Leader — sharing one rate; a record is written only "
            "for those three curated nodes. Not priced: the Assistant Majority/Minority Leader (party whips; the "
            "footnote does not name them), the House's own Speaker/Majority Leader/Minority Leader (no fetched "
            "official source this session could reach — crsreports.congress.gov and www.congress.gov's CRS-report "
            "pages are Cloudflare-blocked to this session, a fact about the network, not the claim), the President "
            "of the Senate/Vice President node (a different statutory salary, 3 U.S.C. 104, not read here), and "
            "no base 'Member of Congress' seat, because none is curated as its own position node. Basic pay is "
            "not the node's cost. Regenerate by re-running the script; never edit by hand."
        ),
        "source": {
            "kind": "senate_salary_schedule",
            "url": loaded["url"],
            "fetched_at": loaded["fetched_at"],
            "sha256": loaded["sha256"],
            "file": _relative(Path(loaded["file"])),
            "year": report["year"],
            "footnote": report["footnote"],
        },
        "report": report,
        "nodes": validated,
    }
    write_json_file(args.out, store)
    print(f"wrote {len(validated)} records -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
