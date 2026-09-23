# White House Office personnel report

**Fetched 2026-09-14.**

    python scripts/fetch_fixture.py \
      https://www.whitehouse.gov/wp-content/uploads/2026/07/2026-Annual-Report-to-Congress-on-White-House-Staff.pdf \
      whitehouse/staff_report_2026.pdf

`staff_report_2026.pdf` (251,322 bytes, sha256
`549c4b93a121dc5ae9905e1584bed9906dff47099013d72eccf46aabad7f2354`, recorded
verbatim in its `.meta.json`) is the **2026 Annual Report to Congress on White
House Staff**, "As of Date: Wednesday, July 1, 2026". Section 6 of Public Law
103-270 requires the President to send it to Congress each July 1 and requires
it to state, for every White House Office employee and detailee, their title
and their annual rate of pay.

It is the only named-salary disclosure the federal government is required to
publish. Every other pay source in this repository — OPM's Executive Schedule,
the U.S. Courts' judicial compensation table, the Senate's salary schedule —
states a rate for a *rank* or a *tier*.

`robots.txt` on www.whitehouse.gov is `User-agent: * / Disallow:` — an empty
disallow, which permits everything; the fetch recorded that verdict.

**Which edition is current.** `whitehouse.gov/disclosures/` links both the
2026 and the 2025 reports and says in its own text that "the White House has
publicly disclosed its 2026 Annual Report on White House Staff listing the
titles, classifications, and salaries of its personnel, as transmitted to
Congress". The 2026 edition is the one the page presents as current and the
one committed here. (The 2025 edition, at the same URL pattern under
`uploads/2025/07/`, is not fetched: nothing reads it, and a second roster
would invite a comparison across administrations that this project makes no
claim about.)

## Read by

`data_pipeline/verification/whitehouse_pay.py`, derived by
`scripts/derive_whitehouse_pay_evidence.py` into
`data/verification/whitehouse_pay_evidence.json`.

**5 of the graph's 27 White House Office position nodes were priced on
2026-09-14**, the first run. The subtree was rebuilt from this roster the same
day (`scripts/expand_whitehouse_office.py`) and now carries 249 positions, 188
of them priced — 22 of those for a title several people hold at one identical
rate. The refusal counts below are the current run's (249 considered); the first run's (27 considered) are given in brackets for the two refusals whose counts it recorded differently, and `title_held_under_several_spellings` did not exist then.

## Read with the standard library, like every other fixture here

This repository parses its fixtures with the standard library alone; the
House Clerk's spreadsheet is read as what it is, a zip of XML
(`congress.read_xlsx_rows`). A PDF yields to the same treatment and no
third-party PDF library was added:

- `%PDF-1.6`, and **no `/Encrypt`** — an encrypted document is refused
  outright rather than having ciphertext read out of it as if it were words;
- all 73 streams are **FlateDecode**, which is `zlib`;
- text sits in ordinary `BT … Tm … TJ` blocks over latin-1 literals.

Two traps this document's own markup sets, both handled and pinned in
`tests/test_whitehouse_pay.py`:

- **Position cannot separate the columns.** Every cell in a data row reports
  the same `Tm` — the row sets the matrix once and advances by intra-stream
  kerning — so an x-sort interleaves the columns differently from row to row.
  The columns are recovered by **shape** instead: the salary matches a money
  pattern, STATUS (`EMPLOYEE`/`DETAILEE`) and PAY BASIS (`Per Annum`) are the
  closed vocabularies the header names, the name matches `LAST, FIRST M.`,
  and the title is what remains. A row not yielding exactly one of each is
  refused: 8 of the 2026 report's rows are, out of 408.
- **Kerning arrays must be joined, not read.** `[(F)-11 (o)1.5 (r)]TJ` is the
  word "For"; the numbers are kerning adjustments and are discarded.

## The NAME column is discarded at parse time

