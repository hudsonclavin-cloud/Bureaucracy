#!/usr/bin/env python
"""One update cycle: fetch what is due, rebuild, run every check, judge the
change budget, and say whether the result may be published.

    python scripts/update_cycle.py --plan                 # what is due and how each would be fetched; fetches and writes nothing
    python scripts/update_cycle.py --hold                 # the whole cycle in HOLD mode: never publishes, writes the report
    python scripts/update_cycle.py --hold --offline       # the same without the fetch step (a rebuild from the committed fixtures)
    python scripts/update_cycle.py --hold --no-tests      # skip the suite (a quick local run; a real cycle runs it)
    python scripts/update_cycle.py --publish              # refused until three consecutive held cycles were clean

`docs/DEFINITION_OF_DONE.md` criterion 5, in the order it gives:

1. Fetch each due source (`data/source_registry.json` through
   `data_pipeline/freshness.py`) with the fixture fetcher's own robots and
   User-Agent policy, recording a `.meta.json` beside every file.
2. Refuse a fetch that is not the document: every registry row carries a
   `contentCheck` (content type, minimum size, strings that must and must
   not appear, for a statement the record date that must be newer than the
   copy in use), and a fetched file that fails it is deleted unread and
   recorded as refused. A host that refuses is "source unavailable this
   cycle", never a failure that blocks the other sources.
3. Run every derive step, regenerate the graph (from the new statement where
   one was fetched) and regenerate the reports.
4. Run the gate, the test suite and the browser smoke check.
5. Run the change budget (`scripts/build_change_history.py --record`; exit 3
   is a hold) and write the review queue.
6. Publish only in `--publish` mode, which this script refuses until
   `data/audit/update_cycles.json` shows three consecutive clean held cycles
   -- the mitigation the definition names. Even then this script never pushes:
   it writes `output/update_cycle_report.json` with `publishable: true` and the
   workflow decides what to do with the branch. A person hears only about a
   failure or a hold.

Everything the cycle did is in the report: each step's exit code and the
tail of its output, every fetch and every refusal with its reason, the budget's
verdict and the queue's open count.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline import freshness as fr  # noqa: E402
from data_pipeline.crawler.treasury_outlays import API_URL as MTS_API_URL  # noqa: E402

GRAPH = PROJECT_ROOT / "output" / "graph.json"
REPORT = PROJECT_ROOT / "output" / "update_cycle_report.json"
CYCLES = PROJECT_ROOT / "data" / "audit" / "update_cycles.json"
FIXTURES = PROJECT_ROOT / "tests" / "fixtures"
CLEAN_CYCLES_BEFORE_PUBLISH = 3
PYTHON = sys.executable
#: The derive steps, in an order that puts a step after the evidence files it
#: reads (the salary-table joins read the listings; the Executive Schedule
#: join reads the listings too).
DERIVE_STEPS = (
    "derive_directory_evidence.py", "derive_govman_evidence.py", "derive_headcount_evidence.py", "derive_position_evidence.py",
    "derive_plum_current_evidence.py", "derive_usajobs_evidence.py", "derive_fr_signature_evidence.py",
    "derive_pay_evidence.py", "derive_gs_pay_evidence.py", "derive_schedule_pay_evidence.py", "derive_judicial_pay_evidence.py",
    "derive_congressional_pay_evidence.py", "derive_whitehouse_pay_evidence.py", "derive_us_code_pay_schedule_evidence.py",
    "derive_va_title38_pay_evidence.py", "derive_derived_pay_evidence.py", "derive_tier_reference_pay_evidence.py",
    "derive_military_pay_evidence.py", "derive_us_code_stated_pay_evidence.py", "derive_doj_ad_pay_evidence.py",
    "derive_employment_status_evidence.py", "derive_usaspending_evidence.py", "derive_object_class_evidence.py",
    "derive_net_cost_evidence.py", "derive_omb_budget_evidence.py", "derive_committee_disbursements_evidence.py",
    "derive_combined_statement_evidence.py",
)
REPORT_STEPS = (
    "report_unpriced_positions.py", "report_cost_coverage.py", "report_evidence_coverage.py",
    "report_list_reconciliation.py", "report_research_prompts.py", "report_source_registry.py",
    "export_flat_csv.py",
)
CONTENT_TYPES = {
    "json": ("application/json", "text/json"), "html": ("text/html",), "csv": ("text/csv", "application/csv", "text/plain", "application/octet-stream"),
    "pdf": ("application/pdf",), "zip": ("application/zip", "application/x-zip-compressed", "application/octet-stream"),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/octet-stream"),
    "xml": ("application/xml", "text/xml"), "text": ("text/plain",),
}


def newest_committed_statement() -> Path | None:
    """The date-named Monthly Treasury Statement fixture with the latest record date."""
    found = sorted(FIXTURES.glob("mts_table5_[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].json"))
    return found[-1] if found else None


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(cmd: list[str], *, cwd: Path = PROJECT_ROOT, timeout: int = 3600) -> dict[str, Any]:
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
        code, out = proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired as error:
        code, out = 124, f"timed out after {timeout}s: {error}"
    except OSError as error:
        code, out = 127, str(error)
    return {"command": " ".join(cmd[:4]) + (" …" if len(cmd) > 4 else ""), "exit": code, "seconds": round(time.time() - started, 1),
            "tail": out[-1500:]}


# --- step 2: a fetched file must be the document ------------------------------

def content_check(path: Path, meta: dict[str, Any], check: dict[str, Any], copy_date: str | None) -> list[str]:
    problems = []
    data = path.read_bytes()
    if check.get("minBytes") and len(data) < int(check["minBytes"]):
        problems.append(f"{len(data):,} bytes is under the floor of {int(check['minBytes']):,}")
    wanted = str(check.get("contentType") or "")
    served = str(meta.get("content_type") or "").split(";")[0].strip().lower()
    if wanted and served and served not in CONTENT_TYPES.get(wanted, (wanted,)):
        problems.append(f"served as {served}, not {wanted}")
    text = data[:5_000_000].decode("utf-8", "replace") if wanted in ("json", "html", "csv", "xml", "text") else ""
    for needle in check.get("mustContain") or []:
        if text and needle not in text:
            problems.append(f"does not contain {needle!r}")
    for needle in check.get("mustNotContain") or []:
        if text and needle in text:
            problems.append(f"contains {needle!r}, a page that is not the document")
    if check.get("parse") and wanted == "json":
        try:
            payload = json.loads(text)
        except ValueError as error:
            problems.append(f"not JSON: {error}")
            payload = None
        if isinstance(payload, dict) and check.get("newerThanCopy") and copy_date:
            field = str(check["newerThanCopy"])
            rows = payload.get("data") if isinstance(payload.get("data"), list) else payload.get("rows") if isinstance(payload.get("rows"), list) else []
            dates = sorted({str(r.get(field) or "")[:10] for r in rows if isinstance(r, dict) and r.get(field)})
            if not dates or dates[-1] <= copy_date:
                problems.append(f"the newest {field} served is {dates[-1] if dates else 'none'}, not newer than the copy in use ({copy_date})")
    return problems


def fetch_statement(entry: dict[str, Any], *, dry: bool) -> dict[str, Any]:
    """The Monthly Treasury Statement: ask the API for its newest record date;
    fetch that statement's rows verbatim into a dated fixture only when it is
    newer than the copy in use."""
    from data_pipeline.crawler.treasury_outlays import fetch_latest_record_date, fetch_rows_for_record_date

    copy_date = (entry.get("copy") or {}).get("date")
    result = {"source": entry["id"], "kind": "api_latest_statement", "url": MTS_API_URL, "copyInUse": copy_date}
    if dry:
        result["would"] = "ask the API for the newest record_date and fetch that statement when newer than the copy in use"
        return result
    try:
        latest = fetch_latest_record_date()
    except Exception as error:  # noqa: BLE001 - the reason is the record
        result.update(outcome="unavailable", reason=f"{type(error).__name__}: {error}")
        return result
    result["latestRecordDate"] = latest
    if not latest or (copy_date and latest <= copy_date):
        result.update(outcome="nothing_newer")
        return result
    target = FIXTURES / f"mts_table5_{latest}.json"
    try:
        rows = fetch_rows_for_record_date(latest)
    except Exception as error:  # noqa: BLE001
        result.update(outcome="unavailable", reason=f"{type(error).__name__}: {error}")
        return result
    payload = {"api_url": f"{MTS_API_URL}?filter=record_date:eq:{latest}&sort=print_order_nbr", "fetched_at": now_iso(), "record_date": latest, "rows": rows}
    totals = [r for r in rows if "total outlays" in str(r.get("classification_desc") or "").casefold()]
    if not rows or not totals:
        result.update(outcome="refused", reason="the response carries no rows or no Total Outlays line; not the statement")
        return result
    body = json.dumps(payload, indent=1).encode("utf-8")
    target.write_bytes(body)
    target.with_name(target.name + ".meta.json").write_text(json.dumps({
        "fetched_at": payload["fetched_at"], "url": payload["api_url"], "status": 200, "final_url": payload["api_url"], "content_type": "application/json",
        "user_agent": "data_pipeline.crawler.treasury_outlays", "robots": "api.fiscaldata.treasury.gov answers robots.txt 404; nothing published to obey",
        "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(), "error": None}, indent=1) + "\n", encoding="utf-8")
    result.update(outcome="fetched", path=str(target.relative_to(PROJECT_ROOT)), rows=len(rows))
    return result


def fetch_fixed(entry: dict[str, Any], row: dict[str, Any], *, dry: bool) -> list[dict[str, Any]]:
    """A source whose URL does not change: re-fetch each of its fixtures to a
    temporary file, check it is the document, and replace the fixture in place
    only when the bytes differ. A refusal leaves the old fixture untouched."""
    from scripts.fetch_fixture import fetch as fetch_file

    check = (row.get("fetch") or {}).get("contentCheck") or {}
    copy_date = (entry.get("copy") or {}).get("date")
    metas = fr.fixture_metas(list(row.get("fixtures") or []))
    if row["fetch"]["kind"] == "fixed_url":
        metas = [m for m in metas if m.get("url") == row["fetch"]["url"]] or metas[:1]
    results = []
    for meta in metas:
        fixture = FIXTURES / meta["path"].replace(".meta.json", "")
        result = {"source": entry["id"], "kind": row["fetch"]["kind"], "url": meta["url"], "fixture": str(fixture.relative_to(PROJECT_ROOT))}
        if dry:
            result["would"] = "re-fetch to a temporary file, check it is the document, replace the fixture if the bytes differ"
            results.append(result)
            continue
        with tempfile.TemporaryDirectory(prefix="fetch-", dir=str(PROJECT_ROOT / "tests" / ".tmp" if (PROJECT_ROOT / "tests" / ".tmp").is_dir() else PROJECT_ROOT / "output")) as tmp:
            temp_target = Path(tmp) / fixture.name
            try:
                code = fetch_file(meta["url"], temp_target)
            except Exception as error:  # noqa: BLE001
                result.update(outcome="unavailable", reason=f"{type(error).__name__}: {error}")
                results.append(result)
                continue
            temp_meta_path = temp_target.with_name(temp_target.name + ".meta.json")
            temp_meta = json.loads(temp_meta_path.read_text(encoding="utf-8")) if temp_meta_path.is_file() else {}
            if code != 0 or not temp_target.is_file():
                result.update(outcome="unavailable", reason=str(temp_meta.get("error") or "not served"))
                results.append(result)
                continue
            problems = content_check(temp_target, temp_meta, check, copy_date)
            if problems:
                result.update(outcome="refused", reason="; ".join(problems))
                results.append(result)
                continue
            if temp_meta.get("sha256") == meta.get("sha256"):
                result.update(outcome="unchanged", sha256=meta.get("sha256"))
                results.append(result)
                continue
            shutil.copyfile(temp_target, fixture)
            shutil.copyfile(temp_meta_path, fixture.with_name(fixture.name + ".meta.json"))
            result.update(outcome="fetched", sha256=temp_meta.get("sha256"), previousSha256=meta.get("sha256"))
            results.append(result)
    return results


def fetch_due(block: dict[str, Any], registry: dict[str, Any], *, dry: bool) -> list[dict[str, Any]]:
    rows = {r["id"]: r for r in registry.get("sources") or []}
    results = []
    for entry in block["sources"]:
        if entry["statusAtBuild"] in (fr.STATUS_CURRENT, fr.STATUS_CLOSED):
            continue
        row = rows.get(entry["id"]) or {}
        kind = str((row.get("fetch") or {}).get("kind") or "")
        if kind == "api_latest_statement" and entry["id"] == "monthly_treasury_statement":
            results.append(fetch_statement(entry, dry=dry))
        elif kind in ("fixed_url", "refetch_each_fixture_url", "api_latest_statement"):
            results.extend(fetch_fixed(entry, row, dry=dry))
        elif kind == "url_changes_each_period":
            results.append({"source": entry["id"], "kind": kind, "url": row["fetch"]["url"], "outcome": "needs_a_reviewed_url",
                            "reason": "the next edition is published at an address that changes each period; a person finds it on the landing page and records it"})
        else:
            results.append({"source": entry["id"], "kind": kind, "outcome": "no_fetch_rule"})
    return results


# --- the cycle ---------------------------------------------------------------

def load_cycles() -> list[dict[str, Any]]:
    try:
        data = json.loads(CYCLES.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


SCHEDULED_TRIGGER = "schedule"


def trigger_of_this_run() -> str:
    """What started this run: GitHub's event name on a runner (`schedule`,
    `workflow_dispatch`), `manual` anywhere else."""
    return os.environ.get("GITHUB_EVENT_NAME") or "manual"


def clean_streak(cycles: list[dict[str, Any]]) -> int:
    """Consecutive clean held cycles that the SCHEDULE started, newest first.

    Criterion 5 asks for three monthly cycles with no manual step. A cycle a
    person dispatched, or ran from a laptop, proves the job works but is not the
    schedule keeping its appointment, so it neither counts nor — being a record
    of something other than the schedule — breaks the run: only a scheduled
    cycle that was held does. A record from before the trigger was recorded has
    none and is not counted.
    """
    streak = 0
    for record in reversed(cycles):
        if record.get("trigger") != SCHEDULED_TRIGGER:
            continue
        if record.get("mode") == "hold" and record.get("clean"):
            streak += 1
        else:
            break
    return streak


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true", help="say what is due and how it would be fetched; do nothing")
    mode.add_argument("--hold", action="store_true", help="run the cycle; never publish")
    mode.add_argument("--publish", action="store_true", help="run the cycle and mark the result publishable if three held cycles were clean")
    parser.add_argument("--offline", action="store_true", help="skip the fetch step")
    parser.add_argument("--no-tests", action="store_true", help="skip the test suite")
    parser.add_argument("--no-smoke", action="store_true", help="skip the browser smoke check")
    parser.add_argument("--smoke-args", default="", help="extra arguments for scripts/frontend_smoke.mjs (e.g. --chromium PATH --modules DIR)")
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args((argv or sys.argv)[1:])

    started = now_iso()
    today = date.today()
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    registry = fr.load_registry()
    block, refused_rows = fr.derive(graph, registry, today)
    due = [e for e in block["sources"] if e["statusAtBuild"] not in (fr.STATUS_CURRENT, fr.STATUS_CLOSED)]
    report: dict[str, Any] = {
        "startedAt": started, "mode": "plan" if args.plan else "publish" if args.publish else "hold", "trigger": trigger_of_this_run(), "asOf": today.isoformat(),
        "anchorBefore": str((graph.get("__budgetSummary") or {}).get("record_date") or "")[:10],
        "due": [{"id": e["id"], "status": e["statusAtBuild"], "copy": e["copy"]["date"], "expectedBy": e["expected"].get("expectedBy") or e["expected"].get("recheckDue")} for e in due],
        "registryRowsRefused": refused_rows, "fetches": [], "steps": [], "held": False, "reasons": [], "publishable": False,
    }
    print(f"update cycle ({report['mode']}) as of {today}: {len(due)} source(s) due: " + ", ".join(f"{e['id']} ({e['statusAtBuild']})" for e in due))

    if args.plan:
        report["fetches"] = fetch_due(block, registry, dry=True)
        for f in report["fetches"]:
            print(f"  {f['source']:34} {f['kind']:26} {f.get('would') or f.get('reason') or ''}")
        print(f"derive steps: {len(DERIVE_STEPS)}; then regenerate, {len(REPORT_STEPS)} reports, the gate, the suite, the smoke check, the change budget")
        print(f"clean scheduled held cycles so far: {clean_streak(load_cycles())} of {CLEAN_CYCLES_BEFORE_PUBLISH} needed before --publish is accepted")
        return 0

    streak = clean_streak(load_cycles())
    if args.publish and streak < CLEAN_CYCLES_BEFORE_PUBLISH:
        report["reasons"].append(f"--publish refused: {streak} consecutive clean held cycles recorded, {CLEAN_CYCLES_BEFORE_PUBLISH} needed")
        report["mode"] = "hold"
        print(report["reasons"][-1])

    new_statement: Path | None = None
    if not args.offline:
        report["fetches"] = fetch_due(block, registry, dry=False)
        for f in report["fetches"]:
            print(f"  fetch {f['source']:34} {f.get('outcome', ''):20} {f.get('reason') or f.get('path') or f.get('fixture') or ''}")
            if f.get("outcome") == "fetched" and f.get("kind") == "api_latest_statement" and f["source"] == "monthly_treasury_statement":
                new_statement = PROJECT_ROOT / f["path"]
    else:
        report["fetches"] = [{"outcome": "skipped", "reason": "--offline"}]

    def step(name: str, cmd: list[str], *, required: bool = True, timeout: int = 3600) -> bool:
        result = run(cmd, timeout=timeout)
        result["name"] = name
        result["required"] = required
        report["steps"].append(result)
        ok = result["exit"] == 0
        print(f"  step {name:40} exit {result['exit']:3} {result['seconds']:7.1f}s")
        if not ok and required:
            report["held"] = True
            report["reasons"].append(f"{name} exited {result['exit']}")
        return ok

    for script in DERIVE_STEPS:
        step(f"derive {script}", [PYTHON, str(PROJECT_ROOT / "scripts" / script)])
    regen = [PYTHON, str(PROJECT_ROOT / "scripts" / "regenerate_published_graph.py")]
    # A rebuild handed no statement carries the published Treasury lines forward
    # (`reused_from_previous_build`) and, on a clean checkout, drops the
    # attachToRoot mark the receipts line earned in the build that applied the
    # statement. The first scheduled run showed it: nothing was due, so the
    # rebuild read none. The newest committed statement is the input whenever no
    # newer one was fetched, so the same checkout always rebuilds the same graph.
    rebuild_from = new_statement or newest_committed_statement()
    if rebuild_from is not None:
        regen += ["--treasury-rows", str(rebuild_from)]
    step("regenerate the graph", regen)
    for script in REPORT_STEPS:
        step(f"report {script}", [PYTHON, str(PROJECT_ROOT / "scripts" / script)])
    # The change budget and the queue BEFORE the gate: the gate checks that the
    # history's latest entry describes the graph beside it, so the entry must
    # be recorded first. Exit 3 is the budget's hold and is read below.
    budget = run([PYTHON, str(PROJECT_ROOT / "scripts" / "build_change_history.py"), "--record"])
    budget["name"] = "change budget and review queue"
    budget["required"] = True
    report["steps"].append(budget)
    print(f"  step {'change budget and review queue':40} exit {budget['exit']:3} {budget['seconds']:7.1f}s")
    if budget["exit"] == 3:
        report["held"] = True
        report["reasons"].append("the change budget held the build")
    elif budget["exit"] != 0:
        report["held"] = True
        report["reasons"].append(f"the change history step exited {budget['exit']}")
    step("gate", [PYTHON, str(PROJECT_ROOT / "scripts" / "validate_published_graph.py")])
    if not args.no_tests:
        step("test suite", [PYTHON, "-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider"], timeout=5400)
    else:
        report["steps"].append({"name": "test suite", "exit": None, "skipped": "--no-tests"})
    if not args.no_smoke:
        step("browser smoke check", ["node", str(PROJECT_ROOT / "scripts" / "frontend_smoke.mjs"), *args.smoke_args.split()], timeout=2400)
    else:
        report["steps"].append({"name": "browser smoke check", "exit": None, "skipped": "--no-smoke"})
    try:
        queue = json.loads((PROJECT_ROOT / "data" / "audit" / "review_queue.json").read_text(encoding="utf-8"))
        report["reviewQueueOpen"] = sum(1 for r in queue if isinstance(r, dict) and r.get("status") == "open")
    except (OSError, ValueError):
        report["reviewQueueOpen"] = None
    try:
        after = json.loads(GRAPH.read_text(encoding="utf-8"))
        report["anchorAfter"] = str((after.get("__budgetSummary") or {}).get("record_date") or "")[:10]
    except (OSError, ValueError):
        report["anchorAfter"] = None

    clean = not report["held"]
    report["clean"] = clean
    report["publishable"] = bool(args.publish and clean and streak >= CLEAN_CYCLES_BEFORE_PUBLISH)
    report["finishedAt"] = now_iso()
    report["verdict"] = ("PUBLISHABLE: every check passed and three held cycles were clean" if report["publishable"]
                         else "HELD: a person must look" if report["held"]
                         else f"CLEAN, held by mode: {streak + 1} of {CLEAN_CYCLES_BEFORE_PUBLISH} clean scheduled held cycles once this one is recorded" if report["trigger"] == SCHEDULED_TRIGGER
                         else f"CLEAN, held by mode; started by {report['trigger']}, so it does not count toward the {CLEAN_CYCLES_BEFORE_PUBLISH} scheduled cycles ({streak} so far)")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    cycles = load_cycles()
    cycles.append({"startedAt": started, "finishedAt": report["finishedAt"], "mode": report["mode"], "trigger": report["trigger"], "clean": clean, "held": report["held"],
                   "reasons": report["reasons"], "anchorBefore": report["anchorBefore"], "anchorAfter": report.get("anchorAfter"),
                   "fetched": [f.get("source") for f in report["fetches"] if f.get("outcome") == "fetched"],
                   "reviewQueueOpen": report.get("reviewQueueOpen"), "publishable": report["publishable"]})
    CYCLES.parent.mkdir(parents=True, exist_ok=True)
    CYCLES.write_text(json.dumps(cycles, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(report["verdict"])
    print(f"wrote {args.report.relative_to(PROJECT_ROOT)} and {CYCLES.relative_to(PROJECT_ROOT)}")
    return 0 if clean else 3


if __name__ == "__main__":
    sys.exit(main())
