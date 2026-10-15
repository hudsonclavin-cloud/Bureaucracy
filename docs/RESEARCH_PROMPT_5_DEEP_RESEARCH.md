# Research prompt 5 — one deep-research run on four questions

Written by hand on 2026-10-15 for Perplexity Deep Research or ChatGPT Deep
Research. Copy everything below the rule into the research tool as one prompt.
Unlike packs 3 and 4 (`report_unpriced_positions.py`,
`report_research_prompts.py`), this one is not generated and is not pinned by a
test; the counts in it are as of the published graph of 2026-10-14 and will
drift. Regenerate the counts from `output/graph.json` before re-running it.

What the project does with the answer: a research report cannot change a
figure on the site. Every number this site publishes is read from a committed
official document by code the release gate re-checks, so the useful output of
this run is a list of DOCUMENTS — publisher, URL, what the document states and
in what unit and period, and the key that joins it to a unit or a post — plus
design recommendations the frontend can act on. A figure reported without the
document that prints it is unusable and will be discarded.

---

## The prompt

You are researching for an open-source project that publishes a browsable 3D
organisational graph of the United States federal government, from the
Constitution down to individual offices and posts, with a cost on every node
and an honest statement of how that cost was obtained. The code is public
(github.com/hudsonclavin-cloud/Bureaucracy). Its standing rule is that the data
and the interface may never claim more than the evidence supports: a figure is
published only when a committed official document prints it (or when it is
arithmetic over printed figures, said in so many words), and a unit or post is
called verified only when an official document names it.

I need four things from you, each in its own section, and the deliverable for
all four is the same shape: **documents, not figures**. For each source you
propose, give the publisher, the exact URL (and the parent page it is linked
from), what the document states and does not state, the unit and the period of
every figure in it, the file format, how it is updated and how often, whether
the host publishes a `robots.txt` that permits crawling, and the join key that
would tie a row of it to a unit of government or a post (a name, an agency
code, a Treasury Account Symbol, a CGAC code, a pay plan and grade, a statutory
citation). Where you know a figure, you may quote it as an illustration, but the
document is the answer. Salary aggregators (Glassdoor, Payscale, FederalPay,
OpenPayrolls, Indeed) and news articles are not sources for this project; name
them only to say what official document they themselves cite.

### Where the project stands (so you do not re-derive what is already done)

- 5,510 nodes: 919 organisations and 4,591 posts. Three branches under the
  Constitution; the Executive's independent establishments and regulatory
  commissions are drawn as two sectors of their own.
- **Costs.** 172 nodes carry a measured cost: the root's anchor (total federal
  outlays, fiscal year to date) and the lines of the Monthly Treasury Statement
  Table 5 (FiscalData API, `api.fiscaldata.treasury.gov`) that name a unit,
  including nine sub-agencies summed from the lines beneath a header the
  statement totals nowhere, and the statement's receipts lines carried as
  explicit negative children. 681 organisations carry an apportioned estimate
  (a share of the nearest measured ancestor, split among siblings by curated
  budget figures, OPM FedScope headcount, committee disbursements or subtree
  size, in that order of evidence), which the site withholds by default. 4,657
  nodes publish no cost figure at all: every post (a post is not a budget
  unit), everything beneath a unit the government has replaced, and units
  beneath a Treasury pool that nets below zero. Beside the cost, and never in
  it, the project already reads: USAspending File A gross outlays per toptier
  agency and GTAS bureau (43 organisations), File B obligations by object class
  with staff pay (classes 11.x and 12.x) summed (86 organisations), OMB's
  Public Budget Database FY2025 actuals summed per agency and bureau (177), the
  Treasury's audited Statement of Net Cost (34), the House Statement of
  Disbursements and the Report of the Secretary of the Senate for 40 of 41
  chamber committees, and OPM FedScope average salary × headcount as civilian
  payroll (178).
