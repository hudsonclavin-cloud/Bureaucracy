"""The Combined Statement of Receipts, Outlays, and Balances, read and reconciled.

Part Three of the Combined Statement prints, per organisation chapter, every
appropriation or fund account with its net outlays for a completed fiscal year,
closes each unit with a "Total, <unit>" line, and closes the chapter with
"Total, <chapter>". `parse_chapter` reads the committed XLSX export into
accounts and totals and refuses to return anything unless the chapter's own
printed arithmetic holds to the cent (CURATION.md Sec 22.6).

**The scale, and how it is established.** The chapter states its scale nowhere
in words, and neither do the four explanatory chapters committed beside it
(Sec 22.5). What establishes it is a second document this project already
trusts for scale: the Monthly Treasury Statement's Table 5, whose API figures
the cost cascade's anchor has always been read as whole dollars. The statement
for September 30 of a fiscal year carries that year's whole-year net outlays in
`current_fytd_net_outly_amt`, and `reconcile_chapter_scale` requires the
chapter's own total line to equal the statement's `Total--<chapter>` line TO
THE CENT, re-reading both committed fixtures with their digests recomputed. On
2026-10-21 the Legislative Branch chapter's $7,232,968,757.51 equals the
September 2025 statement's line exactly; any other reading of the chapter's
scale would be a thousandfold off. The owner granted this as a scale rule the
same day (`financial_evidence.RECONCILED_TO_MONTHLY_STATEMENT_SOURCE_TYPES`).

What the reconciliation establishes is the scale of THIS chapter's figures, and
nothing else. Both documents come from the Bureau of the Fiscal Service's own
ledger, so their agreement is consistency, not independent verification of any
figure; and which node an account names is a separate, reviewed question this
module does not answer.
"""

from __future__ import annotations

import hashlib
import json
import re
import zlib
from decimal import Decimal
from pathlib import Path
from typing import Any

from data_pipeline.verification.congress import read_xlsx_rows

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures"
CHAPTER_DIR = FIXTURE_ROOT / "treasury" / "combined_statement" / "cs2025"

#: The column the chapter prints "Outlays (Net)" in, by the header rows of the
#: XLSX export (index 9 of 12).
OUTLAYS_COLUMN = 9
#: A data row's second cell is its period of availability or "Subtotal".
PERIOD_PATTERN = re.compile(r"^(\d{4}(-\d{4})?|No Year|Subtotal)$")
STRUCTURAL_LABELS = {"Fund Resources:", "Appropriations, Outlays, and Balances"}
TOTAL_PREFIX = "Total, "
OFFSETTING_TOTAL = "Offsetting Receipts"

#: The Monthly Treasury Statement's own prefix for a section's net line, and
#: the field that, on the statement dated the last day of a fiscal year, is
#: that whole year's net outlays.
STATEMENT_TOTAL_PREFIX = "Total--"
STATEMENT_FIELD = "current_fytd_net_outly_amt"

TRAILING_ORG_PATTERN = re.compile(r",\s*[^,]+$")
LEADING_LABEL_PATTERN = re.compile(
    r"^(Salaries and Expenses|Compensation of Members and Related Administrative Expenses),\s*",
    re.IGNORECASE,
)


class ReconciliationError(ValueError):
    """The chapter's own printed totals, or the statement's, do not agree with
    what was parsed."""


def parse_amount(cell: Any) -> Decimal | None:
    text = str(cell or "").strip()
    if not text or text == "----------":
        return None
    return Decimal(text.replace(",", ""))


def _cells(row: list[Any]) -> list[str]:
    return [str(cell or "") for cell in row]


