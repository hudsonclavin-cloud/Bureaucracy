# Bureaucracy — Assessment and Roadmap

Rewritten 2026-09-02. The March assessment this replaces was lost in the
2026-08-04 merge; most of what it listed under "Phase 1" is now done, and
the picture of what the data actually is has changed. Every claim below is
checked against the code and the committed artefacts on the date above.

## Where the project stands

**The structure is hand-compiled and trusted by id.** `data/federal_gov_complete_1.json`
has 5,170 nodes; the published graph is those nodes, gated and annotated.
No crawled node has yet earned publication on its own evidence, so the
site's tree is the curated file. Nothing in the tree carries a source URL,
and the site says so ("No source recorded") rather than calling it
unverified.

**Exactly one figure is measured.** The root's cost is the Treasury's FYTD
net outlays from the Monthly Treasury Statement. Every other cost is that
total apportioned down the tree by one stated rule per sibling set
(reported budget where reported, headcount where that is the best
evidence, subtree size otherwise; a sibling missing the figure its siblings
report is implied at their typical per-node rate, and the panel says so).
The rule is consistent. It is not accurate: an apportioned estimate is an
estimate, and the site labels every one of them.

**The measured figures exist and are now consumed.** The Treasury crawler
returns 642 per-agency outlay lines; as of this generation the exporter
stamps them onto the nodes they name, which makes those nodes `official`
and `verified` with the FiscalData URL as their source. The committed graph
does not show this yet because no crawl has run since the wiring landed
(this environment has no network). The first nightly run with a working
Treasury fetch is the single largest accuracy improvement available.

**Honesty is enforced in three places.** Unit tests pin each gate in both
directions; `scripts/validate_published_graph.py` refuses a graph that
claims more than its evidence supports (and now the review queue beside
it); and the pipeline refuses to overwrite `output/` when its anchor or
every fetch stage is missing.

## What was wrong on 2026-09-02, and is fixed

- The cost cascade summed dollars, headcounts and node counts as one unit
  (IRS $385B beside a Secretary of the Treasury at $32; 120 nodes at $0).
- Every real run rewrote curated names ("Deputy Director / COO" lost its
  slash) and let the copy win over the curated file.
- The Treasury per-agency lines were fetched and discarded.
- The documented entry point exited 0 on a refused publication.
- The publication guard accepted a zero or unparseable Treasury total.
- The served review queue was a March artefact: 1,855 invented positions,
  1,137 foreign bodies, 185 unlabelled items, invented verification dates.
- The renderer drew every curated node as a checked-and-failed ghost and the
  "Show Unverified Nodes" toggle blanked the Constitution.
- The stats bar counted the review queue as published nodes; the corporate
  overlay was template-generated positions merged in as real nodes.
- The three branches never reached their layout triangle; the fiscal year
  was a calendar year to one source and a fiscal year to another.
- README, CLAUDE.md and this file were gone.

## Highest-value next work, in order

1. **Run the pipeline with the network.** `python data_pipeline/run_once.py`
   from a machine that can reach FiscalData. Expected: dozens of agencies
   move from `allocated` to `official`, the gate reports "root + N Treasury
   lines", and `validation.treasury_outlay_rows` lists what did not match.
   Extend `TREASURY_ROW_ALIASES` for the lines it reports unmatched
   (International Assistance Programs, Corps of Engineers, GSA…).
2. **Sub-agency lines by context.** Table 5 lists bureaus under their
   department; a bureau name shared by two departments is skipped today.
   Matching a sub-line within its department's subtree (using
   print order and sequence level) would place most of them.
3. **Budget vs actual.** `processors/budget_reconciliation.py` is wired as of
   this generation and writes `output/budget_reconciliation.json`; it is
   only informative once Treasury lines are on the nodes. Issue #1's
   acceptance criteria are then met except the UI view of variances.
4. **Extract real corporation officers.** `data_expansion/extract_and_expand.py`
   (SEC EDGAR, network) replaces the template overlay; only then set
   `GRAPH_DATA_SOURCES.corporate` in `index.html`.
5. **Source the base graph.** 5,170 nodes with no URL is the largest
   remaining honesty gap. As of 2026-09-03 the machinery exists:
   `scripts/verify_base_graph.py` fetches official pages and records per
   node whether its name is there, and the exporter and gate carry the
   result. What it needs is a network that reaches the 53 hosts
   `--list-hosts` prints. First run: the 63 candidate pages cover the 788
   organisations (one level of inheritance); expect the departments and
   agencies to confirm and many sub-units to come back `not_found` from a
   parent's About page — those need a page of their own in
   `official_sites.json`. Positions (4,382) come after, against their
   unit's leadership page.
6. **Headcount and budget as data, not notes.** The base file's
   `employees` / `budget` strings drive the apportionment. OPM FedScope
   headcounts per agency would replace the hand-typed ones with a sourced
   figure and a date.
7. **Frontend tests.** The explorer has none. `scripts/frontend_smoke.mjs`
   boots the page under Playwright and asserts the honesty-bearing text;
   it needs `playwright-core` and a local copy of Three.js and is not part
   of the pytest suite.

## Known limitations that are deliberate

- The Treasury anchor is year-to-date, and every figure below it inherits
  that period; the panel prints it under each amount. Annualising would be
  a projection, not a measurement.
- A share below one cent is published as unavailable, not $0.
- Template leadership positions are behind `PIPELINE_ENABLE_TEMPLATE_LEADERSHIP`
  and off by default: they are invented, and the queue said so only in a
  `generated://` URL nobody read.
- A candidate whose only source is a single Federal Register notice stays
  in the review queue (0.70 < the 0.7 threshold was never true; it now
  scores below it by construction).
