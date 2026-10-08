"""The U.S. Attorneys' own Administratively Determined pay plan chart, and the
one table of it that names a title this graph carries.

## What the two documents are

`www.justice.gov/usao/career-center/salary-information/administratively-
determined-pay-plan-charts` is the Executive Office for U.S. Attorneys' chart of
the Administratively Determined (AD) pay plan. It says of itself: "These tables
are for 2025 and are effective as of January 12, 2025. The tables below do not
include locality based comparability adjustments (locality pay)." Its first
table is headed **"Assistant United States Attorneys (AUSA)"** and prints seven
grades, AD-21 to AD-29, each with a minimum, two quartiles, a midpoint and a
maximum, every figure with its dollar mark attached ("$63,163"). Its second
table is headed "Executive, Managerial, Supervisory, Special Assistant or Senior
Litigation Counsel AUSAs" (AD-30 to AD-40).

`www.justice.gov/usao/career-center/salary-information` is the page above it,
and says which people the plan pays: "The Administratively Determined (AD) Pay
Plan is a component-specific compensation system for Assistant United States
Attorneys, Supervisory Assistant United States Attorneys, Senior Litigation
Counsel, Special Assistant United States Attorneys and United States Attorneys
established under authority of 28 United States Code 548". It also says
"Promotions to supervisory and Senior Litigation Counsel positions are made on
a temporary basis."

So both halves a range needs are documented, and both are the publisher's own
words: the chart prints the bounds under a heading that IS the title, and the
salary page says that title is paid on that plan, listing Supervisory AUSAs and
Senior Litigation Counsel as categories of their own beside it.

## A range, never a rate

The chart prints the bounds of each grade and says nothing about what any
holder is paid; the grade itself depends on years of experience. So the claim
is the band from the AUSA table's lowest minimum (AD-21) to its highest maximum
(AD-29), BASE pay before locality, the year the chart states (2025). It is
published in `positionTierPay` -- the field for a band a schedule prints beside
a title it names -- as a second source beside the VA's Title 38 ranges, with its
own source, kind and gate branch. Not `positionGradePay`: that field is tied to
a listing of ONE post and is stripped from a node that stands for several, and
the two AUSA nodes are `(×multiple)` by name. A band the chart prints for the
whole title bounds every holder of it, which is the office-rate shape.

## What is priced, and what is not

Two nodes, by id (`AD_ROWS`): `Assistant U.S. Attorney — Civil (×multiple)` and
`Assistant U.S. Attorney — Criminal (×multiple)`, each directly under the U.S.
Attorneys Office node. Which node the chart's heading names is a reviewed
identification (the graph abbreviates "United States", and its "— Civil" /
"— Criminal" qualifier is the graph's own division of the title), so both are
`scopeMatch: proxy`, graded `partial`.

Refused, with the reason on the report:

- `Civil Division Chief`, `Criminal Division Chief`, `First Assistant U.S.
  Attorney`: the chart's second table covers "Executive, Managerial,
  Supervisory, Special Assistant or Senior Litigation Counsel AUSAs" and names
  no post; which of its grades a division chief or a First Assistant holds is
  stated nowhere, and the table prints "$0" and "n/a" in some of its cells.
- `U.S. Attorney (×94, appointed by President)`: the salary page puts United
  States Attorneys on the AD plan and the chart prints no row naming them.

Basic pay is not the node's cost, and nothing here writes `sourceUrls`,
`sourceTypes`, `lastVerified` or `verificationMethod`.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "doj"
DEFAULT_CHART = FIXTURE_DIR / "usao_ad_pay_plan_charts.html"
DEFAULT_PLAN_PAGE = FIXTURE_DIR / "usao_salary_information.html"
DEFAULT_PAY_EVIDENCE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "verification" / "doj_ad_pay_evidence.json"
)

PAY_SOURCE = "doj_usao_ad_pay_plan"
PAY_SOURCE_TYPE = "doj_usao_ad_pay_plan_chart"
PAY_METHOD = "title_heading_a_table_of_the_us_attorneys_ad_pay_plan_chart"
BAND_KIND = "administratively_determined_grade_band"

TABLE_HEADING = "Assistant United States Attorneys (AUSA)"
EXCLUDED_TABLE_HEADING = "Executive, Managerial, Supervisory, Special Assistant or Senior Litigation Counsel AUSAs"
EFFECTIVE_TEXT = "These tables are for 2025 and are effective as of January 12, 2025."
EFFECTIVE_DATE = "2025-01-12"
LOCALITY_TEXT = "The tables below do not include locality based comparability adjustments (locality pay)."
TABLE_COLUMNS = ("AD Grade", "Years Experience", "Minimum", "Q-2 25th Percentile", "Midpoint",
                 "Q-4 75th Percentile", "Maximum")
PLAN_QUOTE = (
    "The Administratively Determined (AD) Pay Plan is a component-specific compensation system for Assistant "
    "United States Attorneys, Supervisory Assistant United States Attorneys, Senior Litigation Counsel, Special "
    "Assistant United States Attorneys and United States Attorneys established under authority of 28 United "
    "States Code 548, Salaries, and approved by the Attorney General."
)
TEMPORARY_PROMOTION_QUOTE = "Promotions to supervisory and Senior Litigation Counsel positions are made on a temporary basis."

#: node id -> (the name the row was written against, the parent id the tree
#: must give it). Reviewed: the chart's heading names the title, never a node.
AD_ROWS = {
    "exec-dept-doj-usao-assistant-u-s-attorney-civil-multiple": (
        "Assistant U.S. Attorney — Civil (×multiple)", "exec-dept-doj-usao",
    ),
    "exec-dept-doj-usao-assistant-u-s-attorney-criminal-multiple": (
        "Assistant U.S. Attorney — Criminal (×multiple)", "exec-dept-doj-usao",
    ),
}
#: Declined, with the reason. Recorded on the report so the dry run says why.
NOT_PRICED = {
    "exec-dept-doj-usao-civil-division-chief": (
        "a supervisory AUSA post: the chart's second table covers 'Executive, Managerial, Supervisory, Special "
        "Assistant or Senior Litigation Counsel AUSAs' and names no post, so which grade a division chief holds "
        "is stated nowhere"
    ),
    "exec-dept-doj-usao-criminal-division-chief": (
        "a supervisory AUSA post: the chart's second table names no post, so which grade a division chief holds "
        "is stated nowhere"
    ),
    "exec-dept-doj-usao-first-assistant-u-s-attorney": (
        "the chart names no First Assistant; the second table covers executive and supervisory AUSAs without "
        "naming a post"
    ),
    "exec-dept-doj-usao-u-s-attorney-94-appointed-by-president": (
        "the salary page puts United States Attorneys on the AD plan and the chart prints no row naming them"
    ),
}

NOTE = (
    "a range the chart prints for the title, not a rate: the U.S. Attorneys' AD pay plan chart states the bounds "
    "of each grade and the grade depends on years of experience; it publishes no figure for any holder"
)
SCOPE_NOTE = (
    "The chart's first table, headed 'Assistant United States Attorneys (AUSA)', prints this range. Its second "
    "table, headed 'Executive, Managerial, Supervisory, Special Assistant or Senior Litigation Counsel AUSAs', is "
    "not included: the salary page lists Supervisory Assistant United States Attorneys and Senior Litigation "
    "Counsel as categories of their own beside Assistant United States Attorneys, and says promotions to those "
    "positions are made on a temporary basis."
)

_MONEY = re.compile(r"^\$([0-9][0-9,]*)$")


class Unreadable(Exception):
    """The page is not the chart this parser knows how to read."""


class _BodyParser(HTMLParser):
    """Headings, paragraphs and table rows, in document order, as text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.events: list[tuple[str, Any]] = []
        self._capture: str | None = None
        self._buf: list[str] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._table: list[list[str]] | None = None

    def handle_starttag(self, tag, attrs):
        if tag in ("h2", "p") and self._table is None:
            self._capture, self._buf = tag, []
        elif tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag == self._capture:
            self.events.append((tag, " ".join("".join(self._buf).split())))
            self._capture = None
        elif tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.events.append(("table", self._table))
            self._table = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)
        elif self._capture is not None:
            self._buf.append(data)


