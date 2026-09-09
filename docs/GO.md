# GO

The standing instruction. When the owner says **go**, do what is on this page,
starting at Step 0, until the work is finished or you are stopped.

You will run out of context long before the work is done. That is expected and
planned for: **every step reads its state from disk, so a fresh session picks
up exactly where the last one stopped.** Never try to hold the work in your
head. Never start over.

---

## Step 0 — Orient (every session, takes a minute)

```bash
cd /home/user/Bureaucracy
git status --short && git log --oneline -1
python scripts/node_audit.py status
python scripts/nominate.py status --kind source
python scripts/nominate.py status --kind cost
```

Those four numbers tell you which phase you are in. Then:

- `node_audit` still has nodes remaining → **Phase 1**, below.
- Phase 1 complete, cost nominations at 0 → **Phase 2**.
- Both complete → **Step 3, the handover**.

Check the network once per session, because it decides how much you can do:

```bash
python - <<'PY'
import urllib.request
for h in ("https://www.federalregister.gov/robots.txt", "https://www.opm.gov/robots.txt"):
    try: print("OK  ", urllib.request.urlopen(h, timeout=20).status, h)
    except Exception as e: print("FAIL", h, str(e)[:60])
PY
```

As of 2026-09-09 every `.gov` host is refused by this session's proxy. If that
is still true, the work is unchanged — you nominate rather than fetch. If it
has opened up, see **Step 2**.

---

## Phase 1 — audit and nominate, one node at a time

Read both runbooks before your first batch. They are the actual instructions;
this page is the order to do them in.

- `docs/NODE_AUDIT_RUNBOOK.md` — the seven checks and the finding rules
- `docs/SOURCE_NOMINATION_RUNBOOK.md` — how to nominate a page

**These are one pass, not two.** Each dossier carries what both need, because
reading 5,195 nodes twice to ask two questions about them is waste.

### The loop

```bash
python scripts/node_audit.py next --count 25 --with-sources > /tmp/batch.json
```

For each node in the batch, decide **both** things from the one reading:

1. The seven audit checks and any findings → `/tmp/findings.json`
2. If `source_nomination.eligible` is true, a page to fetch (or an honest
   `noCandidate`) → `/tmp/nominations.json`

`eligible` is false for positions, synthetic lines and anything that already
has a candidate page. Do not nominate for those; the harness will refuse it.

Then record both, verify, and push:

```bash
python scripts/node_audit.py record --file /tmp/findings.json
python scripts/nominate.py record --kind source --file /tmp/nominations.json --run pass1
git add data/audit && git commit -q -m "Audit and nominate: <first id>..<last id>" && git push
```

**Commit after every single batch.** The ledgers are the only thing that
survives a lost session.

### If a batch is rejected

Both harnesses reject the **whole batch** rather than the bad record. Read the
reason and fix the substance. Do not reword a quote until it passes — that is
fitting the evidence to the claim, and it is the exact failure the harness
exists to catch.

### Pace and honesty

25 nodes a batch. Roughly 208 batches. It is long and most of it is
unglamorous: for most nodes the honest answers are `no_evidence_in_repo` and
an empty findings list, and that is a **complete, correct audit** of that
node, not a failure to find something.

Resist two temptations, both of which get stronger the longer you go:

- **Marking things confirmed from your own knowledge.** You know the
  Department of Defense exists. This repository, at that node, may hold
  nothing that says so. The check is about the evidence, not about you.
- **Reporting the known globals.** "The description is uncited" is true of all
  5,170 and is already labelled on every panel. The runbook's *do not report
  these* list is not optional; ignoring it buries the real findings under five
  thousand copies of the same non-finding.

---

## Step 2 — Only if the network opened up

If `.gov` hosts are reachable, do this once, after a decent number of
nominations exist (a few hundred), before moving on:

```bash
python scripts/nominate.py promote --kind source --dry-run   # read this
python scripts/nominate.py promote --kind source             # queue them
python scripts/verify_base_graph.py --dry-run                # what it would fetch
python scripts/verify_base_graph.py                          # fetch and adjudicate
python scripts/regenerate_published_graph.py --treasury-rows tests/fixtures/mts_table5_latest.json
python -m pytest tests/ -q
git add -A && git add -f output/graph.json output/expanded_nodes.json output/pipeline_stats.json
git commit -q -m "Verify nominated pages" && git push
```

