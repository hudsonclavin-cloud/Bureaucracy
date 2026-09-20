# Evidence triage runbook — phase 1c

Instructions for an agent sweeping every node in the graph and asking one
question the other three phases cannot ask:

> **Given what this node actually is, should it be carrying verification and a
> cost? If it is not, which of the seven causes is it, and is that cause a
> defect somebody can fix or the honest answer?**

Many agents run this at once, on disjoint shards. Read this whole file before
the first batch.

---

## Why this phase exists

On 2026-09-20 the repository owner opened the site, clicked a U.S. Court of
Appeals, and found no verification on it. It was not one court. **Six of the
thirteen circuits carried no source at all**, and the cause was not the
matcher, the name, the robots policy or the network:

- **five had no candidate page in `official_sites.json`.** The verifier had
  never fetched them and never could have, however long it ran. Their
  siblings `ca1`, `ca3`, `ca6`, `ca10` and `ca11` were already queued on the
  identical `caN.uscourts.gov` pattern. These five were simply skipped.
- the Third Circuit's URL was `https://ca3.uscourts.gov/` — missing the `www.`
  its twelve siblings all carry — so its robots.txt was unreachable and RFC
  9309 2.3.1.4 made that a complete disallow.
- the Sixth Circuit's fetch died on a dropped connection.

Seven probes and one nomination pass later, all thirteen verify. Nothing was
loosened to get there: `canonical_name_key` already folded `U.S.` into
`United States`, and every confirmation is label equality in page content.

**The defect had been sitting in plain sight and all three existing phases
were structurally incapable of raising it:**

| Phase | Asks | Why it missed this |
|---|---|---|
| 1a `NODE_AUDIT_RUNBOOK.md` | Is what the site says supported? | `existence: no_evidence_in_repo` is a *correct* answer in its vocabulary, and the runbook's "do not report these" list explicitly suppresses uncited-ness. A node with nothing is not a finding there. |
| 1b `SOURCE_NOMINATION_RUNBOOK.md` | Which page should the verifier fetch? | Works the shard it is handed. It never asks "is this node's emptiness *surprising*?" |
| 2 `COST_NOMINATION_RUNBOOK.md` | Which record would give it its own cost? | Same: it proposes records, it does not triage expectation. |

Phase 1a asks whether what is *there* is supported. **This phase asks whether
what is missing should be.** That is the owner's own heuristic, in his words:
*"if it is an agency it probably should have those things."*

He is right, and the data agrees with him — which is exactly why the rest of
this file is about the cases where he is wrong.

---

## The prior is good. The trap is treating it as a conclusion.

Recomputed from the published graph (see **Recomputing every figure** below —
do not trust these from this page):

| Type | n | verified | measured cost |
|---|---:|---:|---:|
| Cabinet Department | 15 | **15** | **15** |
| Agency | 50 | 42 | 32 |
| Independent Agency | 31 | 28 | 14 |
| Component Agency | 18 | 12 | 14 |
| Bureau | 62 | 29 | 21 |
| **Defense Agency** | **22** | **6** | **0** |

Cabinet Departments are 15 for 15 on both. The prior is real: the further a
type sits from "a named agency that runs its own website and gets its own
appropriation", the thinner the evidence gets, and where a type breaks that
pattern it is worth a look.

**Now look at the Defense Agencies, and do not jump.** Twenty-two nodes —
NSA, DIA, NRO, DLA, DARPA, DISA, MDA, DHA — and **zero measured costs.** By
the owner's heuristic that is twenty-two defects.

It is zero defects. Checked directly against the committed statement rather
than assumed:

```
National Security Agency     -> *** NO LINE ***
Defense Intelligence         -> *** NO LINE ***
Defense Logistics            -> *** NO LINE ***
Missile Defense              -> *** NO LINE ***
Advanced Research Projects   -> *** NO LINE ***
```

The Monthly Treasury Statement does not report these agencies. It reports
`Defense Agencies` as one combined line, and the graph's estimate for each is
the honest state. **There is no number to find.** An agent that "fixes" this
publishes a figure no government document states, which is the one thing this
project exists not to do.