- **Verification.** 1,066 of 5,510 nodes carry an official source. Of the
  organisations, 386 are verified (two or more official documents), 227 partial
  (one), 306 unverified; 259 carry no source at all. Of the posts, 164 verified,
  242 partial, 4,185 with no source. The routes already built: the unit's own
  official page labelling its name (heading, link or list item — never a
  substring of prose), the parent's page listing it (placement), the Federal
  Register agency directory, the Senate's and the House Clerk's committee lists,
  the United States Government Manual (govinfo, 2025-12-31 edition: entry
  names, parent entries, leadership tables for posts, mission statements), the
  Federal Register's signature blocks (the signing official's stated title),
  OPM's Plum Book archive and current export, usa.gov's A-to-Z index (used only
  to find URLs). 358 organisations have no candidate page at all. The verifier
  obeys robots.txt and refuses a host whose robots.txt answers 401/403; 821
  organisations and posts sit on such hosts, the largest being
  www.whitehouse.gov and www.state.gov, with justice.gov, defense.gov, hud.gov,
  ssa.gov, dfas.mil and gao.gov behind them (Akamai/Cloudflare challenges).
- **Pay.** 1,258 of 4,591 posts carry a pay claim from an official document:
  5 U.S.C. §§5312–5316 (the Executive Schedule) joined to OPM Salary Table
  2026-EX, including reviewed identifications through an office's own organic
  statute and the Code's counted classes; statutes that set pay by reference to
  a level (31 U.S.C. 703, the Inspector General Act 5 U.S.C. 403(e), and others)
  and by parity to a judicial tier (26 U.S.C. 7443, 28 U.S.C. 172, 153, 603,
  626; 10 U.S.C. 942; 38 U.S.C. 7253); uscourts.gov's Judicial Compensation
  table; senate.gov's salary table; Schedules 5–8 of the annual pay-adjustment
  executive order as reprinted in the note to 5 U.S.C. 5332 (Schedule 8 is the
  uniformed services' monthly basic pay); 3 U.S.C. 102; the White House Office's
  Annual Report to Congress on White House Staff; OPM's Plum Book rates and
  levels; OPM's GS, SES and SL/ST tables as ranges; the VA's Title 38 pay
  tables; the DOJ AD pay chart; USAJOBS announcements as a listing of a post's
  grade; Reorganization Plans and the chambers' pay orders in the Code's notes.
  **3,333 posts carry none**: 2,158 under a title no document in hand names
  (the largest families are the VA medical centres' service chiefs, 296
  `Chief — <service>` nodes; `Chief Financial Officer` 60; `Chief of Staff` 59;
  `General Counsel` 53; `Inspector General` 49 — mostly at independent agencies
  and Defense agencies where the title is a curated template; `Program
  Director` 35; the Smithsonian's 21 museums × curatorial and facilities
  titles; the national laboratories' deputies); 611 nodes that stand for many
  holders of one title (`Physician (×multiple)`) where only a claim that holds
  for every holder may be published; 432 beneath the VA's eighteen former
  VISNs; 112 at DOE contractor-operated laboratories, which the project now
  marks as not on a federal pay schedule; 20 listed by OPM with no rate.

### Section 1 — Presentation: the ideal way to show this data, and what to show

The interface is a Three.js scene: nodes as discs, hierarchy edges, five
"lenses" (Structure, Money, Evidence, Pay, Whole) that recolour every node from
one published field, a directory view, an inspector panel that prints every
claim with its source and its caveat, and a "Whole" view that lays all 5,510
nodes on one globe (an equal-area treemap by leaf count, the crust in relief by
each branch's share). Node size is uniform by default because the one obvious
encoding, subtree size, measures how deeply the graph was curated and not how
big the unit is; cost cannot be the size because 85% of nodes have none.

Research and recommend, with citations to the visualisation literature and to
comparable published projects (OpenSpending, USAFacts, the Treasury's own
"Your Guide to America's Finances", the UK Treasury's "whole of government
accounts" visualisations, the Federal Register's agency map, Nathan Yau's and
the Financial Times' hierarchy work, Ben Shneiderman's treemap work, Tamara
Munzner's and Jeffrey Heer's writing on hierarchy and uncertainty encoding):

1. How to encode an *apportioned estimate* against a *measured figure* against
   *no figure* so that a reader cannot mistake one for another at a glance, in
   colour, in shape and in text; what the evidence says about hollow vs filled
   marks, hatching, desaturation and "≈" prefixes.
2. How to show a hierarchy of 5,500 nodes where depth of curation is uneven
   (the Department of Defense is drawn to the office, most bureaus as a
   six-post sketch) without the drawing implying that the deeper parts are
   bigger: which encodings make curation depth read as what it is.
3. Whether a 3D node-link view, a treemap, a sunburst, an icicle, a circle
   packing or a hyperbolic/radial tree better serves (a) a first-time viewer in
   a classroom, (b) a reader tracing one office's lineage, (c) a reader
   comparing the branches' money. Say which to use for which task and why.
4. How to present money in several bases at once (net outlays FYTD, gross
   outlays, obligations by object class, OMB completed-year actuals, audited
   net cost, disbursements, salaries) on one node without a reader adding them
   up or taking the wrong one as "the cost"; the best practice for labelling
   basis and period.
5. What a "verification" badge should say when the evidence is one document vs
   two, when it is an alias match, when a page was unreachable rather than
   silent, and when a negative was established by a complete official list.
6. Which of the figures the project already holds should be the *headline* for
   a unit with no measured cost, and in what order, with the argument for the
   order.
7. The two or three things a classroom presentation of this graph should show
   first, and the common misreadings to pre-empt (e.g. "the Executive Branch
   costs nothing" because its figure is a withheld remainder while the two
   small branches carry measured section totals; "the Mint has negative
   cost"; "the Postal Service is tiny" because it nets $2bn).

### Section 2 — Cash flow: where the money of every branch is published

For each of the three branches, and for the Executive's independent
establishments and regulatory commissions, identify every official document
that states money flowing in or out, at the finest unit it reaches, and say
which units it reaches that the Monthly Treasury Statement's Table 5 does not.
Specifically:

- **Treasury / FiscalData.** The MTS Tables 4, 5, 6 and 9; the Daily Treasury
  Statement; the Combined Statement of Receipts, Outlays and Balances (the
  "Combined Statement", with its account-level outlays); the GTAS SF 133
  Report on Budget Execution; the Financial Report of the U.S. Government. For
  each: the API endpoint or file, the unit (dollars, thousands, millions), the
  period, whether it is net or gross, and the identifier it keys on (Treasury
  Account Symbol, agency code, bureau code).
- **USAspending / DATA Act.** Files A, B and C at TAS level; the account-level
  download; which identifiers (TAS, CGAC, toptier/subtier codes, federal
  account) reach bureaus the API's `sub_components` list does not, and how a
  TAS maps to an organisational unit (the Treasury's FAST Book and the
  "Agency Identifier" list).
- **OMB.** The Public Budget Database (already read), the Budget Appendix
  (account-level, with obligations by object class per account), the
  Analytical Perspectives "Federal Budget by Agency and Account" tables, the
  SF 133 reports, apportionments (apportionment data on
  apportionment-public.max.gov or its successor).
- **The Legislative Branch.** The House's Statement of Disbursements (the 26
  MB detail CSV and the summary CSV), the Report of the Secretary of the
  Senate (Parts I and II), the legislative branch appropriations acts' account
  structures, GAO's, CBO's, the Library of Congress's, GPO's, the Architect of
  the Capitol's and the Capitol Police's own financial statements or budget
  justifications: say which document reaches the Members' offices, the
  committees, the officers and the support agencies, and at what period.
- **The Judicial Branch.** The Administrative Office's "Judiciary Budget
  Request" / congressional budget justification, the "Judicial Business" and
  "Federal Court Management Statistics" series, the AO's annual report, the
  Judicial Conference's reports, the Defender Services and Court Security
  accounts, and anything that states spending per circuit or per district
  court. Say what exists at the court level and what does not.
- **Independent establishments and government corporations.** Where the
  self-funded and off-budget bodies publish their own cash flow: the Postal
  Service (10-K, Form 10-Q, the Postal Regulatory Commission's financial
  reports), the Federal Reserve (combined financial statements; the Board's
  budget review), the FDIC, the TVA, the FHFA, the CFPB, Amtrak, the Ex-Im
  Bank, the PBGC, the NCUA, the SEC, the FCC, the Smithsonian; and the agency
  financial reports (AFRs / PARs) every CFO Act agency publishes, with their
  Statements of Net Cost by program or responsibility segment.
- **Intra-governmental flows.** Where transfers between units are stated
  (the MTS's intrabudgetary transactions, the Combined Statement, the
  Treasury's intragovernmental reporting), so that a "cash flow between
  branches and agencies" view could be drawn from a document rather than
  inferred.

For every document, state the join key to the project's units and the units
it cannot reach. Rank the documents by how many of the 681 units that today
carry only an estimate each would reach with a figure of its own, and by how
close its basis and period are to the Monthly Treasury Statement's net
outlays, fiscal year to date.

### Section 3 — Verification: how to get an official document naming every unverified node

Propose routes, with the document and the join key, for the following, in
order of how many nodes each route would move:

1. **The 259 organisations with no source and the 358 with no candidate page.**
   Official directories and lists beyond the ones already read: the
   Federal Register's agency list (read), SAM.gov's Federal Hierarchy (needs an
   API key — say how one is obtained and what the hierarchy's fields are),
   the Treasury's FAST Book and Agency Identifier list, OMB's MAX Federal
   Community, the Government Manual (read), the Plum Book (read), GSA's
   Federal Agency Directory and the A–Z index on usa.gov (read for URLs),
   OPM's Fed Scope agency/sub-agency list (read for headcounts, not names),
   the Federal Register's "Agency Acronyms" list, the DATA Act's agency codes
   (CGAC) list, congressional committee rosters, the Judiciary's court
   locator, the Code of Federal Regulations' organisation parts (each agency's
   Part 1 or "Organization" subpart in Title 5 and in its own title), the
   Government Manual's predecessor lists, and the statutes that create units
   (the United States Code's "Establishment" sections). For each: does it
   state a parent (so it can support a placement claim), and is it complete
   (so absence is evidence)?
2. **Hosts that refuse the crawler.** www.whitehouse.gov, www.state.gov,
   www.justice.gov, www.defense.gov, www.hud.gov, www.ssa.gov, www.dfas.mil,
   www.gao.gov and others answer robots.txt or the page with 401/403 or a
   bot challenge. For the units on them, name a second official publisher of
   the same organisational fact: the Government Manual, the Federal Register
   (agency pages at federalregister.gov/agencies/<slug>), the CFR, govinfo's
   renderings, the agency's budget justification on govinfo or the
   appropriations committees' sites, the Plum Book, GAO reports that print an
   agency's organisation chart, the Congressional Directory (govinfo,
   CDIR-<year>), and the Official Congressional Directory's executive-branch
   section, which lists officers by title.
3. **The 4,185 posts with no source.** Documents that name posts by title under
   their organisation: the Congressional Directory's executive section (posts
   and incumbents — say which columns name only the title), the Plum Book (read),
   the Government Manual's leadership tables (read), Federal Register signature
   blocks (read), agency organisation charts published as official documents
   (budget justifications' org charts, AFR org charts), the Senior Executive
   Service position listings OPM publishes, USAJOBS announcements (read for
   grades), agency delegations of authority and orders published in the Federal
   Register (which name offices), the CFR's organisation subparts (which name
   offices and sometimes posts), inspectors general's semiannual reports (which
   name the IG and senior staff titles), and the Judiciary's court directories.
   For each, say whether it names posts generically (`General Counsel`) or
   scoped to the organisation, since the project refuses a bare title matched
   in a site's shared footer.
4. **Placement.** Which documents state the parent of a unit explicitly, so a
   parent→child edge can be evidenced without inferring it: the Government
   Manual (read), the Federal Register directory (read), the CFR's organisation
   parts, SAM.gov's hierarchy, the Treasury's FAST Book, OMB's agency/bureau
   codes, the appropriations acts' account structure.

Say for each proposed document whether the publisher's host allows crawling
and what access it requires, and give the URL of a sample page or file so the
project can commit a fixture.

### Section 4 — The cost of every position: a pay document for every unpriced post

The project prices a post only when an official document states its pay, a
range for its pay plan and grade, or a statute that sets it by reference, and
it must know WHICH pay system governs the post before it can join a table.
For the 3,333 unpriced posts, grouped as follows, identify the pay system and
the document that publishes its rates, with the join key (title → pay plan and
grade, or statute → level), and say what the document does and does not state:

- **VA medical-centre service chiefs** (296 `Chief — Medicine Service`,
  `Chief — Surgery Service`, `Chief — Finance`, `Chief — Human Resources`, …
  across eighteen template centres) and the other VA clinical posts (Physician,
  Nurse, Clinical Pharmacist, Social Worker, VA Police Chief, Canteen Chief,
  Associate Director for Patient Care Services): which of Title 38 (38 U.S.C.
  7401–7431, the VA's annual pay tables for physicians, dentists, podiatrists,
  nurses by locality), Title 5 GS/GM, the Hybrid Title 38 (7401(3)), the VA
  Police's pay plan, and the Canteen Service (38 U.S.C. 7802, the VCS's own
  pay schedules) governs each; where the national ranges are published; and
  whether any VA document names a service chief's grade.
- **The templated administrative posts at agencies without a statute naming
  them** — `Chief Financial Officer` (60), `Chief of Staff` (59), `General
  Counsel` (53), `Inspector General` (49, at designated federal entities and
  Defense agencies), `Chief Information Officer` (28), `Deputy Director / Vice
  Chair` (19), `Director of Public Affairs` (17): the statutes that place a
  CFO (31 U.S.C. 901), a CIO (44 U.S.C. 3506) or an IG of a designated federal
  entity (5 U.S.C. 415) and whether any states a pay level; OPM's SES
  structure as the fallback; the current Plum Book rows that print a rate for
  them under sub-organisations named "Office of the General Counsel" and the
  like; and the Defense agencies' own directives naming the grade of their
  heads (DoD Directives on the DIA, NSA, NGA, NRO, DARPA, DLA directors).
- **The Smithsonian** (21 museums × Chief Curator, Head of Education, Head of
  Collections Management, Head of Facilities, Curator, Exhibit Specialist):
  federal (GS) versus trust-fund employment, the Smithsonian's own pay
  schedules, and which document distinguishes the two.
- **The national laboratories** (Deputy Laboratory Director and the other
  templated titles at NETL, the one government-operated laboratory): the
  federal pay plan governing NETL's leadership.
- **Program Director / Program Officer** (66, mostly NSF, NIH and foundations):
  NSF's AD pay plan (the "Administratively Determined" bands NSF publishes in
  its vacancy announcements), NIH's Title 42 (42 U.S.C. 209) pay, the
  foundations' own plans.
