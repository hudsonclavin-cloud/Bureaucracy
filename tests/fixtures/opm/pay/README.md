# OPM pay tables

Five files, all `www.opm.gov`'s own bytes, each with the `.meta.json` its fetch
wrote. The Executive Schedule table (2026-09-11) is described below as it was
recorded; the four fetched on **2026-09-21** are the General Schedule, SES and
SL/ST tables, and they are read by `data_pipeline/verification/gs_pay.py`.

| File | Table | Fetched (UTC) | Bytes | sha256 |
|---|---|---|---|---|
| `executive_schedule_2026.html` | Salary Table No. 2026-EX | 2026-09-11T03:05:36Z | 56,991 | `aacccfcb788a08a93a2bd0af20dca967aa8f1a8b5aafeb3c316b1b0168cbd4ab` |
| `general_schedule_2026.pdf` | Salary Table 2026-GS (PDF; the cited document) | 2026-09-21T03:12:47Z | 8,498 | `88317177a9a7f21b1de6243993ac2d88d8db99889d9590826b76c52687df6578` |
| `general_schedule_2026.html` | Salary Table 2026-GS (HTML; corroboration) | 2026-09-21T02:59:12Z | 68,538 | `0bf65e7d20ed2ec841de4d25d946a5d4e34640deb98437f3d85081ec8e1f57c0` |
| `senior_executive_service_2026.html` | Salary Table No. 2026-ES | 2026-09-21T03:00:01Z | 56,855 | `202c3f63db65c9584d7ae37f7f40d58337762517f149c37b587ed71c09e53026` |
| `senior_level_2026.html` | Salary Table No. 2026-SL/ST | 2026-09-21T03:00:01Z | 55,165 | `5e3240ac3b749a48b2ba9c48083767ca426cdb1c04df48e514afb00f90dae97d` |

## The GS, SES and SL/ST tables (2026-09-21)

**Which URLs actually serve them.** The task named
`salary-tables/26Tables/html/ES.aspx` and `.../SLST.aspx`; both answer 200 by
**redirecting to OPM's homepage** (`final_url: https://www.opm.gov/`, 63,890
bytes, one identical digest for both). Those two fetches were deleted rather
than kept: a 200 is not a table. OPM's own 2026 index page links the
executive-and-senior-level tables under `26Tables/exec/html/`, and those are
what is committed. The GS PDF at `26Tables/pdf/GS.pdf` answers 200 by
redirecting to `salary-tables/pdf/2026/GS.pdf`; it was re-fetched at that
address so the record cites the URL that served the bytes, and
`gs_pay._load_fixture` refuses any fixture whose `final_url` is not its `url`.

**No pay-adjustment Executive Order or OPM memo is linked from either 2026
index page** (general-schedule and executive-senior-level, read 2026-09-21);
the only related link is the generic "Compensation Policy Memoranda" index.
Nothing was fetched for that item.

**Why the GS record cites the PDF and not the page.** The HTML table prints
bare integers (`22584`) and the page says "dollars" nowhere; the XML prints
`<Annual>22584</Annual>`. The PDF prints `$  22,584` on grade 1 -- and only on
grade 1; every row beneath is bare (`   25,393`), the ordinary typesetting of a
column marked once at its head. `financial_evidence._prints_whole_dollars` can
therefore vouch for grade 1 and for nothing else, so a fourth, narrowest scale
rule was added for exactly this shape (`COLUMN_HEAD_MARK_SOURCE_TYPES`,
`unitsEvidenceKind: currency_mark_on_the_columns_first_figure`): the record
quotes the column's first figure with its mark and its own bare figure, the
validator checks that shape, `gs_pay` guarantees the two sit in one column, and
the release gate mirrors all fifteen (step 1, step 10) pairs and recomputes
both digests. `load_general_schedule` refuses to return a table unless the PDF
and the HTML agree on the table number, the effective heading and every one of
the 150 step figures.

The SES and SL/ST pages print every bound with its mark (`$151,661`,
`$228,000`), so their records rest on the existing rule. Both pages carry the
same pay-freeze footnote the EX table carries, verbatim, and it rides on every
record. The two tables print identical figures; the SL/ST table is committed
and cited separately because a SL post's range must cite the SL/ST document,
and `parse_pay_structure_table` refuses to read either page as the other.

**What is published from them.** A RANGE, never a rate: a GS grade's step 1 to
step 10 (base pay, before the locality adjustment the table does not state --
the block says so in words and the gate requires it), or a pay system's
minimum and maximum, both rows. Where the archive itself prints a rate for a
post, that rate wins and no range is written (46 ES listings). On the
2026-09-21 evidence: 45 records -- 1 GS-15, 43 SES, 1 SL -- of which 32 reach
the published graph, the other 13 standing for several posts (`×N` names) and
refused by the multi-post rule like every other pay field.

## The Executive Schedule table (2026-09-11)

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
