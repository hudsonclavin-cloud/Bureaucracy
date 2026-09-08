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
no alias can reach the money. Amounts are FYTD net outlays through
2026-07-31, read off `tests/fixtures/mts_table5_latest.json` — the
statement verbatim, committed 2026-09-08. A negative figure is what the
Treasury prints: net receipts exceeded spending (GSA's rents, for one).
Placement is the proposal; the Treasury line names the unit, not its parent.

| Unit, as Table 5 prints it | Proposed parent (id) | Proposed type | FYTD net outlays (2026-07-31) | Candidate official page |
|---|---|---|---|---|
| General Services Administration | `exec-independent` (a peer of NASA, OPM) | Independent Agency | -$836.73M | https://www.gsa.gov/about-us |
| Agency for International Development | `exec-independent` | Independent Agency | $6.33B | https://www.usaid.gov/ |
| Railroad Retirement Board | `exec-ind-misc` | Independent Agency | $3.33B | https://www.rrb.gov/ |
| Corps of Engineers | see note (a) | Component Agency | $9.70B | https://www.usace.army.mil/About/ |
| Agricultural Marketing Service | `exec-dept-usda` | Component Agency | $1.45B | https://www.ams.usda.gov/about-ams |
| Foreign Agricultural Service | `exec-dept-usda` | Component Agency | $1.20B | https://www.fas.usda.gov/about-fas |
| Economic Development Administration | `exec-dept-commerce` | Component Agency | $941.23M | https://www.eda.gov/about |
| Federal Housing Finance Agency | `exec-regulatory` | Regulatory Agency | $231.49M | https://www.fhfa.gov/about |
| Institute of Museum and Library Services | `exec-ind-misc` | Independent Agency | $179.50M | https://www.imls.gov/about |
| Administration for Children and Families | `exec-dept-hhs` | Component Agency | $59.94B | https://www.acf.hhs.gov/about |
| Administration for Community Living | `exec-dept-hhs` | Component Agency | $1.98B | https://acl.gov/about-acl |
| Legal Services Corporation | `exec-ind-misc` | Government Corporation | $540.00M | https://www.lsc.gov/about-lsc |
| Millennium Challenge Corporation | `exec-ind-misc` | Government Corporation | $505.55M | https://www.mcc.gov/about-us/ |
| Bureau of Consumer Financial Protection | `exec-regulatory` | Regulatory Agency | $361.69M | https://www.consumerfinance.gov/about-us/ |
| Corporation for Public Broadcasting | `exec-ind-misc` | Government Corporation (federally chartered, private) | $8.02M | see note (b) |
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

**U.S. Postal Service** (`exec-ind-usps`) is estimated at ≈ $19B while Table
5 prints the Postal Service's own off-budget line. The curated name is
"U.S. Postal Service (USPS)" and the statement's label differs; a probe
(`scripts/probe_treasury_rows.py`) will say which label it prints and
whether one node answers to it. An alias candidate, once confirmed.

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

## 4. Resolved since this document was first written

Two things this proposal used to point at are fixed in the pipeline, not
in curation:

- Six measured Treasury lines under `exec-ind-misc` (PBGC, EEOC, the Peace
  Corps, NLRB, NEA, NEH, $3.08B) were published as "not available"; the
  cascade now pays every measured line beneath a unit one haircut when
  they exceed it, never zero to some.
- The cap itself is gone. Every measured unit publishes the Treasury's own
  net figure, each section's receipts are carried as an explicit negative
  line beneath the unit whose total they reduce, and the government-wide
  offsetting receipts (−$343.3B) sit beside the three branches. CLAUDE.md
  ("Cost cascade") has the design and the identity it rests on.

What that leaves for curation is only what this document lists: the
sixteen units above (their lines now sit, unapportioned, inside their
sections' estimates), the AmeriCorps and Postal Service aliases, and the
Coast Guard duplicate — whose $9.6B, ambiguous between two nodes, is still
the largest single line the graph cannot place.
