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
statement's 644 lines as of 2026-09-03. Every other node is either an
estimate apportioned from those figures, and must read as one, or publishes
no figure at all — on the graph as of 2026-09-23, 693 estimates and 4,657
with none: every post, every superseded unit and what sits beneath it, and
the unmeasured units beneath a Treasury pool that nets below zero.

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
python -c "import sys;sys.path.insert(0,'.');from data_pipeline.exporter.build_graph import DEFAULT_BASE_GRAPH,load_base_graph;from data_pipeline.verification.aliases import load_alias_table;t=load_alias_table(load_base_graph(DEFAULT_BASE_GRAPH));print(len(t),t.refusals)"  # adjudicate data/curation/node_aliases.json; CURATION.md §17
python scripts/add_curated_nodes.py --dry-run     # add a unit the graph lacks, licensed by the statement, a page or the Government Manual; CURATION.md §1
python scripts/mark_superseded_units.py --dry-run # mark a unit the government has replaced; nothing is ever deleted
python scripts/probe_network_access.py           # what this session can reach now, and whether a 403 was the proxy or the host
python scripts/derive_pay_evidence.py --dry-run  # the salary table joined to the listings' levels (the current export's where it lists the post, else the archive's); writes nothing
python scripts/derive_gs_pay_evidence.py --dry-run  # GS / SES / SL-ST base-pay RANGES for the listings' pay plans; writes nothing
python scripts/derive_plum_current_evidence.py --dry-run  # OPM's CURRENT Plum Book export matched to position nodes; the incumbent columns are never read; writes nothing
python scripts/derive_fr_signature_evidence.py --dry-run  # the title an official stated when signing a Federal Register document; the signer's NAME is never read; writes nothing
python scripts/derive_judicial_pay_evidence.py --dry-run    # uscourts.gov's own compensation table; writes nothing
python scripts/derive_derived_pay_evidence.py --dry-run     # a figure NO document states: a statutory parity provision joined to that table; writes nothing
python scripts/derive_tier_reference_pay_evidence.py --dry-run  # pay a statute sets BY REFERENCE to an Executive Schedule level (GAO's officers; the IG Act's Level III + 3%), joined to OPM's table; writes nothing
python scripts/derive_military_pay_evidence.py --dry-run  # Schedule 8 of the pay-adjustment order (the uniformed services' MONTHLY basic pay) joined to the statute fixing a post's grade; the annual figure is 12 × the printed one; writes nothing
python scripts/derive_us_code_stated_pay_evidence.py --dry-run   # an office's salary a Code section states in dollars (3 U.S.C. 102, the President); writes nothing
python scripts/report_unpriced_positions.py --dry-run        # every position with no pay claim, and the prompt pack that covers all of them
python scripts/report_cost_coverage.py --dry-run             # every node in exactly one cost class, and the route that would move each; writes docs/COST_COVERAGE.md
python scripts/report_research_prompts.py --dry-run         # the 100 title families holding the most unpriced posts in one prompt, the rest and every estimate in shards; writes docs/RESEARCH_PROMPT_4_*.md
python scripts/derive_congressional_pay_evidence.py --dry-run  # senate.gov's own salary schedule; writes nothing
python scripts/derive_whitehouse_pay_evidence.py --dry-run     # the White House Office's statutory staff roster; writes nothing
python scripts/expand_whitehouse_office.py --dry-run           # what the roster would add to the curated WHO subtree; writes nothing
python scripts/derive_usaspending_evidence.py --dry-run   # File A gross outlays for the crosswalk's name-equal keys and its reviewed aliases; writes nothing
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
PIPELINE_RUN_ONCE                 "1" (default) runs once; anything else loops daily (data_pipeline/scheduler/nightly_update.py)
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
  `resolve_root_orphans`, and writes `graph.json`, `graph.min.json` (the
  browser's copy), `expanded_nodes.json`, `expanded_edges.json`,
  `node_validity_report.json`.

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

**The statement's own lines beneath a header it totals nowhere (since
2026-10-06).** Table 5 prints some sub-agencies as a header with lines beneath
and no `Total--` line of their own — the Veterans Health Administration, the
NNSA, NRCS, BLM, the Bureau of Reclamation, the Office of Justice Programs,
TTB, the FCC, the Postal Service — and the crawler emits such a header with
`rollup_total_amount: None`, which `collect_treasury_outlay_rows` dropped. So
nine units whose header reduces to exactly one organisation node, each in the
section of its own ancestors, were apportioned by headcount and subtree size
while the statement printed their money line by line under their names:
**about $150.7bn**, the VHA's $100.4bn against an $80.2bn estimate, the
NNSA's $23.8bn against $4.9bn, the FCC's $9.9bn against $0.18bn, NRCS's
$5.3bn against $15.3bn. The twelfth batch's Treasury cluster found it and the
fixture confirmed it before anything was built.

