# Research prompt 5 — four deep-research runs, with the node lists attached

Written by hand on 2026-10-15 for Perplexity Deep Research or ChatGPT Deep
Research. Not generated and not pinned by a test; the counts below are as of
the published graph of 2026-10-14.

**Why it is four prompts with attachments.** The first version was one prompt
with no attachments, and asked the tool to rank documents by how many of this
graph's 681 estimated units each would reach. Perplexity declined it, and was
right to: nobody can say what a document reaches without the list of what is
unreached, and a count made up without that list breaks the rule this project
exists to keep. So:

1. Run `python scripts/export_research_pack.py`. It writes the node lists to
   `output/research_pack/` (gitignored; regenerate it, never commit it).
2. Run each prompt below as its **own** research session, attaching the files
   it names plus the pack's `README.md`. Each is self-contained.
3. Bring the reports back. A report cannot change a figure on the site. What
   it can do is name documents, which this repository then fetches, commits
   as fixtures and reads with code the release gate re-checks.

The shared preamble goes at the top of every prompt; the four sections follow.

---

## Shared preamble (paste at the top of each prompt)

> You are researching for an open-source project, github.com/hudsonclavin-cloud/Bureaucracy:
> a browsable 3D organisational graph of the United States federal government,
> from the Constitution down to offices and posts. Its one rule: the site may
> never claim more than an official document supports. A figure is published
> only when a committed official document prints it, or as arithmetic over
> printed figures that says so. A unit or post is called verified only when
> an official document names it.
>
> The attached CSVs are this graph's own node lists (the pack's README
> explains every column). `id` is a stable key. Answer by id wherever you can.
>
> **What I need is documents, not figures.** For every source you propose,
> give: the publisher; the exact URL, plus the official page it is linked
> from; what the document states and what it does not; the unit and period of
> every figure in it (annual or monthly, dollars or thousands, fiscal year or
> calendar, gross or net); the file format; how often it is updated; whether
> the host's robots.txt allows crawling; and the **join key** that ties one of
> its rows to a node (a name, an agency code, a Treasury Account Symbol, a
> CGAC code, a pay plan and grade, a statutory citation).
>
> **Rules for the answer:**
> - Do not invent a URL. If you could not confirm an exact path, give the
>   parent page you did confirm and say so.
> - Salary aggregators (FederalPay, OpenPayrolls, Glassdoor, Payscale) and
>   news articles are not sources. Name them only to say which official
>   document they cite.
> - Where you match a document to node ids, label each match **certain**
>   (the document prints the node's name or its unique code), **likely**
>   (one reasonable reading), or **speculative**. Count only the matches you
>   actually made. Never estimate a coverage count.
> - Where the curated title is a template no agency uses (many are), say so,
>   and name the real post if a document does.
> - Where two publishers print the same table (OPM's HTML and PDF; the
>   OLRC's and GPO's renderings of a Code section), name both.

---

## Prompt A — Cash flow: where each branch's money is published

**Attach:** `README.md`, `estimated_units.csv`, `organisations.csv`.

> **What the project already reads (do not re-propose; propose what goes
> further):** the Monthly Treasury Statement Table 5 via the FiscalData API
> (the measured cost of 172 nodes, net outlays fiscal year to date);
> USAspending File A gross outlays for toptier agencies and GTAS bureaus
> (43 organisations); File B obligations by object class (86); OMB's Public
> Budget Database FY2025 actuals summed per agency and bureau (177); the
> Treasury's audited Statement of Net Cost (34); the House Statement of
> Disbursements summary CSV and the Report of the Secretary of the Senate
> Part II, for 40 of 41 chamber committees; OPM FedScope average salary ×
> headcount (178).
>
> `estimated_units.csv` lists the 681 organisations whose only cost figure is
> the project's own apportioned share of a measured ancestor. The
> `share_basis` column says how weak each share is (`subtree_weight` is the
> weakest: the count of nodes beneath it). These are the units to reach.
>
> 1. For each branch, and for the Executive's independent establishments and
>    regulatory commissions, find every official document that states money
>    for a unit finer than Table 5 does. Cover at least: the Combined
>    Statement of Receipts, Outlays and Balances (account level); the GTAS
>    SF 133 Report on Budget Execution; the Treasury Account Symbol to
>    organisation crosswalk (the FAST Book, the Agency Identifier list);
>    USAspending's account-level File A/B downloads; the OMB Budget Appendix;
>    agency Financial Reports' Statements of Net Cost by responsibility
>    segment; the Legislative Branch's own budget justifications (GAO, CBO,
>    the Library of Congress, GPO, the Architect of the Capitol, the Capitol
>    Police); the House Statement of Disbursements' detail; the Senate Report
>    Part I; the Judiciary's congressional budget justification and any
>    document that states spending per circuit or district court; the
>    self-funded and off-budget bodies' own financial statements (USPS, the
>    Federal Reserve Board's budget, FDIC, TVA, FHFA, CFPB, Amtrak, Ex-Im, PBGC,
>    NCUA, SEC, FCC, the Smithsonian).
> 2. For each document, go through `estimated_units.csv` and list the ids it
>    would give a figure of their own, with the match label and the join key.
>    Where it reaches a unit only as part of a larger account, say so.
> 3. Where intra-governmental transfers between branches or agencies are
>    printed (intrabudgetary transactions; the Combined Statement), say where,
>    so that a "money between units" view could be drawn from a document
>    rather than inferred.
> 4. Rank your documents first by **matched ids** (your count, not an
>    estimate), then by how close each figure's basis and period are to net
>    outlays, fiscal year to date. Recommend the first three to commit.

