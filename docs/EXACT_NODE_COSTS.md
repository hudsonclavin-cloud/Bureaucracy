# Costs identified for the node itself

Written 2026-09-09, after an external review of this project recommended that
a node should carry a cost only when an authoritative record identifies that
exact node — no parent splitting, no employee weighting, no subtree
allocation. This note records what is true of the graph today, which of that
review's specific findings survive a check against this branch, and what the
achievable route to more exact-node costs actually is.

## Where the graph stands

Printed by `python scripts/validate_published_graph.py` on every run, which
is the copy to trust; restated here as of 2026-09-23:

    cost identified for the node itself:  170 of 5,510 nodes (3.1%)
    a share of an ancestor's total:       693 nodes
    no figure at all:                   4,657 nodes (4,591 of them posts)
    the measured nodes cover 99.0% of the anchor, counting each only once

Those numbers are the whole picture and they point in opposite directions.
**2.9% of nodes** carry a figure a record names for them: the root's Treasury
anchor, and the 159 Monthly Treasury Statement Table 5 lines applied to the
nodes they name (29 of which are the receipts lines the exporter carries
explicitly). But those nodes account for **99.0% of the money**. The apportioned figures are a subdivision of measured totals, not
invented money — every one of them is some measured ancestor's dollars split
among its children.

That does not make a subdivision a measurement, and **since 2026-09-09 the
site does not show one by default.** The owner's decision, and the right
one: a number nobody measured must not be the first thing a reader sees. A
node with no measured cost of its own shows no figure at all and says why;
ticking **"Also show estimated shares of a parent's total"** opts back in to
the estimate, still labelled `cost_status: allocated`,
`cost_validation: estimated_from_parent` and `costVerificationStatus:
unverified`. The estimates remain in `graph.json` — the cascade's arithmetic
and the gate's child-sum checks are built on them — so a consumer of the
JSON must read `cost_status` and not `resolved_total_amount` alone.

**"The costs have been disappearing" (2026-10-05) — they have not.** The owner
reported that the costs of all nodes had been vanishing. Checked against every
published graph since 2026-09-23 rather than argued: each one carries the same
**159** measured lines, the same **693** apportioned shares and the same
**4,657** nodes with no figure (the 693 was 655 before the 39 units of
2026-09-23 landed, and 637 before the 15 Treasury units of 2026-09-19). What
changed is nothing in the data; what a visitor sees is the default view
described in the paragraph above, which withholds every one of the 693 until
the box is ticked — and the tick is remembered per browser in `localStorage`,
so a new browser, a private window or cleared site data shows the withheld
view again. The default stands, because it is the owner's own decision and a
number nobody measured still must not be the first thing a reader sees; what
moved is that the opt-in is now one click away inside the cost block itself
(a "Show the estimate" button beside the sentence saying the figure is
withheld, wired to the same checkbox), and `docs/COST_COVERAGE.md`, generated
by `scripts/report_cost_coverage.py`, puts every one of the 5,510 nodes in
exactly one class — measured, estimate, salary, unpriced post by reason, or
no figure with its reason — with the document route that would move each.

