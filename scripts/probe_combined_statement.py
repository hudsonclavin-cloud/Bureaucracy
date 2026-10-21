"""Report which Combined Statement accounts match a node, and the figure each carries.

Read-only: nothing in data/verification/ or output/ is written. This is the
diagnostic CURATION.md Sec 22.1/22.2 calls for before any derive script acts on
the Combined Statement of Receipts, Outlays, and Balances -- the same role
scripts/probe_treasury_rows.py plays for the Monthly Treasury Statement.

    python scripts/probe_combined_statement.py                       # Legislative Branch (c01)
    python scripts/probe_combined_statement.py --chapter c02         # any committed chapter

Reads the committed chapter's PDF and XLSX verbatim from
tests/fixtures/treasury/combined_statement/cs2025/ (digests are not pinned
here -- fetch_fixture.py's own .meta.json already carries the sha256 of what
was served). For each "Appropriation or Fund Account" title in the chapter:

  - an account title is stripped of a trailing ", <issuing body>" (the same
    shape positions.archive_title_keys strips from a PLUM title) and, where
    present, a leading "Salaries and Expenses, " prefix, then compared to
    every non-post node's name by canonical_name_key equality;
  - the account's own net outlays is the sum of every "Subtotal" row's
    Outlays (Net) column across however many years of availability the
    account carries;
  - the figure is cross-read out of the chapter's own PDF rendering (the
    same FlateDecode text-run extraction whitehouse_pay.py already uses for
    the White House staff report) as a second, independent reading of the
    same chapter, so a transcription slip in either rendering is visible
    before anything is published from it.

This prints a ceiling, not a claim: nothing here is evidence until a scale
statement for the chapter's own dollar figures is found (checked here against
bof.pdf, coa.pdf, pre.pdf and finhigh.pdf and not found in any of them as of
2026-10-21 -- see CURATION.md Sec 22 for what was checked) and a reviewed
table resolves any name that does not reduce to a node by the generic strip
alone.
"""

from __future__ import annotations

import argparse
import re
import sys
import zlib
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

#: A fund account's title ends in its own owning organisational unit --
#: "Capitol Grounds, Architect of the Capitol" -- the same shape
#: positions.archive_title_keys strips from a PLUM Book title. Stripped here
#: only to TEST equality against a node name, never to produce one.
TRAILING_ORG_PATTERN = re.compile(r",\s*[^,]+$")
LEADING_LABEL_PATTERN = re.compile(r"^(Salaries and Expenses|Compensation of Members and Related Administrative Expenses),\s*", re.IGNORECASE)


def is_title_row(row: list[str]) -> bool:
    return bool(row) and bool(row[0]) and not any(cell for cell in row[1:])


def parse_amount(cell: str) -> float | None:
    cell = (cell or "").strip()
    if not cell or cell == "----------":
        return None
    try:
        return float(cell.replace(",", ""))
    except ValueError:
        return None


def chapter_accounts(rows: list[list[str]]) -> list[dict[str, Any]]:
    """Every account title in one chapter, with its own net-outlays sum.

    An account's own net outlays is the sum of every "Subtotal" row's
    Outlays (Net) column (index 9) across however many years of
    availability the account's one Fund Resources block carries. An account
    with no non-dashed Subtotal figure publishes nothing -- never zero.
    """
    accounts: list[dict[str, Any]] = []
    i = 0
    while i < len(rows):
        row = rows[i]
        if is_title_row(row) and row[0] not in ("Fund Resources:",) and "Fund" not in row[0] and row[0] != "Appropriations, Outlays, and Balances":
            title = row[0]
            total = 0.0
            found = False
            j = i + 1
            while j < len(rows):
                r = rows[j]
                if is_title_row(r) and r[0] != "Fund Resources:":
                    break
                if r and len(r) > 9 and r[1] == "Subtotal":
                    value = parse_amount(r[9])
                    if value is not None:
                        total += value
                        found = True
                j += 1
            if found:
                accounts.append({"title": title, "netOutlays": round(total, 2), "rowIndex": i})
            i = j
            continue
        i += 1
    return accounts


