# Bureaucracy — Project Assessment & Roadmap

## What It Is

Bureaucracy is a data pipeline + 3D explorer designed to make the U.S. federal government structurally legible — from constitutional roots down to individual offices and positions — with cost attribution and source verification on every node. This is a genuine hard problem: the government has no single authoritative machine-readable org chart, no centralized directory of all entities, and no consistent data model for budget attribution at the sub-agency level.

---

## Key Strengths

1. **The data architecture is sound.** Separation between committed-JSON data (`output/*.json`) and a static-file frontend is elegant. The pipeline evolves independently of the renderer. GitHub Pages serves data as static assets with no server-side infrastructure.

2. **The cost cascade is principled and auditable.** `annotate_resolved_costs()` clearly distinguishes between `root_total` (Treasury-verified), `official` (matched rollup), `scaled_official` (rescaled rollup), and `allocated` (proportional estimate). The cascade is deterministic and the logic is readable.

3. **The pipeline is resilient.** `safe_stage()` wraps every crawler so a single source failing doesn't abort a run. The graph accumulates across runs rather than rebuilding from scratch — it gets more complete over time even with partial crawl coverage.

4. **The 3D renderer handles scale responsibly.** Fibonacci sphere layout, 5-level LOD clustering, instanced meshes, 200-node-per-frame expansion batching, and density caps are all legitimate approaches to rendering tens of thousands of nodes. The VR path via WebXR is a real differentiator.

5. **The verification metadata model is complete.** Every node carries `confidenceScore`, `verificationStatus`, `sourceUrls`, `sourceTypes`, and `sourceCount`. The recompute-on-write pattern in `verify_node_sources()` keeps these consistent.

6. **No build toolchain is a strength for deployment.** Vanilla ES modules, no bundler, no npm. Snapshot pages are fully self-contained frozen copies — the right approach for archival.

---

## Weaknesses and Gaps

### Data Quality

**1. 99.7% of nodes have estimated costs, not official ones.**
From the last full pipeline run: 63 official-cost nodes out of 20,448 total. The Treasury budget cascade is mathematically correct but the signal it distributes is thin. When a user sees a cost for "Office of Congressional Relations, USDA" they're seeing a proportional allocation based on subtree size — not actual spending data.

**2. The budget denominator is FYTD partial-year data.**
The $3.1T Treasury figure is FYTD net outlays through February 28, 2026. Full-year federal spending is roughly $7–8T. Every percentage shown to users ("2.3% of government") is off by approximately a factor of 2.5. This is a significant data truthfulness problem.

**3. Lobbying data is structurally mismatched.**
The Senate LDA lobbying crawler pulls lobbyist-registered organizations — their clients are primarily corporations and trade associations, not government entities. Importing 125+ lobbying client names per run as graph nodes works against the project's mission. Lobbying data is more appropriate for edges ("this entity lobbied that agency") than for new nodes.

**4. The base graph is manually curated and frozen.**
`data/federal_gov_complete_1.json` is the foundation everything is built on. It has no version history, no automated refresh, and no documentation of when it was last verified. If an agency is created, renamed, or abolished (which happens frequently), the base graph won't reflect it.

**5. ID generation from name slugs is fragile.**
`generate_node_id("Department of Defense")` → `"department-of-defense"`, but `generate_node_id("U.S. Department of Defense")` → `"us-department-of-defense"`. These are two different IDs. With multiple crawlers using different canonical names, duplicate nodes accumulate silently. From the pipeline stats: 31,828 raw nodes → 20,448 after dedup — a 36% redundancy rate.

**6. No node expiry or TTL.**
The graph only grows. Nodes added by any crawler are never removed even if subsequent runs fail to find them again. Abolished agencies, renamed departments, and garbage-crawled entities persist indefinitely.

**7. The `pipeline_state.json` is polluted.**
The `entities` field of the pipeline state contained "french-ministry-of-education-academic-vice-rectorate-of-french-polynesia". Frontier state is not validated against US-federal-entity criteria. The 80-URL frontier may include foreign government pages, wasting crawl budget.

### Architecture

**8. No schema validation on pipeline outputs.**
Nothing between `json.dump(export_nodes, ...)` and `fetch(expandedNodesUrl)` in the browser validates structural integrity. A crawler returning a slightly malformed dict can silently inject invalid data. `node_validity_report.json` is post-hoc analysis, not pre-commit validation.

**9. The Wikidata crawler makes two full SPARQL round-trips per run.**
`crawl()` for direct payloads and `crawl_discovery_records()` for the discovery pipeline use identical queries and limits — doubling Wikidata API load for the same data.

**10. Cache busting is manual.**
The `?v=20260326h` version strings in `index.html` JS imports must be hand-bumped. A forgotten bump means users run stale JavaScript against new data. This has already caused "lost fly mode, sidebar, trace node" symptoms.

