# Source nomination runbook — phase 1b

Instructions for an agent finding a page the verifier can fetch for each
organisation in the graph. Many agents run this at once, on disjoint shards.

Read this whole file before the first batch.

---

## The problem you are solving

`scripts/verify_base_graph.py` earns a node its source by fetching a page and
finding the node's name on it as a label of its own. It works. It is not the
bottleneck.

The bottleneck is that **611 of the graph's 788 organisations have no page to
fetch.** `official_sites.json` holds 177 candidates. For everything else the
verifier has nothing to try, so those nodes can never earn a source however
long it runs.

Naming the right URL is a job you can do and a script cannot. That is the
whole task.

---

## What a nomination is, and what it is not

**A nomination is not a claim.** `official_sites.json` says so in its own
header: *"A URL here is something to check, not evidence."* You are proposing
a fetch. `verify_base_graph.py` reads the page and decides by label equality;
if the name is not there as a heading, link or list item, nothing is
published and your nomination simply came to nothing.

The worst a wrong URL can do is waste one request.

That is why you may nominate from what you know without violating this
project's rule against publishing unsourced claims. You are not publishing
anything. **Do not let that make you sloppy** — a bad nomination costs a
fetch, and fetches are the scarcest thing here — but do not freeze either. A
plausible URL you are unsure of is worth nominating at `speculative`.

**You may never say `certain`.** The harness refuses it. An agent that cannot
read the page cannot be certain it is the right page, and a confidence level
you have no way to earn is one you must not have.

---

## The loop

```bash
python scripts/nominate.py status --kind source
python scripts/nominate.py next --kind source --shard 3/8 --count 25 > /tmp/batch.json
#   ... decide, write /tmp/proposals.json ...
python scripts/nominate.py record --kind source --file /tmp/proposals.json --run agent-3
git add data/audit/nominations && git commit -m "..." && git push
```

**`--shard k/N` is how many of you run at once.** Agent *k* of *N* takes every
*N*th node. The shards are disjoint — nothing is done twice and nothing is
missed. Use the same `k` for your whole run.

**`--run <name>` must be unique to you.** It becomes your own ledger file
(`data/audit/nominations/source-<name>.jsonl`), so N agents never write to the
same file and your branches merge without conflict. Use your shard: `agent-3`.

25 per batch. Commit after every batch.

`next` skips nodes that already have a candidate page, nodes that are not
organisations, and anything already nominated — so the loop is resumable and
you never see the same node twice.

---

## What the harness refuses

| Refusal | Why |
|---|---|
| `http://` | The verifier fetches https. A `.gov` host serving http is still reached over https; the scheme is transport, not a claim. |
| A host that is not `.gov` or `.mil` | The verifier will not fetch it, so nominating it wastes everyone's time. usps.com and si.edu are the real homes of USPS and the Smithsonian — for those say `noCandidate` with reason `not_on_a_gov_host`. |
| `fiscaldata.treasury.gov`, `api.usaspending.gov` | Data services. A record *about* a unit is never the unit's page. |
| `confidence: "certain"` | You cannot read the page. See above. |
| A URL already fetched for this node | The dossier's `urlsAlreadyTried` shows what happened. Nominate a different page, not the one that 404ed. |
| A URL already a candidate for this node | It is already queued. |
| A nomination with no `basis` | Say why you think this is the page. One sentence. |
| A node that is not an organisation | Positions have no page of their own; `next` will not hand you one. |

A rejected batch writes nothing. Fix it and re-run.

---

## Choosing a URL

You get, for each node: its name, type, description, its ancestors **and
their candidate pages**, any Federal Register directory listing, and what the
verifier has already tried.

Three roles, and you may nominate more than one per node:

**`own_site`** — the unit's own homepage or About page. The strongest check:
a confirmation from it publishes `name_labelled_on_own_official_page`.
Prefer the bare homepage (`https://www.nist.gov/`) over a deep link; the name
is more likely to appear as a heading, and deep links rot.

**`parent_listing`** — a page that *should list this unit*, usually the
parent's "bureaus and offices" or "about" page. Weaker, and honestly labelled
as such: it publishes `name_labelled_on_parent_official_page`, which claims
only that the parent's page lists it. Valuable precisely where a unit has no
site of its own, and it is the only thing that can evidence the **edge**.

