# Bureaucracy

A browsable, data-backed 3D organizational graph of the U.S. federal government.
Start at the Constitution and expand outward through branches, departments,
agencies, offices and positions. Each node shows what exists, how it connects,
and what it costs — and says plainly how much of that is measured and how much
is estimated.

Live site: https://hudsonclavin-cloud.github.io/Bureaucracy/

## What the numbers mean

Exactly one figure in the published graph is measured: the root's cost, which
is the U.S. Treasury's fiscal-year-to-date net outlays from the Monthly
Treasury Statement (FiscalData). Every other cost is that total apportioned
downward through the tree. Siblings are split by reported budget where
budgets are reported, by staff count where that is the best evidence, and
by subtree size otherwise; a sibling without the figure its siblings report
is given one implied from their typical per-node rate, and the panel says
so. The site renders those as rounded estimates with an explicit "Estimate"
badge. Only the root — and, once a crawl has run, the agencies the Monthly
Treasury Statement reports outlays for — carry "Measured".
The period the figure covers (for example "FYTD net outlays through
2026-06-30") is printed under every amount.

The hierarchy itself is hand-compiled (`data/federal_gov_complete_1.json`).
Nodes with no source URL attached say "No source recorded" rather than
"unverified" — they were never checked, which is a different claim from
checked-and-failed.

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

# Serve the frontend locally
python -m http.server 8080
# open http://localhost:8080/index.html

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
scripts/validate_published_graph.py   publish-time gate
index.html, js/                       the explorer (vanilla ES modules + Three.js from unpkg, no build step)
tests/                                pytest suite
```

## How a run works

1. Direct crawlers fetch payloads: Treasury FiscalData outlays (the cost
   anchor and the per-agency lines — it runs first), USASpending, Wikidata,
   Senate LDA lobbying.
2. Discovery crawlers (Wikidata, official directories, Federal Register) feed
   `discover_candidates`, which writes the review queue and promotes
   candidates above the confidence threshold.
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
