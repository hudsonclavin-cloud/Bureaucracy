"""A figure no single document states, and the two that between them do.

## The claim this module makes, and why it is a new shape

Every other pay module here publishes a number some document prints. This one
does not. `judicial_pay.py`'s own docstring records the refusal it exists to
lift:

    it will not price ... the specialized Article I courts (Tax Court, Court of
    Federal Claims, Court of International Trade, CAAF, CAVC). Their judges'
    pay follows other statutory provisions this module has not read a source
    for; pricing them from the Article III table would be guessing that the
    numbers are the same.

The refusal was about not having read the provision, and the provisions say
exactly what the Article III table cannot: *which tier* each of these courts'
judges is paid at. Congress wrote four parity provisions, and each one is one
sentence naming another court's judges:

- 26 U.S.C. 7443(c)(1), the Tax Court, at the district-judge rate;
- 28 U.S.C. 172(b), the Court of Federal Claims, at the district-judge rate;
- 10 U.S.C. 942(d), the Court of Appeals for the Armed Forces, at the
  circuit-judge rate;
- 38 U.S.C. 7253(e), the Court of Appeals for Veterans Claims, at the
  district-judge rate.

So the figure is a join: the statute names the tier, and the Administrative
Office's own Judicial Compensation table states what that tier pays. **Neither
document states the figure.** That is a weaker thing than a printed rate and
the published record says so in as many words, rather than presenting a
derivation as a quotation.

## The research this was built from was wrong about one of the four, and the
## statute's own operative text is what caught it

A research pass reported 38 U.S.C. 7253(e)(1)-(2) as splitting the CAVC: the
chief judge at the *circuit*-judge rate, the other judges at the district rate.
That is the text of the section **as it read before amendment**, which
uscode.house.gov prints in full inside the section's Amendments note,
introduced by "Prior to amendment, text read as follows:". The current
subsection (e) reads, whole:

    Each judge of the Court shall receive a salary at the same rate as is
    received by judges of the United States district courts.

A substring search of the page finds the repealed sentence and cannot tell it
from the law. So `operative_text` cuts the page at the first of "Historical
and Revision Notes", "Editorial Notes" or "Statutory Notes" and every parity
quote must be found in what is left, and `tests/test_derived_pay.py` asserts
in both directions: each of the four quotes IS in its section's operative
text, and the repealed CAVC chief-judge sentence is NOT, though it is on the
page.

## The Court of International Trade is refused, and the refusal is the rule

28 U.S.C. 252 states no parity. It reads "Each shall receive a salary at an
annual rate determined under section 225 of the Federal Salary Act of 1967
(2 U.S.C. 351-361), as adjusted by section 461 of this title", which is a
chain through two further documents and an adjustment this project has not
read. CIT judges are in fact paid the district-judge rate; that is a thing
this repository knows and cannot cite, which is the same position
`CURATION.md` puts "Secretary of the Treasury" in. So `jud-specialized-intl-
trade-chief-judge-cit` is refused HERE and the section is committed anyway,
because "nobody looked" and "looked and it states no parity" are different
facts. (Since 2026-10-05 that post and the court's bench are priced by
`us_code_pay_schedules.py` from a document that states the figure outright --
Schedule 7's row "Judges of the Court of International Trade" -- which is a
different field's claim and changes nothing about what this module can
derive from §252.)

## Four nodes, and every other seat refused for the reason judicial_pay gives

Each of these courts carries one single-post chief-judge node and a
`Judge (x18)` / `(x15)` / `(x8)` / `(x4)` node that states a multiplicity. The
multi-post nodes are refused by the rule `pay_tables.py` set and
`judicial_pay.py` repeats: a single rate beside a panel describing a whole
group reads as what one holder earns. A chief judge is priced because a chief
judge IS a judge of that court -- the parity provisions say "Each judge",
without a chief's premium -- which is the same reading `judicial_pay.py`
already applies to Article III chief judges. The four service Courts of
Criminal Appeals nested under the CAAF node are refused: their judges are
commissioned officers paid under title 37, which no document here has read.

## The percentage, and what it does and does not measure

The owner asked for the level of verification as a percentage saying how many
documents verify a claim. `document_strength_percent` is that number and it
is **this project's own existing arithmetic**, not a second scale invented for
this field: `normalize_nodes.verify_node_sources` scores one official document
0.4 + 0.3 and each further one +0.1 to a cap of 0.3, so one document is 70%,
two 80%, three 90%. Reusing it means the figure beside a derived rate is the
same figure the panel already prints beside a node's sources.

What it measures is how much official documentation the claim rests on. It is
not a probability that the figure is right, and on this field in particular it
would be a lie read that way, so every record also carries
`documentsStatingTheFigure: 0` and the panel prints that beside the percentage.
Two documents scoring 80% neither of which states the number is exactly the
situation a bare percentage would hide.

## A percentage of a join (since 2026-10-05, the owner's decision)

The bankruptcy judges (28 U.S.C. 153(a), 92 percent of a district judge's)
take a percentage of the table's own printed figure. Three posts take a
percentage of a figure that is itself a join: the Tax Court's special trial
judges (26 U.S.C. 7443A(d), 90 percent of a Tax Court judge's, which
7443(c)(1) sets at a district judge's), the AO's Deputy Director (28 U.S.C.
603, 92 percent of a Director the same section pays as a district judge) and
the FJC's Deputy Director (28 U.S.C. 626, paid what the AO's Deputy is paid).
Those were refused until the owner decided the shape; now a provision may
carry `percentOf` and `via` together, a `quote` may be a tuple of sentences
from one section (each re-found in the operative text on its own), and the
record names every document in the chain and says that none states the
figure. See the comment above `SPECIAL_TRIAL_JUDGE_QUOTE`.

## A ceiling the compensation table's own page resolves (since 2026-10-06, the
## twelfth research batch's judiciary cluster)

28 U.S.C. 634(a) pays full-time magistrate judges "up to an annual rate equal
to 92 percent of the salary of a judge of the district court" -- a CEILING
the Judicial Conference fixes a salary beneath, which is why the two
magistrate benches were refused here while the bankruptcy benches (28 U.S.C.
153(a), "equal to 92 percent", no ceiling word) were priced. The Administrative
Office's own Judicial Compensation page -- the very document the table is read
from -- prints beneath the table: "By statute, the salary of a bankruptcy or
magistrate judge is equal to 92 percent of the salary of a district judge.
28 U.S.C. §§ 153, 634(a)." That sentence is the document that says what the
Conference fixed under the ceiling. So the magistrate rows are percent-of rows
in the bankruptcy shape with one thing more: a `basisQuote`, re-found in the
compensation page's own text on every run (`build_records` refuses the row
when the page no longer prints it), published on the block as `ceilingBasis`
with the reading in words, and mirrored by the gate by node id. The document
count stays at two -- the sentence is on the same page as the table -- and the
distinction the tests pinned is kept: "up to" IS in §634 and NOT in §153; what
changed is that a second sentence of a document already in hand resolves it.

The same cluster priced the Chair of the United States Sentencing Commission
from 28 U.S.C. 992(c), an office row in the Administrative Office Director's
shape at the CIRCUIT-judge tier, and refused the Commission's `Commissioner
(×6)` bench: §992(c) pays the Vice Chairs at the annual circuit-judge rate and
the other voting members "at the daily rate", so one figure for the bench
would be false of some of its members, the senior-judge refusal's shape.

Basic pay is not the node's cost, for the reason `pay_tables.py` states, and
nothing here writes `sourceUrls`, `sourceTypes`, `lastVerified` or
`verificationMethod` -- the channel by which a five-row table carried 29
positions to `verified` on 2026-09-11.
"""

