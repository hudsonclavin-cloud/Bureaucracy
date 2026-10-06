"""What each chamber paid out for a committee's office, as the chamber prints it.

The graph carries 41 committees under the two chambers and, until this module,
every one of them published only an apportioned estimate: no Monthly Treasury
Statement line names a committee, so the cascade divided the Legislative
Branch's pool among them by subtree size. The documents that DO state what a
committee spent are the chambers' own, and each is required by law:

- the House's quarterly **Statement of Disbursements** (2 U.S.C. 104a), which
  the Chief Administrative Officer publishes on www.house.gov as three signed
  volumes and two CSV files; and
- the Senate's semiannual **Report of the Secretary of the Senate**
  (2 U.S.C. 4108), which the Government Publishing Office publishes on
  govinfo.gov as two signed PDF parts.

Both are large and both name staff beside what they were paid. **No row about a
person is read into anything here.** The House's summary CSV carries no
person at all -- one row per organisation, program and budget object class --
and is the only House file whose rows are read. The House's signed volume is
read for one page, its Statement of Accountability: a stream whose raw bytes
lack a marker of that heading is skipped before any text is formed. The
Senate's Part II is read the same way: only a stream carrying a committee's
summary block is turned into text (about 520 of its 5,189), and from such a
page exactly three things are taken -- the heading, the column heading that
states the period, and the ORGANIZATION TOTALS row with the unexpended
balance beneath it. Some of those pages print payee rows below the block;
nothing is extracted from them, and the tests assert that no payee, document
number or object-class line reaches a record, the evidence file, the graph or
the console.

**It is not the cost, and nothing here writes a cost field.** A disbursement is
cash a chamber's disbursing office paid out for the committee's account over
the report's period: the House's for one quarter, the Senate's for the first
half of the fiscal year. The graph's measured figures are the Treasury's net
outlays for the fiscal year to date, and a committee has none of its own. The
two never share a field, a period or a sentence.

**Committees only.** The owner's decision of 2026-10-07: "committees only,
subcommittees will mostly read 'parent only'." Neither document prints a
subcommittee by name -- a committee's staff and accounts are the committee's
-- so a subcommittee is never given a figure, and the block is refused on any
node not typed Committee.

**Each figure is a sum of totals the chamber prints.** Neither document prints
one total per committee for the period:

- the House prints an office total per (organisation, program): a committee's
  general-expenditures account and its intern allowance are two "offices",
  each with its own OFFICE TOTALS line, and Energy and Commerce's minority
  staff is a third organisation of its own;
- the Senate prints a summary per funding resolution: a committee's
  Inquiries and Investigations account in the period is drawn from three or
  four resolutions (S.Res. 59C and 59D of the 118th Congress, 94B and 94C of
  the 119th), each with its own ORGANIZATION TOTALS line.

So the published figure is this repository's sum over the components the
document prints, every component listed with its printed text, exactly the
shape `treasury_header_sum` has. `documentsStatingTheFigure` is 0 wherever
there is more than one component, because then no document prints the sum.

**Scale.** The Senate prints every period figure with its mark attached
("-$483,438.47") and takes `financial_evidence`'s ordinary printed-mark rule.
The House's summary CSV prints bare decimals ("1571274.53") and says
"dollars" nowhere; its signed volume prints figures bare too, except on the
Statement of Accountability, whose disbursements line carries the mark
("$ 449,333,548.30", everything the House disbursed for salaries and expenses
in the quarter). That marked total bounds the column from both sides: no
committee's quarter can exceed it, and each committee's largest office total,
read in thousands, would exceed it -- so the column is in dollars. That is a
sixth scale rule, granted to the House's statement alone; see
`financial_evidence.STATEMENT_TOTAL_BOUNDED_SOURCE_TYPES`.

**What the House file does not carry.** The summary CSV lists only the
current-year organisations ("2026 COMMITTEE ON AGRICULTURE"). The signed
volume also prints disbursements the quarter charged to a committee's earlier
accounts ("2025 COMMITTEE ON AGRICULTURE", "2023 COMMITTEE ON AGRICULTURE"),
which the CSV omits. Those pages name payees, so they are not read; the House
figure is therefore the 2026 organisation's disbursements, and the block says
so in words rather than calling it everything the House paid for the
committee.

**Matching, in three steps, never fuzzy.** Scoped to one chamber's committees:
(1) `congress.committee_key` equality, the rule the chambers' committee lists
already use; (2) `evidence.committee_core_key` equality, the type-word fold
the page test applies to committees and nothing else, which refuses a core of
under two tokens; (3) `REVIEWED_ROWS`, a table keyed by node id naming every
printed label the row claims and the basis for the identification, re-checked
on every run against the document and the node's current name. A reviewed
row exists for a label the first two rules cannot reach ("INTELLIGENCE",
"COMM ON SCIENCE SPACE&TECH") and for a committee the document splits across
organisations (Energy and Commerce's majority and minority), so the second
organisation is never silently left out of a total. One label reaching two
nodes, or a node reached by two labels outside a reviewed row, is refused.
"""

from __future__ import annotations

