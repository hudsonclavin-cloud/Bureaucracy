#!/usr/bin/env python
"""Measure the three gaps, pick the next one, write the next cycle's prompt.

Step 5 of docs/GO.md. Reads output/graph.json only; writes docs/NEXT_CYCLE.md
(and with --record, appends one line to data/audit/cycle_log.jsonl). It
publishes nothing and edits no data file. Counts reuse the repository's own
classifiers (report_cost_coverage, report_unpriced_positions) so they cannot
drift from the reports.

Order is the owner's (2026-10-21): evidence, then money, then pay.
Stop rule: if the last recorded cycle moved no gap, the file says STOP and
asks the owner, instead of inventing work.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import report_cost_coverage as cost  # noqa: E402
import report_unpriced_positions as unpriced  # noqa: E402

GRAPH = ROOT / "output" / "graph.json"
OUT = ROOT / "docs" / "NEXT_CYCLE.md"
LOG = ROOT / "data" / "audit" / "cycle_log.jsonl"

ORDER = ("evidence", "money", "pay")


def measure(graph: dict) -> dict:
    root_id = graph.get("id")
    orgs = verified = 0
    for node, _parent, _replaced in cost.walk_with_lifecycle(graph):
        if node.get("id") == root_id or cost.is_position(node) or cost.is_treasury_line(node):
            continue
        if node.get("synthetic") or str(node.get("lifecycle") or "") == "superseded":
            continue
        orgs += 1
        if node.get("verificationMethod"):
            verified += 1
    classes = {k: len(v) for k, v in cost.collect(graph).items()}
    groups, positions, priced, _ = unpriced.collect(graph)
    researchable = sum(len(v) for v in unpriced.researchable(groups).values())
    return {
        "evidence": {"organisations": orgs, "verified": verified, "gap": orgs - verified},
        "money": {
            "bare_estimates": classes.get("estimate", 0),
            "committee_estimates": classes.get("estimate_committee", 0),
            "gap": classes.get("estimate", 0),
        },
        "pay": {"positions": positions, "priced": priced, "unpriced_researchable": researchable,
                "gap": researchable},
    }


def last_cycle(log: Path):
    if not log.exists():
        return None
    lines = [l for l in log.read_text().splitlines() if l.strip()]
    return json.loads(lines[-1]) if lines else None


ROUTES = {
    "evidence": [
        "python scripts/nominate.py status --kind source   # organisations with no candidate page",
        "Take a batch of unverified organisations; for each, the Manual, a directory, a committee list or a "
        "nominated page (docs/SOURCE_NOMINATION_RUNBOOK.md). A nomination is not evidence until the verifier reads it.",
        "python scripts/verify_base_graph.py --dry-run, then without --dry-run (needs the .gov hosts)",
        "Where no official document can be read, record the terminal reason (host refuses crawler, no page, no list).",
    ],
    "money": [
        "python scripts/probe_combined_statement.py   # next chapter; it refuses unless the chapter reconciles to the cent",
        "Fetch the chapter only with scripts/fetch_fixture.py; add a REVIEWED_ROWS entry per unit "
        "(CURATION.md 22.6-22.9); never match by fuzzy name.",
        "python scripts/derive_combined_statement_evidence.py --dry-run, then write",
    ],
    "pay": [
        "python scripts/report_research_prompts.py --dry-run   # title families, largest first",
        "Take the largest family; find the pay DOCUMENT (not a figure); add a reviewed row or a terminal reason.",
        "Posts that sit beneath a replaced unit or off the federal schedule are not researched.",
    ],
}

PIPE = [
    "python scripts/regenerate_published_graph.py --treasury-rows <the statement named in __budgetSummary.statement_file>",
    "python scripts/report_cost_coverage.py && python scripts/report_unpriced_positions.py",
    "python scripts/validate_published_graph.py",
    "python -m pytest tests/ -q",
    "node scripts/frontend_smoke.mjs   # only if js/ changed",
]


def render(before: dict, pick: str, stop: str | None) -> str:
    b = before
    lines = [
        "# Next cycle",
        "",
        f"Generated {date.today().isoformat()} by `python scripts/next_cycle.py` from `output/graph.json`. "
        "Do not edit by hand.",
        "",
        "## Gaps now",
        "",
        "| criterion | gap | measure |",
        "|---|---|---|",
        f"| Evidence | **{b['evidence']['gap']}** | {b['evidence']['verified']} of {b['evidence']['organisations']} "
        "current organisations carry a verification method |",
        f"| Money | **{b['money']['gap']}** | bare estimates (no sourced figure of any kind); "
        f"{b['money']['committee_estimates']} committee estimates are counted apart |",
        f"| Pay | **{b['pay']['gap']}** | positions no pay document reaches, excluding those beneath a replaced unit "
        f"or off the federal schedule ({b['pay']['priced']} of {b['pay']['positions']} are priced) |",
        "",
    ]
    if stop:
        lines += ["## STOP", "", stop, ""]
        return "\n".join(lines)
    lines += [f"## This cycle: {pick.upper()}", "", "Order is the owner's: evidence, then money, then pay.", "",
              "### Find and verify", ""]
    lines += [f"{i}. {s}" for i, s in enumerate(ROUTES[pick], 1)]
    lines += ["", "### Place, then prove", ""]
    lines += [f"{i}. `{s}`" if not s.startswith("node") else f"{i}. `{s}`" for i, s in enumerate(PIPE, 1)]
    lines += [
        "",
        "### Hand off",
        "",
        "```bash",
        "python scripts/next_cycle.py --record --note \"<what moved>\"   # logs before/after, rewrites this file",
        "```",
        "",
        "### Rules",
        "",
        "- Never hand-edit data/federal_gov_complete_1.json, data/verification/* or output/*.",
        "- Fixtures only through scripts/fetch_fixture.py. Never read, store or print a person's name.",
        "- Stop if the gate or the suite fails. Report the failure; do not route around it.",
        "- If this cycle moves no gap number, the next run of this script prints STOP and asks the owner.",
        "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", type=Path, default=GRAPH)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--log", type=Path, default=LOG)
    ap.add_argument("--record", action="store_true", help="append this measurement to the cycle log")
    ap.add_argument("--note", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    graph = json.loads(a.graph.read_text())
    now = measure(graph)
    prev = last_cycle(a.log)
    gaps = {k: now[k]["gap"] for k in ORDER}
    stop = None
    # A recorded line carries the gaps as they stood when that cycle was handed out. If the gap it picked
    # has not fallen since, the cycle moved nothing and is not repeated. A "baseline" line is not a cycle.
    if prev and prev.get("pick") and prev.get("note") != "baseline" and gaps[prev["pick"]] >= prev["gaps"][prev["pick"]]:
        stop = (f"The last cycle picked **{prev['pick']}** with a gap of {prev['gaps'][prev['pick']]} and it is now "
                f"{gaps[prev['pick']]}. A cycle that moves no gap is not repeated. Report what blocked it "
                "and ask the owner which route to change.")
    pick = next((k for k in ORDER if gaps[k] > 0), ORDER[0])
    text = render(now, pick, stop)
    if a.dry_run:
        print(text)
        return 0
    a.out.write_text(text + "\n")
    if a.record:
        a.log.parent.mkdir(parents=True, exist_ok=True)
        with a.log.open("a") as f:
            f.write(json.dumps({"date": date.today().isoformat(), "gaps": gaps, "pick": pick,
                                "note": a.note or "baseline"}) + "\n")
    print(json.dumps({"gaps": gaps, "pick": pick, "stop": bool(stop)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
