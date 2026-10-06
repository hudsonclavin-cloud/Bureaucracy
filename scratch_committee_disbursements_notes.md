# Committee disbursements — notes for the coordinator

Proposed paragraph for CLAUDE.md (under "Cost cascade" or beside the OMB /
net-cost sections), written for the owner's decision of 2026-10-07. Not added to
CLAUDE.md by this branch; the coordinator places it.

---

**What each chamber paid out for a committee's account (since 2026-10-07, the
owner's decision: "committees only, subcommittees will mostly read 'parent
only'").** The graph's 41 committees under the two chambers published only an
apportioned estimate, because no Table 5 line names a committee. The documents
that state committee spending are the chambers' own: the House's quarterly
Statement of Disbursements (2 U.S.C. 104a, www.house.gov) and the Senate's
semiannual Report of the Secretary of the Senate (2 U.S.C. 4108, govinfo.gov).
`data_pipeline/verification/committee_disbursements.py` reads both,
`scripts/derive_committee_disbursements_evidence.py` writes
`data/verification/committee_disbursements_evidence.json`, and the exporter
stamps `committeeDisbursements` on a node typed Committee and nothing else —
never a subcommittee (neither document prints one by name), never a post —
beside the estimate and never in a cost field; it is in
`EVIDENCE_OWNED_FIELDS` and `MINIMAL_GRAPH_FIELDS` and writes no `sourceUrls`
or `verificationMethod`. `financial_evidence.BASES` gained `disbursements`, the
one basis that may sit on a committee (`COMMITTEE_ONLY_BASES`, checked in both
directions: no other basis on a committee, this one on nothing else), realized,
with two source types (`house_statement_of_disbursements`,
`senate_secretary_report`).

**Both documents name staff beside their pay, and no person is read.** The
House's summary CSV (621 KB) has one row per organisation, program and object
class and no person; it is the only House file whose rows are read. Its signed
volume 3 is read for its Statement of Accountability alone, and the Senate's
Part II for each committee's summary block alone (heading, period heading,
ORGANIZATION TOTALS row, unexpended balance); a stream whose bytes lack the
page's marker is never turned into text, and a test asserts no payee line,
document number or object-class line reaches a record. The 26 MB detail CSV,
which names staff, was not fetched.

**Each figure is a sum of totals the chamber prints, listed.** Neither
document prints one total per committee for the period. The House prints an
OFFICE TOTALS line per (organisation, program) — general expenditures and the
intern allowance are two "offices", and Energy and Commerce's minority staff
is a separate organisation suffixed "-MIN"; the Senate prints a summary per
funding resolution (S.Res. 59C/59D of the 118th, 94B/94C of the 119th; the
Ethics Committee by fiscal year). So the block carries every component with
its printed text and `documentsStatingTheFigure` is 0 wherever there is more
than one — the `treasury_header_sum` shape. The Senate prints an expenditure as
a reduction of the account ("-$483,438.47"); a figure printed without the sign
is a net credit and reduces the total (one case: Environment and Public Works,
S.Res. 59D, "$1,253.55").

