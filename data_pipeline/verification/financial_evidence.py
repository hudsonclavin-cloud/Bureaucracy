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
when their basis, fiscal year, coverage period and normalised units all
agree.** Everything else here follows from that.

The other reason this is its own module: the single worst error this project
could ship is a units error. A Congressional Justification prints

    Civilian Board of Contract Appeals .......... 10,248

meaning ten million dollars, and a parser that reads it as ten thousand is
wrong by 1000x while looking entirely reasonable. Treasury's API hands back
raw dollars, so nothing in this repository has ever had to think about units.
Every record here declares its units and its multiplier, and the validator
re-derives the amount from the raw text rather than trusting it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Iterable, Mapping


class Rejected(Exception):
    """A record that is structurally invalid. Not a finding — a malformed record."""


# --------------------------------------------------------------------------
# Vocabularies. Each entry is a different measurement of a different thing,
# and the whole point of naming them is that the graph must never let one
# stand in for another.

#: What kind of number this is. `docs/COST_NOMINATION_RUNBOOK.md` named five;
#: Congressional Justifications report several the five could not express, and
#: a record whose basis has no name gets guessed at, which is how a request
#: ends up displayed as a cost.
BASES = {
    # money an agency asked Congress for. A plan, not an outcome, and by far
    # the most common thing a CJ reports.
    "budget_request",
    # money Congress enacted in an appropriations act.
    "appropriations",
    # money made available to be obligated, from whatever source.
    "budget_authority",
    # money committed. Not spent.
    "obligations",
    # cash out, net of offsetting receipts. What the Treasury statement reports
    # and what the whole existing cascade is denominated in.
    "net_outlays",
    # cash out before offsetting receipts are netted off. The Monthly Treasury
    # Statement prints both, they differ by billions on a large agency, and
    # they are not interchangeable.
    "gross_outlays",
    # accrual, audited, from a Statement of Net Cost. The only audited basis.
    "audited_net_cost",
    # what one post pays. Never an organisation's cost.
    "basic_pay",
    # total compensation for a unit's staff. An input to cost, not cost.
    "payroll",
    # not money at all. Carried here because CJs report it in the same tables
    # and it is the honest answer when a unit's money cannot be separated but
    # its staffing can.
    "full_time_equivalents",
}

#: A basis that is not denominated in dollars needs different units and must
#: never be rendered with a currency symbol.
NON_MONETARY_BASES = {"full_time_equivalents"}

#: One post's compensation, which may only ever sit on a position node — the
#: release gate already refuses a measured cost on a non-organisation, and this
#: is the mirror of that rule.
POSITION_ONLY_BASES = {"basic_pay"}

#: Declared units, and the factor that turns the printed figure into the base
#: unit (dollars, or people). Budget documents print thousands as often as
#: dollars and say so only in a table heading.
UNITS = {
    "usd": 1,
    "thousands_usd": 1_000,
    "millions_usd": 1_000_000,
    "billions_usd": 1_000_000_000,
    "count": 1,
}

MONETARY_UNITS = {"usd", "thousands_usd", "millions_usd", "billions_usd"}
COUNT_UNITS = {"count"}

#: What kind of document the figure was read out of.
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

#: How well the figure's scope matches the node it is being attached to. This
#: is the runbook's "too broad / too narrow / different population" rule turned
#: into a field a validator can act on, because prose in a runbook did not stop
#: `Fish and Wildlife and Parks` being read as either of the two agencies it
#: covers.
SCOPE_MATCHES = {
    # the source names this unit and only this unit.
    "exact",
    # the figure covers this unit's parent, or a grouping containing it.
    "parent",
    # the figure covers one part of this unit.
    "child",
    # the figure is an account that funds this unit among others.
    "broader_account",
    # the figure stands in for the unit without naming it.
    "proxy",
    # cannot be determined from the source.
    "ambiguous",
}

#: Only an exact scope match can ever be published as a direct figure for the
#: node. Everything else is at best a scope-limited, official-derived number.
EXACT_SCOPES = {"exact"}

#: Where a figure sits in its table. A total row and the lines beneath it are
#: the same money counted twice, and summing across roles is the classic way a
#: budget table gets double-counted.
ROLLUP_ROLES = {"line", "subtotal", "total"}

