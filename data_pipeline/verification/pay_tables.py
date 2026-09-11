"""OPM's Executive Schedule salary table, and the one claim it can honestly
make about a position node.

This is the first module in the repository that reads a *rate* rather than a
flow, and the distinction is the whole reason it is written carefully.

## The claim, and why it takes two sources to make

The PLUM archive says a post is paid at Executive Schedule Level III. It does
not say what Level III pays. OPM's Salary Table No. 2026-EX says Level III
pays $209,600. It does not say which posts are at Level III. Neither document
on its own says what this position pays, and the join of the two is weaker
than either:

- the level is the **previous administration's** archive (January 21, 2021 -
  January 20, 2025). It is a past report about a past incumbency.
- the table is **effective January 2026**, which is after that archive closed.

So the only defensible sentence is the two-sourced one: *the archive reports
this post at Level III; the January 2026 table pays Level III $209,600* — and
neither half says what the post pays whoever holds it now. Every record this
module writes carries both halves with their own dates (`levelClaim`), and
the panel prints both. `scopeMatch` is `proxy`, never `exact`, because the
table names a rank and not this unit: `financial_evidence.classify` therefore
grades every one of these `partial`, and no route exists by which one becomes
`verified`.

## Basic pay is not the node's cost

`resolved_total_amount` everywhere else in this graph is a share of federal
outlays. A rate of basic pay is not that: it excludes benefits, it is one
post's rate rather than the unit's spending, and adding it to anything would
be adding two different measurements. Nothing here writes a cost field, and
the release gate checks that the figure never reaches one.

## The refusal that matters most

The archive's `LevelGradePay` column carries a General Schedule *grade* in the
same column as an Executive Schedule *level*, and 5,455 of its rows are GS
grades. Those are Arabic ("15") where a level is Roman ("IV"), so the shapes
do not collide — but the pay plan is what actually settles it, and two rows of
the archive prove the point: "THE SECRETARY" carries level III on an `AD`
(administratively determined) pay plan and "BOARD MEMBER - CHAIR" carries
level III on `WC`. Neither is paid from the Executive Schedule. Keying on the
numeral alone would have published $209,600 for both.

So a rate is published only where the archive gives **both** an `EX` pay plan
and a level the table actually prints. 29 of the graph's 126 matched positions
qualify; the 30th that carries "a level or grade" is a GS-15 and is refused.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "opm" / "pay"
DEFAULT_PAY_TABLE_HTML = FIXTURE_DIR / "executive_schedule_2026.html"
DEFAULT_PAY_EVIDENCE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "verification" / "pay_evidence.json"
)

#: The five levels the Executive Schedule has. A table printing a sixth has
#: been restructured, and a parser that shrugged at that would be guessing.
EXECUTIVE_SCHEDULE_LEVELS = ("I", "II", "III", "IV", "V")

#: The archive's pay-plan code for the Executive Schedule. `ES` is the Senior
#: Executive Service — a different pay system entirely, and the archive's most
#: common code — so the two must never be folded together.
EX_PAY_PLAN = "EX"

PAY_SOURCE = "opm_executive_schedule"
PAY_SOURCE_TYPE = "opm_pay_table"
PAY_METHOD = "rate_for_the_level_reported_in_the_plum_archive"

#: The columns the table must have, lowercased. Anything else means OPM
#: reshaped the page and this parser no longer knows what it is reading.
EXPECTED_COLUMNS = ("level", "rate")

_LEVEL_CELL = re.compile(r"^Level\s+([IVX]+)$", re.IGNORECASE)
_RATE_CELL = re.compile(r"^\$\s*([0-9][0-9,]*)$")
_TABLE_NUMBER = re.compile(r"^Salary Table No\.\s*(\S+)$", re.IGNORECASE)
_EFFECTIVE = re.compile(r"^Effective\s+([A-Z][a-z]+)\s+(\d{4})$")

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

#: Tags that implicitly close an open <p>, per HTML5's optional end tags.
#: `html.parser` does not model this, so without it an unclosed footnote
#: swallows everything after it until the next </p> — and the panel prints a
#: footnote verbatim, in quotation marks, as OPM's own words. A red team got
#: "continues through January 30, 2026.UNRELATED PROSE" into one quotation
#: that way, from markup that is perfectly valid HTML5.
_CLOSES_A_PARAGRAPH = {
    "address", "article", "aside", "blockquote", "details", "div", "dl",
    "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3",
    "h4", "h5", "h6", "header", "hgroup", "hr", "main", "menu", "nav", "ol",
    "p", "pre", "section", "table", "ul",
}


class Unreadable(Exception):
    """The page is not the table this parser knows how to read.

    Raised rather than returning a partial result: a salary table read wrong
    is five numbers published under an opm.gov URL, which is exactly the
    failure `tests/fixtures/opm/pay/README.md` refused to risk by declining to
    type the table in by hand.
    """


def _collapse(text: str) -> str:
    return " ".join(text.split())


class ExecutiveScheduleParser(HTMLParser):
    """The data table's header and body rows, the headings around it, and the
    footnotes beneath it.

    The header row is captured for the same reason `SenateCommitteeTableParser`
    captures it: so a reshaped table is noticed rather than read as if nothing
    had changed.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.columns: list[str] = []
        self.rows: list[dict[str, Any]] = []
        self.headings: list[str] = []
        self.footnotes: list[str] = []
        #: How many headings had been seen when the data table opened, so the
        #: table's number and effective date are read from the headings that
        #: precede *it* rather than from anywhere on the page.
        self.headings_before_table: int | None = None
        self.data_tables = 0
        self._in_table = False
        self._in_thead = False
        self._cell: list[str] | None = None
        self._row: list[str] | None = None
        self._heading: list[str] | None = None
        self._footnote: list[str] | None = None

    def _close_footnote(self) -> None:
        if self._footnote is None:
            return
        text = _collapse("".join(self._footnote))
        if text:
            self.footnotes.append(text)
        self._footnote = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {k: (v or "") for k, v in attrs}
        classes = attributes.get("class", "").split()
        # HTML5 lets a <p> be closed by the next block element. Flush first, or
        # the text after it is spliced into the quotation.
        if tag in _CLOSES_A_PARAGRAPH:
            self._close_footnote()
        if tag == "table":
            if "DataTable" in classes:
                self.data_tables += 1
                self._in_table = True
                if self.headings_before_table is None:
                    self.headings_before_table = len(self.headings)
            else:
                self._in_table = False
            return
        if tag in ("h1", "h2", "h3", "h4"):
            self._heading = []
            return
        if tag == "p" and "Footnote" in classes:
            self._footnote = []
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
        if tag in ("h1", "h2", "h3", "h4") and self._heading is not None:
            text = _collapse("".join(self._heading))
            if text:
                self.headings.append(text)
            self._heading = None
            return
        if tag == "p" and self._footnote is not None:
            self._close_footnote()
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
            cells = [c for c in self._row]
            if cells:
                self.rows.append({"cells": cells, "text": _collapse(" ".join(cells))})
            self._row = None

    def handle_data(self, data: str) -> None:
        for sink in (self._cell, self._heading, self._footnote):
            if sink is not None:
                sink.append(data)
                return


