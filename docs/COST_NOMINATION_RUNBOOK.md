# Cost nomination runbook — phase 2

Instructions for an agent proposing, for each node, **which record would give
that node its own cost**. Run this only after phase 1 (`NODE_AUDIT_RUNBOOK.md`
and `SOURCE_NOMINATION_RUNBOOK.md`) has been through the same nodes, because
this phase depends on what phase 1 established.

---

## Why this comes second

137 of 5,402 nodes carry a cost a record names for them (the figure
`python scripts/validate_published_graph.py` prints, which is the copy to
trust). 650 carry a share of an ancestor's total, divided by budget, headcount
or subtree size — which the site no longer shows by default, because a number
nobody measured must not be the first thing a reader sees. The remaining 4,615
carry no figure at all: 4,441 of them are posts, which have no budget to
divide, so a cost nomination for one is never the unit's cost and only ever a
rate of basic pay.

Getting past 137 needs one thing before any new data source: **a reviewed
crosswalk from node to financial identifier.** `docs/EXACT_NODE_COSTS.md` sets
that out. This phase builds it, one nomination at a time.

**Phase 1 is your input, not background reading.** Before nominating for a
node, look at what phase 1 recorded about it:

- If the audit found the node is a **duplicate**, is **not a real unit**, or
  sits under the **wrong parent**, do not nominate a cost for it. A financial
  identifier attached to a node that is about to be merged or moved is worse
  than nothing — it will look like evidence for the wrong thing. Say
  `noCandidate` with the audit's finding as your reason.
- If the audit found the **name is stale**, the identifier you would look up
  under the old name is probably wrong. Say so.
- If phase 1b found an `own_site` for the unit, that page often names the
  unit's budget documents, which is the fastest route to its account numbers.
- If the audit recorded `existence: no_evidence_in_repo` and phase 1b said
  `editorial_grouping`, this is a curated grouping, not a spending entity: it
  can never have a cost of its own. `noCandidate`.

Read the node's audit record before you nominate. If phase 1 has not covered
this node yet, skip it — do not run ahead.

---

## The numbers, and never confusing them

This is the single most important thing in this runbook. "Cost" is many
different measurements and the graph must never let one stand in for another.

The list is defined once, in `data_pipeline/verification/financial_evidence.py`
as `BASES`, and imported here — one vocabulary, so a figure the evidence side
can record is always a figure the nomination side can name.

| `metric` | What it answers | Source system | Notes |
|---|---|---|---|
| `audited_net_cost` | What did this entity cost? | `agency_financial_report` | Audited, accrual basis. The best answer and the only audited one. |
| `net_outlays` | What cash went out, net of receipts? | `treasury_mts`, `usaspending_file_ab` | What this graph already publishes. Not cost. |
| `gross_outlays` | What cash went out, before receipts? | `treasury_mts`, `usaspending_file_ab` | The statement prints both. On a large agency they differ by billions. File A reports only this, fiscal-year-to-date. |
| `obligations` | What was committed? | `usaspending_file_ab` | A commitment, not spending. |
| `budget_authority` | What was made available? | `usaspending_file_ab`, `omb_public_budget` | A plan, not an outcome. |
| `appropriations` | What did Congress enact? | `appropriations_act`, `omb_public_budget` | Enacted, but not yet spent, and often keyed by account rather than by organisation. |
| `budget_request` | What did the agency ask for? | `congressional_justification` | **Not spending, and not even funding.** A request made before the year began, which Congress may cut, ignore, or supersede. It is the most granular figure available by organisation, and the least authoritative. |
| `payroll` | What does this unit's staff cost? | `agency_financial_report`, `congressional_justification` | An input to cost, not cost. |
| `basic_pay` | What does this post pay? | `opm_pay_table`, `uscourts_judicial_compensation`, `senate_salary_schedule`, `us_code_pay_schedules`, `va_title38_pay_ranges`, `whitehouse_staff_report`, `opm_plum_current_export`, `statutory_parity_derived_pay` | Compensation for one post. **Never** an organisation's cost. Most are single primary documents that name a seat or a title directly; the PLUM export's row is an incumbency, so its figure is one listing's; `va_title38_pay_ranges` states a BAND rather than a rate and is published as one; `statutory_parity_derived_pay` is the one source here whose figure NO document states — a parity provision names the tier and the compensation table prices it — and every record carries both documents, the count and what that count is worth. |
| `full_time_equivalents` | How many staff-years? | `congressional_justification` | Not money at all. Carried because budget tables report it beside the dollars, and because it is the honest answer when a unit's money cannot be separated but its staffing can. Never rendered with a currency symbol. |

