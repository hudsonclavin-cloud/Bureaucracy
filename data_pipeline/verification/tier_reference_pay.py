"""A statute that sets a post's pay by REFERENCE to an Executive Schedule level,
joined to OPM's table for that level.

## The claim, and why it is neither `positionSchedulePay` nor `positionDerivedPay`

`statutory_schedule.py` prices a post the Executive Schedule itself places:
5 U.S.C. §§5312-5316 print "Director of the Office of Personnel Management"
at Level II and OPM's Salary Table No. 2026-EX prints what Level II pays.
Some posts are priced the other way round. The Executive Schedule does not
print "Comptroller General of the United States" anywhere; 31 U.S.C. 703(f)
says the Comptroller General's pay "is equal to the rate for level II of the
Executive Schedule". The office is not ON the Schedule, its pay is set BY
REFERENCE to one of the Schedule's tiers -- which is exactly the shape
`derived_pay.py` handles for the Article I courts, with OPM's table standing
where the Judicial Compensation table stood: the statute names the tier, the
table prices the tier, and **neither document states the figure for this
post**. So every record here says so (`documentsStatingTheFigure: 0`) and
publishes the count of documents it rests on and what that count is worth on
this project's own scale, exactly as a derived record does.

It is a field of its own, `positionTierReferencePay`, rather than a widening
of `positionDerivedPay`, for the reason that module gives for not widening
`positionStatutoryPay`: that gate mirrors four parity provisions by node id
against the uscourts.gov table, and folding a different table, a different
statute shape and -- below -- an arithmetic step into it would mean loosening
checks that already guard eight published records to make a new claim easier
to publish.

## Two provisions, read from the committed bytes

- **31 U.S.C. 703(f)**, the Government Accountability Office: "(1) Comptroller
  General is equal to the rate for level II of the Executive Schedule; and
  (2) Deputy Comptroller General is equal to the rate for level III". Two
  reviewed rows, one node each, the figure OPM's table prints for the level.
- **5 U.S.C. 403(e)**, the Inspector General Act: "The annual rate of basic pay
  for an Inspector General (as defined under section 401 of this title) shall
  be the rate payable for level III of the Executive Schedule under section
  5314 of this title, plus 3 percent." That is a figure NO document prints,
  reached by arithmetic on a printed one: $209,600 x 1.03 = $215,888. The
  record carries the arithmetic in the open (`arithmetic`: the base as the
  table prints it, the percentage as the statute states it, the result), the
  panel prints it as a computation and never as a quotation, and
  `financial_evidence` accepts it under a rule granted to this source type
  alone: the record's own figure is not printed anywhere, so the scale is
  vouched for by the currency mark on the figure it is computed FROM.

## Which Inspectors General, and the guard that decides

§403(e) prices "an Inspector General (as defined under section 401 of this
title)", and §401(4) defines that as "the Inspector General of an
establishment", and §401(1) lists the establishments by name -- fifteen
departments and some two dozen agencies. So the rule is scoped by the
statute's own list rather than by anything this repository decides: a node is
priced only when its name is exactly "Inspector General", it sits DIRECTLY
under an organisation whose name reduces to one of §401(1)'s establishments,
and the node stands for one post. The list is parsed out of the committed
section on every run (`parse_establishments`) and the gate parses it again
with its own reader.

That guard is what keeps the stamp out. `CLAUDE.md` records that "Inspector
General" is the name of 80 nodes here and that most of them are a copied
administrative stamp under DIA, NGA, DARPA, DLA and other Defense agencies;
none of those is an establishment, so none is priced. Also refused, each for
a reason recorded in `NOT_PRICED_KINDS`: the IGs of designated Federal
entities (§415, read and committed, which prints no rate of pay -- the NLRB,
the FEC, the NEA, the CPSC and the rest); the CIA's, whose statute is
5 U.S.C. 423 and has not been read; the legislative branch's (the GAO, the
Library, the Architect, the Capitol Police), which §401(2) excludes and
§401(1) does not list; and AmeriCorps, which §401(1) lists as the Corporation
for National and Community Service -- a name this graph carries only in the
alias table, and `aliases.py` is read by name and existence evidence only,
never by a join that lands a number.

## Three bodies whose statute names the office under the stamp (since 2026-10-05)

22 U.S.C. 6203(b)(3) pays the Chief Executive Officer of the U.S. Agency for
Global Media at Level III; 52 U.S.C. 20923(d)(1) pays "Each member" of the
Election Assistance Commission at Level IV; 52 U.S.C. 30106(a)(4) pays the
Federal Election Commission's members (other than its two ex officio ones) at
Level IV. None of the three is on the Schedule, so this module's shape. The
graph draws each body's head with the stamped `Director / Administrator /
Chair, <agency>` and `Deputy Director / Vice Chair` titles, and the rule the
reviewed Schedule rows set applies: the stamp is priced only where the body's
own statute names which office stands under it, and here that sentence is in
the SAME section as the pay sentence -- 6203(b)(1) makes the CEO the head of
the Agency, 20923(c)(1) and 30106(a)(5) have each commission choose its chair
and vice chair "from among its members", whose pay the next sentence sets. So
a row may carry `identificationQuote`, a second sentence of its own section
re-found in the operative text on every run and published in the block's
`identification` as `statuteIdentifies`; it is not a second document, and the
record counts two. The pair reading -- Chair and Vice Chair rather than a
Director and a Deputy -- is the one the statutes support: each creates a
chairman and a vice chairman as a pair and no deputy to its staff director.

All three sections were read from the Government Publishing Office's rendering
of the 2024 edition on www.govinfo.gov (uscode.house.gov was under
maintenance; docs/NETWORK_ACCESS.md §15), so a statute document names its
publisher and edition through `derived_pay.statute_publisher`.

## Every rule the other pay modules keep

`scopeMatch: proxy` and `partial` on every record: the statute names an
office by its class or its tier, not this node by name. Nothing writes
`sourceUrls`, `sourceTypes`, `lastVerified` or `verificationMethod` -- the
channel by which a five-row table carried 29 positions to `verified` on
2026-09-11. A node another pay source has already priced is left alone. A
quote is checked against the section's OPERATIVE text, never the whole page,
for the reason `derived_pay.py` records (38 U.S.C. 7253's repealed subsection).
"""

