#!/usr/bin/env python
"""Research prompt pack 4: the hundred title families that hold the most
unpriced posts, in one prompt, and everything else in shards.

    python scripts/report_research_prompts.py --dry-run   # counts only, writes nothing
    python scripts/report_research_prompts.py             # writes both docs

Writes two generated documents and nothing else:

- `docs/RESEARCH_PROMPT_4_TOP100.md` -- one prompt naming the 100 title
  families that hold the most unpriced position nodes, with an appendix
  mapping each family back to its node ids so an answer can be joined to the
  graph.
- `docs/RESEARCH_PROMPT_4_REMAINDER.md` -- every unpriced position outside
  those 100 families, sharded by organisation, and every organisation node
  that publishes an apportioned estimate instead of a measured cost, sharded
  by parent.

## Why families, and what "most problematic" means here

`docs/PAY_SOURCE_RESEARCH_PROMPT_3.md` shards the unpriced posts by the
organisation they sit in, which is right for a title that exists once. It is
wrong for the titles this graph stamps across many organisations: the same
`Chief — Medicine Service` sits under eighteen medical-centre groupings and
`Chief Financial Officer` under sixty organisations, and an organisation shard
asks the same structural question once per copy. A FAMILY is the title with
its multiplicity, its parenthetical and a trailing network or region number
set aside; one answer about what pays a family's posts reaches every node in
it. "Most problematic" is measured, not judged: a family ranks by how many
unpriced nodes it holds, ties broken by how many organisations they sit in.

Nothing a family groups is a claim that its posts are paid alike. The prompt
says so, and asks for one answer line per employer where the pay system
differs between them.

## Why the big prompt carries a bounded follow-up chain and the shards do not

`recursive-research-elicitation` exempts enumeration passes, where expansion
buries the per-item verdicts. The top-100 prompt is mostly that, so its table
comes first and must be complete. It is also the one place a structural
finding changes many families at once -- whether a national laboratory's staff
are federal employees at all, whether a Smithsonian museum's are -- so after
the table it carries the follow-up directive, scoped to findings that cover
more than one family. The remainder shards are pure enumeration and carry none.

Nothing here fetches, and nothing here writes to the curated file, the
published graph or any evidence file.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.verification.pay_documents import PAY_FIELDS  # noqa: E402
from scripts.report_cost_coverage import classify as coverage_class  # noqa: E402
from scripts.report_unpriced_positions import (  # noqa: E402
    DIRECTIVE,
    NOT_RESEARCHED,
    REASONS,
    SHARD_FORMAT,
    SHARD_TITLES,
    classify as unpriced_reason,
    shard,
)

DEFAULT_GRAPH = PROJECT_ROOT / "output" / "graph.json"
DEFAULT_TOP = PROJECT_ROOT / "docs" / "RESEARCH_PROMPT_4_TOP100.md"
DEFAULT_REMAINDER = PROJECT_ROOT / "docs" / "RESEARCH_PROMPT_4_REMAINDER.md"

TOP_FAMILIES = 100

#: Organisation classes from `report_cost_coverage.py` whose nodes publish an
#: apportioned estimate and could be moved by a document. Measured, salary,
#: negative-pool, superseded and below-precision nodes are not asked about:
#: the first two are done and the rest have no route by construction.
ORG_CLASSES = {
    "estimate_committee": "a committee or subcommittee (no Table 5 line can ever name one)",
    "estimate_beside_sourced_figure": "an estimate with a sourced non-cost figure already beside it",
    "estimate": "an estimate with no sourced figure of any kind",
}

_PAREN = re.compile(r"\s*\([^()]*\)")
_NETWORK_SUFFIX = re.compile(r",\s*VISN\s*\d+\b.*$")
_REGION_SUFFIX = re.compile(r",\s*Region\s+[IVXLC\d]+\b.*$")
_ACRONYM = re.compile(r"\(([A-Z][A-Za-z&/.\-]{1,11})\)\s*$")


def family_name(name: str) -> str:
    """The title with what distinguishes one copy from another set aside."""
    text = str(name or "")
    while True:
        stripped = _PAREN.sub("", text)
        if stripped == text:
            break
        text = stripped
    text = _NETWORK_SUFFIX.sub("", text)
    text = _REGION_SUFFIX.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def short_org(name: str) -> str:
    match = _ACRONYM.search(str(name or ""))
    return match.group(1) if match else str(name or "?")


def walk(root):
    stack = [(root, None, None, False)]
    while stack:
        node, parent, grand, replaced = stack.pop()
        replaced = replaced or str(node.get("lifecycle") or "") == "superseded"
        yield node, parent, grand, replaced
        for child in reversed(node.get("children") or []):
            stack.append((child, node, parent, replaced))


def is_position(node) -> bool:
    return "position" in str(node.get("type") or "").casefold()


def collect(graph):
    """Unpriced posts that are research work, with their family; the unpriced
    posts that are not (paused or placed off federal pay), by reason; and the
    unmeasured organisations."""
    posts: list[dict] = []
    orgs: list[dict] = []
    skipped: Counter = Counter()
    for node, parent, grand, replaced in walk(graph):
        parent = parent or {}
        grand = grand or {}
        if is_position(node):
            if any(isinstance(node.get(field), dict) for field in PAY_FIELDS):
                continue
            reason = unpriced_reason(node, replaced)
            if reason in NOT_RESEARCHED:
                skipped[reason] += 1
                continue
            posts.append(
                {
                    "id": str(node.get("id") or ""),
                    "name": str(node.get("name") or ""),
                    "family": family_name(node.get("name")),
                    "reason": reason,
                    "parentId": str(parent.get("id") or "?"),
                    "parentName": str(parent.get("name") or "?"),
                    "grandName": str(grand.get("name") or "?"),
                    "replaced": replaced,
                }
            )
            continue
        cls = coverage_class(node)
        if cls in ORG_CLASSES:
            orgs.append(
                {
                    "id": str(node.get("id") or ""),
                    "name": str(node.get("name") or ""),
                    "type": str(node.get("type") or ""),
                    "class": cls,
                    "parentId": str(parent.get("id") or "?"),
                    "parentName": str(parent.get("name") or "?"),
                    "beside": sorted(
                        field
                        for field in ("usaspendingOutlays", "ombBudget", "auditedNetCost")
                        if isinstance(node.get(field), dict)
                    ),
                }
            )
    return posts, orgs, skipped


def rank_families(posts):
    """Families ordered by unpriced nodes held, then organisations, then name."""
    members: dict[str, list[dict]] = defaultdict(list)
    for post in posts:
        members[post["family"].casefold()].append(post)
    families = []
    for key, rows in members.items():
        display = Counter(row["family"] for row in rows).most_common(1)[0][0]
        families.append(
            {
                "key": key,
                "name": display,
                "rows": sorted(rows, key=lambda r: r["id"]),
                "orgs": sorted(
                    {(r["parentId"], r["parentName"], r["grandName"]) for r in rows}, key=lambda o: (o[1], o[0])
                ),
            }
        )
    families.sort(key=lambda f: (-len(f["rows"]), -len(f["orgs"]), f["name"].casefold(), f["key"]))
    for index, family in enumerate(families, start=1):
        family["code"] = f"F{index:03d}"
    return families


def biggest_clusters(posts, families):
    by_parent_name = Counter(post["parentName"] for post in posts)
    replaced = sum(1 for post in posts if post["replaced"])
    return {
        "family": families[0] if families else None,
        "parentName": by_parent_name.most_common(1)[0] if by_parent_name else ("?", 0),
        "replaced": replaced,
    }


def _family_line(family) -> str:
    rows = family["rows"]
    multi = sum(1 for r in rows if r["reason"] == "multiplicity")
    listed = sum(1 for r in rows if r["reason"] == "listed_no_rate")
    replaced = sum(1 for r in rows if r["replaced"])
    flags = []
    if multi:
        flags.append(f"{multi} ×N")
    if listed:
        flags.append(f"{listed} OPM-listed, no rate printed")
    if replaced:
        flags.append(f"{replaced} beneath a replaced unit")
    # Organisations sharing the unit above them are one group: fourteen
    # presidential libraries are "14 beneath Presidential Libraries", not
    # fourteen names. Every node is in the appendix.
    by_grand: dict[str, list[str]] = defaultdict(list)
    for _, name, grand in family["orgs"]:
        by_grand[grand].append(name)
    parts = []
    loose: Counter = Counter()
    for grand, names in sorted(by_grand.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if len(names) > 3:
            parts.append(f"{len(names)} beneath {short_org(grand)}")
        else:
            loose.update(names)
    parts.extend(short_org(name) + (f" ×{count}" if count > 1 else "") for name, count in sorted(loose.items()))
    org_text = "; ".join(parts)
    head = f"{family['code']} | {family['name']} | {len(rows)} posts in {len(family['orgs'])} organisation(s)"
    if flags:
        head += " [" + ", ".join(flags) + "]"
    return f"{head} | {org_text}"


TOP_FORMAT = """For EVERY family code below, return one or more lines in this pipe-delimited
format and nothing else per line:

    <family code> | <applies to> | <pay system> | <document URL> | <rate|range|none> | <join key> | <figure or —> | <confidence>

