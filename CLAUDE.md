# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repository.
This file was lost in the 2026-08-04 merge and rewritten from the code on
2026-09-02; where it disagrees with older commit messages, the code wins.

## Start here

`docs/GO.md` is the standing instruction for agent work on this repository.
When the owner says **go**, read it and follow it from Step 0; it decides
which of the three phases the work is currently in by reading state off disk,
so a fresh session resumes exactly where the last one stopped. `/go` is the
same thing as a slash command.

## Project goal

A browsable, data-backed 3D organizational graph of the U.S. federal
government, from the Constitution down to offices and positions, with a cost
on every node and an honest statement of how that cost was obtained. The
project's standing rule: never let the data or the UI claim more than the
evidence supports. Measured costs are the root's Treasury anchor and the
Monthly Treasury Statement Table 5 lines that name a node — 103 of the
statement's 644 lines as of 2026-09-03. Every other node is an estimate
apportioned from those figures, and must read as one.

## Commands

```bash
python data_pipeline/run_once.py                 # full pipeline run
python data_pipeline/exporter/build_graph.py     # rebuild from base graph + last output, no crawl
python -m pytest tests/                          # the suite; every gate is pinned in both directions
python -m pytest tests/test_build_graph.py -v
python scripts/validate_published_graph.py       # publish gate on output/graph.json, exit 1 on violation
python scripts/regenerate_published_graph.py     # rebuild output/ offline from the base graph + published anchor, repair the queue, then gate
python scripts/repair_review_queue.py --dry-run  # what the queue repair would drop, and why
python scripts/probe_treasury_rows.py            # which Treasury lines match a node; read-only, drives TREASURY_ROW_ALIASES
python scripts/probe_post_titles.py --dry-run    # which post titles an org's own page carries; read-only, drives CURATION.md §8
python scripts/rename_templated_post_titles.py --dry-run  # templated cabinet titles -> the title an official document gives them
python scripts/probe_candidate_pages.py --uncovered        # organisations with no candidate page; read-only, no fetch
python scripts/rename_units_to_official_wording.py --dry-run  # organisations -> the wording their own page carries; drives CURATION.md §9
python scripts/add_curated_nodes.py --dry-run     # add a unit the graph lacks, licensed by the statement or a page; CURATION.md §1
python scripts/mark_superseded_units.py --dry-run # mark a unit the government has replaced; nothing is ever deleted
python scripts/probe_network_access.py           # what this session can reach now, and whether a 403 was the proxy or the host
python scripts/derive_pay_evidence.py --dry-run  # the salary table joined to the archive's levels; writes nothing
python scripts/derive_judicial_pay_evidence.py --dry-run    # uscourts.gov's own compensation table; writes nothing
python scripts/derive_congressional_pay_evidence.py --dry-run  # senate.gov's own salary schedule; writes nothing
python scripts/derive_whitehouse_pay_evidence.py --dry-run     # the White House Office's statutory staff roster; writes nothing
python scripts/expand_whitehouse_office.py --dry-run           # what the roster would add to the curated WHO subtree; writes nothing
python scripts/derive_usaspending_evidence.py --dry-run   # File A gross outlays for the crosswalk's name-equal keys; writes nothing
python scripts/derive_net_cost_evidence.py --dry-run       # Treasury's audited Statement of Net Cost; writes nothing
python scripts/derive_omb_budget_evidence.py --dry-run     # OMB's Public Budget Database, last COMPLETED year only; writes nothing
python scripts/verify_base_graph.py --dry-run    # existence checks planned against official pages; no fetch, no write
python scripts/verify_base_graph.py              # run them; writes data/verification/evidence.json only (needs the .gov hosts)
node scripts/frontend_smoke.mjs                  # headless-browser check of the page's claims (needs playwright-core + three locally)
python -m http.server 8080                       # serve the site locally
python data_expansion/extract_and_expand.py      # regenerate the corporate overlay (needs `requests`, SEC network)
```

Environment variables actually read (all optional):

```
PIPELINE_FISCAL_YEAR              default: the current federal fiscal year (FY N starts 1 Oct N-1); USASpending window
PIPELINE_LOBBYING_YEAR            default: current calendar year (LDA filings are calendar-year)
PIPELINE_HTTP_TIMEOUT             default: 30; every crawler (Wikidata uses max(this, 45))
PIPELINE_PROMOTION_THRESHOLD      default: 0.7
PIPELINE_USASPENDING_AGENCIES     default: 20
PIPELINE_USASPENDING_AWARDS       default: 25
PIPELINE_WIKIDATA_HIERARCHY_LIMIT default: 500
PIPELINE_WIKIDATA_HOLDER_LIMIT    default: 250
PIPELINE_WIKIDATA_SUBUNIT_LIMIT   default: 500
PIPELINE_LOBBYING_PAGES           default: 5
PIPELINE_LOBBYING_PAGE_SIZE       default: 50
PIPELINE_OFFICIAL_DIRECTORY_LIMIT default: 150
PIPELINE_FEDERAL_REGISTER_PAGES   default: 3
PIPELINE_FEDERAL_REGISTER_PAGE_SIZE default: 100
PIPELINE_RUN_ONCE                 "1" (default) runs once; anything else loops daily (scheduler/nightly_update.py)
PIPELINE_ENABLE_TEMPLATE_LEADERSHIP "1" adds five template positions under every office to the review queue; off by default
BUREAUCRACY_PIPELINE_UA           User-Agent sent by the crawlers
LDA_API_KEY                       Senate LDA API key (lobbying crawler)
```

## Architecture

Two halves that communicate only through committed JSON in `output/`.

### Python pipeline (`data_pipeline/`)

- `run_pipeline.py` orchestrates. Every fetch stage runs under `safe_stage`;
  a failure is recorded in `stage_errors`, never raised. Two guards decide
  whether the run may overwrite `output/`: `all_fetch_stages_failed` (every
  stage errored or returned nothing) and `cost_basis_missing` (no payload
  carried a Treasury `budgetSummary` while the export gate is on). Either one
  writes a stats file with `publication_blocked: true` and leaves the outputs
  untouched; `main()` exits 1.
- `crawler/` — `treasury_outlays.py` (FiscalData MTS table 5; fetches the
  latest statement regardless of fiscal year; produces the `budgetSummary`
  the whole cost cascade hangs on, plus per-agency `outlayRows` that the
  exporter stamps onto the nodes they name; registered first),
  `usaspending.py`, `wikidata.py` (US-scoped SPARQL), `lobbying.py` (Senate
  LDA), `federal_register.py`, `official_directory.py`, `common.py` (HTTP
  helpers). Crawlers degrade to empty results on network failure.
- `processors/normalize_nodes.py` — `NodeRegistry` dedups and merges nodes,
  recomputes confidence in `verify_node_sources`, and scores the proof fields
  (`existsProven`, `proofSourceCount`, ...) off official `.gov/.mil` sources.
  `normalize_edges.py` — `EdgeRegistry` (an unknown type is kept as
  `related_to`, never rewritten to `manages`). `budget_reconciliation.py` —
  the curated budget notes against the Treasury lines on the nodes; run by
  `build_graph`, written to `output/budget_reconciliation.json` (untracked),
  summary in the validity report and stats.
- `discovery/source_discovery.py` — builds candidate nodes from the discovery
  crawlers, promotes candidates at or above the threshold, and the run then
  writes `output/candidate_nodes.json` (the review queue) without the
  records it promoted or merged. Federal Register and
  advisory-committee hosts are classified before the generic `.gov` rule so a
  single notice cannot clear the promotion threshold on its own.
- `validators/node_requirements.py` and `validators/cost_validator.py` — the
  export gate. Nodes whose id is in the base graph are trusted by id (not by
  type: the old 8-name type allowlist excluded 97% of curated nodes).
- `exporter/build_graph.py` — reloads the previously published graph as a
  payload (so runs accumulate; base nodes without crawler provenance are
  not re-imported, the base file supplies them), merges, builds the tree from
  `data/federal_gov_complete_1.json`, `annotate_proof_tree`,
  `drop_duplicate_child_rollups`, `annotate_resolved_costs`, then the gate
  (`NodeRequirements` ∩ `CostValidator` → `prune_tree_to_allowed_ids`),
  `resolve_root_orphans`, and writes `graph.json`, `expanded_nodes.json`,
  `expanded_edges.json`, `node_validity_report.json`.

### Cost cascade (`annotate_resolved_costs`)

Root gets `cost_status: root_total` anchored to
`budgetSummary.government_total_outlay_amount`. Children with an official
`rollup_total_amount` get `official`. Everything else is `allocated`, split
among siblings by `get_node_weight`: the first non-zero of `annual_budget`,
`budget`, `direct_outlay_amount` (basis `*_weight`), else a parseable
`employees` count (`employee_weight`), else subtree size
(`subtree_weight`). Weights are only summed within one unit. When siblings
disagree, the best-evidenced class present wins (dollars, then headcount,
then size) and a sibling that lacks it gets an implied weight: the
geometric mean of the reported siblings' per-node rates times its own
subtree size, stamped `implied_budget_weight` / `implied_employee_weight`
(the parent carries `child_cost_basis_implied`). A share that rounds below
one cent is published as `unavailable` with `cost_validation:
allocation_below_precision`, never as $0. Treasury outlay lines applied to
a node make it `official` (`costVerificationStatus: verified`, the
FiscalData URL in `sourceUrls`); those are the only measured costs besides
the root, and the gate checks it.

**The statement's own arithmetic, since 2026-09-08.** Table 5 prints each
agency as a section: lines beneath a header, the section's receipts-type
lines (proprietary receipts from the public, intrabudgetary transactions,
offsetting governmental receipts), and a `Total--` line that is the net
figure. The identity the statement itself prints — every top-level section
total, plus the government-wide "Undistributed Offsetting Receipts", summing
to Total Outlays — holds to the cent on the 2026-07-31 statement
(`tests/fixtures/mts_table5_latest.json`, the API response verbatim;
`SectionTree.identity`). The exporter publishes it as it is:

- Every matched unit publishes the Treasury's own net figure, `official`,
  exact. Nothing is capped: `summarize_scaled_official` reports zero
  top-most nodes, where it reported 33 nodes and $262.2B withheld the day
  before.
- Each netted section's receipts are one explicit child of the unit whose
  total they reduce: `type: Treasury accounting line`, `synthetic:
  treasury_receipts`, a negative measured amount, the component lines by
  name and amount in `treasury_component_rows`, and a generated
  description (`descriptionSource: generated_from_treasury_lines`). With
  it, a unit's lines, its receipts and the estimate for its unlined
  children sum to its published total; CMS's $2.33T sits inside HHS's
  $1.72T beside −$749B of Medicare premiums and transfers, and the gate
  bounds a child by the parent less its negative lines.
- The government-wide receipts (−$343.3B) sit beside the three branches as
  `treasury-undistributed-offsetting-receipts`, the one node the root may
  carry besides them; the exporter's root guard and the gate name it.
- A negative line is published as the Treasury prints it — the Mint, the
  FDIC, the Executive Office of the President (−$1.24B) — and a grouping
  whose measured members net below zero publishes a negative estimate,
  stamped `measured_net_beneath`, rather than a positive one nothing
  beneath it supports. Floors are signed for the same reason. Nothing can
  be apportioned from a negative figure: such a unit's unlined children are
  `unavailable` with `cost_validation: treasury_pool_negative`, and a unit
  whose lines exceed its net total by a negative line the graph has no
  node for declares the exact excess in `treasury_pool_negative`, which the
  gate allows to the cent and nothing else.
- A line the Treasury files under a different section from the node's
  ancestors (the Tax Court, printed under the Legislative Branch, curated
  under the judiciary) is measured, `treasury_external_section: true`,
  outside its parent's arithmetic, and the panel says so.
- A netted unit with no unlined child carries `treasury_unapportioned`: the
  statement's lines this graph has no node for, going nowhere.
- Rows inside a receipts-type subtree ("Department of the Navy" under
  "Proprietary Receipts from the Public:") are receipts *of* an agency,
  never matched to a node (`receipts_component_ids`).

The whole construction is gated on the identity. When it fails for the
rows in hand — or no anchor came with them — no receipts line is created,
`treasury_netting.reason` says why, and the older rule applies: negatives
set aside, floors paid from the remainder, and when the direct lines alone
exceed a parent every line beneath takes one haircut and publishes as
`scaled_official`, which the UI labels an estimate (a fully even haircut
was tried and rejected: at the root it cut the two section totals, net
figures that fit the anchor, to 96%). The crawler keeps every row of the
statement, headers included (`is_header`, `classification_id`,
`parent_id`), so the tree can be rebuilt; a build handed no statement
carries the receipts lines forward with the other Treasury lines, and a
fresh statement replaces them (`remove_synthetic_receipts`), so re-feeding
the published graph never duplicates one.
`cost_validation: estimated_from_parent` and
`costVerificationStatus: unverified` on every allocated node.

**A post is not a budget unit (since 2026-09-14).** The measured path had
always refused to land a Treasury line on a position — `is_post_node` /
`NON_ORGANISATION_TYPE_KEYWORDS`, on the grounds that a post is not the thing
that spent the money — but the *estimated* path never carried that rule, so
an apportioned share reached **4,232 of the 4,382 position nodes**, 630 of
them above $1B, with every officer of the Centers for Medicare & Medicaid
Services published at $194.0B each. An apportioned share is the same claim
with an "≈" in front of it, and a post's share of an agency's outlays is not
a quantity that exists. A node whose type matches `POST_TYPE_KEYWORDS`
(position, role, office holder) is now published `unavailable` with
`cost_validation: post_is_not_a_budget_unit`, and the panel says why.

Weighting is deliberately left alone: a post still takes its weight in the
sibling split, so **no organisation's estimate moved** — which is what made it
safe to apply to 4,232 nodes at once, and is pinned in both directions by
`tests/test_cost_cascade_units.PostsAreNotBudgetUnitsTests`. A parent's shown
children can now sum to less than the parent, which is the honest reading:
the remainder is not apportioned to anybody. Allocated nodes fell from 4,885
to 653, and "with a cost" from 5,021 to 789.

**The template half, since 2026-09-15 — and a correction.** The note above
used BSEE drawing a larger share than its measured sibling BOEM as the
reason to do this. Checked directly against the data while building it:
that example was wrong. Neither BSEE nor BOEM carries any templated title —
both have bespoke ones (Regional Director — Gulf of Mexico, Petroleum
Engineer, ...) — and both are weighted by their own `employees` figure, not
by subtree size. The claim was inherited from an external review that used
"template" to mean "a shallow six-node sketch", which BSEE's subtree is, but
being shallow and being *stamped* — the same titles copied verbatim across
unrelated organisations — are different problems; this section fixes the
second one.

The real, stamped pattern is data-verified, not guessed: `General Counsel`,
`Chief Financial Officer`, `Inspector General`, `Chief of Staff` and `Chief
Information Officer` recur (92, 81, 80, 71 and 47 times) across 76
organisations, 46 of them with nothing else beneath them at all — DIA, NSA,
NGA, NRO, DARPA, DLA, TVA, NCUA, PBGC among them. A second, larger variant of
the same stamp sits under every one of the 15 cabinet departments: six more
titles — `Executive Secretary`, `Deputy Inspector General`, `Deputy General
Counsel`, `Deputy CFO / Controller`, `Deputy CIO`, `Diversity & Inclusion
Officer` — occur at *precisely* those 15 organisations and no others, which
is what makes it a stamp and not independent curation: no department was
individually assessed as needing a Diversity & Inclusion Officer, the same
16-line office was written under all of them. `Deputy Administrator` and
`Director of Human Resources` were checked and excluded from the list: the
first always pairs with a real, org-specific `Administrator` title rather
than standing alone as boilerplate, and the second's occurrences span
legislative support offices and NASA field centers with no shared parent
pattern — neither is evidenced as the same mechanical copy the titles above
are.

`GENERIC_ADMINISTRATIVE_TITLES` in `build_graph.py` is that list, and
`compute_subtree_sizes` now gives a Position node matching it — by exact
string equality, never a substring, so `Inspector General (DoJ IG covers
FBI)` and `Chief of Staff of the Air Force` keep counting — no weight toward
its ancestors' counted size. Real structure beneath a stamped title, should
one ever be curated, still counts; only 46 of the 76 organisations have
nothing else, and the other 30 keep every bit of their real substructure.
No marker distinguished these nodes before this — a full key scan of the
curated file found none — so this is a name-based, data-verified detector,
not a flag some earlier stage forgot to set.

