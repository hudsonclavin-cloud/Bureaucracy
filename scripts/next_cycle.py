#!/usr/bin/env python
"""Measure the three gaps, pick the next one, write the next cycle's prompt.

Step 5 of docs/GO.md. Reads output/graph.json only; writes docs/NEXT_CYCLE.md
(and with --record, appends one line to data/audit/cycle_log.jsonl). It
publishes nothing and edits no data file. Counts reuse the repository's own
classifiers (report_cost_coverage, report_unpriced_positions) so they cannot
drift from the reports.

Order is the owner's (2026-10-21): evidence, then money, then pay.

Each criterion has an OPEN gap (the definition of done is not met) and a REACH
(a recorded reason that more documents could still turn into a source or a
figure). The pick is the first criterion in order with an open gap; when every
open gap is zero it is the first with reach, and the file says that the
definition of done is met and this is improvement, not completion. The refresh
side (criterion 5) belongs to scripts/update_cycle.py and is not repeated here.

Stop rule: if the number the last recorded cycle aimed at did not fall, the
file says STOP and asks the owner, instead of inventing work.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import report_cost_coverage as cost  # noqa: E402
import report_evidence_coverage as evidence  # noqa: E402
import report_unpriced_positions as unpriced  # noqa: E402

GRAPH = ROOT / "output" / "graph.json"
OUT = ROOT / "docs" / "NEXT_CYCLE.md"
LOG = ROOT / "data" / "audit" / "cycle_log.jsonl"
BUDGET = ROOT / "data" / "audit" / "cycle_budget.json"

ORDER = ("evidence", "money", "pay")


def measure(graph: dict) -> dict:
    """Two numbers per criterion.

    `gap` is the OPEN gap by the definition of done: what no figure, source or
    recorded reason yet stands behind. `reach` is work that could still turn a
    recorded reason into a figure or a source; it is picked only when every open
    gap is zero, because the definition of done is already met there.
    """
    ev = {k: len(v) for k, v in evidence.collect(graph).items()}
    ev_total = sum(ev.values())
    ev_gap = sum(ev.get(c, 0) for c in evidence.GAP_CLASSES)
    ev_sourced = ev.get("method_page", 0) + ev.get("method_list", 0)
    ev_reach = ev_total - ev_sourced - ev_gap  # unit has a recorded reason, no document yet

    cc = {k: len(v) for k, v in cost.collect(graph).items()}
    bare = cc.get("estimate", 0)
    named = cc.get("estimate_named_in_a_held_document", 0)

    groups, positions, priced, _ = unpriced.collect(graph)
    nodes = {str(n.get("id")): n for n, _p, _r in unpriced.walk(graph)}
    open_pay = reach_pay = 0
    for rows in unpriced.researchable(groups).values():
        for row in rows:
            if isinstance(nodes[row["id"]].get("payNoDocument"), dict):
                reach_pay += 1
            else:
                open_pay += 1
    return {
        "evidence": {"organisations": ev_total, "sourced": ev_sourced, "gap": ev_gap, "reach": ev_reach},
        "money": {"bare_estimates": bare, "named_in_a_held_document": named,
                  "explained_blanks": cc.get("estimate_explained_blank", 0),
                  "committee_estimates": cc.get("estimate_committee", 0), "gap": bare, "reach": named},
        "pay": {"positions": positions, "priced": priced, "gap": open_pay, "reach": reach_pay},
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


def read_budget(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except ValueError:
        return None


def render_header(budget) -> list[str]:
    if not budget:
        return []
    done, total = budget["completed"], budget["total"]
    left = total - done
    if left <= 0:
        return [f"**Loops: {done} of {total} done. The requested number is complete; stop and report.**", ""]
    return [f"**Loop {done + 1} of {total}** ({left} remaining including this one).", ""]


def pick_of(now: dict) -> tuple[str | None, str]:
    for k in ORDER:
        if now[k]["gap"] > 0:
            return k, "gap"
    for k in ORDER:
        if now[k]["reach"] > 0:
            return k, "reach"
    return None, "none"


def render(now: dict, pick: str | None, metric: str, stop: str | None, budget=None) -> str:
    e, m, p = now["evidence"], now["money"], now["pay"]
    lines = [
        "# Next cycle",
        "",
        f"Generated {date.today().isoformat()} by `python scripts/next_cycle.py` from `output/graph.json`. "
        "Do not edit by hand.",
        "",
    ] + render_header(budget) + [
        "## Where the three criteria stand",
        "",
        "Open gap = the definition of done is not met. Reach = a recorded reason that more documents could still "
        "turn into a source or a figure.",
        "",
        "| criterion | open gap | reach | measure |",
        "|---|---|---|---|",
        f"| Evidence | **{e['gap']}** | {e['reach']} | {e['sourced']} of {e['organisations']} current organisations "
        "carry a verification method; the rest carry a recorded reason |",
        f"| Money | **{m['gap']}** | {m['reach']} | {m['bare_estimates']} bare estimates; {m['explained_blanks']} explained "
        f"blanks, {m['named_in_a_held_document']} of them named in a held document with no licensed figure; "
        f"{m['committee_estimates']} committee estimates counted apart |",
        f"| Pay | **{p['gap']}** | {p['reach']} | {p['priced']} of {p['positions']} posts priced; reach counts "
        "researchable posts that carry a documents-checked blank |",
        "",
        "Not measured here: criterion 4(a) (list units, CURATION.md 32.1) and criteria 5-7 (the refresh job, "
        "`scripts/update_cycle.py`, which counts only scheduled cycles).",
        "",
    ]
    if budget and budget["completed"] >= budget["total"]:
        return "\n".join(lines + ["## Done", "", f"All {budget['total']} requested loops are complete. Summarise "
                                 "what each moved (data/audit/cycle_log.jsonl) and stop.", ""])
    if stop:
        return "\n".join(lines + ["## STOP", "", stop, ""])
    if pick is None:
        return "\n".join(lines + ["## Nothing to do", "",
                                 "Every open gap and every reach is zero. Run `scripts/update_cycle.py --plan`.", ""])
    kind = ("This closes an OPEN gap." if metric == "gap" else
            "Every open gap is zero, so the definition of done is met for all three. This cycle IMPROVES: it turns a "
            "recorded reason into a source or a figure.")
    lines += [f"## This cycle: {pick.upper()} ({metric})", "", kind, "", "### Find and verify", ""]
    lines += [f"{i}. {t}" for i, t in enumerate(ROUTES[pick], 1)]
    lines += ["", "### Place, then prove", ""]
    lines += [f"{i}. `{t}`" for i, t in enumerate(PIPE, 1)]
    lines += [
        "",
        "### Hand off",
        "",
        "```bash",
        "python scripts/next_cycle.py --record --note \"<what moved>\"   # logs this measurement, rewrites this file",
        "```",
        "",
        "### Rules",
        "",
        "- Never hand-edit data/federal_gov_complete_1.json, data/verification/* or output/*.",
        "- Fixtures only through scripts/fetch_fixture.py. Never read, store or print a person's name.",
        "- Stop if the gate or the suite fails. Report the failure; do not route around it.",
        "- If the number this cycle aims at does not fall, the next run prints STOP and asks the owner.",
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
    ap.add_argument("--budget", type=Path, default=BUDGET)
    ap.add_argument("--loops", type=int, default=None, help="start a run of N loops (replaces any earlier budget)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.loops is not None:
        if a.loops < 1:
            ap.error("--loops must be at least 1")
        budget = {"total": a.loops, "completed": 0, "started": date.today().isoformat()}
        if not a.dry_run:
            a.budget.parent.mkdir(parents=True, exist_ok=True)
            a.budget.write_text(json.dumps(budget) + "\n")
    else:
        budget = read_budget(a.budget)
    note = a.note or "baseline"
    graph = json.loads(a.graph.read_text())
    now = measure(graph)
    prev = last_cycle(a.log)
    pick, metric = pick_of(now)
    stop = None
    # A recorded line carries the numbers as they stood when that cycle was handed out. If the number it aimed at
    # has not fallen since, the cycle moved nothing and is not repeated. A "baseline" line is not a cycle.
    if prev and prev.get("pick") and prev.get("note") != "baseline":
        was = prev["numbers"][prev["pick"]][prev["metric"]]
        is_now = now[prev["pick"]][prev["metric"]]
        if is_now >= was:
            stop = (f"The last cycle aimed at **{prev['pick']} {prev['metric']}**, which stood at {was} and is now "
                    f"{is_now}. A cycle that moves nothing is not repeated. Report what blocked it and ask the "
                    "owner which route to change.")
    text = render(now, pick, metric, stop, budget)
    if a.dry_run:
        print(text)
        return 0
    a.out.write_text(text + "\n")
    if a.record and budget and note != "baseline" and budget["completed"] < budget["total"]:
        budget["completed"] += 1
        a.budget.write_text(json.dumps(budget) + "\n")
        a.out.write_text(render(now, pick, metric, stop, budget) + "\n")
    if a.record:
        a.log.parent.mkdir(parents=True, exist_ok=True)
        numbers = {k: {"gap": now[k]["gap"], "reach": now[k]["reach"]} for k in ORDER}
        with a.log.open("a") as f:
            f.write(json.dumps({"date": date.today().isoformat(), "numbers": numbers, "pick": pick,
                                "metric": metric, "note": note}) + "\n")
    print(json.dumps({"pick": pick, "metric": metric, "stop": bool(stop)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