def parse_executive_schedule(html: str) -> dict[str, Any]:
    """The table as the page prints it, or `Unreadable`.

    Returns the table number, the effective heading verbatim, a derived
    first-of-month date for it, every level with the rate as printed and as a
    number, the row text each rate was read from, and every footnote — all of
    them, not only the pay freeze, because a note this module did not think to
    look for is exactly the one that would go missing.
    """
    parser = ExecutiveScheduleParser()
    parser.feed(html)
    parser.close()
    parser._close_footnote()

    if not parser.rows:
        raise Unreadable("no rows found in a table classed DataTable")
    if parser.data_tables > 1:
        # Which table the headings date, and which rates belong to which, is
        # not decidable from this parser's model of the page.
        raise Unreadable(
            f"{parser.data_tables} tables classed DataTable; this parser reads a page with one"
        )
    columns = tuple(c.casefold() for c in parser.columns)
    if columns != EXPECTED_COLUMNS:
        raise Unreadable(
            f"the table's columns are {parser.columns!r}, not "
            f"{list(EXPECTED_COLUMNS)!r}; it has been reshaped"
        )

    # Only the headings *above* the table, and the nearest one of each kind.
    # Scanning the whole page would let a heading somewhere else date these
    # rates — the date is the difference between a current rate and a
    # historical one, so it has to be the table's own.
    above = parser.headings[: parser.headings_before_table or 0]
    number = ""
    effective_text = ""
    for heading in above:
        if _TABLE_NUMBER.match(heading):
            number = heading
        if _EFFECTIVE.match(heading):
            effective_text = heading
    if not number:
        raise Unreadable(
            "no 'Salary Table No. ...' heading above the table; an unnumbered table is not citable"
        )
    if not effective_text:
        raise Unreadable(
            "no 'Effective <Month> <Year>' heading above the table; an undated rate is not evidence"
        )

    month_name, year_text = _EFFECTIVE.match(effective_text).groups()
    month = _MONTHS.get(month_name.casefold())
    if month is None:
        raise Unreadable(f"effective heading {effective_text!r} names no month this parser knows")
    effective = date(int(year_text), month, 1)

    levels: dict[str, dict[str, Any]] = {}
    for row in parser.rows:
        if len(row["cells"]) != 2:
            raise Unreadable(f"row {row['text']!r} does not have exactly a level and a rate")
        level_cell, rate_cell = row["cells"]
        level_match = _LEVEL_CELL.match(level_cell)
        if not level_match:
            raise Unreadable(f"cell {level_cell!r} is not a level this parser will read")
        level = level_match.group(1).upper()
        if level not in EXECUTIVE_SCHEDULE_LEVELS:
            raise Unreadable(
                f"level {level!r} is not one of the Executive Schedule's five "
                f"({', '.join(EXECUTIVE_SCHEDULE_LEVELS)})"
            )
        if level in levels:
            raise Unreadable(f"level {level!r} is printed twice; which row is the rate is not decidable")
        rate_match = _RATE_CELL.match(rate_cell)
        if not rate_match:
            raise Unreadable(f"cell {rate_cell!r} is not a rate this parser will read")
        amount = float(rate_match.group(1).replace(",", ""))
        if amount <= 0:
            raise Unreadable(f"rate {rate_cell!r} is not a positive figure")
        levels[level] = {
            "level": level,
            "amount": amount,
            # The digits as the page prints them, without the dollar sign:
            # `financial_evidence.parse_amount_text` reads the figure and not
            # the currency mark, and the mark is carried in `rateText`.
            "amountRaw": rate_match.group(1),
            "rateText": rate_cell,
            "rowText": row["text"],
            "levelText": level_cell,
        }

    # All five, or this is not the Executive Schedule. A single omitted </tr>
    # — legal HTML5 — silently drops a row, and a table quietly missing Level
    # IV would simply leave twelve posts unpriced while the run record blamed
    # it on the pay plan. The module declares the schedule has five levels;
    # reading four and carrying on would be guessing which one went missing.
    if set(levels) != set(EXECUTIVE_SCHEDULE_LEVELS):
        missing = sorted(set(EXECUTIVE_SCHEDULE_LEVELS) - set(levels), key=EXECUTIVE_SCHEDULE_LEVELS.index)
        raise Unreadable(
            f"the table prints {len(levels)} of the Executive Schedule's five levels "
            f"(missing {', '.join(missing)}); a partial table is not this table"
        )

    return {
        "source": PAY_SOURCE,
        "table": number,
        "effectiveText": effective_text,
        "effective": effective.isoformat(),
        # Said plainly because it is an inference, small but real: the heading
        # names a month, and the Executive Schedule's rates actually take
        # effect on the first pay period beginning on or after January 1. The
        # verbatim heading rides beside it so a reader can see what was stated.
        "effectiveFrom": "first of the month named in the heading, derived",
        "levels": levels,
        "footnotes": list(parser.footnotes),
        "columns": list(parser.columns),
    }


