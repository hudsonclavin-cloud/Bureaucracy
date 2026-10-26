# What "done" means for Bureaucracy

Decided by the owner on 2026-10-21, in two rounds of multiple-choice questions.
Every "today" figure below was last re-measured on 2026-10-25 on the published
graph (`output/graph.json`, 5,512 nodes); the criteria sections keep the day each
figure was first taken where the history matters by `scripts/validate_published_graph.py`,
`scripts/report_cost_coverage.py`, `scripts/report_unpriced_positions.py`,
`scripts/report_evidence_coverage.py` (criterion 3, since 2026-10-22) and
`python scripts/nominate.py status --kind source`. Re-measure them with those
commands; do not restate them by hand.

"Done" has two halves and needs both:

1. **Complete** — every node meets the money, pay, evidence and structure
   criteria below, and the site gives a reader what the reader criteria ask.
2. **Self-sustaining** — the site keeps itself current without a person
   running it, and holds anything it cannot settle for review.

Done is not frozen. The government reorganises, pay tables change every
January and the Treasury prints a new statement every month, so done is a
level the project is kept at, not a date it reaches once.

---

## Part 1 — Complete

### 1. Money: sourced, no bare estimates

**Decision.** Every organisation shows a figure a document states, or says in
words why none exists. No organisation is left with only an apportioned
estimate.

**Done when** the cost-coverage class "Estimate — no sourced figure of any kind"
is **0**, and every other organisation is in one of these states:

- measured (a Treasury line names it);
- a sourced figure of another kind is shown, labelled by basis and period
  (File A, OMB, audited net cost, a chamber's disbursements, a Combined
  Statement account);
- an explained blank: a negative Treasury pool, a replaced unit, or a new
  terminal state, "no published document states this unit's money", which
  must name the documents checked.

Subcommittees may read "funded through its committee": the owner's decision
of 2026-10-07 already says neither chamber's document prints them.

Since 2026-10-22 the explained blank is `costNoDocument`
(`data_pipeline/verification/cost_no_document.py`, CURATION.md §24): every
organisation left with only an estimate names the seven money documents this
project holds, each with its version and digest, and says whether any prints
a row carrying the unit's name. `scripts/report_cost_coverage.py` prints the
remaining bare count as one number ("bare estimates — … criterion 1 gap"),
and the gate's "explained blanks" line counts the same set.

| measure | today |
|---|---|
| measured cost | 173 nodes (98.9% of the anchor) |
| estimate beside a sourced figure | 83 |
| committee/subcommittee estimate | 240 (40 committees carry disbursements) |
| explained blank (`costNoDocument`) | 359: 341 no held document names the unit, 18 named in one without a licensed figure |
| **bare estimate — the gap** | **0** |

**Route.**
- The Combined Statement reviewed table (in progress; CURATION.md §22.6–22.7)
  and its other chapters.
- OMB bureau rows for nodes whose name the file carries.
- USAspending File B by Treasury Account Symbol (not yet fetched).
- Agency Financial Reports.

The largest groups in the gap are divisions (115), regional offices (35),
bureaus (32), museums (24), Defense agencies (22) and national laboratories
(17).

**Hidden assumption to test early.** That a document prints money for most of
these 373. Many divisions, regional offices and laboratories are likely funded
from their parent's accounts with no separate line [Likely]. If so, most of
the 373 end in the explained-blank state, not with a figure. That still meets
this criterion, but only if the explanation lists what was checked.

### 2. Pay: every post priced or explained

**Decision.** Every position carries a pay claim an official document supports,
or a stated reason no such figure exists.

**Done when** `docs/UNPRICED_POSITIONS.md` has **0** in `unreached`,
`multiplicity`, `listed_no_rate` and `beneath_replaced_unit`. Every post is
priced, or carries a terminal reason the way the 112 contractor-laboratory
posts carry `not_federally_paid`.

| measure | today |
|---|---|
| positions | 4,591 |
| priced | 1,258 (27.4%) |
| explained (not on a federal pay schedule) | 112 |
| no document names the title | 2,158 |
| stands for several holders | 611 |
| paused beneath a replaced VA network | 432 |
| listed with no rate | 20 |
| carrying `payNoDocument`, the explained blank (2026-10-22) | 3,221 — 2,558 whose title none of the six held title-listing pay documents prints, 663 whose title one prints under a filing no rule ties to the post |