def page_text(raw: bytes) -> str:
    """The page's text with tags removed and whitespace folded -- what a quote
    from it is checked against."""
    text = raw.decode("utf-8", errors="replace")
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", text, flags=re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return " ".join(text.split())


def parse_chart(raw: bytes) -> dict[str, Any]:
    """The AUSA table as the chart prints it, with the sentences that date it
    and say it is before locality. A reshaped page yields nothing."""
    parser = _BodyParser()
    parser.feed(raw.decode("utf-8", errors="replace"))
    events = parser.events
    paragraphs = [value for kind, value in events if kind == "p"]
    if not any(EFFECTIVE_TEXT in p for p in paragraphs):
        raise Unreadable(f"the chart does not print {EFFECTIVE_TEXT!r}")
    if not any(LOCALITY_TEXT in p for p in paragraphs):
        raise Unreadable("the chart does not say its tables exclude locality pay")

    headings = [i for i, (kind, value) in enumerate(events) if kind == "h2" and value == TABLE_HEADING]
    if len(headings) != 1:
        raise Unreadable(f"{len(headings)} headings read {TABLE_HEADING!r}; this parser reads a chart with one")
    table = next((value for kind, value in events[headings[0] + 1:] if kind == "table"), None)
    if not table:
        raise Unreadable(f"no table follows {TABLE_HEADING!r}")
    if tuple(table[0]) != TABLE_COLUMNS:
        raise Unreadable(f"the AUSA table's columns read {table[0]!r}, not {TABLE_COLUMNS!r}")
    excluded = [value for kind, value in events if kind == "h2" and value == EXCLUDED_TABLE_HEADING]
    if len(excluded) != 1:
        raise Unreadable("the chart no longer prints its second table's heading")

    grades: list[dict[str, Any]] = []
    for row in table[1:]:
        if len(row) != len(TABLE_COLUMNS):
            raise Unreadable(f"AUSA row {row!r} does not have {len(TABLE_COLUMNS)} cells")
        grade, years, minimum, _, _, _, maximum = row
        if not re.fullmatch(r"AD-\d{2}", grade):
            raise Unreadable(f"{grade!r} is not an AD grade")
        low, high = _MONEY.match(minimum), _MONEY.match(maximum)
        if not low or not high:
            raise Unreadable(f"{grade}: {minimum!r} / {maximum!r} are not printed dollar figures")
        low_value = float(low.group(1).replace(",", ""))
        high_value = float(high.group(1).replace(",", ""))
        if low_value <= 0 or high_value <= 0 or high_value < low_value:
            raise Unreadable(f"{grade}: {minimum} to {maximum} is not a band of positive figures")
        grades.append({
            "grade": grade, "years": years,
            "minimum": low_value, "maximum": high_value,
            "minimumRaw": low.group(1), "maximumRaw": high.group(1),
        })
    if len(grades) < 2:
        raise Unreadable("the AUSA table prints fewer than two grades")
    for earlier, later in zip(grades, grades[1:]):
        if later["minimum"] < earlier["minimum"] or later["maximum"] < earlier["maximum"]:
            raise Unreadable(f"{later['grade']} prints a band below {earlier['grade']}'s")
    return {
        "table": TABLE_HEADING,
        "excludedTable": EXCLUDED_TABLE_HEADING,
        "grades": grades,
        "effectiveText": EFFECTIVE_TEXT,
        "effective": EFFECTIVE_DATE,
        "localityText": LOCALITY_TEXT,
    }