def federal_fiscal_year_of(day: date) -> int:
    """FY N runs 1 Oct N-1 to 30 Sep N."""
    return day.year + 1 if day.month >= 10 else day.year


def load_executive_schedule(html_path: str | Path = DEFAULT_PAY_TABLE_HTML) -> dict[str, Any]:
    """The committed table, with the provenance its `.meta.json` recorded.

    The digest is recomputed from the bytes on disk and checked against the
    one the fetch wrote. That check is the point: a record's `documentSha256`
    is a claim that this figure came out of that document, and a fixture
    edited after the fetch would otherwise carry a digest that vouches for
    bytes nobody served. A mismatch is refused rather than re-hashed, because
    re-hashing would launder exactly the edit the check exists to catch.
    """
    path = Path(html_path)
    meta_path = path.with_name(path.name + ".meta.json")
    if not meta_path.exists():
        raise Unreadable(
            f"{path.name} has no .meta.json beside it; a table with no record of its fetch "
            "carries no URL and no date, and cannot be cited"
        )
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    recorded = str(meta.get("sha256") or "").lower()
    if not recorded:
        raise Unreadable(f"{meta_path.name} records no sha256; the fetch it describes served nothing")
    if digest != recorded:
        raise Unreadable(
            f"{path.name} does not match the digest its fetch recorded "
            f"({digest} vs {recorded}); the committed file is not the file that was served"
        )
    url = str(meta.get("url") or "")
    fetched_at = str(meta.get("fetched_at") or "")
    if not url or not fetched_at:
        raise Unreadable(f"{meta_path.name} is missing the url or the fetch time")
    if meta.get("error") or int(meta.get("status") or 0) != 200:
        raise Unreadable(
            f"{meta_path.name} records a fetch that did not serve the page "
            f"(status {meta.get('status')!r}, error {meta.get('error')!r})"
        )
    table = parse_executive_schedule(raw.decode("utf-8", errors="replace"))
    return {
        "table": table,
        "url": url,
        "fetched_at": fetched_at,
        "sha256": digest,
        "file": str(path),
    }


