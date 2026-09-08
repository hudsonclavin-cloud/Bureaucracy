# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repository.
This file was lost in the 2026-08-04 merge and rewritten from the code on
2026-09-02; where it disagrees with older commit messages, the code wins.

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
`costVerificationStatus: unverified` on every allocated node. The period of
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
  a bot challenge). Applies nothing; it is a fact about the network.
- `not_checkable` — the curated name could never be evidence: a count label
  ("Individual Senator Offices (100)", 44 of them) or a name too generic to
  distinguish anything ("Energy", "Defense", 16). Never fetched.

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

**Directories — the government's own lists of itself.** The page method is
near its ceiling: 71 organisations have a page of their own, twelve of the
largest hosts refuse `robots.txt` and are refused in turn, 4,382 positions
and 223 committees are never checked, and 520 edges hang under curated
groupings with no page. `data_pipeline/verification/directories.py` adds
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
current names the graph lacks go to CURATION.md, never fuzzy-matched. A
listed subcommittee is placed under its committee by the list's own
structure (`placementMethod: listed_under_committee_in_senate_committee_list`).
`committee_key` folds the graph's artifacts ("Senate Committee on Select
Committee on Ethics", "Committee on Judiciary") onto the Senate's names
and nothing else. First run: all 20 curated Senate committees listed, 43
subcommittees listed and placed, 27 curated names the Senate no longer
carries. The House Clerk's list could not be fetched from the pipeline's
network (proxy refusal, recorded in the fixtures README); house.gov lists
committees only.
OPM's data landed on 2026-09-08 (`tests/fixtures/opm/`, README there):
FedScope civilian employment by agency and sub-agency for March 2025 and
September 2024 — the official counts the cost cascade's headcount weights
should answer to, where today's `employees` fields are uncited — and the
PLUM archive of the previous administration's reported positions. The
current PLUM export is served by escs.opm.gov, which the pipeline's
egress proxy refuses (CONNECT 403), as it refuses clerk.house.gov,
www.usa.gov, api.sam.gov, data.opm.gov and govinfo.gov; those are facts
about the environment's network policy, recorded in the fixtures'
`.meta.json` files, never worked around.
Next in this line, in order of evidence value: the House Clerk's
committee XML once the host is reachable, OPM's Plum Book for positions, OPM FedScope for the headcounts
the cascade weights by, and SAM.gov's Federal Hierarchy if the owner
obtains a key.

**Headcounts and positions (`headcounts.py`, `positions.py`).** Two more
official sources, derived and audited but **not yet wired into the
exporter**: `data/verification/headcount_evidence.json` (133 records) and
`position_evidence.json` (91) exist, and nothing reads them, so nothing of
this reaches the site yet.

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

The PLUM archive is the previous administration's reported positions
(the current export is on escs.opm.gov, which the proxy refuses), so every
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
(failing open only when it cannot be fetched at all) and sends a User-Agent
naming the project. A host that answers `robots.txt` itself with 401 or 403 is
the one case that looks like "unreadable" but is not treated as such:
`RobotFileParser` swallows that status and sets a blanket disallow with no
rules parsed. The path stays refused — by this project's choice, not by the
standard: RFC 9309 [likely; unverified from this environment] treats 4xx as
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
  not checked against any source", because all 5,170 read as fact and none
  has a citation; the provenance line under the title computed from the
  graph, never hardcoded), depth controls, verification toggles, expand
  batching.

Cache busting is manual: bump the `?v=` query string in `index.html` and in
the imports at the top of `js/ui.js` and `js/graph.js` together after any JS
change, or users run stale modules against new data.

GitHub Pages serves the repository root from `main`. Everything the page
fetches is tracked: `index.html`, `js/`, `data/federal_gov_complete_1.json`,
and the five `output/*.json` files. `.nojekyll` stops Pages running the
content through Jekyll. The favicon is an inline `data:` URI rather than a
file, so no request 404s. Two things load from outside the repo and are
outside its control: Three.js from unpkg and the fonts from Google Fonts —
neither is reachable from the pipeline's own sandbox, so
`scripts/frontend_smoke.mjs` rewrites the Three.js import to a local copy and
that one import is the only thing the smoke check cannot prove.

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
  statement files it. Since the receipts are carried explicitly a line
  always fits inside its own section's total — Federal Student Aid's $76B
  inside Education's $53B net beside the section's receipts — so "fits" is
  no longer the test; "the same section" is. A line from another section
  publishes as external, measured, outside the parent's sum.

## Known base-graph gaps

Table 5 lines whose unit the curated graph has no node for at all, so no alias
can reach them. Adding the nodes is curation work, not pipeline work;
`CURATION.md` carries the proposal (parent, type, candidate page) for each,
plus the AmeriCorps alias case, the Coast Guard duplicate and the cap:

    General Services Administration          Agency for International Development
    Railroad Retirement Board                Administration for Children and Families
    Corps of Engineers                       Administration for Community Living
    Agricultural Marketing Service           Corporation for National and Community Service
    Foreign Agricultural Service             Legal Services Corporation
    Economic Development Administration      Millennium Challenge Corporation
    Federal Housing Finance Agency           Bureau of Consumer Financial Protection
    Institute of Museum and Library Services Corporation for Public Broadcasting

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
