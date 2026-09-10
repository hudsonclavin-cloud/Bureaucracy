"""Financial evidence: a direct, period-scoped monetary figure tied to one node.

This is the second evidence track. The first — `evidence.py`, `directories.py`,
`congress.py`, `headcounts.py`, `positions.py` — answers "does this unit exist
and is it where the graph puts it". This one answers "what does a primary
source say this unit's money is", and it is deliberately kept apart from the
cost cascade in `annotate_resolved_costs`.

Why a separate track rather than another `cost_status`:

The cascade's arithmetic is basis-consistent by construction. Every figure in
it is FYTD net outlays from one Monthly Treasury Statement, so the release
gate can compare a child's amount to its parent's and the comparison means
something. A Congressional Justification reports a *budget request* — what an
agency asked for, before the fiscal year, possibly never appropriated. Putting
that number into `resolved_total_amount` would hand the gate's child-sum check
two quantities that cannot be compared, and it would either fire a false
violation or, worse, pass one silently.

So the rule this module exists to enforce: **two amounts may be compared only
when their basis, fiscal year, coverage period, scope and units all agree.**

## What the first draft got wrong

The first version of this file was red-teamed with 178 executed attacks and
47 of them got a false figure past it. The single worst was structural, and
it is worth stating plainly because the shape of the mistake recurs:

    amount == parse(amountRaw) * UNITS[units]      # check 1
    normalizedMultiplier == UNITS[units]           # check 2

Both checks compare the record **to itself**. A record declaring `millions_usd`
over a table that prints thousands is perfectly self-consistent, passes both,
and publishes a figure 1000x too high — the exact disaster the first draft's
docstring claimed this module existed to prevent. Arithmetic self-consistency
is not evidence. So the units claim is now evidence-bearing: the record must
carry the verbatim table heading that states the scale, that heading must
agree with the declared units, and the printed digits must actually appear in
the quoted line. A figure is now bound to text a human can re-read on the page.

The same lesson applies to `scopeMatch`. Declaring "exact" used to be enough
to publish a figure as a unit's own; Treasury's "Fish and Wildlife and Parks"
line could be attached to either agency it covers by writing one word. Scope
is now settled by label equality against the node's own name, the same
discipline `evidence.py` uses to decide whether a page names a unit.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

from data_pipeline.exporter.build_graph import canonical_name_key


class Rejected(Exception):
    """A record that is structurally invalid. Not a finding — a malformed record."""


# --------------------------------------------------------------------------
# Vocabularies. Each entry is a different measurement of a different thing,
# and the whole point of naming them is that the graph must never let one
# stand in for another.

#: What kind of number this is.
BASES = {
    "budget_request",        # asked for. A plan, and the most common CJ figure.
    "appropriations",        # enacted by Congress.
    "budget_authority",      # made available to be obligated.
    "obligations",           # committed. Not spent.
    "net_outlays",           # cash out, net of receipts. The cascade's basis.
    "gross_outlays",         # cash out before receipts. Differs by billions.
    "audited_net_cost",      # accrual, audited. The only audited basis.
    "basic_pay",             # one post's rate. Never an organisation's cost.
    "payroll",               # a unit's staff cost. An input to cost, not cost.
    "full_time_equivalents",  # not money at all.
}

#: Figures about money that has actually moved or been committed. These cannot
#: exist for a fiscal year that has not finished, which is how the first draft
#: let an "audited actual" be filed for FY2028.
REALIZED_BASES = {"net_outlays", "gross_outlays", "obligations", "audited_net_cost", "payroll"}

NON_MONETARY_BASES = {"full_time_equivalents"}
POSITION_ONLY_BASES = {"basic_pay"}

#: Declared units, and the factor that turns the printed figure into the base
#: unit. `thousands_count` exists because FTE tables are printed in thousands
#: too, and the first draft had no way to say so.
UNITS = {
    "usd": 1,
    "thousands_usd": 1_000,
    "millions_usd": 1_000_000,
    "billions_usd": 1_000_000_000,
    "count": 1,
    "thousands_count": 1_000,
}
MONETARY_UNITS = {"usd", "thousands_usd", "millions_usd", "billions_usd"}
COUNT_UNITS = {"count", "thousands_count"}

#: The phrases a budget table actually uses to state its scale. `unitsEvidence`
#: must carry one of the declared unit's phrases and none of a conflicting
#: unit's — that is what turns the units claim from a free-text declaration
#: into something a reviewer can check against the page.
#: Phrases are matched on word boundaries, not as bare substrings: "fte"
#: occurs inside "after", so a heading stating no scale at all used to satisfy
#: a count declaration.
UNIT_PHRASES = {
    "usd": ("in dollars", "whole dollars", "(dollars)", "in actual dollars"),
    "thousands_usd": ("in thousands", "(thousands)", "$000", "thousands of dollars"),
    "millions_usd": ("in millions", "(millions)", "millions of dollars"),
    "billions_usd": ("in billions", "(billions)", "billions of dollars"),
    "count": ("full-time equivalent", "full time equivalent", "fte", "positions", "staff years"),
    "thousands_count": ("fte in thousands", "positions in thousands", "full-time equivalent in thousands"),
}

#: A headcount has a plausibility bound too. The whole federal civilian
#: workforce is about three million; the ceiling used to be skipped for every
#: non-monetary basis, so a headcount had no bound at all.
DEFAULT_COUNT_CEILING = 10_000_000.0

#: How the period is bounded. Free text here was a real defect: re-wording
#: "full fiscal year" as "Full Fiscal Year" made two records incomparable, so
#: a conflict and a double-count both went undetected.
PERIOD_COVERAGES = {
    "full_fiscal_year",
    "fiscal_year_to_date",
    "quarter",
    "month",
    "multi_year",
}
#: A year-to-date figure is meaningless without the date it runs to; two YTD
#: figures cut off at different months are not the same measurement.
PERIODS_NEEDING_AS_OF = {"fiscal_year_to_date", "quarter", "month"}

SOURCE_TYPES = {
    "congressional_justification",
    "appropriations_act",
    "treasury_mts",
    "usaspending_file_ab",
    "agency_financial_report",
    "omb_public_budget",
    "omb_apportionment",
    "opm_pay_table",
}

#: Which bases a source can actually report. A Congressional Justification
#: cannot report an audited net cost; nothing stopped that being claimed.
#: CJs *do* print prior-year actual columns, so realized bases are allowed
#: there — the separate realized-year rule below is what keeps them honest.
SOURCE_BASES = {
    "congressional_justification": {
        "budget_request", "appropriations", "budget_authority", "obligations",
        "net_outlays", "gross_outlays", "payroll", "full_time_equivalents",
    },
    "appropriations_act": {"appropriations", "budget_authority"},
    "treasury_mts": {"net_outlays", "gross_outlays"},
    "usaspending_file_ab": {"net_outlays", "gross_outlays", "obligations", "budget_authority"},
    "agency_financial_report": {"audited_net_cost", "net_outlays", "payroll", "full_time_equivalents"},
    "omb_public_budget": {"budget_authority", "appropriations", "net_outlays", "budget_request"},
    "omb_apportionment": {"budget_authority"},
    "opm_pay_table": {"basic_pay"},
}

SCOPE_MATCHES = {"exact", "parent", "child", "broader_account", "proxy", "ambiguous"}
EXACT_SCOPES = {"exact"}
ROLLUP_ROLES = {"line", "subtotal", "total"}

STATES = {"verified", "partial", "unverified", "conflicted", "no_direct_amount_found"}
#: classify() may lower an author's claim but never raise it. The first draft
#: promoted a record its own author marked "unverified" to "verified".
STATE_RANK = {"unverified": 0, "partial": 1, "verified": 2}

#: No single federal unit outspends the whole government. A ceiling this crude
#: still catches a units error that survives everything else.
DEFAULT_AMOUNT_CEILING = 7_000_000_000_000.0

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_AMOUNT_TEXT = re.compile(r"^\(?-?[\d,]+(?:\.\d+)?\)?$")
_DIGITS = re.compile(r"[\d.]+")


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _matched_phrase(heading: str, units: str) -> str:
    """The longest phrase of `units` this heading states, on word boundaries.

    Word boundaries because a bare substring test read "fte" out of the
    ordinary word "after", so a heading stating no scale at all satisfied a
    count declaration.
    """
    best = ""
    for phrase in UNIT_PHRASES[units]:
        if len(phrase) > len(best) and re.search(
            rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", heading
        ):
            best = phrase
    return best


def scale_stated_by(heading: str, kind: str) -> tuple[str | None, str]:
    """Which unit of `kind` this heading actually states, and the phrase.

    Longest match wins, and that is the whole point. "FTE in thousands"
    contains "fte", so a rule of "matches mine and none of the others" made
    that heading self-contradictory and refused an honest record. It also, in
    the other direction, let the heading satisfy a bare `count` declaration —
    two readings 1000x apart off one line of text. The most specific phrase
    the heading contains is the scale it states.
    """
    units_of_kind = COUNT_UNITS if kind == "count" else MONETARY_UNITS
    best_unit, best_phrase = None, ""
    for unit in sorted(units_of_kind):
        phrase = _matched_phrase(heading, unit)
        if len(phrase) > len(best_phrase):
            best_unit, best_phrase = unit, phrase
    return best_unit, best_phrase


def _is_real_number(value: Any) -> bool:
    """A number, not a bool, and finite.

    NaN and infinity used to pass every check in this module, because every
    guard was a comparison and every comparison against NaN is False. A NaN
    also silently suppressed `detect_conflicts`, and `json.dumps` emits it as
    bare `NaN`, which is not valid JSON for a strict reader.
    """
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def parse_amount_text(raw: Any) -> float:
    """Read the figure as the document prints it.

    Budget tables use accounting negatives — `(1,234)` means −1234 — and
    thousands separators. Everything else is refused rather than guessed at:
    `(-1,234)` used to be double-negated into a positive, and the unbalanced
    `(1,234` had its parenthesis stripped and published positive.
    """
    if not isinstance(raw, str):
        raise Rejected(
            f"amountRaw {raw!r} is not text; it must be the figure as the document prints it"
        )
    text = raw.strip()
    opens, closes = text.count("("), text.count(")")
    if opens != closes or opens > 1:
        raise Rejected(f"amountRaw {raw!r} has unbalanced parentheses")
    negative = text.startswith("(") and text.endswith(")")
    if negative and "-" in text:
        raise Rejected(f"amountRaw {raw!r} is negative twice over — parentheses and a minus sign")
    if not _AMOUNT_TEXT.match(text):
        raise Rejected(f"amountRaw {raw!r} is not a figure this parser will read")
    cleaned = text.strip("()").replace(",", "")
    try:
        value = float(cleaned)
    except ValueError as error:  # pragma: no cover - guarded by the regex
        raise Rejected(f"amountRaw {raw!r} is not numeric") from error
    if not math.isfinite(value):
        raise Rejected(f"amountRaw {raw!r} does not parse to a finite number")
    return -value if negative else value


def federal_fiscal_year(day: date) -> int:
    """FY N runs 1 Oct N-1 to 30 Sep N."""
    return day.year + 1 if day.month >= 10 else day.year


def _past_iso_date(value: Any, field: str) -> date:
    text = _text(value)
    if not text:
        raise Rejected(f"{field} is required")
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise Rejected(f"{field} {value!r} is not an ISO date") from error
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    if stamp > datetime.now(timezone.utc):
        raise Rejected(f"{field} {value!r} is in the future; a retrieval date is never invented")
    return stamp.date()


def is_organisation(node: Mapping[str, Any]) -> bool:
    """Exactly the release gate's test, word for word.

    `scripts/validate_published_graph.py` refuses a measured cost on a node
    whose type contains position, role, **committee**, caucus or office
    holder. The first draft of this function left `committee` out while its
    docstring claimed the tests were the same — so a committee could carry a
    financial record this module blessed and the gate would reject.
    """
    type_text = _text(node.get("type")).casefold()
    return not node.get("synthetic") and not any(
        word in type_text for word in ("position", "role", "committee", "caucus", "office holder")
    )


@dataclass(frozen=True)
class Comparison:
    comparable: bool
    reason: str


def _comparability_key(record: Mapping[str, Any]) -> tuple:
    return (
        _text(record.get("costBasis")),
        record.get("fiscalYear"),
        _text(record.get("periodCoverage")),
        _text(record.get("periodAsOf")),
        _text(record.get("scopeMatch")),
        "count" if _text(record.get("units")) in COUNT_UNITS else "money",
    )


def comparable(left: Mapping[str, Any], right: Mapping[str, Any]) -> Comparison:
    """Two amounts may be compared only when they measure the same thing.

    Scope is part of the key, which the first draft missed: a unit's own
    figure and its parent's agency-wide figure recorded on the same node are
    not two sources disagreeing, they are two different measurements, and
    reporting them as a conflict is itself a false claim.
    """
    labels = (
        ("costBasis", "basis"),
        ("fiscalYear", "fiscal year"),
        ("periodCoverage", "coverage period"),
        ("periodAsOf", "as-of date"),
        ("scopeMatch", "scope"),
    )
    for field, label in labels:
        if _text(left.get(field)) != _text(right.get(field)):
            return Comparison(False, f"different {label}")
    if (_text(left.get("units")) in COUNT_UNITS) != (_text(right.get("units")) in COUNT_UNITS):
        return Comparison(False, "one is a count and the other is money")
    return Comparison(True, "same basis, period, scope and unit kind")


def _rounding_slack(record: Mapping[str, Any]) -> float:
    """Half the smallest increment the document could print.

    A flat 0.5% let two agency-scale figures differ by $8bn and not count as a
    disagreement. Tolerance should absorb *rounding*, and rounding is a
    property of the units the document printed in: a table in millions can be
    out by half a million and no more.
    """
    return UNITS.get(_text(record.get("units")), 1) / 2.0


def validate_record(
    record: Mapping[str, Any],
    node: Mapping[str, Any],
    *,
    amount_ceiling: float = DEFAULT_AMOUNT_CEILING,
) -> dict[str, Any]:
    """Refuse a structurally invalid record. Returns the normalised record.

    `node` is required. It used to be optional, which meant the rule keeping a
    rate of pay off an organisation could be skipped by omitting it — and the
    record's own `nodeId` was never checked against the node handed in, so the
    rule could also be satisfied against a different node entirely.
    """
    node_id = _text(record.get("nodeId"))
    if not node_id:
        raise Rejected("a record has no nodeId")
    if node_id != _text(node.get("id")):
        raise Rejected(
            f"{node_id}: record nodeId does not match the node it was checked against "
            f"({_text(node.get('id'))!r})"
        )

    state = _text(record.get("financialEvidenceStatus"))
    if not state:
        raise Rejected(f"{node_id}: financialEvidenceStatus is required")
    if state not in STATES:
        raise Rejected(f"{node_id}: state {state!r} is not one of {sorted(STATES)}")

    # An absence claim carries no figure — but it still carries provenance,
    # because "we read this document and it names no figure for this unit" is
    # a claim about a document. The first draft returned here before any
    # provenance check and passed every other key through untouched.
    if state == "no_direct_amount_found":
        for field in ("amount", "amountRaw", "units", "costBasis", "normalizedMultiplier"):
            if record.get(field) not in (None, ""):
                raise Rejected(
                    f"{node_id}: no_direct_amount_found carries {field}; an absence claim has no figure"
                )
        if len(_text(record.get("searchNote"))) < 16:
            raise Rejected(f"{node_id}: no_direct_amount_found needs a searchNote saying what was searched")
        url = _validate_source_url(record, node_id)
        _validate_artifact(record, node_id)
        return {
            "nodeId": node_id,
            "financialEvidenceStatus": state,
            "searchNote": _text(record.get("searchNote")),
            "sourceUrl": url,
            "sourceType": _validate_source_type(record, node_id),
            "documentSha256": _text(record.get("documentSha256")).lower(),
            "retrievedAt": _text(record.get("retrievedAt")),
        }

    basis = _text(record.get("costBasis"))
    if basis not in BASES:
        raise Rejected(f"{node_id}: costBasis {basis!r} is not one of {sorted(BASES)}")

    source_type = _validate_source_type(record, node_id)
    if basis not in SOURCE_BASES[source_type]:
        raise Rejected(
            f"{node_id}: a {source_type} cannot report {basis!r} "
            f"(it reports {sorted(SOURCE_BASES[source_type])})"
        )

    units = _text(record.get("units"))
    if units not in UNITS:
        raise Rejected(f"{node_id}: units {units!r} is not one of {sorted(UNITS)}")
    if basis in NON_MONETARY_BASES and units not in COUNT_UNITS:
        raise Rejected(f"{node_id}: basis {basis!r} is not money but units are {units!r}")
    if basis not in NON_MONETARY_BASES and units not in MONETARY_UNITS:
        raise Rejected(f"{node_id}: basis {basis!r} is money but units are {units!r}")

    multiplier = record.get("normalizedMultiplier")
    if not isinstance(multiplier, int) or isinstance(multiplier, bool):
        raise Rejected(f"{node_id}: normalizedMultiplier must be an integer, not {multiplier!r}")
    if multiplier != UNITS[units]:
        raise Rejected(
            f"{node_id}: units {units!r} means a multiplier of {UNITS[units]}, but the record "
            f"declares {multiplier!r}"
        )

    # --- the units claim, made evidence-bearing -------------------------
    units_evidence = _text(record.get("unitsEvidence")).casefold()
    if not units_evidence:
        raise Rejected(
            f"{node_id}: unitsEvidence is required — the verbatim heading or note in which the "
            "document states its scale. Without it the units check only compares the record to itself."
        )
    kind = "count" if units in COUNT_UNITS else "money"
    stated, phrase = scale_stated_by(units_evidence, kind)
    if stated is None:
        raise Rejected(
            f"{node_id}: unitsEvidence {record.get('unitsEvidence')!r} states no scale "
            f"(expected one of {UNIT_PHRASES[units]})"
        )
    if stated != units:
        raise Rejected(
            f"{node_id}: unitsEvidence states {stated!r} (on {phrase!r}) but the record "
            f"declares {units!r}"
        )

    quote = _text(record.get("quote"))
    if len(quote) < 8:
        raise Rejected(f"{node_id}: quote is required — verbatim text from the source supporting the figure")

    printed = parse_amount_text(record.get("amountRaw"))
    # The printed digits must actually appear in the quoted line. This is what
    # catches a parser that already normalised the figure and then declared a
    # scaling unit on top of it, publishing 1000x high.
    bare = _text(record.get("amountRaw")).strip("()").replace(",", "").lstrip("-")
    if bare not in quote.replace(",", ""):
        raise Rejected(
            f"{node_id}: amountRaw {record.get('amountRaw')!r} does not appear in the quote; "
            "the figure must be the one the document prints"
        )

    amount = record.get("amount")
    if not _is_real_number(amount):
        raise Rejected(f"{node_id}: amount {amount!r} is missing, not a number, or not finite")
    expected = printed * UNITS[units]
    if abs(float(amount) - expected) > max(abs(expected) * 1e-9, 0.005):
        raise Rejected(
            f"{node_id}: amount {amount!r} does not equal amountRaw {record.get('amountRaw')!r} "
            f"x {UNITS[units]} = {expected}"
        )
    if float(amount) == 0:
        raise Rejected(f"{node_id}: amount is zero; zero is never published as a measurement")
    # The ceiling is the caller's, never the record's. Reading it off the
    # record would let a record grant itself an exemption from the one check
    # that catches a units error surviving everything else. A headcount gets
    # its own bound rather than no bound: exempting every non-monetary basis
    # left a staff count with nothing to exceed.
    ceiling = DEFAULT_COUNT_CEILING if basis in NON_MONETARY_BASES else amount_ceiling
    if abs(float(amount)) > ceiling:
        raise Rejected(
            f"{node_id}: amount {amount!r} exceeds the whole government's outlays; "
            "a figure this size is a units error, not a unit's budget"
        )

    # --- period ---------------------------------------------------------
    fiscal_year = record.get("fiscalYear")
    if not isinstance(fiscal_year, int) or isinstance(fiscal_year, bool):
        raise Rejected(f"{node_id}: fiscalYear is required and must be an integer")
    this_year = datetime.now(timezone.utc).year
    if not (1900 <= fiscal_year <= this_year + 2):
        raise Rejected(f"{node_id}: fiscalYear {fiscal_year} is not a plausible federal fiscal year")

    coverage = _text(record.get("periodCoverage"))
    if coverage not in PERIOD_COVERAGES:
        raise Rejected(f"{node_id}: periodCoverage {coverage!r} is not one of {sorted(PERIOD_COVERAGES)}")
    as_of = _text(record.get("periodAsOf"))
    if coverage in PERIODS_NEEDING_AS_OF:
        if not as_of:
            raise Rejected(
                f"{node_id}: periodCoverage {coverage!r} needs periodAsOf — two year-to-date figures "
                "cut off at different months are not the same measurement"
            )
        _past_iso_date(as_of, f"{node_id}: periodAsOf")
    elif as_of:
        raise Rejected(f"{node_id}: periodCoverage {coverage!r} takes no periodAsOf")

    retrieved = _past_iso_date(record.get("retrievedAt"), f"{node_id}: retrievedAt")
    # Money that has moved cannot be reported for a year that has not finished.
    if basis in REALIZED_BASES and coverage == "full_fiscal_year":
        if fiscal_year >= federal_fiscal_year(retrieved):
            raise Rejected(
                f"{node_id}: {basis!r} for the whole of FY{fiscal_year} could not exist when the "
                f"document was retrieved ({retrieved.isoformat()}); that fiscal year had not ended"
            )
    if basis in REALIZED_BASES and fiscal_year > federal_fiscal_year(retrieved):
        raise Rejected(
            f"{node_id}: {basis!r} for FY{fiscal_year} is a realized figure for a year that had not "
            f"begun when the document was retrieved ({retrieved.isoformat()})"
        )

    # --- scope ----------------------------------------------------------
    scope = _text(record.get("scopeMatch"))
    if scope not in SCOPE_MATCHES:
        raise Rejected(f"{node_id}: scopeMatch {scope!r} is not one of {sorted(SCOPE_MATCHES)}")
    amount_scope = _text(record.get("amountScope"))
    if not amount_scope:
        raise Rejected(f"{node_id}: amountScope is required — the source's own name for what it measured")
    # An exact claim is settled by label equality, not by assertion. This is
    # the same test `evidence.py` uses to decide whether a page names a unit,
    # and it is what stops "Fish and Wildlife and Parks" being filed as either
    # of the two agencies it covers.
    if scope in EXACT_SCOPES:
        if canonical_name_key(amount_scope) != canonical_name_key(_text(node.get("name"))):
            raise Rejected(
                f"{node_id}: scopeMatch 'exact' claims the source names this unit, but the source "
                f"calls it {amount_scope!r} and the graph calls it {_text(node.get('name'))!r}. "
                "Use 'parent', 'broader_account' or 'proxy', or add an alias first."
            )

    rollup = _text(record.get("rollupRole"))
    if rollup not in ROLLUP_ROLES:
        raise Rejected(f"{node_id}: rollupRole {rollup!r} is not one of {sorted(ROLLUP_ROLES)}")

    # --- provenance -----------------------------------------------------
    url = _validate_source_url(record, node_id)
    _validate_artifact(record, node_id)
    locator = record.get("locator")
    if not isinstance(locator, Mapping) or not any(_text(v) for v in locator.values()):
        raise Rejected(
            f"{node_id}: locator is required and must point somewhere reproducible "
            "(page/table/row/column, or a named section)"
        )

    # --- node kind ------------------------------------------------------
    node_is_org = is_organisation(node)
    if basis in POSITION_ONLY_BASES and node_is_org:
        raise Rejected(f"{node_id}: basis {basis!r} is one post's pay and cannot sit on an organisation")
    if basis not in POSITION_ONLY_BASES and not node_is_org:
        raise Rejected(f"{node_id}: basis {basis!r} is an organisation's measure and cannot sit on a {node.get('type')!r}")

    if state == "conflicted" and not (record.get("conflictsWith") or []):
        raise Rejected(f"{node_id}: a conflicted record must name what it conflicts with")

    return {
        **record,
        "nodeId": node_id,
        "costBasis": basis,
        "units": units,
        "amount": float(amount),
        "sourceUrl": url,
        "sourceType": source_type,
        "financialEvidenceStatus": state,
    }


def _validate_source_type(record: Mapping[str, Any], node_id: str) -> str:
    source_type = _text(record.get("sourceType"))
    if source_type not in SOURCE_TYPES:
        raise Rejected(f"{node_id}: sourceType {source_type!r} is not one of {sorted(SOURCE_TYPES)}")
    return source_type


def _validate_source_url(record: Mapping[str, Any], node_id: str) -> str:
    """A parsed URL, not a string split.

    The first draft took everything after `//` up to the first `/` as the
    host, so a URL with a query string and no path — `https://evil.com?x=.gov`
    — was read as a government host.
    """
    url = _text(record.get("sourceUrl"))
    if not url:
        raise Rejected(f"{node_id}: sourceUrl is required")
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise Rejected(f"{node_id}: sourceUrl {url!r} must be https")
    host = (parts.hostname or "").casefold()
    if not host:
        raise Rejected(f"{node_id}: sourceUrl {url!r} has no host")
    if not (host == "gov" or host.endswith(".gov") or host == "mil" or host.endswith(".mil")):
        raise Rejected(
            f"{node_id}: sourceUrl host {host!r} is not a .gov or .mil host; "
            "a third-party mirror is a lead, never evidence"
        )
    return url


def _validate_artifact(record: Mapping[str, Any], node_id: str) -> None:
    digest = _text(record.get("documentSha256")).lower()
    if not _SHA256.match(digest):
        raise Rejected(f"{node_id}: documentSha256 {record.get('documentSha256')!r} is not a sha256 digest")
    _past_iso_date(record.get("retrievedAt"), f"{node_id}: retrievedAt")


def classify(record: Mapping[str, Any]) -> str:
    """Grade a structurally valid record. May lower an author's claim, never raise it."""
    state = _text(record.get("financialEvidenceStatus"))
    if state in {"no_direct_amount_found", "conflicted"}:
        return state
    derived = "verified" if _text(record.get("scopeMatch")) in EXACT_SCOPES else "partial"
    if state in STATE_RANK and STATE_RANK[state] < STATE_RANK[derived]:
        return state
    return derived


