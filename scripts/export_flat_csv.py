#!/usr/bin/env python
"""A flat CSV of every node with its figures and their sources, for download.

    python scripts/export_flat_csv.py --dry-run    # the row count and the columns; writes nothing
    python scripts/export_flat_csv.py              # writes output/nodes.csv

`docs/DEFINITION_OF_DONE.md` Part 2, "Export / download": a reader can download
the graph and a flat CSV of nodes and figures, with the sources, from the site.
`output/graph.json` is the graph; this script writes the CSV beside it, one
row per node, every column read off the node's own published fields and
nothing computed here that the panel does not already say:

- the node: id, name, type, parent id and name, depth, branch, lifecycle;
- the cost as published: status, the figure (blank where the graph publishes
  none), basis, the Treasury row name and the FiscalData URL for a measured
  line, the validation word for a withheld one;
- sourced figures of another kind, each with its period and URL: File A gross
  outlays, OMB outlays, audited net cost, Combined Statement net outlays, the
  chamber's disbursements, FedScope headcount and civilian payroll;
- the pay headline the panel shows for a post: which field, the figure or the
  range, the document's URL, and the count of documents it rests on;
- existence and placement evidence: method, URL, date; the recorded reason no
  document can be read where there is one;
- the explained blanks: the cost blank's and the pay blank's kind.

A column is blank where the node publishes nothing for it; a zero is never
written for a missing figure. The gate re-reads the CSV beside the graph and
refuses one whose rows are not the graph's nodes or whose figures are not the
nodes' own.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GRAPH = PROJECT_ROOT / "output" / "graph.json"
DEFAULT_OUT = PROJECT_ROOT / "output" / "nodes.csv"

#: The pay headline order the panel uses (js/ui.js PAY_STAND_IN_ORDER): a
#: figure a document states for the office first, then for an incumbency,
#: then a range.
PAY_STAND_IN_ORDER = (
    "positionStatutoryPay", "positionSchedulePay", "positionTierReferencePay", "positionDerivedPay", "positionMilitaryPay",
    "positionReportedPay", "positionCurrentPay", "positionPayRate", "positionGradePay", "positionTierPay",
)
COLUMNS = (
    "id", "name", "type", "parent_id", "parent_name", "depth", "branch", "lifecycle",
    "cost_status", "cost_amount_usd", "cost_basis", "cost_validation", "treasury_row_name", "treasury_section", "cost_source_url", "cost_period",
    "usaspending_gross_outlays_usd", "usaspending_period", "usaspending_url",
    "omb_outlays_usd", "omb_fiscal_year", "omb_url",
    "audited_net_cost_usd", "audited_fiscal_year", "audited_url",
    "combined_statement_net_outlays_usd", "combined_statement_fiscal_year", "combined_statement_url",
    "disbursements_usd", "disbursements_period_start", "disbursements_period_end", "disbursements_url",
    "employees_official", "employees_period", "employees_url", "payroll_official_usd",
    "pay_field", "pay_amount_usd", "pay_minimum_usd", "pay_maximum_usd", "pay_source", "pay_url", "pay_documents",
    "verification_method", "verification_url", "verification_date", "verification_no_document_kind",
    "placement_method", "placement_url",
    "cost_blank_kind", "pay_blank_kind", "pay_employer_kind",
)


def _num(value: Any) -> str:
    if value is None or isinstance(value, bool):
        return ""
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return ""


def _first(node: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = node.get(key)
        if isinstance(value, str) and value:
            return value
        if isinstance(value, list) and value and isinstance(value[0], str):
            return value[0]
    return ""


def pay_headline(node: dict[str, Any]) -> dict[str, str]:
    for field in PAY_STAND_IN_ORDER:
        block = node.get(field)
        if not isinstance(block, dict):
            continue
        # pay_documents.py stamps the count of documents the figure rests on
        # under the block's `verification`
        docs = block.get("verification") if isinstance(block.get("verification"), dict) else {}
        return {
            "pay_field": field,
            "pay_amount_usd": _num(block.get("amount")),
            "pay_minimum_usd": _num(block.get("minimum")),
            "pay_maximum_usd": _num(block.get("maximum")),
            "pay_source": str(block.get("source") or block.get("sourceType") or ""),
            "pay_url": str(block.get("url") or block.get("statuteUrl") or block.get("tableUrl") or ""),
            "pay_documents": str(docs.get("documents") if docs.get("documents") is not None else docs.get("count") or ""),
        }
    return {k: "" for k in ("pay_field", "pay_amount_usd", "pay_minimum_usd", "pay_maximum_usd", "pay_source", "pay_url", "pay_documents")}


def row_for(node: dict[str, Any], parent: dict[str, Any] | None, depth: int, branch: str | None) -> dict[str, str]:
    status = str(node.get("cost_status") or "")
    publishes_figure = status in ("official", "root_total", "allocated", "scaled_official") and node.get("resolved_total_amount") is not None
    usa = node.get("usaspendingOutlays") if isinstance(node.get("usaspendingOutlays"), dict) else {}
    omb = node.get("ombBudget") if isinstance(node.get("ombBudget"), dict) else {}
    aud = node.get("auditedNetCost") if isinstance(node.get("auditedNetCost"), dict) else {}
    comb = node.get("combinedStatementOutlays") if isinstance(node.get("combinedStatementOutlays"), dict) else {}
    disb = node.get("committeeDisbursements") if isinstance(node.get("committeeDisbursements"), dict) else {}
    emp = node.get("employeesOfficialSource") if isinstance(node.get("employeesOfficialSource"), dict) else {}
    payroll = node.get("payrollOfficial") if isinstance(node.get("payrollOfficial"), dict) else {}
    nodoc = node.get("verificationNoDocument") if isinstance(node.get("verificationNoDocument"), dict) else {}
    cost_blank = node.get("costNoDocument") if isinstance(node.get("costNoDocument"), dict) else {}
    pay_blank = node.get("payNoDocument") if isinstance(node.get("payNoDocument"), dict) else {}
    employer = node.get("positionEmployer") if isinstance(node.get("positionEmployer"), dict) else {}
    row = {
        "id": str(node.get("id") or ""), "name": str(node.get("name") or ""), "type": str(node.get("type") or ""),
        "parent_id": str((parent or {}).get("id") or ""), "parent_name": str((parent or {}).get("name") or ""),
        "depth": str(depth), "branch": branch or "", "lifecycle": str(node.get("lifecycle") or ""),
        "cost_status": status, "cost_amount_usd": _num(node.get("resolved_total_amount")) if publishes_figure else "",
        "cost_basis": str(node.get("cost_basis") or ""), "cost_validation": str(node.get("cost_validation") or ""),
        "treasury_row_name": str(node.get("treasury_row_name") or "") if status in ("official", "root_total") else "",
        "treasury_section": str(node.get("treasury_section") or "") if status in ("official", "root_total") else "",
        "cost_source_url": next((u for u in (node.get("sourceUrls") or []) if isinstance(u, str) and "fiscaldata.treasury.gov" in u), "") if status in ("official", "root_total") else "",
        "cost_period": str(node.get("budget_as_of") or ""),
        "usaspending_gross_outlays_usd": _num(usa.get("amount")), "usaspending_period": f"FY{usa.get('fiscalYear')} to {usa.get('periodAsOf')}" if usa else "", "usaspending_url": str(usa.get("url") or ""),
        "omb_outlays_usd": _num(omb.get("outlays")), "omb_fiscal_year": str(omb.get("fiscalYear") or ""), "omb_url": str(omb.get("url") or ""),
        "audited_net_cost_usd": _num(aud.get("netCostUsd")), "audited_fiscal_year": str(aud.get("fiscalYear") or ""), "audited_url": str(aud.get("url") or ""),
        "combined_statement_net_outlays_usd": _num(comb.get("amount")), "combined_statement_fiscal_year": str(comb.get("fiscalYear") or ""), "combined_statement_url": str(comb.get("sourceUrl") or ""),
        "disbursements_usd": _num(disb.get("amount")), "disbursements_period_start": str((disb.get("period") or {}).get("start") or ""), "disbursements_period_end": str((disb.get("period") or {}).get("end") or ""),
        "disbursements_url": str((disb.get("document") or {}).get("url") or ""),
        "employees_official": str(node.get("employeesOfficial")) if isinstance(node.get("employeesOfficial"), int) else "", "employees_period": str(emp.get("period") or ""), "employees_url": str(emp.get("url") or ""),
        "payroll_official_usd": _num(payroll.get("totalAnnualPay")),
        "verification_method": str(node.get("verificationMethod") or ""),
        "verification_url": _first(node, "verificationSiteFrom", "evidenceUrls", "sourceUrls") if node.get("verificationMethod") else "",
        "verification_date": str(node.get("lastVerified") or "") if node.get("verificationMethod") else "",
        "verification_no_document_kind": str(nodoc.get("kind") or ""),
        "placement_method": str(node.get("placementMethod") or ""), "placement_url": str(node.get("placementUrl") or ""),
        "cost_blank_kind": str(cost_blank.get("kind") or ""), "pay_blank_kind": str(pay_blank.get("kind") or ""),
        "pay_employer_kind": str(employer.get("kind") or ""),
    }
    row.update(pay_headline(node))
    return row


def rows_of(graph: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    stack = [(graph, None, 0, None)]
    while stack:
        node, parent, depth, branch = stack.pop()
        if not isinstance(node, dict):
            continue
        here = str(node.get("id")) if depth == 1 else branch
        out.append(row_for(node, parent, depth, here))
        for child in reversed(node.get("children") or []):
            stack.append((child, node, depth + 1, here))
    return out


def render(graph: dict[str, Any]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in rows_of(graph):
        writer.writerow(row)
    return buffer.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args((argv or sys.argv)[1:])
    if not args.graph.exists():
        print(f"refused: {args.graph} does not exist")
        return 1
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    text = render(graph)
    rows = text.count("\n") - 1
    print(f"{rows:,} rows, {len(COLUMNS)} columns, {len(text.encode('utf-8')):,} bytes")
    if args.dry_run:
        return 0
    args.out.write_text(text, encoding="utf-8")
    print(f"wrote {args.out.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
