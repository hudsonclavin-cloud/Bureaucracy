"""Check curated nodes against official pages and record what was found.

    python scripts/verify_base_graph.py --list-hosts        # hosts a network policy must allow
    python scripts/verify_base_graph.py --dry-run           # what would be fetched, for which nodes
    python scripts/verify_base_graph.py                     # organisations (everything but Positions)
    python scripts/verify_base_graph.py --include-positions # positions too, against their unit's page
    python scripts/verify_base_graph.py --ids exec-dept-doe exec-ind-nasa
    python scripts/verify_base_graph.py --recheck           # re-fetch nodes already confirmed
    python scripts/verify_base_graph.py --inherit-depth 0   # only nodes with a page of their own

Reads data/federal_gov_complete_1.json and data/verification/official_sites.json
(candidate URLs: the node's own official site, else an ancestor's, by default
only one level up — a department's About page can name its bureaus; a chamber's
homepage does not name every subcommittee, and a check that never had a chance
is not evidence of anything).
Writes data/verification/evidence.json after every fetch, so a run that is
interrupted has lost nothing and a rerun continues where it stopped. Never
writes the curated file or anything under output/.

Each page is fetched once per run however many nodes it covers.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.crawler.official_directory import request_text  # noqa: E402
from data_pipeline.exporter.build_graph import DEFAULT_BASE_GRAPH, index_tree, load_base_graph  # noqa: E402
from data_pipeline.json_io import write_json_file  # noqa: E402
from data_pipeline.verification.evidence import (  # noqa: E402
    CONFIRMED,
    DEFAULT_EVIDENCE_PATH,
    DEFAULT_SITES_PATH,
    FETCH_FAILED,
    candidate_urls,
    load_evidence,
    load_official_sites,
    page_text,
    verify_node,
)


def select_nodes(node_map: dict[str, dict[str, Any]], *, ids: list[str], include_positions: bool) -> list[dict[str, Any]]:
    if ids:
        return [node_map[i] for i in ids if i in node_map]
    return [
        node
        for node in node_map.values()
        if include_positions or "position" not in str(node.get("type") or "").casefold()
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--sites", type=Path, default=DEFAULT_SITES_PATH)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE_PATH)
    parser.add_argument("--ids", nargs="*", default=[], help="only these node ids")
    parser.add_argument("--include-positions", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="stop after this many fetch-bearing nodes (0 = all)")
    parser.add_argument("--recheck", action="store_true", help="re-fetch nodes already confirmed")
    parser.add_argument(
        "--inherit-depth",
        type=int,
        default=1,
        help="check a node against an ancestor's page only this many levels up (0 = own page only; default 1)",
    )
    parser.add_argument("--sleep", type=float, default=1.0, help="seconds between fetches of distinct pages")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--dry-run", action="store_true", help="print the plan; fetch nothing; write nothing")
    parser.add_argument("--list-hosts", action="store_true", help="print the hosts the candidate URLs use, one per line")
    args = parser.parse_args(argv[1:] if argv else None)

    sites = load_official_sites(args.sites)
    if args.list_hosts:
        for host in sorted({urlparse(u).netloc for urls in sites.values() for u in urls}):
            print(host)
        return 0

    root = load_base_graph(args.base_graph)
    node_map, parent_map = index_tree(root)
    evidence = load_evidence(args.evidence) if args.evidence.exists() else {}
    nodes = select_nodes(node_map, ids=args.ids, include_positions=args.include_positions)

    plan: list[tuple[dict[str, Any], list[str], str | None]] = []
    skipped = Counter()
    for node in nodes:
        node_id = str(node.get("id") or "")
        prior = evidence.get(node_id)
        if prior and prior.get("status") == CONFIRMED and not args.recheck:
            skipped["already_confirmed"] += 1
            continue
        urls, site_from, distance = candidate_urls(node_id, parent_map, sites)
        if not urls:
            skipped["no_candidate_url"] += 1
            continue
        if distance > args.inherit_depth:
            skipped["ancestor_page_too_far"] += 1
            continue
        plan.append((node, urls, site_from))
        if args.limit and len(plan) >= args.limit:
            break

    distinct_pages = {u for _, urls, _ in plan for u in urls}
    print(f"nodes selected {len(nodes)}  to check {len(plan)}  distinct pages {len(distinct_pages)}  skipped {dict(skipped)}")
    if args.dry_run:
        for node, urls, site_from in plan[:50]:
            print(f"  {node.get('id')}  <-  {', '.join(urls)}  (site of {site_from})")
        if len(plan) > 50:
            print(f"  ... {len(plan) - 50} more")
        return 0

    # One fetch per page per run. The text is what the checker sees, so it is
    # what gets cached; a fetch error is cached too, as the exception.
    page_cache: dict[str, str | Exception] = {}
    last_fetch = 0.0

    def fetch(url: str) -> str:
        nonlocal last_fetch
        if url not in page_cache:
            wait = args.sleep - (time.monotonic() - last_fetch)
            if wait > 0:
                time.sleep(wait)
            try:
                page_cache[url] = page_text(request_text(url, timeout=args.timeout))
            except Exception as error:  # noqa: BLE001
                page_cache[url] = error
            last_fetch = time.monotonic()
        cached = page_cache[url]
        if isinstance(cached, Exception):
            raise cached
        return cached

    outcomes = Counter()
    store = {"_note": "Written by scripts/verify_base_graph.py. Each record is the outcome of fetching the URLs listed at checkedAt; nothing here was typed by hand.", "nodes": evidence}
    for index, (node, urls, site_from) in enumerate(plan, 1):
        record = verify_node(node, urls, fetch=fetch, site_from=site_from, timeout=args.timeout)
        evidence[str(node["id"])] = record
        outcomes[record["status"]] += 1
        write_json_file(args.evidence, store)
        if record["status"] != CONFIRMED or index % 25 == 0:
            print(f"[{index}/{len(plan)}] {record['status']:<13} {node.get('id')}")

    print(f"\ndone: {dict(outcomes)}  evidence records now {len(evidence)}  -> {args.evidence}")
    return 0 if outcomes.get(FETCH_FAILED, 0) < len(plan) or not plan else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
