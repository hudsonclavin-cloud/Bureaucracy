# Costs identified for the node itself

Written 2026-09-09, after an external review of this project recommended that
a node should carry a cost only when an authoritative record identifies that
exact node — no parent splitting, no employee weighting, no subtree
allocation. This note records what is true of the graph today, which of that
review's specific findings survive a check against this branch, and what the
achievable route to more exact-node costs actually is.

## Where the graph stands

    cost identified for the node itself:  135 of 5,195 nodes (2.6%)
    a share of an ancestor's total:     4,886 nodes
    unavailable:                          174 nodes
    the measured nodes cover 98.4% of the anchor, counting each only once

Those two numbers are the whole picture and they point in opposite
directions. **2.6% of nodes** carry a figure a record names for them: the
root's Treasury anchor, and the 134 Monthly Treasury Statement Table 5 lines
applied to the nodes they name (25 of which are the receipts lines the
exporter carries explicitly). But those nodes account for **98.4% of the
money**. The apportioned figures are a subdivision of measured totals, not
invented money — every one of them is some measured ancestor's dollars split
among its children. That does not make a subdivision a measurement, and the
site has never said it did: every one is `cost_status: allocated`,
`cost_validation: estimated_from_parent`, `costVerificationStatus:
unverified`, and badged as an estimate in the panel.

Both figures are printed by `scripts/validate_published_graph.py` on every
run, so "5,021 nodes with a cost" can never be read as 5,021 known costs.

The site now also carries a switch — **"Show only costs identified for the
node itself"** — that blanks every apportioned figure and says why. That is
the view the review asks for, available without deleting the estimates. If
the estimates should go entirely, that is the owner's decision and it is one
line in the exporter; this note is not arguing against it, only recording
that the choice is between two honest presentations rather than between an
honest one and a dishonest one.

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
