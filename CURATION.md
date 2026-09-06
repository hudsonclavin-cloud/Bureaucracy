# Curation proposals

Changes to `data/federal_gov_complete_1.json` are the owner's to make; the
pipeline never edits it, and nothing here has been applied. Each item says
what the evidence supports and what it does not. Official URLs listed are
*candidates* for `data/verification/official_sites.json` — a URL there is a
page to fetch, never evidence by itself; the verifier decides.

Standing rule for every proposal below (from CLAUDE.md): a Treasury line is
matched to a node only when the name identifies one line and one node, and
an alias is added to `TREASURY_ROW_ALIASES` only when the line fits inside
its parent's resolved amount. A node can be added without its line ever
being applied; that is still an improvement, because the unit exists and
the site can say so.

## 1. Units the Monthly Treasury Statement reports and the graph lacks

Table 5 prints a line for each of these and no node carries the name, so
no alias can reach the money. Amounts are not in this repository: the last
live statement's per-line figures are printed by
`python scripts/probe_treasury_rows.py --reconcile` in the Treasury
environment, and the table below leaves the column blank rather than quote
a figure nobody in this session read. Placement is the proposal; the
Treasury line names the unit, not its parent.

| Unit, as Table 5 prints it | Proposed parent (id) | Proposed type | FYTD outlays | Candidate official page |
|---|---|---|---|---|
| General Services Administration | `exec-independent` (a peer of NASA, OPM) | Independent Agency | — | https://www.gsa.gov/about-us |
| Agency for International Development | `exec-independent` | Independent Agency | — | https://www.usaid.gov/ |
| Railroad Retirement Board | `exec-ind-misc` | Independent Agency | — | https://www.rrb.gov/ |
| Corps of Engineers | see note (a) | Component Agency | — | https://www.usace.army.mil/About/ |
| Agricultural Marketing Service | `exec-dept-usda` | Component Agency | — | https://www.ams.usda.gov/about-ams |
| Foreign Agricultural Service | `exec-dept-usda` | Component Agency | — | https://www.fas.usda.gov/about-fas |
| Economic Development Administration | `exec-dept-commerce` | Component Agency | — | https://www.eda.gov/about |
| Federal Housing Finance Agency | `exec-regulatory` | Regulatory Agency | — | https://www.fhfa.gov/about |
| Institute of Museum and Library Services | `exec-ind-misc` | Independent Agency | — | https://www.imls.gov/about |
| Administration for Children and Families | `exec-dept-hhs` | Component Agency | — | https://www.acf.hhs.gov/about |
| Administration for Community Living | `exec-dept-hhs` | Component Agency | — | https://acl.gov/about-acl |
| Legal Services Corporation | `exec-ind-misc` | Government Corporation | — | https://www.lsc.gov/about-lsc |
| Millennium Challenge Corporation | `exec-ind-misc` | Government Corporation | — | https://www.mcc.gov/about-us/ |
| Bureau of Consumer Financial Protection | `exec-regulatory` | Regulatory Agency | — | https://www.consumerfinance.gov/about-us/ |
| Corporation for Public Broadcasting | `exec-ind-misc` | Government Corporation (federally chartered, private) | — | see note (b) |
| Corporation for National and Community Service | **not a gap — see §2** | | | |

Notes.

(a) *Corps of Engineers.* Table 5 reports "Corps of Engineers" (the civil
works programme) as its own agency section, outside the Department of
Defense—Military Programs total. Organisationally the Corps is a command of
the Department of the Army. Placing the node under the Army
(`exec-dept-defense-army`, if that is the id) puts a line *outside* DoD's
measured total *inside* it, so the alias rule would leave the line
unmatched; placing it beside the independent agencies matches the
statement's structure and misstates the org chart. This document does not
choose; either placement is defensible if the node's panel says which
structure it follows. If the owner wants the money on the site, the
statement's structure is the one that fits.

(b) *Corporation for Public Broadcasting* is a private nonprofit
corporation chartered by Congress; its site is `cpb.org`, not `.gov`. The
verifier accepts only `.gov`/`.mil` pages as official, by design, so the
node would carry the Treasury line (if it fits) and no existence evidence.
Say so in its description rather than widening the host rule.

(c) *Agency for International Development.* [Likely, unverified in this
environment] the agency was reorganised into the Department of State in
2025. Table 5 still printed the line at the last live run (2026-07-31
data), which is what the pipeline can attest to; the node's description
should not assert a current organisational status the evidence does not
carry.

## 2. Nodes that exist under another name — an alias, not a new node

**Corporation for National and Community Service** is the statutory name
of the unit the graph calls **AmeriCorps** (`exec-ind-misc-americorps`).
This is an alias candidate for `TREASURY_ROW_ALIASES`, not a curation gap.
It is blocked today by the alias rule: its parent, "Other Independent
Agencies (25+)" (`exec-ind-misc`), currently resolves to *no amount at all*
(see §4), so no line fits inside it. Add the alias once §4 is fixed and the
parent carries a positive figure; the earlier attempt to publish this unit
as a fourth child of the root came from the crawler, not from the base
graph, and is the reason `resolve_root_orphans` refuses root attachment.

## 3. One unit, two subtrees: the Coast Guard

`exec-dept-dhs-uscg` (under Homeland Security) and `exec-dept-defense-cg`
(under the Department of Defense "branches" grouping) are both "U.S. Coast
Guard", each with its own Commandant and Master Chief positions. The
Treasury prints one line, "United States Coast Guard", and the pipeline
reports it *ambiguous* rather than pick a copy, so neither node carries
the money ($10.9B at the last live run, per CLAUDE.md). By statute the
Coast Guard sits in DHS except when transferred to the Navy in wartime;
the DoD copy records its status as an armed service. Options, owner's
call:

- Keep one node, under DHS, and give the DoD "branches" grouping a
  cross-reference in its description rather than a duplicate subtree. Then
  the line matches one node — but the alias rule still applies: at the last
  run the $10.9B did not fit inside DHS's resolved amount, so the line
  would stay unmatched until §4/§5 change the cap.
- Keep both and accept that the line is never applied. The site already
  says "ambiguous" honestly.

An earlier session deleted one copy and was reverted; that was the right
reversal — the choice is curatorial.

## 4. Not curation, but found while preparing this: measured lines hidden as "not available"

Six Treasury lines under `exec-ind-misc` publish as `unavailable`
(`allocation_below_precision`): PBGC $1.99B, EEOC $351M, Peace Corps
$336M, NLRB $229M, NEA $124M, NEH $52M — $3.08B measured and shown to
nobody, and not counted in the "$259B withheld" figure either, because
that figure counts only `scaled_official` nodes. The mechanism is in the
cost cascade: the grouping's parent (`exec-independent`) is allocated
$1.550T, which is exactly the measured lines beneath it ($1.615T,
*including* these six) after the branch-wide 96% cap; but inside it the
directly-measured children (SSA $1.445T, OPM, NASA, …) are scaled to fit
first and leave nothing for the weighted siblings, so the six lines two
levels down get a share of zero. The fix — one common haircut for every
measured line beneath a node, direct or deeper — is a pipeline change,
tracked separately from this document.

## 5. The cap itself

Every measured figure beneath a weighted parent is published at ~96% of
what the Treasury reported, all fifteen cabinet departments included,
because Table 5's negative lines (offsetting receipts, intrabudgetary
transactions) are set aside and the positive lines then sum past the net
anchor. Whether to keep capping or to publish true lines and carry the
negatives explicitly is an invariant change and a decision for the owner,
written up separately with the reconciliation numbers.
