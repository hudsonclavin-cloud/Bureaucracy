"""Report how the Monthly Treasury Statement's per-agency lines match the graph.

Nothing in output/ is read or written. This is the diagnostic to run before
touching TREASURY_ROW_ALIASES: it fetches Table 5 (or reads a saved copy),
runs the same matcher build_graph runs, and prints every line that found no
node, every name several nodes claim, and every match it did make.

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rows", type=Path, help="a saved Treasury payload to read instead of fetching")
    parser.add_argument("--save", type=Path, help="write the fetched payload here")
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--limit", type=int, default=0, help="cap each list (0 = every line)")
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
    # name too many nodes claim. Each needs a canonical name -> node id entry.
    by_name = {str(row.get("originalName") or row.get("name")): row for row in rows}
    show(
        "unmatched — no node carries this name",
        stats["unmatched_sample"],
        lambda name: f"{money((by_name.get(name) or {}).get('rollup_total_amount')):>10}  {name}",
    )
    show(
        "ambiguous — several nodes carry this name",
        stats["ambiguous_sample"],
        lambda name: f"{money((by_name.get(name) or {}).get('rollup_total_amount')):>10}  {name}",
    )
    show("negative — net receipts, set aside", stats["negative_sample"], str)
    show(
        "applied — measured cost stamped on a node",
        stats["applied"],
        lambda hit: f"{money(hit.get('amount')):>10}  {hit.get('row')}  ->  {hit.get('id')}",
    )
    print("\nAdd an entry to TREASURY_ROW_ALIASES in data_pipeline/exporter/build_graph.py")
    print("for each line above that names a unit the graph really has.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
