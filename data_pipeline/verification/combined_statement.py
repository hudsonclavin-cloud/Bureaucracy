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
module does not answer -- `REVIEWED_ROWS` below does, one reviewed row per
unit, every account the chapter prints for it (CURATION.md Sec 22.8).
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
            current["figureCells"] = current["_closedCells"] + [
                cell for cell in current["_pendingCells"] if cell["printed"]
            ]
            current["_pending"] = []
            current["_pendingCells"] = []

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
            # The cell the figure is read from, exactly as printed, so a
            # record can say which printed cell (or cells) its figure is.
            cell = {"rowIndex": index, "printed": row[OUTLAYS_COLUMN].strip() if value is not None else ""}
            if not current["accountSymbol"] and row[3].strip() and row[4].strip():
                current["accountSymbol"] = "-".join(part for part in (row[2].strip(), row[3].strip(), row[4].strip()) if part)
            if row[1].strip() == "Subtotal":
                current["_closed"] += value or Decimal(0)
                current["_closedCells"].append(cell)
                current["_pending"] = []
                current["_pendingCells"] = []
                current["subtotalRows"] += 1
            else:
                current["_pending"].append(value)
                current["_pendingCells"].append(cell)
            continue
        if first in STRUCTURAL_LABELS:
            continue
        if sum(1 for cell in row if cell) == 1:
            close()
            current = {"title": first, "rowIndex": index, "_closed": Decimal(0), "_pending": [], "_closedCells": [],
                       "_pendingCells": [], "dataRows": 0, "subtotalRows": 0, "accountSymbol": ""}
            accounts.append(current)
    close()

    accounts = [a for a in accounts if a["dataRows"]]
    for account in accounts:
        del account["_closed"], account["_pending"], account["_closedCells"], account["_pendingCells"]

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


# --------------------------------------------------------------------------
# The reviewed table: which accounts are which node's (CURATION.md Sec 22.8)

#: What a record publishes under, beside the estimate and never in a cost field.
FIELD = "combinedStatementOutlays"
SOURCE_TYPE = "treasury_combined_statement"
CHAPTER_STEM = "c01"
FISCAL_YEAR = 2025
DEFAULT_EVIDENCE_PATH = PROJECT_ROOT / "data" / "verification" / "combined_statement_evidence.json"
DOCUMENT_TITLE = "Combined Statement of Receipts, Outlays, and Balances of the United States Government"
#: The graph's branch node for the chapter this table reads. A row whose node
#: sits under another branch is a unit the Treasury files under the Legislative
#: Branch and this graph curates elsewhere, and must say so.
CHAPTER_BRANCH_ID = "legislative-branch"

