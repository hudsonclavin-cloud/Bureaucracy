"""Derive what each chamber paid out for a committee's account.

    python scripts/derive_committee_disbursements_evidence.py --dry-run   # what would apply; writes nothing
    python scripts/derive_committee_disbursements_evidence.py             # writes data/verification/committee_disbursements_evidence.json

Reads, verbatim and with every digest recomputed from the bytes:

- the House's Statement of Disbursements for April 1 - June 30, 2026: the
  summary CSV (office totals by organisation and program -- no person in it),
  one page of the signed third volume (its Statement of Accountability, for
  the period and the marked total that bounds the CSV's scale), the landing
  page that links both under that period, and the glossary that defines the
  quarterly column;
- the Senate's Report of the Secretary of the Senate for October 1, 2025 -
  March 31, 2026, Part II: each committee's Inquiries and Investigations
  summary block, one per funding resolution, and nothing on the payee pages.

Every record is a sum of totals the chamber prints, each component listed with
its printed text, validated by `financial_evidence.validate_record` under the
`disbursements` basis. It is never the cost: the exporter stamps it beside the
estimate under its own heading, on a node typed Committee and nothing else.
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
from data_pipeline.verification.committee_disbursements import (  # noqa: E402
    DEFAULT_EVIDENCE_PATH,
    build_records,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--out", type=Path, default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv[1:] if argv else None)

    node_map, parent_map = index_tree(load_base_graph(args.base_graph))
    records, report = build_records(node_map, parent_map)

    for chamber in ("house", "senate"):
        part = report[chamber]
        mine = {k: v for k, v in records.items() if v["chamber"] == chamber}
        rules: dict[str, int] = {}
        for rule in part["matched"].values():
            rules[rule] = rules.get(rule, 0) + 1
        print(f"{chamber.upper()}: {len(mine)} of {part['committees_in_graph']} committees carry a figure "
              f"({', '.join(f'{n} {r}' for r, n in sorted(rules.items()))})")
        for node_id, record in sorted(mine.items()):
            print(f"  {node_id:62s} ${record['amount']:>14,.2f}  {record['componentCount']} component(s)"
                  f"  [{record['matchRule']}]")
        for reason, items in sorted(part["refused"].items()):
            print(f"  refused, {reason}: {len(items)}")
            for item in items[:8]:
                print(f"      {item}")
        if part["ambiguous"]:
            print(f"  ambiguous: {part['ambiguous']}")
        print(f"  labels in the document reaching no committee: {part['labels_not_matched']}")
        print()

    print("A disbursement is cash the chamber paid out for the committee's account over the report's")
    print("period. It is not the Treasury's net outlays and not the graph's estimate: it is published")
    print("beside the estimate, under its own heading, and never as the cost.")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0

    store = {
        "_note": (
            "Derived by scripts/derive_committee_disbursements_evidence.py from the House's Statement of "
            "Disbursements and the Senate's Report of the Secretary of the Senate, committed verbatim under "
            "tests/fixtures/disbursements/ with their digests. Each record is the sum of the totals the "
            "chamber prints for one committee's account over the report's period, every component listed. "
            "No row about a person is read. It is not a cost and the exporter never writes it into one."
        ),
        "source": {"kind": "committee_disbursements",
                   "derivedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
        "report": report,
        "nodes": records,
    }
    write_json_file(args.out, store)
    print(f"\nwrote {len(records)} records -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
