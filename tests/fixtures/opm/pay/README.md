# OPM pay tables

Empty of data, on purpose.

1,596 rows of the PLUM archive are Executive Schedule positions carrying a
level (I–V) rather than a rate of pay, and 30 of the graph's matched positions
are among them. OPM's Salary Table No. 2026-EX turns each level into the
statutory rate of basic pay, which would give those positions a figure from an
official source instead of nothing.

**It could not be fetched from this environment.** `www.opm.gov` is refused by
the session's egress proxy with a 403 on the CONNECT, as recorded verbatim in
`executive_schedule_2026.html.meta.json`. The same session refuses
`www.federalregister.gov` and `api.federalregister.gov` — the Executive Order
adjusting the rates would have been a second, independent route to the same
numbers — along with `www.senate.gov` and `fiscaldata.treasury.gov`, all four
of which were fetched successfully on 2026-09-08. See `docs/NETWORK_ACCESS.md`.

Nothing was typed in from memory or from a screenshot in place of the fetch.
Five numbers are easy to transcribe and impossible to audit: a hand-entered
table under an `opm.gov` URL would read on the site exactly like a fetched one,
which is the failure this repository keeps finding in its own history. The
positions therefore publish the level the archive gives them and no rate, and
the panel says the archive gives the rank, not a rate of pay.

To finish this, from a network that allows `www.opm.gov`:

    python scripts/fetch_fixture.py \
      https://www.opm.gov/policy-data-oversight/pay-leave/salaries-wages/salary-tables/26Tables/exec/html/EX.aspx \
      opm/pay/executive_schedule_2026.html

That writes the page and its `.meta.json` (status, sha256, robots verdict).
The parser and the level-to-rate matcher are deliberately **not** written yet:
writing them against a page nobody here has seen would be guessing at its
markup, and a parser fitted to a guess is how a validator comes to run happily
and be wrong. Write them against the fetched file.

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
