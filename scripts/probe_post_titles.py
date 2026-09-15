"""Which post titles an organisation's own page carries, and which it does not.

    python scripts/probe_post_titles.py --dry-run          # what would be fetched
    python scripts/probe_post_titles.py --ids exec-dept-doj exec-dept-state
    python scripts/probe_post_titles.py --unmatched-only   # just the gaps
    python scripts/probe_post_titles.py                    # every org with a page and posts

Read-only, like `probe_treasury_rows.py`: it fetches, compares, prints, and
writes nothing at all — no evidence file, no curated file, no output/. Its
job is to tell a curator what the government's own page calls a post, so
CURATION.md can carry a proposal instead of a guess.

It exists because of what the 2026-09-15 position pass found. The verifier
now checks each post against its organisation's page, and most cabinet
Secretaries still came back `inconclusive` — not because the page is silent
about them, but because the graph calls them something no page will ever
say. Fourteen of the fifteen departments carry a node named
"Secretary of Department of <the department's full name>":

    Secretary of Department of the Treasury      (the office: Secretary of the Treasury)
    Secretary of Department of State             (the office: Secretary of State)
    Secretary of Department of Justice (DOJ)     (there is no such office; DOJ's head
                                                  is the Attorney General)

Those names are template output — 839 position nodes contain their parent
organisation's name verbatim — and the fix is a rename in the curated file,
which is curation work and is never done by widening the matcher. Loosening
label equality until "Secretary of Department of State" matched "Secretary
of State" would also make "Office of Science" match "Office of Science and
Technology Policy", which is the exact failure this project's verifier was
rebuilt to close. So: the matcher stays strict, the verifier keeps saying
`inconclusive`, and this script prints the page's own words for a human to
adjudicate.

Two things are reported per organisation:

  labelled    — a curated post whose title the page carries. Nothing to do.
  not labelled — a curated post the page does not carry as a label. Could be
                 a wrong curated name, or a page that simply does not list
                 its staff. This script does not guess which.
  on the page, no node — a label on the page that reads like an office title
                 and that no curated post under this organisation matches.
                 A CANDIDATE for curation, never a fact: the page's
                 navigation and body are both scanned here, and a title in a
                 mega-menu may belong to a different unit entirely.
"""

from __future__ import annotations

import argparse
import re
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
    canonical_name_key,
    index_tree,
    is_post_node,
    load_base_graph,
)
from data_pipeline.verification.evidence import (  # noqa: E402
    DEFAULT_SITES_PATH,
    REGION_CONTENT,
    find_label_region_rule,
    load_official_sites,
    parse_page,
    uncheckable_reason_for_node,
)
from data_pipeline.verification.politeness import RobotsPolicy  # noqa: E402

#: A label has to start with one of these to be offered as a possible post.
#: Deliberately a closed list of office words rather than anything clever: an
#: open-ended "does this look like a job title" test would fill the report
#: with page furniture, and a curator reading 400 lines of noise reads none
#: of them. Missing a real title costs nothing here — the script proposes,
#: it never concludes.
OFFICE_WORDS = (
    "secretary", "deputy secretary", "under secretary", "assistant secretary",
    "attorney general", "deputy attorney general", "solicitor general",
    "administrator", "deputy administrator", "director", "deputy director",
    "commissioner", "deputy commissioner", "chief", "inspector general",
    "general counsel", "chair", "chairman", "chairwoman", "president",
    "vice president", "speaker", "clerk", "sergeant at arms", "surgeon general",
    "archivist", "librarian", "comptroller general", "public printer",
)
#: Long labels are sentences, not titles.
MAX_TITLE_TOKENS = 8