---

## Prompt B — Verification: an official document naming every unsourced unit

**Attach:** `README.md`, `orgs_without_source.csv`, `orgs_without_page.csv`,
`unread_hosts.csv`, `organisations.csv`.

> **What the project already reads:** each unit's own official page, checked
> for its name as a heading, link or list item (never a substring of prose);
> the parent's page listing it (evidence for the edge); the Federal Register
> agency directory; the Senate's and the House Clerk's committee lists; the
> United States Government Manual, 2025-12-31 edition (entry names, parent
> entries, leadership tables); Federal Register signature blocks; OPM's Plum
> Book (archive and current export); usa.gov's A-to-Z index, used only to
> find URLs. The verifier obeys robots.txt and refuses a host whose
> robots.txt answers 401/403.
>
> `orgs_without_source.csv` (223 live organisations) carries no official
> source of any kind. `orgs_without_page.csv` (321) has no candidate page to
> fetch. `unread_hosts.csv` lists the hosts that refused the crawler or
> served an unreadable page, by failure kind; www.whitehouse.gov,
> www.state.gov, www.justice.gov, the .mil hosts and www.hud.gov dominate it.
>
> 1. For each organisation in the two files, propose an official document
>    that names it, and say whether that document also states its **parent**
>    (which would evidence the edge in the tree) and whether it claims to be
>    **complete** (so a unit's absence from it would itself be evidence).
>    Candidates to assess: SAM.gov's Federal Hierarchy (it needs an API key:
>    say how one is obtained and what its fields are); the Treasury's FAST
>    Book and Agency Identifier list; the CGAC code list; the Code of Federal
>    Regulations' organisation parts (each agency's "Organization" subpart);
>    the "Establishment" sections of the United States Code; the Official
>    Congressional Directory's executive-branch section (govinfo, CDIR); GAO
>    reports that print organisation charts; agency budget justifications on
>    govinfo; federalregister.gov/agencies/<slug> pages.
> 2. For each host in `unread_hosts.csv`, name a **second official
>    publisher** of the same organisational fact (govinfo, the Federal
>    Register, the CFR, a budget justification), since the host itself cannot
>    be read.
> 3. Answer per id with the match label. Where a curated unit does not exist
>    under that name, or has been replaced, say so and cite the document.

---

## Prompt C — Verification: an official document naming every unsourced post

**Attach:** `README.md`, `posts_without_source.csv`.

