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
| General Services Administration | `exec-independent` (a peer of NASA, OPM) | Independent Agency | -$836.73M | https://www.gsa.gov/about-us; directory: http://www.gsa.gov/ (d) |
| Agency for International Development | `exec-independent` | Independent Agency | $6.33B | https://www.usaid.gov/; directory: http://www.usaid.gov (d) |
| Railroad Retirement Board | `exec-ind-misc` | Independent Agency | $3.33B | https://www.rrb.gov/ |
| Corps of Engineers | see note (a) | Component Agency | $9.70B | https://www.usace.army.mil/About/; directory: http://www.usace.army.mil/Pages/default.aspx (d) |
| Agricultural Marketing Service | `exec-dept-usda` | Component Agency | $1.45B | https://www.ams.usda.gov/about-ams; directory: http://www.ams.usda.gov (d) |
| Foreign Agricultural Service | `exec-dept-usda` | Component Agency | $1.20B | https://www.fas.usda.gov/about-fas; directory: http://www.fas.usda.gov/ (d) |
| Economic Development Administration | `exec-dept-doc` | Component Agency | $941.23M | https://www.eda.gov/about; directory: http://www.eda.gov/ (d) |
| Federal Housing Finance Agency | `exec-regulatory` | Regulatory Agency | $231.49M | https://www.fhfa.gov/about |
| Institute of Museum and Library Services | `exec-ind-misc` | Independent Agency | $179.50M | https://www.imls.gov/about |
| Administration for Children and Families | `exec-dept-hhs` | Component Agency | $59.94B | https://www.acf.hhs.gov/about; directory: http://www.acf.hhs.gov/ (d) |
| Administration for Community Living | `exec-dept-hhs` | Component Agency | $1.98B | https://acl.gov/about-acl; directory: http://www.acl.gov/ (d) |
| Legal Services Corporation | `exec-ind-misc` | Government Corporation | $540.00M | https://www.lsc.gov/about-lsc; directory: http://www.lsc.gov/ (d) |
| Millennium Challenge Corporation | `exec-ind-misc` | Government Corporation | $505.55M | https://www.mcc.gov/about-us/; directory: http://www.mcc.gov/ (d) |
| Bureau of Consumer Financial Protection | `exec-regulatory` | Regulatory Agency | $361.69M | https://www.consumerfinance.gov/about-us/; directory: http://www.consumerfinance.gov/ (d) |
| Corporation for Public Broadcasting | `exec-ind-misc` | Government Corporation (federally chartered, private) | $8.02M | see note (b) |
| Corporation for National and Community Service | **not a gap — see §2** | | | directory: http://www.nationalservice.gov/ (d) |

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

(d) *directory:* the Federal Register agency directory's `agency_url` for
the unit's entry, verbatim — `http` scheme, trailing slash or its absence,
and all — from `tests/fixtures/directories/federal_register_agencies.json`
(fetched 2026-09-08T19:19:15Z; entry ids and slugs in §5.5). It is the
directory's record of the agency's site: a candidate to fetch, never
evidence. Every one differs from the page already listed (the directory
records a front page; this table lists an About page). The Railroad
Retirement Board, FHFA and IMLS have entries with no URL, and the
Corporation for Public Broadcasting has no entry, so those rows are
unchanged.

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

## 3. One unit, two subtrees: the Coast Guard — decided 2026-09-18

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

**The owner took the first option on 2026-09-18**, and
`scripts/merge_duplicate_nodes.py` is the change: the curated file is never
hand-edited, so a script makes it, idempotently, with every precondition
checked before anything is written. `exec-dept-defense-cg` and its nine
positions are gone; `exec-dept-dhs-uscg` stays, and it was already the richer
of the two (seventeen children, the nine districts named individually, against
nine with one "District Commander (×9 Districts)" standing for all of them).
"Military Departments & Services" gets the cross-reference this section
proposed, which it needed on its own account: its description read "The six
armed services organized under three military departments" while carrying
six children, and it now says which five it carries and where the sixth is.

The paragraph above expected the alias rule to keep the line unmatched. It
does not any more — the cap it referred to is gone (§4) — and the rebuild
that followed the merge landed it: **`exec-dept-dhs-uscg` publishes the
Treasury's own $10,932,150,297.01, `cost_status: official`,
`costVerificationStatus: verified`**, with the FiscalData URL on the node.
Two contradictory estimates of $4.15B and $9.38B became one measured figure,
and the graph's exact-node count went 136 → 137. That is what a duplicate was
costing: not just a second subtree, but the measured cost of a real agency.

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

## 5. What the government's own lists say about the curated graph (2026-09-08)

Two official machine-readable lists were fetched verbatim on 2026-09-08 and
committed under `tests/fixtures/directories/` (its README carries every
URL, HTTP status and hash): the Federal Register's agency directory
(`federal_register_agencies.json`, 472 entries, fetched 19:19:15Z) and the
Senate's per-committee membership XML (`senate/committee_memberships_<CODE>.xml`,
24 files, 19:20:42Z–19:21:13Z). `scripts/derive_directory_evidence.py`
matched them to the curated organisations by exact canonical name and wrote
`data/verification/directory_evidence.json`: 229 node records, 139 from the
directory and 90 from the Senate list. Everything below is read off those
files and `output/graph.json`. Nothing was fetched for this section, and
nothing in it has been applied to the base graph (§5.6). A third list, the
House Clerk's, was fetched on 2026-09-13 and is in §5.7; the file now holds
344 records.

Headline counts, from `directory_evidence.json`:

| Source (key) | Figure | Value |
|---|---|---|
| Federal Register (`report`) | entries in the directory | 472 |
| | matched to exactly one graph organisation | 139 |
| | unmatched | 333: 179 top-level, 148 filed under a parent the graph matches, 6 under one it does not (a) |
| | placement `listed` (directory parent = the node's parent here) | 63 |
| | placement `ancestor` (directory parent is above the node, but not its parent) | 5 — DCAA, DISA, DIA, DLA, NGA, all filed under "Defense Department" while the graph keeps them in the curated "Defense Agencies & Field Activities" |
| | placement `disagrees` (directory parent is elsewhere in the tree) | 1 — FERC, §5.3 |
| | placement: directory parent matched no node | 2 — NEA and NEH, filed under "National Foundation on the Arts and the Humanities", which the graph has no node for (§5.5, IMLS) |
| | graph names two nodes share, so no entry can match either | 8 (b) |
| Senate list (`senate_report`) | committees in the list / matched to a `leg-senate-cmte-*` node | 24 / 20 |
| | list committees with no such node | 4 — the joint committees, §5.2 |
| | graph Senate committees not in the list | 0 |
| | subcommittees: matched / graph names not in the list / list names not in the graph | 43 / 27 / 27 |
| | placement disagreements | 0 |

(a) 333 is 472 − 139, computed from the `entryId` each record carries; the
file itself keeps only a 60-name `unmatched_sample`. (b)
`ambiguous_names_in_graph`: budget review division, coast guard, districts,
health care, national security division, subcommittee on health,
subcommittee on oversight and investigations, va medical centers.

The Senate figures are symmetric because both sides carry exactly 70
subcommittees under the 20 matched committees: 43 names agree and 27 on
each side do not.

### 5.1 Senate subcommittees the Senate's list no longer carries (27)

Each row is a graph node of type Subcommittee under a committee the list
does match, whose name — after the project's spelling rules ("&" reads as
"and"; a leading "Subcommittee on" is ignored) — is not among the
`<subcommittee_name>` elements in that committee's XML. The site publishes
each as "Checked 8 Sep 2026 against the Senate's official committee list: it
carries no unit of this name under '<committee>'" (`verificationFailure:
not_in_official_list`), with the committee's full list of names beside it
(`listedNames`). That is a fact about the name, not the body: a renamed
subcommittee reads exactly this way. The last column is filled only where
the same committee's XML has exactly one subcommittee the graph lacks that
shares the graph name's distinctive words. It is a lead for the owner, never
a claim, and it is blank when two list names share the words or none does.

Source for every row: `senate_report.subcommittees_not_in_list` in
`data/verification/directory_evidence.json`. List names are verbatim from
`tests/fixtures/directories/senate/committee_memberships_<CODE>.xml`; the
code in brackets is the subcommittee's `<committee_code>`.

| Graph id (`output/graph.json`) | Curated name | Committee (XML code) | Possibly the same body, unverified |
|---|---|---|---|
| `leg-senate-cmte-agriculture-nutrition-and-forestry-sub-commodities-risk-management-trade` | Commodities, Risk Management & Trade | Agriculture, Nutrition, and Forestry (SSAF) | Subcommittee on Commodities, Derivatives, Risk Management, and Trade (SSAF13) |
| `leg-senate-cmte-agriculture-nutrition-and-forestry-sub-conservation-climate-forestry-natural-resources` | Conservation, Climate, Forestry & Natural Resources | Agriculture, Nutrition, and Forestry (SSAF) | Subcommittee on Conservation, Forestry, Natural Resources, and Biotechnology (SSAF14) |
| `leg-senate-cmte-agriculture-nutrition-and-forestry-sub-food-nutrition-specialty-crops-agricultural-research` | Food & Nutrition, Specialty Crops & Agricultural Research | Agriculture, Nutrition, and Forestry (SSAF) | Subcommittee on Food and Nutrition, Specialty Crops, Organics, and Research (SSAF16) |
| `leg-senate-cmte-agriculture-nutrition-and-forestry-sub-livestock-dairy-poultry-local-food-systems-food-safety-security` | Livestock, Dairy, Poultry, Local Food Systems & Food Safety & Security | Agriculture, Nutrition, and Forestry (SSAF) | Subcommittee on Livestock, Dairy, Poultry, and Food Safety (SSAF17) |
| `leg-senate-cmte-agriculture-nutrition-and-forestry-sub-rural-development-energy` | Rural Development & Energy | Agriculture, Nutrition, and Forestry (SSAF) | Subcommittee on Rural Development, Energy, and Credit (SSAF15) |
| `leg-senate-cmte-appropriations-sub-agriculture-rural-development-fda-related-agencies` | Agriculture, Rural Development, FDA & Related Agencies | Appropriations (SSAP) | Subcommittee on Agriculture, Rural Development, Food and Drug Administration, and Related Agencies (SSAP01) |
| `leg-senate-cmte-appropriations-sub-defense` | Defense | Appropriations (SSAP) | Subcommittee on Department of Defense (SSAP02) |
| `leg-senate-cmte-appropriations-sub-homeland-security` | Homeland Security | Appropriations (SSAP) | Subcommittee on Department of Homeland Security (SSAP14) |
| `leg-senate-cmte-appropriations-sub-interior-environment-related-agencies` | Interior, Environment & Related Agencies | Appropriations (SSAP) | Subcommittee on Department of Interior, Environment, and Related Agencies (SSAP17) |
| `leg-senate-cmte-appropriations-sub-labor-hhs-education-related-agencies` | Labor, HHS, Education & Related Agencies | Appropriations (SSAP) | Subcommittee on Departments of Labor, Health and Human Services, and Education, and Related Agencies (SSAP18) |
| `leg-senate-cmte-appropriations-sub-transportation-hud-related-agencies` | Transportation, HUD & Related Agencies | Appropriations (SSAP) | Subcommittee on Transportation, Housing and Urban Development, and Related Agencies (SSAP24) |
| `leg-senate-cmte-commerce-science-transportation-sub-aviation-safety-operations-innovation` | Aviation Safety, Operations & Innovation | Commerce, Science, and Transportation (SSCM) | Subcommittee on Aviation, Space, and Innovation (SSCM33) |
| `leg-senate-cmte-commerce-science-transportation-sub-communications-media-broadband` | Communications, Media & Broadband | Commerce, Science, and Transportation (SSCM) | Subcommittee on Telecommunications and Media (SSCM34) |
| `leg-senate-cmte-commerce-science-transportation-sub-consumer-protection-product-safety-data-security` | Consumer Protection, Product Safety & Data Security | Commerce, Science, and Transportation (SSCM) | Subcommittee on Consumer Protection, Technology, and Data Privacy (SSCM35) |
| `leg-senate-cmte-commerce-science-transportation-sub-oceans-fisheries-climate-change-manufacturing` | Oceans, Fisheries, Climate Change & Manufacturing | Commerce, Science, and Transportation (SSCM) | |
| `leg-senate-cmte-commerce-science-transportation-sub-science-space` | Science & Space | Commerce, Science, and Transportation (SSCM) | |
| `leg-senate-cmte-commerce-science-transportation-sub-surface-transportation-maritime-freight-ports` | Surface Transportation, Maritime, Freight & Ports | Commerce, Science, and Transportation (SSCM) | Subcommittee on Surface Transportation, Freight, Pipelines, and Safety (SSCM38) |
| `leg-senate-cmte-commerce-science-transportation-sub-tourism-trade-export-promotion` | Tourism, Trade & Export Promotion | Commerce, Science, and Transportation (SSCM) | |
| `leg-senate-cmte-environment-public-works-sub-clean-air-climate-nuclear-safety` | Clean Air, Climate & Nuclear Safety | Environment and Public Works (SSEV) | Subcommittee on Clean Air, Climate, and Nuclear Innovation and Safety (SSEV10) |
| `leg-senate-cmte-homeland-security-governmental-affairs-sub-emerging-threats-spending-oversight` | Emerging Threats & Spending Oversight | Homeland Security and Governmental Affairs (SSGA) | |
| `leg-senate-cmte-homeland-security-governmental-affairs-sub-government-operations-border-management` | Government Operations & Border Management | Homeland Security and Governmental Affairs (SSGA) | Subcommittee on Border Management, Federal Workforce, and Regulatory Affairs (SSGA22) |
| `leg-senate-cmte-homeland-security-governmental-affairs-sub-investigations-subcommittee-on-permanent-investigations` | Investigations & Subcommittee on Permanent Investigations | Homeland Security and Governmental Affairs (SSGA) | Permanent Subcommittee on Investigations (SSGA01) |
| `leg-senate-cmte-health-education-labor-pensions-sub-children-families` | Children & Families | Health, Education, Labor, and Pensions (SSHR) | Subcommittee on Education and the American Family (SSHR09) — weakest entry, see note |
| `leg-senate-cmte-judiciary-sub-competition-policy-antitrust-consumer-rights` | Competition Policy, Antitrust & Consumer Rights | the Judiciary (SSJU) | Subcommittee on Antitrust, Competition Policy, and Consumer Rights (SSJU01) |
| `leg-senate-cmte-judiciary-sub-criminal-justice-counterterrorism` | Criminal Justice & Counterterrorism | the Judiciary (SSJU) | Subcommittee on Crime and Counterterrorism (SSJU22) |
| `leg-senate-cmte-judiciary-sub-human-rights-the-law` | Human Rights & the Law | the Judiciary (SSJU) | |
| `leg-senate-cmte-judiciary-sub-immigration-citizenship-border-safety` | Immigration, Citizenship & Border Safety | the Judiciary (SSJU) | Subcommittee on Border Security and Immigration (SSJU04) |

Notes on the last column — what the files show, not what they prove:

- *Appropriations.* The six differences are the curated file's
  abbreviations (FDA, HHS, HUD) and its dropping of "Department of"; the
  same words in the same order otherwise. These are the likeliest to be one
  body under one name written two ways, and they are still unverified: the
  pipeline matches on the exact name and has no abbreviation table. The XML
  prints SSAP24's name with two trailing spaces; the key function strips
  them, so that is not why it failed.
- *Commerce.* The graph has seven, the list six, and the words are
  redistributed. "Science & Space" shares "Space" with SSCM33 and "Science"
  with SSCM37; "Oceans, Fisheries, Climate Change & Manufacturing" shares
  "Fisheries" with SSCM36 ("Coast Guard, Maritime, and Fisheries") and
  "Manufacturing" with SSCM37 ("Science, Manufacturing, and
  Competitiveness"); "Tourism, Trade & Export Promotion" shares nothing
  with any list name. Those three are blank. "Surface Transportation,
  Maritime, Freight & Ports" is filled on "Surface Transportation … Freight"
  although "Maritime" now sits in SSCM36.
- *Homeland Security.* "Emerging Threats & Spending Oversight" shares no
  word with the committee's three list names. The curated name
  "Investigations & Subcommittee on Permanent Investigations" reads as two
  names run together; the list's is "Permanent Subcommittee on
  Investigations".
- *HELP.* "Children & Families" against "Education and the American Family"
  shares one stem. It is the only unmatched pair under that committee, and
  that is the whole basis for the entry.
- *Judiciary.* "Human Rights & the Law" shares only "Rights" with the one
  remaining list name, "Federal Courts, Oversight, Agency Action, and Federal
  Rights"; blank.

The 27 list subcommittees the graph lacks
(`senate_report.subcommittees_not_in_graph`), by committee. Each name is a
verbatim `<subcommittee_name>`; the last column says where it appears above.

| Committee (XML code) | Subcommittee as the list prints it | Code | Appears above as |
|---|---|---|---|
| Agriculture, Nutrition, and Forestry (SSAF) | Subcommittee on Commodities, Derivatives, Risk Management, and Trade | SSAF13 | → Commodities, Risk Management & Trade |
| Agriculture, Nutrition, and Forestry (SSAF) | Subcommittee on Conservation, Forestry, Natural Resources, and Biotechnology | SSAF14 | → Conservation, Climate, Forestry & Natural Resources |
| Agriculture, Nutrition, and Forestry (SSAF) | Subcommittee on Food and Nutrition, Specialty Crops, Organics, and Research | SSAF16 | → Food & Nutrition, Specialty Crops & Agricultural Research |
| Agriculture, Nutrition, and Forestry (SSAF) | Subcommittee on Livestock, Dairy, Poultry, and Food Safety | SSAF17 | → Livestock, Dairy, Poultry, Local Food Systems & Food Safety & Security |
| Agriculture, Nutrition, and Forestry (SSAF) | Subcommittee on Rural Development, Energy, and Credit | SSAF15 | → Rural Development & Energy |
| Appropriations (SSAP) | Subcommittee on Agriculture, Rural Development, Food and Drug Administration, and Related Agencies | SSAP01 | → Agriculture, Rural Development, FDA & Related Agencies |
| Appropriations (SSAP) | Subcommittee on Department of Defense | SSAP02 | → Defense |
| Appropriations (SSAP) | Subcommittee on Department of Homeland Security | SSAP14 | → Homeland Security |
| Appropriations (SSAP) | Subcommittee on Department of Interior, Environment, and Related Agencies | SSAP17 | → Interior, Environment & Related Agencies |
| Appropriations (SSAP) | Subcommittee on Departments of Labor, Health and Human Services, and Education, and Related Agencies | SSAP18 | → Labor, HHS, Education & Related Agencies |
| Appropriations (SSAP) | Subcommittee on Transportation, Housing and Urban Development, and Related Agencies | SSAP24 | → Transportation, HUD & Related Agencies |
| Banking, Housing, and Urban Affairs (SSBK) | Subcommittee on Digital Assets | SSBK13 | no graph near-name; the committee's five graph subcommittees all match the list |
| Commerce, Science, and Transportation (SSCM) | Subcommittee on Aviation, Space, and Innovation | SSCM33 | → Aviation Safety, Operations & Innovation |
| Commerce, Science, and Transportation (SSCM) | Subcommittee on Coast Guard, Maritime, and Fisheries | SSCM36 | named in the Commerce note; not filled |
| Commerce, Science, and Transportation (SSCM) | Subcommittee on Consumer Protection, Technology, and Data Privacy | SSCM35 | → Consumer Protection, Product Safety & Data Security |
| Commerce, Science, and Transportation (SSCM) | Subcommittee on Science, Manufacturing, and Competitiveness | SSCM37 | named in the Commerce note; not filled |
| Commerce, Science, and Transportation (SSCM) | Subcommittee on Surface Transportation, Freight, Pipelines, and Safety | SSCM38 | → Surface Transportation, Maritime, Freight & Ports |
| Commerce, Science, and Transportation (SSCM) | Subcommittee on Telecommunications and Media | SSCM34 | → Communications, Media & Broadband |
| Environment and Public Works (SSEV) | Subcommittee on Clean Air, Climate, and Nuclear Innovation and Safety | SSEV10 | → Clean Air, Climate & Nuclear Safety |
| Homeland Security and Governmental Affairs (SSGA) | Permanent Subcommittee on Investigations | SSGA01 | → Investigations & Subcommittee on Permanent Investigations |
| Homeland Security and Governmental Affairs (SSGA) | Subcommittee on Border Management, Federal Workforce, and Regulatory Affairs | SSGA22 | → Government Operations & Border Management |
| Homeland Security and Governmental Affairs (SSGA) | Subcommittee on Disaster Management, District of Columbia, and Census | SSGA20 | no graph near-name |
| Health, Education, Labor, and Pensions (SSHR) | Subcommittee on Education and the American Family | SSHR09 | → Children & Families (weak) |
| the Judiciary (SSJU) | Subcommittee on Antitrust, Competition Policy, and Consumer Rights | SSJU01 | → Competition Policy, Antitrust & Consumer Rights |
| the Judiciary (SSJU) | Subcommittee on Border Security and Immigration | SSJU04 | → Immigration, Citizenship & Border Safety |
| the Judiciary (SSJU) | Subcommittee on Crime and Counterterrorism | SSJU22 | → Criminal Justice & Counterterrorism |
| the Judiciary (SSJU) | Subcommittee on Federal Courts, Oversight, Agency Action, and Federal Rights | SSJU25 | named in the Judiciary note; not filled |

Twenty-two of the 27 are offered as candidates in the first table, three
are named in its notes and deliberately not filled, and two (SSBK13,
SSGA20) have no near name in the graph at all. Whatever the owner decides
for a candidate pair — rename the node to the Senate's form, or keep the
curated name — the site keeps saying "carries no unit of this name" until
the names agree, and says "the Senate's official committee list carries it"
the build after they do.

### 5.2 The four Senate-list committees with no Senate committee node

`senate_report.committees_not_in_graph` names four, all joint committees.
The matcher considers only nodes whose id begins `leg-senate-cmte-`
(`SENATE_ID_PREFIX`, `data_pipeline/verification/congress.py`), so "not in
graph" means "not among the Senate's committee nodes". `output/graph.json`
does carry all four, under `leg-joint` "Joint Congressional Bodies" — a
Division directly under the Legislative Branch — with no source, no date and
no directory record; the site shows "No source recorded" for each.

| List name (`senate/committee_memberships_<CODE>.xml`) | Code | Graph node (id, name; parent `leg-joint`) | Same name? |
|---|---|---|---|
| Joint Economic Committee (JSEC) | JSEC00 | `leg-joint-econ`, "Joint Economic Committee" | yes, exactly |
| Joint Committee of Congress on the Library (JSLC) | JSLC00 | `leg-joint-library`, "Joint Committee on the Library" | no — the list adds "of Congress"; [Likely] the same body, unverified |
| Joint Committee on Printing (JSPR) | JSPR00 | `leg-joint-printing`, "Joint Committee on Printing" | yes, exactly |
| Joint Committee on Taxation (JSTX) | JSTX00 | `leg-joint-tax`, "Joint Committee on Taxation" | yes, exactly |

No curation is needed for the three exact names; reaching them is pipeline
work (a matcher scope that includes `leg-joint-*`). For the Library
committee the owner can rename the node to the Senate's form, or keep the
curated name and accept that a widened matcher would publish it as "carries
no unit of this name" — the honest reading of a name the list does not
carry.

### 5.3 One placement disagreement: FERC

The record (`nodes["exec-regulatory-ferc"]`, and `report.placements_disagree`):
the Federal Register's directory lists "Federal Energy Regulatory
Commission" (entry 167; page
https://www.federalregister.gov/agencies/federal-energy-regulatory-commission;
`agency_url` http://www.ferc.gov/) with parent "Energy Department", the entry
the graph matches to `exec-dept-doe` "Department of Energy (DOE)". The
published tree places `exec-regulatory-ferc` "Federal Energy Regulatory
Commission (FERC)" (type Independent Regulatory Commission) under
`exec-regulatory` "Independent Regulatory Commissions", a curated Division
directly under the Executive Branch; DOE is not on its path.

What the site does with it: the node carries `placementDirectoryDisagreement`
(`listedUnder: "Energy Department"`, `directoryParentId: exec-dept-doe`, the
entry's URL, `checkedAt` 2026-09-08T19:19:15Z), `placementVerified` stays
null, the existence claim "The Federal Register's agency directory lists it"
stands, and the Placement line reads: *The Federal Register's agency
directory files it under "Energy Department", not under its parent here —
the two sources disagree, and neither is resolved.*

Both positions are defensible. [Likely, from general knowledge; not checked
against any file here] FERC was created by the Department of Energy
Organization Act of 1977 as an independent regulatory commission *within*
the Department: the directory's parent records the statutory housing, the
curated grouping records the independence, and neither is wrong about what
it records. Owner's options: leave it, since the site already publishes the
disagreement and claims nothing; move the node under `exec-dept-doe`, after
which the directory's placement would publish as `listed` and the
"independent" reading would rest on the type field alone; or keep the
placement and say in the node's description which structure the tree
follows. This document does not choose.

### 5.4 Directory entries that appear to be graph organisations under other names

Leads, not matches. The matcher's rule is exact: a directory name — or its
"Department of X" inversion when the last word is a head noun — must equal
one organisation's canonical name (bracketed abbreviations, "&"/"and",
"U.S."/"United States" and punctuation ignored), and exactly one. The rows
below are the pairs a person reading the two names side by side would
suspect are one body and the rule cannot say so. Every row is [possible,
unverified]: nothing was checked against any page, and a row is not a
proposal to rename anything — it says what the owner may want to look at.
Most confident first. Directory fields are verbatim from
`federal_register_agencies.json` (entry `id`, `name`, the parent entry's
name, `agency_url`; "none" where the field is empty or null); graph fields
from `output/graph.json`.

**A. The same name, written differently — an abbreviation or a prefix the rule does not know.**

| # | Directory entry (id, name; listed parent) | agency_url | Graph organisation (id, name; parent here) | What differs |
|---|---|---|---|---|
| 1 | 408 Pipeline and Hazardous Materials Safety Administration; Transportation Department | none | `exec-dept-dot-phmsa` "Pipeline & Hazardous Materials Safety Admin (PHMSA)"; Department of Transportation (DOT) | "Admin" [possible, unverified] |
| 2 | 479 Substance Abuse and Mental Health Services Administration; Health and Human Services Department | none | `exec-dept-hhs-samhsa` "Substance Abuse & Mental Health Services Admin (SAMHSA)"; Department of Health & Human Services (HHS) | "Admin" [possible, unverified] |
| 3 | 181 Federal Motor Carrier Safety Administration; Transportation Department | http://www.fmcsa.dot.gov/ | `exec-dept-dot-fmcsa` "Federal Motor Carrier Safety Admin (FMCSA)"; DOT | "Admin" [possible, unverified] |
| 4 | 345 National Highway Traffic Safety Administration; Transportation Department | none | `exec-dept-dot-nhtsa` "National Highway Traffic Safety Admin (NHTSA)"; DOT | "Admin" [possible, unverified] |
| 5 | 373 National Telecommunications and Information Administration; Commerce Department | none | `exec-dept-doc-ntia` "National Telecommunications & Information Admin (NTIA)"; Department of Commerce | "Admin" [possible, unverified] |
| 6 | 352 National Institute of Standards and Technology; Commerce Department | none | `exec-dept-doc-nist` "NIST — National Institute of Standards & Technology"; Department of Commerce | the "NIST — " prefix [possible, unverified] |
| 7 | 361 National Oceanic and Atmospheric Administration; Commerce Department | none | `exec-dept-doc-noaa` "NOAA — National Oceanic & Atmospheric Administration"; Department of Commerce | the "NOAA — " prefix [possible, unverified] |
| 8 | 402 Patent and Trademark Office; Commerce Department | none | `exec-dept-doc-uspto` "USPTO — Patent & Trademark Office"; Department of Commerce | the "USPTO — " prefix [possible, unverified] |
| 9 | 606 U.S. International Development Finance Corporation; top-level | https://www.dfc.gov/ | `exec-ind-misc-u-s-international-development-finance-corp-dfc` "U.S. International Development Finance Corp (DFC)"; Other Independent Agencies (25+) | "Corp" [possible, unverified] |
| 10 | 177 Federal Law Enforcement Training Center; Homeland Security Department | http://www.fletc.gov/ | `exec-dept-dhs-fletc` "Federal Law Enforcement Training Centers (FLETC)"; Department of Homeland Security (DHS) | singular / plural [possible, unverified] |
| 11 | 80 Comptroller of the Currency; Treasury Department | https://www.occ.gov | `exec-dept-treasury-occ` "Office of the Comptroller of the Currency (OCC)"; Department of the Treasury | "Office of the" [possible, unverified] |
| 12 | 151 Export-Import Bank; top-level | http://www.exim.gov/ | `exec-ind-misc-export-import-bank-of-the-u-s` "Export-Import Bank of the U.S."; Other Independent Agencies (25+) | "of the U.S." [possible, unverified] |
| 13 | 491 Trade Representative, Office of United States; top-level | none | `exec-eop-ustr` "Office of the U.S. Trade Representative"; Executive Office of the President (EOP) | the directory's inverted comma form; its tail "Office of United States" is not itself an entry, so the qualifier rule does not fire. The directory files it top-level while the entry's own description calls it "an agency of the Executive Office of the President", which is where the graph has it [possible, unverified] |
| 14 | 367 National Security Agency/Central Security Service; Defense Department | http://www.nsa.gov/ | `exec-dept-defense-agency-nsa` "National Security Agency (NSA)"; Defense Agencies & Field Activities | the directory joins two names with a slash. If it matched, placement would publish as `ancestor` like DCAA's: "Defense Department" is two levels up [possible, unverified] |

**B. Two directory entries for one body, or one node carrying two names.**

| # | Directory entry (id, name; listed parent) | agency_url | Graph organisation (id, name; parent here) | What the files say |
|---|---|---|---|---|
| 15 | 409 Postal Regulatory Commission; top-level | none | `exec-ind-misc-u-s-postal-rate-commission-postal-regulatory-commission` "U.S. Postal Rate Commission / Postal Regulatory Commission"; Other Independent Agencies (25+) | the node's name joins two names; the entry's description calls the Commission "the successor agency to the Postal Rate Commission" [possible, unverified] |
| 16 | 564 Postal Rate Commission; top-level | http://www.prc.gov | the same node | the directory keeps the predecessor as its own entry. Even with the node's name split, two entries answering to one node match nothing under the rule; the owner would have to choose which name the node carries [possible, unverified] |
| 17 | 41 Broadcasting Board of Governors; top-level | http://www.bbg.gov/ | `exec-ind-misc-broadcasting-board-of-governors-usagm` "Broadcasting Board of Governors / USAGM"; Other Independent Agencies (25+) | the node's name joins two names [possible, unverified] |
| 18 | 608 United States Agency for Global Media; top-level | https://www.usagm.gov/ | the same node | the directory carries both as separate top-level entries, and neither description says one succeeded the other [possible, unverified] |
| 19 | 389 Office of Motor Carrier Safety; Transportation Department | none | `exec-dept-dot-fmcsa` (row 3) | a second Transportation entry sharing FMCSA's distinctive words; [Likely] a predecessor unit rather than the same name. Not a lead on its own [possible, unverified] |
| 20 | 559 Health Care Finance Administration; Health and Human Services Department | none | `exec-dept-hhs-cms` "Centers for Medicare & Medicaid Services (CMS)" — already matched, to entry 45 | the entry's description says HCFA "was created in 1977 to combine under one administration the oversight of the Medicare program, the Federal portion of the Medicaid program"; the directory keeps the old name as its own entry. Not a lead for the graph: the node is listed under its current name |

**C. The military departments — the directory lists departments, the graph lists services.**

| # | Directory entry (id, name; listed parent) | agency_url | Graph organisation (id, name; parent here) | What differs |
|---|---|---|---|---|
| 21 | 13 Air Force Department; Defense Department | http://www.af.mil/ | `exec-dept-defense-af` "U.S. Air Force" (Military Branch); Military Departments & Services | a department and the service inside it are not one body; the curated grouping's own name suggests the node stands for both. Owner's call whether one node should [possible, unverified] |
| 22 | 32 Army Department; Defense Department | http://www.army.mil/ | `exec-dept-defense-army` "U.S. Army"; Military Departments & Services | as row 21 [possible, unverified] |
| 23 | 378 Navy Department; Defense Department | none | `exec-dept-defense-navy` "U.S. Navy"; Military Departments & Services | as row 21; the graph's separate `exec-dept-defense-marines` "U.S. Marine Corps" [Likely] sits inside the Department of the Navy, which the directory does not list separately [possible, unverified] |

**D. Blocked by a duplicate name in the graph.**

| # | Directory entry (id, name; listed parent) | agency_url | Graph organisation (id, name; parent here) | What the files say |
|---|---|---|---|---|
| 24 | 53 Coast Guard; Homeland Security Department | http://www.uscg.mil/ | `exec-dept-dhs-uscg` "U.S. Coast Guard"; DHS — and `exec-dept-defense-cg` "U.S. Coast Guard"; Military Departments & Services | "coast guard" is in `ambiguous_names_in_graph`: one entry, two nodes, no match. The directory files it under Homeland Security, and the entry's description says it "was transferred from Department of Transportation to the Department of Homeland Security on March 1, 2003". Bears on §3 [possible, unverified] |

**E. The alias §2 already makes.**

| # | Directory entry (id, name; listed parent) | agency_url | Graph organisation (id, name; parent here) | What the files say |
|---|---|---|---|---|
| 25 | 91 Corporation for National and Community Service; top-level | http://www.nationalservice.gov/ | `exec-ind-misc-americorps` "AmeriCorps"; Other Independent Agencies (25+) | no shared word; the correspondence is §2's, from the statute, not from this file. The directory has no "AmeriCorps" entry [possible, unverified] |

**Counter-examples** — pairs a word search offers that the files say are
not one body, listed so no one re-derives them:

- "Aging Administration" (entry 8, `agency_url`
  https://www.acl.gov/about-acl/administration-aging, under Health and Human
  Services) against "Community Living Administration" (entry 587,
  http://www.acl.gov/, same parent): the directory carries them as two
  entries; the Aging entry's page is a page *inside* acl.gov, and the ACL
  entry's description says ACL "brings together the efforts and achievements
  of the Administration on …" — one is a component of the other [Likely],
  not a rename. The graph has neither (§1). "Aging Administration" is not
  "Administration for Community Living".
- "Children and Families Administration" (entry 49, http://www.acf.hhs.gov/,
  under HHS): the graph has no organisation of that name — §1's ACF gap. The
  only near name, "Children & Families", is a subcommittee of the Senate HELP
  committee (and itself not in the Senate's list, §5.1): not the same body.
- "Federal Housing Finance Agency" (entry 174, no URL) against
  `exec-dept-hud-fha` "Federal Housing Administration (FHA)": the entry's
  description says FHFA was created in 2008 "to oversee … Fannie Mae, Freddie
  Mac, and the Federal Home Loan Banks"; the FHA is HUD's mortgage insurer.
  Different bodies; FHFA stays a §1 gap. The directory also has a "Federal
  Housing Finance Board" (entry 175, no URL), a third name.
- "Civil Rights Commission" (entry 52, http://www.usccr.gov/) against DOJ's
  "Civil Rights Division" and Education's "Office for Civil Rights (OCR)":
  three bodies; the graph has no node for the Commission.
- "Arms Control and Disarmament Agency" (entry 31, no URL) against State's
  "Bureau of Arms Control, Verification & Compliance": the directory's
  description is in the present tense; [Likely] the Agency was abolished and
  its functions moved into State in 1999, which would make the bureau a
  successor, not the same body. Not a lead.
- "Technology Administration" (entry 484) against NIST; "National Technical
  Information Service" (entry 372) against NTIA; "Harry S. Truman Scholarship
  Foundation" (entry 220) against the Truman Presidential Library: different
  bodies.

What the other unmatched entries are. Of the 333, 179 are top-level and
most have no graph counterpart of any name — commissions, boards and defunct
bodies; 50 of the 333 describe themselves as abolished, terminated or
transferred. 148 are filed under a department the graph matches and name a
unit the graph lacks: the four departmental Inspector General offices
(entries 244 Agriculture, 245 HHS, 626 Interior, 622 Treasury — the graph's
only OIG node is the House's, `leg-house-ig`), the five power
administrations under Energy, USDA's Rural Development services. Those are
gaps, not renames; they belong to a future curation list, and §1 stays the
Treasury-driven one.

### 5.5 The sixteen known base-graph gaps in the directory

For each unit in CLAUDE.md's "Known base-graph gaps", whether
`federal_register_agencies.json` has an entry, and what it carries. Fifteen
do; twelve of those have a non-empty `agency_url`, which has been added to
§1's "Candidate official page" column as "directory: …" with footnote (d).
`agency_url` is verbatim, `http` and all; "none" is the file's empty string
or null.

| Unit (CLAUDE.md) | Entry id, name as listed | slug | agency_url | Listed parent | Note |
|---|---|---|---|---|---|
| General Services Administration | 210, General Services Administration | general-services-administration | http://www.gsa.gov/ | top-level | added to §1 |
| Agency for International Development | 6, Agency for International Development | agency-for-international-development | http://www.usaid.gov | top-level | added to §1; the directory gives it one child, "International Development Cooperation Agency" (258, no URL). §1 note (c) stands: the directory as fetched still lists USAID as its own top-level agency |
| Railroad Retirement Board | 444, Railroad Retirement Board | railroad-retirement-board | none | top-level | no URL to add; §1's candidate stands alone |
| Corps of Engineers | 142, Engineers Corps | engineers-corps | http://www.usace.army.mil/Pages/default.aspx | Defense Department | added to §1. The directory files it under Defense, not under its "Army Department" entry (32, also a child of Defense) — a third placement beside the two §1 note (a) weighs |
| Agricultural Marketing Service | 9, Agricultural Marketing Service | agricultural-marketing-service | http://www.ams.usda.gov | Agriculture Department | added to §1; parent agrees with §1's `exec-dept-usda` |
| Foreign Agricultural Service | 202, Foreign Agricultural Service | foreign-agricultural-service | http://www.fas.usda.gov/ | Agriculture Department | added to §1; parent agrees |
| Economic Development Administration | 120, Economic Development Administration | economic-development-administration | http://www.eda.gov/ | Commerce Department | added to §1; parent agrees with the graph's Department of Commerce, `exec-dept-doc` (§1 had proposed `exec-dept-commerce`, which is not an id in `output/graph.json`; corrected) |
| Federal Housing Finance Agency | 174, Federal Housing Finance Agency | federal-housing-finance-agency | none | top-level | no URL to add; a separate "Federal Housing Finance Board" entry (175, no URL) also exists |
| Institute of Museum and Library Services | 591, Institute of Museum and Library Services | institute-of-museum-and-library-services | none | National Foundation on the Arts and the Humanities | no URL to add. The directory files IMLS, NEA and NEH under that Foundation (342, top-level, no URL, unmatched — the graph has no node for it, which is why NEA's and NEH's placements are the two "parent matched no node" cases above). §1's `exec-ind-misc` keeps IMLS beside NEA and NEH, where the graph has them |
| Administration for Children and Families | 49, Children and Families Administration | children-and-families-administration | http://www.acf.hhs.gov/ | Health and Human Services Department | added to §1; parent agrees with `exec-dept-hhs`. The head-noun rule would match this entry to a node named "Administration for Children and Families" |
| Administration for Community Living | 587, Community Living Administration | community-living-administration | http://www.acl.gov/ | Health and Human Services Department | added to §1; parent agrees. See the Aging counter-example in §5.4 |
| Corporation for National and Community Service | 91, Corporation for National and Community Service | corporation-for-national-and-community-service | http://www.nationalservice.gov/ | top-level | added to §1's row (which points to the §2 alias); a candidate page for the AmeriCorps node, which today has no source at all |
| Legal Services Corporation | 276, Legal Services Corporation | legal-services-corporation | http://www.lsc.gov/ | top-level | added to §1 |
| Millennium Challenge Corporation | 287, Millennium Challenge Corporation | millennium-challenge-corporation | http://www.mcc.gov/ | top-level | added to §1 |
| Bureau of Consumer Financial Protection | 573, Consumer Financial Protection Bureau | consumer-financial-protection-bureau | http://www.consumerfinance.gov/ | top-level | added to §1. Table 5 prints "Bureau of Consumer Financial Protection", the directory "Consumer Financial Protection Bureau"; the head-noun rule answers to either, so one node named either way would match both |
| Corporation for Public Broadcasting | no entry | — | — | — | the only "Broadcasting" entries are the Broadcasting Board of Governors (41), the International Broadcasting Advisory Board (617) and the International Broadcasting Board (256). Consistent with §1 note (b): a private corporation, outside the directory as outside the `.gov` rule |

### 5.6 What the four words mean on the site, and the standing rule

*Listed* — one of the government's own lists carries an entry whose name is
this node's name, letter for letter once the project's spelling rules are
applied (an abbreviation in brackets is ignored, "&" reads as "and",
"Energy Department" reads as "Department of Energy"). The panel says which
list, links the entry, and dates the claim by the day the list was fetched.
It is a weaker claim than reading the unit's own page — the Federal
Register's directory is a list of who publishes notices, the Senate's is a
membership roll — and it is worded as itself, never as "verified". 202
nodes carry it today (139 from the directory, 63 from the Senate list).

*Not in the official list* — only the Senate's list can say this, because
only it is complete for what it lists: every subcommittee of a committee is
in that committee's file, so a graph subcommittee whose name is absent has
been checked and not found *by name*. The panel says exactly that and shows
the names the list does carry. It does not say the body has ceased to
exist; a renamed subcommittee reads the same way, which is what §5.1 is for.
The Federal Register's directory never produces this state, because an
agency that has not published in the Register is simply not in it. 27 nodes
carry it today.

*Filed under an ancestor* — the directory names a parent that is above the
node here but is not its immediate parent: the graph keeps the Defense
Intelligence Agency under a curated grouping, "Defense Agencies & Field
Activities", and the directory says "Defense Department", one level higher.
The panel says so and adds that the grouping between is curated and the
directory says nothing about it. That is not a disagreement; it is the
directory being flatter than the graph. Five nodes.

*Disagrees* — the directory's parent is somewhere else in the tree
altogether (FERC, §5.3). The panel prints both, says the two sources
disagree, and resolves nothing. One node.

Where the directory's parent *is* the node's parent here, the Placement line
reads "the Federal Register's agency directory files it under its parent
here" — or, for a subcommittee, "the Senate's official committee list
carries it under its committee here" — with the list's URL and date (106
edges today); a node whose parent has no entry in any list reads "could not
be checked".

The standing rule: none of this touches `data/federal_gov_complete_1.json`.
The pipeline stamps what the lists say onto the published copies of the
nodes and withdraws those stamps the moment a re-fetched list stops saying
it; it never renames, moves, adds or removes a node, and it never chooses
between a list and the curated file. Every change this section suggests is
the owner's to make by hand, and until it is made the site publishes the
difference as a difference.

### 5.7 The House Clerk's committee list (fetched 2026-09-13)

`tests/fixtures/directories/house/committees.xlsx` is the Clerk's own
committee data (`https://clerk.house.gov/Committees/ExcelCommitteeData`,
2026-09-13T22:51:28Z, 136 rows: name, code, type, parent code, website).
`scripts/derive_directory_evidence.py` matched it by the Senate's rules
(§5, `house_report` in `directory_evidence.json`): a leading "House
Committee on" and "Subcommittee on" are ignored, "&" reads as "and", and
"House Committee on Permanent Select Committee on Intelligence" folds onto
"Permanent Select Committee on Intelligence" as the Senate's Ethics artifact
does. Nothing was fuzzy-matched.