**Measured on 2026-10-22, and what it is not.** Every one of the 3,221 now
carries `payNoDocument` (`pay_no_document.py`, CURATION.md §25): the six
title-listing pay documents this project holds, each with version and digest,
and whether any prints the title. That is criterion 1's "explained blank"
applied to posts, and it is deliberately NOT counted as a terminal reason here:
the gap by this criterion's own test stays **3,221**, because "six documents
were read and none prints the title" is a fact about this repository's
holdings, not a document establishing that no figure exists. The measurement
sharpens the counterargument below: 1,624 of the 2,158 `unreached` titles
appear in no held document at all, and most are curated templates.

**Route.**
- Research packs 3–5.
- The VA re-homing, which waits on a VA document mapping medical centres to
  the five current networks.
- New terminal reasons where a document establishes them, for example "pay
  set administratively by the agency; no published table" or "uncompensated
  by statute".

A terminal reason needs a document exactly as a figure does.

**Strongest counterargument.** Thousands of curated posts are templates
(`Chief — Medicine Service` under eighteen medical centres) that no pay document
will ever name. For those, "explained" may in practice mean "this node is a
template, not a post", which is a structure fix, not a pay fix. Expect part of
this gap to close by curation rather than research [Likely].

### 3. Evidence: every unit has at least one official source

**Decision.** Every organisation carries at least one official document
evidencing that it exists. Posts are not held to this bar; a pay claim or a
listing already evidences most priced posts.

**Done when** every current organisation carries a `verificationMethod`, or a
recorded reason no official document can be read for it (for example, a host
that refuses every crawler and no directory lists the unit). Measured by
`scripts/report_evidence_coverage.py`, whose one number is the gap; the
recorded reasons are `verificationUnread` (a queued page went unread) and,
since 2026-10-22, `verificationNoDocument` (no page was queued: the name is the
graph's own count label or grouping, the site is off every .gov host, the only
host refuses the crawler, or the page read does not carry the graph's name —
CURATION.md §23).

| measure | today |
|---|---|
| current organisations | 870 |
| with a verification method | 631 (72.5%) |
| a recorded reason no document can be read (`verificationNoDocument`) | 166 |
| **neither — the gap** | **40** |
| organisations with no candidate page | 358 (of 890 incl. replaced/lines) |
| queued page unreadable, no other method | 72 (42 hosts refuse the crawler) |
| placement evidenced | 405 of 918 edges (44.1%) |

**Route.**
- Phase 1b nominations.
- The Government Manual, Federal Register directory, committee lists and
  current Plum export, for units a web page cannot reach.
- `docs/NETWORK_ACCESS.md` for walled hosts.

Placement is not part of this criterion. It is tracked, and criterion 4 uses it.

### 4. Structure: match the government's own lists, then go beyond them