Verified on the real graph, not asserted: **`Defense Agencies & Field
Activities`**, which nests NSA/DIA/DARPA/DLA and a dozen more — each padded
with the same five titles — drew **$258.7B** of DoD's pool before this
change, more than `Military Departments & Services` itself ($194.6B). After:
**$124.3B**, with the difference moving to Joint Chiefs, Military
Departments and the Unified Combatant Commands — the parts of DoD with real,
individually curated structure, pinned in
`tests/test_cost_cascade_units.PublishedGraphAdminStampWeightingTests`. 418
of 813 organisation nodes changed. BSEE moved slightly too — not because it
carries the stamp (it does not), but because BLM's own bare `Deputy
Director` is in the excluded list, which shifts the geometric-mean rate BSEE
inherits through `resolve_sibling_weights`; BOEM, anchored to its own
Treasury line, did not move at all.

**That distortion, diagnosed and fixed on 2026-09-19.** This section used to
end by noting that Treasury's `FinCEN`, `OFAC` and `TTB` published implausible
hundred-billion figures and leaving it there. The cause was one missing node.
Table 5 reports **$1.267 trillion** under the Department of the Treasury's
section as **Interest on the Public Debt**, no node carried it, and so the
cascade treated it as money to apportion among Treasury's unlined bureaus —
by headcount, since that is the best evidence those siblings carry. Every one
of the four was exactly its curated headcount times a single rate of
$574,269,987.70 per employee:

    TTB     ~500 staff   $287,134,993,850  ->     $268,630,790
    FinCEN  ~350 staff   $200,994,495,695  ->     $188,041,553
    OFAC    ~250 staff   $143,567,496,925  ->     $134,315,395
    OFR     ~200 staff   $114,853,997,540  ->     $107,452,316

The Alcohol & Tobacco Tax & Trade Bureau was published at more than the
measured IRS. `docs/EXACT_NODE_COSTS.md` had listed this line among the 17
left deliberately unmatched as "Treasury's own funds and groupings", and
leaving it unmatched is precisely what caused this: money reported under a
heading that names no organisation does not stop existing, it gets divided
among organisations.

The fix is one curated node, added by `scripts/add_curated_nodes.py` under the
`treasury_statement_line` licence and typed **`Treasury accounting line`** —
the same type the exporter gives the receipts lines it creates, so the node
does not claim to be a unit of government, and `colour_treasury_lines` draws
it as a line rather than as an office. (That guard keyed on `synthetic` alone
and now keys on the type as well, which is the same defect that drew all 25
receipts lines as Position/Office nodes until 2026-09-18.) **Blast radius,
measured rather than asserted: 53 of 5,426 nodes changed**, four of them the
bureaus above and the rest by rounding through the cascade.

Still open: apportionment by subtree size is still weak wherever a sibling
group has no dollar or headcount evidence and no stamp to exclude either —
most bureaus in this graph bottom out directly in Position leaves with no
deeper structure, so raw node count is a compressed, noisy proxy for real
size even when every title in it was independently curated. Discounting
curation depth itself, rather than just the identifiably mechanical stamp,
would move many more organisations' figures on a much less bounded
justification, and is not attempted here. The period of
the anchor lives on the root's `__budgetSummary` (`amount_kind`,
`record_date`, `label`) — the UI reads it there and applies it to every
figure.

### Existence evidence (`data_pipeline/verification/`, `data/verification/`)

The curated file carries no sources. `scripts/verify_base_graph.py` fetches
each organisation's candidate official page (`official_sites.json`: its own,
else an ancestor's at most `--inherit-depth` levels up, default 1) and looks
for the node's name **as a label of its own** — a heading, a link, a list
item whose text is the name. Not a substring of the page: an earlier version
searched the whole page as one canonicalised string and an adversarial review
found three ways that manufactures confirmations (a one-word name like
"Energy" matching prose; "Office of Science" matching inside "Office of
Science and Technology Policy"; a phrase spanning two DOM elements). Label
equality closes all three. `LabelParser` keeps nav, header, title and footer
— the directory crawler's parser skips them, which is where agencies list
their offices. It reads `title`/`aria-label` only off elements that render:
the 2026-09-06 run found `<link rel="alternate" title="Federal Maritime
Commission » Feed">` in the head of www.fmc.gov and www.sba.gov, which the
separator split turns into exactly the unit's name — a label out of markup
no visitor sees. No published confirmation rested on it; both pages also
carry a real heading.

Five statuses in `evidence.json`, and only the first two are applied:

- `confirmed` — a fragment is the name. Gives `sourceUrls`, `sourceTypes:
  official_site`, `lastVerified`, and `verificationMethod`, which is
  `name_labelled_on_own_official_page` or `..._parent_official_page` — a
  different claim, and the panel says which.
- `not_found` — the unit's **own** page was read and its name is not on it
  in any form. Gives `lastVerified` + `verificationFailure` only, and only if
  no other route gave the node a source. The site shows checked-and-failed,
  worded as "does not name it as a heading or link" — what was actually
  tested.
- `inconclusive` — nothing was learned, for one of two reasons carried in
  `reason`. `only_an_ancestor_page_was_read`: a parent's About page is not
  obliged to list its children. `named_on_the_page_but_not_as_a_label`: the
  unit's own page does name it, in prose rather than as a heading or link —
  `cia.gov/about` says "Central Intelligence Agency" in a sentence, and the
  first live run published "its official page did not name it" about the CIA
  on the strength of that. `name_appears_unlabelled` makes that distinction
  with a deliberately loose match that joins fragments; it is used ONLY to
  withhold a negative claim, never to make a positive one, so it can lower
  the confirmation count and never raise it. Applies nothing either way.
- `fetch_failed` — no page was read: blocked network, 404, robots.txt
  disallow, a 200 with under 400 characters of readable text (a JS shell or
  a bot challenge). It applies no source, no date and no failed check — it
  is a fact about the network, not the unit — but **since 2026-09-20 it
  publishes that fact**: `verificationUnread` carries a closed `kind`
  (`host_refuses_crawler`, `robots_unreachable`, `page_not_found`,
  `page_below_readable_floor`, `site_failing`, `network_error`, `other`)
  classified from the record's own reason, the URL, its host, the date and
  the attempt count, and the panel prints one sentence per kind where it
  said "Not yet verified" — which on ~1,000 nodes read as though nobody had
  tried. A refusal at the sandbox's own proxy ("Tunnel connection failed")
  is a fact about this environment and is never published. The field is
  evidence-owned, kept in the viewer copy, and gated: it may sit beside a
  directory or Manual method (a different document) and beside a list
  negative, never beside a page method or a `not_found`, both of which mean
  a page WAS read. 96 organisations carried it the day it landed, 56 of
  them because the host refuses the crawler outright.
- `not_checkable` — the curated name could never be evidence: a count label
  ("Individual Senator Offices (100)") or a name too generic to distinguish
  anything ("Energy", "Defense", 16). Never fetched.

  **The count-label floor refused any name containing a digit until
  2026-09-18**, which is a claim about the NAME — that no page could ever
  carry it — and it was false of **268 nodes**. The eleven `U.S. Court of
  Appeals for the Nth Circuit` have real pages on `caN.uscourts.gov`, four of
  them already queued, and the verifier had never fetched one; nor nineteen
  `VISN N` networks whose number `department.va.gov` itself prints, nor `K-9
  Unit`, the Joint Staff's `J3`, `Army G-2`, `OPNAV N2/N6`, `AF/A5`. The first
  live probe pass surfaced it — an agent chasing VISN 1 found the rule, not a
  missing URL. `states_a_count_in_prose` replaces it: a cardinal number
  followed, inside the same dash-delimited segment of the name, by a plural
  word. "10 Regions" counts regions; "VISN 1 — New England" counts nothing.
  Segment-wise because this graph's convention is `<name> — <qualifier>`, so a
  count and the thing it counts always sit on the same side of the dash.
  Checked against every digit-bearing name in the curated file rather than
  reasoned about: **56 still refused, every one a real count** ("Port
  Director — 328 Ports of Entry", "All 94 District Courts"); **212 freed, none
  of them**. A committed test had asserted "VISN 1 — New England" IS a count
  label; it is not, and the correction is the same distinction the nomination
  vocabulary draws — "this name could never be evidence" and "the page does
  not carry the whole curated name" are different claims with different fixes.

**Committees, with the graph's type words set aside (since 2026-09-13).**
The graph names every committee with a type word in front — "House
Committee on Armed Services", "Subcommittee on Livestock, Dairy &
Poultry" — and the chambers' sites label the same bodies without it. Label
equality refused 38 of the 78 `not_found` records for that prefix and
nothing else. `committee_core_key` folds a leading chamber word, one or two
"…Committee on" prefixes and a trailing "Committee"/"Subcommittee" on
*both* sides, and the fold is granted only by the node's type
(`COMMITTEE_TYPES`: committee, subcommittee — so "Office of Science" can
never match "Science") and only when two or more tokens remain
("Subcommittee on Readiness" is not confirmed by the word "Readiness";
"Senate Committee on Select Committee on Ethics" folds to one token and
stays unconfirmed). Equality is tried first on every fragment, so a page
carrying the full name is never recorded as folded; a folded match carries
`matchRule: committee_scaffolding_folded` in the record and the exporter
publishes `verificationMatchRule` with `verificationMatchedText` — the
label as the page prints it — and `placementMatchRule` beside
`placementMatchedText`, so the panel says "as 'Livestock, Dairy, and
Poultry' (the graph's 'Committee on' / 'Subcommittee on' prefix set
aside)" and never the plain claim. The rename guard
(`evidence_names_this_node`) takes the node, not just its name: a committee
re-typed as an office loses everything it earned as a committee. The gate
refuses the rule on any other type, without the label, under a method that
read no page, or with a label whose core is not the name's, and mirrors the
fold stdlib-only (`tests/test_committee_fold.py` pins the two together).
First run: 53 confirmed and 48 placed by the fold; `not_found` 78 → 46,
confirmed records 182 → 235, nothing previously confirmed changed.

**Placement — evidence for the edge, not the node.** A hierarchy is the
site's central assertion, and until 2026-09-06 nothing had checked a single
parent→child edge. The verifier's placement pass takes every organisation
whose parent has an official page (259 edges under 36 parents at the time)
and asks whether the parent's page names the child as a label. `listed` is
recorded with the URL, the matched text and the parent it was checked
against, and the exporter stamps `placementVerified: true`,
`placementUrl`, `placementVerifiedAt`, `placementParentId`,
`placementMatchedText` (the label as it appears on the page) and
`placementMethod: name_labelled_on_parent_official_page` — but only when
that parent is the one the published tree actually gives the node and the
label still names the node as it is now called, so a re-parenting or a
rename in the curated file can never inherit evidence for a different edge
or a different name; the gate checks both, plus the date and the method.
`not_listed` is recorded with `urlsRead` — only the pages actually read,
never one that 404ed — and publishes `placementVerified: false`, which
claims nothing: a department's About page is not obliged to list every
bureau. An unreadable parent page records nothing at all. A confirmation
already made on the parent's page (`method` parent, `siteFrom` == parent)
is the same fetch and the same fact and counts as placement without being
fetched again — unless an explicit block for that parent says `not_listed`,
which wins whichever is older: a retraction found by re-reading the very
page the claim rested on must reach the site. A node whose parent has no
entry in `official_sites.json` gets `placementCheckable: false` ("could not
be checked", most of the graph: the fifteen departments sit under a curated
"Cabinet" grouping) rather than "no evidence recorded", and the gate reports
the three counts separately. A record the verifier wrote for the edge alone
carries `status: placement_only`; the existence pass replaces such a record
and carries the block along. The claim the site makes is exactly "the
parent's official page lists it" — not "reports to", which a page listing
partner agencies could not support. The parser tags every fragment with its region — `content`, or
`navigation` for the site-wide nav, header, banner and footer — and the
record carries `matchedIn`; the exporter stamps `placementMatchedIn` /
`verificationMatchedIn` and the panel says "in its site-wide navigation"
when that is where the label sat, because a listing in Treasury's About
mega-menu holds for every page on home.treasury.gov equally (the first
live run's DOI, DOL, Treasury, NSF and NASA listings were all of this
kind). A page counts as *read* only when it carries 400+ characters of
text outside that chrome: www.hud.gov/about served a .gov banner and a
footer address around no body, cleared the old whole-page floor on
boilerplate, and was recorded as "checked and not listed" fifteen times.
A positive label anywhere a visitor can see it still stands — the floor
governs negatives only. A logo's alt text or an SVG title is never a
label, but it does withhold "its own page does not name it": cia.gov/about
and epa.gov/aboutepa name the agency in the logo and nowhere else
readable, and both were published as not found. Known limitation, still
documented rather than fixed: within the chrome the standard is host-blind
inside `.gov` — a footer link to an unrelated agency would count; the
sites file is what scopes it, one page per parent.

**Posts, on their own organisation's page (since 2026-09-15).** 4,604 of
the 5,392 curated nodes are positions and **not one of them carried evidence
of any kind** — no record in `evidence.json`, `directory_evidence.json` or
`official_sites.json`, so the Secretary of Defense and the Speaker of the
House read "no source recorded" beside a confirmed Department of Defense.
That was not a coverage gap the crawl had not got to; it was total and by
construction. `verify_base_graph.py` has always had `--include-positions`
and it had **never been run**; `directories.py` and `headcounts.py` filter
`"position" in type` out of their candidate pools; and `nominate.py` rejects
a position outright with "pages are nominated for organisations only".

That last refusal is correct and stays: a post has no page of its own and
never will. The thing with a page is the **organisation that carries the
post**, and the verifier already fetches it, for the organisation itself.
So the marginal cost of checking a post is one string comparison against
fragments already parsed — 2,731 of the 4,604 positions sit under a parent
that has a candidate page, and the whole run adds no fetch that was not
already being made.

Cheap is not the same as honest, so four things narrow the claim to what was
read, each pinned in both directions by `tests/test_position_evidence.py`:

- **The method says whose page it was.** `METHOD_POST_ON_ORG_PAGE`
  (`name_labelled_on_its_organisations_official_page`) rather than the
  parent-page method, because "a department's page lists a bureau" and "a
  department's page names its own Secretary" are different claims and the
  panel prints a different sentence for each. The distinct string also
  settles the placement question *structurally*: `placement_from_record`
  promotes a confirmation into placement evidence only under
  `METHOD_PARENT_PAGE`, so a post cannot acquire one by anybody forgetting.
- **No placement claim, ever.** For an organisation, existence usually comes
  off its own page and placement off its parent's — two fetches, two facts.
  For a post there is only one page, so publishing both would present a
  single observation as two corroborating findings. `verify_placement`
  returns `None` for a post, the exporter skips the placement pass for one
  (`placements_refused_post`), the gate refuses a page-derived
  `placementMethod` on a post, and the runner does not even queue the fetch
  (2,509 skipped as `placement_not_applicable_to_a_post`). A placement from
  a *different document* is untouched: OPM's PLUM archive files 126
  positions under an organisation, which is a second source and a real claim.
- **A bare job title is never checked.** `uncheckable_reason(..., is_post=True)`
  refuses a canonical key of fewer than two tokens, whatever the word. The
  existing floor refuses an organisation's one-word name only when it is
  short or on `GENERIC_SINGLE_TOKENS`; a post needs more, because scoping to
  one organisation's page supplies the context a *qualified* title lacks
  ("blm.gov labels 'Deputy Director'" does say BLM has one) and supplies
  nothing at all to a single common noun. 118 nodes are refused this way —
  `Hydrologist`, `Warden (×122 facilities)`, `Director (×3)`,
  `U.S. Attorney (×94, appointed by President)`, `Specialist (×multiple)` —
  and the parenthetical never counts toward the two, since
  `canonical_name_key` drops it. The floor is granted by the node's type
  (`uncheckable_reason_for_node`), the same way the committee fold is, so a
  post re-typed as an office loses it and an office re-typed as a post gains it.
- **Site-wide navigation cannot confirm a post.** This file already records
  that inside the chrome the standard is host-blind within `.gov` — a footer
  link to an unrelated agency would count. For an organisation's name that is
  a tolerable edge (agencies do not put other agencies in their own mega-menus
  by accident) and it is load-bearing: the first live run's DOI, DOL, Treasury,
  NSF and NASA confirmations were *all* mega-menu matches. For a job title it
  is the opposite. `Inspector General`, `General Counsel` and `Chief
  Information Officer` are standard site furniture, recurring across 76
  organisations here as a copied stamp, so a match in one department's footer
  would confirm a bureau's own post from markup that says nothing about the
  bureau. A post is confirmed from `REGION_CONTENT` only; a title found in the
  chrome is recorded as `post_title_only_in_site_navigation` and the record
  stays `inconclusive` — not `not_found`, which would be false, and not a
  confirmation, which would rest on furniture. The organisation path is
  unchanged, and a test asserts it stays unchanged.

The label is published (`verificationMatchedText`) for a stronger reason than
a committee's is: `General Counsel` is the name of **84** nodes in this graph
and `Inspector General` of **72**, so the page it was found on and the exact
words on it are the only things tying a confirmation to this post rather than
another's. The gate requires all four — the node is a post, the label is
quoted, the label still names the node, and `verificationMatchedIn` is
`content` — and `tests/test_position_evidence.py` corrupts each one in turn
and asserts the gate rejects it. Note what a confirmation is worth: one
official URL scores 0.4 + 0.3 in `verify_node_sources`, so a post confirmed on
one page publishes **`partial`, not `verified`**. That is the arithmetic that
published 29 positions as verified off a five-row pay table on 2026-09-11, and
it is left exactly where it is.

**A live over-claim this work surfaced, and fixed.** The new gate check
failed on the *existing* published graph: 126 positions already carried
`placementVerified`, all from the PLUM archive. The gate's own coverage line
scopes numerator and denominator to organisations and reported "209 of 812";
`describeProvenance` in `js/ui.js` scoped only the denominator, so the site
told every visitor "**335** of 812 organisation placements evidenced" —
counting positions in a total whose label says organisation. The numerator is
now scoped with the denominator, and `scripts/frontend_smoke.mjs` recomputes
the figure from the served graph and asserts the page agrees with it.

**The first live run (2026-09-15), and what the strict rules actually cost.**
2,858 nodes planned, 452 distinct pages: **20 positions confirmed**, all from
page content, 16 published `partial` and 4 `verified` — the 4 because two
official pages each named them, which is the existing confidence arithmetic
(0.4 + 0.3 for one official URL is 0.70; a second adds 0.1) and not a rule
this work changed. Coverage is 20 of 4,604, **0.4%**, reported on its own
line by the gate so it cannot be read as anything grander. Spot-checked
against the pages: VA's Under Secretary for Health on va.gov/health, NASA's
Deputy Administrator and Associate Administrator on nasa.gov/organization,
EPA's Inspector General on epa.gov/aboutepa. 1,021 positions came back
`fetch_failed` — a fact about which hosts answer `robots.txt` — and 1,468
`inconclusive`, which is what an organisation's page not naming a post means.
A post can never be `not_found`: `is_own_page` is false for every post, so
the negative branch that would say "its own page does not name it" is
unreachable, and an org page is not obliged to list its staff.

