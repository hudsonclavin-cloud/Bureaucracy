"""The source registry: each source's cycle, the copy in use, and what is due.

`docs/DEFINITION_OF_DONE.md` criterion 6: a committed registry gives, for each
source this graph publishes a figure or a piece of evidence from, its expected
cadence and the date of the copy in use; the update job reads it to decide
what is due; and the panel marks a figure "overdue" once its source has missed
its expected publication by a stated margin.

`data/source_registry.json` is the reviewed table -- one row per source, its
cadence (the reviewer's statement of the publisher's cycle, with a basis), how
the date of the copy in use is READ (never written down where the graph or a
fixture's `.meta.json` already carries it), which fixtures hold the copy, how
the next copy would be fetched and what a fetched file must look like to count
as the document, and which published fields the source feeds. This module
derives from it, on every build:

- the copy's date: off the graph root (the anchor's `record_date`), off the
  maximum of a block field across the nodes (`committeeDisbursements.period.end`
  for the House's chamber), off the fixture's own fetch record, or a stated
  date that a `graphCheck` ties to what the graph publishes;
- the fetch date: the newest `fetched_at` among the row's fixtures (a refusal
  record, which carries no digest, is not a copy);
- the next edition's expected date, from the cadence and the copy's date, the
  publication lag and the overdue margin, or a re-check date for a source with
  no fixed cycle;
- the status AT BUILD TIME: `current`, `newer_edition_expected` (the expected
  date has passed, the margin has not), `overdue`, `recheck_due`,
  `closed_record` or `copy_date_unknown`.

The result is stamped once on the graph root as `__sourceRegistry`, carried
into the viewer copy, and the panel recomputes the status against the reader's
own date so the flag cannot go stale between builds. The gate re-derives the
whole block with its own stdlib reader and refuses a mismatch. Nothing here
fetches, and nothing here changes a figure.
"""

from __future__ import annotations

import calendar
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = PROJECT_ROOT / "data" / "source_registry.json"
FIXTURES = PROJECT_ROOT / "tests" / "fixtures"
ROOT_FIELD = "__sourceRegistry"

CADENCE_KINDS = (
    "period_end_monthly", "period_end_quarterly", "period_end_semiannual", "period_end_annual",
    "effective_annual", "fixed_month_day", "on_republication", "closed_record",
)
PERIOD_END_MONTHS = {"period_end_monthly": 1, "period_end_quarterly": 3, "period_end_semiannual": 6, "period_end_annual": 12}
COPY_KINDS = ("graph_root", "graph_field_max", "stated", "fixture_meta", "fixture_meta_oldest")
TRANSFORMS = ("fiscal_year_end", "month_end")
STATUS_CURRENT, STATUS_EXPECTED, STATUS_OVERDUE = "current", "newer_edition_expected", "overdue"
STATUS_RECHECK, STATUS_CLOSED, STATUS_UNKNOWN = "recheck_due", "closed_record", "copy_date_unknown"
STATUSES = (STATUS_CURRENT, STATUS_EXPECTED, STATUS_OVERDUE, STATUS_RECHECK, STATUS_CLOSED, STATUS_UNKNOWN)
FETCH_KINDS = ("api_latest_statement", "fixed_url", "refetch_each_fixture_url", "url_changes_each_period", "closed_record")
ROW_KEYS = ("id", "label", "publisher", "cadence", "copy", "fixtures", "fetch", "graphFields", "note", "perNodeDate")
ENTRY_KEYS = ("id", "label", "publisher", "cadence", "copy", "expected", "statusAtBuild", "lastReadAfterExpected", "graphFields", "fixtureCount", "fetch", "note", "perNodeDate")


# --- dates -------------------------------------------------------------------

def parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def add_months_to_period_end(day: date, months: int) -> date:
    index = day.year * 12 + (day.month - 1) + months
    return month_end(index // 12, index % 12 + 1)


def add_days(day: date, days: int) -> date:
    return date.fromordinal(day.toordinal() + int(days))


def next_fixed_month_day(after: date, month: int, day: int) -> date:
    candidate = date(after.year, month, day)
    return candidate if candidate > after else date(after.year + 1, month, day)


def transform_date(value: Any, transform: str | None) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    if transform == "fiscal_year_end":
        return date(int(text[:4]), 9, 30) if text[:4].isdigit() else None
    if transform == "month_end":
        if len(text) >= 7 and text[:4].isdigit() and text[5:7].isdigit():
            return month_end(int(text[:4]), int(text[5:7]))
        return None
    return parse_date(text)


# --- the graph ---------------------------------------------------------------

def walk(root: dict[str, Any]):
    stack = [root]
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        yield node
        stack.extend(c for c in node.get("children") or [] if isinstance(c, dict))


def dotted(value: Any, path: str) -> Any:
    cursor = value
    for part in str(path).split("."):
        if not isinstance(cursor, dict):
            return None
        cursor = cursor.get(part)
    return cursor


def where_matches(block: Any, where: list[list[Any]] | None) -> bool:
    """`where` is a list of `[path, wanted]` pairs (a list, not an object, so
    the viewer never has to enumerate an object's keys -- `js/` names every
    key it reads); the path is dotted and the wanted value is an exact string
    or `{"prefix": "..."}`."""
    if not where:
        return True
    for path, wanted in where:
        actual = dotted(block, path)
        if isinstance(wanted, dict) and "prefix" in wanted:
            if not str(actual or "").startswith(str(wanted["prefix"])):
                return False
        elif str(actual if actual is not None else "") != str(wanted):
            return False
    return True


def node_uses_source(node: dict[str, Any], graph_fields: list[Any]) -> bool:
    """Does this node carry something the source feeds? A string names a block
    field; `{"field", "where"}` scopes it; `{"costStatus": [...]}` names a
    measured cost; `{"nodeWhere": {...}}` tests node-level keys."""
    for spec in graph_fields:
        if isinstance(spec, str):
            if isinstance(node.get(spec), dict):
                return True
        elif isinstance(spec, dict):
            if "costStatus" in spec:
                if str(node.get("cost_status") or "") in spec["costStatus"]:
                    return True
            elif "nodeWhere" in spec:
                if where_matches(node, spec["nodeWhere"]):
                    return True
            elif "field" in spec:
                block = node.get(spec["field"])
                if isinstance(block, dict) and where_matches(block, spec.get("where")):
                    return True
    return False


def graph_field_max(nodes: list[dict[str, Any]], spec: dict[str, Any]) -> date | None:
    field = spec.get("field")
    path = str(spec.get("path") or "")
    where = spec.get("where")
    transform = spec.get("transform")
    best: date | None = None
    for node in nodes:
        holder = node if field in (None, "") else node.get(field)
        if not isinstance(holder, dict) or not where_matches(holder, where):
            continue
        found = transform_date(dotted(holder, path), transform)
        if found and (best is None or found > best):
            best = found
    return best


def graph_check_holds(nodes: list[dict[str, Any]], check: dict[str, Any] | None) -> bool | None:
    """A stated copy date is tied to the graph: some node's block must carry the
    stated value. None when the row makes no check."""
    if not check:
        return None
    field = check.get("field")
    for node in nodes:
        holder = node if field in (None, "") else node.get(field)
        if isinstance(holder, dict) and str(dotted(holder, str(check.get("path") or "")) or "") == str(check.get("equals")):
            return True
    return False


# --- fixtures ----------------------------------------------------------------

def fixture_metas(fixtures: list[str], fixtures_root: Path = FIXTURES) -> list[dict[str, Any]]:
    """Every `.meta.json` under the row's fixture paths that records a served
    copy (a digest). A refusal record is not a copy."""
    out: list[dict[str, Any]] = []
    for rel in fixtures:
        target = fixtures_root / rel
        if target.is_dir():
            paths = sorted(target.rglob("*.meta.json"))
        elif target.is_file():
            meta = target if target.name.endswith(".meta.json") else target.with_name(target.name + ".meta.json")
            paths = [meta] if meta.is_file() else []
        else:
            paths = []
        for path in paths:
            try:
                meta = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(meta, dict) or not meta.get("sha256"):
                continue
            out.append({
                "path": str(path.relative_to(fixtures_root)),
                "fetchedAt": str(meta.get("fetched_at") or ""),
                "url": str(meta.get("url") or ""),
                "sha256": str(meta.get("sha256") or ""),
            })
    return out


def fixture_present(fixtures: list[str], fixtures_root: Path = FIXTURES) -> bool:
    return any((fixtures_root / rel).exists() for rel in fixtures)


# --- the derivation ----------------------------------------------------------

def copy_of(row: dict[str, Any], graph: dict[str, Any], nodes: list[dict[str, Any]], metas: list[dict[str, Any]]) -> dict[str, Any]:
    spec = row.get("copy") or {}
    kind = str(spec.get("kind") or "")
    out: dict[str, Any] = {"kind": kind, "date": None, "meaning": str(spec.get("meaning") or ""), "basis": str(spec.get("basis") or "")}
    if spec.get("edition"):
        out["edition"] = str(spec["edition"])
    found: date | None = None
    if kind == "graph_root":
        found = transform_date(dotted(graph, str(spec.get("path") or "")), spec.get("transform"))
    elif kind == "graph_field_max":
        found = graph_field_max(nodes, spec)
    elif kind == "stated":
        found = parse_date(spec.get("date"))
        holds = graph_check_holds(nodes, spec.get("graphCheck"))
        out["graphCheck"] = "holds" if holds else ("not_made" if holds is None else "fails")
    elif kind in ("fixture_meta", "fixture_meta_oldest"):
        dates = [parse_date(m["fetchedAt"]) for m in metas if m.get("fetchedAt")]
        dates = [d for d in dates if d]
        if dates:
            found = min(dates) if kind == "fixture_meta_oldest" else max(dates)
    out["date"] = found.isoformat() if found else None
    fetched = [m["fetchedAt"] for m in metas if m.get("fetchedAt")]
    out["fetchedAt"] = max(fetched)[:10] if fetched else None
    return out


def expected_of(cadence: dict[str, Any], copy_date: date | None, fetched: date | None) -> dict[str, Any]:
    kind = str(cadence.get("kind") or "")
    out: dict[str, Any] = {"next": None, "expectedBy": None, "overdueAfter": None, "recheckDue": None}
    if kind == "closed_record":
        return out
    if kind == "on_republication":
        # The copy's own date where one is read off the graph (the oldest Code
        # section, the directory's checkedAt, the newest page read); the fetch
        # record otherwise, where the two are the same date.
        base = copy_date or fetched
        if base is not None:
            out["recheckDue"] = add_days(base, int(cadence.get("recheckDays") or 0)).isoformat()
        return out
    if copy_date is None:
        return out
    if kind in PERIOD_END_MONTHS:
        nxt = add_months_to_period_end(copy_date, PERIOD_END_MONTHS[kind])
    elif kind == "effective_annual":
        nxt = date(copy_date.year + 1, copy_date.month, min(copy_date.day, calendar.monthrange(copy_date.year + 1, copy_date.month)[1]))
    elif kind == "fixed_month_day":
        nxt = next_fixed_month_day(copy_date, int(cadence["month"]), int(cadence["day"]))
    else:
        return out
    expected_by = add_days(nxt, int(cadence.get("lagDays") or 0))
    out["next"] = nxt.isoformat()
    out["expectedBy"] = expected_by.isoformat()
    out["overdueAfter"] = add_days(expected_by, int(cadence.get("overdueMarginDays") or 0)).isoformat()
    return out


def status_at(as_of: date, cadence_kind: str, copy_date: date | None, expected: dict[str, Any]) -> str:
    if cadence_kind == "closed_record":
        return STATUS_CLOSED
    if cadence_kind == "on_republication":
        due = parse_date(expected.get("recheckDue"))
        if due is None:
            return STATUS_UNKNOWN
        return STATUS_RECHECK if as_of > due else STATUS_CURRENT
    if copy_date is None or not expected.get("expectedBy"):
        return STATUS_UNKNOWN
    if as_of <= parse_date(expected["expectedBy"]):
        return STATUS_CURRENT
    if as_of <= parse_date(expected["overdueAfter"]):
        return STATUS_EXPECTED
    return STATUS_OVERDUE


def cadence_text(cadence: dict[str, Any]) -> str:
    kind = str(cadence.get("kind") or "")
    words = {
        "period_end_monthly": "monthly", "period_end_quarterly": "quarterly", "period_end_semiannual": "twice a year",
        "period_end_annual": "yearly, after the period ends", "effective_annual": "yearly, effective each January",
        "fixed_month_day": "yearly, by a fixed date", "on_republication": "no fixed cycle; re-checked",
        "closed_record": "a closed record; nothing newer is expected",
    }
    text = words.get(kind, kind)
    if kind == "fixed_month_day":
        text = f"yearly, by {calendar.month_name[int(cadence['month'])]} {int(cadence['day'])}"
    if kind == "on_republication":
        text = f"no fixed cycle; re-checked every {int(cadence.get('recheckDays') or 0)} days"
    elif kind != "closed_record":
        text += f"; published about {int(cadence.get('lagDays') or 0)} days after the period, overdue {int(cadence.get('overdueMarginDays') or 0)} days after that"
    return text


def build_entry(row: dict[str, Any], graph: dict[str, Any], nodes: list[dict[str, Any]], as_of: date, fixtures_root: Path = FIXTURES) -> dict[str, Any]:
    metas = fixture_metas(list(row.get("fixtures") or []), fixtures_root)
    copy = copy_of(row, graph, nodes, metas)
    cadence = dict(row.get("cadence") or {})
    copy_date = parse_date(copy.get("date"))
    fetched = parse_date(copy.get("fetchedAt"))
    expected = expected_of(cadence, copy_date, fetched)
    status = status_at(as_of, str(cadence.get("kind") or ""), copy_date, expected)
    expected_by = parse_date(expected.get("expectedBy"))
    fetch = dict(row.get("fetch") or {})
    return {
        "id": str(row.get("id") or ""),
        "label": str(row.get("label") or ""),
        "publisher": str(row.get("publisher") or ""),
        "cadence": {**cadence, "text": cadence_text(cadence)},
        "copy": copy,
        "expected": expected,
        "statusAtBuild": status,
        # The copy was last read AFTER its successor was expected: whatever the
        # publisher showed then, this is the copy that read yielded.
        "lastReadAfterExpected": (fetched > expected_by) if (fetched and expected_by) else None,
        "graphFields": list(row.get("graphFields") or []),
        "fixtureCount": len(metas),
        "fetch": {"kind": str(fetch.get("kind") or ""), "url": str(fetch.get("url") or "")},
        "note": str(row.get("note") or ""),
        # A node-level date the panel uses instead of the registry's copy date
        # (a page's own lastVerified), for a source read node by node.
        "perNodeDate": str(row.get("perNodeDate") or "") or None,
    }


def validate_row(row: dict[str, Any], fixtures_root: Path = FIXTURES) -> list[str]:
    problems = []
    for key in ("id", "label", "publisher", "cadence", "copy", "fixtures", "fetch", "graphFields"):
        if key not in row:
            problems.append(f"missing {key}")
    if set(row) - set(ROW_KEYS):
        problems.append(f"unknown keys {sorted(set(row) - set(ROW_KEYS))}")
    cadence = row.get("cadence") or {}
    if str(cadence.get("kind")) not in CADENCE_KINDS:
        problems.append(f"cadence kind {cadence.get('kind')!r} not in the vocabulary")
    if not str(cadence.get("basis") or "").strip():
        problems.append("cadence has no basis")
    kind = str(cadence.get("kind") or "")
    if kind in PERIOD_END_MONTHS or kind in ("effective_annual", "fixed_month_day"):
        for key in ("lagDays", "overdueMarginDays"):
            if not isinstance(cadence.get(key), int) or cadence[key] < 0:
                problems.append(f"cadence {key} must be a non-negative integer")
    if kind == "fixed_month_day" and not (isinstance(cadence.get("month"), int) and isinstance(cadence.get("day"), int)):
        problems.append("fixed_month_day needs month and day")
    if kind == "on_republication" and not (isinstance(cadence.get("recheckDays"), int) and cadence["recheckDays"] > 0):
        problems.append("on_republication needs recheckDays")
    copy = row.get("copy") or {}
    if str(copy.get("kind")) not in COPY_KINDS:
        problems.append(f"copy kind {copy.get('kind')!r} not in the vocabulary")
    if copy.get("transform") is not None and copy.get("transform") not in TRANSFORMS:
        problems.append(f"copy transform {copy.get('transform')!r} not in the vocabulary")
    if copy.get("kind") == "stated" and not parse_date(copy.get("date")):
        problems.append("a stated copy needs an ISO date")
    if copy.get("kind") == "stated" and not str(copy.get("basis") or "").strip():
        problems.append("a stated copy needs a basis")
    if not str(copy.get("meaning") or "").strip():
        problems.append("copy has no meaning")
    fixtures = row.get("fixtures") or []
    if not isinstance(fixtures, list) or not fixtures:
        problems.append("no fixtures")
    elif not fixture_present(fixtures, fixtures_root):
        problems.append("none of the fixtures exists")
    fetch = row.get("fetch") or {}
    if str(fetch.get("kind")) not in FETCH_KINDS:
        problems.append(f"fetch kind {fetch.get('kind')!r} not in the vocabulary")
    if fetch.get("kind") in ("api_latest_statement", "fixed_url", "url_changes_each_period") and not str(fetch.get("url") or "").startswith("https://"):
        problems.append("fetch needs an https URL")
    if fetch.get("kind") != "closed_record" and not isinstance(fetch.get("contentCheck"), dict):
        problems.append("fetch needs a contentCheck")
    if not isinstance(row.get("graphFields"), list) or not row.get("graphFields"):
        problems.append("no graphFields")
    return problems


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


def derive(graph: dict[str, Any], registry: dict[str, Any], as_of: date, fixtures_root: Path = FIXTURES) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """The root block and the refused rows, from the registry and the graph."""
    nodes = list(walk(graph))
    entries, refused, unused = [], [], []
    seen: set[str] = set()
    for row in registry.get("sources") or []:
        problems = validate_row(row, fixtures_root)
        if str(row.get("id")) in seen:
            problems.append("a second row with this id")
        seen.add(str(row.get("id")))
        if problems:
            refused.append({"id": str(row.get("id") or ""), "problems": problems})
            continue
        # A source whose fields no node carries is not behind anything on this
        # graph: it is listed as unused, never as a source to be fresh about,
        # and nothing about its copy is judged (on such a graph there is no
        # block to read a copy date from).
        if not any(node_uses_source(n, list(row.get("graphFields") or [])) for n in nodes):
            unused.append(str(row.get("id") or ""))
            continue
        entry = build_entry(row, graph, nodes, as_of, fixtures_root)
        if entry["copy"].get("graphCheck") == "fails":
            refused.append({"id": entry["id"], "problems": ["the stated copy date's graphCheck fails against the graph"]})
            continue
        if entry["copy"]["date"] is None and str((row.get("cadence") or {}).get("kind")) not in ("on_republication", "closed_record"):
            refused.append({"id": entry["id"], "problems": ["no copy date could be read"]})
            continue
        entries.append(entry)
    counts = {status: sum(1 for e in entries if e["statusAtBuild"] == status) for status in STATUSES}
    block = {
        "asOf": as_of.isoformat(),
        "cadencesAre": str(registry.get("cadencesAre") or ""),
        "sources": entries,
        "unused": unused,
        "counts": counts,
    }
    return block, refused


def annotate_source_registry(graph: dict[str, Any], *, as_of: date | None = None, registry: dict[str, Any] | None = None,
                             fixtures_root: Path = FIXTURES) -> dict[str, Any]:
    """Stamp `__sourceRegistry` on the root. Runs last: it reads the final
    blocks on every node to find each source's copy date."""
    graph.pop(ROOT_FIELD, None)
    registry = registry if registry is not None else load_registry()
    block, refused = derive(graph, registry, as_of or today_utc(), fixtures_root)
    graph[ROOT_FIELD] = block
    return {"sources": len(block["sources"]), "refused": refused, "counts": block["counts"], "asOf": block["asOf"]}
