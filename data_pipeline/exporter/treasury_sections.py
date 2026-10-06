"""The Monthly Treasury Statement's own tree, and what it nets.

Table 5 prints each agency as a section: a header line with no amount, the
lines beneath it (bureaus, programmes, funds), the section's receipts-type
lines — proprietary receipts from the public, intrabudgetary transactions,
offsetting governmental receipts — and a "Total--" line that is the header's
net figure. The identity the statement itself prints, checked here against
the 2026-07-31 statement to the cent: every top-level section total, plus
"Undistributed Offsetting Receipts" (a top-level section that belongs to
no agency), sums to Total Outlays; and inside a section, the lines sum to
the total.

The cost cascade used to set every negative line aside, which left the
positive lines summing past the net anchor and every measured department
published at 96% of what the Treasury reported. This module gives the
exporter what it needs to publish the true lines instead: which rows are a
section's receipts, which rows are components of those receipts (never
organisations, never matched to a node), which top-level section a row
belongs to, and whether the identity holds for the statement in hand.
Every row here is the crawler's row (originalName, rollup_total_amount,
classification_id, parent_id, is_header); nothing is typed in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable



def parse_cost_amount(value: Any) -> float | None:
    """The crawler emits floats; anything else here is a header (None)."""
    if value in (None, "", "null"):
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None

# The eight labels Table 5 uses for money that is netted rather than spent.
# Three appear inside agency sections; the other five make up the
# government-wide "Undistributed Offsetting Receipts" section.
RECEIPTS_LABELS = frozenset(
    {
        "Proprietary Receipts from the Public",
        "Intrabudgetary Transactions",
        "Offsetting Governmental Receipts",
        "Employer Share, Employee Retirement",
        "Interest Received by Trust Funds",
        "Rents and Royalties on the Outer Continental Shelf Lands",
        "Sale of Major Assets",
        "Other Interest",
    }
)
UNDISTRIBUTED_LABEL = "Undistributed Offsetting Receipts"
TOTAL_PREFIX = "Total--"
# Rounding across 800 lines: the statement itself reconciles to the cent, and
# a dollar is the loosest bound that still says "the same number".
IDENTITY_TOLERANCE = 1.0


def plain_label(row: dict[str, Any]) -> str:
    """The printed label without its trailing colon or Total-- prefix."""
    text = str(row.get("originalName") or row.get("name") or "").strip()
    if text.startswith(TOTAL_PREFIX):
        text = text[len(TOTAL_PREFIX):]
    return text.rstrip(":").strip()


def is_total_row(row: dict[str, Any]) -> bool:
    return str(row.get("originalName") or "").startswith(TOTAL_PREFIX)


def is_header_row(row: dict[str, Any]) -> bool:
    return bool(row.get("is_header")) or parse_cost_amount(row.get("rollup_total_amount")) is None


def is_receipts_row(row: dict[str, Any]) -> bool:
    """A receipts-type row: one of the eight netted labels, or the
    government-wide section that is made of them. Everything beneath such a
    row is a receipt OF an agency, never an agency."""
    label = plain_label(row)
    return label in RECEIPTS_LABELS or label == UNDISTRIBUTED_LABEL


@dataclass
class SectionTree:
    rows: dict[str, dict[str, Any]] = field(default_factory=dict)
    children: dict[str | None, list[dict[str, Any]]] = field(default_factory=dict)
    parent_of: dict[str, str | None] = field(default_factory=dict)

    @classmethod
    def from_rows(cls, rows: Iterable[dict[str, Any]]) -> "SectionTree":
        tree = cls()
        ordered = sorted(
            (r for r in rows if isinstance(r, dict) and r.get("classification_id")),
            key=lambda r: int(r.get("print_order") or 0),
        )
        for row in ordered:
            tree.rows[str(row["classification_id"])] = row
        for row in ordered:
            parent = str(row.get("parent_id") or "") or None
            if parent not in tree.rows:
                parent = None
            tree.parent_of[str(row["classification_id"])] = parent
            tree.children.setdefault(parent, []).append(row)
        return tree

    @property
    def complete(self) -> bool:
        """Did the crawler hand over the tree at all? Older payloads carry no
        ids, and then nothing below can be said."""
        return bool(self.rows)

    def kids(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        return list(self.children.get(str(row.get("classification_id") or ""), []))

    def top_sections(self) -> list[dict[str, Any]]:
        return [r for r in self.children.get(None, []) if is_header_row(r)]

    def total_row(self, header: dict[str, Any]) -> dict[str, Any] | None:
        totals = [k for k in self.kids(header) if is_total_row(k)]
        return totals[0] if len(totals) == 1 else None

    def amount(self, row: dict[str, Any]) -> float:
        """A line's amount; a header's is the sum of its non-total children."""
        own = parse_cost_amount(row.get("rollup_total_amount"))
        if own is not None and not is_header_row(row):
            return float(own)
        return sum(self.amount(k) for k in self.kids(row) if not is_total_row(k))

    def section_total(self, header: dict[str, Any]) -> float:
        total = self.total_row(header)
        return float(parse_cost_amount(total.get("rollup_total_amount")) or 0.0) if total else self.amount(header)

    def top_section_of(self, row: dict[str, Any]) -> dict[str, Any] | None:
        current = row
        seen = 0
        while True:
            parent = self.parent_of.get(str(current.get("classification_id") or ""))
            if parent is None:
                return current if is_header_row(current) or current is not row else None
            current = self.rows[parent]
            seen += 1
            if seen > 50:
                return None

    def receipts_rows(self, header: dict[str, Any]) -> list[dict[str, Any]]:
        """The section's own receipts-type lines, direct children only."""
        return [k for k in self.kids(header) if plain_label(k) in RECEIPTS_LABELS and not is_total_row(k)]

    def header_components(self, header: dict[str, Any]) -> list[tuple[dict[str, Any], float]]:
        """The lines the statement prints beneath a header, each with its
        amount, in print order: the rows a reader adds up to get the header's
        figure when the statement prints no "Total--" line for it.

        A "Total--" child is never a component (it is the sum, not a part of
        it). A receipts-type child -- "Proprietary Receipts from the Public",
        which may itself be a header over per-agency rows -- is ONE component
        at its own netted amount, the shape `make_receipts_node` already
        gives it, so the parts listed are the parts the statement prints at
        this level and the sum is the statement's own arithmetic. Any other
        sub-header is descended into, because its lines are this header's
        lines printed one level further in ("Postal Service" prints an
        "Off-Budget" header with two lines beneath and one line beside it).
        """
        out: list[tuple[dict[str, Any], float]] = []
        for kid in self.kids(header):
            if is_total_row(kid):
                continue
            if is_receipts_row(kid) or not is_header_row(kid):
                out.append((kid, self.amount(kid)))
                continue
            out.extend(self.header_components(kid))
        return out

    def total_less_headers(self) -> list[dict[str, Any]]:
        """Headers the statement prints lines beneath and totals nowhere.

        Table 5 prints some sub-agencies this way -- "Natural Resources
        Conservation Service:" with three lines under it and no "Total--"
        line -- so the unit's figure exists on the page only as the sum of
        those lines. A header WITH a "Total--" child is excluded (the total is
        the figure, and the ordinary one-line-one-node rule reads it); so is
        every header inside a receipts-type subtree, where an agency's name
        labels a receipt of that agency and not the agency; so is a header
        with nothing but headers or totals beneath it, which prints no figure
        at all.
        """
        components = self.receipts_component_ids()
        out: list[dict[str, Any]] = []
        for row in self.rows.values():
            if not is_header_row(row) or self.total_row(row) is not None:
                continue
            if str(row.get("classification_id") or "") in components:
                continue
            if not self.header_components(row):
                continue
            out.append(row)
        return out

    def receipts_component_ids(self) -> set[str]:
        """Every row inside a receipts-type subtree — a "Department of the
        Navy" under "Proprietary Receipts from the Public:" is a receipt of
        the Navy's, not the Navy, and must never be matched to a node."""
        out: set[str] = set()

        def mark(row: dict[str, Any]) -> None:
            for kid in self.kids(row):
                out.add(str(kid.get("classification_id") or ""))
                mark(kid)

        for row in self.rows.values():
            if is_receipts_row(row):
                out.add(str(row.get("classification_id") or ""))
                mark(row)
        return out

    def undistributed_section(self) -> dict[str, Any] | None:
        for row in self.top_sections():
            if plain_label(row) == UNDISTRIBUTED_LABEL:
                return row
        return None

    def identity(self, anchor: float | None) -> dict[str, Any]:
        """Do the top-level section totals sum to the anchor?"""
        sections = self.top_sections()
        total = sum(self.section_total(s) for s in sections)
        holds = anchor is not None and bool(sections) and abs(total - float(anchor)) <= IDENTITY_TOLERANCE
        return {
            "anchor": anchor,
            "sections": len(sections),
            "section_totals_sum": round(total, 2),
            "difference": None if anchor is None else round(total - float(anchor), 2),
            "holds": holds,
        }

    def section_mismatches(self) -> list[dict[str, Any]]:
        """Headers whose lines do not sum to their own Total-- line."""
        out = []
        for row in self.rows.values():
            if not is_header_row(row):
                continue
            total = self.total_row(row)
            if total is None:
                continue
            lines = sum(self.amount(k) for k in self.kids(row) if not is_total_row(k))
            printed = float(parse_cost_amount(total.get("rollup_total_amount")) or 0.0)
            if abs(lines - printed) > IDENTITY_TOLERANCE:
                out.append({"section": plain_label(row), "lines_sum": round(lines, 2), "printed_total": round(printed, 2)})
        return out