**The navigation rule paid for itself, measurably.** 27 titles were found in
site chrome and refused — more than the 20 confirmed, so this is not a
free rule. **18 of the 27 were `Inspector General`, in the footer of 18
different agencies**: DOI, DOE, CIA, SBA, NSF, OPM, NLRB, FLRA, FEC, NCUA,
NRC, CPSC, FDIC, CFTC, FMC and more. That is a stamped node on the graph's
side being confirmed by stamped furniture on the page's side — every `.gov`
footer carries an Inspector General link the way it carries FOIA and No FEAR
Act — and it would have manufactured 18 confirmations out of one fact about
federal web conventions. The rule does cost real evidence: the Secretary of
the Senate, the Clerk of the House and two Circuit Executives are named only
in their sites' navigation and go unconfirmed. Trading those for the 18 is
the right way round, and it is recorded here as a measurement rather than a
preference.

**What the first run found, which was not a pipeline bug.** The most
recognisable posts in the government came back `inconclusive` — and not
because the pages are silent about them. **839 position nodes contain their
parent organisation's name verbatim**, and in 28 of them that template
produces a title no page will ever carry: every cabinet department except
Defense has a `Secretary of Department of <full department name>` node.
energy.gov labels "Secretary of Energy"; the graph says "Secretary of
Department of Energy (DOE)". justice.gov labels "The Attorney General"; the
graph says "Secretary of Department of Justice (DOJ)" — **an office that
does not exist.** Defense is the control case: it alone is curated as
"Secretary of Defense", and it is the only one whose title could ever have
matched.

That is curation, and it is now half fixed.
`scripts/probe_post_titles.py` is the read-only probe that found it — the
position analogue of `probe_treasury_rows.py`: it fetches an organisation's
page, says which curated post titles the page labels, and lists
office-looking labels on the page that no curated post matches. It writes
nothing and proposes rather than concludes.
`scripts/rename_templated_post_titles.py` then acts on it, and is the only
writer of these names (the curated file is never hand-edited). It is
idempotent and **renames nothing it cannot cite**: the replacement comes from
OPM's PLUM archive, or from the department's own page where the archive
carries only a bare "SECRETARY". The transform is used to *recognise* a
templated name, never to produce the replacement — dropping "Department of"
is right thirteen times and wrong once, and DHS proves it the other way,
since OPM's archive spells that post "SECRETARY OF THE DEPARTMENT OF HOMELAND
SECURITY", keeping the words the transform strips. A title naming only the
role is refused: the first dry run would have renamed three deputies to a
bare "Deputy Secretary", dropping the department and manufacturing exactly
the generic title the post floor exists to refuse.

**15 of the 28 renamed, and the payoff measured.** Re-verifying just those
nodes confirmed **5** against their departments' own pages — Secretary of
Labor, Secretary and Deputy Secretary of Energy, Secretary and Deputy
Secretary of Veterans Affairs — which was structurally impossible while they
were misnamed. Confirmed positions went **20 → 25**. The other 13 stay
templated because no source in hand names them: the archive files those heads
as a bare "SECRETARY", and seven of the fifteen department pages answer
`robots.txt` with 401/403. "Secretary of the Treasury" is not in doubt as a
fact; it is in doubt as something this repository can cite, and the rule that
a name must be cited is the rule that caught DOJ. `CURATION.md` §8 lists
every rename, every refusal and why.

The matcher was deliberately **not** widened to absorb the difference. A
"Department of" fold looks like the committee fold and is not: that one is
granted by the node's type, folds a closed set of words the chambers' own
sites demonstrably omit, and refuses a core under two tokens, whereas this
would let a curated name differ from a page's label in a way that changes
which office is meant — and the same looseness is what once let "Office of
Science" match "Office of Science and Technology Policy". The matcher stays
strict and the names get fixed where names are fixed.

The binding constraint is otherwise unchanged and is the same one
organisations face: **297 of 786 organisations have no candidate page at
all**, so no post beneath them can be reached either. Nominating org pages
(phase 1b) now moves both counts at once. (That figure was 611 when this
section was written and is not restated by hand any more: `python
scripts/nominate.py status --kind source` prints it. It moved to 305 on
2026-09-13 when the recheck and the brute-force pass took `official_sites.json`
from 185 entries to 483, and to 297 on 2026-09-18 when the probe pass closed
the rest — after which the blocker stopped being the URL and became the name,
which is what the section below is about.)

**Organisation names the pages do not carry (since 2026-09-19).** The post-title
work above has an exact analogue one level up, and it was the largest single
blocker left on verification coverage. For **181 organisations** the candidate
page was read, reads fine, and simply does not carry the name this graph uses —
so no other URL fixes them. `scripts/probe_candidate_pages.py` is the read-only
instrument (the organisation analogue of `probe_post_titles.py`: it runs the
verifier's own `find_label_region_rule` against a page and reports `labelled`,
`labelled-in-site-navigation`, `not-labelled` or `uncheckable`, in words that
are deliberately not the verifier's status strings, and writes nothing);
`--orphan-labels` reports unit-looking labels on the page matching no node,
which is where a proposed name comes from.

`data/curation/unit_renames.json` is the reviewed table and
`scripts/rename_units_to_official_wording.py` is its only writer — the third
sanctioned writer of the curated file, beside `rename_templated_post_titles.py`
and `expand_whitehouse_office.py`. The table is the same shape as
`TREASURY_ROW_ALIASES` and `USASPENDING_NAME_ALIASES`: a reviewed
identification with the basis written beside it, and re-checked against the
source rather than trusted. **The table proposes; the page decides** — every
row is re-fetched and re-tested with the verifier's own label test on every
run, under its robots policy, User-Agent and readable-text floor, so a row
cannot go stale silently and cannot be a hand-edit wearing a script's clothes.
A row is refused when the node no longer carries the name the row was written
against, when the page does not label the proposed name, when the only match is
in site-wide chrome and the row did not declare it, when the proposed name is a
no-op under `canonical_name_key`, when it is one token or on `GENERIC_NAMES`
(`Inspector General` names 72 nodes here and sits in every `.gov` footer), or
when it collides with a **sibling's** name. The collision rule is scoped to
siblings deliberately: the House and the Senate each name a subcommittee after
the appropriations bill it writes, so one name for two seats in two chambers is
what the chambers call them, and the cost — a source matched by name alone
refuses a name reaching two nodes — fails safe.

**69 renames applied, 39 proposals declined**, all recorded in `CURATION.md` §9.
Three are renames the agency states on its own page and the graph was simply
stale about: NREL is now DOE's **National Laboratory of the Rockies**, the Food
and Nutrition Service is USDA's **Food and Nutrition Administration**, and NSF's
EHR is the **Directorate for STEM Education**. Eight were the graph's own
`<ACRONYM> — <name>` typography, which no page carries; moving the acronym into
brackets keeps it and still confirms, because `canonical_name_key` drops
parentheticals. EPA's ten regions took EPA's arabic numbering *and* EPA's own
qualifier, because that parenthetical is never checked against anything and the
graph's own word would ride along unverified — which corrected Region 7 from
"Plains" to EPA's "Midwest". Five of the eleven numbered courts of appeals took
the ordinal spelled out, the family form kept; the other six label only a short
form (`Sixth Circuit`) and are left alone rather than breaking the convention
across thirteen siblings.

Renaming is not free and the cost was measured rather than assumed: the House
Clerk's list went 18 → 20 matched, FedScope 133 → 136 records and the PLUM
archive 126 → 129, while the Food and Nutrition Service **lost** both, since
OPM's files are from March 2025 and still carry the former name. Two
USAspending aliases were deleted rather than updated — after the rename USPTO
and USAGM reduce to the API's own keys, so those records apply by name equality
and are graded `verified` instead of being held at `partial` by an alias, an
upgrade the names earned rather than one an alias could buy. Refused and
recorded rather than applied: HUD's ten regions (the match needs the `HUD` that
keeps them apart from EPA's and Education's), NSF's divisions (`MPS Chemistry`
is the site's breadcrumb, not the unit's name), and every VISN — a case that was
asserted, retracted and then settled in one day, and is worth reading in full at
CURATION.md §10. Short version: one VA page says "comprises 5 Veterans Integrated
Service Networks" a few lines below its own list of eighteen, so it settles
nothing by itself; what settles it is a second VA host on a different system
(`digital.va.gov/rise/`, "5 VISN MAP" beside "18 HEALTH SERVICE AREA MAP", with a
staffing roster naming five Network Directors) and the fact that all eighteen old
slugs return **301** to the index while an invented slug returns **404**, which
makes their retirement an editorial act rather than a rendering quirk. The
eighteen are marked superseded and kept; five current networks are added beside
them. Twice in that sequence this repository asserted the parent carried
*nineteen* children as evidence of inconsistency; it carried eighteen, matching
its own name, and nobody had counted.

One defect in this repository's own rule surfaced and was fixed with it:
`states_a_count_in_prose` read "EPA Region 8 (Mountains and Plains)" as a count
of mountains and refused the name before any fetch. A bracket is a segment of
its own for the same reason the dash is; the fix changes the verdict on no name
in the curated file, and is pinned both ways.

**Units the graph had no node for at all (since 2026-09-19).** `CLAUDE.md`'s
"Known base-graph gaps" listed Table 5 lines whose unit this graph simply had no
node for — the Administration for Children and Families at $65.6B, the Corps of
Engineers, the Railroad Retirement Board, the General Services Administration and
a dozen more, together about **$95.5B** of measured outlays. No alias could reach
them, because an alias maps a line to a node and there was no node, and adding one
was recorded as "curation work, not pipeline work" since nothing was allowed to
write a new node.

`scripts/add_curated_nodes.py` is that writer, the fourth of the curated file, and
`data/curation/new_nodes.json` its reviewed table. A node is added only under a
licence named on the row and **verified on the run, not trusted**:
`treasury_statement_line` requires exactly one row of the CURRENT statement to
carry the name — with header rows and rows inside a receipts subtree removed
first, through `SectionTree.receipts_component_ids`, the exporter's own answer to
which rows name a unit rather than a receipt of one, so "exactly one" means what
it should; `official_page_label` requires the verifier's own label test to find
the name on an official page now. Refused before either: an id already present, a
parent that is not in the file, a name colliding with one of its own siblings, a
name under two tokens or on the generic list, and a name `uncheckable_reason`
says could never be evidence — there is no point creating a node the verifier can
never confirm. It only ever ADDS, and is idempotent.

**15 units added**, each placed as `CURATION.md` §1 had already reasoned, with the
statement's own section stamped on the node so a reviewer can see whether the
placement agrees with where the Treasury files it — and the export gate's
same-section rule is the backstop that refuses a line across sections rather than
publishing it. The gains were not confined to the cost: OPM's FedScope already
carried rows for several of these units and the PLUM archive already carried
positions under them, so the records landed the moment the node existed —
FedScope 136 → 145 and PLUM agencies 62 → 68, with no matcher change at all.

**26 units the Manual carries and this graph did not (since 2026-09-20).**
The Government Manual work above left a by-product: 95 of its 231 agency
entries reach no node by name. `CURATION.md` §13 recorded that list;
`government_manual_entry` is the licence that acts on it, and it is the third
`add_curated_nodes.py` accepts and **the only one that licenses the PLACEMENT
as well as the name**. A Treasury line and a page label each say a unit of some
name exists, and neither says what it sits under, so on those rows the parent
is the row author's assertion and nothing can check it. The Manual prints a
hierarchy, so the parent is checked: the entry must be the only one of that
name, and the Manual's own chain above it must reach the node the row proposes.

It licenses a **region, not a point**. The Manual says "Defense Agencies"; this
graph calls that grouping "Defense Agencies & Field Activities", so an exact
chain match would refuse a placement that is plainly right. A proposed parent
is accepted when it sits at or beneath a node the Manual's chain names — which
can never contradict the Manual — and the node records which of the two it was
(`manualPlacementAtAdd`), because "the Manual files it here" and "the Manual
files it somewhere above here" are different claims. Where it is the looser
one, the generated description says so in words.

**A guard the adversarial review found, which no licence had.** A unit the
Treasury reports JOINTLY with a unit that already has a node must not become a
node of its own. There is no Table 5 row for the Bureau of Indian Education;
there is one combined row, "Bureau of Indian Affairs and Bureau of Indian
Education", and the graph applies its measured $2.43bn to the existing Indian
Affairs node. A separate Education node would not add a measured cost — there
is no separate figure — it would insert an unlined sibling that takes an
apportioned share out of a pool the statement reports for the two together, so
a measured figure would quietly start being divided on no evidence.
`jointly_measured_names` reads those joint rows off the published graph
(offline, no network) and the writer refuses such a row naming the node that
already carries it. It applies to every licence, not only this one.

**Which 26, and how the other 22 were disposed of.** 48 candidates were
adjudicated twice — once to decide, once by a second agent instructed to
overturn — and the second pass did real work: it caught that a substring probe
for "ntis" matches 51 `Scientist` posts, that NOAA, NTIA, DARPA, NSA and FMCSA
are all already in the graph under an acronym, and the Indian Education case
above. The dispositions: **26 added**; 6 already present; 5 are the Manual's
own editorial scaffolding ("Bureaus", "Offices / Boards", "Defense Agencies",
"Joint Service Schools", "Federally Aided Corporations"), which this file
already refuses to treat as units the way it refuses Treasury's groupings; 3
are the civilian-department / uniformed-service distinction this file records
for the Army ("Department of the Navy" is not "U.S. Navy"); 4 are out of scope;
and 3 are left unsure rather than guessed. `CURATION.md` §13 carries each.

Of the 26, **19 sit exactly where the Manual's own chain puts them and 7 under
the looser "within" rule**, each saying so in its description. Three of them
were already in the discovery crawlers' review queue — Bureau of Industry and
Security, Office of Surface Mining Reclamation and Enforcement, Office of
Justice Programs — found independently from Federal Register and directory
sources and sitting unpromoted below the threshold; the queue repair dropped
exactly those three when the nodes landed. None of the 26 names collides with
any existing organisation, so no name-based matcher was made ambiguous by them.

**The gains were not confined to the tree**, the same way they were not when
the 15 Treasury units landed: OPM already held records for several of these
units and they applied the moment the nodes existed. FedScope sub-agency
matches went **86 → 104** and its published records **145 → 163**, with 18
fewer unmatched sub-agency rows, so 18 more organisations now carry an official
headcount. No matcher changed. 36 of the matched headcount nodes carry no
curated `employees` figure of their own against 18 before, which is the honest
state for a node whose whole basis is the Manual naming it.

The PLUM archive gained nothing published, and the distinction is worth
keeping: its matching report went from 68 agencies and 168 organisations to 69
and 180, but its **records stayed at 129**. The archive lists positions, and
these 26 nodes have no position children, so more of its organisations are now
reachable and none of its rows reached a new post. A matching count is not a
published claim.

The estimates move, and that is the honest consequence rather than a defect:
**118 of 5,427 existing nodes changed by more than 0.1%**, every one a sibling
of something added — the Department of Justice's eight litigating divisions
fall 11.1% each because five real DOJ units now share their parent's pool, and
`Defense Agencies & Field Activities` rises 9.6% because six were added
beneath it. Nothing measured moved.

**A unit the government has replaced (since 2026-09-19).** Governments
reorganise, and this file had no way to say so: a replaced unit either sat in the
tree as though it still existed, which is the site claiming something false, or
would have had to be deleted, which throws away a real record of what the
government used to be along with every source, cost and placement anybody earned
for it. **Nothing is ever deleted.** A node marked `lifecycle: superseded` keeps
its id, name, description, evidence and place in the tree, and gains
`supersededOn`, `supersededBy` and `supersededSource` (the page, its own words,
and the date they were read). The viewer hides it unless the reader ticks "also
show units the government has replaced" — the default view is the government as
it stands — and the panel then says what replaced it and quotes the page.

The cascade takes a superseded node out of the sibling weights **entirely**,
rather than merely denying it a share, and this is where it differs from the post
rule deliberately: a post keeps its weight because the organisation really is
that size, while a replaced unit is not there at all, and leaving it in the
denominator would divide a real pool by a phantom and quietly shrink every living
sibling's estimate. `compute_subtree_sizes` gives it and everything beneath it
zero for the same reason. `scripts/mark_superseded_units.py` is the only writer,
the fifth of the curated file, and it clears the four fields it owns before
applying the table, so deleting a row is a real withdrawal. A supersession is a
positive claim and needs a source that states it: the row quotes an official
page's own words and the run re-fetches that page and refuses the row unless the
quote is there now.

**The table ships empty, and the reason is the point.** The case it was built for
was the VA's Integrated Service Networks, and that case does not survive being
checked — see `CURATION.md` §10. Nineteen nodes were nearly restructured on one
true sentence.