Nominate the metric that source actually reports. Do not nominate
`audited_net_cost` and point at a Treasury outlay line; they are different
numbers about different things and the difference is often large.

**On `budget_request` in particular.** Congressional Justifications are the
only source that reports by office and budget activity *with organisation
names attached*, which makes them the most promising route past 136 measured
nodes. They are also the weakest basis in this table. Nominating one is
correct; letting the site render it under a heading a reader parses as
"what this costs" is not. The basis and the fiscal period travel with the
figure everywhere, or the figure does not travel.

---

## The loop

```bash
python scripts/nominate.py status --kind cost
python scripts/nominate.py next --kind cost --shard 3/8 --count 25 > /tmp/batch.json
#   ... read each node's phase-1 record, decide, write /tmp/proposals.json ...
python scripts/nominate.py record --kind cost --file /tmp/proposals.json --run cost-agent-3
git add data/audit/nominations && git commit -m "..." && git push
```

Same sharding and same one-file-per-agent rule as phase 1b. `--run` must be
unique to you.

To read a node's phase-1 record:

```bash
grep '"id": "exec-dept-ed-fsa"' data/audit/node_audit.jsonl | python -m json.tool
grep '"id": "exec-dept-ed-fsa"' data/audit/nominations/source-*.jsonl
```

---

## What an identifier is

A key that a financial system uses to name this exact entity. **Stable codes,
not names.** A name may propose a candidate and must never publish a
financial fact on its own — that rule is why the graph has exactly one
name-keyed alias table and why every entry in it carries a section check.

| `system` | `key` should be |
|---|---|
| `treasury_mts` | The Table 5 line as the statement prints it, e.g. `Total--Office of Federal Student Aid`, plus the section it sits under in `basis` |
| `usaspending_file_ab` | A TAS (agency identifier, main account code, and any sub-account) or a federal account symbol; a toptier CGAC code for a whole department |
| `agency_financial_report` | The entity as the Statement of Net Cost names it, plus the fiscal year |
| `omb_public_budget` | OMB agency and bureau codes |
| `omb_apportionment` | The apportionment's TAS and the OMB approval it carries |
| `appropriations_act` | The public law, the division and the account heading as enacted |
| `congressional_justification` | The CJ's own budget activity or office line, plus the fiscal year of the request |
| `opm_pay_table` | The pay plan and level, e.g. `EX-II` |
| `uscourts_judicial_compensation` | The tier as the U.S. Courts' table names it, e.g. `District Judges` |
| `senate_salary_schedule` | The role as the Senate's footnote names it, e.g. `Majority Leader` |
| `va_title38_pay_ranges` | The coverage phrase exactly as one of the VA's Title 38 pay tables prints it, as a WHOLE item of that tier's list, e.g. `Medical Center Directors`. The result is a minimum and a maximum, never a rate |
| `statutory_parity_derived_pay` | The parity provision's citation, e.g. `26 U.S.C. 7443(c)(1)`, whose sentence must be in that section's OPERATIVE text — not in the repealed text the publisher prints beneath it. The result is a figure no document states: the statute names an Article III tier and the Judicial Compensation table prices it |
| `us_code_pay_schedules` | The office exactly as Schedule 6 prints it in the note to 5 U.S.C. 5332, e.g. `Speaker of the House of Representatives`. Two of its rows name two offices at once (`Majority leader and minority leader of the House of Representatives`), so a key can be a proxy for either and the record says which node it was identified with |
| `whitehouse_staff_report` | The title exactly as the Annual Report to Congress on White House Staff prints it |
| `opm_plum_current_export` | The Agency, Organization and Position Title exactly as OPM's current PLUM export prints them; a row is an incumbency, so the figure is one listing's and the record is a proxy |