- **Uniformed posts** whose grade no statute fixes (the combatant commanders
  designated under 10 U.S.C. 601, the service component commanders, the NGA
  and NRO directors when held by an officer): whether any DoD publication
  states the grade of the incumbent post as a post (DoD Instruction 1320.xx,
  the General and Flag Officer Management Office's authorisations, the
  Joint Staff's J-code billets), without naming the officer.
- **Posts standing for many holders** (611): for each family, a document
  stating a figure or a range that holds for every holder by its own terms
  (a statutory rate "for each", a single pay band, a locality table), since
  an incumbency figure can never be published on such a node.
- **The legislative support staff** (the 49 posts beneath the Secretary of
  the Senate, the Senate Sergeant at Arms, the Clerk and the CAO reached only
  by a pay ceiling in the chambers' orders): the Senate's and House's
  published pay orders, the Statement of Disbursements' salary column (which
  names the person, so say whether a title-level figure can be read without
  the name), and the Legislative Branch's "Pay Adjustment" notices.
- **The GAO's team posts** (32) behind www.gao.gov's 403: the GAO pay bands
  (31 U.S.C. 732–733) and any publisher of GAO's band tables other than
  gao.gov (govinfo, the Federal Register, a budget justification).
- **General Schedule locality**: the project publishes GS ranges before
  locality only. Identify OPM's locality tables' structure (the 2026 locality
  pay areas, the "Rest of U.S." table) and the document that ties a facility
  to its locality area (OPM's locality area definitions, 5 CFR part 531
  subpart F), so that a facility-scoped post could carry its locality range.

For every pay system name the 2026 (or latest) table's exact URL on an
official host, its effective date, whether it prints annual or monthly or
hourly figures and whether the currency mark is on every figure or once at
the column head (the project's scale rules depend on it), and whether the
host allows crawling. Where a title is paid under no federal schedule
(contractors, trust funds, the Postal Service's bargaining units, the Federal
Reserve's own plan, the TVA's), say so with the document that establishes it.

### Output format

Four sections as numbered above. Within each, a table with the columns:
Document · Publisher and URL · What it states (unit, period, basis) · What it
does not state · Join key · Units or posts it would reach (estimate the count
against the groups named above) · Crawlable (robots.txt) · Notes. After each
table, a ranked recommendation of the first three documents to commit, with
the reason. Cite every claim about a document to the document itself or to
the publisher's own description of it. Do not invent a URL: if you cannot
confirm the exact path, give the parent page you did confirm and say so. Where
two publishers print the same table (OPM's HTML and PDF; the OLRC's and GPO's
renderings of a Code section), name both, since the project prefers a second
rendering as corroboration.