**Directories — the government's own lists of itself.** The page method is
near its ceiling: 71 organisations have a page of their own, twelve of the
largest hosts refuse `robots.txt` and are refused in turn, 223 committees are
never checked, and 520 edges hang under curated groupings with no page. `data_pipeline/verification/directories.py` adds
a second, weaker, honestly-labelled kind of evidence from structured
official directories, the first being the Federal Register's agency
directory (`api/v1/agencies.json`: every agency that publishes in the
Register, with its parent and its own site). The directory is fetched
verbatim and committed (`tests/fixtures/directories/`, refreshed only by
re-fetching); `scripts/derive_directory_evidence.py` matches its entries
to the curated organisations by canonical name — with the one rule the
directory needs, "Energy Department" answering to "Department of Energy"
— one entry to one node or nothing, and writes
`data/verification/directory_evidence.json`, each record saying what the
directory lists: the name, the parent, the entry's page, dated by the
directory's fetch time. The exporter applies it after the page evidence,
beside a page claim and never over it: `verificationMethod:
listed_in_federal_register_agency_directory` only where no page method
exists, `directoryListing` always, and `placementMethod:
listed_under_parent_in_federal_register_agency_directory` only when the
directory's parent is the node the tree gives it. When the directory files
a unit under a different parent the node carries
`placementDirectoryDisagreement` and the panel says the two sources
disagree; nothing is resolved either way, and the gate reports the three
counts. A top-level directory entry (a department) claims nothing about
the curated grouping above it. Withdrawal is the page module's: every
field here is in `EVIDENCE_OWNED_FIELDS`, and the URL rides in
`evidenceUrls`. The second directory is the Senate's own committee list
(`data_pipeline/verification/congress.py`): one XML file per committee at
senate.gov/general/committee_membership/, naming the committee and each
subcommittee. Fetched verbatim (24 files, `tests/fixtures/directories/
senate/`), it is the *complete* list, so — unlike a page — absence is
evidence: a curated subcommittee its committee's file does not carry
publishes `verificationFailure: not_in_official_list` with
`verificationFailureSource` (the list, the committee, the date, the names
it does carry), and the panel says "checked against the Senate's official
committee list: it carries no unit of this name under <committee>"; the
current names the graph lacks go to CURATION.md, never fuzzy-matched.
**Two true negatives on one node: the complete list's wins.** The page
module runs first and stamps `not_found` when the committee's own
subcommittees page does not label the curated name; the list's absence
used to be refused for standing "beside a page's own failed check", so
the 2026-09-13 recheck — the first with the committee pages reachable —
silently swapped the stronger claim for the weaker one on nine
subcommittees. Since then the list's badge supersedes a page `not_found`
(never another list's), and the page read stays as `pageReadNotNamed`,
the field a listing already uses to keep that fact; the stat is
`page_negatives_superseded`, and `tests/test_congress.py` pins it in
both directions. A
listed subcommittee is placed under its committee by the list's own
structure (`placementMethod: listed_under_committee_in_senate_committee_list`).
`committee_key` folds the graph's artifacts ("Senate Committee on Select
Committee on Ethics", "Committee on Judiciary") onto the Senate's names
and nothing else; `subcommittee_key` sets the type word aside on either
side — a leading "Subcommittee on" and, since 2026-09-21, a trailing
"Subcommittee", because foreignaffairs.house.gov and docs.house.gov both
print "Europe Subcommittee" where the Clerk prints "Europe" (CURATION.md
§16, which reconciled both lists seat by seat: 11 renames, 18 units added,
nothing superseded). First run: all 20 curated Senate committees listed, 43
subcommittees listed and placed, 27 curated names the Senate no longer
carries. **The House Clerk's list landed on 2026-09-13**, once the
allowlist reached clerk.house.gov (the 2026-09-08 proxy refusal stays
recorded in the fixtures README): `Committees/ExcelCommitteeData` is one
spreadsheet of every committee and subcommittee with its code, type,
parent code and website, committed verbatim at
`tests/fixtures/directories/house/committees.xlsx`, read with the standard
library alone (`congress.read_xlsx_rows`: an .xlsx is a zip of XML) and
matched by exactly the Senate's rules through the shared
`match_committee_list` (`match_senate` and `match_house` are one function
with a source, an id prefix and a list label). Its methods are
`listed_in_house_clerk_committee_list` /
`listed_under_committee_in_house_clerk_committee_list`, its negative is the
same `not_in_official_list` with `verificationFailureSource.source:
house_clerk_committee_list`, and the gate accepts that negative only with
a clerk.house.gov URL. First run: 27 committees in the list, 18 matched
(the joint committees and the Ethics Committee have no curated node;
"Education and Workforce", "Oversight and Government Reform" and the
Strategic Competition select committee are spelled differently from the
curated names and are reported, never fuzzy-matched); 68 subcommittees
listed and placed; 25 curated House names the Clerk does not carry; 30
Clerk names the graph lacks, all in CURATION.md §5.7.
OPM's data landed on 2026-09-08 (`tests/fixtures/opm/`, README there):
FedScope civilian employment by agency and sub-agency for March 2025 and
September 2024 — the official counts the cost cascade's headcount weights
should answer to, where today's `employees` fields are uncited — and the
PLUM archive of the previous administration's reported positions. The
current PLUM export is served by escs.opm.gov, and three different things
have blocked it in turn. Until 2026-09-19 the **proxy** refused to open the
tunnel; then the proxy connected and the **host** answered robots.txt with an
Akamai 403, which this project refused by its own choice rather than by the
standard. On **2026-09-20**, on the owner's explicit instruction, that refusal
was withdrawn for this one host: `politeness.STANDARD_4XX_HOSTS` follows RFC
9309 2.3.1.3 there — a 4xx robots.txt is "Unavailable" and access is
permitted — while every other host keeps the refusal, and a listed host is
still refused on a 5xx or a network failure, which 2.3.1.4 requires. It
manufactures no rule: the verdict says the file could not be read and that no
rule was seen, and adds only which permission the fetch rests on.
**Nothing has been fetched from that host.** The third blocker is this
session's own agent harness, which declined the request, so the policy is
tested offline and has never met the live server; a copy obtained earlier is
deliberately not committed, because it predates the policy and so carries no
honest robots verdict, and a fixture whose provenance record is a guess is
worse than an absent one. So the standing state is permitted by policy,
unfetched in fact, and position evidence still rests entirely on the previous
administration's archive (docs/NETWORK_ACCESS.md §10). The rest of the list that stood
here — clerk.house.gov, www.usa.gov, api.sam.gov, data.opm.gov and
govinfo.gov — was re-measured on 2026-09-19 and **every one of them now
answers**: clerk.house.gov, api.sam.gov and data.opm.gov with a 404 (nothing
published to obey, so crawled), www.usa.gov and www.govinfo.gov with a 200.
clerk.house.gov has in fact been in use since 2026-09-13. So the proxy is no
longer the wall it was; what still refuses does so for its own reasons, host
by host, and govinfo refuses through robots.txt on the endpoint that indexes
it rather than through the network at all. A refusal is recorded in the
fixtures' `.meta.json` files with the reason measured at the time, and never
worked around.
Next in this line, in order of evidence value, with what 2026-09-19's
measurement did to each: the House Clerk's committee list **landed**
(2026-09-13); OPM FedScope for the headcounts the cascade weights by
**landed**; OPM's current Plum Book is refused by its host, so positions still
rest on the previous administration's archive; and SAM.gov's Federal Hierarchy
is reachable at last and still needs a key the owner would have to obtain.
`data.opm.gov` and `www.usa.gov` answer too and nothing here has read either.

**usa.gov's A-to-Z index, used to nominate and not as a source (since
2026-09-20).** The binding constraint on verification has never been fetching;
it is knowing which URL to fetch, and 297 organisations had no candidate page at
all. `www.usa.gov` answers `robots.txt` 200 with a 10-second crawl-delay and
publishes an A-to-Z index pairing each federal agency with the official website
the government itself points the public to. Crawled once across its 22 letter
pages with that delay respected: **475 agency/site pairs, of which 200 reduce to
exactly one node's canonical name and none to two.**

It is deliberately NOT wired in as a fourth directory module beside the Federal
Register's, the Senate's and the House Clerk's. Those make claims — a unit is
listed, and for the complete ones its absence is evidence. usa.gov claims
nothing this project needs: it carries no parent, so it can never support a
placement, and it makes no completeness claim, so it can never support a
negative. What it is good for is the one thing that was missing, and
`official_sites.json` has always said what that is worth: "a URL here is
something to check, not evidence." So the pairs go through `nominate.py` as
ordinary `own_site` nominations and the verifier decides by reading the page.
**25 organisations that had nothing to fetch now have a candidate**, among them
DCSA, MDA, the NRO, USPTO, three national laboratories, SAMHSA, Federal Student
Aid and the OCC.

One was dropped, and it is the reason a directory's own pairing cannot be
trusted wholesale: usa.gov links the **National Security Council** to a
Congressional Research Service report on `congress.gov`, because the NSC has no
public site of its own. Nominated as the NSC's own page it would have let the
verifier confirm the Council from a legislative document that merely names it —
the precise over-claim this project refuses. Publication platforms
(`congress.gov`, `govinfo.gov`, `federalregister.gov`) are filtered out, and the
NSC keeps its honest state of having no page. Two `http://` listings were used
over `https://` with the listed URL recorded, the convention already applied to
a directory's http listing on a `.gov` host: the scheme is transport, not a
claim.

**The government's own handbook of itself (`govman.py`, since 2026-09-20).**
The page method for posts is near its ceiling and this file says why: 35 of
4,591 positions are confirmed by a label in their organisation's own page
content, an agency's site is not obliged to name its officers, and the one
rule that would have lifted the count was measured and refused — 18 of the 27
titles found in site chrome were `Inspector General` in 18 different agencies'
footers, which is federal web convention and not a fact about any of them.

The **United States Government Manual** is the answer to exactly that gap: the
official handbook of the federal government, prepared by the Office of the
Federal Register, in which each agency's entry carries that agency's own
leadership table. One document names an agency and then names the officers of
that agency, so a match is scoped by construction in the way a footer link
never is. `www.govinfo.gov` answers `robots.txt` 200 and allows both paths
read here; the whole Manual is committed verbatim at
`tests/fixtures/govman/GOVMAN-2025-12-31.xml` (8.1 MB, the publisher's own
bytes) with the publisher's manifest beside it, and every digest is recomputed
from the bytes before anything is read.

**The office holder's name is never read.** Each leadership row is a pair:
`NameColumnValue` is a living person and `TitleColumnValue` is the post. This
module reads the second and never the first — not "reads and declines to
publish" — the rule `positions.py` sets for the PLUM archive's incumbent
columns, and `tests/test_govman.py` asserts both that no published title is a
name the Manual prints and that the module never fetches that element.

**Only rows that are complete titles on their own face.** The tables are
typeset rather than tabular, and they qualify a group heading with bare
fragments: under the header `Assistant Administrators`, EPA's rows read
`Water` and `Air and Radiation`; under an ALL-CAPS `DEPUTY ADMINISTRATORS`,
Energy's read `Naval Reactors` and `Defense Programs`. Assembling "Assistant
Administrator for Water" out of two cells would be *producing* a title, which
is the failure this file already refuses by name — the templated-post rename
uses its transform to recognise a name and never to produce the replacement.
So qualifiers are discarded wholesale rather than assembled, by three rules
that are purely structural and need no vocabulary and no grammar: a table that
carries a `Header` at all (anything but empty or the footnote mark `*`)
governs its rows; a row after an ALL-CAPS row is governed by it; a row of
dashes resets the grouping.

That is deliberately blunt and it costs real evidence, measured rather than
argued away: EPA's own `Deputy Administrator` is refused because
`ADMINISTRATOR` sits above it, and its `Chief of Staff` because that table is
headed `Office of the Administrator`. The blunt rule admits 314 rows under the
136 matched agencies and confirms 64 posts; relaxing the header half to "a
header that reads as plural" admits 459 and confirms 95, and the extra rows
demonstrably include qualifiers — `Financial` under `Chief Officers`, and
`Under Secretary` under `Food Safety`, which means the Under Secretary *for*
Food Safety. Closing those leaks needs a plural test on free text, and a
plural test is wrong about `Chief of Naval Operations` and `Chief of
Chaplains`. 64 structurally sound confirmations beat 95 with a known leak,
which is the same trade the navigation rule made and is recorded here as a
measurement rather than a preference.

**Scoped to the agency's own direct children, never its descendants.**
Matching a post to the nearest ancestor that has a Manual entry was tried and
rejected on measurement: it lifts 64 to 86, and the 22 extra are `General
Counsel`, `Inspector General` and `Chief Information Officer` nodes belonging
to DIA, NSA, DLA and other Defense agencies, every one of them confirmed from
the Department of Defense's own single row. One row would have become four
agencies' confirmations — the footer problem again, wearing a better source.
Four refusals make the join unambiguous on both sides: the entry must name
exactly one organisation in the graph, that organisation must answer to
exactly one entry, the entry's eligible rows must carry the title once, and
the organisation must carry one child of that name. On the real data three of
the four never fire, which is what it looks like when a source is genuinely
well scoped.

**No placement claim, ever.** One entry was read and it yields one
observation; publishing existence and placement from it would present a single
finding as two corroborating ones. That is the rule this file already sets for
a post confirmed on its organisation's web page, and the gate refuses a
placement method naming the Manual.

**64 posts listed across 37 agencies, and what each is worth.** 56 take the
Manual as their verification method and publish `partial` — one official URL
is 0.4 + 0.3 in `verify_node_sources`, and no route here makes it more. The
other 8 already carried a claim from a page or from OPM's archive; those keep
their own method, gain the Manual beside it, and reach `verified` on two
genuinely independent official documents, which is the existing confidence
arithmetic and not a rule this work changed. The titles gained are precisely
the stamped administrative posts this file documents as carrying no evidence
at all: `Inspector General` 28, `General Counsel` 15, `Chief of Staff` 9,
`Chief Financial Officer` 4. Nodes with an official source went 684 to 740 of
5,427 (13.6%), and "no source recorded" fell 4,691 to 4,635. (Both totals moved
again the same day when 26 curated units were added: the graph now carries
5,453 nodes and 740 of them an official source, still 13.6%.)

**A listing says nothing about who holds the post, and the panel says so with
the Manual's own words.** 26 of the 64 leadership tables carry a "Sources of
Information were updated" footer, and they run from 2017 to 2022 against a
2025-12-31 edition — the Government Accountability Office's reads `2–2019`.
The footer is published verbatim on every record that has one and printed in
the panel, because a reader is entitled to see it before reading the badge as
current. Staleness costs much less here than it would in a roster, since the
incumbent is never read and a job title outlives its holder, but the claim is
still "the Manual's <edition> entry lists a post of this name" and never more.