| Figure | Value |
|---|---|
| committees in the list / matched to a `leg-house-cmte-*` Committee node | 27 / 18 |
| list committees with no such node | 9 — the four joint committees (`leg-joint-*`, as §5.2), the Committee on Ethics (no curated node), the Select Subcommittee on January 6 (none), and three spelled differently from the curated name: "Committee on Education and Workforce", "Committee on Oversight and Government Reform", "Select Committee on the Strategic Competition Between the United States and the Chinese Communist Party" |
| graph House committees not in the list | 4 — Education & the Workforce, Oversight & Accountability and the Chinese Communist Party select committee (the three above, read from the other side), and `leg-house-cmte-intelligence` "House Committee on Intelligence", which sits beside `leg-house-cmte-permanent-select-committee-on-intelligence` (the one the list matches): [Likely] a duplicate of it, for the owner to merge |
| subcommittees: matched and placed / graph names not in the list / list names not in the graph | 68 / 25 / 30 |
| placement disagreements | 0 |

Each of the 25 publishes as "Checked 13 Sep 2026 against the House Clerk's
official committee list: it carries no unit of this name under
'<committee>'" with the committee's full list of names beside it. The last
column follows §5.1's rule: filled only where the same committee has
exactly one list name the graph lacks that shares the graph name's
distinctive words; a lead, never a claim.

| Graph id | Curated name | Committee | Possibly the same body, unverified |
|---|---|---|---|
| `leg-house-cmte-agriculture-sub-horticulture-farm-inputs-subcommittee-on-precision-agriculture` | Subcommittee on Horticulture, Farm Inputs & Subcommittee on Precision Agriculture | Agriculture | — (two list names share "Horticulture") |
| `leg-house-cmte-agriculture-sub-nutrition-foreign-agriculture-horticulture` | Subcommittee on Nutrition, Foreign Agriculture & Horticulture | Agriculture | Nutrition and Foreign Agriculture (AG03) |
| `leg-house-cmte-appropriations-sub-agriculture-rural-development-fda-related-agencies` | Subcommittee on Agriculture, Rural Development, FDA & Related Agencies | Appropriations | Agriculture, Rural Development, Food and Drug Administration, and Related Agencies (AP01) |
| `leg-house-cmte-appropriations-sub-energy-water-development` | Subcommittee on Energy & Water Development | Appropriations | Energy and Water Development and Related Agencies (AP10) |
| `leg-house-cmte-appropriations-sub-labor-hhs-education-related-agencies` | Subcommittee on Labor, HHS & Education & Related Agencies | Appropriations | Labor, Health and Human Services, Education, and Related Agencies |
| `leg-house-cmte-appropriations-sub-state-foreign-operations-related-programs` | Subcommittee on State, Foreign Operations & Related Programs | Appropriations | National Security, Department of State, and Related Programs |
| `leg-house-cmte-appropriations-sub-transportation-hud-related-agencies` | Subcommittee on Transportation, HUD & Related Agencies | Appropriations | Transportation, Housing and Urban Development, and Related Agencies |
| `leg-house-cmte-armed-services-sub-cyber-information-technology-innovation` | Subcommittee on Cyber, Information Technology & Innovation | Armed Services | Cyber, Information Technologies, and Innovation |
| `leg-house-cmte-energy-commerce-sub-energy-climate-grid-security` | Subcommittee on Energy, Climate & Grid Security | Energy and Commerce | Energy |
| `leg-house-cmte-energy-commerce-sub-environment-manufacturing-critical-materials` | Subcommittee on Environment, Manufacturing & Critical Materials | Energy and Commerce | Environment |
| `leg-house-cmte-energy-commerce-sub-innovation-data-commerce` | Subcommittee on Innovation, Data & Commerce | Energy and Commerce | Commerce, Manufacturing, and Trade |
| `leg-house-cmte-financial-services-sub-financial-institutions-monetary-policy` | Subcommittee on Financial Institutions & Monetary Policy | Financial Services | Financial Institutions |
| `leg-house-cmte-foreign-affairs-sub-global-health-global-human-rights-international-organizations` | Subcommittee on Global Health, Global Human Rights & International Organizations | Foreign Affairs | — |
| `leg-house-cmte-foreign-affairs-sub-indo-pacific` | Subcommittee on Indo-Pacific | Foreign Affairs | East Asia and Pacific |
| `leg-house-cmte-foreign-affairs-sub-middle-east-north-africa-central-asia` | Subcommittee on Middle East, North Africa & Central Asia | Foreign Affairs | Middle East and North Africa |
| `leg-house-cmte-foreign-affairs-sub-oversight-accountability` | Subcommittee on Oversight & Accountability | Foreign Affairs | Oversight and Intelligence |
| `leg-house-cmte-homeland-security-sub-counterterrorism-law-enforcement-intelligence` | Subcommittee on Counterterrorism, Law Enforcement & Intelligence | Homeland Security | Counterterrorism and Intelligence |
| `leg-house-cmte-house-administration-sub-committees` | Subcommittee on Committees | House Administration | — |
| `leg-house-cmte-judiciary-sub-courts-intellectual-property-the-internet` | Subcommittee on Courts, Intellectual Property & the Internet | Judiciary | Courts, Intellectual Property, Artificial Intelligence, and the Internet |
| `leg-house-cmte-judiciary-sub-responsiveness-accountability-to-americans` | Subcommittee on Responsiveness & Accountability to Americans | Judiciary | — |
| `leg-house-cmte-judiciary-sub-weaponization-of-the-federal-government` | Subcommittee on Weaponization of the Federal Government | Judiciary | — |
| `leg-house-cmte-rules-sub-rules-the-organization-of-the-house` | Subcommittee on Rules & the Organization of the House | Rules | Rules and Organization of the House |
| `leg-house-cmte-veterans-affairs-sub-benefits` | Subcommittee on Benefits | Veterans' Affairs | — |
| `leg-house-cmte-ways-means-sub-select-revenue-measures` | Subcommittee on Select Revenue Measures | Ways and Means | — |
| `leg-house-cmte-ways-means-sub-worker-family-support` | Subcommittee on Worker & Family Support | Ways and Means | Work and Welfare |

The 30 Clerk names the graph lacks are in `house_report.subcommittees_not_in_graph`;
beyond the leads above they include the six subcommittees of the Permanent
Select Committee on Intelligence (Central Intelligence Agency; Defense
Intelligence and Overhead Architecture; National Intelligence Enterprise;
National Security Agency and Cyber; Open Source Intelligence; Oversight and
Investigations), Armed Services' "Intelligence and Special Operations",
Foreign Affairs' "Europe" and "South and Central Asia", House
Administration's "Modernization and Innovation", Judiciary's "Oversight" and
Agriculture's "Forestry and Horticulture" — none of which has a curated
node. Adding them is the owner's to do; the pipeline reports them and
publishes nothing about a node that does not exist.

## 6. What the live pages said about the curated names (2026-09-13 brute-force pass)

Thirteen agents each took a shard of the 371 organisations that had no
candidate page, fetched what they could reach, and ran the verifier's own
label test on what they fetched. Their nominations are in
`data/audit/nominations/source-brute1.jsonl` (371 records: 149 nominated,
98 covered by a parent, 47 editorial groupings, 43 with no public page they
could find, 34 not on a .gov host) and were promoted into
`official_sites.json` for the verifier to adjudicate. Along the way they read
pages that contradict a curated name; each is an audit finding in
`data/audit/node_audit.jsonl`, cited to the page as fetched that day (not
committed as a fixture — re-fetch to confirm before renaming). Nothing here
is applied to the base graph.