from __future__ import annotations

import hashlib
import html as html_module
import json
import re
from pathlib import Path
from typing import Any, Mapping

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "uscode"
DEFAULT_PAY_EVIDENCE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "verification" / "derived_pay_evidence.json"
)

PAY_SOURCE = "statutory_parity_derived_pay"
PAY_SOURCE_TYPE = "statutory_parity_derived_pay"
PAY_METHOD = "parity_provision_joined_to_the_judicial_compensation_table"

#: The scale, stated once. `verify_node_sources` scores a node's sources
#: 0.4 for the first, +0.3 where one is an official site, +0.1 per further
#: source capped at 0.3. Applied here to the documents a FIGURE rests on
#: rather than to a node's own URLs, and named as that reuse wherever it is
#: published, because an unexplained percentage is worse than none.
STRENGTH_SCALE = (
    "this project's own source arithmetic (normalize_nodes.verify_node_sources): "
    "0.4 for the first official document, +0.3 because it is an official site, "
    "+0.1 for each further one, capped at 0.3"
)


def document_strength_percent(count: int) -> int:
    """The project's own confidence arithmetic for `count` official documents,
    as a whole percentage. 1 -> 70, 2 -> 80, 3 -> 90, 4 or more -> 100."""
    if count <= 0:
        return 0
    score = 0.4 + 0.3 + min(0.3, (count - 1) * 0.1)
    return int(round(min(score, 1.0) * 100))


#: Where a section's own text stops and the publisher's notes begin. The
#: repealed CAVC sentence lives past this line; so does every historical
#: salary figure in 28 U.S.C. 172's amendment history.
NOTE_HEADINGS = (
    "Historical and Revision Notes",
    "Editorial Notes",
    "Statutory Notes",
)

#: The four provisions, each a reviewed identification of one curated node.
#: An explicit table for the reason `us_code_pay_schedules.SCHEDULE_6_NODE_ROWS`
#: gives: four rows, a statutory salary at stake, and a map this short is more
#: auditable than a pattern that would also have to be proven not to catch
#: anything else. `quote` is checked against the section's OPERATIVE text on
#: every run -- the table proposes, the statute decides.
PARITY_PROVISIONS = {
    "jud-specialized-tax-chief-judge-tax-court": {
        "citation": "26 U.S.C. 7443(c)(1)",
        "fixture": "tax_court_26_usc_7443.html",
        "court": "U.S. Tax Court",
        "subsection": "(c) Salary",
        "tier": "district judges",
        "quote": (
            "Each judge shall receive salary at the same rate and in the same installments "
            "as judges of the district courts of the United States."
        ),
    },
    "jud-specialized-claims-chief-judge-cfc": {
        "citation": "28 U.S.C. 172(b)",
        "fixture": "cfc_28_usc_172.html",
        "court": "U.S. Court of Federal Claims",
        "subsection": "(b)",
        "tier": "district judges",
        "quote": (
            "Each judge shall receive a salary at the rate of pay, and in the same manner, "
            "as judges of the district courts of the United States."
        ),
    },
    "jud-specialized-caaf-chief-judge-caaf": {
        "citation": "10 U.S.C. 942(d)",
        "fixture": "caaf_10_usc_942.html",
        "court": "United States Court of Appeals for the Armed Forces",
        "subsection": "(d) Pay and Allowances",
        "tier": "circuit judges",
        "quote": (
            "Each judge of the court is entitled to the same salary and travel allowances as are, "
            "and from time to time may be, provided for judges of the United States Courts of Appeals."
        ),
    },
    "jud-specialized-cavc-chief-judge-cavc": {
        "citation": "38 U.S.C. 7253(e)",
        "fixture": "cavc_38_usc_7253.html",
        "court": "United States Court of Appeals for Veterans Claims",
        "subsection": "(e) Salary",
        "tier": "district judges",
        "quote": (
            "Each judge of the Court shall receive a salary at the same rate as is received by "
            "judges of the United States district courts."
        ),
    },
}