def _load_fixture(path: Path) -> dict[str, Any]:
    meta_path = path.with_name(path.name + ".meta.json")
    if not meta_path.exists():
        raise Unreadable(f"{path.name} has no .meta.json beside it; an undated fetch cannot be cited")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    recorded = str(meta.get("sha256") or "").lower()
    if not recorded or digest != recorded:
        raise Unreadable(f"{path.name} does not match the digest its fetch recorded")
    url = str(meta.get("url") or "")
    if meta.get("error") or int(meta.get("status") or 0) != 200 or not url or not meta.get("fetched_at"):
        raise Unreadable(f"{meta_path.name} records a fetch that did not serve the document")
    if str(meta.get("final_url") or "") != url:
        raise Unreadable(f"{path.name} was served from {meta.get('final_url')!r}, not the URL it cites")
    return {"raw": raw, "url": url, "fetched_at": str(meta["fetched_at"]), "sha256": digest, "file": str(path)}


def load_documents(chart_path: str | Path = DEFAULT_CHART, plan_path: str | Path = DEFAULT_PLAN_PAGE) -> dict[str, Any]:
    """Both committed pages, digests recomputed, the chart parsed and the salary
    page's two sentences re-found in its text."""
    chart = _load_fixture(Path(chart_path))
    plan = _load_fixture(Path(plan_path))
    parsed = parse_chart(chart["raw"])
    plan_text = page_text(plan["raw"])
    for sentence in (PLAN_QUOTE, TEMPORARY_PROMOTION_QUOTE):
        if sentence not in plan_text:
            raise Unreadable(f"the salary page no longer prints {sentence[:60]!r}...")
    return {"chart": chart, "plan": plan, "parsed": parsed}


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


