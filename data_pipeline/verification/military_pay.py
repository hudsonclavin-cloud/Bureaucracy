"""Military basic pay, from Schedule 8 of the annual pay-adjustment order joined
to the statute that fixes a post's GRADE.

## The document was already in the repository

`tests/fixtures/dfas/README.md` records that every host publishing the
uniformed-services basic-pay table -- dfas.mil, militarypay.defense.gov,
comptroller.defense.gov, the service hosts, the Coast Guard's -- answers
`robots.txt` and the page itself with an Akamai 403, and the twelfth research
batch re-measured the same refusal. What the batch found instead is that the
table had been committed since 2026-09-23 without anybody reading it: the note
to 5 U.S.C. 5332 (`tests/fixtures/uscode/pay_schedules_5_usc_5332.html`), from
which `us_code_pay_schedules.py` prices Schedules 5, 6 and 7, reproduces
Executive Order 14368 in full -- and Schedule 8, "Pay of the Uniformed Services
(Effective January 1, 2026)", is the monthly basic-pay table itself, every
officer, warrant and enlisted row with its footnotes. That parser reads only
the three schedules it was written for (`if number not in ("5", "6", "7")`),
and this module reads the fourth from the same bytes, under the same digest.

## Two routes, both from Schedule 8

**A grade fixed by statute.** Title 10 and Title 14 fix the grade of a few
posts in so many words: "The Chief of Staff, while so serving, has the grade of
general without vacating his permanent grade" (10 U.S.C. 7033(b)); "The
Commandant while so serving shall have the grade of admiral" (14 U.S.C. 302).
37 U.S.C. 201(a)(1) assigns "General" and "Admiral" to pay grade O-10 for the
purpose of computing basic pay, and Schedule 8's O-10 row prints $18,999.90 in
every one of its eleven populated columns. So the figure is a three-document
join -- the grade statute, the pay-grade table, the schedule -- and **no
document states an annual figure for the post**: Schedule 8 prints MONTHLY
rates ("part i-monthly basic pay"), and the annual figure this module
publishes is twelve times the monthly one, arithmetic carried in the open
exactly as the Inspector General Act's 3 percent is. Seventeen posts are
reviewed rows here, keyed by node id (`GRADE_PROVISIONS`): the Chairman and
Vice Chairman of the Joint Chiefs, the Chief of the National Guard Bureau, the
chief and vice chief of each of the five services, the Commandant and Vice
Commandant of the Coast Guard, and the two combatant commanders whose grade a
statute fixes (10 U.S.C. 167(c) and 167b(c)). The other nine combatant
commanders are refused: 10 U.S.C. 164 fixes no grade, theirs comes from a
presidential designation under 10 U.S.C. 601(a) that names no post, and
Schedule 8's footnote names them only as subject to the Level II CEILING.

**A post named in the schedule's own footnote.** The enlisted footnote states
a single RATE for seven posts by title: "For noncommissioned officers serving
as Sergeant Major of the Army, Master Chief Petty Officer of the Navy or Coast
Guard, Chief Master Sergeant of the Air Force, Sergeant Major of the Marine
Corps, Chief Master Sergeant of the Space Force, Senior Enlisted Advisor to
the Chairman of the Joint Chiefs of Staff, or Senior Enlisted Advisor to the
Chief of the National Guard Bureau, basic pay for this grade is $11,166.90 per
month, regardless of cumulative years of service". One document names the
office and prints its monthly figure. Matching is canonical-key EQUALITY
between a listed title and exactly one position node in the graph, and the one
printed item that names two offices at once -- "Master Chief Petty Officer of
the Navy or Coast Guard" -- is read as both by a rule declared once
(`_NAVY_OR_COAST_GUARD`), with the whole printed item quoted on the record. The
graph's generic "Senior Enlisted Advisor" under the Space Force was not priced
until 2026-10-07: the footnote prints "Chief Master Sergeant of the Space
Force", and the two are not equal. On the owner's decision the node was
renamed to the footnote's title by `scripts/rename_posts_to_printed_titles.py`
(`data/curation/post_renames.json`, a reviewed row re-checked against this
footnote on every run), and this route now reaches it by plain equality like
the other five. Which office the generic curated title stood for is the
owner's identification, recorded on the row; no document here states it.

## A row must be flat before one figure may stand for it

Schedule 8 prices by grade AND years of service; most rows rise across their
columns. A grade is priced here only when every populated cell of its row
prints the same figure -- true of O-10 ($18,999.90 in all eleven cells, the
first eleven blank) and false of E-9, which is why the senior enlisted
advisers are priced from the footnote that names them and never from the E-9
row. A row that varies would be a range, and a range is not a rate.

## The $100 the document disagrees with itself about, recorded and not fixed

Footnote 1 to the officer table says basic pay for O-7 through O-10 "is
limited to the rate of basic pay for level II of the Executive Schedule in
effect during calendar year 2026, which is $18,899.90 per month"; the O-10 row
prints $18,999.90. The two differ by $100, and no other rendering of the order
reachable from here settles it (the Federal Register's plain text answers its
"Request Access" page; govinfo's rendering prints the schedules as "[GRAPHIC]
[TIFF OMITTED]"). This module publishes the ROW's figure for the grade, quotes
the footnote verbatim beside it with the discrepancy stated, and reconciles
nothing.

## Every rule the other pay modules keep

Office-rate class: a grade the statute fixes is the office's, so a bench node
would keep the figure with `holders` (none of the seventeen is one).
`scopeMatch: proxy`, `partial`, `documentsStatingTheFigure: 0` for the annual
figure, with the monthly figure's own standing stated beside it (`monthly`).
Nothing writes `sourceUrls`, `sourceTypes`, `lastVerified` or
`verificationMethod`. A node another pay source has already priced is left
alone. Every quote is checked against its section's OPERATIVE text, never the
whole page, for the reason `derived_pay.py` records.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from data_pipeline.exporter.build_graph import STATED_MULTIPLICITY, canonical_name_key, is_post_node
from data_pipeline.verification.derived_pay import (
    STRENGTH_SCALE,
    Unreadable,
    document_strength_percent,
    load_section,
    statute_publisher,
)
from data_pipeline.verification.us_code_pay_schedules import (
    DEFAULT_SCHEDULE_HTML,
    _visible_lines,
)

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "uscode"
DEFAULT_PAY_EVIDENCE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "verification" / "military_pay_evidence.json"
)

FIELD = "positionMilitaryPay"
PAY_SOURCE = "military_basic_pay_schedule"
PAY_SOURCE_TYPE = "military_basic_pay_schedule"
#: A statute fixes the grade, 37 U.S.C. 201 assigns it a pay grade, Schedule 8
#: prices the pay grade by the month; the annual figure is twelve months.
PAY_METHOD_GRADE = "grade_fixed_by_statute_joined_to_37_usc_201_and_schedule_8_monthly_basic_pay"
#: Schedule 8's own footnote names the post and prints its monthly rate.
PAY_METHOD_NAMED = "post_named_in_schedule_8_footnote_at_a_stated_monthly_rate"

SCHEDULE_NUMBER = "8"
SCHEDULE_TITLE = "Pay of the Uniformed Services"
SCHEDULE_LABEL = "Schedule 8 — Pay of the Uniformed Services"
PART_I_HEADING = "part i-monthly basic pay"
MONTHS_IN_A_YEAR = 12
ARITHMETIC_OPERATION = "monthly_times_12"

MAPPING_FIXTURE = "military_pay_grades_37_usc_201_govinfo2024.html"
MAPPING_CITATION = "37 U.S.C. 201(a)(1)"
SPACE_FORCE_MAPPING_CITATION = "37 U.S.C. 201(a)(2)"
#: The sentence 201(a)(2) prints for the Space Force, whose officers take the
#: Air Force's equivalent grade; quoted on the two Space Force rows.
SPACE_FORCE_MAPPING_QUOTE = (
    "For the purpose of computing their basic pay, commissioned officers of the Space Force are assigned "
    "to the pay grades in the table in paragraph (1) by grade or rank in the Air Force that is equivalent "
    "to the grade or rank in which such officers are serving in the Space Force."
)
#: pay grade -> the row of 37 U.S.C. 201(a)(1)'s table as the operative text
#: prints it (the first "O" is followed by an en dash and a U+2060 word joiner
#: in the publisher's HTML). Only the one grade a statute fixes for a post in
#: this graph; O-9 is parsed and deliberately not priced (see NOT_PRICED).
PAY_GRADE_ROWS = {
    "O-10": "O–⁠10 General Admiral",
}
#: The grade word a statute uses -> the pay grade 201(a)(1) assigns it.
GRADE_WORD_TO_PAY_GRADE = {
    "general": "O-10",
    "admiral": "O-10",
    "general or admiral": "O-10",
}

#: The one printed item of the enlisted footnote that names two offices at
#: once: "<title> of the Navy or Coast Guard" is read as "<title> of the Navy"
#: and "<title> of the Coast Guard". Declared once, quoted whole on the record,
#: mirrored by the gate.
_NAVY_OR_COAST_GUARD = re.compile(r"^(?P<title>.+) of the Navy or Coast Guard$")
_FOOTNOTE_OPEN = "For noncommissioned officers serving as "
_FOOTNOTE_RATE = re.compile(r"basic pay for this grade is (\$[\d,]+\.\d{2}) per month")
_CAP_FOOTNOTE_OPEN = "Basic pay is limited to the rate of basic pay for level II of the Executive Schedule"
_CAP_RATE = re.compile(r"which is (\$[\d,]+\.\d{2}) per month")
_MONEY = re.compile(r"^(\$?)([0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2})$")
_GRADE_LABEL = re.compile(r"^([OWE])[–-]⁠?(\d+E?)$")
_MARK = re.compile(r"^\d$")
_EFFECTIVE = re.compile(r"^\(Effective\b.*\)$", re.IGNORECASE)
_YEAR_IN_EFFECTIVE = re.compile(r"January\s+1,\s+(\d{4})", re.IGNORECASE)
_SECOND_BLOCK_HEAD = ("Over 20", "Over 22", "Over 24", "Over 26", "Over 28", "Over 30",
                      "Over 32", "Over 34", "Over 36", "Over 38", "Over 40")

#: The seventeen posts whose grade a section of Title 10 or Title 14 fixes in
#: so many words. `quote` is re-found in the section's operative text on every
#: run; `officeQuote`, where the grade sentence names the office only as "The
#: Chief of Staff", is the sentence of the same section that says which; the
#: node must still carry `nodeName`; `grade` is the statute's own word and
#: `GRADE_WORD_TO_PAY_GRADE` is what turns it into a row of 37 U.S.C. 201.
GRADE_PROVISIONS: dict[str, dict[str, Any]] = {
    "exec-dept-defense-jcs-chairman-of-the-joint-chiefs-of-staff-cjcs": {
        "nodeName": "Chairman of the Joint Chiefs of Staff (CJCS)",
        "office": "Chairman of the Joint Chiefs of Staff",
        "citation": "10 U.S.C. 152(c)",
        "fixture": "jcs_10_usc_152_govinfo2024.html",
        "subsection": "(c) Grade and Rank",
        "grade": "general or admiral",
        "quote": (
            "The Chairman, while so serving, holds the grade of general or, in the case of the Navy, admiral, "
            "and outranks all other officers of the armed forces."
        ),
    },
    "exec-dept-defense-jcs-vice-chairman-of-the-joint-chiefs-of-staff-vcjcs": {
        "nodeName": "Vice Chairman of the Joint Chiefs of Staff (VCJCS)",
        "office": "Vice Chairman of the Joint Chiefs of Staff",
        "citation": "10 U.S.C. 154(f)",
        "fixture": "jcs_10_usc_154_govinfo2024.html",
        "subsection": "(f) Grade and Rank",
        "grade": "general or admiral",
        "quote": (
            "The Vice Chairman, while so serving, holds the grade of general or, in the case of an officer of "
            "the Navy, admiral and outranks all other officers of the armed forces except the Chairman."
        ),
    },
    "exec-dept-defense-jcs-national-guard-bureau-chief": {
        "nodeName": "National Guard Bureau Chief",
        "office": "Chief of the National Guard Bureau",
        "citation": "10 U.S.C. 10502(e)(1)",
        "fixture": "ngb_10_usc_10502_govinfo2024.html",
        "subsection": "(e)(1)",
        "grade": "general",
        "quote": "The Chief of the National Guard Bureau shall be appointed to serve in the grade of general.",
    },
    "exec-dept-defense-army-chief-of-staff-of-the-army-4-star-general": {
        "nodeName": "Chief of Staff of the Army (4-star General)",
        "office": "Chief of Staff of the Army",
        "citation": "10 U.S.C. 7033(b)",
        "fixture": "army_10_usc_7033_govinfo2024.html",
        "subsection": "(b)",
        "grade": "general",
        "quote": "The Chief of Staff, while so serving, has the grade of general without vacating his permanent grade.",
        "officeQuote": "There is a Chief of Staff of the Army",
    },
    "exec-dept-defense-army-vice-chief-of-staff-of-the-army": {
        "nodeName": "Vice Chief of Staff of the Army",
        "office": "Vice Chief of Staff of the Army",
        "citation": "10 U.S.C. 7034(b)",
        "fixture": "army_10_usc_7034_govinfo2024.html",
        "subsection": "(b)",
        "grade": "general",
        "quote": (
            "The Vice Chief of Staff of the Army, while so serving, has the grade of general without vacating "
            "his permanent grade."
        ),
    },
    "exec-dept-defense-navy-chief-of-naval-operations-4-star-admiral": {
        "nodeName": "Chief of Naval Operations (4-star Admiral)",
        "office": "Chief of Naval Operations",
        "citation": "10 U.S.C. 8033(b)",
        "fixture": "navy_10_usc_8033_govinfo2024.html",
        "subsection": "(b)",
        "grade": "admiral",
        "quote": (
            "The Chief of Naval Operations, while so serving, has the grade of admiral without vacating his "
            "permanent grade."
        ),
    },
    "exec-dept-defense-navy-vice-chief-of-naval-operations": {
        "nodeName": "Vice Chief of Naval Operations",
        "office": "Vice Chief of Naval Operations",
        "citation": "10 U.S.C. 8035(b)",
        "fixture": "navy_10_usc_8035_govinfo2024.html",
        "subsection": "(b)",
        "grade": "admiral",
        "quote": (
            "The Vice Chief of Naval Operations, while so serving, has the grade of admiral without vacating "
            "his permanent grade."
        ),
    },
    "exec-dept-defense-marines-commandant-of-the-marine-corps-4-star-general": {
        "nodeName": "Commandant of the Marine Corps (4-star General)",
        "office": "Commandant of the Marine Corps",
        "citation": "10 U.S.C. 8043(b)",
        "fixture": "marines_10_usc_8043_govinfo2024.html",
        "subsection": "(b)",
        "grade": "general",
        "quote": (
            "The Commandant of the Marine Corps, while so serving, has the grade of general without vacating "
            "his permanent grade."
        ),
    },
    "exec-dept-defense-marines-assistant-commandant-of-the-marine-corps": {
        "nodeName": "Assistant Commandant of the Marine Corps",
        "office": "Assistant Commandant of the Marine Corps",
        "citation": "10 U.S.C. 8044(b)",
        "fixture": "marines_10_usc_8044_govinfo2024.html",
        "subsection": "(b)",
        "grade": "general",
        "quote": (
            "The Assistant Commandant of the Marine Corps, while so serving, has the grade of general without "
            "vacating his permanent grade."
        ),
    },
    "exec-dept-defense-af-chief-of-staff-of-the-air-force-4-star-general": {
        "nodeName": "Chief of Staff of the Air Force (4-star General)",
        "office": "Chief of Staff of the Air Force",
        "citation": "10 U.S.C. 9033(b)",
        "fixture": "af_10_usc_9033_govinfo2024.html",
        "subsection": "(b)",
        "grade": "general",
        "quote": "The Chief of Staff, while so serving, has the grade of general without vacating his permanent grade.",
        "officeQuote": "There is a Chief of Staff of the Air Force",
    },
    "exec-dept-defense-af-vice-chief-of-staff": {
        # The graph names this post bare; a row is keyed by id, so the
        # bare-title floor that governs page evidence does not apply.
        "nodeName": "Vice Chief of Staff",
        "office": "Vice Chief of Staff of the Air Force",
        "citation": "10 U.S.C. 9034(b)",
        "fixture": "af_10_usc_9034_govinfo2024.html",
        "subsection": "(b)",
        "grade": "general",
        "quote": (
            "The Vice Chief of Staff of the Air Force, while so serving, has the grade of general without "
            "vacating his permanent grade."
        ),
    },
    "exec-dept-defense-sf-chief-of-space-operations-4-star-general": {
        "nodeName": "Chief of Space Operations (4-star General)",
        "office": "Chief of Space Operations",
        "citation": "10 U.S.C. 9082(b)",
        "fixture": "sf_10_usc_9082_govinfo2024.html",
        "subsection": "(b)",
        "grade": "general",
        "quote": (
            "The Chief, while so serving, has the grade of general without vacating the permanent grade of "
            "the officer."
        ),
        "officeQuote": "There is a Chief of Space Operations",
        "spaceForce": True,
    },
    "exec-dept-defense-sf-vice-chief-of-space-operations": {
        "nodeName": "Vice Chief of Space Operations",
        "office": "Vice Chief of Space Operations",
        "citation": "10 U.S.C. 9083(b)",
        "fixture": "sf_10_usc_9083_govinfo2024.html",
        "subsection": "(b)",
        "grade": "general",
        "quote": (
            "The Vice Chief of Space Operations, while so serving, has the grade of general without vacating "
            "the permanent grade of the officer."
        ),
        "spaceForce": True,
    },
    "exec-dept-dhs-uscg-commandant-of-the-coast-guard-4-star-admiral": {
        "nodeName": "Commandant of the Coast Guard (4-star Admiral)",
        "office": "Commandant of the Coast Guard",
        "citation": "14 U.S.C. 302",
        "fixture": "uscg_14_usc_302_govinfo2024.html",
        "subsection": "(second sentence)",
        "grade": "admiral",
        "quote": "The Commandant while so serving shall have the grade of admiral.",
        "officeQuote": "one Commandant for a period of four years, who may be reappointed for further periods of four years, who shall act as Chief of the Coast Guard",
    },
    "exec-dept-dhs-uscg-vice-commandant": {
        "nodeName": "Vice Commandant",
        "office": "Vice Commandant of the Coast Guard",
        "citation": "14 U.S.C. 304",
        "fixture": "uscg_14_usc_304_govinfo2024.html",
        "subsection": "(first sentence)",
        "grade": "admiral",
        "quote": "The Vice Commandant shall, while so serving, have the grade of admiral with pay and allowances of that grade.",
    },
    "exec-dept-defense-cocom-ussocom-commander-ccdr-ussocom": {
        "nodeName": "Commander (CCDR), USSOCOM",
        "office": "Commander of the United States Special Operations Command",
        "citation": "10 U.S.C. 167(c)",
        "fixture": "socom_10_usc_167_govinfo2024.html",
        "subsection": "(c) Grade of Commander",
        "grade": "general or admiral",
        "quote": (
            "The commander of the special operations command shall hold the grade of general or, in the case "
            "of an officer of the Navy, admiral while serving in that position, without vacating his permanent "
            "grade."
        ),
    },
    "exec-dept-defense-cocom-uscybercom-commander-ccdr-uscybercom": {
        "nodeName": "Commander (CCDR), USCYBERCOM",
        "office": "Commander of the United States Cyber Command",
        "citation": "10 U.S.C. 167b(c)",
        "fixture": "cybercom_10_usc_167b_govinfo2024.html",
        "subsection": "(c) Grade of Commander",
        "grade": "general or admiral",
        "quote": (
            "The Commander of the United States Cyber Command shall hold the grade of general or, in the case "
            "of an officer of the Navy, admiral while serving in that position, without vacating that "
            "officer's permanent grade."
        ),
    },
}

#: Read, and deliberately not priced, with the reason -- printed by the derive
#: step so each is visibly a decision rather than an omission.
NOT_PRICED: dict[str, str] = {
    # The Space Force's "Senior Enlisted Advisor" sat here until 2026-10-07 ("a
    # rename candidate, not a pricing"); the owner decided the rename, the node
    # is now "Chief Master Sergeant of the Space Force" as Schedule 8's footnote
    # prints it (scripts/rename_posts_to_printed_titles.py), and the footnote
    # route prices it by equality.
    "exec-dept-defense-agency-nga-director-national-geospatial-intelligence-agency-nga": (
        "10 U.S.C. 441(b)(3) fixes lieutenant general or vice admiral only IF an officer of the armed forces "
        "holds the post, which is a fact about a person this project never reads"
    ),
    "exec-dept-defense-cocom-commanders-without-a-grade-statute": (
        "nine of the eleven combatant commanders (AFRICOM, CENTCOM, EUCOM, INDOPACOM, NORTHCOM, SOUTHCOM, "
        "SPACECOM, STRATCOM, TRANSCOM) hold their grade by presidential designation under 10 U.S.C. 601(a), "
        "which names no post; 10 U.S.C. 164 fixes none; Schedule 8's footnote names them only as subject to "
        "the Level II ceiling, and a ceiling is not a rate"
    ),
    "exec-dept-defense-jcs-copies-of-the-service-chiefs": (
        "the Joint Chiefs of Staff grouping carries a second node for each service chief and for the "
        "Commandant of the Coast Guard; each is the office the service's own node already carries, and "
        "publishing one salary on two nodes is the rule the Vice President's Senate-leadership node set"
    ),
    # The thirteenth research batch (2026-10-08) cited dfas.mil and
    # militarypay.defense.gov for some seventy uniformed posts. Only a statute
    # that FIXES a post's grade can join it to a flat Schedule 8 row (O-9 and
    # O-10 are the only flat officer rows), so each lead was read against the
    # section that would have to say so, committed under tests/fixtures/uscode/
    # where one was read, and pinned in tests/test_military_pay.py.
    "exec-dept-dhs-uscg-commander-atlantic-area": (
        "14 U.S.C. 305(a)(1)(A) lets the President DESIGNATE no more than five Coast Guard positions whose "
        "holders have the grade of vice admiral, and names no Area Commander (the one post it names, "
        "conditionally, is the Chief of Staff); a designation that names no post is the 10 U.S.C. 601(a) rule"
    ),
    "exec-dept-dhs-uscg-commander-pacific-area": (
        "14 U.S.C. 305(a)(1)(A) lets the President DESIGNATE no more than five Coast Guard positions whose "
        "holders have the grade of vice admiral, and names no Area Commander (the one post it names, "
        "conditionally, is the Chief of Staff); a designation that names no post is the 10 U.S.C. 601(a) rule"
    ),
    "exec-dept-defense-army-chief-army-reserve": (
        "10 U.S.C. 7038 (2024 edition) appoints the Chief of Army Reserve 'from general officers of the Army "
        "Reserve' and counts the officer against the grade limits of sections 525 and 526; it fixes no grade"
    ),
    "exec-dept-defense-army-chief-army-national-guard": (
        "10 U.S.C. 10506 creates a 'Director, Army National Guard', appointed 'from general officers of the "
        "Army National Guard of the United States', and fixes no grade; the graph's 'Chief, Army National "
        "Guard' would also need a reviewed identification with that office"
    ),
    "exec-dept-defense-marines-commanding-general-marine-corps-reserve": (
        "10 U.S.C. 8084 appoints the Commander, Marine Forces Reserve 'from general officers of the Marine "
        "Corps Reserve' and counts the officer against sections 525 and 526; it fixes no grade"
    ),
    "exec-dept-defense-service-staff-principals": (
        "the Army's G-staff and the Air Force's A-staff are 'general officers detailed to those positions' "
        "(10 U.S.C. 7035(a), 9035(a)), OPNAV's Deputy Chiefs are detailed 'from officers ... serving in grades "
        "above captain' (8036(a)) and the Marine Corps' Deputy Commandants are detailed with no grade at all "
        "(8045): a class of grades or a floor, never one grade, so no single row prices them; the Joint "
        "Staff's J1-J8 directors are named by no section read here"
    ),
    "exec-dept-defense-commands-held-by-designation": (
        "the Army's commands (AMC, FORSCOM, TRADOC, USAREUR-AF, USARPAC), the Navy's fleets and systems "
        "commands, the Air Force's major commands, the Space Force's field commands and the Marine Corps' "
        "MARFORCOM, MARFORPAC and MARSOC take their commanders' grades from presidential designation under "
        "10 U.S.C. 601(a), which names no post; no section read here names any of them"
    ),
    "exec-dept-defense-other-uniformed-leads-without-a-flat-grade": (
        "the Coast Guard's district commanders, its Sector Commander (several posts), the Chief of Naval "
        "Research and an embassy's Defense Attache: no section read here fixes any of their grades, and the "
        "only officer rows Schedule 8 prints flat are O-9 and O-10"
    ),
}


class Unreadable8(Unreadable):
    """Schedule 8 is not printed the way this reader was written against."""


def _grade_key(label: str) -> str | None:
    """"O–⁠10" -> "O-10"; "E–9" -> "E-9"; anything else -> None."""
    match = _GRADE_LABEL.match(label.replace("⁠", ""))
    if match is None:
        return None
    return f"{match.group(1)}-{match.group(2)}"


def _parse_block(lines: list[str], start: int) -> tuple[dict[str, dict[str, Any]], int]:
    """The rows of one years-of-service block, from the line after its last
    column header until a line that is neither a grade label, a footnote mark
    nor a money figure. Returns {grade: row} and the index it stopped at."""
    rows: dict[str, dict[str, Any]] = {}
    cursor = start
    while cursor < len(lines):
        grade = _grade_key(lines[cursor])
        if grade is None:
            break
        printed_label = lines[cursor]
        cursor += 1
        marks: list[str] = []
        while cursor < len(lines) and _MARK.match(lines[cursor]) and _grade_key(lines[cursor]) is None:
            marks.append(lines[cursor])
            cursor += 1
        figures: list[dict[str, Any]] = []
        while cursor < len(lines):
            money = _MONEY.match(lines[cursor])
            if money is None:
                break
            figures.append({
                "printed": lines[cursor],
                "amountRaw": money.group(2),
                "amount": float(money.group(2).replace(",", "")),
                "marked": money.group(1) == "$",
            })
            cursor += 1
        # The enlisted table prints E-1 twice, once per footnote ("4 months
        # or more" / "less than 4 months"); the second row is keyed with its
        # marks so neither is lost and a third copy still refuses.
        key = grade
        if key in rows:
            key = f"{grade}/{'+'.join(marks) or 'unmarked'}"
        if key in rows:
            raise Unreadable8(f"Schedule 8 prints pay grade {grade} three times in one block")
        amounts = {figure["amount"] for figure in figures}
        rows[key] = {
            "grade": grade,
            "gradeAsPrinted": printed_label,
            "footnoteMarks": marks,
            "figures": figures,
            "populatedColumns": len(figures),
            "flat": len(figures) > 0 and len(amounts) == 1,
            "flatAmount": figures[0]["amount"] if len(figures) > 0 and len(amounts) == 1 else None,
            "flatAmountRaw": figures[0]["amountRaw"] if len(figures) > 0 and len(amounts) == 1 else None,
            "rowText": " ".join([printed_label, *marks, *(figure["printed"] for figure in figures)]),
        }
    return rows, cursor


def _find(lines: list[str], text: str, start: int, stop: int) -> int:
    for index in range(start, stop):
        if lines[index] == text:
            return index
    raise Unreadable8(f"Schedule 8 does not print {text!r} where this reader expects it")


def _footnote_items(text: str) -> list[str]:
    """The titles the enlisted footnote lists, as printed, in order."""
    if not text.startswith(_FOOTNOTE_OPEN):
        raise Unreadable8("the enlisted footnote no longer opens as this reader expects")
    body = text[len(_FOOTNOTE_OPEN):]
    cut = body.find(", basic pay for this grade is")
    if cut < 0:
        raise Unreadable8("the enlisted footnote no longer states a rate 'for this grade'")
    listed = body[:cut]
    items = [item.strip() for item in listed.split(",")]
    out: list[str] = []
    for item in items:
        if item.startswith("or "):
            item = item[3:].strip()
        if item:
            out.append(item)
    return out


def footnote_titles(items: list[str]) -> list[dict[str, str]]:
    """Each printed item of the footnote as the office or offices it names.
    "Master Chief Petty Officer of the Navy or Coast Guard" names two."""
    titles: list[dict[str, str]] = []
    for item in items:
        match = _NAVY_OR_COAST_GUARD.match(item)
        if match:
            titles.append({"title": f"{match.group('title')} of the Navy", "printedItem": item})
            titles.append({"title": f"{match.group('title')} of the Coast Guard", "printedItem": item})
        else:
            titles.append({"title": item, "printedItem": item})
    return titles


def parse_schedule_8(raw_html: str) -> dict[str, Any]:
    """Schedule 8 as the note prints it: the officer table's second block (Over
    20 through Over 40), the enlisted table's second block, the officer cap
    footnote and the enlisted footnote that names the senior enlisted advisers.

    Raises `Unreadable8` rather than guessing at a reshaped page.
    """
    lines = _visible_lines(raw_html)
    heads = [i for i, line in enumerate(lines) if line == "Schedule" and i + 3 < len(lines) and lines[i + 1] == SCHEDULE_NUMBER]
    if len(heads) != 1:
        raise Unreadable8(f"the note prints the Schedule 8 heading {len(heads)} times, not once")
    start = heads[0]
    if lines[start + 2] != SCHEDULE_TITLE:
        raise Unreadable8(f"Schedule 8 is titled {lines[start + 2]!r}, not {SCHEDULE_TITLE!r}")
    effective = lines[start + 3]
    if not _EFFECTIVE.match(effective):
        raise Unreadable8(f"Schedule 8 is not followed by an effective-date line but by {effective!r}")
    year_match = _YEAR_IN_EFFECTIVE.search(effective)
    if not year_match:
        raise Unreadable8(f"Schedule 8's effective line {effective!r} names no January 1 year")
    if lines[start + 4] != PART_I_HEADING:
        raise Unreadable8(f"Schedule 8's first part is headed {lines[start + 4]!r}, not {PART_I_HEADING!r}")
    ends = [i for i in range(start + 4, len(lines) - 1) if lines[i] == "Schedule" and lines[i + 1] == "9"]
    stop = ends[0] if ends else len(lines)

    def both_blocks(section_heading: str) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], int]:
        """The section's first block (2 or less through Over 18) and its
        second (Over 20 through Over 40), and the index the second ends at."""
        section = _find(lines, section_heading, start, stop)
        over_18 = _find(lines, "Over 18", section, stop)
        first_rows, _first_end = _parse_block(lines, over_18 + 1)
        over_20 = _find(lines, "Over 20", section, stop)
        head = tuple(lines[over_20: over_20 + len(_SECOND_BLOCK_HEAD)])
        if head != _SECOND_BLOCK_HEAD:
            raise Unreadable8(f"{section_heading}'s second block is headed {head!r}")
        second_rows, second_end = _parse_block(lines, over_20 + len(_SECOND_BLOCK_HEAD))
        for grade, row in second_rows.items():
            first = first_rows.get(grade)
            row["firstBlockPopulatedColumns"] = first["populatedColumns"] if first else None
            # One figure may stand for the grade only when the FIRST block
            # prints nothing for it and the second is flat: a grade that
            # prints figures in both blocks varies with years of service.
            row["flat"] = bool(row["flat"] and first is not None and first["populatedColumns"] == 0)
            if not row["flat"]:
                row["flatAmount"] = None
                row["flatAmountRaw"] = None
        return first_rows, second_rows, second_end

    _officer_first, officer_rows, officer_end = both_blocks("Commissioned Officers")
    _enlisted_first, enlisted_rows, enlisted_end = both_blocks("Enlisted Members")

    cap_footnote = next((lines[i] for i in range(officer_end, stop) if lines[i].startswith(_CAP_FOOTNOTE_OPEN)), None)
    if cap_footnote is None:
        raise Unreadable8("Schedule 8's officer table carries no Level II ceiling footnote")
    cap_rate = _CAP_RATE.search(cap_footnote)
    if cap_rate is None:
        raise Unreadable8("the Level II ceiling footnote prints no monthly figure")

    enlisted_footnote = next((lines[i] for i in range(enlisted_end, stop) if lines[i].startswith(_FOOTNOTE_OPEN)), None)
    if enlisted_footnote is None:
        raise Unreadable8("Schedule 8's enlisted table carries no footnote naming the senior enlisted advisers")
    rate = _FOOTNOTE_RATE.search(enlisted_footnote)
    if rate is None:
        raise Unreadable8("the senior enlisted advisers' footnote prints no monthly figure")
    items = _footnote_items(enlisted_footnote)
    rate_raw = rate.group(1)[1:]

    return {
        "number": SCHEDULE_NUMBER,
        "label": SCHEDULE_LABEL,
        "title": SCHEDULE_TITLE,
        "effective": effective,
        "year": year_match.group(1),
        "partHeading": PART_I_HEADING,
        "secondBlockColumns": list(_SECOND_BLOCK_HEAD),
        "officerRows": officer_rows,
        "enlistedRows": enlisted_rows,
        "capFootnote": {
            "text": cap_footnote,
            "monthlyAsPrinted": cap_rate.group(1),
            "monthlyAmount": float(cap_rate.group(1)[1:].replace(",", "")),
        },
        "seniorEnlistedFootnote": {
            "text": enlisted_footnote,
            "items": items,
            "titles": footnote_titles(items),
            "monthlyAsPrinted": rate.group(1),
            "monthlyAmountRaw": rate_raw,
            "monthlyAmount": float(rate_raw.replace(",", "")),
            "grade": "E-9",
        },
    }


def load_schedule_8(html_path: str | Path = DEFAULT_SCHEDULE_HTML) -> dict[str, Any]:
    """The committed note, its digest recomputed from the bytes -- the refusal
    `pay_tables` makes -- and Schedule 8 parsed out of it."""
    path = Path(html_path)
    meta_path = path.with_name(path.name + ".meta.json")
    if not meta_path.exists():
        raise Unreadable8(f"{path.name} has no .meta.json beside it; an undated fetch cannot be cited")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    recorded = str(meta.get("sha256") or "").lower()
    if not recorded:
        raise Unreadable8(f"{meta_path.name} records no sha256")
    if digest != recorded:
        raise Unreadable8(
            f"{path.name} does not match the digest its fetch recorded ({digest} vs {recorded}); "
            "the committed file is not the file that was served"
        )
    url = str(meta.get("url") or "")
    fetched_at = str(meta.get("fetched_at") or "")
    if not url or not fetched_at:
        raise Unreadable8(f"{meta_path.name} is missing the url or the fetch time")
    if meta.get("error") or int(meta.get("status") or 0) != 200:
        raise Unreadable8(f"{meta_path.name} records a fetch that did not serve the page")
    schedule = parse_schedule_8(raw.decode("utf-8", errors="replace"))
    return {"schedule": schedule, "url": url, "fetched_at": fetched_at, "sha256": digest, "file": str(path)}


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


def _money_text(amount: float) -> str:
    return "${:,.2f}".format(amount)


def _annual(monthly: float) -> float:
    return round(monthly * MONTHS_IN_A_YEAR, 2)


def _statute_document(section: Mapping[str, Any], citation: str, quote: str, role: str) -> dict[str, Any]:
    # The edition is read off the address that served the bytes: govinfo's
    # link service answers from the dated edition's granule.
    publisher, edition = statute_publisher(str(section.get("final_url") or section["url"]))
    return {
        "role": role,
        "citation": citation,
        "publisher": publisher,
        "edition": edition,
        "title": f"{citation}, {edition}",
        "quote": quote,
        "url": section["url"],
        "documentSha256": section["sha256"],
        "retrievedAt": section["fetched_at"],
        "statesTheFigure": False,
    }


def _schedule_document(loaded: Mapping[str, Any], quote: str, role: str) -> dict[str, Any]:
    schedule = loaded["schedule"]
    return {
        "role": role,
        "citation": f"5 U.S.C. 5332 note, Ex. Ord. No. 14368, {schedule['label']} {schedule['effective']}",
        "publisher": "Office of the Law Revision Counsel, U.S. House of Representatives, reproducing Executive Order 14368",
        "title": f"{schedule['label']} {schedule['effective']}",
        "quote": quote,
        "url": loaded["url"],
        "documentSha256": loaded["sha256"],
        "retrievedAt": loaded["fetched_at"],
        # The schedule prints a MONTHLY figure; the record's figure is annual.
        "statesTheFigure": False,
        "statesTheMonthlyFigure": True,
    }


def _arithmetic(monthly_raw: str, monthly: float, scope: str) -> dict[str, Any]:
    annual = _annual(monthly)
    return {
        "operation": ARITHMETIC_OPERATION,
        "baseAmount": monthly,
        "baseAmountRaw": monthly_raw,
        "baseText": f"${monthly_raw} per month",
        "factor": MONTHS_IN_A_YEAR,
        "result": annual,
        "resultText": _money_text(annual),
        "note": (
            f"No document prints {_money_text(annual)}. Schedule 8 prints basic pay by the month "
            f"(\"{PART_I_HEADING}\"): ${monthly_raw} for {scope}; the annual figure is twelve times that "
            "and nothing more."
        ),
    }


def _cap_footnote(schedule: Mapping[str, Any]) -> dict[str, Any]:
    """The officer table's Level II ceiling footnote, verbatim, with the $100 it
    disagrees with the O-10 row by stated and not reconciled."""
    cap = schedule["capFootnote"]
    row = schedule["officerRows"].get("O-10") or {}
    if row.get("flat") and row.get("flatAmount") is not None:
        comparison = (
            f"while the O-10 row prints ${row['flatAmountRaw']}; the two differ by "
            f"${abs(float(row['flatAmount']) - float(cap['monthlyAmount'])):,.2f} and this project publishes "
            "the row's figure, recording the discrepancy rather than reconciling it."
        )
    else:
        comparison = "while the O-10 row varies across its columns; the footnote's figure is recorded and not used."
    return {
        "text": cap["text"],
        "monthlyAsPrinted": cap["monthlyAsPrinted"],
        "note": (
            "The officer table's footnote 1 prints the Level II ceiling for pay grades O-7 through O-10 as "
            f"{cap['monthlyAsPrinted']} per month, {comparison}"
        ),
    }


def _record_common(
    node_id: str, loaded: Mapping[str, Any], *, monthly_raw: str, monthly: float, scope: str,
    method: str, office: str, documents: list[dict[str, Any]], source_url: str, source_sha: str,
    source_retrieved: str, locator: dict[str, Any], identification: dict[str, Any], derivation: str,
    units_evidence: str, fiscal_year: int, extra: dict[str, Any],
) -> dict[str, Any]:
    schedule = loaded["schedule"]
    annual = _annual(monthly)
    effective_date = f"{schedule['year']}-01-01"
    record = {
        "nodeId": node_id,
        "financialEvidenceStatus": "partial",
        "costBasis": "basic_pay",
        "amount": annual,
        "amountRaw": "{:,.2f}".format(annual),
        "units": "usd",
        "normalizedMultiplier": 1,
        # The schedule's own text carrying the monthly figure WITH its mark;
        # the record's own (annual) figure is printed nowhere, which is the
        # narrower rule `financial_evidence.COMPUTED_FROM_MARKED_FIGURE_SOURCE_TYPES`
        # grants, with a third operation: monthly times twelve.
        "unitsEvidence": units_evidence,
        "quote": derivation,
        "fiscalYear": int(fiscal_year),
        "periodCoverage": "annual_rate",
        "periodAsOf": effective_date,
        "amountScope": f"{scope}, twelve times the monthly rate",
        "scopeMatch": "proxy",
        "rollupRole": "line",
        "sourceType": PAY_SOURCE_TYPE,
        "sourceUrl": source_url,
        "documentSha256": source_sha,
        "retrievedAt": source_retrieved,
        "locator": locator,
        "method": method,
        "office": office,
        "monthly": {
            "amount": monthly,
            "amountRaw": monthly_raw,
            "text": f"${monthly_raw} per month",
            "statedFor": scope,
        },
        "arithmetic": _arithmetic(monthly_raw, monthly, scope),
        "rateText": _money_text(annual),
        "derivation": derivation,
        "identification": identification,
        "documents": documents,
        "schedule": {
            "label": schedule["label"],
            "title": schedule["title"],
            "effective": schedule["effective"],
            "year": schedule["year"],
            "partHeading": schedule["partHeading"],
        },
        "capFootnote": _cap_footnote(schedule),
        "scheduleUrl": loaded["url"],
        "scheduleSha256": loaded["sha256"],
        "scheduleRetrievedAt": loaded["fetched_at"],
        "effective": effective_date,
    }
    record.update(extra)
    return record


def build_records(
    node_map: Mapping[str, Mapping[str, Any]],
    parent_map: Mapping[str, str | None],
    loaded: Mapping[str, Any],
    *,
    fiscal_year: int,
    directory: str | Path = FIXTURE_DIR,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """One record per reviewed grade row and per senior enlisted adviser the
    footnote names, each re-adjudicated: the grade sentence is still in its
    section's operative text, 37 U.S.C. 201 still assigns the grade to the pay
    grade, the Schedule 8 row is still flat, and the node still carries the
    name the row was written against (or, for the footnote route, is the one
    node named as the footnote prints the title)."""
    schedule = loaded["schedule"]

    def section(fixture: str) -> dict[str, Any]:
        if Path(directory) == FIXTURE_DIR:
            return load_section(fixture)
        return _load_section_from(Path(directory) / fixture)

    records: dict[str, dict[str, Any]] = {}
    refusals: dict[str, str] = {}
    sections: dict[str, dict[str, Any]] = {}

    mapping = section(MAPPING_FIXTURE)
    sections[MAPPING_FIXTURE] = mapping

    # --- the grade route ------------------------------------------------------
    for node_id, row in sorted(GRADE_PROVISIONS.items()):
        pay_grade = GRADE_WORD_TO_PAY_GRADE.get(row["grade"])
        if pay_grade is None:
            refusals[node_id] = f"the row's grade word {row['grade']!r} maps to no pay grade this module knows"
            continue
        mapping_quote = PAY_GRADE_ROWS.get(pay_grade)
        if mapping_quote is None or mapping_quote not in mapping["operative"]:
            refusals[node_id] = f"{MAPPING_CITATION} no longer prints the row assigning {row['grade']} to {pay_grade}"
            continue
        if row.get("spaceForce") and SPACE_FORCE_MAPPING_QUOTE not in mapping["operative"]:
            refusals[node_id] = f"{SPACE_FORCE_MAPPING_CITATION} no longer carries the Space Force sentence"
            continue
        sched_row = schedule["officerRows"].get(pay_grade)
        if sched_row is None:
            refusals[node_id] = f"Schedule 8 prints no {pay_grade} row in its Over 20 through Over 40 block"
            continue
        if not sched_row["flat"]:
            refusals[node_id] = (
                f"Schedule 8's {pay_grade} row varies with years of service, so one figure is not the grade's rate"
            )
            continue
        sec = sections.get(row["fixture"])
        if sec is None:
            sec = section(row["fixture"])
            sections[row["fixture"]] = sec
        if row["quote"] not in sec["operative"]:
            where = "only in the publisher's notes" if row["quote"] in sec["whole"] else "nowhere on the page"
            refusals[node_id] = f"{row['citation']} no longer carries the quoted grade sentence ({where})"
            continue
        office_quote = row.get("officeQuote")
        if office_quote and office_quote not in sec["operative"]:
            where = "only in the publisher's notes" if office_quote in sec["whole"] else "nowhere on the page"
            refusals[node_id] = f"{row['citation']}'s section no longer names the office as quoted ({where})"
            continue
        node = node_map.get(node_id)
        if node is None:
            refusals[node_id] = "node not in the graph"
            continue
        if not is_post_node(node):
            refusals[node_id] = "not a position"
            continue
        if canonical_name_key(node.get("name")) != canonical_name_key(row["nodeName"]):
            refusals[node_id] = f"renamed since the row was written (row: {row['nodeName']!r}, node: {node.get('name')!r})"
            continue
        if STATED_MULTIPLICITY.search(str(node.get("name") or "")):
            refusals[node_id] = "stands for several posts"
            continue
        monthly_raw = str(sched_row["flatAmountRaw"])
        monthly = float(sched_row["flatAmount"])
        scope = f"pay grade {pay_grade}"
        mapping_documents_quote = mapping_quote + (f" … {SPACE_FORCE_MAPPING_QUOTE}" if row.get("spaceForce") else "")
        documents = [
            _statute_document(
                sec, row["citation"], row["quote"] + (f" … {office_quote}" if office_quote else ""),
                f"fixes this post's grade: {row['grade']}",
            ),
            _statute_document(
                mapping, SPACE_FORCE_MAPPING_CITATION if row.get("spaceForce") else MAPPING_CITATION,
                mapping_documents_quote,
                f"assigns the grade of {row['grade']} to pay grade {pay_grade} for the purpose of computing basic pay",
            ),
            _schedule_document(
                loaded, sched_row["rowText"],
                f"prints the monthly basic pay for pay grade {pay_grade}: ${monthly_raw} in every populated column",
            ),
        ]
        derivation = (
            f"{row['citation']} {row['subsection']}: “{row['quote']}” · {MAPPING_CITATION}: “{mapping_quote}” · "
            f"{schedule['label']} {schedule['effective']}, {pay_grade} row: {sched_row['rowText']} · "
            f"${monthly_raw} × {MONTHS_IN_A_YEAR} = {_money_text(_annual(monthly))}"
        )
        records[node_id] = _record_common(
            node_id, loaded, monthly_raw=monthly_raw, monthly=monthly, scope=scope,
            method=PAY_METHOD_GRADE, office=row["office"], documents=documents,
            source_url=sec["url"], source_sha=sec["sha256"], source_retrieved=sec["fetched_at"],
            locator={"section": row["citation"], "subsection": row["subsection"]},
            identification={
                "kind": "grade_fixed_by_statute",
                "nodeName": row["nodeName"],
                "office": row["office"],
                "grade": row["grade"],
                "payGrade": pay_grade,
                "payGradeAsPrinted": sched_row["gradeAsPrinted"],
                "statuteQuote": row["quote"],
                "officeQuote": office_quote,
                "mappingCitation": MAPPING_CITATION,
                "mappingQuote": mapping_quote,
                "spaceForceMapping": SPACE_FORCE_MAPPING_QUOTE if row.get("spaceForce") else None,
            },
            derivation=derivation,
            units_evidence=sched_row["rowText"],
            fiscal_year=fiscal_year,
            extra={
                "statute": row["citation"],
                "statuteQuote": row["quote"],
                "grade": row["grade"],
                "payGrade": pay_grade,
                "payGradeAsPrinted": sched_row["gradeAsPrinted"],
                "scheduleRow": {
                    "grade": pay_grade,
                    "rowText": sched_row["rowText"],
                    "populatedColumns": sched_row["populatedColumns"],
                    "columns": list(schedule["secondBlockColumns"])[: sched_row["populatedColumns"]],
                    "flat": True,
                    "firstBlockPopulatedColumns": sched_row["firstBlockPopulatedColumns"],
                    "note": (
                        f"Every populated cell of the {pay_grade} row prints ${monthly_raw}, in the Over 20 through "
                        f"Over 40 columns; the cells for 2 or less through Over 18 print nothing, so the grade's "
                        "monthly rate does not vary with years of service."
                    ),
                },
            },
        )

    # --- the footnote route -------------------------------------------------
    footnote = schedule["seniorEnlistedFootnote"]
    title_nodes: dict[str, list[str]] = {}
    for node_id, node in node_map.items():
        if not is_post_node(node):
            continue
        title_nodes.setdefault(canonical_name_key(node.get("name")), []).append(node_id)
    footnote_matches: dict[str, dict[str, Any]] = {}
    unmatched_titles: list[str] = []
    for entry in footnote["titles"]:
        key = canonical_name_key(entry["title"])
        candidates = title_nodes.get(key, [])
        if len(candidates) == 0:
            unmatched_titles.append(entry["title"])
            continue
        if len(candidates) > 1:
            refusals["footnote:" + entry["title"]] = f"names {len(candidates)} position nodes; a title reaching two nodes prices neither"
            continue
        node_id = candidates[0]
        if node_id in footnote_matches:
            refusals[node_id] = "reached by two printed items of the footnote"
            footnote_matches.pop(node_id, None)
            continue
        footnote_matches[node_id] = entry
    for node_id, entry in sorted(footnote_matches.items()):
        node = node_map[node_id]
        if node_id in records:
            refusals[node_id] = "already priced by a grade row"
            continue
        if STATED_MULTIPLICITY.search(str(node.get("name") or "")):
            refusals[node_id] = "stands for several posts"
            continue
        monthly_raw = str(footnote["monthlyAmountRaw"])
        monthly = float(footnote["monthlyAmount"])
        scope = f"this post, named in the footnote as “{entry['printedItem']}”"
        documents = [
            _schedule_document(
                loaded, footnote["text"],
                f"names the post by title and prints its monthly basic pay: ${monthly_raw} per month regardless of years of service",
            ),
        ]
        derivation = (
            f"{schedule['label']} {schedule['effective']}, enlisted footnote 1: “{footnote['text']}” · "
            f"${monthly_raw} × {MONTHS_IN_A_YEAR} = {_money_text(_annual(monthly))}"
        )
        records[node_id] = _record_common(
            node_id, loaded, monthly_raw=monthly_raw, monthly=monthly, scope=scope,
            method=PAY_METHOD_NAMED, office=entry["title"], documents=documents,
            source_url=loaded["url"], source_sha=loaded["sha256"], source_retrieved=loaded["fetched_at"],
            locator={"section": "5 U.S.C. 5332 note", "subsection": f"{schedule['label']}, enlisted footnote 1"},
            identification={
                "kind": "named_in_footnote",
                "nodeName": str(node.get("name") or ""),
                "title": entry["title"],
                "printedItem": entry["printedItem"],
                "readsTwoOffices": entry["printedItem"] != entry["title"],
                "grade": footnote["grade"],
            },
            derivation=derivation,
            units_evidence=footnote["text"],
            fiscal_year=fiscal_year,
            extra={
                "statute": "5 U.S.C. 5332 note",
                "grade": "noncommissioned officer, pay grade E-9",
                "payGrade": footnote["grade"],
                "footnote": {
                    "text": footnote["text"],
                    "items": list(footnote["items"]),
                    "printedItem": entry["printedItem"],
                    "title": entry["title"],
                    "monthlyAsPrinted": footnote["monthlyAsPrinted"],
                },
            },
        )

    report = {
        "source": PAY_SOURCE,
        "schedule": {
            "label": schedule["label"], "effective": schedule["effective"], "year": schedule["year"],
            "url": loaded["url"], "sha256": loaded["sha256"], "fetched_at": loaded["fetched_at"],
        },
        "officerRowsRead": sorted(schedule["officerRows"]),
        "flatOfficerRows": sorted(grade for grade, row in schedule["officerRows"].items() if row["flat"]),
        "capFootnote": schedule["capFootnote"],
        "seniorEnlistedFootnote": {k: v for k, v in footnote.items() if k != "titles"},
        "footnoteTitlesUnmatched": unmatched_titles,
        "sections": {
            name: {"url": s["url"], "sha256": s["sha256"], "fetched_at": s["fetched_at"]}
            for name, s in sorted(sections.items())
        },
        "gradeRows": len(GRADE_PROVISIONS),
        "priced": len(records),
        "pricedByGrade": sum(1 for r in records.values() if r["identification"]["kind"] == "grade_fixed_by_statute"),
        "pricedByFootnote": sum(1 for r in records.values() if r["identification"]["kind"] == "named_in_footnote"),
        "documentsStatingTheFigure": 0,
        "strengthScale": STRENGTH_SCALE,
        "refused": dict(sorted(refusals.items())),
        "notPriced": dict(NOT_PRICED),
    }
    return records, report


def _load_section_from(path: Path) -> dict[str, Any]:
    """`derived_pay.load_section` against an explicit path (tests doctor a copy
    of a section in a temporary directory)."""
    import html as html_module

    from data_pipeline.verification.derived_pay import _collapse, operative_text

    meta_path = path.with_name(path.name + ".meta.json")
    if not path.exists() or not meta_path.exists():
        raise Unreadable(f"{path.name} or its .meta.json is not committed")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != str(meta.get("sha256") or "").lower():
        raise Unreadable(f"{path.name} does not match the digest its fetch recorded")
    decoded = raw.decode("utf-8", errors="replace")
    return {
        "file": str(path), "url": str(meta.get("url") or ""), "final_url": str(meta.get("final_url") or meta.get("url") or ""),
        "fetched_at": str(meta.get("fetched_at") or ""),
        "sha256": digest, "operative": operative_text(decoded),
        "whole": _collapse(html_module.unescape(re.sub(r"<[^>]+>", " ", decoded))),
    }


#: The pay fields whose presence leaves a node alone: a printed figure, a
#: level's own table rate, or another route's figure never gives way to this one.
_LEAVE_ALONE_FIELDS = (
    "positionStatutoryPay", "positionPayRate", "positionSchedulePay", "positionDerivedPay",
    "positionTierReferencePay", "positionCurrentPay", "positionReportedPay",
)


def apply_pay_evidence(
    root: dict[str, Any],
    records: Mapping[str, Mapping[str, Any]],
    *,
    index_tree: Any = None,
) -> dict[str, Any]:
    """Stamp `positionMilitaryPay`. A node another pay source has already
    priced is left alone; a record is re-checked against the node's current
    name (and, for the footnote route, the title the footnote prints)."""
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, _parent_map = index_tree(root)
    stats = {
        "priced": 0,
        "priced_by_grade": 0,
        "priced_by_footnote": 0,
        "unknown_node": 0,
        "not_a_position": 0,
        "renamed_since_the_match": 0,
        "already_priced_by_another_source": 0,
    }
    for node_id, record in sorted(records.items()):
        node = node_map.get(node_id)
        if node is None:
            stats["unknown_node"] += 1
            continue
        if not is_post_node(node):
            stats["not_a_position"] += 1
            continue
        identification = record.get("identification") or {}
        kind = identification.get("kind")
        if kind == "grade_fixed_by_statute":
            row = GRADE_PROVISIONS.get(node_id)
            if row is None or canonical_name_key(node.get("name")) != canonical_name_key(row["nodeName"]):
                stats["renamed_since_the_match"] += 1
                continue
        elif kind == "named_in_footnote":
            if canonical_name_key(node.get("name")) != canonical_name_key(identification.get("title")):
                stats["renamed_since_the_match"] += 1
                continue
        else:
            stats["unknown_node"] += 1
            continue
        if any(isinstance(node.get(field), dict) for field in _LEAVE_ALONE_FIELDS):
            stats["already_priced_by_another_source"] += 1
            continue
        node[FIELD] = {
            "source": PAY_SOURCE,
            "sourceLabel": (
                "Schedule 8 of the annual pay-adjustment order (the uniformed services' monthly basic pay), "
                "joined to the statute that fixes the post's grade"
                if kind == "grade_fixed_by_statute"
                else "Schedule 8 of the annual pay-adjustment order, whose footnote names the post and prints its monthly basic pay"
            ),
            "method": record.get("method"),
            "amount": record.get("amount"),
            "rateText": record.get("rateText"),
            "monthly": dict(record.get("monthly") or {}),
            "arithmetic": dict(record.get("arithmetic") or {}),
            "office": record.get("office"),
            "statute": record.get("statute"),
            "statuteQuote": record.get("statuteQuote"),
            "grade": record.get("grade"),
            "payGrade": record.get("payGrade"),
            "payGradeAsPrinted": record.get("payGradeAsPrinted"),
            "scheduleRow": dict(record["scheduleRow"]) if isinstance(record.get("scheduleRow"), dict) else None,
            "footnote": dict(record["footnote"]) if isinstance(record.get("footnote"), dict) else None,
            "capFootnote": dict(record.get("capFootnote") or {}),
            "identification": dict(identification),
            "derivation": record.get("derivation"),
            "quote": record.get("quote"),
            "documents": [dict(document) for document in record.get("documents") or []],
            "schedule": dict(record.get("schedule") or {}),
            "effective": record.get("effective"),
            "fiscalYear": record.get("fiscalYear"),
            "costBasis": record.get("costBasis"),
            "scopeMatch": record.get("scopeMatch"),
            "financialEvidenceStatus": record.get("financialEvidenceStatus"),
            "amountScope": record.get("amountScope"),
            "url": str(record.get("sourceUrl") or ""),
            "scheduleUrl": str(record.get("scheduleUrl") or ""),
            "checkedAt": record.get("retrievedAt"),
            # `verification` is stamped by pay_documents.annotate_pay_documents.
        }
        stats["priced"] += 1
        stats["priced_by_grade" if kind == "grade_fixed_by_statute" else "priced_by_footnote"] += 1
        # Deliberately not written: sourceUrls, sourceTypes, lastVerified,
        # verificationMethod.
    return stats