#: Two OFFICES priced the same way, since 2026-09-28 on the owner's
#: instruction: 28 U.S.C. 603 pays the Director of the Administrative Office
#: "the same as the salary of a district judge", and 28 U.S.C. 626 pays the
#: Director of the Federal Judicial Center "the same as that of the Director
#: of the Administrative Office" -- a chain of two statutes to the tier, so
#: that record rests on THREE documents (`via` is the middle one) and none of
#: them states the figure. `subject` is what the statute's sentence is about,
#: printed by the panel where a court row prints "every judge of <court>".
PARITY_PROVISIONS["jud-support-aousc-director-aousc"] = {
    "citation": "28 U.S.C. 603",
    "fixture": "aousc_28_usc_603.html",
    "court": None,
    "subject": "the Director of the Administrative Office of the United States Courts",
    "subsection": "Salaries",
    "tier": "district judges",
    "quote": "The salary of the Director shall be the same as the salary of a district judge.",
}
PARITY_PROVISIONS["jud-support-fjc-director-fjc"] = {
    "citation": "28 U.S.C. 626",
    "fixture": "fjc_28_usc_626.html",
    "court": None,
    "subject": "the Director of the Federal Judicial Center",
    "subsection": "Compensation of the Director and Deputy Director",
    "tier": "district judges",
    "quote": (
        "The compensation of the Director of the Federal Judicial Center shall be the same as that of "
        "the Director of the Administrative Office of the United States Courts"
    ),
    "via": {
        "citation": "28 U.S.C. 603",
        "fixture": "aousc_28_usc_603.html",
        "subject": "the Director of the Administrative Office of the United States Courts",
        "quote": "The salary of the Director shall be the same as the salary of a district judge.",
    },
}

#: A percentage OF the tier, since 2026-09-30 on the owner's instruction:
#: 28 U.S.C. 153(a) pays "each bankruptcy judge" a salary "equal to 92
#: percent of the salary of a judge of the district court". The figure is
#: arithmetic on the table's printed rate -- the shape
#: `tier_reference_pay.py` publishes for an Inspector General's "plus 3
#: percent" -- and the record carries it in the open (`arithmetic`) under the
#: validator's computed-from-a-marked-figure rule. Two nodes: the Southern
#: District of New York's bench, and the standard-structure template's, which
#: stands for every district's bankruptcy judges and is priced because the
#: statute says "each bankruptcy judge" wherever the judge sits.
BANKRUPTCY_JUDGE_QUOTE = (
    "Each bankruptcy judge shall serve on a full-time basis and shall receive as full compensation "
    "for his services, a salary at an annual rate that is equal to 92 percent of the salary of a "
    "judge of the district court of the United States as determined pursuant to section 135"
)
for _node_id, _subject in (
    ("jud-district-sdny-bankruptcy-judge-12", "every bankruptcy judge of the Southern District of New York"),
    ("jud-district-structure-bankruptcy-judge-varies", "every bankruptcy judge, in every district"),
):
    PARITY_PROVISIONS[_node_id] = {
        "citation": "28 U.S.C. 153(a)",
        "fixture": "bankruptcy_judges_28_usc_153.html",
        "court": None,
        "subject": _subject,
        "subsection": "(a)",
        "tier": "district judges",
        "percentOf": 92,
        "quote": BANKRUPTCY_JUDGE_QUOTE,
    }

#: A percentage of a JOIN, since 2026-10-05 on the owner's decision. Until
#: then a figure that was "arithmetic on a figure that is itself a join" was
#: refused here, and the refusal named the two Deputies. The owner asked for
#: the Tax Court's special trial judges, whose 26 U.S.C. 7443A(d) pays "90
#: percent of the rate for judges of the Tax Court" -- and a Tax Court judge's
#: rate is itself 26 U.S.C. 7443(c)(1)'s parity to a district judge's. That is
#: the same shape as the AO's Deputy (92 percent of the Director's, whom the
#: same section pays as a district judge) and the FJC's Deputy (paid what the
#: AO's Deputy is paid), so all three are priced by one rule: a `via` statute
#: may sit between the percentage and the tier, every sentence of the chain is
#: re-found in its section's operative text on every run, the arithmetic is in
#: the open, and the record names every document, none of which states the
#: figure. A `quote` may be a tuple of sentences from one section when the law
#: needs two of them (28 U.S.C. 603 pays the Director as a district judge in
#: one sentence and the Deputy at 92 percent of the Director in another, with
#: an unrelated sentence between); each is checked separately and the record
#: prints them joined by " … ".
#:
#: 26 U.S.C. 7443A was fetched from the Government Publishing Office's own
#: rendering of the 2024 edition of the Code on www.govinfo.gov, because
#: uscode.house.gov answered every request on 2026-10-05 with an "Under
#: Maintenance" page (docs/NETWORK_ACCESS.md §15). The record names the
#: publisher and the edition; `STATUTE_HOSTS` is the closed list of hosts a
#: statute may be read from, and the gate mirrors it.
SPECIAL_TRIAL_JUDGE_QUOTE = (
    "Each special trial judge shall receive salary— (1) at a rate equal to 90 percent of the rate for "
    "judges of the Tax Court, and (2) in the same installments as such judges."
)
AO_DIRECTOR_QUOTE = "The salary of the Director shall be the same as the salary of a district judge."
AO_DEPUTY_QUOTE = "The salary of the Deputy Director shall be 92 percent of the salary of the Director."
FJC_DEPUTY_QUOTE = (
    "The compensation of the Deputy Director of the Federal Judicial Center shall be the same as that of "
    "the Deputy Director of the Administrative Office of the United States Courts."
)
PARITY_PROVISIONS["jud-specialized-tax-special-trial-judge-multiple"] = {
    "citation": "26 U.S.C. 7443A(d)",
    "fixture": "tax_special_trial_26_usc_7443A_govinfo2024.html",
    "court": None,
    "subject": "every special trial judge of the U.S. Tax Court",
    "subsection": "(d) Salary",
    "tier": "district judges",
    "percentOf": 90,
    "percentOfWhat": "a Tax Court judge's salary, which 26 U.S.C. 7443(c)(1) sets at a district judge's",
    "quote": SPECIAL_TRIAL_JUDGE_QUOTE,
    "via": {
        "citation": "26 U.S.C. 7443(c)(1)",
        "fixture": "tax_court_26_usc_7443.html",
        "subject": "every judge of the U.S. Tax Court",
        "quote": PARITY_PROVISIONS["jud-specialized-tax-chief-judge-tax-court"]["quote"],
    },
}
PARITY_PROVISIONS["jud-support-aousc-deputy-director"] = {
    "citation": "28 U.S.C. 603",
    "fixture": "aousc_28_usc_603.html",
    "court": None,
    "subject": "the Deputy Director of the Administrative Office of the United States Courts",
    "subsection": "Salaries",
    "tier": "district judges",
    "percentOf": 92,
    "percentOfWhat": "the Director's salary, which the same section sets at a district judge's",
    "quote": (AO_DIRECTOR_QUOTE, AO_DEPUTY_QUOTE),
}
PARITY_PROVISIONS["jud-support-fjc-deputy-director"] = {
    "citation": "28 U.S.C. 626",
    "fixture": "fjc_28_usc_626.html",
    "court": None,
    "subject": "the Deputy Director of the Federal Judicial Center",
    "subsection": "Compensation of the Director and Deputy Director",
    "tier": "district judges",
    "percentOf": 92,
    "percentOfWhat": (
        "the Administrative Office Deputy Director's salary, which 28 U.S.C. 603 sets at 92 percent of a "
        "Director paid as a district judge"
    ),
    "quote": FJC_DEPUTY_QUOTE,
    "via": {
        "citation": "28 U.S.C. 603",
        "fixture": "aousc_28_usc_603.html",
        "subject": "the Deputy Director of the Administrative Office of the United States Courts",
        "quote": (AO_DIRECTOR_QUOTE, AO_DEPUTY_QUOTE),
    },
}

