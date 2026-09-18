"""Does this page label these units? Read-only, so a nomination can be a reading.

    python scripts/probe_candidate_pages.py --url https://www.uspto.gov/ --ids exec-dept-doc-uspto
    python scripts/probe_candidate_pages.py --url https://www.commerce.gov/bureaus-and-offices \
        --ids exec-dept-doc --with-children
    python scripts/probe_candidate_pages.py --plan plan.json        # many pages, one polite run
    python scripts/probe_candidate_pages.py --uncovered             # what still has no page, no fetch

`docs/SOURCE_NOMINATION_RUNBOOK.md` says the job is to name a URL the
verifier should fetch, and that an agent with network should "fetch the
parent's page, read the links it actually carries, and nominate the ones it
names. That turns a guess into a reading." Every prior pass ran without
network and nominated from memory: 304 organisations still have no candidate
page, and the declines include units that plainly do have one — USPTO was
declined `covered_by_parent` while uspto.gov exists, MDA and SAMHSA were
declined `no_public_page_known`.

This script is the reading. It fetches a candidate page once, under the same
robots policy, User-Agent and readable-text floor the verifier uses, and runs
**the verifier's own label test** (`find_label_region_rule`) for each unit you
name. So its answer is the answer `verify_base_graph.py` will give, computed
before a fetch is spent on a URL that was never going to confirm.

It writes nothing: no evidence file, no `official_sites.json`, no `output/`,
no curated file. It prints, exactly like `probe_treasury_rows.py` and
`probe_post_titles.py`, and what it prints is an argument for a nomination,
never a nomination and never a confirmation. Only `verify_base_graph.py`
publishes, and it re-fetches and re-decides for itself.

Two things it deliberately does NOT do. It does not rank or choose a URL —
naming candidates is the agent's job and this is the instrument, not the
hand. And it never reports a `navigation` match as equivalent to a `content`
one: a label in a site-wide mega-menu holds for every page on the host, which
is load-bearing evidence for an organisation and furniture for a post, so the
region is printed on every line and the caller decides what it is worth.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.crawler.official_directory import USER_AGENT, request_text  # noqa: E402
from data_pipeline.exporter.build_graph import (  # noqa: E402
    DEFAULT_BASE_GRAPH,
    index_tree,
    is_post_node,
    load_base_graph,
)
from data_pipeline.verification.evidence import (  # noqa: E402
    DEFAULT_SITES_PATH,
    REGION_CONTENT,
    find_label_region_rule,
    folds_committee,
    load_official_sites,
    parse_page,
    uncheckable_reason_for_node,
)
from data_pipeline.verification.politeness import RobotsPolicy  # noqa: E402

#: What a probe of one (page, unit) pair concluded. The strings are the ones
#: printed, and they are deliberately not the verifier's own status words:
#: this script decides nothing, and a reader must never be able to mistake
#: its output for a record in `evidence.json`.
LABELLED = "labelled"
LABELLED_IN_NAV = "labelled-in-site-navigation"
NOT_LABELLED = "not-labelled"
UNCHECKABLE = "uncheckable"


def probe_page(page, nodes: list[dict]) -> list[dict]:
    """Run the verifier's label test for each node against one parsed page."""
    results = []
    for node in nodes:
        name = str(node.get("name") or "")
        reason = uncheckable_reason_for_node(node)
        if reason:
            results.append({"id": node.get("id"), "name": name, "verdict": UNCHECKABLE, "detail": reason})
            continue
        fold = folds_committee(node)
        hit = find_label_region_rule(name, page, fold_committee=fold, is_post=is_post_node(node),
                                     regions_allowed=(REGION_CONTENT,))
        if hit:
            results.append({"id": node.get("id"), "name": name, "verdict": LABELLED,
                            "matchedText": hit[0], "region": hit[1], "matchRule": hit[2]})
            continue
        # The same search with the region restriction lifted. Reported under
        # its own verdict and never folded into the first: for an
        # organisation a mega-menu listing is real evidence the verifier will
        # accept, and for a post it is furniture the verifier refuses. The
        # asymmetry is the verifier's, and printing the region is how this
        # script stays out of it.
        anywhere = find_label_region_rule(name, page, fold_committee=fold, is_post=is_post_node(node))
        if anywhere:
            results.append({"id": node.get("id"), "name": name, "verdict": LABELLED_IN_NAV,
                            "matchedText": anywhere[0], "region": anywhere[1], "matchRule": anywhere[2],
                            "detail": "a post is never confirmed from site-wide chrome; an organisation can be"
                                      if is_post_node(node) else "site-wide chrome: holds for every page on this host"})
            continue
        results.append({"id": node.get("id"), "name": name, "verdict": NOT_LABELLED})
    return results


def expand_ids(ids: list[str], node_map: dict, with_children: bool) -> list[dict]:
    seen: dict[str, dict] = {}
    for nid in ids:
        node = node_map.get(nid)
        if not node:
            print(f"  ! no such node: {nid}", file=sys.stderr)
            continue
        seen.setdefault(nid, node)
        if with_children:
            for child in node.get("children") or []:
                cid = str(child.get("id") or "")
                if cid:
                    seen.setdefault(cid, child)
    return list(seen.values())


