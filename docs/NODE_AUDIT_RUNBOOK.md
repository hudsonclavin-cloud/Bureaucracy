# Node audit runbook

Instructions for an agent auditing every node in the published graph, one at
a time, until all 5,195 are done.

Read this whole file before the first batch. It is the entire brief; there is
no other context you are expected to have.

---

## What you are doing, and what you are not

You are looking at each node and asking whether what the site says about it is
supported by what this repository actually holds. You write down what you
find. **You change nothing else.**

You do **not** edit `data/federal_gov_complete_1.json`. You do not edit
`output/`. You do not edit the evidence files under `data/verification/`. You
do not "fix" a node you think is wrong. Your entire output is lines appended
to `data/audit/node_audit.jsonl` by the `record` command, which is the only
writer.

That separation is not bureaucracy. A previous agent session in this owner's
work deleted 5,165 lines of founding documents while "cleaning up". An audit
that can only append findings cannot do that, however wrong it gets.

**A finding is a proposal for a human curator, not a decision.** Write it so
that a person who has not seen the node can act on it.

---

## The loop

Run this until `status` says nothing remains.

```bash
python scripts/node_audit.py status                          # where you are
python scripts/node_audit.py next --count 25 > /tmp/batch.json
#   ... read the batch, decide, write /tmp/findings.json ...
python scripts/node_audit.py record --file /tmp/findings.json
git add data/audit/node_audit.jsonl && git commit -m "..." && git push
```

**25 nodes per batch. Not 100.** The dossiers are large; a batch you cannot
hold in context is a batch you will start guessing at. If a batch is unusually
heavy (a node with 200 children), do 10.

**Commit after every batch.** The ledger is the only record that survives a
lost session, and re-auditing 400 nodes because nobody pushed is pure waste.

`next` hands you the nodes in tree order and skips anything already in the
ledger, so the loop is resumable with no state of your own. If you are told to
work one branch, pass `--branch <node id>`.

---

## What the harness will not let you do

`record` re-reads every file you cite and **rejects the entire batch** if a
quoted string is not in that file. Not the record — the batch.

This is deliberate and it is aimed at you. Somewhere around the four-hundredth
node you will stop reading and start pattern-matching, and you will write down
a quotation that sounds exactly like what such a file would say. The check
does not care how plausible it is.

Line breaks are forgiven. These files are hard-wrapped, so a
sentence-length quote crosses a newline; the check normalises whitespace on
both sides before comparing. Quote whole sentences — you do not need to
reproduce the wrapping. Nothing else is forgiven: every word must be there,
in order.

When a batch is rejected:

- **Do not** reword the quote until it passes. That is fitting the evidence to
  the claim.
- **Do** go back and read the file. Either the quote is there and you mistyped
  it, or the claim was never supported and belongs at `speculative` with no
  evidence, or it belongs in the bin.

Rules the validator enforces, so you know them up front:

| Rule | Why |
|---|---|
| Every `certain` or `likely` finding carries at least one evidence entry | A confident claim with nothing behind it is the exact failure this project keeps finding in its own history |
| Every quote must appear in the cited file, word for word | See above |
| Cited paths must be under `data/`, `tests/fixtures/`, `output/`, `docs/`, or the two root `.md` files | Anything else is not evidence this site can stand behind |
| Cited URLs must be `.gov` or `.mil` | Same |
| Every check must use its exact vocabulary | So the results can be counted |
| A node already in the ledger is refused | The ledger is append-only; re-auditing needs `--force` and a reason |

---

## The seven checks

Answer all seven for every node, using exactly these values.

**`existence`** — is this a real unit of the federal government under this
name? `confirmed_by_repo_evidence` · `no_evidence_in_repo` ·
`contradicted_by_repo_evidence` · `not_checkable_offline`

**`placement`** — is the parent the tree gives it right?
`confirmed_by_repo_evidence` · `no_evidence_in_repo` ·
`contradicted_by_repo_evidence` · `not_checkable_offline`

**`name_currency`** — is this the name the government uses now?
`current_per_repo_evidence` · `no_evidence_in_repo` · `stale_per_repo_evidence`
· `not_checkable_offline`

**`node_type`** — does `type` describe what this is? `fits` · `wrong` ·
`unclear`

**`description`** — does the prose assert anything the repository's evidence
contradicts? `no_contradiction_found` · `contradicted` · `no_description`

**`cost`** — is the published figure the right kind of number from the right
source? `sound` · `wrong_source` · `wrong_kind` · `no_cost_published`

**`duplication`** — is this the same unit as another node? `distinct` ·
`duplicates_another_node` · `unclear`

### `no_evidence_in_repo` is the honest answer for most nodes

