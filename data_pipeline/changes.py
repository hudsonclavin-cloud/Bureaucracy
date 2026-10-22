"""What changed between two builds, the change budget, and the review queue.

`docs/DEFINITION_OF_DONE.md`:

- Part 2, "Change history": a reader can see what changed since the last
  update -- figures that moved, nodes added or replaced, claims withdrawn, and
  why.
- Criterion 5, step 5: a change budget runs before publishing; a change beyond
  the budget is held, not published. The budget starts as: the node count
  drops; a measured cost moves by more than its source's month-on-month change
  would explain; more than 5% of pay claims are withdrawn; the anchor's period
  goes backwards.
- Criterion 7: when a source contradicts the graph the job withdraws the claim
  that no longer holds, keeps the old record, and adds the change to a review
  list; it never settles a disagreement by itself. The queue is one entry per
  held change, with both documents and what each says, and the only thing a
  person is asked to look at between cycles.

`diff_graphs(before, after)` compares the published graph as it was (the
committed copy) with the graph just built, node by node, and returns one
history ENTRY: the anchor before and after, nodes added, removed and newly
replaced, every measured cost that moved, the largest estimate moves, pay
claims added and withdrawn by field, verification and placement methods added
and withdrawn, sourced figures added, withdrawn and moved, the source
registry's copy dates before and after, and the budget's verdict rule by rule.
Everything in it is read off the two graphs; nothing is asserted.

`review_queue(entry, after, previous_queue)` turns the entry and the graph's
own published disagreements into the queue: one record per held change or
open disagreement, keyed so a run re-finding the same condition keeps the
record's opening date, and a record whose condition no longer holds is closed
with the date rather than deleted. Kinds:

- `budget_hold`: a budget rule tripped; the cycle must not publish.
- `node_removed`, `claim_withdrawn`, `method_withdrawn`,
  `sourced_figure_withdrawn`: something the last graph published that this
  one does not, with the document the old claim rested on.
- `measured_cost_moved_with_new_statement`: a measured line that moved by more
  than the review threshold between statements -- the statement explains it,
  and a person should still see it.
- `placement_directory_disagreement`, `cost_weight_dispute`,
  `verification_failure`: disagreements the graph already publishes and never
  resolves (two documents, what each says).
- `source_overdue`: a registry source past its margin.

Nothing here fetches, and nothing here changes a graph.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = PROJECT_ROOT / "output" / "change_history.json"
QUEUE_PATH = PROJECT_ROOT / "data" / "audit" / "review_queue.json"

PAY_FIELDS = (
    "positionStatutoryPay", "positionSchedulePay", "positionPayRate", "positionGradePay", "positionCurrentPay",
    "positionReportedPay", "positionDerivedPay", "positionTierPay", "positionTierReferencePay", "positionMilitaryPay",
)
#: Each pay field's own figure key: a rate's `amount`, a range's bounds.
PAY_FIGURE_KEYS = {field: ("amount",) for field in PAY_FIELDS}
PAY_FIGURE_KEYS["positionGradePay"] = ("minimum", "maximum")
PAY_FIGURE_KEYS["positionTierPay"] = ("minimum", "maximum")
#: Sourced figures of another kind, with the key the figure sits under.
SOURCED_FIGURE_FIELDS = {
    "usaspendingOutlays": "amount",
    "ombBudget": "outlays",
    "auditedNetCost": "netCostUsd",
    "committeeDisbursements": "amount",
    "combinedStatementOutlays": "amount",
    "spendingByKind": "totalObligations",
    "payrollOfficial": "totalAnnualPay",
}
EVIDENCE_METHOD_FIELDS = ("verificationMethod", "placementMethod")
MEASURED = ("official", "root_total")
#: The budget's starting thresholds (criterion 5: "to be tuned on the first cycles").
PAY_WITHDRAWAL_LIMIT = 0.05
#: A measured line that moved by more than this between statements is queued
#: for review (not held): the new statement explains it, and a person sees it.
MEASURED_REVIEW_MOVE = 0.5
MEASURED_REVIEW_FLOOR = 1_000_000_000.0
RULE_NODE_COUNT = "node_count_drops"
RULE_MEASURED_SAME_STATEMENT = "measured_cost_moved_without_a_new_statement"
RULE_PAY_WITHDRAWN = "pay_claims_withdrawn_above_5_percent"
RULE_ANCHOR_BACKWARDS = "anchor_period_goes_backwards"
RULE_ANCHOR_LOST = "anchor_lost"
BUDGET_RULES = (RULE_NODE_COUNT, RULE_MEASURED_SAME_STATEMENT, RULE_PAY_WITHDRAWN, RULE_ANCHOR_BACKWARDS, RULE_ANCHOR_LOST)

QUEUE_KINDS = (
    "budget_hold", "node_removed", "claim_withdrawn", "method_withdrawn", "sourced_figure_withdrawn",
    "measured_cost_moved_with_new_statement", "placement_directory_disagreement", "cost_weight_dispute",
    "verification_failure", "source_overdue",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def walk(root: dict[str, Any]):
    stack = [(root, None)]
    while stack:
        node, parent = stack.pop()
        if not isinstance(node, dict):
            continue
        yield node, parent
        for child in node.get("children") or []:
            if isinstance(child, dict):
                stack.append((child, node))


def index(root: dict[str, Any]) -> dict[str, tuple[dict[str, Any], str | None]]:
    out: dict[str, tuple[dict[str, Any], str | None]] = {}
    for node, parent in walk(root):
        node_id = str(node.get("id") or "")
        if node_id and node_id not in out:
            out[node_id] = (node, str(parent.get("id")) if parent else None)
    return out


def _amount(node: dict[str, Any]) -> float | None:
    value = node.get("resolved_total_amount")
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _is_post(node: dict[str, Any]) -> bool:
    return any(w in str(node.get("type") or "").casefold() for w in ("position", "role", "office holder"))


def _brief(node: dict[str, Any], parent_id: str | None = None) -> dict[str, Any]:
    out = {"id": str(node.get("id") or ""), "name": str(node.get("name") or ""), "type": str(node.get("type") or "")}
    if parent_id:
        out["parentId"] = parent_id
    return out


def _pct(before: float, after: float) -> float | None:
    if before == 0:
        return None
    return round((after - before) / abs(before) * 100.0, 2)


def _pay_figure(block: dict[str, Any], field: str) -> list[float]:
    out = []
    for key in PAY_FIGURE_KEYS[field]:
        try:
            out.append(round(float(block.get(key)), 2))
        except (TypeError, ValueError):
            out.append(None)
    return out


def _document_of(block: dict[str, Any]) -> str | None:
    """The URL a block rests on, for a withdrawal record."""
    for key in ("url", "sourceUrl", "statuteUrl", "tableUrl"):
        if isinstance(block.get(key), str) and block[key]:
            return block[key]
    docs = block.get("documents")
    if isinstance(docs, list):
        for d in docs:
            if isinstance(d, dict) and d.get("url"):
                return str(d["url"])
    doc = block.get("document")
    if isinstance(doc, dict) and doc.get("url"):
        return str(doc["url"])
    return None


def anchor_of(root: dict[str, Any]) -> dict[str, Any]:
    summary = root.get("__budgetSummary") if isinstance(root.get("__budgetSummary"), dict) else {}
    return {
        "recordDate": str(summary.get("record_date") or "")[:10] or None,
        "total": summary.get("government_total_outlay_amount"),
        "statementFile": summary.get("statement_file"),
    }


def registry_copies(root: dict[str, Any]) -> dict[str, dict[str, Any]]:
    block = root.get("__sourceRegistry") if isinstance(root.get("__sourceRegistry"), dict) else {}
    out = {}
    for entry in block.get("sources") or []:
        if isinstance(entry, dict):
            out[str(entry.get("id"))] = {"copyDate": (entry.get("copy") or {}).get("date"), "status": entry.get("statusAtBuild")}
    return out


def diff_graphs(before: dict[str, Any], after: dict[str, Any], *, built_at: str | None = None) -> dict[str, Any]:
    """One change-history entry: everything that differs between the two
    graphs that a reader or the budget cares about, read off the nodes."""
    b, a = index(before), index(after)
    anchor_b, anchor_a = anchor_of(before), anchor_of(after)
    same_statement = bool(anchor_b["recordDate"]) and anchor_b["recordDate"] == anchor_a["recordDate"]

    added = [_brief(a[i][0], a[i][1]) for i in a if i not in b]
    removed = [_brief(b[i][0], b[i][1]) for i in b if i not in a]
    newly_superseded = [
        _brief(a[i][0], a[i][1]) | {"supersededOn": a[i][0].get("supersededOn"), "supersededBy": a[i][0].get("supersededBy")}
        for i in a if i in b and str(a[i][0].get("lifecycle") or "") == "superseded" and str(b[i][0].get("lifecycle") or "") != "superseded"
    ]
    renamed = [{"id": i, "before": str(b[i][0].get("name")), "after": str(a[i][0].get("name"))} for i in a if i in b and str(a[i][0].get("name")) != str(b[i][0].get("name"))]
    reparented = [{"id": i, "name": str(a[i][0].get("name")), "before": b[i][1], "after": a[i][1]} for i in a if i in b and a[i][1] != b[i][1]]

    measured_moved, measured_gained, measured_lost, estimate_moves = [], [], [], []
    for i, (node_a, _) in a.items():
        status_a = str(node_a.get("cost_status") or "")
        node_b = b[i][0] if i in b else None
        status_b = str(node_b.get("cost_status") or "") if node_b else ""
        amount_a, amount_b = _amount(node_a), (_amount(node_b) if node_b else None)
        if status_a in MEASURED and status_b in MEASURED and amount_a is not None and amount_b is not None and round(amount_a, 2) != round(amount_b, 2):
            measured_moved.append({"id": i, "name": str(node_a.get("name")), "before": round(amount_b, 2), "after": round(amount_a, 2),
                                   "change": round(amount_a - amount_b, 2), "percent": _pct(amount_b, amount_a)})
        elif status_a in MEASURED and node_b is not None and status_b not in MEASURED:
            measured_gained.append({"id": i, "name": str(node_a.get("name")), "after": round(amount_a, 2) if amount_a is not None else None, "before_status": status_b})
        elif status_a not in MEASURED and status_b in MEASURED:
            measured_lost.append({"id": i, "name": str(node_a.get("name")), "before": round(amount_b, 2) if amount_b is not None else None, "after_status": status_a})
        elif status_a == "allocated" and status_b == "allocated" and amount_a is not None and amount_b is not None and abs(amount_a - amount_b) > 0.005:
            estimate_moves.append({"id": i, "name": str(node_a.get("name")), "before": round(amount_b, 2), "after": round(amount_a, 2), "percent": _pct(amount_b, amount_a)})
    for i, (node_b, _) in b.items():
        if i not in a and str(node_b.get("cost_status") or "") in MEASURED:
            measured_lost.append({"id": i, "name": str(node_b.get("name")), "before": _amount(node_b), "after_status": "node removed"})
    estimate_moves.sort(key=lambda m: -abs(m["after"] - m["before"]))

    pay_added, pay_withdrawn, pay_moved = [], [], []
    claims_before = sum(1 for i in b if _is_post(b[i][0]) and any(isinstance(b[i][0].get(f), dict) for f in PAY_FIELDS))
    claims_after = sum(1 for i in a if _is_post(a[i][0]) and any(isinstance(a[i][0].get(f), dict) for f in PAY_FIELDS))
    for i in set(a) | set(b):
        node_a = a[i][0] if i in a else {}
        node_b = b[i][0] if i in b else {}
        for field in PAY_FIELDS:
            block_a, block_b = node_a.get(field), node_b.get(field)
            if isinstance(block_a, dict) and not isinstance(block_b, dict):
                pay_added.append({"id": i, "name": str(node_a.get("name")), "field": field, "figure": _pay_figure(block_a, field), "document": _document_of(block_a)})
            elif isinstance(block_b, dict) and not isinstance(block_a, dict):
                pay_withdrawn.append({"id": i, "name": str(node_b.get("name")), "field": field, "figure": _pay_figure(block_b, field), "document": _document_of(block_b),
                                      "why": "node removed" if i not in a else ("the node now stands for several posts" if node_a.get("representsPosts") and not node_b.get("representsPosts") else "the record no longer applies to this node")})
            elif isinstance(block_a, dict) and isinstance(block_b, dict) and _pay_figure(block_a, field) != _pay_figure(block_b, field):
                pay_moved.append({"id": i, "name": str(node_a.get("name")), "field": field, "before": _pay_figure(block_b, field), "after": _pay_figure(block_a, field), "document": _document_of(block_a)})

    methods_added, methods_withdrawn, methods_changed = [], [], []
    for i in set(a) | set(b):
        node_a = a[i][0] if i in a else {}
        node_b = b[i][0] if i in b else {}
        for field in EVIDENCE_METHOD_FIELDS:
            m_a, m_b = node_a.get(field), node_b.get(field)
            if m_a and not m_b:
                methods_added.append({"id": i, "name": str(node_a.get("name")), "field": field, "method": str(m_a), "url": node_a.get("verificationSiteFrom") or node_a.get("placementUrl") or (node_a.get("sourceUrls") or [None])[0]})
            elif m_b and not m_a:
                methods_withdrawn.append({"id": i, "name": str(node_b.get("name")), "field": field, "method": str(m_b), "url": node_b.get("verificationSiteFrom") or node_b.get("placementUrl") or (node_b.get("sourceUrls") or [None])[0],
                                          "why": "node removed" if i not in a else ("renamed, so the record no longer names it" if str(node_a.get("name")) != str(node_b.get("name")) else "the record was withdrawn or no longer applies")})
            elif m_a and m_b and str(m_a) != str(m_b):
                methods_changed.append({"id": i, "name": str(node_a.get("name")), "field": field, "before": str(m_b), "after": str(m_a)})

    sourced: dict[str, dict[str, list]] = {}
    for field, key in SOURCED_FIGURE_FIELDS.items():
        added_f, withdrawn_f, moved_f = [], [], []
        for i in set(a) | set(b):
            node_a = a[i][0] if i in a else {}
            node_b = b[i][0] if i in b else {}
            block_a, block_b = node_a.get(field), node_b.get(field)
            if isinstance(block_a, dict) and not isinstance(block_b, dict):
                added_f.append({"id": i, "name": str(node_a.get("name")), "figure": block_a.get(key), "document": _document_of(block_a)})
            elif isinstance(block_b, dict) and not isinstance(block_a, dict):
                withdrawn_f.append({"id": i, "name": str(node_b.get("name")), "figure": block_b.get(key), "document": _document_of(block_b), "why": "node removed" if i not in a else "the record was withdrawn or no longer applies"})
            elif isinstance(block_a, dict) and isinstance(block_b, dict) and block_a.get(key) != block_b.get(key):
                moved_f.append({"id": i, "name": str(node_a.get("name")), "before": block_b.get(key), "after": block_a.get(key)})
        if added_f or withdrawn_f or moved_f:
            sourced[field] = {"added": added_f, "withdrawn": withdrawn_f, "moved": moved_f}

    reg_b, reg_a = registry_copies(before), registry_copies(after)
    sources_changed = [{"id": s, "before": reg_b.get(s, {}).get("copyDate"), "after": reg_a[s]["copyDate"], "status": reg_a[s]["status"]}
                       for s in reg_a if reg_b.get(s, {}).get("copyDate") != reg_a[s]["copyDate"]]

    rules = []
    rules.append({"rule": RULE_NODE_COUNT, "tripped": len(a) < len(b), "detail": f"{len(b):,} nodes before, {len(a):,} after; {len(removed)} removed"})
    rules.append({"rule": RULE_ANCHOR_LOST, "tripped": not anchor_a["recordDate"], "detail": f"anchor record date after: {anchor_a['recordDate']}"})
    rules.append({"rule": RULE_ANCHOR_BACKWARDS, "tripped": bool(anchor_a["recordDate"] and anchor_b["recordDate"] and anchor_a["recordDate"] < anchor_b["recordDate"]),
                  "detail": f"anchor {anchor_b['recordDate']} -> {anchor_a['recordDate']}"})
    rules.append({"rule": RULE_MEASURED_SAME_STATEMENT, "tripped": same_statement and bool(measured_moved),
                  "detail": (f"the statement is unchanged ({anchor_a['recordDate']}) and {len(measured_moved)} measured costs moved" if same_statement
                             else f"a new statement ({anchor_b['recordDate']} -> {anchor_a['recordDate']}): {len(measured_moved)} measured costs moved, which the statement explains")})
    withdrawn_share = (len(pay_withdrawn) / claims_before) if claims_before else 0.0
    rules.append({"rule": RULE_PAY_WITHDRAWN, "tripped": withdrawn_share > PAY_WITHDRAWAL_LIMIT,
                  "detail": f"{len(pay_withdrawn)} of {claims_before:,} pay claims withdrawn ({withdrawn_share:.1%}; the limit is {PAY_WITHDRAWAL_LIMIT:.0%})"})
    held = any(r["tripped"] for r in rules)
    review_moves = [m for m in measured_moved if not same_statement and m["percent"] is not None and abs(m["percent"]) > MEASURED_REVIEW_MOVE * 100 and max(abs(m["before"]), abs(m["after"])) >= MEASURED_REVIEW_FLOOR]

    entry = {
        "builtAt": built_at or now_iso(),
        "anchor": {"before": anchor_b, "after": anchor_a, "sameStatement": same_statement},
        "nodes": {"before": len(b), "after": len(a), "added": sorted(added, key=lambda x: x["id"]), "removed": sorted(removed, key=lambda x: x["id"]),
                  "newlySuperseded": sorted(newly_superseded, key=lambda x: x["id"]), "renamed": sorted(renamed, key=lambda x: x["id"]), "reparented": sorted(reparented, key=lambda x: x["id"])},
        "measuredCosts": {"before": sum(1 for i in b if str(b[i][0].get("cost_status") or "") in MEASURED), "after": sum(1 for i in a if str(a[i][0].get("cost_status") or "") in MEASURED),
                          "moved": sorted(measured_moved, key=lambda m: -abs(m["change"])), "gained": sorted(measured_gained, key=lambda x: x["id"]), "lost": sorted(measured_lost, key=lambda x: x["id"]),
                          "forReview": review_moves},
        "estimates": {"moved": len(estimate_moves), "largestMoves": estimate_moves[:20]},
        "pay": {"claimsBefore": claims_before, "claimsAfter": claims_after, "added": sorted(pay_added, key=lambda x: (x["id"], x["field"])),
                "withdrawn": sorted(pay_withdrawn, key=lambda x: (x["id"], x["field"])), "moved": sorted(pay_moved, key=lambda x: (x["id"], x["field"]))},
        "evidence": {"added": sorted(methods_added, key=lambda x: (x["id"], x["field"])), "withdrawn": sorted(methods_withdrawn, key=lambda x: (x["id"], x["field"])),
                     "changed": sorted(methods_changed, key=lambda x: (x["id"], x["field"]))},
        "sourcedFigures": sourced,
        "sources": {"changed": sorted(sources_changed, key=lambda x: x["id"]), "registryAfter": reg_a},
        "budget": {"rules": rules, "held": held, "thresholds": {"payWithdrawalLimit": PAY_WITHDRAWAL_LIMIT, "measuredReviewMove": MEASURED_REVIEW_MOVE, "measuredReviewFloor": MEASURED_REVIEW_FLOOR}},
    }
    entry["touched"] = sorted({
        *(x["id"] for x in added), *(x["id"] for x in newly_superseded), *(x["id"] for x in renamed), *(x["id"] for x in reparented),
        *(x["id"] for x in measured_moved), *(x["id"] for x in measured_gained), *(x["id"] for x in measured_lost),
        *(x["id"] for x in pay_added), *(x["id"] for x in pay_withdrawn), *(x["id"] for x in pay_moved),
        *(x["id"] for x in methods_added), *(x["id"] for x in methods_withdrawn), *(x["id"] for x in methods_changed),
        *(x["id"] for f in sourced.values() for k in ("added", "withdrawn", "moved") for x in f[k]),
    })
    entry["summary"] = summarise(entry)
    return entry


def summarise(entry: dict[str, Any]) -> str:
    n, m, p, e = entry["nodes"], entry["measuredCosts"], entry["pay"], entry["evidence"]
    anchor = entry["anchor"]
    parts = []
    if anchor["before"]["recordDate"] != anchor["after"]["recordDate"]:
        parts.append(f"the Treasury anchor moved from the statement of {anchor['before']['recordDate']} to {anchor['after']['recordDate']}")
    else:
        parts.append(f"the Treasury anchor is still the statement of {anchor['after']['recordDate']}")
    parts.append(f"{n['before']:,} nodes before and {n['after']:,} after ({len(n['added'])} added, {len(n['removed'])} removed, {len(n['newlySuperseded'])} newly marked replaced, {len(n['renamed'])} renamed)")
    parts.append(f"{len(m['moved'])} measured costs moved, {len(m['gained'])} gained a measured figure, {len(m['lost'])} lost one; {entry['estimates']['moved']:,} estimates moved")
    parts.append(f"pay claims {p['claimsBefore']:,} -> {p['claimsAfter']:,} ({len(p['added'])} added, {len(p['withdrawn'])} withdrawn, {len(p['moved'])} changed figure)")
    parts.append(f"verification or placement methods: {len(e['added'])} added, {len(e['withdrawn'])} withdrawn, {len(e['changed'])} changed")
    held = [r["rule"] for r in entry["budget"]["rules"] if r["tripped"]]
    parts.append("HELD by the change budget: " + ", ".join(held) if held else "within the change budget")
    return "; ".join(parts) + "."


# --- the review queue ----------------------------------------------------------

def _key(kind: str, *parts: Any) -> str:
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:12]
    return f"{kind}:{digest}"


def _record(kind: str, key: str, node: dict[str, Any] | None, detail: str, documents: list[dict[str, Any]], opened: str) -> dict[str, Any]:
    return {
        "key": key, "kind": kind, "status": "open", "opened": opened, "closed": None,
        "nodeId": str(node.get("id")) if node else None, "nodeName": str(node.get("name")) if node else None,
        "detail": detail,
        # Both documents and what each says, where there are two; one where
        # the change is a withdrawal of one record.
        "documents": documents,
    }


def queue_records_from_entry(entry: dict[str, Any], opened: str) -> list[dict[str, Any]]:
    out = []
    for rule in entry["budget"]["rules"]:
        if rule["tripped"]:
            out.append(_record("budget_hold", _key("budget_hold", rule["rule"], entry["builtAt"]), None,
                               f"change budget rule {rule['rule']} tripped: {rule['detail']}; this build must not publish until a person has looked",
                               [{"role": "the build", "says": rule["detail"]}], opened))
    for node in entry["nodes"]["removed"]:
        out.append(_record("node_removed", _key("node_removed", node["id"]), node, "a node the last published graph carried is not in this build",
                           [{"role": "the previous graph", "says": f"carried {node['name']} ({node['type']}) under {node.get('parentId')}"}, {"role": "this build", "says": "does not carry it"}], opened))
    for item in entry["pay"]["withdrawn"]:
        out.append(_record("claim_withdrawn", _key("claim_withdrawn", item["id"], item["field"]), {"id": item["id"], "name": item["name"]},
                           f"pay claim {item['field']} withdrawn: {item['why']}",
                           [{"role": "the previous record", "url": item.get("document"), "says": f"{item['field']} {item['figure']}"}, {"role": "this build", "says": item["why"]}], opened))
    for item in entry["evidence"]["withdrawn"]:
        out.append(_record("method_withdrawn", _key("method_withdrawn", item["id"], item["field"]), {"id": item["id"], "name": item["name"]},
                           f"{item['field']} {item['method']} withdrawn: {item['why']}",
                           [{"role": "the previous record", "url": item.get("url"), "says": item["method"]}, {"role": "this build", "says": item["why"]}], opened))
    for field, changes in entry["sourcedFigures"].items():
        for item in changes["withdrawn"]:
            out.append(_record("sourced_figure_withdrawn", _key("sourced_figure_withdrawn", item["id"], field), {"id": item["id"], "name": item["name"]},
                               f"{field} withdrawn: {item['why']}",
                               [{"role": "the previous record", "url": item.get("document"), "says": f"{field} {item['figure']}"}, {"role": "this build", "says": item["why"]}], opened))
    for item in entry["measuredCosts"]["forReview"]:
        out.append(_record("measured_cost_moved_with_new_statement", _key("measured_moved", item["id"], entry["anchor"]["after"]["recordDate"]), {"id": item["id"], "name": item["name"]},
                           f"measured cost moved {item['percent']}% between the statements of {entry['anchor']['before']['recordDate']} and {entry['anchor']['after']['recordDate']}",
                           [{"role": f"the statement of {entry['anchor']['before']['recordDate']}", "says": f"${item['before']:,.2f}"},
                            {"role": f"the statement of {entry['anchor']['after']['recordDate']}", "says": f"${item['after']:,.2f}"}], opened))
    return out


def queue_records_from_graph(after: dict[str, Any], opened: str) -> list[dict[str, Any]]:
    """The disagreements the graph publishes and never resolves, as queue
    records: both documents and what each says, off the node's own blocks."""
    out = []
    for node, parent in walk(after):
        disagreement = node.get("placementDirectoryDisagreement")
        if isinstance(disagreement, dict):
            out.append(_record("placement_directory_disagreement", _key("placement_directory_disagreement", node.get("id"), disagreement.get("source")), node,
                               f"{disagreement.get('source')} files this unit under \"{disagreement.get('listedUnder')}\"; this graph draws it under \"{(parent or {}).get('name')}\"",
                               [{"role": str(disagreement.get("source")), "url": disagreement.get("url"), "says": f"listed under {disagreement.get('listedUnder')} ({disagreement.get('directoryParentId')})"},
                                {"role": "this graph (curated)", "says": f"drawn under {(parent or {}).get('name')} ({(parent or {}).get('id')})"}], opened))
        dispute = node.get("cost_weight_dispute")
        if isinstance(dispute, dict):
            out.append(_record("cost_weight_dispute", _key("cost_weight_dispute", node.get("id"), dispute.get("period")), node,
                               f"the curated headcount {dispute.get('curatedEmployees')} and OPM's {dispute.get('officialEmployees')} ({dispute.get('period')}) differ by more than 10%; the estimate was divided by the curated figure and not recomputed",
                               [{"role": "the curated file", "says": f"employees {dispute.get('curatedEmployees')}"},
                                {"role": "OPM FedScope " + str(dispute.get("period")), "url": dispute.get("url"), "says": f"employees {dispute.get('officialEmployees')}"}], opened))
        failure = node.get("verificationFailure")
        if failure and not node.get("verificationMethod"):
            source = node.get("verificationFailureSource") if isinstance(node.get("verificationFailureSource"), dict) else {}
            out.append(_record("verification_failure", _key("verification_failure", node.get("id"), failure), node,
                               f"a document was read and does not carry this node's name ({failure}); a name question or a curation decision",
                               [{"role": str(source.get("source") or "the document read"), "url": source.get("url") or (node.get("sourceUrls") or [None])[0], "says": "does not carry the name " + str(node.get("name"))},
                                {"role": "this graph (curated)", "says": f"names it {node.get('name')}"}], opened))
    registry = after.get("__sourceRegistry") if isinstance(after.get("__sourceRegistry"), dict) else {}
    for entry in registry.get("sources") or []:
        if isinstance(entry, dict) and entry.get("statusAtBuild") == "overdue":
            out.append(_record("source_overdue", _key("source_overdue", entry.get("id"), (entry.get("expected") or {}).get("next")), None,
                               f"{entry.get('label')}: the edition for {(entry.get('expected') or {}).get('next')} was expected by {(entry.get('expected') or {}).get('expectedBy')}; the copy in use is dated {(entry.get('copy') or {}).get('date')}",
                               [{"role": "the registry", "says": f"expected by {(entry.get('expected') or {}).get('expectedBy')}, overdue after {(entry.get('expected') or {}).get('overdueAfter')}"},
                                {"role": "the copy in use", "url": (entry.get('fetch') or {}).get('url'), "says": f"dated {(entry.get('copy') or {}).get('date')}, read {(entry.get('copy') or {}).get('fetchedAt')}"}], opened))
    return out