from __future__ import annotations

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

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "uscode"
DEFAULT_PAY_EVIDENCE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "verification" / "tier_reference_pay_evidence.json"
)

FIELD = "positionTierReferencePay"
PAY_SOURCE = "statutory_tier_reference_pay"
PAY_SOURCE_TYPE = "statutory_tier_reference_pay"
#: A statute sets the post's pay equal to a level's rate; the table prices it.
PAY_METHOD = "pay_set_by_reference_to_an_executive_schedule_level_joined_to_opm_table"
#: The same, plus a percentage the statute states: a figure no document prints.
PAY_METHOD_PERCENT = (
    "pay_set_by_reference_to_an_executive_schedule_level_plus_a_statutory_percentage_joined_to_opm_table"
)

#: The publisher and edition a statute document names come from its URL
#: (`derived_pay.statute_publisher`): the OLRC's prelim pages, or GPO's
#: rendering of a dated edition on www.govinfo.gov.
STATUTE_PUBLISHER = "Office of the Law Revision Counsel, U.S. House of Representatives"

#: 20 U.S.C. 9517(a) prices "each Commissioner" of "the National Education
#: Centers" and names none of them; 9511(c)(3) is the sentence that says which
#: centers those are. A row that rests on the class sentence carries it as a
#: third document, the way an Inspector General's record carries 401(1)'s
#: establishment list; the NCES Commissioner is priced by 9517(b) by name and
#: needs no such document.
IES_COMPOSITION: dict[str, Any] = {
    "citation": "20 U.S.C. 9511(c)(3)",
    "fixture": "ies_20_usc_9511.html",
    "role": "composes the National Education Centers whose Commissioners 20 U.S.C. 9517(a) prices",
    "quote": (
        "The National Education Centers, which include- (A) the National Center for Education Research (as "
        "described in part B); (B) the National Center for Education Statistics (as described in part C); (C) "
        "the National Center for Education Evaluation and Regional Assistance (as described in part D); and "
        "(D) the National Center for Special Education Research (as described in part E)."
    ),
}