**The organisation route, since 2026-09-20 — the Manual's entry for the unit
itself.** `docs/NETWORK_ACCESS.md` §11 measured all 68 hosts this project had
recorded as refusing robots.txt: **67 refuse the page too**, so for the units
on them a web page can never be the route. The Manual names 162 of the graph's
832 organisations uniquely and 38 of the 344 that carried no verification —
CRS, the OCC, the Naval Academy, the Marine Corps, twelve Defense Agencies,
COPS, OJP, EOIR, BIS, NTIS, the Women's Bureau — so `build_org_records` /
`apply_govman_org_evidence` publish that entry as `verificationMethod:
listed_in_us_government_manual` (a different claim from the post route, and a
different sentence on the panel), with the entry block `govmanEntry` (the name
as printed, the parent as printed, edition, granule, the publisher's URL)
stamped always and the method only where none exists. It follows the Federal
Register directory's shape, **not** the post route's: the entry's name is
existence and the parent entry the Manual files it under is a separate claim
about the edge — `placementMethod: listed_under_parent_in_us_government_manual`
only when that parent IS the one the tree gives the node, a
`placementDirectoryDisagreement` (source `us_government_manual`) when the
Manual's parent names some other node here, and nothing when the parent is the
Manual's own scaffolding ("Defense Agencies", "Bureaus"). FERC is the one
disagreement: the Manual files it under the Department of Energy and this graph
under the independent regulatory commissions, and neither is resolved. Both
routes share one join (`match_organisations`, unambiguous on both sides or
nothing). The gate's independent parse now also records which entity encloses
each entry, so it refuses a parent the Manual does not print and a placement
under a parent the tree does not give, beside every check the post block gets.
First run: 162 entries, 38 methods, 12 placements, 1 disagreement; official
source 747 → 783, placements evidenced 339 → 351.

The gate parses the Manual itself rather than trusting the block: it
recomputes the fixture's digest, re-derives the eligible titles with a
**second, independent stdlib extraction** that imports nothing from the module
it checks, and refuses a block whose title that entry does not print, whose
granule names a different agency, whose URL does not address the granule
quoted, whose edition has not happened, that sits on something other than a
post, or whose organisation is not the parent the tree gives the node —
checked off the tree the gate is walking rather than off `parentId`, for the
reason the scoped Executive Schedule claim already documents. The citation's
granule id is the publisher's own, not a construction hoped to be right:
`app/details/.../GOVMAN-2025-12-31-072` serves the House of Representatives
and `...-72` serves a page whose title is the raw id, so the zero-padding is
pinned against all 241 ids in the committed manifest. That check exists
because a plain HEAD request does not tell you: govinfo answers **200 with a
"Page Not Found" body** for every `content/pkg/.../html/...htm` granule URL,
real ids included, and publishing those would have put a fabricated citation
on all 64 records.

**Headcounts and positions (`headcounts.py`, `positions.py`).** Two more
official sources, applied by the exporter since 2026-09-09 from
`data/verification/headcount_evidence.json` (133 records) and
`position_evidence.json` (126). Both are applied *beside* the curated
figure, never over it: `apply_headcount_evidence` stamps
`employeesOfficial` and `employeesOfficialSource` (the listed name, the
level, the agency/sub-agency codes, the period, OPM's own coverage
sentence and the URL it came from, the previous period's count, the
component rows, and the matcher's flags) and leaves the base graph's
`employees` field exactly as it was; the panel shows both rows and says
they count different populations. `apply_position_evidence` stamps
`positionListing` plus the PLUM placement method. A title the archive
spells with the organisation it has already filed the row under —
"COMMISSIONER, UNITED STATES CUSTOMS AND BORDER PROTECTION" under CBP,
"DEPUTY DIRECTOR, CYBERSECURITY AND INFRASTRUCTURE SECURITY AGENCY" under
CISA — is read back through the same strip the curated side has always had
(`archive_title_keys`), which took the matches from 91 to 126 of the 1,084
positions sitting under a matched organisation; the archive's own spelling
stays a key, so nothing that matched before stops, and two rows that
collapse onto one key claim neither (three more refusals, the Labor
department's two "Deputy Assistant Secretary" rows among them). Nothing
without a comma is stripped: "CHIEF COUNSEL FOR CYBERSECURITY AND
INFRASTRUCTURE SECURITY AGENCY" stays whole. The exporter refuses a
record whose node is not of the right kind, whose name has since changed,
or that carries no date or URL — and, for a headcount, one its own
descendants' records already exceed. The gate checks every field (a
`.gov` URL, a period, a coverage sentence, a past date, a non-negative
integer) and reports how many nodes carry each and how far the curated
figures are from OPM's: **66 of the 133 differ by more than 10%.**

**The cascade is not reweighted by them, and says so.** Seven sibling sets
carry a FedScope record on every headcount-bearing member, so a swap was
possible; it was rejected. One of the seven is Homeland Security, where the
Coast Guard's curated 55,000 sits beside FedScope's 9,583 — the same
civilian-versus-uniformed mismatch this file already refuses for the Army,
and a swap would have cut a uniformed service's share fivefold. The curated
figures are uncited, so nothing in the pipeline can tell a wrong number from
a different population. What is true is that the two disagree, so a node
whose allocated share was divided by a curated headcount an OPM figure
contradicts by more than 10% carries `cost_weight_dispute` — both figures,
the period and the URL — and the panel prints them under the estimate with
"the share was not recomputed from OPM's number". 11 shares carry one. It is
withdrawn on every build before it is recomputed, and dropped from any node
that ends up with no share at all (the four EOP offices beneath a negative
Treasury pool): a caveat about an estimate that does not exist is a claim
about nothing, and the gate refuses it, along with a dispute that cites a
figure the node does not carry, that is within the tolerance, that sits on a
measured cost, or that has no source URL.

A node carrying an OPM headcount and nothing else is no longer told "no
source URL has been attached to it yet" — the provenance block directly
below that sentence shows an `opm.gov` URL. The panel says which claim is
the missing one instead: the employment file is evidence about a unit's
staffing, not that the unit exists as the graph draws it.

FedScope is OPM's civilian employment table by agency and sub-agency
(March 2025, September 2024 beside it). Every record carries the data
dictionary's own coverage sentence, because the population is the whole
point: it is Executive-Branch civilians in an active pay status, excluding
the Postal Service and the intelligence agencies — so it is *not* the
number the curated `employees` fields hold, which mix civilians, uniformed
members and contractors. That mismatch is the reason to have it: 124 of
the matched nodes carry a curated figure, and only 55 of those are within
10% of what OPM reports. Matching is scoped as the Federal Register's is —
a sub-agency row only reaches a node beneath the node its agency matched —
and three refusals were added after the first derivation published things
that were false:

- an "agency" whose whole table entry is one row for a differently-named
  unit is refused (`agency_is_one_other_unit`). FedScope files the U.S.
  Tax Court alone under an agency it calls "JUDICIAL BRANCH" and the
  Bureau of Consumer Financial Protection alone under "FEDERAL RESERVE
  SYSTEM"; the first derivation published 165 as the judicial branch's
  staff and the CFPB's 1,661 as the Federal Reserve's;
- a row whose agency matched no node is refused however unique its name
  (`unscoped_refused`): a name being unique in the graph is not evidence
  of placement, and it had stamped a civilians-only Marine Corps count on
  the node meaning the uniformed service;
- a record its own descendants' records already exceed is marked
  (`subtreeRecordsExceedIt`), so nothing weights a sibling set by a figure
  missing most of its subtree.

The table's own truncation of a leading "NATIONAL" is undone, which is not
a guess about which unit is meant but the file's abbreviation reversed; it
is what lets NASA and NARA match at all. FedScope's "DEPARTMENT OF THE
ARMY" is deliberately *not* matched to the graph's "U.S. Army": the first
is a civilian department, the second the uniformed service, and they are
different populations — a curation gap, in `CURATION.md`, not a matcher
bug.

**Pay, as the archive states it and no further.** The archive's
`LevelGradePay` column holds two different things — a rank ("IV" for an
Executive Schedule row, "15" for a General Schedule one) and, for 983 rows,
a rate of basic pay ("$225,700") — so `split_level_grade_pay` separates
them into `payLevel` and `reportedPay` (with `reportedPayText`, the text
the archive prints, so the figure can be audited against the file). 44 of
the matched positions carry a rate, 30 a level or grade only. A dollar figure
is never published under a heading that reads "Level", the gate refuses each
holding the other's kind of value, and the panel says a level is the rank,
not a rate of pay, and that a rate is neither this unit's cost nor
necessarily what the post pays now.

**The level converted into a rate, since 2026-09-11, by two documents that
each say half of it** (`data_pipeline/verification/pay_tables.py`, derived by
`scripts/derive_pay_evidence.py` into `data/verification/pay_evidence.json`).
OPM's Salary Table No. 2026-EX was fetched once the session's allowlist was
widened — `docs/NETWORK_ACCESS.md` §0a records that the earlier refusals came
of editing the wrong cloud environment — and is committed verbatim at
`tests/fixtures/opm/pay/executive_schedule_2026.html`, with the `.meta.json`
its fetch wrote. `load_executive_schedule` **recomputes the digest from the
bytes on disk and refuses a mismatch**, which is the only such check in the
repository and the thing that makes a record's `documentSha256` a claim
rather than a copied string; a hand-entered table under an `opm.gov` URL
would otherwise read on the site exactly like a fetched one.

The claim is deliberately two-sourced and can never be more: the **level** is
the previous administration's archive (January 2021 – January 2025) and the
**rate** is a table effective January 2026, so neither half says what a post
pays whoever holds it now, and the panel prints both with their own dates.
`scopeMatch` is `proxy` — the table names a rank, not a unit — so
`financial_evidence.classify` grades all 29 `partial` and no route makes one
`verified`.

The pay plan is what settles whether a rank is an Executive Schedule rank,
not the numeral: the archive files General Schedule grades in the same column,
and two of its rows carry a Roman numeral on a pay plan that is not the
Executive Schedule at all (ABMC's "THE SECRETARY" on `AD`, the Corporation for
National and Community Service's "BOARD MEMBER - CHAIR" on `WC`). So a rate is
published only where the archive gives **both** an `EX` pay plan and a level
the table prints. **29** of the 126 matched positions qualify — not the 30
that "carry a level or grade", the 30th being a GS-15 — and one `EX` record
carries no level at all. Level I reaches no node in this graph.

Three boundaries the gate enforces (`table_pay_violations`), each of which
failed or nearly failed in development:

- **It is not the unit's cost.** Basic pay excludes benefits and is not a
  share of federal outlays, which is what `resolved_total_amount` means
  everywhere else. Nothing writes a cost field; the gate refuses a pay block
  beside a measured cost status or an unknown `cost_basis`.
- **It is not evidence that the post exists.** The first version appended the
  table's URL to `sourceUrls`, and the release gate passed it:
  `verify_node_sources` counts URLs and classifies hosts, so a second `.gov`
  URL added `official_site` and carried confidence 0.5 → 0.8. 29 positions
  published `verificationStatus: verified` on the strength of a five-row table
  naming no post, and the graph's verified count went 49 → 78 in one build.
  The module now writes no `sourceUrls`, `sourceTypes`, `lastVerified` or
  `verificationMethod`; the URL rides in `positionPayRate` only.
- **It cannot outlive the level it was looked up from.** `positionPayRate` is
  in `EVIDENCE_OWNED_FIELDS`, and the rate is published only where the node's
  own `positionListing` still reports that level on that pay plan — so when
  `positions.py` withdraws a listing, the rate goes with it rather than
  leaving "$228,000 (Level II)" on the site with nothing asserting the post is
  at Level II.

The gate mirrors the five rates in `EXECUTIVE_SCHEDULE_RATES` because it is
stdlib-only and cannot parse the fixture; `tests/test_pay_tables.py` parses the
committed page and asserts the mirror equals it, so the two cannot drift. The
table's footnotes ride on every record and are printed verbatim — a pay freeze
for the Vice President and certain senior political appointees runs through
January 30, 2026, so a level's table rate is not necessarily what was payable,
and the gate refuses a block whose footnote list is empty.

Feeding these records through `financial_evidence.validate_record` — rather
than stamping them straight onto the graph — needed three changes to a module
that had already survived 178 attacks, each narrow and each recorded there:
`annual_rate` joins `PERIOD_COVERAGES` (a rate is not a flow, and filing it as
`full_fiscal_year` would claim it covered a year it did not) and is required
of `basic_pay` in both directions; and `_prints_whole_dollars` lets a document
state its scale by *printing* it, because the OPM page contains none of the
words "dollar", "thousand" or "million" and an honest record from it was
otherwise unfilable. That relaxation is granted per source type
(`SCALE_PRINTED_SOURCE_TYPES`, four entries as of the judicial,
congressional and White House modules below), applies only when no
scale phrase is present at all, requires the currency mark to be attached to
the record's own figure, and is recorded in `unitsEvidenceKind` so a reviewer
can see which records rest on it.

**The level half, from current law instead of a closed archive (since
2026-09-18).** Every Executive Schedule rate this project published took its
*level* from one place: OPM's PLUM archive of the **previous** administration
(January 2021 – January 2025). That is a record of who held what, so the join
it supports carries two dates and neither is now, and it reached 29 positions.
5 U.S.C. §§5312–5316 **is** the Executive Schedule — five sections, one per
level, each an enumerated list of the positions Congress placed there — and
`uscode.house.gov` answers `robots.txt` 200, which no earlier session could
check. The five sections are committed verbatim at `tests/fixtures/uscode/`
and `statutory_schedule.load_schedule` recomputes every digest before reading,
the same refusal `pay_tables` makes.

It landed in two halves, and the first was a **rename**. `CURATION.md` §8
recorded thirteen cabinet heads left templated because "no source in hand
names them" — the archive files them as a bare "SECRETARY" and seven
department pages answer 401/403. §5312 names every one. So
`rename_templated_post_titles.py` gained the Code as a third source, ordered
**first**, and renamed **12 of the 13**: `Secretary of Department of the
Treasury` → `Secretary of the Treasury`, and so through Commerce, the
Interior, Transportation, Education, HHS, HUD and Agriculture. The statute is
used exactly as the other two sources are — **it selects, it never
produces**. The transform that yields "Secretary of Justice" can only ever
pick a string the Code actually prints, and the Code prints no such title
because the office is the Attorney General, so DOJ selects nothing and falls
through; a second guard requires the statutory title's "of …" remainder to be
part of the department's own name, so a title naming a different department
can never be chosen for this one. The one refusal left is honest: the
Executive Schedule carries no "Deputy Secretary of Commerce".

Then the pay. `positionSchedulePay` is a **fourth** pay field, not a widening
of `positionPayRate`, because the two carry different dates and different
withdrawal rules and folding them together would have meant loosening a gate
check that already guards 29 published records — to make a new claim easier
to publish, which is the wrong direction. Matching is canonical-key
**equality**: the Code prints both "Secretary of the Army" and "Under
Secretary of the Army", and a containment test prices the second from the
first, the same failure `whitehouse_pay.title_core` documents for `Press
Secretary` inside `ASSISTANT PRESS SECRETARY`. A statutory title reaching two
nodes prices neither ("General Counsel" names 84 nodes here); a title the
statute states several of ("Assistant Secretaries of Commerce (11)") prices
none; and "Archivist of the United States", which the Code places at **both**
§5314 and §5316, is dropped from the index rather than adjudicated.

**A second route, scoped the way a FedScope row is.** Whole-name equality
prices "Secretary of Energy" and is useless for the 375 statutory titles
written as `<office>, <organisation>`: the Code says "General Counsel of the
Department of Agriculture" and this graph calls that node `General Counsel`,
under `Department of Agriculture (USDA)`. `match_scoped_positions` splits such
a title and requires the organisation half to name the node's **own parent** —
the same scoping `headcounts.py` applies to a FedScope sub-agency row, on the
same principle that a name is only evidence of placement when something else
already placed it. Four guards: the organisation half must name exactly one
node and not a committee, court or other body the Executive Schedule does not
reach; the office half must be at least two tokens; the office must be exactly
one **direct** child of that organisation; and a node already priced by whole
name, or reached by two statutory titles, is refused. The type guard is not
belt-and-braces — without it "Secretary of Homeland Security" reaches the
Senate Appropriations subcommittee named "Homeland Security", a real node with
a unique name in entirely the wrong branch; the two-token floor happens to
refuse that one too, which is exactly why it must not be the only thing
standing there. **61 more priced**, and they are the stamped titles this file
already documents as recurring 92, 81 and 47 times — `General Counsel`, `Chief
Financial Officer`, `Chief Information Officer` — which otherwise carry no
evidence at all.

**99 positions priced** — 15 at Level I, 17 at II, 10 at III, 53 at IV and 4 at
V — including the Secretary of State, the Attorney General and the Secretary
of Defense, none of which carried pay evidence of any kind before. All
`partial`, all `scopeMatch: proxy`, the same deliberate downgrade
`judicial_pay` and `congressional_pay` make. Nothing writes `sourceUrls`,
`sourceTypes`, `lastVerified` or `verificationMethod`: that is the exact
channel by which a five-row table carried 29 positions to `verified` on
2026-09-11, and `tests/test_statutory_schedule.py` asserts against the
published graph that no priced node gained a `uscode.house.gov` URL.

The gate mirrors node id → (statutory title, level, section, the organisation
it was scoped to or `None`) in `US_CODE_EXECUTIVE_SCHEDULE`, keyed by id for a
reason sharper than the Senate case: **fifteen of these nodes are priced at the
identical $253,100**, so a record moved between them keeps a correct figure, a
correct rate text, a correct citation and a real statutory title, and only a
check tied to the node's own identity catches it. For a scoped record the
placement is checked too, and **off the tree the gate is walking rather than
off `parentId`** — that field is stamped on the exported node list only, so a
check that read it would have passed vacuously for most of the graph while
looking like a check. The mirror is pinned equal to what the committed sections
print, the two routes are asserted mutually exclusive, and the tests corrupt
every dimension in turn — the swap, a different organisation, a dropped office
half, an office half not in the statutory title, a re-parenting, a rename.

**Two more sources, each a single primary document rather than a join
(since 2026-09-14).** `judicial_pay.py` and `congressional_pay.py` write a
different field, `positionStatutoryPay`, because their claim is a different
shape from `positionPayRate`'s: no archive to join, one source that names a
tier or a role directly and states what it pays. `judicial_pay.py` reads
`uscourts.gov`'s own "Judicial Compensation" table (District Judges, Circuit
Judges, Associate Justices, Chief Justice, current year first) and prices
exactly the Chief Justice and every named circuit's or district's own Chief
Judge — a chief judge is paid as a judge of that tier, not at a distinct
"chief" rate, so this is not a proxy for a different post the way an
Executive Schedule level is. It refuses every node that states a
multiplicity (351 circuit- and district-judge nodes), the specialized
Article I courts (Tax Court, CFC, CIT, CAAF, CAVC — a different statutory
basis this module has not read a source for), and one node the multi-post
rule cannot see: `jud-district-structure-chief-judge`, a template describing
every one of the 94 districts' structure rather than one district's actual
chief judge, refused by id. `congressional_pay.py` reads `senate.gov`'s own
year-by-year base-salary table, whose footnote names three specific
leadership roles sharing one rate: the President Pro Tempore, the Majority
Leader, the Minority Leader. It prices exactly those three and nothing
else — not the party whips the footnote does not name, not the House's own
Speaker or Majority/Minority Leader (no fetched official source this
session could reach: `crsreports.congress.gov` and `www.congress.gov`'s CRS
pages are Cloudflare-blocked, a fact about the network), not the Vice
President's Senate-leadership node (a different statutory salary this
module has not read), and no base "Member of Congress" seat, because none
is curated as its own position node — "Individual Senator/Representative
Offices" are staff-office groupings, not the Member's own seat.

Both write `scopeMatch: "proxy"`, deliberately, even where a source's own
wording matches a node's name closely: the Senate's footnote names three
roles together under one shared rate rather than one row per role, and
`financial_evidence.classify` would grade a `scopeMatch: "exact"` record
`verified` — a stronger claim than a grouped statement earns. Both are
gated by one shared checker, `statutory_pay_violations`, mirroring each
source's table/footnote and — the check `table_pay_violations` does not
need, because an Executive Schedule level's five rates are all
different — a `STATUTORY_PAY_NODE_TIERS` map from node id to the specific
tier or role that node is: three Senate leadership roles share one dollar
figure and one shared footnote, so a record for the Majority Leader
relabelled as the President Pro Tempore would still quote a footnote naming
that role and price the same $193,400, and only a check tied to the node's
own identity catches it. `withdraw_pay_from_multi_post_nodes` strips all three pay
fields in one sweep, since the multi-post rule is the same rule on each.
First run: 18 positions priced (15 judicial, 3 congressional), all
`partial`, none `verified`.

**The one named-salary disclosure the law requires, and the narrow claim it
supports (since 2026-09-14).** `whitehouse_pay.py` reads the White House
Office's own Annual Report to Congress on White House Staff, which Section 6
of Public Law 103-270 requires by July 1 each year and requires to state
every employee's and detailee's title and annual rate of pay. It is the only
place in this project where an official document gives a specific post a
specific number of dollars actually paid. It is also, by statute,
**person-level**: the 2026 report lists 408 people, `SENIOR POLICY ADVISOR`
21 times and `STAFF ASSISTANT` 15, at differing salaries. So the claim is
deliberately not "this post pays $X" but "the one person the report lists
under this title is paid $X, as of the report's own as-of date" — which is
why the field is a third one, `positionReportedPay`, with its own gate
checker (`reported_pay_violations`), and why `scopeMatch` stays `proxy`. A
statutory rate attaches to the office and survives a change of holder; a
reported rate does not.

**The NAME column is discarded at parse time**, not carried and declined:
`parse_staff_report` matches the name cell only so as to exclude it, and the
gate refuses any published field whose text looks like the report's own
`LAST, FIRST M.` form. The rule `positions.py` set for the PLUM archive —
the incumbent columns are never read — binds harder here, because this
document names living people beside their salaries.

Refusals: a title more than one person holds (two salaries make the figure
undecidable); a node outside the `exec-eop-who` subtree, scoped as
`headcounts.py` scopes a FedScope row; a node standing for several posts;
and **a rate of $0.00**, which ten of the 408 rows carry — uncompensated
appointees, the National Security Advisor among them. Zero is never
published here, and an uncompensated arrangement is a fact about a person,
not about the post. The report spells a post with its White House
commissioning rank in front, so `title_core` folds those three ranks off the
**front** and then requires exact equality — a containment test would price
a principal from a deputy, since `Press Secretary` is inside `ASSISTANT
PRESS SECRETARY`, and the only titles containing `Director of Legislative
Affairs` and `Social Secretary` are their **Deputies'**. That is the same
failure the existence verifier documents for "Office of Science" inside
"Office of Science and Technology Policy".

**A PDF, read with the standard library alone.** No third-party PDF library
entered the repository: the document is `%PDF-1.6`, carries no `/Encrypt`
(an encrypted one is refused rather than having ciphertext read out of it),
and holds its text in FlateDecode streams — zlib — as ordinary `BT … Tm …
TJ` blocks, so `extract_text_runs` reads it the way `congress.read_xlsx_rows`
reads a spreadsheet as a zip of XML. Position cannot separate the columns
(every cell in a row shares one `Tm` and advances by kerning), so they are
recovered by **shape**: a money pattern, the closed `EMPLOYEE`/`DETAILEE`
and `Per Annum` vocabularies, a `LAST, FIRST M.` name, and the title as
remainder. A row not yielding exactly one of each is refused — 8 of 408 are.

The gate mirrors node id → (printed title, printed rate) in
`WHITEHOUSE_REPORTED_PAY`, keyed by id for the reason the Senate leadership
case established and more sharply: **four of the five priced posts are paid
the identical $195,200**, so a record moved between them would keep a correct
figure, quote and pay basis. First run: 5 positions priced of the 27 the
graph then carried under the White House Office — the binding limit being
that the graph held 27 sketch nodes for a 400-person office.

**The subtree rebuilt from the same roster, the same day.**
`scripts/expand_whitehouse_office.py` is the only writer of the White House
Office subtree (the curated file is never hand-edited) and took it from **27
nodes to 249**, which took the pay module from **5 priced to 166**. One node
per distinct title the report prints: 168 single-post, and 54 standing for a
title several people hold, carrying the report's own count as
`representsPosts` rather than becoming N indistinguishable nodes — the report
tells those people apart by name, and this project does not publish names.
Nodes are named as the report prints the title, in title case, because the
White House rank is part of the official title and an Assistant, a Deputy
Assistant and a Special Assistant are three different appointments;
`index_report_titles` therefore files every row under both its printed and
its folded spelling, and `build_records` tries equality before the fold, the
order `congress.match_committee_list` already uses. The script is idempotent
and never renames, re-types or removes a curated node — the 16 whose titles
the 2026 report does not print are left exactly as they are, because a
roster not carrying a title is not evidence the post does not exist.

Each added node carries `structureSource: listed_in_whitehouse_staff_report`
and `descriptionSource: generated_from_whitehouse_staff_report`, and its
description states only the title and the rate, never duties, which the
report does not give. They are the first nodes in this graph whose
*structure* is sourced rather than curated or templated, and the panel labels
them as such instead of "uncited prose".

Because the roster is 233 titles rather than five rows, the gate does not
mirror it as a literal the way `EXECUTIVE_SCHEDULE_RATES` is mirrored — a
hand-kept copy of 233 figures would rot silently. `whitehouse_roster()` reads
the committed report with a **second, independent** stdlib extraction (this
file imports nothing from `data_pipeline`, by design), checks its digest, and
`tests/test_whitehouse_pay.py` pins the two parsers equal on the real
fixture. The role-swap defence is then structural rather than a mirror: the
claimed title must be one the report prints, must be held by exactly one
person, and must name this node by equality or with the rank folded off.
`CURATION.md` §7.4-7.5 record the run and what stays unpriced.

The PLUM archive is the previous administration's reported positions
(the current export is on escs.opm.gov, which nothing here has fetched — the
refusal was lifted on 2026-09-20 and the fetch has not happened, §10), so every
record and every proposed panel sentence names the archive and its period
and says nothing about who holds a post now: the incumbent columns are
never read. 91 of the graph's 4,382 position nodes matched a listed title
under their own organisation; none matched across organisations.

Everything this module writes is listed in `EVIDENCE_OWNED_FIELDS`, with
`evidenceUrls` (exactly the URLs it added to `sourceUrls`) and
`evidenceVerifiedAt` (the date it set as `lastVerified`), so the next build
withdraws exactly those and nothing else. The first version cleared the
node's whole URL list and stripped the FiscalData URL from 26 measured
nodes; the gate now requires a `fiscaldata.treasury.gov` URL on every
measured node, not just the `treasury_outlays` type.

`apply_evidence_to_tree` **clears every field it owns before applying** the
current evidence, so a withdrawn or downgraded record stops being published
even though the exporter re-feeds the previous `graph.json` as a payload; a
retraction that could never reach the site was the second failure the review
found. It runs *after* `apply_treasury_outlay_rows`, which rewrites
`sourceUrls` on the nodes it stamps — and the sweep must leave that URL
alone: it swept the node's whole URL list, and because it only trips on a
node that already carries a claim of this module's, a confirmed node kept its
FiscalData URL on the build that confirmed it and lost it on the next one,
dropping from `verified` to `partial` and publishing a measured cost with no
source behind it. `claimed_by_another_stage` keeps a URL a surviving
`sourceType` still answers to. `matchedText` is text as it appears on
the page, so a claim can be audited against the live site.

The gate requires: every `lastVerified` a past ISO date; every
`verificationMethod` backed by a URL and one this pipeline can produce; no
node claiming a failed check beside a source; an `official_site` type backed
by a `.gov`/`.mil` URL. Coverage is reported. The verifier obeys `robots.txt`
and sends a User-Agent naming the project. It fails open in exactly one case,
and it is the opposite of the one this line used to name: a host that answers
that there is no robots.txt (404/410) is crawled, because nothing was
published to obey. Every other non-2xx refuses — 401/403 by this project's
choice, 5xx and a DNS/TLS/timeout failure because RFC 9309 §2.3.1.4 makes an
undefined robots.txt a complete disallow. "Cannot be fetched at all" is
therefore the case that refuses, not the case that fails open. A host that answers `robots.txt` itself with 401 or 403 is
the one case that looks like "unreadable" but is not treated as such:
`RobotFileParser` swallows that status and sets a blanket disallow with no
rules parsed. The path stays refused — by this project's choice, not by the
standard: RFC 9309 §2.3.1.3 — committed at
`tests/fixtures/standards/rfc9309.txt`, fetched 2026-09-15, digest recorded —
treats 4xx as
"Unavailable" and permits access, reserving complete-disallow for 5xx, while
Python implements the older 401/403-means-disallow convention. What the
record may not do is quote a rule nobody read, so the reason distinguishes
"could not be read (401/403); refused by policy" from "disallows <path>".
`www.state.gov` did exactly this on the first live run. Positions are checked only with
`--include-positions`.

### Frontend (`index.html`, `js/`)

No bundler, no npm. ES modules loaded by the browser; Three.js comes from
unpkg at runtime. `window.GRAPH_DATA_SOURCES` in `index.html` names the
sources: `primary` (`output/graph.json`), `base` (the curated file, used
only if the primary is missing or malformed), `corporate` (null: the
committed `data_expansion/corporate_expansion.json` is the template output
of `expand_corporate_nodes.py` — invented positions — not EDGAR officers,
so it is not merged until `extract_and_expand.py` has produced real ones).

- `graphLoader.js` fetches primary/base, corporate, expanded nodes/edges and
  candidates, merges the overlays into the tree (`safeAddChild` refuses a
  second parent or a cycle), trims depth to 20, and attaches the candidate
  list separately.
- `graph.js` renders: instanced meshes, sprite labels, Fibonacci-sphere child
  layout with the three branches on a screen-plane triangle, LOD clustering,
  raycast selection, fly mode.
- `ui.js` owns the DOM: search, breadcrumb, info panel (cost with
  measured/estimate badge and period line; verification box with the
  "No source recorded" state and a separate Placement line for the edge
  above the node; every base-graph description labelled "uncited prose —
  not checked against any source", because all 5,155 read as fact and none
  has a citation; the provenance line under the title computed from the
  graph, never hardcoded), depth controls, verification toggles, expand
  batching.

Cache busting is manual: bump the `?v=` query string in `index.html` and in
the imports at the top of `js/ui.js` and `js/graph.js` together after any JS
change, or users run stale modules against new data.

**The key named 25 accounting lines as offices (since 2026-09-18).** A
receipts line is created by the exporter and carried no colour of its own, so
it took `DEFAULT_NODE["color"]` — the same `#666666` the 4,589 Position nodes
carry, whose legend swatch reads "Position / Office". Every one of the 25
Treasury accounting lines was drawn and keyed as a post. They now carry
`TREASURY_LINE_COLOR` (`#8aa0b0`, differing from the position grey in
lightness rather than hue, the same colourblindness reasoning as the
filled-against-hollow cost badge) with their own legend row.
`colour_treasury_lines` runs after the tree is final so a line carried
forward from a build that predates this is recoloured too, not just a freshly
created one; `tests/test_treasury_netting` pins both routes and asserts
nothing else in the graph takes the colour, and the smoke check reads the
legend swatch out of the page and compares it with what the served graph
actually carries.

**"How to read this", and a count that was wrong by a factor of seven
(since 2026-09-18).** Every claim this site makes is hedged precisely, in
the info panel, in nine-pixel type; the line a visitor reads first was six
clauses joined by middots. That is honest and it is not readable cold, so a
first-visit card states the same things in plain sentences — what a box is,
why most of them carry no dollar figure, why a post never gets one, what
"no source recorded" means, and how to read the badges — and is remembered
as dismissed after that (`readingGuideDismissed`, beside the other
per-viewer prefs), with a "How to read this" button under the title to
reopen it. It is a modal: backdrop click, Escape and a button all close it,
and it opens 900ms after boot so it does not take focus behind the loading
overlay.

Writing it is what caught the error. Both the card and the provenance line
are now formatted from **one** tree walk (`summariseGraph`), so they cannot
disagree — and that walk had been deriving the estimate count by
subtraction: everything not measured was published as "5,265 apportioned
estimates, withheld unless asked for". Only **650** nodes carry an
apportioned share. The other **4,615** carry no figure at all and never
will — 4,441 of them posts, which have no budget to divide, and 174 beneath
a Treasury pool that nets below zero — so ticking the estimates box reveals
nothing for them. The line promised 5,265 hidden numbers, of which 4,615 do
not exist. It now counts `cost_status == "allocated"` directly and names the
no-figure group separately, and the measured clause reads 137 (the 25
receipts lines are measured, and were being counted outside the total rather
than inside it). `scripts/frontend_smoke.mjs` recomputes the measured, the
allocated and the post counts from the served graph and asserts the card and
the line both match, which is the check that would have failed before.

**UI honesty fixes, keyboard access, and remembered state (since
2026-09-15).** Four small panel bugs, none data-affecting: a leaf node showed
both "No Sub-nodes" (disabled) and "Expand All Below" (also disabled) side by
side, saying the same thing twice; "Trace Origin" re-rendered the same
root-to-node path the breadcrumb already shows, as a second list, rather than
only confirming the 3D glow path (`pathGlowPool` in graph.js) it actually
adds; the depth buttons are a fixed HTML list (1–12) with no idea the loaded
tree is only 8 levels deep (`state.maxDataDepth`, computed from `__meta`),
so five of the twelve promised a jump the data cannot make; and a candidate
node's description and placement lines were blanked outright rather than
saying what a reviewer actually needs — the discovery notice's own text and
the crawler's `possibleParent` guess, each labelled as unreviewed rather than
presented as fact. `updateDepthButtonAvailability` (`ui.js`) now disables and
retitles any depth button past `stats.maxDataDepth` on every stats update, so
it self-corrects if the tree's depth changes on a future build rather than
needing the button list hand-trimmed.

Every clickable row that was a plain `<div>`/`<span>` with a click handler —
the breadcrumb, the children list, search results — was unreachable by
keyboard and invisible to a screen reader: no role, no tab stop, no label.
`makeInteractiveRow(element, label, onActivate)` adds `role="button"`,
`tabindex="0"`, `aria-label` and an Enter/Space keydown handler that calls the
same activation function as the click, applied at all three sites; the 17
static depth buttons got `aria-label`s directly since they were real
`<button>` elements already, just unlabelled.

A reload used to lose the depth filter, both toggles, and the selected node
every time — nothing was remembered, and there was no way to link someone to
a specific node. `writeStoredPrefs`/`readStoredPrefs` keep one JSON blob under
`bureaucracy-view-prefs-v1` in `localStorage` for the depth filter and the
three toggle states (both wrapped in try/catch: private browsing or blocked
site data must degrade to "nothing remembered," never a broken load); the
selected node goes in the URL hash instead (`#node=<id>` via
`history.replaceState`), since that one is worth sharing as a link, not just
recalling for the same viewer — a cluster's collapsed id is excluded from the
hash since it names whatever the LOD happened to fold together, not a stable
target. `restorePersistedState()` runs once at boot and reflects both back
into the visible controls, not just into memory.

**What the browser fetches, and why it is not `graph.json` (since
2026-09-14).** `output/graph.json` is two things at once: the site's data and
the pipeline's own state file. `load_existing_graph_payload` re-feeds it as a
payload on the next build, `merge_node` carries forward any key it does not
handle, and the Treasury family, `synthetic` and the cost anchor exist nowhere
else on disk — so a field stripped from it is data lost, not bytes saved. The
release gate, `scripts/node_audit.py` and `scripts/nominate.py` read it too.
So it stays whole, pretty-printed and committed, and the browser gets
`output/graph.min.json` instead: the same 5,402 nodes with every field `js/`
never reads removed and the whitespace dropped. **4.0 MB against 10.3 MB.**

`MINIMAL_GRAPH_FIELDS` is the frontend's actual read set, and the list is only
safe because `js/` names every field it reads — there is no `Object.keys`, no
`for...in` and no variable-key access on node data anywhere in it, and
`normalizeNode`'s `{...DEFAULT_NODE, ...rawNode}` carries keys through without
naming any, so an absent key is simply absent. `tests/test_viewer_graph.py`
pins both halves: no dropped field is named in `js/` (with four documented
exemptions, each checked by hand — a nested sub-key, a value comparison, a
local variable, and the expansion-only `attachToRoot`), and the full graph
still carries everything the next build needs back. Nested objects are kept
whole; the panel reads many sub-keys of each.

**Both expansion overlays are off.** `expanded_edges.json` has always been
`[]` — nothing in this project has ever produced a relationship, so the "how
it connects" overlay draws nothing. `expanded_nodes.json` was 1.5 MB in which
**all 546 nodes were already in the tree**, so merging it changed no
structure — but it did change data, for the worse: `mergeNodeData` overwrote
the curated `employees` text with a bare integer on **151 nodes**, which is
why the Legislative Branch read "30000" rather than "~30,000 (total
congressional staff)". Both files are still written, because they are the
pipeline's export record; they are simply not fetched. A `null` in
`GRAPH_DATA_SOURCES` means "no overlay", the convention `corporate` already
used. Together with the pruned copy, a visitor parses **4.0 MB instead of
11.8 MB** and receives about 228 KB gzipped instead of 517 KB.

