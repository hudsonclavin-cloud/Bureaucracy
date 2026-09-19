"""Mark a unit the government has replaced, without deleting anything.

The graph is a record of the federal government, and governments reorganise.
Until now this file had no way to say so: a unit that had been merged, renamed
away or abolished either sat in the tree as though it still existed — which is
the site claiming something false — or would have had to be deleted, which
throws away a real record of what the government used to be, along with every
source, cost and placement anybody ever earned for it.

So nothing is ever deleted. A superseded node keeps its id, its name, its
description, its evidence and its place in the tree exactly as they were, and
gains four fields saying that the government has moved on:

    lifecycle:        "superseded"
    supersededOn:     the date the change took effect, as the source states it
    supersededBy:     the ids of the nodes that replaced it, possibly none
    supersededSource: {url, quote, readAt} — the page, and its own words

The viewer hides these unless the reader ticks "also show units the government
has replaced", so the default view is the government as it stands. The cost
cascade takes them out of the sibling weights entirely rather than merely
denying them a share: left in the denominator a replaced unit would divide a
real pool by a phantom and quietly shrink every living sibling's estimate.

**A supersession is a positive claim and needs a source that says it.** This is
the fifth sanctioned writer of the curated file and it follows the same
discipline as the rename table: the table proposes, the page decides. A row
names a page and the exact words on it, and this run fetches that page — under
the verifier's robots policy, User-Agent and readable-text floor — and refuses
the row unless the quote is really there, now. A claim that a unit no longer
exists is exactly the kind a project like this must not make on somebody's
recollection, and the VA's networks are the standing reminder why: one true
sentence on an official page ("comprises 5 Veterans Integrated Service
Networks") sat a few lines below that same page's own list of eighteen, and
nineteen nodes were nearly restructured on it. See CURATION.md §10.

It is reversible by construction: delete the row and the next run withdraws the
four fields, because every field it owns is cleared before the table is applied.
"""

from __future__ import annotations

import argparse
import json
import re
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
    LIFECYCLE_SUPERSEDED,
    index_tree,
    load_base_graph,
)
from data_pipeline.json_io import write_json_file  # noqa: E402
from data_pipeline.verification.evidence import parse_page  # noqa: E402
from data_pipeline.verification.politeness import RobotsPolicy  # noqa: E402

DEFAULT_TABLE = PROJECT_ROOT / "data" / "curation" / "superseded.json"

#: Exactly the fields this script owns. Cleared on every run before the table is
#: applied, so removing a row is a real withdrawal rather than a row that stops
#: being re-asserted while its claim stays on the node forever.
OWNED_FIELDS = ("lifecycle", "supersededOn", "supersededBy", "supersededSource")

#: An official page, by the same standard the rest of this project uses.
OFFICIAL_HOST = re.compile(r"^https://[^/]*\.(gov|mil)(/|$)", re.IGNORECASE)


def normalise(text: str) -> str:
    """Whitespace-folded, for quoting a page that is hard-wrapped or padded."""
    return re.sub(r"\s+", " ", str(text or "")).strip()


def load_table(path: Path) -> list[dict]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("superseded") if isinstance(payload, dict) else payload
    return list(rows or [])