#: The GAO's two officers: node id -> the row. `quote` is checked against
#: 31 U.S.C. 703's operative text on every run; the node must still carry the
#: name the row was written against; the level must be one OPM's table prints.
TIER_REFERENCE_PROVISIONS: dict[str, dict[str, Any]] = {
    "leg-support-gao-comptroller-general-of-the-united-states": {
        "nodeName": "Comptroller General of the United States",
        "office": "Comptroller General",
        "citation": "31 U.S.C. 703(f)(1)",
        "fixture": "gao_31_usc_703.html",
        "subsection": "(f)",
        "level": "II",
        "percent": 0,
        "quote": "Comptroller General is equal to the rate for level II of the Executive Schedule",
    },
    "leg-support-gao-deputy-comptroller-general": {
        "nodeName": "Deputy Comptroller General",
        "office": "Deputy Comptroller General",
        "citation": "31 U.S.C. 703(f)(2)",
        "fixture": "gao_31_usc_703.html",
        "subsection": "(f)",
        "level": "III",
        "percent": 0,
        "quote": "Deputy Comptroller General is equal to the rate for level III of the Executive Schedule",
    },
    "leg-support-gpo-director-gpo-public-printer": {
        "nodeName": "Director, GPO (Public Printer)",
        "office": "Director of the Government Publishing Office",
        "citation": "44 U.S.C. 303",
        "fixture": "gpo_44_usc_303.html",
        "subsection": "(first sentence)",
        "level": "II",
        "percent": 0,
        "quote": (
            "The annual rate of pay for the Director of the Government Publishing Office shall be a rate "
            "which is equal to the rate for level II of the Executive Schedule"
        ),
    },
    "leg-support-gpo-deputy-director-coo": {
        "nodeName": "Deputy Director / COO",
        "office": "Deputy Director of the Government Publishing Office",
        "citation": "44 U.S.C. 303",
        "fixture": "gpo_44_usc_303.html",
        "subsection": "(second sentence)",
        "level": "III",
        "percent": 0,
        "quote": (
            "The annual rate of pay for the Deputy Director of the Government Publishing Office shall be a "
            "rate which is equal to the rate for level III of such Executive Schedule."
        ),
    },
    "exec-dept-ed-ies-director-ies": {
        "nodeName": "Director, IES",
        "office": "Director of the Institute of Education Sciences",
        "citation": "20 U.S.C. 9514(c)",
        "fixture": "ies_20_usc_9514.html",
        "subsection": "(c) Pay",
        "level": "II",
        "percent": 0,
        "quote": "The Director shall receive the rate of basic pay for level II of the Executive Schedule.",
    },
    "exec-dept-ed-ies-commissioner-national-center-for-education-statistics-nces": {
        "nodeName": "Commissioner — National Center for Education Statistics (NCES)",
        "office": "Commissioner for Education Statistics",
        "citation": "20 U.S.C. 9517(b)(2)",
        "fixture": "ies_20_usc_9517.html",
        "subsection": "(b) Appointment of Commissioner for Education Statistics",
        "level": "IV",
        "percent": 0,
        "quote": (
            "The National Center for Education Statistics shall be headed by a Commissioner for Education "
            "Statistics who shall be appointed by the President and who shall- (1) have substantial knowledge "
            "of programs assisted by the National Center for Education Statistics; (2) receive the rate of "
            "basic pay for level IV of the Executive Schedule;"
        ),
    },
    "exec-dept-ed-ies-commissioner-national-center-for-education-research-ncer": {
        "nodeName": "Commissioner — National Center for Education Research (NCER)",
        "office": "Commissioner of the National Center for Education Research",
        "citation": "20 U.S.C. 9517(a)(2)(A)",
        "fixture": "ies_20_usc_9517.html",
        "subsection": "(a)(2) Pay and qualifications",
        "level": "IV",
        "percent": 0,
        "quote": "each Commissioner shall- (A) receive the rate of basic pay for level IV of the Executive Schedule;",
        "composition": IES_COMPOSITION,
    },
    "exec-dept-ed-ies-commissioner-national-center-for-education-evaluation-ncee": {
        "nodeName": "Commissioner — National Center for Education Evaluation (NCEE)",
        "office": "Commissioner of the National Center for Education Evaluation and Regional Assistance",
        "citation": "20 U.S.C. 9517(a)(2)(A)",
        "fixture": "ies_20_usc_9517.html",
        "subsection": "(a)(2) Pay and qualifications",
        "level": "IV",
        "percent": 0,
        "quote": "each Commissioner shall- (A) receive the rate of basic pay for level IV of the Executive Schedule;",
        "composition": IES_COMPOSITION,
    },
    "exec-ind-misc-farm-credit-administration-director-administrator-chair-farm-credit-administration": {
        "nodeName": "Director / Administrator / Chair, Farm Credit Administration",
        "office": "Chairman of the Farm Credit Administration Board",
        "citation": "12 U.S.C. 2242(d)",
        "fixture": "fca_12_usc_2242.html",
        "subsection": "(d) Compensation",
        "level": "III",
        "percent": 0,
        "quote": (
            "The Chairman of the Board shall receive compensation at the rate prescribed for level III of the Executive Schedule under section 5314 of title 5"
        ),
    },
    # --- 2026-10-05: three bodies whose own section names the office under
    # --- the stamp, read from govinfo's 2024 edition ------------------------
    "exec-ind-misc-broadcasting-board-of-governors-usagm-director-administrator-chair-broadcasting-board-of-governors-usagm": {
        "nodeName": "Director / Administrator / Chair, Broadcasting Board of Governors / USAGM",
        "office": "Chief Executive Officer of the United States Agency for Global Media",
        "citation": "22 U.S.C. 6203(b)(3)",
        "fixture": "usagm_22_usc_6203_govinfo2024.html",
        "subsection": "(b)(3) Compensation",
        "level": "III",
        "percent": 0,
        "quote": (
            "A Chief Executive Officer appointed pursuant to paragraph (1) shall be compensated at the annual "
            "rate of basic pay for level III of the Executive Schedule under section 5314 of title 5."
        ),
        "identificationQuote": (
            "The head of the United States Agency for Global Media shall be a Chief Executive Officer, who shall "
            "be appointed by the President, by and with the advice and consent of the Senate."
        ),
    },
    "exec-ind-misc-election-assistance-commission-eac-director-administrator-chair-election-assistance-commission": {
        "nodeName": "Director / Administrator / Chair, Election Assistance Commission",
        "office": "Chair of the Election Assistance Commission, a member of the Commission",
        "citation": "52 U.S.C. 20923(d)(1)",
        "fixture": "eac_52_usc_20923_govinfo2024.html",
        "subsection": "(d)(1) Compensation",
        "level": "IV",
        "percent": 0,
        "quote": (
            "Each member of the Commission shall be compensated at the annual rate of basic pay prescribed for "
            "level IV of the Executive Schedule under section 5315 of title 5."
        ),
        "identificationQuote": (
            "The Commission shall select a chair and vice chair from among its members for a term of 1 year, "
            "except that the chair and vice chair may not be affiliated with the same political party."
        ),
    },
    "exec-ind-misc-election-assistance-commission-eac-deputy-director-vice-chair": {
        "nodeName": "Deputy Director / Vice Chair",
        "office": "Vice Chair of the Election Assistance Commission, a member of the Commission",
        "citation": "52 U.S.C. 20923(d)(1)",
        "fixture": "eac_52_usc_20923_govinfo2024.html",
        "subsection": "(d)(1) Compensation",
        "level": "IV",
        "percent": 0,
        "quote": (
            "Each member of the Commission shall be compensated at the annual rate of basic pay prescribed for "
            "level IV of the Executive Schedule under section 5315 of title 5."
        ),
        "identificationQuote": (
            "The Commission shall select a chair and vice chair from among its members for a term of 1 year, "
            "except that the chair and vice chair may not be affiliated with the same political party."
        ),
    },
    "exec-ind-misc-federal-election-commission-fec-director-administrator-chair-federal-election-commission": {
        "nodeName": "Director / Administrator / Chair, Federal Election Commission",
        "office": "Chairman of the Federal Election Commission, a member of the Commission",
        "citation": "52 U.S.C. 30106(a)(4)",
        "fixture": "fec_52_usc_30106_govinfo2024.html",
        "subsection": "(a)(4)",
        "level": "IV",
        "percent": 0,
        "quote": (
            "Members of the Commission (other than the Secretary of the Senate and the Clerk of the House of "
            "Representatives) shall receive compensation equivalent to the compensation paid at level IV of the "
            "Executive Schedule (5 U.S.C. 5315)."
        ),
        "identificationQuote": (
            "The Commission shall elect a chairman and a vice chairman from among its members (other than the "
            "Secretary of the Senate and the Clerk of the House of Representatives) for a term of one year."
        ),
    },
    "exec-ind-misc-federal-election-commission-fec-deputy-director-vice-chair": {
        "nodeName": "Deputy Director / Vice Chair",
        "office": "Vice Chairman of the Federal Election Commission, a member of the Commission",
        "citation": "52 U.S.C. 30106(a)(4)",
        "fixture": "fec_52_usc_30106_govinfo2024.html",
        "subsection": "(a)(4)",
        "level": "IV",
        "percent": 0,
        "quote": (
            "Members of the Commission (other than the Secretary of the Senate and the Clerk of the House of "
            "Representatives) shall receive compensation equivalent to the compensation paid at level IV of the "
            "Executive Schedule (5 U.S.C. 5315)."
        ),
        "identificationQuote": (
            "The Commission shall elect a chairman and a vice chairman from among its members (other than the "
            "Secretary of the Senate and the Clerk of the House of Representatives) for a term of one year."
        ),
    },
    # The twelfth batch (2026-10-05, CURATION.md §19.20): the Secret Service
    # Uniformed Division's Chief. 5 U.S.C. 10203(a) prints the Division's
    # schedule of rates as a table and sets the Chief's row by reference to
    # Level V; the Code's own footnote says the sentence "Probably should be
    # followed by 'for'", so the quote stops where the printed words do.
    "exec-ind-misc-privacy-civil-liberties-oversight-board-pclob-director-administrator-chair-privacy-civil-liberties-oversight-board": {
        "nodeName": "Director / Administrator / Chair, Privacy & Civil Liberties Oversight Board",
        "office": "Chairman of the Privacy and Civil Liberties Oversight Board",
        "citation": "42 U.S.C. 2000ee(i)(1)(A)",
        "fixture": "pclob_42_usc_2000ee_govinfo2024.html",
        "subsection": "(i)(1)(A)",
        "level": "III",
        "percent": 0,
        "quote": "The chairman of the Board shall be compensated at the rate of pay payable for a position at level III of the Executive Schedule under section 5314 of title 5.",
        "identificationQuote": "The Board shall be composed of a full-time chairman and 4 additional members, who shall be appointed by the President, by and with the advice and consent of the Senate.",
    },
    "exec-ind-misc-appalachian-regional-commission-arc-director-administrator-chair-appalachian-regional-commission": {
        "nodeName": "Director / Administrator / Chair, Appalachian Regional Commission",
        "office": "Federal Cochairman of the Appalachian Regional Commission",
        "citation": "40 U.S.C. 14301(c)",
        "fixture": "arc_40_usc_14301_govinfo2024.html",
        "subsection": "(c) Compensation",
        "level": "III",
        "percent": 0,
        "quote": "The Federal Cochairman shall be compensated by the Federal Government at level III of the Executive Schedule as set out in section 5314 of title 5.",
        "identificationQuote": "The Commission is composed of the Federal Cochairman, appointed by the President by and with the advice and consent of the Senate, and the Governor of each participating State in the Appalachian region.",
    },
    # The Corporation for National and Community Service (AmeriCorps): the
    # Inspector General Act's shape on a reviewed row, 42 U.S.C. 12651c(b)
    # adding 3 percent to Level III for the Chief Executive Officer the same
    # section puts at the head of the Corporation. The stamped node is priced
    # only because (a) names the office under the template.
    "exec-ind-misc-americorps-director-administrator-chair-americorps": {
        "nodeName": "Director / Administrator / Chair, AmeriCorps",
        "office": "Chief Executive Officer of the Corporation for National and Community Service",
        "citation": "42 U.S.C. 12651c(b)",
        "fixture": "cncs_42_usc_12651c_govinfo2024.html",
        "subsection": "(b) Compensation",
        "level": "III",
        "percent": 3,
        "quote": "The Chief Executive Officer shall be compensated at the rate provided for level III of the Executive Schedule under section 5314 of title 5, plus 3 percent.",
        "identificationQuote": "The Corporation shall be headed by an individual who shall serve as Chief Executive Officer of the Corporation, and who shall be appointed by the President, by and with the advice and consent of the Senate.",
    },
    "exec-dept-dhs-usss-chief-uniformed-division": {
        "nodeName": "Chief — Uniformed Division",
        "office": "Chief of the United States Secret Service Uniformed Division",
        "citation": "5 U.S.C. 10203(a)",
        "fixture": "usss_5_usc_10203_govinfo2024.html",
        "subsection": "(a)",
        "level": "V",
        "percent": 0,
        "quote": "the Chief position will be equal to the rate of pay for level V of the Executive Schedule",
    },
    "leg-support-loc-librarian-of-congress": {
        "nodeName": "Librarian of Congress",
        "office": "Librarian of Congress",
        "citation": "2 U.S.C. 136a-2(1)",
        "fixture": "loc_2_usc_136a-2.html",
        "subsection": "(1)",
        "level": "II",
        "percent": 0,
        "quote": (
            "the Librarian of Congress shall be compensated at an annual rate of pay which is equal to the annual rate of basic pay payable for positions at level II of the Executive Schedule under section 5313 of title 5"
        ),
    },
    # --- 2026-10-06: the twelfth batch's legislative-branch cluster. Three
    # --- more officers whose own section sets the rate at a level, read from
    # --- govinfo's 2024 edition. The "$X less than" officers beside them (the
    # --- AOC's, the Capitol Police's and the GAO's Inspectors General, the
    # --- CBO's Deputy Director) are a subtraction on a join this module does
    # --- not yet publish; CURATION.md §19.20 records them as the next decision.
    "leg-support-aoc-architect-of-the-capitol": {
        "nodeName": "Architect of the Capitol",
        "office": "Architect of the Capitol",
        "citation": "2 U.S.C. 1802",
        "fixture": "aoc_2_usc_1802_govinfo2024.html",
        "subsection": "(the section's one sentence)",
        "level": "II",
        "percent": 0,
        "quote": (
            "The compensation of the Architect of the Capitol shall be at an annual rate which is equal to the "
            "annual rate of basic pay for level II of the Executive Schedule under section 5313 of title 5."
        ),
    },
    "leg-support-uscp-chief-of-police": {
        # The graph names the post "Chief of Police" under the U.S. Capitol
        # Police; the statute says "Chief of the Capitol Police". Keyed by id.
        "nodeName": "Chief of Police",
        "office": "Chief of the Capitol Police",
        "citation": "2 U.S.C. 1902",
        "fixture": "uscp_2_usc_1902_govinfo2024.html",
        "subsection": "(the section's one sentence)",
        "level": "II",
        "percent": 0,
        "quote": (
            "The annual rate of pay for the Chief of the Capitol Police shall be the amount equal to the annual "
            "rate of basic pay for level II of the Executive Schedule under section 5313 of title 5."
        ),
    },
    "leg-support-gao-general-counsel": {
        # "General Counsel" names 92 nodes here; 31 U.S.C. 731(c) names the
        # GAO's by its organisation, which is what keys the row to this one.
        "nodeName": "General Counsel",
        "office": "General Counsel of the Government Accountability Office",
        "citation": "31 U.S.C. 731(c)",
        "fixture": "gao_31_usc_731_govinfo2024.html",
        "subsection": "(c)",
        "level": "IV",
        "percent": 0,
        "quote": (
            "The annual rate of basic pay of the General Counsel of the Government Accountability Office is "
            "equal to the rate for level IV of the Executive Schedule."
        ),
    },
    # The remaining-departments cluster of the same batch: the Energy
    # Department's Under Secretary for Nuclear Security, whose own section
    # pays the office at Level III and, two paragraphs on, makes that officer
    # the Administrator of the National Nuclear Security Administration — the
    # title this graph carries. The Schedule's counted class "Under
    # Secretaries of Energy (3)" agrees and is not needed.
    "exec-dept-doe-nnsa-administrator-nnsa": {
        "nodeName": "Administrator, NNSA",
        "office": "Under Secretary for Nuclear Security, who serves as the Administrator for Nuclear Security",
        "citation": "42 U.S.C. 7132(c)(1)",
        "fixture": "doe_42_usc_7132_govinfo2024.html",
        "subsection": "(c)(1)",
        "level": "III",
        "percent": 0,
        "quote": (
            "The Under Secretary shall be compensated at the rate provided for at level III of the Executive "
            "Schedule under section 5314 of title 5."
        ),
        "identificationQuote": (
            "The Under Secretary for Nuclear Security shall serve as the Administrator for Nuclear Security "
            "under section 2402 of title 50."
        ),
    },
}