import csv
import hashlib
import html as _html
import io
import json
import re
import zlib
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from data_pipeline.exporter.build_graph import canonical_name_key
from data_pipeline.verification import financial_evidence as fe
from data_pipeline.verification.congress import committee_key
from data_pipeline.verification.evidence import committee_core_key
from data_pipeline.verification.omb_budget import PDF_TOKEN
from data_pipeline.verification.whitehouse_pay import _unescape

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "disbursements"
HOUSE_CSV = FIXTURES / "house" / "2026q2_sod_summary_grid.csv"
HOUSE_PDF = FIXTURES / "house" / "2026q2_vol3_signed.pdf"
HOUSE_LANDING = FIXTURES / "house" / "statement-of-disbursements.html"
HOUSE_GLOSSARY = FIXTURES / "house" / "glossary-of-terms.html"
SENATE_PDF = FIXTURES / "senate" / "GPO-CDOC-119sdoc6-2.pdf"
SENATE_LANDING = FIXTURES / "senate" / "report_secsen.htm"
DEFAULT_EVIDENCE_PATH = PROJECT_ROOT / "data" / "verification" / "committee_disbursements_evidence.json"

FIELD = "committeeDisbursements"
BASIS = "disbursements"
HOUSE_SOURCE_TYPE = "house_statement_of_disbursements"
SENATE_SOURCE_TYPE = "senate_secretary_report"
HOUSE_ROOT_ID = "leg-house"
SENATE_ROOT_ID = "leg-senate"

HOUSE_DOCUMENT_TITLE = "Statement of Disbursements of the House"
SENATE_DOCUMENT_TITLE = "Report of the Secretary of the Senate"

#: The House CSV's own column headings. "QTD AMOUNT" is printed with trailing
#: spaces, which are dropped; nothing else about a heading is normalised.
HOUSE_COLUMNS = ("ORGANIZATION", "PROGRAM", "DESCRIPTION", "YTD AMOUNT", "QTD AMOUNT")
HOUSE_QTD_COLUMN = "QTD AMOUNT"
HOUSE_OFFICE_TOTAL = "OFFICE TOTALS:"
#: The glossary's definition of the quarterly column, quoted on every House
#: record so a reader can see what "QTD" means in the publisher's own words.
HOUSE_QUARTER_DEFINITION = "Quarterly Amount — This amount lists the total expenditures for the specified quarter"
HOUSE_LANDING_PERIOD = "Current Statement of Disbursements of the House (April 1, 2026 to June 30, 2026)"
HOUSE_ORG = re.compile(r"^(?:FISCAL YEAR )?(\d{4}) (.+?)\s*$")

#: The Statement of Accountability, as the signed volume prints it. The two
#: labels and then the two figures, the first marked: the marked figure is the
#: salaries-and-expenses line, and that it is ties out by the arithmetic the
#: statement prints (marked + deposited = total funds disbursed), which the
#: loader checks rather than assumes.
HOUSE_PERIOD = re.compile(r"STATEMENT OF DISBURSEMENTS OF THE HOUSE FROM ([A-Z]+ \d{1,2}, \d{4}) TO ([A-Z]+ \d{1,2}, \d{4})")
HOUSE_ACCOUNTABILITY = re.compile(
    r"Disbursements for salaries and expenses and canceled checks Transfers: Deposited in general fund of the "
    r"Treasury (\$ ?[\d,]+\.\d\d) ([\d,]+\.\d\d) Total funds disbursed ([\d,]+\.\d\d)"
)
HOUSE_TOTAL_LABEL = "Disbursements for salaries and expenses and canceled checks"

#: A Senate committee's summary block. The heading names the committee as the
#: Senate prints it and the funding resolution (or, for the Ethics Committee,
#: its fiscal-year account); the column heading states the period; the
#: ORGANIZATION TOTALS row prints three figures -- net funds available, net
#: expenditures for the period, total funding year to date -- and the
#: unexpended balance beneath must equal the first plus the third, which the
#: loader checks so a misread column cannot pass.
SENATE_HEADING = re.compile(
    r"STATEMENT OF EXPENDITURES (?P<label>[A-Z][A-Z ,.'&-]+?) "
    r"(?P<funding>S\.RES\. \S+ \(\d+TH\)|COMMITTEE ON [A-Z ]+ - FY \d{4}) "
    r"EXPENSES OF INQUIRIES AND INVESTIGATIONS (?P<page>B-[\d-]+)"
)
SENATE_PERIOD = re.compile(r"NET EXPENDITURES FOR THE PERIOD OF (\d\d/\d\d/\d{4}) THRU (\d\d/\d\d/\d{4}) \(\$\)")
SENATE_TOTALS = re.compile(r"ORGANIZATION TOTALS (-?\$?[\d,]*\.\d\d) (-?\$[\d,]*\.\d\d) (-?\$[\d,]*\.\d\d)")
SENATE_UNEXPENDED = re.compile(r"UNEXPENDED BALANCE AS OF \d\d/\d\d/\d{4} (-?\$[\d,]*\.\d\d)")
SENATE_ACCOUNT = "Expenses of Inquiries and Investigations"
#: A summary page carries this in its raw bytes; a payee page does not.
SENATE_PAGE_MARKER = b"ORGANIZ"

