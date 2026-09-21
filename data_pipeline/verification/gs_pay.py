"""OPM's General Schedule, SES and SL/ST salary tables, and the one claim each
can honestly make about a position node: a RANGE, never a rate.

`pay_tables.py` prices an Executive Schedule *level*, which the table states
as one figure. The three tables read here state no single figure for anybody:

- **Salary Table 2026-GS** prints, for each of fifteen grades, ten steps of
  annual base pay. A post the PLUM archive files at "GS 15" is somewhere
  between step 1 and step 10, and the table does not say where. What it does
  say, exactly, is the two bounds -- and that they are BASE rates, before the
  locality adjustment that every General Schedule employee in the fifty
  states actually receives on top. So the claim is "the base General Schedule
  range for grade 15 in 2026, before locality pay", and the field carries a
  minimum, a maximum and the words "before locality" rather than a rate.
- **Salary Table No. 2026-ES** states the SES pay system's structure as two
  rows, each a minimum and a maximum: agencies WITH a certified performance
  appraisal system and agencies WITHOUT. The archive says a post is on pay
  plan ES; it does not say which kind of agency employs it. Both rows are
  published as the table prints them.
- **Salary Table No. 2026-SL/ST** does the same for Senior-Level and
  Scientific or Professional positions, with the same two-row shape.

## Why the archive's own rate wins where it states one

Where the archive prints a rate of basic pay for a post ("$225,700" on an ES
row), that is the better statement -- a figure for this post rather than the
band its pay plan allows -- and a range published beside it would be a second
figure for one post, which `pay_tables.py` already refuses ("two rates for one
post"). So a range is published only where the archive gives a pay plan (and,
for GS, a grade) and NO rate. The 46 ES listings that carry a rate keep it and
gain nothing here; the 43 that carry only the pay plan gain the band.

## The scale of the GS table, and why the PDF is the cited document

The HTML rendering of the GS table prints bare integers ("22584") with no
currency mark and no scale phrase anywhere on the page. The PDF rendering of
the same table prints "$  22,584" on grade 1 -- and only on grade 1: every row
beneath is bare ("   25,393"), the ordinary typesetting of a column marked
once at its head. `financial_evidence` can vouch for grade 1 from that and for
nothing else, so a fourth, narrower scale rule was added for exactly this
shape (`COLUMN_HEAD_MARK_SOURCE_TYPES`): the record quotes the column's first
figure with its mark and its own bare figure, the validator checks that shape,
this module guarantees the two sit in one column, and the release gate
re-reads the committed table. The PDF is therefore the document every GS
record cites; the HTML is fetched and committed too, and the loader refuses to
return a table unless the two renderings agree on all 150 figures, so a
mis-read PDF cell can never be published on the strength of the HTML or the
other way round.

## What every record is, and is not

`scopeMatch` is `proxy` on every record -- the table names a grade or a pay
system, never this post -- so `financial_evidence.classify` grades each
`partial` and no route makes one `verified`. A range is not this unit's cost:
nothing here writes a cost field, and the gate refuses the block beside a
measured cost. And it is not evidence that the post exists: nothing here
writes `sourceUrls`, `sourceTypes`, `lastVerified` or `verificationMethod`,
the channel by which a five-row table carried 29 positions to `verified` on
2026-09-11. The field lives only while `positionListing` still reports the
same pay plan (and grade), exactly as `positionPayRate` is tied to its level.
"""

from __future__ import annotations

import hashlib
import json
import re
import zlib
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping

from data_pipeline.exporter.build_graph import is_post_node
from data_pipeline.verification.pay_tables import (
    ExecutiveScheduleParser,
    Unreadable,
    _EFFECTIVE,
    _MONTHS,
    _collapse,
    federal_fiscal_year_of,
)

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "opm" / "pay"
DEFAULT_GS_PDF = FIXTURE_DIR / "general_schedule_2026.pdf"
DEFAULT_GS_HTML = FIXTURE_DIR / "general_schedule_2026.html"
DEFAULT_SES_HTML = FIXTURE_DIR / "senior_executive_service_2026.html"
DEFAULT_SLST_HTML = FIXTURE_DIR / "senior_level_2026.html"
DEFAULT_EVIDENCE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "verification" / "grade_pay_evidence.json"
)

SOURCE = "opm_salary_table_range"
SOURCE_TYPE = "opm_pay_table"

#: The three kinds of range this module publishes, keyed by the archive's pay
#: plan codes. `ST` shares the SL/ST table with `SL`.
KIND_GS = "general_schedule_grade"
KIND_SES = "senior_executive_service"
KIND_SLST = "senior_level"
KINDS = (KIND_GS, KIND_SES, KIND_SLST)
PAY_PLANS_BY_KIND = {KIND_GS: ("GS",), KIND_SES: ("ES",), KIND_SLST: ("SL", "ST")}
METHOD_BY_KIND = {
    KIND_GS: "base_range_for_the_grade_reported_in_the_plum_archive",
    KIND_SES: "pay_system_range_for_the_pay_plan_reported_in_the_plum_archive",
    KIND_SLST: "pay_system_range_for_the_pay_plan_reported_in_the_plum_archive",
}

