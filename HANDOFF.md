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

Cache stamp: `?v=20261020a` (bump index.html, js/ui.js, js/graph.js together
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
6. **The proxy allowlist (owner action).** This session's agent proxy refuses
   every `.gov` host (`scripts/probe_network_access.py`: 327 refused at the
   tunnel). Nothing in CURATION.md §22.1 can be fetched until the owner widens
   it: `python scripts/probe_network_access.py --allowlist` prints the list.
   First fetches once it opens, in order: the Combined Statement FY2025
   chapters (fiscal.treasury.gov), the Senate Report Part I (govinfo), the SES
   career-reserved notice (govinfo), GAO's 2026 pay tables (retry; 403 last time).
7. **Decided 2026-10-20 (yes) and built:** a chamber's disbursement figure is
   the HEADLINE of the 46 committees and House officer offices carrying one
   (fourth in the sourced-figure order, labelled by period; the estimate stays
   withheld behind its button). Cache stamp `?v=20261020b`.

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

**Lenses (2026-10-14, slice 5).** The universe answers four questions,
switched by `#lens-ctrl` in the left rail or keys 1–4 (never while typing):
**Structure** is the branch-hue drawing above, unchanged; **Money**,
**Evidence** and **Pay** recolour every node from one published field,
with a key that says what each colour is (`LENS_LEGENDS` in `ui.js`) and
the brood badges saying the verdict in the panel's own words. Each is one
reader in `graph.js` — `evidenceVerdict` (verificationStatus, with
checked-not-found, host-refused and never-checked told apart as `ui.js`
tells them apart), `payVerdict` (the claim `PAY_STAND_IN_ORDER` would head
the figure with: office-rate, incumbency, a range, not federally paid,
unpriced; a unit is dark, "a unit has no salary"), `moneyVerdict`
(cost_status; an estimate takes a colour only while the estimates box is
ticked, which `ui.js` forwards through `setShowEstimateFigures`) — and the
colour, the badge and the size all draw from that one verdict so they cannot
disagree. Under a lens the batch materials go neutral and the instance
colour carries the verdict (`applyLensMaterials`); Structure restores the
verification profile exactly. **Money is the only lens that changes a
size**, and only for a figure a record states or an estimate the reader
opted into: radius ∝ the fourth root of the figure, clamped 0.7–2.6, the
root untouched; everything else draws at 0.7. Subtree count is never a
size, which CLAUDE.md records as the dishonest proxy. Under Evidence a
hierarchy edge is the placement claim for that edge: bright where
`placementVerified`, dark where the parent has no page, grey where nothing
checked it. The lens is remembered per browser (`lens` in the prefs blob)
and `window.__bureaucracy_lens_verdict__(id)` exposes the verdict so the
smoke check compares the picture with the served graph (one section,
examples picked from the data). Cache stamp: `?v=20261014a`. Orbits, the
fifth concept on the design canvas, was dropped on the owner's decision.
Also fixed in passing: `rowFigure` read "$1.27 billion" as $1, so every
estimate in the inspector's child list printed "$1 ~"; and `frameSubtreeOf`
stamped `lastUserDrillAt`, which let the camera-driven auto-expansion open
nodes outside the subtree for four seconds after "Expand All Below" — on
the Interior, the Council of Economic Advisers' 95-node brood. The smoke's
subtree check compares loaded ids now, not counts, and waits for the
expansion queue to drain before it measures (`__bureaucracy_loaded_node_ids__`,
`__bureaucracy_pending_expansions__`).

**Whole (2026-10-14, slice 6, the owner's ask: "to see how enormous each
branch is").** Key 5. The LOD tiers exist to keep a far camera from
drawing 5,510 dots; this lens is the reader asking for exactly that. It
loads the rest of the tree (`expandProgressively(Infinity)`, a no-op when
loaded), swaps the tier for `WHOLE_LOD` (no depth cap, no clustering, a
density cap that never binds, halos on), draws every node at one SCREEN
size (`WHOLE_NODE_SCALE` × a distance term, so dots do not become balls
when the reader zooms in), colours every node — posts included, 83% of
them — by the branch it sits under (`wholeHue`, cached), fades the 5,510
edges to 0.1, lifts the zoom floor to 0.07 and the far plane to 20,000,
and frames the tree to the stage the rail and the inspector leave
uncovered (`frameWhole`: horizontal fit against the uncovered width, the
focus shifted to its centre). A branch's caption sits at the centre of its
mass (`wholeMassCentres`), not on the branch node beside the root where
the four halos overlapped, and reads "536 units · 3,489 posts in this
graph · $X measured" — `wholeCaption`, counted off the data; the figure
only where a record states one, "≈ … estimate" only when the estimates
box is ticked. The key's note says in words that a mass is this graph's
depth of curation, not the government's size. Whole is never the
remembered lens: a reload comes back to Structure. Two defects fixed on
the way: `refreshFocus` keyed on the selection alone, so slots assigned by
a later expansion kept the mesh's default white under any lens — the
loaded count is in the key now; and `getLabelDistanceScale`'s ceiling of 4
left a far caption unreadable (14 under Whole). Cache stamp:
`?v=20261014b`.

**Presentation readiness (2026-10-14, slice 7).** The owner is showing this
to a class; a pass over what a student clicking around would catch. Camera:
the focus now sits in the UNCOVERED stage — `stageGeometry` reads the rail
and the inspector off the DOM each frame and `stageShift` slides the picture
so a selection is centred between them (it was centred in the canvas, so
every Executive brood, laid down-right, landed under the inspector); the
shift is applied to a copy, never to the lerped `orbitPosition`, because the
first version compounded it twelve-fold through the 8% lerp and the LOD read
the far-off camera as Office View. Selecting a node whose children are
already on the stage frames the brood (`focusNode` → `frameBroodOf`), and
both frame fits use the stage's width. A node nearer the camera than the
focus no longer looms (`nearFactor` in `setNodeMatrix`): a sibling on the
near side of a brood's shell drew as a disc three times its neighbour.
Context cluster rings are half size and dimmer, and a ring's pixel ceiling
fell 92 → 60. Panel: the Executive Branch's estimate (≈$7.15T under a $6.81T
root) now says it is the one unmeasured sibling taking the whole remainder
and names the −$358B receipts line that makes it exceed the parent, where it
said "weighted by staff count" (`soleRemainderNote`); an estimate that a
sourced figure contradicts by more than 3× says so beside it
(`sourcedDisagreementNote` — the EAC's ≈$550M share against OMB's figure);
OMB figures print with the sign leading; zero object-class rows are not
printed; the reading guide has a "Five lenses" point. Known, left as is and
worth saying to the class: the Executive Branch is `partial` (one document,
whitehouse.gov; the Manual has no entry for a branch), "Deputy Secretary of
Department of Commerce" is the one templated title no document in hand
names, the CEA carries two nodes both named "Member, CEA", eight measured
units publish negative net outlays as the Treasury prints them (GSA, TVA,
FDIC, the Mint, the EOP…), and with the estimates box ticked the subtree-size
shares under "Other Independent Agencies (25+)" are identical ≈$0.55B for
units a twentieth of that — the box is off by default and the new caveat
names the sourced figure. Cache stamp `?v=20261014c`.

**The independent establishments, and Whole as a sphere (2026-10-14, slice
8, the owner's ask).** "Independent Establishments & Government
Corporations" swept across the Judiciary's sector as a reader orbited: its
direction (−0.46, −0.68, 0.57) was blended a third of the way toward the
Executive and again toward its anchor, landing it under the Constitution
between the branches. It is now a sector of its own, `independent:
(0.62, −0.28, 0.73)` — out of the branches' plane toward the viewer, on the
Executive's side (straight +z was tried first and projected across the
Constitution from the front) — with the regulatory commissions behind at
−z; a sector root takes almost none of its parent's direction
(`SECTOR_BRANCH_KEYS`). Its 49 units the curated file colours executive red
draw independent green, and the regulatory commissions' two draw orange
(`getNodeColor`, by id prefix; posts keep the grey). Under Whole the tree is
laid out as one sphere (`applyWholeLayout`): an equal-area treemap in
(longitude, height) — a rectangle's area there is its solid angle — split
two ways by leaf count, so each branch and each Executive sector is one
contiguous patch, every leaf on the crust at radius 760, every unit inside
at a radius set by its depth, the Constitution at the centre. The forces
are off while it stands, depth fog sinks the far hemisphere, it turns on its
own until the reader takes hold of it and four seconds after they let go,
captions sit over their own patch and rank branch > sector > root whatever
is selected, and leaving Whole animates every node back to the layout it
had (`restoreWholeLayout`). The smoke check samples leaves by branch and
reads the sector's position back in Structure.

**The globe in relief (2026-10-15, slice 9, the owner's ask: "the radius of
the sphere should be expanded to show the true density of certain
branches").** `WHOLE_SPHERE_RADIUS` 760 → 1,080, so the crust breathes at
the same frame, and the crust is no longer one radius: each of the root's
children takes a factor `1 − WHOLE_RELIEF + WHOLE_RELIEF·√(share)` of its
share of the leaves against the largest branch's (`WHOLE_RELIEF = 0.2`), and
every node beneath it takes its branch's, so the Executive's patch stands at
the full radius and the Judiciary's sits in — the same leaf count the patch
area already carries, shown a second way. Note the honesty limit: an
equal-area treemap puts one leaf per equal patch of crust by construction,
so node density per unit of surface is uniform everywhere; what varies
between branches is patch AREA and now HEIGHT, both this graph's curation
depth, and the lens note and the reading guide say so. The alternative —
equal angular lunes per branch, under which the Executive would read as
crowded — was not built, because it would make a drawing choice look like a
fact about the government. The smoke check samples 48 leaves, groups them by
branch, asserts each branch's leaves sit on one shell (spread < 5) and that
the shells order by leaf count. `docs/RESEARCH_PROMPT_5_DEEP_RESEARCH.md` is
four hand-written deep-research prompts (Perplexity / GPT): cash flow per
branch, verification of unsourced units, verification of unsourced posts,
and a pay document for every unpriced post. The first single-prompt version
was declined by Perplexity for asking coverage counts without the node lists,
so each prompt now names CSVs from `scripts/export_research_pack.py`
(`output/research_pack/`, gitignored) to attach, and forbids estimated
counts; `tests/test_export_research_pack.py` holds the lists to the graph. Cache stamp `?v=20261015a`.

**The fifth research pass, sorted, and the House's officers priced
(2026-10-20).** The owner returned the pass's twelve files; `CURATION.md`
§22 sorts them into documents to fetch once the proxy admits the hosts (the
Combined Statement FY2025, the Senate Report Part I, OPM's career-reserved
SES notice, GAO's pay tables), leads that need a reviewed identification
first, and leads with no usable document (the SF133 workbooks sit behind a
`Disallow: /`; the Congressional Directory prints addresses and no officers;
the pass's "OFFICE OF GENERAL COUNSEL" → Legislative Counsel match was
wrong). The one build the committed documents allowed landed: the House's
Statement of Disbursements prints the House's own officers as organisations,
and `committee_disbursements.py` now prices six of the eight Office nodes
under `leg-house-admin` through `HOUSE_OFFICE_ROWS` (reviewed, re-checked
each run), an office total being the sum of a RUN of programs the module and
the gate both re-add to the cent. The block is the same field marked
`unitKind: house_officer_office`; the validator, the exporter and the gate
each key on the mark and the id. The Parliamentarian is refused by the scale
rule and the Chaplain is printed nowhere. Exactly the eight siblings moved
(the Clerk $34.2m → $14.4m, the SAA $3.8m → $18.9m, the CAO $45.6m →
$52.1m); 46 shares are weighted by a payout, 3 implied; the coverage
report's "with a sourced figure beside" class 62 → 68. Made the headline the
same evening on the owner's "yes" (see Next actions 7). Cache stamp
`?v=20261020b`.

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
- Commit trailer: the `Co-Authored-By: Claude <model> <noreply@anthropic.com>` line the session is given, and the session line.

## Environment gotchas seen this session

- Disk allowance is tight (~1.5 GB free). Agent worktrees fill it; remove them
  after merging. Run pytest with `-p no:cacheprovider` if the cache write fails.
- Merges between agent branches conflict only in `output/*`: take ours, then
  regenerate — never hand-merge generated JSON.
- `uscode.house.gov` intermittently serves a 200 "Under Maintenance" page;
  delete such fixtures and use govinfo's 2024-edition rendering via its link service.