#: The Inspector General Act's rate, and the section that says whose.
INSPECTOR_GENERAL_RULE: dict[str, Any] = {
    "title": "Inspector General",
    "citation": "5 U.S.C. 403(e)",
    "fixture": "ig_5_usc_403.html",
    "subsection": "(e) Rate of Pay",
    "level": "III",
    "percent": 3,
    "quote": (
        "The annual rate of basic pay for an Inspector General (as defined under section 401 of this "
        "title ) shall be the rate payable for level III of the Executive Schedule under section 5314 "
        "of this title , plus 3 percent."
    ),
    "establishmentsCitation": "5 U.S.C. 401(1)",
    "establishmentsFixture": "ig_5_usc_401.html",
    "definitionCitation": "5 U.S.C. 401(4)",
    "definitionQuote": 'The term "Inspector General" means the Inspector General of an establishment.',
}

#: Read, and deliberately not priced, with the reason -- printed by the
#: derive step beside the refusals so each is visibly a decision.
NOT_PRICED_KINDS = {
    "not_an_establishment": (
        "the node's organisation is not one 5 U.S.C. 401(1) lists, so 403(e) does not set its pay: "
        "a designated Federal entity's IG (5 U.S.C. 415, read and committed, prints no rate of pay), "
        "a Defense agency's stamped 'Inspector General' beneath the Department's own, a legislative "
        "office's, or the CIA's (5 U.S.C. 423, not read)"
    ),
    "americorps_named_only_in_the_alias_table": (
        "5 U.S.C. 401(1) lists the Corporation for National and Community Service; this graph calls it "
        "AmeriCorps and carries the statutory name only in node_aliases.json, which no join that lands "
        "a number may read"
    ),
}

