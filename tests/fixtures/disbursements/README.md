# The chambers' own reports of what they paid out

Read by `data_pipeline/verification/committee_disbursements.py` and, with a
reader of its own, by `scripts/validate_published_graph.py`. Every file here
was fetched with `scripts/fetch_fixture.py`, is the publisher's own bytes, and
has a `.meta.json` beside it with the URL, the fetch time, the User-Agent, the
robots.txt verdict and the sha256 the loaders recompute before reading. They
are refreshed only by re-fetching, never edited.

**Both reports name staff beside what they were paid.** Nothing here reads a
row about a person into anything: see the module docstring for exactly what is
taken from each document, and `tests/test_committee_disbursements.py` for the
assertion that no payee line reaches a record.

## The House: Statement of Disbursements, April 1 - June 30, 2026

The quarterly report 2 U.S.C. 104a requires, published by the Chief
Administrative Officer on www.house.gov (fetched 2026-10-06).

| File | What it is | Bytes |
|---|---|---|
| `house/2026q2_sod_summary_grid.csv` | "SOD SUMMARY DATA": one row per organisation, program and budget object class, with year-to-date and quarterly amounts. No person in it. The only House file whose rows are read. | 621,267 |
| `house/2026q2_vol3_signed.pdf` | Part 3 of 3 of the GPO-signed volumes (Committees). Read for one page only, the Statement of Accountability: the period as printed, and the one figure the statement prints with a currency mark, "$ 449,333,548.30", which bounds the CSV's scale. A stream is turned into text only if its raw bytes carry a marker of that heading: 7 of the volume's streams do, 6 of them payee pages from which nothing is taken. | 4,016,549 |
| `house/statement-of-disbursements.html` | The landing page, which links the CSV and the volume under "Current Statement of Disbursements of the House (April 1, 2026 to June 30, 2026)". The loader checks both links. | 29,656 |
| `house/glossary-of-terms.html` | The glossary, quoted for its definition of the quarterly column: "Quarterly Amount — This amount lists the total expenditures for the specified quarter". | 66,821 |

Not fetched, and why:

- `SOD DETAIL TRANSACTIONS` (26.2 MB CSV): one row per transaction, with
  payees and staff named. Nothing here needs it, and a file of named staff
  salaries is not committed for a total the summary file prints.
- The single-volume PDF (14.4 MB) and volumes 1 and 2: the committees are in
  volume 3, and the Statement of Accountability is printed in each volume.
- `https://statementofdisbursements.house.gov/`: the proxy refused the tunnel
  (502) on 2026-10-06, recorded in
  `house/statementofdisbursements.house.gov.html.meta.json`.
  `https://disbursements.house.gov/` answers 301 to the www.house.gov page
  above, which is the address used.

**What the summary CSV does not carry**, measured on these bytes: it lists the
2026 organisations only (544 of them; no "2025 ..." or earlier organisation
appears). Volume 3 also prints disbursements the quarter charged to earlier
committee accounts ("2025 COMMITTEE ON AGRICULTURE", "2023 COMMITTEE ON
AGRICULTURE"). Those pages print payees, so they are not read, and every House
record says its figure is the 2026 organisation's. The CSV's quarterly column
sums to $429,979,738.88 against the statement's $449,333,548.30; the
difference is not reconciled here.

## The Senate: Report of the Secretary of the Senate, October 1, 2025 - March 31, 2026

The semiannual report 2 U.S.C. 4108 requires, published by the Government
Publishing Office on www.govinfo.gov (package `GPO-CDOC-119sdoc6`, issued
2026-05-13) and linked from senate.gov (fetched 2026-10-06).

| File | What it is | Bytes |
|---|---|---|
| `senate/GPO-CDOC-119sdoc6-2.pdf` | Part II. Each committee's Expenses of Inquiries and Investigations account appears as one summary block per funding resolution (S.Res. 59C and 59D of the 118th Congress, 94B and 94C of the 119th; the Ethics Committee by fiscal year), each with the column heading "NET EXPENDITURES FOR THE PERIOD OF 10/01/2025 THRU 03/31/2026 ($)" and an ORGANIZATION TOTALS row whose period figure carries its mark ("-$483,438.47"). | 5,192,693 |
| `senate/report_secsen.htm` | senate.gov's page for the report, which links Part II under "October 1, 2025 to March 31, 2026". The loader checks the link. | 36,600 |

Not fetched: Part I (`GPO-CDOC-119sdoc6-1.pdf`, the senators' offices and the
Senate's officers) and the full report. The Senate Appropriations Committee is
funded from "Salaries, Officers and Employees" in Part I, not from the Inquiries
and Investigations account, and is not read; it carries no figure.

**The reader pairs a heading with a totals row only on the same page.** The
report's content streams are not in page order relative to their headings: a
first pass over the whole text, concatenated, paired each committee's heading
with the NEXT resolution's totals and produced plausible, wrong figures. Read
page by page, the unexpended balance printed beneath each totals row equals
the first column plus the third on every page, which the loader checks.
