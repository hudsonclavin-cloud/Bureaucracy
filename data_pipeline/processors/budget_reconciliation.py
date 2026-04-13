"""Helpers for conservative budget-vs-actual reconciliation.

This module intentionally avoids inventing Treasury account mappings or
mutating graph trust semantics. It only summarizes what is already present on
trusted organization-like nodes.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

TRUSTED_ORG_TYPES = {
    "Agency",
    "Department",
    "Cabinet Department",
    "Independent Agency",
    "Executive Department",
}


def _coerce_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_amount(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    cleaned = text.replace(",", "").replace("$", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _has_budget_fields(node: Mapping[str, Any]) -> bool:
    return any(
        _coerce_amount(node.get(field)) is not None
        for field in ("annual_budget", "budget")
    )


def _has_actual_fields(node: Mapping[str, Any]) -> bool:
    return _coerce_amount(node.get("rollup_total_amount")) is not None


def _normalise_type(value: Any) -> str:
    return _coerce_text(value) or ""


def build_budget_vs_actual_report(nodes: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Return a serializable summary of available budget-vs-actual data.

    Only trusted org-like nodes are included. The helper stays conservative:
    it summarizes existing fields and never infers TAS/account mappings.
    """

    rows: list[dict[str, Any]] = []
    summary = {
        "nodes_seen": len(nodes),
        "trusted_org_nodes_seen": 0,
        "rows_emitted": 0,
        "complete_rows": 0,
        "budget_only_rows": 0,
        "actual_only_rows": 0,
        "unavailable_rows": 0,
        "missing_budget_rows": 0,
        "missing_actual_rows": 0,
        "budget_source_counts": {},
        "actual_source_counts": {},
    }

    for node in nodes:
        node_type = _normalise_type(node.get("type"))
        if node_type not in TRUSTED_ORG_TYPES:
            continue

        summary["trusted_org_nodes_seen"] += 1

        budget_amount = _coerce_amount(node.get("annual_budget"))
        if budget_amount is None:
            budget_amount = _coerce_amount(node.get("budget"))
        actual_amount = _coerce_amount(node.get("rollup_total_amount"))
        budget_source = _coerce_text(node.get("budget_source"))
        budget_year = _coerce_text(node.get("budget_year"))
        budget_as_of = _coerce_text(node.get("budget_as_of"))

        has_budget = budget_amount is not None
        has_actual = actual_amount is not None
        if has_budget:
            summary["budget_source_counts"][budget_source or "unknown"] = (
                summary["budget_source_counts"].get(budget_source or "unknown", 0) + 1
            )
        if has_actual:
            summary["actual_source_counts"]["Treasury rollup"] = (
                summary["actual_source_counts"].get("Treasury rollup", 0) + 1
            )

        if not has_budget:
            summary["missing_budget_rows"] += 1
        if not has_actual:
            summary["missing_actual_rows"] += 1

        if has_budget and has_actual:
            reconciliation_status = "complete"
            variance_amount = round(actual_amount - budget_amount, 2)
            variance_percent = round((variance_amount / budget_amount) * 100.0, 2) if budget_amount else None
            summary["complete_rows"] += 1
        elif has_budget:
            reconciliation_status = "budget_only"
            variance_amount = None
            variance_percent = None
            summary["budget_only_rows"] += 1
        elif has_actual:
            reconciliation_status = "actual_only"
            variance_amount = None
            variance_percent = None
            summary["actual_only_rows"] += 1
        else:
            reconciliation_status = "unavailable"
            variance_amount = None
            variance_percent = None
            summary["unavailable_rows"] += 1

        rows.append(
            {
                "id": _coerce_text(node.get("id")),
                "name": _coerce_text(node.get("name")),
                "type": node_type,
                "budget_amount": budget_amount,
                "actual_amount": actual_amount,
                "variance_amount": variance_amount,
                "variance_percent": variance_percent,
                "budget_source": budget_source,
                "budget_year": budget_year,
                "budget_as_of": budget_as_of,
                "actual_source": "Treasury rollup" if has_actual else None,
                "actual_as_of": budget_as_of if has_actual else None,
                "reconciliation_status": reconciliation_status,
                "availability": {
                    "budget_present": has_budget,
                    "actual_present": has_actual,
                    "complete": has_budget and has_actual,
                },
            }
        )

    summary["rows_emitted"] = len(rows)
    summary["reconciled_rows"] = summary["complete_rows"]
    summary["incomplete_rows"] = (
        summary["budget_only_rows"] + summary["actual_only_rows"] + summary["unavailable_rows"]
    )

    return {
        "summary": summary,
        "rows": rows,
    }


def reconcile_nodes(nodes: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Alias kept for the main agent's integration layer."""

    return build_budget_vs_actual_report(deepcopy(nodes))
