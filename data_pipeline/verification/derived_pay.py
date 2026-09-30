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
trade-chief-judge-cit` stays unpriced and the section is committed anyway,
because "nobody looked" and "looked and it states no parity" are different
facts.

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
    "jud-district-sdny-magistrate-judge-13": (
        "28 U.S.C. 634(a) sets full-time magistrate judges' salaries \"at rates ... up to an annual rate "
        "equal to 92 percent of the salary of a judge of the district court\", fixed by the Judicial "
        "Conference: a ceiling and not a rate, and part-time magistrate judges are paid between $100 and "
        "half the full-time maximum; no document here states what the Conference fixed"
    ),
    "jud-district-structure-magistrate-judge-varies": (
        "28 U.S.C. 634(a) sets full-time magistrate judges' salaries \"at rates ... up to an annual rate "
        "equal to 92 percent of the salary of a judge of the district court\", fixed by the Judicial "
        "Conference: a ceiling and not a rate, and part-time magistrate judges are paid between $100 and "
        "half the full-time maximum; no document here states what the Conference fixed"
    ),
    "jud-support-aousc-deputy-director": (
        "28 U.S.C. 603 sets the Deputy Director's salary at 92 percent of the Director's: arithmetic on "
        "a figure that is itself a join (the Director's, equal to a district judge's by the same section), "
        "which this field does not publish -- unlike 28 U.S.C. 153(a)'s bankruptcy judges, whose 92 "
        "percent is taken of the table's own printed figure"
    ),
    "jud-support-fjc-deputy-director": (
        "28 U.S.C. 626 sets the Deputy Director's compensation at the Administrative Office Deputy "
        "Director's, which 28 U.S.C. 603 sets at 92 percent of that Director's: two hops and arithmetic "
        "on a figure that is itself a join, which this field does not publish"
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
    start = re.search(r"§\s?\d+[A-Za-z]?(?:[-\u2013]\d+)?\.", text)
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


def build_records(
    node_map: Mapping[str, Mapping[str, Any]],
    compensation: Mapping[str, Any],
    *,
    table_url: str,
    table_sha256: str,
    table_retrieved_at: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """One record per parity provision whose quote is still in its section's
    operative text and whose tier the compensation table still prices."""
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
        quote = _collapse(provision["quote"])
        if quote not in section["operative"]:
            # Never fall back to the whole page. If the sentence is only in
            # the notes it is repealed text, which is the exact way the
            # research this was built from got the CAVC wrong.
            where = "only in the publisher's notes" if quote in section["whole"] else "nowhere on the page"
            refusals[node_id] = f"{provision['citation']} no longer carries the quoted sentence ({where})"
            continue
        via = provision.get("via")
        via_section = None
        via_quote = ""
        if via:
            via_section = sections.get(via["fixture"])
            if via_section is None:
                via_section = load_section(via["fixture"])
                sections[via["fixture"]] = via_section
            via_quote = _collapse(via["quote"])
            if via_quote not in via_section["operative"]:
                where = "only in the publisher's notes" if via_quote in via_section["whole"] else "nowhere on the page"
                refusals[node_id] = f"{via['citation']} no longer carries the quoted sentence ({where})"
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
                    f"No document prints {rate_text}. {provision['citation']} sets the rate at {percent_of} percent "
                    f"of a district judge's, and Judicial Compensation {year} prints {tier['rateText']} for "
                    f"{tier_label}; the figure is that arithmetic and nothing more."
                ),
            }
            arithmetic_text = f" × {percent_of}% = {rate_text}"
        else:
            amount = base_amount
            amount_raw = tier["amountRaw"]
            rate_text = tier["rateText"]
            arithmetic = None
            arithmetic_text = ""
        derivation = (
            f"{provision['citation']} {provision['subsection']}: “{quote}” "
            f"{via_text}"
            f"· Judicial Compensation {year}: {tier_label} {tier['rateText']}{arithmetic_text}"
        )
        documents = [
            {
                "role": ("states whose pay this post's equals" if via
                         else f"states the percentage of the tier this post is paid at" if percent_of
                         else "states the tier this post is paid at"),
                "citation": provision["citation"],
                "publisher": "Office of the Law Revision Counsel, U.S. House of Representatives",
                "title": f"{provision['citation']}, current through the prelim edition",
                "quote": quote,
                "url": section["url"],
                "documentSha256": section["sha256"],
                "retrievedAt": section["fetched_at"],
                "statesTheFigure": False,
            },
            *([{
                "role": "states the tier that office is paid at",
                "citation": via["citation"],
                "publisher": "Office of the Law Revision Counsel, U.S. House of Representatives",
                "title": f"{via['citation']}, current through the prelim edition",
                "quote": via_quote,
                "url": via_section["url"],
                "documentSha256": via_section["sha256"],
                "retrievedAt": via_section["fetched_at"],
                "statesTheFigure": False,
            }] if via else []),
            {
                "role": "states what that tier pays",
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
            "arithmetic": arithmetic,
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
            "arithmetic": dict(record["arithmetic"]) if isinstance(record.get("arithmetic"), dict) else None,
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