And the trap has a second floor. There *is* a Table 5 line reading `Defense
Agencies`, and a naive fix would apply it:

```
Defense Agencies   fytd_net=26,542,565,000.00
Defense Agencies   fytd_net=76,825,310,314.73
Defense Agencies   fytd_net=8,061,955,897.67
Defense Agencies   fytd_net=38,885,005,783.56
...nine lines with amounts, one per object class
```

Nine lines carry that name — Military Personnel, O&M, Procurement, RDT&E and
so on. `CLAUDE.md` already forbids resolving this: *"A name several lines
carry is reported ambiguous, never resolved by picking the largest."* Picking
the $76.8bn one is fabrication wearing a citation.

**So the rule for this phase is:**

> A surprising absence is a reason to **investigate**, never a reason to
> **conclude**. "This looks like it should have a number" is a hypothesis.
> The verdict is whichever of the seven causes the evidence actually shows,
> and `no_public_page_known` / "no publisher reports it separately" are
> respectable verdicts, not failures.

---

## The two ways to be wrong, and they are not symmetric

**False negative** — you pass over a real defect. Cost: the Court of Appeals
case. Some unit sits on the public site with a blank where evidence exists and
nobody notices for months. Recoverable; the next sweep catches it.

**False positive** — you assert a unit should have evidence and manufacture a
route to it: an invented URL, a Treasury line that names something broader, a
figure for an agency no publisher reports. Cost: the project's entire claim on
being trustworthy. **Not recoverable by a later sweep, because it now looks
like evidence.**

Weight your judgment accordingly. When you cannot tell, say so — every verdict
below has a slot for "I do not know", and using it is the job working, not the
job failing.

---

## What you are handed, and what you may write

```bash
python scripts/node_audit.py next --count 25 --shard 3/8 > /tmp/batch.json
```

The batch gives you, per node: `name`, `type`, `ancestors`, `siblingNames`,
`childNames`, `childCount`, `description`, `descriptionSource`, `cost`,
`published_claims`, `evidence_records`, and `otherNodesWithThisName`.

**`siblingNames` is the single most useful field in this phase.** The Court of
Appeals defect was visible in one glance at thirteen siblings: five had pages,
five had none, one had the wrong hostname, and they were all the same kind of
thing with the same URL pattern. Read the row, not the cell.

**You write to exactly one place**, and it is a harness that already exists —
this phase adds no new writer:

```bash
python scripts/nominate.py record --kind source --file /tmp/proposals.json --run triage-3
python scripts/nominate.py record --kind cost   --file /tmp/costs.json     --run triage-3
```

Both write only under `data/audit/`. Neither can touch the curated file, the
published graph, or any evidence file. **Nothing you write is a claim** —
`official_sites.json` says it in its own header: *"A URL here is something to
check, not evidence."* You propose; `verify_base_graph.py` reads the page and
adjudicates by label equality. The worst a wrong nomination does is waste one
fetch.

**You may never say `confidence: certain`.** The harness refuses it. An agent
that has not read the page cannot have earned it.

---

## The verdict: route every empty node to one of seven causes

These are `nominate.py`'s own `NO_CANDIDATE_REASONS`, and they are already
exactly the triage vocabulary — which is why this phase needs no new harness.
Pick the one the evidence shows.

**Actionable — propose a fetch:**

- **a page you can name.** Write a `nominations` block with `url`, `role`,
  `basis`, `confidence`. This is the Court of Appeals class and the highest
  value thing you can produce.
  - `role: own_site` — the unit's own page. Filed under the node.
  - `role: parent_listing` — the parent's page lists it. Filed under the
    **parent**, and publishes the weaker `name_labelled_on_parent_official_page`.
  - `role: official_list` — a government directory. **Filed nowhere**; both
    available methods would misdescribe it. Prefer a real module.
  - Getting `role` wrong is not cosmetic: 20 live confirmations once cited
    `energy.gov/national-laboratories` — DOE's *index* of the labs — as each
    lab's *own* official page.

