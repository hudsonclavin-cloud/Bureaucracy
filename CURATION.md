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

**The proposal is a rename, and it is curation.** Thirteen departments need
`Secretary of Department of X` -> the title the department's own page
carries (`Secretary of Energy`, `Secretary of the Treasury`, `Secretary of
State`, ...), and DOJ needs `Attorney General` / `Deputy Attorney General`.
Defense is already correct and is the control case: it alone carries
`Secretary of Defense`, and it is the only department whose curated title
could ever have matched.

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