#: The General Schedule has fifteen grades and ten steps. A table printing a
#: sixteenth grade or an eleventh step has been restructured.
GENERAL_SCHEDULE_GRADES = tuple(str(i) for i in range(1, 16))
GENERAL_SCHEDULE_STEPS = 10

#: The words the panel prints beside every GS range. Base pay is what the
#: table states; the locality adjustment the post's holder receives is not
#: in it, and the field says so rather than leaving a reader to assume the
#: range is what anybody is paid.
GS_BASE_BEFORE_LOCALITY = (
    "base General Schedule rates before locality pay; the table states no locality adjustment"
)

_MONEY_CELL = re.compile(r"^(\$)?\s*([0-9][0-9,]*)$")
_GS_TABLE_HEADING = re.compile(r"^Salary Table\s+(\d{4}-GS)$", re.IGNORECASE)
_STRUCTURE_TABLE_HEADING = re.compile(r"^Salary Table No\.\s*(\S+)$", re.IGNORECASE)
_RATES_HEADING = "annual rates by grade and step"


# ---------------------------------------------------------------------------
# The GS table, PDF rendering: the document every GS record cites.


def _pdf_text_blocks(raw: bytes) -> list[str]:
    """Every `BT ... ET` block's text, in stream order, with the literal
    strings of a `TJ` array joined and its kerning numbers dropped.

    The same stdlib-only reading `whitehouse_pay.extract_text_runs` does; a
    separate, simpler routine because this document is tagged and sets each
    table cell in a block of its own, so the block order IS the cell order.
    Refuses an encrypted file rather than reading ciphertext out of it.
    """
    if not raw.startswith(b"%PDF"):
        raise Unreadable("the file is not a PDF")
    if b"/Encrypt" in raw:
        raise Unreadable("the PDF is encrypted; nothing is read out of ciphertext")
    out: list[str] = []
    for stream in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", raw, re.S):
        try:
            data = zlib.decompress(stream.group(1))
        except zlib.error:
            continue
        for block in re.findall(rb"BT(.*?)ET", data, re.S):
            parts: list[bytes] = []
            for op in re.finditer(rb"\[(.*?)\]\s*TJ|\((.*?)\)\s*Tj", block, re.S):
                if op.group(1) is not None:
                    parts.append(b"".join(re.findall(rb"\((.*?)\)", op.group(1))))
                else:
                    parts.append(op.group(2))
            if parts:
                out.append(b"".join(parts).decode("latin-1"))
    return out


def _money(cell: str) -> tuple[bool, str, float]:
    """(carries the mark, digits as printed, amount) or Unreadable."""
    match = _MONEY_CELL.match(cell.strip())
    if not match:
        raise Unreadable(f"cell {cell!r} is not a figure this parser will read")
    digits = match.group(2)
    amount = float(digits.replace(",", ""))
    if amount <= 0:
        raise Unreadable(f"cell {cell!r} is not a positive figure")
    return bool(match.group(1)), digits, amount


def _effective(text: str) -> tuple[str, str]:
    match = _EFFECTIVE.match(text)
    if not match:
        raise Unreadable(f"heading {text!r} is not an 'Effective <Month> <Year>' heading")
    month_name, year_text = match.groups()
    month = _MONTHS.get(month_name.casefold())
    if month is None:
        raise Unreadable(f"effective heading {text!r} names no month this parser knows")
    return text, date(int(year_text), month, 1).isoformat()