- **applies to** — `all` when one answer holds for every organisation the
  family lists; otherwise the organisations (as named in the list) this line
  covers, and a further line for each other group. A family is a TITLE this
  graph uses in several places, not a claim that the posts are paid alike:
  a Chief Financial Officer at a cabinet department, at a legislative-branch
  agency and at an intelligence agency are three answers, not one.
- **pay system** — one of: `general_schedule`, `senior_executive_service`,
  `senior_level`, `executive_schedule`, `title_38_va`, `title_5_excepted`,
  `administratively_determined`, `foreign_service`, `military_title_37`,
  `federal_wage_system`, `judicial_statutory`, `judiciary_salary_plan`,
  `legislative_chamber`, `board_or_commission_statutory`, `postal_bargaining`,
  `smithsonian_trust`, `contractor_not_federal`, `not_federally_paid`,
  `unknown`.
- **document URL** — the published document that states the pay, on the
  publisher's own site (a `.gov` host wherever one exists). Not a news
  article, Wikipedia, FederalPay.org, GovSalaries, Glassdoor, OpenPayrolls or
  any other republication. If no official document states it, write `—`.
- **rate|range|none** — whether that document prints one annual rate, a
  minimum-and-maximum band, or no figure for this title.
- **join key** — the exact string the document uses for this title or its
  grade, so a matcher can find the row (`GS-15`, `EX-IV`, `ES`, a tier name,
  a printed title, a statutory citation).
