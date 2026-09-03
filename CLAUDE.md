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
`rollup_total_amount` get `official` (or `scaled_official` if rollups exceed
the parent). Everything else is `allocated`, split among siblings by
`get_node_weight`: the first non-zero of `annual_budget`, `budget`,
`direct_outlay_amount` (basis `*_weight`), else a parseable `employees`
count (`employee_weight`), else subtree size (`subtree_weight`). Weights are
only summed within one unit. When siblings disagree, the best-evidenced
class present wins (dollars, then headcount, then size) and a sibling that
lacks it gets an implied weight: the geometric mean of the reported
siblings' per-node rates times its own subtree size, stamped
`implied_budget_weight` / `implied_employee_weight` (the parent carries
`child_cost_basis_implied`). A share that rounds below one cent is
published as `unavailable` with `cost_validation: allocation_below_precision`,
never as $0. Treasury outlay lines applied to a node make it `official`
(`costVerificationStatus: verified`, the FiscalData URL in `sourceUrls`);
those are the only measured costs besides the root, and the gate checks it.
A line beneath a weighted node is a floor on that node's share (the fifteen
department lines under the unlined "Cabinet" grouping are paid before the
excess is apportioned by weight); only when floors exceed what is left are
they scaled, and the lines beneath publish as `scaled_official`, which the
UI labels an estimate. Negative lines (net receipts) are set aside and
counted, never anchored on.
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
their offices.

Five statuses in `evidence.json`, and only the first two are applied:

- `confirmed` — a fragment is the name. Gives `sourceUrls`, `sourceTypes:
  official_site`, `lastVerified`, and `verificationMethod`, which is
  `name_labelled_on_own_official_page` or `..._parent_official_page` — a
  different claim, and the panel says which.
- `not_found` — the unit's **own** page was read and no fragment named it.
  Gives `lastVerified` + `verificationFailure` only, and only if no other
  route gave the node a source. The site shows checked-and-failed.
- `inconclusive` — only an ancestor's page was read, and a parent's About
  page is not obliged to list its children. Applies nothing.
- `fetch_failed` — no page was read: blocked network, 404, robots.txt
  disallow, a 200 with under 400 characters of readable text (a JS shell or
  a bot challenge). Applies nothing; it is a fact about the network.
- `not_checkable` — the curated name could never be evidence: a count label
  ("Individual Senator Offices (100)", 44 of them) or a name too generic to
  distinguish anything ("Energy", "Defense", 16). Never fetched.

`apply_evidence_to_tree` **clears every field it owns before applying** the
current evidence, so a withdrawn or downgraded record stops being published
even though the exporter re-feeds the previous `graph.json` as a payload; a
retraction that could never reach the site was the second failure the review
found. It runs *after* `apply_treasury_outlay_rows`, which rewrites
`sourceUrls` on the nodes it stamps. `matchedText` is text as it appears on
the page, so a claim can be audited against the live site.

The gate requires: every `lastVerified` a past ISO date; every
`verificationMethod` backed by a URL and one this pipeline can produce; no
node claiming a failed check beside a source; an `official_site` type backed
by a `.gov`/`.mil` URL. Coverage is reported. The verifier obeys `robots.txt`
(failing open only when it cannot be read) and sends a User-Agent naming the
project. Positions are checked only with `--include-positions`.

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
  "No source recorded" state), depth controls, verification toggles, expand
  batching.

Cache busting is manual: bump the `?v=` query string in `index.html` and in
the imports at the top of `js/ui.js` and `js/graph.js` together after any JS
change, or users run stale modules against new data.

## Invariants

- Root id is `the-constitution-of-the-united-states`; it has exactly the
  three branch children.
- Measured costs are the root anchor and the Treasury Table 5 lines applied
  to the nodes they name; nothing else is `verified`. Every amount carries
  a `cost_status` and is positive; a missing amount is labelled
  `unavailable`. Children never sum past their parent. No node has both
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
  candidate to fetch, never evidence by itself.
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
- An alias is added to `TREASURY_ROW_ALIASES` only when the line fits inside
  its parent's resolved amount. A line that does not fit (Office of Federal
  Student Aid at $76B inside a $53B Education total, the Coast Guard's $10.9B
  inside DHS) turns measured siblings into scaled estimates and publishes
  itself below its own line; leaving it unmatched keeps the siblings exact and
  the money in the apportioned remainder.

## Known base-graph gaps

Table 5 lines whose unit the curated graph has no node for at all, so no alias
can reach them. Adding the nodes is curation work, not pipeline work:

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
