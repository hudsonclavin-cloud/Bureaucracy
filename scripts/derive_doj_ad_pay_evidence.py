#!/usr/bin/env python
"""Derive the AUSA base-pay RANGE from the U.S. Attorneys' own AD pay plan chart.

    python scripts/derive_doj_ad_pay_evidence.py --dry-run
    python scripts/derive_doj_ad_pay_evidence.py   # writes data/verification/doj_ad_pay_evidence.json

Reads two committed files: `tests/fixtures/doj/usao_ad_pay_plan_charts.html`
(the chart: a table headed "Assistant United States Attorneys (AUSA)", grades
AD-21 to AD-29, minimum to maximum, before locality, tables for 2025) and
`tests/fixtures/doj/usao_salary_information.html` (the page saying the AD plan
pays Assistant United States Attorneys, with Supervisory AUSAs and Senior
Litigation Counsel as categories of their own). See
`data_pipeline/verification/doj_ad_pay.py`.

A range is not a rate. Every record is validated against its own node by
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
from data_pipeline.verification.doj_ad_pay import (  # noqa: E402
    DEFAULT_CHART,
    DEFAULT_PAY_EVIDENCE_PATH,
    DEFAULT_PLAN_PAGE,
    Unreadable,
    build_records,
    load_documents,
)

DEFAULT_BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"
#: Kept beside the validated record so the applier has them;
#: `validate_record` keeps only the fields it knows.
BAND_KEYS = (
    "rangeMinimum", "rangeMaximum", "rangeMinimumRaw", "rangeMaximumRaw", "gradeLow", "gradeHigh",
    "rangeText", "planUrl", "planSha256", "planRetrievedAt",
)


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
    parser.add_argument("--chart", type=Path, default=DEFAULT_CHART)
    parser.add_argument("--plan-page", type=Path, default=DEFAULT_PLAN_PAGE)
    parser.add_argument("--out", type=Path, default=DEFAULT_PAY_EVIDENCE_PATH)
    parser.add_argument("--dry-run", action="store_true", help="report what would be written and write nothing")
    args = parser.parse_args((argv or sys.argv)[1:])

    try:
        loaded = load_documents(args.chart, args.plan_page)
    except Unreadable as error:
        print(f"refused: {error}")
        return 1
    parsed = loaded["parsed"]

    tree = load_base_graph(args.base_graph)
    node_map, _ = index_tree(tree)
    records, report = build_records(node_map, _parent_map(tree), loaded)

    validated: dict[str, dict] = {}
    rejected: list[str] = []
    for node_id, record in sorted(records.items()):
        node = node_map.get(node_id)
        try:
            out = fe.validate_record(record, node)
        except fe.Rejected as error:
            rejected.append(str(error))
            continue
        state = fe.classify(out)
        if state != "partial":
            rejected.append(f"{node_id}: classified {state!r}; a band identified by a reviewed row is a proxy")
            continue
        out["financialEvidenceStatus"] = state
        for key in BAND_KEYS:
            out[key] = record[key]
        validated[node_id] = out

    report["validated"] = len(validated)
    report["rejected"] = rejected

    print(f"U.S. Attorneys' AD pay plan chart ({parsed['effectiveText']}), fetched {loaded['chart']['fetched_at']}")
    print(f"  {parsed['table']}")
    for grade in parsed["grades"]:
        print(f"    {grade['grade']}  {grade['years']:>4}  ${grade['minimum']:>9,.0f} – ${grade['maximum']:>9,.0f}")
    print(f"priced {report['priced']}  validated {report['validated']}")
    for node_id, reason in report["refused"].items():
        print(f"  REFUSED {node_id}: {reason}")
    for node_id, reason in report["notPriced"].items():
        print(f"  not priced {node_id}: {reason}")
    for line in rejected:
        print(f"  REJECTED {line}")
    print("Every figure here is a RANGE before locality pay, never a rate, and is never the node's cost.")

    if args.dry_run:
        return 0
    if not validated:
        print("nothing validated; refusing to write an empty evidence file")
        return 1
    store = {
        "_note": (
            "Derived by scripts/derive_doj_ad_pay_evidence.py from two committed pages of the U.S. Attorneys' "
            f"career centre, fetched {loaded['chart']['fetched_at']}: the Administratively Determined pay plan "
            "chart (the table headed 'Assistant United States Attorneys (AUSA)', grades AD-21 to AD-29, base pay "
            "before locality, tables for 2025) and the salary information page (the AD plan pays Assistant United "
            "States Attorneys; Supervisory AUSAs and Senior Litigation Counsel are categories of their own). Every "
            "figure is a band the chart prints, never a rate paid, and not the node's cost. The chart's second "
            "table names no post and is not read. Regenerate by re-running the script; never edit by hand."
        ),
        "source": {
            "kind": "doj_usao_ad_pay_plan",
            "chart": {**report["chart"], "file": _relative(Path(loaded["chart"]["file"]))},
            "planPage": {**report["planPage"], "file": _relative(Path(loaded["plan"]["file"]))},
            "effective": parsed["effective"],
        },
        "report": report,
        "nodes": validated,
    }
    write_json_file(args.out, store)
    print(f"wrote {_relative(args.out)}  ({len(validated)} nodes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
