# Handoff: apply the Treasury lines

Written 2026-09-03 at the end of a session that could not reach the Treasury
API. Delete this file once the work below is done and committed.

Branch: `claude/bureaucracy-code-review-h3o89b` (16 commits on `a2b2207`,
HEAD `16e7882`). 171 tests pass, `scripts/validate_published_graph.py` is
clean, the tree is clean.

## The one thing left

`output/graph.json` has **zero measured agencies**. The root's total is the
only measured cost in it; all 5,169 other nodes are apportioned estimates.

The Monthly Treasury Statement's Table 5 carries ~640 per-agency outlay
lines, and the exporter already knows what to do with them
(`apply_treasury_outlay_rows`). Nothing has ever run it against the real
statement, because no session so far has been able to reach
`api.fiscaldata.treasury.gov`. `TREASURY_ROW_ALIASES` currently has two
entries, both written from memory of the table rather than from the table.

If you are reading this in a session whose environment allows that host,
that is the work.

## Check you can actually reach it first

```bash
curl -sS -o /dev/null -w '%{http_code}\n' --max-time 20 \
  https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/mts/mts_table_5
```

`200` — go. `000` with `CONNECT tunnel failed, response 403` — the
environment is still on Trusted network access. Stop and say so; do not
work around it, and do not fabricate rows to keep going.

## 1. Look before you write anything

```bash
python scripts/probe_treasury_rows.py --save /tmp/rows.json
```

Read-only: it writes nothing under `output/`, so it is safe to run beside
the published graph. It prints every line under four headings.

- **applied** — the line landed on a node. Read these. A wrong match is the
  expensive failure: it stamps `costVerificationStatus: verified` on the
  wrong unit *and*, because a line acts as a floor, shifts every sibling's
  share. Check each one names the unit you would expect.
- **unmatched** — no node carries that name. Some are real units the graph
  has under a different name (fix with an alias); some are programme,
  interest or offsetting-receipt lines with no organisational home (leave
  them — their amounts stay in the remainder the cascade apportions).
- **ambiguous** — several nodes share the name. Always needs an explicit
  alias to pick one.
- **negative** — net receipts. Set aside by design, nothing to do.

Keep `/tmp/rows.json`. `--rows /tmp/rows.json` re-runs the analysis offline,
so iterate on aliases without re-fetching.

## What to expect (measured against the base graph, 2026-09-03)

I could not fetch the statement, but I could check the graph's half of the
match. Of 23 cabinet departments and major independent agencies checked by
canonical key, **23 matched a single node with no alias needed**
(`Department of Energy` -> `exec-dept-doe`, `Social Security
Administration` -> `exec-ind-ssa`, and so on). So expect most of the large
lines to land on their own.

Five names that appear in Table 5 have **no node at all** in the base graph:

    General Services Administration
    Railroad Retirement Board
    Corps of Engineers
    Other Defense Civil Programs
    International Assistance Programs

No alias can fix those — there is nothing to point at. The first three are
real agencies the curated graph is simply missing, which is a base-graph gap
worth reporting to the user, not something to paper over by inventing nodes.
The last two are Treasury groupings rather than organisations; leaving them
unmatched is correct.

**267 of the graph's 3,221 canonical name keys are claimed by more than one
node.** That is where the ambiguous lines will come from, and where the
alias table will actually earn its keep.

## 2. Fit the aliases

`TREASURY_ROW_ALIASES` in `data_pipeline/exporter/build_graph.py` maps a
**canonical name key** to a **node id**:

```python
TREASURY_ROW_ALIASES = {
    "legislative branch": "legislative-branch",
    "judicial branch": "judicial-branch",
}
```

The key is what `canonical_name_key()` produces: casefolded, parentheticals
stripped, `&` to `and`, punctuation to spaces, `U.S.` to `united states`,
leading article dropped. Compute it rather than guessing:

```bash
python -c "
import sys; sys.path.insert(0,'.')
from data_pipeline.exporter.build_graph import canonical_name_key
print(repr(canonical_name_key('Corps of Engineers--Civil Works')))"
```

Find the node id to point at:

```bash
python -c "
import json,sys
def walk(n,d=0):
    if 'engineers' in n.get('name','').lower(): print(n['id'],'|',n['name'],'|',n.get('type'))
    for c in n.get('children',[]): walk(c,d+1)
walk(json.load(open('data/federal_gov_complete_1.json')))"
```

Rules to hold to:

- Only add an alias when the graph really has that unit. If it does not,
  leaving the line unmatched is the correct outcome — the money stays in the
  parent's apportioned remainder. Do **not** invent a node to catch a line.
- Point at the curated base-graph id, not a crawler twin.
- One line, one node. If two lines would land on the same node, the matcher
  already prefers the `Total--` line; do not add both.
- Re-run the probe after each batch and read the **applied** list again.

## 3. Publish

```bash
python data_pipeline/run_once.py            # exits 1 if it refuses to publish; that is not a bug
python scripts/validate_published_graph.py  # must print PASSED
python -m pytest tests/ -q                  # 171 passing before your change
node scripts/frontend_smoke.mjs --chromium /opt/pw-browsers/chromium-1194/chrome-linux/chrome
```

The gate line to look for is check 2: it should now read
`root + N Treasury line(s)` with N > 0. If it still says `root + 0`, the
rows did not reach the graph — diagnose that before committing anything.

Expect the published costs to move **a lot**. Matched nodes become
`official` floors, and floors are paid before the remainder is apportioned
by weight, so siblings of a matched node all shift. That is the intended
behaviour, not a regression.

Commit the tracked artifacts explicitly (`output/` is gitignored for new
files):

```bash
git add output/graph.json output/expanded_nodes.json output/expanded_edges.json \
        output/candidate_nodes.json output/pipeline_stats.json
```

Never commit `output/audit_report.json`, `output/node_validity_report.json`
or `output/budget_reconciliation.json` — they are untracked diagnostics, and
the audit once grew `pipeline_stats.json` to 16 MB.

## Traps

- **A live run regenerates the review queue.** `output/candidate_nodes.json`
  currently holds 50 records repaired by stated rules
  (`scripts/repair_review_queue.py`). If the discovery hosts are also
  allowlisted, a run rebuilds that file from scratch and the repair is lost.
  Check `git diff --stat output/candidate_nodes.json` before committing; if
  it ballooned, re-run the repair.
- **`pipeline_stats.json` is rewritten even by a refused run.** That is by
  design — the record then says `mode: blocked_run`, `published_artifacts:
  "unchanged"`, and carries a `previous_run` block. Do not commit a
  blocked-run record over a publishing one.
- **The environment's network policy is fixed at session start.** Changing
  it mid-session has no effect; it needs a new session.
- **Do not open a pull request** unless the user asks.

## Standing rule

Never let the data or the UI claim more than the evidence supports. An
unmatched line is honest. A line matched to the wrong unit is not, and is
much harder to notice.
