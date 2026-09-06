"""Helpers for conservative budget-vs-actual reconciliation.

This module intentionally avoids inventing Treasury account mappings or
mutating graph trust semantics. It only summarizes what is already present on
organisation nodes: a budget figure (the curated `budget`/`annual_budget`
note) against the actual outlays a Treasury line stamped on the node.

Wired into build_graph as of 2026-09; the per-run report lands in
output/budget_reconciliation.json (an untracked diagnostic) and its summary
in the validity report and pipeline stats. Rows say `present`, not
`verified`: a curated budget note is a number somebody typed, and this
module does not check it.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Mapping

# A position or a committee does not have outlays of its own. Everything
# else with a figure is reconciled; a fixed allowlist of type names is the
# mechanism that once dropped 97% of the curated graph from the validators.
NON_ORGANISATION_TYPE_KEYWORDS = ("position", "role", "committee", "subcommittee", "caucus", "office holder", "person")
TREASURY_SOURCE_PREFIX = "treasury"


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


def _normalise_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        values = [_coerce_text(item) for item in value]
    else:
        values = [_coerce_text(value)]
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _is_organisation(node: Mapping[str, Any]) -> bool:
    type_text = _normalise_type(node.get("type")).casefold()
    return not any(keyword in type_text for keyword in NON_ORGANISATION_TYPE_KEYWORDS)


def build_budget_vs_actual_report(
    nodes: list[Mapping[str, Any]],
    *,
    amount_parser: Callable[[Any], float | None] | None = None,
) -> dict[str, Any]:
    """Return a serializable summary of available budget-vs-actual data.

    Organisation nodes carrying a budget figure or a Treasury actual are
    included. The helper stays conservative: it summarizes existing fields
    and never infers TAS/account mappings. `amount_parser` lets the caller
    read the curated "~$800M" notes; the default reads plain numbers only.
    """

    parse = amount_parser or _coerce_amount
    nodes = list(nodes)
    rows: list[dict[str, Any]] = []
    summary = {
        "nodes_seen": len(nodes),
        "organisation_nodes_seen": 0,
        "nodes_without_figures": 0,
        "rows_emitted": 0,
        "complete_rows": 0,
        "budget_only_rows": 0,
        "actual_only_rows": 0,
        "unavailable_rows": 0,
        "missing_budget_rows": 0,
        "missing_actual_rows": 0,
        "variance_status_counts": {},
        "budget_source_counts": {},
        "actual_source_counts": {},
    }

    for node in nodes:
        node_type = _normalise_type(node.get("type"))
        if not _is_organisation(node):
            continue
        summary["organisation_nodes_seen"] += 1

        budget_amount = parse(node.get("annual_budget"))
        if budget_amount is None:
            budget_amount = parse(node.get("budget"))
        actual_amount = parse(node.get("rollup_total_amount"))
        if actual_amount == 0:
            actual_amount = None
        if budget_amount is None and actual_amount is None:
            summary["nodes_without_figures"] += 1
            continue
        # budget_source / budget_as_of describe whichever figure stamped them:
        # a Treasury line dates the actual; anything else dates the budget.
        stamped_source = _coerce_text(node.get("budget_source"))
        stamped_as_of = _coerce_text(node.get("budget_as_of"))
        from_treasury = bool(stamped_source and stamped_source.casefold().startswith(TREASURY_SOURCE_PREFIX))
        budget_source = None if from_treasury else stamped_source
        if budget_amount is not None and budget_source is None:
            budget_source = "curated budget note" if node.get("annual_budget") is None else "annual_budget field"
        budget_year = _coerce_text(node.get("budget_year"))
        budget_as_of = None if from_treasury else stamped_as_of
        actual_as_of = stamped_as_of if from_treasury else None
        actual_source = (stamped_source if from_treasury else "Treasury rollup") if actual_amount is not None else None
        tas_codes = _normalise_string_list(
            node.get("treasuryAccountSymbols")
            or node.get("treasury_account_symbols")
            or node.get("tas")
        )

        has_budget = budget_amount is not None
        has_actual = actual_amount is not None
        if has_budget:
            summary["budget_source_counts"][budget_source or "unknown"] = (
                summary["budget_source_counts"].get(budget_source or "unknown", 0) + 1
            )
        if has_actual:
            summary["actual_source_counts"][actual_source] = summary["actual_source_counts"].get(actual_source, 0) + 1

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

        variance_status = (
            "over_budget"
            if variance_amount is not None and variance_amount > 0
            else "under_budget"
            if variance_amount is not None and variance_amount < 0
            else "on_budget"
            if variance_amount == 0
            else "unavailable"
        )
        summary["variance_status_counts"][variance_status] = summary["variance_status_counts"].get(variance_status, 0) + 1

        rows.append(
            {
                "id": _coerce_text(node.get("id")),
                "name": _coerce_text(node.get("name")),
                "type": node_type,
                "treasury_account_symbols": tas_codes,
                "tas_mapping_status": "mapped" if tas_codes else "unmapped",
                "budget_amount": budget_amount,
                "actual_amount": actual_amount,
                "variance_amount": variance_amount,
                "variance_percent": variance_percent,
                "variance_status": variance_status,
                "budget_source": budget_source,
                "budget_year": budget_year,
                "budget_as_of": budget_as_of,
                "actual_source": actual_source,
                "actual_as_of": actual_as_of,
                "budget": {
                    "amount": budget_amount,
                    "source": budget_source,
                    "year": budget_year,
                    "as_of": budget_as_of,
                    "present": has_budget,
                },
                "actual": {
                    "amount": actual_amount,
                    "source": actual_source,
                    "as_of": actual_as_of,
                    "present": has_actual,
                },
                "variance": {
                    "amount": variance_amount,
                    "percent": variance_percent,
                },
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


def reconcile_nodes(
    nodes: list[Mapping[str, Any]],
    *,
    amount_parser: Callable[[Any], float | None] | None = None,
) -> dict[str, Any]:
    """Reconcile a copy of the nodes; the graph is never mutated."""

    return build_budget_vs_actual_report(deepcopy(list(nodes)), amount_parser=amount_parser)