_ESTABLISHMENT_DEFINITION = re.compile(r'The term "establishment" means (.+?), as the case may be\.')


def parse_establishments(operative_401: str) -> list[str]:
    """The establishments 5 U.S.C. 401(1) names, one name per entry, read off
    the section's own definition sentence.

    The statute compresses the departments -- "the Department of Agriculture,
    Commerce, Defense, ..., or Veterans Affairs" -- so the first segment is
    expanded to one "Department of X" per item; the agencies follow, each
    written out, separated by commas with an "or" before the last. A
    description that names no unit ("the Commissions established under
    section 15301 of title 40") comes through as written and matches nothing.
    """
    match = _ESTABLISHMENT_DEFINITION.search(operative_401)
    if match is None:
        raise Unreadable("5 U.S.C. 401 no longer prints the definition of \"establishment\" this module reads")
    segments = [segment.strip() for segment in match.group(1).split(";")]
    if len(segments) != 2 or not segments[0].startswith("the Department of "):
        raise Unreadable("5 U.S.C. 401(1) is no longer printed as departments; then agencies")
    names: list[str] = []
    departments = segments[0][len("the Department of "):]
    for item in _split_list(departments):
        names.append(f"Department of {item}")
    for item in _split_list(segments[1]):
        names.append(item[4:] if item.startswith("the ") else item)
    return names


