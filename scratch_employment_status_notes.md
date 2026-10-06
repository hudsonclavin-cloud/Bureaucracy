# Proposed CLAUDE.md paragraph: employment_status.py (2026-10-07)

For the coordinator to place under "Existence evidence", after the USAJOBS
paragraphs. Not applied to CLAUDE.md or CURATION.md by this branch. The
figures were measured on a local rebuild
(`regenerate_published_graph.py --treasury-rows tests/fixtures/mts_table5_2026-08-31.json`,
gate exit 0). output/ is not committed.

---

**Posts a contractor pays, said in so many words (`employment_status.py`,
since 2026-10-07, the owner's decision).** A post with no pay claim counts as
an unpriced post that a research pass should find a salary for. For some posts
no federal pay document will ever name the title, because the people who hold
them are not paid on a federal schedule. The owner decided to say so for a
post only where a committed official document establishes it. This is the
first case. The claim rests on **three** documents, because the first one
alone does not say what it reads as saying.

- **The operator.** NETL's own page, "The NETL Unique Advantage of Being a
  Government-Owned, Government-Operated Laboratory" (May 22, 2023,
  `tests/fixtures/doe/netl_operating_model.html`): "The U.S. Department of
  Energy operates 17 national laboratories. NETL is the only government-owned,
  government-operated facility. The other 16 are government-owned,
  contractor-operated." The page names only NETL.
- **Which sixteen.** DOE's own index, `www.energy.gov/national-laboratories`
  (`tests/fixtures/doe/national_laboratories.html`, robots allows, fetched
  2026-10-06), prints "The Energy Department's 17 National Labs" and labels
  each of the seventeen as an accordion heading. It says of NETL alone that it
  "is government-owned and government-operated (GOGO)". So "the other 16" is
  read off DOE's page and not inferred from the graph's own grouping.
  `CONTRACTOR_OPERATED_LABS` is a reviewed table keyed by node id, mapping
  each of the graph's sixteen other lab nodes to the label the page prints.
  Every run re-checks it: the page must label exactly seventeen laboratories,
  the sixteen rows plus NETL must be exactly those labels, and each node must
  still carry its reviewed name. One node is renamed from its label in the
  curated file, "National Laboratory of the Rockies (NLR)", and it reduces to
  the page's label under `canonical_name_key`.
- **What an operator's staff are.** "Operated by a contractor" is a statement
  about the operator, not literally about who employs each post. The
  Department of Energy Acquisition Regulation, 48 CFR part 970 (GPO's 2025
  edition, revised as of 2025-10-01, from www.govinfo.gov, robots allows,
  `tests/fixtures/doe/dear_48_cfr_970_govinfo2025.xml`), closes most of the
  gap in its own words. Each quote is re-found inside the one SECTION whose
  SECTNO it names:
  - DOE "has negotiated technology transfer clauses with the contractors
    managing and operating its laboratories" (970.2770-3);
  - "Employees of a management and operating contractor are entitled to the
    same rights and privileges with respect to outside employment as other
    citizens" (970.0371-7);
  - "the compensation paid individual employees should be left to the judgment
    of contractors subject to the limitations of DOE-approved compensation
    policies, programs, classification systems, and schedules"
    (970.3102-506);
  - "The contracts are totally financed by DOE advance payments"
    (970.3102-370).

  **Part 970 never says in words that an M&O contractor's staff are "not
  Federal employees".** A test pins that negative against the bytes. The
  published wording therefore says what the regulation does say: the
  contractor sets the pay within DOE-approved schedules, and DOE finances the
  contract.

**What it publishes.** `positionEmployer` goes on each Position node
**directly** under one of the sixteen laboratory nodes. The block holds
`federallyPaid: false`, `kind: contractor_operated_laboratory`, the laboratory
id, name and DOE label, the three documents (url, sha256, fetchedAt, title,
date, verbatim quotes, CFR section) and two generated sentences.

- The headline: "Not on a federal pay schedule: <laboratory> is one of the 16
  DOE laboratories operated by a contractor (DOE, NETL page, May 22, 2023)."