**Decision (the owner's words).** "Should match the government own lists but
should also go beyond it, if the money does not match then find where it
goes."

**Done when** both of the following hold.

**(a) The lists are reconciled.** Every unit on these lists is either a node,
or recorded in CURATION.md as deliberately not one (scaffolding, a grouping,
out of scope):

- the Government Manual's entries;
- the Federal Register agency directory;
- USAspending's toptier agencies;
- the House Clerk's and the Senate's committee lists;
- the current Plum Book's agencies.

Every curated name a complete list does not carry is resolved: renamed,
superseded, or kept with the reason. Today the Senate list lacks 8 curated
names and the House Clerk's lacks 9. Beyond the lists, the graph may carry
units no list names (offices, posts, regional structure) when a document
supports them.

**Measured on 2026-10-22** (`scripts/report_list_reconciliation.py` →
`docs/LIST_RECONCILIATION.md`, CURATION.md §26): `data/curation/
list_dispositions.json` disposes of every one of the 403 entries that reach no
node across the five lists (44 Manual, 270 directory, 20 toptier, 8 Senate, 7
House, 54 Plum) and of all 21 curated committee names the two complete lists
lack (11 Senate, 10 House), each row re-adjudicated against the committed list
on every run. **Gap: 19 on 2026-10-22, 5 since 2026-10-26** (14 of the 16 units were added; CURATION.md §32.1) = 3 entries left unsure + 16 distinct real units the
lists name and the graph has not added + 0 curated names unresolved. The
sixteen are counted on purpose: a unit recorded as "not added, here is the
route" is neither a node nor deliberately not one. Eight of them need a
toptier-reporter licence for `add_curated_nodes.py`, six a page fetch, two a
decision (the Bureau of Indian Education, Amtrak).

**(b) The money is reconciled.** For every unit with a measured total, the
panel shows:

    parent = measured children + sourced figures + named remainder

The remainder is traced to the documents that explain it: Combined Statement
accounts, receipts lines, or Treasury groupings with no node. What cannot be
traced is labelled "not attributed", with the amount. No remainder is silently
spread across siblings as though it were their money. That is the failure
`CLAUDE.md` records for Interest on the Public Debt, which once made the
Alcohol and Tobacco Tax and Trade Bureau (TTB) look larger than the IRS.

**Route.** The Combined Statement probe and reviewed table already reconcile
the Legislative Branch to the cent (§22.6). The same check, per chapter, is
the engine for (b).

**Measured on 2026-10-22** (`treasury_sum`, CURATION.md §27): every one of
the 57 measured units whose Table 5 header has parts now carries the
statement's own parts beneath it, each landed on the node that carries it or
marked as reaching no node, and **not attributed is zero on all 57** — the
statement's arithmetic closes to the cent. The panel shows the sum. What the
measurement exposes rather than fixes: $2.88tn printed beneath 22 units under
programme and object-class headings no node carries is divided among their
estimated children by weight (the SSA's $1.65tn, Defense's $835bn, the VA's
$58.5bn), and the panel now names each part and each child that takes it,
saying it is an apportionment. Whether to stop that division rather than show
it is the owner's call; the estimates are withheld by default either way.

---

## Part 2 — What the reader gets

All four were chosen.

| criterion | done when | today |
|---|---|---|
| **Every figure explains itself** | every figure on the panel and in the directory names its source, period and kind in words | largely met; keep the smoke check asserting it |
| **Totals add up visibly** | a measured unit's panel shows the sum in criterion 4(b): what each child contributes, what is estimated, what is not attributed | built 2026-10-22: `treasury_sum` on 57 measured units, the panel's "How the total adds up" block (CURATION.md §27) |
| **Change history** | a reader can see what changed since the last update: figures that moved, nodes added or replaced, claims withdrawn, and why | built 2026-10-22: `output/change_history.json` from `scripts/build_change_history.py`, the "What changed" card and the panel's per-node lines (CURATION.md §29) |
| **Export / download** | a reader can download the graph and a flat CSV of nodes and figures, with the sources, from the site | built 2026-10-22: `output/nodes.csv` (`scripts/export_flat_csv.py`, 52 columns) and the "Download" card offering it, both graph copies, the change history and the registry (CURATION.md §31) |

---

## Part 3 — Self-sustaining

### 5. Updating on its own: fully automatic when every check passes

**Decision.** A scheduled job fetches new source documents, rebuilds, runs every
check, and **publishes by itself when all checks pass**. A person hears only
about failures and held changes.

**Done when** the job has run on its schedule for **three consecutive monthly
cycles** with no manual step and no bad publish.

**Today.** **Built 2026-10-22:** `scripts/update_cycle.py` runs the six steps
below (`--plan`, `--hold`, `--offline`; `--publish` refused until three clean held
cycles are recorded in `data/audit/update_cycles.json`), with a per-source
`contentCheck` for step 2 and `build_change_history.py` for step 5;
`.github/workflows/update_cycle.yml` runs it in hold mode on the 16th of each
month and on demand and opens a pull request, which a person merges to publish.
Two cycles have run on GitHub's runner, both started by hand (CURATION.md
§30.5, §30.6): the first exposed two defects in this repository's own work, the
second came out clean. Neither counts. Each cycle records what started it
(`trigger`), and the clean streak counts only cycles the SCHEDULE started, so
the three-cycle count starts when the workflow first fires on the 16th
(2026-11-16 is the first), and a person's dispatch neither adds to it nor
breaks it. The reading of "three consecutive monthly cycles" used is the
strict-but-cheaper one: three scheduled hold-mode cycles before the owner's
switch to `--publish`; whether it means three more after the switch is the
owner's to settle (CURATION.md §30.7). `data_pipeline/scheduler/nightly_update.py` is
still not invoked.

**What the job does, in order:**

1. Fetch each due source with `scripts/fetch_fixture.py` (digest and
   `.meta.json` recorded), under the existing robots and User-Agent policy.
