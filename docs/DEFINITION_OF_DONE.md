# What "done" means for Bureaucracy

Decided by the owner on 2026-10-21, in two rounds of multiple-choice questions.
Every "today" figure below was measured on the published graph that day
(`output/graph.json`, 5,510 nodes) by `scripts/validate_published_graph.py`,
`scripts/report_cost_coverage.py`, `scripts/report_unpriced_positions.py` and
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

| measure | today |
|---|---|
| measured cost | 172 nodes (99.0% of the anchor) |
| estimate beside a sourced figure | 68 |
| committee/subcommittee estimate | 240 (40 committees carry disbursements) |
| **bare estimate — the gap** | **373** |

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
that refuses every crawler and no directory lists the unit).

| measure | today |
|---|---|
| current organisations | 870 |
| with a verification method | 623 (71.6%) |
| **without — the gap** | **247** |
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

---

## Part 2 — What the reader gets

All four were chosen.

| criterion | done when | today |
|---|---|---|
| **Every figure explains itself** | every figure on the panel and in the directory names its source, period and kind in words | largely met; keep the smoke check asserting it |
| **Totals add up visibly** | a measured unit's panel shows the sum in criterion 4(b): what each child contributes, what is estimated, what is not attributed | not built; the data exists (`treasury_unapportioned`, receipts lines, `treasury_pool_negative`) |
| **Change history** | a reader can see what changed since the last update: figures that moved, nodes added or replaced, claims withdrawn, and why | not built; each build already knows what it withdrew and re-derived |
| **Export / download** | a reader can download the graph and a flat CSV of nodes and figures, with the sources, from the site | partly: `graph.json` is public but not offered as a download; no CSV |

---

## Part 3 — Self-sustaining

### 5. Updating on its own: fully automatic when every check passes

**Decision.** A scheduled job fetches new source documents, rebuilds, runs every
check, and **publishes by itself when all checks pass**. A person hears only
about failures and held changes.

**Done when** the job has run on its schedule for **three consecutive monthly
cycles** with no manual step and no bad publish.

**Today.** Nothing runs on a schedule. `data_pipeline/scheduler/nightly_update.py`
exists but nothing invokes it, and there is no CI workflow. Every update is a
person or an agent running commands.

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

**Today.** Every figure carries its period. There is no registry, no overdue
flag, and nothing decides what is due.

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
`cost_weight_dispute`, `CODE_CONTRADICTED_LISTINGS`). What is missing is the
queue itself, and a record of what changed between two builds.

This sits inside criterion 5 without contradicting it: everything a check can
settle publishes automatically, and everything that needs judgement is held.

---

## The finish line, in one table

| # | criterion | target | today | gap |
|---|---|---|---|---|
| 1 | Money | 0 bare estimates | 373 | 373 |
| 2 | Pay | 0 posts unpriced and unexplained | 3,221 | 3,221 |
| 3 | Evidence | every current organisation sourced | 623 / 870 | 247 |
| 4a | Lists | every list unit reconciled | partly | not yet measured as one number |
| 4b | Money traced | every measured parent sums visibly | Legislative Branch probed | only chapter c01 is fetched |
| R | Reader | four features | 1 of 4 | 3 |
| 5 | Self-update | 3 clean automatic cycles | no scheduler | all |
| 6 | Freshness | registry + overdue flag | periods shown | registry, flag |
| 7 | Conflicts | review queue + change log | withdrawal built | queue, log |

The 3,221 in row 2 is the 3,333 positions with no pay figure, less the 112
already explained.

**Suggested order.** Self-update (5, 6 and 7) is built before the long tails of
1–3. Every month the site is not refreshing, the figures already published age.
The research tails will take many batches, and automation makes each batch
stay true once landed.

1. Source registry and change log.
2. Scheduled job in hold mode.
3. Change budget.
4. Three approved cycles.
5. Switch to automatic.

In parallel: the Combined Statement chapters (1, 4b), research packs (2) and
nominations (3). Then the reader features, "totals add up" first, because it
is the visible form of 4b.

Row 4a needs a single number before it can be tracked. The first task under
it is a report, in the shape of `report_cost_coverage.py`, that reconciles
each list against the graph and counts what is unresolved.