The report carries a living person's name beside their salary.
`parse_staff_report` matches the name cell **only so as to exclude it**, and
never returns it — rather than carrying it and declining to print it, so that
no later change can start publishing it by accident. Three separate checks
pin this: the record builder's output carries no surname, the published
`output/graph.json` carries none, and the release gate refuses any field of a
published record whose text looks like `LAST, FIRST` in the report's own
all-caps form.

## What is refused, and why

| Refusal | Count | Why |
|---|---|---|
| `no_row_carries_this_title` | 21 | The graph's 27-node White House Office is a sketch of a 400-person office; `Chief Speechwriter` and `Director of Presidential Personnel` are simply not titles the report prints. This is curation, not parsing. |
| `reported_rate_is_zero` | 7 (1 on 2026-09-14) | Ten of the 408 rows read **$0.00** — uncompensated appointees, the National Security Advisor among them. Zero is never published as an amount here, and an uncompensated arrangement is a fact about one person, not about the post. |
| `title_held_by_several_people_at_different_rates` | 32 | `SENIOR POLICY ADVISOR` appears 21 times and `STAFF ASSISTANT` 15, at differing salaries. Two salaries under one title make the figure undecidable, and this project does not resolve an ambiguity by picking one. Named `title_held_by_several_people` (0 on 2026-09-14) until 2026-09-23. Since then a title the report lists for every holder at one identical rate (23 of its 58 multi-holder titles) is no longer refused on that ground, and 22 published records carry that rate for each holder (`holders`). |
| `title_held_under_several_spellings` | 1 | Two printed titles fold onto one key; the record takes one printed title or nothing. |
| `stands_for_several_posts` | — | The same rule `pay_tables.py` and `judicial_pay.py` enforce. |

## The rank prefix, folded — leading only, never contained

The report spells a post with its White House commissioning rank in front:
`ASSISTANT TO THE PRESIDENT AND CHIEF OF STAFF` for the node this graph calls
`Chief of Staff`. `title_core` folds those three ranks off the **front** and
then requires the remainder to equal the node's name exactly — the same move
`positions.archive_title_keys` makes for the PLUM archive.

A containment test would be actively wrong on this document, and the examples
are not hypothetical:

- `Press Secretary` is contained in `ASSISTANT PRESS SECRETARY` and in
  `SPECIAL ASSISTANT TO THE PRESIDENT AND DEPUTY PRESS SECRETARY`;
- the only report title containing `Director of Legislative Affairs` is the
  **Deputy** Director's;
- the only one containing `Social Secretary` is the **Deputy** Social
  Secretary's.

Each would price a principal from a deputy's salary — the same failure the
existence verifier already documents, "Office of Science" matching inside
"Office of Science and Technology Policy".

## What the claim is, and is not

The report is person-level by statute. So a record here never says a post
*pays* a figure. It says:

> the one person the report lists under this title is paid $X, as of
> July 1, 2026.

Every record is `scopeMatch: "proxy"`, `financial_evidence.classify` grades
all 188 `partial`, and none is `verified`. The field is `positionReportedPay` —
a third field beside `positionPayRate` (a rank joined to a rate) and
`positionStatutoryPay` (a statute's figure for an office), because it is a
third claim shape and the release gate checks each against its own source's
rules.

Basic pay is not the node's cost and is never written to a cost field; it is
also not evidence that the post exists as the graph draws it, so the module
writes no `sourceUrls`, `sourceTypes`, `lastVerified` or `verificationMethod`.

## The gate mirror

`whitehouse_roster()` in `scripts/validate_published_graph.py` re-reads the
committed report with a second, independent stdlib extraction (digest
checked) and maps each title it prints to the rate and the number of people
listed under it, and the gate checks the claimed title and amount against
that. The first five records were mirrored as a literal keyed by **id**
(`WHITEHOUSE_REPORTED_PAY`, since removed), because **four of the five priced
posts are paid the identical $195,200**, so a record moved from one to another
would keep a correct figure, a correct quote and a correct pay basis. The
roster check closes the same hole another way: the claimed title must name
this node, by equality or with the rank folded off — the same lesson the
three equally-paid Senate leadership roles taught.