def parse_general_schedule_pdf(raw: bytes) -> dict[str, Any]:
    """The GS table as the PDF prints it, or `Unreadable`.

    Read by shape and refused on any irregularity: the four headings, the
    twelve column heads, then fifteen rows of a grade, ten figures and a
    within-grade-increase cell. Every grade once, in order; step 1 never above
    step 10; and the FIRST row must carry the currency mark on every step,
    because that mark is the only thing on the page that states the scale.
    """
    blocks = [b.strip() for b in _pdf_text_blocks(raw)]
    blocks = [b for b in blocks if b]
    if len(blocks) < 4:
        raise Unreadable("the PDF carries too little text to be a salary table")
    table_match = _GS_TABLE_HEADING.match(blocks[0])
    if not table_match:
        raise Unreadable(f"the first heading is {blocks[0]!r}, not 'Salary Table <year>-GS'")
    table = f"Salary Table {table_match.group(1).upper()}"
    effective_text = ""
    rates_at = None
    for i, text in enumerate(blocks[1:5], start=1):
        if _EFFECTIVE.match(text):
            effective_text = text
        if text.casefold() == _RATES_HEADING:
            rates_at = i
    if not effective_text:
        raise Unreadable("no 'Effective <Month> <Year>' heading above the table; an undated range is not evidence")
    if rates_at is None:
        raise Unreadable("no 'Annual Rates by Grade and Step' heading; this is not the annual table")
    effective_text, effective = _effective(effective_text)

    heads = blocks[rates_at + 1 : rates_at + 1 + GENERAL_SCHEDULE_STEPS + 2]
    expected_heads = ["Grade"] + [f"Step {n}" for n in range(1, GENERAL_SCHEDULE_STEPS + 1)]
    if [h.casefold() for h in heads[: GENERAL_SCHEDULE_STEPS + 1]] != [h.casefold() for h in expected_heads]:
        raise Unreadable(f"the column heads are {heads!r}, not {expected_heads!r} plus a WGI column; the table has been reshaped")
    wgi_head = heads[GENERAL_SCHEDULE_STEPS + 1] if len(heads) > GENERAL_SCHEDULE_STEPS + 1 else ""
    if not wgi_head:
        raise Unreadable("no within-grade-increase column head after Step 10")

    cells = blocks[rates_at + 1 + GENERAL_SCHEDULE_STEPS + 2 :]
    row_width = GENERAL_SCHEDULE_STEPS + 2
    if len(cells) != row_width * len(GENERAL_SCHEDULE_GRADES):
        raise Unreadable(
            f"{len(cells)} cells after the column heads; fifteen rows of a grade, ten steps and a "
            f"WGI cell would be {row_width * len(GENERAL_SCHEDULE_GRADES)}"
        )
    grades: dict[str, dict[str, Any]] = {}
    column_heads: dict[str, dict[str, str]] = {}
    for index, grade in enumerate(GENERAL_SCHEDULE_GRADES):
        row = cells[index * row_width : (index + 1) * row_width]
        if row[0] != grade:
            raise Unreadable(f"row {index + 1} is headed {row[0]!r}, not grade {grade}; the grades are not in order")
        steps: list[dict[str, Any]] = []
        for step_index, cell in enumerate(row[1 : 1 + GENERAL_SCHEDULE_STEPS], start=1):
            marked, digits, amount = _money(cell)
            steps.append({"step": step_index, "amount": amount, "amountRaw": digits, "text": cell, "marked": marked})
            if index == 0:
                if not marked:
                    raise Unreadable(
                        f"grade 1, step {step_index} prints {cell!r} with no currency mark; the first row is "
                        "the only place this table states its scale, and it does not"
                    )
                column_heads[f"Step {step_index}"] = {"column": f"Step {step_index}", "text": cell, "amountRaw": digits}
        if steps[0]["amount"] > steps[-1]["amount"]:
            raise Unreadable(f"grade {grade} prints step 1 above step 10; that is not a range")
        grades[grade] = {
            "grade": grade,
            "minimum": steps[0]["amount"],
            "minimumRaw": steps[0]["amountRaw"],
            "minimumText": steps[0]["text"],
            "maximum": steps[-1]["amount"],
            "maximumRaw": steps[-1]["amountRaw"],
            "maximumText": steps[-1]["text"],
            "steps": [s["amount"] for s in steps],
            "withinGradeIncrease": row[-1],
            "rowText": _collapse(" ".join(row)),
        }
    return {
        "source": SOURCE,
        "kind": KIND_GS,
        "table": table,
        "effectiveText": effective_text,
        "effective": effective,
        "effectiveFrom": "first of the month named in the heading, derived",
        "ratesHeading": blocks[rates_at],
        "grades": grades,
        "columnHeads": column_heads,
        "wgiHead": wgi_head,
        # The PDF prints no note beneath the table. Carried as an empty list
        # rather than omitted, so the gate can require the field and refuse a
        # note attributed to a page that prints none.
        "footnotes": [],
    }


# ---------------------------------------------------------------------------
# The GS table, HTML rendering: corroboration, never the cited document.


class _GeneralScheduleHtmlParser(HTMLParser):
    """The DataTable's rows and every `<p>` before it inside the table's
    own container. The GS page sets its headings as paragraphs, not `<h2>`."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.paragraphs: list[str] = []
        self.columns: list[str] = []
        self.rows: list[list[str]] = []
        self.data_tables = 0
        self._in_table = False
        self._in_thead = False
        self._para: list[str] | None = None
        self._cell: list[str] | None = None
        self._row: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {k: (v or "") for k, v in attrs}
        if tag == "table":
            if "DataTable" in attributes.get("class", "").split():
                self.data_tables += 1
                self._in_table = True
            return
        if tag == "p" and not self._in_table:
            self._para = []
            return
        if not self._in_table:
            return
        if tag == "thead":
            self._in_thead = True
        elif tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "p" and self._para is not None and not self._in_table:
            text = _collapse("".join(self._para))
            if text:
                self.paragraphs.append(text)
            self._para = None
            return
        if tag == "table":
            self._in_table = False
            return
        if not self._in_table:
            return
        if tag == "thead":
            self._in_thead = False
        elif tag in ("td", "th") and self._cell is not None:
            text = _collapse("".join(self._cell))
            if self._in_thead:
                self.columns.append(text)
            elif self._row is not None:
                self._row.append(text)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(list(self._row))
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)
        elif self._para is not None:
            self._para.append(data)


def parse_general_schedule_html(html: str) -> dict[str, Any]:
    """The same table from the HTML page: grade -> ten step figures, plus the
    table's number and effective heading. Used only to corroborate the PDF."""
    parser = _GeneralScheduleHtmlParser()
    parser.feed(html)
    parser.close()
    if parser.data_tables != 1:
        raise Unreadable(f"{parser.data_tables} tables classed DataTable; this parser reads a page with one")
    table = ""
    effective_text = ""
    for text in parser.paragraphs:
        match = _GS_TABLE_HEADING.match(text)
        if match:
            table = f"Salary Table {match.group(1).upper()}"
        if _EFFECTIVE.match(text):
            effective_text = text
    if not table or not effective_text:
        raise Unreadable("the HTML page does not carry both the table's number and its effective heading")
    expected = ["grade"] + [f"step {n}" for n in range(1, GENERAL_SCHEDULE_STEPS + 1)] + ["wgi"]
    if [c.casefold() for c in parser.columns] != expected:
        raise Unreadable(f"the HTML table's columns are {parser.columns!r}; it has been reshaped")
    grades: dict[str, list[float]] = {}
    for row in parser.rows:
        if len(row) != GENERAL_SCHEDULE_STEPS + 2:
            raise Unreadable(f"HTML row {row!r} does not have a grade, ten steps and a WGI cell")
        grade = row[0]
        if grade not in GENERAL_SCHEDULE_GRADES or grade in grades:
            raise Unreadable(f"HTML row headed {grade!r} is not one grade printed once")
        grades[grade] = [_money(cell)[2] for cell in row[1 : 1 + GENERAL_SCHEDULE_STEPS]]
    if set(grades) != set(GENERAL_SCHEDULE_GRADES):
        raise Unreadable("the HTML table does not print all fifteen grades")
    return {"table": table, "effectiveText": effective_text, "grades": grades}


