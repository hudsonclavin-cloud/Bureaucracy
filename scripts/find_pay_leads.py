#!/usr/bin/env python
"""Find the posts a held pay document prints under another filing, and bring them to the owner.

    python scripts/find_pay_leads.py --dry-run   # print the count and the first leads; writes nothing
    python scripts/find_pay_leads.py             # writes docs/PAY_LEADS.md

No AI and no network. It reads the published graph and the committed current
Plum Book export (digest recomputed, the two name columns and the unique-ID
column never read) and answers one question per unpriced post: does the
export print THIS TITLE under the post's own agency, in an organisation the
reviewed matching rules did not tie to the post?

A lead is a post the rules have NOT tied to a printed row: it carries no listing
of either Plum document, and each organisation it names is either one no node
has been matched to or one that sits in the post's own chain (an organisation
the rules already tied to some OTHER unit is that unit's, not a lead for this
post). Two routes find one: the post's own agency prints the title in such an
organisation, or the agency is one this graph has no node for (the export
files every Defense agency under "OFFICE OF THE SECRETARY OF WAR") and an
organisation named for the post's own parent prints the exact title.

That is a lead and never a claim. The matching rules refuse to guess which of
several organisations' "Chief of Staff" is this one, and they are right to; a
person may know. The output lists, per post, every organisation of its own
agency that prints the title, with the pay plan and level or rate the export
prints for it, so the owner can say "that one" (a reviewed row the pay modules
would then re-check against the document) or "none of them" (a recorded
decision, `data/curation/pay_lead_decisions.json`, which takes the post out of
the open count with the reason beside it).

A title printed only under agencies that are not this post's own is not a
lead: `Chief of Staff` is printed under dozens of agencies, and the stamp
having a row somewhere says nothing about this office. Those posts stay in the
unpriced class and are counted there.

A decision (`data/curation/pay_lead_decisions.json`) closes a lead only while
its row still names the post as it is now called and carries a kind and a
reason. `needs_a_reviewed_row` is the owner saying "yes, that is the post":
it does NOT close the lead, which stays open (marked awaiting a row) until a
reviewed row exists. A malformed decisions file is an error, never an empty
one.
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

from data_pipeline.exporter.build_graph import canonical_name_key, index_tree  # noqa: E402
from data_pipeline.verification.aliases import load_alias_table  # noqa: E402
from data_pipeline.verification.plum_current import (  # noqa: E402
    DEFAULT_EXPORT_CSV,
    Unreadable,
    export_title_keys,
    load_plum_export,
    match_organisations,
    unescape,
)

GRAPH = PROJECT_ROOT / "output" / "graph.json"
DECISIONS = PROJECT_ROOT / "data" / "curation" / "pay_lead_decisions.json"
DOC = PROJECT_ROOT / "docs" / "PAY_LEADS.md"
BLOCK_KIND = "title_printed_in_a_held_pay_document_without_a_row_reaching_this_post"
DECISION_KINDS = ("not_this_post", "stamp_not_a_post_of_this_agency", "needs_a_reviewed_row")


class BadDecisions(ValueError):
    """The decisions file is not readable as the table it is; an unreadable file must never read as 'no decisions'."""


def load_decisions(path: Path = DECISIONS) -> dict[str, dict]:
    path = Path(path)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise BadDecisions(f"{path.name} is unreadable: {error}") from error
    rows = data.get("decisions") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise BadDecisions(f"{path.name} has no 'decisions' list")
    out: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict) or not str(row.get("nodeId") or "").strip():
            raise BadDecisions(f"{path.name} has a row with no nodeId: {row!r}")
        if row.get("kind") not in DECISION_KINDS:
            raise BadDecisions(f"{path.name}: {row.get('nodeId')} has kind {row.get('kind')!r}, not one of {DECISION_KINDS}")
        if not str(row.get("basis") or "").strip() or not str(row.get("name") or "").strip():
            raise BadDecisions(f"{path.name}: {row.get('nodeId')} needs a name (the post as it was called) and a basis")
        if str(row["nodeId"]) in out:
            raise BadDecisions(f"{path.name}: {row['nodeId']} is decided twice")
        out[str(row["nodeId"])] = row
    return out


def find_leads(graph: dict, export: dict, alias_table=None) -> list[dict]:
    """One lead per unpriced post the rules have not tied to a printed row and a title the export prints for it."""
    node_map, parent_map = index_tree(graph)
    root_id = str(graph.get("id") or "")
    groups = export.get("groups") or {}
    agency_nodes, group_nodes, _report = match_organisations(
        groups, node_map, parent_map, root_id=root_id, alias_table=alias_table, alias_hits={},
    )
    groups_by_agency_node: dict[str, list[tuple[str, str]]] = defaultdict(list)
    unmatched_agency_groups: list[tuple[str, str]] = []
    for (agency, organization) in groups:
        node_id = agency_nodes.get(agency)
        if node_id:
            groups_by_agency_node[node_id].append((agency, organization))
        elif group_nodes.get((agency, organization)) is None:
            unmatched_agency_groups.append((agency, organization))

    def ancestors(node_id: str) -> list[str]:
        out, seen = [], set()
        current = parent_map.get(node_id)
        while current and current not in seen:
            seen.add(current)
            out.append(current)
            current = parent_map.get(current)
        return out

    def printed_rows(candidates, key: str, chain: list[str], node_id: str) -> list[dict]:
        printed = []
        for (agency, organization) in sorted(candidates):
            tied_to = group_nodes.get((agency, organization))
            if tied_to is not None and tied_to not in chain and tied_to != node_id:
                continue  # an organisation the rules already tied to some other unit prints that unit's titles
            for row in groups[(agency, organization)]:
                if key in export_title_keys(row["title"], organization):
                    printed.append({
                        "agency": unescape(agency),
                        "organization": unescape(organization),
                        "title": unescape(row["title"]),
                        "payPlan": row.get("payPlan") or "",
                        "level": row.get("level") or "",
                        "rows": int(row.get("rowsListed") or 0),
                    })
        return printed

    leads: list[dict] = []
    for node_id, node in node_map.items():
        block = node.get("payNoDocument")
        if not isinstance(block, dict) or block.get("kind") != BLOCK_KIND:
            continue
        if node.get("positionCurrentListing") or node.get("positionListing"):
            continue  # the rules tied this post to a printed row already; what it prints (or not) is the pay report's
        key = canonical_name_key(node.get("name"))
        if not key:
            continue
        chain = ancestors(node_id)
        # the nearest ancestor an export agency was matched to is the post's own agency
        agency_node = next((a for a in chain if a in groups_by_agency_node), None)
        route = "agency"
        if agency_node is not None:
            printed = printed_rows(groups_by_agency_node[agency_node], key, chain, node_id)
            agency_name = str((node_map.get(agency_node) or {}).get("name") or "")
        else:
            # An agency this graph has no node for: only an organisation named for the post's own parent counts.
            parent_key = canonical_name_key((node_map.get(parent_map.get(node_id)) or {}).get("name"))
            named_for_parent = [g for g in unmatched_agency_groups if canonical_name_key(unescape(g[1])) == parent_key] if parent_key else []
            printed = printed_rows(named_for_parent, key, chain, node_id)
            agency_node = ""
            agency_name = ""
            route = "organisation_named_for_the_posts_parent"
            if printed:
                agency_name = printed[0]["agency"] + " (an export agency this graph has no node for)"
        if not printed:
            continue
        organisations = sorted({p["organization"] for p in printed})
        leads.append({
            "nodeId": node_id,
            "name": str(node.get("name") or ""),
            "parent": str((node_map.get(parent_map.get(node_id)) or {}).get("name") or ""),
            "agencyNode": agency_node,
            "agencyName": agency_name,
            "route": route,
            "organisations": len(organisations),
            "printed": printed,
        })
    leads.sort(key=lambda l: (l["agencyName"], l["name"], l["nodeId"]))
    return leads


def partition(leads: list[dict], decisions: dict[str, dict]) -> tuple[list[dict], list[dict], list[str]]:
    """(open, decided, stale decision ids). A decision closes a lead only if its row names the post as it is now
    called and its kind is not `needs_a_reviewed_row` (the owner's "yes, that is the post", which keeps the lead
    open and marked awaiting a row). A row that names no lead, or names a post by a former name, is stale."""
    open_leads: list[dict] = []
    decided: list[dict] = []
    applies: set[str] = set()
    for lead in leads:
        row = decisions.get(lead["nodeId"])
        if row is None or str(row.get("name") or "") != lead["name"]:
            open_leads.append(lead)
            continue
        applies.add(lead["nodeId"])
        if row.get("kind") == "needs_a_reviewed_row":
            open_leads.append(dict(lead, decision=row, awaiting_row=True))
        else:
            decided.append(dict(lead, decision=row))
    stale = sorted(set(decisions) - applies)
    return open_leads, decided, stale


def render(leads: list[dict], decisions: dict[str, dict], export: dict, unpriced_total: int) -> str:
    open_leads, decided, stale = partition(leads, decisions)
    awaiting = [l for l in open_leads if l.get("awaiting_row")]
    out = [
        "# Pay leads",
        "",
        "Generated by `python scripts/find_pay_leads.py` (no AI, no network) from `output/graph.json` and the committed "
        f"current Plum Book export (`{export.get('file')}`, fetched {str(export.get('fetched_at'))[:10]}, sha256 "
        f"`{str(export.get('sha256'))[:16]}…`, name columns never read). Do not edit by hand.",
        "",
        "A lead is an unpriced post the matching rules have not tied to a printed row (it carries no listing) whose title "
        "the export prints under the post's OWN agency, in an organisation no node has been matched to or one in the "
        "post's own chain; or, where the agency is one this graph has no node for, in an organisation named for the "
        "post's own parent. It is a question for a person, never a claim: the rules refuse to guess which of several "
        "organisations' office this is. Say \"that one\" and a reviewed row follows (the lead stays open, marked "
        "awaiting a row, until it exists); say \"none of them\" and the decision is recorded in "
        "`data/curation/pay_lead_decisions.json` with the reason and closes the lead.",
        "",
        f"**{len(open_leads)} open** ({len(awaiting)} awaiting a reviewed row) · {len(decided)} decided · {len(leads)} "
        f"leads in all · {unpriced_total} unpriced posts (the other {unpriced_total - len(leads)} are already tied to a "
        "printed row, or have no title of theirs printed under their own agency or under an organisation not already "
        "tied to another unit; a stamped title printed under other agencies is not a lead).",
        "",
    ]
    if stale:
        out += [f"Decision rows naming a post that is no longer a lead, or by a former name (stale; the lead stays open): "
                f"{', '.join(stale)}", ""]
    one = [l for l in open_leads if l["organisations"] == 1]
    several = [l for l in open_leads if l["organisations"] != 1]

    def section(title: str, blurb: str, group: list[dict]) -> list[str]:
        lines = [f"## {title} ({len(group)})", "", blurb, ""]
        if not group:
            return lines + ["None.", ""]
        by_agency: dict[str, list[dict]] = defaultdict(list)
        for lead in group:
            by_agency[lead["agencyName"]].append(lead)
        for agency in sorted(by_agency):
            lines += [f"### {agency}", ""]
            for lead in by_agency[agency]:
                note = " — owner said yes: awaiting a reviewed row" if lead.get("awaiting_row") else ""
                lines.append(f"- **{lead['name']}** (`{lead['nodeId']}`), under {lead['parent']}; the export prints it in "
                             f"{lead['organisations']} organisation{'s' if lead['organisations'] != 1 else ''}{note}:")
                for p in lead["printed"]:
                    level = f"{p['payPlan']} {p['level']}".strip() or "no plan or level printed"
                    lines.append(f"  - {p['organization']} — \"{p['title']}\" — {level} — {p['rows']} row{'s' if p['rows'] != 1 else ''}")
            lines.append("")
        return lines

    out += section("Tier 1: one organisation of the agency prints the title",
                   "The question is a yes or no: is the post in this graph that office? Several still need a second look "
                   "(a department's title printed under one bureau may be that bureau's, not the department's).", one)
    out += section("Tier 2: several organisations of the agency print the title",
                   "Nothing here says which one is this post, and the matching rules are right not to guess. A person "
                   "who knows may name the organisation; otherwise the honest answer is \"none of them\".", several)
    if decided:
        out += ["## Decided", ""]
        for lead in sorted(decided, key=lambda l: (l["agencyName"], l["name"], l["nodeId"])):
            d = lead["decision"]
            out.append(f"- **{lead['name']}** (`{lead['nodeId']}`), {lead['agencyName']}: {d.get('kind')} — {d.get('basis')}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def render_issue(leads: list[dict], decisions: dict[str, dict], export: dict, unpriced_total: int, limit: int = 30) -> str:
    """The body of the one GitHub issue the monthly workflow keeps open: counts, the tier-1 leads (capped,
    GitHub bodies are limited) and where the full list lives. No AI wrote it and nothing in it is a claim."""
    open_leads, decided, _stale = partition(leads, decisions)
    awaiting = [l for l in open_leads if l.get("awaiting_row")]
    one = [l for l in open_leads if l["organisations"] == 1]
    out = [
        f"**{len(open_leads)} posts** (of {unpriced_total} unpriced) have a title the current Plum Book export prints under "
        f"their own agency, in an organisation the matching rules did not tie to them; {len(one)} of those name exactly one "
        f"organisation, and {len(awaiting)} await a reviewed row you already said yes to. {len(decided)} are decided. These "
        "are questions for you, not claims: say which post is which office and a reviewed row follows, or say none of them "
        "and the decision is recorded.",
        "",
        "The full list, with every organisation that prints each title, is `docs/PAY_LEADS.md`. First "
        f"{min(limit, len(one))} where one organisation prints the title:",
        "",
    ]
    for lead in one[:limit]:
        p = lead["printed"][0]
        level = f"{p['payPlan']} {p['level']}".strip() or "no plan or level printed"
        out.append(f"- {lead['agencyName']}: **{lead['name']}** (`{lead['nodeId']}`) — export: {p['organization']} — {level}")
    out += ["", f"_Generated by `scripts/find_pay_leads.py` from the committed export fetched {str(export.get('fetched_at'))[:10]}; "
            "no AI, no network._"]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--graph", type=Path, default=GRAPH)
    ap.add_argument("--export", type=Path, default=DEFAULT_EXPORT_CSV)
    ap.add_argument("--decisions", type=Path, default=DECISIONS)
    ap.add_argument("--out", type=Path, default=DOC)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--issue-body", action="store_true", help="print the body of the monthly issue and write nothing")
    args = ap.parse_args(argv)
    try:
        export = load_plum_export(args.export)
    except Unreadable as error:
        print(f"refused: {error}")
        return 1
    try:
        load_decisions(args.decisions)
    except BadDecisions as error:
        print(f"refused: {error}")
        return 1
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    node_map, parent_map = index_tree(graph)
    alias_table = load_alias_table(node_map=node_map, parent_map=parent_map)
    leads = find_leads(graph, export, alias_table)
    unpriced_total = sum(1 for n in node_map.values() if isinstance(n.get("payNoDocument"), dict))
    decisions = load_decisions(args.decisions)
    if args.issue_body:
        print(render_issue(leads, decisions, export, unpriced_total), end="")
        return 0
    text = render(leads, decisions, export, unpriced_total)
    open_leads, decided, _stale = partition(leads, decisions)
    print(f"leads {len(leads)}  open {len(open_leads)}  decided {len(decided)}  unpriced posts with a blank {unpriced_total}")
    if args.dry_run:
        print(text[:3000])
        return 0
    args.out.write_text(text, encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