def _split_list(text: str) -> list[str]:
    items = [part.strip() for part in text.split(",")]
    out: list[str] = []
    for item in items:
        if not item:
            continue
        if item.startswith("or "):
            item = item[3:].strip()
        out.append(item)
    return out


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


def _computed_amount(base: float, percent: int) -> float:
    return round(base * (100 + percent) / 100.0, 2)


def _rate_text(amount: float) -> str:
    return "${:,.0f}".format(amount) if float(amount).is_integer() else "${:,.2f}".format(amount)


def _statute_document(section: Mapping[str, Any], citation: str, quote: str, role: str) -> dict[str, Any]:
    publisher, edition = statute_publisher(str(section["url"]))
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


def _table_document(table: Mapping[str, Any], level_row: Mapping[str, Any], *, url: str, sha256: str,
                    fetched_at: str) -> dict[str, Any]:
    return {
        "role": "states what that Executive Schedule level pays",
        "citation": f"{table['table']}, {table['effectiveText']}",
        "publisher": "U.S. Office of Personnel Management",
        "title": table["table"],
        "quote": level_row["rowText"],
        "url": url,
        "documentSha256": sha256,
        "retrievedAt": fetched_at,
        "statesTheFigure": False,
    }


def build_records(
    node_map: Mapping[str, Mapping[str, Any]],
    parent_map: Mapping[str, str | None],
    loaded_table: Mapping[str, Any],
    *,
    fiscal_year: int,
    directory: str | Path = FIXTURE_DIR,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """One record per GAO row and per Inspector General of an establishment,
    each re-adjudicated: the quote is still in its section's operative text,
    the node still carries the name (or, for an IG, still sits directly under
    a listed establishment), and OPM's table still prices the level."""
    table = loaded_table["table"]
    levels = table["levels"]
    table_url = loaded_table["url"]
    table_sha256 = loaded_table["sha256"]
    table_fetched_at = loaded_table["fetched_at"]

    def section(fixture: str) -> dict[str, Any]:
        path = Path(directory) / fixture
        # `derived_pay.load_section` reads from its own directory; a caller
        # passing another one (a test doctoring a section) gets that one.
        if Path(directory) == FIXTURE_DIR:
            return load_section(fixture)
        return _load_section_from(path)

    records: dict[str, dict[str, Any]] = {}
    refusals: dict[str, str] = {}
    not_priced: dict[str, str] = {}

    # --- the reviewed rows: the GAO's officers, the GPO's, the IES's ---------
    gao_sections: dict[str, dict[str, Any]] = {}
    for node_id, row in sorted(TIER_REFERENCE_PROVISIONS.items()):
        sec = gao_sections.get(row["fixture"])
        if sec is None:
            sec = section(row["fixture"])
            gao_sections[row["fixture"]] = sec
        if row["quote"] not in sec["operative"]:
            where = "only in the publisher's notes" if row["quote"] in sec["whole"] else "nowhere on the page"
            refusals[node_id] = f"{row['citation']} no longer carries the quoted sentence ({where})"
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
            refusals[node_id] = "stands for several posts; a single office's rate is not each holder's"
            continue
        level_row = levels.get(row["level"])
        if level_row is None:
            refusals[node_id] = f"OPM's table does not print level {row['level']}"
            continue
        identification: dict[str, Any] = {"kind": "reviewed_row", "nodeName": row["nodeName"]}
        identifies = row.get("identificationQuote")
        if identifies:
            if identifies not in sec["operative"]:
                where = "only in the publisher's notes" if identifies in sec["whole"] else "nowhere on the page"
                refusals[node_id] = f"{row['citation']}'s section no longer carries the sentence identifying the office ({where})"
                continue
            identification["statuteIdentifies"] = identifies
            identification["office"] = row["office"]
        extra_documents: list[dict[str, Any]] = []
        composition = row.get("composition")
        if composition:
            comp_sec = gao_sections.get(composition["fixture"])
            if comp_sec is None:
                comp_sec = section(composition["fixture"])
                gao_sections[composition["fixture"]] = comp_sec
            if composition["quote"] not in comp_sec["operative"]:
                where = "only in the publisher's notes" if composition["quote"] in comp_sec["whole"] else "nowhere on the page"
                refusals[node_id] = f"{composition['citation']} no longer carries the composing sentence ({where})"
                continue
            extra_documents.append(_statute_document(comp_sec, composition["citation"], composition["quote"], composition["role"]))
        records[node_id] = _record(
            node_id, row["office"], row["citation"], row["subsection"], row["quote"], row["level"],
            int(row["percent"]), sec, level_row, table, fiscal_year,
            table_url=table_url, table_sha256=table_sha256, table_fetched_at=table_fetched_at,
            extra_documents=extra_documents, identification=identification,
        )

    # --- the Inspectors General ----------------------------------------------
    rule = INSPECTOR_GENERAL_RULE
    sec_403 = section(rule["fixture"])
    sec_401 = section(rule["establishmentsFixture"])
    if rule["quote"] not in sec_403["operative"]:
        where = "only in the publisher's notes" if rule["quote"] in sec_403["whole"] else "nowhere on the page"
        refusals["inspector-general-rule"] = f"{rule['citation']} no longer carries the quoted sentence ({where})"
        establishments: list[str] = []
    elif rule["definitionQuote"] not in sec_401["operative"]:
        refusals["inspector-general-rule"] = f"{rule['definitionCitation']} no longer defines an Inspector General as an establishment's"
        establishments = []
    else:
        establishments = parse_establishments(sec_401["operative"])
    establishment_keys = {canonical_name_key(name): name for name in establishments}
    ig_key = canonical_name_key(rule["title"])
    level_row = levels.get(rule["level"])
    ig_considered = 0
    for node_id, node in sorted(node_map.items()):
        if canonical_name_key(node.get("name")) != ig_key or not is_post_node(node):
            continue
        ig_considered += 1
        if not establishments or level_row is None:
            continue
        if STATED_MULTIPLICITY.search(str(node.get("name") or "")):
            refusals[node_id] = "stands for several posts"
            continue
        parent_id = parent_map.get(node_id)
        parent = node_map.get(parent_id or "")
        parent_key = canonical_name_key(parent.get("name")) if parent else ""
        if parent is None or is_post_node(parent) or parent_key not in establishment_keys:
            parent_name = str(parent.get("name") if parent else "")
            if parent_key == canonical_name_key("AmeriCorps"):
                not_priced[node_id] = f"{parent_name}: {NOT_PRICED_KINDS['americorps_named_only_in_the_alias_table']}"
            else:
                not_priced[node_id] = f"{parent_name}: {NOT_PRICED_KINDS['not_an_establishment']}"
            continue
        if node_id in records:
            refusals[node_id] = "already priced by a reviewed row"
            continue
        listed_name = establishment_keys[parent_key]
        records[node_id] = _record(
            node_id, rule["title"], rule["citation"], rule["subsection"], rule["quote"], rule["level"],
            int(rule["percent"]), sec_403, level_row, table, fiscal_year,
            table_url=table_url, table_sha256=table_sha256, table_fetched_at=table_fetched_at,
            extra_documents=[_statute_document(
                sec_401, rule["establishmentsCitation"], rule["definitionQuote"] + " " + _establishment_sentence(sec_401),
                "lists the establishments whose Inspector General 403(e) prices, and this post's organisation is one of them",
            )],
            identification={
                "kind": "establishment_listed_in_5_usc_401",
                "establishment": listed_name,
                "organisationId": str(parent_id or ""),
                "organisationName": str(parent.get("name") or ""),
            },
        )

    report = {
        "source": PAY_SOURCE,
        "table": table["table"],
        "effectiveText": table["effectiveText"],
        "tableUrl": table_url,
        "tableSha256": table_sha256,
        "tableRetrievedAt": table_fetched_at,
        "sections": {
            name: {"url": s["url"], "sha256": s["sha256"], "fetched_at": s["fetched_at"]}
            for name, s in sorted({**gao_sections, rule["fixture"]: sec_403, rule["establishmentsFixture"]: sec_401}.items())
        },
        "establishments": establishments,
        "inspectorGeneralNodesConsidered": ig_considered,
        "reviewedRows": len(TIER_REFERENCE_PROVISIONS),
        "priced": len(records),
        "pricedByReviewedRow": sum(1 for r in records.values() if r["identification"]["kind"] == "reviewed_row"),
        "pricedInspectorsGeneral": sum(1 for r in records.values() if r["identification"]["kind"] != "reviewed_row"),
        "documentsStatingTheFigure": 0,
        "strengthScale": STRENGTH_SCALE,
        "refused": dict(sorted(refusals.items())),
        "notPriced": dict(sorted(not_priced.items())),
        "notPricedKinds": dict(NOT_PRICED_KINDS),
    }
    return records, report


def _establishment_sentence(sec_401: Mapping[str, Any]) -> str:
    match = _ESTABLISHMENT_DEFINITION.search(sec_401["operative"])
    return match.group(0) if match else ""


def _load_section_from(path: Path) -> dict[str, Any]:
    """`derived_pay.load_section` against an explicit path (tests doctor a
    copy of a section in a temporary directory)."""
    import hashlib
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
        "file": str(path), "url": str(meta.get("url") or ""), "fetched_at": str(meta.get("fetched_at") or ""),
        "sha256": digest, "operative": operative_text(decoded),
        "whole": _collapse(html_module.unescape(re.sub(r"<[^>]+>", " ", decoded))),
    }


