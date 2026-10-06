#!/usr/bin/env python
"""Every node in the published graph, by what stands where its cost would be,
and the route that would move each class.

    python scripts/report_cost_coverage.py --dry-run   # counts only, writes nothing
    python scripts/report_cost_coverage.py             # writes docs/COST_COVERAGE.md

The owner's standing ask is that every node should come to carry a figure. This
report is the groundwork for that: it classifies every one of the published
nodes into exactly one class -- a measured cost, an apportioned estimate, a
salary, a post no document prices, a unit beneath a negative Treasury pool, a
unit the government has replaced -- says what each class means, and names the
document route that would move it, or says plainly that none can. It is
generated so that "every node is accounted for" is a checkable claim: a test
re-renders it from `output/graph.json` and compares byte for byte, and asserts
that the classes partition the graph.

Nothing here fetches, and nothing here writes to the curated file, the
published graph or any evidence file. The position half defers to
`report_unpriced_positions.py`, whose `classify` gives the reason a post
carries no pay claim, so the two reports can never disagree about a post.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.verification.pay_documents import PAY_FIELDS  # noqa: E402
from scripts.report_unpriced_positions import classify as classify_unpriced_post  # noqa: E402

DEFAULT_GRAPH = PROJECT_ROOT / "output" / "graph.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "COST_COVERAGE.md"

#: A figure an official source states for the unit that is NOT its cost and
#: is published beside the estimate under its own heading. Where one of these
#: is present the node has a sourced, dated figure a reader can see today;
#: what it lacks is a figure this project is willing to head COST.
SOURCED_FIGURES_BESIDE = ("usaspendingOutlays", "ombBudget", "auditedNetCost")

COMMITTEE_TYPES = ("committee", "subcommittee")

#: Class id -> (heading, what it means, the route). Order is the order of the
#: report. Every node lands in exactly one.
CLASSES = {
    "measured_treasury_line": (
        "Measured — a Treasury accounting line",
        "The receipts and transfers the Monthly Treasury Statement nets inside a unit's published "
        "total, carried as explicit children so the arithmetic closes, plus Interest on the Public "
        "Debt and the government-wide offsetting receipts. Not organisations.",
        "Nothing to do: these ARE the statement's own lines.",
    ),
    "measured": (
        "Measured — the Treasury's own figure for the unit",
        "The root's anchor and every Table 5 line applied to the node it names "
        "(`cost_status: official`). The only costs this graph calls measured.",
        "Nothing to do for the node; the statement is re-fetched and re-applied on each run.",
    ),
    "estimate_committee": (
        "Estimate — a committee or subcommittee",
        "An apportioned share of the chamber's measured total. No line of Table 5 names a "
        "committee, so no Treasury alias can ever reach one of these.",
        "Since 2026-10-07 a committee carries `committeeDisbursements` beside the estimate: what its "
        "chamber paid out for the committee's account over a stated period, from the House's "
        "Statement of Disbursements and the Report of the Secretary of the Senate (40 of the 41 "
        "chamber committees). A different basis on a different clock, never a cost. Subcommittees "
        "have no figure of their own in either document.",
    ),
    "estimate_beside_sourced_figure": (
        "Estimate — with a sourced figure already published beside it",
        "An apportioned share, and beside it at least one figure an official source states for "
        "this unit under its own heading: USAspending File A gross outlays (fiscal year to date), "
        "OMB's Public Budget Database outlays (last completed year, summed over the unit's account "
        "rows), or Treasury's audited Statement of Net Cost (last completed year). Each is on the "
        "panel today; none is headed COST, because each measures something different from the "
        "Treasury's net outlays on a different clock.",
        "The decision is the owner's, not a build: whether the headline may fall back to one of "
        "these, labelled by its basis and period, when the Treasury prints no line — the same move "
        "the panel makes since 2026-10-05 for a post's salary. Measured on the 94 nodes that carry "
        "both, not one OMB FY2025 figure agrees with the Treasury line within 1%, so a fallback "
        "would be a different number under a different label, never the same claim.",
    ),
    "estimate": (
        "Estimate — no sourced figure of any kind",
        "An apportioned share of an ancestor's measured total, divided among siblings by budget, "
        "headcount or subtree size. Table 5 stops at the bureau, so divisions, regional offices, "
        "laboratories, centres and the courts beneath a circuit print no line of their own.",
        "Three routes, in order of reach: OMB's Public Budget Database bureau rows (committed; 72 "
        "bureaus matched so far, more need a node whose name the file carries); USAspending File B "
        "by Treasury Account Symbol, which reaches programme level and has not been fetched; an "
        "agency's own Agency Financial Report. Each yields a figure beside the estimate, not a cost, "
        "until the decision above is made.",
    ),
    "salary": (
        "Salary — a pay claim an official document supports",
        "A position carrying at least one of the ten pay fields: a printed rate, a schedule level "
        "priced by OPM's table, a statutory rate, a roster figure, a derivation the block carries "
        "in the open, twelve months of a printed monthly military rate, or a range. Since 2026-10-05 "
        "it is the post's headline figure, headed as pay "
        "and never as COST.",
        "Nothing to do for the node; each pay field is re-derived from its committed document on "
        "every run and withdrawn when the document stops supporting it.",
    ),
    "post_multiplicity": (
        "Post with no figure — stands for several holders",
        "The node's name states a multiplicity and no claim that holds for every holder has "
        "reached it. An incumbency-shaped claim (one listing's level, one row of the current "
        "export) is refused on such a node because it is one appointment's figure, not the group's.",
        "A tier, a statutory rate, a parity provision or a roster listing every holder at one "
        "figure IS published on such a node with a `holders` block. Finding which pay SYSTEM "
        "governs the title is the useful step: it lets the graph carry the schedule rather than a "
        "rate. `docs/UNPRICED_POSITIONS.md` lists every one.",
    ),
    "post_listed_no_rate": (
        "Post with no figure — OPM lists it and prints no rate",
        "The PLUM archive or the current export names the title under this organisation but the "
        "Level/Grade/Pay cell carries a rank or is empty, and no salary table this project has read "
        "prices that pay plan.",
        "A salary table for the pay plan (AD, OT and the others) where OPM publishes one; most of "
        "these plans have none, and the honest state is a listing with no figure.",
    ),
    "post_unreached": (
        "Post with no figure — no document this project has read names the title",
        "Not a coverage gap somebody has not got to: no pay document in the repository names this "
        "title under this organisation, so nothing could have reached it.",
        "The research prompt pack `docs/PAY_SOURCE_RESEARCH_PROMPT_3.md` names every one of these "
        "titles and asks for the DOCUMENT, not the figure. Research batches are run against it, and "
        "what each bought — and what each got wrong — is in `CURATION.md` §19.",
    ),
    "post_not_federally_paid": (
        "Post with no figure — a document places it off every federal pay schedule",
        "An official document committed here establishes that the post's holder is not paid by the "
        "federal government: it sits in a DOE laboratory that DOE states is operated by a contractor. "
        "The node carries `positionEmployer` saying so, in the document's own words and no further.",
        "Nothing to find: no federal pay figure exists for it. The owner's decision of 2026-10-07 "
        "takes these out of the research packs.",
    ),
    "post_beneath_replaced_unit": (
        "Post with no figure — beneath a unit the government has replaced",
        "The post sits under a unit marked `lifecycle: superseded` (the eighteen former VA networks): "
        "the viewer draws it only when a reader asks for replaced units.",
        "Curation first, by the owner's decision of 2026-10-07: research on these is paused until a VA "
        "document maps medical centres to the five current networks and the posts are re-homed. What "
        "pays a medical-centre post does not depend on its network, so the research question survives.",
    ),
    "negative_pool": (
        "No figure — beneath a Treasury pool that nets below zero",
        "The unit above publishes the Treasury's net figure and its measured lines already reach "
        "or exceed it (the Executive Office of the President nets to −$1.24bn), so nothing remains "
        "to apportion. Published `unavailable` rather than a guess.",
        "USAspending File A gross outlays already sit beside the blank for several EOP offices. A "
        "cost would need the Treasury to print a line for the unit, which it does not.",
    ),
    "superseded": (
        "No figure — a unit the government has replaced",
        "Marked `lifecycle: superseded` from an official page's own words. Kept with its sources as "
        "a record of what the government used to be; takes no share and gives none.",
        "Never: a replaced unit has no current cost by construction.",
    ),
    "below_precision": (
        "No figure — the share rounds below one cent",
        "An apportioned share so small it rounds below a cent, published `unavailable` rather than $0.",
        "Moves only when the pool above it is re-divided.",
    ),
    "other": (
        "Unclassified",
        "A node none of the classes above claims. Should be empty; anything here is a defect in this report.",
        "Fix the report.",
    ),
}


def walk(root):
    for node, parent, _ in walk_with_lifecycle(root):
        yield node, parent


def walk_with_lifecycle(root):
    """(node, parent, beneath a replaced unit?) for every node."""
    stack = [(root, None, False)]
    while stack:
        node, parent, replaced = stack.pop()
        replaced = replaced or str(node.get("lifecycle") or "") == "superseded"
        yield node, parent, replaced
        for child in node.get("children") or []:
            stack.append((child, node, replaced))


def is_position(node) -> bool:
    return "position" in str(node.get("type") or "").casefold()


def is_treasury_line(node) -> bool:
    return str(node.get("synthetic") or "") == "treasury_receipts" or "treasury accounting line" in str(
        node.get("type") or ""
    ).casefold()


def has_pay_claim(node) -> bool:
    return any(isinstance(node.get(field), dict) for field in PAY_FIELDS)


def classify(node, replaced: bool = False) -> str:
    """Exactly one class per node, decided in this order."""
    status = str(node.get("cost_status") or "").casefold()
    validation = str(node.get("cost_validation") or "").casefold()
    if status in ("official", "root_total"):
        return "measured_treasury_line" if is_treasury_line(node) else "measured"
    if is_position(node):
        if has_pay_claim(node):
            return "salary"
        return "post_" + classify_unpriced_post(node, replaced)
    if validation == "unit_superseded" or str(node.get("lifecycle") or "") == "superseded":
        return "superseded"
    if validation == "treasury_pool_negative":
        return "negative_pool"
    if validation == "allocation_below_precision":
        return "below_precision"
    if status in ("allocated", "scaled_official"):
        if any(word in str(node.get("type") or "").casefold() for word in COMMITTEE_TYPES):
            return "estimate_committee"
        if any(isinstance(node.get(field), dict) for field in SOURCED_FIGURES_BESIDE):
            return "estimate_beside_sourced_figure"
        return "estimate"
    return "other"


def collect(graph):
    """Class -> rows, every node exactly once."""
    rows: dict[str, list[dict]] = defaultdict(list)
    for node, parent, replaced in walk_with_lifecycle(graph):
        cls = classify(node, replaced)
        rows[cls].append(
            {
                "id": str(node.get("id") or ""),
                "name": str(node.get("name") or ""),
                "type": str(node.get("type") or ""),
                "parent": str((parent or {}).get("name") or ""),
                "beside": [field for field in SOURCED_FIGURES_BESIDE if isinstance(node.get(field), dict)],
            }
        )
    return rows


def render(rows) -> str:
    total = sum(len(v) for v in rows.values())
    out: list[str] = []
    w = out.append
    w("# Cost coverage — every node, by what stands where its cost would be")
    w("")
    w("Generated by `python scripts/report_cost_coverage.py` from `output/graph.json`.")
    w("Do not edit by hand; regenerate it. `tests/test_cost_coverage.py` re-renders it and")
    w("asserts that the classes below partition the graph.")
    w("")
    w("The standing ask is that every node come to carry a figure. This is the inventory")
    w("that ask is measured against: one class per node, what the class means, and the")
    w("document route that would move it — or the plain statement that none can. A figure")
    w("this project publishes is one a committed document states and a matcher re-derives")
    w("on every run; nothing here is a number somebody reports.")
    w("")
    w(f"- nodes in the published graph: **{total:,}**")
    with_figure = sum(len(rows[c]) for c in ("measured", "measured_treasury_line", "salary"))
    estimates = sum(len(rows[c]) for c in ("estimate", "estimate_committee", "estimate_beside_sourced_figure"))
    none_ever = sum(len(rows[c]) for c in ("negative_pool", "superseded", "below_precision"))
    posts_researchable = sum(len(rows[c]) for c in ("post_multiplicity", "post_listed_no_rate", "post_unreached"))
    posts_paused = len(rows.get("post_beneath_replaced_unit", []))
    posts_unpaid = len(rows.get("post_not_federally_paid", []))
    w(f"- showing a figure a document states (measured cost or salary): **{with_figure:,}**")
    w(f"- carrying an apportioned estimate, withheld unless asked for: **{estimates:,}**")
    w(f"- positions no document prices: **{posts_researchable + posts_paused + posts_unpaid:,}** — "
      f"{posts_researchable:,} research work, {posts_paused:,} paused beneath a replaced unit, "
      f"{posts_unpaid:,} a document places off every federal pay schedule")
    w(f"- no figure now and none from any route (negative pool, replaced unit, below a cent): **{none_ever:,}**")
    w("")
    w("| class | nodes | what it means | route |")
    w("|---|---|---|---|")
    for cls, (heading, meaning, route) in CLASSES.items():
        count = len(rows.get(cls, []))
        if cls == "other" and count == 0:
            continue
        w(f"| {heading} | {count:,} | {meaning} | {route} |")
    w("")
    w("## Types inside the estimate classes")
    w("")
    w("Where Table 5 stops is visible in which TYPES carry an estimate and no line:")
    w("")
    w("| type | estimate (no sourced figure) | with a sourced figure beside | committee |")
    w("|---|---|---|---|")
    types = Counter()
    per = {c: Counter(r["type"] for r in rows.get(c, [])) for c in ("estimate", "estimate_beside_sourced_figure", "estimate_committee")}
    for c in per.values():
        types.update(c)
    for type_name, _ in sorted(types.items(), key=lambda kv: (-kv[1], kv[0])):
        w(f"| {type_name} | {per['estimate'][type_name]:,} | {per['estimate_beside_sourced_figure'][type_name]:,} | {per['estimate_committee'][type_name]:,} |")
    w("")
    w("---")
    w("")
    for cls, (heading, meaning, route) in CLASSES.items():
        entries = rows.get(cls, [])
        if cls.startswith("post_") and entries:
            w(f"## {heading} — {len(entries):,}")
            w("")
            w(f"{meaning}")
            w("")
            w(f"**Route.** {route}")
            w("")
            w("Listed one per line, with its reason, in `docs/UNPRICED_POSITIONS.md`; not repeated here.")
            w("")
            continue
        if cls == "salary" and entries:
            w(f"## {heading} — {len(entries):,}")
            w("")
            w(f"{meaning}")
            w("")
            w(f"**Route.** {route}")
            w("")
            w("Listed by source in `docs/EXACT_NODE_COSTS.md`; not repeated here.")
            w("")
            continue
        if not entries and cls == "other":
            continue
        w(f"## {heading} — {len(entries):,}")
        w("")
        w(f"{meaning}")
        w("")
        w(f"**Route.** {route}")
        w("")
        for row in sorted(entries, key=lambda r: (r["parent"], r["name"])):
            beside = f" — beside it: {', '.join(row['beside'])}" if row["beside"] else ""
            w(f"- `{row['id']}` — {row['name']} ({row['type']}; under {row['parent'] or 'the root'}){beside}")
        w("")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true", help="print the counts and write nothing")
    args = parser.parse_args((argv or sys.argv)[1:])
    if not args.graph.exists():
        print(f"refused: {args.graph} does not exist")
        return 1
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    rows = collect(graph)
    total = sum(len(v) for v in rows.values())
    print(f"nodes {total:,}")
    for cls in CLASSES:
        if rows.get(cls):
            print(f"  {len(rows[cls]):6,}  {cls}")
    if rows.get("other"):
        print("refused: a node fell outside every class")
        for row in rows["other"][:20]:
            print("   ", row["id"], row["type"])
        return 1
    if args.dry_run:
        return 0
    args.output.write_text(render(rows), encoding="utf-8")
    print(f"wrote {args.output.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