Most of this graph has never been checked against anything. 4,762 of 5,195
nodes carry no source at all. If the dossier's `evidence_records` is empty and
nothing else in it bears on the question, the answer is `no_evidence_in_repo`
— and that is a **complete, correct audit of that node**, not a failure.

Do not reach for `confirmed` because a node is obviously real. You know the
Department of Defense exists; this repository, at that node, may hold nothing
that says so. The check is about the evidence, not about your knowledge.

Use `not_checkable_offline` when the question *could* be settled but only by
fetching something (see **Network** below).

---

## What counts as a finding

A finding is something a curator could act on. Most nodes will have **none** —
an empty `findings: []` beside seven honest checks is a good audit.

Kinds: `stale_name` · `wrong_parent` · `duplicate` · `wrong_type` ·
`description_contradicted` · `cost_source_mismatch` · `not_a_real_unit` ·
`missing_from_official_list` · `count_mismatch` · `other`

Severity: `blocking` (the site is currently saying something false) ·
`correction` (something is wrong but not a false public claim) · `note`
(worth a curator's attention, no error established).

Confidence: `certain` · `likely` · `speculative`. Be honest here. A
`speculative` finding with a clear question in `proposedAction` is more useful
than a `likely` one you cannot support, and it is the only confidence level
that may go without evidence.

### Do not report these

They are already known, already labelled on the site, and reporting them 5,000
times buries the real findings:

- **"The description has no citation."** True of all 5,170. Every panel
  already says "uncited prose — not checked against any source". Only report a
  description that is **contradicted** by evidence in the repo.
- **"The cost is an estimate."** True of 4,885. Already labelled, and since
  2026-09-09 not even shown by default.
- **"This node has no sources."** True of 4,762 — that is what
  `existence: no_evidence_in_repo` records. It is a check, not a finding.
- **"This grouping is editorial rather than official"** for the named
  groupings the graph already flags — `Individual Senator Offices (100)`,
  `District Offices (68)`, and the rest listed under **Names that state a
  count** in `CLAUDE.md`. Already published as such.
- **Anything in `CLAUDE.md`'s "Known base-graph gaps"** — the missing agencies
  are recorded with proposals in `CURATION.md`.

### Do report these

- A node whose name an official list in this repo **carries under a different
  parent**, or does not carry at all when the list is complete (the Senate
  committee list is complete; a department's About page is not).
- Two nodes that are the same unit. `otherNodesWithThisName` in the dossier is
  a hint, not the answer — duplicates usually have *different* names ("U.S.
  Coast Guard" under two parents, an acronym beside a spelled-out name).
- A `type` that misleads: a person's post typed as an office, a fund typed as
  a bureau, an editorial grouping typed as an agency.
- A description asserting a number or a fact that the repository's own
  evidence contradicts — a headcount the FedScope record disagrees with, a
  budget figure the Treasury line disagrees with, a claim about a unit's
  parent that the directory disagrees with.
- A measured cost whose source is the wrong kind of thing for that node.
- A node the evidence suggests was abolished, renamed, or merged.

---

## Reading the dossier

Each node in `next`'s output gives you:

- `name`, `type`, `description`, `ancestors` (nearest parent first),
  `childNames`, `siblingNames`
- `otherNodesWithThisName` — other node ids sharing this exact name
- `cost` — status, amount, basis, and the Treasury row name if any
- `published_claims` — every claim the site currently makes about this node
- `evidence_records` — what each evidence file holds for this node id

`evidence_records` is where the real work is. The four sources:

| Key | What it is | What absence means |
|---|---|---|
| `evidence` | Page-label checks against official sites | Nothing. A page not read says nothing. |
| `directory_evidence` | Federal Register agency directory, **and** the Senate committee list | For the Senate list, **absence is evidence** — it is complete. For the Federal Register, absence means only that the unit does not publish in the Register. |
| `headcount_evidence` | OPM FedScope civilian employment | Absence means unmatched, not zero staff |
| `position_evidence` | OPM PLUM archive of reported positions | Absence means unmatched. The archive is the **previous** administration's and is not complete for career posts. |

Read the `status` and `reason` fields, not just presence. `inconclusive` with
`only_an_ancestor_page_was_read` means **nothing was learned** — it is not a
negative. `not_found` means the unit's own page was read and did not name it,
which is a real negative and worth a finding if it is surprising.

Population traps that have already produced false claims here, so do not
repeat them:

- FedScope counts **Executive-Branch civilians in an active pay status**,
  excluding the Postal Service and the intelligence agencies. It is not the
  same population as the curated `employees` field, which mixes civilians,
  uniformed members and contractors. A gap between them is usually **not** an
  error — the Coast Guard's 55,000 against FedScope's 9,583 is two different
  questions, not a mistake.
- The PLUM archive covers **January 2021 – January 2025**. It says nothing
  about who holds a post now, and its absence proves nothing about a career
  position.
- A Treasury line is **net outlays for a period**, not a budget, not
  obligations, and not audited cost.

---

## Network

Assume you have none. As of 2026-09-09 this environment's egress proxy refuses
`fiscaldata.treasury.gov`, `api.usaspending.gov`, `www.opm.gov`,
`federalregister.gov` and `www.senate.gov` with `403` on the CONNECT — all of
which worked on 2026-09-08. `docs/NETWORK_ACCESS.md` §0 has the detail.

Before your first batch, check once:

```bash
python - <<'PY'
import urllib.request
for h in ["https://www.federalregister.gov/robots.txt", "https://www.opm.gov/robots.txt"]:
    try:
        print("OK  ", urllib.request.urlopen(h, timeout=20).status, h)
    except Exception as e:
        print("FAIL", h, str(e)[:60])
PY
```

**If it fails:** work entirely from `evidence_records`, and use
`not_checkable_offline` wherever a fetch would have settled it. Do not
substitute your own knowledge for a source. You may know a bureau was renamed
in 2023; without a citable source that is `speculative` with the question in
`proposedAction`, never `certain`.

**If it succeeds:** fetch with `python scripts/fetch_fixture.py <url> <path
under tests/fixtures>`, which writes the file and a `.meta.json` with its
sha256 and robots verdict, and on a refusal writes the meta and no file. Then
cite the fixture path. Never quote a page you did not save — an unciteable
fetch is not evidence.

Never disable TLS verification and never unset `HTTPS_PROXY`.

---

## The record format

Write a JSON file with a `records` list. One object per node, all seven
checks, `findings` always present (`[]` when clean):

```json
{"records": [
  {
    "id": "exec-dept-ed-fsa",
    "checks": {
      "existence": "confirmed_by_repo_evidence",
      "placement": "confirmed_by_repo_evidence",
      "name_currency": "no_evidence_in_repo",
      "node_type": "fits",
      "description": "contradicted",
      "cost": "sound",
      "duplication": "distinct"
    },
    "findings": [
      {
        "kind": "description_contradicted",
        "severity": "correction",
        "confidence": "likely",
        "claim": "The description says the office administers about $120B a year; the Treasury line applied to this node reports $76.05B of net outlays for the period.",
        "evidence": [
          {"source": "output/graph.json", "locator": "exec-dept-ed-fsa.desc",
           "quote": "Administers ~$120B in federal student aid annually"}
        ],
        "proposedAction": "Curator: either cite the $120B figure or reword it; the two numbers measure different things and the panel does not say which."
      }
    ]
  }
]}
```

`locator` is free text pointing a human at the right place in the cited file —
a key path, a heading, a line number. It is not validated; the quote is.

---

## Before you stop

Run these and act on what they say:

```bash
python scripts/node_audit.py verify   # every citation still exact
python scripts/node_audit.py report   # what the audit has found
```

`verify` re-reads every citation in the whole ledger. If it fails, a cited
file changed under you: re-read it and correct the record with `--force`.

Then hand back: how many nodes audited, the finding counts by kind and
severity, and the blocking findings in full. If you were stopped partway, say
which node id the next session should resume from — though `next` will work
that out on its own.

Do not summarise the audit as "all clean" if the honest answer is "most nodes
have no evidence either way". That is the actual finding, and it is the one
the project most needs to hear.

---

## What runs after you

You are phase 1a of three. What you record is read by the two that follow, so
a finding you leave vague costs someone else a pass.

**Phase 1b — `docs/SOURCE_NOMINATION_RUNBOOK.md`.** Nominates a page for the
verifier to fetch, for the 611 organisations that have none. Your
`existence: no_evidence_in_repo` verdicts are exactly its work list. Where you
concluded a node is an editorial grouping the government does not name, say so
in a finding: phase 1b can then record `noCandidate` instead of hunting for a
page that cannot exist.

**Phase 2 — `docs/COST_NOMINATION_RUNBOOK.md`.** Proposes which record would
give each node its own cost. It reads your ledger *before* nominating, and
skips any node you marked a duplicate, not a real unit, wrongly parented or
stale-named — because a financial identifier attached to a node that is about
to be merged or moved looks like evidence for the wrong thing.

So three of your finding kinds carry more weight than the rest, because a
later phase acts on them: `duplicate`, `not_a_real_unit`, `wrong_parent`. When
you raise one, make the `claim` specific enough that phase 2 can act on it
without re-deriving your reasoning.

Phase 2 also feeds back. If it learns something about a node's *identity*
while chasing its money, it appends to this same ledger with `--force`. So a
node may be audited twice; that is intended, and `verify` still holds.