#: The published verification state.
STATES = {
    # direct primary-source figure, exact scope, everything checks.
    "verified",
    # official source, but the figure maps to a parent, a broader account, or
    # a documented component rather than this unit.
    "partial",
    # not enough to publish as official.
    "unverified",
    # credible sources disagree for a comparable scope, basis and period.
    "conflicted",
    # searched, and no direct public figure maps to this node. An answer, not
    # a gap: it is the difference between "nobody looked" and "we looked".
    "no_direct_amount_found",
}

#: How far two comparable figures may differ before they are called a
#: conflict. Budget documents round; a cent of drift is not a disagreement.
CONFLICT_TOLERANCE = 0.005  # 0.5%

#: Exactly what this module may write onto a node, so a later build can take
#: back exactly those fields and nothing else.
#:
#: This is not optional bookkeeping. `apply_evidence_to_tree` clears every
#: field the identity track owns before re-applying, because the exporter
#: re-feeds the previously published graph as a payload — without the owned
#: set, a withdrawn record keeps being published forever and a retraction can
#: never reach the site. The first version of the identity module cleared the
#: node's whole URL list instead and stripped the FiscalData URL off 26
#: measured nodes. So: a named set, and it is a set of fields this module
#: alone writes.
FINANCIAL_EVIDENCE_OWNED_FIELDS = (
    "financialEvidence",
    "financialEvidenceStatus",
    "financialConflicts",
    # exactly the URLs this module added to sourceUrls, never the whole list
    "financialEvidenceUrls",
    # the date this module set, so a withdrawal takes back that one and leaves
    # a date some other stage supplied
    "financialEvidenceVerifiedAt",
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_AMOUNT_TEXT = re.compile(r"^\(?-?[\d,]+(?:\.\d+)?\)?$")


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def parse_amount_text(raw: str) -> float:
    """Read the figure as the document prints it.

    Budget tables use accounting negatives — `(1,234)` means −1234 — and
    thousands separators. Anything else is refused rather than guessed at.
    """
    text = _text(raw)
    if not text or not _AMOUNT_TEXT.match(text):
        raise Rejected(f"amountRaw {raw!r} is not a figure this parser will read")
    negative = text.startswith("(") and text.endswith(")")
    cleaned = text.strip("()").replace(",", "")
    try:
        value = float(cleaned)
    except ValueError as error:  # pragma: no cover - guarded by the regex
        raise Rejected(f"amountRaw {raw!r} is not numeric") from error
    return -value if negative else value


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
    """The same test the audit harness and the release gate use."""
    type_text = _text(node.get("type")).casefold()
    return not node.get("synthetic") and not any(
        word in type_text for word in ("position", "role", "caucus", "office holder")
    )


@dataclass(frozen=True)
class Comparison:
    """Why two figures may or may not be set beside one another."""

    comparable: bool
    reason: str


def comparable(left: Mapping[str, Any], right: Mapping[str, Any]) -> Comparison:
    """Two amounts may be compared only when they measure the same thing.

    This is the rule the whole module exists for. The release gate's
    child-sum check is arithmetic on `resolved_total_amount`, and it is only
    meaningful because every figure in the cascade is FYTD net outlays from
    one statement. A budget request and an outlay are different quantities
    about different years; subtracting one from the other produces a number
    with no referent.
    """
    for field, label in (
        ("costBasis", "basis"),
        ("fiscalYear", "fiscal year"),
        ("periodCoverage", "coverage period"),
    ):
        if _text(left.get(field)) != _text(right.get(field)):
            return Comparison(False, f"different {label}")
    left_unit = _text(left.get("units"))
    right_unit = _text(right.get("units"))
    if (left_unit in COUNT_UNITS) != (right_unit in COUNT_UNITS):
        return Comparison(False, "one is a count and the other is money")
    return Comparison(True, "same basis, period and unit kind")


def validate_record(record: Mapping[str, Any], node: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Refuse a structurally invalid record. Returns the normalised record.

    A record that fails here is malformed, not merely weak — weakness is what
    `classify` grades. Nothing that fails this function may be stored.
    """
    node_id = _text(record.get("nodeId"))
    if not node_id:
        raise Rejected("a record has no nodeId")

    state = _text(record.get("costVerificationStatus"))
    if state and state not in STATES:
        raise Rejected(f"{node_id}: state {state!r} is not one of {sorted(STATES)}")

    # An absence claim carries no figure. Publishing "we searched and found
    # nothing" beside an amount would be self-contradicting.
    if state == "no_direct_amount_found":
        for field in ("amount", "amountRaw", "units", "costBasis"):
            if record.get(field) not in (None, ""):
                raise Rejected(
                    f"{node_id}: no_direct_amount_found carries {field}; an absence claim has no figure"
                )
        if not _text(record.get("searchNote")):
            raise Rejected(f"{node_id}: no_direct_amount_found needs a searchNote saying what was searched")
        return {**record, "nodeId": node_id, "costVerificationStatus": state}

    basis = _text(record.get("costBasis"))
    if basis not in BASES:
        raise Rejected(f"{node_id}: costBasis {basis!r} is not one of {sorted(BASES)}")

    units = _text(record.get("units"))
    if units not in UNITS:
        raise Rejected(f"{node_id}: units {units!r} is not one of {sorted(UNITS)}")

    # A headcount is not money and must not be rendered as money; a dollar
    # figure declared as a count would publish "$1,204" as "1,204 people".
    if basis in NON_MONETARY_BASES and units not in COUNT_UNITS:
        raise Rejected(f"{node_id}: basis {basis!r} is not money but units are {units!r}")
    if basis not in NON_MONETARY_BASES and units not in MONETARY_UNITS:
        raise Rejected(f"{node_id}: basis {basis!r} is money but units are {units!r}")

    declared_multiplier = record.get("normalizedMultiplier")
    if declared_multiplier is None:
        raise Rejected(f"{node_id}: normalizedMultiplier is required")
    if declared_multiplier != UNITS[units]:
        raise Rejected(
            f"{node_id}: units {units!r} means a multiplier of {UNITS[units]}, "
            f"but the record declares {declared_multiplier!r}"
        )

    # The figure is re-derived from the text the document prints rather than
    # trusted. This is the check that catches a 1000x units error.
    printed = parse_amount_text(record.get("amountRaw"))
    amount = record.get("amount")
    if not isinstance(amount, (int, float)) or isinstance(amount, bool):
        raise Rejected(f"{node_id}: amount is missing or not a number")
    expected = printed * UNITS[units]
    if abs(float(amount) - expected) > max(abs(expected) * 1e-9, 0.005):
        raise Rejected(
            f"{node_id}: amount {amount!r} does not equal amountRaw {record.get('amountRaw')!r} "
            f"x {UNITS[units]} = {expected}"
        )
    # Zero is never published, here as everywhere else in this repository.
    if float(amount) == 0:
        raise Rejected(f"{node_id}: amount is zero; zero is never published as a measurement")

    fiscal_year = record.get("fiscalYear")
    if not isinstance(fiscal_year, int) or isinstance(fiscal_year, bool):
        raise Rejected(f"{node_id}: fiscalYear is required and must be an integer")
    this_year = datetime.now(timezone.utc).year
    if not (1900 <= fiscal_year <= this_year + 2):
        raise Rejected(f"{node_id}: fiscalYear {fiscal_year} is not a plausible federal fiscal year")

    # A year alone does not say whether this is the full year, a year to date,
    # or a quarter — and the existing cascade is denominated in FYTD, which is
    # not a full year.
    if not _text(record.get("periodCoverage")):
        raise Rejected(
            f"{node_id}: periodCoverage is required — a fiscal year alone does not say "
            "whether the figure is full-year, year-to-date, or a part period"
        )

    scope = _text(record.get("scopeMatch"))
    if scope not in SCOPE_MATCHES:
        raise Rejected(f"{node_id}: scopeMatch {scope!r} is not one of {sorted(SCOPE_MATCHES)}")
    if not _text(record.get("amountScope")):
        raise Rejected(f"{node_id}: amountScope is required — the source's own name for what it measured")

    rollup = _text(record.get("rollupRole"))
    if rollup not in ROLLUP_ROLES:
        raise Rejected(f"{node_id}: rollupRole {rollup!r} is not one of {sorted(ROLLUP_ROLES)}")

    source_type = _text(record.get("sourceType"))
    if source_type not in SOURCE_TYPES:
        raise Rejected(f"{node_id}: sourceType {source_type!r} is not one of {sorted(SOURCE_TYPES)}")

    url = _text(record.get("sourceUrl"))
    if not url:
        raise Rejected(f"{node_id}: sourceUrl is required")
    host = url.split("//", 1)[-1].split("/", 1)[0].casefold()
    if not (host.endswith(".gov") or host.endswith(".mil")):
        raise Rejected(
            f"{node_id}: sourceUrl host {host!r} is not a .gov or .mil host; "
            "a third-party mirror is a lead, never evidence"
        )

    # The artifact must be preserved and identifiable, or the figure cannot be
    # audited against what was actually served.
    digest = _text(record.get("documentSha256")).lower()
    if not _SHA256.match(digest):
        raise Rejected(f"{node_id}: documentSha256 {record.get('documentSha256')!r} is not a sha256 digest")
    _past_iso_date(record.get("retrievedAt"), f"{node_id}: retrievedAt")

    locator = record.get("locator")
    if not isinstance(locator, Mapping) or not any(_text(v) for v in locator.values()):
        raise Rejected(
            f"{node_id}: locator is required and must point somewhere reproducible "
            "(page/table/row/column, or a named section)"
        )

    quote = _text(record.get("quote"))
    if len(quote) < 8:
        raise Rejected(f"{node_id}: quote is required — verbatim text from the source supporting the figure")

    # The mirror of the release gate's rule that a measured cost sits only on
    # an organisation: a rate of pay is a fact about a post, and an
    # organisation's money is not.
    if node is not None:
        node_is_org = is_organisation(node)
        if basis in POSITION_ONLY_BASES and node_is_org:
            raise Rejected(f"{node_id}: basis {basis!r} is one post's pay and cannot sit on an organisation")
        if basis not in POSITION_ONLY_BASES and not node_is_org:
            raise Rejected(f"{node_id}: basis {basis!r} is an organisation's measure and cannot sit on a position")

    return {**record, "nodeId": node_id, "costBasis": basis, "units": units, "amount": float(amount)}


def classify(record: Mapping[str, Any]) -> str:
    """Grade a structurally valid record. Weakness, not malformation."""
    state = _text(record.get("costVerificationStatus"))
    if state in {"no_direct_amount_found", "conflicted"}:
        return state
    # Only a figure the source names for this exact unit may be shown as the
    # unit's own. Everything else is official-derived and scope-limited, and
    # the panel has to say which.
    if _text(record.get("scopeMatch")) in EXACT_SCOPES:
        return "verified"
    return "partial"


def detect_conflicts(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Comparable records that disagree.

    Two figures from different documents for the same unit, basis and period
    that differ beyond rounding are a real finding: one of them is wrong, or
    they measure something subtler than either says. Neither may be chosen
    automatically.
    """
    valid = [r for r in records if _text(r.get("costVerificationStatus")) != "no_direct_amount_found"]
    conflicts: list[dict[str, Any]] = []
    for i, left in enumerate(valid):
        for right in valid[i + 1 :]:
            if _text(left.get("nodeId")) != _text(right.get("nodeId")):
                continue
            if not comparable(left, right).comparable:
                continue
            a, b = float(left.get("amount") or 0), float(right.get("amount") or 0)
            scale = max(abs(a), abs(b)) or 1.0
            if abs(a - b) / scale > CONFLICT_TOLERANCE:
                conflicts.append(
                    {
                        "nodeId": _text(left.get("nodeId")),
                        "costBasis": _text(left.get("costBasis")),
                        "fiscalYear": left.get("fiscalYear"),
                        "periodCoverage": _text(left.get("periodCoverage")),
                        "amounts": [a, b],
                        "sources": [_text(left.get("sourceUrl")), _text(right.get("sourceUrl"))],
                    }
                )
    return conflicts


def double_counted(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """A total row recorded beside the lines it totals, for one node and period.

    Budget tables print a total and its components together. Storing both for
    the same unit means whichever is summed later counts the money twice.
    """
    groups: dict[tuple[str, str, Any, str], list[Mapping[str, Any]]] = {}
    for record in records:
        if _text(record.get("costVerificationStatus")) == "no_direct_amount_found":
            continue
        key = (
            _text(record.get("nodeId")),
            _text(record.get("costBasis")),
            record.get("fiscalYear"),
            _text(record.get("periodCoverage")),
        )
        groups.setdefault(key, []).append(record)
    findings = []
    for (node_id, basis, year, period), group in groups.items():
        roles = {_text(r.get("rollupRole")) for r in group}
        if len(roles) > 1 and roles & {"total", "subtotal"}:
            findings.append(
                {
                    "nodeId": node_id,
                    "costBasis": basis,
                    "fiscalYear": year,
                    "periodCoverage": period,
                    "roles": sorted(roles),
                }
            )
    return findings