def static_refusal(row: dict, node_map: dict, today: str) -> tuple[str, str] | None:
    node_id = str(row.get("id") or "")
    if node_id not in node_map:
        return "no_such_node", f"{node_id} is not in the curated file"
    url = str(row.get("url") or "")
    if not OFFICIAL_HOST.match(url):
        return "source_is_not_official", f"{url!r} is not an https .gov/.mil URL"
    if not normalise(row.get("quote")):
        return "row_quotes_nothing", "a supersession must quote the words that say it"
    on = str(row.get("supersededOn") or "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", on):
        return "date_is_not_an_iso_date", f"{on!r}"
    if on > today:
        return "date_is_in_the_future", f"{on} is after {today}"
    for replacement in row.get("supersededBy") or []:
        if str(replacement) not in node_map:
            return "replacement_is_not_a_node", f"{replacement} is not in the curated file"
    if str(row.get("id")) in {str(r) for r in (row.get("supersededBy") or [])}:
        return "node_replaces_itself", node_id
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv[1:] if argv else None)

    root = load_base_graph(args.base_graph)
    node_map, _ = index_tree(root)
    rows = load_table(args.table)
    today = date.today().isoformat()

    #: Withdraw first, apply second. A node dropped from the table must stop
    #: being marked, and a node whose row now fails its check must stop too.
    withdrawn = []
    for node in node_map.values():
        if any(field in node for field in OWNED_FIELDS):
            withdrawn.append(str(node.get("id")))
            for field in OWNED_FIELDS:
                node.pop(field, None)

    robots = RobotsPolicy(user_agent=USER_AGENT, timeout=args.timeout)
    pages: dict[str, tuple[str, object]] = {}
    results: list[dict] = []
    marked: list[str] = []
    last_fetch = 0.0

    for row in rows:
        node_id = str(row.get("id") or "")
        verdict = static_refusal(row, node_map, today)
        if verdict:
            results.append({"id": node_id, "marked": False, "reason": verdict[0], "detail": verdict[1]})
            continue
        url = str(row.get("url"))
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
                except Exception as error:  # noqa: BLE001 — a failed fetch marks nothing
                    pages[url] = ("failed", f"{error.__class__.__name__}: {error}")
                last_fetch = time.monotonic()
        kind, value = pages[url]
        if kind != "page":
            results.append({"id": node_id, "marked": False, "reason": f"page_{kind}", "detail": str(value)})
            continue
        page = value
        if not page.readable:
            results.append({"id": node_id, "marked": False, "reason": "page_below_the_readable_floor",
                            "detail": f"{page.content_chars} readable chars"})
            continue
        quote = normalise(row.get("quote"))
        haystack = normalise(" ".join(page.fragments))
        if quote.casefold() not in haystack.casefold():
            # The claim rests on these words. If the page has stopped saying
            # them the claim has to stop too, and saying so is the whole job.
            results.append({"id": node_id, "marked": False, "reason": "page_no_longer_carries_the_quote",
                            "detail": url})
            continue

        node = node_map[node_id]
        node["lifecycle"] = LIFECYCLE_SUPERSEDED
        node["supersededOn"] = str(row["supersededOn"])
        node["supersededBy"] = [str(r) for r in (row.get("supersededBy") or [])]
        node["supersededSource"] = {"url": url, "quote": quote, "readAt": today}
        marked.append(node_id)
        results.append({"id": node_id, "marked": True, "name": node.get("name"), "url": url})

    changed = bool(marked) or bool(withdrawn)
    if args.json:
        print(json.dumps({"marked": len(marked), "withdrawnFirst": withdrawn, "results": results}, indent=1))
    else:
        for item in results:
            if item.get("marked"):
                print(f"  superseded  {item['name']!r}  ({item['id']})\n      {item['url']}")
        refused = [r for r in results if not r.get("marked")]
        if refused:
            print(f"\nnot marked ({len(refused)}):")
            for item in refused:
                print(f"  {str(item['id'])[:56]:58s} {item['reason']}")
                if item.get("detail"):
                    print(f"      {str(item['detail'])[:150]}")
        still = [n for n in withdrawn if n not in marked]
        if still:
            print(f"\nwithdrawn — no longer marked superseded ({len(still)}): {', '.join(still[:10])}")
        print(f"\nmarked {len(marked)}  refused {len(results) - len(marked)}  of {len(rows)} rows")
    if args.dry_run:
        print("dry run: nothing written.")
        return 0
    if changed:
        write_json_file(args.base_graph, root)
        print(f"wrote {args.base_graph}")
    else:
        print("nothing to do; the curated file is unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
