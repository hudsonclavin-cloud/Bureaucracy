# Proposed CLAUDE.md paragraph (headline fallback to a sourced non-cost figure)

For the coordinator to place after "A priced post's salary is its headline
figure, and the estimate is one click away (since 2026-10-05)". Not applied
to CLAUDE.md by this branch.

---

**An organisation's sourced figure of another kind is its headline, labelled
by basis (since 2026-10-07, the owner's decision).** The cost-coverage report
named two decisions only the owner could make; this is the first. An
organisation with no measured Treasury cost read "Not available" or a withheld
estimate in its headline while one of three sourced figures sat under its own
heading a few rows below: USAspending File A's gross outlays
(`usaspendingOutlays`), the sum of OMB's account rows for a completed year
(`ombBudget`), Treasury's audited net cost (`auditedNetCost`). The headline now
shows one of them, through the same mechanism that made salaries headlines on
2026-10-05: `costStandInOf` reads `PAY_STAND_IN_ORDER` and, where nothing
there applies, a second declared constant, `SOURCED_FIGURE_STAND_IN_ORDER`,
for an organisation only. A post never takes this path, nor a measured node,
a Treasury accounting line or a replaced unit. A unit beneath a negative
Treasury pool may: it has no estimate, and these figures are about it rather
than apportioned to it. Zero is never a headline; a negative figure is shown
as the source gives it, sign leading.

**The order is the anchor's two coordinates, and the trade between the first
two was measured.** The anchor is net outlays for the current fiscal year to
date. File A is the same year to date and cash, but gross, before offsetting
collections; OMB is the anchor's basis (net of offsetting collections, and in
OMB's words "generally consistent with" the statement) for a completed year;
audited net cost is a completed year and accrual, furthest on both counts. On
the 9 measured nodes that carry both File A and OMB beside their Treasury
line, File A sits a median 7.7% from the measured figure and OMB 18.4% (6 of 9
within 10% against 3 of 9), so the clock wins: File A, then OMB, then audited
net cost. Nine is a small sample; the stated reason is the clock and the
measurement agrees with it.

Each kind has its own heading, never COST — "GROSS OUTLAYS — USASPENDING FILE
A", "OUTLAYS — OMB PUBLIC BUDGET DATABASE", and "AUDITED NET COST — TREASURY
STATEMENT OF NET COST", whose only COST is its publisher's name for the
measure — a period line read off the block ("FY2026 to 2026-09-17, fiscal
year to date — gross, before offsetting collections; not the cost"; "FY2025,
a completed year — the sum of N account rows OMB files under this unit, not a
figure OMB prints, and not the cost"; "FY2025, ended 2025-09-30 — accrual,
not outlays; not the cost"), the hollow dashed badge "No measured cost; a
sourced figure of another kind is shown", and a sentence saying what the
figure measures and how it differs from the Treasury's net outlays — OMB's
own net-of-collections and "generally consistent" sentences quoted, its
"detail below millions is not available" where the block carries it, the
audited block's own `basisNote` verbatim. Where an estimate exists it stays
withheld and the "Show the estimate" button stays beside the new headline.
The directory view mirrors the order (`SOURCED_FIGURE_ORDER` in
`js/atlas.js`), names the row for the measure instead of "Cost", and puts the
figure's source on a row of its own; its formatter is its own
(`formatSourcedFigure`), so the exact Treasury formatter stays reachable from
the measured branch alone, which `tests/test_atlas_view.py` pins.

**Measured on the published graph of 2026-10-07: 72 organisations** are now
headed by a sourced figure — **34 by File A** (27 of them holding a withheld
estimate, 7 beneath a negative Treasury pool), **38 by OMB** (35 and 3; three
of the 38 net below zero — the Federal Retirement Thrift Investment Board,
the Farm Credit Administration and the National Technical Information
Service), and **none by audited net cost**: the one unmeasured organisation
carrying an audited figure, the Development Finance Corporation, also carries
File A, which the order puts first. The 62 that hold an estimate are exactly
`docs/COST_COVERAGE.md`'s "Estimate — with a sourced figure already published
beside it". The provenance line and the "How to read this" card count them as
a group of their own, never as measured, and the card's "have no figure at
all" became "have no cost figure at all", since ten of those now show a
figure of another kind. No pipeline field, no `MINIMAL_GRAPH_FIELDS` entry and
no published number changed; `scripts/frontend_smoke.mjs` opens one node of
each kind the graph has (audited is recorded as skipped while no node is
headed by it), a negative OMB figure, a unit beneath a negative pool and a
measured node carrying an OMB block, and holds the card's count to the served
graph.
