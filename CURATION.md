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
nothing in it has been applied to the base graph (§5.6).

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
