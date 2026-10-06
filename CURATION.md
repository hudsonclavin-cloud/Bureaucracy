# Curation proposals

Changes to `data/federal_gov_complete_1.json` are the owner's to make; the
pipeline never edits it. Nothing here had been applied when this was
first written; §3's merge (2026-09-18, `scripts/merge_duplicate_nodes.py`)
and §1's fifteen units (2026-09-19, `scripts/add_curated_nodes.py`) have
been since, and later sections say what they applied. Each item says
what the evidence supports and what it does not. Official URLs listed are
*candidates* for `data/verification/official_sites.json` — a URL there is a
page to fetch, never evidence by itself; the verifier decides.

Standing rule for every proposal below (from CLAUDE.md): a Treasury line is
matched to a node only when the name identifies one line and one node, and
an alias is added to `TREASURY_ROW_ALIASES` only when the line belongs to
the section of the node's ancestors, or the node is placed where the
statement files it (until the cap went, §4, the test was that the line fit
inside its parent's resolved amount). A node can be added without its line ever
being applied; that is still an improvement, because the unit exists and
the site can say so.

## 1. Units the Monthly Treasury Statement reports and the graph lacks

Table 5 prints a line for each of these and, when this was written, no node
carried the name, so no alias could reach the money. All fifteen were added
on 2026-09-19 by `scripts/add_curated_nodes.py` (licence
`treasury_statement_line`), and each now publishes its line as
`cost_status: official`. Amounts are FYTD net outlays through
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
It was blocked, when this was written, by the alias rule then in force: its
parent, "Other Independent Agencies (25+)" (`exec-ind-misc`), resolved to
*no amount at all* (see §4), so no line fit inside it. Neither holds now:
the parent carries a $14.42B estimate, the test is the same section, and
Table 5 files this line under Independent Agencies, the section it files
twelve of `exec-ind-misc`'s fifteen measured children under. The alias has
simply not been added — `TREASURY_ROW_ALIASES` has no key for it, and
AmeriCorps publishes an apportioned $1.37B; the earlier attempt to publish this unit
as a fourth child of the root came from the crawler, not from the base
graph, and is the reason `resolve_root_orphans` refuses root attachment.

**U.S. Postal Service** (`exec-ind-usps`) was estimated at ≈ $19B when this was written (an
apportioned $22.03B now) while Table
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

What that left for curation, when this was written, was only what this
document lists: the sixteen units above (their lines then sat,
unapportioned, inside their sections' estimates), the AmeriCorps and Postal
Service aliases, and the Coast Guard duplicate — whose $10.9B, ambiguous
between two nodes, was then the largest single line the graph could not
place. The Coast Guard was merged and its line applied on 2026-09-18 (§3),
and the fifteen units of §1 were added on 2026-09-19 and each publishes its
own line, `cost_status: official`; the AmeriCorps and Postal Service aliases
are what is left.

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

What the site did with it on 2026-09-08: the node carried `placementDirectoryDisagreement`
(`listedUnder: "Energy Department"`, `directoryParentId: exec-dept-doe`, the
entry's URL, `checkedAt` 2026-09-08T19:19:15Z), `placementVerified` stayed
null, the existence claim "The Federal Register's agency directory lists it"
stood, and the Placement line read: *The Federal Register's agency
directory files it under "Energy Department", not under its parent here —
the two sources disagree, and neither is resolved.* Since the Government
Manual's organisation route landed (2026-09-20) the field holds the Manual's
disagreement instead, written over the directory's (`source:
us_government_manual`, `listedUnder: "Department of Energy"`, the same
`directoryParentId`, granule GOVMAN-2025-12-31-207), so the panel now reads
*The United States Government Manual files it under "Department of Energy",
not under its parent here*; `placementVerified` is still null, the
existence claim still stands, and the directory's own record still says
`disagrees`.

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
nodes carried it on 2026-09-08 (139 from the directory, 63 from the Senate list).

*Not in the official list* — only a complete list can say this: the
Senate's, and since 2026-09-13 the House Clerk's (§5.7). Each is complete
for what it lists: every subcommittee of a committee is listed under it,
so a graph subcommittee whose name is absent has
been checked and not found *by name*. The panel says exactly that and shows
the names the list does carry. It does not say the body has ceased to
exist; a renamed subcommittee reads the same way, which is what §5.1 is for.
The Federal Register's directory never produces this state, because an
agency that has not published in the Register is simply not in it. 27 nodes
carried it on 2026-09-08; 17 carry it on 2026-09-23 (8 from the Senate's
list, 9 from the House Clerk's).

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
the owner's to make — not by hand, since the curated file is never
hand-edited, but through the reviewed scripts that are its only writers
(§3, §9, §16) — and until it is made the site publishes the
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
**23 of 4,382 position nodes carried a rate of pay from a primary source**
when this section was opened: 15 judicial, 3 congressional, 5 White House
Office. The same day's expansion (§7.4) took the White House Office to 166,
so 184 by the end of 2026-09-14.

### 7.1 Blocked on one allowlist entry — three House leadership nodes

**Resolved (2026-09-23).** `us_code_pay_schedules.py` reads Schedule 6 from
the note to 5 U.S.C. § 5332 (committed at
`tests/fixtures/uscode/pay_schedules_5_usc_5332.html`), and the three nodes
below carry `positionStatutoryPay` at exactly these rates. As written on
2026-09-14: `uscode.house.gov` answered the proxy's CONNECT with 403 (see
`docs/NETWORK_ACCESS.md` §1b). It serves 5 U.S.C. § 5332 Schedule 6, which
states the statutory salaries of congressional leadership. Once the host was
reachable, three curated nodes would become priceable by a module that would
be a near-clone of `congressional_pay.py`:

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

*Superseded on 2026-09-30 (§19.13).* The multi-post rule became per field on
2026-09-23, and on the owner's instruction the bankruptcy benches are priced
at $229,908 from §153(a) with the arithmetic in the open; the magistrate
benches stay unpriced because §634(a)'s "up to" is a ceiling, not a rate.

28 U.S.C. § 172(b) (Court of Federal Claims) gives those judges the
district-judge rate; § 252 (Court of International Trade) does not — it sets
the salary by reference to section 225 of the Federal Salary Act of 1967,
which this paragraph misread as parity on 2026-09-14. The statutory text has
been reachable since 2026-09-18, and since 2026-09-23 `derived_pay.py` prices
the Tax Court (26 U.S.C. § 7443(c)(1)), the Court of Federal Claims, the CAAF
and the CAVC from the committed sections:
`jud-specialized-tax-chief-judge-tax-court` and seven other nodes carry
`positionDerivedPay`, and the Court of International Trade is refused.

### 7.3 Structurally out of reach — the graph carries no pay key

Three whole categories of official pay table could not reach any node in this
graph on 2026-09-14, for one shared reason: **the curated file records no pay
grade, no SES status and no GS grade/step/duty station on any node.** (The
curated file still records none. Since 2026-09-21 `gs_pay.py` reaches the SES,
SL/ST and GS tables through a different key — the pay plan and grade an OPM
Plum Book listing reports — and 18 positions publish a base-pay range in
`positionGradePay`: 16 SES, 1 SL, 1 GS-15.) Matching a node to a
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

After the expansion, **166 of the 249** White House Office positions carried a
rate; **188** do since 2026-09-23 (§19.4). The rest are refused, each for a
reason worth keeping:

- **54 stood for several posts; 32 still carry no rate.** A title the report
  lists several people under at differing salaries gets one node and no rate:
  one figure on such a node would read as what a single holder is paid. The
  other 22, whose every holder the report lists at one rate and whose count
  is the node's own, carry that rate since 2026-09-23.
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

**Still templated on 2026-09-15: 13, because no official source in hand named
the title** (12 of them were renamed from 5 U.S.C. §§ 5312–5316 on 2026-09-18;
only `Deputy Secretary of Department of Commerce` remains templated).
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
row not yet applied is re-fetched and re-tested on every run; a row whose
node already carries the proposed name is recorded `already_applied` before
any fetch, so its page is not re-read. The script refuses a row whose node no
longer carries the name the row was written against.

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
already recorded (§5.1 and §5.7 respectively) as names the official lists spell differently.

**The remaining 21** are EPA's ten regions and five courts of appeals, below,
and six rows this section does not itemise, among them NSF's Geosciences and
Engineering directorates (§9.4 refers back to them); every one is in
`data/curation/unit_renames.json`.

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
courts' own sites print. The owner approved the six short forms the same day
(commit 6563a9c), so `First Circuit`, `Third Circuit`, `Sixth Circuit`,
`Eighth Circuit`, `Tenth Circuit` and `Eleventh Circuit` are the curated
names now and the family carries both conventions (§15.1).

### 9.4 The 39 proposals declined, and why

  - **HUD's ten regions** (10). HUD's Field Leadership page names each region
    by headquarters city — `Region VIII - Denver` — and the match requires
    dropping the `HUD` the graph uses to keep its regions apart from EPA's and
    Education's identically numbered ones. A family decision that trades ten
    nodes' disambiguation for ten confirmations; left to the owner, who
    approved all ten the same day (commit 6563a9c): the curated file now
    carries HUD's own `Region I - Boston` through `Region X - Seattle`.
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
    names 80 nodes here and every `.gov` footer carries those words, which is
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
record, because OPM's FedScope file (March 2025, September 2024 beside it)
and its PLUM archive (January 2021 – January 2025) still name the bureau the
Food and Nutrition Service. The alternative was to
leave the graph stale about a rename USDA states on its own site, which is
worse: the node now reads as USDA reads it, and OPM has not caught up — its
current Plum Book export, read since 2026-09-21, still files 23 live rows
under `FOOD AND NUTRITION SERVICE`, which `plum_current.py` reports
unmatched. A second alias mechanism was not built for one record.
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
missing machinery — the one script that has rewritten a hand-curated description,
`merge_duplicate_nodes.py` (§3), carries only the two texts hard-coded beside
its two merges — which is itself worth noting: of the six scripts that write
the curated file, none can correct an arbitrary wrong sentence.

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
Education. That is 21, so with the 26 added the dispositions account for 47 of
the 48: the commit that applied them (fa1575b) records that the hand-typed
adjudication input "sent one candidate short".

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
**one disagrees**. Nothing is resolved either way and, on this pass, no field
was published from it: the Manual's hierarchy was measured and found to add
nothing the tree does not already evidence (all 39 agreeing edges already
carry placement from another source), so no placement was derived from the
Manual at all. That changed later the same day with the organisation route
(§15.4): the gate now reports 4 nodes placed under their parent by the
Manual's hierarchy and 1 filed elsewhere by it, the Federal Energy Regulatory
Commission, which publishes a `placementDirectoryDisagreement`. Recorded here
so the next pass need not re-measure it.

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
the file: OMB's guide says "these historical records are adjusted each year to
conform to the agency and account structure of the current budget", and the
BLS was a Commerce bureau
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
  parses as two fragments, so a Ways & Means subcommittee fails label
  equality on its own committee's page unless the committee fold rescues it:
  the two-word seats (Social Security, Work & Welfare) are confirmed there
  that way, and the one-word ones (Health, Oversight, Tax, Trade) never can be. A parser rule joining *inline*
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
  a rename — a candidate row for `mark_superseded_units.py`, whose table
  already carried the eighteen VISN rows (§16.4 says why none was added).
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
  Weaponization node (its `nameSource: named_on_its_own_official_page`)
  rests on that archived block — the very thing §9.4 declined a different
  proposal for. It earned no page confirmation: its evidence record is
  `inconclusive` (`only_an_ancestor_page_was_read`) and it publishes no
  `verificationMethod`.

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
| HPSCI | Subcommittee on Oversight and Investigations | docs.house.gov IG00 (four other committees have one; a cross-parent duplicate is allowed, this committee had none) |

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

Five more rows were added later the same day (commit 82d80c5) and are in
neither this table nor the measurements below: the Export-Import Bank, the CFPB,
the ODNI, CIGIE and the PCLOB. The CFPB row reverses the refusal §17.4 records.
It now rests on the Manual's entry 321 rather than on 12 U.S.C. 5491, although
the table's `_declined` list still carries the old refusal. The table holds 13
rows now, all accepted. None of the five yet carries a `verificationAliasMatch`
on the published graph: `govman_evidence.json` and `plum_current_evidence.json`
have not been re-derived since.

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
  guessed; a committed section of the Code would settle it. (Reversed later
  the same day, commit 82d80c5: `node_aliases.json` now accepts this row on
  the Manual's entry 321 rather than the statute, though its own `_declined`
  block still lists it.)
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

## 18. The current Plum Book's own agency list, reconciled (2026-09-21)

OPM's current PLUM export landed the same morning (`CLAUDE.md`, "The current
Plum Book, read"; `docs/NETWORK_ACCESS.md` §12) and its first derivation reached
**170 of the graph's 4,591 positions**. The binding constraint was not the title
matcher: **96 of the export's 174 agency names reached no organisation node at
all**, and 1,301 of its 9,797 live rows sat under them, so no position beneath
one could be reached however well its title matched. That is the same shape as
§13's Government Manual reconciliation, and this section disposes of all 96 the
way §13 disposed of the Manual's 95.

`data/audit/plum_unmatched_agencies_2026-09-21.json` is the table: every agency,
its live-row count measured from the committed export, its canonical key, the
disposition and the reasoning. The dispositions:

| Disposition | Agencies | Live rows |
|---|---:|---:|
| Node added under a verified licence | 36 | 324 |
| Node added, but the export spells the name otherwise | 3 | 8 |
| The graph already has the unit under another name (alias candidate) | 4 | 57 |
| An Office of Inspector General with no distinguishing name | 30 | 43 |
| No licence reaches it — a real unit, no readable official page | 13 | 108 |
| Constituted between governments; not a unit of the United States | 5 | 14 |
| The owner is deciding these separately (Navy, Army, Air Force) | 3 | 240 |
| Not one unit at all (Office of the Secretary of War) | 1 | 506 |
| Not a unit (the Vice President's official residence) | 1 | 1 |

**39 nodes were added**, every one under `official_page_label` and every one
re-tested by `scripts/add_curated_nodes.py` on the run: the row proposes a page
and the verifier's own `find_label_region_rule` decides, in the page's content
region, under its robots policy and readable-text floor. 38 sit under
`exec-ind-misc` ("Other Independent Agencies"), one — the Council on
Environmental Quality — under `exec-eop`.

The Government Manual could not license any of them, and the reason is
structural rather than incidental: of its 231 entities **105 are printed at top
level with no parent**, and every independent agency here is one of those, so
`manual_files_it_under` has no chain with which to reach a proposed parent. The
Manual licenses a placement only where it prints a hierarchy, which it does for
departmental bureaus and not for independent establishments. Several of the 39
were expected to earn `listed_in_us_government_manual` from the *organisation*
route once `derive_govman_evidence` next ran (it ran the same day, in merge
3ae6db7: all sixteen now carry the entry as `govmanEntry`, and one, the
Holocaust Memorial Museum, takes it as its method; the other fifteen keep a
method from another source), because the Manual does carry an
entry of their name — the Holocaust Memorial Museum, the Commission on Civil
Rights, the Surface Transportation Board, the International Trade Commission,
the Institute of Peace, the FRTIB, the DNFSB, the FMSHRC, the OSHRC, the
Inter-American Foundation, the African Development Foundation, the Trade and
Development Agency, the FMCS, ACUS, the Office of Government Ethics and the
ODNI. Licensing a node and verifying one are different acts, and this is the
clearest case of it yet.

**Fifteen of the 39 are licensed by usa.gov's A-to-Z index rather than by the
unit's own site**, and each says so on its row. Eight because the unit's own
host cannot be read at all — `ushmm.org` and `usip.org` do not answer
`robots.txt` from this sandbox, `dnfsb.gov`, `iaf.gov` and `acus.gov` answer it
403 and are refused by this project's policy, `jusfc.gov` answers a redirect the
fetcher does not follow, and `whitehouse.gov` (50–55 readable characters) and
`ncd.gov` serve a JavaScript shell below the readable-text floor. Six because the
unit's own readable page labels itself by a short form or an acronym and not by
the name the export and the Manual use: `frtib.gov`, `ustda.gov`, `oge.gov`,
`jamesmadison.gov`, `csosa.gov` and `macpac.gov` are each allowed and readable
and each failed the label test. MedPAC's row, the fifteenth, names no host of
its own.
`CLAUDE.md` already records usa.gov's index as a source of candidate pages
rather than of claims; here it is not being believed, it is being *read* — the
same label test runs against it as against any other page.

**Eight real units were refused and are recorded rather than added**, which is
the point of recording them: the President's Committee on the Arts and the
Humanities (25 rows, `pcah.gov` unreachable), the U.S.-China Economic and
Security Review Commission (14, `uscc.gov` readable and simply not carrying its
own full name as a label on either page tried), the Goldwater Foundation (9,
JavaScript shell), the Udall Foundation (9, labels its short form), the Utah
Reclamation Mitigation and Conservation Commission (4), the Federal Permitting
Improvement Steering Council (3), the Gulf Coast Ecosystem Restoration Council
(1) and the Semiquincentennial Commission (1).

**The five Executive Office units are one measurement worth keeping.** The
export files the Office of the National Cyber Director (24 rows), the Office of
the Vice President (11), the U.S. DOGE Service (4), the Office of Pandemic
Preparedness and Response Policy (1) and the Intellectual Property Enforcement
Coordinator (2) under its own `EXECUTIVE OFFICE OF THE PRESIDENT - <unit>` form,
whose scoped rule found no unit of the name beneath the EOP because the graph
has none. All five would have been added on one fetch each had `whitehouse.gov`
served text: it is allowed by `robots.txt`, returns 200, and carries 24, 50 and
55 readable characters on the three paths tried. The Manual carries **no
Executive Office entries at all** — not the EOP, not the White House Office, not
OMB — so that route is closed too. The CEQ is the one that landed, and only
because usa.gov's index happens to list it.

### 18.1 The Office of the Secretary of War: 506 rows, and nothing added

This was the largest single block and the one this pass was most at risk of
getting wrong. Nothing is added, for two independent reasons, either sufficient.

**First, the export's bucket is not a unit.** Beneath
`OFFICE OF THE SECRETARY OF WAR` the export files 42 rows under an organisation
of the same name, and the offices of the Under Secretaries (Research and
Engineering 39, Comptroller 29, Policy 25, Acquisition and Sustainment 14,
Personnel and Readiness 13, Intelligence & Security 6), the Assistant
Secretaries, Cost Assessment and Program Evaluation (23), the Department CIO
(16), Administration and Management (12) and Washington Headquarters Services
(15) — which genuinely are the Office of the Secretary. But it also files, in
the same bucket:

| Organisation in the export | Rows | Where this graph already carries it |
|---|---:|---|
| Defense Finance and Accounting Service | 20 | `exec-dept-defense-agencies` |
| Defense Health Agency | 12 | `exec-dept-defense-agencies` |
| Office of the Joint Chiefs of Staff | 8 | `exec-dept-defense-jcs` |
| United States Court of Appeals for the Armed Forces | 7 | the judiciary |
| Department of War Education Activity | 6 | `exec-dept-defense-agencies` |
| Defense Commissary Agency | 5 | `exec-dept-defense-agencies` |
| National Guard Bureau | 4 | no unit node; a `National Guard Bureau Chief` post under `exec-dept-defense-jcs` |
| Defense Advanced Research Projects Agency | 3 | `exec-dept-defense-agencies` |

It is OPM's reporting bucket for the Department other than the three military
departments, not an organisational unit. A single node carrying all 506 rows
would file a DARPA director, a commissary chief executive and an Article I
appellate judge inside the Secretary's immediate office. That is precisely the
over-claim a 506-row attachment risks, and it is worse than no attachment.

**Second, no licence reaches it.** Checked, not assumed:

- the **Government Manual**, 2025-12-31 edition, committed at
  `tests/fixtures/govman/` and digest-checked: no "Office of the Secretary"
  entry among its 231 entities. Its Defense entries are the department itself,
  the three military departments, "Defense Agencies" and the Joint Service
  Schools;
- the **Monthly Treasury Statement**: its only `Office of the Secretary` line
  (classification 59309312, record date 2026-08-31) sits under the Department of
  Transportation. There is no Defense one;
- the **department's own pages**: `www.defense.gov`, `dod.defense.gov` and
  `www.war.gov` each answer `robots.txt` with **403 on three attempts** and are
  refused by this project's policy. No page can be read, so
  `official_page_label` has nothing to test.

### 18.2 Whether the department has been renamed: four documents against one

§14.3 recorded one clause in OMB's FY2027 user's guide — "for technical reasons,
the Department of War is referred to as the Department of Defense" — and
deliberately did nothing about it. The PLUM export raises the same question from
the other side, and this is what the documents in hand actually say.

| Document | Fetched / edition | What it prints |
|---|---|---|
| United States Government Manual | 2025-12-31 edition | **Department of Defense** (entity 114), with Air Force, Army, Navy and "Defense Agencies" beneath it |
| Federal Register agency directory | 2026-09-08 | **Defense Department**; no War Department entry |
| Monthly Treasury Statement, Table 5 | record date 2026-08-31, fetched 2026-09-20 | **"Department of Defense--Military Programs"**, and "Department of Defense Medicare-Eligible Retiree Health Care Fund" |
| USAspending toptier agency list | committed fixture | **Department of Defense** |
| OPM PLUM current export | 2026-09-21 | **War** — "OFFICE OF THE SECRETARY OF WAR", "OFFICE OF THE DEPARTMENT OF WAR CHIEF INFORMATION OFFICER" |

Four official documents, three of them more recent than the Manual, still print
Defense; one prints War. The export is also **internally mixed**: it keeps
`DEPARTMENT OF THE NAVY`, `DEPARTMENT OF THE ARMY`, `DEPARTMENT OF THE AIR
FORCE`, `DEFENSE FINANCE AND ACCOUNTING SERVICE`, `DEFENSE HEALTH AGENCY`,
`DEFENSE ADVANCED RESEARCH PROJECTS AGENCY` and
`DEPARTMENT OF DEFENSE OFFICE OF THE INSPECTOR GENERAL` in the same file that
spells the Secretary's office War.

**So the graph's `Department of Defense (DoD)` is not renamed, and no node is
created under either name.** The rule §9 sets is that a name must be carried by
a source and re-checked against it; here the sources disagree, and the one that
would settle it is the department's own page, which this project cannot read.
§14.3's conclusion stands and is now backed by a measurement rather than a
single sentence. Recorded so the next pass starts here.

### 18.3 Thirty Offices of Inspector General, and the floor that nearly missed them

The export files an Office of Inspector General as a peer agency of its
department — 30 of them, 43 live rows. Every one is a real statutory office and
this graph has a node for none of them; what it has is an `Inspector General`
**position** under most of the parents, one of the stamped administrative titles
`CLAUDE.md` documents, which names **80 nodes** here.

None is added, because the name that identifies the unit is "Office of Inspector
General" and it identifies thirty of them. The export's qualified string
("Department of Labor Office of Inspector General") is OPM's own scoping, not a
name any page carries as a label, so a node under it would be named by no
source; and a node under the unit's own name would be exactly the generic name
`GENERIC_NAMES` exists to refuse.

**A defect in that floor, found by trying it.** `GENERIC_NAMES` in
`scripts/add_curated_nodes.py` carried `"office of the inspector general"` and
not the `the`-less `"office of inspector general"`, which is how most of these
offices style themselves and what `canonical_name_key` returns for them. The
floor would therefore **not** have refused these thirty; they are declined on
the principle the floor exists for, not on its letter. Nothing is changed in the
script here — a floor is a gate, and widening one is a code decision for the
owner — but the gap is recorded so it is not rediscovered by something that goes
through it. (Closed the same day by the merge that integrated this section,
3ae6db7: the script now imports the one `GENERIC_NAMES` in
`data_pipeline/verification/aliases.py`, which carries both spellings.)

Two of the thirty do have distinguishing names of their own — the Office of the
Special Inspector General for Pandemic Recovery (3 rows) and the Treasury
Inspector General for Tax Administration (1) — and both are still declined,
because the export's string is not that name, so a node under the official name
would reach none of their rows. Real gaps, recorded.

### 18.4 Five bodies constituted between governments

The Great Lakes Fishery Commission (5 rows), the International Joint Commission
(3), the Interstate Commission on the Potomac River Basin (3), the International
Boundary and Water Commission (2) and the Asian Development Bank (1) are listed
by OPM because federal appointments are made to them. None is a unit of the
United States government: the first two and the fourth are established by treaty
between the United States and Canada or Mexico, the third by an interstate
compact, and the fifth is an international financial institution the Manual
lists among international organizations rather than as part of the government.

The IBWC is the closest call and is recorded as such: its **United States
Section** is a federal agency on a `.gov` host with appropriated funds, and had
the export named that section it would have been added. The export names the
whole commission, and a node of that name would place a body constituted between
two governments inside the United States government's tree. Left unresolved
rather than guessed — the treatment §14.1 gives the PBGC and `CLAUDE.md` gives
the Treasury's Tax Court line.

### 18.5 What it moved, measured

Re-running `scripts/derive_plum_current_evidence.py` against the curated file
after the 39 nodes landed:

| | Before | After |
|---|---:|---:|
| Agencies matched | 78 | **114** |
| Agencies unmatched | 96 | **60** |
| Live rows under an unmatched agency | 1,301 | **977** |
| Organisations matched | 161 | **191** |
| Positions listed | 170 | **170** |
| Placements | 170 | **170** |
| Pay records | 100 | **100** |

**The published claims did not move at all, and that is the honest result rather
than a disappointment.** It is exactly what §13 recorded when the 26 Manual
units landed and the PLUM archive's records stayed at 129: the export lists
*positions*, and these 39 nodes have no position children, so more of the
export's organisations are now reachable and none of its rows reached a new
post. A matching count is not a published claim. What the 39 nodes buy is what
the 26 bought — a place for evidence to land when a later pass curates the posts
beneath them, and, for the sixteen the Government Manual names, an existence
method the moment the organisation route next runs.

Three of the 39 added nodes are themselves still unmatched by the export, and
deliberately: the ODNI, CIGIE and the Interagency Council on Homelessness are
named as their own sources name them, not as the export spells them. Those three
and the four units the graph already carried under another name are handed off
in `data/audit/plum_alias_candidates_2026-09-21.md`; nothing was aliased here.
`plum_current.py` has no alias table of its own, but since §17 it consults the
shared `data/curation/node_aliases.json`, and later the same day (commit
82d80c5) that table took rows for the ODNI, CIGIE, the Export-Import Bank, the
PCLOB and the CFPB and declined the Interagency Council on the Homeless as a
succession claim. `plum_current_evidence.json` has not been re-derived since; a
dry run now matches 120 agencies against its committed 115.

**Nothing measured moved and nothing was superseded or renamed.** The curated
file gained 39 nodes and lost nothing: `add_curated_nodes.py` only ever adds,
and the diff is additions only. The cost cascade will reapportion
`exec-ind-misc`'s pool across 70 children instead of 32 on the next build, which
is the same honest consequence §13 records for the Manual's 26 — every sibling's
*estimate* moves because real units now share the pool, and no measured figure
does.

### 18.6 The gains were not confined to the export, and one of them is publishable

The same thing happened here that §1 and §13 record for the fifteen Treasury
units and the Manual's twenty-six: other sources already held rows for these
units and reached them the moment the nodes existed, with **no matcher change at
all**.

**OPM FedScope — 15 new published headcounts.** The employment table already
carried an agency row for fifteen of the 39: the Holocaust Memorial Museum
(109), the International Trade Commission (443), the Surface Transportation
Board (126), the DNFSB (112), the Office of Government Ethics (72), the
Commission on Civil Rights (60), the Trade and Development Agency (59), the
Inter-American Foundation (36), the African Development Foundation (32), the
Armed Forces Retirement Home (311), the Marine Mammal Commission (23), the
Nuclear Waste Technical Review Board (22), the National Council on Disability
(18), the Commission of Fine Arts (12) and the Interagency Council on
Homelessness (13). Records go **164 → 179**, agencies matched **59 → 74**,
and `compare_with_curated`'s "compared" is **unchanged at 128** — no figure that
was already being compared moved; all fifteen are nodes with no curated
`employees` of their own, so `no_curated_figure` goes 36 → 51. That is the
honest state for a node whose whole basis is a page naming it.

**Nine more headcounts are within reach and are refused, correctly.** FedScope
abbreviates the *agency* row for nine of these units — `FED RETIREMENT THRIFT
INVESTMENT BOARD`, `ADV COUNCIL ON HISTORIC PRESERVATION`, `CMSN FOR PRES OF
AMERICA'S HERITAGE ABRD`, `FED MINE SAFETY AND HEALTH REVIEW CMSN`,
`OCCUPATIONAL SAFETY & HEALTH REVIEW CMSN`, `MEDICAID & CHIP PAYMENT & ACCESS
COMM`, `COUNCIL OF INSP. GEN. ON INTEG.& EFFIC.`, `FED MEDIATION AND
CONCILIATION SERVICE`, `JAPAN-UNITED STATES FRIENDSHIP CMSN` — while the
sub-agency row beneath spells the name out and does match the new node. The
matcher refuses them (`unscoped_refused` 8 → 17) on the rule this file already
records: a unique name is not evidence of placement. Undoing FedScope's agency
abbreviations the way the leading `NATIONAL` is undone would reach all nine;
that is a matcher decision for the owner and is deliberately not taken here.

**The PLUM archive — 33 more agencies, no new record.** The archive of the
previous administration files rows under almost all of these units too:
agencies matched **70 → 103**, organisations **181 → 208**. Its published
records stay at **129**, because none of the 39 has a position child for a row
to reach. The same distinction §13 draws: a matching count is not a published
claim.

**What was and was not regenerated.** `data/verification/plum_current_evidence.json`
was re-derived, and its 170 listings and 100 pay records came back
byte-identical — only the `report` block's matching counts moved.
`headcount_evidence.json` and `position_evidence.json` were **not** re-derived
here, so the fifteen new FedScope headcounts were measured above but not yet
written, and `output/` was not rebuilt. The headcounts and the rebuild both happened the same day in the merge
that integrated this section (3ae6db7): `headcount_evidence.json` now holds 179
records and all fifteen publish `employeesOfficial`. `position_evidence.json` is
still not re-derived — its report reads 70 agencies and 181 organisations — which
moves no published record.

## 19. The third research pack, read against the documents (2026-09-23)

`docs/PAY_SOURCE_RESEARCH_PROMPT_3.md` was run: a lead prompt on which pay
systems exist and where each is published, and enumeration shards naming every
unpriced title. The owner pasted the answers to Prompt 0 and to the shards
covering the White House Office, the Federal Reserve and VISNs 15–23. What
follows is what each answer was checked against and what it did or did not
license. The standing rule applies to research as it applies to a page: a
figure is published only from a document this repository has read, and a
research answer is a lead, never a source.

### 19.1 The Federal Reserve: a figure the statute does not print

The shard reported the Chair's salary as "$203,500 per annum | likely", citing
12 U.S.C. § 242. The section was fetched (`tests/fixtures/uscode/
fed_12_usc_242.html`, `robots.txt` allows the path, digest recorded) and it
prints **no dollar figure at all**. `tests/test_statutory_schedule.py::
ReviewedMirrorTests::test_the_section_prints_no_salary_figure` pins that
against the committed bytes, so the claim cannot be re-introduced by anybody
remembering the research rather than the page.

What § 242 does print is the *identification*: "1 shall be designated by the
President, by and with the advice and consent of the Senate, to serve as
Chairman of the Board for a term of 4 years", "2 shall be designated … to serve
as Vice Chairmen of the Board", and "1 of whom shall be designated Vice Chairman
for Supervision". That is the document the route needed, because neither
matcher in `statutory_schedule.py` could reach the three posts: the graph's
"Chair, Board of Governors" is not equal to the Code's "Chairman, Board of
Governors of the Federal Reserve System" (§ 5312, Level I), and the Vice Chairs
are placed by a title that never names them — § 5313 prints "Members, Board of
Governors of the Federal Reserve System" (Level II). `REVIEWED_TITLE_ROWS` is
the reviewed table: node → statutory title, with the § 242 sentence that says
why the node is that office, re-checked on every run in the section's
*operative* text (the page prints each sentence a second time in its
Amendments note, and the cut is what keeps a repealed sentence from ever
counting). Three posts priced at the rates 5 U.S.C. §§ 5312–5313 joined to
OPM's Salary Table 2026-EX give — $253,100 and $228,000 — each resting on
**three** documents, of which one states the figure, graded `partial`.

**"Governor (×4 members)" is deliberately not priced.** The same "Members"
title reaches it, but it stands for several posts and `positionSchedulePay` is
an incumbency-class field the multi-post sweep strips (§19.4), so a row would
be written and withdrawn on every build. Pricing a bench from a class title is
a separate decision and is left to the owner.

### 19.2 VISNs 15–23: the shards contradict each other, and the module's refusal stands

The VA shards priced service chiefs from the Title 38 tables by choosing a
table per clinical specialty — and disagreed with one another about which table
applies: one shard filed `Chief — Dental Service` at Table 1's Tier 2, another
at Tier 3. That is exactly the failure `va_title38_pay.py` refuses by name:
Tables 1 and 2 print the same leadership titles at *different* ranges because
they cover different specialty lists, so choosing a table per node is this
repository deciding which VA service chiefs are doctors. Two research passes
reading the same PDF and reaching different tiers for one title is the
measurement that the refusal is right, not an argument for relaxing it.
Nothing was priced from these shards; `Chief — Dental Service` and the other
service chiefs stay in `docs/UNPRICED_POSITIONS.md` under `unreached`.

### 19.3 The White House Office: the shard cited last year's report

The WHO shard cited the 2025 Annual Report to Congress on White House Staff.
This repository reads the 2026 report (`tests/fixtures/whitehouse/`, the
Section 6 disclosure as of July 1, 2026), which is the one already committed
and gated. The shard added no document; what it did prompt was a re-read of
the multi-holder titles, which §19.4 records.

### 19.4 What the pack was actually good for: the multi-post rule, made per field

Prompt 0's structural answer was right about one thing the graph had been
getting wrong in the other direction: a rule written for one shape of claim
had been applied to all eight pay fields. `withdraw_pay_from_multi_post_nodes`
stripped **every** pay field from a node stating a multiplicity, on the
reasoning that "one rate beside a panel describing a whole group reads as what
one holder earns". That is true of an incumbency-shaped claim — a listing, a
row of the current export, one office's archived level — and false of a claim
that holds for every holder by its own terms:

- a **tier or parity rate** (`positionStatutoryPay` from uscourts.gov,
  `positionDerivedPay` from a parity provision) is paid to *every* judge of the
  tier: "Each judge shall receive…";
- a **band** (`positionTierPay`) states bounds every holder is within;
- a **roster** (`positionReportedPay`) lists every holder by title, and where
  all N are at one rate, the rate is the group's fact and not one person's.

So the sweep is now per field (`pay_tables.INCUMBENCY_PAY_FIELDS` stripped;
`OFFICE_RATE_PAY_FIELDS` kept and stamped with a `holders` block saying how
many and that it applies to each; `UNIFORM_ROSTER_PAY_FIELDS` kept only when
every holder is at one rate and the count equals the node's own stated
multiplicity). **28 multi-post nodes priced**: `Judge (×18)` and the other
three Article I benches from their courts' own parity provisions; the eight
Associate Justices and a district's own active judges from the compensation
table; and 22 White House Office titles the roster lists N times at one rate
(`Special Assistant (×4)`, `Presidential Speechwriter (×2)`, …). The rule that stayed: a bench whose name bundles
senior judges (`Circuit Judge (×28 active + senior judges)`) is refused, because
28 U.S.C. § 371(b)(2) sets an uncertified senior judge's salary by reference to
a past year (the salary last drawn in active service or when last certified,
adjusted under § 461), not necessarily the tier's current rate, so one rate for
the bench would be false of some of its members. (A first draft said "frozen";
the section's last sentence says "adjusted", and the wording follows the
section now.) `tests/fixtures/uscode/
senior_judges_28_usc_371.html` is committed for that reason.

### 19.5 Standing correction: the CAVC's repealed subsection

Recorded in `CLAUDE.md` and repeated here because the research pack could
re-surface it: 38 U.S.C. § 7253(e) as it read *before amendment* — the chief
judge at the circuit rate — is printed on the page in the Amendments note and
is not the law. A quote is accepted only from the operative text, and the
repealed sentence is refused by the gate wherever it appears in a derived-pay
block.

### 19.6 Which prompts have been run, and where the next one starts

The pack is regenerated whenever a position gets priced, and its prompt
numbers shift when it is, so a record of what was run has to name the commit
the numbers came from.

- **Run:** Prompt 0 and prompts 1–3 of the pack as committed at `77a13f6` —
  the White House Office, the Federal Reserve, and VA Medical Centers under
  VISNs 15–23. Nothing came back for that pack's prompt 4.
- **In the pack as committed at `b25d64c`** (the same unpriced list as
  `f5a1240`, with rule 4 reworded to the per-field multi-post rule), those
  answers cover **prompts 1–5 in full** — prompts 1–2 are the same nodes, and
  prompts 3–5 are the same 24 VA medical-centre titles under the other VISNs,
  which the Title 38 answer and §19.2's refusal already decide — and the
  **Federal Reserve block of prompt 6** (23 titles).
- **Next:** prompt 6 without its Federal Reserve block, then 7–10, then a
  yield check before 11 onward. The first batch covered 301 titles and yielded
  one usable lead (§19.1, three posts priced).
- **Held:** prompts 30, 32, 33 and 35–39 are dominated by committee chairs and
  ranking members (438 posts, every one held by a Member of Congress) and by
  committee staff. Asking about those title by title is several prompts spent
  learning one fact; the chairs are an owner decision about a reviewed
  identification (a chair is a Member, paid under Schedule 6, the chairmanship
  adding nothing), not a research question.

### 19.7 The fourth batch: six Executive Schedule rows survive, the military table is walled (2026-09-27)

The owner pasted the answers to prompt 6 (without its Federal Reserve block)
and prompts 7–10 of the pack as committed at `b25d64c`. Checked against the
committed sections of 5 U.S.C. §§5312–5316 rather than taken on the answer's
own grade:

**What survived — six reviewed identifications**, each the Fed's shape (§19.1):
the Code prints a title this graph does not, and a second statute says which
office it is. All six basis sections were fetched from `uscode.house.gov` and
committed under `tests/fixtures/uscode/`; every quoted sentence is in the
section's operative text, above the publisher's notes, by both readers.

| Node | Code title (level) | Basis | The sentence relied on |
|---|---|---|---|
| `Chair, FCC` | Chairman, Federal Communications Commission (III) | 47 U.S.C. 154 | "The Chairman of the Commission … shall receive an annual salary at the annual rate payable from time to time for level III of the Executive Schedule." |
| `Chair, FTC` | Chairman, Federal Trade Commission (III) | 15 U.S.C. 41 | "The President shall choose a chairman from the Commission's membership." |
| `Commissioner, IRS` | Commissioner of Internal Revenue (III) | 26 U.S.C. 7803 | "There shall be in the Department of the Treasury a Commissioner of Internal Revenue …" |
| `Administrator, FAA` | Administrator, Federal Aviation Administration (II) | 49 U.S.C. 106 | "The head of the Administration is the Administrator …" |
| `Secretary of the Department of Homeland Security` | Secretary of Homeland Security (I) | 6 U.S.C. 112 | "There is a Secretary of Homeland Security, appointed by the President …" |
| `Deputy Secretary of the Department of Homeland Security` | Deputy Secretary of Homeland Security (II) | 6 U.S.C. 113 | "A Deputy Secretary of Homeland Security, who shall be the Secretary's first assistant …" |

The FCC's is the one basis that states the level itself, and it agrees with
§5314. The two DHS posts were unpriced only because §8 kept OPM's archive
spelling ("of the Department of"), which whole-name equality cannot reach; a
reviewed row prices them without renaming anything. Positions priced from the
Schedule **102 → 108**, pay claims **492 → 498**, unpriced **4,099 → 4,093**.

**What the batch got wrong, checked against the bytes.** Its "certain" grades
were unreliable in the same way §19.1's dollar figure was: inspectors general
are not printed in §§5312–5316 at all (their pay is set by a provision this
repository has not read, so nothing here says what it is); the IRS Chief Counsel is printed at
**Level V** (§5316), not IV; the Code prints no "Deputy Secretary of Commerce"
(the refusal §8 already records) and no CDC Director. None of those was
written into a row.

**Left unpriced, deliberately.** "Members, Federal Communications Commission"
and "Members, Federal Trade Commission" (Level IV, §5315) reach the two
`Commissioner (×4)` benches exactly as "Members, Board of Governors" reaches the
Fed's `Governor (×4 members)`; `positionSchedulePay` is incumbency-class and
would be stripped on every build, so pricing a bench from a class title stays
the owner's open decision (§19.6), now with three benches waiting on it rather
than one.

**The military basic-pay table: walled, recorded, not worked around.** The
batch named DFAS's basic-pay tables as the document for the Joint Chiefs, the
service chiefs and the senior enlisted advisers. `www.dfas.mil`,
`militarypay.defense.gov`, `comptroller.defense.gov`, the Coast Guard's two
hosts and all six service hosts answer `robots.txt` **and** the pay-table page
with an Akamai 403 from this sandbox — the host refusing the crawler, not the
proxy and not a rule. `tests/fixtures/dfas/README.md` records every attempt
with `fetch_fixture.py`'s own `.meta.json`. What is committed is the law the
table rests on, 37 U.S.C. 203 and 1009: §203(a)(2) caps O-7 to O-10 basic pay
at the monthly equivalent of Executive Schedule level II, and a ceiling is not
a rate, so nothing is published from either. The module, if a DoD-published
table ever answers, is `derived_pay.py`'s shape — grade from Title 10, rate
from the table, neither stating the figure — and it also has to settle a
duplicate-office question the graph carries: each service chief sits both
under the Joint Chiefs of Staff and under their own service, and one salary
must not be published twice.

**Next:** the yield check §19.6 called for. Two batches, ~40 prompts' worth
of titles, have yielded nine reviewed rows and one walled document; prompts 11
onward are worth running only if the owner still wants Executive Schedule
coverage at that rate.

### 19.8 The benches, priced from the Code's class title; the fifth batch triaged (2026-09-27)

**The decision.** The owner: "price the ×4 benches from the class title."
Five nodes stand for a bench the Code places as a class — "Members, Federal
Communications Commission" and its FTC, CFTC and FERC counterparts at Level
IV, "Members, Board of Governors of the Federal Reserve System" at Level II —
and each is now priced for every holder from that title, on a reviewed row
marked `classTitle` whose basis is the statute composing the body (47 U.S.C.
154, 15 U.S.C. 41, 7 U.S.C. 2, 42 U.S.C. 7171, 12 U.S.C. 241). The mechanism
and its guards are in `CLAUDE.md` ("Benches priced from the Code's class
title"); the one point to record here is the trap in 12 U.S.C. 241, whose
operative text still prints "shall each receive basic compensation at the
rate of $15,000 per annum" — the 1935 figure. Nothing publishes it; the row's
basis names it so nobody re-finds it later and thinks the module missed a
printed rate.

**Nine more single-post rows** from the fifth batch survived the same check
as §19.7's: the Code prints the title, a second statute identifies the office,
its section is committed and its quoted sentence is in the operative text by
both readers. Chair, CFTC (III; 7 U.S.C. 2); Chair, FERC (III; 42 U.S.C.
7171); Director, OPM (II; 5 U.S.C. 1102); Commissioner, SSA (I) and Deputy
Commissioner, SSA (II; 42 U.S.C. 902 — subsection (b)(3) itself says "level
II of the Executive Schedule", agreeing with §5313); Administrator, FEMA (II;
6 U.S.C. 313); Director, BLM (V; 43 U.S.C. 1731); Director of the CIA (II;
50 U.S.C. 3036) and Deputy Director of the CIA (III; 50 U.S.C. 3037);
Administrator, CMS (III; 42 U.S.C. 1317). Reviewed rows 9 → 24; positions
priced from the Schedule 108 → 123; pay claims 498 → 513; unpriced 4,093 →
4,078.

**What the batch got wrong, checked against the committed table.** Its
OPM "pay-freeze memo" figures — $203,500 (I), $183,100 (II), $168,400 (III),
$158,500 (IV), $148,500 (V) — are not the 2026 rates: Salary Table
2026-EX, committed and pinned, prints $253,100, $228,000, $209,600,
$197,200 and $184,900. Whatever year that memo's figures belong to (it was
not fetched), they were quoted as if current on every SSA, OPM, NOAA, NNSA
and CMS row and on the Vice President's Senate node ($235,100 against
Schedule 6's $292,300). None was used; the level identifications
behind them were checked against the Code instead, and where the Code
prints the title a row was written on the Code, not the memo.

**Refused, with the reason:**

- **Eleven Senate leadership roles at $174,000** (whips, conference chairs,
  policy and steering chairs, campaign committee chairs): that is a
  Senator's pay under Schedule 6, and senate.gov's footnote names only the
  three roles `congressional_pay.py` already prices. Pricing a whip as a
  Member is the committee-chair decision §19.6 holds, not a new fact.
- **NOAA Administrator, NNSA Administrator**: the Code prints neither
  "Under Secretary of Commerce for Oceans and Atmosphere" nor "Under
  Secretary for Nuclear Security" in §§5312–5316 as committed; only "Principal
  Deputy Administrator, National Nuclear Security Administration" (IV), for
  which the graph has no node. NNSA's two Deputy Administrators are not
  printed at all.
- **Archivist of the United States**: printed at both §5314 and §5316, which
  `load_schedule` drops as ambiguous rather than adjudicating.
- **Deputy USTRs (×3, three named nodes)**: the Code prints "Deputy United
  States Trade Representatives (3)" — a counted plural the matcher refuses.
  Identifying three individually named nodes with one counted class is a
  further shape (each node IS one of the three), not the bench shape landed
  today; deferred rather than stretched.
- **Comptroller General and Deputy Comptroller General**: 31 U.S.C. 703(f)
  was fetched and committed. It sets their pay "equal to the rate for level
  II [and III] of the Executive Schedule", but §§5312–5316 do not print the
  titles, so no reviewed row can reach them. This is `derived_pay.py`'s
  shape — the statute names the tier, OPM's table prices it, neither states
  the figure — and a module, not a row.
- **Inspectors General (80 nodes)**: 5 U.S.C. 403(e) was fetched and
  committed: "the rate payable for level III of the Executive Schedule under
  section 5314 of this title, plus 3 percent". A figure no document prints,
  reached by arithmetic on a printed one — a step further than `derived_pay`
  goes. Not built; the section is in hand for when it is decided. The
  batch's "5 U.S.C. 403(e)" citation was right and it printed no figure,
  which is the honest form.
- **The military rows** (Commandant, Sergeant Major, the combatant
  commanders): §19.7, walled at every DoD host.
- **CRS Director** "at the SL/ST maximum $228,000": a range's ceiling is not
  a rate, and the graph carries no listing putting the post on that plan.
- **SCOTUS officers** (28 U.S.C. 671–675), **FSA COO** (20 U.S.C. 1018),
  **NASA Center Directors** (an SES tier designation), **Deputy U.S.
  Marshals** (a special-rate table): each names a pay system and prints no
  figure for the post, or prints a range with no listing to tie it to. The
  bankruptcy and magistrate judges' "92 percent of district judge salary"
  (28 U.S.C. 153, 634) is a derived percentage — `derived_pay`'s shape once
  more, on two multi-post benches — and is a candidate, not a row.

**Next:** the yield check stands. Prompts 11 onward can wait; three module
decisions now carry more than any prompt would: the GAO/IG tier-reference
shape (statute names the level, table prices it — 82 posts), the counted-class
shape (Deputy USTRs), and whether committee chairs and Senate whips are
Members paid under Schedule 6.

### 19.9 The tier-reference module; the sixth batch triaged (2026-09-28)

**Built, on the owner's instruction: "build the tier-reference module for
GAO and the IGs."** `data_pipeline/verification/tier_reference_pay.py`,
`scripts/derive_tier_reference_pay_evidence.py`, the ninth pay field
`positionTierReferencePay`. The shape and its guards are in `CLAUDE.md`
("Pay set BY REFERENCE to a level"); what belongs here is what the
statute's own list decided and what it refused.

**29 derived, 28 published.** The Comptroller General at Level II
($228,000) and the Deputy at Level III ($209,600) from 31 U.S.C. 703(f), and
27 Inspectors General at Level III plus 3 percent — **$215,888, a figure no
document prints** — from 5 U.S.C. 403(e), scoped by 401(1)'s own list of
establishments: fifteen departments, and the EPA, NASA, OPM, the SBA, the
SSA, the FCC, the NRC, the FDIC, the TVA, the Export-Import Bank, the NSA and
the NRO. The Department of Justice's IG is derived and not published,
because it carries OPM's archived listing with a printed level and rate and
a figure set by reference never displaces a printed one.

**54 `Inspector General` nodes refused, and the list is the reason, not a
judgement about the node.** The stamped IGs under DIA, NGA, DARPA, DLA,
DCAA, DCMA, DCSA, DISA, DTRA, MDA, DFAS, DHA, DoDEA and PFPA — none is an
establishment; the designated Federal entities' (NLRB, EEOC, FEC, EAC, OSC,
MSPB, FLRA, NMB, CSB, PCLOB, PRC, the FCA, the NCUA, the PBGC, the ARC, the
NCPC, the ABMC, the SEC, the FTC, FERC, the CPSC, the CFTC, the FMC, the
NTSB, USAGM, the NEA, the NEH, the DFC, the Peace Corps, the Selective
Service, the Smithsonian, NARA, NSF) — 5 U.S.C. 415 was fetched and
committed and its operative text prints no rate of pay, so "looked and it
states none" is what the refusal rests on; the legislative branch's four
(GAO, the Library, the Architect, the Capitol Police), which 401(2) excludes
by name; the CIA's, whose statute is 5 U.S.C. 423 and has not been read (the
batch's "403(e) via 423(a)(1)" was not checked and is not relied on); the
FBI's `Inspector General (DoJ IG covers FBI)`, under a bureau; and
AmeriCorps, whose IG the Act does cover — 401(1) says "the Corporation for
National and Community Service" — but reaches only through the alias table,
which no join that lands a number may read. That last is a real cost of a
rule this repository chose, recorded as such.

**The sixth batch, triaged against the committed Code.** Its level
identifications were right this time and its dollar figures were the
pay-freeze memo's again ($168,400, $183,100, $158,500, $203,500 — not the
2026 table's); none was used. What the Code prints, and what a reviewed row
could reach once its basis section is fetched (none was, this round):

- **Director, NIST** — the Code's own title says the identification:
  "Under Secretary of Commerce for Standards and Technology, who also serves
  as Director of the National Institute of Standards and Technology" (III).
- **Chair, NRC** — "Chairman, Nuclear Regulatory Commission" (II); **NRC
  `Commissioner (×4)`** — "Members, Nuclear Regulatory Commission" (III), the
  class-title bench shape §19.8 landed; the three NRC office directors the
  batch graded IV are printed ("Director of Nuclear Reactor Regulation,
  Nuclear Regulatory Commission" and two more) and reach nothing because the
  graph writes "Director — Office of Nuclear Reactor Regulation".
- **Administrator, SBA** (III); **Director, NSF** (II) and **Deputy
  Director, NSF** (III); **Director (Drug Czar)**, ONDCP — "Director of
  National Drug Control Policy" (I); **Commissioner, BLS** (IV, printed with
  a footnote mark as "The 2 Commissioner of Labor Statistics"); **Director,
  Census Bureau** (IV); **Chair, CEA** (II) and the two single `Member, CEA`
  nodes — "Members, Council of Economic Advisers" (IV), the Vice-Chair shape;
  **Chair, CPSC** (III). CPSC's `Commissioner (×4)` is "Members, Consumer
  Product Safety Commission (4)" — a counted plural the matcher refuses, so
  that bench stays out until the counted-class shape is decided.

**Refused, with the reason:**

- **USPS officers at $342,280 / $313,000 / $346,780** from 8-K filings:
  those are named individuals' compensation disclosures, person-level by
  construction; this project never publishes a figure tied to a person's
  name, and USPS is not on any pay system this repository reads.
- **USPS Board of Governors** "$30,000 a year plus $300 a day": a statutory
  figure (39 U.S.C. 202) printed on a web page, on a node standing for nine
  members — a `positionStatutoryPay`-shaped candidate needing the statute
  read, and a `holders` block; not a row.
- **Director, NEC at $195,200 from the White House roster**: the roster
  module is scoped to the White House Office subtree, as `headcounts.py`
  scopes a FedScope row, and the NEC is a sibling office; widening the scope
  is a decision, not a match.
- **AUSAs on the AD pay-plan charts, the JCT chief of staff (2 U.S.C. 4302),
  NASA centre directors, the USMS special-rate table, the Mint, the BEP, the
  House Clerk's office, the Smithsonian museums** (whose curated structure is
  itself a repeated template, and whose staff "can sit side by side" on
  federal and trust rolls, as the batch itself notes): each names a system or
  a range and no figure for the post, or no document at all.
- **JPL and the DOE laboratories as "not federally paid"**: a curation fact
  worth having — contractor-operated laboratories' staff are not federal
  employees and no federal pay document can ever price them — and one this
  repository cannot publish from a research answer; the DOE page the batch
  cites was not fetched.
- **The combatant commanders at "$18,999.90 per month"**: DFAS, walled
  (§19.7); and a monthly basic-pay figure for O-10 is capped by 37 U.S.C.
  203(a)(2) at the monthly equivalent of Level II, which is the ceiling and
  not necessarily the rate.

**Next:** the candidate rows above are fifteen posts for eleven basis
fetches on a host that answers; the counted-class shape (Deputy USTRs, the
CPSC bench) and the Members-paid-under-Schedule-6 decision (chairs, whips)
are the two decisions still open.


### 19.10 Thirteen reviewed rows from §19.9's list; the seventh batch triaged (2026-09-28)

**Added, on the owner's instruction: "add the fifteen reviewed rows."** §19.9
called its candidate list fifteen posts; counted by node id when the rows were
written it is **thirteen**, one of them a bench of four, and the miscount is
recorded here rather than the list restated. The rows are the Fed's shape
(§19.1): the Code prints the title, a second statute identifies the office,
and the quote is re-found in that section's operative text on every run by
the module and by the gate's own reader. Ten basis sections fetched and
committed under `tests/fixtures/uscode/`; every fetch answered.

| Node | Statutory title (level) | Basis |
|---|---|---|
| `Director, NIST` | Under Secretary of Commerce for Standards and Technology, who also serves as Director of the National Institute of Standards and Technology (III) | 15 U.S.C. 273a(d): "The Under Secretary shall serve as the Director of the Institute" |
| `Chair, NRC` | Chairman, Nuclear Regulatory Commission (II) | 42 U.S.C. 5841(a)(1): the President designates one member as Chairman |
| NRC `Commissioner (×4)` | Members, Nuclear Regulatory Commission (III), class title | 42 U.S.C. 5841(a)(1): "composed of five members" |
| `Administrator, SBA` | Administrator of the Small Business Administration (III) | 15 U.S.C. 633(b)(1): management "vested in an Administrator" |
| `Director, NSF` | Director of the National Science Foundation (II) | 42 U.S.C. 1864(a): the section itself sets basic pay at level II |
| `Deputy Director, NSF` | Deputy Director, National Science Foundation (III) | 42 U.S.C. 1864a: the section itself sets basic pay at level III |
| `Director (Drug Czar)` | Director of National Drug Control Policy (I) | 21 U.S.C. 1703(a)(1)(A): "at the head of the Office a Director" |
| `Commissioner, BLS` | The 2 Commissioner of Labor Statistics, Department of Labor (IV) | 29 U.S.C. 3: the Bureau "under the charge of a Commissioner of Labor Statistics" |
| `Director, Census Bureau` | Director, Bureau of the Census, Department of Commerce (IV) | 13 U.S.C. 21(a)(1): "headed by a Director of the Census" |
| `Chair, CEA` | Chairman, Council of Economic Advisers (II) | 15 U.S.C. 1023(a)(2): three members, one the chairman |
| `Member, CEA` (two nodes) | Members, Council of Economic Advisers (IV), one row per node, no class mark | 15 U.S.C. 1023(a)(2): "2 shall be appointed by the President" |
| `Chair, CPSC` | Chairman, Consumer Product Safety Commission (III) | 15 U.S.C. 2053(a): the Chairman appointed "from among the members" |

**Three things the fetches settled that the list had assumed.**

- **The NIST identification is in a section the list did not name.** The
  Code's Schedule title carries it in its own words, but a reviewed row needs
  the second statute, and neither 15 U.S.C. 272 (establishment) nor 274 (the
  Director's powers) prints "Under Secretary" anywhere, notes included: the
  America COMPETES Reauthorization Act of 2010 struck the appointment
  sentence out of §274, which the Code's Amendments note records, and put the
  office at **15 U.S.C. 273a**, found from the chapter's own table of
  contents. §273a also compensates the Under Secretary at level III itself.
  The three dead-end fetches (§§272, 274 and 278 — the last is the Visiting
  Committee on Advanced Technology) were deleted rather than committed; the
  section that says it is committed.
- **The ONDCP Director is no longer where the batch put him.** 21 U.S.C.
  1702(b) "related to Director of National Drug Control Policy and Deputy
  Directors" and was struck by Pub. L. 115–271 in 2018; the Director is now
  at 21 U.S.C. 1703(a)(1)(A). Both sections are committed: §1703 is the basis,
  and §1702 is the one that establishes the Office the Director heads.
- **The BLS title is published with the Code's own typo.** §5315 prints "The
  <sup>2</sup> Commissioner of Labor Statistics, Department of Labor" and
  footnotes it: "The word 'The' probably should not appear." The index keeps
  the title as printed, so the record's `statutoryTitle` reads "The 2
  Commissioner of Labor Statistics, Department of Labor", and the row's basis
  says why. Correcting it would be editing a quotation.

**Measured:** reviewed rows 24 → 37; positions priced from the Schedule
123 → 136 (I 19, II 29, III 22, IV 61, V 5); pay claims **541 → 554**;
unpriced **4,050 → 4,037** (3,257 unreached, 759 stating a multiplicity, 21
listed without a rate); class-title benches 5 → 6; multi-post nodes priced
33 → 34. Nothing measured moved, nothing outside `positionSchedulePay` changed,
and no matcher, gate rule or sweep rule changed — the gate mirror gained
thirteen 9-tuples and the one test that counts class benches reads six.

**Still refused from the same list:** CPSC's `Commissioner (×4)`, whose
Schedule title is the counted plural "Members, Consumer Product Safety
Commission (4)" — the counted-class shape (§19.8, with the Deputy USTRs) the
matcher refuses until the owner decides it; and the three NRC office
directors, printed by the Code and curated here as "Director — Office of
Nuclear Reactor Regulation", which no route reaches without a rename.

**The seventh batch, triaged.** It was mostly systems and ranges, and the
refusals are the ones §19.7–19.9 already made, with the exceptions worth a
row or a module noted first.

*Candidates the committed Code confirms, for the next round (reviewed-row
shape, one basis fetch each):*

- **`Administrator, FHWA`** — the Code prints "Administrator, Federal
  Highway Administration" at Level II, as the batch said; the basis is
  whichever section of title 49 puts an Administrator at the head of the
  Administration (the batch names §104; not fetched). The batch's Deputy is printed too ("Deputy
  Federal Highway Administrator", IV) and reaches nothing: this graph has no
  such node.
- **USPTO's `Director / Under Secretary for IP`** — "Under Secretary of
  Commerce for Intellectual Property and Director of the United States Patent
  and Trademark Office" (III), the batch's grade; the basis would be the
  section of title 35 that creates the office (the batch names §3; not
  fetched). Its bare `Deputy Director` node answers to the Deputy Under
  Secretary title (IV), though a row on a bare title is the shape the post floor
  exists to distrust and should be reviewed as such.
- **`Commissioner, BOR`** — "Commissioner of Reclamation, Department of the
  Interior" at **Level V**, as the batch said; the basis section has not been
  identified from here and must be fetched, not assumed.
- **`Register of Copyrights & Director`** — the batch cited 17 U.S.C. 701(f)
  as setting the pay by reference to level III. The Code ALSO prints
  "Register of Copyrights" on the Schedule itself at §5314 (III), so this is a
  reviewed row and not a tier-reference record, with §701 as the basis —
  §701(a) styles the Register "as director of the Copyright Office", which is
  the graph's "& Director".

*Candidates that are the tier-reference shape (§19.9), if the sections say
what the batch reports; none fetched this round:* the **IES Director** (the
batch: Level II by 20 U.S.C. 9517) and its commissioners; the **CBO
Director** (2 U.S.C. 601); the **GPO Director** (II) and Deputy (III) under
44 U.S.C. — none of these titles is printed on the Schedule, so if their
statutes set pay by reference to a level the record belongs in
`positionTierReferencePay` with `documentsStatingTheFigure: 0`. The **FJC
Director**, if 28 U.S.C. 628 sets the salary at a judicial tier's, is the
`derived_pay.py` shape instead. Each is one fetch and a reviewed row in the
relevant module's table, not a research question.

*Already done, which the batch reported as open:* the **CAAF `Judge (×4)`**
bench at the circuit-judge rate — priced since 2026-09-23 from 10 U.S.C.
942(d) (`derived_pay.BENCH_NODES`), $264,900 beside its Chief Judge.

*Refused, with the reason:*

- **DoD agencies "via the PLUM Book"** (DCSA, DISA, DTRA, the rest): the
  current export lists their principals on the ES pay plan with no figure in
  the rate column, and a listing that prints no rate is what `listed_no_rate`
  already counts; the archive's ES rows are the same. A pay plan is a system,
  not a figure.
- **Circuit-court staff at CL/JSP grades, and the AUSA/AD charts again**: a
  grade names a system and a range; no document states the post's figure.
- **Circuit-judge benches "at $264,900"**: the thirteen `Circuit Judge (×N
  active + senior judges)` nodes bundle senior judges, whose salary 28 U.S.C.
  371(b)(2) sets apart from the tier rate (§19.8); a circuit's own *active*
  bench is already priced from the compensation table where the graph
  curates one.
- **The Federal Public Defenders (×82)**: the batch reports 18 U.S.C.
  3006A(g)(2)(A) as fixing the compensation at a rate not to exceed the
  district's United States attorney's — if so, a ceiling and not a rate, the
  37 U.S.C. 203(a)(2) shape, and the section was not fetched to check it.
- **ICE, MDA, NETL, NGA and NHTSA "ranges from USAJOBS"**: a vacancy posting
  is not a pay document — it states one job's advertised band on one day,
  names no post this graph carries, and is not a publisher this project
  reads. Refused as the prompt pack itself says salary aggregators are.
- **The DOE laboratories and JPL as "not federally paid"**: §19.9's
  refusal stands; a contractor-operated laboratory's staff are not on any
  federal pay document, and the DOE page was not fetched.
- **FNS (now the Food and Nutrition Administration) and PFPA**: SES posts on
  no schedule the Code prints; nothing to cite.

**Next:** the four reviewed-row candidates above (FHWA, USPTO, BOR, the
Register of Copyrights) are four fetches; the four tier-reference candidates
(IES, CBO, GPO, plus the FJC as derived) are four more, each a row in an
existing table. The two owner decisions still open are unchanged: the
counted-class shape (CPSC's bench, the Deputy USTRs) and Members paid under
Schedule 6 (committee chairs, the whips).

### 19.11 The eight candidates of §19.10, in three tables; the eighth batch triaged (2026-09-28)

**Added, on the owner's instruction: "add the eight candidates."** Fourteen
basis sections were fetched from uscode.house.gov and eleven are committed;
the three that turned out to be dead ends (28 U.S.C. 625, 627 and 628 — the
FJC's staff, retirement and appropriations sections, none of them pay) were
deleted rather than committed, the rule §19.10 applied to the NIST fetches.
The eight fell into three tables, and two of them were not where the
candidate list had put them.

**Four reviewed Executive Schedule rows** (`statutory_schedule.REVIEWED_TITLE_ROWS`, §19.1's shape):

| Node | Statutory title (level) | Basis |
|---|---|---|
| `Administrator, FHWA` | Administrator, Federal Highway Administration (II) | 49 U.S.C. 104(b)(1): "The head of the Administration is the Administrator" |
| USPTO `Director / Under Secretary for IP` | Under Secretary of Commerce for Intellectual Property and Director of the United States Patent and Trademark Office (III) | 35 U.S.C. 3(a)(1): the Office's powers "vested in" that one joint title |
| `Commissioner, BOR` | Commissioner of Reclamation, Department of the Interior (V) | 43 U.S.C. 373a: reclamation "administered by a Commissioner of Reclamation" |
| `Register of Copyrights & Director` | Register of Copyrights (III) | 17 U.S.C. 701(a): "the Register of Copyrights as director of the Copyright Office" |

The Register's is worth a line: the batch had cited 17 U.S.C. 701(f) as
setting the pay by reference to Level III, which would have made it a
tier-reference record. The Code prints "Register of Copyrights" on the
Schedule itself at §5314, so it is a Schedule row with §701 as the basis, and
§701(a)'s "as director of the Copyright Office" is what the graph's
"& Director" stands for. The USPTO's bare `Deputy Director` node is left
alone: the Code prints the Deputy's joint title (IV), but a row on a bare
title is the shape the post floor exists to distrust, and the owner named
the Director, not the Deputy.

**Six tier-reference rows** (`tier_reference_pay.TIER_REFERENCE_PROVISIONS`,
§19.9's shape; the table stopped being "the GAO's two officers"):

| Node | Statute | Level |
|---|---|---|
| `Director, GPO (Public Printer)` | 44 U.S.C. 303, first sentence | II |
| `Deputy Director / COO` (GPO) | 44 U.S.C. 303, second sentence | III |
| `Director, IES` | 20 U.S.C. 9514(c) | II |
| `Commissioner — NCES` | 20 U.S.C. 9517(b)(2), which names the Commissioner for Education Statistics | IV |
| `Commissioner — NCER` | 20 U.S.C. 9517(a)(2)(A), "each Commissioner" of the National Education Centers, + 9511(c)(3) | IV |
| `Commissioner — NCEE` | the same two sections | IV |

The batch had graded the IES Director "Level II by 20 U.S.C. 9517"; the
level was right and the section was the Commissioners'. §9514(c) is the
Director's. And §9517(a) prices "each Commissioner" of "the National
Education Centers" without naming one, so the NCER and NCEE rows carry a
third document, 20 U.S.C. 9511(c)(3), the sentence that lists the four
Centers — the way an Inspector General's record carries 401(1)'s list. The
gate mirrors that sentence and the two rows that need it, and refuses a
block that lacks it, misquotes it, or carries it on the NCES row, which
§9517(b) prices by name. The GPO's `Deputy Director / COO` is the graph's own
styling of the one Deputy Director §302 creates; the row is by node id and
the name check is by canonical key.

**One office priced in the derived field, and one through a chain.** The
condition the candidate list set — "if 28 U.S.C. 628 sets the salary at a
judicial tier's" — was not met. §628 is appropriations. **28 U.S.C. 626** is
the section: "The compensation of the Director of the Federal Judicial
Center shall be the same as that of the Director of the Administrative Office
of the United States Courts", and **28 U.S.C. 603** sets that Director's
salary "the same as the salary of a district judge". So:

- `Director, AOUSC` is priced from §603 alone — one statute, the compensation
  table, two documents, 80%, exactly the four courts' shape, with the record's
  `subject` ("the Director of the Administrative Office …") printed where a
  court row prints "every judge of <court>".
- `Director, FJC` is priced through a **chain**: §626 → §603 → the table,
  three documents, 90%, none stating the figure. The provision carries `via`,
  the middle statute; the gate's mirror row grows a fourth element for it and
  refuses a block that drops the middle document, misquotes it, or claims a
  chain its provision does not make.
- Both Deputies are refused and say why: §603 pays the AO's Deputy "92
  percent of the salary of the Director", and §626 pays the FJC's Deputy what
  the AO's Deputy is paid — arithmetic on a figure that is itself a join, which
  this field does not publish.

**Read and refused: the CBO.** 2 U.S.C. 601(a)(5)(A) pays the Director "at an
annual rate of pay that is equal to the maximum rate of pay in effect under
section 4575(f) of this title" — the Senate's own pay ceiling, a chain through
a section this project has not read — and (B) the Deputy "$1,000 less than
the annual rate of pay received by the Director". The section is committed as
`cbo_2_usc_601.html` because "looked and it chains elsewhere" is a fact worth
keeping; nothing is published from it.

**Measured:** reviewed Schedule rows 37 → 41 and positions priced from the
Schedule 136 → 140 (I 19, II 30, III 24, IV 61, V 6); tier-reference records
28 → 34; derived records 8 → 10; pay claims **554 → 566**; unpriced
**4,037 → 4,025** (3,246 unreached, 759 stating a multiplicity, 20 listed
without a rate). Nothing measured moved. The only frontend change is the
derived-pay sentence in the panel and the atlas, which now prints the
record's subject and, on a chain, the middle statute; the cache stamp is
`20260928b`.

**The eighth batch, triaged.** It was a sweep of some 250 nodes and its
findings are mostly the refusals the earlier batches already established,
so the exceptions come first.

*Checked against the committed Schedule sections — none of these is priced
yet, and the check was done after a first draft of this section had asserted
the opposite for several of them:*

- **`Director, NSF` at Level II** — priced on 2026-09-28 (§19.10). The one
  the batch reported that the graph already carries.
- **`Librarian of Congress` at Level II** — the batch cites OPM's table, but
  §§5312–5316 print no "Librarian of Congress" at any level; if the
  Librarian's pay is set by a statute of the Library's own, that statute has
  not been read and the post is a tier-reference candidate, not a Schedule
  row. Refused on the batch's word.
- **`Director, OFR` at Level III** — the batch cites 12 U.S.C. 5342 as
  setting the pay by reference; the Code in fact prints "Director of the
  Office of Financial Research" on the Schedule itself at §5314, so this is
  a reviewed Schedule row with §5342 as its basis (one fetch), not a
  tier-reference record. The OFR's `Chief Data Officer`, `Chief of Staff`,
  `Deputy Director`, `Director — Research & Analysis` and `General Counsel`
  are, per the batch, administratively determined under 5342(d)(2) — a
  system with no printed figure — and stay refused.
- **Reviewed-row candidates the Code confirms at the batch's level**, each
  one basis fetch away and none added on the batch's word: `Administrator,
  NASA` ("Administrator of the National Aeronautics and Space Administration",
  II); `Administrator, FTA` ("Federal Transit Administrator", II);
  `Administrator, FRA` (III); `Administrator, MARAD` (III); `Assistant
  Secretary of Labor for Mine Safety` ("Assistant Secretary of Labor for Mine
  Safety and Health", IV); `Chair, FMC` (III) and its `Commissioner (×4)`
  ("Members, Federal Maritime Commission", IV, the class-title bench shape);
  and the stamped `Director / Administrator / Chair, <agency>` heads of the
  MSPB (III), the NCUA Board (III), the Peace Corps (III), the Selective
  Service (IV), the FLRA (IV), the NEH (III), the NTSB (III), the Office of
  Special Counsel (III), the PBGC (III) and the Postal Regulatory Commission
  (III). The last group is the five-title template §19.9 documents: a row
  would identify which of Director, Administrator or Chair the agency's own
  statute creates, agency by agency, the FCC/FTC shape.
- **Not on the Schedule under the batch's title**: the OSHA Assistant
  Secretary (the Code prints the Review Commission's chair and members, not
  the Assistant Secretary by name) and the CSB's chair; and the **Assistant
  Attorneys General**, printed as "Assistant Attorneys General (11)" at Level
  IV — the counted-class shape the matcher refuses until the owner decides
  it. *Corrected the same day (§19.12):* this bullet first listed the
  Export-Import Bank's head and the FCA's here too, on a search of the
  index for "export-import" and nothing for "farm credit"; the Code prints
  "President of the Export-Import Bank of Washington" (III) and "Governor of
  the Farm Credit Administration" (III), both at the batch's level.

*Refused, with the reason:*

- **`$158,500` "EX-IV payable" for every State Department Assistant Secretary,
  the DOJ Assistant Attorneys General and the CSB Chair**, from OPM's pay-freeze
  memo: the memo states a frozen payable rate for covered political appointees,
  not the Schedule's rate for the office, and this project publishes the
  official rate OPM's Salary Table 2026-EX prints ($197,200 for Level IV) with
  the table's own freeze footnote beside it (see `pay_tables.py`). The same
  figure has been refused in every batch since the fourth.
- **`$174,000` for the Joint Economic Committee's Chair and Vice Chair**, from
  the House Clerk's salary page: a Member's salary, which this graph publishes
  for no Member's seat (§19.6, the held decision on chairs), and the Clerk's
  page was not fetched.
- **The TVA Board chair's "$50,000 per year"** from 16 U.S.C. 831a: the batch
  itself notes the statute requires adjustments, and a node named `Director /
  Administrator / Chair, Tennessee Valley Authority` is the stamped template
  and not the Board's chair; not fetched.
- **The PCLOB chair** — "board_or_commission_statutory" with no figure; 42
  U.S.C. 2000ee was not fetched and prints, per the batch, no rate.
- **Tax Court and Court of Federal Claims `Judge (×18)` / `(×15)` at
  $249,900** — priced since 2026-09-23 from their own parity provisions
  (`derived_pay.BENCH_NODES`); the CFC's `Senior Judge (×multiple)` stays
  refused for the reason the module records (28 U.S.C. 178, unread). The Tax
  Court's `Special Trial Judge (×multiple)`: the batch cites the court's
  budget justification, which states a system and no figure.
- **ATF agents and inspectors, the Capitol Police officers, GAO's analysts,
  the Foreign Service officers, the USCIS, FSA, NRCS, FWS, BIA and HRSA
  field titles, the presidential libraries' staff, the NSA's stamped five, the
  DOE Office of Science associate directors, OFAC, TTB (whose Administrator
  is SES with no printed figure), AmeriCorps, ABMC, ARC, NCPC, DFC and the
  NSC** — each is a grade, a system, a range, a careers page or nothing; no
  document states the post's figure. `unknown | — | none`, which the batch
  itself says "does not mean the position is unpaid", is the honest state and
  the one the graph already shows.

**Next:** the reviewed-row candidates above are seventeen posts for about
seventeen basis fetches — NASA, FTA, FRA, MARAD, MSHA, the OFR, the FMC's
chair and bench, and the ten stamped heads — and the counted-class
(Assistant Attorneys General, CPSC, PRC, NCUA members) and
Members-under-Schedule-6 decisions are still the owner's. (Done the same
day: §19.12.)

### 19.12 Every batch's leads, accounted for; the eighth batch's rows landed (2026-09-28)

**The owner's ask: "make sure that you used everything from the perplexity
responses I gave to you so far."** So this section is a ledger rather than a
triage: every lead any batch carried that the committed Code could confirm,
and its disposition, batch by batch. Where a lead was still open it is closed
here; where it stays open it says what decision or document it waits on.

**Batch 4 (§19.7).** Six reviewed rows (FCC, FTC, IRS, FAA, DHS ×2) — landed
that day. The FCC and FTC benches — landed in §19.8. DFAS — walled,
recorded, still walled. Nothing outstanding.

**Batch 5 (§19.8).** Nine reviewed rows and five class benches — landed. The
GAO's officers and the Inspectors General — the tier-reference module,
§19.9. Refused and unchanged: NOAA and NNSA (not on the Schedule), the
Archivist (ambiguous in the Code), the CRS Director (a range's ceiling),
SCOTUS officers, the FSA COO, NASA centre directors, Deputy Marshals (systems
without a figure), the Senate whips and committee chairs (the Members
decision). **Still open, and now buildable:** the bankruptcy and magistrate
judges at "92 percent of the salary of a judge of the district court" (28
U.S.C. 153(a), 634(a)) — arithmetic on a printed tier rate, which is exactly
the shape `tier_reference_pay.py` publishes for an Inspector General's Level
III plus 3 percent; the difference is the table (uscourts.gov, not OPM) and
the field, so it is a variant of `derived_pay.py` carrying `arithmetic`, on
two multi-post benches, and a module decision the owner has not made. The
Deputy USTRs — the counted-class decision.

**Batch 6 (§19.9).** Thirteen reviewed rows — landed in §19.10. Refused and
unchanged: USPS officers (person-level 8-K figures), the USPS Board's
statutory "$30,000 a year plus $300 a day" (39 U.S.C. 202 — a dollar figure
printed in a statute, which no module here reads; a `positionStatutoryPay`
source of a new kind and a nine-member board, still a decision), the NEC
Director from the White House roster (a scope decision), AUSAs, JCT, the
Smithsonian, JPL and the DOE laboratories, the combatant commanders (DFAS).

**Batch 7 (§19.10).** The eight candidates — landed in §19.11 (four Schedule
rows, six tier-reference rows, the AO and FJC Directors), the CBO read and
refused. The one lead left there — **the USPTO's bare `Deputy Director`,
"Deputy Under Secretary of Commerce for Intellectual Property and Deputy
Director of the United States Patent and Trademark Office" (IV) by 35 U.S.C.
3(b)(1)** — is landed here: a reviewed row is keyed to the node by id, so
the floor that refuses a bare title as page evidence does not apply to it,
and the section was already committed.

**Batch 8 (§19.11).** The seventeen candidates the Code confirmed, plus the
two §19.11 wrongly said it did not, are landed here as **twenty reviewed
Schedule rows** (the USPTO Deputy among them) and **two tier-reference
rows**. Twenty-three sections were fetched; three were wrong guesses and were
deleted rather than committed (46 U.S.C. 301 is the conforming-changes
section, not the Commission's; 5 U.S.C. 1201 composes the MSPB but its
Chairman is at §1203; 50 U.S.C. 3803 is liability for service, the Director
is at §3809), so twenty are committed.

*Reviewed Schedule rows* (level; basis): NASA's Administrator (II; 51 U.S.C.
20111), the FTA's ("Federal Transit Administrator", II; 49 U.S.C. 107), the
FRA's (III; 49 U.S.C. 103), MARAD's (III; 49 U.S.C. 109), the Assistant
Secretary of Labor for Mine Safety and Health (IV; 29 U.S.C. 557a), the OFR
Director (III; 12 U.S.C. 5342, which itself compensates the Director at
Level III), the FMC's Chair (III) and its `Commissioner (×4)` bench from
"Members, Federal Maritime Commission" (IV, the seventh class-title bench;
46 U.S.C. 46101), and ten of the stamped `Director / Administrator / Chair,
<agency>` heads, each identified with the office the agency's own statute
puts at its head: the MSPB's Chairman (III; 5 U.S.C. 1203), the NCUA Board's
Chairman (III; 12 U.S.C. 1752a), the Director of the Peace Corps (III; 22
U.S.C. 2503), the Director of Selective Service (IV; 50 U.S.C. 3809), the
FLRA's Chairman (IV; 5 U.S.C. 7104), the NEH's chairperson (III; 20 U.S.C.
956), the NTSB's Chairman (III; 49 U.S.C. 1111), the Special Counsel (III; 5
U.S.C. 1211), the PBGC's Director (III; 29 U.S.C. 1302), the PRC's Chairman
(III; 39 U.S.C. 502), and the Export-Import Bank's President (III; 12 U.S.C.
635a). The last is the one row whose identification leans on a fact outside
its operative text: the Schedule still prints "President of the
Export-Import Bank **of Washington**", the Bank's name before Pub. L. 90–267
renamed it in 1968, which the Code records in the notes to 12 U.S.C. 635 and
nowhere in §635a's operative text. There is one Export-Import Bank and one
President of it; the row's basis says what it rests on. On the stamped
template: `Director / Administrator / Chair, <agency>` is one node standing
for whichever of those three the agency actually has, and each row names
which one the statute creates — the template is not being priced, the office
under it is.

*Tier-reference rows:* the FCA Board's Chairman — the Schedule prints
"Governor of the Farm Credit Administration" (III), an office 12 U.S.C. 2242
no longer has (the Administration is managed by a three-member Board), so no
Schedule row is honest; but §2242(d) itself sets the Chairman's compensation
"at the rate prescribed for level III of the Executive Schedule", which is
the tier-reference shape, and the row prices the head the template stands
for from that sentence. And the **Librarian of Congress** at Level II from 2
U.S.C. 136a–2(1) — §19.11 had refused it because the Schedule prints no
Librarian; the batch's Level II was right and the section is the Library's
own. The Deputy Librarian is refused: §136a–2(2) pays "the greater of" Level
III and the SL/ST maximum, a maximum of two documents rather than a rate.

**A reader defect the Librarian's section exposed.** 2 U.S.C. 136a–2 is
numbered with an en-dash and a second number, and all three operative-text
readers — `derived_pay.operative_text`, `statutory_schedule`'s and the gate's
own — matched a section heading as `§<digits><letter>.`, so none found the
heading and the module read the page chrome as the law. The pattern now
admits the dashed suffix in all three, and `tests/test_tier_reference_pay.py`
asserts each reader starts the Librarian's operative text at "§136a–2."
and finds the pay sentence in it.

**Measured:** reviewed Schedule rows 41 → 61 and positions priced from the
Schedule 140 → 160 (I 19, II 32, III 37, IV 66, V 6); tier-reference records
34 → 36; class-title benches 6 → 7; multi-post nodes priced 34 → 35; pay
claims **566 → 588**; unpriced **4,025 → 4,003** (3,225 unreached, 758
stating a multiplicity, 20 listed without a rate). Nothing measured moved
and no frontend file changed.

**Still open after this section, all of them decisions and not fetches:**
the counted-class shape (Assistant Attorneys General (11), Assistant
Secretaries of State, the CPSC's, PRC's and NCUA's members, the Deputy
USTRs); Members of Congress paid under Schedule 6 (committee chairs, the
Senate whips, the JEC's chair and vice chair); the bankruptcy and magistrate
judges' 92-percent arithmetic on the district-judge rate (decided 2026-09-30,
§19.13: the bankruptcy benches priced, the magistrate benches refused on the
statute's "up to"); the USPS Board's
statutory stipend; and the Deputy Librarian's "greater of". Every other lead
in eight batches is either published or refused with its reason on the
record.

### 19.13 The bankruptcy judges at 92 percent; the magistrate judges refused (2026-09-30)

The owner's instruction was "price the bankruptcy and magistrate judges at 92
percent". Both sections were fetched (`tests/fixtures/uscode/
bankruptcy_judges_28_usc_153.html`, `magistrate_judges_28_usc_634.html`) and
read in their operative text before anything was built, and they do not say
the same thing.

**28 U.S.C. 153(a) — priced.** "Each bankruptcy judge shall serve on a
full-time basis and shall receive as full compensation for his services, a
salary at an annual rate that is equal to 92 percent of the salary of a judge
of the district court of the United States as determined pursuant to section
135." A rate, stated for every holder. The Judicial Compensation table prints
$249,900 for district judges; 92 percent of it is **$229,908**, which no
document prints. Two nodes carry it, both benches under the per-field
multi-post rule with a `holders` block: `Bankruptcy Judge (×12)` under the
Southern District of New York (`jud-district-sdny-bankruptcy-judge-12`) and
`Bankruptcy Judge (×varies)` under the standard district structure
(`jud-district-structure-bankruptcy-judge-varies`), the second because the
statute says "each bankruptcy judge" wherever the judge sits. The field is
`positionDerivedPay` with `percentOf: 92` and an `arithmetic` block
(`percent_of`), the shape the tier-reference module publishes for an
Inspector General's "plus 3 percent"; `financial_evidence` gained the second
operation and the second grantee for its computed-from-a-marked-figure rule,
and the gate mirrors the two rows by node id (`DERIVED_PAY_PERCENT_OF`). Two
documents, 80 percent on the project's scale, `documentsStatingTheFigure: 0`,
`partial`, `proxy`.

**28 U.S.C. 634(a) — refused.** "Officers appointed under this chapter shall
receive, as full compensation for their services, salaries to be fixed by the
conference pursuant to section 633, at rates for full-time United States
magistrate judges up to an annual rate equal to 92 percent of the salary of a
judge of the district court of the United States, as determined pursuant to
section 135, and at rates for part-time magistrate judges of not less than an
annual salary of $100, nor more than one-half the maximum salary payable to a
full-time magistrate judge." That is a **ceiling**, and the Judicial
Conference fixes the figure beneath it: 92 percent is the most a full-time
magistrate judge may be paid, not what one is paid, and a part-time
magistrate judge may be paid anything from $100 to half the full-time
maximum. No document this project has read states what the Conference fixed,
so `Magistrate Judge (×13)` (S.D.N.Y.) and `Magistrate Judge (×varies)` stay
unpriced with the reason on the record (`derived_pay.NOT_PRICED`), and
`tests/test_derived_pay.py` asserts against the committed bytes that "up to
an annual rate" is in §634's operative text and not in §153's. The research
batches and the instruction both put the two benches together at 92 percent;
the statute puts only one of them there. Should the Conference's own schedule
be found on a `.gov` host — the Administrative Office publishes one — a
magistrate judge's figure would be a printed rate and belong in
`positionStatutoryPay`, not here.

**Also refused, and reworded rather than reopened:** the AO's Deputy Director
is 92 percent of the Director's under the same 28 U.S.C. 603 that pays the
Director as a district judge. The reason used to read "arithmetic on a figure
that is itself a join, which this field does not publish", and this field now
does publish a percentage; the difference is that the bankruptcy percentage is
taken of the table's own printed figure and the Deputy's would be taken of a
join. The record says so now.

**Counted on the rebuilt graph:** derived records 10 → 12, pay claims
588 → 590, unpriced 4,003 → 4,001 (3,225 unreached, 756 stating a
multiplicity, 20 listed without a rate), multi-post nodes priced 35 → 37,
prompt-pack shards 39 → 38. The unpriced report's "N such nodes carry one"
sentence is read off the graph since this section; it had said 28 since
2026-09-23 while the graph carried 37. Nothing measured moved.

**Still open after this section:** the counted-class shape (decided the same
day, §19.14); Members of Congress paid under Schedule 6; the USPS Board's
statutory stipend; the Deputy Librarian's "greater of".

### 19.14 The counted-class shape decided; the ninth batch triaged (2026-09-30)

The owner's instruction was "decide the counted-class shape and price them",
with a ninth Perplexity batch pasted after it. The Code prints 44 titles of
the form "<class> (N)" across §§5312–5316 — "Assistant Attorneys General
(11)", "Assistant Secretaries of Labor (10)", "Members, Consumer Product
Safety Commission (4)" — and every route refused them. The decision, built
as `statutory_schedule.match_counted_classes` and recorded in `CLAUDE.md`:
a member is priced only when the section prints the class title with its
count, the node is a single post named as the class's singular office and
nothing else, it sits inside the class's organisation, no listing on it
reports another pay plan or level, the graph names no more members than the
Code counts, and the node id is in the reviewed table `COUNTED_CLASSES`.
Where a statute composes the class it is the third document; where it names
the office itself the sentence rides on the record.

**Eight classes, 40 members priced, 34 of them for the first time** (six
already carried OPM's archived EX-IV listing and now carry both blocks,
agreeing):

| Class | Composing statute | Members priced | Declined |
|---|---|---|---|
| Assistant Attorneys General (11), IV | 28 U.S.C. 506 | 7 (Antitrust, Civil, Civil Rights, Criminal, ENRD, NSD, Tax) | — |
| Assistant Administrators, EPA (8), IV | none read (Reorganization Plan No. 3 of 1970 is not a section of the Code); the Schedule also prints two of them under older names at the same level | 7 (OAR, OW, OLEM, OCSPP, ORD, OECA, OITA) | — |
| Assistant Secretaries of State (24), IV | 22 U.S.C. 2651a(c), which itself sets Level IV and names eight bureau heads | 13 | FSI, Office of the Chief of Protocol, U.S. Mission to the UN: the State stamp names an "Assistant Secretary" over each, and their heads are a Director, an Ambassador and a Permanent Representative |
| Assistant Secretaries of Labor (10), IV | 29 U.S.C. 553 (nine offices; names OSHA's) | 3 (OSHA, ETA, EBSA); MSHA's is a reviewed row already | — |
| Assistant Secretaries of Education (10), IV | 20 U.S.C. 3412(b), naming both by title | 2 (OESE, OCR) | — |
| Assistant Secretaries of HUD (8), IV | 42 U.S.C. 3533(a): SEVEN, where the Schedule counts eight; the Federal Housing Commissioner "shall be one of the Assistant Secretaries" | 4 (FHA Commissioner, PIH, CPD, FHEO) | — |
| Assistant Secretaries of Energy (8), IV | 42 U.S.C. 7133(a), which itself sets Level IV | 2 (EERE, EM) | — |
| Assistant Secretaries of Commerce (11), IV | none read: 15 U.S.C. 1506 adds one office to those "now provided for by law" and was not committed | 2 (ITA's Global Markets; Enforcement & Compliance) | — |

Also declined, structurally or by review: SAMHSA's "Assistant Secretary for
Mental Health & Substance Use (dual-hat)" — the parenthetical rule refuses
it, and whether that office is one of HHS's six is not something read here;
NASA's five mission-directorate Associate Administrators against
"Associate Administrators, NASA (7)" (V) and the SBA's four against
"Associate Administrators of the SBA (4)" (V) — the current export lists
the NASA ones it lists on the ES plan, so the class's membership is
contested by the one document that could settle it, and the SBA's are
declined on the same doubt; "Under Secretaries of State / Energy / the
Treasury", "Deputy United States Trade Representatives (3)", "Assistant
Directors of OMB (3)", "Additional officers, OMB (6)" and the rest of the
44 reach no node in this graph or name no office ("Additional officers").
The State class's title is printed inside a longer paragraph ("… (24) and 4
other State Department officials to be appointed …") that the title parser
sets aside, so the counted route checks the printed words directly; Labor's
paragraph carries a proviso naming the VETS Assistant Secretary and is read
the same way. 22 U.S.C. 2652, the batch's composition section for State,
was fetched, is REPEALED, and was deleted rather than committed.

**The counted bench.** A "Members, X (N)" class-title row now requires the
bench's own count to equal N (`reviewed_row_bench_count_disagrees_with_the_
code`, mirrored in the gate), and on that rule the CPSC's `Commissioner (×4)`
is priced from "Members, Consumer Product Safety Commission (4)" with 15
U.S.C. 2053 (already committed) composing the Commission of five.

**The ninth batch, triaged.** It priced 24 ids and named systems for ~200
more; every lead is accounted for here.

- **Landed as reviewed rows (14, the Fed's shape).** EEOC Chairman (III) and
  Vice Chairman as one of "Members, EEOC (4)" (IV), both on 42 U.S.C.
  2000e-4(a)'s "The President shall designate one member to serve as
  Chairman of the Commission, and one member to serve as Vice Chairman";
  NMB chairman (III, 45 U.S.C. 154 Second); NEA Chairperson (III, 20 U.S.C.
  954(b), the Schedule spelling it Chairman); President of Ginnie Mae (IV,
  12 U.S.C. 1723); Wage and Hour Administrator (IV, 29 U.S.C. 204); OMB
  Director (I) and Deputy Director (II), 31 U.S.C. 502; the OMB's three
  templated "Administrator / Chief" heads — Federal Procurement Policy (III,
  41 U.S.C. 1102; §1101 names no Administrator and was deleted), the
  Controller of Federal Financial Management (III, 31 U.S.C. 504), the
  Administrator of Electronic Government (III, 44 U.S.C. 3602); PHMSA
  Administrator (III, 49 U.S.C. 108, first fetch reset by the host, second
  served); the SEC's `Commissioner (×4)` bench from "Members, SEC" (IV, 15
  U.S.C. 78d(a)); and the CPSC bench above.
- **Landed through the counted class:** EBSA's, ENRD's, Tax's, OESE's and
  the FHA Commissioner's rows.
- **Declined.** The NCUA's and PRC's stamped "Deputy Director / Vice Chair":
  12 U.S.C. 1752a designates a Chairman and no Vice Chairman (the Board's
  three members are read and committed; nothing here says which member the
  stamp stands for), and 39 U.S.C. 502 was not fetched on the same doubt.
  (The PRC half of this was wrong: §502(e), committed since for the
  Commission's Chairman row, has the Commissioners designate a Vice Chairman
  by majority vote. Corrected and priced on 2026-10-05, §19.20.)
  The SEC's `Chair, SEC`: 15 U.S.C. 78d composes the Commission and does
  not designate its Chairman (Reorganization Plan No. 10 of 1950 does),
  so no basis sentence exists in a section of the Code. The EPA's
  `Administrator, EPA` at "Administrator of the Environmental Protection
  Agency" (II): the Agency has no organic section of the Code to cite. The
  USAGM CEO: 22 U.S.C. 6203 is not on the Schedule and was not read. The
  two "$158,500 / $168,400 frozen payable" figures from OPM's pay-freeze
  memo: a memo about certain political appointees' payable rates is
  person-level, and the table's own freeze footnote already rides on every
  Schedule record.
- **Members of Congress at $174,000 (every committee chair and ranking
  member, ~150 nodes, from a CRS report, senate.gov's salary page and the
  Clerk's Salary.pdf): still the open Members decision** recorded in §19.12.
  The sources are real; what is undecided is whether a committee-chair node
  is a seat.
- **Leads, not rows.** The EPA's ten regional administrators and deputies
  as SES in the 2024 Plum Book (govinfo PDFs): the archive `positions.py`
  reads is the same document, and those rows did not reach the nodes by
  name — an alias/organisation problem for the archive matcher, not a pay
  row. FISC judges and the presiding judge at the district-judge rate: 50
  U.S.C. 1803(a) designates district judges, which is `derived_pay.py`'s
  shape with a composition sentence; not read here. BVA Veterans Law
  Judges and Vice Chairman under 38 U.S.C. 7101A: not read. GAO's analysts
  and directors on GAO's own pay bands, NSF programme directors at the AD-4
  band on nsf.gov's careers page, the CAVC clerk's 2023 vacancy range:
  each names a system and prints no figure a record could quote, or a
  recruitment range that is not the post's rate. Foreign Service officers
  and Capitol Police ranks: systems named, documents not.

Counted on the rebuilt graph: reviewed rows 61 → 75, Schedule-priced
160 → 214 (40 as counted-class members, 9 class-title benches), pay claims
590 → 638, unpriced 4,001 → 3,953 (3,181 unreached, 754 stating a
multiplicity, 18 listed without a rate), multi-post nodes priced 37 → 39.

**Still open after this section:** Members of Congress paid under Schedule 6
(now the largest single lead, ~150 chair and ranking-member nodes); the USPS
Board's statutory stipend; the Deputy Librarian's "greater of"; the FISC and
BVA derivations above.

### 19.15 The offices Members of Congress hold, priced at the seat rate; every remaining lead placed (2026-09-30, evening)

**The decision.** Every batch since the fourth reported $174,000 for every
committee chair and ranking member — senate.gov's SenateSalariesSince1789
page, the House Clerk's Salary.pdf, CRS RL30064 — and §19.6 through §19.14
held the lot under one question: is a committee-chair node a seat? The
premise was recorded in §7.1 as a finding ("a Member who holds one of those
posts is paid the Member rate. Neither is a committee chair separately
compensated") and used there as the reason NOT to price them. The owner
decided the other way, keeping the premise. A committee's chair and ranking
member are Members of the chamber that constitutes the committee; Schedule 6
prints a separate rate only for the Vice President, the Speaker, the
majority and minority leaders of each chamber and the President pro tempore,
and none for a committee chair, a ranking member, a whip or a conference
chair; so those offices are priced at the seat's own rate and nothing is
added for holding them. The §19.7 refusal of "eleven Senate leadership roles
at $174,000" said in terms that "pricing a whip as a Member is the
committee-chair decision"; it is the same decision, and it is made.

**The rule, not a table.** `us_code_pay_schedules.match_member_seats`
reaches two shapes. A **committee post** is a single-post Position whose
name begins `Chair, ` or `Ranking Member, ` under a parent typed Committee
or Subcommittee: 436 nodes, 218 of each, and the `Staff Director` /
`Minority Staff Director` nodes beside them are never reached. A
**leadership office** is one of 25 nodes listed by id
(`MEMBER_LEADERSHIP_NODES`) under a chamber's Leadership grouping: the
Senate's eleven (both whips, both assistant leaders, both conference chairs,
the conference secretary, both policy committee chairs, the steering and
campaign committee chairs) and the House's fourteen (the Speaker pro
tempore, both whips, both chief deputy whips, the Democratic Caucus chair
and vice chair, the Republican Conference chair, vice chair and secretary,
the Steering & Policy chair, and the Republican Study Committee, Freedom
Caucus and New Democrat Coalition chairs). **The chamber is read off the
tree**: `leg-senate` prices from "Senators", `leg-house` from "Members of the
House of Representatives", and every House record notes that the Delegate
and Resident Commissioner rows print the same 174,000. Each record carries
its own method and a `memberSeat` block with the role, the body, the chamber
and the basis in words; the panel leads with "PRICED AS A MEMBER'S SEAT, NOT
FOR THE OFFICE"; the document count is one document stating the figure for
the seat, with a caution saying the identification is a reviewed rule and
not a document naming the post; `scopeMatch: proxy`, graded `partial`. The
gate mirrors the rule and refuses the forgeries `CLAUDE.md` lists;
`tests/test_us_code_pay_schedules.py` pins both directions and asserts on
the published graph that every qualifying chair and ranking member carries a
seat and no staff director does.

**Four posts refused by name**, each a decision and not a gap:

- **The Joint Economic Committee's Chair and Vice Chair.** The chair
  alternates between the chambers by Congress and the vice chair is from the
  other chamber. Schedule 6 prints one figure for both rows, so the number
  would be the same either way — but a record names one row, and which
  chamber the holder sits in is a fact about a person this project never
  reads. §19.11 refused the same two from the Clerk's page on the held
  decision; they stay refused on this narrower ground.
- **Problem Solvers Caucus Co-Chairs.** Two people in a form the multi-post
  rule cannot read (the name states no `(×N)`); the figure would be each
  co-chair's, and nothing on the node says how many there are.
- **President of the Senate (Vice President).** The office `exec-vp` already
  carries at Schedule 6's own Vice President row; one officer, one salary,
  priced once (§19.6).

One curation note, recorded rather than fixed: the Senate Leadership
grouping carries both `Majority Whip` and `Assistant Majority Leader` (and
the minority pair), which in the Senate are two names for one office. Both
are priced, each as a Senator's seat, so no published figure is wrong; but a
reader counting priced posts is counting that office twice, and whether to
merge the pair is a `merge_duplicate_nodes.py` question for §3, not a pay
question.

**Counted on the rebuilt graph:** 461 offices priced (436 committee posts,
25 leadership offices; Senate 191, House 270); statutory-pay positions
24 → 485; pay claims **638 → 1,099**; unpriced **3,953 → 3,492**
(2,720 unreached, 754 stating a multiplicity, 18 listed without a rate);
organisations with an unpriced position 734 → 627; the prompt pack's shards
38 → 34. Nothing measured moved and no organisation's estimate moved: a
post is not a budget unit and takes no share.

**Every other lead from the nine batches, placed.** The owner asked that
nothing from the Perplexity responses be left unplaced before the next
batch. Read against §19.12's ledger and §19.14's triage, what remained was
this, and each is now either built, declined with its reason, or blocked by
one named fetch:

- **FISC judges and the presiding judge at the district-judge rate
  (50 U.S.C. 1803(a)).** The shape is `derived_pay.py`'s with a composition
  sentence: the section designates eleven district judges, and this graph
  carries the presiding judge and a `FISC Judge (×10 assigned district
  judges)` node, which is the statute's eleven. **Blocked by the fetch**:
  `uscode.house.gov` closed every tunnel this evening
  (`docs/NETWORK_ACCESS.md` §15). Not built on memory; the section must be
  read first, because "district judges designated to the court" and "paid
  as district judges" are different claims and only the operative text says
  which the statute makes.
- **BVA Veterans Law Judges and Vice Chairman (38 U.S.C. 7101A).** The
  research reported the section as setting pay by reference to a grade or
  level. **Blocked by the same fetch**; the shape, if the section says so,
  is `tier_reference_pay.py`'s.
- **USAGM CEO (22 U.S.C. 6203).** The batch said the section sets Level III;
  §5314 as committed does not print the office (§19.14). **Blocked by the
  same fetch**; if the section sets the pay by reference, the tier-reference
  shape; if it names nothing, declined.
- **The USPS Board of Governors' stipend (39 U.S.C. 202).** Two things stand
  against it before the fetch: the graph's node is `USPS Board of Governors
  (9 members)`, a body standing for nine, and "$30,000 a year plus $300 a
  day" is not an annual rate of basic pay — the per-diem half is nobody's
  figure until somebody's attendance is known, which is person-level.
  **Blocked by the same fetch** for the reading; expected outcome: declined.
- **The Deputy Librarian's "greater of".** Declined in §19.11 and unchanged:
  §136a–2(2) pays "the greater of" two figures, and choosing one is
  arithmetic on a comparison no document performs.
- **The EPA's ten regional administrators and deputies as SES in the 2024
  Plum Book.** Re-checked on the published graph: none of the twenty nodes
  carries a PLUM listing from the archive or the current export, so the
  rows exist and do not reach the nodes by name — an organisation/alias
  question for `positions.py`'s matcher and not a pay row (§19.14 stands).
  Were they listed, the ES plan states a range and no rate, and
  `gs_pay.py` would publish the SES band.
- **NASA's and the SBA's Associate Administrators against the Code's counted
  classes.** Re-checked against the current export: NASA's five
  mission-directorate Associate Administrators are listed on the ES plan
  (four with a printed rate, which they publish; one without), so the Level
  V class is contradicted by the one document that could settle it, and the
  SBA's four carry no listing at all and stay declined on the same doubt
  (§19.14 stands).
- **The NCUA's and PRC's Vice Chairs, the SEC's Chair, the EPA's
  Administrator, the pay-freeze memo's "$158,500 / $168,400", the
  GAO/NSF/CAVC bands, Foreign Service and Capitol Police systems.** Declined
  in §19.14 with the reason on each; nothing new was reported and nothing
  changes.

**Still open after this section:** exactly four fetches — 50 U.S.C. 1803,
38 U.S.C. 7101A, 22 U.S.C. 6203 and 39 U.S.C. 202 — each in one
`fetch_fixture.py` command once the host answers, and each with its shape
decided above. No lead from the nine batches is undecided. The next batch
can start.

### 19.16 The tenth batch: the Court of International Trade from Schedule 7, the Ex-Im Vice Chair, and a host under maintenance (2026-10-05)

**The four fetches, retried, and seven stubs deleted.** `uscode.house.gov`
answered every request this morning — the four sections §19.15 left open and
three more this batch named — with HTTP 200 and a 14,615-byte page titled
"Under Maintenance", the same page for 5 U.S.C. 5312, which is committed and
real. `fetch_fixture.py` wrote seven "fixtures" on those 200s; each yields an
empty operative text; all seven were deleted with their `.meta.json` before
anything read them (`docs/NETWORK_ACCESS.md` §15). So the FISC, BVA, USAGM and
USPS leads stand exactly as §19.15 placed them, and two of this batch's
leads join them, each with its shape decided:

- **The Tax Court's special trial judges, 26 U.S.C. 7443A.** The batch names
  the section and no figure. If §7443A(d) pays a special trial judge a
  percentage of a Tax Court judge's salary — which is itself 26 U.S.C.
  7443(c)(1)'s parity to the district-judge rate — the shape is a percentage of
  a JOIN, the shape §19.11 refused for the AO's and FJC's deputies
  ("arithmetic on a figure that is itself a join, which this field does not
  publish"). Three nodes now wait on that one decision, and it is the owner's:
  the arithmetic is honest and open, the objection is only that two statutes
  and a table and a multiplication is a longer chain than any record here
  carries. **Open, blocked by the fetch and then by that decision.**
- **The Election Assistance Commission, 52 U.S.C. 20923.** The batch reports
  the section compensating each commissioner "at the annual rate of basic pay
  payable for level IV of the Executive Schedule". The EAC is on no Schedule
  section this project has committed, so if the section says that it is the
  tier-reference shape (`tier_reference_pay.py`), for the two stamped nodes
  `Director / Administrator / Chair, EAC` and `Deputy Director / Vice Chair`
  as the Chair and Vice Chair the section elects from among the members.
  **Open, blocked by the fetch.**
- **The FEC's Chair and Vice Chair, 52 U.S.C. 30106.** §§5312–5316 as
  committed print no Federal Election Commission title at all (grep'd rather
  than remembered), so the Schedule cannot reach them; whether §30106 sets the
  members' pay by reference to a level is what the section would say.
  **Open, blocked by the fetch.** The batch's own row for the Chair gives no
  figure and cites §30106(a)(6), which — if the section numbers as the batch
  says — is the rotating one-year chairmanship, not pay.

**Built without the host: two things.**

- **The Ex-Im Bank's Vice Chair** (`exec-ind-misc-export-import-bank-of-the-u-s-deputy-director-vice-chair`,
  Level IV). The batch reported it at EX-IV on OPM's table alone; the
  identification is in a section already committed for the Bank's President:
  12 U.S.C. 635a(b) creates "a First Vice President of the Bank" and 635a(c)(1)
  seats "the First Vice President who shall serve as Vice Chairman" on the
  Board, and §5315 places the "First Vice President of the Export-Import Bank
  of Washington" at Level IV — the Bank's pre-1968 name, the same rename the
  President's row already relies on. One reviewed row, the Fed's shape; the
  stamped "Deputy Director / Vice Chair" template under the Bank is that
  Vice Chairman. Reviewed rows **75 → 76**.
- **The Court of International Trade's judges, from Schedule 7.** The batch's
  two CIT rows were wrong twice: they cite 28 U.S.C. 135, which is the
  DISTRICT judges' salary section (the CIT's is §252, read in §19.6 and
  stating no parity), and they give $243,300 and $231,700, neither of which is
  any 2026 judicial rate. What the lead was right about is that the nodes
  exist. `CLAUDE.md` and the Schedule 6 module's docstring both said the CIT
  "has a court node and no judge node"; it has `Chief Judge, CIT` and
  `Judge (×8)`, and nobody had looked at the graph. Schedule 7 of the same
  note this project has read since 2026-09-23 prints "Judges of the Court of
  International Trade 249,900" — the one judicial tier uscourts.gov's own table
  does not print, which is why `judicial_pay.py` could never reach it and why
  Schedule 7 had "priced nothing". `SCHEDULE_7_NODE_ROWS` prices exactly those
  two under `positionStatutoryPay` with `schedule: "7"`: the chief judge as a
  judge of that court, the bench for each of eight holders (the field is
  office-rate class). The gate's mirror grows the row, Schedule 7's heading
  and the marked head of ITS column ($320,700), and refuses the District
  Judges row claimed in the CIT's place, a Schedule 7 tier outside the
  judiciary, a Schedule 6 office on a judge, the mark dropped, and the record
  moved to the Tax Court's chief judge. `derived_pay.py`'s refusal of the CIT
  under §252 stands unchanged — that module still cannot derive it; a document
  that states the figure outright is a different claim. Multi-post nodes
  priced **39 → 40**.

**The rest of the batch, placed.** Some 230 Senate and House committee chairs
and ranking members at $174,000 from senate.gov and the Clerk's Salary.pdf —
every one already priced by §19.15's member-seat rule, checked against the
published graph rather than assumed (the rule's published-graph test asserts
every qualifying node carries a seat). Every staff director and minority staff
director: "none", which agrees with the rule never reaching them. Declined,
each for a reason an earlier section already gives:

- **SES "ranges" on some forty deputies, chiefs of staff, general counsels
  and regional heads** (DOJ division DAAGs, State's DASes, EPA's and the FMC's
  officers, Ginnie Mae's, HUD's, PHMSA's, WHD's, IHS's area directors, NASA's
  and NSF's deputies) from OPM's ES table: `gs_pay.py` publishes an SES band
  only where a PLUM listing reports the ES plan for the post, because the
  table names a pay system and no post, and "likely SES" is a guess about which
  system. Where the current export lists one of these on ES the band is
  already published or a printed rate stands in its place; the rest need a
  listing, not a row.
- **NSF's AD-3 and AD-4 ranges** from nsf.gov's careers page, on every
  division director and programme director: a recruitment page's band for a
  pay plan, naming no post (§19.14 stands).
- **DOJ Criminal Division trial attorneys at GS-15** from one vacancy
  announcement: one posting's grade for one opening is not the system the
  `(×multiple)` node's holders are on, and the GS range would need a listing.
- **The EPA Administrator at EX-II**: the batch cites OPM's table and nothing
  identifying the office; §5313 does print "Administrator of the Environmental
  Protection Agency", and the one identifying document would be
  Reorganization Plan No. 3 of 1970, which is not a section of the Code. Stays
  declined (§19.14) rather than priced from a name match the whole-name route
  refuses because the graph writes "Administrator, EPA".
- **The FEC's Deputy Director / Vice Chair at EX-IV, "speculative"**: the
  Schedule does not print the FEC; see the §30106 lead above.
- **IHS's Chief Medical and Chief Nursing Officers as Title 38**: a system
  named, no document.
- **NSC directors, BEA's, IES's, OCR's, OMB's and the Solicitor General's
  staff, CAVC and Tax Court clerks and counsel: "unknown"** — nothing offered,
  nothing to decide.

Counted on the rebuilt graph: pay claims **1,099 → 1,102**, unpriced
**3,492 → 3,489** (2,718 unreached, 753 stating a multiplicity, 18 listed
without a rate), statutory-pay positions 485 → 487, Schedule-priced 214 → 215.

**Still open after this section:** the same four fetches plus three — 50
U.S.C. 1803, 38 U.S.C. 7101A, 22 U.S.C. 6203, 39 U.S.C. 202, 26 U.S.C. 7443A,
52 U.S.C. 20923, 52 U.S.C. 30106 — each one `fetch_fixture.py` command once
the host serves sections again, and `load_basis_section` will refuse a
maintenance page by its empty operative text if one is ever committed by
mistake; and one decision, the percentage-of-a-join shape (the AO's and FJC's
deputies, the Tax Court's special trial judges). Both were taken up the same evening; see §19.17.

### 19.17 The special trial judges, and a percentage of a join (2026-10-05, evening)

**The decision.** The owner's instruction was "retry the seven fetches and
price the special trial judges". §19.16 had left the percentage-of-a-join
shape as the one open decision: `derived_pay.py` priced a percentage of the
compensation table's own printed figure (the bankruptcy judges, §19.15) and
refused a percentage of a figure that is itself a join, naming the AO's and
FJC's Deputy Directors as the two posts refused on it. The special trial
judges are the same shape — 26 U.S.C. 7443A(d) pays "90 percent of the rate
for judges of the Tax Court", and a Tax Court judge's rate is 26 U.S.C.
7443(c)(1)'s parity to a district judge's, so the percentage is of a join —
and pricing them is deciding the shape. All three are priced by one rule
rather than three exceptions.

**The seven fetches.** 50 U.S.C. 1803, 38 U.S.C. 7101A, 22 U.S.C. 6203, 39
U.S.C. 202, 26 U.S.C. 7443A, 52 U.S.C. 20923 and 52 U.S.C. 30106 were
retried against `uscode.house.gov` and every one came back as it had in the
morning: HTTP 200 and the 14,615-byte "Under Maintenance" page. Seven stubs
deleted with their `.meta.json` files, nothing committed, `docs/NETWORK_ACCESS.md`
§15. The one section the decision needed was then taken from the Government
Publishing Office's rendering of the **2024 edition** of the Code on
`www.govinfo.gov` — a host this repository already reads the Government
Manual and OMB's Public Budget Database from, whose `robots.txt` allows
`/content/pkg/`. The link service `https://www.govinfo.gov/link/uscode/26/7443A?link-type=html`
resolved to the granule
`USCODE-2024-title26/html/USCODE-2024-title26-subtitleF-chap76-subchapC-partI-sec7443A.htm`
(a URL guessed from the chapter structure, `partII`, was a 404 behind a
redirect to `/error`, which is why the link service and not a guess is the
route recorded). Committed as
`tests/fixtures/uscode/tax_special_trial_26_usc_7443A_govinfo2024.html`, 9,412
bytes, sha256 `a6a6274d…05db`, fetched 18:44 UTC. GPO's rendering prints the
same "Editorial Notes" heading the OLRC's does, so `operative_text` cuts it at
the same place and the quote is checked against the law and not the notes. The
record names the publisher and the edition; `derived_pay.STATUTE_HOSTS` is the
closed list of the two hosts, and the gate refuses a statute cited to any
other.

**What the sections say, read against the operative text.**

- **26 U.S.C. 7443A(d)**: "Each special trial judge shall receive salary—
  (1) at a rate equal to 90 percent of the rate for judges of the Tax Court,
  and (2) in the same installments as such judges." A rate, for every special
  trial judge, by the statute's own "Each".
- **26 U.S.C. 7443(c)(1)**, already committed: the Tax Court judge's parity to
  a district judge's rate — the middle statute of the chain.
- **28 U.S.C. 603**, already committed, in two sentences with an unrelated
  sentence between: "The salary of the Director shall be the same as the
  salary of a district judge." and "The salary of the Deputy Director shall be
  92 percent of the salary of the Director." Both are re-found in the
  operative text separately and the record prints them joined by " … ";
  `tests/test_derived_pay.py` asserts they are each in the law and not
  contiguous.
- **28 U.S.C. 626**, already committed: "The compensation of the Deputy
  Director of the Federal Judicial Center shall be the same as that of the
  Deputy Director of the Administrative Office of the United States Courts."
  — a chain through §603 to the tier.

**Three nodes priced**, each `positionDerivedPay`, `scopeMatch: proxy`,
graded `partial`, arithmetic in the open, no document stating the figure:

| Node | Figure | Documents | Chain |
|---|---|---|---|
| `Special Trial Judge (×multiple)`, U.S. Tax Court | $249,900 × 90% = **$224,910**, for each holder | 3 (90%) | 7443A(d) → 7443(c)(1) → table |
| `Deputy Director`, Administrative Office of the U.S. Courts | $249,900 × 92% = **$229,908** | 2 (80%) | 603 (two sentences) → table |
| `Deputy Director`, Federal Judicial Center | $249,900 × 92% = **$229,908** | 3 (90%) | 626 → 603 → table |

The `NOT_PRICED` reasons the two Deputies carried are withdrawn. The
magistrate judges (§634(a)'s "up to") and the Court of International Trade
(§252 states no parity; Schedule 7 prices it, §19.16) stay refused in this
module for the reasons §19.15 and §19.16 record, and nothing else in the
batch moved.

Counted on the rebuilt graph: derived records **12 → 15**, pay claims
**1,102 → 1,105**, unpriced **3,489 → 3,486** (2,716 unreached, 752 stating
a multiplicity, 18 listed without a rate), multi-post nodes priced **40 → 41**.

**Still open after this section:** six sections — 50 U.S.C. 1803, 38 U.S.C.
7101A, 22 U.S.C. 6203, 39 U.S.C. 202, 52 U.S.C. 20923, 52 U.S.C. 30106 — each
one `fetch_fixture.py` command against either host (govinfo's link service
`/link/uscode/<title>/<section>?link-type=html` resolves the granule when the
OLRC's host is down), with the lead each serves named in §19.15 and §19.16.
Fetched from govinfo the same evening; see §19.18.

### 19.18 The six sections, read from govinfo: three price five posts, three price nothing (2026-10-05, later)

**The instruction** was "fetch the six sections from govinfo and keep
going". Each was resolved through govinfo's link service and committed from
GPO's rendering of the 2024 edition (`docs/NETWORK_ACCESS.md` §15 has the
granules and sizes). Read against the operative text, each section says
exactly one thing about pay, and the six fall into two groups.

**Three are the tier-reference shape, and two of the three fall under the
stamp rule.**

- **22 U.S.C. 6203(b)(3)**: "A Chief Executive Officer appointed pursuant to
  paragraph (1) shall be compensated at the annual rate of basic pay for level
  III of the Executive Schedule under section 5314 of title 5." §19.14 had
  declined the USAGM CEO because §5314 prints no such office; it does not need
  to — this section sets the pay by reference, which is `tier_reference_pay.py`'s
  shape. The graph's node is the stamped `Director / Administrator / Chair,
  Broadcasting Board of Governors / USAGM`, and (b)(1) of the same section
  says what stands under it: "The head of the United States Agency for Global
  Media shall be a Chief Executive Officer, who shall be appointed by the
  President, by and with the advice and consent of the Senate." Priced at
  Level III, **$209,600**.
- **52 U.S.C. 20923(d)(1)**: "Each member of the Commission shall be
  compensated at the annual rate of basic pay prescribed for level IV of the
  Executive Schedule under section 5315 of title 5." (c)(1): "The Commission
  shall select a chair and vice chair from among its members for a term of 1
  year, except that the chair and vice chair may not be affiliated with the
  same political party." So the EAC's chair and vice chair are members and
  (d)(1) prices them. The stamped `Director / Administrator / Chair, Election
  Assistance Commission` and `Deputy Director / Vice Chair` are read as the
  Chair and the Vice Chair, the pair the statute creates; the EAC's Executive
  Director (20924) has no statutory deputy, so the "Director / Deputy
  Director" reading has nothing to pair with. Both at Level IV, **$197,200**.
- **52 U.S.C. 30106(a)(4)**: "Members of the Commission (other than the
  Secretary of the Senate and the Clerk of the House of Representatives)
  shall receive compensation equivalent to the compensation paid at level IV
  of the Executive Schedule (5 U.S.C. 5315)." (a)(5): "The Commission shall
  elect a chairman and a vice chairman from among its members (other than the
  Secretary of the Senate and the Clerk of the House of Representatives) for
  a term of one year." The same pair reading, for the same reason: (f) gives
  the FEC a staff director and a general counsel, paid "at a rate not to
  exceed" Levels IV and V — ceilings, which price nothing — and no deputy.
  The batch's own row cited "§30106(a)(6)", which does not exist; (a)(4) and
  (a)(5) are the sentences. Both at Level IV, **$197,200**. The FEC's
  `General Counsel` already carries OPM's archived listing ($184,900, the
  Level V figure the ceiling names) and is left as it is.

Each of the five rows carries `identificationQuote`, the second sentence of
its own section, re-found in the operative text on every run and published as
`identification.statuteIdentifies`; it is not a second document, so the
record rests on two (80%) with neither stating the figure. The derive step
records the publisher as the Government Publishing Office and the edition as
2024, and the gate now accepts a Code granule from either host — keyed on the
granule, not the host, because govinfo also serves the Government Manual
whose URL sits among many nodes' own sources; a host-keyed first version
refused seventeen honest Inspector General blocks and was corrected before
anything was published.

**Three price nothing, each for a reason in the text.**

- **50 U.S.C. 1803(a)** — the FISC. "The Chief Justice of the United States
  shall publicly designate 11 district court judges from at least seven of
  the United States judicial circuits … who shall constitute a court". That
  is composition and jurisdiction; the section's only sentence about
  compensation is (i)(11), an amicus's, "at such rate as the court considers
  appropriate". The judges' pay is each one's own district judgeship, which
  this section neither sets nor restates, and nothing in it limits
  designation to judges in active service — a senior district judge remains a
  "district court judge", and this file already refuses one figure for a
  bench that may include senior judges because 28 U.S.C. 371(b)(2) sets their
  salary apart from the tier's. `Presiding Judge, FISC` and `FISC Judge (×10
  assigned district judges)` stay unpriced; the lead §19.15 carried as "the
  shape is `derived_pay.py`'s with a composition sentence" was wrong about
  the shape, because the section makes no parity claim to join.
- **38 U.S.C. 7101A(b)** — the Board of Veterans' Appeals. "Members of the
  Board (other than the Chairman and any member of the Board who is a member
  of the Senior Executive Service) shall, in accordance with regulations
  prescribed by the Secretary, be paid basic pay at rates equivalent to the
  rates payable under section 5372 of title 5." That names a pay SYSTEM (the
  administrative law judge system, several levels and steps OPM sets) and no
  rate, and carves out members in the SES without naming which. `Veterans
  Law Judge (×multiple)` cannot take a band "for each holder" when the
  statute says some holders are paid under another system, and `Vice
  Chairman` is a member whose system the section leaves to the carve-out.
  Declined. A band from OPM's ALJ table on a node the carve-out does not
  reach would be a new decision, and there is no such node.
- **39 U.S.C. 202(a)(1)** — the Postal Service's Governors. "Each Governor
  shall receive a salary of $30,000 a year plus $300 a day for not more than
  42 days of meetings each year". A stipend plus an attendance figure is not
  an annual rate of basic pay; the per-diem half is nobody's figure until
  somebody's attendance is known, and `USPS Board of Governors (9 members)`
  is a body of nine. (c) and (d) leave the Postmaster General's and Deputy
  Postmaster General's pay to be "fixed by the Governors", stating no figure.
  Declined, as §19.15 expected.

Counted on the rebuilt graph: tier-reference records **37 → 42**, published
**36 → 41** (the DOJ IG's archived listing still wins), reviewed rows **10 →
15**; pay claims **1,105 → 1,110**, unpriced **3,486 → 3,481** (2,711
unreached, 752 stating a multiplicity, 18 listed without a rate).

**Still open after this section:** nothing from the ten batches. Every lead
is built, declined with its reason here, or — the FISC and the BVA —
declined on the section's own text. The eleventh came the same night; see §19.19.

### 19.19 The eleventh batch: 130 House chairs already priced, the President's salary from 3 U.S.C. 102, and four declines (2026-10-05, night)

**The owner marked these as the last of the Perplexity responses.** Read
against the graph by id rather than by title:

**130 House committee and subcommittee chairs and ranking members at
$174,000.** Every one of the 130 ids exists and every one already carries the
member-seat record (§19.15): checked by id, 130 priced, 0 missing, 0
unpriced. The batch cites two documents the project had not: the House
Ethics Committee's 2026 Annual Pay Memo (`ethics.house.gov/wp-content/
uploads/2026/01/2026-Annual-Pay-Memo.pdf`) and the OLRC's chapter page for
2 U.S.C. chapter 45. Neither is fetched: each would be a second document for
a figure Schedule 6 already states for the seat, and a second source for a
published figure changes no claim here; the member-seat caution is about the
rule that makes the post a Member's, which no pay memo settles.

**The President, 3 U.S.C. 102 — built.** The batch gave the figure as
"certain" from the OLRC's chapter page; the section was fetched from GPO's
2024-edition rendering on govinfo instead (the OLRC host was still under
maintenance) and reads, in its operative text: "The President shall receive
in full for his services during the term for which he shall have been elected
compensation in the aggregate amount of $400,000 a year, to be paid monthly,
and in addition an expense allowance of $50,000 to assist in defraying
expenses relating to or resulting from the discharge of his official duties."
That is a fourth shape for `positionStatutoryPay`: the section names the
office itself and states the figure, where every earlier source printed a
figure beside a tier. `us_code_stated_pay.py` is the module, one reviewed row
keyed by node id (`exec-president`; the Code says "The President" and the
graph "The President of the United States"), graded `partial` and `proxy`
exactly as the Vice President's Schedule 6 row is. **The $50,000 expense
allowance is not published** — the same sentence says it reverts to the
Treasury when unused and is not income — and the gate refuses a block
carrying it, because the validator alone would not: the digits are in the
quote. The record also re-finds the section's own credit for the 1999
amendment that set the figure (Pub. L. 106–58, title VI, §644(a)), so the
year on the record is the year the section was read and the figure is not
claimed to have been set then. Pay claims **1,110 → 1,111**, unpriced
**3,481 → 3,480**, statutory-pay positions **487 → 488**.

**Declined, with the reason.**

- **NSF's Assistant Director for TIP at AD-5, "$202,542–$209,600", from
  nsf.gov's careers page** — a recruitment page's band for a pay plan, naming
  no post; §19.14 stands. The Deputy Assistant Director: the batch itself
  offers nothing.
- **The VA's `Deputy Under Secretary — Community Care` at Table 4 Tier 1
  ($145,000–$310,000)**, cited to `AnnualPayRanges.pdf`. The committed
  `PayTables.pdf` Table 4 Tier 1 coverage list, read off the bytes, is:
  "Deputy Under Secretary for Health; Assistant Under Secretaries for Health;
  Associate Deputy Under Secretary for Health; Assistant Deputy Under
  Secretary for Health; Chief Officers (VHA CO); Network Directors; Medical
  Center Directors". A record may claim only a whole printed item, and the
  node's name is not "Deputy Under Secretary for Health"; whether the Deputy
  Under Secretary for Community Care is one of the Deputy Under Secretaries
  for Health is a fact about VHA's structure no document in hand states.
  Declined. (The extractor renders two items as "Deput y Under Secretary for
  Health" and "Associate Deputy Un der Secretary for Health" — the text-run
  split `va_title38_pay.py`'s docstring already records — so a future match
  would have to repair that before it could test equality.)
- **`Principal Deputy Under Secretary for Health`**: the batch says
  "unknown", and Table 4 prints no "Principal" item; the whole-item rule
  refuses containment in "Deputy Under Secretary for Health". Declined.
- **The USPS area vice presidents, "not federally paid"**: the Postal
  Service sets its own pay under 39 U.S.C. 1003 and publishes no schedule
  this project has read; nothing to cite. The VISN Network CFOs: "unknown",
  nothing offered.

Counted on the rebuilt graph: pay claims **1,110 → 1,111**, unpriced
**3,481 → 3,480** (2,710 unreached, 752 stating a multiplicity, 18 listed
without a rate).

**Still open after this section:** nothing. The owner said these were the
last Perplexity responses; every lead across the eleven batches is built,
declined with its reason in this file, or declined on the section's own
text. `docs/PAY_SOURCE_RESEARCH_PROMPT_3.md` carries the 3,480 titles still
unpriced should a twelfth batch be wanted.


### 19.20 The twelfth batch, run as ten parallel agents against the repository's own documents (2026-10-05, late)

**How this batch differs from the eleven before it.** Every earlier batch was
a set of Perplexity answers pasted in by the owner and read against the graph.
The owner closed that series ("these are the last perplexity responses") and
asked for the twelfth to be started from the research pack itself, in
parallel. So this batch is ten research agents, one per cluster of
`docs/UNPRICED_POSITIONS.md` (the VA's medical centres, the White House and
the rest of the Executive Office, the regulatory and financial agencies,
Justice and Homeland Security, Defense, congressional staff, the judiciary,
the remaining departments, a scan of the Code's titles, and the Treasury
alias candidates), each read-only on the repository, each allowed `.gov` and
`.mil` documents only, each returning leads with the document's URL, what it
states (a rate, a range, a level, a system or nothing), a verbatim quote and
the join key, and declines with the reason. The agents ran two at a time on
this sandbox's four cores, so the clusters landed over an evening; what each
yielded is below, cluster by cluster, and the ones still running when this
section was written are marked.

**What was built before any cluster returned, because the panel itself was
the first finding.** The owner's complaint that positions "still don't have
their salaries attached" was true of the panel and not of the data:
`CLAUDE.md`'s "A priced post's salary is its headline figure" records the
fix, and `docs/COST_COVERAGE.md` the inventory the standing ask is measured
against.

**White House Office and the Executive Office of the President (192 unpriced
posts). Built: two reviewed Schedule rows and two matcher rules.**

- **ONDCP Deputy Director** — 5 U.S.C. 5313 prints "Deputy Director of
  National Drug Control Policy." (Level II) and 21 U.S.C. 1703(a)(1)(B),
  already committed, creates the office: "There shall be a Deputy Director
  who shall report directly to the Director, and who shall be appointed by
  the President, and shall serve at the pleasure of the President." A
  reviewed row, the Fed's shape. $228,000, `partial`, `proxy`.
- **OSTP Director (Presidential Science Advisor)** — 42 U.S.C. 6612(a),
  fetched from govinfo's 2024-edition rendering (the OLRC host still under
  maintenance): "There shall be at the head of the Office a Director who
  shall be appointed by the President, by and with the advice and consent of
  the Senate, and who shall be compensated at the rate provided for level II
  of the Executive Schedule in section 5313 of title 5." The agent proposed
  the tier-reference shape; the reviewed-row shape was used instead because
  §5313 itself prints the office — as "Director of the Office of Science and
  Technology", the Office's name before Pub. L. 94–282 (1976) created the
  present one — so this is the Fed's shape with a basis section that states
  the level itself, which the FCC's and NSF's rows already are. The gate's
  reviewed-row check accepted only an OLRC basis URL and refused the govinfo
  one on the first build; `us_code_url_names_section` now accepts either
  host's URL for the section the citation names and nothing else.
- **The export's rows under sub-organisations this graph has no node for.**
  The agent found four printed SES rates the matcher never reached — the
  OMB's and the ONDCP's Chiefs of Staff ($197,200, $195,200) and General
  Counsels — filed under "OFFICE OF THE DIRECTOR", "GENERAL COUNSEL" and
  "OFFICE OF GENERAL COUNSEL", and proposed a scoping fallback. Measured
  first, in two shapes. A broad fallback (any unmatched sub-organisation's
  rows scoped to the agency's own children) reaches 283 rows on 173 posts
  and lands an Under Secretary's "CHIEF OF STAFF" on the Secretary's eleven
  times over at Agriculture alone: **refused**. The narrow rule — the
  sub-organisation is NAMED FOR THE TITLE ("Office of the General Counsel" /
  "General Counsel") — reaches 72 rows on 70 posts, every one a stamped
  administrative title, and was built with its own `scopeRule` on the
  record, a placement under the agency, a panel sentence saying where the
  export files it, and gate checks in both directions. Two of the four posts
  the agent named are priced by it — the OMB's General Counsel ($197,200,
  under "GENERAL COUNSEL") and the ONDCP's ($195,200, under "OFFICE OF
  GENERAL COUNSEL"); both Chiefs of Staff sit under "OFFICE OF THE
  DIRECTOR", which is not named for a Chief of Staff, and stay unpriced by
  this rule, which is the honest edge of it.
- **The White House rank fold, applied to the export.** "ASSISTANT TO THE
  PRESIDENT AND DIRECTOR OF LEGISLATIVE AFFAIRS" folds, by the roster
  module's own `title_core`, to the graph's `Director of Legislative
  Affairs`; 8 rows reach 7 posts, the Director of Legislative Affairs among
  them (the July roster prints no row for the principal). The first build
  matched the row in the derive step and then refused it as "renamed" in the
  build, because the rename guard did not know the fold; it does now.
- **Declined, with the reason.** The three Deputy USTRs are a counted class
  ("Deputy United States Trade Representatives (3)", Level III, 19 U.S.C.
  2171(b)(2) composing exactly three) whose nodes are named "Deputy USTR —
  Americas" and so fail the counted-class name rule (the singular office
  first and whole); a rename is a curated-file write no sanctioned script
  makes for a post of this shape, and an alias is read by no money join —
  left for a rename decision. Three WHO posts the roster and the export both
  print at one rate under a title the graph words differently ("Assistant to
  the President & Counsel" against "COUNSEL TO THE PRESIDENT", "Chief
  Speechwriter" against "DIRECTOR OF SPEECHWRITING", "Director of Public
  Liaison" against "DIRECTOR OF THE OFFICE OF PUBLIC LIAISON") — the
  equality-after-fold rule is right to refuse each, and the same rename
  decision applies. The NEC's Director and deputies are WHO appointees
  printed in the WHO roster under compound titles and placed outside the
  `exec-eop-who` subtree the roster module scopes to. 3 U.S.C. 105, 106 and
  107 state CEILINGS ("at rates not to exceed … level II"), as do 42 U.S.C.
  6612(b) for OSTP's Associate Directors, 42 U.S.C. 4372(b) and 19 U.S.C.
  2171(e)(1): none prices anybody. The NSC's and CEA's staff are a pay
  SYSTEM (the General Schedule; AD for the CEA's experts) with no title
  named. Seven WHO posts the roster lists at $0.00 and 33 titles it lists at
  differing rates stay refused as before.

**The VA's medical centres (450 unpriced posts). Built: nothing; the governing
handbook confirms the refusal.** The agent read VA Handbook 5007 Part IX
(5007/59): paragraph 9c assigns the TIER by role ("Tier 3. Service chief,
service line manager or other assignment … requiring a specialty within the
assigned pay table") and paragraph 13a makes the TABLE a per-person
determination ("recommending the appropriate pay table, tier level and
market pay amount … for individual physicians, dentists [and podiatrists]").
So no VA document assigns "Chief — Medicine Service" to Table 1 or Table 2,
and §19.2's refusal of the sixteen service-chief families (288 nodes) rests
on the source now rather than on inference. The four leads it did return are
all USAJOBS vacancy announcements giving a pay plan and grade (VAMC Associate
Director GS-15 on five announcements; Associate Director for Patient Care
Services Nurse V on four; Network CFO GS-15 on one, a detail; VA Police
Chief GS-12 on two), and §19.12 refuses a vacancy posting as a pay document:
a posting is one facility's advertisement for one appointment, not a
document stating what the title pays. Recorded, not built; the owner can
decide the class. Two curation findings ride with it: Handbook 5007 Part II
Appendix B defines the Nurse Executive as "Chiefs of Nursing Service or
equivalent positions that represent the highest ranking nurse management
position at a facility", so the graph's separate `Chief — Nursing` beside
`Associate Director for Patient Care Services (CNO)` duplicates one post;
and the Network CFO announcement says VISN CFOs report to VA's Office of
Management, not to the Network Director. Nurses are a per-station locality
system (152 stations, 8,513 rows); pharmacists and social workers are
hybrid Title 38 on per-station GS special rates; canteen chiefs are outside
the GS by 38 U.S.C. 7802(e). A "Physician (×multiple)" band spanning Tables
1 and 2 ($124,308–$400,000) was flagged and not recommended: the union is
not a printed row.

**A displacement the rules made, recorded as a finding.** With the export's
listings reaching 252 posts, four tier-reference figures were displaced by a
listed level the table prices, under the standing rule that a figure set by
reference never displaces a printed one: the GPO's Director (listed EX II,
the same $228,000) and the Treasury's, Commerce's and Energy's Inspectors
General, which OPM's export lists at EX IV, EX IV and EX III where 5 U.S.C.
403(e) sets Level III plus 3 percent ($215,888). Two official documents
disagree about three Inspectors General; the panel now shows the export's
level and the table's rate for it, and this ledger records that the Act says
otherwise. Whether a statute's tier-reference figure should outrank an
incumbency listing's level is the owner's decision.

**Justice and Homeland Security (about 230 unpriced posts across 25
organisations). Built: four reviewed Schedule rows, one tier-reference row,
one alias row.**

- **CISA's two Executive Assistant Directors** (Cybersecurity;
  Infrastructure Security) — 5 U.S.C. 5315 prints "Assistant Director for
  Cybersecurity, Cybersecurity and Infrastructure Security Agency" and
  "Assistant Director for Infrastructure Security, …" at Level IV, and 6
  U.S.C. 653(a)(3) and 654(a)(3) (fetched from govinfo) each deem "Any
  reference to … Assistant Director for Cybersecurity in any law, regulation,
  map, document, record, or other paper of the United States" to be a
  reference to the Executive Assistant Director — the same deeming shape 6
  U.S.C. 652(a) supplies for CISA's Treasury line. Reviewed rows, Level IV,
  $197,200 each.
- **Director, BOP** — §5315's "Director, Bureau of Prisons, Department of
  Justice" (Level IV) with 18 U.S.C. 4041: "The Bureau of Prisons shall be in
  charge of a director appointed by and serving directly under the Attorney
  General." The scoped route had refused this one because the office half is
  the bare word Director.
- **FEMA Deputy Administrator** — §5314's class "Deputy Administrators,
  Federal Emergency Management Agency" (Level III) with 6 U.S.C. 321c(a)
  composing "not more than 4 Deputy Administrators"; the agent's correction
  that the composition is in §321c and not in the committed §313 is right,
  and §321c is committed now. The graph's second node, `Deputy Administrator
  — Protection & National Preparedness`, is declined: the export lists two
  PAS EX-III rows, neither under that name, so the name reads as stale, and
  a reviewed row is written against a node's name.
- **Secret Service Chief, Uniformed Division** — 5 U.S.C. 10203(a) prints the
  Division's schedule of rates as a table and sets the Chief's row by
  reference: "the Chief position will be equal to the rate of pay for level V
  of the Executive Schedule" — the Code's own footnote reads "So in original.
  Probably should be followed by 'for'", so the quote stops where the printed
  words do. A tier-reference row, $184,900; the Officer and Sergeant rows of
  the same schedule are as-enacted figures adjusted annually under (b)(1)(A),
  and the current schedule sits on a host that answers 403.
- **The Bureau of Prisons, in the alias table.** The export files all 72 of
  the Bureau's live rows under "FEDERAL BUREAU OF PRISONS" and this graph
  names the node "Bureau of Prisons (BOP)", so its Director's and Deputy
  Director's rows reached nothing. One row in `node_aliases.json` (§17), with
  18 U.S.C. 4041's statutory name as the basis: the Deputy Director's
  $193,209 reaches the graph through it, and the alias is read by the
  export's agency scoping only, never by a money matcher.
- **Declined, with the reason.** 28 U.S.C. 548 caps U.S. Attorneys and
  Assistant U.S. Attorneys at Level IV ("Subject to sections 5315 through
  5317 of title 5, the Attorney General shall fix the annual salaries") — a
  ceiling. 6 U.S.C. 464(b) and 317(b)(1) put the FLETC Director and FEMA's
  Regional Administrators in the Senior Executive Service by statute, a pay
  SYSTEM the project has no shape for yet (a statute-placed SES range would
  be a new field; recorded as a candidate). The 94 U.S. Marshals are an SL
  bench the export lists mostly at $197,200 and once at GS-15 — not one rate
  for every holder. The DHS Chief of Staff sits under "OFFICE OF THE
  SECRETARY", which is not named for a Chief of Staff. CISA's Executive
  Assistant Director for Emergency Communications ($220,780) and TSA's
  Executive Assistant Administrators ($221,900) are printed under titles the
  graph words differently ("FOR" where the graph prints a dash; "Executive"
  dropped) — rename candidates, not matcher loosenings. The DHS and DOJ
  Directors of Legislative and Public Affairs under the stamp are, by 6
  U.S.C. 113(a)(1)(I) and 28 U.S.C. 506, Assistant Secretaries and an
  Assistant Attorney General if designated — conditional, and the node names
  are not the class's office. TSA's 2026 compensation bands by occupational
  series, the Coast Guard's flag grades (37 U.S.C. 203(a)(2) is a ceiling and
  the DFAS table is walled) and the FBI/DEA SES system (5 U.S.C. 3151 names no
  title) price nothing. Every DOJ and DHS component host probed answers an
  Akamai 403.

**The regulatory and financial agencies. Built: nine reviewed Schedule rows
and three tier-reference rows — and one earlier decline corrected.**

- Reviewed rows, each the Fed's shape with the body's own section committed
  (the NLRB's, FDIC's and DFC's fetched from govinfo; the MSPB's, NTSB's,
  Peace Corps', PRC's and FLRA's already in hand for their chairs or members):
  the **NLRB's Chairman** (III; 29 U.S.C. 153(a) "The President shall
  designate one member to serve as Chairman of the Board."); the **FDIC's
  Chairperson** (III) and **Vice Chairperson** (IV, the Code's singular
  "Member, Board of Directors of the Federal Deposit Insurance Corporation";
  12 U.S.C. 1812(b)(1)–(2)); the **MSPB's Vice Chairman** (IV; 5 U.S.C.
  1203(b)); the **NTSB's Vice Chairman** (IV; 49 U.S.C. 1111(d)); the **Peace
  Corps' Deputy Director** (IV; 22 U.S.C. 2503(a)); the **PRC's Vice
  Chairman** (IV, one of "Members, Postal Regulatory Commission (4)"; 39
  U.S.C. 502(e)); the **FLRA's General Counsel** (V, the Code's one compound
  item "Members, Federal Labor Relations Authority (2) and its General
  Counsel"; 5 U.S.C. 7104(f)(1); the export already listed the post at EX V,
  which agrees); and the **DFC's Chief Executive Officer** (II; 22 U.S.C.
  9613(d)(1)). Six of the nine price a stamped "Director / Administrator /
  Chair" or "Deputy Director / Vice Chair" node, each only because the body's
  own section names the office under it.
- **§19.14 was wrong about the PRC.** It declined the PRC's Vice Chair
  because "neither statute designates one" and recorded that 39 U.S.C. 502
  had not been fetched; §502(e), committed since for the Chairman's row,
  reads "The Commissioners shall by majority vote designate a Vice Chairman
  of the Commission." The NCUA half of that decline stands.
- Tier-reference rows: the **PCLOB's chairman** at Level III (42 U.S.C.
  2000ee(i)(1)(A), with (h)(1) naming "a full-time chairman and 4 additional
  members" under the stamp — a section number with two letters, which the
  three operative-text readers refused until their heading pattern admitted
  it); the **ARC's Federal Cochairman** at Level III (40 U.S.C. 14301(c),
  with (b)(1) composing the Commission "of the Federal Cochairman … and the
  Governor of each participating State"); and **AmeriCorps' Chief Executive
  Officer** at Level III plus 3 percent (42 U.S.C. 12651c(b), with (a)
  putting the Chief Executive Officer at the head of the Corporation) — the
  Inspector General Act's arithmetic on a reviewed row, $215,888, which the
  gate's row tuple now carries as a seventh element.
- **Declined, with the reason.** The NRC's three statutory office directors
  are Level IV in the Code and ES $228,000 in the export — recorded as a
  conflict, priced from neither. The FCC's Managing Director: 47 U.S.C.
  155(e) sets Level V and the export prints $228,000, now published; a
  tier-reference row would be derived and displaced on every build, so the
  conflict is recorded instead. The SEC's Chairman and the EPA's
  Administrator are identified by Reorganization Plans in Title 5's
  Appendix, a document kind the reviewed-row reader has not handled. The
  ARC's alternate Federal Cochairman (Level V) is not shown to be the stamped
  "Deputy Director / Vice Chair". The SSA's Chief Actuary is paid "at the
  highest rate of basic pay for the Senior Executive Service under section
  5382(b)", whose maximum depends on a certification this project cannot
  read. OPM's five Associate Directors are a counted class at Level V the
  export lists on the ES plan, which the counted-class rule defers to. TVA's
  chairman draws a stipend. Administrative law judges are an AL table across
  steps. NASA's centre directors, EPA's regional administrators and SSA's
  deputy commissioners are export rows whose titles or organisations this
  graph words differently ("DIRECTOR, AMES RESEARCH CENTER" against "Center
  Director, Ames Research Center (ARC)"; "REGION 1- BOSTON, MASSACHUSETTS"
  against "EPA Region 1 (New England)"; "DEPUTY COMMISSIONER FOR OPERATIONS"
  against "Deputy Commissioner — Operations") — rename and alias candidates.
  **The strongest new-source lead** is the Federal Reserve's own Annual
  Report, Table G.12, which prints each Reserve Bank president's annual
  salary (Boston $496,700 … New York $568,100, effective December 31, 2024),
  on a `.gov` host: a roster-shaped document for twelve nodes this project
  has no module for yet. The Fed, SEC, CFTC, OCC, NCUA and FDIC set their own
  staff pay outside Title 5 and publish no figure per title; www.sec.gov
  answers the crawler 403.

**The batch's running total.** Pay claims **1,111 → 1,158**, unpriced
positions **3,480 → 3,433**, reviewed Schedule rows **76 → 91**,
Schedule-priced posts **215 → 230**, tier-reference records **42 → 46** (41
published), current-export listings **170 → 255** (255 with the Bureau of
Prisons alias; 252 without), printed rates **88 → 128**, nodes with an
official source **980 → 1,039**.

**Defense: the military basic-pay table was in the repository all along
(2026-10-06).** The Defense cluster's first finding was about this
repository and not about the government. `tests/fixtures/dfas/README.md`
had recorded, on 2026-09-27, that every host publishing the uniformed
services' basic-pay table answers 403, and the cluster re-measured the same
refusal on ten hosts — then found the table in a file committed four days
before that README was written: the note to 5 U.S.C. 5332
(`tests/fixtures/uscode/pay_schedules_5_usc_5332.html`), from which
`us_code_pay_schedules.py` prices Schedules 5, 6 and 7, reproduces Executive
Order 14368 in full, and its **Schedule 8 — Pay of the Uniformed Services
(Effective January 1, 2026)** is the monthly basic-pay table itself, every
officer, warrant and enlisted row with its footnotes. The parser had refused
every schedule number but the three it was written for, so the document sat
unread under a digest the gate already recomputed on every run.

`military_pay.py` reads the eighth schedule from the same bytes, and prices
posts by two routes, both from it. **A grade a statute fixes:** Title 10 and
Title 14 fix the grade of seventeen posts in so many words — "The Chief of
Staff, while so serving, has the grade of general without vacating his
permanent grade" (10 U.S.C. 7033(b)), "The Commandant while so serving shall
have the grade of admiral" (14 U.S.C. 302) — 37 U.S.C. 201(a)(1) assigns
"General" and "Admiral" to pay grade O-10, and Schedule 8's O-10 row prints
$18,999.90 in every one of its eleven populated columns. Three documents,
and **no document states an annual figure**: the schedule prints MONTHLY
rates ("part i-monthly basic pay"), so the $227,998.80 the graph publishes is
twelve times the printed monthly figure, arithmetic the block carries in the
open the way the Inspector General Act's 3 percent is, under a third
operation the validator now accepts (`monthly_times_12`, the factor named on
the record). The seventeen are the Chairman and Vice Chairman of the Joint
Chiefs (10 U.S.C. 152(c), 154(f)), the Chief of the National Guard Bureau
(10502(e)(1)), the chief and vice chief of each of the five services (7033,
7034, 8033, 8035, 8043, 8044, 9033, 9034, 9082, 9083), the Commandant and
Vice Commandant of the Coast Guard (14 U.S.C. 302, 304) and the two combatant
commanders whose grade a statute fixes, Special Operations Command and Cyber
Command (10 U.S.C. 167(c), 167b(c)). Every grade sentence was re-found in its
section's operative text, fetched from GPO's 2024-edition rendering on
govinfo; the two Space Force rows carry 201(a)(2)'s sentence as well, since
Space Force officers take the Air Force's equivalent grade. **A post the
schedule's own footnote names:** the enlisted footnote states one rate for
seven posts by title — "basic pay for this grade is $11,166.90 per month,
regardless of cumulative years of service" — and five of them are nodes here
by name equality: the Sergeant Major of the Army, the Master Chief Petty
Officers of the Navy and of the Coast Guard, the Chief Master Sergeant of the
Air Force and the Sergeant Major of the Marine Corps, at $134,002.80 a year.
The one printed item that names two offices, "Master Chief Petty Officer of
the Navy or Coast Guard", is read as both by a rule declared once and quoted
whole on the record.

Three things the module refuses, each recorded on the derive step's output.
**A row must be flat before one figure may stand for it:** Schedule 8 prices
by grade AND years of service, and a grade is priced only when its first
block prints nothing and every populated cell of its second prints the same
figure — true of O-10 (and O-9, which no row here needs) and false of every
other grade, which is why the senior enlisted advisers are priced from the
footnote that names them and never from the E-9 row, whose eleven cells run
from $8,105.10 to $10,729.20. **The document disagrees with itself by $100,
and the disagreement is published, not fixed:** the officer table's footnote
1 says basic pay for O-7 through O-10 "is limited to the rate of basic pay
for level II of the Executive Schedule in effect during calendar year 2026,
which is $18,899.90 per month", while the O-10 row prints $18,999.90; no
rendering of the order reachable from here settles it (the Federal
Register's plain text answers its "Request Access" page and govinfo's prints
the schedules as "[GRAPHIC] [TIFF OMITTED]"), so every record quotes the
footnote verbatim beside the row's figure and says the two differ. **The
nine combatant commanders whose grade no statute fixes are not priced:**
10 U.S.C. 164 fixes none, theirs comes from a presidential designation under
10 U.S.C. 601(a) that names no post, and the footnote names them only as
subject to the Level II ceiling — a ceiling, not a rate, the reading §19.7
already applied to 37 U.S.C. 203(a)(2). Also declined: the Joint Chiefs
grouping's six copies of the service chiefs and the Commandant of the Coast
Guard (the same office as the service's own node, and one salary is published
once, the rule `exec-vp` set); the Space Force's "Senior Enlisted Advisor",
because the footnote prints "Chief Master Sergeant of the Space Force" and
no document in hand says which office stands under the graph's generic title
— a rename candidate; and the Director of the National Geospatial-Intelligence
Agency, whose 10 U.S.C. 441(b)(3) grade holds only IF an officer holds the
post, a fact about a person this project never reads. The cluster's wider
declines are the staff posts: the Joint Staff's J-directors, the services'
G-, N- and A-staff deputies and the Marine Corps' Deputy Commandants (their
sections say "general officers" or "officers above captain" and fix no
grade), every service-component and area commander (designated under 601(a)
or 14 U.S.C. 305(a)(1)(A), which name no post), the Chief of Army Reserve
and the Director of the Army National Guard (appointed "from general
officers", no grade), the defense agencies' directors (50 U.S.C. 3602 and
10 U.S.C. 201 and 1073c name the posts and state no grade or pay), the
sixteen agencies' stamped CFO/CIO/CoS/GC/IG titles, and the ninety-nine
combatant-command staff posts.

**Defense: the Department's own Chief Financial Officer.** Two of the
Department's stamped administrative posts stand under titles the Code prints
for them, and one row landed. `exec-dept-defense-chief-financial-officer` is
priced as the **Under Secretary of Defense (Comptroller)** (Level III,
5 U.S.C. 5314, $209,600) on 10 U.S.C. 135(b)'s own sentence — "The Under
Secretary of Defense (Comptroller) is the agency Chief Financial Officer of
the Department of Defense for the purposes of chapter 9 of title 31." — read
from govinfo's 2024-edition rendering and re-found in the operative text by
both readers. The Schedule's own history agrees and the row's basis says so:
§5315's Amendments note records a "Chief Financial Officer, Department of
Defense" item inserted at Level IV by Pub. L. 101–576 and struck by Pub. L.
103–160, the same Act whose §5314 entry inserted "Comptroller of the
Department of Defense" at Level III, renamed by Pub. L. 103–337. "Chief
Financial Officer" names 81 nodes in this graph, so the row is keyed to the
Department's node alone, and the test asserts the gate refuses the same
record on every one of the other 80. The **Chief Information Officer** was
declined, not for want of a statute — 10 U.S.C. 142(a) was fetched and its
appointment sentence is in the operative text — but because §5315 prints the
title as "Chief Information Officer, Department of Defense (unless the
official designated as the Chief Information Officer of the Department of
Defense is an official listed under section 5312, 5313, or 5314 of this
title)", 213 characters with a 164-character proviso, and the title parser
refuses anything over 140 characters as a sentence rather than a title. The
proviso makes Level IV conditional on who is designated; reading it would be
reading law, and the parser was left as it is. The "Director of Legislative
Affairs" template was declined too: 10 U.S.C. 138(b)(3) names an Assistant
Secretary of Defense for Legislative Affairs, one of the Level IV counted
class, and treating the stamped Director as that office is the judgement the
stamp rule refuses; the Code also counts 20 Assistant Secretaries where
§138(a)(1) says 19. The Department's Under Secretaries, Deputy Under
Secretaries, Assistant Secretaries, DOT&E and CAPE directors are a curation
gap — §§5314–5315 print all of them and the Department's node carries none.

**Congressional staff: three officers priced, four shapes recorded, and
roughly 330 posts paid at a rate the appointing officer fixes under a
ceiling.** The cluster read GPO's 2024 edition of Title 2 and Title 31, the
two chambers' pay orders as the Code's notes reprint them, the House
Statement of Disbursements and the Senate's Report of the Secretary, and
sorted its ~400 unpriced posts the way this file sorts everything: a rate a
document states, a shape this project has not decided, a ceiling, or nothing.
Three posts are **tier-reference rows** in the shape the GAO's officers
already take, each sentence re-found in its section's operative text: the
**Architect of the Capitol** at Level II (2 U.S.C. 1802: "The compensation of
the Architect of the Capitol shall be at an annual rate which is equal to the
annual rate of basic pay for level II of the Executive Schedule"); the
**Chief of the Capitol Police** at Level II (2 U.S.C. 1902, keyed by id to the
graph's "Chief of Police"); and the **GAO's General Counsel** at Level IV
(31 U.S.C. 731(c), which names the Office and so answers the stamp problem
"General Counsel" otherwise has). Four more are a subtraction on a join —
the shape the Inspector General Act's "plus 3 percent" takes turned the other
way — and are **recorded as the next decision rather than built**: the AOC's
Inspector General at "$1,500 less than the annual rate of pay of the
Architect" (2 U.S.C. 1808(c)(3), $226,500); the Capitol Police's Inspector
General at "$1,000 less than the annual rate of pay in effect for the Chief"
(2 U.S.C. 1909(b)(4), $227,000); the GAO's Inspector General at "$5,000 less
than the annual rate of pay of the Comptroller General" (31 U.S.C. 705(b)(4),
$223,000); and the CBO's Director and Deputy Director, whose chain §19.10
left unread and the cluster closed — 2 U.S.C. 601(a)(5)(A) pays the Director
"the maximum rate of pay in effect under section 4575(f)", 4575(f)'s own
operative text names "the annual rate of basic pay in effect for level II of
the Executive Schedule", and (5)(B) pays the Deputy "$1,000 less than the
annual rate of pay received by the Director" — a two-statute chain to Level
II ($228,000) and a subtraction on it ($227,000). None of these five figures
is printed by any document; each would publish `documentsStatingTheFigure: 0`
with the arithmetic in the open, and the one thing they need is a
`minus_dollars` operation beside `plus_percent` and `percent_of`, which is a
validator and gate change the owner should see before it is made. Two more
are a different kind of document: the Order of the President pro tempore
(2 U.S.C. 4571 notes, March 25, 2024) makes the Secretary of the Senate, the
Sergeant at Arms and Doorkeeper and the Legislative Counsel "each … equal to
the annual rate for level II" and the Chaplain likewise, and the Order of the
Speaker (2 U.S.C. 4532 notes, January 17, 2025) puts the Clerk, the
Sergeant-at-Arms, the Chief Administrative Officer, the Chaplain, the General
Counsel, the Inspector General, the Director of Interparliamentary Affairs
and the Attending Physician at Level II. Both are law-like instruments issued
under a statute (2 U.S.C. 4575a(i), 4532), both are printed only in the
Code's Statutory Notes — beneath the cut this project uses to keep repealed
text out — and a later order of each exists that the OLRC host would not
serve. They reach four position nodes (the Secretary of the Senate, the
Senate's Sergeant at Arms, the Clerk and the CAO) and are declined for now
with the reason stated: an order is its own document class, and reading it
out of a notes block would be the one thing the operative-text rule exists
to forbid. The House disbursement statement corroborates by arithmetic the
document does not perform (the Clerk's $57,000 for a quarter is $228,000/4),
which is a reason to believe the orders and not a document stating a rate.
The remaining ~330 posts — Senators' and Members' office staff, committee
staff directors, the Secretary's and Sergeant at Arms' offices, the Clerk's
and CAO's directors, the CBO's staff and the GAO's analysts — are paid at
rates the appointing officer fixes within a floor and the Level II ceiling
(2 U.S.C. 4575(d)(2), (e)(3)(B), (f); the Speaker's order's $45,000–Level II
band; 2 U.S.C. 601(b) for the CBO; 31 U.S.C. 732(c) for the GAO's own band
table, which maps no title to a band), and both disbursement reports are
person-level amounts for a period, never a rate for a title — so none is
priced, each for a reason now recorded. The CRS Director's "greater of"
Level III or the certified SL maximum (2 U.S.C. 166(c)) is the Deputy
Librarian's declined shape and is left with it; the Senate Chaplain and the
House's Sergeant at Arms, Chaplain and Inspector General exist here only as
Office nodes, a curation gap the orders would reach if a post were curated.

**The judiciary: three rows, and a ceiling the compensation table's own page
resolves (2026-10-06).** The cluster's three strong leads all landed, each in
a shape this file already has. **The IRS Chief Counsel.** 5 U.S.C. 5316
prints "Chief Counsel for the Internal Revenue Service, Department of the
Treasury" at Level V, and no route could reach the node: the graph's name is
the bare "Chief Counsel", a title nine bureaus carry, and the scoped route
splits the Code's title at its comma into an office half no node is named by
and an organisation half ("Department of the Treasury") that is not the
node's parent. It is a reviewed row keyed to `exec-dept-treasury-irs-chief-
counsel` alone, with 26 U.S.C. 7803(b)(1) as the identifying statute —
"There shall be in the Department of the Treasury a Chief Counsel for the
Internal Revenue Service who shall be appointed by the President, by and
with the consent of the Senate." — the same section the Commissioner's row
already cites, a different sentence of it, quoted as the page prints it (the
Chief Counsel's appointment clause lacks the "advice and" the Commissioner's
carries, and a tidied copy would have been refused by both readers). $184,900,
`partial`, `proxy`. The Tax Court subtree draws the same office a second time
as "Chief Counsel — IRS (opposing)", the post where it litigates; it is
reached by no route and the gate refuses the record moved onto it, onto the
eight other Chief Counsels and onto the Commissioner; a test moves
7803(b)(1)'s sentence beneath the Editorial Notes and the Chief Counsel's row
falls while the Commissioner's stands. Level V prices eight posts now.
**The Chair of the U.S. Sentencing Commission.** 28 U.S.C. 992(c), fetched
from GPO's 2024 edition through govinfo's link service, pays "The Chair and
Vice Chairs of the Commission … at the annual rate at which judges of the
United States courts of appeals are compensated", so `jud-support-ussc-chair-
ussc` is a derived office row in the Administrative Office Director's shape
at the circuit-judge tier — $264,900, two documents, 80%, neither stating
the figure. The CAAF's chief judge prices the identical figure from 10 U.S.C.
942(d), so the gate's id-keyed mirror is what tells a record moved between
the two apart, and a test moves it both ways. The Commission's `Commissioner
(×6)` bench is deliberately not priced and recorded in `derived_pay.
NOT_PRICED`: the same subsection pays the voting members other than the
Chair and Vice Chairs "at the daily rate at which judges of the United
States courts of appeals are compensated", so the bench bundles three Vice
Chairs at the annual rate with members paid by the day, and one annual
figure would be false of some of its holders — the senior-judge refusal's
shape. The three Vice Chairs have no nodes and nothing was invented for
them. A link-service fetch records the link as `url` and the dated granule as
`final_url`, so `statute_publisher` now reads the edition off either and a
record names "U.S. Government Publishing Office, 2024 edition of the United
States Code" rather than "an edition". **The magistrate judges.** §19.13 had
refused both benches on a true reading of 28 U.S.C. 634(a): full-time
magistrate judges' salaries are "fixed by the conference … up to an annual
rate equal to 92 percent of the salary of a judge of the district court", a
ceiling and not a rate, which is why the bankruptcy benches were priced and
these were not. The committed Judicial Compensation page — the document the
tier is already read from — prints beneath its table, in its Explanatory
Notes: "By statute, the salary of a bankruptcy or magistrate judge is equal
to 92 percent of the salary of a district judge. 28 U.S.C. §§ 153, 634(a)."
That is the Administrative Office stating what the Judicial Conference fixed
under the ceiling, checked against the bytes (exactly one occurrence, in no
row the table parser carries). So `jud-district-sdny-magistrate-judge-13` and
`jud-district-structure-magistrate-judge-varies` are percent-of rows in the
bankruptcy shape — $249,900 × 92% = $229,908, arithmetic in the open, two
documents, 80%, none stating the figure — with one thing more: the provision
carries the page's sentence as `basisQuote`, `build_records` re-finds it in
the page's own text on every run and refuses the row when it is gone, the
block publishes it as `ceilingBasis` with a reading in words (a ceiling, the
full-time salary, part-time magistrates at $100 to half the maximum), the
derivation carries it, and the gate mirrors it by node id, re-reads the
committed page's bytes, and refuses a `ceilingBasis` on any row whose statute
states the rate itself. The distinction the tests pinned is kept — "up to" IS
in §634 and NOT in §153 — and what changed is a second sentence of a
document already in hand resolving it; the owner, who decided the bankruptcy
shape and left the magistrates refused, may reverse this one. The multi-post
sweep keeps both with `holders`; derived rows **15 → 18**. The cluster's
other leads are recorded and not built: the CFC's chief special master at
Level IV (42 U.S.C. 300aa-12(c)(5)) needs a node the graph lacks; the SSA's
administrative law judges are bounded by OPM's 2026-ALJ table and placed by
5 CFR 930.205, a system and not a rate; law clerks sit at JSP-11 to JSP-14 by
OSCAR's own statement and court unit executives on a JSP table to grade 18,
but no official document states which grade a given clerk or executive holds;
the circuit executive (28 U.S.C. 332(f)(1)), the Federal Public Defender (18
U.S.C. 3006A(g)(2)(A), chained to the U.S. Attorney's own ceiling under 28
U.S.C. 548), the Sentencing Commission's Staff Director (§995(a)(2)) and the
FJC's professional staff (§625(b)) are ceilings; the Supreme Court's officers
are paid as the Court fixes (28 U.S.C. 671–675); the CFC's senior judges are
topped up only while recalled (28 U.S.C. 797(d)); and the court reporters'
and Court Personnel System tables print bands no document ties a post to.

**The remaining departments: 1,259 unpriced posts under twelve departments,
and where the Code reaches.** The cluster read the five committed Executive
Schedule sections against every title under HHS, USDA, Commerce, Education,
Energy, the Interior, Labor, State, Transportation, the Treasury, the VA and
HUD, fetched each identifying section from GPO's 2024-edition rendering on
govinfo (`uscode.house.gov` still under maintenance; `www.state.gov` answers
`robots.txt` and its homepage with a 659,508-byte 403 page, so State's own
Senior Foreign Service table cannot be read from here), and read the
committed current PLUM export by its `READ_COLUMNS` only. 432 of the 1,259
are the VA Medical Centers' service chiefs `va_title38_pay.py` refuses by
design and 51 are the Energy Department's contractor-laboratory posts;
neither was re-adjudicated. What the Code sets or identifies, in shapes this
repository already has: **four Transportation reviewed rows** the Schedule
already prints — the NHTSA Administrator (III) and Deputy Administrator (V)
through 49 U.S.C. 105(b), the FMCSA Deputy Administrator (V) through 49
U.S.C. 113(d), and the Deputy Federal Highway Administrator (IV) through the
committed 49 U.S.C. 104(b)(2); the FTA's Deputy Administrator is printed by
§5316 but 49 U.S.C. 107 names no deputy, so it stays speculative. **The NNSA
Administrator**: 42 U.S.C. 7132(c) pays the Under Secretary for Nuclear
Security at Level III and (c)(3), with 50 U.S.C. 2402(a)(2), makes that
officer the Administrator — the tier-reference shape with an identification
sentence. **The IRS Chief Counsel**: §5316 prints "Chief Counsel for the
Internal Revenue Service, Department of the Treasury" at Level V and 26
U.S.C. 7803(b)(1) creates the office — the judiciary cluster found the same
lead and it is recorded with that cluster's rows. **Reorganization Plans are
a document kind this repository has not read**, and the cluster's three
strongest Commerce leads rest on them: Reorganization Plan No. 4 of 1970
sets NOAA's Administrator at Level III, its Deputy Administrator at Level IV
and its Chief Scientist at Level V, and Reorganization Plan No. 3 of 1979
sets a Deputy Secretary of Commerce at Level II — the office §19.7 and §8
recorded as absent from §5313, which it is; the Plan sets its pay by
reference — and the Under Secretary for International Trade at Level III.
The Plans sit in Title 5's Appendix on govinfo, their pages carry no "§N."
heading for `operative_text` to anchor on, and §19.14 already declined the
SEC's Chairman and the EPA's Administrator for the same reason; they are
recorded here as one decision — a reader for the Appendix — covering six
posts rather than taken one at a time. **Listing leads that need a name, not
a matcher**: the export files the FDA's head as "COMMISSIONER OF FOOD AND
DRUGS" at EX IV (21 U.S.C. 393(d)(1) identifies the office), the Mint's
Director at SL $176,300 and its Deputy at ES $226,026 (31 U.S.C. 304(b)(1)),
the United States Representative to the United Nations at EX III under the
graph's stamped "Assistant Secretary, U.S. Mission to the United Nations",
the Chief of Protocol at EX IV under the same stamp, the NNSA's two Deputy
Administrators at EX IV, and some twenty SES rows for the Office of Science's
associate directors, OFAC, the BLS, CMS, Ginnie Mae, the Fiscal Service, the
BEP, BOEM and PIH — each a rename or alias candidate, each declined until a
document supplies the graph's title. **Ceilings and systems, not rates,**
each declined with its section: every chief of mission at "one of Levels
II–V as the President determines" (22 U.S.C. 3961(a), a band of four levels
no field here carries); the Senior Foreign Service within the SES range (22
U.S.C. 3962(a)); the National Taxpayer Advocate and the Chief of Appeals at
the SES maximum, which OPM's committed table prints twice (26 U.S.C. 7803);
USPTO's Commissioners at the SES maximum and its trademark judges at Level
III (35 U.S.C. 3(b)); the FAA's Chief Operating Officer at 3 U.S.C. 102's
$400,000 (49 U.S.C. 106(r)(2)(A)); Federal Student Aid's Chief Operating
Officer at the SES maximum (20 U.S.C. 1018(d)(5)(A)); the Board of Veterans'
Appeals' Vice Chairman on 5 U.S.C. 5372's rates unless SES (38 U.S.C.
7101(a)(4)); and the OCC's pay fixed outside Title 5 (12 U.S.C. 482; the
export prints its Senior Deputy Comptroller and Chief Counsel at OT
$331,800). The VHA's "Principal Deputy Under Secretary for Health" against
38 U.S.C. 7306(a)(1)'s "Deputy Under Secretary for Health", which Table 4
Tier 1 lists, is the reviewed identification §19.19 already left to the
owner. Declined with reasons: the fifteen departments' stamped ten-title
office (no statute names any of them), the DOL, DOI and State "General
Counsel" stamps (the Code prints Solicitors and a Legal Adviser instead), two
IRS Deputy Commissioner nodes where the Code places one office, SAMHSA's
Administrator (the same office as its Assistant Secretary), the NNSA and EM
site managers, every bureau-level GS and SES post no document names, and the
embassy section chiefs and attachés of the Foreign Service system.

**The batch's running total, restated (2026-10-06, morning).** Pay claims
**1,158 → 1,193** of 4,591 positions; unpriced **3,433 → 3,398** (no document
names the title **2,663 → 2,630**; a multiplicity no office-rate claim reaches
**752 → 750**; listed with no rate 18); reviewed Schedule rows **91 → 97**,
Schedule-priced posts **230 → 236**; tier-reference rows **19 → 23**, records
**46 → 50**, published **41 → 45**; derived rows **15 → 18**; the new
`positionMilitaryPay` field on **22** posts; nodes with an official source
1,039, `verified` 538, `partial` 454. `docs/COST_COVERAGE.md` puts the 5,510
nodes in their classes: 160 measured, 693 estimates (240 committees, 42 beside
a sourced non-cost figure, 411 bare), 1,193 salaries, 3,398 unpriced posts by
reason, 30 beneath a negative pool, 36 replaced units.

**Still running when this paragraph was written (2026-10-06, morning):** the
Code title scan and the Treasury alias candidates. Their results are appended
below as they land.