#: node id -> the reviewed identification. `accounts` is EVERY account the
#: chapter prints for the unit, by its printed title; `phrase` is the words
#: every one of those titles carries and no other account's title does, which
#: is how completeness is checked rather than asserted; `chapterUnit` is the
#: "Total, <unit>" line that closes each listed account; `filedInAnotherSection`
#: is the row's own declaration, re-checked against the tree on every run.
REVIEWED_ROWS: dict[str, dict[str, Any]] = {
    "leg-support-aoc-capitol-building": {
        "nodeName": "Capitol Building",
        "accounts": ("Capitol Buildings, Architect of the Capitol",),
        "phrase": "Capitol Buildings",
        "chapterUnit": "Architect of the Capitol",
        "filedInAnotherSection": False,
        "basis": ("The Architect of the Capitol's Capitol Buildings account is the appropriation for the "
                  "jurisdiction this node draws as 'Capitol Building'. The plural is the account's title and "
                  "the singular the graph's: a reviewed identification (the owner's, 2026-10-21), not a name match."),
    },
    "leg-support-aoc-capitol-grounds": {
        "nodeName": "Capitol Grounds",
        "accounts": ("Capitol Grounds, Architect of the Capitol",),
        "phrase": "Capitol Grounds",
        "chapterUnit": "Architect of the Capitol",
        "filedInAnotherSection": False,
        "basis": "The Architect's account titled for this jurisdiction, under the Architect's own total.",
    },
    "leg-support-aoc-senate-office-buildings": {
        "nodeName": "Senate Office Buildings",
        "accounts": ("Senate Office Buildings, Architect of the Capitol",),
        "phrase": "Senate Office Buildings",
        "chapterUnit": "Architect of the Capitol",
        "filedInAnotherSection": False,
        "basis": "The Architect's account titled for this jurisdiction, under the Architect's own total.",
    },
    "leg-support-aoc-house-office-buildings": {
        "nodeName": "House Office Buildings",
        "accounts": ("House Office Buildings, Architect of the Capitol",),
        "phrase": "House Office Buildings",
        "chapterUnit": "Architect of the Capitol",
        "filedInAnotherSection": False,
        "basis": "The Architect's account titled for this jurisdiction, under the Architect's own total.",
    },
    "leg-support-aoc-capitol-power-plant": {
        "nodeName": "Capitol Power Plant",
        "accounts": ("Capitol Power Plant, Architect of the Capitol",),
        "phrase": "Capitol Power Plant",
        "chapterUnit": "Architect of the Capitol",
        "filedInAnotherSection": False,
        "basis": "The Architect's account titled for this jurisdiction, under the Architect's own total.",
    },
    "leg-support-aoc-capitol-visitor-center": {
        "nodeName": "Capitol Visitor Center",
        "accounts": (
            "Capitol Visitor Center, Architect of the Capitol",
            "Capitol Visitor Center Revolving Fund, Architect of the Capitol",
        ),
        "phrase": "Capitol Visitor Center",
        "chapterUnit": "Architect of the Capitol",
        "filedInAnotherSection": False,
        "basis": ("Both accounts the chapter prints whose titles name the Capitol Visitor Center: its "
                  "appropriation and its revolving fund, which nets below zero for the year."),
    },
    "leg-support-loc-crs": {
        "nodeName": "Congressional Research Service",
        "accounts": ("Salaries and Expenses, Congressional Research Service, Library of Congress",),
        "phrase": "Congressional Research Service",
        "chapterUnit": "Library of Congress",
        "filedInAnotherSection": False,
        "basis": "The Library's account titled for this service, under the Library's own total.",
    },
    "leg-support-loc-copyright": {
        "nodeName": "Copyright Office",
        "accounts": (
            "Salaries and Expenses, Copyright Office, Library of Congress",
            "Payments to Copyright Owners, Copyright Office, Library of Congress",
        ),
        "phrase": "Copyright Office",
        "chapterUnit": "Library of Congress",
        "filedInAnotherSection": False,
        "basis": ("Both accounts the chapter prints under 'Copyright Office, Library of Congress': the "
                  "Office's salaries and expenses, and the payments to copyright owners it disburses."),
    },
    "leg-support-loc-nls": {
        "nodeName": "National Library Service for the Blind and Print Disabled (NLS)",
        "accounts": ("Salaries and Expenses, National Library Service for the Blind and Print Disabled, "
                     "Library of Congress",),
        "phrase": "National Library Service for the Blind",
        "chapterUnit": "Library of Congress",
        "filedInAnotherSection": False,
        "basis": "The Library's account titled for this service, under the Library's own total.",
    },
    "leg-senate-admin-legal": {
        "nodeName": "Office of Senate Legal Counsel",
        "accounts": ("Salaries and Expenses, Office of Senate Legal Counsel, Senate",),
        "phrase": "Senate Legal Counsel",
        "chapterUnit": "Senate",
        "filedInAnotherSection": False,
        "basis": "The Senate's account titled for this office, under the Senate's own total.",
    },
    "exec-ind-misc-macpac": {
        "nodeName": "Medicaid and CHIP Payment and Access Commission",
        "accounts": ("Medicaid and CHIP Payment and Access Commission",),
        "phrase": "Medicaid and CHIP Payment and Access Commission",
        "chapterUnit": "Legislative Branch Boards and Commissions",
        "filedInAnotherSection": True,
        "basis": ("The account is titled with the Commission's name. The Treasury prints it under the "
                  "Legislative Branch's boards and commissions; this graph curates the Commission among the "
                  "executive branch's independent agencies, and the placement is not resolved here."),
    },
    "exec-ind-misc-medpac": {
        "nodeName": "Medicare Payment Advisory Commission",
        "accounts": ("Salaries and Expenses, Medicare Payment Advisory Commission",),
        "phrase": "Medicare Payment Advisory Commission",
        "chapterUnit": "Legislative Branch Boards and Commissions",
        "filedInAnotherSection": True,
        "basis": ("The account is titled with the Commission's name. The Treasury prints it under the "
                  "Legislative Branch's boards and commissions; this graph curates the Commission among the "
                  "executive branch's independent agencies, and the placement is not resolved here."),
    },
}