def looks_like_an_office(key: str) -> bool:
    tokens = key.split()
    if not (2 <= len(tokens) <= MAX_TITLE_TOKENS):
        return False
    return any(key == word or key.startswith(word + " ") for word in OFFICE_WORDS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--sites", type=Path, default=DEFAULT_SITES_PATH)
    parser.add_argument("--ids", nargs="*", default=[], help="only these organisation ids")
    parser.add_argument("--limit", type=int, default=0, help="stop after this many organisations (0 = all)")
    parser.add_argument("--unmatched-only", action="store_true", help="print only the gaps")
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--ignore-robots", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="print the plan; fetch nothing")
    args = parser.parse_args(argv[1:] if argv else None)

    root = load_base_graph(args.base_graph)
    node_map, parent_map = index_tree(root)
    sites = load_official_sites(args.sites)

    posts_by_parent: dict[str, list[dict]] = {}
    for node in node_map.values():
        if not is_post_node(node):
            continue
        parent = parent_map.get(str(node.get("id") or ""))
        if parent and parent in sites:
            posts_by_parent.setdefault(parent, []).append(node)

    targets = [oid for oid in posts_by_parent if not args.ids or oid in args.ids]
    targets.sort()
    if args.limit:
        targets = targets[: args.limit]
    print(f"organisations with a page and posts beneath them: {len(targets)}  "
          f"posts covered: {sum(len(posts_by_parent[o]) for o in targets)}")
    if args.dry_run:
        for oid in targets[:40]:
            print(f"  {oid}  <-  {', '.join(sites[oid])}  ({len(posts_by_parent[oid])} posts)")
        if len(targets) > 40:
            print(f"  ... {len(targets) - 40} more")
        return 0

    robots = RobotsPolicy(user_agent=USER_AGENT, timeout=args.timeout, enabled=not args.ignore_robots)
    totals = Counter()
    last_fetch = 0.0
    for oid in targets:
        org = node_map[oid]
        pages = []
        for url in sites[oid]:
            allowed, why = robots.allows(url)
            if not allowed:
                totals["page_refused"] += 1
                print(f"\n{org.get('name')} ({oid})\n  {url}: refused by policy ({why})")
                continue
            wait = max(args.sleep, robots.crawl_delay(url)) - (time.monotonic() - last_fetch)
            if wait > 0:
                time.sleep(wait)
            try:
                pages.append((url, parse_page(request_text(url, timeout=args.timeout))))
            except Exception as error:  # noqa: BLE001 — a failed fetch concludes nothing
                totals["fetch_failed"] += 1
                print(f"\n{org.get('name')} ({oid})\n  {url}: {error.__class__.__name__}: {error}")
            last_fetch = time.monotonic()
        if not pages:
            continue

        labelled, missing, refused, chrome = [], [], [], []
        for post in posts_by_parent[oid]:
            name = str(post.get("name") or "")
            reason = uncheckable_reason_for_node(post)
            if reason:
                refused.append((name, reason))
                continue
            hit = chrome_hit = None
            for url, page in pages:
                found = find_label_region_rule(name, page, is_post=True, regions_allowed=(REGION_CONTENT,))
                if found:
                    hit = (found[0], url)
                    break
                # The same search with the region restriction lifted. Reported
                # separately and never as a confirmation: it is the measured
                # cost of the content-only rule, which is a design choice and
                # should be arguable from a number rather than from taste.
                anywhere = find_label_region_rule(name, page, is_post=True)
                if anywhere and chrome_hit is None:
                    chrome_hit = (anywhere[0], url)
            if hit:
                labelled.append((name, hit))
            elif chrome_hit:
                chrome.append((name, chrome_hit))
            else:
                missing.append((name, None))

        # Labels on the page that read like an office and match no curated post.
        curated_keys = {canonical_name_key(p.get("name")) for p in posts_by_parent[oid]}
        orphans: dict[str, str] = {}
        for url, page in pages:
            for fragment, region in zip(page.fragments, page.regions):
                for part in re.split(r"\s*[—–|·•:>›»/·]\s*|\s+[-–]\s+|\n+", fragment):
                    key = canonical_name_key(part)
                    if key and key not in curated_keys and looks_like_an_office(key):
                        orphans.setdefault(key, f"{part.strip()[:80]} [{region}]")

        totals["labelled"] += len(labelled)
        totals["labelled_in_chrome_only"] += len(chrome)
        totals["not_labelled"] += len(missing)
        totals["refused_bare_title"] += len(refused)
        totals["on_page_no_node"] += len(orphans)
        if args.unmatched_only and not missing and not orphans and not chrome:
            continue
        print(f"\n{org.get('name')} ({oid})")
        for url, _ in pages:
            print(f"  page: {url}")
        if not args.unmatched_only:
            for name, hit in labelled:
                print(f"  labelled            {name!r}  as {hit[0]!r}")
        for name, hit in chrome:
            print(f"  chrome only         {name!r}  as {hit[0]!r}  (site furniture; never published for a post)")
        for name, _ in missing:
            print(f"  not labelled        {name!r}")
        for name, reason in refused:
            print(f"  not checkable       {name!r}  ({reason})")
        for key in sorted(orphans):
            print(f"  on the page, no node {orphans[key]!r}")

    print(f"\ntotals: {dict(totals)}")
    print("Nothing was written. Titles under \"on the page, no node\" are candidates for "
          "CURATION.md, not facts: this script proposes and never concludes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