**Correct absence — say so, with the reason, so nobody re-does the work:**

| reason | means | example from this graph |
|---|---|---|
| `not_an_organisation` | a position, role or accounting line | any of the 4,591 Position nodes |
| `editorial_grouping` | a heading this graph invented; the government names no such body | `Mission Teams (15)`, `Analytical Divisions`, `House Committees` |
| `covered_by_parent` | no page of its own; the parent's is the right check | most subcommittees |
| `no_public_page_known` | a real unit, and you cannot name a page | the honest fallback |
| `not_on_a_gov_host` | real, but on a host the verifier refuses | 24 Smithsonian museums on `si.edu`, USPS on `usps.com` |
| `host_refuses_crawler` | a `.gov`/`.mil` page exists; the host will not serve robots.txt | 16 of the 22 Defense Agencies |
| `page_read_does_not_name_it` | the page was read; the curated name is not a label on it | a curation problem, not a URL problem |

The last two **require a probe block**. Each asserts something about a
specific page rather than about your own ignorance, so you must have looked:

```bash
python scripts/probe_candidate_pages.py --url https://www.ca2.uscourts.gov/ --ids jud-circuit-2nd-circuit
```

It is read-only, it writes nothing, and it runs the verifier's own label test.
Use it before every nomination you can afford to — a `basis` that quotes the
matched label and the readable character count is worth ten that reason from
the hostname.

---

## Diagnosing the "why" — read the evidence record first

`evidence_records` in the batch usually already contains the answer, and
reading it is the difference between a diagnosis and a guess. Across the 346
organisations currently carrying no verification:

| What the record says | n | What it means | Your move |
|---|---:|---|---|
| **no record at all, no page queued** | **100** | the verifier has never been given anything to fetch | **the highest-value class — nominate a URL** |
| `inconclusive: only_an_ancestor_page_was_read` | 92 | a parent's page was read; it is not obliged to list children | nominate the unit's own page if one exists, else `covered_by_parent` |
| `fetch_failed` (robots/network) | 57 | the host refused, or the network did | check the hostname for the `www.` class of error; else `host_refuses_crawler` |
| `not_found` | 26 | its own page was read and does not name it | `page_read_does_not_name_it` — a **name** problem; route to `CURATION.md` §9 |
| `fetch_failed` (other) | 23 | read the reason verbatim | depends |
| `not_checkable` | 21 | the name could never be evidence (`Individual Senator Offices (100)`) | `editorial_grouping`, and leave it alone |
| `fetch_failed: 404` | 17 | the page moved | nominate the replacement |
| `inconclusive: named_on_the_page_but_not_as_a_label` | 10 | the page names it in prose, not as a heading or link | usually correct to leave; the loose match exists only to withhold a false negative |

**A `fetch_failed` is not a dead end — look at the hostname before you accept
it.** Two of the thirteen circuits failed this way and both were recoverable:
one had a missing `www.`, the other a transient dropped connection. A
`RemoteDisconnected` or a bare `URLError` is worth one re-probe. An Akamai 403
on `robots.txt` is a policy fact and is not.

---

## The cost question, separately

Cost is not verification and the two do not travel together. A node can be
measured and unverified, or verified with no figure. Judge them apart.

Before proposing any cost record, know what the honest states are:

- **a post never gets one.** `post_is_not_a_budget_unit`. A post's share of an
  agency's outlays is not a quantity that exists. 4,591 nodes. Never nominate.
- **`allocated` is the expected state**, not a defect. 638 of 832
  organisations carry an apportioned estimate. That is the design.
- **`unit_superseded`** (36) and **`treasury_pool_negative`** (29) are
  deliberate. Nothing can be apportioned out of a pool that nets below zero.
- **no publisher reports it separately** — the Defense Agencies case. The most
  common honest answer for a sub-departmental unit.

Nominate a cost only when you can name a **specific record** — a Treasury
Table 5 line, a USAspending File A key, an OMB account grouping, an audited
net-cost row — that names **this unit** and not a broader one. The three
scoping failures in `docs/COST_NOMINATION_RUNBOOK.md` are the ones to avoid,
and the middle one is the Defense Agencies trap by another name:

