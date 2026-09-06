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

from data_pipeline.crawler.official_directory import USER_AGENT, request_text  # noqa: E402
from data_pipeline.exporter.build_graph import DEFAULT_BASE_GRAPH, index_tree, load_base_graph  # noqa: E402
from data_pipeline.json_io import write_json_file  # noqa: E402
from data_pipeline.verification.evidence import (  # noqa: E402
    CONFIRMED,
    DEFAULT_EVIDENCE_PATH,
    DEFAULT_SITES_PATH,
    FETCH_FAILED,
    NOT_CHECKABLE,
    PLACEMENT_LISTED,
    PLACEMENT_ONLY,
    candidate_urls,
    load_evidence,
    load_official_sites,
    uncheckable_reason,
    utc_now_iso,
    verify_node,
    verify_placement,
)
from data_pipeline.verification.politeness import RobotsPolicy  # noqa: E402


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
    parser.add_argument("--ignore-robots", action="store_true", help="do not read robots.txt (use only with the site owner's agreement)")
    parser.add_argument("--no-placement", action="store_true", help="skip the placement pass (parent pages naming their children)")
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

    now = utc_now_iso()
    plan: list[tuple[dict[str, Any], list[str], str | None, bool]] = []
    skipped = Counter()
    for node in nodes:
        node_id = str(node.get("id") or "")
        prior = evidence.get(node_id)
        if prior and prior.get("status") == CONFIRMED and not args.recheck:
            skipped["already_confirmed"] += 1
            continue
        reason = uncheckable_reason(node.get("name"))
        if reason:
            # Recorded, not fetched: a curator's label ("Individual Senator
            # Offices (100)") or a name too generic to distinguish anything
            # ("Energy"). Neither a hit nor a miss would mean anything.
            evidence[node_id] = {
                "name": node.get("name"), "status": NOT_CHECKABLE, "reason": reason, "checkedAt": now,
            }
            skipped[reason] += 1
            continue
        urls, site_from, distance = candidate_urls(node_id, parent_map, sites)
        if not urls:
            skipped["no_candidate_url"] += 1
            continue
        if distance > args.inherit_depth:
            skipped["ancestor_page_too_far"] += 1
            continue
        plan.append((node, urls, site_from, distance == 0))
        if args.limit and len(plan) >= args.limit:
            break

    # Placement pass: every organisation whose PARENT has a page of its own is
    # checked against that page, whether or not the child has one too. That
    # is a different question from existence — "does the department's own
    # page list this bureau?" is evidence for the edge, which is the site's
    # central claim and the one thing nothing had checked.
    placement_plan: list[tuple[dict[str, Any], str, list[str]]] = []
    if not args.no_placement:
        for node in nodes:
            node_id = str(node.get("id") or "")
            parent_id = parent_map.get(node_id)
            if not parent_id or parent_id not in sites or uncheckable_reason(node.get("name")):
                continue
            prior = evidence.get(node_id) or {}
            existing = prior.get("placement") if isinstance(prior.get("placement"), dict) else None
            if (
                existing
                and existing.get("status") == PLACEMENT_LISTED
                and existing.get("parentId") == parent_id
                and str(existing.get("url") or "") in sites[parent_id]
                and not args.recheck
            ):
                skipped["placement_already_listed"] += 1
                continue
            if args.limit and len(plan) + len(placement_plan) >= args.limit:
                break
            placement_plan.append((node, parent_id, list(sites[parent_id])))

    distinct_pages = {u for _, urls, _, _ in plan for u in urls} | {u for _, _, urls in placement_plan for u in urls}
    print(
        f"nodes selected {len(nodes)}  to check {len(plan)}  placements to check {len(placement_plan)}  "
        f"distinct pages {len(distinct_pages)}  skipped {dict(skipped)}"
    )
    if args.dry_run:
        for node, urls, site_from, own in plan[:50]:
            print(f"  {node.get('id')}  <-  {', '.join(urls)}  ({'own page' if own else 'page of ' + str(site_from)})")
        if len(plan) > 50:
            print(f"  ... {len(plan) - 50} more")
        for node, parent_id, urls in placement_plan[:20]:
            print(f"  placement: {node.get('id')}  under {parent_id}  <-  {', '.join(urls)}")
        if len(placement_plan) > 20:
            print(f"  ... {len(placement_plan) - 20} more placements")
        return 0

    # One fetch per page per run. The text is what the checker sees, so it is
    # what gets cached; a fetch error is cached too, as the exception.
    page_cache: dict[str, str | Exception] = {}
    last_fetch = 0.0
    robots = RobotsPolicy(user_agent=USER_AGENT, timeout=args.timeout, enabled=not args.ignore_robots)

    def fetch(url: str) -> str:
        nonlocal last_fetch
        if url not in page_cache:
            allowed, why = robots.allows(url)
            if not allowed:
                page_cache[url] = PermissionError(f"robots.txt disallows this path ({why})")
            else:
                wait = max(args.sleep, robots.crawl_delay(url)) - (time.monotonic() - last_fetch)
                if wait > 0:
                    time.sleep(wait)
                try:
                    page_cache[url] = request_text(url, timeout=args.timeout)
                except Exception as error:  # noqa: BLE001
                    page_cache[url] = error
                last_fetch = time.monotonic()
        cached = page_cache[url]
        if isinstance(cached, Exception):
            raise cached
        return cached

    outcomes = Counter(r["status"] for r in evidence.values() if r.get("status") == NOT_CHECKABLE)
    store = {
        "_note": (
            "Written by scripts/verify_base_graph.py. Each record is the outcome of looking for the node's "
            "name as a label on the URLs listed, at checkedAt; nothing here was typed by hand. "
            "confirmed = a fragment of the page is the name; not_found = the unit's own page was read and "
            "did not name it; inconclusive = only an ancestor's page was read, which is not obliged to; "
            "fetch_failed = no page was read; not_checkable = the curated name could not be evidence; "
            "placement_only = only the parent's page was read, for the edge above the node. "
            "placement.listed = the parent's page names the unit as a label; placement.not_listed = the pages in "
            "urlsRead were read and none does."
        ),
        "nodes": evidence,
    }
    for index, (node, urls, site_from, own_page) in enumerate(plan, 1):
        record = verify_node(node, urls, fetch=fetch, now=now, site_from=site_from, is_own_page=own_page)
        prior_block = (evidence.get(str(node["id"])) or {}).get("placement")
        if isinstance(prior_block, dict):
            # The existence record is replaced wholesale; the edge evidence
            # gathered by a previous placement pass rides along, and only the
            # placement pass below may replace it.
            record["placement"] = prior_block
        evidence[str(node["id"])] = record
        outcomes[record["status"]] += 1
        write_json_file(args.evidence, store)
        if record["status"] != CONFIRMED or index % 25 == 0:
            print(f"[{index}/{len(plan)}] {record['status']:<14} {node.get('id')}")

    placements = Counter()
    for index, (node, parent_id, parent_urls) in enumerate(placement_plan, 1):
        block = verify_placement(node, parent_id, parent_urls, fetch=fetch, now=now)
        node_id = str(node["id"])
        if block is None:
            placements["parent_page_unreadable"] += 1
            continue
        record = evidence.setdefault(node_id, {"name": node.get("name"), "checkedAt": now, "status": PLACEMENT_ONLY})
        record["placement"] = block
        placements[block["status"]] += 1
        write_json_file(args.evidence, store)
        if index % 25 == 0:
            print(f"[placement {index}/{len(placement_plan)}] {block['status']:<11} {node_id}")

    write_json_file(args.evidence, store)
    print(f"\ndone: {dict(outcomes)}  placements: {dict(placements)}  evidence records now {len(evidence)}  -> {args.evidence}")
    # Nonzero when the run learned nothing it set out to learn, so a wrapper
    # cannot mistake a blocked network for "checked everything, found nothing".
    attempted = len(plan)
    if attempted and outcomes.get(FETCH_FAILED, 0) == attempted:
        print("every fetch failed: nothing was checked, and nothing was recorded about any node.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
