# Perplexity prompt #2 — closing the blocks the first pass could not

Paste everything below the rule. This is the follow-up to
`docs/PAY_SOURCE_RESEARCH_PROMPT.md`, written 2026-09-23 after acting on the
first pass. It is deliberately narrower: the first pass established *which*
documents exist, and every remaining question is about a **join** — what turns
a document that prices a category into a figure for a named office.

What changed since the first pass, so the answer does not re-tread it:

- **Schedule 6 is done.** Fetched from `uscode.house.gov` (the note to 5 U.S.C.
  § 5332), verified, and shipped. The Vice President ($292,300), the Speaker
  ($223,500) and the House Majority and Minority Leaders ($193,400) are priced.
- **Schedule 7 was in the same document**, which the first pass said it could
  not retrieve. It prints: Chief Justice $320,700, Associate Justices $306,600,
  Circuit Judges $264,900, District Judges $249,900, **Judges of the Court of
  International Trade $249,900**. It agrees with uscourts.gov to the dollar,
  and Schedule 5 agrees with OPM's Salary Table 2026-EX to the dollar.
- So the Article I question is now **narrower than the first pass framed it**:
  Schedule 7 covers the CIT and nothing else on that list.

---

I maintain a public, evidence-gated map of the U.S. federal government. Every
figure must be traceable to a primary government document, carry that
document's own date and wording, and claim no more than the document states. I
never read the names of individual office holders.

I have 4,591 position nodes and 385 now carry a pay claim. The first research
pass established which official pay documents exist. Every remaining question
is about **joining a document to a named office**, so please answer these
specific questions rather than re-listing sources.

## Question 1 — VA Title 38: which named titles does the schedule itself pair with a tier?

This is my largest single block: **468 unpriced positions under VA Medical
Centers** (Medical Center Directors, Associate Directors, Chiefs of Staff,
and clinical service chiefs).

I understand the 2026 VA Title 38 pay tables state tier minimum/maximum annual
rates and that an incumbent's selected rate is not disclosed. I am content to
publish an **office-linked range** and label it as a range. What I need is the
join:

1. In the current VA pay schedule document, **which specific position titles
   are printed**, and under which tier? Quote the document's own words for the
   coverage category, e.g. does it print "Medical Center Director" as a
   covered assignment, or does it print a broader category such as "Executive
   Assignments" that a reader must then map to that title?
2. Is the **assignment of a given VA medical center to a tier** published
   anywhere? A tier range is only usable per-office if something official says
   which tier a particular medical center's director sits in. If that mapping
   is not published, say so plainly — that is a decisive answer for me.
3. Give the **exact current URL** of the pay-table document and its effective
   date, and say whether `www.va.gov` (or whichever host serves it) allows an
   automated fetch of that path under robots.txt.
4. Are the **VISN Network Director** positions priced by the same document or
   a different one?

## Question 2 — the four Article I courts Schedule 7 does not reach

Schedule 7 covers the Court of International Trade. It does not name the **Tax
Court**, the **Court of Federal Claims**, the **Court of Appeals for the Armed
Forces**, or the **Court of Appeals for Veterans Claims**.

For each of those four, I need one of two answers, and "there is no published
current figure" is a perfectly good one:

- the **current-year dollar figure** for that court's judges, from a primary
  source I can fetch (statute text, an Executive Order schedule, an
  administrative-office publication), with the URL; or
- the **statutory parity provision** that sets it by reference to another tier
  (I am aware of 28 U.S.C. § 171(a), 28 U.S.C. § 258(a), 26 U.S.C. § 7443(c),
  10 U.S.C. § 942, 38 U.S.C. § 7253) — and, critically, **whether the current
  text of that provision still states the parity**, quoted, rather than a
  secondary source asserting it.

A parity provision plus Schedule 7's district-judge figure would let me publish
a derived figure — but only if I can cite the provision's current text. Please
quote it.

## Question 3 — does a title-to-grade mapping exist for SEC, CFPB or the Fed?

The first pass established that the SEC publishes SK/SO ranges, the CFPB
publishes CN bands, and the Federal Reserve Board publishes FR grade ranges —
but that none of them publishes which named office sits at which grade.

Is that correct? Specifically, does any **official** document (an org chart
with grades, a published position description, a vacancy announcement archive,
a congressional-budget-justification staffing table, an IG report) state the
pay grade or band of a **named** senior office at any of these three? If the
honest answer is that agencies publish grades only in transient vacancy
postings, say so — I would rather leave 45 nodes unpriced than infer a grade.

## Question 4 — the Federal Reserve annual report, current edition

The first pass cited Table G.12 of the **2024** annual report for each Reserve
Bank President's salary, and noted it was archived. Has the **2025** edition
been published? If so, give the direct URL, confirm the table number, and say
whether the table still pairs one President's salary with each named Bank.

## Question 5 — what did the first pass miss?

One source in the first pass turned out to contain more than the pass reported:
Schedule 7 was in the same document as Schedule 6, and was described as
unretrievable. Please check specifically whether any source you recommend
contains adjacent schedules, appendices or tables that price offices beyond the
one you are recommending it for — and name them.

## Answer format

Per source or per question: the document's official name and publisher, the
direct URL, format, effective date, whether the figure attaches to the office
or to a person, roughly how many of my unpriced positions it would reach, and
whether the path is robots.txt-fetchable. Quote the document's own words
wherever a claim rests on them. Rank by how many positions each would let me
price, and be explicit where the answer is "no such document is published."

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