The one exception is a real salary. **1,196** position nodes carry a pay claim an
official source states (1,193 before the Code title scan's three rows of
2026-10-06 — the FDA Commissioner, the NOAA Administrator and the Archivist —
1,158 before the twelfth batch's later clusters of
2026-10-06, which priced the uniformed services' principals from Schedule 8 of
the pay-adjustment order — twelve months of a printed monthly rate, arithmetic
no document prints — the Defense Comptroller, the IRS Chief Counsel, four
Transportation posts, the Architect of the Capitol, the Chief of the Capitol
Police, the GAO's General Counsel, the NNSA Administrator, the Sentencing
Commission's Chair and the two magistrate benches; 1,111 before the twelfth batch of 2026-10-05: its
current-export rules — a sub-organisation named for the post, and the White
House rank fold — took the export's listings from 170 to 255 and its printed
rates from 88 to 128, and its fifteen reviewed Schedule rows and four
tier-reference rows priced nineteen more posts from the Code) — 461 the offices Members of Congress hold (every
committee's chair and ranking member in both chambers, the whips, the
conference and caucus chairs), priced since 2026-09-30 by the owner's decision
at Schedule 6's SEAT rate for their chamber ($174,000), because Schedule 6
prints a separate rate only for the Vice President, the Speaker, each
chamber's leaders and the President pro tempore and none for those offices;
the panel leads with "priced as a Member's seat, not for the office", and the
two joint-committee posts are refused because which chamber their holder sits
in is a fact about a person this project never reads — 188 from the White House Office roster (22 of them
titles the roster lists N times at one rate, published for each holder), 237
from the Executive Schedule as 5 U.S.C. §§5312–5316 sets it (98 of them through
a reviewed identification a second statute backs, each resting on three
documents; nine of those are benches — the FCC's, FTC's, CFTC's, FERC's,
NRC's, FMC's, CPSC's and SEC's `Commissioner (×4)` and the Fed's `Governor (×4
members)` — and, since 2026-09-30, 40 as reviewed members of a COUNTED class
the Code places without naming, "Assistant Attorneys General (11)" and seven
more, on the Code, the table and, where one has been read, the statute that
composes the class —
priced from the Code's own "Members, …" class title for each holder alike), 128
the rate OPM's current PLUM export prints for the one row under the title (88
until the office-named-for-the-post rule and the rank fold of 2026-10-05), 47 a
rate a statute sets by REFERENCE to an Executive Schedule level the post is not
itself placed at (`positionTierReferencePay`, 45 until the Code title scan's
NOAA Administrator at 15 U.S.C. 1503b and Archivist at 44 U.S.C. 2103(b) landed
later on 2026-10-06: the Comptroller General and the
Deputy at 31 U.S.C. 703(f)'s levels II and III, the GPO's Director and Deputy
at 44 U.S.C. 303's levels II and III, the IES Director at 20 U.S.C. 9514's
Level II and its three Commissioners at 9517's Level IV, the FCA Board's
Chairman at 12 U.S.C. 2242(d)'s Level III, the Librarian of Congress at 2
U.S.C. 136a–2's Level II, since 2026-10-05 the U.S. Agency for Global Media's
Chief Executive Officer at 22 U.S.C. 6203(b)(3)'s Level III and the Election
Assistance Commission's and Federal Election Commission's chairs and vice
chairs at 52 U.S.C. 20923(d)(1)'s and 30106(a)(4)'s Level IV — each a stamped
`Director / Administrator / Chair` or `Deputy Director / Vice Chair` title
priced only because the same section says which office stands under it, read
from GPO's 2024-edition rendering on govinfo, since 2026-10-06 the Architect
of the Capitol at 2 U.S.C. 1802's Level II, the Chief of the Capitol Police at
2 U.S.C. 1902's Level II, the GAO's General Counsel at 31 U.S.C. 731(c)'s
Level IV and the NNSA Administrator at 42 U.S.C. 7132(c)'s Level III — and 27
Inspectors General of the establishments 5 U.S.C. 401(1) lists at Level III
plus the Act's 3 percent — $215,888, arithmetic the block carries in the open
and no document prints; 23 of the 27 published, the other four displaced by a
listed level the current export supplied on 2026-10-05), 22 twelve months of
the uniformed services' MONTHLY basic pay (`positionMilitaryPay`, since
2026-10-06: Schedule 8 of the pay-adjustment order, found in the committed
note to 5 U.S.C. 5332, joined to the Title 10 or 14 section fixing the
post's grade — 17 posts — or naming the post in its own footnote — 5 senior
enlisted advisers — the annual figure arithmetic no document prints), 72 a
Title 38 tier BAND rather than a rate, 68 from a
listing's level joined to OPM's table (31 before the current export's rules of
2026-10-05), 27 statutory at a row naming the office
or tier (uscourts.gov, senate.gov, Schedule 6 and, since 2026-10-05, Schedule 7's
"Judges of the Court of International Trade" for the CIT's chief judge and its
bench of eight — the one judicial tier uscourts.gov's own table does not print),
22 a base-pay RANGE (18 until the current export supplied more listed pay
plans on 2026-10-05), and
**18 a figure no single document states** (four Article I chief judges and,
since the multi-post rule became per field on 2026-09-23, their four benches —
`Judge (×18)` among them, because "Each judge shall receive salary at the same
rate" is the bench's fact and not one holder's — and, since 2026-09-28, the
Director of the Administrative Office of the U.S. Courts, paid by 28 U.S.C.
603 as a district judge, and the Director of the Federal Judicial Center,
paid by 28 U.S.C. 626 what the AO's Director is paid: a chain of two statutes
and the table, three documents, none stating the figure; and, since
2026-09-30, two bankruptcy benches — the Southern District of New York's
`Bankruptcy Judge (×12)` and the standard district structure's — at 28 U.S.C.
153(a)'s "92 percent of the salary of a judge of the district court",
$249,900 × 92% = $229,908, arithmetic the block carries in the open and no
document prints; the magistrate judges are refused because 28 U.S.C. 634(a)
sets "up to" that percentage, a ceiling the Judicial Conference fixes a figure
beneath; and, since 2026-10-05 by the owner's decision, a percentage of a
JOIN — the Tax Court's `Special Trial Judge (×multiple)` at 26 U.S.C.
7443A(d)'s 90 percent of a Tax Court judge's rate, itself 7443(c)(1)'s parity
to a district judge's, $249,900 × 90% = $224,910 for each; and the Deputy
Directors of the Administrative Office and the Federal Judicial Center at 28
U.S.C. 603's 92 percent of a Director paid as a district judge, $229,908,
the FJC's through §626 — three documents each for the chains, none stating the
figure, 7443A read from GPO's 2024-edition rendering on govinfo because the
OLRC's host was under maintenance). A node may carry
more than one, so the per-source figures sum past 1,196 (the President's $400,000,
stated by 3 U.S.C. 102 itself since 2026-10-05, among them). Each shows in place of
the withheld estimate, under its
own heading rather than COST, with the panel saying it is compensation for one
post — or, on a node standing for several, for each of its holders — and not
what the unit costs. An incumbency-shaped claim (a listing, a row of the
current export, one office's archived level) is still never published on a
node standing for several posts, and a bench whose name bundles senior judges
is refused because 28 U.S.C. 371(b)(2) sets an uncertified senior judge's salary
by reference to a past year, adjusted under §461 — not necessarily the tier's
current rate.

Those last eight — four chief judges and their four benches — are a claim
shape nothing else here makes, and they are labelled as one. A statutory parity provision — 26 U.S.C. 7443(c)(1),
28 U.S.C. 172(b), 10 U.S.C. 942(d), 38 U.S.C. 7253(e) — states which tier of
Article III judge an Article I court's judges are paid at, and the Judicial
Compensation table states what that tier pays; the figure is the join, and
neither document prints it. So the block publishes **how many documents verify
it and what that count is worth on this project's own source arithmetic** (two
official documents, 80%, the same scale `verify_node_sources` uses), beside an
explicit count of how many of them state the figure: **none.** The one block
that counts three is the other way round: a post priced through a reviewed
identification (24 posts and benches, from the Fed's Chair to the FEMA
Administrator; `statutory_schedule.REVIEWED_TITLE_ROWS` is the list)
names the statute that says which office it is, the
Executive Schedule section that sets that office's level and OPM's table, and
exactly one of the three states the figure. A percentage
read as a probability that the number is right would be a lie, and that pairing
is what stops it being read that way. The Court of International Trade is not
among them: 28 U.S.C. 252 states no parity, only a chain through the Federal
Salary Act of 1967, so no derivation reaches its chief judge. Since 2026-10-05
that post and the court's `Judge (×8)` bench are priced instead from a document
that states the figure outright — Schedule 7 of the annual pay-adjustment order,
as 5 U.S.C. 5332's note prints it, whose row "Judges of the Court of
International Trade" reads 249,900 — a single-document statutory claim and not
a derivation.

Both coverage figures are printed by `scripts/validate_published_graph.py`
on every run, so "853 nodes with a cost" can never be read as 853 known
costs.

## The review's findings, checked against this branch

The review was run against a different, older checkout (it reports 164 nodes
in one place and 6,486 in another; this graph has 5,402, and it names files
this branch does not contain). Each specific defect was tested here:

| Claim | Checked | Result |
|---|---|---|
| $463.2M of Comptroller of the Currency outlays published on a node typed Position | every node with `cost_status: official` | **Not true here.** 0 of the 134 measured nodes is a position; OCC's $313.0M sits on the Bureau node. `apply_treasury_outlay_rows` has excluded position, committee, role and caucus types from name matching. |
| Row-level provenance discarded; the crawler keeps only name, amount, date, dataset URL | `data_pipeline/crawler/treasury_outlays.py` | **Not true here.** It keeps `classification_id`, `parent_id` and `line_code`, which is what the section-netting build is made of. |
| USAspending reads `agency_total_obligated_amount`, a field the live schema no longer has | `data_pipeline/crawler/usaspending.py` | **Not true here.** It reads `obligated_amount` and `budget_authority_amount`. |
| Name matching lives in `data_pipeline/processors/enrichment.py` | the tree | **No such file.** |
| The published total uses 2026-02-28 data while Treasury has 2026-07-31 | the root's `__budgetSummary` | **Not true here.** The anchor is FYTD net outlays through 2026-07-31. |
| Verification is circular: a rollup becomes official, which generates a source count the validator then accepts | all 134 measured nodes | **Not true here.** Every one carries a `fiscaldata.treasury.gov` URL and its source rows; the gate requires the URL, after a real bug that stripped it from 26 nodes. |
| The government-wide total is "incorrectly attached to the Constitution" | by design | The root anchor is the one figure the whole cascade hangs on, labelled `root_total` with its period. Not a defect, though it is correctly *not* a claim about a document. |
| Costs, budgets, obligations and outlays are treated as one number | the panel | Partly fair. The published figure is net outlays and says so; the curated `budget` note is shown separately and labelled hand-compiled. There is no obligations or budget-authority figure on any node. |

**One finding is fair and is now fixed.** Nothing in the release gate forbade
a measured cost on a position, committee, role or caucus — only the exporter's
own matching prevented it, and a re-fed payload or a future change could have
reintroduced exactly the error the review described. The gate now refuses it,
pinned in both directions.

The review's *direction* and its source list are right, and the rest of this
note is built on them.

## What each number actually is

The single most useful correction the review makes is that "cost" is four
different measurements, and the graph should never let them stand in for one
another.

| Question | Source | What it is |
|---|---|---|
| What did this entity cost? | Agency AFR/PAR Statement of Net Cost; Treasury's government-wide Statement of Net Cost | Audited, accrual basis. The best answer, and the only *audited* one. |
| What cash went out? | Treasury MTS Table 5 (what this graph publishes); USAspending File A/B | Net outlays for a period. Not cost. |
| What was committed? | USAspending | Obligations. Not spending. |
| What was made available? | USAspending; OMB Public Budget Database | Budget authority. A plan, not an outcome. |
| What does this post pay? | OPM salary tables; PLUM's own reported rates | Compensation for one post. Never an organisation's cost. |

The graph publishes the second of these and labels it. The last has just
started: 44 position nodes carry a rate of basic pay the PLUM archive reports,
explicitly not presented as the unit's cost.

## The route to more exact-node costs

In order of evidence value. When this was written each was gated on a fetch
the environment could not make (`fiscaldata.treasury.gov`, `www.opm.gov` and
`federalregister.gov` were all refused at the proxy); since 2026-09-16 the
allowlist is `*.gov` and `*.mil` (`docs/NETWORK_ACCESS.md` §7), and on
2026-09-17 step 1 got its first pass: USAspending's toptier and bureau lists
are committed verbatim under `tests/fixtures/usaspending/` (README there), and
`data/audit/nominations/cost-cost-usaspending.jsonl` proposes 47 File A keys —
22 toptier CGAC codes and 25 Treasury bureau slugs — for the 619 organisations
phase 2 had declined for want of the network, every one citing the fixture it
was read from and carrying the metric `gross_outlays`. Later the same day
step 3 followed: `data_pipeline/verification/usaspending.py` reads the
proposals whose API name and node name reduce to the same canonical key and
publishes the fixture's own figure in a block of its own, `usaspendingOutlays`
— **37 organisations, 17 by toptier code and 20 by Treasury's bureau slug**,
gross and fiscal-year-to-date, beside the cost and never as it (CLAUDE.md,
"USAspending File A, beside the cost"). 9 proposals are held for review by
name and one is refused for printing zero. The measured-cost count was left
unchanged at 136 that day on purpose: a gross year-to-date outlay from a different
system is not the Treasury net line this graph calls a cost, and the gate
refuses the block wherever the two coincide. The other 572 are refused with the
reason on the record, most often that the entity does not report under the
DATA Act at all:

1. **A reviewed identifier crosswalk, before any new source.** The one thing
   that must exist first. `graph_node_id → source_system + source_entity_key +
   parent_key + metric + effective dates`, keyed on stable identifiers — CGAC
   and toptier codes, OMB agency/bureau codes, federal-account codes, full TAS
   components — and versioned in the repository like `official_sites.json`.
   Names may propose a candidate and must never publish a financial fact on
   their own. The graph's existing `TREASURY_ROW_ALIASES` is this crosswalk in
   its weakest form: a name-to-name map with a section check. Every rule it
   already enforces carries over, plus node-type compatibility, which the gate
   now requires.

2. **Treasury MTS, with the row's identity retained per release.** Already
   fetched and already netted against the statement's own identity. What is
   missing is that `classification_id` is not stable between releases, so the
   crosswalk must key on `table_nbr` + `line_code_nbr` + the hierarchy path
   and treat the classification id as period-specific.

3. **USAspending File A/B at TAS level.** Monthly, account-level outlays and
   obligations with program-activity breakdowns. This is the source that could
   take exact-node coverage from bureaus down to offices with their own
   accounts. It must be published as a *separate metric* from the MTS figure,
   never merged into it.

4. **Agency AFR Statements of Net Cost.** Audited, and the only answer to
   "what did this cost" rather than "what cash moved". PDF, one per agency,
   so this is the most labour and the best evidence.

5. **OMB Public Budget Database** for budget authority, again as its own
   metric.

## Every Treasury section total, and why it does or does not reach a node

Worked through on 2026-09-09 against the committed 2026-07-31 statement
(`tests/fixtures/mts_table5_latest.json`). Table 5 prints 78 `Total--`
section lines. 41 reach a node; the other 37 are accounted for here, so
nobody has to re-derive this list. **Only one was an alias this pipeline
could add**, and it is now added.

**Added (1).** `Office of Federal Student Aid`, $76.05B → `exec-dept-ed-fsa`,
which the graph calls "Federal Student Aid (FSA)" and was publishing as a
$13.37B share of its parent — a 5.7× correction on a real node. The statement
files the row under the Department of Education and the graph puts the office
there, which is the same-section test. Size is not the test and could not be:
$76.05B exceeds Education's own $52.94B net figure, which is possible only
because the section's receipts are carried explicitly beside it.

**Not organisations — Treasury's own accounts and groupings (17).** Matching
any of these would put a fund's or a category's money on an org-chart box.

    Federal Old-Age and Survivors Insurance Trust Fund   $1,249.20B
    Interest on Treasury Debt Securities (Gross)         $1,169.59B
    Interest on the Public Debt                          $1,169.59B
    Federal Supplementary Medical Insurance Trust Fund     $721.07B
    Federal Hospital Insurance Trust Fund                  $407.64B
    Interest Received by Trust Funds                      -$206.69B
    Federal Disability Insurance Trust Fund                $135.60B
    Employer Share, Employee Retirement                   -$125.57B
    Unemployment Trust Fund                                 $35.70B
    Airport and Airway Trust Fund                           $15.31B
    Other Defense Civil Programs                            $58.41B
    International Assistance Programs                       $17.34B
    Independent Agencies                                     $4.20B

**Budget categories inside a section already measured (5).** Operation and
Maintenance ($275.87B), Military Personnel ($196.64B), Procurement
($143.48B), Research, Development, Test and Evaluation ($130.05B) and
Military Construction ($11.71B) are object-class slices of the Department of
Defense, whose section total ($764.71B) is already applied to the DoD node.
Matching them would double-count the same dollars.

**Treasury's intermediate groupings, which are not the units beneath them
(9).** Benefits Programs, Energy Programs, Administration of Foreign
Affairs, International Security Assistance, Departmental Offices, Fish and
Wildlife and Parks, Water and Science, Housing Programs, Land and Minerals
Management. Each covers several curated nodes — "Fish and Wildlife and
Parks" is the Fish and Wildlife Service *and* the National Park Service —
so no one node is the thing the line measures. A name-overlap search
proposes a node for every one of them, which is exactly why names may only
propose.

**Units the graph has no node for (5), which is curation, not pipeline
work.** Administration for Children and Families ($59.94B), Corps of
Engineers ($9.70B), Agency for International Development ($6.33B), General
Services Administration (−$836.7M), Railroad Retirement Board ($3.30B).
These are in `CLAUDE.md`'s known base-graph gaps with proposals in
`CURATION.md`. Adding the nodes would make five more measured costs
reachable, worth roughly **$78B**.

`python scripts/probe_treasury_rows.py --rows tests/fixtures/mts_table5_latest.json`
reproduces the raw lists. It previously reported "0 of 0 fetched" when
handed a verbatim FiscalData response rather than a crawler payload, which
made it look as though there was nothing to find; it now parses either
shape.

## The limit, stated plainly

4,591 of the 5,402 nodes — 85% — are positions. Federal financial systems
report by entity, bureau, Treasury account, program activity and object
class. They do not report by org-chart box or by post. So:

- departments and significant agencies can carry audited net cost;
- many bureaus can carry exact account-level outlays;
- offices can, where they have dedicated accounts;
- divisions, committees, roles and positions mostly cannot, ever, and should
  say so rather than carry a number;
- a position can carry a salary, which is a different claim and is labelled
  as one.

There is no route to an exact cost for every node, and any design that
promises one is promising to invent numbers. The right target is not 100%
coverage; it is that every figure says which of the five things it is, and
every node with no figure says so.