Nothing anywhere reads `expanded_nodes.json` back in; a comment in
`build_graph` claiming it "is re-fed as a payload on the next run" was simply
wrong and is corrected — only `graph.json` is.

GitHub Pages serves the repository root from `main`. Everything the page
fetches is tracked: `index.html`, `js/`, `data/federal_gov_complete_1.json`,
`output/graph.min.json` and the remaining `output/*.json` files. `.nojekyll` stops Pages running the
content through Jekyll. The favicon is an inline `data:` URI rather than a
file, so no request 404s. Two things load from outside the repo and are
outside its control: Three.js from unpkg and the fonts from Google Fonts —
neither is reachable from the pipeline's own sandbox, so
`scripts/frontend_smoke.mjs` rewrites the Three.js import to a local copy and
that one import is the only thing the smoke check cannot prove.

### Exact-node costs, and what the graph does not claim

`docs/EXACT_NODE_COSTS.md` is the standing answer to "why is most of this
graph an estimate". 139 of 5,402 nodes (2.6%) carry a cost a record names
for them; those cover **98.4% of the anchor**, so the apportioned figures
subdivide measured money rather than invent it — which does not make a
subdivision a measurement. **Since 2026-09-09 the site does not show one by
default**, by the owner's decision: a node with no measured cost of its own
shows no figure and says why, and ticking "Also show estimated shares of a
parent's total" opts back in. The exception is a real salary — **311** of the
4,591 positions now carry a rate of pay an official source states: 99 from the
Executive Schedule as 5 U.S.C. §§5312–5316 sets it, 166 from the White House
roster, 30 from the archive's level joined to OPM's table, 18 statutory. Shown
in the cost block under its own heading and never headed COST.