def pdf_text(path: Path) -> str:
    """The chapter's own PDF rendering, as a flat string -- zlib decompress
    every stream and pull the Tj/TJ string operands out directly. Faster
    than whitehouse_pay.extract_text_runs on a file this size and sufficient
    for a substring check: no word-spacing is attempted."""
    raw = path.read_bytes()
    blobs = []
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", raw, re.DOTALL):
        try:
            blobs.append(zlib.decompress(match.group(1)))
        except zlib.error:
            continue
    joined = b"".join(blobs)
    strings = re.findall(rb"\((?:[^()\\]|\\.)*\)", joined)
    text = b"".join(s[1:-1] for s in strings)
    return text.decode("latin-1", "ignore")


def strip_candidates(title: str) -> list[str]:
    """What the account's title reduces to once the issuing-unit suffix and
    an account-type prefix are set aside -- candidates, not a chosen name."""
    candidates = {title}
    no_suffix = TRAILING_ORG_PATTERN.sub("", title).strip()
    if no_suffix and no_suffix != title:
        candidates.add(no_suffix)
    for base in list(candidates):
        no_prefix = LEADING_LABEL_PATTERN.sub("", base).strip()
        if no_prefix and no_prefix != base:
            candidates.add(no_prefix)
    return sorted(candidates, key=len)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--chapter", default="c01", help="chapter stem under tests/fixtures/treasury/combined_statement/cs2025/ (default: c01, the Legislative Branch)")
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--section", default=None, help="only report accounts whose title mentions this (case-insensitive substring)")
    args = parser.parse_args(argv[1:] if argv else None)

    xlsx_path = FIXTURE_DIR / f"{args.chapter}.xlsx"
    pdf_path = FIXTURE_DIR / f"{args.chapter}.pdf"
    if not xlsx_path.exists():
        print(f"not fetched: {xlsx_path}")
        return 2

    rows = read_xlsx_rows(xlsx_path)
    accounts = chapter_accounts(rows)
    if args.section:
        needle = args.section.lower()
        accounts = [a for a in accounts if needle in a["title"].lower()]

    node_map, _ = index_tree(load_base_graph(args.base_graph))
    owners: dict[str, list[str]] = {}
    for node_id, node in node_map.items():
        if is_post_node(node):
            continue
        owners.setdefault(canonical_name_key(node.get("name")), []).append(node_id)

    chapter_text = pdf_text(pdf_path) if pdf_path.exists() else ""

    matched = []
    unmatched = []
    ambiguous = []
    for account in accounts:
        hit_candidate = None
        hit_ids: list[str] = []
        for candidate in strip_candidates(account["title"]):
            ids = owners.get(canonical_name_key(candidate)) or []
            if ids:
                hit_candidate = candidate
                hit_ids = ids
                break
        amount_text = f"{account['netOutlays']:,.2f}"
        in_pdf = amount_text in chapter_text if chapter_text else None
        account["pdfCorroborated"] = in_pdf
        if not hit_ids:
            unmatched.append(account)
        elif len(hit_ids) > 1:
            account["candidateName"] = hit_candidate
            account["nodeIds"] = hit_ids
            ambiguous.append(account)
        else:
            account["candidateName"] = hit_candidate
            account["nodeId"] = hit_ids[0]
            matched.append(account)

    print(f"chapter {args.chapter}: {len(accounts)} accounts with a non-dashed net-outlays figure\n")
    print(f"matched to exactly one non-post node: {len(matched)}")
    for a in matched:
        pdf_flag = "pdf agrees" if a["pdfCorroborated"] else ("pdf DISAGREES" if a["pdfCorroborated"] is False else "pdf not read")
        print(f"  {a['nodeId']:45s} ${a['netOutlays']:>18,.2f}  ({pdf_flag})  {a['title']!r} -> {a['candidateName']!r}")

    if ambiguous:
        print(f"\nreaches more than one node (refused): {len(ambiguous)}")
        for a in ambiguous:
            print(f"  {a['title']!r} -> {a['candidateName']!r} -> {a['nodeIds']}")

    print(f"\nno node carries this name, even stripped: {len(unmatched)}")
    for a in unmatched[:40]:
        print(f"  ${a['netOutlays']:>18,.2f}  {a['title']!r}")
    if len(unmatched) > 40:
        print(f"  ... and {len(unmatched) - 40} more")

    print(
        "\nNothing here is a cost claim: no scale statement for these dollar figures has been\n"
        "found in bof.pdf, coa.pdf, pre.pdf or finhigh.pdf (checked 2026-10-21), and the one\n"
        "name mismatch a strip cannot resolve (if any, above) needs a reviewed row before it\n"
        "can be matched, not a looser rule."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