#: Reviewed identifications, keyed by node id: the node's name when the row was
#: written, every label the document prints for the committee, and the basis.
#: Re-checked on every run: each label must be in the document, the node must
#: still carry the name. A row lists ALL the organisations it claims, so a
#: committee the document splits is summed whole or not at all.
REVIEWED_ROWS: dict[str, dict[str, Any]] = {
    "leg-house-cmte-energy-commerce": {
        "chamber": "house",
        "name": "House Committee on Energy & Commerce",
        "labels": ("2026 COMMITTEE ON ENERGY & COMMERCE", "2026 COMM ON ENERGY & COMMERCE-MIN"),
        "basis": (
            "The statement files the committee under two organisations, the majority's and one "
            "suffixed '-MIN'; no other committee in the file is split. Both are this committee's "
            "staff, so the row claims both and the figure is their sum -- the majority alone, which "
            "the name rule reaches, would leave the minority's disbursements out."
        ),
    },
    "leg-house-cmte-education-the-workforce": {
        "chamber": "house",
        "name": "House Committee on Education & the Workforce",
        "labels": ("2026 COMMITTEE ON EDUCATION AND WORKFORCE",),
        "basis": "The statement prints the committee's name without the article; no other committee "
                 "of the House has this jurisdiction.",
    },
    "leg-house-cmte-oversight-accountability": {
        "chamber": "house",
        "name": "House Committee on Oversight and Government Reform",
        "labels": ("2026 COMMITTEE ON OVERSIGHT AND ACCOUNTABILITY",),
        "basis": "The statement's organisation still carries the committee's 118th-Congress name; the "
                 "House Clerk's committee list (tests/fixtures/directories/house/committees.xlsx) carries "
                 "no committee of that name and this graph's node, whose id keeps the earlier name, is "
                 "the same committee under its current one.",
    },
    "leg-house-cmte-house-administration": {
        "chamber": "house",
        "name": "House Committee on House Administration",
        "labels": ("2026 HOUSE ADMINISTRATION",),
        "basis": "The statement prints the committee's name without the type words; the chamber word "
                 "is part of this committee's own name, so the fold that drops a leading 'House' cannot "
                 "reach it.",
    },
    "leg-house-cmte-transportation-infrastructure": {
        "chamber": "house",
        "name": "House Committee on Transportation & Infrastructure",
        "labels": ("2026 TRANSPORTATION-INFRASTRUCTURE",),
        "basis": "The statement abbreviates the committee's name with a hyphen for 'and'.",
    },
    "leg-house-cmte-science-space-technology": {
        "chamber": "house",
        "name": "House Committee on Science, Space & Technology",
        "labels": ("2026 COMM ON SCIENCE SPACE&TECH",),
        "basis": "The statement abbreviates 'Committee' and 'Technology'; no other committee of the House "
                 "has this jurisdiction.",
    },
    "leg-house-cmte-permanent-select-committee-on-intelligence": {
        "chamber": "house",
        "name": "House Permanent Select Committee on Intelligence",
        "labels": ("2026 INTELLIGENCE",),
        "basis": "The statement prints the committee by its subject alone; the House has one "
                 "intelligence committee.",
    },
    "leg-house-cmte-select-committee-on-the-chinese-communist-party": {
        "chamber": "house",
        "name": "Select Committee on the Strategic Competition Between the United States and the Chinese Communist Party",
        "labels": ("2026 SELECT COMMITTEE COMPETITION US AND CHINA",),
        "basis": "The statement abbreviates the select committee's name; the House has one select "
                 "committee on competition with China.",
    },
    "leg-senate-cmte-budget": {
        "chamber": "senate",
        "name": "Senate Committee on the Budget",
        "labels": ("BUDGET",),
        "basis": "The report heads each Inquiries and Investigations account with the committee's "
                 "subject alone; the one-word label is below the fold's two-token floor.",
    },
    "leg-senate-cmte-finance": {
        "chamber": "senate",
        "name": "Senate Committee on Finance",
        "labels": ("FINANCE",),
        "basis": "As for the Budget Committee: the report's one-word label for the committee's account.",
    },
    "leg-senate-cmte-judiciary": {
        "chamber": "senate",
        "name": "United States Senate Committee on the Judiciary",
        "labels": ("JUDICIARY",),
        "basis": "As for the Budget Committee: the report's one-word label for the committee's account.",
    },
    "leg-senate-cmte-select-committee-on-intelligence": {
        "chamber": "senate",
        "name": "Senate Select Committee on Intelligence",
        "labels": ("INTELLIGENCE",),
        "basis": "As for the Budget Committee: the Senate has one intelligence committee.",
    },
    "leg-senate-cmte-select-committee-on-ethics": {
        "chamber": "senate",
        "name": "U.S. Senate Select Committee on Ethics",
        "labels": ("ETHICS",),
        "basis": "The report heads the account 'ETHICS' and names its funding 'COMMITTEE ON ETHICS - FY "
                 "2026'; the Senate has one ethics committee.",
    },
    "leg-senate-cmte-special-committee-on-aging": {
        "chamber": "senate",
        "name": "Senate Special Committee on Aging",
        "labels": ("SPECIAL COMMITTEE ON AGING",),
        "basis": "The report prints the committee's own name; the fold leaves the single token 'aging', "
                 "which is below its two-token floor.",
    },
}


