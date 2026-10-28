# Next cycle

Generated 2026-10-28 by `python scripts/next_cycle.py` from `output/graph.json`. Do not edit by hand.

## Where the three criteria stand

Open gap = the definition of done is not met. Reach = a recorded reason that more documents could still turn into a source or a figure.

| criterion | open gap | reach | measure |
|---|---|---|---|
| Evidence | **0** | 239 | 645 of 884 current organisations carry a verification method; the rest carry a recorded reason |
| Money | **0** | 19 | 0 bare estimates; 345 explained blanks, 19 of them named in a held document with no licensed figure; 242 committee estimates counted apart |
| Pay | **0** | 2789 | 1258 of 4591 posts priced; reach counts researchable posts that carry a documents-checked blank |

Not measured here: criterion 4(a) (list units, CURATION.md 32.1) and criteria 5-7 (the refresh job, `scripts/update_cycle.py`, which counts only scheduled cycles).

## This cycle: EVIDENCE (reach)

Every open gap is zero, so the definition of done is met for all three. This cycle IMPROVES: it turns a recorded reason into a source or a figure.

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
python scripts/next_cycle.py --record --note "<what moved>"   # logs this measurement, rewrites this file
```

### Rules

- Never hand-edit data/federal_gov_complete_1.json, data/verification/* or output/*.
- Fixtures only through scripts/fetch_fixture.py. Never read, store or print a person's name.
- Stop if the gate or the suite fails. Report the failure; do not route around it.
- If the number this cycle aims at does not fall, the next run prints STOP and asks the owner.