# ---------------------------------------------------------------------------
# The SES and SL/ST tables: two rows of a minimum and a maximum.


def parse_pay_structure_table(html: str, *, expected_suffix: str) -> dict[str, Any]:
    """The 'Structure of the ... Pay System' table as the page prints it.

    Same page template as the Executive Schedule table, so the same parser
    reads the headings, the DataTable and the footnotes; what differs is the
    shape of the rows, which is checked here. `expected_suffix` is "ES" or
    "SL/ST": the table number must end in it, so the SL/ST page can never be
    read as the SES page although the two print identical figures.
    """
    parser = ExecutiveScheduleParser()
    parser.feed(html)
    parser.close()
    parser._close_footnote()
    if not parser.rows:
        raise Unreadable("no rows found in a table classed DataTable")
    if parser.data_tables > 1:
        raise Unreadable(f"{parser.data_tables} tables classed DataTable; this parser reads a page with one")
    columns = [c.casefold() for c in parser.columns]
    if len(columns) != 3 or not columns[0].startswith("structure of the") or columns[1:] != ["minimum", "maximum"]:
        raise Unreadable(f"the table's columns are {parser.columns!r}, not a structure, a minimum and a maximum")
    above = parser.headings[: parser.headings_before_table or 0]
    number = ""
    effective_text = ""
    for heading in above:
        if _STRUCTURE_TABLE_HEADING.match(heading):
            number = heading
        if _EFFECTIVE.match(heading):
            effective_text = heading
    if not number:
        raise Unreadable("no 'Salary Table No. ...' heading above the table; an unnumbered table is not citable")
    if not number.upper().endswith("-" + expected_suffix.upper()):
        raise Unreadable(f"the table is {number!r}, not the {expected_suffix} table this loader was asked for")
    if not effective_text:
        raise Unreadable("no 'Effective <Month> <Year>' heading above the table; an undated range is not evidence")
    effective_text, effective = _effective(effective_text)
    rows: list[dict[str, Any]] = []
    for row in parser.rows:
        if len(row["cells"]) != 3:
            raise Unreadable(f"row {row['text']!r} does not have exactly a label, a minimum and a maximum")
        label_cell, low_cell, high_cell = row["cells"]
        low_marked, low_raw, low = _money(low_cell)
        high_marked, high_raw, high = _money(high_cell)
        if not (low_marked and high_marked):
            raise Unreadable(f"row {row['text']!r} prints a bound without its currency mark")
        if low > high:
            raise Unreadable(f"row {row['text']!r} prints a minimum above its maximum")
        if not label_cell:
            raise Unreadable("a structure row carries no label")
        rows.append({
            "label": label_cell,
            "minimum": low, "minimumRaw": low_raw, "minimumText": low_cell,
            "maximum": high, "maximumRaw": high_raw, "maximumText": high_cell,
            "rowText": row["text"],
        })
    if len(rows) != 2:
        raise Unreadable(f"the table prints {len(rows)} structure rows; the pay system has two (certified and not)")
    labels = [r["label"].casefold() for r in rows]
    if not (labels[0].startswith("agencies with a certified") and labels[1].startswith("agencies without a certified")):
        raise Unreadable(f"the rows are {[r['label'] for r in rows]!r}, not the certified / not-certified pair")
    if rows[0]["minimum"] != rows[1]["minimum"]:
        raise Unreadable("the two rows print different minimums; the pay system's floor is not decidable")
    return {
        "source": SOURCE,
        "table": number,
        "effectiveText": effective_text,
        "effective": effective,
        "effectiveFrom": "first of the month named in the heading, derived",
        "columns": list(parser.columns),
        "rows": rows,
        "minimum": rows[0]["minimum"],
        "maximum": max(r["maximum"] for r in rows),
        "footnotes": list(parser.footnotes),
    }


