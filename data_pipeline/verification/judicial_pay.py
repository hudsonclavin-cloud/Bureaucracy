"""The judicial compensation table published by the U.S. Courts, and the one
claim it can honestly make about a judicial-branch position node.

## One source, not two

`pay_tables.py` needed two documents because the PLUM archive names a rank
and a separate OPM table prices the rank. Judicial pay does not have that
seam: `uscourts.gov`'s own "Judicial Compensation" page states, in one table,
what each of four judicial pay tiers — District Judges, Circuit Judges,
Associate Justices, Chief Justice — pays for a given year, current year
first. The source is the whole claim; there is no archive to join it to.

That single source still does not name a specific node. The table's columns
are tiers ("Circuit Judges"), not the graph's node names ("Chief Judge, 1st
Circuit"), so a record here is `scopeMatch: "proxy"` for the same reason an
Executive Schedule record is: the source names a category of post, and the
join from category to a specific curated node is this module's own claim, not
the source's.

## What this module will and will not price

A federal judge's compensation is the same for every judge at the same tier
regardless of seniority within it — a circuit's chief judge earns the
circuit-judge rate, not a premium, because Article III courts have no
"chief's salary" the way the House has a Speaker's salary. So the nodes this
module prices are: the Chief Justice (the one node type-matched to the
table's own "Chief Justice" column), and every curated node that is a
specific circuit's or a specific district's own Chief Judge — priced at that
tier's rate, because a chief judge IS a circuit or district judge, paid as
one.

It will not price:

- any node standing for more than one holder (`representsPosts`) — the same
  rule `pay_tables.py` enforces, for the same reason: 351 circuit- and
  district-judge nodes in this graph state a count, and one rate on a node
  named "(×28 active + senior judges)" reads as what a single judge earns.
- `jud-district-structure-chief-judge`, the one node under "All 94 District
  Courts — Standard Structure" that describes what every district's
  organisation looks like rather than naming one district's actual chief
  judge. It carries no count in its own name, so the multi-post guard above
  does not catch it; this module refuses it by id.
- the specialized Article I courts (Tax Court, Court of Federal Claims,
  Court of International Trade, CAAF, CAVC). Their judges' pay follows other
  statutory provisions this module has not read a source for; pricing them
  from the Article III table would be guessing that the numbers are the
  same. **Four of those provisions have since been read**, and
  `derived_pay.py` prices those courts' chief judges from them in a field of
  its own -- a figure NO document states, since the statute names a tier and
  this table prices it. The refusal here stands unchanged: what that module
  publishes is a derivation, labelled as one, and not something this table
  says. The Court of International Trade is still unpriced, because
  28 U.S.C. 252 states no parity at all.

## Basic pay is not the node's cost

Exactly the rule `pay_tables.py` states: this is one post's rate, excludes
benefits, and is never written to a cost field. The release gate checks it.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "uscourts"
DEFAULT_TABLE_HTML = FIXTURE_DIR / "judicial_compensation.html"
DEFAULT_PAY_EVIDENCE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "verification" / "judicial_pay_evidence.json"
)

PAY_SOURCE = "uscourts_judicial_compensation"
PAY_SOURCE_TYPE = "uscourts_judicial_compensation"
PAY_METHOD = "rate_for_the_tier_this_post_holds"

#: The table's own column order, left to right, as printed. A page that
#: prints a different set of columns has been reshaped and this parser
#: should not guess which column is which.
EXPECTED_COLUMNS = ("year", "district judges", "circuit judges", "associate justices", "chief justice")

#: A node this module refuses even though nothing else here would catch it:
#: it names no count, but it is a template describing every district's
#: structure, not one district's actual chief judge.
DISTRICT_STRUCTURE_TEMPLATE_ID = "jud-district-structure-chief-judge"
#: Every node under the "All 94 District Courts -- Standard Structure"
#: template describes what a district looks like rather than any district's
#: actual bench, so none of them is a seat this table prices.
DISTRICT_STRUCTURE_TEMPLATE_PREFIX = "jud-district-structure-"
#: The one multi-post node the table's own "Associate Justices" column names.
ASSOCIATE_JUSTICES_ID = "jud-scotus-associate-justice-8"
#: A name that bundles senior judges into the count. 28 U.S.C. 371(b)(2)
#: sets an uncertified senior judge's salary by reference to a past year --
#: the salary "when he or she was last in active service" or when a
#: certification "was last in effect", then "adjusted under section 461" --
#: which need not equal the tier's current rate, so that rate cannot be
#: claimed for each holder.
SENIOR_JUDGE_MARKER = re.compile(r"\bsenior\b", re.IGNORECASE)

_RATE_CELL = re.compile(r"^\$\s*([0-9][0-9,]*)$")
_YEAR_CELL = re.compile(r"^(\d{4})")


class Unreadable(Exception):
    """The page is not the table this parser knows how to read."""


def _collapse(text: str) -> str:
    return " ".join(text.split())


class JudicialCompensationParser(HTMLParser):
    """The one data table on the page, and every footnote beneath it.

    There is exactly one `<table>` on this page (unlike the Executive
    Schedule page, its rows are not wrapped in a `<thead>`/`<tbody>` split —
    the header row is the first row, marked by `<strong>` in every cell — so
    the header is read from row shape, not from a `<thead>` tag.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables = 0
        self.rows: list[dict[str, Any]] = []
        self.footnotes: list[str] = []
        self._in_table = False
        self._row: list[str] | None = None
        self._row_is_header: bool | None = None
        self._cell: list[str] | None = None
        self._cell_has_strong = False
        self._footnote: list[str] | None = None
        self._in_footnote_anchor = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {k: (v or "") for k, v in attrs}
        classes = attributes.get("class", "").split()
        if tag == "table" and "usa-table" in classes:
            self.tables += 1
            self._in_table = True
            return
        if tag == "p" and "Footnote" in classes:
            self._footnote = []
            return
        if not self._in_table:
            return
        if tag == "tr":
            self._row = []
            self._row_is_header = None
        elif tag == "td":
            self._cell = []
            self._cell_has_strong = False
        elif tag == "strong" and self._cell is not None:
            self._cell_has_strong = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "p" and self._footnote is not None:
            text = _collapse("".join(self._footnote))
            if text:
                self.footnotes.append(text)
            self._footnote = None
            return
        if tag == "table":
            self._in_table = False
            return
        if not self._in_table:
            return
        if tag == "td" and self._cell is not None:
            text = _collapse("".join(self._cell))
            if self._row is not None:
                self._row.append(text)
            if self._row_is_header is None:
                self._row_is_header = self._cell_has_strong
            elif self._cell_has_strong != self._row_is_header:
                raise Unreadable("a row mixes header and data cells; this parser cannot tell which it is")
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append({"cells": list(self._row), "header": bool(self._row_is_header), "text": _collapse(" ".join(self._row))})
            self._row = None
            self._row_is_header = None

    def handle_data(self, data: str) -> None:
        for sink in (self._cell, self._footnote):
            if sink is not None:
                sink.append(data)
                return


def parse_judicial_compensation(html: str) -> dict[str, Any]:
    """Every year the table prints, most recent first as the page orders it,
    with each tier's rate as printed and as a number. Raises `Unreadable`
    rather than guessing at a reshaped page."""
    parser = JudicialCompensationParser()
    parser.feed(html)
    parser.close()

    if parser.tables != 1:
        raise Unreadable(f"{parser.tables} tables classed usa-table; this parser reads a page with exactly one")
    if not parser.rows:
        raise Unreadable("no rows found in the usa-table")
    header_rows = [r for r in parser.rows if r["header"]]
    if len(header_rows) != 1:
        raise Unreadable(f"{len(header_rows)} header rows found; this parser expects exactly one")
    columns = tuple(c.casefold() for c in header_rows[0]["cells"])
    if columns != EXPECTED_COLUMNS:
        raise Unreadable(f"the table's columns are {header_rows[0]['cells']!r}, not {list(EXPECTED_COLUMNS)!r}; it has been reshaped")

    years: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for row in parser.rows:
        if row["header"]:
            continue
        cells = row["cells"]
        if len(cells) != len(EXPECTED_COLUMNS):
            raise Unreadable(f"row {row['text']!r} does not have {len(EXPECTED_COLUMNS)} cells")
        year_match = _YEAR_CELL.match(cells[0])
        if not year_match:
            raise Unreadable(f"cell {cells[0]!r} is not a year this parser will read")
        year = year_match.group(1)
        if year in years:
            raise Unreadable(f"year {year!r} is printed twice; which row is the rate is not decidable")
        tiers: dict[str, dict[str, str | float]] = {}
        for column, cell in zip(EXPECTED_COLUMNS[1:], cells[1:]):
            match = _RATE_CELL.match(cell)
            if not match:
                raise Unreadable(f"cell {cell!r} in the {column!r} column is not a rate this parser will read")
            amount = float(match.group(1).replace(",", ""))
            if amount <= 0:
                raise Unreadable(f"rate {cell!r} is not a positive figure")
            tiers[column] = {"amount": amount, "amountRaw": match.group(1), "rateText": cell}
        years[year] = {"year": year, "tiers": tiers, "rowText": row["text"], "headerText": header_rows[0]["text"]}
        order.append(year)

    if not order:
        raise Unreadable("no data rows found beneath the header")
    return {
        "source": PAY_SOURCE,
        "years": years,
        # The order the page itself prints them in — most recent first, as
        # this page is written — never re-sorted, so "the current year" means
        # exactly what a reader looking at the page's own first row would see.
        "yearOrder": order,
        "currentYear": order[0],
        "footnotes": list(parser.footnotes),
        "columns": list(header_rows[0]["cells"]),
    }


def load_judicial_compensation(html_path: str | Path = DEFAULT_TABLE_HTML) -> dict[str, Any]:
    """The committed table, with the provenance its `.meta.json` recorded.

    Same digest check as `pay_tables.load_executive_schedule`, for the same
    reason: `documentSha256` is a claim about which bytes were read, and a
    fixture edited after the fetch must not carry a digest that vouches for
    text nobody served.
    """
    path = Path(html_path)
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
        raise Unreadable(f"{meta_path.name} records a fetch that did not serve the page")
    table = parse_judicial_compensation(raw.decode("utf-8", errors="replace"))
    return {"table": table, "url": url, "fetched_at": fetched_at, "sha256": digest, "file": str(path)}


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


def classify_seat(node_id: str, node: Mapping[str, Any]) -> tuple[str | None, str]:
    """Which of the table's four columns this node's post is paid at, or
    `None` with the reason it is refused.

    A rule, not a lookup table: any node that is a named circuit's or
    district's own Chief Judge is priced at that tier, because the office
    carries no salary of its own separate from the judgeship. This is
    deliberately narrower than "matches by name" — it is checked against the
    id's own shape, which this curated file has kept consistent across all
    thirteen circuits and the one instantiated district.
    """
    if str(node.get("type") or "").casefold() != "position":
        return None, "not_a_position"
    name = str(node.get("name") or "")
    # A node standing for several judges IS priced since 2026-09-23 -- the
    # tier rate is the office's and holds for each of them alike, and the
    # multi-post sweep stamps `holders` so the panel says so -- with one
    # refusal that is a statute's, not a preference. 28 U.S.C. 371(b)(2)
    # (committed at tests/fixtures/uscode/senior_judges_28_usc_371.html): a
    # senior judge who does not meet subsection (e) "shall continue to
    # receive the salary that he or she was receiving when he or she was last
    # in active service or, if a certification under subsection (e) was made
    # for such justice or judge, when such a certification was last in
    # effect. The salary of such justice or judge shall be adjusted under
    # section 461 of this title." A salary set by reference to a past year
    # and adjusted since is not necessarily this year's tier rate -- not
    # "frozen", which an earlier draft of this rule said and the section's
    # last sentence contradicts. So a node that bundles senior judges into
    # its count cannot claim the current tier rate for each holder, and every
    # circuit's "(×N active + senior judges)" node is refused on that
    # provision rather than priced.
    if SENIOR_JUDGE_MARKER.search(name):
        return None, "bundles_senior_judges_whose_salary_28_usc_371b2_sets_apart_from_the_tier_rate"
    if node_id == "jud-scotus-chief-justice-of-the-united-states":
        return "chief justice", "the_chief_justice"
    if node_id == ASSOCIATE_JUSTICES_ID:
        return "associate justices", "every_associate_justice"
    if node_id.startswith(DISTRICT_STRUCTURE_TEMPLATE_PREFIX):
        return None, "generic_structure_template_not_a_specific_court"
    if "-chief-judge-" in node_id:
        if node_id.startswith("jud-circuit-"):
            return "circuit judges", "a_circuit_s_own_chief_judge"
        if node_id.startswith("jud-district-"):
            return "district judges", "a_district_s_own_chief_judge"
    if node_id.startswith("jud-district-") and "-district-judge-" in node_id:
        # A named district's own bench, e.g. "District Judge (×28 active)":
        # every judge in regular active service is paid the district-judge
        # rate. The senior-judge rule above has already refused any node
        # whose name bundles senior judges.
        return "district judges", "a_districts_own_active_judges"
    if node_id.startswith("jud-circuit-") and "-circuit-judge-" in node_id:
        return "circuit judges", "a_circuits_own_active_judges"
    return None, "not_a_seat_this_table_prices"


def build_records(
    node_map: Mapping[str, Mapping[str, Any]],
    table: Mapping[str, Any],
    *,
    url: str,
    sha256: str,
    retrieved_at: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """A financial-evidence record for every judicial-branch node this table
    can price. The caller validates each against its node."""
    year = str(table["currentYear"])
    years = table["years"][year]
    header_text = years["headerText"]
    records: dict[str, dict[str, Any]] = {}
    refusals: dict[str, int] = {}
    considered = 0
    for node_id, node in sorted(node_map.items()):
        if not node_id.startswith("jud-"):
            continue
        if str(node.get("type") or "").casefold() != "position":
            continue
        considered += 1
        column, reason = classify_seat(node_id, node)
        if column is None:
            refusals[reason] = refusals.get(reason, 0) + 1
            continue
        tier = years["tiers"][column]
        quote = f"{header_text}; {years['rowText']}"
        records[node_id] = {
            "nodeId": node_id,
            "financialEvidenceStatus": "partial",
            "costBasis": "basic_pay",
            "amount": float(tier["amount"]),
            "amountRaw": tier["amountRaw"],
            "units": "usd",
            "normalizedMultiplier": 1,
            "unitsEvidence": quote,
            "quote": quote,
            "fiscalYear": int(year),
            "periodCoverage": "annual_rate",
            # The table is organised by calendar year and does not itself
            # state a month; judicial pay adjustments have historically taken
            # effect January 1, so this is the same kind of stated inference
            # `pay_tables.py` makes for the Executive Schedule's own heading.
            "periodAsOf": f"{year}-01-01",
            "amountScope": table["columns"][EXPECTED_COLUMNS.index(column) ],
            "scopeMatch": "proxy",
            "rollupRole": "line",
            "sourceType": PAY_SOURCE_TYPE,
            "sourceUrl": url,
            "documentSha256": sha256,
            "retrievedAt": retrieved_at,
            "locator": {"table": "Judicial Compensation", "row": year, "column": table["columns"][EXPECTED_COLUMNS.index(column)]},
            "seatTier": column,
            "seatReason": reason,
            "year": year,
            "rateText": tier["rateText"],
            "tableFootnotes": list(table.get("footnotes") or []),
        }
    report = {
        "source": PAY_SOURCE,
        "year": year,
        "url": url,
        "documentSha256": sha256,
        "retrievedAt": retrieved_at,
        "tiers": {k: v["amount"] for k, v in years["tiers"].items()},
        "footnotes": list(table.get("footnotes") or []),
        "considered": considered,
        "priced": len(records),
        "refused": dict(sorted(refusals.items())),
    }
    return records, report


def apply_pay_evidence(
    root: dict[str, Any],
    records: Mapping[str, Mapping[str, Any]],
    *,
    index_tree: Any = None,
) -> dict[str, Any]:
    """Stamp `positionStatutoryPay` on every judicial position this table
    prices. A separate field from `positionPayRate`: that field's shape is
    the Executive Schedule's two-source join (a level, and a rate for the
    level), and this is a different, single-source claim — the release gate
    checks each field against its own source, and folding the two together
    would let one source's rules be satisfied by the other's fields."""
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, _ = index_tree(root)
    stats = {"priced": 0, "unknown_node": 0, "not_a_position": 0}
    for node_id, record in sorted(records.items()):
        node = node_map.get(node_id)
        if node is None:
            stats["unknown_node"] += 1
            continue
        if str(node.get("type") or "").casefold() != "position":
            stats["not_a_position"] += 1
            continue
        # Multiplicity is reconciled by `pay_tables.withdraw_pay_from_multi_post_nodes`
        # after the counts are annotated; a tier rate holds for every holder
        # and is kept there with a `holders` block, so nothing is refused here.
        node["positionStatutoryPay"] = {
            "source": PAY_SOURCE,
            "sourceLabel": "the U.S. Courts' own Judicial Compensation table",
            "method": PAY_METHOD,
            "amount": record.get("amount"),
            "rateText": record.get("rateText"),
            "year": record.get("year"),
            "effective": record.get("periodAsOf"),
            "costBasis": record.get("costBasis"),
            "scopeMatch": record.get("scopeMatch"),
            "financialEvidenceStatus": record.get("financialEvidenceStatus"),
            "amountScope": record.get("amountScope"),
            "seatTier": record.get("seatTier"),
            "quote": record.get("quote"),
            "footnotes": list(record.get("tableFootnotes") or []),
            "url": str(record.get("sourceUrl") or ""),
            "checkedAt": record.get("retrievedAt"),
        }
        stats["priced"] += 1
        # Deliberately not written: sourceUrls, sourceTypes, lastVerified,
        # verificationMethod. A salary table says what a tier of judge is
        # paid; it does not say this post exists. The same defect that once
        # made 29 Executive Schedule positions read `verified` on the
        # strength of a five-row table that named no post — see
        # `pay_tables.apply_pay_evidence` — is the reason this rule is
        # repeated here rather than assumed to carry over.
    return stats
