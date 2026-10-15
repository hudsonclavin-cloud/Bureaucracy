#!/usr/bin/env python3
"""Export the node lists a deep-research run needs as attachable CSVs.

`docs/RESEARCH_PROMPT_5_DEEP_RESEARCH.md` asks an outside research tool which
documents would reach which of this graph's units and posts. The first run
(Perplexity, 2026-10-15) declined, correctly: it could not say what a document
reaches without the lists of what is unreached. This script writes those lists
from the published graph, so the prompt can be run with them attached.

It reads `output/graph.json` and `data/verification/official_sites.json` and
writes nothing anywhere else: the pack goes to `output/research_pack/`
(gitignored), and is regenerated rather than committed, because every file in
it is a view of the published graph and would go stale with the next build.

Files written:

  organisations.csv        every organisation node, with its parent, branch,
                           cost status, verification status and what the graph
                           already holds about it (candidate page, Manual entry,
                           USAspending toptier code, OMB CGAC code, FedScope)
  estimated_units.csv      the organisations that publish an apportioned
                           estimate, with the basis of the share
  orgs_without_source.csv  organisations with no official source at all
  orgs_without_page.csv    organisations with no candidate page to fetch
  unread_hosts.csv         pages the verifier could not read, by host and kind
  posts_without_source.csv every post with no official source
  unpriced_posts.csv       every post with no pay claim, with its title family,
                           its parent and nearest organisation, and the reason
  README.md                what each file is and how the counts were made

No person's name is in any of it: the graph carries none.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report_research_prompts import family_name  # noqa: E402
from report_unpriced_positions import PAY_FIELDS, classify  # noqa: E402

GRAPH = ROOT / "output" / "graph.json"
SITES = ROOT / "data" / "verification" / "official_sites.json"
DEFAULT_OUT = ROOT / "output" / "research_pack"

BRANCHES = {
    "legislative-branch": "Legislative",
    "executive-branch": "Executive",
    "judicial-branch": "Judicial",
}
SECTORS = {"exec-independent": "Independent establishments", "exec-regulatory": "Regulatory commissions"}


def is_post(node) -> bool:
    return "position" in str(node.get("type") or "").casefold() or "role" in str(node.get("type") or "").casefold()


def is_line(node) -> bool:
    return bool(node.get("synthetic")) or "treasury accounting line" in str(node.get("type") or "").casefold()


def walk(root):
    """(node, ancestors, replaced?) for every node, ancestors root-first."""
    stack = [(root, [], False)]
    while stack:
        node, ancestors, replaced = stack.pop()
        replaced = replaced or str(node.get("lifecycle") or "") == "superseded"
        yield node, ancestors, replaced
        for child in reversed(node.get("children") or []):
            stack.append((child, ancestors + [node], replaced))


def branch_of(ancestors, node) -> str:
    chain = ancestors + [node]
    for item in chain:
        if item.get("id") in SECTORS:
            return f"Executive — {SECTORS[item['id']]}"
    for item in chain:
        if item.get("id") in BRANCHES:
            return BRANCHES[item["id"]]
    return "Root"


def nearest_org(ancestors):
    for item in reversed(ancestors):
        if not is_post(item) and not is_line(item):
            return item
    return {}


def get(block, *keys):
    for key in keys:
        if not isinstance(block, dict):
            return ""
        block = block.get(key)
    return "" if block is None else block


def write_csv(path: Path, header, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    return len(rows)


def build(out_dir: Path) -> dict:
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    sites = json.loads(SITES.read_text(encoding="utf-8"))
    anchor = graph.get("__budgetSummary") or {}
    out_dir.mkdir(parents=True, exist_ok=True)

    orgs, estimates, orgs_nosrc, orgs_nopage, posts_nosrc, unpriced = [], [], [], [], [], []
    unread = Counter()
    for node, ancestors, replaced in walk(graph):
        if not ancestors or is_line(node):
            continue
        parent = ancestors[-1]
        branch = branch_of(ancestors, node)
        sources = node.get("sourceUrls") or []
        status = node.get("verificationStatus") or "unverified"
        unread_block = node.get("verificationUnread")
        if isinstance(unread_block, dict):
            host = urlparse(str(unread_block.get("url") or "")).netloc
            unread[(host, unread_block.get("kind") or "other", "post" if is_post(node) else "organisation")] += 1
        if is_post(node):
            org = nearest_org(ancestors)
            if not sources and not replaced:
                posts_nosrc.append([node.get("id"), node.get("name"), parent.get("id"), parent.get("name"),
                                    org.get("id", ""), org.get("name", ""), branch])
            if not any(isinstance(node.get(f), dict) for f in PAY_FIELDS):
                listing = node.get("positionCurrentListing") or node.get("positionListing") or {}
                unpriced.append([
                    node.get("id"), node.get("name"), family_name(node.get("name") or ""),
                    parent.get("id"), parent.get("name"), org.get("id", ""), org.get("name", ""), branch,
                    classify(node, replaced), node.get("representsPosts") or "",
                    get(listing, "payPlan"), get(listing, "payLevel") or get(listing, "level"),
                ])
            continue
        has_page = bool([u for u in (sites.get(node.get("id")) or []) if isinstance(u, str)])
        row = [
            node.get("id"), node.get("name"), node.get("type") or "", parent.get("id"), parent.get("name"),
            branch, len(ancestors), "yes" if replaced else "",
            node.get("cost_status") or "", node.get("resolved_total_amount") if node.get("cost_status") in ("official", "root_total") else "",
            status, len(sources), node.get("verificationMethod") or "",
            "yes" if has_page else "",
            get(node, "govmanEntry", "listedName"),
            get(node, "usaspendingOutlays", "toptierCode") or get(node, "usaspendingOutlays", "agencyCode"),
            get(node, "ombBudget", "cgacAgencyCode"),
            get(node, "employeesOfficialSource", "listedName"),
            node.get("employees") or "",
        ]
        orgs.append(row)
        if replaced:
            continue
        if node.get("cost_status") == "allocated":
            estimates.append([node.get("id"), node.get("name"), node.get("type") or "", parent.get("id"),
                              parent.get("name"), branch, node.get("cost_basis") or "",
                              node.get("resolved_total_amount") or "",
                              "yes" if any(isinstance(node.get(k), dict) for k in
                                           ("usaspendingOutlays", "ombBudget", "auditedNetCost",
                                            "committeeDisbursements")) else ""])
        if not sources:
            orgs_nosrc.append([node.get("id"), node.get("name"), node.get("type") or "", parent.get("id"),
                               parent.get("name"), branch, "yes" if has_page else ""])
        if not has_page:
            orgs_nopage.append([node.get("id"), node.get("name"), node.get("type") or "", parent.get("id"),
                                parent.get("name"), branch, status])

    counts = {
        "organisations.csv": write_csv(out_dir / "organisations.csv", [
            "id", "name", "type", "parent_id", "parent_name", "branch_or_sector", "depth", "replaced_unit",
            "cost_status", "measured_amount_usd", "verification_status", "official_source_count",
            "verification_method", "has_candidate_page", "government_manual_entry_name",
            "usaspending_toptier_code", "omb_cgac_agency_code", "opm_fedscope_listed_name",
            "curated_employees_text_uncited"], orgs),
        "estimated_units.csv": write_csv(out_dir / "estimated_units.csv", [
            "id", "name", "type", "parent_id", "parent_name", "branch_or_sector", "share_basis",
            "apportioned_estimate_usd", "already_has_a_sourced_figure_of_another_kind"], estimates),
        "orgs_without_source.csv": write_csv(out_dir / "orgs_without_source.csv", [
            "id", "name", "type", "parent_id", "parent_name", "branch_or_sector", "has_candidate_page"], orgs_nosrc),
        "orgs_without_page.csv": write_csv(out_dir / "orgs_without_page.csv", [
            "id", "name", "type", "parent_id", "parent_name", "branch_or_sector", "verification_status"], orgs_nopage),
        "unread_hosts.csv": write_csv(out_dir / "unread_hosts.csv", ["host", "kind", "node_kind", "nodes"],
                                      [[h, k, n, c] for (h, k, n), c in unread.most_common()]),
        "posts_without_source.csv": write_csv(out_dir / "posts_without_source.csv", [
            "id", "title", "parent_id", "parent_name", "organisation_id", "organisation_name",
            "branch_or_sector"], posts_nosrc),
        "unpriced_posts.csv": write_csv(out_dir / "unpriced_posts.csv", [
            "id", "title", "title_family", "parent_id", "parent_name", "organisation_id", "organisation_name",
            "branch_or_sector", "reason", "represents_posts", "listed_pay_plan", "listed_level_or_grade"], unpriced),
    }
    readme = [
        "# Research pack",
        "",
        f"Exported by `scripts/export_research_pack.py` from the published graph "
        f"(anchor: {anchor.get('label') or 'FYTD net outlays'} through {anchor.get('record_date') or '?'}). "
        "Attach these files to the prompts in `docs/RESEARCH_PROMPT_5_DEEP_RESEARCH.md`.",
        "",
        "| file | rows | what it is |",
        "|---|---|---|",
        f"| organisations.csv | {counts['organisations.csv']} | every organisation node, including replaced units (flagged) |",
        f"| estimated_units.csv | {counts['estimated_units.csv']} | organisations whose only cost figure is an apportioned share of a measured ancestor |",
        f"| orgs_without_source.csv | {counts['orgs_without_source.csv']} | live organisations with no official source of any kind |",
        f"| orgs_without_page.csv | {counts['orgs_without_page.csv']} | live organisations with no candidate official page to fetch |",
        f"| unread_hosts.csv | {counts['unread_hosts.csv']} | (host, failure kind) pairs where a page was queued and could not be read |",
        f"| posts_without_source.csv | {counts['posts_without_source.csv']} | live posts with no official source |",
        f"| unpriced_posts.csv | {counts['unpriced_posts.csv']} | posts with no pay claim; `reason` is the project's own classification |",
        "",
        "Notes for a reader:",
        "",
        "- `id` values are stable keys. Answer by id where you can.",
        "- `curated_employees_text_uncited` is hand-entered and cited by nothing; do not treat it as evidence.",
        "- `apportioned_estimate_usd` is the project's own division of a parent's measured figure and is "
        "NOT a measurement; it is included so a source's figure can be compared, never as a target to match.",
        "- `reason` in unpriced_posts.csv: `unreached` = no document read names the title; `multiplicity` = the node "
        "stands for several holders, so only a figure that holds for every holder may be published; "
        "`beneath_replaced_unit` and `not_federally_paid` are not research work; `listed_no_rate` = OPM lists the "
        "post with a grade or level but no rate.",
        "- `title_family` groups templated copies of one title (e.g. 'Chief Financial Officer' under 60 "
        "organisations). Answer per family where one document governs the whole family.",
        "- Many titles are curated templates, not titles any agency prints. A useful answer may be "
        "'no agency uses this title; the real post is X'.",
        "",
    ]
    (out_dir / "README.md").write_text("\n".join(readme), encoding="utf-8")
    return counts


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    counts = build(args.out)
    for name, n in counts.items():
        print(f"{n:6d}  {args.out / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