class Unreadable(RuntimeError):
    """A committed document is not the one this module was written against."""


# --------------------------------------------------------------------------
# Documents


def _digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _meta(path: Path) -> dict[str, Any]:
    """The fetch record beside a fixture, with its digest checked against the bytes."""
    meta_path = Path(path).with_name(Path(path).name + ".meta.json")
    if not meta_path.exists():
        raise Unreadable(f"{path.name}: no fetch record beside it")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    digest = _digest(path)
    if meta.get("sha256") != digest:
        raise Unreadable(f"{path.name}: sha256 on disk {digest} does not match the fetch record {meta.get('sha256')}")
    if not meta.get("final_url") or meta.get("final_url") != meta.get("url"):
        raise Unreadable(f"{path.name}: the fetch was redirected or has no final URL")
    return {"file": str(Path(path).relative_to(PROJECT_ROOT)), "url": meta["url"], "sha256": digest,
            "fetchedAt": meta.get("fetched_at")}


def _html_text(path: Path) -> str:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", _html.unescape(text)).strip()


def pdf_page_texts(raw: bytes, must_contain: bytes = b"") -> list[str]:
    """The text of each content stream, in file order, whitespace normalised.

    The standard library alone, the way `omb_budget.guide_text` reads OMB's
    guide: strings are concatenated, a positioning operator or a wide kerning
    gap is a space. One string per stream, so a heading and the totals row
    beneath it are only ever paired when they sit on the same page.

    `must_contain` skips, before any text is formed, a stream whose raw bytes
    lack the marker: the pages this module reads are found by a heading, and a
    payee page is then never tokenised at all.
    """
    if not raw.startswith(b"%PDF-"):
        raise Unreadable("not a PDF")
    if b"/Encrypt" in raw:
        raise Unreadable("PDF is encrypted; this reader will not guess at its contents")
    pages: list[str] = []
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", raw, re.S):
        try:
            body = zlib.decompress(match.group(1))
        except zlib.error:
            continue
        if b"BT" not in body or (must_contain and must_contain not in body):
            continue
        out: list[str] = []
        for token_match in PDF_TOKEN.finditer(body):
            token = token_match.group(0)
            if token.startswith(b"("):
                out.append(_unescape(token[1:-1]))
            elif token in (b"Td", b"TD", b"T*", b"Tm", b"ET"):
                out.append(" ")
            elif token not in (b"TJ", b"Tj", b"BT"):
                try:
                    if float(token) <= -120:
                        out.append(" ")
                except ValueError:
                    continue
        pages.append(re.sub(r"\s+", " ", "".join(out)).strip())
    return pages


def _parse_date(text: str, fmt: str) -> str:
    return datetime.strptime(text.title() if "%B" in fmt else text, fmt).date().isoformat()


def load_house_statement() -> dict[str, Any]:
    """The House's summary CSV and the one page of its signed volume read here."""
    csv_meta = _meta(HOUSE_CSV)
    pdf_meta = _meta(HOUSE_PDF)
    landing_meta = _meta(HOUSE_LANDING)
    glossary_meta = _meta(HOUSE_GLOSSARY)

    landing = _html_text(HOUSE_LANDING)
    if HOUSE_LANDING_PERIOD not in landing:
        raise Unreadable("the landing page does not name the statement's period as expected")
    raw_landing = HOUSE_LANDING.read_text(encoding="utf-8", errors="replace")
    for meta in (csv_meta, pdf_meta):
        path = re.sub(r"^https://www\.house\.gov", "", meta["url"])
        if f'href="{path}"' not in raw_landing:
            raise Unreadable(f"the landing page does not link {path} under the current statement")
    if HOUSE_QUARTER_DEFINITION not in _html_text(HOUSE_GLOSSARY):
        raise Unreadable("the glossary no longer defines the quarterly column as quoted")

    statement_page = None
    for text in pdf_page_texts(HOUSE_PDF.read_bytes(), must_contain=b"ABILITY"):
        if "STATEMENT OF ACCOUNTABILITY FOR APPROPRIATIONS" in text:
            statement_page = text
            break
    if statement_page is None:
        raise Unreadable("the signed volume carries no Statement of Accountability")
    period = HOUSE_PERIOD.search(statement_page)
    accountability = HOUSE_ACCOUNTABILITY.search(statement_page)
    if not period or not accountability:
        raise Unreadable("the Statement of Accountability is not printed as this reader expects")
    marked, deposited, total = accountability.groups()
    as_cents = lambda s: round(float(s.replace("$", "").replace(",", "").strip()) * 100)  # noqa: E731
    if as_cents(marked) + as_cents(deposited) != as_cents(total):
        raise Unreadable("the marked disbursements line and the deposits do not sum to total funds disbursed")

    raw_rows = list(csv.reader(io.StringIO(HOUSE_CSV.read_text(encoding="utf-8-sig"))))
    header = [cell.strip() for cell in raw_rows[0]]
    if tuple(header) != HOUSE_COLUMNS:
        raise Unreadable(f"the summary file's columns are {header}")
    organisations: dict[str, dict[str, Any]] = {}
    for row_number, row in enumerate(raw_rows[1:], start=2):
        if len(row) != len(HOUSE_COLUMNS):
            raise Unreadable(f"row {row_number} has {len(row)} cells")
        org, program, description, ytd, qtd = (cell.strip() for cell in row)
        entry = organisations.setdefault(org, {"programs": {}})
        program_entry = entry["programs"].setdefault(program, {"officeTotals": [], "programTotals": []})
        if description == HOUSE_OFFICE_TOTAL:
            program_entry["officeTotals"].append({"row": row_number, "ytd": ytd, "qtd": qtd, "printed": ",".join(row).rstrip()})
        elif description == f"{program} TOTALS:":
            program_entry["programTotals"].append({"row": row_number, "qtd": qtd})
    return {
        "csv": csv_meta, "pdf": pdf_meta, "landing": landing_meta, "glossary": glossary_meta,
        "period": {
            "printed": period.group(0),
            "start": _parse_date(period.group(1), "%B %d, %Y"),
            "end": _parse_date(period.group(2), "%B %d, %Y"),
        },
        "statementTotal": {"text": marked, "amountRaw": marked.replace("$", "").strip(), "label": HOUSE_TOTAL_LABEL,
                           "deposited": deposited, "totalFundsDisbursed": total},
        "organisations": organisations,
    }