def _record(
    node_id: str, office: str, citation: str, subsection: str, quote: str, level: str, percent: int,
    section: Mapping[str, Any], level_row: Mapping[str, Any], table: Mapping[str, Any], fiscal_year: int,
    *, table_url: str, table_sha256: str, table_fetched_at: str,
    extra_documents: list[dict[str, Any]], identification: dict[str, Any],
) -> dict[str, Any]:
    base = float(level_row["amount"])
    amount = _computed_amount(base, percent) if percent else base
    amount_raw = "{:,.0f}".format(amount) if float(amount).is_integer() else "{:,.2f}".format(amount)
    rate_text = _rate_text(amount)
    level_text = str(level_row["levelText"])
    if percent:
        arithmetic: dict[str, Any] | None = {
            "operation": "plus_percent",
            "baseAmount": base,
            "baseAmountRaw": str(level_row["amountRaw"]),
            "baseText": str(level_row["rateText"]),
            "baseLevel": level,
            "percent": percent,
            "result": amount,
            "resultText": rate_text,
            "note": (
                f"No document prints {rate_text}. {citation} sets the rate at {level_text}'s "
                f"plus {percent} percent, and {table['table']} prints {level_row['rateText']} for "
                f"{level_text}; the figure is that arithmetic and nothing more."
            ),
        }
        amount_scope = f"{level_text} plus {percent} percent"
        derivation = (
            f"{citation} {subsection}: “{quote}” · {table['table']}, {table['effectiveText']}: "
            f"{level_row['rowText']} · {level_row['rateText']} + {percent}% = {rate_text}"
        )
        method = PAY_METHOD_PERCENT
    else:
        arithmetic = None
        amount_scope = level_text
        derivation = (
            f"{citation} {subsection}: “{quote}” · {table['table']}, {table['effectiveText']}: "
            f"{level_row['rowText']}"
        )
        method = PAY_METHOD
    documents = [
        _statute_document(section, citation, quote,
                          f"sets this post's basic pay by reference to Executive Schedule {level_text}"
                          + (f", plus {percent} percent" if percent else "")),
        _table_document(table, level_row, url=table_url, sha256=table_sha256, fetched_at=table_fetched_at),
        *extra_documents,
    ]
    return {
        "nodeId": node_id,
        "financialEvidenceStatus": "partial",
        "costBasis": "basic_pay",
        "amount": amount,
        "amountRaw": amount_raw,
        "units": "usd",
        "normalizedMultiplier": 1,
        # The table's own row: the level's figure printed with its mark. For a
        # GAO row that is the record's own figure; for an IG it is the figure
        # the record is computed from, which is the narrower rule
        # `financial_evidence.COMPUTED_FROM_MARKED_FIGURE_SOURCE_TYPES` grants.
        "unitsEvidence": str(level_row["rowText"]),
        "quote": derivation,
        "fiscalYear": int(fiscal_year),
        "periodCoverage": "annual_rate",
        "periodAsOf": str(table["effective"]),
        "amountScope": amount_scope,
        "scopeMatch": "proxy",
        "rollupRole": "line",
        "sourceType": PAY_SOURCE_TYPE,
        "sourceUrl": section["url"],
        "documentSha256": section["sha256"],
        "retrievedAt": section["fetched_at"],
        "locator": {"section": citation, "subsection": subsection},
        "method": method,
        "office": office,
        "statute": citation,
        "statuteQuote": quote,
        "level": level,
        "levelText": level_text,
        "levelRateText": str(level_row["rateText"]),
        "levelAmount": base,
        "percent": percent,
        "arithmetic": arithmetic,
        "rateText": rate_text,
        "derivation": derivation,
        "identification": identification,
        "documents": documents,
        "table": table["table"],
        "effectiveText": table["effectiveText"],
        "effective": str(table["effective"]),
        "tableFootnotes": list(table.get("footnotes") or []),
        "tableUrl": table_url,
        "tableSha256": table_sha256,
        "tableRetrievedAt": table_fetched_at,
    }


