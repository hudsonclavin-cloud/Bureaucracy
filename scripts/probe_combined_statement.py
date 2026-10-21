"""Report which Combined Statement accounts and unit totals match a node.

Read-only: nothing in data/verification/ or output/ is written. This is the
diagnostic CURATION.md Sec 22.5 calls for before any derive script acts on
the Combined Statement of Receipts, Outlays, and Balances -- the same role
scripts/probe_treasury_rows.py plays for the Monthly Treasury Statement.

    python scripts/probe_combined_statement.py                       # Legislative Branch (c01)
    python scripts/probe_combined_statement.py --chapter c02         # any committed chapter

Reads the committed chapter's XLSX verbatim from
tests/fixtures/treasury/combined_statement/cs2025/ and its PDF as a second,
independent rendering. What it does, in order:

  1. Parses every "Appropriation or Fund Account" into one net-outlays figure:
     the Outlays (Net) column of each "Subtotal" row, plus every data row
     after the last Subtotal (an account with a single year of availability
     prints no Subtotal at all; one that also carries "Funds Held Outside the
     Treasury" prints them inside its Subtotal). Each account belongs to the
     unit whose "Total, <unit>" line closes it.
  2. Refuses to report anything unless the chapter's own arithmetic holds to
     the cent: every "Total, <unit>" line equals the sum of its accounts, and
     the unit totals plus the chapter's "Total, Offsetting Receipts" equal
     the chapter total. The 2026-10-21 first version of this probe skipped
     every single-year account and so under-counted the Senate by $10.7m; a
     reconciliation the publisher prints is the check that catches that.
  3. Matches each unit total to a node by canonical_name_key equality. Those
     are the publisher's own figures for the unit.
  4. Matches each account by its title with a trailing ", <issuing body>"
     and a leading "Salaries and Expenses, " or "Compensation of Members and
     Related Administrative Expenses, " set aside -- candidates to TEST
     equality against, never a name to publish -- and REFUSES an account
     whose candidate is the name of the unit whose total closes it. That
     account is one of several the unit holds ("Compensation of Members ...,
     Senate" is $24.4m of the Senate's $1.31bn), and publishing it as the
     unit's figure would be a narrower thing presented as the whole.
  5. Cross-reads every reported figure against the PDF's own text.

This prints a ceiling, not a claim. CURATION.md Sec 22.5 records what blocks
publication: no document read so far states the scale of these figures in
words (the chapter prints a "$" only in a footnote of opening-balance
adjustments), and every match below is a candidate for a reviewed table.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zlib
from decimal import Decimal
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.exporter.build_graph import (  # noqa: E402
    DEFAULT_BASE_GRAPH,
    canonical_name_key,
    index_tree,
    is_post_node,
    load_base_graph,
)
from data_pipeline.verification.congress import read_xlsx_rows  # noqa: E402

FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "treasury" / "combined_statement" / "cs2025"
PUBLISHED_GRAPH = PROJECT_ROOT / "output" / "graph.json"

#: The column the chapter prints "Outlays (Net)" in, by the header rows of the
#: XLSX export (index 9 of 12).
OUTLAYS_COLUMN = 9
#: A data row's second cell is its period of availability or "Subtotal".
PERIOD_PATTERN = re.compile(r"^(\d{4}(-\d{4})?|No Year|Subtotal)$")
STRUCTURAL_LABELS = {"Fund Resources:", "Appropriations, Outlays, and Balances"}
TOTAL_PREFIX = "Total, "
OFFSETTING_TOTAL = "Offsetting Receipts"

TRAILING_ORG_PATTERN = re.compile(r",\s*[^,]+$")
LEADING_LABEL_PATTERN = re.compile(
    r"^(Salaries and Expenses|Compensation of Members and Related Administrative Expenses),\s*",
    re.IGNORECASE,
)


class ReconciliationError(ValueError):
    """The chapter's own printed totals do not equal what was parsed."""


def parse_amount(cell: Any) -> Decimal | None:
    text = str(cell or "").strip()
    if not text or text == "----------":
        return None
    return Decimal(text.replace(",", ""))


def _cells(row: list[Any]) -> list[str]:
    return [str(cell or "") for cell in row]