#: The Chair of the United States Sentencing Commission, since 2026-10-06 (the
#: twelfth research batch's judiciary cluster): 28 U.S.C. 992(c) pays "The
#: Chair and Vice Chairs of the Commission" at "the annual rate at which judges
#: of the United States courts of appeals are compensated" -- an office row in
#: the AO Director's shape, at the CIRCUIT-judge tier, read from GPO's 2024
#: edition on www.govinfo.gov. The Commission's `Commissioner (×6)` bench is
#: NOT priced (see `NOT_PRICED`): the same subsection pays the Vice Chairs the
#: annual rate and the other voting members "at the daily rate at which judges
#: of the United States courts of appeals are compensated", so one annual
#: figure for the bench would be false of some of its members. The three Vice
#: Chairs have no nodes of their own in this graph.
USSC_CHAIR_QUOTE = (
    "The Chair and Vice Chairs of the Commission shall hold full-time positions and shall be compensated "
    "during their terms of office at the annual rate at which judges of the United States courts of appeals "
    "are compensated."
)
PARITY_PROVISIONS["jud-support-ussc-chair-ussc"] = {
    "citation": "28 U.S.C. 992(c)",
    "fixture": "ussc_28_usc_992_govinfo2024.html",
    "court": None,
    "subject": "the Chair of the United States Sentencing Commission",
    "subsection": "(c)",
    "tier": "circuit judges",
    "quote": USSC_CHAIR_QUOTE,
}

#: The magistrate judges, since 2026-10-06 (the owner's decision): a CEILING
#: the compensation table's own page resolves. 28 U.S.C. 634(a) pays
#: full-time magistrate judges "up to an annual rate equal to 92 percent of
#: the salary of a judge of the district court", fixed by the Judicial
#: Conference -- so the statute alone states no rate, and these two rows were
#: in `NOT_PRICED` for exactly that reason. The Administrative Office's own
#: Judicial Compensation page prints, beneath the table this module prices
#: from: "By statute, the salary of a bankruptcy or magistrate judge is equal
#: to 92 percent of the salary of a district judge." That is the document
#: stating what the Conference fixed under the ceiling, so the row carries it
#: as `basisQuote`, `build_records` refuses the row unless the page still
#: prints that sentence, the block publishes it as `ceilingBasis` with the
#: reading in words, and the gate mirrors it by node id. The statute quote
#: stops at "section 135" as the bankruptcy quote does; the part-time clause
#: that follows it (between $100 and half the full-time maximum) is named in
#: the reading, because the AO's sentence states the salary without that
#: qualification and the figure is the full-time one.
MAGISTRATE_JUDGE_QUOTE = (
    "Officers appointed under this chapter shall receive, as full compensation for their services, salaries to "
    "be fixed by the conference pursuant to section 633, at rates for full-time United States magistrate judges "
    "up to an annual rate equal to 92 percent of the salary of a judge of the district court of the United "
    "States, as determined pursuant to section 135"
)
MAGISTRATE_BASIS_QUOTE = (
    "By statute, the salary of a bankruptcy or magistrate judge is equal to 92 percent of the salary of a "
    "district judge."
)
MAGISTRATE_BASIS_READING = (
    "28 U.S.C. 634(a) sets a CEILING, not a rate: full-time magistrate judges' salaries are fixed by the "
    "Judicial Conference \"up to\" 92 percent of a district judge's, and part-time magistrate judges are paid "
    "between $100 and half the full-time maximum. The Administrative Office's own Judicial Compensation page, "
    "the document this figure's tier is read from, states beneath its table that the salary \"is equal to 92 "
    "percent of the salary of a district judge\", which is what the Conference fixed under that ceiling; the "
    "figure is published on that sentence and is the full-time salary."
)
for _node_id, _subject in (
    ("jud-district-sdny-magistrate-judge-13", "every full-time magistrate judge of the Southern District of New York"),
    ("jud-district-structure-magistrate-judge-varies", "every full-time magistrate judge, in every district"),
):
    PARITY_PROVISIONS[_node_id] = {
        "citation": "28 U.S.C. 634(a)",
        "fixture": "magistrate_judges_28_usc_634.html",
        "court": None,
        "subject": _subject,
        "subsection": "(a)",
        "tier": "district judges",
        "percentOf": 92,
        "percentOfWhat": (
            "a district judge's salary -- the ceiling 28 U.S.C. 634(a) sets, which the Administrative Office's own "
            "Judicial Compensation page states the salary is equal to"
        ),
        "quote": MAGISTRATE_JUDGE_QUOTE,
        "basisQuote": MAGISTRATE_BASIS_QUOTE,
        "basisReading": MAGISTRATE_BASIS_READING,
    }