The list is `financial_evidence.SOURCE_TYPES`, imported rather than copied,
so a source the evidence side can record is always one this side can name.

`basis` is where you say why this key is this node — the section it appears
under, the parent account, the page that lists it. That sentence is what a
reviewer checks.

---

## The scoping rule that keeps this honest

An identifier is only this node's if it covers **this node and nothing else.**

Three ways that fails, all of which have already produced false numbers in
this project:

- **Too broad.** Treasury's "Fish and Wildlife and Parks" covers the Fish and
  Wildlife Service *and* the National Park Service. Attaching it to either one
  publishes the pair's money as one unit's. If a key covers several nodes, it
  is the *parent's* key, not this node's.
- **Too narrow.** One account of an agency that has twelve is not the agency's
  cost. Several keys may sum to one node — nominate them all and say in
  `basis` that together they are complete and non-overlapping. If you cannot
  say that, do not nominate the set.
- **A different population.** FedScope counts Executive-Branch civilians and
  excludes uniformed members; the Coast Guard's civilian count is not the
  Coast Guard. The same trap exists on the money side between an agency's
  appropriated accounts and its trust funds.

When a key is the parent's rather than this node's, say `noCandidate` with
that reason. It is a useful finding, not a failure.

---

## The record format

```json
{"records": [
  {
    "id": "exec-dept-ed-fsa",
    "metric": "net_outlays",
    "identifiers": [
      {"system": "treasury_mts", "key": "Total--Office of Federal Student Aid",
       "basis": "Table 5 prints this line under the Department of Education, which is where the graph puts the office, so it passes the same-section test.",
       "confidence": "likely"}
    ]
  },
  {
    "id": "exec-dept-doi-fws",
    "noCandidate": true,
    "reason": "The only Treasury line that reaches it is 'Fish and Wildlife and Parks', which also covers the National Park Service. That is the parent's key, not this node's."
  },
  {
    "id": "leg-senate-leadership",
    "noCandidate": true,
    "reason": "Phase 1 recorded this as a probable editorial grouping (node_type: unclear, senate.gov does not label a unit of this name). A grouping the government does not name has no account of its own."
  }
]}
```

`confidence` is `likely` or `speculative` — never `certain`, for the same
reason as phase 1b: you have not read the source that would settle it.

---

## What happens to your work

Nothing is published. A cost nomination is a proposed crosswalk entry, and a
crosswalk entry becomes a published figure only when:

1. the source is fetched (`scripts/fetch_fixture.py`, verbatim, with its
   `.meta.json`);
2. a matcher reads the key out of that file and finds one entity;
3. the release gate's rules pass — a measured cost sits only on an
   organisation, children never sum past their parent, every measured node
   carries its source URL;
4. the panel says which of the five numbers it is.

None of that is your job. Your job is the crosswalk.

For `usaspending_file_ab` the matcher exists (`scripts/derive_usaspending_evidence.py`):
it applies a proposal only where the API's name and the node's reduce to the
same canonical key, and holds every other proposal — an alias, an
abbreviation, a bureau broader than the node — as `awaiting_review` with the
confidence you gave it. A held proposal is not wasted; it is the list a
curator reads. What it publishes is `gross_outlays`, beside the cost, never
as it.

---

## Feeding back into phase 1

If nominating a cost teaches you something about the *node* — that it is a
grouping, that it duplicates another node, that the Treasury files it under a
different parent than the graph does — that belongs in the **phase 1 audit
ledger**, not here. Record it with `scripts/node_audit.py record --force` and
say in the claim that it was found during the cost pass.

The two phases are meant to feed each other. A node whose money nobody can
identify is often a node whose identity nobody has pinned down, and that is
the more useful finding of the two.

---

## Before you stop

Run `python scripts/nominate.py report --kind cost` and hand back the split by
metric and by system, how many nodes you could not place, and — separately —
any phase-1 findings you fed back.

Do not report nominated nodes as nodes with a cost. Say plainly how many nodes
now have a *proposed* identifier and that none of them is a published figure.