def load_senate_report() -> dict[str, Any]:
    """Every committee summary block in Part II, one per funding resolution."""
    pdf_meta = _meta(SENATE_PDF)
    _meta(SENATE_LANDING)
    landing_raw = SENATE_LANDING.read_text(encoding="utf-8", errors="replace")
    if pdf_meta["url"] not in landing_raw:
        raise Unreadable("senate.gov's report page does not link the committed Part II")
    sections: list[dict[str, Any]] = []
    periods: set[tuple[str, str]] = set()
    for index, text in enumerate(pdf_page_texts(SENATE_PDF.read_bytes(), must_contain=SENATE_PAGE_MARKER)):
        heading = SENATE_HEADING.search(text)
        if not heading or "ORGANIZATION TOTALS" not in text:
            continue
        period = SENATE_PERIOD.findall(text)
        totals = SENATE_TOTALS.findall(text)
        unexpended = SENATE_UNEXPENDED.findall(text)
        if len(SENATE_HEADING.findall(text)) != 1 or len(period) != 1 or len(totals) != 1 or len(unexpended) != 1:
            raise Unreadable(f"stream {index}: a summary page is not one heading, one period, one totals row")
        available, net, life = totals[0]
        cents = lambda s: round(float(s.replace("$", "").replace(",", "") or 0) * 100)  # noqa: E731
        if cents(available) + cents(life) != cents(unexpended[0]):
            raise Unreadable(f"stream {index}: available + total funding YTD does not equal the unexpended balance")
        periods.add(period[0])
        line = re.search(r"ORGANIZATION TOTALS \S+ \S+ \S+", text).group(0)
        sections.append({
            "stream": index, "page": heading.group("page"), "label": heading.group("label").strip(),
            "funding": heading.group("funding"), "heading": heading.group(0),
            "periodHeading": SENATE_PERIOD.search(text).group(0), "totalsLine": line, "netPrinted": net,
        })
    if len(periods) != 1:
        raise Unreadable(f"the summary pages state {len(periods)} different periods")
    (start, end), = periods
    return {
        "pdf": pdf_meta,
        "period": {"printed": sections[0]["periodHeading"],
                   "start": _parse_date(start, "%m/%d/%Y"), "end": _parse_date(end, "%m/%d/%Y")},
        "sections": sections,
    }


# --------------------------------------------------------------------------
# Matching


def chamber_committees(node_map: Mapping[str, Mapping[str, Any]], parent_map: Mapping[str, Any], root_id: str) -> dict[str, Mapping[str, Any]]:
    """Nodes typed Committee whose ancestor chain reaches the chamber's node."""
    out = {}
    for node_id, node in node_map.items():
        if str(node.get("type") or "").strip().casefold() != "committee":
            continue
        current = parent_map.get(node_id)
        while current and current != root_id:
            current = parent_map.get(current)
        if current == root_id:
            out[node_id] = node
    return out


def _auto_match(labels: dict[str, str], committees: Mapping[str, Mapping[str, Any]],
                claimed: set[str], report: dict[str, Any]) -> dict[str, list[tuple[str, str]]]:
    """label -> node by the two existing rules, one to one or nothing."""
    by_key: dict[str, list[str]] = {}
    by_core: dict[str, list[str]] = {}
    for node_id, node in committees.items():
        by_key.setdefault(committee_key(node.get("name")), []).append(node_id)
        core = committee_core_key(canonical_name_key(node.get("name")))
        if core:
            by_core.setdefault(core, []).append(node_id)
    reached: dict[str, list[tuple[str, str]]] = {}
    for label, name in labels.items():
        if label in claimed:
            continue
        rule, ids = "committee_key_equal", by_key.get(committee_key(name), [])
        if not ids:
            core = committee_core_key(canonical_name_key(name))
            rule, ids = "committee_type_words_folded", (by_core.get(core, []) if core else [])
        if len(ids) == 1:
            reached.setdefault(ids[0], []).append((label, rule))
        elif len(ids) > 1:
            report["ambiguous"].append({"label": label, "nodes": ids})
    return reached