#: The hosts a statute may be read from, and the publisher each one is. The
#: Office of the Law Revision Counsel's prelim edition is the first choice;
#: the Government Publishing Office's annual edition is the same text as of
#: its edition year, read when the first host is down. Mirrored in the gate.
STATUTE_HOSTS = ("uscode.house.gov", "www.govinfo.gov")


def statute_publisher(url: str, final_url: str = "") -> tuple[str, str]:
    """(publisher, edition words) for a committed statute's URL. A fetch made
    through govinfo's link service records the link as `url` and the dated
    granule it resolved to as `final_url`; the edition is read off whichever
    carries the package id."""
    if "www.govinfo.gov" in url:
        match = re.search(r"USCODE-(\d{4})", url) or re.search(r"USCODE-(\d{4})", str(final_url or ""))
        edition = f"{match.group(1)} edition of the United States Code" if match else "an edition of the United States Code"
        return ("U.S. Government Publishing Office", edition)
    return ("Office of the Law Revision Counsel, U.S. House of Representatives", "current through the prelim edition")


def quote_parts(quote: Any) -> list[str]:
    """A provision's quote as its sentences, whitespace collapsed: a string is
    one sentence, a tuple is several from one section."""
    if isinstance(quote, (list, tuple)):
        return [_collapse(str(part)) for part in quote]
    return [_collapse(str(quote))]


def joined_quote(quote: Any) -> str:
    return " … ".join(quote_parts(quote))


#: The same four provisions reach each court's bench node -- "Judge (×18)",
#: "(×15)", "(×4)", "(×8)" -- because each says "Each judge", and a tier rate
#: holds for every holder alike. Refused until 2026-09-23 under the blanket
#: multi-post rule; the owner asked for them, and the sweep now keeps an
#: office-rate claim on a multi-post node with a `holders` block saying it is
#: each judge's rate and not one judge's. The Court of Federal Claims' "Senior
#: Judge (×multiple)" is NOT here: a senior judge's pay there is 28 U.S.C.
#: 178, which this repository has not read.
BENCH_NODES = {
    "jud-specialized-tax-judge-18": "jud-specialized-tax-chief-judge-tax-court",
    "jud-specialized-claims-judge-15": "jud-specialized-claims-chief-judge-cfc",
    "jud-specialized-caaf-judge-4": "jud-specialized-caaf-chief-judge-caaf",
    "jud-specialized-cavc-judge-8": "jud-specialized-cavc-chief-judge-cavc",
}
for _bench, _chief in BENCH_NODES.items():
    PARITY_PROVISIONS[_bench] = dict(PARITY_PROVISIONS[_chief])

#: Read, and deliberately not priced, with the reason. Kept as data so the
#: derive step can print it and a reviewer can see each is a decision.
NOT_PRICED = {
    # The two magistrate benches sat here until 2026-10-06 ("a ceiling and not
    # a rate ... no document here states what the Conference fixed"); the
    # Administrative Office's own page does, and they are priced above.
    "jud-support-ussc-commissioner-6": (
        "28 U.S.C. 992(c) pays the Commission's Chair and Vice Chairs at the annual rate of a judge of the "
        "courts of appeals and its other voting members \"at the daily rate at which judges of the United "
        "States courts of appeals are compensated\"; this bench of six bundles the three Vice Chairs at the "
        "annual rate with members paid by the day, so one annual figure would be false of some of its holders"
    ),
    "jud-specialized-intl-trade-chief-judge-cit": (
        "28 U.S.C. 252 states no parity: it sets the rate by reference to section 225 of the "
        "Federal Salary Act of 1967 as adjusted by 28 U.S.C. 461, a chain through documents "
        "this project has not read"
    ),
}

#: The sentence 38 U.S.C. 7253's Amendments note prints as the section's prior
#: text. It is on the page and it is not the law, and a module that found its
#: quotes by searching the whole page would price the CAVC's chief judge at the
#: circuit rate on the strength of it. Pinned absent from the operative text.
REPEALED_CAVC_CHIEF_JUDGE_TEXT = (
    "The chief judge of the Court shall receive a salary at the same rate as is received by "
    "judges of the United States Courts of Appeals."
)


class Unreadable(Exception):
    """A committed section is not the section this module was written against."""


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def operative_text(raw_html: str) -> str:
    """The section's own text: everything from its `SS<number>.` heading to the
    first publisher's-note heading, whitespace collapsed.

    Cutting at the notes is the whole guard. uscode.house.gov prints a
    section's repealed text, its amendment history and decades of superseded
    salary figures beneath the law, all in the same prose, and a quote found
    only there is a quote of something that is no longer in force.
    """
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", raw_html)
    text = _collapse(html_module.unescape(re.sub(r"<[^>]+>", " ", text)))
    # Up to two letters: 42 U.S.C. 2000ee (the Privacy and Civil Liberties
    # Oversight Board) is a real section number, and the first version of
    # this pattern admitted one letter and refused its heading.
    start = re.search(r"§\s?\d+[A-Za-z]{0,2}(?:[-\u2013]\d+)?\.", text)
    if start is None:
        raise Unreadable("the page carries no section heading")
    body = text[start.start() :]
    cuts = [body.find(heading) for heading in NOTE_HEADINGS]
    cuts = [cut for cut in cuts if cut > 0]
    if not cuts:
        raise Unreadable("the page carries no notes heading, so the law cannot be separated from the history")
    return body[: min(cuts)].strip()