def print_uncovered(node_map: dict, parent_map: dict, sites: dict, limit: int) -> None:
    """The working list: organisations the verifier has nothing to fetch for."""
    rows = []
    for nid, node in node_map.items():
        if is_post_node(node) or node.get("synthetic") or nid in sites:
            continue
        parent = parent_map.get(nid)
        rows.append((nid, str(node.get("name") or ""), str(node.get("type") or ""),
                     len(node.get("children") or []),
                     "parent has a page" if parent in sites else "parent has none"))
    rows.sort()
    print(f"organisations with no candidate page: {len(rows)}  "
          f"(children beneath them: {sum(r[3] for r in rows)})")
    for row in rows[: limit or len(rows)]:
        print(f"  {row[0][:58]:60s} {row[2][:18]:20s} kids {row[3]:3d}  {row[4]}")
    if limit and len(rows) > limit:
        print(f"  ... {len(rows) - limit} more")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--sites", type=Path, default=DEFAULT_SITES_PATH)
    parser.add_argument("--url", action="append", default=[], help="a candidate page to read")
    parser.add_argument("--ids", nargs="*", default=[], help="the units to test against every --url")
    parser.add_argument("--with-children", action="store_true", help="also test each id's own children")
    parser.add_argument("--plan", type=Path, help='JSON: [{"url": "...", "ids": [...], "withChildren": true}]')
    parser.add_argument("--uncovered", action="store_true", help="list organisations with no page; fetch nothing")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--ignore-robots", action="store_true")
    args = parser.parse_args(argv[1:] if argv else None)

    root = load_base_graph(args.base_graph)
    node_map, parent_map = index_tree(root)
    sites = load_official_sites(args.sites)

    if args.uncovered:
        print_uncovered(node_map, parent_map, sites, args.limit)
        return 0

    plan: list[dict] = []
    if args.plan:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        if not isinstance(plan, list):
            print("--plan must hold a JSON list", file=sys.stderr)
            return 1
    for url in args.url:
        plan.append({"url": url, "ids": list(args.ids), "withChildren": args.with_children})
    if not plan:
        parser.error("give --url (with --ids), --plan, or --uncovered")

    robots = RobotsPolicy(user_agent=USER_AGENT, timeout=args.timeout, enabled=not args.ignore_robots)
    totals, report, last_fetch = Counter(), [], 0.0
    for entry in plan:
        url = str(entry.get("url") or "")
        nodes = expand_ids([str(i) for i in (entry.get("ids") or [])], node_map,
                           bool(entry.get("withChildren", args.with_children)))
        block: dict = {"url": url, "ids": [n.get("id") for n in nodes]}
        allowed, why = robots.allows(url)
        if not allowed:
            totals["refused"] += 1
            block["error"] = f"refused by policy: {why}"
            report.append(block)
            if not args.json:
                print(f"\n{url}\n  REFUSED — {why}")
            continue
        wait = max(args.sleep, robots.crawl_delay(url)) - (time.monotonic() - last_fetch)
        if wait > 0:
            time.sleep(wait)
        try:
            page = parse_page(request_text(url, timeout=args.timeout))
        except Exception as error:  # noqa: BLE001 — a failed fetch concludes nothing
            totals["fetch_failed"] += 1
            block["error"] = f"{error.__class__.__name__}: {error}"
            report.append(block)
            if not args.json:
                print(f"\n{url}\n  FETCH FAILED — {error.__class__.__name__}: {error}")
            last_fetch = time.monotonic()
            continue
        last_fetch = time.monotonic()
        # The verifier's own floor. Below it a page is a banner and a footer
        # around no body, and it records nothing either way -- so a probe that
        # called such a page "not labelled" would be predicting a verdict the
        # verifier will never reach.
        block["readable"] = page.readable
        block["contentChars"] = page.content_chars
        block["results"] = probe_page(page, nodes)
        for row in block["results"]:
            totals[row["verdict"]] += 1
        report.append(block)
        if not args.json:
            floor = "" if page.readable else "  (BELOW the readable-text floor: the verifier would record nothing)"
            print(f"\n{url}  [{page.content_chars} readable chars]{floor}")
            for row in block["results"]:
                extra = f'  as "{row["matchedText"][:70]}" [{row.get("region")}]' if row.get("matchedText") else ""
                rule = f'  rule={row["matchRule"]}' if row.get("matchRule") else ""
                detail = f'  ({row["detail"]})' if row.get("detail") and not row.get("matchedText") else ""
                print(f"   {row['verdict']:28s} {row['name'][:46]:48s}{extra}{rule}{detail}")
    if args.json:
        json.dump({"totals": dict(totals), "pages": report}, sys.stdout, indent=1)
        print()
    else:
        print(f"\ntotals: {dict(totals)}")
        print("This is a reading, not a record. Only scripts/verify_base_graph.py publishes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