**11. `load_existing_graph_payload` reads the entire graph on every build.**
At 20K+ nodes this flattens to a 20K-item list every run. Fine today, but will slow proportionally as the graph grows. No incremental update path exists.

### UX

**12. "Allocated" vs "official" is invisible to non-technical users.**
The info panel shows `cost_status: allocated` or `cost_validation: estimated_from_parent`. A citizen exploring the graph has no way to know whether the displayed cost is real government data or a mathematical estimate. This is the most urgent UX problem.

**13. The 3D graph is disorienting at first contact.**
There is no onboarding, no guided path, no "start here" affordance. A first-time user loads the page and sees a sphere of glowing dots with no explanation.

**14. Expanding large subtrees is destructive.**
"Expand All Below" on the Executive Branch attempts to place thousands of nodes simultaneously. Even with 200-node batching, the result is a dense, unnavigable cloud. There's no depth limiter on the info panel and no visual warning about expansion scale.

**15. Node size, color, and label density carry no consistent semantic meaning.**
Node colors are set per-type but verification status and cost confidence don't modulate visual appearance. A completely unverified node looks the same as a Treasury-verified one.

### Data Integrity

**16. FYTD-vs-annualized ambiguity is not surfaced anywhere in the UI.**
The Treasury source URL and `record_date` are stored in `__budgetSummary` but never shown to users. "2.3% of the government" is meaningless if the denominator is a partial year.

**17. `rollup_total_amount` from Wikidata is unreliable.**
Wikidata budget entries are often years old, in a different fiscal year, sourced from Wikipedia which itself cites old appropriations bills. When used as `rollup_total_amount` inputs they produce misleading `official` or `scaled_official` cost status on nodes whose costs aren't actually verified.

**18. No source timestamp per node.**
`lastVerified` exists as a field but is rarely populated. There's no way to tell a user "this node's cost data was last verified in 2024" vs "this was scraped last month."

---

## Highest-Value Next Features

Ranked by impact against the project's core mission:

1. **USASpending TAS/program-level enrichment** — USASpending has award-level spending data broken down by Treasury Account Symbol (TAS), which maps to specific program offices. Linking TAS codes to node IDs would move hundreds of nodes from `allocated` to `official`. Expanding the existing crawler from 20 agencies to full coverage with TAS lookups is the single highest-leverage improvement to cost accuracy.

2. **Cost certainty UI layer** — Replace raw `cost_status` field display with human-readable labels and visual indicators. "Treasury-verified: $4.2B" should look visually different from "Estimated from parent budget: ~$340M." The underlying data is already correct — the UX just needs to surface it.

3. **FYTD budget denominator fix** — Change the root's cost basis from FYTD outlays to full-year appropriations data (OMB budget documents or Treasury annual totals). If FYTD must be used, annualize it (multiply by 12/months elapsed) and label it explicitly. "~$7.5 trillion estimated full-year equivalent" is far more meaningful than "$3.1 trillion FYTD."

4. **OPM/FedScope payroll allocation** — FedScope publishes quarterly headcount and average salary by agency, occupation series, and grade. A single quarterly pull would provide employee-count-weighted cost allocation for every agency with reportable employees — a major improvement over subtree-size weighting.

5. **Source audit trail in the info panel** — Add a "Sources" tab to the info panel showing every source URL that contributed to the current node, what it contributed (name, budget link, edge, verification change), and the date. This is the transparency primitive the project needs to be taken seriously as a reference tool.

6. **Automated snapshot trigger** — After each successful pipeline run, copy the output files to a `saved_pages/YYYYMMDD/` directory with the current `index.html`. This creates a permanent historical record with no extra effort and enables before/after comparisons. Infrastructure for manual snapshots already exists.

7. **Node color/size as trust signal** — Modulate node visual properties by cost certainty and verification status. Nodes with `official` costs and `verified` status should be visually more prominent (larger, brighter) than `allocated`/`unverified` nodes. This turns the 3D view into a trust map, not just a hierarchy map.

8. **Guided entry experience** — Replace the cold launch with a short guided expansion: start at the Constitution, auto-expand to the three branches with cost callouts, pause and let the user choose where to go next. This communicates the core value proposition in 30 seconds.

9. **Lobbying data as edges, not nodes** — Restructure the lobbying crawler to emit edges ("Corporation X lobbied Agency Y, $Z spent in year N") rather than creating lobbying-entity nodes. Preserves the lobbying data's real value (influence mapping) without polluting the hierarchy with non-government entities.

10. **Snapshot diffs** — Show what changed between the last two pipeline runs: new nodes, removed nodes, cost changes, verification changes. This enables temporal transparency and auditing.

---

## Architectural Risks to Address

**Node ID stability** — Before the graph gets much larger, establish a stable ID registry. Maintain a `data/canonical_ids.json` that maps known canonical names to their stable IDs. The `normalize_node` step looks here first before generating a slug from the name.

**Wikidata double-crawl** — Consolidate `crawl()` and `crawl_discovery_records()` into one SPARQL call per pipeline run, sharing the results across both direct and discovery pipelines. This halves Wikidata API load.