def _shared(node_id: str, node: Mapping[str, Any], chamber: str, document: dict[str, Any], period: dict[str, Any],
            labels: list[str], rule: str, basis: str | None) -> dict[str, Any]:
    record = {
        "nodeId": node_id, "nodeName": node.get("name"), "chamber": chamber,
        "costBasis": BASIS, "document": document, "period": period,
        "listedNames": labels, "matchRule": rule,
        "scopeMatch": "proxy", "financialEvidenceStatus": "partial",
    }
    if basis:
        record["matchBasis"] = basis
    return record


def _finish(record: dict[str, Any], components: list[dict[str, Any]], zeros: list[dict[str, Any]]) -> dict[str, Any]:
    total_cents = sum(round(c["amount"] * 100) for c in components)
    record["components"] = components
    record["zeroComponents"] = zeros
    record["amount"] = total_cents / 100
    record["componentCount"] = len(components)
    record["documentsStatingTheFigure"] = 1 if len(components) == 1 else 0
    record["arithmetic"] = {
        "operation": "sum_of_printed_totals",
        "note": ("The figure is the one total the document prints for this committee."
                 if len(components) == 1 else
                 f"The document prints no single total for this committee; the figure is the sum of the "
                 f"{len(components)} totals it prints, each listed with its printed text."),
    }
    record["notTheCost"] = (
        "Cash the chamber's disbursing office paid out for the committee's account over the period. It is "
        "not the Treasury's net outlays, not the graph's estimate for this node, and not its cost."
    )
    return record


def build_house_records(node_map, parent_map, statement=None) -> tuple[dict[str, Any], dict[str, Any]]:
    statement = statement or load_house_statement()
    committees = chamber_committees(node_map, parent_map, HOUSE_ROOT_ID)
    report: dict[str, Any] = {"chamber": "house", "committees_in_graph": len(committees), "ambiguous": [],
                              "refused": {}, "matched": {}, "labels_not_matched": []}
    labels: dict[str, str] = {}
    for org in statement["organisations"]:
        parsed = HOUSE_ORG.match(org)
        if parsed:
            labels[org] = parsed.group(2)
    claimed = {label for row in REVIEWED_ROWS.values() if row["chamber"] == "house" for label in row["labels"]}
    reached = _auto_match(labels, committees, claimed, report)
    for node_id, row in REVIEWED_ROWS.items():
        if row["chamber"] != "house":
            continue
        reached[node_id] = [(label, "reviewed_row") for label in row["labels"]]
    document = {"title": HOUSE_DOCUMENT_TITLE, "file": statement["csv"]["file"], "url": statement["csv"]["url"],
                "sha256": statement["csv"]["sha256"], "fetchedAt": statement["csv"]["fetchedAt"],
                "statementVolume": {k: statement["pdf"][k] for k in ("file", "url", "sha256")},
                "column": HOUSE_QTD_COLUMN, "columnDefinition": HOUSE_QUARTER_DEFINITION,
                "statementTotal": {k: statement["statementTotal"][k] for k in ("text", "label")}}
    period = dict(statement["period"], coverage="quarter")
    records: dict[str, Any] = {}

    def refuse(reason: str, detail: str) -> None:
        report["refused"].setdefault(reason, []).append(detail)

    for node_id, matches in reached.items():
        node = node_map.get(node_id)
        if node is None or node_id not in committees:
            refuse("reviewed_node_is_not_a_house_committee", node_id)
            continue
        rules = {rule for _, rule in matches}
        if len(matches) > 1 and rules != {"reviewed_row"}:
            refuse("node_reached_by_several_labels_outside_a_reviewed_row", f"{node_id}: {[m[0] for m in matches]}")
            continue
        row = REVIEWED_ROWS.get(node_id)
        if row and canonical_name_key(node.get("name")) != canonical_name_key(row["name"]):
            refuse("reviewed_row_node_renamed", node_id)
            continue
        missing = [label for label, _ in matches if label not in statement["organisations"]]
        if missing:
            refuse("label_not_in_the_document", f"{node_id}: {missing}")
            continue
        printed = []
        for label, _ in matches:
            for program, entry in statement["organisations"][label]["programs"].items():
                offices, programs = entry["officeTotals"], entry["programTotals"]
                if len(offices) != 1 or len(programs) != 1 or offices[0]["qtd"] != programs[0]["qtd"]:
                    printed = None
                    break
                printed.append((label, program, offices[0]))
            if printed is None:
                break
        if not printed:
            refuse("office_totals_not_one_per_program", node_id)
            continue
        nonzero = [p for p in printed if float(p[2]["qtd"]) != 0]
        if not nonzero:
            refuse("nothing_disbursed_in_the_quarter", node_id)
            continue
        anchor = max(nonzero, key=lambda p: abs(float(p[2]["qtd"])))
        anchor_raw = anchor[2]["qtd"]
        total_text = statement["statementTotal"]["text"]
        total_value = float(statement["statementTotal"]["amountRaw"].replace(",", ""))
        if abs(float(anchor_raw)) * 1000 <= total_value:
            refuse("largest_office_total_too_small_to_bound_the_scale", node_id)
            continue
        rule = matches[0][1]
        record = _shared(node_id, node, "house", document, period, [m[0] for m in matches], rule,
                         row["basis"] if row else None)
        components, zeros = [], []
        try:
            for label, program, office in printed:
                entry = {"label": label, "program": program, "printed": office["qtd"],
                         "locator": {"row": office["row"], "column": HOUSE_QTD_COLUMN,
                                     "organization": label, "program": program, "description": HOUSE_OFFICE_TOTAL}}
                if float(office["qtd"]) == 0:
                    zeros.append(entry)
                    continue
                evidence = (f"{HOUSE_QTD_COLUMN}: {office['printed']} | statement total, {HOUSE_TOTAL_LABEL}: "
                            f"{total_text} | largest office total in this column for the committee: {anchor_raw}")
                validated = fe.validate_record({
                    "nodeId": node_id, "financialEvidenceStatus": "partial", "costBasis": BASIS,
                    "sourceType": HOUSE_SOURCE_TYPE, "units": "usd", "normalizedMultiplier": 1,
                    "unitsEvidence": evidence,
                    "statementTotal": {"text": total_text, "label": HOUSE_TOTAL_LABEL},
                    "columnAnchor": {"amountRaw": anchor_raw, "column": HOUSE_QTD_COLUMN},
                    "quote": office["printed"], "amountRaw": office["qtd"], "amount": float(office["qtd"]),
                    "fiscalYear": 2026, "periodCoverage": "quarter", "periodAsOf": period["end"],
                    "retrievedAt": statement["csv"]["fetchedAt"], "scopeMatch": "proxy",
                    "amountScope": f"{label} / {program}", "rollupRole": "subtotal",
                    "sourceUrl": statement["csv"]["url"], "documentSha256": statement["csv"]["sha256"],
                    "locator": entry["locator"],
                }, node)
                entry["amount"] = float(office["qtd"])
                entry["unitsEvidenceKind"] = validated["unitsEvidenceKind"]
                components.append(entry)
        except fe.Rejected as error:
            refuse("component_refused_by_financial_evidence", f"{node_id}: {error}")
            continue
        record["unitsEvidence"] = {"kind": components[0]["unitsEvidenceKind"], "statementTotal": total_text,
                                   "columnAnchor": anchor_raw}
        record["caveat"] = (
            "The statement's summary file lists the committee's current-year organisation only. "
            "Disbursements the quarter charged to the committee's earlier-year accounts are printed in the "
            "signed volumes beside named payees and are not in this figure."
        )
        records[node_id] = _finish(record, components, zeros)
        report["matched"][node_id] = rule
    used = {label for record in records.values() for label in record["listedNames"]}
    report["labels_not_matched"] = sorted(
        label for label in labels if label not in used and re.search(r"\bCOMM(?:ITTEE|MMITTEE)?\b|\bCOMM\b", label))
    return records, report


