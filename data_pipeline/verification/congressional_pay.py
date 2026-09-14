"""The Senate's own published salary schedule, and the one claim it can
honestly make about a congressional leadership position node.

## What `senate.gov` actually states

`senate.gov/senators/SenateSalariesSince1789.htm` is a year-by-year table of
the base Member salary back to 1789 (2026: $174,000 "per annum"), with one
footnote beneath it:

    Since the early 1980s, Senate leaders--majority and minority leaders,
    and the president pro tempore--have received higher salaries than other
    members. Currently, leaders earn $193,400 per year.

That sentence names three roles by their ordinary titles — not a numbered
rank the way OPM's Executive Schedule levels are, and not a proxy for a rank
`pay_tables.py` then has to guess which node it means. It is still filed here
as `scopeMatch: "proxy"` rather than `"exact"`: the sentence states one rate
shared by three roles together, not a rate stated once per role, and
treating a shared, grouped claim as if it individually named each role is
exactly the kind of one-word gap `financial_evidence.py`'s own docstring
warns about ("Fish and Wildlife and Parks" attached to either of the two
agencies it covers by writing one word). Filed as a proxy, the record still
carries the whole footnote as its quote, so a reader can see for themselves
which roles the source actually names.

## What this module prices, and what it does not

Only three Senate leadership positions are named in that footnote: the
President Pro Tempore, the Majority Leader, the Minority Leader. This
module prices exactly those three and nothing else:

- **Not** the Assistant Majority/Minority Leader (the party whips). The
  footnote does not name them, and this module does not guess that an
  unnamed role gets either the leaders' rate or the base rate — an
  unconfirmed number is worse than an honest gap.
- **Not** the House's Speaker, Majority Leader or Minority Leader. Search
  results describing House-side figures were not traced to a fetched
  official source this session could reach (`clerk.house.gov`'s own Salary
  document states only the base rate for all Members; `crsreports.congress.
  gov` and `www.congress.gov`'s CRS-report pages are Cloudflare-blocked to
  this session, a fact about the network, not the claim). Left unpriced
  rather than guessed.
- **Not** the President of the Senate (Vice President) node. The Vice
  President's salary is a different statutory figure entirely (3 U.S.C.
  § 104, not 2 U.S.C. § 4501), and this module has not read a source for it.
- **Not** any base "Member of Congress" seat, because none exists as a
  curated position node: "Individual Senator Offices (100)" and "Individual
  Representative Offices (435)" are curated staff-office groupings (Chief of
  Staff, Legislative Director, ...), not the Member's own seat. If a
  Senator/Representative position node is ever curated, `build_records`
  will price it automatically from the same table — nothing here needs to
  change for that.

Basic pay is not the node's cost, for exactly the reason `pay_tables.py`
states: it excludes benefits and is not a share of federal outlays.
"""

from __future__ import annotations

import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "congress"
DEFAULT_TABLE_HTML = FIXTURE_DIR / "senate_salaries_since_1789.html"
DEFAULT_PAY_EVIDENCE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "verification" / "congressional_pay_evidence.json"
)

PAY_SOURCE = "senate_salary_schedule"
PAY_SOURCE_TYPE = "senate_salary_schedule"
PAY_METHOD = "senate_leadership_rate_named_in_the_page_s_own_footnote"

#: The three roles the footnote names, and the curated node id each answers
#: to. An explicit map rather than a name-matching rule: there are three of
#: them, the stakes of mismatching a statutory salary are real, and a map
#: this short is more auditable than a pattern that would also have to be
#: proven not to catch anything else.
LEADERSHIP_NODE_IDS = {
    "leg-senate-leadership-president-pro-tempore": "president pro tempore",
    "leg-senate-leadership-majority-leader": "majority leader",
    "leg-senate-leadership-minority-leader": "minority leader",
}

#: Substrings the leadership footnote must contain for each role above, used
#: both to build the record and, in the release gate's mirror, to re-check
#: that the quoted footnote really does name the role being priced.
LEADERSHIP_FOOTNOTE_PHRASES = {
    "president pro tempore": "president pro tempore",
    "majority leader": "majority and minority leaders",
    "minority leader": "majority and minority leaders",
}

_YEAR_ROW = re.compile(r"^(\d{4})$")
_RATE_CELL = re.compile(r"^\$\s*([0-9][0-9,]*)\s+per\s+annum$", re.IGNORECASE)
_LEADER_RATE = re.compile(r"leaders?\s+earn\s+\$\s*([0-9][0-9,]*)\s+per\s+year", re.IGNORECASE)


