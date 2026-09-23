#!/usr/bin/env python
"""Derive White House Office pay evidence from the report the law requires.

    python scripts/derive_whitehouse_pay_evidence.py --dry-run
    python scripts/derive_whitehouse_pay_evidence.py   # writes data/verification/whitehouse_pay_evidence.json

Reads one committed file: `tests/fixtures/whitehouse/staff_report_2026.pdf`,
the White House Office's own Annual Report to Congress on White House Staff as
fetched from whitehouse.gov. Section 6 of Public Law 103-270 requires it by
July 1 each year and requires it to state, for every employee and detailee,
their title and their annual rate of pay.

It is the only named-salary disclosure the federal government is required to
publish, and that is exactly why the claim derived from it is narrow. The
report is person-level: `SENIOR POLICY ADVISOR` appears 21 times at differing
salaries. So a record here never says a post *pays* a figure; it says the one
person the report lists under this title is paid it, as of the report's own
as-of date. Every record is `scopeMatch: "proxy"` and classifies `partial`.

The NAME column is discarded at parse time and never reaches a record.

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
from data_pipeline.verification.whitehouse_pay import (  # noqa: E402
    DEFAULT_PAY_EVIDENCE_PATH,
    DEFAULT_REPORT_PDF,
    SCOPE_NODE_ID,
    Unreadable,
    build_records,
    load_staff_report,
    scoped_node_ids,
)

DEFAULT_BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"


def _relative(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PDF,
                        help="verbatim whitehouse.gov staff report PDF (its .meta.json sibling supplies URL, fetch time and digest)")
    parser.add_argument("--out", type=Path, default=DEFAULT_PAY_EVIDENCE_PATH)
    parser.add_argument("--dry-run", action="store_true", help="report what would be written and write nothing")
    args = parser.parse_args((argv or sys.argv)[1:])

    try:
        loaded = load_staff_report(args.report)
    except Unreadable as error:
        print(f"refused: {error}")
        return 1
    parsed = loaded["report"]

    root = load_base_graph(args.base_graph)
    node_map, _ = index_tree(root)
    scope = scoped_node_ids(root)
    if not scope:
        print(f"refused: the base graph carries no {SCOPE_NODE_ID!r} subtree to scope the report to")
        return 1

    records, report = build_records(
        node_map,
        parsed,
        url=loaded["url"],
        sha256=loaded["sha256"],
        retrieved_at=loaded["fetched_at"],
        scope_ids=scope,
    )

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
            rejected.append(
                f"{node_id}: classified {state!r}; a roster row is one person's pay and never the post's own rate"
            )
            continue
        out["financialEvidenceStatus"] = state
        for carried in ("reportedTitle", "reportedStatus", "payBasis", "rateText", "asOf", "titleFolded"):
            if carried in record:
                out[carried] = record[carried]
        validated[node_id] = out

    report["validated"] = len(validated)
    report["rejected"] = rejected
    conflicts = fe.detect_conflicts(validated.values())
    duplicates = fe.double_counted(validated.values())
    report["conflicts"] = conflicts
    report["double_counted"] = duplicates

    print(f"report: Annual Report to Congress on White House Staff, as of {report['asOf']}, fetched {loaded['fetched_at']}")
    print(f"  rows read {report['rowsRead']}  distinct titles {report['distinctTitles']}")
    if report["malformedRows"]:
        for reason, count in report["malformedRows"].items():
            print(f"    {count:5d}  rows refused at parse: {reason}")
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
    print(
        "Every record is scoped 'proxy': the report states what one listed person is paid, "
        "not what the office pays whoever holds it, so none of these is 'verified'."
    )

    if args.dry_run:
        return 0
    if not validated:
        print("nothing validated; refusing to write an empty evidence file")
        return 1

    store = {
        "_note": (
            "Derived by scripts/derive_whitehouse_pay_evidence.py from one source: the White House Office's own "
            f"Annual Report to Congress on White House Staff (as of {report['asOf']}), fetched "
            f"{loaded['fetched_at']} from {loaded['url']}, required by Section 6 of Public Law 103-270. The "
            "report is person-level by statute, so a record here says only that the one person listed under this "
            "title is paid this figure as of that date - never that the post pays it to whoever holds it. A title "
            "carried by more than one person is priced only when every row printed under that exact title carries "
            "one figure, one status and one pay basis and the count equals the (xN) the node's own name states; "
            "the record then says so in `holders` and the claim is that each of the N listed people is paid this "
            "figure. Differing rates, differing terms, or rows under several spellings refuse. Rows reading $0.00 "
            "are refused: ten of them are uncompensated appointees, and an "
            "uncompensated arrangement is a fact about a person, not about the post. The report's NAME column is "
            "discarded at parse time and appears nowhere in this file. Matching is scoped to descendants of "
            f"{SCOPE_NODE_ID!r}; a title being unique in the graph is not evidence of placement. Basic pay is not "
            "the node's cost. Regenerate by re-running the script; never edit by hand."
        ),
        "source": {
            "kind": "whitehouse_staff_report",
            "url": loaded["url"],
            "fetched_at": loaded["fetched_at"],
            "sha256": loaded["sha256"],
            "file": _relative(Path(loaded["file"])),
            "as_of": report["asOf"],
            "rows_read": report["rowsRead"],
            "statute": "Section 6 of Public Law 103-270",
        },
        "report": report,
        "nodes": validated,
    }
    write_json_file(args.out, store)
    print(f"wrote {len(validated)} records -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