def parse_chapter(rows: list[list[Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Every account and every "Total, <unit>" line of one chapter.

    An account's figure is the Outlays (Net) column of each "Subtotal" row plus
    every data row after the last one (a single-year account prints no
    Subtotal; one that also carries "Funds Held Outside the Treasury" prints
    them inside its Subtotal). Each account belongs to the unit whose total
    line closes it.

    Raises ReconciliationError unless every unit total equals the sum of its
    accounts and the unit totals (with the chapter's offsetting receipts)
    equal the chapter total, all to the cent.
    """
    accounts: list[dict[str, Any]] = []
    totals: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def close() -> None:
        if current is not None:
            current["netOutlays"] = current["_closed"] + sum(
                (value for value in current["_pending"] if value is not None), Decimal(0)
            )
            current["_pending"] = []

    for index, raw in enumerate(rows):
        row = _cells(raw)
        if not any(row):
            continue
        first = row[0]
        if first.startswith(TOTAL_PREFIX):
            close()
            current = None
            totals.append({
                "unit": first[len(TOTAL_PREFIX):].strip(),
                "label": first.strip(),
                "printed": row[OUTLAYS_COLUMN].strip() if len(row) > OUTLAYS_COLUMN else "",
                "rowIndex": index,
                "netOutlays": parse_amount(row[OUTLAYS_COLUMN]) if len(row) > OUTLAYS_COLUMN else None,
            })
            continue
        if len(row) > OUTLAYS_COLUMN and PERIOD_PATTERN.match(row[1].strip()):
            if current is None:
                raise ReconciliationError(f"data row {index} sits outside any account")
            current["dataRows"] += 1
            value = parse_amount(row[OUTLAYS_COLUMN])
            if row[1].strip() == "Subtotal":
                current["_closed"] += value or Decimal(0)
                current["_pending"] = []
                current["subtotalRows"] += 1
            else:
                current["_pending"].append(value)
            continue
        if first in STRUCTURAL_LABELS:
            continue
        if sum(1 for cell in row if cell) == 1:
            close()
            current = {"title": first, "rowIndex": index, "_closed": Decimal(0), "_pending": [], "dataRows": 0, "subtotalRows": 0}
            accounts.append(current)
    close()

    accounts = [a for a in accounts if a["dataRows"]]
    for account in accounts:
        del account["_closed"], account["_pending"]

    previous = -1
    chapter_total: dict[str, Any] | None = None
    unit_sum = Decimal(0)
    for total in totals:
        members = [a for a in accounts if previous < a["rowIndex"] < total["rowIndex"]]
        if total is totals[-1] and not members:
            chapter_total = total
            break
        for account in members:
            account["unit"] = total["unit"]
        total["accountCount"] = len(members)
        if members:
            parsed = sum((a["netOutlays"] for a in members), Decimal(0))
            if parsed != total["netOutlays"]:
                raise ReconciliationError(
                    f"Total, {total['unit']} prints {total['netOutlays']} but its {len(members)} accounts sum to {parsed}"
                )
        unit_sum += total["netOutlays"] or Decimal(0)
        previous = total["rowIndex"]
    if chapter_total is None:
        raise ReconciliationError("no chapter total line found")
    if unit_sum != chapter_total["netOutlays"]:
        raise ReconciliationError(
            f"Total, {chapter_total['unit']} prints {chapter_total['netOutlays']} but the unit totals sum to {unit_sum}"
        )
    chapter_total["isChapterTotal"] = True
    return accounts, totals


def pdf_text(path: Path) -> str:
    """The chapter's PDF as one flat string of its Tj/TJ string operands --
    enough for a substring check of a printed figure; no spacing attempted."""
    raw = Path(path).read_bytes()
    blobs = []
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", raw, re.DOTALL):
        try:
            blobs.append(zlib.decompress(match.group(1)))
        except zlib.error:
            continue
    strings = re.findall(rb"\((?:[^()\\]|\\.)*\)", b"".join(blobs))
    return b"".join(s[1:-1] for s in strings).decode("latin-1", "ignore")


def strip_candidates(title: str) -> list[str]:
    """What an account title reduces to once the issuing-unit suffix and an
    account-type prefix are set aside -- candidates, not a chosen name."""
    candidates = {title}
    no_suffix = TRAILING_ORG_PATTERN.sub("", title).strip()
    if no_suffix and no_suffix != title:
        candidates.add(no_suffix)
    for base in list(candidates):
        no_prefix = LEADING_LABEL_PATTERN.sub("", base).strip()
        if no_prefix and no_prefix != base:
            candidates.add(no_prefix)
    return sorted(candidates, key=len)


def _verified_fixture(path: Path) -> tuple[bytes, dict[str, Any]]:
    """The fixture's bytes and its fetch record, refused unless the digest the
    fetch recorded is the digest of the bytes on disk."""
    path = Path(path)
    data = path.read_bytes()
    meta_path = path.with_name(path.name + ".meta.json")
    if not meta_path.exists():
        raise ReconciliationError(f"{path.name}: no fetch record beside it")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(data).hexdigest()
    if meta.get("sha256") != digest:
        raise ReconciliationError(f"{path.name}: sha256 on disk {digest} is not the fetch record's {meta.get('sha256')}")
    return data, {**meta, "sha256": digest}


def load_chapter(stem: str = "c01", directory: Path | None = None) -> dict[str, Any]:
    """One committed chapter, digest recomputed, parsed and reconciled."""
    path = Path(directory or CHAPTER_DIR) / f"{stem}.xlsx"
    _, meta = _verified_fixture(path)
    accounts, totals = parse_chapter(read_xlsx_rows(path))
    return {"accounts": accounts, "totals": totals, "sha256": meta["sha256"], "url": meta.get("url") or ""}


def statement_fixture(fiscal_year: int, root: Path | None = None) -> Path:
    """The committed Table 5 response dated the last day of `fiscal_year`."""
    return Path(root or FIXTURE_ROOT) / f"mts_table5_{fiscal_year}-09-30.json"


def statement_line(fiscal_year: int, unit: str, root: Path | None = None) -> dict[str, Any]:
    """The September statement's `Total--<unit>` line, digest recomputed.

    Exactly one row must carry the label, and the response must be the one
    dated September 30 of the fiscal year, so its year-to-date column is the
    whole year's.
    """
    path = statement_fixture(fiscal_year, root)
    if not path.exists():
        raise ReconciliationError(f"no Table 5 statement for FY{fiscal_year} is committed at {path.name}")
    data, meta = _verified_fixture(path)
    payload = json.loads(data.decode("utf-8"))
    record_date = str(payload.get("record_date") or "")
    if record_date != f"{fiscal_year}-09-30":
        raise ReconciliationError(f"{path.name} is dated {record_date!r}, not the last day of FY{fiscal_year}")
    label = f"{STATEMENT_TOTAL_PREFIX}{unit}"
    rows = [r for r in payload.get("rows") or [] if str(r.get("classification_desc") or "").strip() == label]
    if len(rows) != 1:
        raise ReconciliationError(f"{path.name} carries {len(rows)} rows labelled {label!r}, not one")
    row = rows[0]
    if str(row.get("record_fiscal_year") or "") != str(fiscal_year):
        raise ReconciliationError(f"{label} on {path.name} is filed under FY{row.get('record_fiscal_year')}")
    return {
        "label": label,
        "amountRaw": str(row.get(STATEMENT_FIELD) or "").strip(),
        "recordDate": record_date,
        "field": STATEMENT_FIELD,
        "url": meta.get("url") or "",
        "documentSha256": meta["sha256"],
    }


def reconcile_chapter_scale(
    stem: str = "c01",
    fiscal_year: int = 2025,
    *,
    chapter_dir: Path | None = None,
    statement_root: Path | None = None,
) -> dict[str, Any]:
    """The block a record from this chapter carries as `scaleReconciliation`.

    Raises ReconciliationError unless the chapter's own total line equals the
    September statement's line for the same unit to the cent.
    """
    chapter = load_chapter(stem, chapter_dir)
    total = next(t for t in chapter["totals"] if t.get("isChapterTotal"))
    line = statement_line(fiscal_year, total["unit"], statement_root)
    printed = parse_amount(line["amountRaw"])
    if printed is None or printed != total["netOutlays"]:
        raise ReconciliationError(
            f"{total['label']} prints {total['netOutlays']} but the FY{fiscal_year} statement's "
            f"{line['label']} prints {line['amountRaw']!r}"
        )
    return {
        "chapterTotal": {
            "label": total["label"],
            "amountRaw": total["printed"],
            "url": chapter["url"],
            "documentSha256": chapter["sha256"],
        },
        "statementLine": line,
    }