NOT_THE_COST = (
    "Net outlays for fiscal year {fy}, a completed year, as the Combined Statement prints them for the "
    "account(s) listed. The Treasury's own basis, but not the current fiscal year the graph's figures cover, "
    "and not this node's cost."
)
ANOTHER_SECTION_NOTE = (
    "The Treasury files this account under the {chapter} chapter; this graph places the unit under {branch}. "
    "The figure is published as printed and is never used to divide a pool here."
)


class Unreadable(RuntimeError):
    """The committed documents cannot support the table."""


def _branch_of(node_id: str, node_map: dict[str, Any], parent_map: dict[str, str]) -> str | None:
    current = node_id
    while current in parent_map:
        parent = parent_map[current]
        if parent not in parent_map:  # the parent is the root
            return current
        current = parent
    return None


def build_records(node_map: dict[str, Any], parent_map: dict[str, str], *,
                  chapter_dir: Path | None = None, statement_root: Path | None = None
                  ) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """One record per reviewed row whose every check holds, and a report of the rest."""
    from data_pipeline.exporter.build_graph import canonical_name_key, is_post_node
    from data_pipeline.verification import financial_evidence as fe

    chapter = load_chapter(CHAPTER_STEM, chapter_dir)
    scale = reconcile_chapter_scale(CHAPTER_STEM, FISCAL_YEAR, chapter_dir=chapter_dir, statement_root=statement_root)
    pdf_path = Path(chapter_dir or CHAPTER_DIR) / f"{CHAPTER_STEM}.pdf"
    _, pdf_meta = _verified_fixture(pdf_path)
    printed_pdf = pdf_text(pdf_path)
    xlsx_meta = json.loads((Path(chapter_dir or CHAPTER_DIR) / f"{CHAPTER_STEM}.xlsx.meta.json").read_text(encoding="utf-8"))
    chapter_total = next(t for t in chapter["totals"] if t.get("isChapterTotal"))
    section = chapter_total["unit"]
    by_title: dict[str, list[dict[str, Any]]] = {}
    for account in chapter["accounts"]:
        by_title.setdefault(account["title"], []).append(account)

    records: dict[str, dict[str, Any]] = {}
    refused: dict[str, list[str]] = {}

    def refuse(reason: str, node_id: str) -> None:
        refused.setdefault(reason, []).append(node_id)

    claimed: dict[str, str] = {}
    for node_id, row in REVIEWED_ROWS.items():
        node = node_map.get(node_id)
        if node is None:
            refuse("node_not_in_graph", node_id)
            continue
        if canonical_name_key(node.get("name")) != canonical_name_key(row["nodeName"]):
            refuse("node_renamed_since_the_row_was_written", node_id)
            continue
        if is_post_node(node) or node.get("synthetic"):
            refuse("not_an_organisation", node_id)
            continue
        phrase = row["phrase"].casefold()
        components: list[dict[str, Any]] = []
        failure = None
        for title in row["accounts"]:
            found = by_title.get(title) or []
            if len(found) != 1:
                failure = "account_not_printed_exactly_once"
                break
            account = found[0]
            if account.get("unit") != row["chapterUnit"]:
                failure = "account_closed_by_another_unit_total"
                break
            if phrase not in title.casefold():
                failure = "listed_account_does_not_carry_the_phrase"
                break
            if title in claimed:
                failure = "account_claimed_by_two_rows"
                break
            cells = account.get("figureCells") or []
            if len(cells) != 1 or parse_amount(cells[0]["printed"]) != account["netOutlays"]:
                failure = "account_figure_is_not_one_printed_cell"
                break
            if cells[0]["printed"] not in printed_pdf:
                failure = "pdf_does_not_print_the_figure"
                break
            components.append({
                "account": title,
                "accountSymbol": account.get("accountSymbol") or "",
                "chapterUnit": account["unit"],
                "printed": cells[0]["printed"],
                "amount": float(account["netOutlays"]),
                "rowIndex": cells[0]["rowIndex"],
            })
        if failure:
            refuse(failure, node_id)
            continue
        unlisted = sorted(a["title"] for a in chapter["accounts"]
                          if phrase in a["title"].casefold() and a["title"] not in row["accounts"])
        if unlisted:
            refuse("chapter_prints_another_account_for_the_unit", node_id)
            continue
        branch_id = _branch_of(node_id, node_map, parent_map)
        another = branch_id != CHAPTER_BRANCH_ID
        if another != bool(row["filedInAnotherSection"]):
            refuse("section_mark_disagrees_with_the_tree", node_id)
            continue
        total_cents = sum(round(Decimal(c["printed"].replace(",", "")) * 100) for c in components)
        if total_cents == 0:
            refuse("figure_is_zero", node_id)
            continue
        for title in row["accounts"]:
            claimed[title] = node_id
        amount_raw = f"{Decimal(total_cents) / 100:,.2f}"
        single = len(components) == 1
        evidence = (
            f"{scale['chapterTotal']['label']} {scale['chapterTotal']['amountRaw']} = "
            f"{scale['statementLine']['label']} {scale['statementLine']['amountRaw']} "
            f"({scale['statementLine']['recordDate']}); "
            + "; ".join(f"{c['account']} {c['printed']}" for c in components)
            + ("" if single else f"; sum {amount_raw}")
        )
        branch_name = str((node_map.get(branch_id) or {}).get("name") or branch_id or "")
        record = {
            "nodeId": node_id,
            "nodeName": node.get("name"),
            "costBasis": "net_outlays",
            "units": "usd",
            "normalizedMultiplier": 1,
            "amount": total_cents / 100,
            "amountRaw": amount_raw,
            "unitsEvidence": evidence,
            "scaleReconciliation": scale,
            "fiscalYear": FISCAL_YEAR,
            "periodCoverage": "full_fiscal_year",
            "amountScope": "; ".join(row["accounts"]),
            "scopeMatch": "proxy",
            "rollupRole": "line" if single else "subtotal",
            "sourceType": SOURCE_TYPE,
            "sourceUrl": chapter["url"],
            "documentSha256": chapter["sha256"],
            "retrievedAt": xlsx_meta.get("fetched_at"),
            "locator": {"chapter": CHAPTER_STEM, "accounts": list(row["accounts"]), "column": "Outlays (Net)"},
            "quote": " | ".join(f"{c['account']} ... {c['printed']}" for c in components),
            "financialEvidenceStatus": "partial",
            "components": components,
            "componentCount": len(components),
            "documentsStatingTheFigure": 1 if single else 0,
            "arithmetic": {
                "operation": "sum_of_printed_account_figures",
                "note": ("The figure is the one account's net outlays as the chapter prints it." if single else
                         f"The chapter prints no single figure for this unit; the figure is the sum of the "
                         f"{len(components)} accounts it prints whose titles name it, each listed with its printed figure."),
            },
            "document": {
                "title": DOCUMENT_TITLE,
                "edition": f"Fiscal Year {FISCAL_YEAR}",
                "part": "Part Three, Detail of Appropriations, Outlays, and Balances",
                "chapter": CHAPTER_STEM,
                "chapterSection": section,
                "xlsxUrl": chapter["url"],
                "xlsxSha256": chapter["sha256"],
                "pdfUrl": pdf_meta.get("url") or "",
                "pdfSha256": pdf_meta["sha256"],
            },
            "treasurySection": {
                "chapter": section,
                "graphBranch": branch_name,
                "filedInAnotherSection": another,
                **({"note": ANOTHER_SECTION_NOTE.format(chapter=section, branch=branch_name)} if another else {}),
            },
            "matchRule": "reviewed_row",
            "matchBasis": row["basis"],
            "notTheCost": NOT_THE_COST.format(fy=FISCAL_YEAR),
        }
        # Each component is validated as the record of one printed figure (the
        # disbursement module's shape): the validator requires a record's own
        # figure to be the one the document prints, and a sum of two accounts
        # is not printed anywhere.
        try:
            kinds = set()
            for component in components:
                validated = fe.validate_record({
                    **{k: v for k, v in record.items() if k not in ("components", "arithmetic")},
                    "amount": component["amount"],
                    "amountRaw": component["printed"],
                    "amountScope": component["account"],
                    "rollupRole": "line",
                    "unitsEvidence": (
                        f"{scale['chapterTotal']['label']} {scale['chapterTotal']['amountRaw']} = "
                        f"{scale['statementLine']['label']} {scale['statementLine']['amountRaw']} "
                        f"({scale['statementLine']['recordDate']}); {component['account']} {component['printed']}"
                    ),
                    "quote": f"{component['account']} ... {component['printed']}",
                    "locator": {"chapter": CHAPTER_STEM, "account": component["account"],
                                "row": component["rowIndex"], "column": "Outlays (Net)"},
                }, node)
                component["unitsEvidenceKind"] = validated["unitsEvidenceKind"]
                kinds.add(validated["unitsEvidenceKind"])
        except fe.Rejected as error:
            refuse(f"financial_evidence_refused: {error}", node_id)
            continue
        if len(kinds) != 1:
            refuse("components_rest_on_different_scale_rules", node_id)
            continue
        record["unitsEvidenceKind"] = kinds.pop()
        records[node_id] = record
    report = {
        "chapter": CHAPTER_STEM,
        "fiscalYear": FISCAL_YEAR,
        "rowsReviewed": len(REVIEWED_ROWS),
        "published": len(records),
        "refused": refused,
        "scale": scale,
    }
    return records, report


