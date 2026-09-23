"""The White House Office's own annual personnel report, and the one claim it
can honestly make about a position node beneath `exec-eop-who`.

## The only named-salary disclosure the federal government is required to make

Section 6 of Public Law 103-270 requires the President to send Congress, by
July 1 each year, a report listing every White House Office employee and
detailee with their title and their annual rate of pay. The White House
publishes it at `whitehouse.gov/disclosures/`. It is the one place in this
entire project where an official document states, for a specific post, a
specific number of dollars actually paid — every other pay source here
(`pay_tables.py`, `judicial_pay.py`, `congressional_pay.py`) states a rate for
a *rank* or a *tier* and leaves the join to a node as this pipeline's own
claim.

## Which is why the claim is narrower than it looks

The report is person-level by statute, not post-level. It lists 408 people;
`SENIOR POLICY ADVISOR` appears 21 times and `STAFF ASSISTANT` 15, at
different salaries. So even a title this graph carries as one node cannot be
said to *pay* the figure beside it. What can be said — and is all this module
says — is:

    the one person the report lists under this title is paid $X,
    as of the report's own as-of date.

That is why every record is `scopeMatch: "proxy"` and why the field is
`positionReportedPay` rather than `positionStatutoryPay`. A statutory rate
(`judicial_pay.py`, `congressional_pay.py`) attaches to the office and
survives a change of holder; a reported rate does not. The release gate
checks each field against its own source's rules for exactly this reason:
folding them together would let a roster satisfy a statute's checks.

## The incumbent columns are never read

`positions.py` established the rule for the PLUM archive and it binds here
with more force, because this document is far more personal: it carries a
living person's name beside their salary. This module reads the STATUS,
SALARY, PAY BASIS and POSITION TITLE columns. It never reads, stores, derives
from or publishes the NAME column — `parse_staff_report` discards the name
cell at parse time rather than carrying it and declining to print it, so no
downstream change can start publishing it by accident.

## What it refuses, and why each refusal exists

- **a rate of $0.00** (`reported_rate_is_zero`). Ten of the 408 rows are
  $0.00 — uncompensated appointees, the National Security Advisor among them.
  This repository's standing invariant is that zero is never published as an
  amount, and the reason applies with full force here: a $0.00 is a fact
  about the arrangement one person has, not about the post.
- **a title more than one person holds** (`title_held_by_several_people`).
  Two people under one title at different salaries make the figure beside the
  title undecidable, and this project does not resolve an ambiguity by
  picking one.
- **a node standing for several posts** (`stands_for_several_posts`), the
  same rule `pay_tables.py` and `judicial_pay.py` enforce.
- **a node outside the White House Office subtree**. The report covers the
  White House Office, not the whole Executive Office of the President, so the
  match is scoped to descendants of `exec-eop-who` exactly as `headcounts.py`
  scopes a FedScope sub-agency row beneath the node its agency matched. A
  title being unique in the graph is not evidence of placement.

## The rank prefix, folded — and only as a leading prefix

The report spells a post with its White House commissioning rank in front:
`ASSISTANT TO THE PRESIDENT AND CHIEF OF STAFF` for the node this graph calls
`Chief of Staff`. `title_core` folds those three ranks off the front, which is
the same move `positions.archive_title_keys` makes for the PLUM archive and
`congress.committee_key` makes for the chambers' committee names.

It folds a **leading prefix only**, and then requires the remainder to equal
the node's name exactly. A containment test would be actively wrong on this
document, and not hypothetically:

- `Press Secretary` is contained in `ASSISTANT PRESS SECRETARY` and in
  `SPECIAL ASSISTANT TO THE PRESIDENT AND DEPUTY PRESS SECRETARY`;
- the only report title containing `Director of Legislative Affairs` is the
  **Deputy** Director's;
- the only one containing `Social Secretary` is the **Deputy** Social
  Secretary's.

Each of those would price a principal from a deputy's salary. It is the same
failure the existence verifier already documents — "Office of Science"
matching inside "Office of Science and Technology Policy" — and label
equality is the same answer.

## Reading a PDF with the standard library

Every other fixture here is parsed with the standard library alone, including
the House Clerk's spreadsheet (`congress.read_xlsx_rows`: an .xlsx is a zip
of XML). A PDF yields to the same treatment: this one is `%PDF-1.6`, carries
no `/Encrypt`, and holds its text in FlateDecode streams — zlib, which is
stdlib — as ordinary `BT ... Tm ... TJ` blocks over latin-1 literals. So
`extract_text_runs` decompresses each stream and reads the text-showing
operators with their positions, and no third-party PDF library enters this
repository.

Positions alone will not separate the columns: the rows share a single `Tm`
and advance by intra-stream kerning, so every cell in a row reports the same
x. The columns are recovered by **shape** instead — a salary matches a money
pattern, STATUS and PAY BASIS are closed vocabularies the header names, the
name cell matches `LAST, FIRST M.`, and the title is what remains. A row that
does not yield exactly one of each is refused rather than guessed at, which
is what the eight malformed rows in the 2026 report get.
"""