2. Refuse a fetch that is not the document. This has happened twice:
   uscode.house.gov served a 200 "Under Maintenance" page, and
   federalregister.gov served a 200 "Request Access" page. Each source needs a
   content check: expected title or heading, minimum size, and the parse
   succeeding.
3. Commit new fixtures, run every derive step, regenerate, and regenerate the
   reports.
4. Run the gate, the full test suite and the browser smoke check.
5. Run a **change budget** before publishing. If the change exceeds the
   budget, it is held, not published. The budget starts as:
   - the node count drops;
   - a measured cost moves by more than its source's month-on-month change
     would explain;
   - more than 5% of pay claims are withdrawn;
   - the anchor's period goes backwards.

   (All thresholds to be tuned on the first cycles.)
6. Publish (push to `main`, which GitHub Pages serves), write the change-history
   entry for Part 2, and notify only on failure or hold.

**Where it runs.** A scheduled GitHub Actions workflow is the natural home
[Likely]: Pages already serves from `main`, and Actions runners are not
behind this sandbox's allowlist. Several hosts refuse automated clients with
an Akamai 403, and may refuse GitHub's runners too [Speculative]. The job
must treat that as "source unavailable this cycle", never as a failure that
blocks every other source.

**Biggest risk.** A source changes what a column means, not just its numbers.
For example, OPM restructures the Plum export, or the Treasury reclassifies a
section. Every check then passes on a quietly wrong reading, and automatic
publishing ships it. The change budget, the per-source parse checks and the
existing "re-derive from the committed document" gate are the defence. None
of them catches a plausible reinterpretation.

**Mitigation that keeps the decision.** For the first three cycles the job
runs in hold-everything mode and a person approves each publish. After three
clean cycles it switches to automatic. That is the cycle count criterion 5
already requires.

### 6. Freshness: each source on its own cycle

**Decision.** Each source is refreshed on the cycle its publisher keeps. The site
shows each figure's date and flags anything overdue.

**Done when** there is a committed source registry giving, for each source, its
expected cadence and the date of the copy in use; the job reads it to decide
what is due; and the panel marks a figure "overdue" once its source has missed
its expected publication by a stated margin.

Expected cadences, to be confirmed against each publisher before the registry
is written [Likely]:

| source | cadence |
|---|---|
| Monthly Treasury Statement (the anchor and every measured cost) | monthly |
| USAspending File A / File B | monthly |
| House Statement of Disbursements | quarterly |
| Report of the Secretary of the Senate | semiannual |
| OPM salary tables (EX, GS, ES, SL/ST); pay-adjustment schedules in the 5 U.S.C. 5332 note | each January |
| uscourts.gov judicial compensation; senate.gov salaries | each January |
| White House staff report | each July 1 (statutory) |
| OPM current Plum export; FedScope | as OPM republishes |
| Government Manual | annual edition |
| OMB Public Budget Database | with each President's Budget |
| Statement of Net Cost; Combined Statement | annual, after fiscal year end |
| U.S. Code sections | when amended (re-check yearly) |

