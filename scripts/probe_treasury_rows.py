"""Report how the Monthly Treasury Statement's per-agency lines match the graph.

Nothing in output/ is read or written. This is the diagnostic to run before
touching TREASURY_ROW_ALIASES: it fetches Table 5 (or reads a saved copy),
runs the same matcher build_graph runs, and prints every line that found no
node, every name that does not identify one line and one node, and every
match it did make.

    python scripts/probe_treasury_rows.py                     # live fetch
    python scripts/probe_treasury_rows.py --save rows.json    # live, keep the payload
    python scripts/probe_treasury_rows.py --rows rows.json    # offline, from that copy

Only api.fiscaldata.treasury.gov is contacted. On a network that blocks it the
fetch fails with a plain message and exit 2; --rows then does the same work
from a payload captured elsewhere.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.exporter.build_graph import (  # noqa: E402
    DEFAULT_BASE_GRAPH,
    TREASURY_ROW_ALIASES,
    apply_treasury_outlay_rows,
    build_graph_tree,
    collect_treasury_outlay_rows,
    load_base_graph,
    parse_cost_amount,
)


def money(value: Any) -> str:
    amount = parse_cost_amount(value)
    if amount is None:
        return "-"
    for unit, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(amount) >= unit:
            return f"${amount / unit:,.1f}{suffix}"
    return f"${amount:,.0f}"


def fetch_payload(timeout: int) -> dict[str, Any]:
    from data_pipeline.crawler.treasury_outlays import crawl

    try:
        return crawl(timeout=timeout)
    except Exception as error:  # noqa: BLE001
        print(f"could not reach the Treasury API: {error.__class__.__name__}: {error}", file=sys.stderr)
        print("Capture the payload where the host is reachable and re-run with --rows.", file=sys.stderr)
        raise SystemExit(2) from error


def reconcile_rows(rows: list[dict[str, Any]], anchor: float | None) -> dict[str, Any]:
    """Where the anchor's net figure and the sum of the agency lines part ways.

    The published graph scales every measured department to 96% of its line.
    The cascade is not wrong about arithmetic: the positive lines really do
    sum past the net anchor. What this report shows is WHY, in the statement's
    own terms — which negative lines carry the difference, and at what level
    of the table they sit. A negative that belongs to a department is netted
    inside that department's "Total--" line already; a negative that belongs
    to nobody (undistributed offsetting receipts) is netted only at the grand
    total, and the cascade has no node to put it on. Report, do not decide.
    """
    def amt(row: dict[str, Any]) -> float:
        value = parse_cost_amount(row.get("rollup_total_amount"))
        return float(value) if value is not None else 0.0

    by_level: dict[int, dict[str, float]] = {}
    for row in rows:
        level = int(row.get("sequence_level") or 0)
        bucket = by_level.setdefault(level, {"positive": 0.0, "negative": 0.0, "rows": 0})
        bucket["rows"] += 1
        bucket["positive" if amt(row) >= 0 else "negative"] += amt(row)
    negatives = sorted((r for r in rows if amt(r) < 0), key=amt)
    totals = [r for r in rows if str(r.get("originalName") or "").startswith("Total--")]
    shallowest = min((int(r.get("sequence_level") or 0) for r in totals), default=None)
    top_totals = [r for r in totals if int(r.get("sequence_level") or 0) == shallowest] if shallowest is not None else []
    top_total_sum = sum(amt(r) for r in top_totals)
    # Positive lines at the shallowest level that are NOT a department total:
    # interest on the debt, and the groupings the curated graph has no node for.
    top_positive_other = [
        r for r in rows
        if int(r.get("sequence_level") or 0) == shallowest and amt(r) > 0 and r not in top_totals
    ] if shallowest is not None else []
    return {
        "anchor": anchor,
        "rows": len(rows),
        "by_level": {str(k): v for k, v in sorted(by_level.items())},
        "shallowest_total_level": shallowest,
        "top_level_totals": len(top_totals),
        "top_level_totals_sum": top_total_sum,
        "top_level_other_positive": [
            {"name": r.get("originalName"), "amount": amt(r)} for r in sorted(top_positive_other, key=amt, reverse=True)
        ],
        "anchor_minus_top_totals": (anchor - top_total_sum) if anchor is not None else None,
        "largest_negatives": [
            {"name": r.get("originalName"), "amount": amt(r), "level": int(r.get("sequence_level") or 0),
             "print_order": int(r.get("print_order") or 0)}
            for r in negatives[:15]
        ],
        "negative_total": sum(amt(r) for r in negatives),
    }


def print_reconciliation(report: dict[str, Any]) -> None:
    print("\n=== reconciliation: the net anchor vs the agency lines ===")
    print(f"anchor (FYTD net outlays)           : {money(report['anchor'])}")
    for level, bucket in report["by_level"].items():
        print(f"level {level:<3} rows {bucket['rows']:>4}   +{money(bucket['positive']):>10}   {money(bucket['negative']):>11}")
    print(f"shallowest 'Total--' level          : {report['shallowest_total_level']}")
    print(f"sum of those {report['top_level_totals']} totals              : {money(report['top_level_totals_sum'])}")
    print(f"anchor minus those totals           : {money(report['anchor_minus_top_totals'])}")
    print("other positive lines at that level  :")
    for item in report["top_level_other_positive"][:12]:
        print(f"    {money(item['amount']):>10}  {item['name']}")
    print(f"all negative lines sum to           : {money(report['negative_total'])}")
    print("largest negatives (level, print order):")
    for item in report["largest_negatives"]:
        print(f"    {money(item['amount']):>11}  L{item['level']} #{item['print_order']:<4} {item['name']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rows", type=Path, help="a saved Treasury payload to read instead of fetching")
    parser.add_argument("--save", type=Path, help="write the fetched payload here")
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--limit", type=int, default=0, help="cap each list (0 = every line)")
    parser.add_argument("--reconcile", action="store_true", help="also explain the gap between the net anchor and the agency lines")
    args = parser.parse_args(argv[1:] if argv else None)

    if args.rows:
        payload = json.loads(args.rows.read_text(encoding="utf-8"))
    else:
        payload = fetch_payload(args.timeout)
        if args.save:
            args.save.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(f"payload saved to {args.save}")

    summary = payload.get("budgetSummary") or {}
    rows = collect_treasury_outlay_rows([payload])
    print(f"statement    : {summary.get('label') or summary.get('record_date') or 'unknown'}")
    print(f"anchor       : {money(summary.get('government_total_outlay_amount'))}")
    print(f"lines usable : {len(rows)} of {len(payload.get('outlayRows') or [])} fetched")

    root = build_graph_tree(base_graph_path=args.base_graph, nodes=[], edges=[])
    trusted = set()
    stack = [load_base_graph(args.base_graph)]
    while stack:
        node = stack.pop()
        trusted.add(str(node.get("id") or ""))
        stack.extend(child for child in node.get("children", []) if isinstance(child, dict))
    stats = apply_treasury_outlay_rows(
        root,
        rows,
        root_id=str(root.get("id") or ""),
        trusted_node_ids=trusted,
        # Nothing here is published, so report every line rather than a sample.
        sample_limit=len(rows) + 1,
    )

    print(
        f"\napplied {stats['rows_applied']}  unmatched {stats['rows_unmatched']}  "
        f"ambiguous {stats['rows_ambiguous']}  superseded {stats['rows_superseded']}  "
        f"negative {stats['rows_negative_skipped']}"
    )
    if stats["rows"]:
        print(f"match rate   : {stats['rows_applied'] / stats['rows']:.1%} of every line")
    print(f"aliases in use: {len(TREASURY_ROW_ALIASES)}")

    def show(title: str, items: list[Any], render) -> None:
        shown = items[: args.limit] if args.limit else items
        print(f"\n--- {title} ({len(items)}) ---")
        for item in shown:
            print(f"  {render(item)}")
        if len(shown) < len(items):
            print(f"  ... {len(items) - len(shown)} more")

    # These two are the alias table's to-do list: a line no node claims, and a
    # name that does not pin down one line and one node. Each needs a
    # canonical name -> node id entry.
    #
    # One name can be several lines (Table 5 repeats "Department of the Navy"
    # under four budget categories). Keying a single row by name would print
    # whichever one happened to be last — including a negative line under a
    # positive name — and the alias table is edited off this output.
    by_name: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_name.setdefault(str(row.get("originalName") or row.get("name")), []).append(row)

    def amount_of(name: str) -> str:
        matches = by_name.get(name) or []
        if len(matches) == 1:
            return money(matches[0].get("rollup_total_amount"))
        if not matches:
            return "-"
        total = sum(parse_cost_amount(row.get("rollup_total_amount")) or 0.0 for row in matches)
        return f"{money(total)} /{len(matches)}"

    show(
        "unmatched — no node carries this name",
        stats["unmatched_sample"],
        lambda name: f"{amount_of(name):>14}  {name}",
    )
    show(
        # Either several nodes answer to the name, or several lines carry it;
        # both need an explicit alias to resolve, and "/n" marks the second.
        "ambiguous — the name does not identify one line and one node",
        stats["ambiguous_sample"],
        lambda name: f"{amount_of(name):>14}  {name}",
    )
    show("negative — net receipts, set aside", stats["negative_sample"], str)
    show(
        "applied — measured cost stamped on a node",
        stats["applied"],
        lambda hit: f"{money(hit.get('amount')):>10}  {hit.get('row')}  ->  {hit.get('id')}",
    )
    if args.reconcile:
        all_rows = [r for r in (payload.get("outlayRows") or []) if isinstance(r, dict)]
        anchor_value = parse_cost_amount(summary.get("government_total_outlay_amount"))
        print_reconciliation(reconcile_rows(all_rows, float(anchor_value) if anchor_value is not None else None))
    print("\nAdd an entry to TREASURY_ROW_ALIASES in data_pipeline/exporter/build_graph.py")
    print("for each line above that names a unit the graph really has.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
