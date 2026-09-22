# Perplexity prompt — official sources for federal pay, by post

Paste everything between the rules below into Perplexity (Research / Deep
Research mode). The FOLLOW-UP CHAIN DIRECTIVE at the end is Hudson's standing
convention for exploratory research prompts and is reproduced verbatim; do not
strip it.

Written 2026-09-22 against the published graph: **381 of 4,591 position nodes
carry a pay claim, 4,210 do not.** The counts quoted in the prompt are measured
from `output/graph.json`, not estimated. Regenerate them with
`scripts/validate_published_graph.py` before re-firing this prompt if the graph
has moved.

---

I am building a public, data-backed 3D map of the U.S. federal government —
every organisation and every named position, from the Constitution down to
individual offices. Its governing rule is that **the map may never claim more
than the evidence supports**: every figure it shows must be traceable to a
primary document published by the government itself, and every figure carries
that document's own date, scope and wording beside it.

I have 4,591 position nodes. 381 of them currently carry a rate of pay backed
by a primary source. I need help finding the official documents that would
cover more of the remaining 4,210.

## What I have already read — do not return these

Please treat these as exhausted and do not spend answer budget re-recommending
them. Tell me only if you believe one of them contains a section I have
plainly missed.

1. **5 U.S.C. §§5312–5316** (the Executive Schedule, Levels I–V as enacted),
   read from uscode.house.gov — 99 positions priced.
2. **OPM Salary Table No. 2026-EX** — the annual rate for each Executive
   Schedule level.
3. **OPM Salary Tables No. 2026-GS, 2026-ES and 2026-SL/ST** — base-pay
   ranges (not rates) for General Schedule grades, the Senior Executive
   Service and Senior Level / Scientific & Professional.
4. **OPM's PLUM archive** (positions reported 2021–2025) and **OPM's current
   Plum Book export** from escs.opm.gov — pay plan, level, and for some rows a
   printed rate. 88 positions priced from the current export.
5. **The White House Office's Annual Report to Congress on White House Staff**,
   required by §6 of Public Law 103-270 — every staff title and its annual
   rate. 166 positions priced.
6. **uscourts.gov's Judicial Compensation table** — District Judges, Circuit
   Judges, Associate Justices, Chief Justice.
7. **senate.gov's year-by-year Senate salary schedule**, including the footnote
   naming the President Pro Tempore and the Majority and Minority Leaders.

## What an acceptable source looks like

A source is only useful to me if it meets **all** of these. Say explicitly, per
source, whether each holds — and say so honestly, including "no".

- **Published by the U.S. government**, on a `.gov` or `.mil` host, or by the
  body itself where the body is not on a `.gov` host (e.g. the Federal Reserve
  Board on federalreserve.gov, which is a `.gov`; the Federal Reserve Banks,
  which are not). A think-tank summary, a news article, a salary-aggregator
  site, or a Wikipedia table is not a source for my purposes — though such a
  page is *useful to me as a pointer* if it cites the primary document, in
  which case give me the primary document.
- **It pairs a JOB TITLE with a NUMBER.** A document listing only people's
  names and salaries, with no titles, is useless to me: I never read the names
  of office holders, by design. A document listing titles and a pay plan or
  grade is useful if you can also name the published table that converts that
  plan or grade into a figure.
- **It has a stable URL that returns the document itself**, not a search
  interface, a landing page, or a page that requires a session or a key. If a
  key is required (e.g. api.sam.gov), say so and say how one is obtained.
- **State the format**: JSON, CSV, XML, XLSX, an HTML table, or a PDF — in that
  order of preference for me. Say the approximate size and row count if you can
  see it.
- **State whether the figure attaches to the OFFICE or to the PERSON.** A
  statutory rate for "Secretary of Agriculture" survives a change of holder; a
  roster line saying the current Deputy Assistant Secretary is paid $172,100
  does not. I publish these differently and must know which I have.
- **State the document's own effective date or as-of date**, and whether it is
  current or an archived edition.
- **Say whether the host's `robots.txt` allows an automated fetch of that
  path.** I obey robots.txt and do not work around a refusal. If the host
  blocks crawlers (Cloudflare challenge, 403 on robots.txt, a JS shell), say
  so — that is a useful finding, not a disqualification.

## The gaps, measured, largest first

These are the concrete blocks of unpriced positions in my data. For each, I
want to know what the official pay document is, or a clear statement that none
is published.