from __future__ import annotations

import hashlib
import json
import re
import zlib
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "whitehouse"
DEFAULT_REPORT_PDF = FIXTURE_DIR / "staff_report_2026.pdf"
DEFAULT_PAY_EVIDENCE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "verification" / "whitehouse_pay_evidence.json"
)

PAY_SOURCE = "whitehouse_staff_report"
PAY_SOURCE_TYPE = "whitehouse_staff_report"
PAY_METHOD = "rate_reported_for_the_one_person_listed_under_this_title"
#: The same claim on a node the roster lists N times at one rate: each listed
#: person's figure, never "one person" beside a count of six.
PAY_METHOD_UNIFORM = "rate_reported_for_each_of_the_people_listed_under_this_title"

#: The subtree the report covers. The document's own heading is "ANNUAL REPORT
#: TO CONGRESS ON WHITE HOUSE OFFICE PERSONNEL"; the Executive Office of the
#: President contains several other units this report says nothing about.
SCOPE_NODE_ID = "exec-eop-who"

#: The columns the report prints, in the order its header row prints them.
#: A report that reshapes is refused rather than read positionally.
EXPECTED_COLUMNS = ("NAME", "STATUS", "SALARY", "PAY BASIS", "POSITION TITLE")

#: Closed vocabularies. Both are what the 2026 report actually carries; a
#: value outside them makes the row's shape undecidable and refuses it.
STATUS_VALUES = frozenset({"EMPLOYEE", "DETAILEE"})
PAY_BASIS_VALUES = frozenset({"Per Annum"})

#: The White House commissioning ranks, longest first so that "DEPUTY
#: ASSISTANT TO THE PRESIDENT AND" is tried before "ASSISTANT TO THE
#: PRESIDENT AND" and never leaves a stray "DEPUTY" on the front.
RANK_PREFIXES = (
    "DEPUTY ASSISTANT TO THE PRESIDENT AND ",
    "SPECIAL ASSISTANT TO THE PRESIDENT AND ",
    "ASSISTANT TO THE PRESIDENT AND ",
)

#: A folded title must keep at least this many tokens. One token is too
#: little to identify a post: the same guard `congress.committee_core_key`
#: applies for the same reason.
MIN_CORE_TOKENS = 2

_SALARY_CELL = re.compile(r"^\$([\d,]+\.\d{2})$")
_NAME_CELL = re.compile(r"^[A-Z][A-Za-z.'\- ]*, [A-Z]")
_AS_OF = re.compile(r"As of Date:\s*(.+?)\s*$")

#: "Wednesday, July 1, 2026" — the form the report's own heading prints. The
#: weekday is optional and discarded; the date is what the record is stamped
#: with, and a heading this parser cannot read is refused rather than dated by
#: the fetch, which would silently substitute "when we downloaded it" for
#: "what the report says it describes".
_AS_OF_DATE = re.compile(
    r"(?:[A-Za-z]+,\s*)?([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})"
)
_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def as_of_date(text: str) -> date:
    """The report's own as-of date, as a date."""
    found = _AS_OF_DATE.search(str(text or ""))
    if not found:
        raise Unreadable(f"as-of date {text!r} is not a date this parser will read")
    month = _MONTHS.get(found.group(1).casefold())
    if month is None:
        raise Unreadable(f"as-of date {text!r} names no month this parser knows")
    try:
        return date(int(found.group(3)), month, int(found.group(2)))
    except ValueError as error:
        raise Unreadable(f"as-of date {text!r} is not a real date") from error