def _quote_for(parsed: Mapping[str, Any]) -> str:
    """The chart's own words: its dating sentence, its locality sentence, the
    table heading and the two rows the band's bounds are printed on."""
    low, high = parsed["grades"][0], parsed["grades"][-1]
    return " · ".join([
        parsed["effectiveText"],
        parsed["localityText"],
        parsed["table"],
        "{} minimum ${}".format(low["grade"], low["minimumRaw"]),
        "{} maximum ${}".format(high["grade"], high["maximumRaw"]),
    ])


def build_records(
    node_map: Mapping[str, Mapping[str, Any]],
    parent_of: Mapping[str, str],
    loaded: Mapping[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """A band record for each reviewed row whose node still carries the name
    and sits under the parent it was written against."""
    parsed = loaded["parsed"]
    chart, plan = loaded["chart"], loaded["plan"]
    low, high = parsed["grades"][0], parsed["grades"][-1]
    quote = _quote_for(parsed)
    records: dict[str, dict[str, Any]] = {}
    refusals: dict[str, str] = {}
    for node_id, (expected_name, expected_parent) in sorted(AD_ROWS.items()):
        node = node_map.get(node_id)
        if node is None:
            refusals[node_id] = "not in the graph"
            continue
        if str(node.get("name") or "") != expected_name:
            refusals[node_id] = f"now called {node.get('name')!r}, not the {expected_name!r} the row was written against"
            continue
        if parent_of.get(node_id) != expected_parent:
            refusals[node_id] = f"sits under {parent_of.get(node_id)!r}, not {expected_parent!r}"
            continue
        if str(node.get("type") or "").casefold() != "position":
            refusals[node_id] = "not a position"
            continue
        records[node_id] = {
            "nodeId": node_id,
            "financialEvidenceStatus": "partial",
            "costBasis": "basic_pay",
            # One amount per record for `financial_evidence`: the band's
            # MINIMUM, printed on the AD-21 row; the maximum rides beside it.
            "amount": float(low["minimum"]),
            "amountRaw": low["minimumRaw"],
            "units": "usd",
            "normalizedMultiplier": 1,
            "unitsEvidence": quote,
            "quote": quote,
            "fiscalYear": int(parsed["effective"][:4]),
            "periodCoverage": "annual_rate",
            "periodAsOf": parsed["effective"],
            "amountScope": TABLE_HEADING,
            "scopeMatch": "proxy",
            "rollupRole": "line",
            "sourceType": PAY_SOURCE_TYPE,
            "sourceUrl": chart["url"],
            "documentSha256": chart["sha256"],
            "retrievedAt": chart["fetched_at"],
            "locator": {"page": TABLE_HEADING, "section": "{} to {}".format(low["grade"], high["grade"])},
            "rangeMinimum": float(low["minimum"]),
            "rangeMaximum": float(high["maximum"]),
            "rangeMinimumRaw": low["minimumRaw"],
            "rangeMaximumRaw": high["maximumRaw"],
            "gradeLow": low["grade"],
            "gradeHigh": high["grade"],
            "rangeText": "${} – ${}".format(low["minimumRaw"], high["maximumRaw"]),
            "planUrl": plan["url"],
            "planSha256": plan["sha256"],
            "planRetrievedAt": plan["fetched_at"],
        }
    report = {
        "source": PAY_SOURCE,
        "chart": {"url": chart["url"], "sha256": chart["sha256"], "fetchedAt": chart["fetched_at"]},
        "planPage": {"url": plan["url"], "sha256": plan["sha256"], "fetchedAt": plan["fetched_at"]},
        "effective": parsed["effective"],
        "table": parsed["table"],
        "grades": [
            {"grade": g["grade"], "years": g["years"], "minimum": g["minimum"], "maximum": g["maximum"]}
            for g in parsed["grades"]
        ],
        "priced": len(records),
        "refused": refusals,
        "notPriced": dict(sorted(NOT_PRICED.items())),
        "tableNotRead": {
            EXCLUDED_TABLE_HEADING: (
                "names no post; prints '$0' and 'n/a' in some cells; which of its grades a division chief or a "
                "First Assistant holds is stated nowhere"
            ),
        },
    }
    return records, report


def apply_pay_evidence(
    root: dict[str, Any],
    records: Mapping[str, Mapping[str, Any]],
    *,
    index_tree: Any = None,
) -> dict[str, Any]:
    """Stamp `positionTierPay` from the AD chart -- a BAND, never a rate.

    A node standing for several posts may carry it: the chart prints the band
    for the title, so it bounds every holder, and the multi-post sweep stamps
    `holders` on it as it does on every office-rate field. A node another
    source has already banded is left alone.
    """
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, _ = index_tree(root)
    stats = {"priced": 0, "unknown_node": 0, "not_a_position": 0, "already_banded": 0, "not_a_reviewed_row": 0}
    for node_id, record in sorted(records.items()):
        node = node_map.get(node_id)
        if node is None:
            stats["unknown_node"] += 1
            continue
        if node_id not in AD_ROWS or str(node.get("name") or "") != AD_ROWS[node_id][0]:
            stats["not_a_reviewed_row"] += 1
            continue
        if str(node.get("type") or "").casefold() != "position":
            stats["not_a_position"] += 1
            continue
        if node.get("positionTierPay"):
            stats["already_banded"] += 1
            continue
        node["positionTierPay"] = {
            "source": PAY_SOURCE,
            "sourceLabel": "the U.S. Attorneys' Administratively Determined pay plan chart",
            "method": PAY_METHOD,
            "kind": BAND_KIND,
            "minimum": record.get("rangeMinimum"),
            "maximum": record.get("rangeMaximum"),
            "rangeText": record.get("rangeText"),
            "gradeLow": record.get("gradeLow"),
            "gradeHigh": record.get("gradeHigh"),
            "coverageTitle": TABLE_HEADING,
            "table": TABLE_HEADING,
            "excludedTable": EXCLUDED_TABLE_HEADING,
            "matchRule": "reviewed_row_by_node_id",
            "effective": record.get("periodAsOf"),
            "effectiveText": EFFECTIVE_TEXT,
            "localityText": LOCALITY_TEXT,
            "costBasis": record.get("costBasis"),
            "scopeMatch": record.get("scopeMatch"),
            "financialEvidenceStatus": record.get("financialEvidenceStatus"),
            "note": NOTE,
            "scopeNote": SCOPE_NOTE,
            "quote": record.get("quote"),
            "url": str(record.get("sourceUrl") or ""),
            "documentSha256": record.get("documentSha256"),
            "checkedAt": record.get("retrievedAt"),
            "planDocument": {
                "url": str(record.get("planUrl") or ""),
                "sha256": record.get("planSha256"),
                "checkedAt": record.get("planRetrievedAt"),
                "quote": PLAN_QUOTE,
                "temporaryPromotionQuote": TEMPORARY_PROMOTION_QUOTE,
            },
        }
        stats["priced"] += 1
        # Deliberately not written: sourceUrls, sourceTypes, lastVerified,
        # verificationMethod — see `judicial_pay.apply_pay_evidence`.
    return stats