That figure read **354** until 2026-09-19 and was wrong: it added up the
*records* each source derives rather than counting the nodes that publish one,
and the archive's 46 pay records yield 30 published `positionPayRate` blocks
because the rest carry a level or grade and no rate. The published count is
what the site shows, so it is the one stated here; it was 310 before the §9
renames and is 311 after. The estimates
stay in `graph.json` because the cascade's arithmetic and the gate's
child-sum checks are built on them, so a consumer of the JSON must read
`cost_status`, not `resolved_total_amount` alone. The gate prints both
coverage numbers on every run so "789 nodes with a cost" cannot be read as
789 known costs.

That document also works through **every one of Table 5's 78 section
totals** and says why each does or does not reach a node, so the analysis
need not be redone: 41 reach one, 17 are Treasury's own funds and
groupings, 5 are object-class slices of a DoD total already applied, 9 are
intermediate groupings covering several curated nodes each, and 5 name
units the graph has no node for (curation, ~$78B). Exactly one alias was
addable and is added: `Office of Federal Student Aid` → `exec-dept-ed-fsa`,
replacing a $13.37B apportioned share with the statement's measured
$76.05B — a 5.7× correction on a real node, licensed by the same-section
rule and not by size, since $76.05B exceeds Education's own $52.94B net.

A measured cost may sit only on an organisation: an external review of an
older checkout reported Treasury outlays published on a node typed
Position, which is not true here (the exporter has always excluded
position, committee, role and caucus types from name matching) but was not
forbidden by anything. It is now. That document also records which of that
review's findings survive a check against this branch — most do not, it
was run against a different tree — and the achievable route to more
exact-node costs: a reviewed identifier crosswalk first (CGAC, TAS,
toptier and OMB codes, names proposing candidates and never publishing
facts), then USAspending File A/B at TAS level, then agency AFR Statements
of Net Cost. 84% of the nodes are positions, which no federal financial
system reports on; the target is not full coverage but that every figure
says which of outlays, obligations, budget authority, audited net cost or
salary it is.