def build_senate_records(node_map, parent_map, report_doc=None) -> tuple[dict[str, Any], dict[str, Any]]:
    report_doc = report_doc or load_senate_report()
    committees = chamber_committees(node_map, parent_map, SENATE_ROOT_ID)
    report: dict[str, Any] = {"chamber": "senate", "committees_in_graph": len(committees), "ambiguous": [],
                              "refused": {}, "matched": {}, "labels_not_matched": []}
    by_label: dict[str, list[dict[str, Any]]] = {}
    for section in report_doc["sections"]:
        by_label.setdefault(section["label"], []).append(section)
    labels = {label: label for label in by_label}
    claimed = {label for row in REVIEWED_ROWS.values() if row["chamber"] == "senate" for label in row["labels"]}
    reached = _auto_match(labels, committees, claimed, report)
    for node_id, row in REVIEWED_ROWS.items():
        if row["chamber"] == "senate":
            reached[node_id] = [(label, "reviewed_row") for label in row["labels"]]
    document = {"title": SENATE_DOCUMENT_TITLE, "part": "Part II", "file": report_doc["pdf"]["file"],
                "url": report_doc["pdf"]["url"], "sha256": report_doc["pdf"]["sha256"],
                "fetchedAt": report_doc["pdf"]["fetchedAt"], "account": SENATE_ACCOUNT}
    period = dict(report_doc["period"], coverage="fiscal_year_to_date")
    records: dict[str, Any] = {}

    def refuse(reason: str, detail: str) -> None:
        report["refused"].setdefault(reason, []).append(detail)

    for node_id, matches in reached.items():
        node = node_map.get(node_id)
        if node is None or node_id not in committees:
            refuse("reviewed_node_is_not_a_senate_committee", node_id)
            continue
        if len(matches) > 1 and {r for _, r in matches} != {"reviewed_row"}:
            refuse("node_reached_by_several_labels_outside_a_reviewed_row", f"{node_id}: {[m[0] for m in matches]}")
            continue
        row = REVIEWED_ROWS.get(node_id)
        if row and canonical_name_key(node.get("name")) != canonical_name_key(row["name"]):
            refuse("reviewed_row_node_renamed", node_id)
            continue
        sections = [s for label, _ in matches for s in by_label.get(label, [])]
        if not sections or any(label not in by_label for label, _ in matches):
            refuse("label_not_in_the_document", node_id)
            continue
        record = _shared(node_id, node, "senate", document, period, [m[0] for m in matches], matches[0][1],
                         row["basis"] if row else None)
        components, zeros = [], []
        try:
            for section in sorted(sections, key=lambda s: s["stream"]):
                printed = section["netPrinted"]
                magnitude = printed.lstrip("-").lstrip("$")
                entry = {"label": section["label"], "funding": section["funding"], "printed": printed,
                         "locator": {"page": section["page"], "heading": section["heading"],
                                     "row": "ORGANIZATION TOTALS", "column": section["periodHeading"]}}
                if float(magnitude.replace(",", "") or 0) == 0:
                    zeros.append(entry)
                    continue
                evidence = f"{section['periodHeading']} | {section['totalsLine']}"
                fe.validate_record({
                    "nodeId": node_id, "financialEvidenceStatus": "partial", "costBasis": BASIS,
                    "sourceType": SENATE_SOURCE_TYPE, "units": "usd", "normalizedMultiplier": 1,
                    "unitsEvidence": evidence, "quote": f"{section['heading']} | {evidence}",
                    "amountRaw": magnitude, "amount": float(magnitude.replace(",", "")),
                    "fiscalYear": 2026, "periodCoverage": "fiscal_year_to_date", "periodAsOf": period["end"],
                    "retrievedAt": report_doc["pdf"]["fetchedAt"], "scopeMatch": "proxy",
                    "amountScope": f"{section['label']} {section['funding']}", "rollupRole": "subtotal",
                    "sourceUrl": report_doc["pdf"]["url"], "documentSha256": report_doc["pdf"]["sha256"],
                    "locator": entry["locator"],
                }, node)
                # The report prints an expenditure as a reduction of the account ("-$483,438.47"); a
                # figure printed without the minus sign is a net credit to the account in the period.
                entry["amount"] = float(magnitude.replace(",", "")) * (1 if printed.startswith("-") else -1)
                entry["unitsEvidenceKind"] = "currency_mark_on_the_printed_figure"
                components.append(entry)
        except fe.Rejected as error:
            refuse("component_refused_by_financial_evidence", f"{node_id}: {error}")
            continue
        if not components:
            refuse("nothing_disbursed_in_the_period", node_id)
            continue
        record["unitsEvidence"] = {"kind": "currency_mark_on_the_printed_figure"}
        record["signConvention"] = (
            "The report prints an expenditure as a reduction of the account, with a minus sign; a figure "
            "printed without one is a net credit in the period and reduces the total."
        )
        records[node_id] = _finish(record, components, zeros)
        report["matched"][node_id] = matches[0][1]
    used = {label for record in records.values() for label in record["listedNames"]}
    report["labels_not_matched"] = sorted(label for label in by_label if label not in used)
    return records, report