def parse_chapter(rows: list[list[Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Every account and every "Total, <unit>" line of one chapter.

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

    # Assign each account to the unit total that closes it, and reconcile.
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
    raw = path.read_bytes()
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


def published_cost_status() -> dict[str, tuple[str | None, Any]]:
    if not PUBLISHED_GRAPH.exists():
        return {}
    graph = json.loads(PUBLISHED_GRAPH.read_text())
    status: dict[str, tuple[str | None, Any]] = {}
    stack = [graph]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if node.get("id"):
                status[node["id"]] = (node.get("cost_status"), node.get("resolved_total_amount"))
            stack.extend(node.get("children") or [])
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--chapter", default="c01", help="chapter stem under tests/fixtures/treasury/combined_statement/cs2025/ (default: c01, the Legislative Branch)")
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    args = parser.parse_args(argv[1:] if argv else None)

    xlsx_path = FIXTURE_DIR / f"{args.chapter}.xlsx"
    pdf_path = FIXTURE_DIR / f"{args.chapter}.pdf"
    if not xlsx_path.exists():
        print(f"not fetched: {xlsx_path}")
        return 2

    try:
        accounts, totals = parse_chapter(read_xlsx_rows(xlsx_path))
    except ReconciliationError as error:
        print(f"refused: the chapter's own arithmetic does not hold as parsed -- {error}")
        return 1

    node_map, _ = index_tree(load_base_graph(args.base_graph))
    owners: dict[str, list[str]] = {}
    for node_id, node in node_map.items():
        if not is_post_node(node):
            owners.setdefault(canonical_name_key(node.get("name")), []).append(node_id)
    status = published_cost_status()
    chapter_text = pdf_text(pdf_path) if pdf_path.exists() else ""

    def pdf_flag(amount: Decimal) -> str:
        if not chapter_text:
            return "pdf not read"
        return "pdf agrees" if f"{amount:,.2f}" in chapter_text else "pdf DISAGREES"

    def describe(node_id: str) -> str:
        cost_status, amount = status.get(node_id, (None, None))
        if cost_status is None:
            return "not in published graph"
        if amount is None:
            return f"published {cost_status}"
        return f"published {cost_status} ${amount:,.0f}"

    unit_node: dict[str, str] = {}
    print(f"chapter {args.chapter}: {len(accounts)} accounts in {len(totals) - 1} printed totals; every unit total equals its accounts' sum and the chapter total, to the cent\n")
    print("unit totals the statement prints, matched to exactly one non-post node:")
    for total in totals:
        if total.get("isChapterTotal") or total["unit"] == OFFSETTING_TOTAL:
            continue
        ids = owners.get(canonical_name_key(total["unit"])) or []
        line = f"${total['netOutlays']:>18,.2f}  ({pdf_flag(total['netOutlays'])})  Total, {total['unit']} [{total['accountCount']} accounts]"
        if len(ids) == 1:
            unit_node[total["unit"]] = ids[0]
            print(f"  {ids[0]:42s} {line}  -- {describe(ids[0])}")
        else:
            print(f"  {'(' + str(len(ids)) + ' nodes)':42s} {line}")

    matched, narrower, ambiguous, unmatched = [], [], [], []
    for account in accounts:
        hit_candidate, hit_ids = None, []
        for candidate in strip_candidates(account["title"]):
            ids = owners.get(canonical_name_key(candidate)) or []
            if ids:
                hit_candidate, hit_ids = candidate, ids
                break
        account["candidateName"] = hit_candidate
        if not hit_ids:
            unmatched.append(account)
        elif len(hit_ids) > 1:
            account["nodeIds"] = hit_ids
            ambiguous.append(account)
        elif canonical_name_key(hit_candidate) == canonical_name_key(account["unit"]) or unit_node.get(account["unit"]) == hit_ids[0]:
            account["nodeId"] = hit_ids[0]
            narrower.append(account)
        else:
            account["nodeId"] = hit_ids[0]
            matched.append(account)

    print(f"\naccounts naming a unit below the one whose total closes them, matched to exactly one non-post node: {len(matched)}")
    for a in matched:
        print(f"  {a['nodeId']:42s} ${a['netOutlays']:>18,.2f}  ({pdf_flag(a['netOutlays'])})  {a['title']!r} -- {describe(a['nodeId'])}")

    print(f"\nrefused: the account names the unit whose own total closes it, so it is one account of several, not the unit: {len(narrower)}")
    for a in narrower:
        print(f"  {a['nodeId']:42s} ${a['netOutlays']:>18,.2f}  {a['title']!r} (Total, {a['unit']} is the unit's figure)")

    if ambiguous:
        print(f"\nreaches more than one node (refused): {len(ambiguous)}")
        for a in ambiguous:
            print(f"  {a['title']!r} -> {a['candidateName']!r} -> {a['nodeIds']}")

    print(f"\nno node carries this name, even stripped: {len(unmatched)}")
    for a in unmatched:
        print(f"  ${a['netOutlays']:>18,.2f}  [{a['unit']}]  {a['title']!r}")

    print(
        "\nNothing here is a cost claim: no document read so far states the scale of these\n"
        "figures in words (CURATION.md Sec 22.5), and every match above is a candidate for a\n"
        "reviewed table, not a published identification."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
