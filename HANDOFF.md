# HANDOFF — read this first, then CLAUDE.md

Written 2026-10-12 at the close of a long session. `CLAUDE.md` is the full
record (why every rule exists); this file is the short version of **where
things stand and what to do next**. Where they disagree, the code wins, then
CLAUDE.md.

## State at handoff

- `main` = `claude/serene-darwin-a79mop` = **33dc0eb**, pushed, working tree
  clean. All temporary agent branches and worktrees were deleted (every one
  was already merged into main).
- **Full pass check on 2026-10-12: green.** All 26 `scripts/derive_*_evidence.py`
  re-run from committed fixtures → no change except `readOn` dates; rebuild →
  `graph.json` identical field-for-field except dates; the three generated
  reports byte-identical; gate `PASSED`; suite 2,234 passed / 1 skipped;
  browser smoke `ok: true`. Nothing is stale.
- Treasury anchor: the **2026-08-31** Monthly Treasury Statement
  (`tests/fixtures/mts_table5_2026-08-31.json`). The September statement was
  **not yet published** on 2026-10-12 (API checked directly: no record_date
  ≥ 2026-09-01). Expected ~2026-10-14/15.

## Headline numbers (published graph)

| | |
|---|---|
| Nodes | 5,510 |
| Measured costs (Treasury lines + root) | 172 (cover ~99% of the anchor) |
| Positions | 4,591 — **1,258 priced**, 3,333 unpriced |
| Unpriced by reason | unreached 2,158 · multiplicity 611 · beneath replaced VA units 432 · not federally paid 112 · listed no rate 20 |
| Staff payroll (OPM FedScope, Mar 2025, civilian basic pay) | 178 orgs; top-level $185.1bn for 1.65M civilians |
| Spending by object class (USAspending, FY2025 obligations) | 86 agencies incl. all 15 departments; staff pay (11.x+12.x) $595.0bn of $10.09tn obligations |

Cache stamp: `?v=20261012b` (bump index.html, js/ui.js, js/graph.js together
on any JS change).

## Next actions, in order

1. **September Treasury statement (~Oct 14–15).** It closes FY2026, so every
   measured cost moves (~1/12 up) and estimates shift. Procedure:
   ```bash
   python -c "import sys,json,datetime;sys.path.insert(0,'.');from data_pipeline.crawler import treasury_outlays as t;d=t.fetch_latest_record_date(timeout=60);print(d)"
   # if d == 2026-09-30: fetch rows with t.fetch_rows_for_record_date(d) and write
   # tests/fixtures/mts_table5_2026-09-30.json in the SAME shape as the 08-31 file
   # (keys: api_url, fetched_at, record_date, rows). Keep 08-31 and latest.json untouched.
   python scripts/regenerate_published_graph.py --treasury-rows tests/fixtures/mts_table5_2026-09-30.json
   ```
   Then: regenerate the 3 reports (`report_cost_coverage`, `report_unpriced_positions`,
   `report_research_prompts`), gate, full suite, smoke, update the
   `--treasury-rows` path in `docs/GO.md`, commit, push main + branch.
   Report which measured nodes moved and by how much.
2. **"Committed vs paid out" (owner decision, open).** `spendingByKind` is
   FY2025 *obligations*; summing agencies double-counts intragovernmental
   transfers ($10.1tn vs ~$7tn outlays). If the owner wants cash, show gross
   outlays by class (already in each minor-class row) and/or set it beside the
   Treasury figure.
3. **Payroll gaps.** FedScope's "DEPARTMENT OF THE ARMY/NAVY/AIR FORCE" civilian
   rows match no node (deliberately — civilian dept ≠ uniformed service). Needs
   a curation decision (add civilian-department nodes) before ~$65bn of payroll
   can land.
4. **Still-open curation decisions** (recorded, not taken): re-homing the 432
   VA medical-centre posts (declined until VA publishes centre→VISN mapping,
   CURATION.md §10/§19.23); merging the NEC and Office of Administration
   duplicate director nodes; the Army/Navy/Air Force civilian-department nodes.