def load_section(fixture: str) -> dict[str, Any]:
    """One committed section, with the digest recomputed from the bytes -- the
    refusal `pay_tables` makes -- and its operative text separated out."""
    path = FIXTURE_DIR / fixture
    meta_path = path.with_name(path.name + ".meta.json")
    if not meta_path.exists():
        raise Unreadable(f"{path.name} has no .meta.json beside it; an undated fetch cannot be cited")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    recorded = str(meta.get("sha256") or "").lower()
    if not recorded:
        raise Unreadable(f"{meta_path.name} records no sha256")
    if digest != recorded:
        raise Unreadable(
            f"{path.name} does not match the digest its fetch recorded ({digest} vs {recorded}); "
            "the committed file is not the file that was served"
        )
    url = str(meta.get("url") or "")
    fetched_at = str(meta.get("fetched_at") or "")
    if not url or not fetched_at:
        raise Unreadable(f"{meta_path.name} is missing the url or the fetch time")
    if meta.get("error") or int(meta.get("status") or 0) != 200:
        raise Unreadable(f"{meta_path.name} records a fetch that did not serve the page")
    decoded = raw.decode("utf-8", errors="replace")
    return {
        "file": str(path),
        "url": url,
        # govinfo's link service redirects to the dated edition's granule; the
        # address that served the bytes is what names the edition.
        "final_url": str(meta.get("final_url") or url),
        "fetched_at": fetched_at,
        "sha256": digest,
        "operative": operative_text(decoded),
        "whole": _collapse(html_module.unescape(re.sub(r"<[^>]+>", " ", decoded))),
    }