The verifier decides what is true; your nominations only decided what it would
look at. **Report how many nominations became confirmations and how many did
not** — the failure rate is the interesting number, because it says how good
agent nomination actually is, and nobody knows that yet.

Also try the one fetch that unlocks 30 more measured figures:

```bash
python scripts/fetch_fixture.py \
  https://www.opm.gov/policy-data-oversight/pay-leave/salaries-wages/salary-tables/26Tables/exec/html/EX.aspx \
  opm/pay/executive_schedule_2026.html
```

If it succeeds, read `tests/fixtures/opm/pay/README.md` — it says exactly what
a parser for that page must be honest about. Do not write the parser against a
page you have not fetched.

---

## Phase 2 — cost nominations

Start only when `node_audit.py status` says nothing remains.

Read `docs/COST_NOMINATION_RUNBOOK.md`. Same loop, same sharding, same
commit-every-batch:

```bash
python scripts/nominate.py next --kind cost --count 25 > /tmp/batch.json
#   ... read each node's phase-1 record before deciding ...
python scripts/nominate.py record --kind cost --file /tmp/proposals.json --run pass2
git add data/audit && git commit -q -m "Cost nominations: <range>" && git push
```

**Phase 2 reads phase 1.** Before nominating for a node:

```bash
grep '"id": "<node id>"' data/audit/node_audit.jsonl | python -m json.tool
```

If the audit called it a duplicate, not a real unit, wrongly parented or
stale-named, do **not** nominate a cost for it — say `noCandidate` and quote
the audit's finding. An identifier on a node about to be merged or moved looks
like evidence for the wrong thing.

If chasing a node's money teaches you something about its *identity*, that
goes back into the audit ledger:

```bash
python scripts/node_audit.py record --file /tmp/correction.json --force
```

---

## Step 3 — The handover

When both phases are done:

```bash
python scripts/node_audit.py verify        # every citation still exact
python scripts/node_audit.py report
python scripts/nominate.py report --kind source
python scripts/nominate.py report --kind cost
python -m pytest tests/ -q
python scripts/validate_published_graph.py
```

Then write the owner a summary that leads with the truth rather than the
volume:

- how many nodes audited, and how many had **nothing to report** (this will be
  most of them, and that is the honest headline);
- the blocking findings **in full** — these are places the site is currently
  saying something false;
- the `duplicate`, `not_a_real_unit` and `wrong_parent` findings, which are
  curation work for a human;
- how many pages were nominated, and — stated plainly — that **none of them is
  evidence until the verifier reads the page**;
- how many cost identifiers were proposed, and that **none of them is a
  published figure**;
- what you could not do, and why.

Never report nominations as verifications, or proposed identifiers as costs.
The number that matters is not how much you produced; it is how much of it a
machine has confirmed.

---

## Standing rules, which override anything above

1. **Never edit `data/federal_gov_complete_1.json`.** Curation is the owner's
   call. If a node is wrong, that is a finding.
2. **Never edit `output/` by hand.** It is generated. If it needs to change,
   regenerate it and let the gate check it.
3. **Never edit files under `data/verification/` by hand.** The verifier writes
   those. `nominate.py promote` is the one sanctioned exception and it writes
   only the fetch queue.
4. **Push to `claude/bureaucracy-code-review-h3o89b` and nowhere else.** Do not
   open a pull request unless the owner asks.
5. **`python -m pytest tests/` and `python scripts/validate_published_graph.py`
   must both pass before any push that touches code or `output/`.** A batch
   that only appends to `data/audit/` cannot break either, so commit those
   freely.
6. **Never disable TLS verification. Never unset `HTTPS_PROXY`.** A blocked
   host is a fact to record, not an obstacle to route around.
7. **If you find yourself inventing a citation, a URL, or a number to get past
   a validator, stop and say so.** Every harness here is built on the
   assumption that you will be tempted to, somewhere past the four-hundredth
   node. Being the one to report it is worth more than the batch.

---

## If something is genuinely blocked

Say what is blocked, what you tried, and what the next session would need —
then keep working on whatever is not blocked. There are 5,195 nodes; almost
nothing blocks all of them at once.
