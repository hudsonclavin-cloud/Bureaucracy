"""How a measured unit's total adds up, part by part, from the statement itself.

`docs/DEFINITION_OF_DONE.md` criterion 4(b): for every unit with a measured
total the panel shows

    parent = measured children + sourced figures + named remainder

with the remainder traced to the documents that explain it and anything
untraceable labelled "not attributed", so that no remainder is silently spread
across siblings as though it were their money.

Table 5 prints each agency as a section -- a header, the lines and
sub-headers beneath it, its receipts-type lines, and a `Total--` line that is
their sum -- so the statement itself says what a unit's total is made of. This
pass reads the committed statement the graph was built from (the one the
root's `__budgetSummary.record_date` names, under `tests/fixtures/`) and, for
every measured organisation that carries a Table 5 classification id whose
header has parts, publishes `treasury_sum`:

- `parts`: the statement's direct items beneath the unit's header, in print
  order, each with the name as printed, its exact amount (a sub-header at the
  sum of its own lines, which is the statement's arithmetic), its kind
  (`line`, `header`, `receipts`), its classification id, and WHERE it landed in
  this graph: `child` (a direct child node carries the line or the
  sub-header's total), `descendant` (a deeper node does), `elsewhere` (a node
  outside this unit's subtree does -- the Tax Court, printed under the
  Legislative Branch and drawn under the judiciary), or `none` (no node
  carries it);
- `partsSum` and `notAttributed = total - partsSum`, which is zero wherever
  the statement's own arithmetic holds, and is published with its amount
  where it does not;
- `landedOnChildren`, `appliedElsewhere` and `toNoNode`, the three sums a
  reader needs: what the children account for, what is measured but drawn
  under another unit while staying inside this total, and what the statement
  prints beneath this unit that no node here carries;
- `estimatedChildren`: the direct organisation children whose figure is an
  apportioned share -- the units the cascade divides `toNoNode` (and the
  `elsewhere` money) among, by weight. Naming them beside the amount is what
  makes the spread visible rather than silent.

It writes no cost field and changes no figure. The gate re-derives every part
from the committed statement with its own reader and refuses a block whose
parts, amounts, landings or sums are not the statement's and the tree's.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from data_pipeline.exporter.treasury_sections import SectionTree, is_header_row, is_receipts_row, is_total_row, plain_label

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = PROJECT_ROOT / "tests" / "fixtures"
FIELD = "treasury_sum"
MEASURED_STATUSES = ("official",)
KIND_LINE, KIND_HEADER, KIND_RECEIPTS = "line", "header", "receipts"
WHERE_CHILD, WHERE_DESCENDANT, WHERE_ELSEWHERE, WHERE_NONE = "child", "descendant", "elsewhere", "none"
SYNTHETIC_RECEIPTS = "treasury_receipts"


def _round(value: float) -> float:
    return round(float(value) + 0.0, 2)


def statement_fixture(record_date: str | None) -> Path | None:
    if not record_date:
        return None
    path = FIXTURES / f"mts_table5_{str(record_date)[:10]}.json"
    return path if path.is_file() else None


def load_section_tree(record_date: str | None) -> SectionTree | None:
    """The committed statement the graph was built from, as the exporter's own
    section tree; None where none is committed for that date."""
    from data_pipeline.crawler.treasury_outlays import parse_outlay_rows

    path = statement_fixture(record_date)
    if path is None:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows, _summary = parse_outlay_rows(payload.get("rows") or [])
    tree = SectionTree.from_rows(rows)
    return tree if tree.complete else None


def _is_post(node: dict[str, Any]) -> bool:
    type_text = str(node.get("type") or "").casefold()
    return any(word in type_text for word in ("position", "role", "office holder"))


def _is_organisation(node: dict[str, Any]) -> bool:
    return not _is_post(node) and not node.get("synthetic") and "treasury accounting line" not in str(node.get("type") or "").casefold()


def takes_block(node: dict[str, Any]) -> bool:
    return (str(node.get("cost_status") or "") in MEASURED_STATUSES and _is_organisation(node)
            and bool(str(node.get("treasury_classification_id") or "").strip()))


def header_of(tree: SectionTree, row: dict[str, Any]) -> dict[str, Any] | None:
    if is_total_row(row):
        return tree.rows.get(str(row.get("parent_id") or ""))
    return row if is_header_row(row) else None


def build_block(node: dict[str, Any], tree: SectionTree, *, by_classification: dict[str, str], receipts_child: dict[str, str],
                parent_map: dict[str, str], node_map: dict[str, dict[str, Any]], record_date: str) -> dict[str, Any] | None:
    row = tree.rows.get(str(node.get("treasury_classification_id") or "").strip())
    if row is None:
        return None
    header = header_of(tree, row)
    if header is None:
        return None
    kids = [k for k in tree.kids(header) if not is_total_row(k)]
    if not kids:
        return None
    node_id = str(node.get("id") or "")

    def where_of(target: str | None) -> str:
        if not target:
            return WHERE_NONE
        if parent_map.get(target) == node_id:
            return WHERE_CHILD
        cursor = parent_map.get(target)
        while cursor:
            if cursor == node_id:
                return WHERE_DESCENDANT
            cursor = parent_map.get(cursor)
        return WHERE_ELSEWHERE

    parts = []
    for kid in kids:
        kid_id = str(kid.get("classification_id") or "")
        if is_receipts_row(kid):
            kind = KIND_RECEIPTS
            landed = receipts_child.get(node_id)
        elif is_header_row(kid):
            kind = KIND_HEADER
            total = tree.total_row(kid)
            landed = by_classification.get(kid_id) or (by_classification.get(str(total.get("classification_id") or "")) if total else None)
        else:
            kind = KIND_LINE
            landed = by_classification.get(kid_id)
        if landed == node_id:
            landed = None
        parts.append({
            "name": plain_label(kid),
            "amount": _round(tree.amount(kid)),
            "kind": kind,
            "classificationId": kid_id,
            "nodeId": landed,
            "nodeName": str((node_map.get(landed) or {}).get("name") or "") if landed else None,
            "where": where_of(landed),
        })
    total = _round(float(node.get("resolved_total_amount") or 0.0))
    parts_sum = _round(sum(p["amount"] for p in parts))
    estimated = [
        {"id": str(c.get("id") or ""), "name": str(c.get("name") or "")}
        for c in node.get("children") or []
        if isinstance(c, dict) and _is_organisation(c) and str(c.get("cost_status") or "") == "allocated"
    ]
    return {
        "statementDate": record_date,
        "classificationId": str(row.get("classification_id") or ""),
        "total": total,
        "parts": parts,
        "partsSum": parts_sum,
        "notAttributed": _round(total - parts_sum),
        "landedOnChildren": _round(sum(p["amount"] for p in parts if p["where"] in (WHERE_CHILD, WHERE_DESCENDANT))),
        "appliedElsewhere": _round(sum(p["amount"] for p in parts if p["where"] == WHERE_ELSEWHERE)),
        "toNoNode": _round(sum(p["amount"] for p in parts if p["where"] == WHERE_NONE)),
        "estimatedChildren": estimated,
    }


def annotate_treasury_sums(root: dict[str, Any], *, tree: SectionTree | None = None) -> dict[str, Any]:
    """Stamp `treasury_sum` on every measured organisation whose Table 5 header
    has parts. The field is cleared everywhere first; runs after the cost
    cascade, since it reads the final statuses and amounts."""
    from data_pipeline.exporter.build_graph import index_tree

    summary = root.get("__budgetSummary") if isinstance(root.get("__budgetSummary"), dict) else {}
    record_date = str(summary.get("record_date") or "")[:10]
    node_map, parent_map = index_tree(root)
    for node in node_map.values():
        node.pop(FIELD, None)
    if tree is None:
        tree = load_section_tree(record_date)
    stats: dict[str, Any] = {"statementDate": record_date, "stamped": 0, "parts": 0, "notAttributed": 0, "toNoNode": 0.0, "appliedElsewhere": 0.0}
    if tree is None:
        stats["reason"] = "no_committed_statement_for_the_anchor_date"
        return stats
    by_classification: dict[str, str] = {}
    receipts_child: dict[str, str] = {}
    for node_id, node in node_map.items():
        cid = str(node.get("treasury_classification_id") or "").strip()
        if cid and not node.get("synthetic"):
            by_classification.setdefault(cid, node_id)
        if str(node.get("synthetic") or "") == SYNTHETIC_RECEIPTS and parent_map.get(node_id):
            receipts_child[parent_map[node_id]] = node_id
    for node_id, node in node_map.items():
        if node is root or not takes_block(node):
            continue
        block = build_block(node, tree, by_classification=by_classification, receipts_child=receipts_child,
                            parent_map=parent_map, node_map=node_map, record_date=record_date)
        if block is None:
            continue
        node[FIELD] = block
        stats["stamped"] += 1
        stats["parts"] += len(block["parts"])
        stats["toNoNode"] += block["toNoNode"]
        stats["appliedElsewhere"] += block["appliedElsewhere"]
        if abs(block["notAttributed"]) > 0.005:
            stats["notAttributed"] += 1
    stats["toNoNode"] = _round(stats["toNoNode"])
    stats["appliedElsewhere"] = _round(stats["appliedElsewhere"])
    return stats