- **figure** — only where the document prints one, exactly as printed.
  Never estimate, average or interpolate.
- **confidence** — `certain` only if you read the row in the document;
  `likely` if the pay system is documented and the row inferred;
  `speculative` otherwise.

Rules that matter more than coverage:
1. **A missing answer is a result.** `F017 | all | unknown | — | none | — | — | certain`
   is a correct line and more useful than a guess.
2. **Say when the people are not federal employees.** National laboratory
   staff are employed by the laboratory's management-and-operating
   contractor; some Smithsonian staff are paid from trust funds; postal pay
   is set by collective-bargaining agreements. Where that is the answer, say
   it (`contractor_not_federal`, `smithsonian_trust`, `postal_bargaining`),
   name the document that establishes it, and give no figure unless an
   official document prints one.
3. **A posting is one vacancy, not the post.** A USAJOBS announcement states
   one vacancy's grade at one location; cite it only for the grade, and say
   how many announcements agree.
4. **Never one holder's pay for a group.** Where the family is marked ×N,
   give a figure only where the document states one rate every holder is paid
   by its own terms (a tier, a statutory rate); otherwise the system, the
   document and `range` or `none`."""


def render_top(families, posts, orgs, top_n, skipped=None) -> str:
    skipped = skipped or {}
    top = families[:top_n]
    covered = sum(len(f["rows"]) for f in top)
    clusters = biggest_clusters(posts, families)
    first = clusters["family"]
    parent_name, parent_count = clusters["parentName"]
    out: list[str] = []
    w = out.append
    w("# Research prompt 4 — the 100 title families that hold the most unpriced posts")
    w("")
    w("Generated by `python scripts/report_research_prompts.py` from `output/graph.json`.")
    w("Do not edit by hand; regenerate it. The rest of the unpriced posts and every")
    w("organisation that publishes an estimate are in `docs/RESEARCH_PROMPT_4_REMAINDER.md`.")
    w("")
    w("## The biggest clusters")
    w("")
    w(f"- **{len(posts):,}** positions carry no pay claim and are research work, in **{len(families):,}** title families.")
    for reason, count in sorted(skipped.items()):
        w(f"- **{count:,}** more carry none and are not asked about here: {REASONS[reason][0]}.")
    if first is not None:
        w(
            f"- The largest family is **{first['name']}**: {len(first['rows'])} unpriced posts in "
            f"{len(first['orgs'])} organisation(s)."
        )
    w(
        f"- The largest single grouping by name is **{parent_name}**: {parent_count} unpriced posts "
        "sit directly beneath groupings of that name."
    )
    w(
        "- The first run of this prompt, answered on 2026-10-07 against the ranking of that morning, "
        "is ledgered family by family in `CURATION.md` §19.22, with what it settled and what it left "
        "unknown. Codes are renumbered on every render; the ledger names families, not codes."
    )
    w(
        f"- The {min(top_n, len(families))} families below hold **{covered:,}** of the {len(posts):,} "
        f"({covered / max(len(posts), 1):.0%}). The other {len(families) - len(top):,} families hold "
        f"{len(posts) - covered:,}, most of them a title that exists once."
    )
    w("")
    w("## How the families were formed and ranked")
    w("")
    w("A family is a post's title with its multiplicity and any parenthetical removed, and a")
    w("trailing `, VISN N …` or `, Region N …` removed. A family ranks by the number of unpriced")
    w("nodes it holds, ties broken by the number of organisations they sit in. Grouping posts by")
    w("title is not a claim that they are paid alike; the prompt asks for one line per employer")
    w("group wherever the pay system differs.")
    w("")
    w("**Nothing an answer returns is published until a matcher reads it out of a committed")
    w("document.** An answer names a document to fetch; it is never itself the citation.")
    w("")
    w("---")
    w("")
    w("## The prompt")
    w("")
    w("```")
    w("I am building a data-backed public graph of the U.S. federal government. Every")
    w("published figure must be traceable to a specific published government document")
    w("that prints it; I cannot publish a reported or estimated salary. Below are the")
    w(f"{len(top)} job-title families that hold the most positions in the graph with no")
    w("pay figure. For each I need to know what the posts are paid and, more")
    w("importantly, WHICH PUBLISHED DOCUMENT states that.")
    w("")
    w(TOP_FORMAT)
    w("")
    w("THE FAMILIES (code | title | how many posts and where | organisations):")
    w("")
    for family in top:
        w(_family_line(family))
    w("")
    w("After the table is complete for every family code, and only then:")
    w("")
    w(DIRECTIVE.replace(
        "raises for this tool, and answer each with sources.",
        "raises for this tool, choosing only questions whose answer would change the\n"
        "lines for MORE THAN ONE family, and answer each with sources.",
        1,
    ))
    w("```")
    w("")
    w("---")
    w("")
    w("## Appendix — every node each family holds")
    w("")
    w("For joining an answer back to the graph. A family's line in the prompt names the")
    w("organisations; this lists the node ids.")
    for family in top:
        w("")
        w(f"### {family['code']} — {family['name']} ({len(family['rows'])})")
        w("")
        for row in family["rows"]:
            marks = []
            if row["reason"] == "multiplicity":
                marks.append("×N")
            if row["reason"] == "listed_no_rate":
                marks.append("OPM-listed")
            if row["replaced"]:
                marks.append("beneath a replaced unit")
            suffix = f" — {', '.join(marks)}" if marks else ""
            w(f"- `{row['id']}` — {row['name']} — under {row['parentName']}{suffix}")
    w("")
    return "\n".join(out) + "\n"


ORG_FORMAT = """For EVERY unit listed below, return exactly one line in this pipe-delimited
format and nothing else per unit:

    <node id> | <basis> | <document URL> | <period> | <figure or —> | <join key> | <confidence>