> `posts_without_source.csv` lists 3,663 live posts with no official source.
> Many are curated templates: the same administrative titles (General
> Counsel, Chief Financial Officer, Inspector General, Chief of Staff, Chief
> Information Officer) stamped under dozens of agencies. The project refuses
> a bare title found in a website's shared footer, because every .gov footer
> links an Inspector General.
>
> 1. Propose documents that name posts **by title, scoped to their
>    organisation**: the Congressional Directory's executive section (say
>    which columns carry only the title; the project never reads a person's
>    name); CFR organisation subparts that name offices and their heads;
>    delegations of authority and organisation orders published in the
>    Federal Register; OPM's Senior Executive Service position data;
>    inspectors general's semiannual reports; budget justifications' org
>    charts; the Judiciary's court directories.
> 2. Work by organisation: for the 30 organisations holding the most rows in
>    the file, say which document names which of their posts, by id and with
>    the match label.
> 3. Say plainly where a template title is not a post that organisation has
>    (for example, a small commission with no separate Chief Information
>    Officer), with the document that shows it.

---

## Prompt D — Pay: a pay document for every unpriced post

**Attach:** `README.md`, `unpriced_posts.csv`.

> **What the project already prices from:** 5 U.S.C. §§5312–5316 (the
> Executive Schedule) with OPM Salary Table 2026-EX, including reviewed
> identifications through an office's organic statute and the Code's counted
> classes; statutes that set pay by reference to a level or by parity to a
> judicial tier; uscourts.gov's Judicial Compensation table; senate.gov's
> salary table; Schedules 5–8 of the annual pay-adjustment executive order as
> reprinted in the note to 5 U.S.C. 5332 (Schedule 8 is the uniformed
> services' monthly basic pay); 3 U.S.C. 102; the White House Office's annual
> staff report; OPM's Plum Book rates and levels; OPM's GS, SES and SL/ST
> tables as ranges; the VA's Title 38 pay tables; the DOJ AD pay chart;
> USAJOBS announcements as a listing of a post's grade.
>
> `unpriced_posts.csv` lists 3,333 posts with no pay claim. Ignore rows whose
> `reason` is `beneath_replaced_unit` or `not_federally_paid`; the 2,789 left
> are the research. `title_family` groups templated copies of one title;
> answer per family where one document governs the whole family. A row whose
> `reason` is `multiplicity` stands for several holders, so only a figure
> that holds for every holder by the document's own terms (a statutory rate
> "for each", one pay band) can be used for it.
>
> 1. For each of the 40 largest families, and then for every other row you
>    can, identify which **pay system** governs the post (Executive Schedule,
>    SES, GS/GM, Title 38 or Hybrid Title 38, AD plans, Title 42, a
>    foundation's own plan, the Foreign Service, military grades, the
>    legislative branch's pay orders, or no federal schedule at all), and the
>    **official document that publishes that system's 2026 (or latest)
>    rates**: its URL, effective date, whether it prints annual, monthly or
>    hourly figures, and whether the currency mark sits on every figure or
>    once at the column head.
> 2. Then the **join**: the document that says THIS post is in THAT system
>    at THAT level or grade (a statute, an OPM listing, a classification
>    standard, a vacancy announcement series, an agency directive). Without
>    it, a pay table cannot be applied to a post.
> 3. Cover in particular: the VA medical-centre service chiefs and clinical
>    posts (Title 38 versus Title 5 versus Hybrid Title 38; the Veterans
>    Canteen Service's own pay under 38 U.S.C. 7802); the stamped
>    administrative posts at agencies where no statute names them; the
>    Smithsonian's museum posts (federal GS versus trust-fund employment, and
>    the document that distinguishes them); NSF and NIH program directors
>    (NSF's AD bands, NIH's Title 42); uniformed posts whose grade no statute
>    fixes (combatant and component commanders); the legislative support
>    staff the chambers' pay orders reach only with a ceiling; GAO's band
>    tables from any publisher other than gao.gov; and OPM's locality-area
>    definitions (5 CFR 531 subpart F), so a facility-scoped post could carry
>    its locality range.
> 4. Where a post is paid on no federal schedule (contractor, trust fund,
>    Postal Service bargaining unit, the Federal Reserve's or TVA's own plan),
>    give the document that establishes it.

---

## What to do with the reports

Triage each one into three piles before anything is built: documents to
fetch as fixtures (only from a host whose robots.txt allows it, via
`scripts/fetch_fixture.py`); identifications that need a reviewed table row
with its basis quoted; and leads that name no document, which are recorded
in `CURATION.md` and go no further. Treat a "certain" match from a report as
a lead until the committed document has been read; earlier batches showed
"certain" claims that the Code itself contradicted (`CURATION.md` §19).