def load_pay_evidence(path: str | Path = DEFAULT_PAY_EVIDENCE_PATH) -> dict[str, dict[str, Any]]:
    """The derived records, or nothing. A missing file is not an error: the
    exporter must build without it, exactly as it does without the others."""
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        loaded = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    nodes = loaded.get("nodes") if isinstance(loaded, dict) else None
    return nodes if isinstance(nodes, dict) else {}


def _listing_of(record: Mapping[str, Any]) -> tuple[str, str]:
    """The pay plan and level a position-evidence record reports, as text."""
    return str(record.get("payPlan") or "").strip(), str(record.get("payLevel") or "").strip()


def eligible(record: Mapping[str, Any], table: Mapping[str, Any]) -> tuple[bool, str]:
    """Whether the archive's report of this post can be priced by this table.

    Both halves are required, and the pay plan is the one that matters: a
    Roman numeral on an `AD` or `WC` pay plan is a rank in some other system,
    and the archive contains two of those.
    """
    pay_plan, level = _listing_of(record)
    if record.get("reportedPay") is not None:
        return False, "archive_reports_a_rate"
    if not level:
        return False, "no_level_reported"
    if not pay_plan:
        return False, "no_pay_plan_reported"
    if pay_plan != EX_PAY_PLAN:
        return False, f"pay_plan_is_{pay_plan.casefold()}_not_executive_schedule"
    if level not in table["levels"]:
        return False, f"level_{level}_is_not_printed_in_this_table"
    # The archive must have printed this pay plan and this level on one row.
    # positions.describe_listing aggregates the two independently, so without
    # this the pair could be assembled from two rows that each state only half
    # of it. Absent on records derived before that field existed, which is
    # refused rather than assumed: an unpriced post is a gap, a wrongly priced
    # one is a false claim.
    if not record.get("payPlanAndLevelOnOneRow"):
        return False, "pay_plan_and_level_never_printed_on_one_row"
    return True, "listed_at_an_executive_schedule_level"


def level_claim(record: Mapping[str, Any]) -> dict[str, Any]:
    """The archive's half of the claim, with its own dates.

    Kept whole and separate rather than flattened into the pay record, because
    the point of the whole module is that these are two sources and the reader
    has to be able to see which one said what.
    """
    pay_plan, level = _listing_of(record)
    return {
        "payLevel": level,
        "payPlan": pay_plan,
        "listedTitle": record.get("listedTitle"),
        "source": record.get("source"),
        "edition": record.get("edition"),
        "period": record.get("period"),
        "url": record.get("url"),
        "checkedAt": record.get("checkedAt"),
        "valuesFrom": record.get("valuesFrom"),
    }


