# Costs identified for the node itself

Written 2026-09-09, after an external review of this project recommended that
a node should carry a cost only when an authoritative record identifies that
exact node — no parent splitting, no employee weighting, no subtree
allocation. This note records what is true of the graph today, which of that
review's specific findings survive a check against this branch, and what the
achievable route to more exact-node costs actually is.

## Where the graph stands

    cost identified for the node itself:  136 of 5,195 nodes (2.6%)
    a share of an ancestor's total:     4,885 nodes
    unavailable:                          174 nodes
    the measured nodes cover 98.4% of the anchor, counting each only once

Those two numbers are the whole picture and they point in opposite
directions. **2.6% of nodes** carry a figure a record names for them: the
root's Treasury anchor, and the 135 Monthly Treasury Statement Table 5 lines
applied to the nodes they name (25 of which are the receipts lines the
exporter carries explicitly). But those nodes account for **98.4% of the
money**. The apportioned figures are a subdivision of measured totals, not
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

The one exception is a real salary. 44 position nodes carry a rate of basic
pay OPM's PLUM archive reports, and those show it in place of the withheld
estimate, under the heading REPORTED RATE OF BASIC PAY rather than COST,
with the panel saying it is compensation for one post and not what the unit
costs.

Both coverage figures are printed by `scripts/validate_published_graph.py`
on every run, so "5,021 nodes with a cost" can never be read as 5,021 known
costs.

## The review's findings, checked against this branch

The review was run against a different, older checkout (it reports 164 nodes
in one place and 6,486 in another; this graph has 5,195, and it names files
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

In order of evidence value, and each one gated on a fetch this environment
currently cannot make (see `docs/NETWORK_ACCESS.md` — `fiscaldata.treasury.gov`,
`www.opm.gov` and `federalregister.gov` are all refused by this session's
egress proxy, having worked on 2026-09-08):

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

4,382 of the 5,195 nodes — 84% — are positions. Federal financial systems
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
