#!/usr/bin/env python
"""Every current organisation in the published graph, by what stands where its
existence evidence would be, and the route that would move each class.

    python scripts/report_evidence_coverage.py --dry-run   # counts only, writes nothing
    python scripts/report_evidence_coverage.py             # writes docs/EVIDENCE_COVERAGE.md

`docs/DEFINITION_OF_DONE.md` criterion 3 is done when every current
organisation carries a `verificationMethod`, or a recorded reason no official
document can be read for it. This report is the number that criterion is
measured by: it puts every current organisation -- not a post, not a Treasury
accounting or receipts line, not a unit the government has replaced -- into
exactly one class, says what the class means, and names the route that would
move it or says plainly that none can. The gap is printed as one number and
never folded into "unread" or "not yet looked at". It is the evidence analogue
of `report_cost_coverage.py` and is generated for the same reason: a test
re-renders it from `output/graph.json` and compares byte for byte, and asserts
that the classes partition the population.

Nothing here fetches, and nothing here writes to the curated file, the
published graph or any evidence file.
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

from data_pipeline.verification.no_document import (  # noqa: E402
    FIELD as NO_DOCUMENT_FIELD,
    KINDS as NO_DOCUMENT_KINDS,
    is_current_organisation,
)

DEFAULT_GRAPH = PROJECT_ROOT / "output" / "graph.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "EVIDENCE_COVERAGE.md"
ROOT_ID = "the-constitution-of-the-united-states"

#: Class id -> (heading, what it means, the route). Order is the order of the
#: report. Every current organisation lands in exactly one. The first two meet
#: the criterion by a method; the `unread` and `no_document_*` classes meet it
#: by a recorded reason; the last two are the gap.
CLASSES = {
    "method_page": (
        "Sourced — an official page labels it",
        "`verificationMethod` is one of the page methods: the unit's own page, its parent's page or "
        "(for a post) its organisation's page names it as a heading, link or list item of its own. "
        "The strongest claim this project makes about a unit's existence.",
        "Nothing to do; the page is re-fetched and the label re-tested by `scripts/verify_base_graph.py`.",
    ),
    "method_list": (
        "Sourced — an official list or document names it",
        "`verificationMethod` is one of the document methods: the Federal Register's agency directory, "
        "the Senate's or the House Clerk's committee list, the Government Manual's entry, OPM's PLUM "
        "archive or current export, or a Federal Register signature. A different document from a "
        "page, and the panel says which.",
        "Nothing to do; each list is committed verbatim and re-matched on every build.",
    ),
    "unread": (
        "Recorded reason — a page queued for it could not be read",
        "`verificationUnread`: a candidate page WAS queued and the verifier could not read it — the "
        "host refuses the crawler (401/403 to robots.txt or the page), robots.txt is unreachable, the "
        "page answered 404, served under 400 readable characters, or the site was failing. A dated "
        "fact about the host or the page, never about the unit.",
        "For `page_not_found` and the readable floor, nominate a better page (phase 1b). For a host "
        "that refuses the crawler, nothing on that host can ever be read under the robots policy "
        "(`docs/NETWORK_ACCESS.md` §11: 67 of 68 such hosts refuse the page too); the route is a "
        "different document — the Manual, a directory, a committee list.",
    ),
    "no_document_curated_count_label": (
        "Recorded reason — the name is this graph's own count label",
        "`verificationNoDocument.kind: curated_count_label`: the name counts things (\"Mission Teams "
        "(15)\", \"All 94 District Courts — Standard Structure\"), so no official page can carry it as "
        "a label and none was fetched. Recomputed from the name on every build by the verifier's own "
        "floor.",
        "None by evidence: the name is the graph's annotation. Renaming the grouping to a unit's real "
        "name would make it checkable, where one exists.",
    ),
    "no_document_name_too_generic": (
        "Recorded reason — the name is one common word",
        "`verificationNoDocument.kind: name_too_generic`: a one-token name a page may use without "
        "naming the unit (\"Defense\", \"Districts (multiple)\"), refused by the verifier's floor before "
        "any fetch.",
        "A rename to the wording the parent's page carries, where the page carries a fuller one.",
    ),
    "no_document_editorial_grouping": (
        "Recorded reason — the graph's own grouping",
        "`verificationNoDocument.kind: editorial_grouping`: the phase 1b nomination ledger's latest "
        "record for the node declines a page because the node is this graph's organising header "
        "(\"Joint Congressional Bodies\", \"Judicial Support Organizations\"), which no official page "
        "names. The ledger's note is quoted on the panel.",
        "None by evidence: a grouping is curation. Dissolving or renaming it is a curation decision.",
    ),
    "no_document_covered_by_parent": (
        "Recorded reason — no page of its own; the parent's is the check",
        "`verificationNoDocument.kind: covered_by_parent`: the ledger's latest record says the unit has "
        "no page of its own and its parent's page is the right place to look — and that page does not "
        "label it.",
        "A rename to what the parent's page calls it, or a page of its own if one appears.",
    ),
    "no_document_no_public_page_known": (
        "Recorded reason — no official page could be named",
        "`verificationNoDocument.kind: no_public_page_known`: a real unit for which the nomination "
        "pass, with network, could name no official page at all (the Office of the Attending "
        "Physician; the NSC's directorates).",
        "A document that names it: the Government Manual, a directory, a statute committed as a "
        "fixture. The page route is exhausted for these.",
    ),
    "no_document_not_on_a_gov_host": (
        "Recorded reason — its site is not on a .gov or .mil host",
        "`verificationNoDocument.kind: not_on_a_gov_host`: the unit's site exists and is on a host this "
        "verifier does not read (si.edu for the Smithsonian's museums, usps.com for the Postal "
        "Service's areas, cpb.org). A fact about the policy, recorded so it does not read as "
        "\"nobody looked\".",
        "An owner's decision to admit a named non-.gov host for a named unit, as "
        "`politeness.STANDARD_4XX_HOSTS` admits two hosts to a different rule; or a .gov document "
        "that names the unit (the Smithsonian's museums appear in no committed list).",
    ),
    "no_document_host_refuses_crawler": (
        "Recorded reason — the host that would carry it refuses this crawler",
        "`verificationNoDocument.kind: host_refuses_crawler`: no page was queued for the node itself, "
        "and the ledger's probe found the only host that would carry it answering 401/403 "
        "(gao.gov for GAO's mission teams, state.gov for State's bureaus, the .mil hosts for the "
        "combatant commands). The probe's URL and verdict ride on the record.",
        "The same as `unread/host_refuses_crawler`: a different document, never that host.",
    ),
    "no_document_page_read_does_not_name_it": (
        "Recorded reason — the page was read and does not carry the graph's name",
        "`verificationNoDocument.kind: page_read_does_not_name_it`: the ledger's probe read the page "
        "that would name it and the graph's wording is not a label on it (NSF's divisions, whose pages "
        "label \"Mathematical Sciences\" where the graph says \"Division of Mathematical Sciences\"; the "
        "Department of Education's regions). A question about the NAME, not about whether the unit "
        "exists.",
        "A reviewed row in `data/curation/unit_renames.json` where the page's wording names the same "
        "unit (`CURATION.md` §9), re-tested against the live page on every run; or a recorded refusal "
        "to rename, where the page's label is a breadcrumb rather than the unit's name.",
    ),
    "negative_read": (
        "Gap — checked and not found",
        "`verificationFailure`: the unit's own page or a complete official list was read and does "
        "not carry the name. A real negative about the graph's wording, not a reason no document can "
        "be read — a document was read — so it counts against criterion 3 until the name is fixed, "
        "the unit superseded, or the name kept with its reason in CURATION.md. Where the nomination "
        "ledger also declines a page for the node, the panel prints the negative, which a reader can "
        "audit against its URL.",
        "A rename to the document's wording (`unit_renames.json`), a supersession, or a recorded "
        "decision to keep the name.",
    ),
    "unrecorded": (
        "Gap — no method, no unread page and no recorded reason",
        "Nothing is published about this unit's existence and the nomination ledger's latest record "
        "for it NOMINATES a page (so no reason applies) or is missing. The page is queued or queueable "
        "and has not confirmed the unit.",
        "Run the verifier on the queued page; where the page labels a different wording, a reviewed "
        "rename (`CURATION.md` §9).",
    ),
    "other": (
        "Unclassified",
        "A node none of the classes above claims. Should be empty; anything here is a defect in this report.",
        "Fix the report.",
    ),
}

GAP_CLASSES = ("negative_read", "unrecorded")
PAGE_METHOD_PREFIX = "name_labelled_on_"


def walk(root):
    stack = [(root, None)]
    while stack:
        node, parent = stack.pop()
        yield node, parent
        for child in node.get("children") or []:
            stack.append((child, node))


def in_population(node) -> bool:
    return str(node.get("id") or "") != ROOT_ID and is_current_organisation(node)


def classify(node) -> str:
    """Exactly one class per current organisation, decided in this order."""
    method = str(node.get("verificationMethod") or "")
    if method:
        return "method_page" if method.startswith(PAGE_METHOD_PREFIX) else "method_list"
    if isinstance(node.get("verificationUnread"), dict):
        return "unread"
    # A document that WAS read and does not carry the name outranks a reason
    # no document can be read: the two can sit on one node (the ledger's
    # decline beside the page's own negative), and the negative is the one a
    # reader can audit against a URL, so it is the one that counts here.
    if node.get("verificationFailure"):
        return "negative_read"
    block = node.get(NO_DOCUMENT_FIELD)
    if isinstance(block, dict) and str(block.get("kind") or "") in NO_DOCUMENT_KINDS:
        return "no_document_" + str(block.get("kind"))
    if not node.get("sourceUrls"):
        return "unrecorded"
    return "other"


def collect(graph):
    """Class -> rows, every current organisation exactly once."""
    rows: dict[str, list[dict]] = defaultdict(list)
    for node, parent in walk(graph):
        if not in_population(node):
            continue
        block = node.get(NO_DOCUMENT_FIELD) if isinstance(node.get(NO_DOCUMENT_FIELD), dict) else {}
        unread = node.get("verificationUnread") if isinstance(node.get("verificationUnread"), dict) else {}
        rows[classify(node)].append(
            {
                "id": str(node.get("id") or ""),
                "name": str(node.get("name") or ""),
                "type": str(node.get("type") or ""),
                "parent": str((parent or {}).get("name") or ""),
                "method": str(node.get("verificationMethod") or ""),
                "unreadKind": str(unread.get("kind") or ""),
                "unreadHost": str(unread.get("host") or ""),
                "failure": str(node.get("verificationFailure") or ""),
                "probeHost": _host(str((block.get("probe") or {}).get("url") or "")) if block else "",
            }
        )
    return rows


def _host(url: str) -> str:
    from urllib.parse import urlparse

    return urlparse(url).netloc.lower()


def render(rows) -> str:
    total = sum(len(v) for v in rows.values())
    out: list[str] = []
    w = out.append
    w("# Evidence coverage — every current organisation, by what stands where its source would be")
    w("")
    w("Generated by `python scripts/report_evidence_coverage.py` from `output/graph.json`.")
    w("Do not edit by hand; regenerate it. `tests/test_evidence_coverage.py` re-renders it and")
    w("asserts that the classes below partition the current organisations.")
    w("")
    w("`docs/DEFINITION_OF_DONE.md` criterion 3: every current organisation carries a")
    w("`verificationMethod`, or a recorded reason no official document can be read for it. The")
    w("population is every organisation node that is not a post, not a Treasury accounting or")
    w("receipts line and not a unit the government has replaced. A recorded reason is a fact")
    w("about what this project can read — a host, a policy, a name that counts things — and")
    w("never a finding about the unit; every panel says which.")
    w("")
    sourced = sum(len(rows.get(c, [])) for c in ("method_page", "method_list"))
    recorded = sum(len(rows.get(c, [])) for c in CLASSES if c == "unread" or c.startswith("no_document_"))
    gap = sum(len(rows.get(c, [])) for c in GAP_CLASSES)
    w(f"- current organisations: **{total:,}**")
    w(f"- with a verification method: **{sourced:,}** ({sourced / total:.1%})" if total else "- with a verification method: 0")
    w(f"- with a recorded reason no official document can be read: **{recorded:,}**")
    w(f"- **criterion 3 gap — neither: {gap:,}**")
    w("")
    w("| class | organisations | what it means | route |")
    w("|---|---|---|---|")
    for cls, (heading, meaning, route) in CLASSES.items():
        count = len(rows.get(cls, []))
        if cls == "other" and count == 0:
            continue
        w(f"| {heading} | {count:,} | {meaning} | {route} |")
    w("")
    w("## Where the recorded reasons and the gap sit")
    w("")
    w("The parents holding the most organisations that carry no method, so the work can be")
    w("taken a parent at a time:")
    w("")
    w("| parent | unread | recorded reason | gap |")
    w("|---|---|---|---|")
    per_parent: dict[str, Counter] = defaultdict(Counter)
    for cls, entries in rows.items():
        if cls in ("method_page", "method_list", "other"):
            continue
        bucket = "unread" if cls == "unread" else ("gap" if cls in GAP_CLASSES else "reason")
        for row in entries:
            per_parent[row["parent"] or "the root"][bucket] += 1
    ranked = sorted(per_parent.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))
    for parent, counts in ranked[:40]:
        w(f"| {parent} | {counts['unread']:,} | {counts['reason']:,} | {counts['gap']:,} |")
    w("")
    w("---")
    w("")
    for cls, (heading, meaning, route) in CLASSES.items():
        entries = rows.get(cls, [])
        if cls in ("method_page", "method_list") and entries:
            w(f"## {heading} — {len(entries):,}")
            w("")
            w(f"{meaning}")
            w("")
            w(f"**Route.** {route}")
            w("")
            methods = Counter(r["method"] for r in entries)
            for method, count in sorted(methods.items(), key=lambda kv: (-kv[1], kv[0])):
                w(f"- `{method}` — {count:,}")
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
            detail = ""
            if row["unreadKind"]:
                detail = f" — {row['unreadKind']}" + (f" ({row['unreadHost']})" if row["unreadHost"] else "")
            elif row["probeHost"]:
                detail = f" — probed {row['probeHost']}"
            elif row["failure"]:
                detail = f" — {row['failure']}"
            w(f"- `{row['id']}` — {row['name']} ({row['type']}; under {row['parent'] or 'the root'}){detail}")
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
    gap = sum(len(rows.get(c, [])) for c in GAP_CLASSES)
    print(f"current organisations {total:,}; criterion 3 gap {gap:,}")
    for cls in CLASSES:
        if rows.get(cls):
            print(f"  {len(rows[cls]):6,}  {cls}")
    if rows.get("other"):
        print("refused: an organisation fell outside every class")
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
