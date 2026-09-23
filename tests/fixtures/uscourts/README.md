# U.S. Courts judicial compensation

**Fetched 2026-09-14.**

    python scripts/fetch_fixture.py \
      https://www.uscourts.gov/about-federal-courts/about-federal-judges/judicial-compensation \
      uscourts/judicial_compensation.html

`judicial_compensation.html` (248,816 bytes, sha256
`014c9a66ad48a019ab127752e9cd46e4cec94da5e8e94d41a4eb9e785e96e494`, recorded
verbatim in `judicial_compensation.html.meta.json`) is the U.S. Courts' own
"Judicial Compensation" page: one table, four tiers, current year first —

| Year | District Judges | Circuit Judges | Associate Justices | Chief Justice |
|---|---|---|---|---|
| 2026 | $249,900 | $264,900 | $306,600 | $320,700 |

back to 1994, plus one footnote (`fn1`, about two 2014 cost-of-living
adjustments, `Beer v. United States`) that does not apply to the current row
and carries through this module's `footnotes` field as an empty tuple rather
than being silently dropped — an empty list is a checked fact, not a missing
one.

**Read by `data_pipeline/verification/judicial_pay.py`, derived by
`scripts/derive_judicial_pay_evidence.py`.** Unlike the Executive Schedule
join in `../opm/pay/README.md`, there is no second document: this one page
states the tier and the rate together. The parser was written against this
file and refuses rather than guesses — a reshaped table (different columns),
two tables on the page, a header/data cell mismatch, or a year printed twice
all raise `Unreadable`.

**17 positions are priced** (15 until 2026-09-23), not the 202 judicial-branch
position nodes this graph carries: the Chief Justice (the table's own "Chief
Justice" column), and the thirteen named circuits' and SDNY's own Chief Judge,
each priced at the tier a chief judge actually holds (a circuit's chief judge
is a circuit judge, paid as one — Article III courts carry no separate
"chief's salary" the way the House pays its Speaker more); and, since
2026-09-23, `Associate Justice (×8)` and SDNY's `District Judge (×28 active)`,
where the tier rate applies to each holder alike (`holders`). Every other
judicial position either states a multiplicity the table cannot price
("Circuit Judge (×28 active + senior judges)" bundles senior judges, whose
salary 28 U.S.C. 371(b)(2) sets apart) or is
`jud-district-structure-chief-judge`, a node describing what every one of
the 94 districts' structure looks like rather than naming one district's
actual chief judge; that one is refused by id, since it carries no count in
its own name for the multi-post guard to catch. The specialized Article I
courts (Tax Court, Court of Federal Claims, Court of International Trade,
CAAF, CAVC) are not priced: their judges' pay follows other statutory
provisions this module has not read a source for, and pricing them from the
Article III table would be guessing the numbers are the same.

Every record is `scopeMatch: "proxy"` — the table names a tier, not this
specific node — so `financial_evidence.classify` grades all 15 `partial`;
none is `verified`. Basic pay is not the node's cost, so it is published in
`positionStatutoryPay` and never in the cost cascade; the release gate
(`statutory_pay_violations`) checks the tier claimed against a
`STATUTORY_PAY_NODE_TIERS` map keyed by node id, not just against the mirror
of the current year's rates, because the four tiers' dollar figures alone do
not stop a Circuit Chief Judge's record being mislabelled as, say, a
District Judge's without also changing the amount to match.
