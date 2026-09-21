"""Rename an organisation to the wording its own official page carries.

`CURATION.md` §8 did this for post titles: the graph said "Secretary of
Department of Justice (DOJ)", justice.gov says "The Attorney General", and the
fix was a rename argued from the page's own wording rather than a loosening of
the matcher. This script is the organisation analogue, and it exists because a
2026-09-18 pass over every organisation with no candidate page found that the
largest single blocker is not a missing URL: for 181 nodes the page was read,
reads fine, and simply does not carry the name this graph uses.

The curated file is never hand-edited, so the renames live in a reviewed table
(`data/curation/unit_renames.json`) and this script is their only writer. The
table is the same shape as `TREASURY_ROW_ALIASES` and `USASPENDING_NAME_ALIASES`:
a human-reviewed identification, with the basis on which the two names denote
one unit written down beside it — and, like those, re-checked against the
source rather than trusted. Every row is verified against the live page on
every run, so a row cannot go stale silently and cannot be a hand-edit wearing
a script's clothes.

**The table proposes; the page decides.** A row is applied only when all of
these hold, and the reason is printed for every one that does not:

  - the node still carries the exact name the row was written against, so a
    rename by another route (or by a later edit of this table) can never be
    overwritten on the strength of a stale reading;
  - the page is fetched now, under the verifier's own robots policy, User-Agent
    and readable-text floor, and **the verifier's own label test** finds the
    proposed name on it — the same test `verify_base_graph.py` will run, so a
    rename this script makes is one that can actually confirm;
  - the region matches what the row claims: a row that did not declare
    `"region": "navigation"` is refused if the only match is in site-wide
    chrome, because a mega-menu label holds for every page on the host;
  - the rename buys something — a proposed name whose canonical key already
    equals the curated one changes no verifier outcome and is refused as a
    no-op, since `canonical_name_key` folds `&`/`and` and drops parentheticals;
  - the proposed name is at least two tokens and is not a bare generic title.
    "Inspector General" names 72 nodes in this graph and every `.gov` footer
    carries a link with those words, which is precisely the furniture match
    `CLAUDE.md` records refusing 18 times;
  - the proposed name does not collide with a SIBLING's. Two nodes under one
    parent sharing a name is a real ambiguity -- nothing downstream could tell
    the listing's two entries apart. Across different parents it is not: the
    House and the Senate each name a subcommittee after the appropriations
    bill it writes, so "Agriculture, Rural Development, Food and Drug
    Administration, and Related Agencies" is the true name of two seats in two
    chambers. The cost of allowing that is stated rather than hidden: a source
    matched by name alone refuses a name reaching two nodes (a statutory title
    "reaching two nodes prices neither"), so a cross-parent duplicate can lose
    a node an unrelated match. It fails safe -- a refusal, never a figure
    attributed to the wrong unit -- and being named what the government names
    it is worth that.

It is idempotent: a row whose node already carries the proposed name is a
no-op, and re-running renames nothing twice.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
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
from data_pipeline.json_io import write_json_file  # noqa: E402
from data_pipeline.verification.aliases import GENERIC_NAMES as ALIAS_GENERIC_NAMES  # noqa: E402
from data_pipeline.verification.evidence import (  # noqa: E402
    REGION_CONTENT,
    find_label_region_rule,
    folds_committee,
    parse_page,
    uncheckable_reason_for_node,
)
from data_pipeline.verification.politeness import RobotsPolicy  # noqa: E402

DEFAULT_TABLE = PROJECT_ROOT / "data" / "curation" / "unit_renames.json"

#: What this script stamps on a node it renames, so the site can say where the
#: name came from. The same two fields `rename_templated_post_titles.py` writes.
NAME_SOURCE = "named_on_its_own_official_page"

#: A proposed name reducing to fewer than this many tokens is refused. One
#: token is a word, not a unit's name; the floor is the organisation analogue
#: of the two-token floor `uncheckable_reason(..., is_post=True)` applies.
MIN_NAME_TOKENS = 2

#: Names too generic to identify a unit even when a page carries them. These
#: are the stamped administrative titles `CLAUDE.md` records recurring 92, 81,
#: 80, 71 and 47 times across 76 organisations, plus the words a `.gov` footer
#: carries as standard furniture. A page labelling one of these says nothing
#: about which unit it means.
#:
#: The list lives in `data_pipeline/verification/aliases.py` and is imported
#: rather than copied: the alternative-names table applies exactly this floor
#: to an alternative for the same reason this one applies it to a proposed
#: name, and two copies would drift.
GENERIC_NAMES = ALIAS_GENERIC_NAMES


def load_table(path: Path) -> list[dict]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("renames") if isinstance(payload, dict) else payload
    return list(rows or [])


def refuse(results: list, row: dict, reason: str, detail: str = "") -> None:
    results.append({"id": row.get("id"), "applied": False, "reason": reason, "detail": detail})


def check_static(row: dict, node: dict | None, siblings: dict) -> tuple[str, str] | None:
    """Everything decidable without a fetch. Returns (reason, detail) or None."""
    node_id = str(row.get("id") or "")
    proposed = str(row.get("to") or "").strip()
    expected = str(row.get("from") or "").strip()
    if not node:
        return "no_such_node", node_id
    if not proposed or not expected:
        return "row_is_incomplete", "a row needs both 'from' and 'to'"
    name = str(node.get("name") or "")
    if name == proposed:
        return "already_applied", "the node already carries the proposed name"
    if name != expected:
        return "curated_name_has_changed", f"the row was written against {expected!r}, the node now reads {name!r}"
    if is_post_node(node):
        return "node_is_a_post", "this script renames organisations; post titles are rename_templated_post_titles.py's"
    key = canonical_name_key(proposed)
    if key == canonical_name_key(name) and not uncheckable_reason_for_node(node):
        # Equal keys usually mean the rename changes nothing -- `canonical_name_key`
        # folds `&`/`and` and drops parentheticals, so those spellings already
        # match. The exception is a name the verifier refuses BEFORE any fetch:
        # "National Laboratories (17)" is a count label, so it is never checked
        # at all, and dropping the count changes the outcome even though the
        # key is identical. Refusing that as a no-op would be wrong.
        return "rename_is_a_no_op", f"both names reduce to {key!r}, so no verifier outcome changes"
    if len(key.split()) < MIN_NAME_TOKENS:
        return "proposed_name_too_short", f"{key!r} is fewer than {MIN_NAME_TOKENS} tokens"
    if key in GENERIC_NAMES:
        return "proposed_name_is_generic", f"{proposed!r} names many units and identifies none"
    owner = siblings.get(key)
    if owner and owner != node_id:
        return "proposed_name_collides_with_a_sibling", f"{owner} already reduces to {key!r}"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    parser.add_argument("--dry-run", action="store_true", help="decide everything, write nothing")
    parser.add_argument("--ids", nargs="*", default=[], help="only these rows")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv[1:] if argv else None)

    root = load_base_graph(args.base_graph)
    node_map, _ = index_tree(root)
    rows = load_table(args.table)
    if args.ids:
        wanted = set(args.ids)
        rows = [r for r in rows if str(r.get("id")) in wanted]

    #: Which node owns each canonical key among its own siblings, so a rename
    #: cannot make two entries of one listing indistinguishable. Built before
    #: any rename is applied, and keyed by (parent, name) rather than by name:
    #: see the collision rule in this module's docstring for why a duplicate
    #: across two different parents is allowed.
    sibling_owner: dict[tuple[str, str], str] = {}
    for parent in list(node_map.values()):
        pid = str(parent.get("id") or "")
        for child in parent.get("children") or []:
            sibling_owner.setdefault((pid, canonical_name_key(child.get("name"))), str(child.get("id") or ""))
    child_parent: dict[str, str] = {}
    for parent in list(node_map.values()):
        for child in parent.get("children") or []:
            child_parent[str(child.get("id") or "")] = str(parent.get("id") or "")

    robots = RobotsPolicy(user_agent=USER_AGENT, timeout=args.timeout)
    results: list[dict] = []
    renames: list[tuple[str, str, str]] = []
    pages: dict[str, object] = {}
    last_fetch = 0.0

    for row in rows:
        node_id = str(row.get("id") or "")
        node = node_map.get(node_id)
        pid = child_parent.get(node_id, "")
        siblings = {key: owner for (owner_pid, key), owner in sibling_owner.items() if owner_pid == pid}
        verdict = check_static(row, node, siblings)
        if verdict:
            refuse(results, row, *verdict)
            continue
        url = str(row.get("url") or "")
        proposed = str(row.get("to") or "").strip()
        if url not in pages:
            allowed, why = robots.allows(url)
            if not allowed:
                pages[url] = ("refused", why)
            else:
                wait = max(args.sleep, robots.crawl_delay(url)) - (time.monotonic() - last_fetch)
                if wait > 0:
                    time.sleep(wait)
                try:
                    pages[url] = ("page", parse_page(request_text(url, timeout=args.timeout)))
                except Exception as error:  # noqa: BLE001 — a failed fetch renames nothing
                    pages[url] = ("failed", f"{error.__class__.__name__}: {error}")
                last_fetch = time.monotonic()
        kind, value = pages[url]
        if kind == "refused":
            refuse(results, row, "page_refused_by_policy", str(value))
            continue
        if kind == "failed":
            refuse(results, row, "page_fetch_failed", str(value))
            continue
        page = value
        if not page.readable:
            refuse(results, row, "page_below_the_readable_floor",
                   f"{page.content_chars} readable chars; the verifier would record nothing from it")
            continue
        fold, post = folds_committee(node), is_post_node(node)
        hit = find_label_region_rule(proposed, page, fold_committee=fold, is_post=post,
                                     regions_allowed=(REGION_CONTENT,))
        region = REGION_CONTENT if hit else None
        if not hit:
            hit = find_label_region_rule(proposed, page, fold_committee=fold, is_post=post)
            region = hit[1] if hit else None
        if not hit:
            refuse(results, row, "page_does_not_label_the_proposed_name", url)
            continue
        if region != REGION_CONTENT and str(row.get("region") or "") != region:
            refuse(results, row, "matched_only_in_site_navigation",
                   "the row does not declare region 'navigation'; chrome holds for every page on the host")
            continue
        results.append({"id": node_id, "applied": True, "from": str(node.get("name")), "to": proposed,
                        "url": url, "matchedText": hit[0], "region": region, "matchRule": hit[2]})
        renames.append((node_id, str(node.get("name")), proposed))
        if not args.dry_run:
            node["name"] = proposed
            node["nameSource"] = NAME_SOURCE
            node["nameSourceDetail"] = url
            node["nameVerifiedAt"] = date.today().isoformat()
            node["nameMatchedText"] = hit[0]

    if args.json:
        print(json.dumps({"applied": len(renames), "results": results}, indent=1))
    else:
        for item in results:
            if item.get("applied"):
                print(f"  {item['from']!r}\n      -> {item['to']!r}   [{item['region']}]  {item['url']}")
        refused = [r for r in results if not r.get("applied")]
        if refused:
            print(f"\nleft alone ({len(refused)}):")
            for item in refused:
                print(f"  {str(item['id'])[:58]:60s} {item['reason']}")
                if item.get("detail"):
                    print(f"      {item['detail'][:150]}")
        print(f"\nrenamed {len(renames)}  refused {len(results) - len(renames)}  of {len(rows)} rows")
    if args.dry_run:
        print("dry run: nothing written.")
        return 0
    if renames:
        write_json_file(args.base_graph, root)
        print(f"wrote {args.base_graph}")
    else:
        print("nothing to do; the curated file is unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
