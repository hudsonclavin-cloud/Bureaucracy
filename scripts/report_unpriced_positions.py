#!/usr/bin/env python
"""Every position in the published graph that carries no pay claim, and a
research prompt pack that covers all of them.

    python scripts/report_unpriced_positions.py --dry-run   # counts only, writes nothing
    python scripts/report_unpriced_positions.py             # writes both docs

Writes two generated documents and nothing else:

- `docs/UNPRICED_POSITIONS.md` -- the complete inventory, every unpriced
  position by id, name and parent, with the reason nothing reached it. It
  exists so "covers every position" is a checkable claim rather than an
  assertion: the prompt pack below is generated from this same list in the
  same run, and `--dry-run` prints the totals both are built from.
- `docs/PAY_SOURCE_RESEARCH_PROMPT_3.md` -- the prompt pack. One lead prompt
  asking the structural question, then one enumeration prompt per shard, each
  listing the titles it covers by name.

## Why the prompts ask for a DOCUMENT and not only a number

This pipeline cannot publish a figure somebody reports; it publishes a figure
a committed document prints, under a matcher that re-derives it on every run.
A research answer of "the VA Police Chief earns about $110,000" is unusable
here. An answer of "VA Police Chiefs are GS-0083 series, General Schedule,
priced by OPM's Salary Table 2026-GS at <url>, and the schedule states a range
per grade rather than a rate" is directly actionable: it names a document this
repository can fetch, a join key, and what the document does and does not say.

So every prompt asks for four things per title -- the pay system, the
published document, whether that document states a rate or a range, and the
join key -- and asks for the figure itself only where a document prints one.

## Why the shards are enumeration prompts and the lead prompt is not

`recursive-research-elicitation` applies the follow-up-chain directive to
exploratory prompts and exempts verification and enumeration passes, where
expansion buries the per-item verdicts the pass exists to produce. The lead
prompt is exploratory -- it asks which pay systems govern federal positions at
all -- so it carries the directive. The shards ask for one line per title
across hundreds of titles, so they do not; each ends in its own LOAD-BEARING
NUMBERS list instead.

Nothing here fetches, and nothing here writes to the curated file, the
published graph or any evidence file.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_GRAPH = PROJECT_ROOT / "output" / "graph.json"
DEFAULT_INVENTORY = PROJECT_ROOT / "docs" / "UNPRICED_POSITIONS.md"
DEFAULT_PROMPTS = PROJECT_ROOT / "docs" / "PAY_SOURCE_RESEARCH_PROMPT_3.md"

#: Every field that counts as a pay claim. Imported rather than restated so a
#: new pay field cannot make this report silently over-count.
from data_pipeline.verification.pay_documents import PAY_FIELDS  # noqa: E402

#: Titles per shard. Chosen so a shard is answerable in one research pass:
#: past roughly this many the answers get thinner per line, which is the
#: opposite of what this pack is for.
SHARD_TITLES = 110

BRANCH_NAMES = {
    "exec": "Executive Branch",
    "leg": "Legislative Branch",
    "jud": "Judicial Branch",
    "?": "Unplaced",
}

REASONS = {
    "multiplicity": (
        "the node states a multiplicity (×N) and no claim that holds for every holder has reached it",
        "Since 2026-09-23 a claim that holds for each holder by its own terms IS published on such a "
        "node with a `holders` block -- a tier or parity rate paid to every judge of the tier, a band "
        "every holder is within, or a roster listing every holder at one rate -- and 28 such nodes carry "
        "one. What stays refused is an incumbency-shaped claim (one listing's level, one row of the "
        "current export), because that is one appointment's figure and not the group's. For these nodes "
        "no office-rate claim has reached them at all. Knowing "
        "which pay system governs the title is still useful -- it is what would let the graph "
        "carry the schedule rather than a rate -- so these are listed and asked about.",
    ),
    "listed_no_rate": (
        "OPM lists the position and the row prints no rate",
        "The PLUM archive or the current export names the title under this organisation but the "
        "Level/Grade/Pay cell carries a rank or is empty, and no salary table this project has "
        "read prices that pay plan.",
    ),
    "unreached": (
        "no source this project has read names the title at all",
        "Not a coverage gap somebody has not got to: no pay document in the repository names "
        "this title under this organisation, so nothing could have reached it.",
    ),
}


def walk(root):
    stack = [(root, None)]
    while stack:
        node, parent = stack.pop()
        yield node, parent
        for child in node.get("children") or []:
            stack.append((child, node))


def branch_of(node_id: str) -> str:
    prefix = str(node_id or "").split("-", 1)[0]
    return prefix if prefix in BRANCH_NAMES else "?"


def classify(node) -> str:
    if node.get("representsPosts"):
        return "multiplicity"
    if isinstance(node.get("positionListing"), dict) or isinstance(node.get("positionCurrentListing"), dict):
        return "listed_no_rate"
    return "unreached"


def collect(graph):
    """Every position with no pay claim, grouped by its parent organisation."""
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    priced = 0
    positions = 0
    for node, parent in walk(graph):
        if "position" not in str(node.get("type") or "").casefold():
            continue
        positions += 1
        if any(isinstance(node.get(field), dict) for field in PAY_FIELDS):
            priced += 1
            continue
        key = (str((parent or {}).get("id") or "?"), str((parent or {}).get("name") or "?"))
        groups[key].append(
            {
                "id": str(node.get("id") or ""),
                "name": str(node.get("name") or ""),
                "reason": classify(node),
                "branch": branch_of(node.get("id")),
                "listed": bool(
                    isinstance(node.get("positionListing"), dict)
                    or isinstance(node.get("positionCurrentListing"), dict)
                ),
            }
        )
    return groups, positions, priced


def shard(groups, per_shard: int):
    """Whole organisations packed into shards, never split across two.

    An organisation's titles are answered together or not at all: the pay
    system is a fact about the employer, so splitting one agency across two
    prompts asks the same structural question twice and invites two answers.
    """
    ordered = sorted(groups.items(), key=lambda item: (-len(item[1]), item[0][1]))
    shards: list[list] = []
    current: list = []
    size = 0
    for key, rows in ordered:
        if current and size + len(rows) > per_shard:
            shards.append(current)
            current, size = [], 0
        current.append((key, rows))
        size += len(rows)
    if current:
        shards.append(current)
    return shards


DIRECTIVE = """FOLLOW-UP CHAIN DIRECTIVE:
After answering the question above in full, continue as follows:

