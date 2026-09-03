# Bureaucracy

A browsable, data-backed 3D organizational graph of the U.S. federal government.
Start at the Constitution and expand outward through branches, departments,
agencies, offices and positions. Each node shows what exists, how it connects,
and what it costs — and says plainly how much of that is measured and how much
is estimated.

Live site: https://hudsonclavin-cloud.github.io/Bureaucracy/

## What the numbers mean

The measured figures in the published graph are the root's cost — the U.S.
Treasury's fiscal-year-to-date net outlays from the Monthly Treasury
Statement (FiscalData) — and the per-agency lines of that statement applied
to the units they name: 103 of the statement's 644 lines, covering the
cabinet departments, the major independent agencies and 60-odd bureaus and
offices beneath them. Every other cost is the total
apportioned downward through the tree, with a Treasury line beneath a unit
acting as a floor on that unit's share. Siblings are split by reported budget where
budgets are reported, by staff count where that is the best evidence, and
by subtree size otherwise; a sibling without the figure its siblings report
is given one implied from their typical per-node rate, and the panel says
so. The site renders those as rounded estimates with an explicit "Estimate"
badge. Only the root and the units the Monthly Treasury Statement names carry
"Measured". A line whose unit the graph does not have, or whose name the
statement gives to several different lines, is left unmatched on purpose: its
money stays in the remainder that is apportioned, which is a smaller claim
than putting it on the wrong unit.
The period the figure covers (for example "FYTD net outlays through
2026-06-30") is printed under every amount.

The hierarchy itself is hand-compiled (`data/federal_gov_complete_1.json`).
Nodes with no source URL attached say "No source recorded" rather than
"unverified" — they were never checked, which is a different claim from
checked-and-failed.

A curated node earns a source one way: `scripts/verify_base_graph.py`
fetches an official `.gov`/`.mil` page on a date and finds the node's name
in its text. The outcome — confirmed, not found, or fetch failed — is
recorded in `data/verification/evidence.json` with the URL, the moment and
the matched text, and the exporter stamps it onto the node at build time.
A confirmed check is a source and a "Last checked" date; a failed check is
the date alone, which the site shows as checked-and-failed. The candidate
pages to fetch live in `data/verification/official_sites.json`; a URL there
is something to check, not a claim.

## Commands

Python 3.9+ and the standard library are enough for the pipeline and its
tests. `data_expansion/extract_and_expand.py` additionally needs `requests`.

```bash
# Run the whole pipeline once (crawl -> discover -> build -> gate -> write output/)
python data_pipeline/run_once.py

# Rebuild the graph from the base graph plus the last published output only
python data_pipeline/exporter/build_graph.py

# Tests
python -m pytest tests/
python -m pytest tests/test_build_graph.py -v

# Publish-time gate: refuses (exit 1) if output/graph.json claims more than
# its evidence supports. Run this before committing a regenerated graph.
python scripts/validate_published_graph.py

# Rebuild output/ without the network (base graph + the published Treasury
# anchor), then run the gate. Use after changing the exporter or the base graph.
python scripts/regenerate_published_graph.py

# Verify curated nodes against official pages (network: the hosts that
# `--list-hosts` prints). Resumable; writes data/verification/evidence.json only.
python scripts/verify_base_graph.py --dry-run
python scripts/verify_base_graph.py

# Which Monthly Treasury Statement lines match a node and which do not.
# Reads and writes nothing in output/; contacts only the FiscalData host.
# Run this before editing TREASURY_ROW_ALIASES.
python scripts/probe_treasury_rows.py
python scripts/probe_treasury_rows.py --save rows.json   # keep the payload
python scripts/probe_treasury_rows.py --rows rows.json   # offline, from a copy

# Serve the frontend locally
python -m http.server 8080
# open http://localhost:8080/index.html

# Frontend smoke check (optional; needs Node plus a local playwright-core and three):
#   npm install --no-save playwright-core three@0.160.1
# (the three version has to match the one js/graph.js imports)
node scripts/frontend_smoke.mjs

# Attempt to extract government-corporation officers from SEC EDGAR (network).
# The committed data_expansion/corporate_expansion.json is NOT that: it is the
# template output of expand_corporate_nodes.py (invented positions), which is
# why index.html does not merge it. Point GRAPH_DATA_SOURCES.corporate at the
# file once it holds extracted officers.
python data_expansion/extract_and_expand.py
```

## Layout

```
data/federal_gov_complete_1.json      hand-curated base graph (5,170 nodes) — the trusted source of structure
data_pipeline/                        Python pipeline (crawlers, processors, discovery, validators, exporter)
data_expansion/corporate_expansion.json  template-generated corporation org chart; not served (see above)
output/graph.json                     the gated, cost-annotated tree the site renders
output/expanded_nodes.json            nodes the crawl added beyond the base graph (empty until one earns publication)
output/expanded_edges.json            non-hierarchical relationships between published nodes
output/candidate_nodes.json           discovery review queue; shown only behind "Show Candidate Nodes"
output/pipeline_stats.json            summary of the last run
output/budget_reconciliation.json     budget notes vs Treasury actuals per organisation (untracked diagnostic)
scripts/validate_published_graph.py   publish-time gate
scripts/regenerate_published_graph.py offline rebuild of output/ (graph, stats, repaired review queue), gated
scripts/repair_review_queue.py        the review-queue repair rules, with a report
scripts/probe_treasury_rows.py        Treasury line -> node match report (read-only diagnostic)
scripts/verify_base_graph.py          fetch official pages, record existence evidence per node
data/verification/official_sites.json candidate official pages per node id (to check, not claims)
data/verification/evidence.json       what the verifier found, per node: URL, time, matched text
scripts/frontend_smoke.mjs            headless-browser check of what the page tells a visitor
ROADMAP.md                            where the project stands and what is worth doing next
index.html, js/                       the explorer (vanilla ES modules + Three.js from unpkg, no build step)
tests/                                pytest suite
```

## How a run works

1. Direct crawlers fetch payloads: Treasury FiscalData outlays (the cost
   anchor and the per-agency lines — it runs first), USASpending, Wikidata,
   Senate LDA lobbying.
2. Discovery crawlers (Wikidata, official directories, Federal Register) feed
   `discover_candidates`; the run promotes candidates above the confidence
   threshold, builds the graph, then writes the review queue without the
   records that were promoted and actually published.
3. `build_graph` merges the previously published graph, the base graph and
   the new payloads; annotates proof and cost; then applies the export gate
   (`NodeRequirements` and `CostValidator`), prunes what fails, and writes
   `output/`.
4. The run refuses to overwrite `output/` when every fetch stage failed or
   when no Treasury budget summary arrived. Without the anchor the cascade
   would assign nothing, the gate would prune everything, and a near-empty
   graph would replace a good one. `run_pipeline.main()` exits nonzero in
   either case.

Pipeline knobs are environment variables; see `CLAUDE.md` for the list.

## Repository size policy

`.gitignore` excludes `output/` from *new* additions, but the JSON files the
site fetches (`output/graph.json`, `expanded_nodes.json`, `expanded_edges.json`,
`candidate_nodes.json`, `pipeline_stats.json`) are tracked because GitHub
Pages serves them as static assets. `output/node_validity_report.json` is a
diagnostic the site never fetches and stays untracked. Do not commit
`pipeline_stats.json` with a per-node audit embedded in it (it grew to 16 MB
once); the summary is what belongs in history.