_TEXT_OP = re.compile(
    rb"([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+Tm"
    rb"|\[(.*?)\]\s*TJ"
    rb"|\((?:\\.|[^\\()])*\)\s*Tj",
    re.S,
)
_LITERAL = re.compile(rb"\((?:\\.|[^\\()])*\)", re.S)


class Unreadable(RuntimeError):
    """The document is not the one this parser was written against."""


def _unescape(raw: bytes) -> str:
    """A PDF literal string's own escapes, per the spec's Table 3."""
    out = bytearray()
    index = 0
    simple = {0x6E: 10, 0x72: 13, 0x74: 9, 0x62: 8, 0x66: 12}
    while index < len(raw):
        char = raw[index]
        if char != 0x5C or index + 1 >= len(raw):
            out.append(char)
            index += 1
            continue
        nxt = raw[index + 1]
        if nxt in simple:
            out.append(simple[nxt])
            index += 2
            continue
        if 0x30 <= nxt <= 0x37:
            cursor = index + 1
            digits = b""
            while cursor < len(raw) and len(digits) < 3 and 0x30 <= raw[cursor] <= 0x37:
                digits += bytes([raw[cursor]])
                cursor += 1
            out.append(int(digits, 8) & 0xFF)
            index = cursor
            continue
        out.append(nxt)
        index += 2
    return out.decode("latin-1")


def content_streams(raw: bytes) -> list[bytes]:
    """Every FlateDecode stream in the file, decompressed.

    An encrypted document is refused outright: its streams would decompress
    to ciphertext and any text recovered from them would be nonsense read as
    if it were the publisher's words.
    """
    if not raw.startswith(b"%PDF-"):
        raise Unreadable("file does not begin with a PDF header")
    if b"/Encrypt" in raw:
        raise Unreadable("PDF is encrypted; this reader will not guess at its contents")
    streams: list[bytes] = []
    for match in re.finditer(rb"stream\r?\n", raw):
        start = match.end()
        end = raw.find(b"endstream", start)
        if end < 0:
            continue
        try:
            streams.append(zlib.decompress(raw[start:end]))
        except zlib.error:
            continue
    if not streams:
        raise Unreadable("no FlateDecode streams could be decompressed")
    return streams


def extract_text_runs(stream: bytes) -> list[tuple[float, float, str]]:
    """`(x, y, text)` for each text-showing operator, in stream order."""
    runs: list[tuple[float, float, str]] = []
    position: tuple[float, float] | None = None
    for token in _TEXT_OP.finditer(stream):
        whole = token.group(0)
        if whole.rstrip().endswith(b"Tm"):
            parts = whole.split()
            position = (float(parts[4]), float(parts[5]))
            continue
        if position is None:
            continue
        if token.group(7) is not None:
            text = "".join(_unescape(lit[1:-1]) for lit in _LITERAL.findall(token.group(7)))
        else:
            found = _LITERAL.findall(whole)
            if not found:
                continue
            text = _unescape(found[0][1:-1])
        if text.strip():
            runs.append((position[0], position[1], text))
    return runs


def _rows(stream: bytes) -> list[list[str]]:
    """Text runs grouped into visual rows by their y coordinate."""
    grouped: dict[float, list[tuple[float, str]]] = {}
    for x, y, text in extract_text_runs(stream):
        grouped.setdefault(round(y, 1), []).append((x, text.strip()))
    out = []
    for y in sorted(grouped, reverse=True):
        cells = [text for _, text in grouped[y] if text]
        if cells:
            out.append(cells)
    return out


def classify_row(cells: list[str]) -> tuple[dict[str, Any] | None, str]:
    """One personnel row's columns, recovered by shape, or the reason it is
    refused.

    The NAME cell is matched so that it can be *excluded*; its text is never
    returned. Everything left after salary, status, pay basis and name is the
    position title, and there must be exactly one of each.
    """
    salaries = [c for c in cells if _SALARY_CELL.match(c)]
    if not salaries:
        return None, "no_salary_cell"
    statuses = [c for c in cells if c in STATUS_VALUES]
    bases = [c for c in cells if c in PAY_BASIS_VALUES]
    rest = [
        c
        for c in cells
        if not _SALARY_CELL.match(c) and c not in STATUS_VALUES and c not in PAY_BASIS_VALUES
    ]
    names = [c for c in rest if _NAME_CELL.match(c)]
    titles = [c for c in rest if not _NAME_CELL.match(c)]
    if len(salaries) != 1 or len(statuses) != 1 or len(bases) != 1:
        return None, "row_does_not_carry_one_salary_status_and_pay_basis"
    if len(names) != 1 or len(titles) != 1:
        return None, "row_does_not_carry_one_name_and_one_title"
    amount = float(salaries[0][1:].replace(",", ""))
    return (
        {
            "title": titles[0],
            "amount": amount,
            "amountRaw": _SALARY_CELL.match(salaries[0]).group(1),
            "rateText": salaries[0],
            "status": statuses[0],
            "payBasis": bases[0],
        },
        "ok",
    )


