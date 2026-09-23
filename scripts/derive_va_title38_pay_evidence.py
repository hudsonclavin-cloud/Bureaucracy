#!/usr/bin/env python
"""Derive VA Title 38 pay RANGES for the posts the schedule's own table names.

    python scripts/derive_va_title38_pay_evidence.py --dry-run
    python scripts/derive_va_title38_pay_evidence.py   # writes data/verification/va_title38_pay_evidence.json

Reads one committed file: `tests/fixtures/va/title38_pay_tables_2026.pdf`, the
Veterans Health Administration's annual pay ranges under 38 U.S.C. 7431. PAY TABLES 3 and 4 are read; Tables 1 and 2 are not, because they print the
same leadership titles at two different ranges selected by clinical specialty.
See `data_pipeline/verification/va_title38_pay.py`.

A range is not a rate. Every record here is a band the schedule sets, and the
panel heads it as one.

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
from data_pipeline.verification.va_title38_pay import (  # noqa: E402
    DEFAULT_PAY_EVIDENCE_PATH,
    DEFAULT_PAY_PDF,
    Unreadable,
    build_records,
    load_pay_tables,
)

DEFAULT_BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"


def _relative(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path)


def _parent_map(root) -> dict[str, str]:
    parents: dict[str, str] = {}

    def walk(node):
        for child in node.get("children") or []:
            parents[str(child.get("id"))] = str(node.get("id"))
            walk(child)

    walk(root)
    return parents


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--tables", type=Path, default=DEFAULT_PAY_PDF,
                        help="verbatim VA pay-range PDF (its .meta.json sibling supplies URL, fetch time and digest)")
    parser.add_argument("--out", type=Path, default=DEFAULT_PAY_EVIDENCE_PATH)
    parser.add_argument("--dry-run", action="store_true", help="report what would be written and write nothing")
    args = parser.parse_args((argv or sys.argv)[1:])

    try:
        loaded = load_pay_tables(args.tables)
    except Unreadable as error:
        print(f"refused: {error}")
        return 1
    table = loaded["table"]

    tree = load_base_graph(args.base_graph)
    node_map, _ = index_tree(tree)
    records, report = build_records(
        node_map, _parent_map(tree), table,
        url=loaded["url"], sha256=loaded["sha256"], retrieved_at=loaded["fetched_at"],
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
            rejected.append(f"{node_id}: classified {state!r}; a tier band identified by a reviewed rule is a proxy")
            continue
        out["financialEvidenceStatus"] = state
        # validate_record keeps only the fields it knows; the band's own
        # numbers ride back on so the applier has them.
        for key in ("rangeMinimum", "rangeMaximum", "rangeMinimumRaw", "rangeMaximumRaw",
                    "tier", "coverageTitle", "matchRule", "rangeText"):
            out[key] = record[key]
        validated[node_id] = out

    report["validated"] = len(validated)
    report["rejected"] = rejected
    report["conflicts"] = fe.detect_conflicts(validated.values())
    report["double_counted"] = fe.double_counted(validated.values())

    print(f"VA Title 38 pay ranges ({table['effectiveText']}), fetched {loaded['fetched_at']}")
    for number, tiers in report["tables"].items():
        print(f"  PAY TABLE {number}")
        for tier in tiers:
            print(f"    TIER {tier['tier']}  ${tier['minimum']:>9,.0f} – ${tier['maximum']:>9,.0f}   {'; '.join(tier['coverage'])[:96]}")
    print(f"priced {report['priced']}  validated {report['validated']}")
    for rule, count in report["matchedByRule"].items():
        print(f"    {count:5d}  {rule}")
    if report["refused"]:
        print("  refused:")
        for reason, count in report["refused"].items():
            print(f"    {count:5d}  {reason}")
    for line in rejected[:20]:
        print(f"  REJECTED {line}")
    print("Tables deliberately not read:")
    for name, reason in report["tablesNotRead"].items():
        print(f"    {name}: {reason}")
    for line in report["titlesNotPrinted"]:
        print(f"    the schedule prints no {line}")
    print("Every figure here is a RANGE, never a rate, and is never the node's cost.")

    if args.dry_run:
        return 0
    if not validated:
        print("nothing validated; refusing to write an empty evidence file")
        return 1

    store = {
        "_note": (
            "Derived by scripts/derive_va_title38_pay_evidence.py from one source: the Veterans Health "
            f"Administration's Title 38 annual pay RANGES, fetched {loaded['fetched_at']} from {loaded['url']}. "
            "PAY TABLES 3 and 4 are read. Tables 1 and 2 are not: they print the same leadership titles at two "
            "different ranges selected by clinical specialty, and this graph's 'Chief — X Service' family includes "
            "Finance and Human Resources, which are in neither. A record may claim a band only for a phrase that is "
            "a WHOLE printed item of a tier's coverage list. 'Associate Director' is printed nowhere in the "
            "document, so those nodes are refused. Every figure is a band the schedule sets, never a rate paid: "
            "the VA publishes the bounds "
            "within which an appointment may be set and not what any holder receives. Not the node's cost. "
            "Regenerate by re-running the script; never edit by hand."
        ),
        "source": {
            "kind": "va_title38_pay_ranges",
            "url": loaded["url"],
            "fetched_at": loaded["fetched_at"],
            "sha256": loaded["sha256"],
            "file": _relative(Path(loaded["file"])),
            "tables": sorted(table["tables"]),
            "effective": table["effective"],
            "authority": table["authority"],
        },
        "report": report,
        "nodes": validated,
    }
    write_json_file(args.out, store)
    print(f"wrote {_relative(args.out)}  ({len(validated)} nodes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
