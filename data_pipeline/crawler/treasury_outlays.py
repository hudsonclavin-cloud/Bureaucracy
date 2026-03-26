from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from data_pipeline.crawler.common import request_json
from data_pipeline.processors.normalize_nodes import normalize_name


API_URL = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/mts/mts_table_5"
DATASET_URL = "https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/outlays-of-the-u-s-government"
TOTAL_OUTLAYS_LABEL = "Total Outlays"
IGNORED_TOTAL_LABELS = {
    "Total On-Budget",
    "Total Off-Budget",
    "Total Surplus (+) or Deficit (-)",
}


@dataclass(frozen=True)
class TreasuryOutlayRow:
    name: str
    original_name: str
    amount: float
    fiscal_year: str
    record_date: str
    sequence_level: int
    print_order: int


def parse_amount(value: Any) -> float | None:
    if value in (None, "", "null"):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def normalize_row_name(label: str) -> str:
    text = str(label or "").strip().rstrip(":").strip()
    if text.startswith("Total--"):
        text = text[len("Total--") :].strip()
    return normalize_name(text)


def fetch_latest_record_date(*, fiscal_year: int | None = None, timeout: int = 30) -> str | None:
    params = {
        "sort": "-record_date",
        "page[size]": 1,
    }
    if fiscal_year:
        params["filter"] = f"record_fiscal_year:eq:{fiscal_year}"
    payload = request_json(API_URL, params=params, timeout=timeout)
    rows = payload.get("data", []) if isinstance(payload, dict) else []
    if not rows:
        return None
    return str(rows[0].get("record_date") or "").strip() or None


def fetch_rows_for_record_date(record_date: str, *, timeout: int = 30) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    page_number = 1
    while True:
        payload = request_json(
            API_URL,
            params={
                "filter": f"record_date:eq:{record_date}",
                "sort": "print_order_nbr",
                "page[size]": 1000,
                "page[number]": page_number,
            },
            timeout=timeout,
        )
        page_rows = payload.get("data", []) if isinstance(payload, dict) else []
        if not isinstance(page_rows, list) or not page_rows:
            break
        rows.extend(row for row in page_rows if isinstance(row, dict))
        links = payload.get("links", {}) if isinstance(payload, dict) else {}
        if not isinstance(links, dict) or not links.get("next"):
            break
        page_number += 1
    return rows


def parse_outlay_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    outlay_rows: list[dict[str, Any]] = []
    budget_summary: dict[str, Any] | None = None
    for row in rows:
        original_label = str(row.get("classification_desc") or "").strip()
        if not original_label:
            continue
        amount = parse_amount(row.get("current_fytd_net_outly_amt"))
        if original_label == TOTAL_OUTLAYS_LABEL and amount is not None:
            budget_summary = {
                "government_total_outlay_amount": amount,
                "amount_kind": "fytd_net_outlays",
                "fiscal_year": str(row.get("record_fiscal_year") or "").strip() or None,
                "record_date": str(row.get("record_date") or "").strip() or None,
                "label": f"FYTD net outlays through {row.get('record_date')}",
                "source_system": "Treasury Fiscal Data",
                "source_url": DATASET_URL,
            }
            continue
        if amount is None or original_label in IGNORED_TOTAL_LABELS:
            continue
        normalized_name = normalize_row_name(original_label)
        if not normalized_name:
            continue
        outlay_rows.append(
            {
                "name": normalized_name,
                "originalName": original_label,
                "rollup_total_amount": amount,
                "amount_kind": "fytd_net_outlays",
                "budget_year": str(row.get("record_fiscal_year") or "").strip() or None,
                "budget_as_of": str(row.get("record_date") or "").strip() or None,
                "source_system": "Treasury Fiscal Data",
                "budget_source": "Treasury MTS Table 5",
                "allocation_basis": "treasury_rollup",
                "sourceUrls": [DATASET_URL],
                "sourceTypes": ["official_site"],
                "sequence_level": int(str(row.get("sequence_level_nbr") or 0) or 0),
                "print_order": int(str(row.get("print_order_nbr") or 0) or 0),
            }
        )
    return outlay_rows, budget_summary


def crawl(*, fiscal_year: int | None = None, timeout: int = 30) -> dict[str, Any]:
    record_date = fetch_latest_record_date(fiscal_year=fiscal_year, timeout=timeout)
    if not record_date:
        return {"nodes": [], "edges": [], "outlayRows": [], "budgetSummary": None}
    rows = fetch_rows_for_record_date(record_date, timeout=timeout)
    outlay_rows, budget_summary = parse_outlay_rows(rows)
    return {
        "nodes": [],
        "edges": [],
        "outlayRows": outlay_rows,
        "budgetSummary": budget_summary,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(crawl(), indent=2))