def build_records(node_map, parent_map) -> tuple[dict[str, Any], dict[str, Any]]:
    house, house_report = build_house_records(node_map, parent_map)
    senate, senate_report = build_senate_records(node_map, parent_map)
    overlap = set(house) & set(senate)
    if overlap:
        raise Unreadable(f"nodes reached by both chambers: {sorted(overlap)}")
    return {**house, **senate}, {"house": house_report, "senate": senate_report}


# --------------------------------------------------------------------------
# Applying


def load_committee_disbursements_evidence(path: str | Path | None) -> dict[str, dict[str, Any]]:
    if not path:
        return {}
    try:
        store = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    nodes = store.get("nodes") if isinstance(store, dict) else None
    return {str(k): v for k, v in (nodes or {}).items() if isinstance(v, dict)}


def apply_committee_disbursements_evidence(root: dict[str, Any], records: Mapping[str, Mapping[str, Any]],
                                           *, index_tree=None) -> dict[str, Any]:
    """Stamp each committee's block beside its estimate, never in a cost field.

    Withdrawn from every node first, so a record refused since the last build
    stops being published even though the exporter re-feeds graph.json. Never
    on a node not typed Committee, and never after a rename.
    """
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree
        index_tree = _index_tree
    node_map, _ = index_tree(root)
    applied = withdrawn = refused_type = refused_renamed = 0
    for node_id, node in node_map.items():
        if node.pop(FIELD, None) is not None:
            withdrawn += 1
        record = records.get(node_id)
        if not record:
            continue
        if str(node.get("type") or "").strip().casefold() != "committee":
            refused_type += 1
            continue
        if canonical_name_key(node.get("name")) != canonical_name_key(record.get("nodeName")):
            refused_renamed += 1
            continue
        node[FIELD] = json.loads(json.dumps(record))
        applied += 1
    return {"applied": applied, "withdrawn_first": withdrawn, "refused_not_a_committee": refused_type,
            "refused_renamed": refused_renamed}