| Graph id | Curated name | Finding | Claim | Page and the text it carries |
|---|---|---|---|---|
| `exec-ind-nsf-computer-information-science-engineering-cise-computing-communication-foundations` | Division of Computing & Communication Foundations | stale_name / note / likely | NSF's CISE directorate no longer organizes itself into a division called 'Computing and Communication Foundations' (CCF); its current program areas are named differently. | [www.nsf.gov/cise](https://www.nsf.gov/cise) — "Computing and AI Foundations ... Center-Scale and Testbeds ... Cyber, " |
| `exec-ind-nsf-engineering-eng-emerging-frontiers-in-research-innovation` | Division of Emerging Frontiers in Research & Innovation | stale_name / correction / likely | 'EFRI' is a program inside NSF ENG's 'Office of Emerging Frontiers and Multidisciplinary Activities (EFMA)', not a 'Division of Emerging Frontiers in Research & Innovation'; no NSF page names a division by the curated ti | [www.nsf.gov/eng/emerging-frontiers-multi](https://www.nsf.gov/eng/emerging-frontiers-multidisciplinary-activities) — "The U.S. National Science Foundation Directorate for Engineering Offic" |
| `exec-ind-nsf-engineering-eng-chemical-bioengineering-environmental-transport-systems` | Division of Chemical, Bioengineering, Environmental & Transport Systems | stale_name / correction / likely | The curated name 'Division of Chemical, Bioengineering, Environmental & Transport Systems' does not match NSF's current name for this division; NSF's own site redirects the environmental-named URL to an energy-named one  | [www.nsf.gov/eng/chemical-bioengineering-](https://www.nsf.gov/eng/chemical-bioengineering-energy-transport-systems) — "ENG Chemical, Bioengineering, Energy and Transport Systems - Directora" |
| `exec-ind-nsf-mathematical-physical-sciences-mps-mathematical-sciences` | Division of Mathematical Sciences | stale_name / note / likely | The curated name carries a 'Division of' prefix that NSF's current page for this unit does not use. | [www.nsf.gov/mps/mathematical-sciences](https://www.nsf.gov/mps/mathematical-sciences) — "MPS Mathematical Sciences - Directorate for Mathematical and Physical " |
| `exec-dept-ed-region-ix-pacific` | Dept of Education Region IX — Pacific | not_a_real_unit / note / speculative | The Department of Education's current own directory of its offices names all 17 of them and none is a numbered geographic region; ED does not appear to organize itself this way today (unlike HUD, which this node's struct | [www.ed.gov/about/ed-offices](https://www.ed.gov/about/ed-offices) — "Each of ED's 17 offices play a vital role in ensuring students of all " |
| `exec-ind-epa-office-of-research-development-ord` | Office of Research & Development (ORD) | stale_name / note / likely | EPA's own research-hub page no longer names an 'Office of Research and Development' anywhere in its content, and the analogous 'about-office-research-and-development-ord' URL 404s; EPA's About page nav now reads 'Labs an | [www.epa.gov/research](https://www.epa.gov/research) — "Research \| US EPA" |
| `exec-dept-doj-div-enrd` | Environment & Natural Resources Division | stale_name / correction / likely | DOJ's division is now officially titled 'Energy and Natural Resources Division', not 'Environment & Natural Resources Division' as curated. | [www.justice.gov/enrd](https://www.justice.gov/enrd) — "Energy and Natural Resources Division" |
| `exec-ind-nsf-biological-sciences-bio-integrative-organismal-systems` | Division of Integrative Organismal Systems | stale_name / note / likely | No page on nsf.gov names a distinct 'Division of Integrative Organismal Systems' any longer; both the legacy index path (nsf.gov/div/index.jsp?div=IOS) and a guessed direct path (nsf.gov/bio/ios) redirect to the general  | [www.nsf.gov/bio/ios](https://www.nsf.gov/bio/ios) — "Directorate for Biological Sciences (BIO)" |
| `exec-ind-nsf-engineering-eng-electrical-communications-cyber-systems` | Division of Electrical, Communications & Cyber Systems | stale_name / correction / likely | Curated name is 'Division of Electrical, Communications & Cyber Systems', but NSF's own page for this division (div=ECCS) titles itself 'ENG Electrical, Communications and Computing Systems' -- 'Computing', not 'Cyber'. | [www.nsf.gov/div/index.jsp?div=ECCS](https://www.nsf.gov/div/index.jsp?div=ECCS) — "ENG Electrical, Communications and Computing Systems" |
| `exec-ind-nsf-biological-sciences-bio-biological-infrastructure` | Division of Biological Infrastructure | stale_name / note / likely | The BIO directorate's own page does not link or label a 'Division of Biological Infrastructure'; the closest match is a link titled 'Initiatives and Infrastructure', suggesting the division may have been renamed or restr | [www.nsf.gov/div/index.jsp?div=DBI](https://www.nsf.gov/div/index.jsp?div=DBI) — "Initiatives and Infrastructure" |
| `exec-dept-ed-region-ii-new-york` | Dept of Education Region II — New York | stale_name / note / speculative | The Department of Education's own current 'ED Offices' page lists only functional/program offices (OCIO, OCO, OCR, OCTAE, ODS, OELA, OESE, OFO, OGC, OLCA, OPE, OPEPD, OS, OSERS, OUS, Office of the Inspector General) and  | [www.ed.gov/about/ed-offices](https://www.ed.gov/about/ed-offices) — "ED Offices" |
| `exec-ind-nsf-computer-information-science-engineering-cise-information-intelligent-systems` | Division of Information & Intelligent Systems | stale_name / note / likely | NSF's CISE directorate page no longer names a 'Division of Information & Intelligent Systems'; it now describes six current thematic science areas instead, one of which ('Cyber, Physical and Intelligent Systems') is the  | [www.nsf.gov/cise](https://www.nsf.gov/cise) — "CISE is organized around six thematic science areas that support found" |
| `exec-ind-nsf-geosciences-geo-atmospheric-geospace-sciences` | Division of Atmospheric & Geospace Sciences | stale_name / note / likely | NSF's GEO directorate page no longer names a 'Division of Atmospheric & Geospace Sciences'; it now runs a single 'Core Geoscience Research' funding opportunity with an 'Atmospheric and Geospace Sciences (AGS) program' in | [www.nsf.gov/geo/core-geoscience-research](https://www.nsf.gov/geo/core-geoscience-research) — "GEO Core calls for proposals in three programs: Atmospheric and Geospa" |
| `leg-senate-admin-saa` | Sergeant at Arms of the Senate | stale_name / note / likely | The Senate's own page never appends 'of the Senate' to the office name -- it is headed 'About the Sergeant at Arms' and refers to 'the sergeant at arms' throughout, so the curated name 'Sergeant at Arms of the Senate' wi | [www.senate.gov/about/officers-staff/serg](https://www.senate.gov/about/officers-staff/sergeant-at-arms.htm) — "About the Sergeant at Arms" |
| `leg-support-loc-nls` | National Library Service for Blind & Print Disabled | stale_name / note / likely | The Library of Congress's own page spells the unit 'National Library Service for the Blind and Print Disabled (NLS)' -- with 'the' and 'and' -- where the curated name is 'National Library Service for Blind & Print Disabl | [www.loc.gov/nls/](https://www.loc.gov/nls/) — "National Library Service for the Blind and Print Disabled (NLS)" |
| `exec-ind-nsf-computer-information-science-engineering-cise-advanced-cyberinfrastructure` | Division of Advanced Cyberinfrastructure | stale_name / correction / likely | NSF's own page names this unit 'Office of Advanced Cyberinfrastructure', not 'Division of Advanced Cyberinfrastructure' as curated -- a different organizational-level word, not just punctuation. | [www.nsf.gov/cise/office-advanced-cyberin](https://www.nsf.gov/cise/office-advanced-cyberinfrastructure) — "Office of Advanced Cyberinfrastructure" |
| `exec-ind-nsf-technology-innovation-partnerships-tip-convergence-accelerator` | Division of Convergence Accelerator | stale_name / correction / likely | NSF's own page calls this a program, 'Convergence Accelerator', with no 'Division of' prefix and no NSF page found describing it as a division at all. | [www.nsf.gov/funding/initiatives/converge](https://www.nsf.gov/funding/initiatives/convergence-accelerator) — "Convergence Accelerator" |
| `exec-ind-nsf-education-human-resources-ehr` | Education & Human Resources (EHR) | stale_name / correction / likely | The curated parent directorate 'Education & Human Resources (EHR)' appears to have been renamed by NSF to 'EDU' (Directorate for STEM Education); its own divisions are now labelled with an EDU/ prefix, not EHR/. | [www.nsf.gov/edu/drl](https://www.nsf.gov/edu/drl) — "Division of Research on Learning in Formal and Informal Settings (EDU/" |
| `exec-ind-nsf-education-human-resources-ehr` | Education & Human Resources (EHR) | stale_name / correction / likely | The curated name 'Education & Human Resources (EHR)' is stale. NSF's own site now brands this directorate 'Directorate for STEM Education (EDU)', with divisions filed under nsf.gov/edu (EHR's old URL nsf.gov/ehr redirect | [www.nsf.gov/edu](https://www.nsf.gov/edu) — "Directorate for STEM Education (EDU) \| NSF - U.S. National Science Fou" |
| `exec-ind-nsf-technology-innovation-partnerships-tip-directorate-for-tip-programs` | Division of Directorate for TIP Programs | other / correction / likely | The curated node 'Division of Directorate for TIP Programs' (a sub-unit of the TIP directorate named after its own directorate) does not appear to correspond to any real NSF organizational unit; NSF's own TIP page descri | [www.nsf.gov/tip](https://www.nsf.gov/tip) — "TIP comprises three primary strategy areas" |
| `exec-dept-ed-region-v-midwest` | Dept of Education Region V — Midwest | stale_name / note / speculative | ED's own current 'ED Offices' page lists all of the Department's principal offices by name and includes no numbered regional office ('Region V', 'Midwest', or any other), which is consistent with ED having discontinued i | [www.ed.gov/about/ed-offices](https://www.ed.gov/about/ed-offices) — "ED's Operating Structure View ED's organizational charts to learn more" |
| `exec-ind-nsf-education-human-resources-ehr-human-resource-development` | Division of Human Resource Development | stale_name / correction / likely | This node's parent, 'Education & Human Resources (EHR)', appears to have been renamed by NSF: the fetched page for org group 17 (formerly EHR's org id) carries the title 'Directorate for STEM Education (EDU) \| NSF - U.S. | [www.nsf.gov/dir/index.jsp?org=EHR](https://www.nsf.gov/dir/index.jsp?org=EHR) — "Directorate for STEM Education (EDU) \| NSF - U.S. National Science Fou" |
| `exec-dept-doj-usao` | U.S. Attorneys Office (USAO — 94 Districts) | stale_name / correction / likely | The Department of Justice does not call this unit 'U.S. Attorneys Office (USAO — 94 Districts)'; its own site names the collective 'Offices of the United States Attorneys' / 'U.S. Attorneys' with no '(USAO)' abbreviation | [www.justice.gov/usao](https://www.justice.gov/usao) — "U.S. Attorneys \| Offices of the United States Attorneys" |
| `jud-support-fpd` | Federal Public Defender Offices (82) | count_mismatch / correction / likely | The curated name states '(82)' federal public defender offices, but the U.S. Courts' own Defender Services page states a different, larger figure and a different unit of count: 83 authorized federal defender organization | [www.uscourts.gov/about-federal-courts/de](https://www.uscourts.gov/about-federal-courts/defender-services) — "Today, there are 83 authorized federal defender organizations. They em" |

The pattern worth reading across the rows: NSF reorganised in 2025 and its
site no longer names most curated "Division of …" units under those names
(CISE, GEO, BIO, ENG each now describe program areas); the Department of
Education's own office list carries no numbered regions; DOJ's ENRD is now
"Energy and Natural Resources Division". These are the largest single sources
of the remaining `not_found` and `inconclusive` records, and they are curation.

## 7. Pay sources: what is priced, what is blocked, what is structurally out of reach (2026-09-14)

Following the salary work in `judicial_pay.py`, `congressional_pay.py` and
`whitehouse_pay.py`, this is the standing account of which official pay
sources can reach a node and which cannot, so the analysis is not redone.
**23 of 4,382 position nodes carry a rate of pay from a primary source**: 15
judicial, 3 congressional, 5 White House Office.

### 7.1 Blocked on one allowlist entry — three House leadership nodes

`uscode.house.gov` answers the proxy's CONNECT with 403 (see
`docs/NETWORK_ACCESS.md` §1b). It serves 5 U.S.C. § 5332 Schedule 6, which
states the statutory salaries of congressional leadership. Once the host is
reachable, three curated nodes become priceable by a module that would be a
near-clone of `congressional_pay.py`:

| Node | Post | Schedule 6 rate |
|---|---|---|
| `leg-house-leadership-speaker-of-the-house` | Speaker of the House | $223,500 |
| `leg-house-leadership-majority-leader` | Majority Leader | $193,400 |
| `leg-house-leadership-minority-leader` | Minority Leader | $193,400 |

These cannot be priced from the Senate's own salary page, which is what
`congressional_pay.py` reads: its footnote names only the three **Senate**
leadership roles.

**The other 15 House leadership nodes must stay unpriced**, and that is a
finding, not a gap. The whips, the caucus and conference chairs, the Freedom
Caucus and Problem Solvers chairs receive **no separate statutory personal
salary** — a Member who holds one of those posts is paid the Member rate.
Neither is a committee chair separately compensated. Nothing should price
them.

### 7.2 Reaches zero nodes, despite a clean statutory rule

28 U.S.C. § 153(a) sets a full-time bankruptcy judge at 92% of the
district-judge rate — $229,908 at the 2026 rate — and 28 U.S.C. § 634(a)
caps a full-time magistrate judge at the same 92%, with the Judicial
Conference fixing the actual figure. Neither reaches a node: **every
bankruptcy and magistrate node in this graph states a multiplicity**
(`Bankruptcy Judge (×12)`, `Magistrate Judge (×13)`, `(×varies)`), and the
multi-post rule refuses them all. Splitting those into individually named
seats is curation; until then there is nothing for the rule to price.

28 U.S.C. § 172(b) (Court of Federal Claims) and § 252 (Court of
International Trade) give those judges the district-judge rate, and
`jud-specialized-tax-chief-judge-tax-court` is a single-post node — but the
statutory text is on `uscode.house.gov`, blocked as above.

### 7.3 Structurally out of reach — the graph carries no pay key

Three whole categories of official pay table cannot reach any node in this
graph, for one shared reason: **the curated file records no pay grade, no SES
status and no GS grade/step/duty station on any node.** Matching a node to a
row would mean guessing which row it is, which is the inference this project
refuses everywhere else.

| Source | What it states | Why it cannot reach a node |
|---|---|---|
| DFAS military basic pay tables | pay grade × years of service; O-7 to O-10 capped at Executive Schedule Level II ($18,999.90/month in 2026) | Pricing `Chief of Staff, U.S. Army` requires asserting the post is an O-10 with *n* years of service. No curated field says so. (`www.dfas.mil` is also proxy-blocked.) |
| OPM SES salary table | two national bands — $151,661–$228,000 certified, $151,661–$209,600 not — under 5 U.S.C. §§ 5382 and 5307(d) | It is two ranges, not a per-agency or per-post figure, and nothing records which nodes are SES. |
| OPM GS and locality tables | grade × step × locality | The best-formatted federal pay data there is, and useless here: no node carries a grade, a step or a duty station, and a title string is not a grade. |

The narrow DOJ sources are real but tiny: the U.S. Trustee Program states
$197,200 for a U.S. Trustee and $135,000–$197,100 for an Assistant U.S.
Trustee (`www.justice.gov` answered 401 on 2026-09-14), and the USAO
Administratively Determined pay plan states grade/experience ranges rather
than a post's rate.

### 7.4 The White House Office was a sketch — expanded from its own roster (2026-09-14)

**Resolved.** `scripts/expand_whitehouse_office.py` rebuilt the subtree from
the report itself: **27 nodes -> 249**, and the pay module went from **5
priced to 166**. The script is the only writer of that subtree (the curated
file is never hand-edited), it is idempotent, and it never renames, re-types
or removes a curated node.

One node per distinct title the report prints: 168 single-post nodes, and 54
standing for a title several people hold, carrying the report's own count as
`representsPosts` — the convention the curated file already used for "Deputy
Press Secretary (x2)". Deliberately not N separate nodes, because the report
distinguishes those people by name and this project does not publish names.

Each added node carries `structureSource: listed_in_whitehouse_staff_report`
and `descriptionSource: generated_from_whitehouse_staff_report`, and its
description states only what the roster says — the title and the rate, never
duties, which the report does not give. That makes these the first nodes in
the graph whose *structure* is sourced rather than curated or templated.

The 16 curated nodes whose titles the 2026 report does not print are left
exactly as they were. The report not carrying a title is not evidence the
post does not exist, and deleting a curated node on that basis would be a
claim this script cannot support. They remain unpriced.

### 7.5 What is still out of reach

After the expansion, **166 of the 249** White House Office positions carry a
rate. The rest are refused, each for a reason worth keeping:

- **54 stand for several posts.** A title the report lists several people
  under gets one node and no rate: the salaries differ, and one figure on
  such a node would read as what a single holder is paid.
- **21 curated nodes the report does not print.** `Chief Speechwriter`,
  `Director of Presidential Personnel`, `Director of Public Liaison`,
  `Director of Strategic Communications`, `Director of Scheduling & Advance`,
  `Director of the White House Situation Room` and `Deputy Chief of Staff for
  Implementation` among them. These are the curated sketch nodes that predate
  the expansion; the 2026 roster carries no title matching them, which is not
  evidence they are wrong.
- **7 are listed at $0.00** — uncompensated appointees, the National Security
  Advisor among them. Ten of the report's 408 rows read $0.00. That is a fact
  about the arrangement one person has, not about the post, and zero is never
  published here as an amount.
- **1 title is held by several people under a name a curated node also
  carries**, so which salary is the node's is undecidable.

The remaining lever on this subtree is not parsing but the report's own
reissue: a fresh July roster replaces every figure, and titles that gain or
lose a second holder change category.

## 8. Post titles the government's own pages do not carry (2026-09-15)

Found by the first run of the position existence pass. The verifier now
checks each post against its organisation's page, so for the first time the
curated titles were compared against what the pages actually say — and the
most recognisable posts in the federal government came back `inconclusive`,
not because the pages are silent about them but because **the graph calls
them something no page will ever say.**

839 position nodes contain their parent organisation's full name verbatim.
That is template output, and in 28 of them it produces a title that is
wrong rather than merely verbose: every cabinet department except Defense
carries a `Secretary of Department of <full department name>` node and a
`Deputy Secretary of ...` beside it.

`scripts/probe_post_titles.py` is the read-only probe that produced the
evidence below. It fetches an organisation's page, reports which curated
post titles the page labels, and lists office-looking labels on the page
that no curated post matches. It writes nothing.

    Department of Energy — https://www.energy.gov/leadership-organization
      not labelled          'Secretary of Department of Energy (DOE)'
      not labelled          'Deputy Secretary of Department of Energy (DOE)'
      on the page, no node  'Secretary of Energy' [navigation]
      on the page, no node  'Deputy Secretary of Energy' [navigation]
      on the page, no node  'Under Secretary for Science' [content]
      on the page, no node  'Under Secretary for Nuclear Security and NNSA Administrator' [content]

    Department of Justice — https://www.justice.gov/about
      not labelled          'Secretary of Department of Justice (DOJ)'
      not labelled          'Deputy Secretary of Department of Justice (DOJ)'
      on the page, no node  'The Attorney General' [navigation]

The DOJ pair is the sharpest case: **there is no Secretary of Justice.** The
head of the Department of Justice is the Attorney General and the second is
the Deputy Attorney General, and justice.gov says so on the page the
verifier read. The graph asserts an office that does not exist, and has
since the curated file was written.

**Resolved for 15 of the 28, the same day.**
`scripts/rename_templated_post_titles.py` is the only writer of these names
(the curated file is never hand-edited), it is idempotent, and it renames
nothing it cannot cite. The replacement is never produced by string surgery
-- dropping "Department of" is right thirteen times and wrong once, and the
once is DOJ. It comes from OPM's PLUM archive, or, where the archive carries
only a bare "SECRETARY", from the department's own page:

    Secretary of Department of Justice (DOJ)      -> Attorney General            [archive]
    Deputy Secretary of Department of Justice     -> Deputy Attorney General     [archive]
    Secretary of Department of State              -> Secretary of State          [archive]
    Deputy Secretary of Department of State       -> Deputy Secretary of State   [archive]
    Secretary of Department of Labor (DOL)        -> Secretary of Labor          [archive]
    Deputy Secretary of Department of Labor       -> Deputy Secretary of Labor   [archive]
    Secretary of Department of Veterans Affairs   -> Secretary of Veterans Affairs        [archive]
    Deputy Secretary of Dept of Veterans Affairs  -> Deputy Secretary of Veterans Affairs [archive]
    Secretary of Department of Homeland Security  -> Secretary of the Department of Homeland Security     [archive]
    Deputy Secretary of Dept of Homeland Security -> Deputy Secretary of the Department of Homeland Security [archive]
    Deputy Secretary of Department of Energy      -> Deputy Secretary of Energy  [archive]
    Secretary of Department of Energy (DOE)       -> Secretary of Energy         [energy.gov]
    Deputy Secretary of Department of Agriculture -> Deputy Secretary of Agriculture [archive]
    Deputy Secretary of Department of the Interior-> Deputy Secretary of the Interior [archive]
    Deputy Secretary of Dept of the Treasury      -> Deputy Secretary of the Treasury [archive]

Note DHS: OPM's own archive spells it "SECRETARY OF THE DEPARTMENT OF
HOMELAND SECURITY", keeping the words a transform would have stripped. It is
the second proof that the replacement must be cited rather than computed.

**The immediate payoff, measured.** Re-verifying just those 15 nodes
confirmed **5** against their departments' own pages, which was structurally
impossible while they were misnamed: Secretary of Labor (dol.gov), Secretary
and Deputy Secretary of Energy (energy.gov), Secretary and Deputy Secretary
of Veterans Affairs (va.gov). Confirmed positions went 20 -> 25.

**Still templated: 13, because no official source in hand names the title.**
Commerce, Education, Transportation, HHS and HUD (both posts each), and the
Secretary side of Agriculture, the Interior and the Treasury. The archive
files those heads as a bare "SECRETARY", which names the role and not the
post and is refused; and seven of the fifteen department pages
(www.dhs.gov, www.commerce.gov, www.transportation.gov, www.ed.gov,
www.hhs.gov, www.usda.gov, www.state.gov) answer `robots.txt` with 401/403
and are refused by policy. "Secretary of the Treasury" is not in doubt as a
matter of fact; it is in doubt as a matter of what this repository can cite,
and the rule that the name must be cited is the rule that caught DOJ.
Defense is the control case: it alone was already correct, and it is the only
department whose curated title could ever have matched.

**What must not happen, and why it is written down here rather than left to
judgement.** The temptation is to widen the matcher until "Secretary of
Department of State" matches "Secretary of State" — drop a "Department of"
the way the committee fold drops a "Committee on". It is the same shape of
fix and it is not the same thing. The committee fold is granted by the
node's type, folds a closed set of scaffolding words that a chamber's own
site demonstrably omits, and refuses a core of fewer than two tokens. A
"Department of" fold would instead let a node's name differ from the page's
label in a way that changes **which office is meant**: it would confirm the
non-existent "Secretary of Justice" from the page's "Attorney General" only
if the fold were loose enough to be useless, and short of that it would
still teach that a curated name and a real title need not agree. The same
looseness is what once let "Office of Science" match "Office of Science and
Technology Policy". The matcher stays strict, the verifier keeps recording
`inconclusive`, and the names get fixed where names are fixed.

Two departments could not be probed at all: `www.state.gov` and
`www.ed.gov` answer `robots.txt` with 401/403, which this project treats as
a refusal (see CLAUDE.md on RFC 9309). That is a fact about the network, not
about the titles.

## 9. Organisation names the government's own pages do not carry (2026-09-19)

§8 did this for post titles. This is the same finding one level up, and it
was the largest single blocker left on verification coverage.

A 2026-09-18 pass over every organisation with no candidate page established
that the binding constraint is **not a missing URL**. For 181 organisations
the page was read, reads fine, and simply does not carry the name this graph
uses. No other URL fixes that: it is a curated-name problem, and the fix is a
rename argued from the page's own wording — never a loosening of the matcher,
for the reason §8 gives at length.

Ten agents read those 181 nodes' pages with `scripts/probe_candidate_pages.py`
and proposed or refused each. They returned **107 proposals and 74 refusals**,
and they were told a refusal is a result. Every proposal was then re-tested
independently against the live page with the verifier's own label test, and
the curated name re-tested beside it: **64 of the first 65 confirmed, and the
curated name was genuinely not labelled in every one**, so the premise held
rather than being inherited.

**69 renames applied; 39 proposals declined.** `data/curation/unit_renames.json`
is the reviewed table and `scripts/rename_units_to_official_wording.py` is its
only writer — the curated file is never hand-edited. The table is the same
shape as `TREASURY_ROW_ALIASES` and `USASPENDING_NAME_ALIASES`: a reviewed
identification with the basis written beside it, and re-checked against the
source rather than trusted. **The table proposes; the page decides.** Every
row is re-fetched and re-tested on every run, so a row cannot go stale
silently, and the script refuses a row whose node no longer carries the name
the row was written against.

### 9.1 What the renames actually were

Four kinds, and they are worth keeping apart because they carry different risk.

**The graph's own typography, not a different name** (8). The curated file
writes `<ACRONYM> — <Name>`, which no page carries. `canonical_name_key` drops
parentheticals, so moving the acronym into brackets keeps it *and* confirms —
strictly better than the bare form the agents proposed, and checked before
being relied on:

    NIST — National Institute of Standards & Technology
        -> National Institute of Standards and Technology (NIST)
    S.D.N.Y. — Southern District of New York
        -> Southern District of New York (S.D.N.Y.)
    Substance Abuse & Mental Health Services Admin (SAMHSA)
        -> Substance Abuse and Mental Health Services Administration (SAMHSA)

**A rename the agency itself states** (3). Not a wording difference: the graph
is stale about a real rename, and the agency's own page says so.

  - `National Renewable Energy Laboratory` → **National Laboratory of the
    Rockies (NLR)**. energy.gov states it in its own words: "The National
    Laboratory of the Rockies (NLR), formerly known as the National Renewable
    Energy Laboratory (NREL), is a U.S. Department of Energy (DOE) national
    laboratory".
  - `Food & Nutrition Service (FNS)` → **Food and Nutrition Administration
    (FNA)**. fns.usda.gov labels itself so throughout, with FNA as its
    abbreviation, over the same SNAP/WIC/school-meals programmes.
  - `Education & Human Resources (EHR)` → **Directorate for STEM Education
    (EDU)**. The page states the rename: "EDU was formerly the Directorate of
    Education".

These three were the ones most worth checking directly rather than accepting,
because an agent proposing "the lab is now called something else" is exactly
where a confident error would do most damage. All three were read at source
before being applied. Note which way the check ran: the prior belief that
NREL is NREL was the stale thing, not the agent.

**A garbled curated name** (6). `Senate Committee on Select Committee on
Intelligence` stacks the graph's scaffolding in front of a name that already
contains "Committee on", which is why the committee fold reduces it to one
token and can never match; `Investigations & Subcommittee on Permanent
Investigations` duplicates half of itself; `Division of National Center for
Science & Engineering Statistics` prefixes "Division of" to a National Center.

**A seat the chamber has since renamed** (31, all committees and
subcommittees), each argued from the parent committee's own complete listing
or from the Senate and House Clerk lists already committed under
`tests/fixtures/directories/`. Two of these retire a standing
`not_in_official_list` negative the site publishes today: `Competition Policy,
Antitrust & Consumer Rights` is the Senate's `Antitrust, Competition Policy,
and Consumer Rights` reordered, and `House Committee on Oversight &
Accountability` is the Clerk's `Oversight and Government Reform` — both
already recorded in §5.7 as names the official lists spell differently.

**The remaining 21** are EPA's ten regions and five courts of appeals, below.

### 9.2 EPA's regions: the qualifier is EPA's, not the graph's

All ten regions were renamed from roman to arabic numerals, which is EPA's own
numbering. The qualifier moved too, and that is the more careful half: because
`canonical_name_key` **drops parentheticals, the qualifier is never checked
against anything**. Keeping the graph's own word in brackets would ride along
unverified, so EPA's is used instead — which corrected two:

    EPA Region VII — Plains      -> EPA Region 7 (Midwest)
    EPA Region VIII — Mountain   -> EPA Region 8 (Mountains and Plains)
    EPA Region IX — Pacific      -> EPA Region 9 (Pacific Southwest)

Region 8 is also what surfaced a false positive in this repository's own count
rule, fixed with it: `states_a_count_in_prose` read "EPA Region 8 (Mountains
and Plains)" as "8 ... Mountains", a count of mountains, and refused the name
before any fetch. A bracket is a segment of its own for the same reason the
dash is, and the fix changes the verdict on **no name in the curated file** —
it is what lets an agency's own bracketed qualifier be proposed at all. Pinned
both ways in `tests/test_verification.CountLabelFloorTests`.

### 9.3 The courts of appeals: five of eleven, and the family kept

The only thing blocking all eleven numbered circuits is the numeral: the graph
writes `9th`, the courts write `Ninth`. The minimal edit keeps the graph's
family form intact, and it was tested against all eleven rather than assumed:

    confirm the family form  ->  2nd, 4th, 5th, 7th, 9th   (renamed)
    label only a short form  ->  1st, 3rd, 6th, 8th, 10th, 11th   (left alone)

The six left alone label themselves only `Sixth Circuit` or `Eighth Circuit
Court of Appeals`. Adopting those would break the family convention across
thirteen sibling nodes to confirm six, and `First Circuit` is two generic
tokens besides. Five renames and six principled refusals is the honest split;
the refusals are not a coverage failure but a statement about what those
courts' own sites print.

### 9.4 The 39 proposals declined, and why

  - **HUD's ten regions** (10). HUD's Field Leadership page names each region
    by headquarters city — `Region VIII - Denver` — and the match requires
    dropping the `HUD` the graph uses to keep its regions apart from EPA's and
    Education's identically numbered ones. A family decision that trades ten
    nodes' disambiguation for ten confirmations; left to the owner.
  - **VA's VISNs** (6). Proposed as bare `VISN 17` / `VISN 08`, matching only
    in site-wide navigation. Refusing them was right for a better reason than
    the one given at the time: the whole subtree was superseded, not misnamed.
    The VA consolidated eighteen networks into five under RISE; the eighteen are
    now marked superseded and kept, five current ones sit beside them, and the
    parent is renamed. §10 carries the evidence, the three passes it took to
    establish it, and the corrections to this document's own claims along the
    way. `VISN 4 — VISN 4` is moot: that node is one of the superseded eighteen.
  - **NSF's divisions** (9). `MPS Chemistry`, `ENG Civil, Mechanical, and
    Manufacturing Innovation`, `Earth Sciences (EAR) program`. The redesigned
    nsf.gov carries no "Division of" anywhere, but what it carries instead is
    its own site-section labelling, not the unit's name — and "program"
    mis-types a division. NSF's *directorates* were renamed (§9.1) because
    `Directorate for Geosciences (GEO)` is a formal name; its divisions were
    not, because `MPS Chemistry` is a breadcrumb.
  - **A bare generic title** (5). `Inspector General` for the House OIG,
    `Chaplain`, `Environment`, `Sergeant at Arms`, `Library of Congress` for
    the AOC's buildings node. The first is the sharpest: `Inspector General`
    names 72 nodes here and every `.gov` footer carries those words, which is
    exactly the furniture match CLAUDE.md records the navigation rule refusing
    18 times. The script refuses these by rule (`GENERIC_NAMES`, and a
    two-token floor), not by taste.
  - **A bare acronym** (1). `USSOCOM` is one token, and `Special Operations
    Command (USSOCOM)` does not match, so the refusal is on the evidence
    rather than on the convention.
  - **Positional inference only** (1). The CIA's five directorates are named on
    cia.gov and four match; the fifth is proposed as `Directorate of Mission
    Systems` because it is what is left over. The page states no rename. That
    is an argument from arithmetic, not from the page, and the agent marked it
    speculative.
  - **A stale or undecidable source** (7). One rests on an archived
    118th-Congress block; one moves maritime jurisdiction the page does not
    confirm; the rest are groupings no page names.

### 9.5 The guard that earned its place

`Subcommittee on Energy` was refused on the first pass because the House
Science Committee already has one. That refusal was **too strict and the rule
was changed, not the row**: the House and the Senate each name a subcommittee
after the appropriations bill it writes, so `Agriculture, Rural Development,
Food and Drug Administration, and Related Agencies` is the true name of two
seats in two chambers. The collision guard is now scoped to siblings, where an
ambiguity is real, and the cost of allowing a cross-parent duplicate is stated
rather than hidden: a source matched by name alone refuses a name reaching two
nodes, so a duplicate can lose a node an unrelated match. It fails safe — a
refusal, never a figure attributed to the wrong unit.

Two rows were refused on the first run for serving below the readable-text
floor (judiciary.senate.gov served 0 characters; ca4.uscourts.gov 263) and
applied on the next, one of them from the court's `/judges` page instead. That
is the re-check doing its job rather than a fact about those courts.

### 9.6 What the renames cost, measured rather than assumed

A rename is not free: every source this project matches by name was re-run
against the new names, and the counts moved in both directions.

    House Clerk committee list   18 -> 20 matched   (both renamed to the Clerk's own wording)
    OPM FedScope headcounts     133 -> 136 records  (+4, -1)
    OPM PLUM archive positions  126 -> 129 records  (+4, -1)
    USAspending File A          two aliases retired, both upgraded

The gains are the graph's `<ACRONYM> — <name>` typography going away: NIST,
USPTO, SAMHSA and USAGM had been unmatchable by every name-keyed source at
once, and now match all of them.

Two USAspending aliases were **deleted rather than updated**. `USPTO` and
`USAGM` were held at `partial` by an alias recording that two spellings meant
one unit; after the rename the names reduce to the same canonical key, so the
records now apply by name equality and are graded `verified`. That is an
upgrade the *names* earned, not one an alias could — writing an alias down has
never been allowed to buy `exact`.

**The one loss is real and is not aliased away.** The Food and Nutrition
Service lost its FedScope headcount record and its Administrator lost a PLUM
record, because both of OPM's files are from March 2025 and September 2024 and
still name the bureau the Food and Nutrition Service. The alternative was to
leave the graph stale about a rename USDA states on its own site, which is
worse: the node now reads as the government reads it, and one official dataset
has not caught up. A second alias mechanism was not built for one record.
Expect this shape again — a correctly adopted rename will strand older datasets
until they are refreshed.

The PLUM matcher also reports two new *ambiguous* organisations, both the
USPTO's: the archive files rows under `PATENT AND TRADEMARK OFFICE` and
`UNITED STATES PATENT AND TRADEMARK OFFICE`, and both now reduce to the node's
key, so neither is attributed. Before the rename neither matched at all, so the
outcome is unchanged — and it fails the safe way, as a refusal rather than a
row attributed to the wrong unit.

## 10. The VA's networks: five, and what it took to establish that (2026-09-19)

This section was written three times in one day and the rewrites are the record
worth keeping, because each one was wrong in a way the next one caught.

**First pass — asserted.** A probing agent read
`department.va.gov/integrated-service-networks/` and reported that the VA "now
states it comprises 5 Veterans Integrated Service Networks where the graph
carries 18". That went into `CLAUDE.md` and into this file as settled fact, and
was reported upward as the largest open correctness problem.

**Second pass — retracted.** Checked directly, the same page that carries that
sentence carries, in its own navigation, **eighteen** VISN entries (VISN 01, 02,
04, 05, 06, 07, 08, 09, 10, 12, 15, 16, 17, 19, 20, 21, 22, 23). Every
per-network sub-page fetched returned the identical 3,308 characters — the index
itself. One page saying both things is not a settled fact, so the claim was
withdrawn and nineteen nodes were not restructured.

**Third pass — settled, at five.** The retraction was right to refuse the first
pass's evidence and wrong to stop there. Three things settle it, none of which
was on that page:

  - **A second VA host, on a different system.** `digital.va.gov/rise/` (last
    updated 2026-09-16) prints **"5 VISN MAP (CAPTURE AREA BY STATE)"** beside
    **"18 HEALTH SERVICE AREA (HSA) MAP CROSSING STATE LINES"**, and describes
    the change as RISE — the Restructure for Impact and Sustainability Effort.
    `digital.va.gov/rise/leadership/` (dated 2026-07-14/15) carries exactly five
    networks, each with a named Network Director, subdivided into eighteen Health
    Service Areas with named Executive Directors. That is an operational staffing
    roster, not a proposal.
  - **The old pages were retired deliberately, and the status codes prove it.**
    All eighteen former slugs return **301 Moved Permanently** to the index,
    while an invented slug (`visn-99-nonexistent`) returns **404**. A catch-all
    would 200 or 404 both; a 301 on exactly the eighteen real ones is an
    editorial act. This is the discriminator the second pass missed by reading
    the served content and never the status code.
  - **The five territories are a complete partition.** The state lists for VISN
    1-5 contain the fifty states plus DC, Puerto Rico, the U.S. Virgin Islands,
    American Samoa, Guam and the Northern Mariana Islands, with no gaps and no
    duplicates. A stale fragment does not partition the United States exactly.

So the contradiction is **stale navigation, not an error**: VA's menu and its
sitemap are two symptoms of one un-regenerated site, and the body text is
current.

### 10.1 What was done

Nothing was deleted. The eighteen numbered networks keep their ids, names,
descriptions and every source they ever earned, and are marked
`lifecycle: superseded` by `scripts/mark_superseded_units.py`, quoting the VA's
own sentence. The site does not draw them unless the reader ticks "also show
units the government has replaced". Five current networks — `VISN 1` through
`VISN 5` — were added by `scripts/add_curated_nodes.py` under the
`official_page_label` licence, because the VA's page labels each of them in its
content. The parent, whose name stated a count the VA no longer reports (and
which, because it stated a count, `uncheckable_reason` refused before any fetch,
so it could never have earned a source), is renamed to the VA's own heading,
**Veterans Integrated Service Networks**.

`supersededBy` is empty on all eighteen, deliberately. The territories were
redrawn rather than renumbered, so no old network maps onto one new one, and
naming a successor for each would invent a correspondence no source states. The
date recorded is 2026-07-14, the earliest dated official artefact showing the new
structure staffed; **VA has published no single effective date**, and the RISE
FAQ says placement below Network Director level is still ongoing.

### 10.2 Three corrections to this repository's own claims

  - `CLAUDE.md` and this file both said the parent carried **nineteen** children
    and called that the graph disagreeing with itself. It carried **eighteen**,
    matching its own name. The "inconsistency" was mine, asserted twice without
    counting, and it was doing work in the argument.
  - The VA is not the only place "18" appears: the new structure has **eighteen
    Health Service Areas**, numbered 1.1 to 5.5, unrelated to the eighteen old
    VISN numbers. Anyone reconciling these later will meet 18 twice meaning two
    different things.
  - No statute fixes the number. Title 38 refers to "each" VISN generically and
    never states a count, which is why no Federal Register notice announced the
    change — it is administrative. (38 U.S.C. §7309A, guessed at as the relevant
    section, is "Office of Patient Advocacy" and has nothing to do with it.)

### 10.3 Named, but not adopted

VA names the new networks **by number only**. The single regional name found on
any official page is "Pacific West", in prose on the RISE homepage describing
VISN 5's director. No regional name exists for VISNs 1-4, and none is invented
here — the old names the graph carried (New England, Capitol Health Care
Network, Sunshine, Desert Pacific) all belong to the superseded eighteen and none
attaches to a new network.


## 11. Interest on the Public Debt, and what leaving a line unmatched cost (2026-09-19)

`docs/EXACT_NODE_COSTS.md` worked through all 78 of Table 5's section totals
and set 17 aside as "Treasury's own funds and groupings" — lines that name no
organisation, so no node should carry them. Interest on the Public Debt was
one. That reasoning is half right and the missing half was expensive.

A line that names no organisation still reports real money, and the cascade
has to do *something* with it. What it did was apportion $1.267 trillion among
the Treasury bureaus that had no measured line of their own, by the best
evidence those siblings carried — their headcounts. The result was live on the
site:

    Alcohol & Tobacco Tax & Trade Bureau   ~500 staff    $287,134,993,850
    Financial Crimes Enforcement Network   ~350 staff    $200,994,495,695
    Office of Foreign Assets Control       ~250 staff    $143,567,496,925
    Office of Financial Research           ~200 staff    $114,853,997,540

Each is exactly its curated headcount times $574,269,987.70. TTB was published
at more than the measured Internal Revenue Service.

The node added is **not** an organisation and does not claim to be: it is typed
`Treasury accounting line`, the type the exporter already gives the receipts
lines it creates, and it is drawn and keyed as a line. What it does is stop the
money being divided among units, which is the only thing wrong with leaving it
out. After: TTB $268.6M, FinCEN $188.0M, OFAC $134.3M, OFR $107.5M — figures a
bureau of a few hundred people could plausibly spend.

**53 of 5,426 nodes changed**, the four above and the rest by rounding.

The general lesson, which applies to the other sixteen set-aside lines: "this
line names no organisation" is a good reason not to put it on an organisation,
and not a reason to leave it out of the tree. Anything inside a parent's total
that no child carries is apportioned to the children that remain. The other
sixteen should each be checked for the same effect rather than assumed benign.

## 12. The two answers to "is there an actual difference" (2026-09-19)

Two suspected curation defects, checked against primary sources rather than
pattern-matched. Neither turned out to be what it looked like.

### 12.1 The Council of Economic Advisers' two identical members — not a duplicate

`exec-eop-cea-member-cea` and `exec-eop-cea-member-cea-1` are byte-identical
apart from the id suffix, and they are the curated file's **only** sibling name
collision. That looks like an accident. It is not.

15 U.S.C. §1023(a)(2), fetched from `uscode.house.gov` on 2026-09-19, states
verbatim:

> "The Council shall be composed of three members, of whom— (A) 1 shall be the
> chairman who shall be appointed by the President by and with the advice and
> consent of the Senate; and (B) 2 shall be appointed by the President."

So the graph's `Chair, CEA` plus two `Member, CEA` is **structurally correct**:
three members, one of them the chairman. The two Member nodes are two real,
distinct seats. What is wrong is only that nothing tells them apart — and
nothing can, because the statute does not distinguish them either.

The graph already has the right shape for exactly this: `representsPosts`, used
for a title several people hold. Collapsing the two into one `Member, CEA (×2)`
would keep the statutory count at three, remove the only sibling collision, and
say honestly that the two seats are indistinguishable. It needs a writer this
repository does not yet have — no sanctioned script collapses two curated nodes
into one with a multiplicity — so it is recorded here rather than done.

**A second, worse finding on the same node, which nobody was looking for.** The
Council of Economic Advisers' own description reads "Provides economic analysis
and forecasting to the President. **Three Senate-confirmed members.** ~30
staff." The statute above says only the **chairman** is confirmed by the Senate;
the other two are appointed by the President alone. The site publishes that
sentence today as uncited prose, and it is false. Fixing it needs the same
missing machinery — nothing here writes a curated description — which is itself
worth noting: of the five sanctioned writers, none can correct a wrong sentence.

### 12.2 House Committee on Education & the Workforce — a disagreement between two official sources, not a stale name

The House Clerk's committed committee list spells this committee "Education and
Workforce"; the graph says "House Committee on Education & the Workforce". The
difference is the word "the", which `canonical_name_key` does not fold, so the
Clerk's list records the node as one it does not carry.

Renaming to the Clerk's spelling was proposed, with a measured gain: committees
matched 20 → 21 and subcommittees 81 → 84. It is refused, because the
committee's **own site** disagrees with the Clerk. Probed on 2026-09-19,
`edworkforce.house.gov` labels itself, verbatim:

> "Committee on Education & the Workforce | Republicans"

and the node is already confirmed against it through the committee fold. So the
rename would trade a confirmation from the committee's own page for a listing in
the Clerk's administrative index — and would have the graph call the committee
something its own website does not.

A committee's own site is the better authority for its own name. The
disagreement is real, it is the Clerk's abbreviation rather than the graph being
stale, and §5.7 already records it as one of the names the official lists spell
differently. No action.

## 13. What the Government Manual says the graph is missing (2026-09-20)

`data_pipeline/verification/govman.py` matches the United States Government
Manual's agency entries to curated organisations by canonical-name equality,
one entry to one node or nothing. 136 of the Manual's 231 agency entries reach
a node. **95 do not**, and since the Manual is the government's own handbook
of itself, an agency it carries that this graph does not is worth writing
down. Nothing below is applied: this section proposes, as §5 and §9 do.

The 95 split three ways, and only the third is curation work.

### 13.1 Four are the graph's own abbreviation, and renaming them gains nothing here

The graph writes `Admin` where the Manual writes `Administration`, and `&`
where it writes `and` — the same class `unit_renames.json` exists for:

| The Manual's name | The curated name |
|---|---|
| Federal Motor Carrier Safety Administration | Federal Motor Carrier Safety Admin (FMCSA) |
| National Highway Traffic Safety Administration | National Highway Traffic Safety Admin (NHTSA) |
| Pipeline and Hazardous Materials Safety Administration | Pipeline & Hazardous Materials Safety Admin (PHMSA) |
| National Telecommunications and Information Administration | National Telecommunications & Information Admin (NTIA) |

`canonical_name_key` already folds `&` to `and` and drops the parenthetical,
so the only thing keeping these apart is `Admin`/`Administration`.

**They are not proposed for renaming on this evidence**, because the reason to
rename must be the agency's own wording and the payoff must be real, and here
the payoff is zero: **all four entries carry no eligible leadership rows at
all**, so confirming the name would confirm no post. Whether the expansion
helps the USAspending or FedScope joins is a separate question this pass did
not measure, and it is not asserted.

### 13.2 Some are a distinction this file already records, not a gap

The Manual carries `Department of the Air Force`, `Department of the Army` and
`Department of the Navy`; the graph carries `U.S. Air Force`, `U.S. Army` and
`U.S. Navy`. §5 already records the same split for FedScope's `DEPARTMENT OF
THE ARMY` — the first is a civilian department, the second the uniformed
service, and they are different populations. `Defense Agencies` and `Lower
Courts` are the Manual's own grouping headings, the way "Other Defense Civil
Programs" is a Treasury grouping; the graph groups the same units differently
and neither is wrong.

### 13.3 Genuine gaps: units the Manual carries and this graph has no node for

**Adjudicated and applied on 2026-09-20.** The list below was the first pass.
All 48 Manual entries with a mapped ancestor were then put through two rounds —
one agent to decide, a second instructed to overturn — and **26 were added** by
`scripts/add_curated_nodes.py` under the new `government_manual_entry` licence,
which checks the Manual's own hierarchy as well as the name. The second round
earned its place: it found that NOAA, NTIA, DARPA, NSA and FMCSA are all
already in the graph under acronyms, that a substring probe for "ntis" matches
51 `Scientist` posts, and the Bureau of Indian Education case in §13.5 below.

Added (26): Bureau of Industry and Security, Minority Business Development
Agency and the National Technical Information Service under Commerce; the
United States Naval Academy under the Navy; the Defense Commissary, Legal
Services and Security Cooperation Agencies, the National Intelligence,
National Defense and Uniformed Services Universities under Defense Agencies &
Field Activities; the Agency for Toxic Substances and Disease Registry under
HHS; the Office of Surface Mining Reclamation and Enforcement under Interior;
the Offices of Justice Programs, Community Oriented Policing Services and
Violence Against Women, the Executive Office for Immigration Review, the
Foreign Claims Settlement Commission, the United States Parole Commission and
INTERPOL-Washington under Justice; the Bureau of International Labor Affairs,
Veterans' Employment and Training Service and Women's Bureau under Labor; the
Great Lakes Saint Lawrence Seaway Development Corporation under Transportation;
and the Kennedy Center, the National Gallery of Art and the Woodrow Wilson
International Center for Scholars, which the Manual files under the
Smithsonian Institution.

Not added: 6 already present under another name; 5 are the Manual's own
grouping headings ("Bureaus", "Offices / Boards", "Defense Agencies", "Joint
Service Schools", "Federally Aided Corporations"); 3 are the
civilian-department / uniformed-service distinction §5 already records; 4 are
out of scope; 3 were left unsure rather than guessed — Economics and Statistics
Administration, Defense Acquisition University and the Bureau of Indian
Education.

The first pass's reasoning is kept below, unchanged, because it is what the
adjudication was run against.



Each was checked against the whole published graph twice: by
`canonical_name_key` equality, and by a distinctive phrase from the name
("gallaudet", "kennedy center", "multidistrict", "interpol", "seaway",
"veterans employment"). All 19 return nothing. The phrase probe matters —
a single-token probe returns false hits, since "programs", "international"
and "development" all appear in subcommittee names:

- **Office of Justice Programs** (Department of Justice). The Manual files it
  under DOJ's `Bureaus`.
- **Gallaudet University**, **Howard University**, **American Printing House
  for the Blind**, **National Technical Institute for the Deaf / Rochester
  Institute of Technology** — the Manual's `Federally Aided Corporations`
  under the Department of Education.
- **John F. Kennedy Center for the Performing Arts**, **National Gallery of
  Art**, **Woodrow Wilson International Center for Scholars** — filed by the
  Manual beside the Smithsonian Institution.
- **Defense Acquisition University**, **National Intelligence University**,
  **National Defense University**, **Uniformed Services University of the
  Health Sciences** — the Manual's `Joint Service Schools`.
- **Bureau of International Labor Affairs**, **Veterans' Employment and
  Training Service**, **Women's Bureau** (Department of Labor).
- **Great Lakes Saint Lawrence Seaway Development Corporation** (Department of
  Transportation).
- **Territorial Courts**, **Judicial Panel on Multidistrict Litigation**
  (the judiciary; the Manual files both under `Lower Courts`).
- **International Criminal Police Organization (INTERPOL)–Washington**
  (Department of Justice).

Each would enter through `scripts/add_curated_nodes.py`, which already accepts
an `official_page_label` licence; the Manual is a stronger basis than a page
label, so a `government_manual_entry` licence would be the honest way to add
them — the Manual states the unit's name, its parent and its own website, and
the parent is what a page label never supplies. That is a change to the writer
and is not made here.

### 13.4 One placement disagreement, unresolved

Of the 40 edges where both the Manual and the tree name a parent, 39 agree and
**one disagrees**. Nothing is resolved either way and no field is published
from it: the Manual's hierarchy was measured for this pass and found to add
nothing the tree does not already evidence (all 40 agreeing edges already
carry placement from another source), so no placement is derived from the
Manual at all. Recorded here so the next pass need not re-measure it.

## 14. What OMB's Public Budget Database says, and the one placement it disputes (2026-09-20)

`data_pipeline/verification/omb_budget.py` matches OMB's agencies and bureaus
to curated organisations by canonical-name equality, scoped so a bureau only
reaches a node beneath its own agency's node. 133 units match. Three things the
join surfaced are curation questions rather than pipeline ones, and none is
applied here.

### 14.1 One placement disagreement, refused rather than resolved

OMB files the **Pension Benefit Guaranty Corporation** as a bureau of the
**Department of Labor**. This graph curates it as an independent agency
(`exec-ind-misc-pension-benefit-guaranty-corporation-pbgc`). Both are
defensible: the PBGC is a wholly owned federal corporation whose board of
directors is chaired by the Secretary of Labor, so OMB's budget presentation
files it there, while the graph treats it as the independent body its own
governance makes it. The row is refused and no figure is published for the
PBGC from this source. Nothing is resolved — this is the same treatment the
Monthly Treasury Statement's Tax Court line gets, where the Treasury files
under the Legislative Branch what the graph curates under the judiciary.

### 14.2 A name that means two different units in the same file

**"Bureau of Labor Statistics"** appears in this database under the Department
of Commerce as well as under the Department of Labor. That is not an error in
the file: OMB "adjusts [historical records] each year to conform to the agency
and account structure of the current budget", and the BLS was a Commerce bureau
before 1913. The matcher refuses a bureau name several of OMB's agencies use,
so neither row is published. Recorded because it is the clearest example of why
a name is never enough on its own here.

### 14.3 The Department of War

The FY2027 user's guide contains this sentence, in a passage about restating
historical records onto the current budget's agency structure:

> However, for technical reasons, the Department of War is referred to as the
> Department of Defense.

Read in context — the paragraph is about OMB renaming historical units to
today's names, giving "Department of Health, Education, and Welfare" becoming
HHS/Education/SSA as its example — this says the department's current name in
the FY2027 Budget's structure is the **Department of War**, and that this
database keeps calling it Defense as a technical carryover.

**Nothing is done about it here, deliberately.** This graph names the node
"Department of Defense (DoD)", and one clause in a data user's guide is a lead,
not a licence: §10 records what it cost this repository to act on a single true
sentence about the VA's networks. A rename would need what the renames in §9
needed — the department's own page, or the statute, carrying the name — and
`scripts/rename_units_to_official_wording.py` re-checks every row against the
source on every run, so the row cannot be written until such a source is in
hand. Recorded so the next pass starts from the evidence rather than rediscovering
the sentence.

### 13.5 Bureau of Indian Education: why a real, absent unit is still not added

The strongest finding of the adversarial round, and it generalises.

The Monthly Treasury Statement has **no row** named "Bureau of Indian
Education". It has one combined row, `Bureau of Indian Affairs and Bureau of
Indian Education` (classification 59309125), and the graph applies its measured
**$2,427,080,474.47** to `exec-dept-doi-bia`, the existing Bureau of Indian
Affairs node.

So adding a Bureau of Indian Education node would not add a measured cost —
there is no separate figure to add. It would insert an unlined sibling next to
a node whose measured figure covers both of them, and the cascade would then
apportion a share to it out of a pool the Treasury reports for the two
together. A measured figure would start being divided on no evidence at all.

`jointly_measured_names` in `scripts/add_curated_nodes.py` now refuses any row
whose name is one half of a joint Treasury row already measured on another
node, under every licence, and names the row and the node in the refusal. The
unit is real and the graph does lack it; what is missing is a way to give it a
figure without taking one from its sibling, and until the Treasury reports them
separately there is none.

### 13.6 The three left unsure

- **Economics and Statistics Administration** — genuinely absent by every
  probe, and the reviewer could not establish whether it still exists as a
  distinct unit rather than as a title for the Under Secretary for Economic
  Affairs' office. Absent evidence either way, it is not added.
- **Defense Acquisition University** — absence confirmed independently; the
  reviewer questioned whether it belongs under `Defense Agencies & Field
  Activities` alongside the intelligence agencies rather than under a schools
  grouping the graph does not have.
- **Bureau of Indian Education** — §13.5.

### 13.7 Three of the 26 were already in the review queue

A corroboration worth recording. `output/candidate_nodes.json` is the
discovery crawlers' review queue, and the queue repair that runs after every
rebuild dropped exactly three entries when these nodes landed: **Bureau of
Industry and Security**, **Office of Surface Mining Reclamation and
Enforcement** and **Office of Justice Programs**. All three had been found
independently by the crawlers from Federal Register and directory sources
before the Manual was ever read, and sat unpromoted because a candidate needs
to clear the promotion threshold. The Manual and the crawlers agree on them,
which is the kind of agreement this project has had few opportunities to
observe.

## 15. 2026-09-20: what a visitor clicks first, and what was behind it

The repository owner opened the site and found a U.S. Court of Appeals with no
verification, and then a review found the first three nodes anyone clicks were
blank. Each case was checked against the graph before anything was changed,
and most were not what they looked like.

### 15.1 The thirteen circuits: five had never been given a page

Six of thirteen carried nothing. Five (2nd, 4th, 5th, 7th, 9th) had **no
candidate page in `official_sites.json` at all** — their siblings were queued
on the identical `caN.uscourts.gov` pattern and these were simply skipped —
so the verifier had never fetched them and never could have. The Third
Circuit's URL lacked the `www.` its twelve siblings carry, so its robots.txt
was unreachable; the Sixth died on a dropped connection. All eight pages were
probed read-only first, then nominated with the observed label in the basis,
and the verifier confirmed **13 of 13**. `canonical_name_key` already folds
`U.S.` into `United States`, so no matcher was touched. The Fourth Circuit
confirmed off a 263-character JavaScript shell — correctly, since the readable
floor governs negatives only — and the record says so. The Eighth keeps its
parent-page method rather than being upgraded on a page nothing read.

Still open: this family carries two naming conventions across thirteen
siblings — six short ("Sixth Circuit"), seven long ("U.S. Court of Appeals for
the Ninth Circuit") — and both verify against their courts' own pages, so the
evidence does not settle which the graph should use. Left for the owner.

### 15.2 The branches: one page, one rename

`usa.gov/branches-of-government` — the federal government's official portal
stating its own structure — labels all three branches as headings in page
content, the same class of page the Executive Branch's confirmation already
rested on (`whitehouse.gov/government/executive-branch/`). senate.gov,
house.gov and uscourts.gov label none of them. The **Judicial Branch** was
nominated there and confirmed. The **Legislative Branch** could not be, under
any URL: the curated name was `Legislative Branch — The Congress`, which keys
to `legislative branch the congress`, and no page carries that. Renamed to
`Legislative Branch` through `rename_units_to_official_wording.py` on that
page's evidence — the same em-dash-qualifier class §9 records. The Senate
Appropriations subcommittee of the same name is not a sibling, is excluded from
Treasury name-matching by type, and the branch's $6.47bn is applied by
`TREASURY_ROW_ALIASES` to the node id; `tests/test_treasury_outlays_wiring.py`
still pins that the subcommittee never takes it.

### 15.3 The 715 robots refusals, measured: one host was worth it

Recorded in full in `docs/NETWORK_ACCESS.md` §11. 67 of 68 hosts refuse the
page exactly as they refuse the robots file. `www.nga.mil` alone serves its
homepage behind a 403 robots.txt and is now the second entry in
`STANDARD_4XX_HOSTS`; NGA confirmed. The rest are unrecoverable from this
environment and the site now says so per node (`verificationUnread`).

### 15.4 The Government Manual's own entries: 38 organisations, no network

The route to evidence for units on walled hosts is a directory, and the Manual
is one this repository already holds verbatim. `build_org_records` names 162
organisations uniquely; 38 of the unverified take it as their method. The
Manual's printed hierarchy places 12 under the parent the tree gives them and
files **one elsewhere**: the Federal Energy Regulatory Commission, under the
Department of Energy, where this graph has it among the independent regulatory
commissions. Both are defensible — FERC is an independent commission housed in
DOE — so nothing is resolved and the panel says the two sources disagree.

Three of the 38 are worth a note. "U.S. Courts of Appeals (13 Circuits)" and
"U.S. District Courts (94 Districts)" match the Manual's "United States Courts
of Appeals" / "United States District Courts" because `canonical_name_key`
drops the parenthetical; those are real Manual entries for those court
families and the match is right. "Export-Import Bank of the U.S." matches the
Manual's spelling the same way.

### 15.5 The evidence-triage sweep (phase 1c)

`docs/EVIDENCE_TRIAGE_RUNBOOK.md` is the brief; 16 Sonnet agents took a shard
of 52 organisations each with everything the repository knows about each node
(siblings' evidence state, queued URLs, which hosts are walled, prior
nominations, candidate Treasury lines), probed live, and proposed; 16
adversarial verifiers then re-probed every nomination, rename and cost key to
refute it. The results, once recorded, promoted and verified, are the subject
of the next section.

### 15.6 What the sweep found, and what was done with it

**Scale.** 832 organisations, 16 shards of 52, 32 agents (16 triage, 16
adversarial verify), 1,150 live probes and tool calls, 3.4 hours. Verdicts:
342 already confirmed on their own page, 438 declined with a specific reason,
30 nominated, 22 honestly unsure. The verifiers refuted **19 of 29 rename
proposals** (page headings, site-section labels, a "program" suffix, an
Obama-library basis under a Ford-library id, one no-op), **4 of 30
nominations**, and the one cost identifier's *reasoning* while confirming its
substance (OSMRE, §15.4 above). Nothing an agent proposed reached a ledger
without a second agent trying to refute it.

**What landed.** 26 upheld URL nominations and 2 more the verifiers found
while spot-checking declines (the FDIC homepage; NSF's SBE/BCS division
page); 204 declines carrying a probe synthesized from a *recorded* reading —
the evidence record or the 68-host measurement — and **45 declines dropped**
because they named a page nobody in the repository had read, which the
harness rightly refuses; 54 cost records (53 declines, one identifier); and
eight renames the page licensed (NTIA, the House Inspector General, the
Senate Ethics Committee's long-standing "Committee on Select Committee"
artifact, the Judiciary IP subcommittee's current name, the DFC, and the
Nixon, Roosevelt and George Bush libraries' official names). Three proposals
were refused by the script and are NOT in the table, because a row the page
did not license is a declined proposal and `tests/test_unit_renames.py` holds
the table to that: "Energy and Natural Resources Division" for DOJ's ENRD and
"Offices of the United States Attorneys" for the USAO, both on justice.gov,
which answered 401 on every attempt today (re-proposable when it answers; the
verifiers read both labels in content earlier in the day), and "Subcommittee
on Personnel", which the Senate's list names but no page labels. The House Chaplain's proposed "Office of the Chaplain"
was declined by hand for dropping the chamber.

**The over-claim the verifiers exposed, fixed.** 35 subcommittees carried
their *committee's* index of subcommittees under their own key, and 26 of them
were published `verified` on it as "its own official page" — the
energy.gov/national-laboratories mechanism on nine other hosts. The harness
refused the repair twice, as "already a candidate" and as "already fetched
for this node"; both rules keep their force for `own_site` and now admit a
re-nomination under a role that files the URL elsewhere, which is the one
input `promote --refile-misplaced` acts on. 36 URLs moved to their committees;
those subcommittees now publish the parent-page method with placement from
the same page.

**The same fact, published once.** Eleven organisations — Federal Student Aid
($76bn measured), six DOE laboratories, the FHA, CRS, the Senate Chaplain and
the House Legislative Counsel — had their own queued host walled while the
placement pass had already read the parent's page and found them listed by
name. The site said "not verified" beside "listed on its parent's page". This
file already treats a parent-page confirmation as placement without a second
fetch; the reverse is now true too, and the label is quoted exactly where the
confirmed path quotes it (a folded committee match), which the gate caught
when the first cut quoted it everywhere.

**On the published graph:** official source 783 → 806 of 5,453; no source
recorded 4,618 → 4,597; placements 480 → 486; 26 gained a method, 52 changed
one (26 honestly down from own-page to parent-page, 12 Manual and 9
directory listings up to page confirmations), 1 lost one — DOJ's Civil
Division, on a host that served its page at 00:33 and refused it at 21:00.

**Open, recorded rather than guessed:**

- **Ways & Means.** `<h2><span>Subcommittee On</span> <span>Tax</span></h2>`
  parses as two fragments, so every Ways & Means subcommittee fails label
  equality on its own committee's page. A parser rule joining *inline*
  children inside one heading element — never across block elements, which is
  the "phrase spanning two DOM elements" case the adversarial review refused —
  would fix the family. A code decision for the owner.
- **usa.gov as a branch's "own page"** (§15.2). Verifier (shard 1): the
  method wording over-claims; usa.gov is the government's portal, not the
  judiciary's site. The confirmation stands with that objection recorded; the
  honest alternative is a distinct method for a government portal that
  describes the unit, which `official_list` nominations would also need.
- **NSF CISE/IIS** carries the *directorate's* page under its own key as
  `own_site`, so the verifier publishes a false `not_found`; recorded role is
  own_site, so `--refile-misplaced` cannot reach it. Needs a hand refiling.
- **Weaponization select subcommittee** expired with the 118th Congress;
  judiciary.house.gov names it only in an archived block. A supersession, not
  a rename — the first honest entry for `mark_superseded_units.py`.
- **EERE**: energy.gov/eere now redirects to the Office of Critical Minerals
  and Energy Innovation. A rename or supersession lead.
- **Bureau of Reclamation**: Table 5 prints it as a header with two lines
  beneath summing to $2.756bn and no Total line; the graph's apportioned
  estimate is $4.374bn. Worth a curator's eye.
- **Prior recheck1 records (2026-09-13)** assert headings for the Truman,
  Clinton and LBJ libraries and several subcommittees that today's re-probes
  cannot find. Six of the 22 unsure verdicts are this pattern.

## 16. The two chambers' complete lists, reconciled seat by seat (2026-09-21)

§5.1 and §5.7 recorded what the Senate's committee-membership files and the
House Clerk's spreadsheet say about the curated committees, and §9 acted on
the clearest cases. What was left on 2026-09-21, read off
`scripts/derive_directory_evidence.py --dry-run` rather than off those
sections: **12 Senate and 21 House subcommittee nodes** published as
"checked against the official list: it carries no unit of this name", one
House committee (§12.2, no action), and **12 Senate and 23 House list names
the graph had no node for**. This section is the seat-by-seat disposition of
every one of them, under the same rules §9 and §10 set: nothing is renamed
or added except by its sanctioned script, every rename or addition is
licensed by an official page the script re-fetches and re-tests on every
run, and a decision that cannot be cited is recorded as a decision not to
act.

**What was read.** Every committee's own subcommittees page (21 pages,
senate.gov and house.gov hosts), the five Senate committee-membership XML
files at senate.gov for the committees concerned, and — where a committee's
own page is a script shell below the verifier's readable floor
(`armedservices.house.gov/subcommittees` at 278 characters,
`intelligence.house.gov/subcommittees/` at 360, `cha.house.gov/subcommittees`
at 229, every `oversight.house.gov/subcommittee/…` page at 343) or names its
subcommittees only in site-wide navigation (`oversight.house.gov`,
`cha.house.gov`) — the House's own document repository,
`docs.house.gov/Committee/Committees.aspx?Code=<code>`, which prints each
committee's subcommittees in page content and had already licensed the
Intelligence Committee's NSA rename in §9. Every page was fetched once under
the verifier's robots policy and User-Agent by a read-only scratch script
that ran the verifier's own `find_label_region_rule` for every curated child
name, every list name, and every proposed name, both with the committee fold
(the rename script's test) and without it (the add script's test). The
script wrote nothing; the two sanctioned scripts re-fetched every page again
before writing.

Three things the reading established that decided cases below:

- **The Senate Appropriations Committee's own site names its subcommittees
  without "Department of".** appropriations.senate.gov labels them "Defense",
  "Homeland Security", "Interior, Environment, and Related Agencies", "Labor,
  Health and Human Services, Education, and Related Agencies"; the Senate's
  XML prints "Subcommittee on Department of Defense", "…Department of Homeland
  Security", "…Department of Interior, Environment, and Related Agencies",
  "…Departments of Labor, Health and Human Services, and Education, and
  Related Agencies". The committee fold did find "Department of Defense" and
  "Department of Homeland Security" on two subcommittee pages, and those hits
  were checked in context before being believed: they are entries in each
  subcommittee's *jurisdiction* list ("Department of Defense—Military" sits
  beside "Defense Health", "Missile Defense Agency (DOD)"), not the
  subcommittee's label. A rename licensed by that hit would have been exactly
  the over-match the fold was built to refuse.
- **help.senate.gov and judiciary.senate.gov split each subcommittee name
  across DOM elements** — `SUBCOMMITTEE ON` / `Education` / `&` / `the American
  Family`; `Subcommittee on` / `Federal Courts, Oversight, Agency Action and` /
  `Federal Rights` — which label equality refuses by design (the "phrase
  spanning two DOM elements" case §15.6 records for Ways & Means). Neither
  page can confirm any subcommittee, current or curated; the Senate's own
  membership file is the page that can, and §9 had already used it for three
  Judiciary renames.
- **judiciary.house.gov/about/subcommittees is an archive.** It carries a
  "Current Congress" block of six names and then blocks headed "118th
  Congress", "117th Congress" and so on back to the 110th. "The Subcommittee
  on Responsiveness and Accountability To Oversight" and the "Select
  Subcommittee on the Weaponization of the Federal Government" sit under the
  118th heading and not under the current one. §9's rename of the
  Weaponization node, and the `name_labelled_on_own_official_page`
  confirmation it then earned, rest on that archived block — the very thing
  §9.4 declined a different proposal for.

### 16.1 Eleven renames, each licensed by the page the row names

All eleven are in `data/curation/unit_renames.json` with the basis written
beside them, and were applied by `rename_units_to_official_wording.py`
(dry run: `renamed 11 refused 95 of 106 rows`; the 95 are the earlier rows,
already applied, skipped before any fetch). The rule applied is the brief's:
the current list name plainly denotes the same seat — same committee, and
the jurisdiction words shared — and the committee's own page, or the House's
own listing, labels it.

| Node | Was | Now | Licensed by | Shared jurisdiction words |
|---|---|---|---|---|
| HSGAC `…-sub-government-operations-border-management` | Government Operations & Border Management | Border Management, Federal Workforce, and Regulatory Affairs | hsgac.senate.gov/subcommittees/ (content, under a "SUBCOMMITTEE ON" heading; the site drops the Oxford comma) | Border Management; three seats in both Congresses, PSI unchanged |
| House Armed Services `…-sub-cyber-information-technology-innovation` | Subcommittee on Cyber, Information Technology & Innovation | Subcommittee on Cyber, Information Technologies, and Innovation | the node's own queued page (its title), and docs.house.gov AS00 | all of them; one letter |
| House E&C `…-sub-energy-climate-grid-security` | Subcommittee on Energy, Climate & Grid Security | Subcommittee on Energy | docs.house.gov IF00 (content); the committee's home page lists its six current subcommittees in content | Energy; six seats in both Congresses |
| House E&C `…-sub-environment-manufacturing-critical-materials` | Subcommittee on Environment, Manufacturing & Critical Materials | Subcommittee on Environment | docs.house.gov IF00 | Environment |
| House E&C `…-sub-innovation-data-commerce` | Subcommittee on Innovation, Data & Commerce | Subcommittee on Commerce, Manufacturing, and Trade | docs.house.gov IF00; energycommerce.house.gov home page (folded) | Commerce; the sixth seat once the other five are accounted for by name — the weakest of the eleven, and recorded as such on the row |
| House Financial Services `…-sub-financial-institutions-monetary-policy` | Subcommittee on Financial Institutions & Monetary Policy | Subcommittee on Financial Institutions | financialservices.house.gov/subcommittees (content) | Financial Institutions; the qualifier dropped (monetary policy now sits with a task force, which is not a subcommittee and is not added) |
| House Foreign Affairs `…-sub-indo-pacific` | Subcommittee on Indo-Pacific | East Asia and Pacific Subcommittee | foreignaffairs.house.gov/subcommittees/ (content); docs.house.gov FA00 prints the same | Pacific; one regional seat |
| House Foreign Affairs `…-sub-middle-east-north-africa-central-asia` | Subcommittee on Middle East, North Africa & Central Asia | Middle East and North Africa Subcommittee | foreignaffairs.house.gov/subcommittees/ | Middle East, North Africa; Central Asia moved to a new seat, added in §16.2 |
| House Oversight `…-sub-government-operations-the-federal-workforce` | Subcommittee on Government Operations & the Federal Workforce | Subcommittee on Government Operations | docs.house.gov GO00 (content); the committee's own site carries the name in navigation only | Government Operations |
| House Ways & Means `…-sub-worker-family-support` | Subcommittee on Worker & Family Support | Subcommittee on Work and Welfare | waysandmeans.house.gov/subcommittees/ ("Work & Welfare" under a "Subcommittee On" heading, folded); docs.house.gov WM00 | Work; the other five seats unchanged by name |
| HPSCI `…-sub-defense-intelligence-warfighter-support` | Subcommittee on Defense Intelligence & Warfighter Support | Subcommittee on Defense Intelligence and Overhead Architecture | docs.house.gov IG00 (the page that licensed §9's NSA rename) | Defense Intelligence |

Two of the Foreign Affairs renames take the form the committee's own page
prints — type word after the region, "East Asia and Pacific Subcommittee" —
rather than the graph's "Subcommittee on …", because the page and
docs.house.gov both print it that way and the sibling "Africa Subcommittee"
already does. That form is what §16.5 is about.

### 16.2 Eighteen units added, all under `official_page_label`

All in `data/curation/new_nodes.json`, added by `add_curated_nodes.py`
(dry run: `added 18 refused 47 of 65 rows`; the 47 are the earlier rows,
already present), typed `Subcommittee`, parent the committee node, with the
generated description that says only that the page names the unit. The add
script applies plain label equality — no committee fold — so each name is
exactly what its page prints, which is why the Senate rows are bare ("Digital
Assets") where the committee's page is bare and prefixed ("Subcommittee on
Education and the American Family") where the only page that can decide is
the Senate's membership file. Nothing was named from a list alone.

| Under | Added | Licensed by |
|---|---|---|
| Senate Banking | Digital Assets | banking.senate.gov/about/subcommittees |
| Senate Commerce | Coast Guard, Maritime, and Fisheries | commerce.senate.gov/about/commerce-subcommittees/ (prints "&") |
| Senate Commerce | Science, Manufacturing, and Competitiveness | same |
| Senate Commerce | Surface Transportation, Freight, Pipelines, and Safety | same |
| Senate HSGAC | Disaster Management, District of Columbia, and Census | hsgac.senate.gov/subcommittees/ |
| Senate HELP | Subcommittee on Education and the American Family | senate.gov committee_memberships_SSHR.xml |
| Senate Judiciary | Subcommittee on Federal Courts, Oversight, Agency Action, and Federal Rights | senate.gov committee_memberships_SSJU.xml (a seat the 118th Congress had too; the graph never carried it) |
| House Agriculture | Subcommittee on Forestry and Horticulture | docs.house.gov AG00; the committee's page labels "Forestry and Horticulture" |
| House Armed Services | Subcommittee on Intelligence and Special Operations | docs.house.gov AS00 |
| House Foreign Affairs | Europe Subcommittee | foreignaffairs.house.gov/subcommittees/ |
| House Foreign Affairs | South and Central Asia Subcommittee | same |
| House Administration | Subcommittee on Modernization and Innovation | docs.house.gov HA00 |
| House Judiciary | Subcommittee on Oversight | judiciary.house.gov/about/subcommittees, under "Current Congress" |
| House Oversight | Subcommittee on Delivering on Government Efficiency | docs.house.gov GO00 |
| House Oversight | Subcommittee on Federal Law Enforcement | docs.house.gov GO00 |
| HPSCI | Subcommittee on the National Intelligence Enterprise | docs.house.gov IG00 (prints "the"; `subcommittee_key` sets it aside) |
| HPSCI | Subcommittee on Open Source Intelligence | docs.house.gov IG00 |
| HPSCI | Subcommittee on Oversight and Investigations | docs.house.gov IG00 (three other committees have one; a cross-parent duplicate is allowed, this committee had none) |

None of the eighteen collides with a sibling. The `jointly_measured_names`
guard had nothing to say: no committee carries a Treasury line.

### 16.3 Left alone, each with the reason

**The Senate Appropriations four** — Defense; Homeland Security; Interior,
Environment & Related Agencies; Labor, Health and Human Services, Education,
and Related Agencies. The committee's own site names all four as the graph
does, three are confirmed on their own pages already, and the Senate's XML
alone adds "Department(s) of". §12.2's rule governs: a committee's own site is
the better authority for its own name, and a rename to the list's spelling
would trade a confirmation from the committee's page for a listing in an
administrative index. They stay published as names the list does not carry,
and the list's four names stay reported as ones the graph lacks — the same
four seats, spelled two ways by two official sources. "Defense" is the one
that costs something: one generic word, so `uncheckable_reason` refuses it
before any fetch and the list was its only possible evidence.

**Senate Commerce's four** — Oceans, Fisheries, Climate Change &
Manufacturing; Science & Space; Surface Transportation, Maritime, Freight &
Ports; Tourism, Trade & Export Promotion. The committee's page labels none of
them in any form; its six current subcommittees are all now in the graph (three
matched, three added). The words were redistributed rather than renamed —
§5.1's notes set out how — and §9.4 had already declined the Surface
Transportation rename for moving maritime jurisdiction the page does not
confirm. No official page states in words that any of the four was abolished.

**HSGAC's "Emerging Threats & Spending Oversight"**: shares no word with any
current name (§5.1). **HELP's "Children & Families"**: shares one stem with
"Education and the American Family", which §5.1 called the weakest lead; under
the brief's rule — same jurisdiction words — that is not a rename, so the
current seat is added beside it. **Senate Judiciary's "Human Rights & the
Law"**: no current name is its successor.

**House Agriculture's "Subcommittee on Horticulture, Farm Inputs &
Subcommittee on Precision Agriculture"**: a garbled name (two run together)
matching no seat on the committee's page in any Congress. **House Foreign
Affairs' "Global Health, Global Human Rights & International Organizations"**:
no such seat in the 119th Congress's seven. **House Administration's
"Subcommittee on Committees"**: no such seat; the Clerk lists Elections and
Modernization and Innovation. **Veterans' Affairs' "Subcommittee on
Benefits"**: no such seat. **HPSCI's "Strategic Technologies & Advanced
Research"**: no current name is its successor.

**Two whose successor is already a sibling.** House Oversight's "National
Security, the Border & Foreign Affairs" is the 118th-Congress name of the seat
the graph already carries as "Subcommittee on Military & Foreign Affairs";
Ways & Means' "Select Revenue Measures" is the 118th name of the seat the graph
already carries as "Subcommittee on Tax". A rename would collide with the
sibling, and nothing here merges nodes; both are leads for
`merge_duplicate_nodes.py`, for the owner.

**House Judiciary's two archived names.** "Responsiveness & Accountability to
Americans" is a garbled form of "The Subcommittee on Responsiveness and
Accountability To Oversight", which the committee's page files under its
"118th Congress" heading. Renaming to an archived name is what §9.4 declined,
so it is left; the current "Subcommittee on Oversight" is added. The
Weaponization select subcommittee is §16.4.

**House Education & the Workforce**: §12.2, no action.

### 16.4 No supersession applied, and the one it nearly was

`data/curation/superseded.json` gains no row. The candidate §15.6 named — the
Select Subcommittee on the Weaponization of the Federal Government — was
taken as far as the discipline allows:

- the House Clerk's complete list (2026-09-13) does not carry it;
- judiciary.house.gov files it under "118th Congress" and not "Current
  Congress" — a statement by heading, not in words;
- the resolution that created it, H.Res.12 of the 118th Congress, is served
  by govinfo.gov (`content/pkg/BILLS-118hres12eh/html/…`, robots.txt allows
  it, 5,381 readable characters) and states, in its own words: **"The select
  subcommittee shall cease to exist 30 days after filing the final report
  required under subsection (b)."**

That sentence states the condition on which it ceased, not that the condition
occurred, and no official page read states the date. `mark_superseded_units.py`
requires `supersededOn` "as the source states it", and the only date on offer
would be reasoned from the Twentieth Amendment rather than read off a page —
which is a restructuring on one true sentence, the thing §10 exists to refuse.
Left, with this trail, for the owner: the quote above is on a page the script
can fetch, so a row needs only a citable date.

### 16.5 A fold the list matcher lacked, found on nodes the page had confirmed

"Africa Subcommittee" and "Oversight and Intelligence Subcommittee" were
renamed in §9 to the wording foreignaffairs.house.gov prints, confirmed on
that page, and still published as names the Clerk's list does not carry —
because `congress.subcommittee_key` set aside a leading "Subcommittee on" and
not a trailing "Subcommittee", while the Clerk prints "Africa". docs.house.gov
prints the committee's seven regional subcommittees the same way the
committee does. The page test's own fold, `evidence.committee_core_key`, has
always folded the type word on both sides; the list key now does too, and
nothing else: "Permanent Subcommittee on Investigations" keeps its name, and a
type word in the middle of the garbled Agriculture name is not a suffix.
Pinned both ways in `tests/test_congress.py`. It is a closed type-word fold,
not a similarity match, and it is what lets the two Foreign Affairs renames and
two additions above take the committee's own wording and still match the
Clerk. Six nodes match by it.

### 16.6 What moved, measured

`scripts/derive_directory_evidence.py` before and after (the committed
`directory_evidence.json` against the regenerated one):

| | Before | After |
|---|---|---|
| Senate list: subcommittees matched and placed | 58 | 66 |
| Senate list: curated names not in the list | 12 | 11 |
| Senate list: list names not in the graph | 12 | 4 (the Appropriations four, §16.3) |
| House Clerk: subcommittees matched and placed | 82 | 105 |
| House Clerk: curated names not in the list | 21 | 9 |
| House Clerk: list names not in the graph | 23 | 0 |
| Directory records in the file | 384 | 402 |
| Curated nodes | 5,424 | 5,442 |

Of the 31 nodes whose status changed, 13 went `not_in_list → listed` (11
renames, 2 by the fold) and 18 are new. Nothing measured moved: no committee
carries a cost of its own, and `output/` is untouched — the integrator
rebuilds it.

**What it cost.** The supersession script's real run — made only because the
brief asked for all three scripts to run for real, with no row to add — met a
transient `RemoteDisconnected` at `department.va.gov/robots.txt`, refused all
18 VA rows as `page_refused`, and, because it withdraws every mark before
re-applying the table, wrote the curated file with the 18 marks gone. A second
run a minute later re-fetched the page, found the quote, and restored all 18
with `readAt` moved from 2026-09-19 to 2026-09-21. That is the design working
as written — a mark that cannot be re-checked is not re-asserted — but it means
a real run on a bad network day silently unmarks nodes and a dry run does not
warn of it. Worth a line in that script's docstring, or a refusal to write
when a fetch failed rather than the quote; a code decision for the owner.

**What the verifier will see next.** The eleven renamed nodes carry
`nameSource`, `nameSourceDetail` and `nameMatchedText` from the pages above.
The eighteen new nodes have no candidate page in `official_sites.json` — that
file was not touched — so their existence evidence is, for now, the list's
listing and placement alone, which is what the panel will say. For the House
committees whose own subcommittee pages are script shells, the readable page
that names the seat is `docs.house.gov`'s listing for the committee, which is
neither the unit's own page nor its parent's in the sense `filing_id_for_role`
draws; nominating it is phase 1b's, and the `official_list` role is the one
that describes it.

## 17. Alternative names a node answers to (2026-09-21)

A node keeps the name the graph displays. `data/curation/node_aliases.json`
records, per node, the OTHER names an official document may print for the same
unit, and the verification process accepts them. It is the fourth table of this
shape, after `unit_renames.json`, `TREASURY_ROW_ALIASES` and
`USASPENDING_NAME_ALIASES`: a reviewed identification, with the basis written
beside it, re-adjudicated against the curated file on every run rather than
trusted.

It exists because §13.1 recorded the problem and then correctly declined the
only tool available at the time. The Manual prints "Federal Motor Carrier
Safety Administration" where this graph writes "Admin"; §13.1 refused to
*rename* those four nodes, because "the reason to rename must be the agency's
own wording and the payoff must be real". Both halves of that still hold. An
alias is the other move: the displayed name does not change, and the matcher
does not loosen — a name is either in the table or it is not.

### 17.1 What a row must clear, and what it may never touch

Per row: the node id, the node's **current** name, the alternative, and a
`basis`. A row is refused — offline, on every run, with the reason printed —
when the node is not there, when it no longer carries the stated name, when
there is no basis, when the alternative reduces to the node's own key (a
no-op), when it is **one token** or on `GENERIC_NAMES`, and when it collides
with a **sibling's** name or a sibling's accepted alias. The collision rule is
sibling-scoped for exactly the reason §9 gives.

**An alias is consulted by name and existence evidence only.** The page-label
test in `evidence.py`, the Government Manual's entry join, the chambers'
committee lists, and the current PLUM export's agency scoping. It is never
consulted by a join that lands a number — not `headcounts.py`, not the Treasury
row matching, not `usaspending.py`, `net_cost.py` or `omb_budget.py`. Those
already have their own tables where a figure is at stake, and CLAUDE.md records
why one table for both kinds of claim would be dangerous: FedScope's
"DEPARTMENT OF THE ARMY" is a civilian department and this graph's "U.S. Army"
the uniformed service. The separation is **structural** — those modules do not
import the alias module, and `tests/test_node_aliases.py::IsolationTests`
asserts the whole repository's import list against a whitelist and that none of
the money matchers even has a parameter one could be handed to.

**A confirmation reached this way is the weaker claim and reads as one.** The
record carries `matchRule: matched_on_a_recorded_alternative_name` with the
alternative and its basis; the node publishes `verificationAliasMatch`; and
`cap_alias_only_confirmations` holds a node whose every official source came
through the table at `partial`, never `verified`. That is the same deliberate
downgrade `usaspending.py` makes for an aliased key. The panel (and the atlas
view) prints both names and the basis in words, and says when the cap applied.
A **node-scoped** alias never publishes a placement, in either the page route
or the Manual's organisation route.

### 17.2 The eight rows, and what each unlocked

| Node | The graph's name | The alternative | Basis |
|---|---|---|---|
| `exec-ind-misc-americorps` | AmeriCorps | Corporation for National and Community Service | §2 records the statutory name; the Manual's entry 133 is printed under it; OPM's current PLUM export files 31 live rows under it |
| `exec-vp` | The Vice President of the United States | The Vice President | The Manual's top-level entry 97, headed exactly so |
| `jud-support-aousc` | Administrative Office of U.S. Courts (AOUSC) | Administrative Office of the United States Courts | The same words; the graph writes "U.S." and drops "the" |
| `exec-dept-doc-noaa` | NOAA — National Oceanic & Atmospheric Administration | National Oceanic and Atmospheric Administration | The graph's own `<ACRONYM> — <name>` typography; the Manual's entry 264 prints "(NOAA)" |
| `exec-dept-dot-fmcsa` | Federal Motor Carrier Safety Admin (FMCSA) | Federal Motor Carrier Safety Administration | §13.1; the Manual's entry 249 prints "(FMCSA)" |
| `exec-dept-dot-nhtsa` | National Highway Traffic Safety Admin (NHTSA) | National Highway Traffic Safety Administration | §13.1; entry 243 prints "(NHTSA)" |
| `exec-dept-dot-phmsa` | Pipeline & Hazardous Materials Safety Admin (PHMSA) | Pipeline and Hazardous Materials Safety Administration | §13.1; entry 247 prints "(PHMSA)" |
| `exec-dept-defense-agency-darpa` | DARPA | Defense Advanced Research Projects Agency | The acronym, letter for letter; §13.3 records the same adjudication |

Measured on the two derivations and the rebuilt graph, before → after:

- Manual entries matched to an organisation **163 → 170**; posts listed from
  the leadership tables **85 → 89**; official descriptions **142 → 149**;
  Manual-as-method **23 → 28**.
- Current PLUM export: agencies matched **78 → 79**, positions listed
  **170 → 173**, rates **100 → 101**.
- Published graph: nodes with an official source **931 → 942**; `verified`
  **484 → 485**; `partial` **401 → 415**; **16 nodes** change verification
  status and **no cost figure moves at all**. **15 nodes** carry a
  `verificationAliasMatch` and **14** of them rest on nothing else and are
  held at `partial` by the cap. The one that is not is DARPA, which already
  had `darpa.mil`.

**The cap turns on `official_site`, not on "a `.gov` URL", and the first
version had it wrong.** NOAA, FMCSA and NHTSA each carried exactly one source
before this work — the FiscalData URL their measured Treasury line put there —
which `classify_source_url` files as `government_dataset` and which earns no
`official_site` bonus, so each sat at confidence 0.4. One aliased Manual entry
took all three to **0.8 and `verified`** in the first build, because the
broader test read the dataset URL as other evidence and lifted the cap. The
gate caught it, the rule is now `official_site` exactly on both sides, and the
gate mirrors the three-line classification stdlib-only with a test pinning the
two equal. A second defect surfaced in the same build: the cap was applied
beside the other evidence passes, and both `verify_node_sources` and
`annotate_proof_tree` run after them and recompute the status from the URL
count, silently undoing it. It now runs after the tree is final, beside
`withdraw_pay_from_multi_post_nodes`.

`output/` is not rebuilt by this change — the integrator does that — so the
classes in `tests/test_node_aliases.py` that measure the PUBLISHED graph skip
with "output/graph.json predates the alias table; regenerate it" until it is.
They were run green against a locally regenerated graph, and the release gate
passed clean on it.

**AmeriCorps is the row that gained least where it was expected to gain most,
and the reason is worth recording.** The export's 31 live CNCS rows all sit
under sub-organisations (`… / OFFICE OF AMERICORPS VISTA`, `… / OFFICE OF THE
CHIEF EXECUTIVE OFFICER`) that this graph has no nodes for, so matching the
agency reached no position. What the row did buy is the Manual's entry for the
unit itself, its official description, and two of its posts. The remaining 31
rows need *nodes*, not an alias — the distinction §13.3 already draws.

The three positions the table unlocked in the export are FMCSA's and PHMSA's
Administrators and PHMSA's Deputy Administrator, and they are reached through
the ORGANISATION half of the export's filing rather than the agency half, so
each carries `scope: "organisation"` and the panel says the agency, not the
post, was named differently.

### 17.3 The President and the Vice President

`govman.match_organisations` skips every post, and the post route requires the
post to be a direct child of a matched organisation, so neither office could
ever be reached however its name was spelled. The Manual carries a top-level
entry for each — entity 96 "The President" and entity 97 "The Vice President" —
and those entries are not agencies: the entry IS the office.

`govman.build_office_records` is that third route, published as
`verificationMethod: listed_as_its_own_entry_in_us_government_manual` in its
own field `govmanOfficeEntry`, and **never as a placement**. Four guards keep
it from reaching an ordinary agency entry, each checked on the run: the entry
has no parent entry; it names no organisation in this graph (an agency entry
does, and the organisation route owns it); it reaches exactly one post and that
post answers to exactly one such entry; and the post's own parent is not an
organisation the Manual has an entry for.

A fifth guard was added because the first version failed without it, on the
real data: the entry's ALL-CAPS principal row may be used as a name only when
it is the entry's own heading, or that heading plus the five words "of the
United States". Without it, the Manual's entry for the **United States
International Trade Commission** — an agency this graph has no node for —
printed `CHIEF ADMINISTRATIVE LAW JUDGE`, which reached the Social Security
Administration's Chief Administrative Law Judge: an agency entry naming one of
its officers, published as though the Manual carried an entry for that officer.
With the rule, 32 caps rows are refused and exactly two offices are listed.

**The President has no alias row, and that is the rule working rather than a
gap.** The Manual's heading is "The President", which reduces to the single
token `president` under `canonical_name_key`, and the alias is consulted by the
page-label test — "President" is a label on thousands of `.gov` pages. The
one-token floor refuses it. No alias is needed: the same entry's leadership
table prints the office as `THE PRESIDENT OF THE UNITED STATES`, which is
exactly this node's name, and the route reaches it by plain equality. The Vice
President's caps row reads only `THE VICE PRESIDENT`, so that one does need the
row — and "The Vice President" is two tokens and clears the floor.

Both publish `partial`: one official URL is 0.4 + 0.3 in `verify_node_sources`,
and nothing here changes that arithmetic.

### 17.4 Four cases considered and declined

- **`U.S. Army` / `U.S. Navy` / `U.S. Air Force` → `Department of the …`.**
  Refused outright and recorded in the table's own comment block. CLAUDE.md
  records twice — for FedScope's employment table and for the Manual's
  entries — that the civilian department and the uniformed service are
  different units with different populations, and §13.2 records the same split.
  That is a semantic claim, not a spelling. The owner is deciding it
  separately, and a test asserts no row here names any of the three.
- **`Bureau of Consumer Financial Protection` → `Consumer Financial Protection
  Bureau`.** The Manual's entry 321 is headed with the second and says the
  agency was "established by title X of the Dodd-Frank Wall Street Reform and
  Consumer Protection Act of 2012 (12 U.S.C. 5491)". The two are almost
  certainly one agency under its statutory name and its branding — but
  establishing that needs 12 U.S.C. 5491 itself, which this repository has not
  read. A word-order difference is not a spelling. Declined rather than
  guessed; a committed section of the Code would settle it.
- **`National Security Agency (NSA)` → `National Security Agency / Central
  Security Service`.** The Manual's entry 229 is a joint designation and its
  own opening paragraph says so: "The National Security Agency (NSA) was
  established in 1952 and the Central Security Service (CSS) was established in
  1972." Recording it would have this node answer to a label covering a body
  the graph does not carry — the shape `usaspending.BROADER_API_ENTITY`
  refuses.
- **A wholesale fold of `Admin` → `Administration`.** Not attempted. That is a
  matcher change rather than a table, and it is the looseness that once let
  "Office of Science" match "Office of Science and Technology Policy". Four
  rows, each argued, cost nothing and can be read.