def apply_pay_evidence(
    root: dict[str, Any],
    records: Mapping[str, Mapping[str, Any]],
    *,
    index_tree: Any = None,
) -> dict[str, Any]:
    """Stamp `positionTierReferencePay`. A node another pay source has already
    priced is left alone, and an IG record is re-scoped against the tree: the
    node must still sit directly under the organisation the record names."""
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, parent_map = index_tree(root)
    stats = {
        "priced": 0,
        "priced_inspectors_general": 0,
        "unknown_node": 0,
        "not_a_position": 0,
        "renamed_since_the_match": 0,
        "reparented_since_the_match": 0,
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
        if identification.get("kind") == "reviewed_row":
            if canonical_name_key(node.get("name")) != canonical_name_key(identification.get("nodeName")):
                stats["renamed_since_the_match"] += 1
                continue
        else:
            if canonical_name_key(node.get("name")) != canonical_name_key(INSPECTOR_GENERAL_RULE["title"]):
                stats["renamed_since_the_match"] += 1
                continue
            if parent_map.get(node_id) != identification.get("organisationId"):
                stats["reparented_since_the_match"] += 1
                continue
        if any(isinstance(node.get(field), dict) for field in (
                "positionStatutoryPay", "positionPayRate", "positionSchedulePay", "positionDerivedPay")):
            stats["already_priced_by_another_source"] += 1
            continue
        node[FIELD] = {
            "source": PAY_SOURCE,
            "sourceLabel": "a statute setting the post's pay by reference to an Executive Schedule level, joined to OPM's table",
            "method": record.get("method"),
            "amount": record.get("amount"),
            "rateText": record.get("rateText"),
            "level": record.get("level"),
            "levelText": record.get("levelText"),
            "levelRateText": record.get("levelRateText"),
            "levelAmount": record.get("levelAmount"),
            "percent": record.get("percent"),
            "arithmetic": dict(record["arithmetic"]) if isinstance(record.get("arithmetic"), dict) else None,
            "office": record.get("office"),
            "statute": record.get("statute"),
            "statuteQuote": record.get("statuteQuote"),
            "identification": dict(identification),
            "derivation": record.get("derivation"),
            "quote": record.get("quote"),
            "documents": [dict(document) for document in record.get("documents") or []],
            "table": record.get("table"),
            "effectiveText": record.get("effectiveText"),
            "effective": record.get("effective"),
            "fiscalYear": record.get("fiscalYear"),
            "footnotes": list(record.get("tableFootnotes") or []),
            "costBasis": record.get("costBasis"),
            "scopeMatch": record.get("scopeMatch"),
            "financialEvidenceStatus": record.get("financialEvidenceStatus"),
            "amountScope": record.get("amountScope"),
            "url": str(record.get("sourceUrl") or ""),
            "tableUrl": str(record.get("tableUrl") or ""),
            "checkedAt": record.get("retrievedAt"),
            # `verification` is stamped by pay_documents.annotate_pay_documents.
        }
        stats["priced"] += 1
        if identification.get("kind") != "reviewed_row":
            stats["priced_inspectors_general"] += 1
        # Deliberately not written: sourceUrls, sourceTypes, lastVerified,
        # verificationMethod.
    return stats