5. **Viewer size margin** is ~141 KB (`graph.min.json` must stay under half of
   `graph.json`). Next field added may trip it; the planned fix is to store the
   461 member-seat blocks once (`SHARED_DOCUMENT_BLOCKS`), never to loosen the rule.

## Design system (2026-10-12, three slices, all on main)

Both views now share one look, "Ledger ink", in `css/shell.css` (tokens +
the universe shell) and `css/atlas.css` (the directory on the same tokens):
ground #0A0E14, gold #D4B25A / #EDD27E, the branch hues the data draws,
Playfair for names and headline figures, IBM Plex Sans for reading text,
Plex Mono for numbers and labels, nothing under 12px. The shell is a 60px
top bar (`#topbar`: wordmark, `#search-wrap`, `#view-switcher`, `#stats`),
a 264px left rail (`#left-stack`, now holding `#depth-ctrl` and `#legend`
in its flow), the full-window `#canvas`, and a 400px `#info-panel`. Every
id and class the JS and the smoke check query is unchanged. `ui.js`'s
`renderChildrenList` lists units before posts with a figure per row by the
headline's own rule; `graph.js` paints its badges and clear colour in the
same language. A fourth slice made an expansion legible: the selected
node's children carry name badges (`updateBroodLabels`, 48 at most, thinned
by the overlap pass; type and count beneath, never a figure), everything
outside the selection, its ancestors and its brood is tinted toward the ink
through the instance colour (`refreshFocus`, a selection state, never a data
claim — base colours and sizes are untouched), brood edges draw in the
child's hue, collapsed sibling clusters shrink, dim and keep their badges out
of the brood's screen area, and "Expand All Below" frames the whole subtree
it drew (`frameSubtreeOf`; it reads `visible`, never `culled`, which is last
frame's frustum and left 137 of the White House Office's 249 out of the fit
on the first try). Cache stamp: `?v=20261012b`.

Left deliberately undone: a fiscal-anchor chip in the top bar (the figure
lives in `#data-provenance`, computed from the graph — a static chip would
go stale on the next statement); collapsing the long provenance prose
blocks in the inspector into `<details>` (the smoke check reads them with
`innerText`, so hidden text would fail its assertions until those checks
read `textContent`); and any camera offset for the rail and inspector.
The design canvas the slices were built from is in Hudson's Claude
artifacts ("Bureaucracy — Unified Explorer").

## Non-negotiable rules (short form — CLAUDE.md has the reasons)

- Never claim more than the evidence supports; zero is never published; no
  person's name is ever read, stored or printed.
- Fetch fixtures only via `python scripts/fetch_fixture.py <url> <path under tests/fixtures>`;
  a refusing host is recorded, never worked around; never disable TLS or unset the proxy.
- Never hand-edit `data/federal_gov_complete_1.json`, `data/verification/*`
  or `output/*` — use the sanctioned writers / derive scripts / regenerate.
- Every gate rule pinned by tests in both directions.
- Before push: derive → regenerate → reports → gate → full suite → smoke
  (`CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome node scripts/frontend_smoke.mjs`,
  check the output says `"ok": true`, not just exit code).
- Push: `git push -u origin main`, then `git branch -f claude/serene-darwin-a79mop main && git push -u origin claude/serene-darwin-a79mop`.
- Commit trailer: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and the session line.

## Environment gotchas seen this session

- Disk allowance is tight (~1.5 GB free). Agent worktrees fill it; remove them
  after merging. Run pytest with `-p no:cacheprovider` if the cache write fails.
- Merges between agent branches conflict only in `output/*`: take ours, then
  regenerate — never hand-merge generated JSON.
- `uscode.house.gov` intermittently serves a 200 "Under Maintenance" page;
  delete such fixtures and use govinfo's 2024-edition rendering via its link service.