| Unpriced posts | Where they sit | What I think the pay regime is — correct me |
|---|---|---|
| 468 | VA Medical Centers (Directors, Chiefs of Staff, Associate Directors, service chiefs) | Title 38 VHA pay: physician/dentist base-and-market-pay schedules, plus Title 5 SES for centre directors. Is there a published VA pay schedule naming these positions? |
| 83 | White House Office (titles the 2026 roster does not print) | Possibly none — the statutory report is the only roster. |
| 56 | "Districts (multiple)" — U.S. Attorneys' and federal district staff | Are U.S. Attorneys' salaries published anywhere as rates? |
| 26 | Federal Reserve System (Board Governors, Reserve Bank Presidents) | Governors are set by 12 U.S.C. 241/242; Reserve Bank President salaries are published in the Board's Annual Report. Which document, which year, what URL? |
| 21 | FBI | Is SES/SL the whole answer, or is there an FBI-specific schedule? |
| 19 | SEC | The SEC has its own "SK" pay system outside the GS. Is the SK table published? |
| 18 each | Individual Senator Offices; House Leadership; Bureau of Prisons; Secretary of the Senate; Sergeant at Arms of the Senate; Joint Chiefs of Staff | For the chambers: is there a published staff pay schedule (Senate Salary Schedule, House Members' Representational Allowance statements of disbursements) that gives TITLES and rates? |
| 17 each | U.S. Air Force, U.S. Space Force, U.S. Coast Guard (and 16 U.S. Army) | Uniformed pay under 37 U.S.C.: the annual DoD military pay tables give pay grade and years of service, not titles. What is the authoritative published mapping from a named post (e.g. Chief of Staff of the Air Force) to a pay grade, and is general/flag officer pay capped by a separate provision? |
| 16 | U.S. Embassies & Consulates | The Foreign Service pay schedule (FS classes) and Chiefs of Mission. Which published table, and does anything name ambassadorial posts specifically? |
| 16 | National Institutes of Health | Title 42 §209(f) special consultant pay, and the published NIH Title 42 pay bands. Are these published as a table? |

## Named gaps I already know about and cannot presently cite

Tell me the primary document for each, or tell me there isn't one.

- The **Speaker of the House** and the House **Majority** and **Minority
  Leaders'** salaries. The Congressional Research Service reports that carry
  these are behind a Cloudflare challenge for me. Is the figure stated in
  statute (2 U.S.C. 4501?) or in a published House document I can fetch?
- The **Vice President's** salary, as a rate attaching to the office.
- The **base salary of a Member of Congress**, from a primary source rather
  than a secondary summary.
- The **Article I courts** — the U.S. Tax Court, the Court of Federal Claims,
  the Court of International Trade, the Court of Appeals for the Armed Forces,
  the Court of Appeals for Veterans Claims. These sit on a different statutory
  basis from the Article III judges whose pay uscourts.gov publishes.
- **Locality pay.** The GS table I have states base rates before locality
  adjustment, and says so. Where are the locality percentages published, and is
  there a table stating a *rate* for a named post in a named locality?
- Positions on **pay systems outside Title 5 altogether** — the FDIC, the OCC,
  the CFPB, FHFA, the Farm Credit Administration and the other
  financial-regulator agencies that set their own compensation. Do any of them
  publish a pay schedule with titles?

## What I want back

For each source you find, give me:

1. The document's official name and the body that publishes it.
2. The direct URL that returns the document.
3. Format, size, row count if visible.
4. Effective date / as-of date, and whether it is the current edition.
5. Whether the figure attaches to the office or to a person.
6. Roughly how many of my unpriced positions it could plausibly reach, and
   which block from the table above.
7. Whether the path is robots.txt-fetchable, as far as you can tell.
8. Any statutory citation that governs the figure.

Rank the sources by how many positions they would let me price, and be
explicit where the honest answer is "no such document is published" — a
well-evidenced negative saves me more time than a hopeful lead.

FOLLOW-UP CHAIN DIRECTIVE:
After answering the question above in full, continue as follows:

LEVEL 1 — State the 3 most decision-relevant follow-up questions your answer
raises for this federal-government pay-mapping tool, and answer each with sources.

LEVEL 2 — For each Level-1 answer that materially affects a design decision,
pose and answer the single most important follow-up it raises, with sources.

LEVEL 3 — Repeat once more for any Level-2 answer that still carries open
decision weight.

BUDGET: no more than 10 follow-up answers total across all levels. Prune by
decision-relevance, not curiosity — drop branches that only add color.

For EVERY follow-up answer:
(a) open with one line stating why this follow-up matters for the tool,
(b) cite primary sources,
(c) flag each number as official-published vs third-party-estimated.

END with a section titled LOAD-BEARING NUMBERS: a flat list of every number
in this entire response that a design decision might rest on — one line per
number, with its source. This list feeds an independent verification pass.