def load_combined_statement_evidence(path: str | Path | None) -> dict[str, dict[str, Any]]:
    if not path:
        return {}
    try:
        store = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    nodes = store.get("nodes") if isinstance(store, dict) else None
    return {str(k): v for k, v in (nodes or {}).items() if isinstance(v, dict)}


def apply_combined_statement_evidence(root: dict[str, Any], records: dict[str, dict[str, Any]],
                                      *, index_tree=None) -> dict[str, Any]:
    """Stamp each record beside the node's estimate, never in a cost field.

    Withdrawn from every node first, so a row deleted or refused since the last
    build stops being published though the exporter re-feeds graph.json. Never
    on a node whose id the reviewed table does not carry, never after a rename,
    never on a post, and never where the section mark disagrees with the tree.
    """
    from data_pipeline.exporter.build_graph import canonical_name_key, is_post_node
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree
        index_tree = _index_tree
    node_map, parent_map = index_tree(root)
    applied = withdrawn = refused_unlisted = refused_renamed = refused_section = 0
    for node_id, node in node_map.items():
        if node.pop(FIELD, None) is not None:
            withdrawn += 1
        record = records.get(node_id)
        if not record:
            continue
        row = REVIEWED_ROWS.get(node_id)
        if row is None or is_post_node(node) or node.get("synthetic"):
            refused_unlisted += 1
            continue
        if canonical_name_key(node.get("name")) != canonical_name_key(row["nodeName"]) or \
                canonical_name_key(node.get("name")) != canonical_name_key(record.get("nodeName")):
            refused_renamed += 1
            continue
        another = _branch_of(node_id, node_map, parent_map) != CHAPTER_BRANCH_ID
        section = record.get("treasurySection") if isinstance(record.get("treasurySection"), dict) else {}
        if another != bool(section.get("filedInAnotherSection")) or another != bool(row["filedInAnotherSection"]):
            refused_section += 1
            continue
        node[FIELD] = json.loads(json.dumps(record))
        applied += 1
    return {"applied": applied, "withdrawn_first": withdrawn, "refused_not_a_reviewed_row": refused_unlisted,
            "refused_renamed": refused_renamed, "refused_section_mark": refused_section}