- **basis** — what the figure measures, one of: `net_outlays`, `gross_outlays`,
  `obligations`, `budget_authority`, `appropriations`, `budget_request`,
  `audited_net_cost`, `payroll`, `disbursements`, `full_time_equivalents`,
  `none`. These are different quantities and must never be mixed: an
  appropriation is not spending, a request is not an appropriation, and a
  committee's disbursements are not outlays.
- **document URL** — the published document that prints the figure for THIS
  unit by name, on the publisher's own site (a `.gov` host wherever one exists:
  the Monthly Treasury Statement, OMB's Public Budget Database, USAspending
  File A/B by Treasury Account Symbol, the agency's own Agency Financial Report
  or Congressional Budget Justification, the House Statement of Disbursements,
  the Report of the Secretary of the Senate). Not a news article, Wikipedia or
  any republication.
- **period** — the fiscal year or reporting period the figure covers, as the
  document states it. A budget-year or out-year figure is a projection, not a
  figure for a year that has happened; say so.
- **figure** — only where the document prints one for this unit, as printed,
  with its stated unit (dollars, thousands, millions). Never apportion a parent's
  figure, never sum rows yourself unless the document prints the total.
- **join key** — the string, account symbol or code the document uses for this
  unit (a Treasury Account Symbol, an OMB bureau code, a committee name as the
  disbursement report prints it).