# ---------------------------------------------------------------------------
# Loading, with the digest recomputed before anything is read.


def _load_fixture(path: str | Path) -> dict[str, Any]:
    """The bytes on disk and the provenance their `.meta.json` recorded, or
    `Unreadable` -- the same refusal `pay_tables.load_executive_schedule`
    makes, for the same reason: a `documentSha256` is a claim that this figure
    came out of that document, and re-hashing an edited file would launder
    exactly the edit the check exists to catch."""
    file_path = Path(path)
    meta_path = file_path.with_name(file_path.name + ".meta.json")
    if not meta_path.exists():
        raise Unreadable(f"{file_path.name} has no .meta.json beside it; a table with no record of its fetch cannot be cited")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    raw = file_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    recorded = str(meta.get("sha256") or "").lower()
    if not recorded:
        raise Unreadable(f"{meta_path.name} records no sha256; the fetch it describes served nothing")
    if digest != recorded:
        raise Unreadable(
            f"{file_path.name} does not match the digest its fetch recorded ({digest} vs {recorded}); "
            "the committed file is not the file that was served"
        )
    url = str(meta.get("url") or "")
    fetched_at = str(meta.get("fetched_at") or "")
    if not url or not fetched_at:
        raise Unreadable(f"{meta_path.name} is missing the url or the fetch time")
    if meta.get("error") or int(meta.get("status") or 0) != 200:
        raise Unreadable(f"{meta_path.name} records a fetch that did not serve the page")
    final_url = str(meta.get("final_url") or url)
    if final_url.rstrip("/") != url.rstrip("/"):
        # The first attempt at the SES table "succeeded" by redirecting to
        # OPM's homepage. A fetch that landed somewhere else served some
        # other page, whatever its status code said.
        raise Unreadable(f"{meta_path.name} records a redirect to {final_url!r}; the page fetched is not the page cited")
    return {"raw": raw, "url": url, "fetched_at": fetched_at, "sha256": digest, "file": str(file_path)}


def load_general_schedule(
    pdf_path: str | Path = DEFAULT_GS_PDF, html_path: str | Path = DEFAULT_GS_HTML
) -> dict[str, Any]:
    """The GS table from the PDF, corroborated cell for cell by the HTML.

    Both are the publisher's own renderings of one table; the PDF is cited
    because it is the one that states the scale. They must agree on the
    table's number, its effective heading and every one of the 150 step
    figures, or nothing is returned.
    """
    pdf = _load_fixture(pdf_path)
    page = _load_fixture(html_path)
    table = parse_general_schedule_pdf(pdf["raw"])
    html_table = parse_general_schedule_html(page["raw"].decode("utf-8", errors="replace"))
    if html_table["table"] != table["table"] or html_table["effectiveText"] != table["effectiveText"]:
        raise Unreadable(
            f"the PDF is {table['table']} ({table['effectiveText']}) and the HTML page is "
            f"{html_table['table']} ({html_table['effectiveText']}); they are not one table"
        )
    for grade, row in table["grades"].items():
        if html_table["grades"].get(grade) != row["steps"]:
            raise Unreadable(
                f"grade {grade}: the PDF prints {row['steps']} and the HTML page prints "
                f"{html_table['grades'].get(grade)}; the two renderings disagree and neither is trusted"
            )
    return {
        "table": table,
        "url": pdf["url"],
        "fetched_at": pdf["fetched_at"],
        "sha256": pdf["sha256"],
        "file": pdf["file"],
        "corroboration": {
            "url": page["url"],
            "fetched_at": page["fetched_at"],
            "sha256": page["sha256"],
            "file": page["file"],
            "agrees": "every one of the 150 step figures, the table number and the effective heading",
        },
    }


def load_pay_structure(path: str | Path, *, kind: str) -> dict[str, Any]:
    suffix = {KIND_SES: "ES", KIND_SLST: "SL/ST"}[kind]
    loaded = _load_fixture(path)
    table = parse_pay_structure_table(loaded["raw"].decode("utf-8", errors="replace"), expected_suffix=suffix)
    table["kind"] = kind
    return {"table": table, "url": loaded["url"], "fetched_at": loaded["fetched_at"], "sha256": loaded["sha256"], "file": loaded["file"]}


def load_all_tables(
    *,
    gs_pdf: str | Path = DEFAULT_GS_PDF,
    gs_html: str | Path = DEFAULT_GS_HTML,
    ses_html: str | Path = DEFAULT_SES_HTML,
    slst_html: str | Path = DEFAULT_SLST_HTML,
) -> dict[str, dict[str, Any]]:
    return {
        KIND_GS: load_general_schedule(gs_pdf, gs_html),
        KIND_SES: load_pay_structure(ses_html, kind=KIND_SES),
        KIND_SLST: load_pay_structure(slst_html, kind=KIND_SLST),
    }


def load_evidence(path: str | Path = DEFAULT_EVIDENCE_PATH) -> dict[str, dict[str, Any]]:
    """The derived records, or nothing. A missing file is not an error."""
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        loaded = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    nodes = loaded.get("nodes") if isinstance(loaded, dict) else None
    return nodes if isinstance(nodes, dict) else {}