def load_pay_evidence(path: str | Path = DEFAULT_PAY_EVIDENCE_PATH) -> dict[str, dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        loaded = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    nodes = loaded.get("nodes") if isinstance(loaded, dict) else None
    return nodes if isinstance(nodes, dict) else {}


def page_text(raw_html: str) -> str:
    """A page's whole readable text: tags stripped, entities unescaped,
    whitespace collapsed. What a provision's `basisQuote` is re-found in --
    the compensation page's Explanatory Notes sit outside its table, so the
    table parser's rows cannot carry them."""
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", raw_html)
    return _collapse(html_module.unescape(re.sub(r"<[^>]+>", " ", text)))


def compensation_page_text(html_path: str | Path) -> str:
    """The committed Judicial Compensation page's text, read from the same
    bytes `judicial_pay.load_judicial_compensation` has just vouched for."""
    return page_text(Path(html_path).read_text(encoding="utf-8", errors="replace"))


def build_records(
    node_map: Mapping[str, Mapping[str, Any]],
    compensation: Mapping[str, Any],
    *,
    table_url: str,
    table_sha256: str,
    table_retrieved_at: str,
    table_text: str | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """One record per parity provision whose quote is still in its section's
    operative text and whose tier the compensation table still prices.

    `table_text` is the compensation page's own text (`compensation_page_text`);
    a provision carrying a `basisQuote` -- the magistrate judges, whose statute
    states a ceiling the page's own sentence resolves -- is refused unless that
    sentence is still printed there. A caller that passes no page text prices
    no such row: the sentence is half of what the claim rests on."""
    year = str(compensation.get("year") or "")
    tiers = compensation.get("tiers") or {}
    header = str(compensation.get("headerText") or "")
    row = str(compensation.get("rowText") or "")
    if not year or not tiers or not row:
        raise Unreadable("the judicial compensation table carries no priced year")
    table_quote = _collapse(f"{header}; {row}")

    records: dict[str, dict[str, Any]] = {}
    refusals: dict[str, str] = {}
    sections: dict[str, dict[str, Any]] = {}

    for node_id, provision in sorted(PARITY_PROVISIONS.items()):
        section = sections.get(provision["fixture"])
        if section is None:
            section = load_section(provision["fixture"])
            sections[provision["fixture"]] = section
        missing = [part for part in quote_parts(provision["quote"]) if part not in section["operative"]]
        if missing:
            # Never fall back to the whole page. If the sentence is only in
            # the notes it is repealed text, which is the exact way the
            # research this was built from got the CAVC wrong.
            where = "only in the publisher's notes" if missing[0] in section["whole"] else "nowhere on the page"
            refusals[node_id] = f"{provision['citation']} no longer carries the quoted sentence ({where})"
            continue
        quote = joined_quote(provision["quote"])
        via = provision.get("via")
        via_section = None
        via_quote = ""
        if via:
            via_section = sections.get(via["fixture"])
            if via_section is None:
                via_section = load_section(via["fixture"])
                sections[via["fixture"]] = via_section
            via_missing = [part for part in quote_parts(via["quote"]) if part not in via_section["operative"]]
            if via_missing:
                where = "only in the publisher's notes" if via_missing[0] in via_section["whole"] else "nowhere on the page"
                refusals[node_id] = f"{via['citation']} no longer carries the quoted sentence ({where})"
                continue
            via_quote = joined_quote(via["quote"])
        basis_quote = _collapse(str(provision.get("basisQuote") or ""))
        if basis_quote:
            # A ceiling is resolved only by the page's own sentence, re-found
            # now; a page that no longer prints it leaves the statute's "up
            # to" standing alone, which prices nothing.
            if table_text is None:
                refusals[node_id] = (
                    f"{provision['citation']} states a ceiling and the compensation page's text was not supplied, "
                    "so the sentence that resolves it could not be re-found"
                )
                continue
            if basis_quote not in table_text:
                refusals[node_id] = (
                    f"{provision['citation']} states a ceiling and the Judicial Compensation page no longer prints "
                    "the sentence that resolved it"
                )
                continue
        tier = tiers.get(provision["tier"])
        if not tier:
            refusals[node_id] = f"the compensation table does not price {provision['tier']!r} for {year}"
            continue
        node = node_map.get(node_id)
        if node is None:
            refusals[node_id] = "node not in the graph"
            continue
        if str(node.get("type") or "").casefold() != "position":
            refusals[node_id] = "not a position"
            continue
        # A bench node ("Judge (×18)") is priced: "Each judge" is paid the
        # tier rate, and `pay_tables.withdraw_pay_from_multi_post_nodes`
        # stamps `holders` on it after the counts are annotated.

        tier_label = provision["tier"].title()
        via_text = (
            f"· {via['citation']}: “{via_quote}” " if via else ""
        )
        percent_of = provision.get("percentOf")
        base_amount = float(tier["amount"])
        percent_of_what = provision.get("percentOfWhat") or "a district judge's"
        if percent_of:
            amount = round(base_amount * percent_of / 100.0, 2)
            amount_raw = "{:,.0f}".format(amount) if float(amount).is_integer() else "{:,.2f}".format(amount)
            rate_text = "${}".format(amount_raw)
            arithmetic = {
                "operation": "percent_of",
                "baseAmount": base_amount,
                "baseAmountRaw": str(tier["amountRaw"]),
                "baseText": str(tier["rateText"]),
                "baseTier": provision["tier"],
                "percent": int(percent_of),
                "result": amount,
                "resultText": rate_text,
                "note": (
                    (
                        f"No document prints {rate_text}. {provision['citation']} caps the rate at {percent_of} percent "
                        f"of {percent_of_what}, the Judicial Compensation page states the salary is equal to that "
                        f"percentage, and Judicial Compensation {year} prints {tier['rateText']} for {tier_label}; "
                        "the figure is that arithmetic and nothing more."
                    ) if basis_quote else (
                        f"No document prints {rate_text}. {provision['citation']} sets the rate at {percent_of} percent "
                        f"of {percent_of_what}, and Judicial Compensation {year} "
                        f"prints {tier['rateText']} for {tier_label}; the figure is that arithmetic and nothing more."
                    )
                ),
            }
            arithmetic_text = f" × {percent_of}% = {rate_text}"
        else:
            amount = base_amount
            amount_raw = tier["amountRaw"]
            rate_text = tier["rateText"]
            arithmetic = None
            arithmetic_text = ""
        basis_text = (
            f"· Judicial Compensation {year}, Explanatory Notes: “{basis_quote}” " if basis_quote else ""
        )
        derivation = (
            f"{provision['citation']} {provision['subsection']}: “{quote}” "
            f"{via_text}"
            f"{basis_text}"
            f"· Judicial Compensation {year}: {tier_label} {tier['rateText']}{arithmetic_text}"
        )
        ceiling_basis = {
            "quote": basis_quote,
            "reading": _collapse(str(provision.get("basisReading") or "")),
            "citation": f"Judicial Compensation, {year}, Explanatory Notes",
            "publisher": "Administrative Office of the United States Courts",
            "url": table_url,
            "documentSha256": table_sha256,
            "retrievedAt": table_retrieved_at,
            "statuteStatesACeiling": True,
        } if basis_quote else None
        publisher, edition = statute_publisher(section["url"], section.get("final_url", ""))
        documents = [
            {
                "role": (f"states the percentage of another office's pay this post is paid" if (via and percent_of)
                         else "states whose pay this post's equals" if via
                         else "caps this post's pay at a percentage of the tier, a ceiling the compensation page's own sentence resolves" if basis_quote
                         else f"states the percentage of the tier this post is paid at" if percent_of
                         else "states the tier this post is paid at"),
                "citation": provision["citation"],
                "publisher": publisher,
                "edition": edition,
                "title": f"{provision['citation']}, {edition}",
                "quote": quote,
                "url": section["url"],
                "documentSha256": section["sha256"],
                "retrievedAt": section["fetched_at"],
                "statesTheFigure": False,
            },
            *([{
                "role": "states the tier that office is paid at",
                "citation": via["citation"],
                "publisher": statute_publisher(via_section["url"], via_section.get("final_url", ""))[0],
                "edition": statute_publisher(via_section["url"], via_section.get("final_url", ""))[1],
                "title": f"{via['citation']}, {statute_publisher(via_section['url'], via_section.get('final_url', ''))[1]}",
                "quote": via_quote,
                "url": via_section["url"],
                "documentSha256": via_section["sha256"],
                "retrievedAt": via_section["fetched_at"],
                "statesTheFigure": False,
            }] if via else []),
            {
                "role": ("states what that tier pays, and in its Explanatory Notes that the salary is equal to the "
                         "percentage the statute caps it at" if basis_quote else "states what that tier pays"),
                "citation": f"Judicial Compensation, {year}",
                "publisher": "Administrative Office of the United States Courts",
                "title": "Judicial Compensation",
                "quote": table_quote,
                "url": table_url,
                "documentSha256": table_sha256,
                "retrievedAt": table_retrieved_at,
                "statesTheFigure": False,
            },
        ]
        records[node_id] = {
            "nodeId": node_id,
            "financialEvidenceStatus": "partial",
            "costBasis": "basic_pay",
            "amount": amount,
            "amountRaw": amount_raw,
            "units": "usd",
            "normalizedMultiplier": 1,
            # The mark is printed on the figure in the compensation table's own
            # row, which is what SCALE_PRINTED_SOURCE_TYPES asks for.
            "unitsEvidence": table_quote,
            "quote": derivation,
            "fiscalYear": int(year),
            "periodCoverage": "annual_rate",
            "periodAsOf": f"{year}-01-01",
            "amountScope": f"{percent_of} percent of {tier_label}" if percent_of else tier_label,
            "percentOf": int(percent_of) if percent_of else None,
            "percentOfWhat": provision.get("percentOfWhat") if percent_of else None,
            "arithmetic": arithmetic,
            # The sentence of the compensation page that resolves a statutory
            # ceiling, where the row rests on one; None on every other row.
            "ceilingBasis": ceiling_basis,
            # Never "exact", and not for the usual reason alone: no document
            # here states this figure for this post at all.
            "scopeMatch": "proxy",
            "rollupRole": "line",
            "sourceType": PAY_SOURCE_TYPE,
            # The statute is the record's citation: it is the half that names
            # THIS court. The table rides in `documents` beside it, and the
            # gate checks both.
            "sourceUrl": section["url"],
            "documentSha256": section["sha256"],
            "retrievedAt": section["fetched_at"],
            "locator": {"section": provision["citation"], "subsection": provision["subsection"]},
            "court": provision.get("court"),
            "subject": provision.get("subject") or f"every judge of {provision.get('court')}",
            "statute": provision["citation"],
            "statuteQuote": quote,
            "viaStatute": via["citation"] if via else None,
            "viaQuote": via_quote or None,
            "seatTier": provision["tier"],
            "year": year,
            "rateText": rate_text,
            "derivation": derivation,
            "documents": documents,
            "tableUrl": table_url,
            "tableSha256": table_sha256,
            "tableRetrievedAt": table_retrieved_at,
        }

    report = {
        "source": PAY_SOURCE,
        "year": year,
        "tableUrl": table_url,
        "tableSha256": table_sha256,
        "tableRetrievedAt": table_retrieved_at,
        "sections": {
            name: {"url": section["url"], "sha256": section["sha256"], "fetched_at": section["fetched_at"]}
            for name, section in sorted(sections.items())
        },
        "considered": len(PARITY_PROVISIONS),
        "priced": len(records),
        "documentsPerRecord": {
            node_id: len(record["documents"]) for node_id, record in sorted(records.items())
        },
        "documentsStatingTheFigure": 0,
        "documentStrengthPercent": {
            str(count): document_strength_percent(count)
            for count in sorted({len(record["documents"]) for record in records.values()})
        },
        "strengthScale": STRENGTH_SCALE,
        "refused": dict(sorted(refusals.items())),
        "notPriced": dict(sorted(NOT_PRICED.items())),
        "repealedTextRefused": REPEALED_CAVC_CHIEF_JUDGE_TEXT,
        "ceilingBasisRows": sorted(
            node_id for node_id, record in records.items() if isinstance(record.get("ceilingBasis"), dict)
        ),
    }
    return records, report


def apply_pay_evidence(
    root: dict[str, Any],
    records: Mapping[str, Mapping[str, Any]],
    *,
    index_tree: Any = None,
) -> dict[str, Any]:
    """Stamp `positionDerivedPay` on the Article I chief judges and benches,
    and on the two judicial-branch office holders whose statutes pay them at a
    judge's rate.

    Its own field rather than `positionStatutoryPay`, for the reason
    `statutory_schedule.py` gives for not widening `positionPayRate`: that
    field's records are each one document's own printed figure, and folding a
    derivation into it would mean loosening a gate check that already guards
    published records in order to make a weaker claim easier to publish. A
    node another source has already priced is left alone -- there is no such
    node today, and the rule is what keeps a derived figure from ever
    displacing a printed one.
    """
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, _ = index_tree(root)
    stats = {
        "priced": 0,
        "unknown_node": 0,
        "not_a_position": 0,
        "already_priced_by_another_source": 0,
    }
    for node_id, record in sorted(records.items()):
        node = node_map.get(node_id)
        if node is None:
            stats["unknown_node"] += 1
            continue
        if str(node.get("type") or "").casefold() != "position":
            stats["not_a_position"] += 1
            continue
        if isinstance(node.get("positionStatutoryPay"), dict) or isinstance(node.get("positionPayRate"), dict):
            stats["already_priced_by_another_source"] += 1
            continue
        documents = [dict(document) for document in record.get("documents") or []]
        node["positionDerivedPay"] = {
            "source": PAY_SOURCE,
            "sourceLabel": "a statutory parity provision joined to the U.S. Courts' Judicial Compensation table",
            "method": PAY_METHOD,
            "amount": record.get("amount"),
            "rateText": record.get("rateText"),
            "year": record.get("year"),
            "effective": record.get("periodAsOf"),
            "costBasis": record.get("costBasis"),
            "scopeMatch": record.get("scopeMatch"),
            "financialEvidenceStatus": record.get("financialEvidenceStatus"),
            "amountScope": record.get("amountScope"),
            "seatTier": record.get("seatTier"),
            "statute": record.get("statute"),
            "statuteQuote": record.get("statuteQuote"),
            "court": record.get("court"),
            "subject": record.get("subject"),
            "viaStatute": record.get("viaStatute"),
            "viaQuote": record.get("viaQuote"),
            "percentOf": record.get("percentOf"),
            "percentOfWhat": record.get("percentOfWhat"),
            "arithmetic": dict(record["arithmetic"]) if isinstance(record.get("arithmetic"), dict) else None,
            "ceilingBasis": dict(record["ceilingBasis"]) if isinstance(record.get("ceilingBasis"), dict) else None,
            "derivation": record.get("derivation"),
            "quote": record.get("quote"),
            "documents": documents,
            "url": str(record.get("sourceUrl") or ""),
            "tableUrl": str(record.get("tableUrl") or ""),
            "checkedAt": record.get("retrievedAt"),
            # `verification` -- the document count, the percentage and the
            # sentence saying what the percentage does not measure -- is
            # stamped by `pay_documents.annotate_pay_documents`, which reads
            # the count off `documents` here and does the same for every other
            # pay field. One code path for one number: a second copy of the
            # arithmetic living in this module is how the two would drift.
        }
        stats["priced"] += 1
        # Deliberately not written: sourceUrls, sourceTypes, lastVerified,
        # verificationMethod -- see `judicial_pay.apply_pay_evidence`.
    return stats
