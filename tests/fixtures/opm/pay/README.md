# OPM pay tables

**Fetched 2026-09-11.** `www.opm.gov` was refused by this session's egress
proxy from 2026-09-09 through 2026-09-10 (see `docs/NETWORK_ACCESS.md` §0);
`docs/NETWORK_ACCESS.md` §0a traced that to an allowlist edit landing on the
wrong cloud environment (`Bureaucracy (Treasury)` instead of the `Default`
environment this session actually runs in). Once the correct environment's
allowlist was widened, `scripts/probe_network_access.py` confirmed
`www.opm.gov` reachable and this fetch succeeded on the first try:

    python scripts/fetch_fixture.py \
      https://www.opm.gov/policy-data-oversight/pay-leave/salaries-wages/salary-tables/26Tables/exec/html/EX.aspx \
      opm/pay/executive_schedule_2026.html

`executive_schedule_2026.html` (56,991 bytes, sha256
`aacccfcb788a08a93a2bd0af20dca967aa8f1a8b5aafeb3c316b1b0168cbd4ab`, recorded
verbatim in `executive_schedule_2026.html.meta.json`) is Salary Table
No. 2026-EX, "Rates of Basic Pay for the Executive Schedule (EX)", effective
January 2026:

| Level | Rate |
|---|---|
| I | $253,100 |
| II | $228,000 |
| III | $209,600 |
| IV | $197,200 |
| V | $184,900 |

The page also carries this footnote verbatim, which any parser must carry
through rather than drop:

> Under a provision in the Continuing Appropriations Act, 2026 (November 12,
> 2025), the freeze on the payable pay rates for the Vice President and
> certain senior political appointees continues through January 30, 2026.
> Future Congressional action will determine whether these frozen rates
> continue beyond that date.

1,596 rows of the PLUM archive carry the `EX` pay plan; 1,544 of those carry a
level (I–V) rather than a rate of pay. This table turns each level into the
statutory rate of basic pay, which gives those positions a figure from an
official source instead of nothing.

**Read by `data_pipeline/verification/pay_tables.py`, derived by
`scripts/derive_pay_evidence.py`.** The parser was written against this file
and not before it, which is the whole reason the fetch had to come first: a
parser fitted to a guess about markup is how a validator comes to run happily
and be wrong. It refuses rather than guesses — a reshaped table, an
unnumbered or undated one, a sixth level, a level printed twice, or a rate
that is not a figure all raise `Unreadable`.

**29 positions are priced, not 30.** An earlier draft of this README said 30,
counting every matched position that carries "a level". One of those thirty is
a GS-15 (`exec-dept-ed-ocr-deputy-assistant-secretary`), which Salary Table
2026-EX says nothing about. The pay plan, not the numeral, decides: the
archive files General Schedule grades in the same column, and two of its rows
carry a Roman numeral on a pay plan that is not the Executive Schedule at all
("THE SECRETARY" on `AD`, "BOARD MEMBER - CHAIR" on `WC`). A rate is published
only where the archive gives both an `EX` pay plan and a level this table
prints. Level I matches no node in the graph.

The two things the matcher had to be honest about, and how it is:

- the level is from the **2021–2025 archive** and the table is **effective
  January 2026**, so every record carries both halves with their own dates
  (`levelClaim`), the scope is `proxy` rather than `exact` because the table
  names a rank and not the unit, and `financial_evidence.classify` therefore
  grades all 29 `partial` — there is no route by which one becomes `verified`;
- basic pay is **not** the position's cost, so it is published in
  `positionPayRate` beside the listing and never in the cost cascade, and the
  release gate refuses a pay block that sits beside a measured cost status.

The freeze note above rides on every record and is printed verbatim in the
panel, because a rate that was frozen is not what was payable.

Two things the matcher will have to be honest about when it is written:

- the level comes from the **Biden administration's archive** (January 2021 –
  January 2025) and the table is **effective January 2026**, so the claim is
  "the archive reports this post at Level II; the January 2026 table pays Level
  II $X" — two sources, one of them about a past period, and neither says what
  the post pays its current holder;
- basic pay is not the position's cost. It excludes benefits, and it is not the
  node's share of federal outlays, which is what `resolved_total_amount` means
  everywhere else in this graph. It belongs beside the listing, not in the cost
  cascade.

The 2026-EX table also carries a note that a pay freeze for the Vice President
and certain senior political appointees runs through January 30, 2026, so a
level's table rate is not necessarily what was payable. Whatever the fetched
page says on that point must be carried through to the panel rather than
dropped.