**Scale.** The Senate's period figures carry the mark and take the ordinary
printed-mark rule. The House's CSV prints bare decimals ("1571274.53", trailing
zeros dropped: "22996") and its volumes print the committees' figures bare;
the one marked figure is the Statement of Accountability's "$ 449,333,548.30",
everything the House disbursed for salaries and expenses in the quarter (the
loader checks it plus the printed deposits equals the printed total funds
disbursed, which is what ties the mark to that line). A sixth scale rule,
granted to the House's statement alone
(`STATEMENT_TOTAL_BOUNDED_SOURCE_TYPES`, kind
`currency_mark_on_the_statements_own_total_bounds_the_column`), uses it to bound
the column from both sides: a record's figure is at most its committee's
largest office total in the same column, that anchor is at most the House's
whole quarter, and the anchor read in thousands would exceed it — so the
column is not in thousands or larger. Every committee's anchor clears it
(smallest, Small Business's general expenditures, about $750,000).

**The Senate report's streams are not in heading order.** A first pass over
the concatenated text of Part II paired each committee's heading with the
NEXT page's totals and produced plausible, wrong figures for every committee;
the heading sits at the end of its own page's stream. The reader pairs only
within one stream, and checks on every page that the unexpended balance equals
available funds plus the year-to-date column.

**Matching, never fuzzy, scoped to one chamber.** `congress.committee_key`
equality, then the existing type-word fold (`evidence.committee_core_key`,
two-token floor), then 14 reviewed rows keyed by node id (8 House, 6 Senate),
each naming every printed label and its basis and re-checked against the
document and the node's name: the one-word Senate labels (BUDGET, FINANCE,
JUDICIARY, INTELLIGENCE, ETHICS) and "SPECIAL COMMITTEE ON AGING", below the
fold's floor; the House's abbreviations (COMM ON SCIENCE SPACE&TECH,
TRANSPORTATION-INFRASTRUCTURE, INTELLIGENCE, HOUSE ADMINISTRATION, SELECT
COMMITTEE COMPETITION US AND CHINA, EDUCATION AND WORKFORCE); the statement
still filing Oversight under its 118th-Congress name ("OVERSIGHT AND
ACCOUNTABILITY"); and Energy and Commerce, whose row claims the majority and
minority organisations together so the name rule cannot publish half the
committee. The gate mirrors the rows by node id and the committee key, both
pinned equal to the module's by a test.

**Measured on the rebuild:** 40 of 41 chamber committees carry a figure. House
21 of 21 (11 by key equality, 2 by the fold, 8 reviewed), 42 office totals,
$45,701,952.54 for April 1 – June 30, 2026, from $772,119.57 (Small Business)
to $5,197,559.86 (Appropriations). Senate 19 of 20 (13 by the fold, 6
reviewed), 50 non-zero resolution totals (25 printed "$.00" and are listed as
zero components, never published as a measurement), $69,106,197.81 for October
1, 2025 – March 31, 2026, from $1,216,038.51 (Indian Affairs) to $6,713,120.65
(Judiciary). No measured cost moved, no estimate moved, and no node other than
the 40 changed (one unrelated pre-existing drift on the CFPB's `sourceTypes`
between the committed graph and the committed evidence).

**Declined, and why:** the Senate Appropriations Committee, funded from
"Salaries, Officers and Employees" in Part I rather than the Inquiries and
Investigations account (Part I not read); the joint committees (the Joint
Economic Committee's account is in Senate Part II and the Joint Committee on
Taxation's in the House CSV, as "JOINT COMMMITTEE ON TAXATION"), outside the
chambers' subtrees this decision covered; the House Ethics Committee and the
Republican Study Committee, which the CSV prints and the graph has no
committee node for; every subcommittee; the House's prior-year committee
organisations ("2025 COMMITTEE ON AGRICULTURE"), which the summary CSV omits
and volume 3 prints only beside named payees — every House block says its
figure is the 2026 organisation's; and the CSV's year-to-date column, whose
period the file does not print.

**Not compared, deliberately.** The 40 estimates these nodes publish sum to
$2.48bn of FYTD net outlays (House $1.61bn, Senate $0.87bn) against $114.8m of
disbursements over a quarter and a half-year. The periods differ and the
disbursements are not the whole of what a committee costs (benefits paid
centrally, the House's earlier-year accounts, hearing-room and support
offices), so nothing here says by how much the estimates are wrong — but the
gap is more than an order of magnitude, and it is the subtree-size apportionment
this file already records as its weakest point. The gate refuses a block equal
to its node's estimate to the cent; whether the cascade should ever weight
committees by these figures is the owner's decision, not taken here.

---

Files: `data_pipeline/verification/committee_disbursements.py`,
`scripts/derive_committee_disbursements_evidence.py`,
`data/verification/committee_disbursements_evidence.json`,
`tests/fixtures/disbursements/` (README there),
`tests/test_committee_disbursements.py`, the `disbursements` basis and the
sixth scale rule in `financial_evidence.py`, the gate check
`committee_disbursement_violations` in `scripts/validate_published_graph.py`,
the panel row and sentence in `js/ui.js` (cache stamp 20261007d), and three
rows in the hand-written `docs/COST_NOMINATION_RUNBOOK.md` (the metric and its
two systems), which `tests/test_nominate.py` requires of every basis.
