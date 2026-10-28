# Next cycle

Generated 2026-10-28 by `python scripts/next_cycle.py` from `output/graph.json`. Do not edit by hand.

## Gaps now

| criterion | gap | measure |
|---|---|---|
| Evidence | **247** | 623 of 870 current organisations carry a verification method |
| Money | **360** | bare estimates (no sourced figure of any kind); 240 committee estimates are counted apart |
| Pay | **2789** | positions no pay document reaches, excluding those beneath a replaced unit or off the federal schedule (1258 of 4591 are priced) |

## This cycle: EVIDENCE

Order is the owner's: evidence, then money, then pay.

### Find and verify

1. python scripts/nominate.py status --kind source   # organisations with no candidate page
2. Take a batch of unverified organisations; for each, the Manual, a directory, a committee list or a nominated page (docs/SOURCE_NOMINATION_RUNBOOK.md). A nomination is not evidence until the verifier reads it.
3. python scripts/verify_base_graph.py --dry-run, then without --dry-run (needs the .gov hosts)
4. Where no official document can be read, record the terminal reason (host refuses crawler, no page, no list).

### Place, then prove

1. `python scripts/regenerate_published_graph.py --treasury-rows <the statement named in __budgetSummary.statement_file>`
2. `python scripts/report_cost_coverage.py && python scripts/report_unpriced_positions.py`
3. `python scripts/validate_published_graph.py`
4. `python -m pytest tests/ -q`
5. `node scripts/frontend_smoke.mjs   # only if js/ changed`

### Hand off

```bash
python scripts/next_cycle.py --record --note "<what moved>"   # logs before/after, rewrites this file
```

### Rules

- Never hand-edit data/federal_gov_complete_1.json, data/verification/* or output/*.
- Fixtures only through scripts/fetch_fixture.py. Never read, store or print a person's name.
- Stop if the gate or the suite fails. Report the failure; do not route around it.
- If this cycle moves no gap number, the next run of this script prints STOP and asks the owner.