LEVEL 1 — State the 3 most decision-relevant follow-up questions your answer
raises for this tool, and answer each with sources.

LEVEL 2 — For each Level-1 answer that materially affects a design decision,
pose and answer the single most important follow-up it raises, with sources.

LEVEL 3 — Repeat once more for any Level-2 answer that still carries open
decision weight.

BUDGET: no more than 10 follow-up answers total across all levels. Prune by
decision-relevance, not curiosity — drop branches that only add color.

For EVERY follow-up answer:
(a) open with one line stating why this follow-up matters for the tool,
(b) cite primary sources,
(c) flag each number as official-published vs third-party-estimated.

END with a section titled LOAD-BEARING NUMBERS: a flat list of every number
in this entire response that a design decision might rest on — one line per
number, with its source. This list feeds an independent verification pass."""


SHARD_FORMAT = """For EVERY title listed below, return exactly one line in this pipe-delimited
format and nothing else per title:

    <node id> | <pay system> | <document URL> | <rate|range|none> | <join key> | <figure or —> | <confidence>

- **pay system** — one of: `general_schedule`, `senior_executive_service`,
  `senior_level`, `executive_schedule`, `title_38_va`, `title_5_excepted`,
  `administratively_determined`, `foreign_service`, `military_title_37`,
  `federal_wage_system`, `judicial_statutory`, `legislative_chamber`,
  `board_or_commission_statutory`, `not_federally_paid`, `unknown`.
- **document URL** — the URL of the *published document that states the pay*,
  on the publisher's own site. A `.gov` host wherever one exists. Not a news
  article, not a salary-aggregator site, not Wikipedia, not FederalPay.org or
  GovSalaries — those are third-party republications and this tool cannot cite
  them. If no official document states it, write `—` and say so.
- **rate|range|none** — whether that document prints a single annual rate,
  a minimum-and-maximum band, or no figure at all for this title.