def detect_conflicts(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Comparable records that disagree by more than the documents could round."""
    valid = [
        r for r in records
        if _text(r.get("financialEvidenceStatus")) != "no_direct_amount_found"
        and _is_real_number(r.get("amount"))
    ]
    conflicts: list[dict[str, Any]] = []
    for i, left in enumerate(valid):
        for right in valid[i + 1 :]:
            if _text(left.get("nodeId")) != _text(right.get("nodeId")):
                continue
            if not comparable(left, right).comparable:
                continue
            # A total and the lines beneath it are not two sources disagreeing;
            # that is double counting, and double_counted() reports it.
            if _text(left.get("rollupRole")) != _text(right.get("rollupRole")):
                continue
            a, b = float(left["amount"]), float(right["amount"])
            slack = max(_rounding_slack(left), _rounding_slack(right))
            if abs(a - b) > slack:
                conflicts.append(
                    {
                        "nodeId": _text(left.get("nodeId")),
                        "costBasis": _text(left.get("costBasis")),
                        "fiscalYear": left.get("fiscalYear"),
                        "periodCoverage": _text(left.get("periodCoverage")),
                        "scopeMatch": _text(left.get("scopeMatch")),
                        "amounts": [a, b],
                        "sources": [_text(left.get("sourceUrl")), _text(right.get("sourceUrl"))],
                    }
                )
    return conflicts


def double_counted(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The same money stored twice for one unit and period.

    Two shapes. A total row kept beside the lines it totals; and the same row
    of the *same document* recorded twice, which is what happens when an
    extractor runs again.

    Deliberately NOT flagged: two same-role records from two different
    documents. That is corroboration, or a genuine disagreement — and
    `detect_conflicts` is what reports the second. An earlier version flagged
    it as double counting, which fired on ordinary good evidence: a unit
    funded from two appropriation accounts, and a figure confirmed by a second
    source. A validator that refuses honest data gets worked around, and the
    workaround is where the real damage happens.
    """
    groups: dict[tuple, list[Mapping[str, Any]]] = {}
    for record in records:
        if _text(record.get("financialEvidenceStatus")) == "no_direct_amount_found":
            continue
        key = (
            _text(record.get("nodeId")),
            _text(record.get("costBasis")),
            record.get("fiscalYear"),
            _text(record.get("periodCoverage")),
            _text(record.get("periodAsOf")),
        )
        groups.setdefault(key, []).append(record)
    findings = []
    for (node_id, basis, year, coverage, as_of), group in groups.items():
        roles = [_text(r.get("rollupRole")) for r in group]
        mixed = len(set(roles)) > 1 and set(roles) & {"total", "subtotal"}
        # the same row of the same document, recorded twice
        stamps = [(_text(r.get("documentSha256")), json.dumps(r.get("locator"), sort_keys=True, default=str))
                  for r in group]
        repeated = len(stamps) != len(set(stamps))
        if mixed or repeated:
            findings.append(
                {
                    "nodeId": node_id,
                    "costBasis": basis,
                    "fiscalYear": year,
                    "periodCoverage": coverage,
                    "periodAsOf": as_of,
                    "roles": sorted(set(roles)),
                    "shape": "total_beside_its_lines" if mixed else "same_row_recorded_twice",
                }
            )
    return findings