# ---------------------------------------------------------------------------
# Eligibility and records.


def _listing_of(record: Mapping[str, Any]) -> tuple[str, str]:
    return str(record.get("payPlan") or "").strip(), str(record.get("payLevel") or "").strip()


def kind_for_pay_plan(pay_plan: str) -> str | None:
    for kind, plans in PAY_PLANS_BY_KIND.items():
        if pay_plan in plans:
            return kind
    return None


def eligible(record: Mapping[str, Any], tables: Mapping[str, Mapping[str, Any]]) -> tuple[bool, str]:
    """Whether the archive's report of this post can be given a range.

    The archive's own rate wins where it states one; a pay plan with no
    table here is refused with its code in the reason; a GS listing needs a
    grade the table prints, on one archive row with the plan; an ES or SL/ST
    listing must carry NO level, because those systems have none and a row
    printing one is a row this module does not understand.
    """
    pay_plan, level = _listing_of(record)
    if record.get("reportedPay") is not None:
        return False, "archive_reports_a_rate"
    if record.get("anyListingReportsRate"):
        # The OTHER PLUM listing on this node states a rate
        # (plum_current.combine_listings marks it); a range beside it is a
        # second figure for one post.
        return False, "a_listing_reports_a_rate"
    if not pay_plan:
        return False, "no_pay_plan_reported"
    kind = kind_for_pay_plan(pay_plan)
    if kind is None:
        return False, f"pay_plan_{pay_plan.casefold()}_has_no_table_here"
    if kind not in tables:
        return False, f"no_{kind}_table_loaded"
    if kind == KIND_GS:
        if not level:
            return False, "no_grade_reported"
        if level not in tables[kind]["grades"]:
            return False, f"grade_{level}_is_not_printed_in_this_table"
        if not record.get("payPlanAndLevelOnOneRow"):
            return False, "pay_plan_and_grade_never_printed_on_one_row"
        return True, "listed_at_a_general_schedule_grade"
    if level:
        return False, f"{kind}_listing_carries_a_level"
    return True, f"listed_on_the_{kind}_pay_plan"


def listing_claim(record: Mapping[str, Any]) -> dict[str, Any]:
    pay_plan, level = _listing_of(record)
    return {
        "payPlan": pay_plan,
        "payLevel": level or None,
        "listedTitle": record.get("listedTitle"),
        "source": record.get("source"),
        "edition": record.get("edition"),
        "period": record.get("period"),
        "url": record.get("url"),
        "checkedAt": record.get("checkedAt"),
        "valuesFrom": record.get("valuesFrom"),
    }