def parse_staff_report(raw: bytes) -> dict[str, Any]:
    """The report's rows and its own as-of date. Names are discarded here."""
    streams = content_streams(raw)
    pages = [s for s in streams if b"TJ" in s or b"Tj" in s]
    if not pages:
        raise Unreadable("no text-bearing content streams in the document")

    as_of = ""
    header_seen = False
    rows: list[dict[str, Any]] = []
    refusals: dict[str, int] = {}
    for stream in pages:
        for cells in _rows(stream):
            joined = " ".join(cells)
            if not as_of:
                found = _AS_OF.search(joined)
                if found:
                    as_of = found.group(1).strip()
            if not header_seen and all(column in cells for column in EXPECTED_COLUMNS):
                header_seen = True
                continue
            record, reason = classify_row(cells)
            if record is None:
                if reason != "no_salary_cell":
                    refusals[reason] = refusals.get(reason, 0) + 1
                continue
            rows.append(record)

    if not header_seen:
        raise Unreadable(
            "the report's header row was not found; its columns are not the ones this parser reads"
        )
    if not as_of:
        raise Unreadable("the report states no 'As of Date:'; an undated roster cannot be cited")
    if not rows:
        raise Unreadable("no personnel rows were recovered beneath the header")
    return {
        "source": PAY_SOURCE,
        "asOfText": as_of,
        "rows": rows,
        "columns": list(EXPECTED_COLUMNS),
        "malformedRows": dict(sorted(refusals.items())),
    }


def load_staff_report(pdf_path: str | Path = DEFAULT_REPORT_PDF) -> dict[str, Any]:
    """The committed report, with the provenance its `.meta.json` recorded.

    Same digest check as `pay_tables.load_executive_schedule`: a
    `documentSha256` must vouch for bytes that were actually served.
    """
    path = Path(pdf_path)
    meta_path = path.with_name(path.name + ".meta.json")
    if not meta_path.exists():
        raise Unreadable(f"{path.name} has no .meta.json beside it; an undated fetch cannot be cited")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    recorded = str(meta.get("sha256") or "").lower()
    if not recorded:
        raise Unreadable(f"{meta_path.name} records no sha256")
    if digest != recorded:
        raise Unreadable(
            f"{path.name} does not match the digest its fetch recorded ({digest} vs {recorded}); "
            "the committed file is not the file that was served"
        )
    url = str(meta.get("url") or "")
    fetched_at = str(meta.get("fetched_at") or "")
    if not url or not fetched_at:
        raise Unreadable(f"{meta_path.name} is missing the url or the fetch time")
    if meta.get("error") or int(meta.get("status") or 0) != 200:
        raise Unreadable(f"{meta_path.name} records a fetch that did not serve the document")
    report = parse_staff_report(raw)
    return {"report": report, "url": url, "fetched_at": fetched_at, "sha256": digest, "file": str(path)}


#: The multiplicity suffix `scripts/expand_whitehouse_office.py` writes on a
#: node standing for several holders: " (×4)". Read only to set it aside for
#: the roster lookup and to check the count; the same shape
#: `build_graph.annotate_stated_counts` reads.
_MULTIPLICITY_SUFFIX = re.compile(r"\s*\(\u00d7\s*(\d+)\s*\)\s*$")


def stated_multiplicity(name: str) -> int | None:
    """The N in a trailing "(×N)", or None when the name states none."""
    match = _MULTIPLICITY_SUFFIX.search(str(name or ""))
    return int(match.group(1)) if match else None