1. the record names a **broader** entity (the VBA's USAspending key is
   "Benefits Programs", a $233bn grouping);
2. the record's name is carried by **several lines** (nine `Defense
   Agencies` rows, eight `Department of the Navy` rows);
3. the record names a unit with a **similar** name in a different branch
   ("Secretary of Homeland Security" reaches a Senate *subcommittee*).

Every record must name its **metric**, and `nominate.py` accepts exactly ten:
`appropriations`, `audited_net_cost`, `basic_pay`, `budget_authority`,
`budget_request`, `full_time_equivalents`, `gross_outlays`, `net_outlays`,
`obligations`, `payroll`. A figure whose metric you cannot name is a figure
you cannot nominate — and naming it is not a formality, because the graph's
own measured cost is `net_outlays` and a `gross_outlays` or `budget_request`
figure filed as though it were the same number is the error the USAspending
and OMB blocks exist to keep apart.

(`CLAUDE.md` describes this vocabulary as five metrics. It is ten; the list
above was read out of `scripts/nominate.py` on 2026-09-20. Where the two
disagree the code wins — that is `CLAUDE.md`'s own standing rule about
itself.)

---

## What NOT to report

This list carries as much weight as the rest. Without it the sweep returns the
same true, useless sentence thousands of times and buries the real findings.

- **"the description is uncited."** True of nearly every curated node, and
  already labelled on every panel as *"uncited prose — not checked against any
  source."* Only a description the repo's own evidence **contradicts** is a
  finding, and it belongs in phase 1a, not here.
- **"this node has no source."** True of 4,654 nodes. The finding is never the
  absence; it is the absence **plus a named, fixable cause**.
- **"a Position has no budget."** By rule, for 4,591 nodes.
- **"this estimate looks too high/low."** Unless you can name the record that
  contradicts it. An apportioned share is not a measurement and the panel
  already says so.
- **a nomination for a node another phase's ledger already covers.** Run
  `nominate.py report --kind source` first.
- **anything about a `Treasury accounting line`.** The exporter creates those;
  they are not units of government and claim not to be.

---

## Scope, sharding, and what a good run looks like

Triage the **832 non-post, non-accounting-line nodes**. The other 4,621 are
positions and accounting lines whose empty state is decided by rule, and
handing them out would produce thousands of identical refusals — the same
reason phase 1b never hands out a position.

```bash
python scripts/node_audit.py next --count 25 --shard 3/8 > /tmp/batch.json
```

`--shard k/N` partitions deterministically — disjoint and complete, pinned by
a test — and each agent writes its own ledger file under
`data/audit/nominations/`, so N agents never collide and their branches merge
without conflict. Use `--run triage-<k>` so the ledger says which pass it came
from.

**Work sibling sets, not nodes.** The single highest-yield move in this phase
is to notice that twelve of thirteen siblings share a URL pattern and one does
not. `siblingNames` is in every batch for this reason.

A good run produces, per 25 nodes, something like: a handful of real URL
nominations with probed bases; a larger number of `noCandidate` verdicts with
the *specific* reason rather than `no_public_page_known` as a catch-all; and
one or two genuine "I cannot tell" entries. A run that returns 25 nominations
is not thorough, it is guessing. A run that returns 25 `no_public_page_known`
did not read the evidence records.

---

## Recomputing every figure on this page

Nothing here is restated by hand on the next edit. Each number above comes
from one of these:

```bash
python scripts/validate_published_graph.py          # coverage, verified-by, cost_status
python scripts/nominate.py status --kind source     # organisations with no candidate page
python scripts/nominate.py report --kind source     # what the ledger already covers
python scripts/probe_candidate_pages.py --uncovered # what still has no page, no fetch
```

The type table and the 346-node diagnosis table are computed by walking
`output/graph.json` against `data/verification/evidence.json` and
`official_sites.json`. If a figure here disagrees with a command, **the
command is right and this page is stale** — that is the standing convention in
`CLAUDE.md` and it applies to this file too.