def build_records(
    listings: Mapping[str, Mapping[str, Any]],
    table: Mapping[str, Any],
    *,
    url: str,
    sha256: str,
    retrieved_at: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """A financial-evidence record for every position the table can price.

    The records are the shape `financial_evidence.validate_record` checks; the
    caller validates each against its node, which is where a record is bound to
    a real node of the right kind.
    """
    effective = date.fromisoformat(str(table["effective"]))
    fiscal_year = federal_fiscal_year_of(effective)
    records: dict[str, dict[str, Any]] = {}
    refusals: dict[str, int] = {}
    for node_id, listing in sorted(listings.items()):
        ok, reason = eligible(listing, table)
        if not ok:
            refusals[reason] = refusals.get(reason, 0) + 1
            continue
        level = table["levels"][_listing_of(listing)[1]]
        records[node_id] = {
            "nodeId": node_id,
            "financialEvidenceStatus": "partial",
            "costBasis": "basic_pay",
            "amount": float(level["amount"]),
            "amountRaw": level["amountRaw"],
            "units": "usd",
            "normalizedMultiplier": 1,
            # The row as the page renders it. It carries the figure with its
            # dollar sign attached, which is how this page states its scale.
            "unitsEvidence": level["rowText"],
            "quote": level["rowText"],
            "fiscalYear": fiscal_year,
            "periodCoverage": "annual_rate",
            "periodAsOf": table["effective"],
            # What the source named. It named a rank, not this unit — which is
            # exactly why the scope below is a proxy and the record can never
            # be graded `verified`.
            "amountScope": level["levelText"],
            "scopeMatch": "proxy",
            "rollupRole": "line",
            "sourceType": PAY_SOURCE_TYPE,
            "sourceUrl": url,
            "documentSha256": sha256,
            "retrievedAt": retrieved_at,
            "locator": {"table": table["table"], "row": level["levelText"], "column": "Rate"},
            # --- the two halves, each with its own date ---------------------
            "levelClaim": level_claim(listing),
            "table": table["table"],
            "effectiveText": table["effectiveText"],
            "rateText": level["rateText"],
            # Every footnote the page carries, not only the one about the pay
            # freeze: a note nobody thought to look for is the one that goes
            # missing. The freeze note is the reason this field is required —
            # the table's rate is not necessarily what was payable.
            "tableFootnotes": list(table.get("footnotes") or []),
        }
    report = {
        "source": PAY_SOURCE,
        "table": table["table"],
        "effective": table["effective"],
        "effectiveText": table["effectiveText"],
        "url": url,
        "documentSha256": sha256,
        "retrievedAt": retrieved_at,
        "levels": {k: v["amount"] for k, v in table["levels"].items()},
        "footnotes": list(table.get("footnotes") or []),
        "listings_considered": len(listings),
        "priced": len(records),
        "refused": dict(sorted(refusals.items())),
        "priced_by_level": {
            level_id: sum(1 for r in records.values() if r["levelClaim"]["payLevel"] == level_id)
            for level_id in EXECUTIVE_SCHEDULE_LEVELS
        },
    }
    return records, report


def withdraw_pay_from_multi_post_nodes(root: dict[str, Any]) -> int:
    """Take the rate off any node that stands for several posts.

    Run *after* `annotate_stated_counts`, which is the only thing that computes
    `representsPosts`. The guard inside `apply_pay_evidence` cannot do this
    job: that runs before the tree is pruned and before the counts are
    annotated, so on a fresh build the field it tests does not exist yet and
    the guard silently passes — a red team caught exactly that, with a rate
    published on a node named "... (×4)" and `stands_for_many_posts: 0` in the
    run record.

    742 position nodes carry a multiplicity. One rate on such a node reads as
    what a single holder is paid while the panel beside it describes a group.
    """
    withdrawn = 0
    stack = [root]
    while stack:
        node = stack.pop()
        if node.get("representsPosts") and node.pop("positionPayRate", None) is not None:
            withdrawn += 1
        stack.extend(node.get("children") or [])
    return withdrawn


def apply_pay_evidence(
    root: dict[str, Any],
    records: Mapping[str, Mapping[str, Any]],
    *,
    index_tree: Any = None,
) -> dict[str, Any]:
    """Stamp `positionPayRate` on every position whose published listing still
    reports the level the record was derived from.

    The dependency is the safety rule, and it is deliberately strict: this
    figure is only meaningful as a gloss on the archive's level, so it is
    published only where that listing is itself published and still says the
    same thing. If `positions.py` withdraws a listing — the record dropped, the
    node renamed, the title no longer naming the post — the rate goes with it
    rather than outliving the claim it rests on.
    """
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, _ = index_tree(root)
    stats = {
        "priced": 0,
        "unknown_node": 0,
        "not_a_position": 0,
        "no_listing_published": 0,
        "listing_reports_a_different_level": 0,
        "listing_reports_a_rate": 0,
        "stands_for_many_posts": 0,
    }
    for node_id, record in sorted(records.items()):
        node = node_map.get(node_id)
        if node is None:
            stats["unknown_node"] += 1
            continue
        if "position" not in str(node.get("type") or "").casefold():
            stats["not_a_position"] += 1
            continue
        # 742 position nodes stand for several posts at once ("×multiple",
        # a range, an exact count). One rate on such a node reads as what one
        # holder is paid, and the panel's own sentence for those nodes says any
        # figure above is the group's — the two would contradict each other.
        if node.get("representsPosts"):
            stats["stands_for_many_posts"] += 1
            continue
        listing = node.get("positionListing")
        if not isinstance(listing, Mapping):
            stats["no_listing_published"] += 1
            continue
        claim = record.get("levelClaim") or {}
        if listing.get("reportedPay") is not None:
            stats["listing_reports_a_rate"] += 1
            continue
        if (
            str(listing.get("payLevel") or "") != str(claim.get("payLevel") or "")
            or str(listing.get("payPlan") or "") != EX_PAY_PLAN
        ):
            stats["listing_reports_a_different_level"] += 1
            continue

        url = str(record.get("sourceUrl") or "")
        node["positionPayRate"] = {
            "source": PAY_SOURCE,
            "method": PAY_METHOD,
            "payLevel": claim.get("payLevel"),
            "payPlan": claim.get("payPlan"),
            "amount": record.get("amount"),
            "rateText": record.get("rateText"),
            "table": record.get("table"),
            "effectiveText": record.get("effectiveText"),
            "effective": record.get("periodAsOf"),
            "fiscalYear": record.get("fiscalYear"),
            "costBasis": record.get("costBasis"),
            "scopeMatch": record.get("scopeMatch"),
            "financialEvidenceStatus": record.get("financialEvidenceStatus"),
            "amountScope": record.get("amountScope"),
            "quote": record.get("quote"),
            "footnotes": list(record.get("tableFootnotes") or []),
            "levelSource": {
                "source": claim.get("source"),
                "edition": claim.get("edition"),
                "period": claim.get("period"),
                "listedTitle": claim.get("listedTitle"),
                "url": claim.get("url"),
                "checkedAt": claim.get("checkedAt"),
            },
            "url": url,
            "checkedAt": record.get("retrievedAt"),
        }
        stats["priced"] += 1
        # Deliberately NOT written: `sourceUrls`, `evidenceUrls`, `sourceTypes`,
        # `lastVerified`, `verificationMethod`. A salary table says what a rank
        # pays. It does not say this unit exists, and every one of those fields
        # is read elsewhere as a claim that something does.
        #
        # Not a theoretical scruple: the first version of this function appended
        # the table's URL to `sourceUrls`, and the release gate passed the
        # result. `verify_node_sources` counts URLs and classifies hosts, so a
        # second `.gov` URL took these nodes from one source to two *and* added
        # `official_site` to `sourceTypes` — together carrying confidence from
        # 0.5 to 0.8, which is the `verified` threshold. 29 positions published
        # `verificationStatus: verified`, backed by `official_site`, on the
        # strength of a five-row table that names no post at all; the graph's
        # verified count went 49 -> 78 in one build. The URL rides in
        # `positionPayRate` only, where the panel shows it beside the claim it
        # actually supports.
    return stats