def strip_multiplicity(name: str) -> str:
    """The name with a trailing "(×N)" removed."""
    return _MULTIPLICITY_SUFFIX.sub("", str(name or "")).strip()


def canonical(text: str) -> str:
    """Upper-case, ampersand spelled out, punctuation dropped, spaces
    collapsed — so that "Director of Scheduling & Advance" and "DIRECTOR OF
    SCHEDULING AND ADVANCE" are the same string and nothing else is."""
    upper = str(text or "").upper().replace("&", " AND ")
    return " ".join(re.sub(r"[^A-Z0-9 ]+", " ", upper).split())


def title_core(title: str) -> str:
    """A report title with its White House commissioning rank folded off the
    front, if it carries one. A leading prefix only, never a containment."""
    key = canonical(title)
    for prefix in RANK_PREFIXES:
        if key.startswith(prefix):
            folded = key[len(prefix):].strip()
            if len(folded.split()) >= MIN_CORE_TOKENS:
                return folded
            return key
    return key


def index_report_titles(rows: Iterable[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Title -> every row carrying it, under both the title as printed and the
    title with its rank folded off.

    Both keys, because the graph carries both spellings: the curated nodes
    that predate this module are named for the function alone ("Chief of
    Staff") while the nodes `scripts/expand_whitehouse_office.py` adds from
    this same report are named as the report prints them ("Assistant to the
    President and Chief of Staff"). Equality is tried before the fold in
    `build_records`, the order `congress.match_committee_list` already uses,
    so a node named exactly as the source prints it is never recorded as a
    folded match.

    A row is filed under one key when the two coincide, so a title held by
    one person cannot look like two by being counted under both spellings.
    """
    index: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        printed = canonical(str(row.get("title") or ""))
        for key in {printed, title_core(str(row.get("title") or ""))}:
            index.setdefault(key, []).append(dict(row))
    return index


def scoped_node_ids(root: Mapping[str, Any]) -> set[str]:
    """Every node id beneath the White House Office, inclusive."""
    found: set[str] = set()

    def collect(node: Mapping[str, Any]) -> None:
        node_id = str(node.get("id") or "")
        if node_id:
            found.add(node_id)
        for child in node.get("children") or []:
            collect(child)

    def search(node: Mapping[str, Any]) -> bool:
        if str(node.get("id") or "") == SCOPE_NODE_ID:
            collect(node)
            return True
        return any(search(child) for child in node.get("children") or [])

    search(root)
    return found


def build_records(
    node_map: Mapping[str, Mapping[str, Any]],
    report: Mapping[str, Any],
    *,
    url: str,
    sha256: str,
    retrieved_at: str,
    scope_ids: Iterable[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """A financial-evidence record for each White House Office position the
    report prices unambiguously. The caller validates each against its node."""
    index = index_report_titles(report["rows"])
    as_of = str(report["asOfText"])
    as_of_day = as_of_date(as_of)
    # FY N runs 1 Oct N-1 to 30 Sep N, so a 1 July report falls in the fiscal
    # year of its own calendar year.
    fiscal_year = as_of_day.year + 1 if as_of_day.month >= 10 else as_of_day.year
    in_scope = set(scope_ids)
    records: dict[str, dict[str, Any]] = {}
    refusals: dict[str, int] = {}
    considered = 0

    def refuse(reason: str) -> None:
        refusals[reason] = refusals.get(reason, 0) + 1

    for node_id, node in sorted(node_map.items()):
        if node_id not in in_scope or node_id == SCOPE_NODE_ID:
            continue
        if str(node.get("type") or "").casefold() != "position":
            continue
        considered += 1
        name = str(node.get("name") or "")
        key = canonical(name)
        matches = index.get(key)
        stated = stated_multiplicity(name)
        if not matches and stated is not None:
            # `scripts/expand_whitehouse_office.py` names a title several
            # people hold "<title> (×N)", with N the report's own count. The
            # parenthetical is the graph's, not the report's, so the lookup
            # sets it aside -- and only accepts the rows when there are exactly
            # N of them, so the count in the name is the join condition rather
            # than decoration.
            # Only rows PRINTED as that title: the index files a row under its
            # folded spelling too, so the bucket for "PRESIDENTIAL
            # SPEECHWRITER" also holds "SPECIAL ASSISTANT TO THE PRESIDENT AND
            # PRESIDENTIAL SPEECHWRITER", and counting those refused a title
            # the report lists exactly N times at one rate (found by review).
            stripped_key = canonical(strip_multiplicity(name))
            candidates = [m for m in index.get(stripped_key) or [] if canonical(m["title"]) == stripped_key]
            if candidates and len(candidates) == stated:
                matches = candidates
        if not matches:
            refuse("no_row_carries_this_title")
            continue
        # A title several people hold WAS refused outright -- "two salaries
        # make the figure undecidable" -- and that is right whenever the
        # salaries differ. Measured on the 2026 report (2026-09-23): 58 titles
        # are held by more than one person and 23 of them list every holder at
        # one identical rate, so for those the figure is decidable and the
        # honest claim is "the report lists all N people under this title at
        # $X". The record says so (`holders`), the multi-post sweep keeps it
        # only where N is the count the node's own name states, and the panel
        # prints "N people" rather than "one person". Differing rates, or any
        # holder at $0.00, still refuse.
        if len(matches) > 1:
            # One PRINTED title, or nothing. `index_report_titles` files a row
            # under its folded spelling too, so "ASSISTANT TO THE PRESIDENT
            # AND X" and "DEPUTY ASSISTANT TO THE PRESIDENT AND X" -- two
            # appointments, which CLAUDE.md records as different ones -- both
            # land under X. At one rate they would otherwise read as one title
            # listed twice, with the quote naming only the first. Latent on
            # the 2026 report (its four fold-collision keys each print several
            # rates) and refused before it can be live.
            if len({str(m["title"]) for m in matches}) != 1:
                refuse("title_held_under_several_spellings")
                continue
            amounts = {float(m["amount"]) for m in matches}
            if len(amounts) != 1:
                refuse("title_held_by_several_people_at_different_rates")
                continue
            if any(float(m["amount"]) <= 0 for m in matches):
                refuse("reported_rate_is_zero")
                continue
            statuses = {str(m["status"]) for m in matches}
            bases = {str(m["payBasis"]) for m in matches}
            if len(statuses) != 1 or len(bases) != 1:
                refuse("title_held_by_several_people_on_different_terms")
                continue
        row = matches[0]
        if float(row["amount"]) <= 0:
            # Ten of the 2026 report's rows are $0.00. Zero is never published
            # as an amount in this repository, and the reason holds here: an
            # uncompensated appointment is a fact about the arrangement one
            # person has, not about the post.
            refuse("reported_rate_is_zero")
            continue
        quote = (
            f"{row['title']}; {row['rateText']}; {row['payBasis']}; {row['status']} "
            f"(As of Date: {as_of})"
        )
        if len(matches) > 1:
            quote = f"{quote} — listed {len(matches)} times, each at {row['rateText']}"
        records[node_id] = {
            "nodeId": node_id,
            "financialEvidenceStatus": "partial",
            "costBasis": "basic_pay",
            "amount": float(row["amount"]),
            "amountRaw": row["amountRaw"],
            "units": "usd",
            "normalizedMultiplier": 1,
            "unitsEvidence": quote,
            "quote": quote,
            "fiscalYear": fiscal_year,
            "periodCoverage": "annual_rate",
            "periodAsOf": as_of_day.isoformat(),
            "amountScope": row["title"],
            "scopeMatch": "proxy",
            "rollupRole": "line",
            "sourceType": PAY_SOURCE_TYPE,
            "sourceUrl": url,
            "documentSha256": sha256,
            "retrievedAt": retrieved_at,
            "locator": {
                "table": "Annual Report to Congress on White House Staff",
                "row": row["title"],
                "column": "SALARY",
            },
            "reportedTitle": row["title"],
            "reportedStatus": row["status"],
            "payBasis": row["payBasis"],
            "rateText": row["rateText"],
            "asOf": as_of,
            "asOfDate": as_of_day.isoformat(),
            # Whether *this match* needed the fold, not merely whether the
            # title carries a rank: a node named as the report prints it
            # matched on equality and the panel must not claim otherwise.
            "titleFolded": key != canonical(row["title"]),
        }
        if len(matches) > 1:
            records[node_id]["holders"] = {
                "count": len(matches),
                "uniformRate": True,
                "appliesToEachHolder": True,
                "note": (
                    f"The report lists {len(matches)} people under this title, every one at "
                    f"{row['rateText']}; the figure is each listed person's pay, not one person's "
                    "and not the group's combined pay."
                ),
            }

    report_out = {
        "source": PAY_SOURCE,
        "asOf": as_of,
        "asOfDate": as_of_day.isoformat(),
        "url": url,
        "documentSha256": sha256,
        "retrievedAt": retrieved_at,
        "rowsRead": len(report["rows"]),
        "distinctTitles": len(index),
        "malformedRows": dict(report.get("malformedRows") or {}),
        "considered": considered,
        "priced": len(records),
        "refused": dict(sorted(refusals.items())),
    }
    return records, report_out


def load_pay_evidence(path: str | Path = DEFAULT_PAY_EVIDENCE_PATH) -> dict[str, dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        loaded = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    nodes = loaded.get("nodes") if isinstance(loaded, dict) else None
    return nodes if isinstance(nodes, dict) else {}


def apply_pay_evidence(
    root: dict[str, Any],
    records: Mapping[str, Mapping[str, Any]],
    *,
    index_tree: Any = None,
) -> dict[str, Any]:
    """Stamp `positionReportedPay` on every White House Office position the
    report prices.

    A third field beside `positionPayRate` and `positionStatutoryPay`, because
    it is a third claim shape: not a rank joined to a rate, and not a statute's
    figure for an office, but what one named individual is reported to be paid.
    The release gate checks each field against its own source's rules.
    """
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, _ = index_tree(root)
    in_scope = scoped_node_ids(root)
    stats = {
        "priced": 0,
        "unknown_node": 0,
        "not_a_position": 0,
        "outside_the_white_house_office": 0,
        "name_no_longer_matches": 0,
    }
    for node_id, record in sorted(records.items()):
        node = node_map.get(node_id)
        if node is None:
            stats["unknown_node"] += 1
            continue
        if str(node.get("type") or "").casefold() != "position":
            stats["not_a_position"] += 1
            continue
        if node_id not in in_scope or node_id == SCOPE_NODE_ID:
            stats["outside_the_white_house_office"] += 1
            continue
        # A rename in the curated file must withdraw the figure rather than
        # let it ride on a node the report's title no longer names — the same
        # guard `evidence.evidence_names_this_node` applies to page evidence.
        reported = str(record.get("reportedTitle") or "")
        node_name = str(node.get("name") or "")
        accepted = {canonical(node_name)}
        if isinstance(record.get("holders"), dict) and stated_multiplicity(node_name) == record["holders"].get("count"):
            accepted.add(canonical(strip_multiplicity(node_name)))
        if not accepted & {canonical(reported), title_core(reported)}:
            stats["name_no_longer_matches"] += 1
            continue
        uniform = isinstance(record.get("holders"), dict) and record["holders"].get("uniformRate") is True
        node["positionReportedPay"] = {
            "source": PAY_SOURCE,
            "sourceLabel": "the White House Office's own annual report to Congress on its personnel",
            "method": PAY_METHOD_UNIFORM if uniform else PAY_METHOD,
            "amount": record.get("amount"),
            "rateText": record.get("rateText"),
            "payBasis": record.get("payBasis"),
            "reportedTitle": reported,
            "reportedStatus": record.get("reportedStatus"),
            "titleFolded": bool(record.get("titleFolded")),
            "asOf": record.get("asOf"),
            "costBasis": record.get("costBasis"),
            "scopeMatch": record.get("scopeMatch"),
            "financialEvidenceStatus": record.get("financialEvidenceStatus"),
            "amountScope": record.get("amountScope"),
            "quote": record.get("quote"),
            "url": str(record.get("sourceUrl") or ""),
            "checkedAt": record.get("retrievedAt"),
        }
        if isinstance(record.get("holders"), dict):
            # Kept by the multi-post sweep only where this count is the count
            # the node's own name states; stripped otherwise.
            node["positionReportedPay"]["holders"] = dict(record["holders"])
        stats["priced"] += 1
        # Deliberately not written: sourceUrls, sourceTypes, lastVerified,
        # verificationMethod. A payroll roster says what someone is paid; it
        # is not evidence that the graph draws this post correctly. The
        # Executive Schedule defect that once made 29 positions read
        # `verified` on the strength of a table naming no post is the reason
        # this is restated rather than assumed to carry over.
    return stats
