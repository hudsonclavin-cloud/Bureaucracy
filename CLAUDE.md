# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Goal

A browsable, data-backed 3D organizational graph of the U.S. federal government. Users start at the Constitution and expand outward through branches, departments, agencies, offices, and positions. Each node shows what exists, how it connects, and what it costs.

## Commands

**Run pipeline once:**
```bash
python data_pipeline/run_once.py
```

**Run tests:**
```bash
python -m pytest tests/
```

**Run a single test file:**
```bash
python -m pytest tests/test_build_graph.py -v
```

**Serve frontend locally:**
```bash
python -m http.server 8080
# Open http://localhost:8080/index.html
```

**Expand corporate nodes:**
```bash
python data_expansion/expand_corporate_nodes.py
```

**Key pipeline env vars:**
```bash
PIPELINE_FISCAL_YEAR=2026
PIPELINE_FRONTIER_LIMIT=80
PIPELINE_PROMOTION_THRESHOLD=0.7
PIPELINE_ENRICHMENT_HTTP_LIMIT=50
PIPELINE_HTTP_TIMEOUT=30
PIPELINE_ENABLE_TEMPLATE_LEADERSHIP=1   # off by default
PIPELINE_RUN_ONCE=1                     # for nightly scheduler
```

## Architecture

The project has two halves that communicate only through committed JSON files in `output/`.

### Python Data Pipeline (`data_pipeline/`)

Crawlers (`crawler/`) hit USASpending, Treasury FiscalData, Wikidata SPARQL, Senate LDA, and `.gov` org chart pages. Raw records flow into:

- `processors/candidate_nodes.py` — `CandidateRegistry` normalizes, scores, and deduplicates candidates. Confidence scoring: base 0.4, +0.3 for `.gov` source, +0.2 for Wikidata, +0.2 for multiple source types. Promotion threshold defaults to 0.7.
- `processors/normalize_nodes.py` — `NodeRegistry` deduplicates and merges nodes. `verify_node_sources()` recomputes confidence on every write.
- `processors/normalize_edges.py` — `EdgeRegistry` deduplicates edges across 10 allowed relationship types.
- `processors/enrichment.py` — scrapes official agency pages for leadership, budget links, and relationships.
- `discovery/source_discovery.py` — multi-method discovery: Wikidata scan, advisory committees, org chart scraping, official directories, Federal Register. Outputs candidate nodes to `output/candidate_nodes.json`.
- `exporter/build_graph.py` — assembles the hierarchical tree rooted at `the-constitution-of-the-united-states`, runs `annotate_resolved_costs()` (Treasury-backed cost cascade), validates referential integrity, writes all output files.

`run_pipeline.py` orchestrates all stages. Errors in individual stages are caught and logged in `stage_errors` rather than aborting the run.

### Cost system (in `build_graph.py`)

`annotate_resolved_costs()` assigns `resolved_total_amount` to every node via top-down allocation:
- Root → `cost_status: "root_total"` anchored to Treasury `government_total_outlay_amount`
- Children with `rollup_total_amount` → `"official"` if it matches allocated, `"scaled_official"` if official rollups exceed parent total (rescaled to fit)
- Remaining children → `"allocated"` using employee/budget/subtree-size weighting

### JavaScript Frontend (`js/`)

No bundler, no npm. All ES modules loaded directly by the browser.

`graphLoader.js` fetches four JSON sources in parallel and merges them into one tree:
1. `output/graph.json` (base hierarchy)
2. `data_expansion/corporate_expansion.json`
3. `output/expanded_nodes.json`
4. `output/expanded_edges.json`

`graph.js` renders with Three.js: instanced meshes for nodes, sprite labels, Fibonacci sphere layout for children, 5-level LOD clustering by camera distance, raycasting for selection.

`ui.js` wires all DOM events, manages progressive "Expand All Below" batching (200 nodes/frame), breadcrumb navigation, search, cost rollup display, and verification badges.

VR support: `vrMode.js` (WebXR lifecycle), `vrControls.js` (Quest controller bindings), `vrHud.js` (canvas texture HUD), `vrConfig.js` (constants including `maxVisibleNodes: 8000`).

### Data flow

```
Python pipeline → output/*.json (committed to git)
                            ↓
GitHub Pages serves output/*.json as static assets
                            ↓
graphLoader.js fetches + merges → graph.js renders
```

### Key invariants

- Root node ID is always `the-constitution-of-the-united-states`
- `graph.json`'s top-level `relationships` array and `expanded_edges.json` contain the same non-hierarchical edges (written in the same `build_graph()` call)
- `safeAddChild()` / `safe_attach_child()` enforce cycle-free attachment
- Depth is capped at 20 in both the loader (`MAX_DEPTH`) and renderer
- Cache busting uses version query params on all JS imports (e.g., `?v=20260326h`); bump manually after changes

### Saved snapshots

`saved_pages/` contains self-contained frozen copies of the app + data. Each snapshot has its own `index.html`, `js/`, and `output/` mirror and is fully independent of the live app.