**`official_list`** — a government directory that enumerates units of this
kind. Use sparingly; the Federal Register and Senate directories are already
wired in.

### Where to look, in order

1. **The dossier's `directoryListing`** — if the Federal Register already
   lists a URL for this unit, that is the best candidate and costs you no
   thinking.
2. **An ancestor's candidate page** — if the parent has one, its
   bureaus/offices/about page is a strong `parent_listing`.
3. **The unit's own domain** where you know it: `nist.gov`, `nhtsa.gov`,
   `cbp.gov`. Many bureaus have one.
4. **A path under the parent's domain**: `https://www.hud.gov/program_offices/public_indian_housing`.
   Guessing deep paths is low-yield — prefer the parent's index page and let
   the label test do the work.

### When to say `noCandidate`

Honest and common. Reasons, exact strings:

- `editorial_grouping` — "Senate Leadership", "Other Independent Agencies
  (25+)", "The Cabinet — Executive Departments". The government does not name
  a body of this kind, so no page will label it.
- `covered_by_parent` — a real unit with no site of its own, where the
  parent's page is the right check and you have nominated it there.
- `no_public_page_known` — a real unit you cannot name a page for. Say what
  you suspect in `note`; an agent with network can try it.
- `not_on_a_gov_host` — USPS, the Smithsonian, the Federal Reserve banks.
- `not_an_organisation` — you should not see these, but if one reaches you.

**Do not invent a URL to avoid saying `noCandidate`.** A wasted fetch is
worse than an honest gap, and there are 611 of these — the ones you skip
honestly are a shorter list for the next pass than a pile of 404s.

---

## The record format

```json
{"records": [
  {
    "id": "exec-dept-doc-nist",
    "nominations": [
      {"url": "https://www.nist.gov/", "role": "own_site",
       "basis": "NIST publishes under its own nist.gov domain; the homepage should carry the institute's name as a heading.",
       "confidence": "likely"},
      {"url": "https://www.commerce.gov/bureaus-and-offices", "role": "parent_listing",
       "basis": "The department's own list of its bureaus should name NIST as a link, which would evidence the edge.",
       "confidence": "likely"}
    ]
  },
  {
    "id": "exec-dept-dot-fmcsa",
    "noCandidate": true,
    "reason": "no_public_page_known",
    "note": "Probably publishes under fmcsa.dot.gov; I cannot confirm the host without fetching."
  }
]}
```

---

## If you have network

Check once, at the start:

```bash
python - <<'PY'
import urllib.request
try:
    print("OK", urllib.request.urlopen("https://www.federalregister.gov/robots.txt", timeout=20).status)
except Exception as e:
    print("FAIL", str(e)[:60])
PY
```

**If it works, your job gets much better**: fetch the parent's page with
`python scripts/fetch_fixture.py <url> <path under tests/fixtures>`, read the
links it actually carries, and nominate the ones it names. That turns a guess
into a reading. Raise nothing above `likely` even so — the verifier still has
to find the label, and that is its call, not yours.

**If it fails**, nominate from what you know and let the fetch happen later.
As of 2026-09-09 every `.gov` host is refused by this session's proxy; see
`docs/NETWORK_ACCESS.md` §0.

Never disable TLS verification, never unset `HTTPS_PROXY`.

---

## What happens to your work

Nothing is published by nominating. When the owner is ready:

```bash
python scripts/nominate.py promote --kind source --dry-run   # what would be queued
python scripts/nominate.py promote --kind source             # write the queue
python scripts/verify_base_graph.py                          # fetch and adjudicate
```

`promote` adds your URLs to `official_sites.json` and records every one in
`official_sites_provenance.json` with your run name, your basis and your
confidence — so a confirmation that later turns out to rest on a bad
nomination can be traced back to it. The verifier then decides.

---

## Before you stop

Run `python scripts/nominate.py report --kind source` and hand back: how many
nodes you nominated, how many pages, the split by role and confidence, and
how many you honestly could not place and why.

Do not report the count of nominations as if it were a count of verified
nodes. You have queued work, not proved anything. The next honest sentence is
"none of these is evidence until the verifier reads the page."