def merge_queue(previous: list[dict[str, Any]], current: list[dict[str, Any]], today: str) -> list[dict[str, Any]]:
    """Keep every record ever opened: a re-found condition keeps its opening
    date and any resolution a person recorded; a condition no longer found is
    closed with today's date, never deleted; a new one is opened today."""
    by_key = {str(r.get("key")): dict(r) for r in previous if isinstance(r, dict) and r.get("key")}
    found = {r["key"] for r in current}
    out = []
    for record in current:
        old = by_key.get(record["key"])
        if old is None:
            out.append(record)
            continue
        merged = dict(record)
        merged["opened"] = old.get("opened") or record["opened"]
        if old.get("status") == "resolved":
            merged["status"] = "resolved"
            merged["resolution"] = old.get("resolution")
        else:
            merged["status"] = "open"
        merged["closed"] = None
        out.append(merged)
    for key, old in by_key.items():
        if key not in found:
            closed = dict(old)
            if closed.get("status") != "closed":
                closed["status"] = "closed"
                closed["closed"] = today
            out.append(closed)
    out.sort(key=lambda r: (r.get("status") != "open", r.get("kind"), r.get("nodeName") or "", r.get("key")))
    return out


def review_queue(entry: dict[str, Any], after: dict[str, Any], previous: list[dict[str, Any]] | None = None, today: str | None = None) -> list[dict[str, Any]]:
    today = today or now_iso()[:10]
    current = queue_records_from_entry(entry, today) + queue_records_from_graph(after, today)
    seen, unique = set(), []
    for record in current:
        if record["key"] not in seen:
            seen.add(record["key"])
            unique.append(record)
    return merge_queue(previous or [], unique, today)


def load_json(path: Path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default