- **confidence** — `certain` only if you read the row; `likely` if the document
  is right and the row inferred; `speculative` otherwise.

Rules that matter more than coverage:
1. **A missing answer is a result.** `<id> | none | — | — | — | — | certain` is
   correct where no document prints a figure for the unit, and is more useful
   than a guess. Many divisions, regional offices and laboratories are funded
   from a parent's accounts and no document prints their spending alone.
2. **A parent's figure is not the unit's.** If a document prints only the
   bureau or department total, say `none` for the unit and name the document
   in the join key column as `parent only: <name>`.
3. **Contractor-operated is not federal spending by the unit.** A national
   laboratory's budget is the sponsoring department's obligations to its
   operating contractor; say so and give the department's own document.

END with a section titled LOAD-BEARING NUMBERS: every figure you returned
above, one line each, with the document URL it came from and whether it is
official-published or third-party-estimated."""


def render_remainder(families, posts, orgs, top_n, per_shard) -> str:
    rest = [row for family in families[top_n:] for row in family["rows"]]
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rest:
        groups[(row["parentId"], row["parentName"])].append(row)
    post_shards = shard(groups, per_shard)

    org_groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for org in orgs:
        org_groups[(org["parentId"], org["parentName"])].append(org)
    org_shards = shard(org_groups, per_shard)
    org_counts = Counter(org["class"] for org in orgs)

    out: list[str] = []
    w = out.append
    w("# Research prompt 4 — everything outside the top 100")
    w("")
    w("Generated by `python scripts/report_research_prompts.py` from `output/graph.json`.")
    w("Do not edit by hand; regenerate it. The 100 largest title families are in")
    w("`docs/RESEARCH_PROMPT_4_TOP100.md`.")
    w("")
    w("## What this covers")
    w("")
    w(f"- **Part A — {len(rest):,} unpriced positions** in the {len(families) - top_n if len(families) > top_n else 0:,} "
      f"title families outside the top {top_n}, across **{len(post_shards)} shards**, whole organisations per shard.")
    w(f"- **Part B — {len(orgs):,} organisation nodes** that publish an apportioned estimate rather than a measured")
    w(f"  cost, across **{len(org_shards)} shards**, whole parents per shard:")
    for cls, label in ORG_CLASSES.items():
        w(f"  - {org_counts.get(cls, 0):,} — {label}")
    w("")
    w("Not asked about, by construction: measured nodes and priced posts (done), and the units")
    w("beneath a Treasury pool that nets below zero or replaced by the government (no route")
    w("can give them a current figure). `docs/COST_COVERAGE.md` lists every class.")
    w("")
    w("The shards are enumeration prompts and carry no follow-up directive: an expansion pass")
    w("buries the per-line verdicts a shard exists to produce. Each ends in its own")
    w("LOAD-BEARING NUMBERS list. **Nothing an answer returns is published until a matcher")
    w("reads it out of a committed document.**")
    w("")
    w("---")
    w("")
    w("# Part A — positions")
    for index, entries in enumerate(post_shards, start=1):
        titles = sum(len(rows) for _, rows in entries)
        w("")
        w(f"## Prompt A{index} — {len(entries)} organisation(s), {titles} title(s)")
        w("")
        w("```")
        w("I am building a data-backed public graph of the U.S. federal government. Every")
        w("published figure must be traceable to a specific published government document")
        w("that prints it; I cannot publish a reported or estimated salary.")
        w("")
        w("Below are federal POSITIONS, grouped by the organisation they sit in. For each")
        w("one I need to know what it is paid and, more importantly, WHICH PUBLISHED")
        w("DOCUMENT states that.")
        w("")
        w(SHARD_FORMAT)
        w("")
        w("THE TITLES:")
        for (org_id, org_name), rows in entries:
            w("")
            w(f"### {org_name}  [{org_id}]")
            for row in sorted(rows, key=lambda r: (r["name"], r["id"])):
                mark = "  [×N]" if row["reason"] == "multiplicity" else ""
                listed = "  [OPM lists it; the row prints no rate]" if row["reason"] == "listed_no_rate" else ""
                w(f"- {row['id']} | {row['name']}{mark}{listed}")
        w("```")
    w("")
    w("---")
    w("")
    w("# Part B — organisations that publish an estimate")
    for index, entries in enumerate(org_shards, start=1):
        units = sum(len(rows) for _, rows in entries)
        w("")
        w(f"## Prompt B{index} — {len(entries)} parent(s), {units} unit(s)")
        w("")
        w("```")
        w("I am building a data-backed public graph of the U.S. federal government. Every")
        w("published figure must be traceable to a specific published government document")
        w("that prints it for that unit by name. Below are federal UNITS (bureaus, divisions,")
        w("offices, regional offices, laboratories, committees), grouped by the unit above")
        w("them, for which I currently publish only a share apportioned from a parent's total.")
        w("For each I need the published document that prints the unit's OWN spending, if one")
        w("exists, and what kind of figure it prints.")
        w("")
        w(ORG_FORMAT)
        w("")
        w("THE UNITS:")
        for (parent_id, parent_name), rows in entries:
            w("")
            w(f"### beneath {parent_name}  [{parent_id}]")
            for row in sorted(rows, key=lambda r: (r["name"], r["id"])):
                beside = f"  [already carries: {', '.join(row['beside'])}]" if row["beside"] else ""
                w(f"- {row['id']} | {row['name']} | {row['type']}{beside}")
        w("```")
    w("")
    return "\n".join(out) + "\n"


def build(graph, top_n=TOP_FAMILIES, per_shard=SHARD_TITLES):
    posts, orgs, skipped = collect(graph)
    families = rank_families(posts)
    return (
        posts,
        orgs,
        families,
        render_top(families, posts, orgs, top_n, skipped),
        render_remainder(families, posts, orgs, top_n, per_shard),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--top", type=Path, default=DEFAULT_TOP)
    parser.add_argument("--remainder", type=Path, default=DEFAULT_REMAINDER)
    parser.add_argument("--dry-run", action="store_true", help="print the counts and write nothing")
    args = parser.parse_args((argv or sys.argv)[1:])

    if not args.graph.exists():
        print(f"refused: {args.graph} does not exist")
        return 1
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    posts, orgs, families, top_text, remainder_text = build(graph)
    top = families[:TOP_FAMILIES]
    covered = sum(len(f["rows"]) for f in top)
    print(f"unpriced positions that are research work {len(posts):,} in {len(families):,} families")
    print(f"top {len(top)} families hold {covered:,}; the remainder holds {len(posts) - covered:,}")
    print(f"beneath a replaced unit: {sum(1 for p in posts if p['replaced']):,}")
    for cls in ORG_CLASSES:
        print(f"  {sum(1 for o in orgs if o['class'] == cls):6,}  {cls}")
    prompt = top_text.split("```", 2)[1]
    print(f"top-100 prompt length: {len(prompt):,} characters")

    if args.dry_run:
        return 0
    args.top.write_text(top_text, encoding="utf-8")
    args.remainder.write_text(remainder_text, encoding="utf-8")
    print(f"wrote {args.top.relative_to(PROJECT_ROOT)}")
    print(f"wrote {args.remainder.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