- **join key** — the exact string the document uses for this title, so a
  matcher can find the row: a grade (`GS-15`), a level (`EX-IV`), a printed
  title, a tier name, a statutory citation.
- **figure** — only where the document prints one, as printed. `—` otherwise.
  Never estimate, never average, never interpolate between grades.
- **confidence** — `certain` only if you opened the document and read the row;
  `likely` if the pay system is documented but the specific row is inferred;
  `speculative` otherwise.

Rules that matter more than coverage:
1. **A missing answer is a result.** A line reading
   `<node id> | unknown | — | none | — | — | certain` is a correct answer and
   is more useful than a guess. Do not fill gaps.
2. **Never average or interpolate.** If a title spans GS-13 to GS-15, say
   `range` and give the grade span as the join key — do not produce a midpoint.
3. **Do not read across agencies.** An Inspector General's pay at one agency
   is not evidence about another's; answer per organisation as listed.
4. A title marked `[×N]` stands for several holders in this graph. Give a
   figure only where the document states ONE rate that applies to every
   holder of the title by its own terms (a tier, a statutory rate, a roster
   listing each holder at the same figure); otherwise answer the pay system,
   the document and `range` or `none`. Never one holder's pay for the group.

END with a section titled LOAD-BEARING NUMBERS: every figure you returned
above, one line each, with the document URL it came from and whether it is
official-published or third-party-estimated."""


def render_prompts(shards, totals) -> str:
    positions, priced, unpriced, reason_counts = totals
    out: list[str] = []
    w = out.append
    w("# Pay-source research prompt pack — every unpriced position")
    w("")
    w("Generated by `python scripts/report_unpriced_positions.py` from")
    w("`output/graph.json`. Do not edit by hand; regenerate it.")
    w("")
    w("## What this covers")
    w("")
    w(f"The published graph carries **{positions:,} position nodes**. **{priced:,}** carry a pay claim")
    w(f"an official document supports. **{unpriced:,}** do not, and every one of them is listed")
    w(f"in this pack across **{len(shards)} shards** — the complete inventory, with each")
    w("position's id and the reason nothing reached it, is in `docs/UNPRICED_POSITIONS.md`.")
    w("")
    w("Why each is unpriced today:")
    w("")
    for reason, count in sorted(reason_counts.items(), key=lambda kv: -kv[1]):
        headline, detail = REASONS[reason]
        w(f"- **{count:,}** — {headline}. {detail}")
    w("")
    w("## How to run this pack")
    w("")
    w("Run **Prompt 0** first and read the answer before running any shard: it decides")
    w("which pay systems exist and where each is published, and a shard answer that")
    w("contradicts it is a finding rather than an update. Then run the shards in any")
    w("order; they are independent.")
    w("")
    w("Prompt 0 carries the follow-up-chain directive because it is exploratory. The")
    w("shards do not, deliberately: they ask for one line per title across hundreds of")
    w("titles, and an expansion pass there buries the per-title verdicts the shard")
    w("exists to produce. Each shard ends in its own LOAD-BEARING NUMBERS list.")
    w("")
    w("**Nothing an answer returns is published by this project until a matcher reads")
    w("it out of a committed document.** A research answer names a document to fetch;")
    w("it is never itself the citation.")
    w("")
    w("---")
    w("")
    w("## Prompt 0 — the structural question")
    w("")
    w("```")
    w("I am building a data-backed public graph of the U.S. federal government in which")
    w("every published figure must be traceable to a specific published government")
    w("document that prints it. I need to price federal POSITIONS (job titles), not")
    w("agencies.")
    w("")
    w("Question: what is the complete set of pay systems under which U.S. federal")
    w("civilian and uniformed positions are compensated, and for EACH system:")
    w("")
    w("1. Which statute or authority establishes it?")
    w("2. Which agency publishes the current pay schedule, and at what exact URL?")
    w("3. Does that published schedule state a single annual RATE per position, a")
    w("   RANGE (minimum/maximum or steps), or no figure at all?")
    w("4. What is the join key a matcher would use to find one position's row in it")
    w("   (grade, level, tier, series, statutory citation, printed title)?")
    w("5. Which categories of federal position are NOT covered by any published")
    w("   schedule, so that no official document states what they are paid?")
    w("")
    w("Be exhaustive about (5) in particular. I need to know where the honest answer")
    w("is “no document states this”, because publishing an estimate there would be a")
    w("false claim, and I would rather publish nothing.")
    w("")
    w("Prefer .gov primary sources. Flag every number as official-published vs")
    w("third-party-estimated. Do not cite salary-aggregator sites (FederalPay.org,")
    w("GovSalaries, Glassdoor and similar) as authorities — name them only to say a")
    w("figure is a third-party republication.")
    w("")
    w(DIRECTIVE)
    w("```")
    w("")
    w("---")
    for index, entries in enumerate(shards, start=1):
        titles = sum(len(rows) for rows in (rows for _, rows in entries))
        orgs = len(entries)
        w("")
        w(f"## Prompt {index} — {orgs} organisation(s), {titles} title(s)")
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
            for row in sorted(rows, key=lambda r: r["name"]):
                mark = "  [×N]" if row["reason"] == "multiplicity" else ""
                listed = "  [OPM lists it; the row prints no rate]" if row["reason"] == "listed_no_rate" else ""
                w(f"- {row['id']} | {row['name']}{mark}{listed}")
        w("```")
    w("")
    return "\n".join(out) + "\n"


def render_inventory(groups, totals) -> str:
    positions, priced, unpriced, reason_counts = totals
    out: list[str] = []
    w = out.append
    w("# Positions with no pay claim")
    w("")
    w("Generated by `python scripts/report_unpriced_positions.py` from")
    w("`output/graph.json`. Do not edit by hand; regenerate it.")
    w("")
    w("This file exists so that “the prompt pack covers every unpriced position” is a")
    w("checkable claim. `docs/PAY_SOURCE_RESEARCH_PROMPT_3.md` is generated from this")
    w("same list in the same run.")
    w("")
    w(f"- position nodes in the published graph: **{positions:,}**")
    w(f"- carrying a pay claim an official document supports: **{priced:,}**")
    w(f"- carrying none: **{unpriced:,}**")
    w("")
    w("| reason | count | what it means |")
    w("|---|---|---|")
    for reason, count in sorted(reason_counts.items(), key=lambda kv: -kv[1]):
        headline, detail = REASONS[reason]
        w(f"| `{reason}` | {count:,} | {headline}. {detail} |")
    w("")
    w("---")
    w("")
    for (org_id, org_name), rows in sorted(groups.items(), key=lambda item: (-len(item[1]), item[0][1])):
        w("")
        w(f"## {org_name}  — {len(rows)} unpriced")
        w("")
        w(f"`{org_id}`")
        w("")
        for row in sorted(rows, key=lambda r: r["name"]):
            w(f"- `{row['id']}` — {row['name']} — `{row['reason']}`")
    w("")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--prompts", type=Path, default=DEFAULT_PROMPTS)
    parser.add_argument("--shard-titles", type=int, default=SHARD_TITLES)
    parser.add_argument("--dry-run", action="store_true", help="print the counts and write nothing")
    args = parser.parse_args((argv or sys.argv)[1:])

    if not args.graph.exists():
        print(f"refused: {args.graph} does not exist")
        return 1
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    groups, positions, priced = collect(graph)
    rows = [row for group in groups.values() for row in group]
    reason_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        reason_counts[row["reason"]] += 1
    totals = (positions, priced, len(rows), dict(reason_counts))
    shards = shard(groups, args.shard_titles)

    print(f"positions {positions:,}  priced {priced:,}  unpriced {len(rows):,}")
    for reason, count in sorted(reason_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {count:6,}  {reason}")
    print(f"organisations with an unpriced position: {len(groups):,}")
    print(f"shards at {args.shard_titles} titles each: {len(shards)}")
    covered = sum(len(r) for entries in shards for _, r in entries)
    print(f"titles carried by the pack: {covered:,} (of {len(rows):,})")
    if covered != len(rows):
        print("refused: the pack does not cover every unpriced position")
        return 1

    if args.dry_run:
        return 0
    args.inventory.write_text(render_inventory(groups, totals), encoding="utf-8")
    args.prompts.write_text(render_prompts(shards, totals), encoding="utf-8")
    print(f"wrote {args.inventory.relative_to(PROJECT_ROOT)}")
    print(f"wrote {args.prompts.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
