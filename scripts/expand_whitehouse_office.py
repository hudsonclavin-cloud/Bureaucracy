#!/usr/bin/env python
"""Expand the White House Office subtree from the roster the law requires.

    python scripts/expand_whitehouse_office.py --dry-run
    python scripts/expand_whitehouse_office.py      # edits data/federal_gov_complete_1.json

The curated graph carries 27 position nodes under `exec-eop-who` for an office
the White House's own Annual Report to Congress shows employing 408 people
across 229 distinct titles. `CURATION.md` §7.4 records that gap as the binding
limit on the pay work: 21 of the 27 nodes could not be priced because the
report simply does not print those titles, while the titles it does print had
no node to attach to.

This script closes it from the source itself. It is the only writer of the
White House Office subtree — the curated file is never hand-edited — so a
re-run against a newer report is how the subtree is refreshed.

## What it adds, and what it refuses to invent

One node per distinct title the report prints, and nothing else:

- a title one person holds becomes a single-post node;
- a title several people hold becomes **one** node carrying
  `representsPosts` with the report's own count — the convention the curated
  file already uses ("Deputy Press Secretary (×2)"). It is deliberately not
  N nodes: the report distinguishes those people by name, and this project
  does not publish names, so N indistinguishable nodes would be N claims it
  cannot source.

Nodes are named as the report prints the title, in title case
(`Assistant to the President and Chief of Staff`), not by the function alone.
The rank is part of the post's official title and distinguishes real
seniority: an Assistant to the President, a Deputy Assistant and a Special
Assistant are three different appointments. `whitehouse_pay.py` matches on
equality before the fold, so both spellings reach their row.

Nothing is invented. Each new node's description states only what the roster
says, and carries `descriptionSource: generated_from_whitehouse_staff_report`
so the site does not label it "uncited prose" alongside the curated
descriptions, which is what it would otherwise do to a sourced sentence. Each
also carries `structureSource`, recording that this node exists because an
official roster lists the post — which is more than can be said for the
template positions stamped across the rest of the graph.

## What it will not touch

An existing curated node is never renamed, re-described, re-typed or removed.
A report title that matches one — by equality or with the White House rank
prefix folded off, the same rule `whitehouse_pay.py` uses — is skipped, so
running this twice adds nothing the second time. The 21 curated nodes the
report does not carry are left exactly as they are: this script has no
evidence they are wrong, only that the 2026 roster does not print those
titles, and deleting a curated node on that basis would be a claim it cannot
support.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.json_io import write_json_file  # noqa: E402
from data_pipeline.verification.whitehouse_pay import (  # noqa: E402
    DEFAULT_REPORT_PDF,
    SCOPE_NODE_ID,
    Unreadable,
    canonical,
    load_staff_report,
    title_core,
)

DEFAULT_BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"

#: The curated file's own colour for a position node under this office.
POSITION_COLOR = "#666666"

#: Words a title keeps in lower case, and tokens the report spells as
#: initialisms that must not be title-cased into words.
SMALL_WORDS = {"and", "for", "of", "the", "to", "in", "on", "at", "a", "an", "&"}
KEEP_UPPER = {
    "US", "USA", "AI", "IT", "HR", "NSC", "OMB", "CEA", "ONDCP", "OSTP", "NEC",
    "USTR", "EOP", "WHO", "VA", "DC", "FBI", "CIA", "NSA", "DHS", "DOJ", "DOD",
    "NASA", "NATO", "UN", "G7", "G20", "COO", "CFO", "CIO", "CTO", "CDO",
}


def title_case(text: str) -> str:
    """The report's ALL-CAPS title, cased the way the curated file writes one.

    Deliberately mechanical: first and last word always capitalised, the small
    words lower-cased between them, known initialisms left upper. The report's
    own verbatim string is kept on the node in `reportedTitle`, so nothing is
    lost to this transformation and it can be audited against the source.
    """
    words = str(text or "").split()
    out: list[str] = []
    for index, word in enumerate(words):
        core = word.strip("(),.")
        if core.upper() in KEEP_UPPER:
            out.append(word.upper())
            continue
        lowered = word.lower()
        if index not in (0, len(words) - 1) and lowered.strip("(),.") in SMALL_WORDS:
            out.append(lowered)
            continue
        # Hyphenated and slashed compounds capitalise each part.
        out.append(re.sub(r"[A-Za-z']+", lambda m: m.group(0).capitalize(), lowered))
    return " ".join(out)


def slug(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")
    return re.sub(r"-{2,}", "-", cleaned)


def find_node(node: dict, node_id: str) -> dict | None:
    if str(node.get("id") or "") == node_id:
        return node
    for child in node.get("children") or []:
        found = find_node(child, node_id)
        if found is not None:
            return found
    return None


def existing_keys(who: dict) -> set[str]:
    """Every spelling an existing child already answers to."""
    keys: set[str] = set()
    for child in who.get("children") or []:
        name = str(child.get("name") or "")
        # A curated name may carry the multiplicity in its own text
        # ("Deputy Press Secretary (×2)"); the key is the name without it.
        bare = re.sub(r"\s*\(×[^)]*\)\s*$", "", name)
        keys.add(canonical(bare))
        keys.add(title_core(bare))
    return keys


def all_ids(node: dict, into: set[str]) -> set[str]:
    node_id = str(node.get("id") or "")
    if node_id:
        into.add(node_id)
    for child in node.get("children") or []:
        all_ids(child, into)
    return into


def build_new_nodes(rows, who: dict, taken: set[str]) -> tuple[list[dict], dict]:
    counts = Counter(str(row["title"]) for row in rows)
    salaries: dict[str, list[float]] = {}
    for row in rows:
        salaries.setdefault(str(row["title"]), []).append(float(row["amount"]))

    known = existing_keys(who)
    added: list[dict] = []
    skipped_existing: list[str] = []
    for title in sorted(counts):
        if canonical(title) in known or title_core(title) in known:
            skipped_existing.append(title)
            continue
        held = counts[title]
        name = title_case(title)
        if held > 1:
            name = f"{name} (×{held})"
        node_id = f"{SCOPE_NODE_ID}-{slug(title)}"
        if held > 1:
            node_id = f"{node_id}-{held}"
        suffix = 2
        base_id = node_id
        while node_id in taken:
            node_id = f"{base_id}-{suffix}"
            suffix += 1
        taken.add(node_id)

        if held > 1:
            low, high = min(salaries[title]), max(salaries[title])
            if low == high:
                pay_sentence = (
                    f"The report lists {held} people under this title, each at "
                    f"${low:,.2f} per annum."
                )
            else:
                pay_sentence = (
                    f"The report lists {held} people under this title, paid between "
                    f"${low:,.2f} and ${high:,.2f} per annum."
                )
        else:
            pay_sentence = (
                f"The report lists one person under this title, at "
                f"${salaries[title][0]:,.2f} per annum."
            )

        node = {
            "id": node_id,
            "name": name,
            "type": "Position",
            "desc": (
                f'"{title}" is a post in the White House Office. {pay_sentence} '
                "The report states titles and rates of pay, not duties, so nothing "
                "here describes what the post does."
            ),
            "descriptionSource": "generated_from_whitehouse_staff_report",
            "structureSource": "listed_in_whitehouse_staff_report",
            "reportedTitle": title,
            "employees": None,
            "budget": None,
            "color": POSITION_COLOR,
            "children": [],
        }
        if held > 1:
            node["representsPosts"] = {"text": f"×{held}", "kind": "exact", "count": held}
        added.append(node)

    report = {
        "distinct_titles": len(counts),
        "people_listed": len(rows),
        "already_curated": len(skipped_existing),
        "added": len(added),
        "added_single_post": sum(1 for n in added if "representsPosts" not in n),
        "added_multi_post": sum(1 for n in added if "representsPosts" in n),
        "skipped_existing": skipped_existing,
    }
    return added, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PDF)
    parser.add_argument("--dry-run", action="store_true", help="report what would be added and write nothing")
    args = parser.parse_args((argv or sys.argv)[1:])

    try:
        loaded = load_staff_report(args.report)
    except Unreadable as error:
        print(f"refused: {error}")
        return 1
    parsed = loaded["report"]

    base = json.loads(args.base_graph.read_text(encoding="utf-8"))
    who = find_node(base, SCOPE_NODE_ID)
    if who is None:
        print(f"refused: the base graph carries no {SCOPE_NODE_ID!r} node")
        return 1

    taken = all_ids(base, set())
    added, report = build_new_nodes(parsed["rows"], who, taken)

    print(f"report: as of {parsed['asOfText']}, {report['people_listed']} people, "
          f"{report['distinct_titles']} distinct titles")
    print(f"  already curated under a matching name : {report['already_curated']}")
    print(f"  nodes to add                          : {report['added']} "
          f"({report['added_single_post']} single-post, {report['added_multi_post']} standing for several)")
    print(f"  White House Office children           : {len(who.get('children') or [])} -> "
          f"{len(who.get('children') or []) + report['added']}")
    curated_unmatched = len(who.get("children") or []) - report["already_curated"]
    print(f"  curated nodes the report does not print, left untouched: {curated_unmatched}")
    for node in added[:12]:
        print(f"      + {node['name']}")
    if len(added) > 12:
        print(f"      … and {len(added) - 12} more")

    if args.dry_run:
        return 0
    if not added:
        print("nothing to add; the subtree already carries every title the report prints")
        return 0

    who.setdefault("children", []).extend(added)
    write_json_file(args.base_graph, base)
    print(f"wrote {len(added)} nodes -> {args.base_graph}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