class Unreadable(Exception):
    """The page is not the table this parser knows how to read."""


def _collapse(text: str) -> str:
    return " ".join(text.split())


class SenateSalaryTableParser(HTMLParser):
    """The one sortable table on the page, and the `<footer>` beneath it that
    carries the leadership rate."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables = 0
        self.rows: list[dict[str, str]] = []
        self.columns: list[str] = []
        self.footnote = ""
        self._in_table = False
        self._in_thead = False
        self._in_footer = False
        self._table_closed = False
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._footnote: list[str] | None = None
        # Every year cell hides a sort key ahead of the visible text:
        # <span style="display:none">2026</span>2026. Without suppressing it,
        # the cell reads "20262026" and no year matches this parser's regex.
        self._in_hidden_span = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {k: (v or "") for k, v in attrs}
        if tag == "table" and attributes.get("id") == "SortableData_table":
            self.tables += 1
            self._in_table = True
            return
        if tag == "footer":
            self._in_footer = True
            return
        # Only the FIRST <footer><p> immediately after the table's own close
        # is this table's note. The page carries a second, site-wide footer
        # further down (Contact | Content Responsibility | ...) — without
        # this guard the last <footer><p> on the page wins, and the
        # leadership rate is silently replaced by boilerplate.
        if self._in_footer and tag == "p" and self._table_closed and not self.footnote:
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
        elif tag == "span" and "display:none" in attributes.get("style", "").replace(" ", ""):
            self._in_hidden_span = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "p" and self._footnote is not None:
            text = _collapse("".join(self._footnote))
            if text:
                self.footnote = text
            self._footnote = None
            return
        if tag == "footer":
            self._in_footer = False
            return
        if tag == "table":
            self._in_table = False
            self._table_closed = True
            return
        if tag == "span":
            self._in_hidden_span = False
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
            if len(self._row) == 2:
                self.rows.append({"years": self._row[0], "salary": self._row[1]})
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._in_hidden_span:
            return
        for sink in (self._cell, self._footnote):
            if sink is not None:
                sink.append(data)
                return


def parse_senate_salary_table(html: str) -> dict[str, Any]:
    """Every row the table prints, and the leadership-rate footnote. Raises
    `Unreadable` rather than guessing at a reshaped page."""
    parser = SenateSalaryTableParser()
    parser.feed(html)
    parser.close()

    if parser.tables != 1:
        raise Unreadable(f"{parser.tables} tables with id SortableData_table; this parser reads a page with exactly one")
    if not parser.rows:
        raise Unreadable("no rows found in the sortable salary table")
    columns = tuple(c.casefold() for c in parser.columns)
    if columns != ("years", "salary"):
        raise Unreadable(f"the table's columns are {parser.columns!r}, not ['Years', 'Salary']; it has been reshaped")
    if not parser.footnote:
        raise Unreadable("no footer paragraph found beneath the table; the leadership rate is not citable without it")

    leader_match = _LEADER_RATE.search(parser.footnote)
    if not leader_match:
        raise Unreadable(f"footnote {parser.footnote!r} does not state a leaders' rate in the form this parser reads")
    leader_amount = float(leader_match.group(1).replace(",", ""))

    years: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for row in parser.rows:
        match = _YEAR_ROW.match(row["years"])
        if not match:
            # A range ("1789-1815") or a per-diem historical row: real, but
            # not a single current year, and this module only ever prices
            # the current year.
            continue
        year = match.group(1)
        rate_match = _RATE_CELL.match(row["salary"])
        if not rate_match:
            raise Unreadable(f"cell {row['salary']!r} for {year} is not a 'per annum' rate this parser will read")
        amount = float(rate_match.group(1).replace(",", ""))
        if amount <= 0:
            raise Unreadable(f"rate {row['salary']!r} is not a positive figure")
        years[year] = {"year": year, "amount": amount, "amountRaw": rate_match.group(1), "rateText": row["salary"]}
        order.append(year)

    if not order:
        raise Unreadable("no single-year base-salary rows found")
    # The page lists years in ascending order; the current one is the last.
    order.sort(key=int)
    return {
        "source": PAY_SOURCE,
        "baseYears": years,
        "currentYear": order[-1],
        "footnote": parser.footnote,
        "leadershipAmount": leader_amount,
        "leadershipAmountRaw": leader_match.group(1),
        "columns": list(parser.columns),
    }


def load_senate_salary_table(html_path: str | Path = DEFAULT_TABLE_HTML) -> dict[str, Any]:
    """The committed table, with the provenance its `.meta.json` recorded.
    Same digest check as `pay_tables.load_executive_schedule`."""
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
    table = parse_senate_salary_table(raw.decode("utf-8", errors="replace"))
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


def build_records(
    node_map: Mapping[str, Mapping[str, Any]],
    table: Mapping[str, Any],
    *,
    url: str,
    sha256: str,
    retrieved_at: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """A financial-evidence record for every Senate leadership node the
    footnote names. The caller validates each against its node."""
    year = str(table["currentYear"])
    records: dict[str, dict[str, Any]] = {}
    refusals: dict[str, int] = {}
    for node_id, role in sorted(LEADERSHIP_NODE_IDS.items()):
        node = node_map.get(node_id)
        if node is None:
            refusals["node_not_in_graph"] = refusals.get("node_not_in_graph", 0) + 1
            continue
        if str(node.get("type") or "").casefold() != "position":
            refusals["not_a_position"] = refusals.get("not_a_position", 0) + 1
            continue
        if node.get("representsPosts"):
            refusals["stands_for_several_posts"] = refusals.get("stands_for_several_posts", 0) + 1
            continue
        phrase = LEADERSHIP_FOOTNOTE_PHRASES[role]
        if phrase not in table["footnote"].casefold():
            refusals["footnote_does_not_name_this_role"] = refusals.get("footnote_does_not_name_this_role", 0) + 1
            continue
        records[node_id] = {
            "nodeId": node_id,
            "financialEvidenceStatus": "partial",
            "costBasis": "basic_pay",
            "amount": float(table["leadershipAmount"]),
            "amountRaw": table["leadershipAmountRaw"],
            "units": "usd",
            "normalizedMultiplier": 1,
            "unitsEvidence": table["footnote"],
            "quote": table["footnote"],
            "fiscalYear": int(year),
            "periodCoverage": "annual_rate",
            "periodAsOf": f"{year}-01-01",
            "amountScope": "Senate leadership (majority leader, minority leader, president pro tempore)",
            "scopeMatch": "proxy",
            "rollupRole": "line",
            "sourceType": PAY_SOURCE_TYPE,
            "sourceUrl": url,
            "documentSha256": sha256,
            "retrievedAt": retrieved_at,
            "locator": {"page": "Senate Salaries (1789 to Present)", "section": "footer note"},
            "role": role,
            "year": year,
            "rateText": f"${table['leadershipAmountRaw']} per year",
        }
    report = {
        "source": PAY_SOURCE,
        "year": year,
        "url": url,
        "documentSha256": sha256,
        "retrievedAt": retrieved_at,
        "baseRate": table["baseYears"].get(year, {}).get("amount"),
        "leadershipRate": table["leadershipAmount"],
        "footnote": table["footnote"],
        "considered": len(LEADERSHIP_NODE_IDS),
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
    """Stamp `positionStatutoryPay` on every Senate leadership position the
    footnote prices. Deliberately the same field name and general shape
    `judicial_pay.py` writes — both are single-source statutory claims, one
    per branch — so the panel needs one rendering path for both."""
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, _ = index_tree(root)
    stats = {"priced": 0, "unknown_node": 0, "not_a_position": 0, "stands_for_many_posts": 0}
    for node_id, record in sorted(records.items()):
        node = node_map.get(node_id)
        if node is None:
            stats["unknown_node"] += 1
            continue
        if str(node.get("type") or "").casefold() != "position":
            stats["not_a_position"] += 1
            continue
        if node.get("representsPosts"):
            stats["stands_for_many_posts"] += 1
            continue
        node["positionStatutoryPay"] = {
            "source": PAY_SOURCE,
            "sourceLabel": "the Senate's own published salary schedule",
            "method": PAY_METHOD,
            "amount": record.get("amount"),
            "rateText": record.get("rateText"),
            "year": record.get("year"),
            "effective": record.get("periodAsOf"),
            "costBasis": record.get("costBasis"),
            "scopeMatch": record.get("scopeMatch"),
            "financialEvidenceStatus": record.get("financialEvidenceStatus"),
            "amountScope": record.get("amountScope"),
            "seatTier": record.get("role"),
            "quote": record.get("quote"),
            "footnotes": [record.get("quote")] if record.get("quote") else [],
            "url": str(record.get("sourceUrl") or ""),
            "checkedAt": record.get("retrievedAt"),
        }
        stats["priced"] += 1
        # Deliberately not written: sourceUrls, sourceTypes, lastVerified,
        # verificationMethod — see `judicial_pay.apply_pay_evidence`.
    return stats