`SectionTree.total_less_headers()` names such a header (no `Total--` child,
outside every receipts-type subtree per `receipts_component_ids`, at least one
line beneath), `header_components` lists its lines — a receipts-type child is
ONE component at its own netted amount, the shape `make_receipts_node` uses,
and a sub-header is descended into, since "Postal Service:" prints an
"Off-Budget:" sub-header with two lines beneath and one beside — and
`derive_header_sum_rows` turns it into a row carrying the sum, stamped
`treasury_header_sum: True` with `treasury_component_rows` and a generated
sentence (`treasury_header_sum_note`: "The statement prints no total line for
this unit; the figure is the sum of the N lines it prints beneath the unit's
header, listed below."). The row joins the statement's rows AFTER the
receipts filter and BEFORE the key counting, so the ordinary one-line-one-node
rule covers it: "Defense Agencies:" is a header and the name of nine
object-class lines, and prices nothing. **It takes no alias.** An alias in
`TREASURY_ROW_ALIASES` is a reviewed identification of a PRINTED line, and a
sum is already one step from a printed figure, so the "Government National
Mortgage Association:" header (one line, −$1.84bn) reaches nothing while the
node is named "Ginnie Mae" — recorded, not forced. A sum of exactly zero is
never derived; a negative one is kept, the Mint's rule. A build handed no
statement carries the three fields forward with the other Treasury fields and
a fresh statement clears and re-derives them, so re-feeding the published
graph never duplicates one.

The claim is exact and the words say so: the figure is a sum this repository
performed over lines the statement prints, which the statement itself totals
nowhere — never "a line the Treasury prints". The panel prints the
sentence under the Treasury's source line and every component by name and
exact amount (`#info-cost-components`), the atlas the same in prose, and the
gate re-reads the components off the committed statement with its own stdlib
reading of the API rows — by classification id, parent id and the printed
amounts — and refuses a stamp on a post or a synthetic line, a sentence with
the wrong count, a figure that is not the listed lines' sum, a header that has
a `Total--` child or sits inside a receipts subtree, a header whose label does
not reduce to the node's name, components that are not the statement's lines
beneath that header, and a header whose key more than one matchable row
carries; `tests/test_treasury_header_sums.py` corrupts it nineteen ways and
pins the nine sums to the cent against the raw rows. One consequence to know:
the gate re-derives only from `tests/fixtures/mts_table5_*.json`, so a graph
built from a newer live statement fails the gate until that statement is
committed as a fixture — which this repository already does for every
statement it builds from.

**Measured on the rebuild, not asserted.** Nine header sums, 28 lines,
$150,714,848,412; measured nodes **160 → 170** and Treasury lines **159 →
169** — the nine, plus the one alias row the same cluster supplied,
`Corporation for National and Community Service` → AmeriCorps, the gap the
"Known base-graph gaps" section had carried since 2026-09-19 (AmeriCorps
`allocated` $1.37bn → `official` $941,240,516.35; the line sits in the
independent agencies' section where the node does). **140 nodes moved by more
than 0.1%**, every one an unlined sibling of something now measured: the
Energy Department's "National Laboratories" grouping fell from $34.9bn to
$19.2bn as the NNSA's money left its pool, each VISN rose a quarter as the
VHA's estimate stopped taking $80bn of the VA's remainder, the seven USPS
Areas fell from $2.82bn to $0.26bn each, and the CIA and its five directorates
rose from $0.73bn to $6.16bn, because the Postal Service's $22bn estimate had
dominated the pool the independent agencies share and the measured Postal
Service nets $2.06bn. Those moves are the honest direction, and the cascade's
weakness they expose is the one this file already records: wherever a sibling
group has no dollar or headcount evidence, one measured line landing beside
it redistributes everything else. `treasury_component_rows` is in the viewer
copy now, for the receipts lines as well, so the panel can list the lines.

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

`GENERIC_ADMINISTRATIVE_TITLES` in `build_graph.py` is that list plus five
titles the paragraph above does not name — `Deputy Director`, `Deputy
Director / Vice Chair`, `Chief Human Capital Officer`, `Director of
Legislative Affairs` and `Director of Public Affairs`, sixteen in all, the
five without the recurrence evidence recorded here for the other eleven — and
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
  anything ("Energy", "Defense"; 13 on 2026-09-23, 16 before the 2026-09-19 renames). Never fetched.

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
be checked", 231 of the gate's 918 organisation edges on 2026-09-23: the fifteen departments sit under a curated
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
a committee's is: `General Counsel` is the name of **92** nodes in this graph
and `Inspector General` of **80**, so the page it was found on and the exact
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

That is curation, and it was half fixed on 2026-09-15; since 2026-09-18, when
the U.S. Code supplied twelve more titles, 27 of the 28 are fixed (see "The
level half" below).
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
were misnamed. Confirmed positions went **20 → 25**. The other 13 stayed templated until 2026-09-18 (one, the Deputy Secretary of
Commerce, still is) because no source then in hand named them: the archive files those heads
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
and `expand_whitehouse_office.py` (`merge_duplicate_nodes.py`, which on
2026-09-18 merged the duplicate units `CURATION.md` §3 records, also writes
it; it is not otherwise named in this file and is left out of the ordinals
here and below). The table is the same shape as
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
(`Inspector General` names 80 nodes here and sits in every `.gov` footer), or
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

**The table holds eighteen rows, and how it got them is the point.** The case it
was built for was the VA's Integrated Service Networks: asserted on one true
sentence, retracted, then settled on a second VA host and the 301s the old pages
return — see `CURATION.md` §10. All eighteen former networks are superseded as
of 2026-07-14 with `supersededBy` empty, since the territories were redrawn
rather than renumbered.

**Directories — the government's own lists of itself.** When the first one
landed (2026-09-08) the page method was near its ceiling: 71 organisations had
a page of their own, twelve of the largest hosts refused `robots.txt` and were
refused in turn, 223 committees were never checked, and 520 edges hung under
curated groupings with no page. (Now: 532 organisations have a candidate page,
69 hosts' `robots.txt` refusals (401/403) stand in `evidence.json`, all 240
committees carry a record, and 231 edges sit under a parent with no page.) `data_pipeline/verification/directories.py` adds
a second, weaker, honestly-labelled kind of evidence from structured
official directories, the first being the Federal Register's agency
directory (`api/v1/agencies.json`: every agency that publishes in the
Register, with its parent and its own site). The directory is fetched
verbatim and committed (`tests/fixtures/directories/`, refreshed only by
re-fetching); `scripts/derive_directory_evidence.py` matches its entries
to the curated organisations by canonical name — with the rewrites the
directory needs, "Energy Department" answering to "Department of Energy"
(the same inversion for every head noun in `HEAD_NOUNS`) and a leading
"United States" it often drops ("Coast Guard", "Mint")
— one entry to one node or nothing, and writes
`data/verification/directory_evidence.json`, each record saying what the
directory lists: the name, the parent, the entry's page, dated by the
directory's fetch time. The exporter applies it after the page evidence,
beside a page claim and never over it: `verificationMethod:
listed_in_federal_register_agency_directory` only where no page method
exists, `directoryListing` always, and `placementMethod:
listed_under_parent_in_federal_register_agency_directory` only when the
directory's parent is the node the tree gives it. When the directory files
a unit under an ancestor of its tree parent the node carries
`placementDirectoryAncestor` and the panel says the grouping between is
curated; under any other parent it carries
`placementDirectoryDisagreement` and the panel says the two sources
disagree; nothing is resolved either way, and the gate reports the four
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
one of the two chambers' list URLs (senate.gov or clerk.house.gov; it does
not tie the House source to the Clerk's host). First run: 27 committees in the list, 18 matched
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
**The export landed on 2026-09-21** (`tests/fixtures/opm/plum/
escs_pbpub_download-data.csv`, 2.8 MB, 15,777 rows, its `.meta.json` beside
it), fetched with `fetch_fixture.py` exactly as §10 prescribes — and on a
permission neither §9 nor §10 anticipated: the host answered `robots.txt` with
**200 and an HTML page** rather than a 403, which RFC 9309 §2.3.1.2 reads as a
successfully fetched file with no parseable rules, so the standard's ordinary
rule allowed the path and the 4xx policy never came into play
(`docs/NETWORK_ACCESS.md` §12; `tests/fixtures/opm/README.md` §1 says what the
file contains, name columns never read). **It is read since the same day** by
`plum_current.py`, as a second document beside the archive and never over
it — see "The current Plum Book, read" below. The rest of the list that stood
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
**landed**; OPM's current Plum Book **landed** on 2026-09-21 and is read by
`plum_current.py` beside the archive; and SAM.gov's Federal Hierarchy
is reachable at last and still needs a key the owner would have to obtain.
`data.opm.gov` answers too and nothing here has read it; `www.usa.gov`'s
A-to-Z index was crawled once on 2026-09-20, to nominate pages (below).

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
dashes resets the grouping. **The ALL-CAPS row itself is a title (since
2026-09-21).** It is how the Manual prints the principal — `SECRETARY OF
STATE`, `ATTORNEY GENERAL`, `LIBRARIAN OF CONGRESS`, `COMPTROLLER GENERAL OF
THE UNITED STATES` — and until then it was refused along with what it
governs, which is why nine department heads and the Attorney General carried
no evidence while the government's own handbook named each of them. The
worry that motivated refusing it, that the same typography marks a plural
group heading (`DEPUTY ADMINISTRATORS`), is answered by the join rather than
by a plural test: a row reaches a post only by equality with exactly one
curated child, and no post is named in the plural. Measured before the
change: 175 caps rows under the matched entries, 21 equal to exactly one
curated post, every one of the 21 a real title. What follows a caps row is
still refused.

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

**The entry's own description, beside the curated prose (since 2026-09-21).**
Every one of the 5,155 curated descriptions is published as "uncited prose —
not checked against any source", and the Manual carries, per entry, the
government's own statement of what the unit is for. `entity_description_texts`
in `govman.py` reads two elements and nothing else: `MissionStatement/
Record[1]/Paragraph`, the element the publisher itself labels as the entry's
mission statement (131 of 231 entries carry one — 33 of them sub-entities,
among them CRS, NOAA and BIS — the longest is 544 characters, only the FIRST record is read because Congress's
second is history); otherwise the entry's opening paragraph — the first
non-empty `Detail/Paragraph` under `ProgramAndActivities` in document order —
and only when the **published** text carries the entry's printed name. The
guard is what ties the paragraph to the unit, the job label equality does for
a page: four sub-entities open with "The Administration posts an
organizational chart on its 'Offices' web page", a navigation note, and it
refuses all four; it also refuses "The U.S. Naval Academy is the undergraduate
college of the Naval Service" for the entry named "United States Naval
Academy", a real cost recorded rather than argued away. The text is verbatim,
bounded at 600 characters and cut only at a sentence boundary (a terminator
after a lower-case letter, digit or closing bracket, then a capital, so "15
U.S.C. 271" is never a sentence end); no mission statement needs the cut and
17 opening paragraphs take it, with `truncated` and the full length on the
record. The guard was first written against the whole paragraph and the test
suite caught it: the Court of International Trade is named only after the cut,
so a reader would have seen a paragraph that never names the court. It is
tested on the published text now. The guard is not enough on its own, and
the end-to-end check found why: four HHS sub-entities open with "The Centers
for Medicare and Medicaid Services (CMS) posts an organizational chart in
Portable Document Format", which names the unit in full and describes its
website. `NAVIGATION_NOTE_MARKERS` — "organizational chart", "organization
chart", "web page", "website", a closed list that can only ever withhold, the
direction `name_appears_unlabelled` is allowed to work in — refuses exactly
those four on the real Manual and no mission statement contains any of them;
the gate mirrors the list and refuses such a text even where it is verbatim.

It is published as `descriptionOfficial` {text, kind, extractedFrom,
truncated, fullLength, source, listedName, edition, package, granule, url,
documentSha256} **beside** `desc`, which is never overwritten and keeps its
"uncited" label; the panel prints it under "OFFICIAL DESCRIPTION — U.S.
Government Manual, <edition>" with the element it came from and a link. It is
in `EVIDENCE_OWNED_FIELDS` (withdrawn each build with the entry block it
depends on) and `MINIMAL_GRAPH_FIELDS`. The gate re-derives both texts per
granule with its own stdlib parse and refuses a block whose text is not
verbatim in the element it names (the whole, or a prefix ending at a sentence
boundary when it says it was cut), that cites a granule its own `govmanEntry`
does not, whose granule names another agency, whose node no longer carries
the name, whose URL is not the granule's, whose digest is not the committed
package's, on a post, of an unknown kind or path, past the bound, publishing
an opening paragraph where a mission statement is printed, or where the
curated `desc` has become the Manual's text. `tests/test_govman.py` corrupts
each in turn. Dry run on the real join: **142 of the 163 matched
organisations** (89 mission statements, 53 opening paragraphs, 17 cut); 14
refused by the name guard, 4 as navigation notes, 2 with no descriptive text,
1 with no sentence boundary inside the bound. Nothing writes `sourceUrls` or `verificationMethod` from this: a
description is not evidence that the unit exists, and the entry block already
carries that claim.

The post route was measured for reach at the same time and left alone: beside
the 64 posts the complete-title rule admits, 144 more under matched agencies
equal exactly one leadership row that the rule refuses — 69 under a table
header, 37 under an ALL-CAPS row, and 38 that are ALL-CAPS rows themselves.
The third group was admitted the same day (see the caps-row paragraph
above): the equality join, not a plural test, is what keeps "DEPUTY
ADMINISTRATORS" from reaching anything. The first two stay refused, recorded
as a measurement.

**Alternative names a node answers to (since 2026-09-21).** A node keeps the
name the graph displays and carries a reviewed list of other names the
verification process will also accept. `data/curation/node_aliases.json` is
that table and `data_pipeline/verification/aliases.py` its only reader: per
row, the node id, the node's **current** name, the alternative and a `basis`
saying on what authority the two denote one unit. It is the fourth table of
this shape after `unit_renames.json`, `TREASURY_ROW_ALIASES` and
`USASPENDING_NAME_ALIASES`, and like those it is re-adjudicated against the
curated file on every run rather than trusted: a row is refused when the node
is gone, when it no longer carries the stated name, when there is no basis,
when the alternative is a no-op under `canonical_name_key`, when it is one
token or on `GENERIC_NAMES`, or when it collides with a **sibling's** name or
a sibling's accepted alias — the sibling-scoped rule
`rename_units_to_official_wording.py` already uses, for the reason recorded
there.

It exists because `CURATION.md` §13.1 recorded the problem and correctly
declined the only tool then available. The Manual prints "Federal Motor
Carrier Safety Administration" where this graph writes "Admin"; §13.1 refused
to *rename* those nodes, because the reason to rename must be the agency's own
wording and the payoff must be real. An alias is the other move: the displayed
name does not change and the matcher does not loosen — a name is either in the
table or it is not.

**It is consulted by name and existence evidence only — with the one
exception below, a rate riding on a listing it scoped — and that is
structural.** The page-label test in `evidence.py`, the Government Manual's
entry join, the chambers' committee lists and the current PLUM export's agency
scoping take an alias table explicitly, and the last can carry a printed rate
with it: PHMSA's Deputy Administrator publishes the export's $197,200 on a
listing its agency reached through the table, graded `partial`. No other join
that lands a NUMBER may see one: not `headcounts.py`, not the Treasury row matching, not `usaspending.py`,
`net_cost.py` or `omb_budget.py`. Each of those has its own reviewed table
where a figure is at stake, and this file records why one table for both kinds
of claim would be dangerous — FedScope's "DEPARTMENT OF THE ARMY" is a
civilian department and this graph's "U.S. Army" the uniformed service, so a
name written down for a badge would start dividing money. The rule is not
discipline: those modules do not import the alias module, and
`tests/test_node_aliases.py::IsolationTests` asserts the whole repository's
import list against a whitelist and that no money matcher even has a parameter
one could be handed to.

**A confirmation reached this way is weaker and says so.** The record carries
`matchRule: matched_on_a_recorded_alternative_name` with the alternative and
its basis; the node publishes `verificationAliasMatch` {alias, basis,
matchedText, scope, urls, matches}; and `cap_alias_only_confirmations` — run
after the last evidence pass, because every `apply_*` ends in
`verify_node_sources` and would undo it — holds a node whose every official
source came through the table at `partial`, never `verified`. That is the same
deliberate downgrade `usaspending.py` makes for an aliased key: `verified` is
what two documents naming the unit outright earn. The panel and the atlas view
print both names and the basis in words and say when the cap applied. A
**node-scoped** alias never publishes a placement — the claim would be "the
parent's own page lists it by name", and a page printing a name the graph does
not use is a weaker thing with no honest wording; an **organisation-scoped**
one (the post's own title matched, its agency needed the table) leaves the
source's own filing standing and says whose name was different. Both fields
are in `EVIDENCE_OWNED_FIELDS` and `MINIMAL_GRAPH_FIELDS`, so a deleted row is
a real withdrawal.

**Eight rows, and what they bought, measured rather than asserted.**
AmeriCorps → Corporation for National and Community Service; the Vice
President → The Vice President; AOUSC, NOAA, FMCSA, NHTSA, PHMSA and DARPA →
the Manual's own spelling of each. Manual entries matched to an organisation
**163 → 170**, posts listed from the leadership tables **85 → 89**, official
descriptions **142 → 149**; the current PLUM export's agencies **78 → 79**,
positions **170 → 173**, rates **100 → 101**; on the rebuilt graph, nodes with
an official source **931 → 942**, `verified` **484 → 485**, `partial`
**401 → 415**, **16** nodes changing verification status and **no cost figure
moving at all**, with **15** nodes carrying an alias match and **14** held at
`partial` by the cap (the exception is DARPA, which already had `darpa.mil`).
The cap turns on `official_site` and not on "a `.gov` URL", because the first
version used the broader test and let one aliased Manual entry carry NOAA,
FMCSA and NHTSA from 0.4 to 0.8 — their only other source being the FiscalData
URL a measured Treasury line puts on every measured node, which
`classify_source_url` files as `government_dataset` and which earns no
`official_site` bonus. The gate caught that, and a second defect in the same
build: the cap sat beside the other evidence passes, and both
`verify_node_sources` and `annotate_proof_tree` run after them and recompute
the status from the URL count. It runs after the tree is final now.
AmeriCorps gained least where most was expected: the
export's 31 live CNCS rows all sit under sub-organisations this graph has no
nodes for, so matching the agency reached no position — those rows need
*nodes*, not an alias.

**The President and the Vice President, and the narrow route that reaches
them.** `govman.match_organisations` skips every post and the post route needs
the post's own parent to have an entry, so neither office was reachable however
its name was spelled. The Manual carries a top-level entry for each — the entry
IS the office — and `build_office_records` publishes that as
`verificationMethod: listed_as_its_own_entry_in_us_government_manual` in its
own field `govmanOfficeEntry`, **never as a placement**. Four guards keep it
off an ordinary agency entry: the entry has no parent entry, it names no
organisation in this graph, it reaches exactly one post and that post answers
to exactly one such entry, and the post's parent is not an organisation the
Manual has an entry for. A fifth was added because the first version failed
without it on the real data — the entry's ALL-CAPS principal row counts only
when it is the entry's own heading, or that heading plus "of the United
States". Without it the Manual's entry for the United States International
Trade Commission printed `CHIEF ADMINISTRATIVE LAW JUDGE` and reached the
Social Security Administration's Chief Administrative Law Judge: an agency
entry naming one of its officers, published as an entry for that officer. With
it, 32 caps rows are refused and exactly two offices are listed.

**The President has no alias row, and the refusal is the rule working.** The
Manual's heading is "The President", which reduces to the single token
`president` — a label on thousands of `.gov` pages, and the alias IS consulted
by the page test — so the one-token floor refuses it. None is needed: the same
entry prints the office as `THE PRESIDENT OF THE UNITED STATES`, exactly this
node's name, and the route reaches it by plain equality. The Vice President's
caps row reads only `THE VICE PRESIDENT`, so that one needs the row, and two
tokens clear the floor. Both publish `partial`.

**Declined, and recorded in `CURATION.md` §17.4.** `U.S. Army` / `Navy` /
`Air Force` → `Department of the …` is refused outright and named in the
table's own comment: this file records twice that the civilian department and
the uniformed service are different units with different populations, so it is
a semantic claim the owner is deciding separately, and a test asserts no row
names any of the three. `Bureau of Consumer Financial Protection` →
`Consumer Financial Protection Bureau` was declined first as a word-order
difference whose basis would need 12 U.S.C. 5491, which this repository has not
read; later the same day it was added on the Manual's own entry 321 instead, so
the table now carries it among 13 rows and `NODE_ALIASES` mirrors it (14
since 2026-10-05: the Bureau of Prisons answers to "Federal Bureau of
Prisons", the name OPM's current export files its 72 rows under, §19.20). The
Manual evidence was not re-derived until 2026-10-07, so for two weeks the
published graph carried no alias match for it; since then the CFPB carries the
Manual's entry, its official description and the alias match, held at
`partial` by the cap, and the file's `_declined` list and §17.4 still record
the earlier refusal. `National
Security Agency (NSA)` → the Manual's joint `National Security Agency /
Central Security Service` names a second body the graph has no node for — the
shape `usaspending.BROADER_API_ENTITY` refuses.

The gate mirrors the table **by node id** with the name each row was written
against (`NODE_ALIASES`, pinned equal to the committed JSON by a test) and
refuses: an alias match whose node — or whose owning ancestor — no longer
carries the recorded name, a quoted alternative the table does not carry for
that node, a `verified` badge on alias evidence alone, a match with no basis,
a URL the block's own matches do not name, an organisation-scoped row filed as
the node's own name, and `matched_on_a_recorded_alternative_name` or
`verificationAliasMatch` anywhere inside a money or headcount block.
`tests/test_node_aliases.py` corrupts each in turn.

**The documents the government signs (`federal_register_signatures.py`, since
2026-09-21).** Every source above is a document ABOUT an agency, and each is as
complete as somebody decided to make it: a web page is not obliged to name an
agency's officers, and the Government Manual's leadership tables carry what the
Office of the Federal Register chose to print. Counted on the published graph:
4,280 of the 4,591 positions carry no verification method at all, and **1,922 of
those sit under an organisation whose own page WAS read** -- it named the
organisation, or was recorded as not naming it -- and simply does not name the
post.

A Federal Register document is a different kind of thing. Every rule and every
notice the government publishes ends with a signature block, and the block names
the signing official and that official's own title:

    R.N. Macon,
    Captain, U.S. Coast Guard, Captain of the Port, Lake Michigan.
    [FR Doc. 2026-19270 Filed 9-18-26; 8:45 am]

It is not a roster somebody compiled; it is an act of government carried out by
a named officer, published by the Office of the Federal Register, and the title
is there because the document has no legal force without somebody competent to
sign it. So it carries something no other source here does: the post existed
**and was filled** on the day the document was signed.

**The signer's name is never read**, and here that is structural rather than a
promise. The block's shape is `<name>,` then the title, so `signature_title`
locates the name line's index and builds the title out of
`lines[name_index + 1 : fr_doc_index]` — the name line is stepped over, never
bound to anything that escapes. That is the rule `positions.py` sets for the
PLUM archive's incumbent columns and `whitehouse_pay.classify_row` for its
report's NAME column, and the test is the strongest of the three:
`tests/test_federal_register_signatures.py` re-finds, per committed document,
exactly the line the module steps over, and asserts none of those strings
appears anywhere in what the module returns, writes or prints — including the
dry run's own output.

**Scoping is the API's, not the text's.** The signature says "U.S. Coast Guard"
in its own words, and reading that would be the assembly this file refuses
everywhere else. What scopes a document is the Register's own `agencies` field,
resolved by `directories.federal_register_name_keys` — the same rule the agency
directory uses, shared so the two can never disagree about which agency is which
node — and **only when the whole agency list reduces to exactly one organisation
here**. It is the second-largest refusal this module makes -- 133 of 443
committed documents -- and it is measured rather than argued around: the
Register files a Coast Guard rule under both "Homeland Security Department" and
"Coast Guard", both are nodes in this graph, and which of the two signed it is
not something the API settles.

**Equality, never containment**, and a floor of two tokens. Most signature
titles are written `<office>, <organisation>` — "Administrator, Agricultural
Marketing Service" — and splitting one to reach a node named `Administrator`
would be producing a title rather than selecting one, the failure
`rename_templated_post_titles.py` is built around. The titles that do reach a
node are the bare ones -- `Attorney General`, `Executive Director for
Operations`, `Secretary of Transportation` -- and they are the whole of what
this source yields.

**What it actually reaches, measured on 443 committed documents: three posts.**
The corpus yields **360 signature titles, 208 of them distinct**. Of the 443
documents, 133 are refused because the Register files them under two agencies
that are both nodes here, 83 carry no signature block above the `[FR Doc. …]`
line at all, 14 sign with a title of under two tokens, and **210 sign with a
title the scoped organisation carries no post of**. Three reach a node:

- the **Attorney General**, on Justice Department rule 2026-17815;
- the NRC's **Executive Director for Operations**, on rule 2026-17445;
- the **Secretary of Transportation**, on rule 2026-18040.

Five titles were re-fetched live and compared with the committed bytes — the
three above, the Coast Guard rule this section opens with, and a Labor
Department notice — and all five agree.

**The 210 refusals are the finding, not the failure.** Read against the posts
those organisations carry, they are almost all one of two things. Most
signatures are an administrative officer's rather than a principal's:
`Federal Register Liaison Officer, U.S. Department of Energy`, `Departmental
PRA Compliance Officer`, `FOIA/Privacy Act Officer`, `Alternate OSD Federal
Register Liaison Officer` — real posts, signing because somebody has to, and
posts this graph does not carry. And this graph's small independent agencies
are the stamped five this file documents elsewhere (`Director / Administrator
/ Chair, <agency>`, `Deputy Director / Vice Chair`, `General Counsel`,
`Inspector General`, `Chief Financial Officer`), which almost nothing signs
under. The near misses are refused deliberately and correctly: `Acting
General Counsel` against the CSB's `General Counsel`, `Acting Comptroller
General of the United States` against the GAO's `Comptroller General of the
United States`, `Chair, Federal Election Commission` against `Director /
Administrator / Chair, Federal Election Commission`. Folding "Acting" or
splitting a comma would reach each of them, and each fold is the containment
failure this file records twice already.

**All three were already sourced, and that is where the value landed.** None
of the three takes the signature as its verification method: the Attorney
General and the Secretary of Transportation carried the Government Manual's
entry (`partial`, 0.70, one URL) and the NRC's Executive Director for
Operations a label on the NRC's own page. The signature is a second,
genuinely independent official document, so the first two move **`partial` →
`verified`** on the existing arithmetic (0.70 + 0.10 for a second source) and
the third stays verified at 0.90. Three of 4,591 positions is **0.07%**, it is
printed on its own line by the gate so it cannot be read as anything grander,
and the honest summary is that the Federal Register confirms the government's
principals rarely and its paperwork officers constantly.

**It claims no placement, and it is never a cost.** One document was read and it
yields one observation; publishing existence and placement from it would present
a single finding as two corroborating ones — the rule the Manual's post route
already follows, and the gate refuses a placement method naming this source.

**And it is worth less than it first looks, which is the existing arithmetic
rather than a new rule.** `classify_source_url` files a `federalregister.gov`
URL as `federal_register` and deliberately NOT as `official_site` — "a notice is
documentation of an office, not the office's own site" — so it scores the bare
0.4 any source scores and misses the 0.3 an official site adds. A post confirmed
by a signature ALONE publishes **`unverified` with a source recorded**, not
`partial`: the site shows what was read and does not call it a verification.
A post that already carries a page or Manual claim keeps it and the second
source adds 0.1, which is the only route from here to `verified`.

**A response that is not the document is refused, not parsed.**
`www.federalregister.gov` answers `robots.txt` **200** with real rules, none of
which covers either path read here, and it answers a document's `raw_text_url`
with a 10,596-byte HTML page titled "Federal Register :: Request Access" at
random — under HTTP **200**, so nothing in the status says anything is wrong,
and the same URL serves the document on the next attempt. It is neither a fact
about this project's agent nor a simple rate limit: measured against three
header sets the rate did not move, and across four stretches of the run paced
at 2.5, 2.0, 6.0 and 2.5 seconds it came back on 63%, 68%, 59% and 82% of
requests, drifting without tracking the delay (`docs/NETWORK_ACCESS.md` §13).
What it costs is attempts rather than patience, so the run allows twelve, after
which one document of the 444 the two tranches asked for was never served. A
response whose media type is not `text/plain` is therefore not the document: it
is deleted and retried, and where the host never served it no fixture is
committed and the `.meta.json` says why. The plain-text rendering the Publishing
Office does serve is wrapped in a fixed `<html>…<pre>` envelope and a few bodies
carry an injected Cloudflare e-mail span; nothing here parses either. The
signature block is located by the document's own `[FR Doc. <number> Filed …]`
line, whose number must be the number the API gives, and a tag or an HTML
entity inside the block refuses it — a bare ampersand does not, because this
graph names units "Health & Human Services" and carries a curated post called
`AF/A1 (Manpower & Personnel)`.

**The sample is a census in two tranches, and its bias is stated.** Tranche A:
for each of the 143 agency-directory entries that reduce to exactly one
organisation carrying a post a signature could name, one API listing call took
that agency's two most recent RULE and NOTICE documents, and every document
those listings named was fetched. Tranche B: the 300 most recent RULE and the
300 most recent NOTICE documents government-wide, three listing pages each, of
which the ones whose agency list reduces to exactly one organisation here were
fetched — because tranche A
under-weights the departments, whose newest documents are filed under a bureau
as well and so are refused by the scoping rule. Every listing is committed, so
what was refused before any fetch is reproducible offline with no network, and
`read_documents` counts a document the host refused separately from one nothing
asked for. Neither tranche selected anything for what its signature says, and
together they say nothing about how often a title is signed in general — only
that it was signed on the documents in here
(`tests/fixtures/federal_register/README.md`).

**The gate** re-reads the committed fixtures by the block's own document number,
recomputes every digest, re-derives the signature title with a second,
independent stdlib parse, and re-resolves the agency list against the published
organisations — so the scope the claim rests on is checked rather than copied.
The parent is read off the **tree the gate is walking, never off `parentId`**,
for the reason the scoped Executive Schedule claim already documents: `General
Counsel` names 92 nodes here, so a record moved to another node of the same name
keeps a real title, a real document and a real URL, and only the parent tells
them apart. It refuses a block on a non-post, a renamed node, a document not in
the fixtures, a digest or URL that is not the committed one, a title the
document does not print in its signature position, an agency list the Register
does not print, a future date, an inflated occurrence count, a citation that is
not the Register's own address, a method with no block behind it, and any
placement claimed from this source.
`tests/test_federal_register_signatures.py` corrupts each in turn, against a
record applied to a copy of the published graph so every other gate check runs
beside it — but built from fixtures the test WRITES rather than the committed
ones. That is deliberate: the Register publishes what it publishes, so a corpus
fetched today may trip a given rule once or never, and a gate rule exercised
only when the host happens to cooperate is not pinned at all. What the
committed corpus really yields is checked separately, and the gate accepts it.

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
or that carries no date or URL. A headcount its own descendants' records
already exceed is not refused: the derive step marks it
`subtreeRecordsExceedIt` and the exporter publishes the flag beside it (none
carries one now). The gate checks every field (a
`.gov` URL, a period, a coverage sentence, a past date, a non-negative
integer) and reports how many nodes carry each and how far the curated
figures are from OPM's: **66 of the 133 differed by more than 10%** when this landed; 69 of 179 do now.

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
"the share was not recomputed from OPM's number". 11 shares carried one when
this landed; 10 do now. It is
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
the matched nodes carried a curated figure when this landed, and only 55 of
those were within 10% of what OPM reports; 128 of 179 and 59 now. Matching is scoped as the Federal Register's is —
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
bytes on disk and refuses a mismatch**, which was the only such check in the
repository when it landed (fourteen other verification modules make it now,
`gs_pay`, `plum_current` and `statutory_schedule` among them) and is the
thing that makes a record's `documentSha256` a claim
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

**A range, never a rate: the GS, SES and SL/ST tables (`gs_pay.py`, since
2026-09-21).** The archive's 129 matched positions break down by pay plan as
ES 89 (46 with a rate the archive states, none with a level), EX 31 (30 with
a level), OT 4, AD 3, GS 1 (grade 15) and SL 1. `pay_tables.py` prices the
EX levels; the ES, GS and SL posts had nothing, because no table states one
figure for them — Salary Table 2026-GS prints ten steps per grade, and
Salary Tables No. 2026-ES and 2026-SL/ST print a pay system's minimum and
maximum, once for agencies with a certified appraisal system and once
without. So the fifth pay field, `positionGradePay`, is a **range**: a
minimum, a maximum, the kind (`general_schedule_grade`,
`senior_executive_service`, `senior_level`), for GS the grade and its ten
steps and the words "base General Schedule rates before locality pay; the
table states no locality adjustment", for the structure tables both rows as
printed. Tied to `positionListing` exactly as `positionPayRate` is — the
listing must still report the same pay plan (and grade, on one archive row)
and no rate — withdrawn with it, in `EVIDENCE_OWNED_FIELDS`, and where the
archive itself prints a rate for a post that rate wins and no range is
written (46 ES listings). `scopeMatch: proxy`, graded `partial`, every
bound of every range through `financial_evidence.validate_record` against
its node; nothing writes `sourceUrls`, `sourceTypes`, `lastVerified` or
`verificationMethod`. **45 records** on the 2026-09-21 evidence (1 GS, 43 SES,
1 SL), of which **32 reached the published graph**; **26** now (1 GS, 24 SES,
1 SL), of which **18** are published — the other 8 sit on nodes that stand
for several posts, and the multi-post sweep strips this field from them as
an incumbency claim.

**The GS table states its scale in one place, and the HTML is not it.** The
web page prints bare integers (`22584`) and says "dollars" nowhere; the XML
prints `<Annual>22584</Annual>`. The PDF rendering prints `$  22,584` on
grade 1 — and only on grade 1; every row beneath is bare, the ordinary
typesetting of a column marked once at its head. `_prints_whole_dollars` can
vouch for grade 1 and nothing else, so an honest GS-15 record was unfilable,
which `financial_evidence` names as the dangerous case. A fourth and
narrowest rule, `COLUMN_HEAD_MARK_SOURCE_TYPES` (`unitsEvidenceKind:
currency_mark_on_the_columns_first_figure`, granted to `opm_pay_table`
and, since Schedule 6 on 2026-09-23, `us_code_pay_schedules`), files a record that quotes the column's first figure WITH its mark
and its own bare figure, names the column, and would have filed under the
stronger rule had its own figure carried the mark — the validator checks that
shape, `gs_pay` guarantees the two sit in one column, and the gate mirrors
all fifteen (step 1, step 10) pairs in `GENERAL_SCHEDULE_RANGES` and
recomputes the digest. The PDF is therefore the cited document
(`salary-tables/pdf/2026/GS.pdf`, the address it redirects to, because a
record cites the URL that served the bytes) and the HTML page is
corroboration: `load_general_schedule` refuses to return a table unless the
two renderings agree on the number, the effective heading and every one of
the 150 figures. The SES and SL/ST pages mark every bound, print identical
figures, and are committed and cited separately, since a SL post's range
must cite the SL/ST document; the gate refuses a `senior_level` block naming
the ES table, and a first fetch of both at the URLs the task named
"succeeded" with a 200 by redirecting to OPM's homepage, which is why
`_load_fixture` refuses a fixture whose `final_url` is not its `url`. The
gate (`grade_pay_violations`) further refuses a block on a non-post, on a
node standing for several posts, beside a rate the archive states, beside a
measured cost, with a grade or plan the listing no longer reports, with
bounds or printed digits or structure rows the table does not print, with a
GS block lacking the before-locality sentence or carrying a note the PDF
does not print, with the wrong scale rule, claiming more than a proxy, or
citing the table as a source of the post's existence;
`tests/test_gs_pay.py` corrupts each in turn. The panel prints the range in
the listing block beside the pay plan it rests on, and in the cost block
under `BASE PAY RANGE, BEFORE LOCALITY` (or `PAY SYSTEM RANGE`), never under
COST.

**The current Plum Book, read (`plum_current.py`, since 2026-09-21).** The
export `docs/NETWORK_ACCESS.md` §12 landed the same morning is the live
counterpart of the archive `positions.py` reads: 15,777 rows, one per
incumbency, `Position Status` `Filled` (6,846), `Vacant` (2,951) or
`Historical` (5,980). `data_pipeline/verification/plum_current.py` reads it,
`scripts/derive_plum_current_evidence.py` writes
`data/verification/plum_current_evidence.json`, and the digest is recomputed
from the bytes before a row is read, the refusal `pay_tables` and `gs_pay`
make. Only `Filled` and `Vacant` rows are read — a Vacant row is still a
listed position — and the 5,980 Historical rows are counted and never read.
**The two name columns and the unique-ID column are never read**, not read
and declined: `READ_COLUMNS` is the whole of what is taken off a row, by
header index, and the gate's own reader projects the same seven columns;
`tests/test_plum_current.py` plants a sentinel in the three incumbent columns
of every fixture row and asserts it appears nowhere in what either returns,
writes or prints. Identical rows for one position — the same (Agency,
Organization, Position Title, Pay Plan, Level) — are folded into one listing
carrying the row count and both statuses BEFORE the archive's rule that two
titles collapsing onto one key claim neither; 442 folds on the real file.

Matching is the archive's, reused: `positions.archive_title_keys`,
`position_name_alternatives`, the same (Agency, Organization) scoping, one
name to one node or nothing. One rule is added and it is the export's own
filing read back rather than a guess: the file names twelve units
`EXECUTIVE OFFICE OF THE PRESIDENT - <unit>`, and where the whole name
matches nothing the half before " - " must name exactly one organisation and
the half after it exactly one organisation beneath it — the scoping
`headcounts.py` applies to a FedScope sub-agency row. The archive printed the
same form and `positions.py` never reached those units; the rule matched 7
agencies and **43 positions**, most of them White House Office titles the
roster had already named. HTML entities (`&amp;`, `&#039;`) are resolved for
keys only; every published string is the file's own. Two groups that are both
the agency itself (the USPTO's rows sit under two spellings of its own name)
feed one title index rather than cancelling each other as ambiguous.

**No alias table, at first.** The largest unmatched block is `OFFICE OF THE SECRETARY
OF WAR` (506 live rows, the archive's "Office of the Secretary of Defense"):
this graph has no OSD node to alias it to, so an alias could reach nothing.
`DEPARTMENT OF THE NAVY` / `ARMY` / `AIR FORCE` (240 rows) are the
civilian-department against uniformed-service distinction this file already
refuses for FedScope. 96 of 174 agencies were unmatched in all on the first
derivation; 59 are now, and since 2026-09-21 the agency scoping also reads
`node_aliases.json`, through which one agency and four organisations match.
The dry run prints the unmatched by live rows so the coordinator can see
what a node — not an alias — would buy.

**What it publishes.** `positionCurrentListing` (method
`listed_in_opm_current_plum_export`, the export's URL in `sourceUrls`, the
method only where none exists) and, on the tree's own parent only, placement
`listed_under_organization_in_opm_current_plum_export`. It is a second,
independent official document, so a post listed in the archive too reaches
`verified` on the existing arithmetic (0.4 + 0.3 for one official URL, +0.1
for a second) and a post with only this one stays `partial`. Where the row
prints a rate of basic pay, `positionCurrentPay`: the export's own figure for
the one row listed under this title now, validated by
`financial_evidence.validate_record` (`opm_plum_current_export` joins
`SCALE_PRINTED_SOURCE_TYPES`, since the cell prints `$228,000` and nothing in
the file says "dollars"), `scopeMatch: proxy` and graded `partial`
deliberately — a row is an incumbency, and what one listing is paid is not
what the post pays whoever holds it. Never $0 (a printed `$0.00` is refused
as its own reason). Tied to the listing exactly as `positionPayRate` is tied
to the archive's: published only while the listing still reports the same
figure, both in `EVIDENCE_OWNED_FIELDS` and `MINIMAL_GRAPH_FIELDS`, and it
writes no `sourceUrls`, `sourceTypes`, `lastVerified` or
`verificationMethod` and is never a cost. The multi-post sweep takes it with
the other incumbency fields (`positionPayRate`, `positionGradePay`,
`positionSchedulePay`); since 2026-09-23 the rule is per field and a tier
rate stays (see "A rate that holds for every holder" below), and since
2026-09-27 so does a schedule block priced from the Code's class title.

**First derivation, measured on the evidence files (the graph is not
rebuilt here).** 170 of 4,591 positions listed, 170 placements, **100 rates**
(all partial); 118 of the 170 are in the archive too and will read `verified`
on the next build, 52 are current-only, 11 archive-only. Filled 121, Vacant
37, 12 with rows of both. Pay plans ES 85, AD 43, EX 32, OT 6, SL 1, 3 whose
rows disagree. 63 listings print no rate and 7 print several figures for one
title, so no rate is written for them. **36 White House Office posts now
carry both the roster's figure and the export's, and all 36 agree** — two
documents, one number. The salary-table joins now read either listing:
`positions.LISTING_FIELD_BY_SOURCE` ties a claim to the field of the document
that reported the level or pay plan, `combine_listings` prefers the current
export where it lists a post, and a rate stated by EITHER listing refuses a
table rate or a range (`a_listing_reports_a_rate`), because that would be two
figures for one post. Regenerated: Executive Schedule records **29 → 31** (170
listings now supply the level, 11 from the archive); ranges **45 → 26**,
because 104 listings now state the rate the range used to stand in for,
which is the honest direction — a printed figure beats a band. Both apply
functions and both gate checkers read the listing the record's own
`levelSource`/`listingSource` names, so a rate looked up from the current
export is withdrawn with the current listing and never survives on the
archive's.

**The gate** (`current_listing_violations`, `current_pay_violations`,
stdlib-only) re-reads the committed CSV by the block's own keys — never the
incumbent columns — and refuses a block on a non-post, a renamed node, a
parent that is not the organisation the export files the title under
(checked off the tree, against the parent's name), a `Historical` status, a
digest that is not the committed file's, a status, pay plan, level or figure
no live row of the title carries, a placement method with no listing beneath
it, a rate its listing does not report, zero, more than a proxy, a rate
beside a measured cost, and a table rate or range beside a rate the other
listing states. The panel prints a CURRENT PLUM BOOK sentence in the listing
block and the rate under `PAY — CURRENT PLUM BOOK` with the fetch date on the
period line, never under COST; the atlas view carries the same block.

**Two more ways a row of the current export reaches a post (since
2026-10-05, the twelfth research batch).** The batch's White House agent
found four printed SES rates the matcher never reached — the OMB's and the
ONDCP's Chiefs of Staff and General Counsels — because the export files them
under sub-organisations this graph has no node for ("OFFICE OF THE
DIRECTOR", "GENERAL COUNSEL"), and one White House principal the July roster
does not list but the export does, under its commissioning rank. Both were
measured before anything was built. A broad fallback — any unmatched
sub-organisation's rows scoped to the agency's own children — reaches 283
rows on 173 posts and was **refused**, because it lands an Under Secretary's
"CHIEF OF STAFF" on the Secretary's: the Department of Agriculture's
department-level Chief of Staff would have taken rows from eleven Under and
Assistant Secretaries' offices. The rule built instead is the export's own
filing read back, the way `archive_title_keys` reads a title's trailing
organisation: **a sub-organisation NAMED FOR THE TITLE** — "Office of the
General Counsel" / "General Counsel", "Office of Inspector General" /
"Inspector General", "Office of the Administrator" / "Administrator" — whose
name reduces, with a leading "Office of (the)" removed, to the row's own
title, and which names no node here. The office is named for its head, so
the row is the agency's own General Counsel and nothing else; it is scoped
to the agency node's direct children under every refusal the main pass
makes, a title filed under two such offices of one agency claims nothing,
and a row the agency itself carries is never displaced. Measured on the
committed export: 72 rows reach 70 posts, every one a stamped administrative
title (General Counsel 30, Chief Information Officer 11, Chief Financial
Officer 6, Inspector General 4). The record and the published block carry
`scopeRule: office_named_for_the_post`, the placement claimed is under the
agency (the unit the export files the office under), the panel says the
export files the title "under a unit named for this very post, which this
graph has no node for", and the gate refuses the rule on a row filed under
the agency itself, on an organisation not named for the title, a rule it
does not know, and the block moved under another parent. The second rule is
the roster's own fold applied to the export: `export_title_keys` now also
yields the title with its White House commissioning rank folded off the
front, by `whitehouse_pay.title_core` (a leading rank only, never a
containment, at least two tokens left), so "ASSISTANT TO THE PRESIDENT AND
DIRECTOR OF LEGISLATIVE AFFAIRS" reaches `Director of Legislative Affairs`;
8 rows, 7 posts, and the rename guard `listed_title_still_names` learned the
same fold, because the first build matched the row in the derive step and
refused it as "renamed" in the build. The gate mirrors both
(`plum_rank_folded_key`, `plum_office_named_for_key`), and
`tests/test_plum_current.py` pins the module and the gate equal and corrupts
each rule in turn. Listings **170 → 252** (255 once the Bureau of Prisons
alias row let the export's "FEDERAL BUREAU OF PRISONS" rows reach the
Bureau), printed rates **88 → 128**, placements from the export **55 →
137**, nodes with an official source **980 → 1,039**, `verified` **520 →
538**, and — with the salary-table and range joins re-derived from the
enlarged listings (EX records 31 → 68, ranges 26 → 30 derived) and the
reviewed Schedule rows and tier-reference rows the same batch supplied
(fifteen reviewed rows: the ONDCP's Deputy Director at Level II through 21
U.S.C. 1703; the OSTP's Director at Level II through 42 U.S.C. 6612(a), the
Code still printing the Office's pre-1976 name; CISA's two Executive
Assistant Directors at Level IV through the deeming rules of 6 U.S.C.
653(a)(3) and 654(a)(3); the Director of the Bureau of Prisons through 18
U.S.C. 4041; FEMA's Deputy Administrator from the Code's class title through
6 U.S.C. 321c(a); the NLRB's Chairman, the FDIC's Chairperson and Vice
Chairperson, the MSPB's, NTSB's and PRC's Vice Chairmen, the Peace Corps'
Deputy Director, the FLRA's General Counsel and the DFC's Chief Executive
Officer, each from the body's own section; and four tier-reference rows: the
Secret Service Uniformed Division's Chief at Level V from 5 U.S.C. 10203(a),
the PCLOB's chairman and the ARC's Federal Cochairman at Level III from 42
U.S.C. 2000ee(i)(1)(A) and 40 U.S.C. 14301(c), and AmeriCorps' Chief
Executive Officer at Level III plus 3 percent from 42 U.S.C. 12651c(b), the
Inspector General Act's arithmetic on a reviewed row, which the gate's
reviewed-row tuple now carries as a seventh element) — pay claims **1,111 →
1,158**, unpriced **3,480 → 3,433**, reviewed Schedule rows **76 → 91**,
Schedule-priced **215 → 230**, tier-reference records **42 → 46** (41
published: the four the listings displaced, above, stay displaced). The
heading pattern all three operative-text readers share admitted one letter
after a section number and refused "§2000ee."; it admits two now, pinned
both ways. The gate's salary-table summary line, which subtracted the priced
count from the ARCHIVE's levels alone, printed "-37 not priced" on the first
build and now counts a level from either listing. **The batch's later
clusters, the next morning (2026-10-06), took the totals further**: pay
claims **1,158 → 1,193** — 22 uniformed posts from Schedule 8 of the same
pay-adjustment order (`military_pay.py`, below); the Department of Defense's
Chief Financial Officer as the Under Secretary of Defense (Comptroller), the
IRS Chief Counsel and four Transportation posts (the NHTSA Administrator and
Deputy, the FMCSA and FHWA Deputies) as reviewed Schedule rows, **91 → 97**
rows and **230 → 236** priced; the Architect of the Capitol, the Chief of
the Capitol Police, the GAO's General Counsel and the NNSA Administrator as
tier-reference rows, **41 → 45** published; the Sentencing Commission's Chair
at the circuit-judge rate and the two magistrate benches at 92 percent — a
ceiling 28 U.S.C. 634(a) sets and the compensation table's own Explanatory
Note resolves — as derived rows, **15 → 18**; unpriced **3,433 → 3,398**.
Later the same morning the Code title scan's three rows took pay claims
**1,193 → 1,196** and unpriced **3,398 → 3,395**: the FDA's Commissioner as a
reviewed Schedule row (**97 → 98** rows, **236 → 237** priced) on a title the
parser could not see until a footnote-mark rule was fixed, and the NOAA
Administrator and the Archivist as tier-reference rows (**45 → 47** published)
— see "Titles the Code prints with a footnote mark" below.
`CURATION.md` §19.20 carries every cluster and every decline.

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
nodes prices neither ("General Counsel" names 92 nodes here); a title the
statute states several of ("Assistant Secretaries of Commerce (11)") prices
none by name (since 2026-09-30 the counted-class route below prices its
reviewed members); and "Archivist of the United States", which the Code places at **both**
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

**The VA's Title 38 bands, and a correction I nearly published (since
2026-09-23).** The VA Medical Centers block is the largest unpriced group of
positions in this graph, and the Veterans Health Administration publishes
`www.va.gov/OHRM/Pay/2026/PDOP/PayTables.pdf` — its annual pay RANGES under
38 U.S.C. 7431, effective January 11, 2026, four tables of tiers each with a
printed minimum, maximum and a coverage list. `va_title38_pay.py` reads it
with the standard library alone, the route `whitehouse_pay.extract_text_runs`
and `omb_budget.guide_text` already take.

**A band is not a rate, and the sixth pay field exists to keep them apart.**
`positionTierPay` states bounds within which an appointment may be set and
says in its own `note` that the schedule publishes no rate for anybody; the
panel prints "That is a RANGE, not a rate" and the gate refuses a block that
carries an `amount`, a `rateText` or an empty note. It is its own field rather
than `positionGradePay` for the reason `statutory_schedule.py` gives for not
widening `positionPayRate`: that one is published only while a PLUM listing
still reports the pay plan it was looked up from, and this one rests on a
title printed in a schedule with no listing underneath it at all. Two
withdrawal rules cannot share a field.

**72 posts banded, from two of the four tables.** Table 3 names `Network
Chief Medical Officer` (Tier 1, $220,000–$400,000) and `Chief of Staff`
(Tier 2, $200,000–$400,000); Table 4's Tier 1 coverage list ends `...; Chief
Officers (VHA CO); Network Directors; Medical Center Directors`
($145,000–$310,000). Four curated families reach them, 18 nodes each:
`VAMC Chief of Staff (Medical)` and `VAMC Director` under the `VA Medical
Centers` grouping, and `Chief Medical Officer, VISN N` and `Network Director,
VISN N` under their own VISN — the latter two split at the first comma with
the organisation half required to name the node's own parent, the scoping
`statutory_schedule.match_scoped_positions` uses, and that parent required to
be typed `VISN`. A record may claim only a phrase that is a **whole printed
item** of a tier's coverage list, never a substring of one, because Table 4's
Tier 1 is seven items long.

**Tables 1 and 2 are refused, and the refusal is the interesting one.** They
print the same leadership titles — `Supervisor, Program Manager, Section
Chief` at Tier 2, `Service Chief, Service Line Manager, ...` at Tier 3 — at
**different ranges**, because the two tables cover different lists of clinical
specialties: Table 1's Tier 3 is $165,000–$350,000 and Table 2's is
$225,000–$400,000. This graph carries `Chief — Medicine Service`, `Chief —
Surgery Service` and fourteen more per medical centre, and choosing a table per
node would mean reading "Surgery" against Table 2's "Surgery — Cardio-Thoracic,
General, Hand, Neurosurgery, Orthopedic, Plastic, Thoracic, Transplant,
Vascular" and calling it a match. The tell that this is assembly rather than
selection is that the same curated family includes `Chief — Finance`, `Chief —
Human Resources` and `Chief — Facilities Management`, which are not clinical
specialties and appear in neither table: pricing the clinical ones would be
this module deciding which VA service chiefs are doctors. `Associate Director`
is printed nowhere in the document, so the 36 `VAMC Associate Director
(Administrative)` and `Associate Director for Patient Care Services (CNO)`
nodes are refused outright.

**The correction, recorded because it nearly went the other way.** A research
pass reported Table 4's Tier 1 as printing "Network Directors; Medical Center
Directors". A first pass at this module checked that with an ad-hoc grep whose
text reconstruction dropped runs, concluded **the opposite** — that the
document prints neither phrase — wrote that into the module's docstring and
the evidence file's note, and refused 36 nodes on it. The research was right
and the check was wrong. What caught it was this repository's own habit of
asserting a negative in a test against the committed bytes: the test said
"these strings are absent", it failed on the real PDF, and the claim collapsed
in the one place it could not be argued with. `tests/test_va_title38_pay.py`
now asserts **both directions** — every priced title is present, `Associate
Director` and `VISN` are absent — so neither rests on anybody's memory of a
search. The word `VISN` really is absent, which is why identifying a Veterans
Integrated Service Network with the schedule's "Network" stays a reviewed
judgement and every one of the 72 is `scopeMatch: proxy`, graded `partial`.

The gate mirrors each priced coverage phrase with its table, tier and both
bounds, refuses a band whose table is not the one that prints its phrase, a
band on a name the pipeline does not price, a scoped band whose organisation
half is not the parent the tree gives it, a band moved to `VAMC Associate
Director`, anything published as a rate, and a `va.gov/OHRM` URL among the
node's sources. Positions carrying any pay claim went **385 → 457**.

**A figure no document states, and the percentage that says so (since
2026-09-23).** Every pay claim above publishes a number some document prints.
`derived_pay.py` publishes one that none of them does, and it exists because
`judicial_pay.py`'s own docstring named the refusal: it "will not price ... the
specialized Article I courts (Tax Court, Court of Federal Claims, Court of
International Trade, CAAF, CAVC). Their judges' pay follows other statutory
provisions this module has not read a source for". The refusal was about not
having read the provision. Congress wrote four, each one sentence naming
another court's judges:

- **26 U.S.C. 7443(c)(1)**, the Tax Court, at the district-judge rate;
- **28 U.S.C. 172(b)**, the Court of Federal Claims, at the district-judge rate;
- **10 U.S.C. 942(d)**, the CAAF, at the circuit-judge rate;
- **38 U.S.C. 7253(e)**, the CAVC, at the district-judge rate.

So the figure is a join: the statute names the tier, the Administrative
Office's own Judicial Compensation table states what that tier pays, and
**neither document states the number.** That is a weaker thing than a printed
rate and the seventh pay field, `positionDerivedPay`, says so in as many words
rather than presenting a derivation as a quotation. Four positions priced --
0.09% of 4,591, printed on its own line by the gate so it cannot be read as
anything grander -- and pay claims went **457 → 461**.

**The percentage, which is the owner's ask and not a new scale.** The request
was for the level of verification as a percentage saying how many documents
verify a claim. `document_strength_percent` is `verify_node_sources`'
arithmetic and nothing else: 0.4 for the first official document, +0.3 where
one is an official site, +0.1 for each further one capped at 0.3 -- one
document 70%, two 80%, three 90%. Reusing it rather than inventing a second
scale is what makes the figure beside a derived rate comparable with the one
the panel already prints beside a node's sources, and the panel's own line was
reworded to lead with it (`Verification: 70% — 1 official document`) where it
read `Confidence: 0.70 (70%) · Sources: 1` and left a reader to guess what
turned the count into the score.

What the percentage measures is how much official documentation the claim
rests on, and on this field in particular it would be a lie read as anything
else -- so every record also publishes `documentsStatingTheFigure: 0`, the
panel prints it in the same breath, and the gate refuses a block that claims
otherwise. Two documents scoring 80%, neither of which states the number, is
exactly the situation a bare percentage would hide.

**The research this was built from was wrong about one of the four, and the
statute's own operative text is what caught it.** A research pass reported
38 U.S.C. 7253(e)(1)-(2) as splitting the CAVC -- the chief judge at the
*circuit* rate, the rest at the district rate. That is the section **as it
read before amendment**, which uscode.house.gov prints in full inside the
Amendments note under "Prior to amendment, text read as follows:". The current
subsection (e) puts every judge of that court at the district rate. A
substring search of the page finds the repealed sentence and cannot tell it
from the law, so `operative_text` cuts each page at the first of "Historical
and Revision Notes", "Editorial Notes" or "Statutory Notes", every quote must
be found in what is left, and a quote found only below the line is **refused
rather than fallen back on** -- the report says so in words
(`only in the publisher's notes`). `tests/test_derived_pay.py` asserts both
directions: each current sentence IS in its section's operative text, and the
repealed one is NOT, though it is on the page. The gate mirrors the repealed
sentence too and refuses it anywhere in the block.

**The Court of International Trade is refused, and the refusal is the rule
working.** 28 U.S.C. 252 states no parity: "Each shall receive a salary at an
annual rate determined under section 225 of the Federal Salary Act of 1967
(2 U.S.C. 351-361), as adjusted by section 461 of this title" -- a chain
through two further documents this project has not read. CIT judges are in
fact paid the district-judge rate, which is a thing this repository knows and
cannot cite, the same position `CURATION.md` §8 puts "Secretary of the
Treasury" in. The section is committed anyway, because "nobody looked" and
"looked and it states no parity" are different facts.

Every other seat was refused at first for the reason `judicial_pay.py` gives:
each of the four courts carries one single-post chief-judge node and a
`Judge (×18)` / `(×15)` / `(×8)` / `(×4)` node stating a multiplicity, and one
rate beside a panel describing a whole group reads as what one holder earns.
The same day the per-field multi-post rule below reversed that for these four
benches: `derived_pay.BENCH_NODES` gives each its chief judge's provision with
a `holders` block, and 8 nodes carry the figure now.
A chief judge IS a judge of that court -- the provisions say "Each judge",
with no chief's premium -- which is the reading `judicial_pay.py` already
applies to Article III chief judges. The four service Courts of Criminal
Appeals nested under the CAAF node are refused: their judges are commissioned
officers paid under title 37, which nothing here has read.

All eight are `scopeMatch: proxy` and graded `partial`, and nothing writes
`sourceUrls`, `sourceTypes`, `lastVerified` or `verificationMethod` -- the
channel by which a five-row table carried 29 positions to `verified` on
2026-09-11, asserted against the published graph. The gate mirrors each
provision **by node id** for a reason sharper than the Senate case: **three of
the four price the identical $249,900** from three different statutes, so a
record moved between them keeps a correct figure, a correct tier and a real
citation, and only the node's own identity tells them apart. It refuses a
block whose sentence the section no longer prints, that names fewer or more
than two documents, whose document claims to state the figure, whose
percentage is not what the mirrored scale gives for the count it lists, that
counts more documents than it lists, that claims a `verified` grade or an
`exact` scope, that cites a statute its own document list does not name, that
sits beside a measured cost, that verifies the post's existence or places it,
or that puts either pay document among the node's own sources.
`tests/test_derived_pay.py` corrupts each in turn.

**The count on every pay field, and 4,099 positions that have none (since
2026-09-23).** The derived block above publishes how many documents its figure
rests on; the owner asked for the same on the rest, and the reason is that the
distinction was real and stated only in prose a reader had to assemble.
`positionPayRate` is a two-document join (a listing states the level, OPM's
table prices it) and `positionStatutoryPay` is one document's printed figure,
and the panel said so in different words in different places.

`pay_documents.py` is one pass over the finished tree, run after every pay
pass and after the multi-post sweep, and **the count is read off the block
rather than written down**: every pay block already carries the URL of each
document it rests on — the table in `url`, the listing in `levelSource.url`,
the statute in `statuteUrl`, both of a derived figure's in `documents[].url` —
so `PAY_DOCUMENT_FIELDS` names those keys per field and the published count is
the number of DISTINCT URLs actually there. A block whose second document went
missing publishes 1 and 70%, not 2 and 80%, and a build that put one URL in
both keys publishes 1, because it would be resting on one document. The gate
recomputes the same set from its own mirror of those keys and refuses a count
the block does not support.

The second field is what keeps the percentage honest. Two documents scoring
80% sounds stronger than one scoring 70% in every case, and on exactly one
field it is weaker, so each field declares how many of its documents state the
figure ITSELF: every printed rate and every printed pair of bounds declares
**1** — the table or the roster prints the number, and the second document
where there is one supplies the level or pay plan saying WHICH printed number
applies — and `positionDerivedPay` declares **0**, as does
`positionTierReferencePay` since 2026-09-28 (a statute sets the pay by
reference to a level; the table prices the level; no document states the
post's figure, and an Inspector General's is arithmetic besides). The gate
mirrors that per field, a test asserts those two are the only zeros, and the
panel prints the two in one sentence through a single helper
(`payDocumentsSentence`) called from all nine renderers in `js/ui.js`. The
atlas view does not call it: `js/atlas.js` carries its own shorter copy,
`payDocuments`, writes the derived block's sentence inline, and renders seven
of the nine fields (no `positionTierPay` or `positionGradePay`). The
derived module stopped writing its own copy of the arithmetic when this
landed: one code path for one number.

**And the gap this made visible, counted rather than estimated.** 1,111 of 4,591
positions carry a pay claim (461 when this section was first written, before
the multi-post rule below and the Federal Reserve rows; 492 before the
reviewed rows of 2026-09-27, 498 before that day's class-title benches, 513
before the tier-reference module of 2026-09-28, 541 before that day's
thirteen reviewed rows, 554 before the eight candidates of §19.10, 566
before the twenty-two rows §19.12 closed the eighth batch with, 588 before
the bankruptcy judges of 2026-09-30, 590 before that day's counted classes
and the ninth batch's rows, 638 before the 461 offices Members of Congress
hold were priced at the seat rate the same day, 1,099 before the Court of
International Trade and the Ex-Im Vice Chair of 2026-10-05, 1,102 before the
Tax Court's special trial judges and the two judicial-support Deputy
Directors the same day, 1,105 before the USAGM's CEO and the EAC's and FEC's
chairs and vice chairs that evening, 1,110 before the President's own salary
from 3 U.S.C. 102 the same night, 1,111 before the twelfth batch's
current-export rules and its nineteen reviewed and tier-reference rows later
that night, which took it to 1,158, and 1,158 before the batch's later
clusters the next morning, which took it to 1,193, and 1,193 before the Code
title scan's three rows later that morning, which took it to 1,196, and 1,196
before the owner's six decisions of 2026-10-07, which took it to 1,231);
**3,360 do not** (3,480 before that night, 3,433 before the morning, 3,398
before the scan's rows, 3,395 before the decisions), and `scripts/report_unpriced_positions.py`
says why for every one of them:

- **2,592** — no pay document this project has read names the title at all.
  Not a coverage gap somebody has not got to. (2,710 before the
  current-export rules and the twelfth batch's rows of 2026-10-05; 2,630
  before the Code title scan's rows later on 2026-10-06; 2,627 before the
  owner's six decisions of 2026-10-07; 2,663
  before its later clusters of 2026-10-06.)
- **750** — the node states a multiplicity (`Physician (×multiple)`) and no
  claim that holds for every holder reaches it. Since the per-field rule
  below, a tier rate, a parity rate, a band or a uniform roster line IS
  published on such a node (`Judge (×18)` is priced now); what stays refused
  is an incumbency-shaped claim. These are still listed, because which pay
  SYSTEM governs the title is a fact worth having.
- **18** — OPM lists the position and the row prints no rate.

The concentration is the useful part: **414** of the 3,360 sit under `VA
Medical Centers` (432 before the 18 USAJOBS-graded Associate Directors), 360
of them among the 2,592 (the service chiefs
`va_title38_pay.py` deliberately refuses, since choosing a Title 38 table per
node would be this module deciding which VA service chiefs are doctors), 61
under the White House Office (83 before the multi-post rule), 56 under
`Districts (multiple)`, and the rest spread across 627 organisations (734
before the committee chairs and ranking members were priced).

`docs/UNPRICED_POSITIONS.md` is the complete inventory, generated, one line
per unpriced position with its id and its reason;
`docs/PAY_SOURCE_RESEARCH_PROMPT_3.md` is a research prompt pack generated
from the same list in the same run — a lead prompt asking which pay systems
exist and where each is published, then **33 enumeration shards naming every
one of the 3,360 titles** (33 and 3,395 until the owner's six decisions of
2026-10-07, 33 and 3,398 until the Code title scan's rows
later on 2026-10-06, 33 and 3,433 until that morning,
39 and 4,003 until 2026-09-30, 38 and 3,953 until
that evening's Members decision, 34 and 3,492 until 2026-10-05, 34 and 3,489
until that day's special trial judges, 34 and 3,486 until its six govinfo
sections, 34 and 3,481 until the President's salary, 34 and 3,480 until the
twelfth batch's current-export rules and rows). The multiplicity
reason's "N such nodes carry one" is read off the graph on each run since
2026-09-30; it had said 28 since 2026-09-23 while the graph carried 37. `tests/test_unpriced_positions.py` asserts the
coverage rather than trusting it: every unpriced id appears in the pack, no
priced position appears in either document, and both documents are regenerated
and compared byte-for-byte so a stale copy fails.

Two things the pack does deliberately. **It asks for the DOCUMENT, not only
the figure**: this pipeline cannot publish a number somebody reports, so
"about $110,000" is unusable and "GS-0083, priced by OPM's Salary Table
2026-GS at <url>, which states a range per grade" is directly actionable — it
names a document to fetch, a join key, and what the document does and does not
say. Salary aggregators are named in the prompt only to be refused. And the
shards carry **no** follow-up-chain directive, which the lead prompt does:
that directive is for exploratory prompts and is anti-signal on an enumeration
pass, where expansion buries the per-title verdicts the shard exists to
produce. A test pins that asymmetry.

**Pack 4: the families, and the units (since 2026-10-07).** Pack 3 shards by
organisation, which asks the same question once per copy of a stamped title:
`Chief — Medicine Service` sits under eighteen medical-centre groupings and
`Chief Financial Officer` under sixty organisations.
`scripts/report_research_prompts.py` groups the unpriced posts into title
FAMILIES — the name with its multiplicity, any parenthetical and a trailing
`, VISN N` or `, Region N` set aside — and ranks them by unpriced nodes held.
On the first run 3,360 posts fall into 1,705 families and the top 100 hold
1,686 of them (50%); the largest family is `Chief Financial Officer` (60 posts
in 60 organisations) and the largest grouping by name is `VA Medical Centers`
(414). `docs/RESEARCH_PROMPT_4_TOP100.md` is one prompt naming those 100, about
18,000 characters with an appendix mapping each family to its node ids, asking
for one answer line per employer group wherever the pay system differs and
naming the cases where the people are not federal employees at all
(contractor-operated laboratories, Smithsonian trust staff, postal bargaining
units). It carries the follow-up directive after the table, scoped to findings
that change more than one family. `docs/RESEARCH_PROMPT_4_REMAINDER.md` carries
the other 1,674 posts in 16 organisation shards and, for the first time, the
681 organisation nodes that publish an estimate (240 committees, 62 with a
sourced figure beside, 379 bare) in 7 shards asking for the document that
prints the unit's own spending, by basis and period. `tests/test_research_prompts.py`
asserts every unpriced post is named exactly once across the two documents,
every estimate organisation once, and both equal a fresh render.

**A finding the families made visible: 432 of the 3,360 unpriced posts, and
90 priced ones, sit beneath a unit the graph marks as replaced** — the eighteen
former VISNs of `CURATION.md` §10, each still carrying its `VA Medical Centers`
grouping, its network officers and their posts. The viewer draws a replaced
node only when the reader asks for replaced units, so those 90 salaries
(the 72 Title 38 bands and the 18 USAJOBS-graded Associate Directors) are not
in the default view. What pays a medical-centre post does not depend on which
network it reports to; re-homing the medical-centre posts under the five
current networks is a curation decision, recorded and not taken here.

**Schedule 6, and the two refusals it turns into figures (since
2026-09-23).** `congressional_pay.py`'s own docstring records exactly what it
could not reach: "**Not** the House's Speaker, Majority Leader or Minority
Leader ... Left unpriced rather than guessed", and "**Not** the President of
the Senate (Vice President) node ... this module has not read a source for
it." Both refusals were about the network rather than the claim — the CRS
reports carrying those figures are Cloudflare-blocked from here — and the
figures were published the whole time on a host this project already reads.

The annual pay-adjustment order attaches its schedules by number ("(b) The
Vice President (3 U.S.C. 104) and the Congress (2 U.S.C. 4501) at Schedule
6"), and the Office of the Law Revision Counsel reproduces them verbatim in
the note to **5 U.S.C. 5332**. `uscode.house.gov` answers `robots.txt` 200 and
`statutory_schedule.py` has read it since 2026-09-18, so this was one fetch of
a host already in use. `us_code_pay_schedules.py` reads it,
`scripts/derive_us_code_pay_schedule_evidence.py` writes the evidence, and the
digest is recomputed from the bytes before a row is read.

**Four offices priced, and four refusals that are the point.** The Vice
President ($292,300), the Speaker of the House ($223,500), and the House
Majority and Minority Leaders ($193,400) — 4 of 4,591 positions, **0.09%**,
and the gate prints it on its own line so it cannot be read as anything
grander. What is not priced matters more than what is:

- **The three Senate leadership roles Schedule 6 also names are refused.**
  They already carry `positionStatutoryPay` from senate.gov's own footnote,
  and the field holds one source, so writing this one over that one would
  replace a claim with a claim rather than add evidence. `apply_pay_evidence`
  leaves any node another source has already priced alone, and the exporter
  runs it *after* `congressional_pay` for that reason. The agreement is real
  and is recorded rather than published twice: Schedule 6 prints 193,400 for
  the President pro tempore and for the Senate's leaders, which is the figure
  senate.gov states.
- **The Vice President's Senate-leadership node is refused.** This graph
  carries the office twice — `exec-vp` and
  `leg-senate-leadership-president-of-the-senate-vice-president` — and
  Schedule 6 states one salary for one officer. Pricing both would publish one
  salary as two.
- **No Member's SEAT is priced as such.** 174,000 is what Schedule 6 pays
  Senators, Members, Delegates and the Resident Commissioner, and this graph
  curates no seat node for any of them, for the reason `congressional_pay.py`
  already records: "Individual Senator Offices (100)" is a staff-office
  grouping. The OFFICES Members hold are another matter, and since
  2026-09-30 they are priced at that rate — see "The offices Members of
  Congress hold" below.
- **Schedule 7 priced nothing until 2026-10-05, and the stated reason was
  wrong.** This bullet used to say the Court of International Trade "has a
  court node and no judge node". It has two — `Chief Judge, CIT` and `Judge
  (×8)` — and they were the only Article I judges in the graph with no pay
  claim at all: 28 U.S.C. 252 states no parity (`derived_pay.py` refuses
  them) and uscourts.gov's table prints no CIT row (`judicial_pay.py`
  refuses them). Schedule 7 prints one, "Judges of the Court of International
  Trade 249,900", and the tenth research batch's CIT lead is what made the
  graph get checked rather than the docstring. `SCHEDULE_7_NODE_ROWS` prices
  exactly those two under the same `positionStatutoryPay` field: the chief
  judge as a judge of that court (the reading `judicial_pay.py` applies to
  every Article III chief judge) and the bench for each of its eight holders,
  since the field is office-rate class. The record says `schedule: "7"`, quotes
  Schedule 7's own heading, effective line and the marked head of ITS column
  ($320,700, the Chief Justice's row — 249,900 is also the District Judges
  row, so the heading is what ties the figure to the CIT), and the gate
  refuses a Schedule 7 tier on a node outside the judiciary, a Schedule 6
  office on a judicial node, the District Judges row claimed in its place, a
  dropped schedule mark, and the record moved to the Tax Court's chief judge.
  The other four Schedule 7 rows still price nothing: each tier is already
  priced from uscourts.gov, or reaches only circuit benches that bundle senior
  judges. The batch's own figures for the CIT ($243,300 and $231,700, citing
  28 U.S.C. 135) were wrong twice over — §135 is the district judges' salary
  section, and neither figure is the 2026 rate — and are recorded in
  `CURATION.md` §19.16 as the lead that pointed at the right nodes with the
  wrong numbers.

**The corroboration is the quiet win.** One document carries the schedules
three separate modules price from, and this is the only place the three can be
compared. Schedule 5's five Executive Schedule levels equal OPM's Salary Table
2026-EX to the dollar; Schedule 7's four judicial tiers equal uscourts.gov's
own table to the dollar. Nothing is published from either — a second source
for a figure already published changes no claim — but
`tests/test_us_code_pay_schedules.py` pins both agreements, so a drift in
either direction now fails a test instead of going unnoticed.

**Which node a row names is a reviewed identification, so nothing here is
better than a proxy.** Not one of the four matches its row by name: the Code
says "Vice President" where this graph says "The Vice President of the United
States", and "Speaker of the House of Representatives" where it says "Speaker
of the House". `SCHEDULE_6_NODE_ROWS` is that table, and **the alias table is
deliberately not consulted** — `aliases.py` is read by name and existence
evidence only and by no join that lands a number, and this is a join that
lands a number. Two of the four rows price two offices at once ("Majority
leader and minority leader of the House of Representatives"), the same
grouped shape as the Senate's footnote, so all four are filed
`scopeMatch: proxy` and graded `partial`.

**The scale, and a second grant of the narrowest rule.** Schedule 6 prints
"$292,300" on its first row and "223,500" on the Speaker's: the currency mark
sits once at the head of the column, which is exactly the typesetting
`financial_evidence.COLUMN_HEAD_MARK_SOURCE_TYPES` was written for when OPM's
GS table did the same thing. It is granted to a second source type here. The
guarantee that rule asks of a derive step is structural rather than promised:
`parse_pay_schedules` refuses a schedule whose first figure is unmarked or
whose later figures are marked, so the two figures a record quotes are
provably in one column of one table. The Vice President's own row carries the
mark and takes the stronger `_prints_whole_dollars` rule instead; the panel
shows which kind each record rests on.

The gate mirrors Schedule 6's rows as literals (`US_CODE_SCHEDULE_6_RATES`,
pinned equal to what the committed note prints), keyed by node id for a reason
sharper than the Senate case: the House Majority and Minority Leaders are
priced from **one row**, so they share a figure, a quote, a tier and a
citation, and only the node's own identity tells them apart. It refuses a
record whose quote does not carry the schedule's heading (193,400 appears
three times in Schedule 6 alone), whose quote drops the effective line, whose
bare figure is quoted without the marked head of its column, that prices a
judicial node from this source, that carries notes which are not its own
schedule row, or that puts a `uscode.house.gov` URL among the node's sources —
the exact channel by which a five-row table carried 29 positions to `verified`
on 2026-09-11. `tests/test_us_code_pay_schedules.py` corrupts each in turn.
Positions carrying a single-source statutory rate went **18 → 22**.

**A rate that holds for every holder, and the multi-post rule made per field
(since 2026-09-23).** Until this landed, `withdraw_pay_from_multi_post_nodes`
stripped every one of the eight pay fields from a node stating a multiplicity,
on one sentence of reasoning: "one rate beside a panel describing a whole group
reads as what one holder earns". That is true of an *incumbency-shaped* claim
and false of the others, and the owner's ask — "I want the Judge ×18" — was the
case that made the difference visible. 26 U.S.C. 7443(c)(1) says "Each judge
shall receive salary at the same rate … as judges of the district courts"; the
figure is the bench's fact by the statute's own words, and refusing it on the
`Judge (×18)` node while publishing it on the Chief Judge was the graph
claiming less than the evidence supports, which is the same error in the other
direction.

So the sweep is now per field, and the three classes are declared in
`pay_tables.py` so a new field cannot be added without deciding which it is:

- `INCUMBENCY_PAY_FIELDS` — `positionPayRate`, `positionGradePay`,
  `positionCurrentPay`, `positionSchedulePay` — are **stripped** from a
  multi-post node as before. A listing, a row of the current export, a level
  one archived office was at: each is one appointment's fact. One per-record
  exception since 2026-09-27: a `positionSchedulePay` block marked
  `classTitle`, priced from the Code's "Members, …" title, is every member's
  level and stays with `holders` (`pay_tables.CLASS_TITLE_PAY_FIELD`; the
  class-title section below).
- `OFFICE_RATE_PAY_FIELDS` — `positionStatutoryPay`, `positionDerivedPay`,
  `positionTierPay` and, since 2026-09-28, `positionTierReferencePay` — are
  **kept**, stamped with a `holders` block (`text`,
  `kind`, `count` or bounds, `appliesToEachHolder: true`, and a note) that
  the panel prints as "for each of the N holders". A tier rate is paid to
  every judge of the tier and a band bounds every holder.
- `UNIFORM_ROSTER_PAY_FIELDS` — `positionReportedPay` — is kept **only** when
  the roster lists the title N times at ONE rate and N equals the node's own
  stated multiplicity; `holders.uniformRate` says so, and two people at two
  rates still strip it, because then the figure is nobody's.

**28 multi-post nodes priced** on 2026-09-23 (33 since the five class-title
benches of 2026-09-27), each pinned in `tests/test_multi_post_pay.py`:
the four Article I benches (`Judge (×18)`, `(×15)`, `(×8)`, `(×4)`) from their
own courts' parity provisions (`derived_pay.BENCH_NODES` copies each chief
judge's provision to its bench, and a bench moved to another court's
provision is refused by node id); the eight Associate Justices and the
Southern District of New York's `District Judge (×28 active)` from the
compensation table (`judicial_pay.classify_seat` now prices a district's or
circuit's own *active* bench); and 22 White House Office titles the roster
lists N times at one rate — `Special Assistant (×4)` at $74,500,
`Special Assistant to the President for Domestic Policy (×6)` at $121,500,
`Presidential Speechwriter (×2)` at $110,500 (the last reached only once the
review found the stripped-title lookup counting rows printed under OTHER
titles in the same folded bucket, which had refused a title the report lists
exactly twice at one rate as "no row carries this title").
`whitehouse_pay.stated_multiplicity` reads the graph's own `(×N)` and accepts
the stripped title only when the report carries exactly N rows for it, every
row prints the same figure and every row prints the same TITLE
(`title_held_by_several_people_at_different_rates`, `..._on_different_terms`
and `title_held_under_several_spellings` are the three refusals — the third
because the folded index files "Assistant to the President and X" and "Deputy
Assistant to the President and X", two appointments, under one key, and at one
rate they would read as one title listed twice; latent on the 2026 report,
whose four fold-collision keys each print several rates — the one the new
refusal catches, `Senior Associate Staff Secretary`, is listed once bare at
$191,850 (a detailee) and once as a Special Assistant to the President at
$121,500 (an employee), and was already refused for the rates — so it is refused before it can be live). The quote's own "listed N times" suffix is checked by the gate
against the roster, so it cannot outlive a stripped `holders` block, and a
uniform block on a node whose name states no count is withdrawn by the sweep
rather than trimmed to one person's — the gate refuses the same block, and
the two agree. A uniform record publishes its own method string
(`rate_reported_for_each_of_the_people_listed_under_this_title`) and its
document-count block is worded for each listed person, because the review
found the one-person wording shipped beside a `holders` count of six; the
gate mirrors both method strings and refuses either on the other's block. Pay claims went **461 → 488** on this, and to **491** with the
Federal Reserve below, and to **492** when the lookup above was corrected.

**One bench shape stays refused, and the statute is committed for it — with
a correction the adversarial review made.** Thirteen `Circuit Judge (×N
active + senior judges)` nodes bundle senior judges into the count. 28 U.S.C.
371(b)(2) provides that a senior judge who does not meet subsection (e)'s
certification "shall continue to receive the salary that he or she was
receiving when he or she was last in active service or, if a certification
under subsection (e) was made for such justice or judge, when such a
certification was last in effect. The salary of such justice or judge shall
be adjusted under section 461 of this title." A salary set by reference to a
past year and adjusted since need not equal the tier's current rate, so one
figure for such a bench would be false of some of its members. The first
draft of this rule said the salary "may be frozen" and quoted only the first
half of the provision; the review read the committed fixture's operative
text and found the last sentence contradicts that word — the same shape as
the CAVC repealed-text case, caught the same way. The refusal is worded to
the section now, the test pins the §461 sentence beside the first, and
nothing published changed: no figure rests on the reading either way.
`tests/fixtures/uscode/senior_judges_28_usc_371.html` is committed,
`judicial_pay.SENIOR_JUDGE_MARKER` refuses any judge node whose name says
"senior" (`bundles_senior_judges_whose_salary_28_usc_371b2_sets_apart_from_
the_tier_rate`), and the gate mirrors the marker and refuses such a block
outright, pinned by a corruption test. Measured: 15 judge nodes name senior
judges and none is priced.

**The Federal Reserve, and a third route into the Executive Schedule.** The
research pack (`CURATION.md` §19) reported the Fed Chair's salary as "$203,500
per annum" from 12 U.S.C. 242. The section was fetched and **prints no dollar
figure**; a test pins that against the bytes. What it prints is the
identification the two existing matchers could not make: "Chair, Board of
Governors" is not equal to the Code's "Chairman, Board of Governors of the
Federal Reserve System" (§5312, Level I), and the two Vice Chairs are placed by
a title that never names them — §5313's "Members, Board of Governors of the
Federal Reserve System" (Level II) — with §242 the statute that designates the
two Vice Chairmen from among the members. `statutory_schedule.REVIEWED_TITLE_
ROWS` is the reviewed table (node → statutory title → the §242 sentence that
says why), the same shape as `SCHEDULE_6_NODE_ROWS`, re-adjudicated on every
run: the node must still carry the name the row was written against, the
title must be one the committed sections print, the fixture's digest is
recomputed, and the quote must be in the section's **operative** text — the
page prints each designation sentence a second time in its Amendments note,
and `tests/test_statutory_schedule.py` moves a sentence beneath the cut to
show the row falls. Three posts priced under their own method
(`level_assigned_by_5_usc_5312_5316_to_the_office_a_second_statute_identifies_
this_post_as`), each resting on **three** documents — §242 identifies the
office, §5312/§5313 sets its level, OPM's table prices it — of which one
states the figure, so the count block reads 3 and 90% where every other
schedule record reads 2 and 80%, and the panel prints the basis and the
quoted sentence in words. `Governor (×4 members)` is reached by the same
"Members" title and was deliberately left unpriced for four days:
`positionSchedulePay` is incumbency-class, so a row would have been written
and withdrawn on every build, and pricing a bench from a class title was
recorded as a separate decision — which the owner made on 2026-09-27 (see
"Benches priced from the Code's class title" below). The gate mirrors
the three rows by node id (`US_CODE_REVIEWED_IDENTIFICATIONS`), re-reads the
basis fixture with its own stdlib cut, and refuses a swap between the two
Level II Vice Chairs, a renamed node, a scope claimed on a reviewed row, a
reviewed identification on a node with no row, a basis quote found only in
the notes, a digest that is not the committed section's, a `basis` sentence
that is not the reviewed row's (the panel prints it as the reason the figure
applies, so an unmirrored one was a fabricated-reason channel — an
adversarial review found it passing with the opposite legal reading), and the
ordinary method on a reviewed node; each route's own method string is now
checked on every schedule record.

**Six more reviewed rows, from the fourth research batch (since 2026-09-27).**
The batch reported Executive Schedule levels for some forty posts, and most of
its "certain" grades were checked against the committed sections and found not
to be in the Code at all (inspectors general are not on the Schedule; the IRS
Chief Counsel is Level V, not IV; the Code prints no "Deputy Secretary of
Commerce" and no CDC Director). Six survived, and each is the same shape as the
Fed's: the Code prints a title the graph does not — "Chairman, Federal
Communications Commission" against `Chair, FCC`, "Commissioner of Internal
Revenue" against `Commissioner, IRS`, "Administrator, Federal Aviation
Administration" against `Administrator, FAA`, and "Secretary of Homeland
Security" against OPM's archive spelling `Secretary of the Department of
Homeland Security`, which `CURATION.md` §8 kept because that is what the
archive prints — and a second statute says which office it is. Each row's
basis section is committed under `tests/fixtures/uscode/` (47 U.S.C. 154,
15 U.S.C. 41, 26 U.S.C. 7803, 49 U.S.C. 106, 6 U.S.C. 112 and 113) and its
quoted sentence is re-found in the section's operative text by both readers on
every run; 47 U.S.C. 154 is the one basis that states the level itself ("shall
receive an annual salary at the annual rate payable from time to time for level
III of the Executive Schedule"), and it agrees with §5314. The FCC's and FTC's
`Commissioner (×4)` benches are reached by "Members, Federal Communications
Commission" / "Members, Federal Trade Commission" (Level IV) and were left
unpriced that morning for the reason the Fed's Governors were; the owner
decided the same day, below. Nine reviewed rows then; positions priced
from the Schedule **102 → 108**, pay claims **492 → 498**, unpriced **4,099 →
4,093**. The test that doctors the Fed's section copies every basis fixture
into the temporary directory first, so it now shows the other six rows standing
while the three Fed rows fall — a doctored fixture says something about that
fixture alone.

**The military basic-pay table, refused by the host and recorded (2026-09-27).**
The same batch named DFAS's basic-pay tables as the document that would price
the Joint Chiefs, the service chiefs and the senior enlisted advisers at the
O-10 and E-9 rates. Every host that publishes the table — `www.dfas.mil`,
`militarypay.defense.gov`, `comptroller.defense.gov`, the six service hosts
and the Coast Guard's — answers `robots.txt` **and** the page itself with an
Akamai 403 from this sandbox, so `STANDARD_4XX_HOSTS` would buy nothing: that
policy covers a host whose robots file is unavailable but whose pages answer.
`tests/fixtures/dfas/README.md` records each attempt with its `.meta.json`,
and 37 U.S.C. 203 and 1009 are committed as the law the table rests on —
§203(a)(2) caps O-7 to O-10 basic pay at the monthly equivalent of Executive
Schedule level II, which is a ceiling and not a rate, so no module reads them
and nothing is published from them. The module's shape, should a DoD-published
table ever answer, is `derived_pay.py`'s: Title 10 gives the post its grade,
the table prices the grade, neither states the figure, and the panel says so.

**The uniformed services, priced from a table the repository already held
(`military_pay.py`, since 2026-10-06).** `tests/fixtures/dfas/README.md` had
recorded on 2026-09-27 that every host publishing the military basic-pay
table — dfas.mil, militarypay.defense.gov, comptroller.defense.gov, the
service hosts, the Coast Guard's — answers `robots.txt` and the page itself
with an Akamai 403, and that "if a DoD-published table becomes reachable" the
module's shape would be `derived_pay.py`'s. The twelfth batch's Defense
cluster re-measured the same refusal on ten hosts and then found the table in
a file committed four days before that README was written: the note to 5
U.S.C. 5332 (`pay_schedules_5_usc_5332.html`), from which
`us_code_pay_schedules.py` prices Schedules 5, 6 and 7, reproduces Executive
Order 14368 in full, and its **Schedule 8 — Pay of the Uniformed Services
(Effective January 1, 2026)** is the monthly basic-pay table itself. The
parser's `if number not in ("5", "6", "7")` had been stepping over it on
every run under a digest the gate already recomputed. `military_pay.py` reads
the eighth schedule from the same bytes; nothing was fetched from any DoD
host and the README now says so.

**Two routes, both from Schedule 8, and a tenth pay field.**
`positionMilitaryPay` is office-rate class — a grade a statute fixes is the
office's — and its figure is **twelve times a printed monthly rate**, which no
document states: Schedule 8 prints basic pay by the month ("part i-monthly
basic pay"), so every record carries the monthly figure as printed, an
`arithmetic` block (`operation: monthly_times_12`, the factor named on the
record) and `documentsStatingTheFigure: 0`, and `financial_evidence` accepts
it under a third computed operation beside `plus_percent` and `percent_of`,
granted to this source type (`military_basic_pay_schedule`): the monthly
figure must carry its mark in the evidence, the annual figure must be printed
nowhere, and the result must equal base × 12 to the cent. **A grade a statute
fixes** (`GRADE_PROVISIONS`, seventeen reviewed rows by node id): Title 10
and Title 14 fix the grade in so many words — "The Chief of Staff, while so
serving, has the grade of general without vacating his permanent grade"
(10 U.S.C. 7033(b)), "The Commandant while so serving shall have the grade of
admiral" (14 U.S.C. 302) — 37 U.S.C. 201(a)(1) assigns "General" and
"Admiral" to pay grade O-10 (the Space Force rows carry 201(a)(2)'s sentence
too), and the O-10 row prints $18,999.90 in all eleven populated columns:
three documents, 90% on the project's scale, $227,998.80 a year. The Chairman
and Vice Chairman of the Joint Chiefs, the Chief of the National Guard
Bureau, the chief and vice chief of each of the five services, the Commandant
and Vice Commandant of the Coast Guard, and the commanders of Special
Operations Command and Cyber Command (10 U.S.C. 167(c), 167b(c)) — the only
two of the eleven combatant commanders whose grade a statute fixes. **A post
the schedule's own footnote names**: the enlisted footnote states one rate
for seven posts by title, "basic pay for this grade is $11,166.90 per month,
regardless of cumulative years of service", and five are nodes here by name
equality — the Sergeant Major of the Army, the Master Chief Petty Officers of
the Navy and of the Coast Guard (one printed item, "of the Navy or Coast
Guard", read as both by a rule declared once and quoted whole), the Chief
Master Sergeant of the Air Force and the Sergeant Major of the Marine Corps —
one document, 70%, $134,002.80 a year. Twenty-two posts, all `partial`, all
`proxy`, none of which carried a pay claim of any kind before.

**Three rules, each a measurement.** A row must be **flat** before one figure
may stand for the grade: the first block (2 or less through Over 18) must
print nothing for it and every populated cell of the second must print the
same figure, true of O-10 and O-9 and false of every other grade — which is
why the senior enlisted advisers are priced from the footnote that names them
and never from the E-9 row, whose cells run from $8,105.10 to $10,729.20. The
document **disagrees with itself by $100**: the officer table's footnote 1
prints the Level II ceiling as "$18,899.90 per month" while the O-10 row
prints $18,999.90, no rendering of the order reachable from here settles it
(the Federal Register's plain text answers its "Request Access" page and
govinfo's prints every schedule as "[GRAPHIC] [TIFF OMITTED]"), so every
record quotes the footnote verbatim beside the row's figure and reconciles
nothing. And **a ceiling is not a rate**: the nine combatant commanders whose
grade a presidential designation under 10 U.S.C. 601(a) carries, not a
statute, are named by the footnote only as subject to the Level II cap and
are refused, as §19.7 refused 37 U.S.C. 203(a)(2). Also refused, each on the
derive step's output: the Joint Chiefs grouping's six copies of the service
chiefs and the Coast Guard's Commandant (one office, one node priced, the
`exec-vp` rule), the Space Force's generic "Senior Enlisted Advisor" (the
footnote prints "Chief Master Sergeant of the Space Force"; a rename
candidate), and the NGA Director (10 U.S.C. 441(b)(3)'s grade holds only IF an
officer holds the post). The gate (`military_pay_violations`) re-parses
Schedule 8 from the committed bytes with its own reader, mirrors the
seventeen rows by node id and the footnote's title rule, re-finds every grade
sentence and the §201 row in the operative text, recomputes the twelve months
and refuses the monthly figure published as the annual one, a row that is not
flat, a document claiming to state the figure, a block on a JCS copy, a
`verified` grade, and a statute or schedule URL among the node's own sources;
`tests/test_military_pay.py` and `tests/test_military_pay_gate.py` corrupt
each in turn. The panel heads the figure "PAY — MILITARY BASIC PAY, 12 × THE
MONTHLY RATE" and prints the monthly figure, the multiplication, the grade
sentence and the $100 beside it.

**Titles the Code prints with a footnote mark where a full stop should be,
and the parser that could not see them (since 2026-10-06).** The twelfth
batch's Code title scan compared `statutory_schedule.load_schedule()`'s index
against the five committed sections and found the index short of what the Code
prints: `parse_section` accepts a list item only when its text ends in a full
stop, and the Office of the Law Revision Counsel prints four items with a
footnote reference — `&nbsp;<sup><a …>1</a></sup>`, an element whose digit
survives tag-stripping as " 1" — two of them IN PLACE of the stop. Both carry
the Code's own footnote, "So in original. Probably should be followed by a
period." So "Commissioner of Food and Drugs, Department of Health and Human
Services" (§5315, Level IV) and "Under Secretary of Education" (§5314, Level
III) were never indexed, and `CURATION.md` §19.7 had recorded that the Code
prints no NOAA Under Secretary when §5314 does — in a 162-character item over
`MAX_TITLE_CHARS`, which the parser also skips. Two rules were measured before
one was built. Dropping every footnote element admits neither title (with the
element gone the item still has no stop) and FELLS the BLS reviewed row, which
deliberately keys on the printed "The 2 Commissioner of Labor Statistics,
Department of Labor" — a mid-text mark the Code's footnote says "probably
should not appear" and this project publishes as printed. The rule built
strips a TRAILING footnote-reference element only, before `_text_of`, and
treats the item as closed by it; a mark after a full stop yields the title
without the digit, a mid-text mark is never touched, and nothing looser (a bare
trailing digit, a `<sup>` without the Code's anchor shape, an over-long item)
changes anything. Measured: 415 → 418 positions, 413 → 416 indexed, 9 → 6
skipped, exactly three titles added and none removed — the two above and
"Principal Deputy Under Secretary of Defense for Acquisition, Technology, and
Logistics" (§5314, whose establishing section the Code's own note says was
repealed in 2011, printed and therefore indexed like the thirty other defunct
titles the Schedule still carries) — zero existing records changed, and none
of the three reaches a node by the whole-name or scoped route. The 140-character
bound is left alone: the five items over it are exactly the ones carrying
provisos and joint titles the parser would have to split, and splitting is the
production of a title this file refuses by name. `tests/test_statutory_schedule.py::FootnoteMarkTests`
pins the four marks as the pages print them, the three titles, the BLS row
unchanged and the bound.

**One reviewed row rides on it and two tier-reference rows need no Schedule
title at all.** The FDA's Commissioner (`Commissioner, FDA`) is priced from
the title the fix made visible, with 21 U.S.C. 393(d)(1) — "There shall be in
the Administration a Commissioner of Food and Drugs …" — the section that
creates the office; the current PLUM export lists "COMMISSIONER OF FOOD AND
DRUGS" at EX-IV under the FDA, which corroborates the level and reaches no
node, since the archive's strip reads only a trailing ", <organisation>".
Reviewed rows **97 → 98**, Schedule-priced **236 → 237**. The NOAA
Administrator and the Archivist of the United States are the NNSA
Administrator's and the Librarian's shapes: 15 U.S.C. 1503b both pays the
Under Secretary of Commerce for Oceans and Atmosphere "at the rate now or
hereafter provided for Level III of the Executive Schedule Pay Rates (5 U.S.C.
5314)" and says that officer "shall serve as the Administrator of the National
Oceanic and Atmospheric Administration" — the identification sentence rides
on the record as it does for the NNSA — and 44 U.S.C. 2103(b) pays the
Archivist "at the rate provided for level III of the Executive Schedule under
section 5314 of title 5". The Archivist's row rests on 2103(b) alone and
settles nothing about the Schedule's double listing of the title at §5314 and
§5316, which `statutory_schedule.py` still drops as ambiguous; the row's
comment says so. Both fixtures and the FDA's came from govinfo's 2024-edition
rendering through the link service (`docs/NETWORK_ACCESS.md` §16), and the
fetch surfaced a precision gap this module had carried since 2026-10-05: it read
the edition off the link URL alone, so ten of its records said "an edition of
the United States Code" where the meta's `final_url` named the 2024 granule.
It reads `final_url` since, and all fifteen of its govinfo documents name the
edition. Tier-reference rows **23 → 25**, published **45 → 47**. Pay claims
**1,193 → 1,196**, unpriced **3,398 → 3,395**. `CURATION.md` §19.20
carries the scan's other twenty-three leads and why each was declined: the
export contradicting the Code on the NRC's office directors, the SBA's and
OPM's associate officials and the NRO's Director; thirty-one organisations the
Code names that carry no post node; the Deputy U.S. Trade Representatives'
counted class blocked on the graph's abbreviation "Deputy USTR"; and the
Solicitors the Code prints where the graph stamps a General Counsel.

**Posts renamed to the title a committed document prints (since 2026-10-07,
the owner's decision).** Two leads the twelfth batch left as "rename
candidates" were blocked on a name and nothing else: the Space Force's
`Senior Enlisted Advisor`, whose office Schedule 8's enlisted footnote prints
as "Chief Master Sergeant of the Space Force", and the three `Deputy USTR — …`
nodes, which §5314 places as the counted class "Deputy United States Trade
Representatives (3)" at Level III and 19 U.S.C. 2171 composes ("There shall be
in the Office three Deputy United States Trade Representatives, …"). No
sanctioned writer renamed a post from a Code document, so
`scripts/rename_posts_to_printed_titles.py` is one, the sixth writer of the
curated file, with `data/curation/post_renames.json` its reviewed table: each
row names the node, its current name, the proposed name and the committed
document and verbatim string that license it. Every run recomputes the
fixture's digest and re-reads the string (inside Schedule 8 as
`military_pay.load_schedule_8` parses it, or in a Code section's operative
text), and refuses a row whose node no longer carries the stated name or has
moved, that is not a post, that is a no-op under `canonical_name_key`, a
single token, generic, or a sibling's name; a counted-class row must keep the
graph's own qualifier after the separator unchanged and spell out only the
part before it, which must equal the class title's singular. It never
re-types, re-parents or removes, and a second run applies nothing. The Space
Force row's basis says in words that treating the curated "Senior Enlisted
Advisor" as that office is the owner's identification and no document states
it. The renames priced all four through routes that already existed: the
footnote route of `military_pay.py` at $11,166.90 a month ($134,002.80 a
year, one document, 70%), and a ninth counted class at Level III ($209,600,
three documents, 90%). The current PLUM export lists three "DEPUTY UNITED
STATES TRADE REPRESENTATIVE (RANK OF AMBASSADOR)" rows at EX-III under
sub-organisations the graph has no node for, so it corroborates the level and
reaches no post. A per-node diff showed nothing else move: no page, Manual,
PLUM or signature record of the four was lost. The gate's counted-class check
had required a composing statute on the OLRC host; it now takes the same
either-host test the reviewed-row checker uses, pinned against a govinfo URL
for the wrong section.

**The owner's six decisions of 2026-10-07, and the one this repository did
not carry out as asked.** The twelfth batch closed by listing six decisions
only the owner could make; the owner made all six the same morning, and five
landed as asked.

**The COPS Office was not re-parented, because the Government Manual says
where it sits.** The decision was "yes to the re-parent": move the Office of
Community Oriented Policing Services under the Office of Justice Programs, so
its Treasury line ($462,550,050.10, printed beneath OJP's header) could apply
without being counted twice. Checked before anything was built, the Manual's
entry files COPS among the Justice Department's own offices ("Offices /
Boards") and OJP among its bureaus. The Treasury's header is an appropriation
grouping, not an organisation chart, and a re-parent would have made the
graph contradict the government's own handbook to make the arithmetic
convenient. So the decision's intent was built instead: a printed line that
is a component of a header sum applied to one node may also be applied to a
different organisation node it names, provided that node is neither the
holder nor its ancestor or descendant. The node is `official` with the exact
line, stamped `treasury_counted_in_header_sum` with the holder's id and a
generated sentence saying the same money is already inside the holder's
figure, and kept out of its parent's arithmetic by the route external-section
lines take. The gate re-derives every stamp from the committed statement and
refuses an unstamped measured node whose line sits inside a header sum that
does not contain it — the silent double count this rule exists to prevent.
COPS reached its line through a `TREASURY_ROW_ALIASES` row (the node's name
contains the line's; the Manual's entry 290). OJP is unchanged at
$4,518,129,781.85, and the Department of Justice's thirteen unlined
organisations each rose 1.64%, because COPS's old apportioned share went back
to the pool and its measured money was not subtracted a second time.

**Ginnie Mae, through the one alias a header sum may take.** Header sums took
no alias by design. The owner chose to alias the statement's "Government
National Mortgage Association:" header (one line, "Guarantees of
Mortgage-Backed Securities", −$1,839,035,438.49) to the node named "Ginnie
Mae", on 12 U.S.C. 1716b's statutory name and the Manual's HUD entry. It is
the only key in `TREASURY_HEADER_SUM_ALIAS_KEYS`; every other alias is still
refused on a header, and the gate mirrors it by node id. The figure is
negative and is published as the statement prints it, the Mint's rule, and
the node's own unlined children become `treasury_pool_negative`. The
consequence is worth stating plainly because it looks wrong at first: HUD's
twelve unlined organisations (FHA, FHEO and the ten regions) each rose
51.25%, from $263.1m to $398.0m. HUD's published figure is the statement's
net, and a measured child that nets $1.84bn below zero means everything else
in HUD spent that much more than the net shows; the cascade divides that
remainder among the unlined units by subtree size, the same weak proxy this
file already records, now applied to a larger and more honest pool.

**A stated number of dollars less, and a chain through a second statute.**
Four posts are paid an amount LESS than another officer whose pay this
project already sets by reference to a level: the Architect of the Capitol's
Inspector General at "$1,500 less than the annual rate of pay of the
Architect of the Capitol" (2 U.S.C. 1808(c)(3), $226,500), the Capitol
Police's at "$1,000 less than the annual rate of pay in effect for the Chief
of the Capitol Police" (2 U.S.C. 1909(b)(4), $227,000), the GAO's at "$5,000
less than the annual rate of pay of the Comptroller General" (31 U.S.C.
705(b)(4), $223,000), and the CBO's Deputy Director at "$1,000 less than the
annual rate of pay received by the Director" (2 U.S.C. 601(a)(5)(B),
$227,000). The CBO's Director is the fifth: 601(a)(5)(A) pays "the maximum
rate of pay in effect under section 4575(f)", and 4575(f) sets that maximum
at Level II, a chain row ($228,000). `financial_evidence` gained a fourth
computed operation, `minus_dollars`, granted to the tier-reference source
type: the dollar amount must be printed with its mark in the record's own
quote, the result must equal base minus amount to the cent, and the record's
own figure must be printed nowhere. **The base cannot outlive the officer it
is read from**: a subtraction is computed only from the referenced officer's
own record in the same derivation, stamped only after that officer's block is
on the graph at exactly that base, and the gate refuses one whose officer
publishes nothing or another figure. Every record rests on three documents,
none stating the figure; the CBO Deputy's two sentences of 601 are one
document.

**A reader for instruments the Code prints outside its sections.**
`notes_instruments.py` reads two document classes this project had refused:
Reorganization Plans, which sit in Title 5's Appendix, and the chambers' pay
orders, which the Code prints only in its Statutory Notes, below the cut
`operative_text` makes to keep repealed amendment text out. Reading notes
generally would let that text through, so the reader locates ONE instrument
by its own printed heading (once, and only once), takes it to the next
heading of its kind, removes any Amendments note inside the range, cuts at
"Prior to amendment", refuses a quote found only inside GPO's bracketed
insertions, and drops the signature paragraphs before any text is formed.
Eight posts priced: NOAA's Deputy Administrator (Level IV) and Chief
Scientist (Level V) from Reorganization Plan No. 4 of 1970, the Deputy
Secretary of Commerce (Level II) from No. 3 of 1979 — the office §8 recorded
as absent from §5313, which it is, because the Plan sets its pay by
reference — and the SEC's Chair as a reviewed Schedule row whose basis is
Plan No. 10 of 1950; the Secretary of the Senate and the Senate's Sergeant at
Arms from the Order of the President pro tempore of March 25, 2024, and the
Clerk and the Chief Administrative Officer of the House from the Order of the
Speaker of January 17, 2025, each at Level II. Every pay-order record carries
the caution that it is the order the 2024 edition of the Code reprints and a
later order, which this project has not read, may have changed the rate; the
panel prints it. Plan No. 3 of 1970 creates the EPA's Administrator and
states no level, so that node keeps the rate it already had. The posts the
orders name that exist here only as office nodes (the House Sergeant-at-Arms,
the Chaplains, the House Inspector General) are not priced, and the gate
refuses a block moved between a post and the office node of the same name.

**USAJOBS announcements as a listing of a post's grade.** The owner asked
whether USAJOBS can be used because it is a `.gov` host. The host is OPM's,
so the publisher is official; what an announcement states is narrower than
that suggests — the pay plan, grade and series of one vacancy at one
facility, often a temporary detail, with that locality's salary range. So it
is used for exactly that and no more: `usajobs.py` reads the title, agency,
pay scale and grade, series, location and dates, never the HR contact (a
sentinel test plants one and asserts it appears nowhere) and never the
salary; a reviewed table maps a curated title family to its announcements,
and the family is priced only when at least two announcements agree on one
plan and grade. The figure is OPM's 2026 GS-15 BASE range ($126,384–$164,301,
before locality), through `gs_pay.py`, with the announcements as the listing
the range rests on. Five announcements at five medical centres list
"Associate (Medical Center) Director" at GS-15, series 0670, so the 18
`VAMC Associate Director (Administrative)` nodes carry the range; the
`Network CFO` family has one announcement and is refused; the Associate
Director for Patient Care Services is Title 38 Nurse V, which has no national
range, and is declined. The listing writes no source URL and no verification
method — no announcement names a node, and a Montana vacancy cannot confirm a
template node under a VISN the VA has replaced — and the five announcements
count as one listing, so the range rests on two documents (80%), not six.

**What the six decisions bought, measured on the rebuild.** Pay claims
**1,196 → 1,231** of 4,591 positions; unpriced **3,395 → 3,360** (no document
names the title **2,627 → 2,592**); Schedule-priced posts **237 → 241** (the
three Deputy U.S. Trade Representatives as a ninth counted class and the SEC's
Chair on a Plan-based reviewed row); tier-reference **47 → 59** (five
subtractions and chains, seven instrument rows); military **22 → 23**; GS and
SES ranges **22 → 40**, eighteen of them from USAJOBS; measured nodes **170 →
172** (COPS and Ginnie Mae), estimates **683 → 681**; `verified` 539 → 547 and
`partial` 453 → 445 on the existing arithmetic. `CURATION.md` §19.21 records
each decision, what was built and what was declined.

**Posts a contractor pays, said in so many words (`employment_status.py`,
since 2026-10-07, the owner's decision).** A post with no pay claim counts as
an unpriced post that a research pass should find a salary for. For some posts
no federal pay document will ever name the title, because the people who hold
them are not paid on a federal schedule. The owner decided to say so for a
post only where a committed official document establishes it. This is the
first case. The claim rests on **three** documents, because the first one
alone does not say what it reads as saying.

- **The operator.** NETL's own page, "The NETL Unique Advantage of Being a
  Government-Owned, Government-Operated Laboratory" (May 22, 2023,
  `tests/fixtures/doe/netl_operating_model.html`): "The U.S. Department of
  Energy operates 17 national laboratories. NETL is the only government-owned,
  government-operated facility. The other 16 are government-owned,
  contractor-operated." The page names only NETL.
- **Which sixteen.** DOE's own index, `www.energy.gov/national-laboratories`
  (`tests/fixtures/doe/national_laboratories.html`, robots allows, fetched
  2026-10-06), prints "The Energy Department's 17 National Labs" and labels
  each of the seventeen as an accordion heading. It says of NETL alone that it
  "is government-owned and government-operated (GOGO)". So "the other 16" is
  read off DOE's page and not inferred from the graph's own grouping.
  `CONTRACTOR_OPERATED_LABS` is a reviewed table keyed by node id, mapping
  each of the graph's sixteen other lab nodes to the label the page prints.
  Every run re-checks it: the page must label exactly seventeen laboratories,
  the sixteen rows plus NETL must be exactly those labels, and each node must
  still carry its reviewed name. One node is renamed from its label in the
  curated file, "National Laboratory of the Rockies (NLR)", and it reduces to
  the page's label under `canonical_name_key`.
- **What an operator's staff are.** "Operated by a contractor" is a statement
  about the operator, not literally about who employs each post. The
  Department of Energy Acquisition Regulation, 48 CFR part 970 (GPO's 2025
  edition, revised as of 2025-10-01, from www.govinfo.gov, robots allows,
  `tests/fixtures/doe/dear_48_cfr_970_govinfo2025.xml`), closes most of the
  gap in its own words. Each quote is re-found inside the one SECTION whose
  SECTNO it names:
  - DOE "has negotiated technology transfer clauses with the contractors
    managing and operating its laboratories" (970.2770-3);
  - "Employees of a management and operating contractor are entitled to the
    same rights and privileges with respect to outside employment as other
    citizens" (970.0371-7);
  - "the compensation paid individual employees should be left to the judgment
    of contractors subject to the limitations of DOE-approved compensation
    policies, programs, classification systems, and schedules"
    (970.3102-506);
  - "The contracts are totally financed by DOE advance payments"
    (970.3102-370).

  **Part 970 never says in words that an M&O contractor's staff are "not
  Federal employees".** A test pins that negative against the bytes. The
  published wording therefore says what the regulation does say: the
  contractor sets the pay within DOE-approved schedules, and DOE finances the
  contract.

**What it publishes.** `positionEmployer` goes on each Position node
**directly** under one of the sixteen laboratory nodes. The block holds
`federallyPaid: false`, `kind: contractor_operated_laboratory`, the laboratory
id, name and DOE label, the three documents (url, sha256, fetchedAt, title,
date, verbatim quotes, CFR section) and two generated sentences.

- The headline: "Not on a federal pay schedule: <laboratory> is one of the 16
  DOE laboratories operated by a contractor (DOE, NETL page, May 22, 2023)."
- What is not established: "No document here names who holds this post or
  says every holder is the contractor's employee, and the title is a template
  every DOE laboratory node carries. 'Not on a federal pay schedule' means not
  paid as a federal employee on a federal pay schedule; the money is DOE's, through the
  contract."

What the documents *do* establish is not paraphrased onto the node. The panel
prints each document's quotes verbatim beside its link (a CFR quote with its
section).

**112 posts** carry it (16 laboratories × 7 templated titles). That includes
the multi-post nodes, because an employer is the same fact for every holder.
**NETL's 7 posts get nothing.** NETL is government-operated, its posts are
federal, they stay unpriced, and the gate refuses the block there.

The block writes no `sourceUrls`, `sourceTypes`, `lastVerified` or
`verificationMethod`, no cost field and no pay field. A post that any pay
document has priced is left alone. The block is applied after
`annotate_pay_documents`, so that rule is read off the final tree. The field
is in `EVIDENCE_OWNED_FIELDS` and `MINIMAL_GRAPH_FIELDS`. On the rebuild the
only change to the graph was the 112 blocks: no cost, verification status or
source moved.

**The gate** (`employer_violations`, stdlib only) re-reads the three fixtures
with its own reader and does the following:

- recomputes each digest against both the `.meta.json` and the block;
- re-finds every mirrored quote, each CFR quote inside its named section;
- re-reads the seventeen accordion labels;
- reads the parent off the tree it walks, never off `parentId`.

It refuses the block in each of these cases:

- on a NETL post, on a non-post, or under any parent that is not one of the
  mirrored sixteen;
- under a renamed laboratory, or with a laboratory id, name or label that is
  not the tree's;
- beside any of the ten pay fields, or beside a measured cost;
- with `federallyPaid` anything but `false`;
- with a headline or qualifier that is not the mirrored template, or any key
  (on the block, a document or a quote) that the module never writes, so a
  paraphrase cannot ride along unchecked;
- with a dropped, reordered, retitled or redated document, or a fetch date
  that is not the committed one;
- with an edited quote or a moved section, or a digest or URL that is not the
  committed one;
- with an inflated document count or a future date;
- with any of the three URLs among the node's own sources, or a verification
  method naming this source.

`tests/test_employment_status.py` corrupts each case in turn. It also pins
both mirrors (the sixteen ids and the documents) equal to the module, and
runs derive, build, gate and withdrawal end to end on a small base graph.

**The panel** reads PAY over "Not on a federal pay schedule" where it read
"Not available". The badge reads "No cost known; not on a federal pay schedule".
`#info-employer` prints the headline, the qualifier, and the three documents
as links, each followed by its own quoted words. The atlas view prints the same text in its Pay row.
`scripts/frontend_smoke.mjs` opens a contractor-laboratory post and asserts
the headline, the PAY heading, the exact sentence and the qualifier. It also
opens NETL's Laboratory Director and asserts it says none of it.

**Declined, and why.**

- No block on NETL's posts. They are federal, and no pay document in hand
  names them.
- No reading of 48 CFR part 970 as saying "not federal employees", because it
  does not say that.
- No block deeper than a laboratory's direct children. There are none today,
  and a deeper node might be something other than the laboratory's staff.
- The headline the owner's decision named, "Not federally paid", was not used
  as written: 970.3102-370 says DOE finances the contracts, so the money is
  federal and only the salary schedule is the contractor's. The headline and
  the qualifier say "Not on a federal pay schedule"; the field keeps its name,
  `federallyPaid: false`, and the qualifier says in words what it means.

**Size, and a margin the next field will break.**
`tests/test_viewer_graph.py` requires `graph.min.json` to be under half of
`graph.json`. At HEAD the margin was already only 29,631 bytes (9,163,641
against 18,386,544 / 2).

- The first draft quoted whole paragraphs, repeated each document's publisher
  and description on every node, and carried a paraphrase of what the
  documents establish. That broke the rule by about 15 KB.
- The block now carries the shortest verbatim span that holds each part of the
  claim, with no paraphrase. The descriptive fields sit once in the evidence
  file's report.
- On the rebuild: `graph.json` 18,940,566 bytes, `graph.min.json` 9,465,327,
  a margin of **4,956 bytes**.

The next field added to the viewer copy will trip the rule whatever it is. The
rule should be revisited deliberately, not loosened by whoever trips it.

**Benches priced from the Code's class title (since 2026-09-27, the owner's
decision).** The Executive Schedule places some offices one at a time
("Chairman, Federal Trade Commission", Level III) and some as a class —
"Members, Federal Trade Commission" (Level IV) is the office every one of
the Commission's other four members holds, and 15 U.S.C. 41 is what composes
the Commission of five Commissioners. This graph draws such a bench as one
node, `Commissioner (×4)`, and until now nothing could price it: the
reviewed route could name the class title, but `positionSchedulePay` is
incumbency-class and the sweep stripped it. The owner's ask was to price
the benches, and the reading is the one `derived_pay.BENCH_NODES` already
applies to "Each judge shall receive salary at the same rate": the level is
the office's by the statute's own words, so it is each holder's, not one
appointment's.

Rather than reclassifying the whole field — a singular statutory title on a
node that states "(×N)" would then publish one office's level for N posts,
and the whole-name and scoped routes could reach such a node — the exception
is per record and declared three times over. A reviewed row carries
`classTitle: True`; `match_reviewed_rows` refuses such a row unless the
statutory title IS a class title (`is_class_title`: the Code's
"Members, …" form, so "Independent Members, Thrift Depositor Protection
Oversight Board" and every singular title are refused) and the node's own
name states a multiplicity, and refuses an unmarked row on a node that
states one, since the sweep would strip it on every build; the record and
the published block carry `classTitle: True`, and only that mark lets
`withdraw_pay_from_multi_post_nodes` keep the block, stamping `holders` from
the node's own `representsPosts` exactly as it does for an office-rate field.
The gate mirrors the mark by node id as the ninth element of each
`US_CODE_REVIEWED_IDENTIFICATIONS` row and refuses: the mark on a row that
prices one office, the mark outside a reviewed identification, a class-title
row without the mark, a marked block whose title is not "Members, …", a
marked block on a node that stands for one post, and a bench block without
`holders` or with a count the name does not state. The panel and the atlas
view say in words that the Code's title is a class title placing every
member of the body at that level, then print the holders sentence, and the
document-count block is reworded for a class (`classRoles` /
`classCaution` in `pay_documents.py`: the third document "composes the body
of the members this node stands for").

**Five benches priced**, all `partial`, all `proxy`, each on three
documents: the FCC's, FTC's, CFTC's and FERC's `Commissioner (×4)` at Level
IV ($197,200) from 47 U.S.C. 154, 15 U.S.C. 41, 7 U.S.C. 2 and 42 U.S.C.
7171 respectively, and the Fed's `Governor (×4 members)` at Level II
($228,000) from 12 U.S.C. 241, which composes the Board of seven members.
That section is also a trap worth recording: its operative text prints
"shall each receive basic compensation at the rate of $15,000 per annum",
the 1935 figure the Executive Schedule superseded, and a reader who searched
the section for a salary would find it. The row's basis says so, nothing
publishes it, and the figure comes from OPM's table as on every other
schedule record. **Nine more single-post reviewed rows** landed with them,
the Fed's shape each time, their basis sections committed under
`tests/fixtures/uscode/`: the CFTC and FERC chairs (7 U.S.C. 2, 42 U.S.C.
7171), the Director of OPM (5 U.S.C. 1102), the Commissioner and Deputy
Commissioner of Social Security (42 U.S.C. 902 — whose subsection (b)(3)
itself compensates the Deputy "at the rate provided for level II of the
Executive Schedule", agreeing with §5313), the FEMA Administrator (6 U.S.C.
313), the Director of the BLM (43 U.S.C. 1731), the Director and Deputy
Director of the CIA (50 U.S.C. 3036, 3037) and the CMS Administrator
(42 U.S.C. 1317). Twenty-four reviewed rows in all; positions priced from
the Schedule **108 → 123**, pay claims **498 → 513**, unpriced **4,093 →
4,078**, multi-post nodes priced **28 → 33**.

**Pay set BY REFERENCE to a level: the GAO's officers and the Inspectors
General (`tier_reference_pay.py`, since 2026-09-28, the owner's decision).**
Two sections read on 2026-09-27 and recorded rather than built on: 31 U.S.C.
703(f) sets the Comptroller General's pay "equal to the rate for level II of
the Executive Schedule" and the Deputy's at level III, and 5 U.S.C. 403(e)
(the Inspector General Act) sets an Inspector General's basic pay at "the
rate payable for level III of the Executive Schedule under section 5314 of
this title, plus 3 percent". Neither office is ON the Schedule — §§5312–5316
print none of these titles, so `statutory_schedule.py` can never reach them —
their pay is set by reference to one of its tiers. That is `derived_pay.py`'s
shape from the other side of the Schedule, with OPM's Salary Table No.
2026-EX standing where the Judicial Compensation table stood: the statute
names the tier, the table prices the tier, and **no document states the
figure for the post**. So it is a ninth pay field, `positionTierReferencePay`,
office-rate class, publishing `documentsStatingTheFigure: 0` and the count
of documents it rests on with what that count is worth on the project's own
scale — its own field rather than a widening of `positionDerivedPay`, for the
reason that module gives for not widening `positionStatutoryPay`: that gate
mirrors four parity provisions against the uscourts.gov table, and folding a
different table, a different statute shape and an arithmetic step into it
would loosen checks already guarding eight published records.

**An Inspector General's figure is arithmetic on a printed one, and the
block says so.** $209,600 × 1.03 = $215,888, which no document prints. The
record carries the arithmetic in the open (`arithmetic`: the base as the
table prints it, the percentage as the statute states it, the result), the
panel prints "$209,600 + 3% = $215,888 — arithmetic this project performed,
printed by no document", and `financial_evidence` accepts it under a fifth
scale rule granted to this source type alone (and, since 2026-09-30, to
the derived module's percent-of records, below),
`COMPUTED_FROM_MARKED_FIGURE_SOURCE_TYPES` (`unitsEvidenceKind:
currency_mark_on_the_figure_the_record_is_computed_from`): the base must
carry the currency mark ATTACHED in the evidence exactly as
`_prints_whole_dollars` demands of a record's own figure, the record's own
figure must NOT be printed with a mark anywhere in it, and the figure must
equal the computation to the cent. A GAO record's figure is the level's own
printed row and takes the ordinary printed-mark rule.

**Which Inspectors General, decided by the statute's own list.** 403(e)
prices "an Inspector General (as defined under section 401 of this title)";
401(4) defines that as "the Inspector General of an establishment"; 401(1)
lists the establishments by name — fifteen departments (printed compressed,
"the Department of Agriculture, Commerce, Defense, …") and some two dozen
agencies. `parse_establishments` reads that sentence off the committed
section on every run, the gate parses it again with its own reader
(`tier_reference_establishments`, pinned equal), and a node is priced only
when it is named exactly `Inspector General`, sits DIRECTLY under an
organisation whose name reduces to a listed establishment, and stands for one
post. That guard is what keeps the stamp out: this file records that
`Inspector General` names 80 nodes here and most are a copied administrative
stamp under DIA, NGA, DARPA, DLA and the other Defense agencies, and none of
those is an establishment. Measured: **81 IG nodes considered, 27 priced**,
54 refused with the reason on the record — the designated Federal entities'
(5 U.S.C. 415, read and committed, prints no rate of pay: the NLRB, the FEC,
the NEA, the CPSC, the SEC and the rest), the CIA's (5 U.S.C. 423, not read),
the legislative branch's (the GAO's own, the Library's, the Architect's, the
Capitol Police's), the FBI's qualified `Inspector General (DoJ IG covers
FBI)`, and AmeriCorps — which 401(1) lists as the Corporation for National
and Community Service, a name this graph carries only in the alias table,
and `aliases.py` is read by no join that lands a number. The NSA's and NRO's
ARE establishments by name and are priced, though they sit among the stamped
agencies; the list decides, not the neighbourhood.

**Three bodies whose own section names the office under the stamp (since
2026-10-05, the owner's "fetch the six sections from govinfo and keep
going").** `CURATION.md` §19.15 and §19.16 had left six sections unread
behind the OLRC host's maintenance page. Fetched from the Government
Publishing Office's 2024-edition rendering on `www.govinfo.gov` through its
link service, three of them are this module's shape and two of those are
stamped titles: **22 U.S.C. 6203(b)(3)** pays the U.S. Agency for Global
Media's Chief Executive Officer "at the annual rate of basic pay for level
III"; **52 U.S.C. 20923(d)(1)** pays "Each member" of the Election
Assistance Commission at Level IV; **52 U.S.C. 30106(a)(4)** pays the
Federal Election Commission's members, other than its two ex officio ones,
"compensation equivalent to the compensation paid at level IV". The graph
draws each head as `Director / Administrator / Chair, <agency>` with a
`Deputy Director / Vice Chair` beside it, and the rule the reviewed Schedule
rows set for that stamp applies: it is priced only where the body's own
statute names which office stands under it. Here that sentence is in the
same section as the pay sentence — 6203(b)(1) makes the CEO the head of the
Agency; 20923(c)(1) and 30106(a)(5) have each commission choose its chair
and vice chair "from among its members" — so a row carries
`identificationQuote`, re-found in the operative text on every run and
published as `identification.statuteIdentifies`, which the panel prints as
the sentence that says what the template stands for. It is not a second
document and the record counts two. The pair reading (a Chair and a Vice
Chair, not a Director and a Deputy) is the one the statutes support: each
creates a chairman and a vice chairman together and no deputy to its staff
director, whose own pay 30106(f) caps "at a rate not to exceed" Level IV — a
ceiling, which prices nothing, and the FEC's `General Counsel` (capped at
Level V) already carries OPM's archived listing. A statute document now
names its publisher and edition from its URL (`derived_pay.statute_publisher`),
the gate accepts a Code granule from either host, and — because govinfo also
publishes the Government Manual, whose URL sits legitimately among many
nodes' own sources — the gate's leak check keys on `is_us_code_document_url`
(the OLRC host, or a govinfo path carrying `USCODE-`), not on the host; the
first version keyed on the host and refused seventeen honest nodes. The
other three sections price nothing and `CURATION.md` §19.18 says why: 50
U.S.C. 1803(a) designates "11 district court judges" and states no pay (and
nothing in it bars a senior judge, whose salary §371(b)(2) sets apart); 38
U.S.C. 7101A(b) names a pay SYSTEM, "rates equivalent to the rates payable
under section 5372 of title 5", with a carve-out for members in the SES it
does not name; 39 U.S.C. 202(a)(1) pays a Governor "$30,000 a year plus $300
a day for not more than 42 days of meetings", a stipend and an attendance
figure, not an annual rate. Five priced (USAGM's CEO $209,600; the four
commissioners $197,200 each), all `partial`, all `proxy`; tier-reference
records **37 → 42**, published **36 → 41**, reviewed rows **10 → 15**; pay
claims **1,105 → 1,110**, unpriced **3,486 → 3,481**.

**28 published of 29 derived**, and the one difference is the leave-alone
rule working: the Department of Justice's IG carries OPM's archived listing
with a printed level and rate (`positionPayRate`), and a figure set by
reference never displaces a printed one. The gate mirrors the GAO rows by
node id and the IG rule with its establishment list, reads the parent off
the tree it is walking, recomputes the arithmetic from
`EXECUTIVE_SCHEDULE_RATES`, and refuses: an IG under a Defense agency or a
DFE, a block naming another establishment than the tree's, an IG block
without arithmetic or a GAO row with it, a percentage the Act does not state,
a result that is not the base plus the percentage, a base that is not the
table's Level III, a GAO row moved onto the other officer or priced at the
wrong level, a dropped document, one claiming to state the figure, an
inflated percentage, a verified grade, an exact scope, a rate beside another
pay field, and a statute or table URL among the node's own sources.
`tests/test_tier_reference_pay.py` corrupts each in turn; pay claims
**513 → 541**, unpriced **4,078 → 4,050**.

**Thirteen more reviewed rows, from §19.9's candidate list (since
2026-09-28, the owner's decision).** `CURATION.md` §19.9 closed by listing
the posts whose Executive Schedule title the committed sections print under a
name this graph does not use, and called them fifteen; counted by node id
when the rows were written, they are **thirteen** — one of them a bench of
four — and the correction is recorded rather than the count restated. Each
is the Fed's shape: the Code prints the title, a second statute says which
office it is, and the row's basis quote is re-found in that section's
operative text by both readers on every run. Ten basis sections were
committed under `tests/fixtures/uscode/` for them, and two of the fetches
are worth a line each. **The NIST Director took three fetches to cite.** The
Code's own title carries the identification ("Under Secretary of Commerce
for Standards and Technology, who also serves as Director of the National
Institute of Standards and Technology", Level III), but a reviewed row needs
a second statute, and 15 U.S.C. 272 (establishment) and 274 (the Director's
powers) print no Under Secretary at all: the 2010 reauthorization struck the
appointment sentence out of §274, and the chapter's own table of contents
puts it at **15 U.S.C. 273a**, whose subsection (d) reads "The Under
Secretary shall serve as the Director of the Institute". The three dead
ends (§§272, 274 and 278, the last the Visiting Committee) are not
committed; the section that says it is. **The ONDCP Director's
provision moved too.** 21 U.S.C. 1702(b), which the sixth batch would have
cited, was struck in 2018 — the Code says so in its Amendments note — and
the Director is now at 21 U.S.C. 1703(a)(1)(A): "There shall be at the head
of the Office a Director". §1702 is committed beside it because it is the
section that establishes the Office the Director heads, and because "looked
and it no longer says so" is a fact worth keeping.

The thirteen: the NIST Director (III); the NRC's Chair (II) and its
`Commissioner (×4)` bench from the class title "Members, Nuclear Regulatory
Commission" (III, the sixth class-title bench, 42 U.S.C. 5841 composing the
Commission of five); the SBA Administrator (III, 15 U.S.C. 633); the NSF
Director (II) and Deputy Director (III), whose own sections — 42 U.S.C. 1864
and 1864a — each set the office's basic pay at the level the Schedule
prints, the SSA Deputy's shape; the ONDCP Director (I); the BLS Commissioner
(IV, 29 U.S.C. 3), whose Schedule title the Code prints as "The 2
Commissioner of Labor Statistics, Department of Labor" with its own footnote
saying the word "The" probably should not appear, and which this project
publishes as printed rather than corrected; the Census Director (IV, 13
U.S.C. 21); the CEA Chair (II) and its two single `Member, CEA` nodes from
"Members, Council of Economic Advisers" (IV) — the Vice-Chair shape, one row
per node, no class mark, because each node stands for one post; and the
CPSC Chair (III, 15 U.S.C. 2053). CPSC's own `Commissioner (×4)` stayed out
until 2026-09-30: the Code prints "Members, Consumer Product Safety
Commission (4)", the counted-class shape the owner decided that day (below). Nothing
in the matcher, the gate or the sweep changed; the one test that moved
counts the class-title benches and reads six now. Reviewed rows **24 → 37**,
positions priced from the Schedule **123 → 136**, pay claims **541 → 554**,
unpriced **4,050 → 4,037**, multi-post nodes priced **33 → 34**.

**The eight candidates of §19.10, in three tables (since 2026-09-28, the
owner's decision).** Four are reviewed Schedule rows, the shape above: the
FHWA Administrator (II, 49 U.S.C. 104), the USPTO's `Director / Under
Secretary for IP` (III, 35 U.S.C. 3 — the Code's one joint title, which the
graph writes as two halves), the Commissioner of Reclamation (V, 43 U.S.C.
373a) and the `Register of Copyrights & Director` (III — the Register is on
the Schedule by name, and 17 U.S.C. 701 styles the office "as director of
the Copyright Office", which is the graph's "& Director"). Reviewed rows
**37 → 41**.

Three are the tier-reference shape, and the module's row table stopped
being "the GAO's two officers": 44 U.S.C. 303 pays the GPO's Director at
Level II and its Deputy at Level III; 20 U.S.C. 9514(c) pays the IES
Director at Level II; and 20 U.S.C. 9517 pays "each Commissioner" of the
National Education Centers at Level IV — the NCES Commissioner by name in
subsection (b), and the NCER and NCEE Commissioners under subsection (a)'s
class sentence, which names no centre. So those two rows carry a **third
document**, 20 U.S.C. 9511(c)(3), the sentence that composes the Centers,
the way an Inspector General's record carries 401(1)'s list: a row's
`composition` block, mirrored in the gate as `TIER_REFERENCE_IES_COMPOSITION`
with the set of rows that need it, and refused where the block is missing,
misquoted, or present on a row 9517(b) prices by name. The batch had put
the IES Director at Level II "by 20 U.S.C. 9517"; the level was right and
the section was the Commissioners'. Tier-reference records **28 → 34**.

The eighth is the FJC Director, which the batch's condition ("if 28 U.S.C.
628 sets the salary at a judicial tier's") did not meet: §628 is
appropriations, §627 is retirement, §625 is staff, and §626 pays the
Director "the same as that of the Director of the Administrative Office of
the United States Courts" — whose salary 28 U.S.C. 603 sets "the same as
the salary of a district judge". Two statutes to the tier, so
`derived_pay.py` gained two things: an office row (the AO Director, one
hop, exactly the four courts' shape with `subject` where a court row says
"every judge of") and a **chain** row (the FJC Director) whose provision
carries `via`, the middle statute, and whose record lists **three**
documents, 90% on the project's scale, none stating the figure. The gate's
mirror row grows a fourth element for the chain and refuses a block that
drops the middle document, misquotes it, or claims a chain its provision
does not make; the two Deputies (92 percent of the Director's, under both
sections) were refused with the reason on the record, arithmetic on a join
being a thing this field did not publish — until 2026-10-05, when the owner
decided the shape for the Tax Court's special trial judges and both were
priced with them (see "A percentage of a join" below). The panel and the atlas print
the subject and the chain in words. Derived records **8 → 10**; pay claims
**554 → 566**, unpriced **4,037 → 4,025**. The CBO Director was read and
refused: 2 U.S.C. 601(a)(5) sets the pay at "the maximum rate of pay in
effect under section 4575(f)", a chain through a section this project has
not read, and the Deputy's at $1,000 less than that.

**Every batch's leads accounted for (since 2026-09-28, the owner's ask).**
`CURATION.md` §19.12 is the ledger: each of the eight research batches, what
it yielded, and where each lead ended up. Closing it landed **twenty more
reviewed Schedule rows** — NASA, FTA, FRA, MARAD and MSHA's heads, the OFR
Director, the FMC's Chair and its `Commissioner (×4)` bench (the seventh
class-title bench), the USPTO's bare `Deputy Director` (a row is keyed by
id, so the bare-title floor that governs page evidence does not apply), and
ten of the stamped `Director / Administrator / Chair, <agency>` heads — the
MSPB, the NCUA Board, the Peace Corps, Selective Service, the FLRA, the NEH,
the NTSB, the Special Counsel, the PBGC, the PRC and the Export-Import
Bank's President — each row naming which of the three offices the agency's
own statute creates, so the office under the template is priced and never
the template. The Export-Import row is the one whose identification leans
on a fact outside its operative text: the Schedule still prints the Bank's
pre-1968 name ("of Washington"), and the row says so. **Two tier-reference
rows** with them: the FCA Board's Chairman, because the Schedule prints a
"Governor of the Farm Credit Administration" the statute no longer has
while 12 U.S.C. 2242(d) itself pays the Chairman at Level III; and the
Librarian of Congress at Level II from 2 U.S.C. 136a–2. That section is
numbered with an en-dash, and none of the three operative-text readers
matched such a heading — the Librarian's section read as page chrome until
the pattern admitted a dashed suffix in all three, pinned by a test.
Reviewed rows **41 → 61**, Schedule-priced **140 → 160**, tier-reference
**34 → 36**, pay claims **566 → 588**, unpriced **4,025 → 4,003**.

**The bankruptcy judges at 92 percent, and the magistrate judges refused
(since 2026-09-30, the owner's decision).** `CURATION.md` §7.2 had recorded
both benches as reaching zero nodes under the old blanket multi-post rule,
and §19.12 left them as the one "still open" item that was a build rather than
a decision once the owner made it. The owner asked for both at 92 percent.
One of the two statutes says that and one does not, and the difference is the
whole of what this section records. **28 U.S.C. 153(a)** pays "each bankruptcy
judge" "a salary at an annual rate that is equal to 92 percent of the salary
of a judge of the district court": a rate, for every holder, by the
statute's own words. **28 U.S.C. 634(a)** pays magistrate judges "salaries to
be fixed by the conference pursuant to section 633, at rates for full-time
United States magistrate judges **up to** an annual rate equal to 92 percent"
of the same, and part-time magistrate judges "not less than an annual salary
of $100, nor more than one-half the maximum". That is a ceiling the Judicial
Conference sets a figure beneath, and no document here states what it
fixed. Both sections are committed under `tests/fixtures/uscode/`; the
bankruptcy judges are priced and the magistrate judges are refused, with the
reason on the record (`derived_pay.NOT_PRICED`) and a test asserting both
directions against the operative text — "up to an annual rate" is in §634
and not in §153.

The figure is **$249,900 × 92% = $229,908**, which no document prints, so it
is `positionDerivedPay`'s shape with one step more: the parity provisions
join a statute naming a tier to the table pricing it, and this row multiplies
the table's printed figure by a percentage the statute states. The record
carries `percentOf` and an `arithmetic` block (`operation: percent_of`, the
base as the table prints it, the tier, the percentage, the result, and a
note saying no document prints it), the same open arithmetic the
tier-reference module publishes for an Inspector General's "plus 3 percent",
and `financial_evidence` accepts it under the same computed-from-a-marked-
figure rule, which gained a second operation (`percent_of` beside
`plus_percent`) and a second grantee (`statutory_parity_derived_pay`); the
validator recomputes base × percent / 100 and refuses a result that is not
it. The gate mirrors the two rows by node id in `DERIVED_PAY_PERCENT_OF`,
computes the expected figure from the mirrored tier, and refuses: the tier's
own rate published as the figure, a dropped arithmetic block, a percentage
the statute does not state, a base that is not the table's figure for the
tier, a result that is not the percentage of the base, the other operation,
a scope that does not say it is a percentage, an empty note, an arithmetic
block on a parity row, and the record moved to the magistrate bench of the
same court — which has the same count shape and a real statute and no
provision. The panel and the atlas print the multiplication in words, and
the document-count pass words the caution for it ("the figure is that
arithmetic, which neither prints"). Two documents, 80% on the project's
scale, neither stating the figure — here literally true of the table too.

**Two nodes, both benches.** `Bankruptcy Judge (×12)` under the Southern
District of New York and `Bankruptcy Judge (×varies)` under the standard
district structure, which stands for every district's bankruptcy judges and
is priced because §153(a) says "each bankruptcy judge" wherever the judge
sits; the office-rate sweep stamps `holders` on both, exact 12 and unstated.
The AO's Deputy Director stayed refused that day and its reason said why the
two cases differ: that one is 92 percent of a figure that is itself a join
(the Director's, equal to a district judge's by the same section), where the
bankruptcy percentage is taken of the table's own printed figure; the owner
decided that shape on 2026-10-05 (below). Derived
records **10 → 12**, pay claims **588 → 590**, unpriced **4,003 → 4,001**,
multi-post nodes priced **35 → 37**.

**A percentage of a join, from a host that was under maintenance (since
2026-10-05, the owner's decision).** The bankruptcy section above ends on the
one shape `derived_pay.py` still refused: a percentage taken not of the
table's printed figure but of a figure that is itself a join. `CURATION.md`
§19.16 carried it as the one open decision, with three nodes behind it, and
the owner decided it with "price the special trial judges". **26 U.S.C.
7443A(d)** pays "Each special trial judge … at a rate equal to 90 percent of
the rate for judges of the Tax Court", and a Tax Court judge's rate is itself
26 U.S.C. 7443(c)(1)'s parity to a district judge's; the AO's Deputy
Director is 92 percent of a Director whom 28 U.S.C. 603 pays as a district
judge, in two sentences of one section with an unrelated sentence between;
the FJC's Deputy is paid by 28 U.S.C. 626 what the AO's Deputy is paid. So
the chain rule the FJC Director already used (`via`, the middle statute)
and the percent-of rule the bankruptcy judges already used now compose: a
provision may carry `percentOf` and `via` together, a `quote` may be a tuple
of sentences from one section, each re-found separately in the operative
text and published joined by " … ", and `percentOfWhat` says in words what
the percentage is of ("a Tax Court judge's salary, which 26 U.S.C. 7443(c)(1)
sets at a district judge's"). The arithmetic is the same open block the
bankruptcy records carry — $249,900 × 90% = **$224,910** for the special trial
judges, × 92% = **$229,908** for both Deputies — and no document prints any of
the three. The special trial judges are a `(×multiple)` node, so the
office-rate sweep stamps `holders` on it and the figure reads as every
special trial judge's by the statute's own "Each".

**The seven fetches, retried, and the route taken instead.** 50 U.S.C. 1803,
38 U.S.C. 7101A, 22 U.S.C. 6203, 39 U.S.C. 202, 26 U.S.C. 7443A, 52 U.S.C.
20923 and 52 U.S.C. 30106 were fetched from `uscode.house.gov` again and every
one came back HTTP 200 with the same 14,615-byte "Under Maintenance" page as
the morning's attempt; all seven stubs were deleted with their `.meta.json`
files before anything read them (`docs/NETWORK_ACCESS.md` §15). The one
section this decision needed was taken from the **Government Publishing
Office's own rendering of the 2024 edition of the Code** on `www.govinfo.gov`,
a host this project already reads the Government Manual and OMB's database
from, whose `robots.txt` allows the path, and whose link service
(`/link/uscode/26/7443A?link-type=html`) resolves to the granule rather than
to a URL guessed from the chapter structure (the first guess, `partII`, was a
404 behind a redirect). `operative_text` cuts that rendering at the same
"Editorial Notes" heading, so the quote is checked against the law and not
the notes exactly as on the OLRC's pages. `STATUTE_HOSTS` is the closed list
of the two hosts a derived-pay statute may be read from, each record names
its publisher and edition, and the gate mirrors the list and refuses a statute
cited to any other host. The other six sections were not fetched from
govinfo: nothing in hand needed them that evening, and each is a lead
`CURATION.md` §19.15–§19.17 names with its section, which the next session
can take by either host. Derived records **12 → 15** (12 on two documents at
80%, 3 on three at 90%, none stating the figure); pay claims **1,102 →
1,105**, unpriced **3,489 → 3,486**, multi-post nodes priced **40 → 41**.
The six sections the OLRC host would not serve were then fetched from
govinfo the same evening, on the owner's instruction, and three of them
priced five posts through the tier-reference module (the paragraph "Three
bodies whose own section names the office under the stamp" above); the
other three are declined in `CURATION.md` §19.18.

**A counted class of offices, and the fourteen rows the ninth batch bought
(since 2026-09-30, the owner's decision).** The Code places some offices one
at a time and some as a counted class: "Assistant Attorneys General (11)" at
Level IV places eleven offices at once and names none of them, and 44 such
titles stand across the five sections. Every route refused them — the
whole-name route because the title states several posts, the scoped route
because it names no organisation, the reviewed route because a bench row
needs a "Members, …" title — and `CURATION.md` §19.12 carried the shape as
the first of its open decisions. The owner decided it; the shape is the
fourth route, `match_counted_classes`, and it is narrower than a name and
wider than a bench. A member is priced only when the Code's own section
prints the class title with its count (checked as printed words, because
the title parser sets the State paragraph aside — "Assistant Secretaries of
State (24) and 4 other State Department officials…" — and the Labor one
carries a proviso); the node is a single post whose name is the class's
singular office first and whole, then a separator from a closed list, and
where the name says "of <department>" that department is the class's own
(so an "Assistant Secretary of Defense for Policy" curated under Labor
would be refused, not priced as one of Labor's ten); the node sits inside the
organisation the class belongs to, walked up the tree; no listing on the
node (OPM's archive or the current export) reports another pay plan or
level — a listing that says ES wins, and an EX listing at the class's level
corroborates; the graph names no more members than the Code counts; and
**the node id is in `COUNTED_CLASSES`**, because which nodes are members is
a review and not a rule. That last condition is what the State Department
proved necessary: its stamp names an "Assistant Secretary" over the Foreign
Service Institute, the Office of the Chief of Protocol and the U.S. Mission
to the United Nations, whose heads are a Director, an Ambassador and a
Permanent Representative, and a name rule alone would have priced the
template. The three are declined in `CURATION.md` §19.14 with the reason, as
is SAMHSA's "(dual-hat)" Assistant Secretary, refused structurally by the
parenthetical rule.

Where a second statute composes the class it is the record's third document
— 28 U.S.C. 506's "11 Assistant Attorneys General", 22 U.S.C. 2651a(c)'s "not
more than 24 Assistant Secretaries of State … at level IV", 29 U.S.C. 553's
nine offices, 20 U.S.C. 3412(b)'s list, 42 U.S.C. 3533(a)'s seven, 42 U.S.C.
7133(a)'s eight — and where that statute names the office itself the sentence
rides on the record as `namedAs`: 2651a says which Assistant Secretary heads
which bureau for eight of State's thirteen, 3412 names Education's two by
title, 553 names OSHA's, and 3533 says the Federal Housing Commissioner "shall
be one of the Assistant Secretaries". Two classes have no composing statute
in hand — the EPA's Assistant Administrators (Reorganization Plan No. 3 of
1970 is not a section of the Code) and Commerce's Assistant Secretaries (15
U.S.C. 1506 was read and adds one office to those "now provided for by law"
without counting them) — and those records rest on two documents and say so.
HUD's organic act says seven Assistant Secretaries where the Schedule counts
eight; the record quotes the seven and the bound used is the Schedule's own,
recorded rather than reconciled. **40 members priced across eight classes**
(State 13, DOJ 7, EPA 7, HUD 4, Labor 3, Education 2, Energy 2, Commerce 2),
six of them already carrying OPM's archived EX-IV listing and now both
blocks, agreeing; 34 posts priced for the first time. The gate mirrors the
whole table (`US_CODE_COUNTED_CLASSES`), reads the class title off the
section's own operative text, walks the tree for the scope, re-checks the
name rule, the listing, the composing sentence, the naming sentence, the
digest and the granule, and after the walk counts members per class across
the whole graph against the Code's N; `tests/test_counted_classes.py`
corrupts each in turn and asserts on the real base graph that every member
passes the rule and sits in its scope.

The same decision settled the counted BENCH shape: a "Members, X (N)" title
may price a `Commissioner (×N)` node through a class-title reviewed row only
when the bench's own count equals the Code's, checked in the matcher and
the gate (`reviewed_row_bench_count_disagrees_with_the_code`), so the CPSC's
four are priced from "Members, Consumer Product Safety Commission (4)" with
15 U.S.C. 2053 composing the Commission of five. The ninth research batch
then bought **fourteen reviewed rows** in the shapes this file already has:
the SEC's bench from "Members, Securities and Exchange Commission" (15
U.S.C. 78d composes it of five); the EEOC's Chairman (III) and its Vice
Chairman as one of "Members, Equal Employment Opportunity Commission (4)"
(IV), both from 42 U.S.C. 2000e-4(a)'s designation sentence; the NMB's
chairman (45 U.S.C. 154 Second); the NEA's Chairperson, whom the Schedule
still spells Chairman (20 U.S.C. 954(b)); the President of Ginnie Mae (12
U.S.C. 1723); the Wage and Hour Administrator (29 U.S.C. 204); the OMB's
Director (I) and Deputy Director (II) from 31 U.S.C. 502, and its three
templated "Administrator / Chief" office heads — the Administrator for
Federal Procurement Policy (41 U.S.C. 1102; §1101 was fetched first and
names no Administrator, so it is not committed), the Controller of Federal
Financial Management (31 U.S.C. 504) and the Administrator of Electronic
Government (44 U.S.C. 3602); and the PHMSA Administrator (49 U.S.C. 108,
which the current export already lists at EX-III). Declined with reasons in
§19.14: the NCUA's and PRC's stamped Vice Chairs (neither statute
designates one — wrong for the PRC, whose 39 U.S.C. 502(e) was not fetched
that day and does; corrected and priced on 2026-10-05, §19.20), the SEC's Chair (78d does not designate the Chairman; that
is a 1950 reorganization plan), the EPA's Administrator (no organic section
of the Code to cite), and every Member of Congress the batch priced at
$174,000 as a committee chair or ranking member, which is the Members
decision still open. The reviewed checker's granule regex now admits a
dashed section number (2000e-4), which the EEOC rows needed. Reviewed rows
**61 → 75**, Schedule-priced **160 → 214**, class-title benches **7 → 9**,
pay claims **590 → 638**, unpriced **4,001 → 3,953**, multi-post nodes
priced **37 → 39**.

**The offices Members of Congress hold, priced at the seat rate (since
2026-09-30, the owner's decision).** Every research batch since the fourth
reported the same figure for the same posts — $174,000 for every committee
chair and ranking member, from senate.gov's salary page, the House Clerk's
Salary.pdf and CRS RL30064 — and every batch was held under one question,
carried from `CURATION.md` §19.6 to §19.14 as the largest open lead: is a
committee-chair node a seat? The premise was never in doubt and this file
had already recorded it as a finding (§7.1 of the ledger: "a Member who
holds one of those posts is paid the Member rate. Neither is a committee
chair separately compensated") — recorded as a reason NOT to price them.
The owner decided the other way, keeping the premise: a committee's chair
and ranking member ARE Members of the chamber that constitutes the
committee, Schedule 6 prints a separate rate only for the Vice President,
the Speaker, the majority and minority leaders of each chamber and the
President pro tempore, and none for a committee chair, a ranking member, a
whip or a conference chair, so those offices are priced at the seat's own
rate and nothing is added for holding them.

It is a rule, not a table, and the gate mirrors the rule. A **committee
post** is a single-post Position whose name begins `Chair, ` or `Ranking
Member, ` and whose tree parent is typed Committee or Subcommittee — 436
nodes, 218 of each; `Staff Director` and `Minority Staff Director` share
those parents and are never reached. A **leadership office** is one of the
25 nodes `MEMBER_LEADERSHIP_NODES` lists by id under a chamber's Leadership
grouping: the Senate's eleven (the whips, the assistant leaders, the
conference chairs and secretary, the policy, steering and campaign
committee chairs — the "eleven Senate leadership roles" the fourth batch
reported and §19.7 refused as "the committee-chair decision") and the
House's fourteen. **The chamber is read off the tree, never off the name**:
`leg-senate` prices from the row "Senators", `leg-house` from "Members of
the House of Representatives", and every House record notes that the
Delegate and Resident Commissioner rows print the same 174,000, since a
subcommittee chair could in principle be a Delegate. Four posts are refused
by name: the Joint Economic Committee's Chair, which alternates between the
chambers by Congress, and its Vice Chair — the figure would be the same
either way, but a record names one row, and which chamber the holder sits
in is a fact about a person this project never reads; the Problem Solvers
Caucus's "Co-Chairs" node, two people in a form the multi-post rule cannot
read; and the Senate's "President of the Senate (Vice President)", the
office `exec-vp` already carries at its own row.

The record is its own method (`METHOD_MEMBER_SEAT`), carries a `memberSeat`
block with the role, the body, the chamber and the basis in words, and the
panel leads with "PRICED AS A MEMBER'S SEAT, NOT FOR THE OFFICE". The
document count is one document stating the figure — for the SEAT — and the
caution says that the post being a Member's is a reviewed rule this project
applies, not a document naming the post; `scopeMatch` is `proxy` and the
grade `partial`. The gate (`member_seat_violations`) reads the parent's type
and the chamber off the tree it is walking and refuses a seat block on a
leadership office that has its own Schedule 6 row, on a node outside both
chambers, on a post whose name has no Member-role prefix, under a parent
that is not a committee, on a node that stands for several posts, at the
other chamber's row, with a role or body the name does not say, with a
basis that lacks the schedule's own list of separately priced offices or
does not say it is a rule, and a seat row priced without the method;
`tests/test_us_code_pay_schedules.py` corrupts each in turn and asserts on
the published graph that every qualifying chair and ranking member carries
one and no staff director does. **461 priced** (436 committee posts, 25
leadership offices; Senate 191, House 270): pay claims **638 → 1,099**,
unpriced **3,953 → 3,492**, and the positions no document reaches
**3,181 → 2,720**. The four U.S. Code sections the ninth batch's remaining
leads need (50 U.S.C. 1803, 38 U.S.C. 7101A, 22 U.S.C. 6203, 39 U.S.C. 202)
could not be fetched the same evening: `uscode.house.gov` closed every
tunnel after 11 seconds with 39 bytes received, while govinfo answered 200
and senate.gov 302, so it is that host and not the proxy
(`docs/NETWORK_ACCESS.md` §15); `CURATION.md` §19.15 carries each lead.

**The tenth batch, and a host that answers 200 with nothing (2026-10-05).**
The retry of those four fetches, and of three more sections the tenth batch
named (26 U.S.C. 7443A for the Tax Court's special trial judges, 52 U.S.C.
20923 for the Election Assistance Commission, 52 U.S.C. 30106 for the FEC),
came back HTTP 200 with a 14,615-byte page titled "Under Maintenance" — the
same page for a section already committed — so `fetch_fixture.py` recorded
seven successes that were nothing of the kind. All seven were deleted
unread; `docs/NETWORK_ACCESS.md` §15 records it, and a maintenance page is a
fact about the host's evening and not about any section. What the batch
bought without the host: the **Ex-Im Bank's Vice Chair**, a reviewed row on
the section already committed for its President — 12 U.S.C. 635a(c)(1) seats
"the First Vice President who shall serve as Vice Chairman" on the Board, and
§5315 places the "First Vice President of the Export-Import Bank of
Washington" at Level IV (reviewed rows **75 → 76**, Schedule-priced
**214 → 215**); and the **Court of International Trade** from Schedule 7
(above). The rest of the batch is 230-odd committee chairs and ranking
members the member-seat rule already prices, the staff directors it already
refuses, and leads that name a pay SYSTEM with no document naming the post
(SES bands for deputies and chiefs of staff, NSF's AD-3/AD-4 recruitment
ranges, a DOJ vacancy announcement's GS-15 range, Title 38 for the IHS's
officers), each declined in `CURATION.md` §19.16 for the reason the earlier
batches' copies were. Pay claims **1,099 → 1,102**, unpriced
**3,492 → 3,489**, multi-post nodes priced **39 → 40**. The same evening the
seven sections were retried and the host was still under maintenance; the
special trial judges' section came from govinfo instead and the
percentage-of-a-join shape was decided — see "A percentage of a join" above.

**The President's salary, stated by the Code itself (`us_code_stated_pay.py`,
since 2026-10-05, the eleventh research batch).** Every `positionStatutoryPay`
claim came from a document printing a figure beside a TIER or a group of
roles — uscourts.gov's table, senate.gov's footnote, the schedules in 5 U.S.C.
5332's note. **3 U.S.C. 102** is a fourth shape: the section names the office
itself and states the figure in its own operative text, "The President shall
receive in full for his services during the term for which he shall have been
elected compensation in the aggregate amount of $400,000 a year, to be paid
monthly, and in addition an expense allowance of $50,000 …". Read from GPO's
2024-edition rendering on govinfo (the OLRC host was still under maintenance),
through `derived_pay.load_section`, so the digest is recomputed and the
sentence is re-found in the operative text on every run, and the section's
own credit for the 1999 amendment that set the figure (Pub. L. 106–58
§644(a)) is re-found beside it, so "the figure has stood since then" is read
off the page. One reviewed row (`STATED_RATE_ROWS`, keyed by node id, because
the Code says "The President" and the graph "The President of the United
States" and no name rule is loosened to join them), one record, graded
`partial` and `proxy` exactly as the Vice President's Schedule 6 row is, so
the two offices read alike. **The $50,000 is not published**: the same
sentence calls it an expense allowance that reverts to the Treasury when
unused and is not income, the block carries that refusal in words
(`notPublished`), and the gate refuses a block whose figure is anything but
the mirrored $400,000 — the validator alone would pass $50,000, since the
sentence prints it. The block says `statesTheOffice: true`, the panel and the
atlas print "the section names the office itself" instead of the tier
sentence, `pay_documents` words the caution for it, and the gate refuses that
flag on any other source. Source type `us_code_stated_rate` joins the
validator's lists; the gate's `STATUTORY_PAY_SOURCES` and
`STATUTORY_PAY_NODE_TIERS` mirror it; `tests/test_us_code_stated_pay.py`
corrupts each dimension — the allowance filed as the rate, a figure the
section does not print, the block moved onto the Vice President, a foreign
host, the flag on a Schedule 6 record. Pay claims **1,110 → 1,111**, unpriced
**3,481 → 3,480**; statutory-pay positions **487 → 488**.

The rest of that batch, in `CURATION.md` §19.19: its 130 House committee
chairs and ranking members were checked by id and every one already carries
the member-seat record (the batch's new citation, the House Ethics
Committee's 2026 pay memo, would be a second document for a figure Schedule 6
already states, and changes no claim); NSF's AD-5 recruitment band stays
declined (§19.14); the VA's `Deputy Under Secretary — Community Care` and
`Principal Deputy Under Secretary for Health` stay unpriced because Table 4
Tier 1 prints "Deputy Under Secretary for Health" as a whole item and
neither node's name is that item (and the PDF's text runs split the words,
"Deput y Under Secretary", a reconstruction artefact `va_title38_pay.py` does
not repair); the USPS area vice presidents and the VISN CFOs name no
document.

**The panel's Trace Origin, restored.** A 2026-09-15 change reduced "Trace
Origin" to a one-line confirmation on the grounds that the breadcrumb already
showed the path. The owner wanted the full tree back: `renderOriginTrace` lists
every step from the root to the node again, each row a keyboard-reachable
button that selects that node, with the count and the glow-path confirmation
beneath it.

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
Executive Schedule level is. It refused every node that states a
multiplicity (351 circuit- and district-judge nodes) until 2026-09-23, when
`classify_seat` began pricing the eight Associate Justices and a district's or
circuit's own active bench (17 nodes priced from the table now); of the nodes
stating a multiplicity it still refuses the 15 that name senior judges, and it
still refuses the specialized
Article I courts (Tax Court, CFC, CIT, CAAF, CAVC — a different statutory
basis this module has not read a source for; four of those bases were read on
2026-09-23 and `derived_pay.py` prices those courts' chief judges from them in
a field of its own, which does not change what THIS table says), and one node
the multi-post
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
own identity catches it. `withdraw_pay_from_multi_post_nodes` used to strip all
three pay fields in one sweep; since 2026-09-23 the rule is per field (see
"A rate that holds for every holder" above) and a tier rate is KEPT on a bench
node with a `holders` block, while an incumbency-shaped claim is still stripped.
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
undecidable — since 2026-09-23 refused only where the rows differ in rate,
in terms or in printed spelling; see "A rate that holds for every holder"
above); a node outside the `exec-eop-who` subtree, scoped as
`headcounts.py` scopes a FedScope row; a node standing for several posts,
unless (since 2026-09-23) the roster lists the title exactly as many times
as the node's own (×N) states, all at one rate;
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

The gate first mirrored node id → (printed title, printed rate) in
`WHITEHOUSE_REPORTED_PAY` (replaced the same day by the roster read below),
keyed by id for the reason the Senate leadership case established and more
sharply: **four of the five priced posts are paid
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
person (or, since 2026-09-23, by exactly the N a `(×N)` node states, every
one at one rate), and must name this node by equality or with the rank
folded off.
`CURATION.md` §7.4-7.5 record the run and what stays unpriced.

The PLUM archive is the previous administration's reported positions
(the current export from escs.opm.gov landed on 2026-09-21 and is read by
`plum_current.py` as a second document beside it, §12), so every
record and every proposed panel sentence names the archive and its period
and says nothing about who holds a post now: the incumbent columns are
never read. 91 of the graph's 4,382 position nodes matched a listed title
under their own organisation when this was written (129 of 4,591 now); none
matched across organisations.

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
and sends a User-Agent naming the project. It fails open in two cases, and
the first is the opposite of the one this line used to name: a host that
answers that there is no robots.txt (404/410, or any 4xx but 401/403) is
crawled, because nothing was published to obey; the second, since
2026-09-20, is a 401/403 from one of the two hosts
`politeness.STANDARD_4XX_HOSTS` lists (escs.opm.gov, www.nga.mil), where RFC
9309 §2.3.1.3 is followed as written. Every other non-2xx refuses — 401/403
by this project's choice, 5xx and a DNS/TLS/timeout failure because RFC 9309
§2.3.1.4 makes an undefined robots.txt a complete disallow. "Cannot be fetched at all" is
therefore the case that refuses, not the case that fails open. A host that answers `robots.txt` itself with 401 or 403 is
the one case that looks like "unreadable" but is not treated as such:
`RobotFileParser` swallows that status and sets a blanket disallow with no
rules parsed. Outside those two hosts the path stays refused — by this project's choice, not by the
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
sources: `primary` (`output/graph.min.json`), `base` (the curated file, used
only if the primary is missing or malformed), `corporate` (null: the
committed `data_expansion/corporate_expansion.json` is the template output
of `expand_corporate_nodes.py` — invented positions — not EDGAR officers,
so it is not merged until `extract_and_expand.py` has produced real ones).

- `graphLoader.js` fetches primary/base and candidates, plus the corporate
  and expanded nodes/edges overlays when `GRAPH_DATA_SOURCES` names them
  (all three are null today, so none is fetched), merges the overlays into
  the tree (`safeAddChild` refuses a
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

**Expanding a node drew its edges and not its children (since 2026-09-22).**
Three rules that are each individually right combined into a state where
expanding a node drew almost none of what it expanded. The White House Office
carries 249 children; pressing "Expand All Below" on it put **4 of those 249
on screen**, and what a reader saw was a fan of edges leaving the frame on
every side with nothing at the end of any of them. Measured in a headless
browser at 1400x900, by counting how many of that node's own child ids were
in the drawn set, not reasoned about.

The three: `getSpreadPositions` lays a brood on a shell whose radius is a
function of DEPTH (`shellRadiusForDepth`, plus the crowding bump added the day
before) — 374 units for this one; `focusNode` centres the selection and
deliberately never pulls the camera outward, because a reader who zoomed in
should stay in; and `lodManager.shouldRenderNode` caps drawn depth by a tier
that is a function of camera DISTANCE. So the children were placed far outside
a view the camera was not allowed to widen, and widening it by hand was
exactly what dropped the tier and stopped them being drawn at all.

`frameBroodOf` is the camera half and is called **only from an expansion** —
`btnExpand`, and `expandProgressively` when it was scoped to a node, never
from a depth button and never from plain selection, so the rule `focusNode`
states still governs every other path. Pressing Expand is a request to see the
children, so that one path may pull back. It frames the brood rather than the
parent: `getSpreadPositions` uses a CONE (half-angle 0.42 radians, widening to
0.95 for a large brood), so a camera centred on the parent puts the whole
brood to one side and leaves half the frame empty — the focus point is the
centroid of the parent and its children, and the fit radius the farthest of
them from it. It reads `targetPos` rather than `pos`, since a brood expanded a
frame ago is still animating out of the parent's own position and `pos` would
fit the camera to a sphere of radius nearly zero.

The camera half **alone makes it worse, measurably**: pulling back to hold the
brood took the view from Office View to Branch View and the brood's own drawn
count from 4 to **11 of 249** — the tier that draws those children is exactly
the tier the camera left. Zooming out to see something cannot be the thing
that hides it, so `isNodeRenderableAtCurrentLod` exempts the selected node's
own children from the tier, the way it already exempts the selected node
itself. Bounded to **one brood, never a subtree** — 249 nodes at the worst node
in this graph — so the cost is the selection's child count and not a second
copy of the tree. The two choices a reader makes above the tier still stand:
an explicit depth filter wins (that is a reader saying how deep to go, not the
camera guessing), and the verification toggles decide what may be shown at
all.

Both halves together: **235 of 249**. The remaining fourteen are the
screen-tile density cap doing its job — 249 nodes in one frame is more than
some tiles will hold — and how many it trims depends on where the camera
happens to sit, so the same expansion run at the end of the smoke file's
sequence rather than on its own drew 183. `scripts/frontend_smoke.mjs` expands
that node from the served graph, pins the unverified toggle and the depth
filter first (a toggle left off would correctly withhold most of the brood,
and the exemption is deliberately subordinate to an explicit depth filter),
and asserts that a majority of the brood is drawn. The bar is 60% rather than
90% for the density cap's sake; the state it exists to catch scored 1.6%.

**That 235 was a transient, and the density cap was undoing the fix (found
and fixed 2026-09-30).** The smoke check sampled the drawn set once, six
seconds after the click, and on the slower renderer of that day's sandbox it
flapped: 146, 148 and 153 of 249 on the working tree against a bar of 150,
and 138 on the committed HEAD, so it was not the day's change. Sampling the
same expansion every few seconds instead — with the LOD label and the
"density-hidden" count read off the page beside it — showed what the single
sample had been measuring. The expansion itself finishes in three seconds;
the brood is then admitted as the camera pulls back through Office, Agency
and Branch View (48 drawn at two seconds, 163 at six, 239 at twenty, holding
there to twenty-five); and then, from thirty seconds on, "density-hidden"
climbs 10 → 244 and the brood falls 239 → 26. That is `applyDensityCap`
trimming the brood to `nodesPerTile` at the pulled-back tier — two per tile at
Branch View — once `DENSITY_HOLD_FRAMES` (80 frames, landed 2026-09-21) has
expired, which on a software renderer at a few frames a second takes about
twenty-five seconds and in a real browser at 60 frames a second takes just
over one. So the 235 measured on 2026-09-22 sat inside the hold, and what a
reader with a real GPU saw after pressing Expand was the brood appear and
then, a second and a half later, 90% of it vanish — the state the fix
existed to cure, with a delay in front of it.

The exemption `isNodeRenderableAtCurrentLod` already grants the selected
node's own children from the LOD tier is now granted from the density cap
too, in `applyDensityCap`, on the same reasoning and with the same bound:
one brood, never a subtree, and a reader who pressed Expand asked to see
these. The cap's job is the pile a reader did not ask for. And the smoke
check measures the SETTLED state rather than a snapshot: it waits for the
expansion to finish (the button reads "Expand All Below" again), then thirty
seconds for any hold to expire on a renderer of any speed, then polls until
three consecutive samples agree, and prints every sample with its result
under `measurements` so a passing run is a number and not just "ok". On the
old code that check settles at 26 of 249 and fails, which is what it should
have done all along; with the exemption it settled at **249 of 249**, on a
run made while the test suite was contending for the same four cores.

**Labels were de-overlapped against each other and against the page's own
panels against nothing (since 2026-09-22).** `suppressOverlappingLabels` has
always hidden a label that collides with a higher-priority label; nothing
compared one with the chrome drawn over the canvas. The same 1400x900 capture
had "Executive Office of the President (EOP) (430)" sitting on top of the
legend's colour key, two cluster labels sliced off by the right panel's edge,
and a third under the left column's text. `getChromeRects` measures the eight
panels from the DOM once a frame — `getBoundingClientRect`, canvas-relative,
skipping anything not displayed — rather than writing coordinates down: the
left column's width has changed three times this month, with the reading-guide
button, the depth list and the stats block. A label overlapping one is hidden
before the label-against-label pass runs. Geometry is untouched: a cluster
ring that drifts behind the breadcrumb is where the data puts it, and moving
it would be a lie about the scene; only the text the renderer chooses to draw
is suppressed.

**A priced post's salary is its headline figure, and the estimate is one
click away (since 2026-10-05).** The owner reported two things on the same
day: that "the costs of all nodes have been disappearing", and that
positions "still don't have their salaries attached" although the data was
there. Both were checked against the published graphs before anything was
changed. The first is not a data loss: every `graph.json` committed since
2026-09-23 carries the same 159 measured lines, 693 apportioned shares and
4,657 nodes with no figure, and the pay claims climbed 381 → 1,111 across
the same commits. What a visitor sees is the default view the owner chose on
2026-09-09, which withholds all 693 estimates until "Also show estimated
shares of a parent's total" is ticked — and `readStoredPrefs` remembers that
tick per browser, so a new browser or a private window shows the withheld
view again. The default is kept; the control moved: `buildCostBlock` now
draws a "Show the estimate" button beside the sentence that says the figure
is withheld, wired to the same checkbox so the column's box reflects it, and
drawn only where `hasWithheldEstimate` is true — a post or a unit beneath a
negative pool has nothing to reveal and gets no button. The second was real
and was the panel's: `costStandInOf` promoted only three of the nine pay
fields to the headline (the current export's rate, the archive's, a table's
range), so a post priced from the Executive Schedule, a statute, the White
House roster or a parity provision read "Not available" and "No cost known
for this node" above a nine-pixel line stating its salary — the President at
"Not available" with $400,000 a year beneath. `PAY_STAND_IN_ORDER` now reads
all nine, in a declared order: a figure a document states for the OFFICE
first (`positionStatutoryPay`, `positionSchedulePay`,
`positionTierReferencePay`, `positionDerivedPay`), then one it states for an
incumbency (the roster's `positionReportedPay`, the current export's rate,
the archive's rate, the table's rate for a listed level), then a range
(`positionGradePay`, `positionTierPay`). Each kind has its own heading —
"PAY — EXECUTIVE SCHEDULE", "PAY — DERIVED, STATED BY NO DOCUMENT", "TITLE
38 PAY RANGE, NOT A RATE" — never the word COST, its own badge ("No cost
known; the statutory rate of pay is shown") and its own sentence saying what
the figure is and is not, with "for each of the N holders" where the block
carries a `holders` stamp. The reading guide's count of posts that show a
salary now uses the same rule, having missed the two Code-supplied fields
and under-counted by a few hundred. `scripts/frontend_smoke.mjs` opens a
statutory, a schedule, a roster and a bench node and asserts each one's
headline is the document's own figure under a PAY heading, that the button
exists only where an estimate is withheld, and that pressing it turns the
column's checkbox on. `scripts/report_cost_coverage.py` is the groundwork
for the standing ask that every node come to carry a figure: it puts every
one of the 5,510 nodes in exactly one class (measured, estimate — committee,
beside a sourced figure, or bare —, salary, unpriced post by the unpriced
report's own reason, negative pool, replaced unit) with the document route
that would move it, writes `docs/COST_COVERAGE.md`, and
`tests/test_cost_coverage.py` asserts the partition and compares the
committed copy byte for byte. The two decisions it surfaces are the owner's,
not a build's: whether the headline may fall back to a sourced non-cost
figure (OMB's completed-year outlays, File A gross outlays, audited net
cost) where the Treasury prints no line, labelled by basis and period as a
salary now is; and whether to read the chambers' own disbursement reports
for the 240 committees, which no Table 5 line can ever name.

**An organisation's sourced figure of another kind is its headline, labelled
by basis (since 2026-10-07, the owner's decision).** The cost-coverage report
named two decisions only the owner could make; this is the first. An
organisation with no measured Treasury cost read "Not available" or a withheld
estimate in its headline while one of three sourced figures sat under its own
heading a few rows below: USAspending File A's gross outlays
(`usaspendingOutlays`), the sum of OMB's account rows for a completed year
(`ombBudget`), Treasury's audited net cost (`auditedNetCost`). The headline now
shows one of them, through the same mechanism that made salaries headlines on
2026-10-05: `costStandInOf` reads `PAY_STAND_IN_ORDER` and, where nothing
there applies, a second declared constant, `SOURCED_FIGURE_STAND_IN_ORDER`,
for an organisation only. A post never takes this path, nor a measured node,
a Treasury accounting line or a replaced unit. A unit beneath a negative
Treasury pool may: it has no estimate, and these figures are about it rather
than apportioned to it. Zero is never a headline; a negative figure is shown
as the source gives it, sign leading.

**The order is the anchor's two coordinates, and the trade between the first
two was measured.** The anchor is net outlays for the current fiscal year to
date. File A is the same year to date and cash, but gross, before offsetting
collections; OMB is the anchor's basis (net of offsetting collections, and in
OMB's words "generally consistent with" the statement) for a completed year;
audited net cost is a completed year and accrual, furthest on both counts. On
the 9 measured nodes that carry both File A and OMB beside their Treasury
line, File A sits a median 7.7% from the measured figure and OMB 18.4% (6 of 9
within 10% against 3 of 9), so the clock wins: File A, then OMB, then audited
net cost. Nine is a small sample; the stated reason is the clock and the
measurement agrees with it.

Each kind has its own heading, never COST — "GROSS OUTLAYS — USASPENDING FILE
A", "OUTLAYS — OMB PUBLIC BUDGET DATABASE", and "AUDITED NET COST — TREASURY
STATEMENT OF NET COST", whose only COST is its publisher's name for the
measure — a period line read off the block ("FY2026 to 2026-09-17, fiscal
year to date — gross, before offsetting collections; not the cost"; "FY2025,
a completed year — the sum of N account rows OMB files under this unit, not a
figure OMB prints, and not the cost"; "FY2025, ended 2025-09-30 — accrual,
not outlays; not the cost"), the hollow dashed badge "No measured cost; a
sourced figure of another kind is shown", and a sentence saying what the
figure measures and how it differs from the Treasury's net outlays — OMB's
own net-of-collections and "generally consistent" sentences quoted, its
"detail below millions is not available" where the block carries it, the
audited block's own `basisNote` verbatim. Where an estimate exists it stays
withheld and the "Show the estimate" button stays beside the new headline.
The directory view mirrors the order (`SOURCED_FIGURE_ORDER` in
`js/atlas.js`), names the row for the measure instead of "Cost", and puts the
figure's source on a row of its own; its formatter is its own
(`formatSourcedFigure`), so the exact Treasury formatter stays reachable from
the measured branch alone, which `tests/test_atlas_view.py` pins.

**Measured on the published graph of 2026-10-07: 72 organisations** are now
headed by a sourced figure — **34 by File A** (27 of them holding a withheld
estimate, 7 beneath a negative Treasury pool), **38 by OMB** (35 and 3; three
of the 38 net below zero — the Federal Retirement Thrift Investment Board,
the Farm Credit Administration and the National Technical Information
Service), and **none by audited net cost**: the one unmeasured organisation
carrying an audited figure, the Development Finance Corporation, also carries
File A, which the order puts first. The 62 that hold an estimate are exactly
`docs/COST_COVERAGE.md`'s "Estimate — with a sourced figure already published
beside it". The provenance line and the "How to read this" card count them as
a group of their own, never as measured, and the card's "have no figure at
all" became "have no cost figure at all", since ten of those now show a
figure of another kind. No pipeline field, no `MINIMAL_GRAPH_FIELDS` entry and
no published number changed; `scripts/frontend_smoke.mjs` opens one node of
each kind the graph has (audited is recorded as skipped while no node is
headed by it), a negative OMB figure, a unit beneath a negative pool and a
measured node carrying an OMB block, and holds the card's count to the served
graph.

**Still true and deliberately not changed: every node is the same size.**
`nodeRadiusForDepth` takes a depth and returns the constant `NODE_RADIUS`, so
the most available visual channel in the scene encodes nothing — the 159
measured nodes are drawn exactly like the 4,657 with no figure. The obvious
encoding is subtree size, and this file already records why that would be
wrong: raw node count is "a compressed, noisy proxy for real size even when
every title in it was independently curated", which is the reason the cost
cascade discounts the administrative stamp rather than trusting depth. Putting
that proxy on the loudest channel in the renderer would make the picture claim
more than the data supports, which is the one thing this project does not do.
Cost cannot be the encoding either: 4,657 nodes have no figure, and of those
that do most are apportioned. Uniform size is the honest default, and it is
recorded here as a decision rather than left looking like an oversight.

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
adds; the depth buttons are a fixed HTML list (1–6, 8, 12) with no idea the
loaded tree is only 8 levels deep (`state.maxDataDepth`, computed from
`__meta`), so the 12 in each of its two rows promised a jump the data cannot
make; and a candidate
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

**Repeated documents are stored once in the viewer copy (since 2026-10-07).**
The rule that `graph.min.json` stay under half of `graph.json` broke the day
three new blocks landed together: the employer block repeats the same three
documents' quotes on each of its 112 posts, about 1.9 KB a node, and with the
committee disbursements beside it the viewer copy came out 16.6 KB over. The
rule was kept and the repetition removed instead: `share_repeated_documents`
moves each distinct `documents` list of a block named in
`SHARED_DOCUMENT_BLOCKS` (only `positionEmployer` today) to the viewer root's
`__sharedDocuments` and leaves `documentsRef` on the block; the panel and the
atlas resolve it. `graph.json` keeps every block whole, which is what the gate
reads. The viewer copy went 9,592,074 → 9,388,678 bytes against a ceiling of
9,575,476; `tests/test_viewer_graph.py` resolves every reference and asserts
the resolved block equals graph.json's, and that no shared list is orphaned.
The margin is about 187 KB, and the biggest remaining repetition is the 461
member-seat blocks inside `positionStatutoryPay` (1.4 MB in all), the next
candidate if the rule trips again.

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
fetches is tracked: `index.html`, `css/atlas.css`, `js/`,
`data/federal_gov_complete_1.json`, `output/graph.min.json` and
`output/candidate_nodes.json`. `.nojekyll` stops Pages running the
content through Jekyll. The favicon is an inline `data:` URI rather than a
file, so no request 404s. Two things load from outside the repo and are
outside its control: Three.js from unpkg and the fonts from Google Fonts —
neither is reachable from the pipeline's own sandbox, so
`scripts/frontend_smoke.mjs` rewrites the Three.js import to a local copy and
that one import is the only thing the smoke check cannot prove.

### Exact-node costs, and what the graph does not claim

`docs/EXACT_NODE_COSTS.md` is the standing answer to "why is most of this
graph an estimate". 172 of 5,510 nodes (3.1%; 139 of 5,402 when this was
first written, 160 until the nine header sums and the AmeriCorps alias of
2026-10-06, 170 until COPS and Ginnie Mae on 2026-10-07) carry a cost a record names for them; those cover **99.0% of
the anchor**, so the apportioned figures
subdivide measured money rather than invent it — which does not make a
subdivision a measurement. **Since 2026-09-09 the site does not show one by
default**, by the owner's decision: a node with no measured cost of its own
shows no figure and says why, and ticking "Also show estimated shares of a
parent's total" opts back in. The exception is a real salary — **1,231** of the
4,591 positions carry a pay claim an official source states (1,196 before the
owner's six decisions of 2026-10-07, 1,193 before the
Code title scan's three rows landed later on 2026-10-06, 1,158 before the
twelfth batch's later clusters landed on the morning of 2026-10-06, 1,111
before its current-export rules and its nineteen rows landed late on
2026-10-05), counted on the
published graph on 2026-10-05 after Schedule 6, the VA's Title 38 bands, the
Article I parity derivations, the per-field multi-post rule, the Federal
Reserve rows, the reviewed rows of the fourth research batch, the six
class-title benches, the tier-reference module, the thirteen reviewed rows
of §19.9's list, the eight candidates of §19.10 and the twenty-two rows that
closed the eighth batch (§19.12), the bankruptcy judges of 2026-09-30 and
that day's counted classes and ninth-batch rows, landed: 18 a figure no
document states (`positionDerivedPay`, four chief judges and their four
benches, the Administrative Office's Director, the Federal Judicial
Center's Director through a chain of two statutes, two bankruptcy
benches at 28 U.S.C. 153(a)'s 92 percent of the district-judge rate,
arithmetic the block carries in the open, and since 2026-10-05 the Tax
Court's special trial judges at 26 U.S.C. 7443A(d)'s 90 percent of a Tax
Court judge's own parity rate and the AO's and FJC's Deputy Directors at 92
percent of a Director paid as a district judge — a percentage of a join, and
since 2026-10-06 the Sentencing Commission's Chair at the circuit-judge rate
by 28 U.S.C. 992(c) and the two magistrate benches at 28 U.S.C. 634(a)'s 92
percent, a ceiling the compensation table's own Explanatory Note states the
Judicial Conference fixed at), 45 a rate a
statute sets by REFERENCE to an Executive Schedule level (`positionTierReferencePay`:
the GAO's two officers, the GPO's two, the IES's Director and three
Commissioners, the FCA Board's Chairman, the Librarian of Congress, since
2026-10-05 the USAGM's Chief Executive Officer and the EAC's and FEC's chairs
and vice chairs from sections read on govinfo, since 2026-10-06 the Architect
of the Capitol, the Chief of the Capitol Police, the GAO's General Counsel
and the NNSA Administrator, and 26
Inspectors General at Level III plus the Act's
3 percent, arithmetic no document prints — 37 published on the night of
2026-10-05, when the current export's office-named-for-the-post rule gave
the GPO's Director and the Treasury's, Commerce's and Energy's Inspectors
General a listed level the table prices, which a figure set by reference
never displaces, 45 the next morning, and 47 later that morning with the
NOAA Administrator from 15 U.S.C. 1503b and the Archivist from 44 U.S.C.
2103(b)), 22 twelve months of the uniformed
services' MONTHLY basic pay (`positionMilitaryPay`, since 2026-10-06:
Schedule 8 of the pay-adjustment order joined to the statute that fixes a
post's grade, or naming the post in its own footnote — the Joint Chiefs'
Chairman and Vice Chairman, the service chiefs and vice chiefs, the Coast
Guard's Commandant and Vice Commandant, the Chief of the National Guard
Bureau, two combatant commanders and five senior enlisted advisers, the
annual figure arithmetic no document prints), 72 a Title 38 tier BAND rather than a rate (`positionTierPay`), 237 from the
Executive Schedule as 5 U.S.C. §§5312–5316 sets it (98 of them through a
reviewed identification a second statute backs — 12 U.S.C. 241–242 for the
Fed's four, then the FCC's, FTC's, CFTC's, FERC's, NRC's and FMC's chairs
and benches, the IRS, FAA, DHS, OPM, SSA, FEMA, BLM, CIA, CMS, NIST, SBA,
NSF, ONDCP, BLS, Census, CEA, CPSC, FHWA, USPTO, Reclamation, NASA, FTA,
FRA, MARAD, MSHA and OFR principals, the Register of Copyrights, and ten
stamped agency heads from the MSPB to the Export-Import Bank, and since
2026-09-30 the EEOC's, NMB's and NEA's heads, the EEOC's Vice Chairman,
Ginnie Mae's President, the Wage and Hour Administrator, the OMB's
Director, Deputy Director and three office heads, and the PHMSA
Administrator, and since 2026-10-06 the Department of Defense's Chief
Financial Officer as the Under Secretary of Defense (Comptroller), the IRS
Chief Counsel, the NHTSA Administrator and Deputy Administrator and the
FMCSA's and FHWA's Deputy Administrators, and later that morning the FDA's
Commissioner on a title the Code prints with a footnote mark in place of its
full stop; nine of the 75 are benches priced from the Code's "Members,
…" class title for each holder, the CPSC's and SEC's among them since
2026-09-30 — and 40 more as reviewed members of a COUNTED class the Code
places without naming, "Assistant Attorneys General (11)" and seven more,
each on the Code, the table and, for six of the eight classes, the statute
that composes the class), 188 from
the White House
roster (22 of them titles listed N times at one rate), 128 the rate the current PLUM export prints for the one row under the
title (88 before the office-named-for-the-post rule and the rank fold of
2026-10-05), 68 from a listing's level joined to OPM's table (31 before the
same rules supplied more listed levels), 488 statutory (20 from
uscourts.gov and senate.gov, 4 from Schedule 6 of the annual pay-adjustment
order naming the office, 2 from its Schedule 7 since 2026-10-05 — the Court
of International Trade's chief judge and bench, the one judicial tier
uscourts.gov's table does not print — 1 the President's own salary as 3
U.S.C. 102 states it in dollars, since the same night, and since 2026-09-30 the 461 offices Members of
Congress hold — every committee's chair and ranking member, the whips, the
conference and caucus chairs — at Schedule 6's SEAT rate for their chamber,
by the owner's decision and a rule the gate mirrors), and 22 a
base-pay **range** rather than a rate (`positionGradePay`, counted separately
because a range is not a rate and the panel says so; it read 32 until the
current export supplied a printed figure for 14 of them, and a printed figure
beats a band). A node may carry more than one of these, so the per-source
figures sum past 590 — 461 on 2026-09-23 when four Article I chief judges
took a figure NO document states, 488 the same day when the multi-post rule
became per field, 491 with the Federal Reserve's three (`positionDerivedPay`
was 4 and is 8, since each court's bench now takes its own parity provision)
492 once the review corrected the roster lookup (`positionDerivedPay`, a parity provision
joined to the compensation table, publishing its document count and what that
count is worth), 498 on 2026-09-27 with the six reviewed rows, 513 the
same day with the five class-title benches and nine more reviewed rows, 541
on 2026-09-28 with the tier-reference module, 554 the same day with the
thirteen reviewed rows of §19.9's list, 566 with the eight candidates of
§19.10, 588 with the twenty-two rows of §19.12, 590 with the bankruptcy
benches of 2026-09-30, 638 with that day's counted classes and
ninth-batch rows, 1,099 with the Members' offices the same evening, 1,102
on 2026-10-05 with the Court of International Trade's two judge nodes and the
Ex-Im Bank's Vice Chair, 1,105 the same evening with the Tax Court's
special trial judges and the two judicial-support Deputy Directors, 1,110
with the USAGM's CEO and the EAC's and FEC's chairs and vice chairs from the
six sections govinfo served, 1,111 with the President's salary from 3
U.S.C. 102, 1,158 late the same night with the twelfth batch's
current-export rules and its nineteen reviewed and tier-reference rows, and
1,193 on the morning of 2026-10-06 with the batch's later clusters — the
uniformed services, the Defense Comptroller, the legislative-branch officers,
the Sentencing Commission's Chair, the magistrate benches and the
Transportation deputies — and 1,196 later that morning with the Code title
scan's FDA Commissioner, NOAA Administrator and Archivist. Shown in
the cost block under its own heading and never headed COST — and, since the
same night, as the post's headline figure where it has no cost.

That figure read **354** until 2026-09-19 and was wrong: it added up the
*records* each source derives rather than counting the nodes that publish one,
and the archive's 46 pay records yield 30 published `positionPayRate` blocks
because the rest carry a level or grade and no rate. The published count is
what the site shows, so it is the one stated here; it was 310 before the §9
renames, 311 after, 380 once the current export was read, 385 once
Schedule 6 priced the Vice President and the House's three elected leaders,
457 once the VA's Title 38 bands landed, 461 with the derived figures, 488 with
the per-field multi-post rule, 491 with the Federal Reserve rows, 492 after
the review, 498 with the six reviewed rows of 2026-09-27, 513 with that
day's class-title benches and nine more reviewed rows, 541 on 2026-09-28
with the GAO's officers and 26 Inspectors General, 554 the same day with
the thirteen reviewed rows, 566 with the eight candidates, 588 with the
twenty-two rows that closed the eighth batch, 590 with the bankruptcy
benches, 638 with the counted classes and the ninth batch's rows, 1,099
with the offices Members of Congress hold, 1,102 with the Court of
International Trade and the Ex-Im Vice Chair, 1,105 with the special
trial judges and the two Deputy Directors, 1,110 with the five posts the
govinfo sections priced, 1,111 with the President, 1,158 with the
twelfth batch's current-export rules and rows, 1,193 with its later
clusters the next morning, 1,196 with the Code title scan's three rows
later that morning, and 1,231 with the owner's six decisions of 2026-10-07.
The estimates
stay in `graph.json` because the cascade's arithmetic and the gate's
child-sum checks are built on them, so a consumer of the JSON must read
`cost_status`, not `resolved_total_amount` alone. The gate prints both
coverage numbers on every run so "853 nodes with a cost" cannot be read as
853 known costs.

That document also works through **every one of Table 5's 78 section
totals** and says why each does or does not reach a node, so the analysis
need not be redone: worked through on 2026-09-09 against the 2026-07-31
statement, 41 reached one, 17 were Treasury's own funds and groupings, 5
are object-class slices of a DoD total already applied, 9 are intermediate
groupings covering several curated nodes each, and 5 named units the graph
then had no node for (curation, ~$78B). All five — ACF, the Corps of
Engineers, USAID, GSA and the Railroad Retirement Board — were added on
2026-09-19 and carry their measured cost now, as does one of the 17,
Interest on the Public Debt. Exactly one alias was
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
- **Scope.** 40 reporting entities, of which 5 name no unit of government —
  "Total" (the whole government, $7.3tn), "All other entities", "Security
  Assistance Accounts", "Interest on Treasury Securities held by the public",
  "National Railroad Retirement Investment Trust".
  Those are refused by name rather than matched to the nearest node, for the
  reason `headcounts.py` refuses an agency whose whole entry is one other unit:
  aliasing the Total anywhere would publish the government's cost as one
  agency's.

Matching is canonical-key **equality** and there is no alias table, because none
is needed: **34 of the 40 rows reach exactly one node and none reaches two**
(33 until the Development Finance Corporation's rename on 2026-09-21; the
Farm Credit System Insurance Corporation reaches none).
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

**177 organisations carry a figure** (90 agency, 87 bureau), **64 of which
publish no measured cost of their own** (133, 61, 72 and 39 when this landed;
the 28 added on 2026-10-07 came of re-deriving a committed file that had gone
stale against its own code: all 28 are small independent bodies added on
2026-09-21 when the current Plum Book's agency list was reconciled, each
licensed by its name on an official page, and none had been matched against
OMB's rows since). A measure the package carries no row
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
to its node's estimate to the cent.

**The payouts divide the committees' pool, not the chamber's (since
2026-10-08, decided on the owner's delegation).** The owner left this decision
to the repository, and it was taken half-way on purpose. Within one chamber
the payouts are comparable — one statement, one period, one basis — and
subtree size is not evidence of spending at all, so `get_node_weight` now reads
`committeeDisbursements.amount` as a fourth weight class, `disbursements`
(`disbursement_weight`, and `implied_disbursement_weight` for a sibling the
statement does not print), ranked above the uncited curated dollar figures in
`WEIGHT_CLASS_PRIORITY`. `resolve_sibling_weights` uses it only when one
statement printed every weighted sibling for one period
(`disbursement_document_key`: the document's digest and the period's start
and end); a House quarter and a Senate half-year are never compared, and a set
that mixes them falls back to what each sibling would carry without the block.
What it does not touch is the pool: each chamber's committees still take their
share of the chamber by subtree size, so the House's committees hold $1.61bn of
the House's estimate beside $55m for the 435 Representatives' offices — the
distortion that matters most, left in place because fixing it means weighting
the chamber's other groupings (member offices, officers, leadership) by the
same statement, whose member-office organisations are named for the Member,
and this project does not read names. The panel's estimate sentence says the
payouts set how the committees divide their pool and that the pool is still
divided by size.

Measured on the rebuild: 40 committee shares weighted by a payout, the Senate
Appropriations Committee implied at its siblings' rate ($138.8m → $161.0m),
196 descendants moved with them, **nothing outside the two committee groupings
changed** and no cost status changed. The House Agriculture Committee fell from
$88.2m to $56.1m and Budget rose from $18.4m to $39.9m — subtree size had given
the Budget Committee, which has no subcommittees, the smallest share in the House (tied with the China select committee). The gate
(`disbursement_weight_violations`) refuses a payout weight with no block behind
it, two statements or periods in one sibling set, an implied payout with no
reported sibling or beside its own block, a payout weight on a measured figure,
and shares that are not one rate per dollar paid; `tests/test_cost_cascade_units.py`
(`CommitteePayoutWeightTests`) and `tests/test_committee_disbursements.py`
(`PayoutWeightGateTests`) pin both directions.

### Names that state a count

Seven curated groupings state a number in their own name (eight until
"National Laboratories (17)" was renamed on 2026-09-19). Three carry it
("Mission Teams (15)"); four do not — Individual Senator Offices (100)
carries 18, Individual Representative Offices (435) carries 15, District
Offices (68) carries 4, Federal Public Defender Offices (82) carries 7 —
and a reader who expanded one had nothing telling them the rest were
absent. 793 position nodes carry a multiplicity instead (89 exact, 23 a
range, 681 an unstated "×multiple"; 742, 35 and 684 when this was written),
each drawn as one node and none with an apportioned figure: all 793 publish
`unavailable` — 694 as `post_is_not_a_budget_unit` (the post rule, since
2026-09-14), 72 as `unit_superseded`, 27 as `treasury_pool_negative`. `annotate_stated_counts` publishes the name's number
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
were written, 5,402 on 2026-09-18; 5,510 today), each with a harness
that refuses what it cannot adjudicate — and since 2026-09-20 a fourth, phase
1c's `EVIDENCE_TRIAGE_RUNBOOK.md`, which batches with `node_audit.py next`,
records through `nominate.py record` and adds no writer. All four write
**only** to
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
failed, a metric outside `financial_evidence.BASES` (ten names since
2026-09-10, when `COST_METRICS` was widened from the five `net_outlays`,
`audited_net_cost`, `obligations`, `budget_authority`, `basic_pay`), an
identifier with no basis.
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

The standing numbers this work exists to move: 358 of 890 organisations have
no candidate page at all, so the verifier can never reach them; and 172 of
5,510 nodes carry a cost identified for themselves (294 of 807 and 139 of
5,402 when this was written). `nominate.py status --kind
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
most common — answer, not a failure: 4,530 nodes carry no source at all
(4,713 on 2026-09-20).
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
  graph then named "Broadcasting Board of Governors / USAGM", which needed no
  outside source because the curated name stated the two are one unit (renamed
  "U.S. Agency for Global Media" on 2026-09-19, whose key the line now equals).
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
statutory name, and `TREASURY_ROW_ALIASES` carries no row joining the two, so
the statement's line for it ($941.2M on the 2026-08-31 statement) reaches no
node and AmeriCorps publishes an `allocated` share — until 2026-10-06, when
the twelfth batch's Treasury cluster supplied the row (basis: §2's statutory
name, the identification `node_aliases.json` already carries for name
evidence; the line sits in the independent agencies' section where the node
does) and AmeriCorps publishes the statement's $941,240,516.35 as `official`.
The same cluster found the larger gap this section never listed, because it
was not a missing node: nine sub-agencies the statement prints as a header
with lines beneath and no `Total--` line, about $150.7bn, now measured as
the sum of those lines (see "The statement's own lines beneath a header it
totals nowhere" above). The `0.0` this section
used to cite is the `outlay_amount` USAspending's toptier agency list prints for the agency, not
this line's, and zero is never published as a measurement.

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