**Today.** Every figure carries its period. **Built 2026-10-22:**
`data/source_registry.json` (27 sources, cadence with a stated basis, copy date
read off the graph or the fixtures' fetch records), derived onto the graph root
as `__sourceRegistry` by `data_pipeline/freshness.py`, mirrored by the gate;
the panel lists the sources behind each node and marks one overdue against the
reader's date; `scripts/report_source_registry.py --due` is the list the job
reads. First derivation: 23 current, 1 newer edition expected (the Treasury
statement), 2 overdue (FedScope March 2025; the 2025 AUSA pay chart), 1 closed
record (CURATION.md §28). Cadences are the reviewer's, to be tuned on the first
cycles; no job reads the registry yet (criterion 5).

### 7. Conflicts: hold and queue, never resolve automatically

**Decision.** When a source contradicts the graph (a unit renamed, a post
abolished, two documents disagreeing), the job withdraws the claim that no
longer holds, keeps the old record, and adds the change to a review list. It
never settles a disagreement by itself.

**Done when:**
- the job writes a committed review queue (one entry per held change, with
  both documents and what each says);
- the site shows a withdrawn claim as withdrawn, not silently gone;
- the queue is the only thing a person is asked to look at between cycles.

**Today.** Withdrawal is already built in: every evidence field is owned and
cleared each build, and a renamed node loses its evidence. Disagreements are
already published, not resolved (`placementDirectoryDisagreement`,
`cost_weight_dispute`, `CODE_CONTRADICTED_LISTINGS`). **Built 2026-10-22:**
`data/audit/review_queue.json`, rebuilt by `scripts/build_change_history.py --record`
from each build's diff (holds, withdrawals, removals) and the graph's own
disagreements, each record with both documents and what each says, closed and
never deleted when its condition goes; and `output/change_history.json`, the
record of what changed between two builds. First queue: 53 open (40 name
questions, 10 headcount disputes, 2 overdue sources, 1 placement
disagreement); CURATION.md §29. The job that writes both each cycle is
criterion 5's.

This sits inside criterion 5 without contradicting it: everything a check can
settle publishes automatically, and everything that needs judgement is held.

---

## The finish line, in one table

| # | criterion | target | today | gap |
|---|---|---|---|---|
| 1 | Money | 0 bare estimates | 0 (359 explained blanks; 341 have no held document naming the unit) | 0 by the test; the 18 named-but-unlicensed rows are the route to more figures |
| 2 | Pay | 0 posts unpriced and unexplained | 3,221 (every one with a documents-checked blank since 2026-10-22) | 3,221 |
| 3 | Evidence | every current organisation sourced | 884 current organisations; 40 with neither a method nor a recorded reason | 40: 17 stale subcommittees, 7 groupings, 11 NSF units, 5 others; a decision, not a build (CURATION.md §32.2) |
| 4a | Lists | every list unit reconciled | every unmatched entry disposed, 21 of 21 curated names resolved; 14 of the 16 real units added 2026-10-26 (CURATION.md §32.1) | 5: 3 unsure + Amtrak and the Bureau of Indian Education (the owner's) |
| 4b | Money traced | every measured parent sums visibly | 57 of 57 measured units with parts show the sum; not attributed 0 (2026-10-22) | $3.15tn beneath 22 units (September statement) is still apportioned to estimated children, now named |
| R | Reader | four features | 4 of 4 (figures explain themselves; totals add up visibly; change history; export/download) | — |
| 5 | Self-update | 3 clean automatic cycles | job and monthly hold-mode workflow (the 16th, after the statement's latest possible publication) built 2026-10-22; run on GitHub's runner 2026-10-22 (clean); 0 SCHEDULED cycles counted — a cycle a person started proves the job works and is not counted | three clean scheduled cycles, then the owner's switch to --publish; earliest mid-January 2027 |
| 6 | Freshness | registry + overdue flag | registry (27 sources) + overdue flag built 2026-10-22; 24 current, 2 overdue (FedScope, the AUSA pay chart) on 2026-10-25 | the job that acts on "due" (criterion 5); cadences to tune |
| 7 | Conflicts | review queue + change log | queue (53 open) and change log built 2026-10-22; withdrawals recorded with the document and why; the change budget has six rules since 2026-10-25 (a build that read no statement is held) | the job that writes both each cycle (criterion 5) |

The 3,221 in row 2 is the 3,333 positions with no pay figure, less the 112
already explained.

**Order — the owner's decision (2026-10-21): every node verified and given a
cost comes before everything else.** Criteria 1, 2 and 3 are the work; 4–7
and the reader features wait until those gaps close. This overrides the first
draft of this document, which put self-updating first on the grounds that
published figures age while nothing refreshes. That risk still stands and is
accepted.

1. **Evidence (3):** the 247 unsourced organisations, starting with the 358
   that have no candidate page at all (nominations, the Manual, directories).
2. **Money (1):** the bare estimates, by the routes in criterion 1: the other
   Combined Statement chapters first, since the Legislative Branch chapter
   showed the route works to the cent.
3. **Pay (2):** the unpriced posts, by title family (research pack 4),
   with a terminal reason recorded wherever no figure exists.

"A cost" means, for an organisation, a measured figure, a sourced figure of
another kind labelled by basis and period, or an explained blank; for a post,
pay or an explained blank. A post never carries a share of a budget. That
reading is criterion 1 and 2's, unchanged.

After those: self-update (5–7: source registry and change log, a scheduled job
in hold mode, the change budget, three approved cycles, then automatic), then
the reader features, "totals add up" first.

Row 4a needs a single number before it can be tracked. The first task under
it is a report, in the shape of `report_cost_coverage.py`, that reconciles
each list against the graph and counts what is unresolved.