**USAspending File A, beside the cost and never in it (since 2026-09-17).**
The crosswalk `docs/EXACT_NODE_COSTS.md` §1 asks for got its first pass the
day the network opened: USAspending's toptier agency list (the 111 DATA Act
reporters with their CGAC codes) and, per matched agency, the `sub_components`
bureau list — Treasury's own GTAS grouping, each bureau with a stable slug and
FY-to-date `total_outlays` — were fetched verbatim into
`tests/fixtures/usaspending/` (README there; 130 files, every one with its
`.meta.json` and sha256), and phase 2 re-nominated the 619 organisations it
had declined for want of the network: **47 File A keys proposed, 572
refused** with the reason on the record (313 have no DATA Act reporter at
all — committees, the courts, LOC/GPO/AOC/USCP/CBO, CIA, USPS, the
Smithsonian, the Fed; 221 are not separable under their toptier; 38 are an
ancestor's key). `data_pipeline/verification/usaspending.py` then applies a
proposal only where the API's name and the node's reduce to the same
canonical key — the test `evidence.py` uses for a page label and
`financial_evidence` uses for `scopeMatch: exact`. **37 pass that test** and
publish `verified`.

The other ten were, on 2026-09-17, all held under one reason, and that reason
was doing two different jobs badly. **Six were spelling**: an abbreviation
("Admin" for "Administration", "Corp" for "Corporation"), the "Office of"
prefix the API drops, or a rename the graph records both sides of
("Broadcasting Board of Governors / USAGM"). Refusing those was a string
comparison failing, not a doubt about which unit was meant, so
`USASPENDING_NAME_ALIASES` records each with the basis on which the two names
denote one unit — and an alias buys nothing beyond that: the record is filed
`scopeMatch: proxy` and graded **`partial`**, because `exact` is re-derived
from the names by the validator and would grade `verified`, a stronger claim
than writing an alias down can earn. That is the same deliberate downgrade
`judicial_pay.py` and `congressional_pay.py` make. The gate mirrors the table
by node id, so an alias moved to another node is caught even though both
names it quotes are real. **43 organisations now carry `usaspendingOutlays`**
(20 toptier, 23 bureau), 6 of them on an alias and graded partial, and the
panel says so in as many words rather than leaving a reader to wonder why the
quoted name differs from the one above it.

**Two are not spelling and no alias may touch them**, because USAspending's
entity is a larger thing containing the node: the VBA's key would be
"Benefits Programs", Treasury's grouping of the accounts it administers, at
$233bn, and the NSC's would be "National Security Council and Homeland
Security Council", covering a body this graph has no node for. Aliasing
either publishes a bigger unit's money as this one's, the first of the three
scoping failures `docs/COST_NOMINATION_RUNBOOK.md` names, so both stay held
under `awaiting_review_api_entity_is_broader` — a reason that says which
problem it actually is.

The seventh alias changed no figure and is the most useful of them.
AmeriCorps was held on its spelling, which hid the real blocker: `CURATION.md`
§2 already records the Corporation for National and Community Service as its
statutory name, and with that written down the record falls through to the
rule underneath — the fixture prints an `outlay_amount` of `0.0`, and zero is
never published as a measurement. The FTC's key is refused for the same
reason.

The figure is `gross_outlays`: File A's `GrossOutlayAmountByTAS_CPE`, which
the DATA Act specification crosswalks to GTAS SF 133 line 3020 "Outlays,
Gross" — *gross*, before the offsetting collections the Monthly Treasury
Statement nets off, and fiscal-year-to-date as of the fetch. So it is a
different measure from the Treasury line the graph publishes as a node's
cost, and everything about it is built to keep the two apart: it writes no
cost field, the panel prints it under its own heading ("GROSS OUTLAYS —
USAspending File A (FY2026 to <date>; not the cost)") with a sentence saying
which system it came from, `cost identified for the node itself` stays at
136 by design, and the gate's check re-reads the fixture by the block's own
key — digest recomputed from the bytes, the API's name still reducing to the
node's, the figure the row prints — and refuses the block anywhere its
amount equals the node's measured cost to the cent, since gross is not net
and equality there means the figure leaked. Where it is most useful is where
the graph honestly publishes no cost: the EOP offices beneath the Executive
Office's negative Treasury pool now carry a sourced, dated File A figure
beside that blank.

**The scale, stated the only way this publisher states it.** USAspending's
JSON prints `117451319504.29` with no currency mark and no heading, and its
endpoint documentation is served client-side from a non-`.gov` host, so the
validator's two existing scale rules — a phrase such as "in thousands", or a
`$` printed on the figure — cannot see it. What the publisher does state, in
its own Data Dictionary crosswalk (`data_dictionary_crosswalk.xlsx`, fetched
verbatim from files.usaspending.gov), is which DATA Act element each API
field carries, and that element is the Treasury's own SF 133 dollar figure.
`DICTIONARY_SCALED_SOURCE_TYPES` grants exactly this source type a third
rule, `publishers_data_dictionary`: the record must quote the dictionary's
mapping row (both the API field and the DAIMS element) and name the
workbook's digest, the derive step re-reads the row from the committed
workbook, and the gate recomputes the workbook's digest again. It is the same
shape as `_prints_whole_dollars` — granted per document class somebody here
has read, recorded in `unitsEvidenceKind` on every record — and the
validator's own plausibility ceiling is what bounds a units error.
`tests/test_usaspending.py` pins it both ways: a name-equal key applies and
the fixture's own figure is what is published; an unequal one is held with
its confidence; a tampered fixture, a post, a renamed node, a zero and a
figure equal to the measured cost are each refused; the block is withdrawn
with everything else the evidence modules own.

**Audited net cost, the third step of the route, and it needed no PDF (since
2026-09-20).** `docs/EXACT_NODE_COSTS.md` names three steps toward exact-node
costs and puts "agency AFR Statements of Net Cost" last and hardest, because an
Agency Financial Report is a large PDF per agency. It turned out not to need
one: Treasury publishes the consolidated **Statement of Net Cost** as structured
JSON on `api.fiscaldata.treasury.gov`, the same service this pipeline already
crawls for the Monthly Treasury Statement, whose `robots.txt` answers 404 —
nothing published to obey. The response is committed verbatim at
`tests/fixtures/treasury/net_cost/` and `net_cost.load_statement` recomputes its
digest before reading, the refusal `pay_tables` makes.

This is the only cost figure in the project **an auditor outside the reporting
agency has checked**, and it is still not the graph's cost. Three differences
ride on every record and on the panel:

- **Basis.** Net cost is accrual — gross cost less earned revenue, what a
  unit's programmes cost to run. The graph's measured figure is the statement's
  *net outlays*, cash out of the door.
- **Period.** FY2025, a year that has **ended**. The anchor is the current year
  to date. The panel prints both dates rather than one.
- **Scope.** 40 reporting entities, of which 7 name no unit of government —
  "Total" (the whole government, $7.3tn), "All other entities", "Security
  Assistance Accounts", "Interest on Treasury Securities held by the public".
  Those are refused by name rather than matched to the nearest node, for the
  reason `headcounts.py` refuses an agency whose whole entry is one other unit:
  aliasing the Total anywhere would publish the government's cost as one
  agency's.

Matching is canonical-key **equality** and there is no alias table, because none
is needed: **33 of the 40 rows reach exactly one node and none reaches two.**
The contrast it publishes is the useful part — the Department of the Treasury's
audited net cost is **$296.8bn** beside **$1,520.3bn** of measured outlays, and
the difference is interest on the public debt, which is cash out but not a
programme cost.

The scale is stated by the publisher **in the column name** (`net_cost_bil_amt`,
billions), which is a third way a unit can be known beside
`financial_evidence`'s "prints a currency mark" and "says so in its data
dictionary"; every record records which one it rests on in `unitsEvidenceKind`.
`auditedNetCost` is in `EVIDENCE_OWNED_FIELDS`, so a withdrawn record stops
being published; the gate re-derives each figure from the committed statement by
the block's own agency name, refuses a block on a post, one whose name the node
no longer carries, one citing a digest the file does not have, one that does not
say which year it covers — and, outright, one whose amount equals the node's
measured cost to the cent, since different basis and different period means
equality can only be the two being confused.

**OMB's Public Budget Database, and the source where most of the columns are
the future (since 2026-09-20).** `docs/EXACT_NODE_COSTS.md` §1 asks for a
reviewed identifier crosswalk as the first step toward exact-node costs. OMB's
**Public Budget Database** is that crosswalk with the money already attached:
one row per budget account, carrying the account's agency, bureau, Treasury
agency code, **CGAC agency code**, subfunction and BEA category, and a figure
for every fiscal year from 1962 to 2031. `www.govinfo.gov` answers `robots.txt`
200 and allows the path; the package (`BUDGET-2027-DB`, 3.9 MB, two
spreadsheets and a user's guide) is committed verbatim at `tests/fixtures/omb/`
and its digest is recomputed from the bytes before anything is read.

**This is the most dangerous source this project has read, and the danger is
not subtle: most of its year columns have not happened.** The FY2027 package
runs to FY2031, and the columns are identical in form — bare four-digit
headers, no marker of any kind in the spreadsheets. The boundary appears in
exactly one place, the user's guide:

    "Budget estimates for the current fiscal year (2026), the budget year
     (2027), and each subsequent year are prepared by agencies"

so FY2025 is the last actual. The guide says the same thing a second time, in
a different part of the document and a different form — the per-file field
tables read "30-78 | 1977-2025 values | Actual amounts, in thousands of
dollars" against "79-84 | 2026-2031 values | Estimated amounts, in thousands of
dollars, for FY 2026 through FY 2031". **Both are parsed out of the committed
guide on every run and must agree**, or `load_database` refuses to return
anything at all; the gate then reads the boundary again, independently. Two
reads rather than one because every other check in this module would pass
happily on a projection. The
boundary is not a constant anybody can edit; it is what the publisher printed,
re-read each time. A year-column slip is the one error here that no
plausibility check could catch, since FY2026's estimate is a perfectly
reasonable-looking number, so it is guarded structurally instead.

Reading the guide needed its own extractor. The PDF splits words across literal
strings and spaces them with TJ kerning offsets, so `whitehouse_pay`'s
`extract_text_runs` — which this repo already uses for the White House
roster — returns **zero characters** for it. `guide_text` concatenates the
strings with no separator and emits a space only where the kerning is wide
enough to be a word gap, which is what turns "t hous a nds" back into
"thousands". One residual split survives and is handled by quoting around it:
the guide's "Treasury Fiscal Service" recovers as "Fi scal", so the quoted
clause stops before those words rather than publishing a typo the document does
not contain.

**The publisher states no figure for any unit.** There is no total row anywhere
in this database — every one of the 5,760 outlay rows is a budget account — so a
unit's figure is not something OMB prints, it is **this repository's sum over
the account rows OMB files under that unit**. The Department of the Treasury's
$1.46 trillion is 368 rows added together. So every record carries
`outlayAccountRows` and `budgetAuthorityAccountRows`, the gate re-counts them
from the package, and the panel says "these are not figures OMB prints … each is
the sum of the 368 account rows OMB files under it" rather than "OMB reports",
which would attribute an arithmetic result to a publisher who never performed
it. The first version of the panel copy said "OMB's Public Budget Database
reports these", and that was wrong.

**The unit is thousands — not millions — and precise only to the million.** Both
from the guide: "Data for budget authority, outlays, offsetting receipts, and
governmental receipts are shown in thousands of dollars", and "the file data
from FY 1995 through FY 2031 represent the Budget amounts multiplied by one
thousand to convert the amounts to thousands ; detail below millions is not
available." So a figure is exact to the million whatever its trailing digits
suggest, and the gate refuses a block that does not carry that second sentence.
Summing the FY2025 outlay column over every row gives $7.011 trillion, which is
the right order for the year and corroborates the stated unit without replacing
the publisher's statement of it.

**A negative figure is normal here** and is published as it stands, for the
reason the Treasury's own negative lines are. OMB: "Budget authority and outlay
amounts are reported net of any offsetting collections, such as fees, fines,
and penalties", and "Outlays are usually positive values. Offsetting receipts
are usually negative values." Ten of the 133 units net below zero — the FDIC at
−$31.2bn, the SEC, the NCUA, the Export-Import Bank — because they collect more
than they spend. Both sentences ride on every record so the panel explains the
minus sign rather than leaving a reader to assume a bug.

**It is not this graph's cost.** Different period (a completed year against the
anchor's year to date), and OMB's own guide calls its totals only "generally
consistent with data published in the Monthly Treasury Statement", then says
why they differ: "a small number of reporting and classification corrections
made subsequent to the Treasury publications and some conceptual differences
between OMB and Treasury reporting". *Generally consistent* is not *the same*,
and the publisher is the one saying so. Nothing writes a cost field, no
`sourceUrls`, no `verificationMethod` — that channel is exactly how a five-row
pay table carried 29 positions to `verified` on 2026-09-11.

Measured rather than asserted: **94 nodes carry both an OMB FY2025 figure and a
measured Treasury cost, and not one of the 94 agrees within 1%.** The median
ratio is 0.863 — the graph's eleven months of FY2026 against OMB's completed
FY2025 — with the Department of Labor closest at 1.019 and Health & Human
Services at 0.967. That is what two honest figures for the same unit on
different clocks look like, and it is why the gate's "equals the measured cost
to the cent" check is a leak detector rather than a tolerance.

**Matching is scoped the way a FedScope row is**, and three guards each earn
their place on the real data:

- a **type guard**: without it OMB's agency "Legislative Branch" reaches the
  Senate Appropriations *Subcommittee on the Legislative Branch*, a real node
  with a unique name in entirely the wrong branch, and every legislative bureau
  would then be scoped underneath a subcommittee;
- **uniqueness of the bureau name across the whole file**: this database
  restates history onto the current account structure, so "Bureau of Labor
  Statistics" appears under Commerce as well as Labor and the name alone
  identifies no single row;
- the **subtree guard**, which after the other two refuses exactly one pair:
  OMB files the Pension Benefit Guaranty Corporation under the Department of
  Labor and this graph curates it as an independent agency. Both are
  defensible — the PBGC's board is chaired by the Secretary of Labor — so
  nothing is resolved, the row is refused, and `CURATION.md` records it, the
  treatment the Treasury's Tax Court line already gets.

**Two identifiers this source does not have, and one choice it forces.** The
`CGAC Agency Code` column is what made this package worth fetching — it is the
crosswalk `docs/EXACT_NODE_COSTS.md` §1 asks for — and it is **per account, not
per agency**: 20 of the 160 agencies carrying a code carry several, the
Department of the Treasury nine and the Legislative Branch twenty-two, because
OMB's "Agency" is a budget-presentation grouping over several Treasury
entities. The first version published the first code seen, which is an
identifier the file never assigns to the unit. A code is now published only
where the agency has exactly one, the count rides beside it either way, and the
gate refuses both a code on a multi-code agency and a count that is not the
package's. 102 of OMB's codes are shared with USAspending's toptier list and 88
of those agree on the name, which is the join to build on — by code, one day,
rather than by name.

And the row selection is a choice, not a given: summing every row rather than
the on-budget rows alone is worth **13×** on the Social Security Administration
($1,646.5bn against $125.6bn). Every record therefore declares the rule it used
in words ("every account row OMB files under this unit for the year, on-budget
and off-budget together, including the negative offsetting-receipt rows"), and
the gate refuses a block that does not. A figure whose selection rule is not
stated cannot be audited.

**133 organisations carry a figure** (61 agency, 72 bureau), **39 of which
publish no measured cost of their own**. A measure the package carries no row
for is published as ABSENT, never as zero: the two member files do not cover
the same units — the Farm Credit Administration has outlay rows and no
budget-authority rows — and the first version defaulted the missing one to 0.0,
which the gate caught as a figure the package does not carry.

The gate re-derives everything from the package with a **second, independent
stdlib reader** (an .xlsx is a zip of XML, the same fact `congress.read_xlsx_rows`
uses) importing nothing from the module it checks, and refuses: a block on a
post, a fiscal year that is not the guide's last completed one, a figure or a
row count that is not what the package gives, a unit name that is not the
node's, an agency-level block carrying a bureau name (the one way this block
can lie while every number in it stays right), a missing units, precision or
net-of-collections quote, and a citation that does not point at govinfo.
`tests/test_omb_budget.py` corrupts each in turn.

### Names that state a count

Eight curated groupings state a number in their own name. Four carry it
("Mission Teams (15)"); four do not — Individual Senator Offices (100)
carries 18, Individual Representative Offices (435) carries 15, District
Offices (68) carries 4, Federal Public Defender Offices (82) carries 7 —
and a reader who expanded one had nothing telling them the rest were
absent. 742 position nodes carry a multiplicity instead (35 exact, 23 a
range, 684 an unstated "×multiple"), each drawn as one node with one
apportioned figure. `annotate_stated_counts` publishes the name's number
beside the graph's (`statedChildCount`, `carriedChildCount`,
`childrenIncomplete`, `representsPosts`); the panel says the rest are not
in this graph at all, and that a multi-post node's figure is for the group
and not one holder. Nothing is corrected — that is curation — and where
the name gives no number none is invented, which the gate enforces along
with the arithmetic and the requirement that the quoted text really is in
the node's name. Every field is cleared and recomputed each build, so a
rename withdraws the claim.

### The three agent phases

Three runbooks, run in order over the same nodes (5,195 when the runbooks
were written; 5,402 today), each with a harness
that refuses what it cannot adjudicate. All three write **only** to
`data/audit/`; none edits the curated file, the published graph or any
evidence file, which is what makes it safe to point many agents at the whole
tree.

| Phase | Runbook | Harness | Writes | Asks |
|---|---|---|---|---|
| 1a | `NODE_AUDIT_RUNBOOK.md` | `node_audit.py` | `node_audit.jsonl` | Is what the site says about this node supported? |
| 1b | `SOURCE_NOMINATION_RUNBOOK.md` | `nominate.py --kind source` | `nominations/source-*.jsonl` | Which page should the verifier fetch for it? |
| 2 | `COST_NOMINATION_RUNBOOK.md` | `nominate.py --kind cost` | `nominations/cost-*.jsonl` | Which record would give it its own cost? |

Phase 2 reads phase 1's ledger before nominating and skips any node the audit
called a duplicate, not a real unit, wrongly parented or stale-named: a
financial identifier on a node about to be merged or moved looks like
evidence for the wrong thing. It feeds back the other way too — an identity
problem found while chasing money goes into the audit ledger with `--force`.

**Phases 1b and 2 are deliberately weaker than 1a, and that is the design.**
A nomination is not a claim: `official_sites.json` has always said a URL there
is "something to check, not evidence", so an agent may propose a page it
cannot read and the verifier adjudicates by label equality. The worst a wrong
nomination does is waste one fetch. Both refuse `confidence: certain`
outright — an agent that cannot read the source has no way to earn it — and
both refuse what could never be adjudicated at all: a host the verifier will
not fetch, a dataset URL offered as a unit's own page, a URL already tried and
failed, a metric outside the five (`net_outlays`, `audited_net_cost`,
`obligations`, `budget_authority`, `basic_pay`), an identifier with no basis.
`nominate.py promote` is the only command that writes outside `data/audit/`:
it adds candidates to the verifier's fetch queue and records each one's run,
basis and confidence in `official_sites_provenance.json`. Two rules fixed by
the 2026-09-13 brute-force pass (13 Sonnet agents, one shard each, live
fetches, `source-brute1.jsonl`, 371 records): the ledger's "later record
wins" is by `nominatedAt`, not by file name — `source-brute1` sorted before
`source-pass1` and 371 live-fetched records were shadowed by the blind
declines they replaced, so `promote` queued one page of 160; and a URL is
refused as "already fetched" only when it was fetched *for this node* — a
parent's page is read once and lists many children, and the global rule
had refused senate.gov as the page that labels the Secretary of the Senate.
`label_matches` tests the whole fragment before splitting it on separators:
"Division of Social and Economic Sciences (SBE/SES)" was split at the "/"
before the key dropped the parenthetical, and a page naming the unit exactly
was recorded as not naming it.

**Which key a nominated URL is filed under is what it CLAIMS (since
2026-09-18).** `official_sites.json` is keyed by node, `candidate_urls`
returns `distance == 0` for any URL under a node's own key, and `verify_node`
turns `distance == 0` into `name_labelled_on_own_official_page`. `promote`
wrote every nomination to `sites[node_id]` whatever its role, and the role
went into `official_sites_provenance.json` and was never read again — so the
runbook's documented promise, that a `parent_listing` publishes
`name_labelled_on_parent_official_page`, was implemented nowhere. **20
confirmations were live under it**, among them nine Department of Energy
national laboratories each citing `energy.gov/national-laboratories`, the
department's index of them, as *its own* official page; also JPL on nasa.gov,
three presidential libraries on archives.gov, the Secretary of the Senate,
Federal Student Aid and the CAAF.

**A refiling is not a wasted nomination (since 2026-09-20).** `record` refused
a URL already queued under the node's own key, and a URL already fetched for
the node — right for `own_site`, and exactly wrong for the one case
`--refile-misplaced` exists to repair, since the ledger is its only input. The
sweep's verifiers found 35 subcommittees carrying their committee's index
page as their own, 26 published `verified` on it; both rules now apply to
`own_site` only, and a re-nomination under a role that files the URL
elsewhere records as a refiling (`tests/test_nominate.py::RefilingTests`).

**A listed placement publishes the existence it is (since 2026-09-20).** A
node whose own queued host is walled reached the site with existence
`fetch_failed` while the placement pass had already read the parent's page
and found it listed by name — Federal Student Aid and six DOE labs. This file
already treats a parent-page confirmation as placement without a second
fetch; `apply_evidence_to_tree` now does the reverse, stamping
`name_labelled_on_parent_official_page` from the placement block when no
method exists, quoting the label only on a folded committee match as the
confirmed path does, and dropping `verificationUnread` for the page that was
read. Never on a post, which never carries a placement.

`filing_id_for_role` is the rule now: `own_site` files under the node, so the
claim is true; `parent_listing` files under the node's **parent**, so the
verifier finds it one level up, `is_own_page` is false, and it publishes what
the runbook always said; `official_list` files **nowhere**, because a
government directory is neither the unit's page nor its parent's and both
available methods would misdescribe it — structured directories have their own
modules here (the Federal Register's, the Senate's, the House Clerk's), which
is where such a source belongs. `promote --refile-misplaced` repairs a queue
written before the rule (63 URLs moved onto their parents, 19 dropped), moving
each provenance record with its URL so the committed queue/provenance
invariant still holds, and touching only URLs the ledger says were nominated
for that node — a seeded URL with no nomination is left alone, because nothing
knows what it was meant to be.

The retraction had to be able to reach the site, too. A node whose candidate
page is removed was simply *skipped*, so its old confirmation stayed and the
exporter kept publishing it — the same "a retraction that could never reach
the site" this file already records once. `verify_base_graph.py` now withdraws
such a record on a full pass (never on `--ids` or `--limit`, which say nothing
about the nodes they did not select), keeping any placement block, which came
from the parent's page and does not depend on this node having a candidate of
its own.

It was found by a second-opinion agent that had nothing to nominate — all 21
nodes in its shard were Smithsonian museums, correctly declined
`not_on_a_gov_host` — and reported the mechanism instead, naming both files
and both line numbers. Checked against the live evidence file before being
believed.

**Many agents at once.** `--shard k/N` partitions the work deterministically
(disjoint and complete, pinned by a test) and each run writes its own ledger
file under `data/audit/nominations/`, so N agents never touch the same file
and their branches merge without conflict. Positions and synthetic lines are
never handed out for page nomination — 4,382 positions would produce 4,382
identical refusals — but a position *can* carry a cost nomination, its rate of
basic pay, which is never the unit's cost.

The standing numbers this work exists to move: 294 of 807 organisations have
no candidate page at all, so the verifier can never reach them; and 139 of
5,402 nodes carry a cost identified for themselves. `nominate.py status --kind
source` prints the first and `validate_published_graph.py` the second; those
are the copies to trust, and neither is restated by hand any more.

### The node-by-node audit

`docs/NODE_AUDIT_RUNBOOK.md` is the brief for an agent examining all 5,402
nodes one at a time; `scripts/node_audit.py` is the harness. `next` hands
over a batch of nodes with every claim the site makes about each and every
evidence record keyed to its id; `record` validates findings and appends
them to `data/audit/node_audit.jsonl`, which is the audit's **only** output
— nothing in this path edits the curated file, the published graph or any
evidence file, so an agent turned loose on the whole tree cannot damage it.

The harness exists for one reason: an agent 400 nodes into a mechanical
sweep stops reading and starts pattern-matching, and writes down a
quotation that is not on the page. So `record` re-reads every cited file
and **rejects the whole batch** if a quoted string is not in it — whole
batch, not the bad record, because letting the good half through teaches
that some invented citations survive. Whitespace is normalised (these files
are hard-wrapped and an honest sentence-length quote crosses a newline);
nothing else is. A `certain` or `likely` finding must carry evidence;
`speculative` is the one level that may stand alone, and is how a question
gets raised without being dressed as a fact. Citable sources are the
repository's own published files and `.gov`/`.mil` URLs. Seven checks per
node with fixed vocabularies, and `no_evidence_in_repo` is the honest — and
most common — answer, not a failure: 4,713 nodes carry no source at all.
`verify` re-checks every citation in the ledger against its source, since a
file can change after a finding was accepted. The runbook's "do not report
these" list matters as much as the rest: without it the sweep returns
"description is uncited" 5,155 times and buries the real findings.

## Invariants

- Root id is `the-constitution-of-the-united-states`; it has exactly the
  three branch children, plus at most the one Treasury accounting line for
  the government-wide offsetting receipts.
- Measured costs are the root anchor and the Treasury Table 5 lines applied
  to the nodes they name, the receipts lines the exporter carries
  explicitly included; nothing else is `verified`. Every amount carries a
  `cost_status`; a missing amount is labelled `unavailable`; zero is never
  published; a negative amount is only ever a Treasury line, a receipts
  line, or an estimate for a grouping whose measured members net below zero
  (`measured_net_beneath`). Children never sum past their parent, signed,
  except by a declared `treasury_pool_negative`, and a line filed under
  another Treasury section is outside its parent's sum. No node has both
  `attachToRoot` and a `parentId`. `sourceCount` equals `len(sourceUrls)`;
  `costSourceCount` needs a URL, a rollup, or (root only) the anchor. No
  duplicate ids. `scripts/validate_published_graph.py` enforces all of these
  and must pass before a regenerated graph is committed.
- A USAspending File A figure lives only in `usaspendingOutlays`, labelled
  gross and fiscal-year-to-date, and is never a cost: nothing writes it into
  a cost field, and the gate refuses the block on a post, on a node whose
  name the API no longer prints, from a fixture whose digest has changed, or
  wherever its amount equals the node's measured cost to the cent.
- A curated node's name and type come from the base file, never from a
  payload copy. Anything a crawler adds to a base node merges around them.
- A run that refuses to publish exits nonzero from every entry point
  (`run_pipeline.main`, `run_once.py`, the scheduler) and names the failed
  stage in `stage_errors`; a crawler that returned part of its data
  (Wikidata with one query failed) is `partial` in `stage_results` and
  listed in `stage_warnings`.
- `lastVerified` is never invented: a node carries a date only if a record
  supplied one — a crawler record or a verifier fetch at that moment. The
  site's "No source recorded" state keys on that. `data/verification/` is
  written by the verifier only; a URL in `official_sites.json` is a
  candidate to fetch, never evidence by itself. Candidates may be seeded from an
  official directory by `scripts/seed_official_sites.py` (the Federal
  Register's `agency_url`, the chambers' committee pages); every seeded
  URL is marked in `official_sites_provenance.json` with the directory's
  own listing, and an `http://` listing on a `.gov`/`.mil` host is used as
  `https://` with the listed URL kept beside it — the scheme is transport,
  not a claim, and the verifier still has to find the label.
- A run that lost its Treasury anchor or every fetch stage must not touch any
  file the site fetches. It does rewrite `output/pipeline_stats.json`, which is
  the run record: that record is `mode: blocked_run`, carries
  `published_artifacts: "unchanged"` and a `previous_run` block describing the
  graph still on disk, and omits `verification_breakdown`,
  `average_confidence_score` and `verified_node_count` rather than zeroing
  them — this run measured no graph, and a zero would read as if it had.
- `output/` is gitignored for new files, but the files the site fetches are
  tracked and must stay committed (GitHub Pages serves them). Never commit
  `pipeline_stats.json` with the per-node audit embedded.
- `enforce_export_gate` is threaded from `run_pipeline` to `build_graph` so
  tests can exercise plumbing with the gate off; production keeps it on.
- A Treasury line is applied to a node only when the name identifies one line
  and one node. A name several lines carry (Table 5 prints "Department of the
  Navy" eight times, once per budget category) is reported ambiguous, never
  resolved by picking the largest — the exception is a unit's header line
  beside its own `Total--` line, which is one unit reported twice.
- A build that was handed no Monthly Treasury Statement carries the published
  Treasury lines forward instead of clearing them
  (`payloads_carry_treasury_statement`). `regenerate_published_graph.py`
  rebuilds offline and passes no outlay rows; the stale-rollup sweep used to
  run anyway and republished a graph with every measured cost stripped, which
  the release gate passed because no rule forbids a graph without Treasury
  lines. A statement that has stopped reporting a node still clears it.
- An alias is added to `TREASURY_ROW_ALIASES` only when the line belongs to
  the section of the node's ancestors, or the node is placed where the
  statement files it. Two were added on 2026-09-18 where the Treasury's
  account name had simply not caught up with a rename: `National Protection
  and Programs Directorate` → CISA, licensed by 6 U.S.C. §652(a) (committed at
  `tests/fixtures/uscode/cisa_6_usc_652.html`), which deems "any reference to
  the National Protection and Programs Directorate … in any … document, record
  or other paper of the United States" to be a reference to CISA — Table 5 is
  such a record; and `United States Agency for Global Media` → the node the
  graph itself names "Broadcasting Board of Governors / USAGM", which needs no
  outside source because the curated name already states the two are one unit.
  Both are filed by the statement under the section the graph gives the node. Since the receipts are carried explicitly a line
  always fits inside its own section's total — Federal Student Aid's $76B
  inside Education's $53B net beside the section's receipts — so "fits" is
  no longer the test; "the same section" is. A line from another section
  publishes as external, measured, outside the parent's sum.

## Known base-graph gaps

This section used to list sixteen Table 5 units the curated graph had no node
for at all. **Fifteen of them were added on 2026-09-19** by
`scripts/add_curated_nodes.py` under the `treasury_statement_line` licence,
and every one now carries its measured cost (`cost_status: official`): GSA,
USAID, the Railroad Retirement Board, the Administration for Children and
Families, the Corps of Engineers, the Administration for Community Living,
the Agricultural Marketing Service, the Foreign Agricultural Service, the
Legal Services Corporation, the Economic Development Administration, the
Millennium Challenge Corporation, the FHFA, the CFPB, the IMLS and the CPB.
Checked against the published graph on 2026-09-20 rather than restated.

The one left is the **Corporation for National and Community Service**,
which is the AmeriCorps alias case `CURATION.md` §2 records: the graph's
node is named for the agency's current branding and the statement for its
statutory name, and the record falls through to the rule beneath — the
statement's line for it prints an outlay amount of `0.0`, and zero is never
published as a measurement.

A second, quieter gap surfaced the same day: a unit added under a licence
that is not the Treasury's — the Office of Surface Mining Reclamation and
Enforcement, added from the Government Manual — whose name equals a unique
Table 5 money line and whose cost stayed `allocated` for a day, because an
offline rebuild only carries previously applied lines forward and a line is
matched only on a build that is handed a statement. The phase 1c sweep
nominated it as a cost identifier; the same afternoon the current statement
(2026-08-31, the date the anchor already carried) was fetched through the
crawler's own functions to `tests/fixtures/mts_table5_2026-08-31.json` — the
pinned 2026-07-31 fixture is untouched — and one `regenerate
--treasury-rows` build applied the line: OSMRE is `official` at $1.18bn,
159 Treasury lines against 158. Any unit added under a non-Treasury licence
needs that same step before its line lands.

("Other Defense Civil Programs" and "International Assistance Programs" are
Treasury groupings rather than organisations; those stay unmatched by design.)

## Things that have bitten this repo

- A merge that resolved entirely to one side silently reverted 20 commits
  and deleted whole modules and these docs. Check `git diff --stat` of a
  merge before trusting its message.
- Validators that "ran happily and were wrong" three times in one week; every
  gate now has a test in both directions (good evidence passes, absent
  evidence fails).
- A missing producer (`treasury_outlays.py`) with consumers still wired made
  the export gate prune the whole tree; the publication guard exists because
  of it.
- Fixed-position UI elements injected from JS at the same coordinates as
  elements in `index.html` covered them; injected controls now live inside
  the flow of the element they belong to.
- The cost cascade summed a dollar budget, a headcount and a subtree count
  into one denominator, so the IRS was allocated $385B beside a Secretary
  of the Treasury at $32 and 120 nodes published "≈ $0". Weights must share
  a unit before they are compared.
- Re-feeding the previous graph.json through the normaliser rewrote curated
  names on every run ("Deputy Director / COO" lost its slash) and the merge
  let the copy win over the curated file.