**Cache bust automation** — The JS version string should be generated from the current date at HTML build time (a one-line git hook or pre-commit script), not maintained manually.

**Schema contract on outputs** — Add a minimal JSON schema check in `build_graph.py` before writing outputs. At minimum: root ID must be `the-constitution-of-the-united-states`, all node IDs must be strings, no NaN or Infinity in numeric fields. A failed schema check should halt the write rather than publishing corrupt data.

**Pipeline state pollution** — Add a filter in `update_pipeline_state()` that rejects entities whose IDs don't appear in the base graph or whose names match known foreign-entity patterns. The frontier URL list should only include `.gov` and `.mil` domains.

---

## Prioritized Roadmap

### Phase 1 — Trust and Accuracy (immediate)

- [ ] **Cost label translation** — Replace `cost_status: allocated` with human language in the info panel. No data changes needed, pure UI.
- [ ] **FYTD disclaimer and annualized estimate** — Show "FYTD 2026 through February; estimated full-year: ~$X" at the root node and in the budget summary tooltip.
- [ ] **Source freshness field** — Populate `lastVerified` from crawler run timestamps; display it in the info panel.
- [ ] **Pipeline state cleanup** — Remove non-US-federal entities from `pipeline_state.json` entities and frontier targets; add `.gov`/`.mil` domain filter.
- [ ] **Re-run the full pipeline** — Current output is the stripped-down base graph (5,170 nodes post-cleanup). Run `python data_pipeline/run_once.py` to rebuild with all sources now that the Wikidata US filter and orphan attachment fixes are in place.

### Phase 2 — Cost Accuracy (1–4 weeks)

- [ ] **USASpending full-agency TAS enrichment** — Expand the USASpending crawler to pull all top-level agencies with TAS cross-references; link TAS to node IDs to move nodes from `allocated` to `official`.
- [ ] **OPM/FedScope payroll integration** — Pull quarterly FedScope headcount and average pay by agency; replace subtree-size weighting with employee-weighted allocation.
- [ ] **Annualized Treasury denominator** — Replace FYTD raw total with annualized estimate or switch to prior-year final outlays as the cost cascade anchor.
- [ ] **Remove lobbying nodes, convert to edges** — Restructure lobbying crawler output as influence edges rather than hierarchy nodes.
- [ ] **Wikidata crawl consolidation** — Single SPARQL call per pipeline run, results shared across direct and discovery pipelines.

### Phase 3 — UX Clarity (1–2 months)

- [ ] **Node visual trust encoding** — Map verification status and cost certainty to node color intensity and/or size in the 3D renderer.
- [ ] **Source audit panel** — "Sources" tab in the info panel listing all contributing sources with timestamps and contribution type.
- [ ] **Guided first-run experience** — Animated intro expansion from Constitution → branches → top departments with cost callouts.
- [ ] **"Expand to depth N" control** — Add a depth selector to the info panel to prevent unbounded expansion.
- [ ] **Automated snapshot creation** — Hook `run_pipeline.py` to create a `saved_pages/YYYYMMDD/` snapshot on each successful run.
- [ ] **Cache bust automation** — Generate the JS `?v=` query string from the current date at build time via a git hook.

### Phase 4 — Depth and Scale (ongoing)

- [ ] **Node ID stability registry** — `data/canonical_ids.json` with pinned name→ID mappings for top-level entities to survive crawler name variations.
- [ ] **Schema validation on output** — Pre-write validation in `build_graph.py`; halt write on structural violations.
- [ ] **Snapshot diffs** — Show what changed between the last two snapshots: new nodes, removed nodes, cost changes, verification changes.
- [ ] **Time series view** — Compare costs across multiple snapshot runs to surface budget trends.
- [ ] **Federal Register rule → agency mapping** — Extract agency citations from recent Federal Register rules and link them to graph nodes as structural evidence.
- [ ] **Position-level occupancy data** — Match FedScope occupation series and grades to position nodes to model real staffing costs at position level.
- [ ] **Base graph refresh workflow** — Document and automate how `data/federal_gov_complete_1.json` is updated when agencies are created, renamed, or abolished.

---

## Summary Judgment

Bureaucracy is a technically ambitious project with a sound architecture and a genuine mission. The data pipeline is more sophisticated than it looks — cost cascade, confidence scoring, multi-source merging, enrichment, and frontier management are all real work. The 3D renderer handles scale responsibly.

The critical weakness is the gap between what the cost numbers look like and what they actually are. A visitor sees dollar amounts on every node and reasonably assumes those are real government spending figures. Most are not — they are proportional estimates derived from the total Treasury outlay, allocated by subtree size. That gap is the project's biggest trust problem and its most important fix. Close that gap (through better data sourcing, honest UI labeling, and clearer visual differentiation between official and estimated costs) and Bureaucracy becomes a genuinely useful public transparency tool.