def _bound_record(
    node_id: str, *, amount: float, amount_raw: str, quote: str, units_evidence: str,
    scope: str, table: Mapping[str, Any], loaded: Mapping[str, Any], locator: Mapping[str, Any],
    column_head: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """One bound, in the shape `financial_evidence.validate_record` checks.

    Each bound of a range goes through the validator on its own -- the
    minimum and the maximum are two figures the document prints, and each
    must be shown to be the one it prints, with the scale it states.
    """
    effective = date.fromisoformat(str(table["effective"]))
    record = {
        "nodeId": node_id,
        "financialEvidenceStatus": "partial",
        "costBasis": "basic_pay",
        "amount": float(amount),
        "amountRaw": amount_raw,
        "units": "usd",
        "normalizedMultiplier": 1,
        "unitsEvidence": units_evidence,
        "quote": quote,
        "fiscalYear": federal_fiscal_year_of(effective),
        "periodCoverage": "annual_rate",
        "periodAsOf": table["effective"],
        "amountScope": scope,
        "scopeMatch": "proxy",
        "rollupRole": "line",
        "sourceType": SOURCE_TYPE,
        "sourceUrl": loaded["url"],
        "documentSha256": loaded["sha256"],
        "retrievedAt": loaded["fetched_at"],
        "locator": dict(locator),
    }
    if column_head is not None:
        record["columnHead"] = dict(column_head)
    return record


def build_records(
    listings: Mapping[str, Mapping[str, Any]],
    tables: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """A range record for every position a table can bound.

    `tables` maps a kind to what `load_general_schedule` / `load_pay_structure`
    returned. Each record carries its bounds as separate validator-shaped
    records under `bounds`; the caller validates every one against its node.
    """
    records: dict[str, dict[str, Any]] = {}
    refusals: dict[str, int] = {}
    parsed = {kind: loaded["table"] for kind, loaded in tables.items()}
    for node_id, listing in sorted(listings.items()):
        ok, reason = eligible(listing, parsed)
        if not ok:
            refusals[reason] = refusals.get(reason, 0) + 1
            continue
        pay_plan, level = _listing_of(listing)
        kind = kind_for_pay_plan(pay_plan)
        loaded = tables[kind]
        table = loaded["table"]
        common = {
            "nodeId": node_id,
            "kind": kind,
            "payPlan": pay_plan,
            "financialEvidenceStatus": "partial",
            "costBasis": "basic_pay",
            "scopeMatch": "proxy",
            "sourceType": SOURCE_TYPE,
            "sourceUrl": loaded["url"],
            "documentSha256": loaded["sha256"],
            "retrievedAt": loaded["fetched_at"],
            "table": table["table"],
            "effectiveText": table["effectiveText"],
            "periodAsOf": table["effective"],
            "fiscalYear": federal_fiscal_year_of(date.fromisoformat(str(table["effective"]))),
            "tableFootnotes": list(table.get("footnotes") or []),
            "listingClaim": listing_claim(listing),
        }
        if kind == KIND_GS:
            row = table["grades"][level]
            scope = f"Grade {level}, step 1 to step {GENERAL_SCHEDULE_STEPS}"
            heads = table["columnHeads"]
            bounds = {}
            for name, step, key in (("minimum", 1, "minimum"), ("maximum", GENERAL_SCHEDULE_STEPS, "maximum")):
                head = heads[f"Step {step}"]
                raw = row[f"{key}Raw"]
                # The column's first figure with its mark, this row's figure
                # without one, and the column named -- the shape the fourth
                # scale rule checks. Grade 1's own row IS the head, and its
                # marked figure satisfies the stronger rule instead.
                units_evidence = f"Step {step} column: {head['text']} at grade 1; {row[f'{key}Text']} at grade {level}"
                bounds[name] = _bound_record(
                    node_id, amount=row[key], amount_raw=raw, quote=row["rowText"],
                    units_evidence=units_evidence, scope=scope, table=table, loaded=loaded,
                    locator={"table": table["table"], "row": f"Grade {level}", "column": f"Step {step}"},
                    column_head=head,
                )
            records[node_id] = {
                **common,
                "grade": level,
                "amountScope": scope,
                "quote": row["rowText"],
                "minimum": row["minimum"], "minimumRaw": row["minimumRaw"],
                "maximum": row["maximum"], "maximumRaw": row["maximumRaw"],
                "steps": list(row["steps"]),
                "withinGradeIncrease": row["withinGradeIncrease"],
                "baseBeforeLocality": GS_BASE_BEFORE_LOCALITY,
                "bounds": bounds,
                "corroboration": dict(loaded["corroboration"]),
            }
        else:
            rows = table["rows"]
            system = "Senior Executive Service" if kind == KIND_SES else "Senior-Level and Scientific or Professional"
            scope = f"{system} pay system, {rows[0]['label']} / {rows[1]['label']}"
            bounds = {}
            for name, row, key in (
                ("minimum", rows[0], "minimum"),
                ("maximumWithCertifiedSystem", rows[0], "maximum"),
                ("maximumWithoutCertifiedSystem", rows[1], "maximum"),
            ):
                bounds[name] = _bound_record(
                    node_id, amount=row[key], amount_raw=row[f"{key}Raw"], quote=row["rowText"],
                    units_evidence=row["rowText"], scope=scope, table=table, loaded=loaded,
                    locator={"table": table["table"], "row": row["label"], "column": key.capitalize()},
                    column_head=None,
                )
            records[node_id] = {
                **common,
                "grade": None,
                "amountScope": scope,
                "quote": " | ".join(r["rowText"] for r in rows),
                "minimum": table["minimum"], "minimumRaw": rows[0]["minimumRaw"],
                "maximum": table["maximum"], "maximumRaw": rows[0]["maximumRaw"],
                "rows": [
                    {"label": r["label"], "minimum": r["minimum"], "minimumRaw": r["minimumRaw"],
                     "maximum": r["maximum"], "maximumRaw": r["maximumRaw"], "rowText": r["rowText"]}
                    for r in rows
                ],
                "bounds": bounds,
            }
    report = {
        "source": SOURCE,
        "tables": {
            kind: {"table": loaded["table"]["table"], "effectiveText": loaded["table"]["effectiveText"],
                   "url": loaded["url"], "documentSha256": loaded["sha256"], "retrievedAt": loaded["fetched_at"]}
            for kind, loaded in tables.items()
        },
        "listings_considered": len(listings),
        "ranged": len(records),
        "refused": dict(sorted(refusals.items())),
        "ranged_by_kind": {kind: sum(1 for r in records.values() if r["kind"] == kind) for kind in KINDS},
        "ranged_by_grade": dict(sorted(
            ((r["grade"], sum(1 for x in records.values() if x["grade"] == r["grade"]))
             for r in records.values() if r["grade"]),
        )),
    }
    return records, report


# ---------------------------------------------------------------------------
# Applying to the tree.


def apply_grade_pay(
    root: dict[str, Any],
    records: Mapping[str, Mapping[str, Any]],
    *,
    index_tree: Any = None,
) -> dict[str, Any]:
    """Stamp `positionGradePay` on every position whose published listing
    still reports the pay plan (and grade) the record was derived from.

    The dependency is the safety rule and it mirrors `positionPayRate`'s: a
    range is only meaningful as a gloss on the archive's pay plan, so it is
    published only where that listing is itself published and still says the
    same thing. If `positions.py` withdraws or changes the listing, the range
    goes with it rather than outliving the claim it rests on.
    """
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, _ = index_tree(root)
    stats = {
        "ranged": 0,
        "ranged_by_kind": {kind: 0 for kind in KINDS},
        "unknown_node": 0,
        "not_a_position": 0,
        "no_listing_published": 0,
        "listing_reports_a_different_plan_or_grade": 0,
        "listing_reports_a_rate": 0,
        "stands_for_many_posts": 0,
        "bounds_not_validated": 0,
    }
    for node_id, record in sorted(records.items()):
        node = node_map.get(node_id)
        if node is None:
            stats["unknown_node"] += 1
            continue
        if not is_post_node(node):
            stats["not_a_position"] += 1
            continue
        if node.get("representsPosts"):
            stats["stands_for_many_posts"] += 1
            continue
        kind = str(record.get("kind") or "")
        claim = record.get("listingClaim") or {}
        # Which document reported the pay plan: the archive's listing or the
        # current export's (positions.LISTING_FIELD_BY_SOURCE). The range is
        # tied to that listing and withdrawn with it, never the other one.
        from data_pipeline.verification.positions import any_listing_reports_a_rate, listing_field_for

        listing = node.get(listing_field_for(claim.get("source")) or "positionListing")
        if not isinstance(listing, Mapping):
            stats["no_listing_published"] += 1
            continue
        if listing.get("reportedPay") is not None or any_listing_reports_a_rate(node):
            stats["listing_reports_a_rate"] += 1
            continue
        listed_plan = str(listing.get("payPlan") or "")
        listed_level = str(listing.get("payLevel") or "")
        if kind not in KINDS or listed_plan != str(claim.get("payPlan") or "") or listed_plan not in PAY_PLANS_BY_KIND[kind]:
            stats["listing_reports_a_different_plan_or_grade"] += 1
            continue
        if kind == KIND_GS:
            if listed_level != str(record.get("grade") or "") or not listing.get("payPlanAndLevelOnOneRow"):
                stats["listing_reports_a_different_plan_or_grade"] += 1
                continue
        elif listed_level:
            stats["listing_reports_a_different_plan_or_grade"] += 1
            continue

        bounds = record.get("bounds") or {}
        units_kinds = sorted({str(b.get("unitsEvidenceKind") or "") for b in bounds.values() if isinstance(b, Mapping)})
        if not bounds or len(units_kinds) != 1 or not units_kinds[0]:
            # `unitsEvidenceKind` is written by financial_evidence.validate_record
            # and by nothing else, so a record whose bounds lack it -- or whose
            # bounds rest on different rules -- never went through the
            # validator as one range. The derive script is the only producer
            # and always validates; a hand-edited or stale file is what this
            # refuses.
            stats["bounds_not_validated"] += 1
            continue
        block: dict[str, Any] = {
            "source": SOURCE,
            "method": METHOD_BY_KIND[kind],
            "kind": kind,
            "payPlan": listed_plan,
            "grade": record.get("grade"),
            "minimum": record.get("minimum"),
            "minimumPrinted": record.get("minimumRaw"),
            "maximum": record.get("maximum"),
            "maximumPrinted": record.get("maximumRaw"),
            "table": record.get("table"),
            "effectiveText": record.get("effectiveText"),
            "effective": record.get("periodAsOf"),
            "fiscalYear": record.get("fiscalYear"),
            "costBasis": record.get("costBasis"),
            "scopeMatch": record.get("scopeMatch"),
            "financialEvidenceStatus": record.get("financialEvidenceStatus"),
            "amountScope": record.get("amountScope"),
            "quote": record.get("quote"),
            "unitsEvidenceKind": units_kinds[0] if len(units_kinds) == 1 else units_kinds,
            "footnotes": list(record.get("tableFootnotes") or []),
            "listingSource": {
                "source": claim.get("source"),
                "edition": claim.get("edition"),
                "period": claim.get("period"),
                "listedTitle": claim.get("listedTitle"),
                "url": claim.get("url"),
                "checkedAt": claim.get("checkedAt"),
            },
            "url": record.get("sourceUrl"),
            "documentSha256": record.get("documentSha256"),
            "checkedAt": record.get("retrievedAt"),
        }
        if kind == KIND_GS:
            block["steps"] = list(record.get("steps") or [])
            block["baseBeforeLocality"] = record.get("baseBeforeLocality")
            corroboration = record.get("corroboration") or {}
            block["corroboration"] = {
                "url": corroboration.get("url"),
                "documentSha256": corroboration.get("sha256"),
                "checkedAt": corroboration.get("fetched_at"),
                "agrees": corroboration.get("agrees"),
            }
        else:
            block["rows"] = [dict(r) for r in (record.get("rows") or [])]
        node["positionGradePay"] = block
        stats["ranged"] += 1
        stats["ranged_by_kind"][kind] += 1
        # Deliberately NOT written: `sourceUrls`, `evidenceUrls`, `sourceTypes`,
        # `lastVerified`, `verificationMethod`. A salary table says what a
        # grade or a pay system pays. It does not say this unit exists, and
        # every one of those fields is read elsewhere as a claim that it does
        # -- the channel by which a five-row table carried 29 positions to
        # `verified` on 2026-09-11.
    return stats