- What is not established: "No document here names who holds this post or
  says every holder is the contractor's employee, and the title is a template
  every DOE laboratory node carries. Not federally paid means not paid as a
  federal employee on a federal pay schedule; the money is DOE's, through the
  contract."

What the documents *do* establish is not paraphrased onto the node. The panel
prints each document's quotes verbatim beside its link (a CFR quote with its
section).

**112 posts** carry it (16 laboratories × 7 templated titles). That includes
the multi-post nodes, because an employer is the same fact for every holder.
**NETL's 7 posts get nothing.** NETL is government-operated, its posts are
federal, they stay unpriced, and the gate refuses the block there.

The block writes no `sourceUrls`, `sourceTypes`, `lastVerified` or
`verificationMethod`, no cost field and no pay field. A post that any pay
document has priced is left alone. The block is applied after
`annotate_pay_documents`, so that rule is read off the final tree. The field
is in `EVIDENCE_OWNED_FIELDS` and `MINIMAL_GRAPH_FIELDS`. On the rebuild the
only change to the graph was the 112 blocks: no cost, verification status or
source moved.

**The gate** (`employer_violations`, stdlib only) re-reads the three fixtures
with its own reader and does the following:

- recomputes each digest against both the `.meta.json` and the block;
- re-finds every mirrored quote, each CFR quote inside its named section;
- re-reads the seventeen accordion labels;
- reads the parent off the tree it walks, never off `parentId`.

It refuses the block in each of these cases:

- on a NETL post, on a non-post, or under any parent that is not one of the
  mirrored sixteen;
- under a renamed laboratory, or with a laboratory id, name or label that is
  not the tree's;
- beside any of the ten pay fields, or beside a measured cost;
- with `federallyPaid` anything but `false`;
- with a headline or qualifier that is not the mirrored template, or any key
  (on the block, a document or a quote) that the module never writes, so a
  paraphrase cannot ride along unchecked;
- with a dropped, reordered, retitled or redated document, or a fetch date
  that is not the committed one;
- with an edited quote or a moved section, or a digest or URL that is not the
  committed one;
- with an inflated document count or a future date;
- with any of the three URLs among the node's own sources, or a verification
  method naming this source.

`tests/test_employment_status.py` corrupts each case in turn. It also pins
both mirrors (the sixteen ids and the documents) equal to the module, and
runs derive, build, gate and withdrawal end to end on a small base graph.

**The panel** reads PAY over "Not federally paid" where it read "Not
available". The badge reads "No cost known; not on a federal pay schedule".
`#info-employer` prints the headline, the qualifier, and the three documents
as links, each followed by its own quoted words. The atlas view prints the same text in its Pay row.
`scripts/frontend_smoke.mjs` opens a contractor-laboratory post and asserts
the headline, the PAY heading, the exact sentence and the qualifier. It also
opens NETL's Laboratory Director and asserts it says none of it.

**Declined, and why.**

- No block on NETL's posts. They are federal, and no pay document in hand
  names them.
- No reading of 48 CFR part 970 as saying "not federal employees", because it
  does not say that.
- No block deeper than a laboratory's direct children. There are none today,
  and a deeper node might be something other than the laboratory's staff.
- The headline "Not federally paid" is the owner's wording. It is accurate
  only in the sense the qualifier states: 970.3102-370 says DOE finances the
  contracts, so the money is federal and the salary is the contractor's. The
  coordinator may prefer "Not a federal salary".

**Size, and a margin the next field will break.**
`tests/test_viewer_graph.py` requires `graph.min.json` to be under half of
`graph.json`. At HEAD the margin was already only 29,631 bytes (9,163,641
against 18,386,544 / 2).

- The first draft quoted whole paragraphs, repeated each document's publisher
  and description on every node, and carried a paraphrase of what the
  documents establish. That broke the rule by about 15 KB.
- The block now carries the shortest verbatim span that holds each part of the
  claim, with no paraphrase. The descriptive fields sit once in the evidence
  file's report.
- On the rebuild: `graph.json` 18,940,566 bytes, `graph.min.json` 9,465,327,
  a margin of **4,956 bytes**.

The next field added to the viewer copy will trip the rule whatever it is. The
rule should be revisited deliberately, not loosened by whoever trips it.
