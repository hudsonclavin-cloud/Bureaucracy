#!/usr/bin/env python3
"""Release gate for the published graph.

Reads output/graph.json (or a path given as the first argument) and exits
nonzero if any node asserts more than its evidence supports. This runs over the
real artefact rather than a fixture, which is the only way it could have caught
the three validator failures of this week: each one produced a plausible number
and passed its own unit tests.

The gate never writes. Run it before every push that touches output/.
"""

from __future__ import annotations

import io
import json
import re
from datetime import datetime, timezone
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GRAPH = PROJECT_ROOT / "output" / "graph.json"

EXPECTED_ROOT_ID = "the-constitution-of-the-united-states"
MAX_TOP_LEVEL_CHILDREN = 10
CHILD_SUM_TOLERANCE = 0.005  # 0.5%, for rounding in the apportionment cascade
SAMPLE_LIMIT = 20

# OPM's Salary Table No. 2026-EX, mirrored so the gate can check a published
# rate against the figure the table actually prints. The gate is stdlib-only
# and reads one file — it cannot parse the fixture — and without a mirror it
# could not tell $209,600 from $290,600 on any node. The mirror is pinned to
# the fetched page by tests/test_pay_tables.py, which parses
# tests/fixtures/opm/pay/executive_schedule_2026.html and asserts equality, so
# the two cannot drift apart silently. Same precedent as `position_title_keys`.
EXECUTIVE_SCHEDULE_TABLE = "Salary Table No. 2026-EX"
EXECUTIVE_SCHEDULE_RATES = {
    "I": 253_100.0,
    "II": 228_000.0,
    "III": 209_600.0,
    "IV": 197_200.0,
    "V": 184_900.0,
}
#: node id -> (the title 5 U.S.C. 5312-5316 prints, its level, its section,
#: and the organisation it was scoped to, or None when the node's whole name
#: is the statutory title).
#: Keyed by node id for the reason STATUTORY_PAY_NODE_TIERS established and
#: more sharply still: FIFTEEN of these nodes are priced at Level I and carry
#: the identical $253,100, so a record moved from the Secretary of Agriculture
#: to the Secretary of Commerce would keep a correct figure, a correct rate
#: text, a correct citation and a real statutory title. Only a check tied to
#: the node's own identity catches it. The statute's own words are mirrored
#: too, because the panel prints them as the Code's: a published title the
#: statute does not carry is a fabricated quotation attributed to Congress.
#: tests/test_statutory_schedule.py parses the committed sections and asserts
#: this mirror equals what they print, so the two cannot drift.
US_CODE_EXECUTIVE_SCHEDULE = {
    'exec-dept-defense-af-secretary-of-the-air-force': ('Secretary of the Air Force', 'II', '5313', None),
    'exec-dept-defense-af-under-secretary-of-the-air-force': ('Under Secretary of the Air Force', 'III', '5314', None),
    'exec-dept-defense-agency-nsa-deputy-director-national-security-agency-nsa': ('Deputy Director, National Security Agency', 'V', '5316', None),
    'exec-dept-defense-army-secretary-of-the-army': ('Secretary of the Army', 'II', '5313', None),
    'exec-dept-defense-army-under-secretary-of-the-army': ('Under Secretary of the Army', 'III', '5314', None),
    'exec-dept-defense-deputy-secretary-of-defense': ('Deputy Secretary of Defense', 'II', '5313', None),
    'exec-dept-defense-general-counsel': ('General Counsel of the Department of Defense', 'IV', '5315', 'exec-dept-defense'),
    'exec-dept-defense-navy-secretary-of-the-navy': ('Secretary of the Navy', 'II', '5313', None),
    'exec-dept-defense-navy-under-secretary-of-the-navy': ('Under Secretary of the Navy', 'III', '5314', None),
    'exec-dept-defense-secretary-of-defense': ('Secretary of Defense', 'I', '5312', None),
    'exec-dept-dhs-chief-financial-officer': ('Chief Financial Officer, Department of Homeland Security', 'IV', '5315', 'exec-dept-dhs'),
    'exec-dept-dhs-chief-information-officer': ('Chief Information Officer, Department of Homeland Security', 'IV', '5315', 'exec-dept-dhs'),
    'exec-dept-dhs-general-counsel': ('General Counsel, Department of Homeland Security', 'IV', '5315', 'exec-dept-dhs'),
    'exec-dept-dhs-tsa-deputy-administrator': ('Deputy Administrator, Transportation Security Administration', 'III', '5314', 'exec-dept-dhs-tsa'),
    'exec-dept-doc-chief-financial-officer': ('Chief Financial Officer, Department of Commerce', 'IV', '5315', 'exec-dept-doc'),
    'exec-dept-doc-chief-information-officer': ('Chief Information Officer, Department of Commerce', 'IV', '5315', 'exec-dept-doc'),
    'exec-dept-doc-general-counsel': ('General Counsel of the Department of Commerce', 'IV', '5315', 'exec-dept-doc'),
    'exec-dept-doc-secretary-of-department-of-commerce': ('Secretary of Commerce', 'I', '5312', None),
    'exec-dept-doe-chief-financial-officer': ('Chief Financial Officer, Department of Energy', 'IV', '5315', 'exec-dept-doe'),
    'exec-dept-doe-chief-information-officer': ('Chief Information Officer, Department of Energy', 'IV', '5315', 'exec-dept-doe'),
    'exec-dept-doe-deputy-secretary-of-department-of-energy-doe': ('Deputy Secretary of Energy', 'II', '5313', None),
    'exec-dept-doe-general-counsel': ('General Counsel of the Department of Energy', 'IV', '5315', 'exec-dept-doe'),
    'exec-dept-doe-nnsa-principal-deputy-administrator': ('Principal Deputy Administrator, National Nuclear Security Administration', 'IV', '5315', 'exec-dept-doe-nnsa'),
    'exec-dept-doe-secretary-of-department-of-energy-doe': ('Secretary of Energy', 'I', '5312', None),
    'exec-dept-doi-chief-financial-officer': ('Chief Financial Officer, Department of the Interior', 'IV', '5315', 'exec-dept-doi'),
    'exec-dept-doi-chief-information-officer': ('Chief Information Officer, Department of the Interior', 'IV', '5315', 'exec-dept-doi'),
    'exec-dept-doi-deputy-secretary-of-department-of-the-interior-doi': ('Deputy Secretary of the Interior', 'II', '5313', None),
    'exec-dept-doi-secretary-of-department-of-the-interior-doi': ('Secretary of the Interior', 'I', '5312', None),
    'exec-dept-doj-chief-financial-officer': ('Chief Financial Officer, Department of Justice', 'IV', '5315', 'exec-dept-doj'),
    'exec-dept-doj-chief-information-officer': ('Chief Information Officer, Department of Justice', 'IV', '5315', 'exec-dept-doj'),
    'exec-dept-doj-deputy-secretary-of-department-of-justice-doj': ('Deputy Attorney General', 'II', '5313', None),
    'exec-dept-doj-secretary-of-department-of-justice-doj': ('Attorney General', 'I', '5312', None),
    'exec-dept-doj-solicitor-solicitor-general-of-the-united-states': ('Solicitor General of the United States', 'III', '5314', None),
    'exec-dept-dol-chief-financial-officer': ('Chief Financial Officer, Department of Labor', 'IV', '5315', 'exec-dept-dol'),
    'exec-dept-dol-chief-information-officer': ('Chief Information Officer, Department of Labor', 'IV', '5315', 'exec-dept-dol'),
    'exec-dept-dol-deputy-secretary-of-department-of-labor-dol': ('Deputy Secretary of Labor', 'II', '5313', None),
    'exec-dept-dol-secretary-of-department-of-labor-dol': ('Secretary of Labor', 'I', '5312', None),
    'exec-dept-dot-chief-financial-officer': ('Chief Financial Officer, Department of Transportation', 'IV', '5315', 'exec-dept-dot'),
    'exec-dept-dot-chief-information-officer': ('Chief Information Officer, Department of Transportation', 'IV', '5315', 'exec-dept-dot'),
    'exec-dept-dot-deputy-secretary-of-department-of-transportation-dot': ('Deputy Secretary of Transportation', 'II', '5313', None),
    'exec-dept-dot-faa-deputy-administrator': ('Deputy Administrator, Federal Aviation Administration', 'IV', '5315', 'exec-dept-dot-faa'),
    'exec-dept-dot-general-counsel': ('General Counsel, Department of Transportation', 'IV', '5315', 'exec-dept-dot'),
    'exec-dept-dot-secretary-of-department-of-transportation-dot': ('Secretary of Transportation', 'I', '5312', None),
    'exec-dept-ed-chief-financial-officer': ('Chief Financial Officer, Department of Education', 'IV', '5315', 'exec-dept-ed'),
    'exec-dept-ed-chief-information-officer': ('Chief Information Officer, Department of Education', 'IV', '5315', 'exec-dept-ed'),
    'exec-dept-ed-deputy-secretary-of-department-of-education': ('Deputy Secretary of Education', 'II', '5313', None),
    'exec-dept-ed-general-counsel': ('General Counsel, Department of Education', 'IV', '5315', 'exec-dept-ed'),
    'exec-dept-ed-secretary-of-department-of-education': ('Secretary of Education', 'I', '5312', None),
    'exec-dept-hhs-chief-financial-officer': ('Chief Financial Officer, Department of Health and Human Services', 'IV', '5315', 'exec-dept-hhs'),
    'exec-dept-hhs-chief-information-officer': ('Chief Information Officer, Department of Health and Human Services', 'IV', '5315', 'exec-dept-hhs'),
    'exec-dept-hhs-deputy-secretary-of-department-of-health-human-services-hhs': ('Deputy Secretary of Health and Human Services', 'II', '5313', None),
    'exec-dept-hhs-general-counsel': ('General Counsel of the Department of Health and Human Services', 'IV', '5315', 'exec-dept-hhs'),
    'exec-dept-hhs-secretary-of-department-of-health-human-services-hhs': ('Secretary of Health and Human Services', 'I', '5312', None),
    'exec-dept-hud-chief-financial-officer': ('Chief Financial Officer, Department of Housing and Urban Development', 'IV', '5315', 'exec-dept-hud'),
    'exec-dept-hud-chief-information-officer': ('Chief Information Officer, Department of Housing and Urban Development', 'IV', '5315', 'exec-dept-hud'),
    'exec-dept-hud-deputy-secretary-of-department-of-housing-urban-development-hud': ('Deputy Secretary of Housing and Urban Development', 'II', '5313', None),
    'exec-dept-hud-general-counsel': ('General Counsel of the Department of Housing and Urban Development', 'IV', '5315', 'exec-dept-hud'),
    'exec-dept-hud-secretary-of-department-of-housing-urban-development-hud': ('Secretary of Housing and Urban Development', 'I', '5312', None),
    'exec-dept-state-chief-financial-officer': ('Chief Financial Officer, Department of State', 'IV', '5315', 'exec-dept-state'),
    'exec-dept-state-chief-information-officer': ('Chief Information Officer, Department of State', 'IV', '5315', 'exec-dept-state'),
    'exec-dept-state-deputy-secretary-of-department-of-state': ('Deputy Secretary of State', 'II', '5313', None),
    'exec-dept-state-secretary-of-department-of-state': ('Secretary of State', 'I', '5312', None),
    'exec-dept-treasury-chief-financial-officer': ('Chief Financial Officer, Department of the Treasury', 'IV', '5315', 'exec-dept-treasury'),
    'exec-dept-treasury-chief-information-officer': ('Chief Information Officer, Department of the Treasury', 'IV', '5315', 'exec-dept-treasury'),
    'exec-dept-treasury-deputy-secretary-of-department-of-the-treasury': ('Deputy Secretary of the Treasury', 'II', '5313', None),
    'exec-dept-treasury-general-counsel': ('General Counsel of the Department of the Treasury', 'IV', '5315', 'exec-dept-treasury'),
    'exec-dept-treasury-occ-comptroller-of-the-currency': ('Comptroller of the Currency', 'III', '5314', None),
    'exec-dept-treasury-secretary-of-department-of-the-treasury': ('Secretary of the Treasury', 'I', '5312', None),
    'exec-dept-usda-chief-financial-officer': ('Chief Financial Officer, Department of Agriculture', 'IV', '5315', 'exec-dept-usda'),
    'exec-dept-usda-chief-information-officer': ('Chief Information Officer, Department of Agriculture', 'IV', '5315', 'exec-dept-usda'),
    'exec-dept-usda-deputy-secretary-of-department-of-agriculture-usda': ('Deputy Secretary of Agriculture', 'II', '5313', None),
    'exec-dept-usda-general-counsel': ('General Counsel of the Department of Agriculture', 'IV', '5315', 'exec-dept-usda'),
    'exec-dept-usda-secretary-of-department-of-agriculture-usda': ('Secretary of Agriculture', 'I', '5312', None),
    'exec-dept-va-bva-chairman-board-of-veterans-appeals': ("Chairman, Board of Veterans' Appeals", 'IV', '5315', None),
    'exec-dept-va-chief-financial-officer': ('Chief Financial Officer, Department of Veterans Affairs', 'IV', '5315', 'exec-dept-va'),
    'exec-dept-va-chief-information-officer': ('Chief Information Officer, Department of Veterans Affairs', 'IV', '5315', 'exec-dept-va'),
    'exec-dept-va-deputy-secretary-of-department-of-veterans-affairs-va': ('Deputy Secretary of Veterans Affairs', 'II', '5313', None),
    'exec-dept-va-general-counsel': ('General Counsel, Department of Veterans Affairs', 'IV', '5315', 'exec-dept-va'),
    'exec-dept-va-secretary-of-department-of-veterans-affairs-va': ('Secretary of Veterans Affairs', 'I', '5312', None),
    'exec-eop-omb-deputy-director-for-management': ('Deputy Director for Management, Office of Management and Budget', 'II', '5313', 'exec-eop-omb'),
    'exec-eop-ustr-chief-agricultural-negotiator': ('Chief Agricultural Negotiator, Office of the United States Trade Representative', 'III', '5314', 'exec-eop-ustr'),
    'exec-eop-ustr-u-s-trade-representative-ambassador': ('United States Trade Representative', 'I', '5312', None),
    'exec-ind-cia-general-counsel': ('General Counsel of the Central Intelligence Agency', 'IV', '5315', 'exec-ind-cia'),
    'exec-ind-epa-chief-financial-officer': ('Chief Financial Officer, Environmental Protection Agency', 'IV', '5315', 'exec-ind-epa'),
    'exec-ind-epa-chief-information-officer': ('Chief Information Officer, Environmental Protection Agency', 'IV', '5315', 'exec-ind-epa'),
    'exec-ind-epa-deputy-administrator': ('Deputy Administrator of the Environmental Protection Agency', 'III', '5314', 'exec-ind-epa'),
    'exec-ind-misc-equal-employment-opportunity-commission-eeoc-general-counsel': ('General Counsel of the Equal Employment Opportunity Commission', 'V', '5316', 'exec-ind-misc-equal-employment-opportunity-commission-eeoc'),
    'exec-ind-misc-national-labor-relations-board-nlrb-independent-general-counsel': ('General Counsel of the National Labor Relations Board', 'IV', '5315', 'exec-ind-misc-national-labor-relations-board-nlrb-independent'),
    'exec-ind-nasa-associate-administrator': ('Associate Administrator of the National Aeronautics and Space Administration', 'IV', '5315', 'exec-ind-nasa'),
    'exec-ind-nasa-chief-financial-officer': ('Chief Financial Officer, National Aeronautics and Space Administration', 'IV', '5315', 'exec-ind-nasa'),
    'exec-ind-nasa-chief-information-officer': ('Chief Information Officer, National Aeronautics and Space Administration', 'IV', '5315', 'exec-ind-nasa'),
    'exec-ind-nasa-deputy-administrator': ('Deputy Administrator of the National Aeronautics and Space Administration', 'III', '5314', 'exec-ind-nasa'),
    'exec-ind-nasa-general-counsel': ('General Counsel of the National Aeronautics and Space Administration', 'V', '5316', 'exec-ind-nasa'),
    'exec-ind-nsf-chief-information-officer': ('Chief Information Officer, National Science Foundation', 'IV', '5315', 'exec-ind-nsf'),
    'exec-ind-opm-chief-information-officer': ('Chief Information Officer, Office of Personnel Management', 'IV', '5315', 'exec-ind-opm'),
    'exec-ind-opm-deputy-director': ('Deputy Director of the Office of Personnel Management', 'III', '5314', 'exec-ind-opm'),
    'exec-ind-sba-deputy-administrator': ('Deputy Administrator of the Small Business Administration', 'IV', '5315', 'exec-ind-sba'),
    'exec-regulatory-nrc-executive-director-for-operations': ('Executive Director for Operations, Nuclear Regulatory Commission', 'IV', '5315', 'exec-regulatory-nrc'),
    'exec-regulatory-nrc-general-counsel': ('General Counsel of the Nuclear Regulatory Commission', 'V', '5316', 'exec-regulatory-nrc'),
}
US_CODE_SECTIONS = ("5312", "5313", "5314", "5315", "5316")
US_CODE_HOST = "uscode.house.gov"

# The third route into positionSchedulePay: a REVIEWED identification. Neither
# matcher can make these -- "Chair, Board of Governors" is not equal to the
# Code's "Chairman, Board of Governors of the Federal Reserve System", and the
# two Vice Chairs are placed by a title that never names them ("Members,
# Board of Governors ...", §5313). What makes a Vice Chairman a member is a
# SECOND statute, 12 U.S.C. 242, and the row carries the sentence of it that
# says so. Mirrored by node id with the name each row was written against and
# the basis quote, and pinned equal to `statutory_schedule.REVIEWED_TITLE_ROWS`
# by tests/test_statutory_schedule.py. The gate recomputes the basis fixture's
# digest and re-finds the quote in the section's OPERATIVE text with its own
# stdlib cut -- a quote found only beneath the law, in the publisher's notes,
# is refused for the reason the CAVC's repealed subsection taught.
US_CODE_SCHEDULE_METHOD = "level_assigned_by_5_usc_5312_5316"
US_CODE_SCHEDULE_SCOPED_METHOD = "level_assigned_by_5_usc_5312_5316_to_this_post_in_this_organisation"
US_CODE_REVIEWED_METHOD = (
    "level_assigned_by_5_usc_5312_5316_to_the_office_a_second_statute_identifies_this_post_as"
)
US_CODE_BASIS_FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "uscode"
#: Mirrors statutory_schedule.CLASS_TITLE_PREFIX: the only title shape a
#: class-title row may cite.
US_CODE_CLASS_TITLE_PREFIX = "Members, "
#: node id -> (node name the row was written against, statutory title, level,
#: section, basis citation, basis fixture, the basis section's own sentence,
#: the reviewed basis in words -- printed by the panel as the reason the
#: figure applies, so it is a fabricated-reason channel unless mirrored --
#: and whether the row prices a BENCH from the Code's class title: True only
#: where the title is "Members, ..." and the node's name states "(×N)", and
#: the one thing that lets a positionSchedulePay block stay on a multi-post
#: node, with `holders`, instead of being stripped as one appointment's level)
#: A COUNTED class of offices, mirrored from `statutory_schedule.COUNTED_CLASSES`
#: and pinned equal to it by tests/test_counted_classes.py: which section
#: prints the class, the singular office a member's name must begin with,
#: the organisation every member must sit inside, the statute that composes
#: the class (or None), and the reviewed member ids with the sentence the
#: composing statute names the office by (or None). The Code's own count is
#: read off the title on every run and never written down.
#: The exporter's own "(×N)" reader, mirrored stdlib-only: what a node's name
#: says about how many posts it stands for.
US_CODE_STATED_MULTIPLICITY = re.compile(r"\(\s*[\u00d7x]\s*([^)]+?)\s*\)", re.IGNORECASE)
US_CODE_SECTIONS_LEVELS = {'5312': 'I', '5313': 'II', '5314': 'III', '5315': 'IV', '5316': 'V'}
US_CODE_COUNTED_METHOD = 'level_assigned_by_5_usc_5312_5316_to_a_counted_class_of_offices_this_post_is_one_of'
US_CODE_COUNTED_CLASS_SEPARATORS = (', ', ' for ', ' of the ', ' of ', ' — ', ' / ', ' - ')
US_CODE_COUNTED_CLASSES = {
    'Assistant Attorneys General (11)': {
        "section": '5315', "singular": 'Assistant Attorney General', "scopeId": 'exec-dept-doj',
        "departmentWords": (),
        "composition": ('28 U.S.C. 506', 'aag_28_usc_506.html',
                        'The President shall appoint, by and with the advice and consent of the Senate, 11 Assistant Attorneys General, who shall assist the Attorney General in the performance of his duties.'),
        "basis": "5 U.S.C. 5315 places the eleven Assistant Attorneys General at Level IV as a class and names none of them; 28 U.S.C. 506 creates the eleven offices; each of these nodes is named as the Assistant Attorney General heading one of the Department's litigating divisions",
        "members": {
            'exec-dept-doj-div-antitrust-assistant-attorney-general-antitrust-division': None,
            'exec-dept-doj-div-civil-assistant-attorney-general-civil-division': None,
            'exec-dept-doj-div-civil-rights-assistant-attorney-general-civil-rights-division': None,
            'exec-dept-doj-div-criminal-assistant-attorney-general-criminal-division': None,
            'exec-dept-doj-div-enrd-assistant-attorney-general-environment-natural-resources-division': None,
            'exec-dept-doj-div-nsd-assistant-attorney-general-national-security-division': None,
            'exec-dept-doj-div-tax-assistant-attorney-general-tax-division': None,
        },
    },
    'Assistant Administrators, Environmental Protection Agency (8)': {
        "section": '5315', "singular": 'Assistant Administrator', "scopeId": 'exec-ind-epa',
        "departmentWords": (),
        "composition": None,
        "basis": "5 U.S.C. 5315 places the Agency's eight Assistant Administrators at Level IV as a class and names none of them (it also prints two of them under older office names, at the same level); no statute composing the class has been read here, so the record rests on the Code and the table alone; each node is named as the Assistant Administrator heading one of the Agency's national programme offices",
        "members": {
            'exec-ind-epa-office-of-air-radiation-oar-assistant-administrator-office-of-air-radiation': None,
            'exec-ind-epa-office-of-water-ow-assistant-administrator-office-of-water': None,
            'exec-ind-epa-office-of-land-emergency-management-olem-assistant-administrator-office-of-land-emergency-management': None,
            'exec-ind-epa-office-of-chemical-safety-pollution-prevention-ocspp-assistant-administrator-office-of-chemical-safety-pollution-prevention': None,
            'exec-ind-epa-office-of-research-development-ord-assistant-administrator-office-of-research-development': None,
            'exec-ind-epa-office-of-enforcement-compliance-assurance-oeca-assistant-administrator-office-of-enforcement-compliance-assurance': None,
            'exec-ind-epa-office-of-international-tribal-affairs-oita-assistant-administrator-office-of-international-tribal-affairs': None,
        },
    },
    'Assistant Secretaries of State (24)': {
        "section": '5315', "singular": 'Assistant Secretary', "scopeId": 'exec-dept-state',
        "departmentWords": ('State',),
        "composition": ('22 U.S.C. 2651a', 'state_22_usc_2651a.html',
                        'There shall be in the Department of State not more than 24 Assistant Secretaries of State who shall be compensated at the rate provided for at level IV of the Executive Schedule under section 5315 of title 5'),
        "basis": "5 U.S.C. 5315 places the Assistant Secretaries of State at Level IV as a class of not more than 24 (the section prints the class inside a longer paragraph naming four other officials, which the title parser sets aside, so the printed words are checked directly); 22 U.S.C. 2651a(c) composes the class at the same level and itself names eight of these bureaux' heads as Assistant Secretaries; each node is named as the Assistant Secretary heading one bureau",
        "members": {
            'exec-dept-state-bureau-of-african-affairs-assistant-secretary-bureau-of-african-affairs': 'The Assistant Secretary for African Affairs shall be the head of the Bureau of African Affairs.',
            'exec-dept-state-bureau-of-east-asian-pacific-affairs-assistant-secretary-bureau-of-east-asian-pacific-affairs': 'The Assistant Secretary for East Asian and Pacific Affairs shall be the head of the Bureau of East Asian and Pacific Affairs.',
            'exec-dept-state-bureau-of-european-eurasian-affairs-assistant-secretary-bureau-of-european-eurasian-affairs': 'The Assistant Secretary for European and Eurasian Affairs shall be the head of the Bureau of European and Eurasian Affairs.',
            'exec-dept-state-bureau-of-near-eastern-affairs-assistant-secretary-bureau-of-near-eastern-affairs': 'The Assistant Secretary for Near Eastern Affairs shall be the head of the Bureau of Near Eastern Affairs.',
            'exec-dept-state-bureau-of-south-central-asian-affairs-assistant-secretary-bureau-of-south-central-asian-affairs': 'The Assistant Secretary for South and Central Asian Affairs shall be the head of the Bureau of South and Central Asian Affairs.',
            'exec-dept-state-bureau-of-western-hemisphere-affairs-assistant-secretary-bureau-of-western-hemisphere-affairs': 'The Assistant Secretary for Western Hemisphere Affairs shall be the head of the Bureau of Western Hemisphere Affairs.',
            'exec-dept-state-bureau-of-international-organization-affairs-assistant-secretary-bureau-of-international-organization-affairs': 'The Assistant Secretary for International Organization Affairs shall be the head of the Bureau of International Organization Affairs.',
            'exec-dept-state-bureau-of-consular-affairs-assistant-secretary-bureau-of-consular-affairs': 'The Assistant Secretary for Consular Affairs shall be the head of the Bureau of Consular Affairs.',
            'exec-dept-state-bureau-of-arms-control-verification-compliance-assistant-secretary-bureau-of-arms-control-verification-compliance': None,
            'exec-dept-state-bureau-of-international-security-nonproliferation-assistant-secretary-bureau-of-international-security-nonproliferation': None,
            'exec-dept-state-bureau-of-political-military-affairs-assistant-secretary-bureau-of-political-military-affairs': None,
            'exec-dept-state-bureau-of-diplomatic-security-assistant-secretary-bureau-of-diplomatic-security': None,
            'exec-dept-state-bureau-of-global-public-affairs-assistant-secretary-bureau-of-global-public-affairs': None,
        },
    },
    'Assistant Secretaries of Labor (10)': {
        "section": '5315', "singular": 'Assistant Secretary', "scopeId": 'exec-dept-dol',
        "departmentWords": ('Labor',),
        "composition": ('29 U.S.C. 553', 'labor_29_usc_553.html',
                        'There are established in the Department of Labor nine offices of Assistant Secretary of Labor, which shall be filled by appointment by the President, by and with the advice and consent of the Senate.'),
        "basis": "5 U.S.C. 5315 places the Assistant Secretaries of Labor at Level IV as a class of ten (its paragraph goes on to name the one for Veterans' Employment and Training, which is why the title parser reads it as a single post and the printed words are checked directly); 29 U.S.C. 553 establishes nine of the offices and names the one for Occupational Safety and Health; each node is named as an Assistant Secretary heading one of the Department's agencies",
        "members": {
            'exec-dept-dol-osha-assistant-secretary-of-labor-for-occupational-safety-health': 'One of such Assistant Secretaries shall be an Assistant Secretary of Labor for Occupational Safety and Health.',
            'exec-dept-dol-eta-assistant-secretary-for-employment-training': None,
            'exec-dept-dol-ebsa-assistant-secretary-of-labor-for-ebsa': None,
        },
    },
    'Assistant Secretaries of Education (10)': {
        "section": '5315', "singular": 'Assistant Secretary', "scopeId": 'exec-dept-ed',
        "departmentWords": ('Education',),
        "composition": ('20 U.S.C. 3412', 'education_20_usc_3412.html',
                        'There shall be in the Department- (A) an Assistant Secretary for Elementary and Secondary Education; (B) an Assistant Secretary for Postsecondary Education; (C) an Assistant Secretary for Career, Technical, and Adult Education; (D) an Assistant Secretary for Special Education and Rehabilitative Services; (E) an Assistant Secretary for Civil Rights'),
        "basis": "5 U.S.C. 5315 places the Assistant Secretaries of Education at Level IV as a class of ten; 20 U.S.C. 3412(b) establishes the offices and names each of these two by title; each node is named as the Assistant Secretary heading one of the Department's principal offices",
        "members": {
            'exec-dept-ed-oese-assistant-secretary-for-oese': '(A) an Assistant Secretary for Elementary and Secondary Education',
            'exec-dept-ed-ocr-assistant-secretary-for-civil-rights': '(E) an Assistant Secretary for Civil Rights',
        },
    },
    'Assistant Secretaries of Housing and Urban Development (8)': {
        "section": '5315', "singular": 'Assistant Secretary', "scopeId": 'exec-dept-hud',
        "departmentWords": ('Housing and Urban Development', 'Housing & Urban Development', 'HUD'),
        "composition": ('42 U.S.C. 3533', 'hud_42_usc_3533.html',
                        'There shall be in the Department a Deputy Secretary, 7 Assistant Secretaries, and a General Counsel, who shall be appointed by the President by and with the advice and consent of the Senate'),
        "basis": "5 U.S.C. 5315 places the Assistant Secretaries of Housing and Urban Development at Level IV as a class of eight; 42 U.S.C. 3533(a) establishes seven Assistant Secretaries (the two documents disagree by one, and the Code's own count is the bound used here) and names the Federal Housing Commissioner as one of them; each node is named as the Assistant Secretary heading one of the Department's programme offices",
        "members": {
            'exec-dept-hud-fha-assistant-secretary-for-housing-fha-commissioner': 'There shall be in the Department a Federal Housing Commissioner, who shall be one of the Assistant Secretaries, who shall head a Federal Housing Administration within the Department',
            'exec-dept-hud-pih-assistant-secretary-for-public-indian-housing': None,
            'exec-dept-hud-cpd-assistant-secretary-for-community-planning-development': None,
            'exec-dept-hud-fheo-assistant-secretary-for-fair-housing-equal-opportunity': None,
        },
    },
    'Assistant Secretaries of Energy (8)': {
        "section": '5315', "singular": 'Assistant Secretary', "scopeId": 'exec-dept-doe',
        "departmentWords": ('Energy',),
        "composition": ('42 U.S.C. 7133', 'energy_42_usc_7133.html',
                        'There shall be in the Department 8 Assistant Secretaries, each of whom shall be appointed by the President, by and with the advice and consent of the Senate; who shall be compensated at the rate provided for at level IV of the Executive Schedule under section 5315 of title 5'),
        "basis": "5 U.S.C. 5315 places the Assistant Secretaries of Energy at Level IV as a class of eight; 42 U.S.C. 7133(a) establishes the eight at the same level and assigns their functions without naming the offices; each node is named as the Assistant Secretary heading one of the Department's programme offices",
        "members": {
            'exec-dept-doe-eere-assistant-secretary-eere': None,
            'exec-dept-doe-em-assistant-secretary-for-environmental-management': None,
        },
    },
    'Assistant Secretaries of Commerce (11)': {
        "section": '5315', "singular": 'Assistant Secretary', "scopeId": 'exec-dept-doc',
        "departmentWords": ('Commerce',),
        "composition": None,
        "basis": "5 U.S.C. 5315 places the Assistant Secretaries of Commerce at Level IV as a class of eleven and names none of them; no statute composing the class has been read here (15 U.S.C. 1506 was read and adds one office to those 'now provided for by law' without counting them), so the record rests on the Code and the table alone; each node is named as an Assistant Secretary heading one of the International Trade Administration's units",
        "members": {
            'exec-dept-doc-ita-assistant-secretary-global-markets': None,
            'exec-dept-doc-ita-assistant-secretary-enforcement-compliance': None,
        },
    },
}
US_CODE_REVIEWED_IDENTIFICATIONS = {
    "exec-regulatory-fed-chair-board-of-governors": (
        "Chair, Board of Governors",
        "Chairman, Board of Governors of the Federal Reserve System", "I", "5312",
        "12 U.S.C. 242", "fed_12_usc_242.html",
        "1 shall be designated by the President, by and with the advice and consent of the Senate, "
        "to serve as Chairman of the Board for a term of 4 years",
        "the same office: 12 U.S.C. 242 designates one member of the Board to serve as Chairman of the "
        "Board, and 5 U.S.C. 5312 places that Chairman at Level I; the graph spells the title without "
        "gender and without the System's name",
        False,
    ),
    "exec-regulatory-fed-vice-chair-board-of-governors": (
        "Vice Chair, Board of Governors",
        "Members, Board of Governors of the Federal Reserve System", "II", "5313",
        "12 U.S.C. 242", "fed_12_usc_242.html",
        "2 shall be designated by the President, by and with the advice and consent of the Senate, "
        "to serve as Vice Chairmen of the Board",
        "a Vice Chairman is a member of the Board: 12 U.S.C. 242 designates the two Vice Chairmen from "
        "among the members, 5 U.S.C. 5313 places Members of the Board at Level II, and only the Chairman "
        "is placed separately (5312); 5314-5316 print no Federal Reserve entry",
        False,
    ),
    "exec-regulatory-fed-vice-chair-for-supervision": (
        "Vice Chair for Supervision",
        "Members, Board of Governors of the Federal Reserve System", "II", "5313",
        "12 U.S.C. 242", "fed_12_usc_242.html",
        "1 of whom shall be designated Vice Chairman for Supervision",
        "the Vice Chairman for Supervision is one of the two Vice Chairmen 12 U.S.C. 242 designates from "
        "among the members, and 5 U.S.C. 5313 places Members of the Board at Level II",
        False,
    ),
    "exec-regulatory-fcc-chair-fcc": (
        "Chair, FCC",
        "Chairman, Federal Communications Commission", "III", "5314",
        "47 U.S.C. 154", "fcc_47_usc_154.html",
        "The Chairman of the Commission, during the period of his service as Chairman, shall receive an annual salary at the annual rate payable from time to time for level III of the Executive Schedule.",
        "the same office: 47 U.S.C. 154 itself pays the Chairman of the Commission at level III of the Executive Schedule, the level 5 U.S.C. 5314 prints for 'Chairman, Federal Communications Commission'; the graph spells the title without gender and names the Commission by its acronym",
        False,
    ),
    "exec-regulatory-ftc-chair-ftc": (
        "Chair, FTC",
        "Chairman, Federal Trade Commission", "III", "5314",
        "15 U.S.C. 41", "ftc_15_usc_41.html",
        "The President shall choose a chairman from the Commission's membership.",
        "the same office: 15 U.S.C. 41 has the President choose a chairman from the Commission's membership, and 5 U.S.C. 5314 places that Chairman at Level III; the graph spells the title without gender and names the Commission by its acronym",
        False,
    ),
    "exec-dept-treasury-irs-commissioner-irs": (
        "Commissioner, IRS",
        "Commissioner of Internal Revenue", "III", "5314",
        "26 U.S.C. 7803", "irs_26_usc_7803.html",
        "There shall be in the Department of the Treasury a Commissioner of Internal Revenue who shall be appointed by the President, by and with the advice and consent of the Senate.",
        "the same office: 26 U.S.C. 7803 creates the Commissioner of Internal Revenue in the Department of the Treasury, and 5 U.S.C. 5314 places that Commissioner at Level III; the graph files the post under the Internal Revenue Service and names it by the Service's acronym",
        False,
    ),
    "exec-dept-dot-faa-administrator-faa": (
        "Administrator, FAA",
        "Administrator, Federal Aviation Administration", "II", "5313",
        "49 U.S.C. 106", "faa_49_usc_106.html",
        "The head of the Administration is the Administrator, who shall be appointed by the President, by and with the advice and consent of the Senate.",
        "the same office: 49 U.S.C. 106 makes the Administrator the head of the Federal Aviation Administration, and 5 U.S.C. 5313 places that Administrator at Level II; the graph names the Administration by its acronym",
        False,
    ),
    "exec-dept-dhs-secretary-of-department-of-homeland-security-dhs": (
        "Secretary of the Department of Homeland Security",
        "Secretary of Homeland Security", "I", "5312",
        "6 U.S.C. 112", "dhs_6_usc_112.html",
        "There is a Secretary of Homeland Security, appointed by the President, by and with the advice and consent of the Senate.",
        "the same office: 6 U.S.C. 112 creates the Secretary of Homeland Security, and 5 U.S.C. 5312 places that Secretary at Level I; the graph keeps OPM's archive spelling 'Secretary of the Department of Homeland Security' (CURATION.md §8), which whole-name equality cannot reach",
        False,
    ),
    "exec-dept-dhs-deputy-secretary-of-department-of-homeland-security-dhs": (
        "Deputy Secretary of the Department of Homeland Security",
        "Deputy Secretary of Homeland Security", "II", "5313",
        "6 U.S.C. 113", "dhs_6_usc_113.html",
        "A Deputy Secretary of Homeland Security, who shall be the Secretary's first assistant for purposes of subchapter III of chapter 33 of title 5 .",
        "the same office: 6 U.S.C. 113 provides for a Deputy Secretary of Homeland Security as the Secretary's first assistant, and 5 U.S.C. 5313 places that Deputy Secretary at Level II; the graph keeps OPM's archive spelling 'Deputy Secretary of the Department of Homeland Security' (CURATION.md §8), which whole-name equality cannot reach",
        False,
    ),
    "exec-regulatory-fcc-commissioner-4": (
        "Commissioner (×4)",
        "Members, Federal Communications Commission", "IV", "5315",
        "47 U.S.C. 154", "fcc_47_usc_154.html",
        "shall be composed of five commissioners appointed by the President, by and with the advice and consent of the Senate, one of whom the President shall designate as chairman",
        "a bench priced from its class title: 47 U.S.C. 154 composes the Commission of five commissioners, one of whom is designated chairman, so each of the other four is a member of the Commission, and 5 U.S.C. 5315 places 'Members, Federal Communications Commission' at Level IV; the level is the office's and holds for each of the four alike",
        True,
    ),
    "exec-regulatory-ftc-commissioner-4": (
        "Commissioner (×4)",
        "Members, Federal Trade Commission", "IV", "5315",
        "15 U.S.C. 41", "ftc_15_usc_41.html",
        "which shall be composed of five Commissioners, who shall be appointed by the President, by and with the advice and consent of the Senate",
        "a bench priced from its class title: 15 U.S.C. 41 composes the Commission of five Commissioners and has the President choose a chairman from among them, so each of the other four is a member of the Commission, and 5 U.S.C. 5315 places 'Members, Federal Trade Commission' at Level IV; the level is the office's and holds for each of the four alike",
        True,
    ),
    "exec-regulatory-fed-governor-4-members": (
        "Governor (×4 members)",
        "Members, Board of Governors of the Federal Reserve System", "II", "5313",
        "12 U.S.C. 241", "fed_12_usc_241.html",
        "shall be composed of seven members, to be appointed by the President, by and with the advice and consent of the Senate",
        "a bench priced from its class title: 12 U.S.C. 241 composes the Board of seven members, of whom 12 U.S.C. 242 designates a Chairman and two Vice Chairmen, so a Governor is one of the four members holding no designated office, and 5 U.S.C. 5313 places 'Members, Board of Governors of the Federal Reserve System' at Level II; the level is the office's and holds for each alike (the '$15,000 per annum' 12 U.S.C. 241 itself prints is the 1935 figure the Executive Schedule superseded, and nothing here publishes it)",
        True,
    ),
    "exec-regulatory-cftc-commissioner-4": (
        "Commissioner (×4)",
        "Members, Commodity Futures Trading Commission", "IV", "5315",
        "7 U.S.C. 2", "cftc_7_usc_2.html",
        "The Commission shall be composed of five Commissioners who shall be appointed by the President, by and with the advice and consent of the Senate.",
        "a bench priced from its class title: 7 U.S.C. 2 composes the Commission of five Commissioners and has the President appoint one of them as Chairman, so each of the other four is a member of the Commission, and 5 U.S.C. 5315 places 'Members, Commodity Futures Trading Commission' at Level IV; the level is the office's and holds for each of the four alike",
        True,
    ),
    "exec-regulatory-ferc-commissioner-4": (
        "Commissioner (×4)",
        "Members, Federal Energy Regulatory Commission", "IV", "5315",
        "42 U.S.C. 7171", "ferc_42_usc_7171.html",
        "The Commission shall be composed of five members appointed by the President, by and with the advice and consent of the Senate.",
        "a bench priced from its class title: 42 U.S.C. 7171 composes the Commission of five members and has the President designate one as Chairman, so each of the other four is a member of the Commission, and 5 U.S.C. 5315 places 'Members, Federal Energy Regulatory Commission' at Level IV; the level is the office's and holds for each of the four alike",
        True,
    ),
    "exec-regulatory-cftc-chair-cftc": (
        "Chair, CFTC",
        "Chairman, Commodity Futures Trading Commission", "III", "5314",
        "7 U.S.C. 2", "cftc_7_usc_2.html",
        "The President shall appoint, by and with the advice and consent of the Senate, a member of the Commission as Chairman, who shall serve as Chairman at the pleasure of the President.",
        "the same office: 7 U.S.C. 2 has the President appoint a member of the Commission as Chairman, and 5 U.S.C. 5314 places that Chairman at Level III; the graph spells the title without gender and names the Commission by its acronym",
        False,
    ),
    "exec-regulatory-ferc-chair-ferc": (
        "Chair, FERC",
        "Chairman, Federal Energy Regulatory Commission", "III", "5314",
        "42 U.S.C. 7171", "ferc_42_usc_7171.html",
        "One of the members shall be designated by the President as Chairman.",
        "the same office: 42 U.S.C. 7171 has the President designate one member of the Commission as Chairman, and 5 U.S.C. 5314 places that Chairman at Level III; the graph spells the title without gender and names the Commission by its acronym",
        False,
    ),
    "exec-ind-opm-director-opm": (
        "Director, OPM",
        "Director of the Office of Personnel Management", "II", "5313",
        "5 U.S.C. 1102", "opm_5_usc_1102.html",
        "There is at the head of the Office of Personnel Management a Director of the Office of Personnel Management appointed by the President, by and with the advice and consent of the Senate.",
        "the same office: 5 U.S.C. 1102 puts a Director of the Office of Personnel Management at the head of the Office, and 5 U.S.C. 5313 places that Director at Level II; the graph names the Office by its acronym",
        False,
    ),
    "exec-ind-ssa-commissioner-ssa": (
        "Commissioner, SSA",
        "Commissioner of Social Security, Social Security Administration", "I", "5312",
        "42 U.S.C. 902", "ssa_42_usc_902.html",
        "There shall be in the Administration a Commissioner of Social Security",
        "the same office: 42 U.S.C. 902 creates in the Social Security Administration a Commissioner of Social Security, and 5 U.S.C. 5312 places that Commissioner at Level I; the graph names the Administration by its acronym",
        False,
    ),
    "exec-ind-ssa-deputy-commissioner-ssa": (
        "Deputy Commissioner, SSA",
        "Deputy Commissioner of Social Security, Social Security Administration", "II", "5313",
        "42 U.S.C. 902", "ssa_42_usc_902.html",
        "The Deputy Commissioner shall be compensated at the rate provided for level II of the Executive Schedule.",
        "the same office: 42 U.S.C. 902 creates in the Social Security Administration a Deputy Commissioner of Social Security and itself compensates that office at level II of the Executive Schedule, the level 5 U.S.C. 5313 prints for it; the graph names the Administration by its acronym",
        False,
    ),
    "exec-dept-dhs-fema-administrator-fema": (
        "Administrator, FEMA",
        "Administrator of the Federal Emergency Management Agency", "II", "5313",
        "6 U.S.C. 313", "fema_6_usc_313.html",
        "There is in the Department the Federal Emergency Management Agency, headed by an Administrator.",
        "the same office: 6 U.S.C. 313 places the Federal Emergency Management Agency in the Department of Homeland Security headed by an Administrator, and 5 U.S.C. 5313 places that Administrator at Level II; the graph names the Agency by its acronym",
        False,
    ),
    "exec-dept-doi-blm-director-blm": (
        "Director, BLM",
        "Director, Bureau of Land Management, Department of the Interior", "V", "5316",
        "43 U.S.C. 1731", "blm_43_usc_1731.html",
        "The Bureau of Land Management established by Reorganization Plan Numbered 3, of 1946 shall have as its head a Director.",
        "the same office: 43 U.S.C. 1731 gives the Bureau of Land Management a Director as its head, and 5 U.S.C. 5316 places that Director at Level V; the graph names the Bureau by its acronym",
        False,
    ),
    "exec-ind-cia-director-of-the-cia-dcia": (
        "Director of the CIA (DCIA)",
        "Director of the Central Intelligence Agency", "II", "5313",
        "50 U.S.C. 3036", "cia_50_usc_3036.html",
        "There is a Director of the Central Intelligence Agency who shall be appointed by the President, by and with the advice and consent of the Senate.",
        "the same office: 50 U.S.C. 3036 creates the Director of the Central Intelligence Agency as head of the Agency, and 5 U.S.C. 5313 places that Director at Level II; the graph names the Agency by its acronym",
        False,
    ),
    "exec-ind-cia-deputy-director-of-the-cia-ddcia": (
        "Deputy Director of the CIA (DDCIA)",
        "Deputy Director of the Central Intelligence Agency", "III", "5314",
        "50 U.S.C. 3037", "cia_50_usc_3037.html",
        "There is a Deputy Director of the Central Intelligence Agency who shall be appointed by the President",
        "the same office: 50 U.S.C. 3037 creates the Deputy Director of the Central Intelligence Agency, and 5 U.S.C. 5314 places that Deputy Director at Level III; the graph names the Agency by its acronym",
        False,
    ),
    "exec-dept-hhs-cms-administrator-cms": (
        "Administrator, CMS",
        "Administrator of the Centers for Medicare & Medicaid Services", "III", "5314",
        "42 U.S.C. 1317", "cms_42_usc_1317.html",
        "The Administrator of the Centers for Medicare & Medicaid Services shall be appointed by the President by and with the advice and consent of the Senate.",
        "the same office: 42 U.S.C. 1317 provides for the appointment of the Administrator of the Centers for Medicare & Medicaid Services, and 5 U.S.C. 5314 places that Administrator at Level III; the graph names the Centers by their acronym",
        False,
    ),
    "exec-dept-doc-nist-director-nist": (
        "Director, NIST",
        "Under Secretary of Commerce for Standards and Technology, who also serves as Director of the National Institute of Standards and Technology", "III", "5314",
        "15 U.S.C. 273a", "nist_15_usc_273a.html",
        "The Under Secretary shall serve as the Director of the Institute and shall perform such duties as required of the Director by the Secretary under this chapter or by law.",
        "the same office: 15 U.S.C. 273a creates in the Department of Commerce an Under Secretary of Commerce for Standards and Technology who shall serve as the Director of the Institute, and itself compensates that office at level III of the Executive Schedule, the level 5 U.S.C. 5314 prints for the joint title; the graph names the post by the Director half of that title and the Institute by its acronym",
        False,
    ),
    "exec-regulatory-nrc-chair-nrc": (
        "Chair, NRC",
        "Chairman, Nuclear Regulatory Commission", "II", "5313",
        "42 U.S.C. 5841", "nrc_42_usc_5841.html",
        "The President shall designate one member of the Commission as Chairman thereof to serve as such during the pleasure of the President.",
        "the same office: 42 U.S.C. 5841 establishes the Nuclear Regulatory Commission of five members and has the President designate one of them as Chairman, and 5 U.S.C. 5313 places that Chairman at Level II; the graph writes 'Chair' where the Code writes 'Chairman' and names the Commission by its acronym",
        False,
    ),
    "exec-regulatory-nrc-commissioner-4": (
        "Commissioner (×4)",
        "Members, Nuclear Regulatory Commission", "III", "5314",
        "42 U.S.C. 5841", "nrc_42_usc_5841.html",
        "There is established an independent regulatory commission to be known as the Nuclear Regulatory Commission which shall be composed of five members, each of whom shall be a citizen of the United States.",
        "a bench priced from its class title: 42 U.S.C. 5841 composes the Nuclear Regulatory Commission of five members, one of whom the President designates as Chairman, so each of the other four is a member of the Commission, and 5 U.S.C. 5314 places 'Members, Nuclear Regulatory Commission' at Level III; the level is the office's and holds for each of the four alike",
        True,
    ),
    "exec-ind-sba-administrator-sba": (
        "Administrator, SBA",
        "Administrator of the Small Business Administration", "III", "5314",
        "15 U.S.C. 633", "sba_15_usc_633.html",
        "The management of the Administration shall be vested in an Administrator who shall be appointed from civilian life by the President, by and with the advice and consent of the Senate,",
        "the same office: 15 U.S.C. 633 vests the management of the Small Business Administration in an Administrator appointed by the President with the Senate's consent, and 5 U.S.C. 5314 places that Administrator at Level III; the graph names the Administration by its acronym",
        False,
    ),
    "exec-ind-nsf-director-nsf": (
        "Director, NSF",
        "Director of the National Science Foundation", "II", "5313",
        "42 U.S.C. 1864", "nsf_42_usc_1864.html",
        "The Director shall receive basic pay at the rate provided for level II of the Executive Schedule under section 5313 of title 5",
        "the same office: 42 U.S.C. 1864 provides for the Director of the Foundation, appointed by the President with the Senate's consent, and itself sets that Director's basic pay at level II of the Executive Schedule, the level 5 U.S.C. 5313 prints for it; the graph names the Foundation by its acronym",
        False,
    ),
    "exec-ind-nsf-deputy-director-nsf": (
        "Deputy Director, NSF",
        "Deputy Director, National Science Foundation", "III", "5314",
        "42 U.S.C. 1864a", "nsf_42_usc_1864a.html",
        "The Deputy Director shall receive basic pay at the rate provided for level III of the Executive Schedule under section 5314 of title 5",
        "the same office: 42 U.S.C. 1864a provides for a Deputy Director of the Foundation, appointed by the President with the Senate's consent, and itself sets that Deputy Director's basic pay at level III of the Executive Schedule, the level 5 U.S.C. 5314 prints for it; the graph names the Foundation by its acronym",
        False,
    ),
    "exec-eop-ondcp-director-drug-czar": (
        "Director (Drug Czar)",
        "Director of National Drug Control Policy", "I", "5312",
        "21 U.S.C. 1703", "ondcp_21_usc_1703.html",
        "There shall be at the head of the Office a Director who shall hold the same rank and status as the head of an executive department listed in section 101 of title 5",
        "the same office: 21 U.S.C. 1703 puts a Director at the head of the Office of National Drug Control Policy, the Office 21 U.S.C. 1702 establishes in the Executive Office of the President and the node above this one, and 5 U.S.C. 5312 places the Director of National Drug Control Policy at Level I; the graph names the post by its informal label in brackets",
        False,
    ),
    "exec-dept-dol-bls-commissioner-bls": (
        "Commissioner, BLS",
        "The 2 Commissioner of Labor Statistics, Department of Labor", "IV", "5315",
        "29 U.S.C. 3", "bls_29_usc_3.html",
        "The Bureau of Labor Statistics shall be under the charge of a Commissioner of Labor Statistics, who shall be appointed by the President, by and with the advice and consent of the Senate;",
        "the same office: 29 U.S.C. 3 puts the Bureau of Labor Statistics under the charge of a Commissioner of Labor Statistics appointed by the President with the Senate's consent, and 5 U.S.C. 5315 places that Commissioner at Level IV, printing the title with a leading 'The' and the footnote mark '2' (the Code's own note: the word 'The' probably should not appear), which the index keeps as printed; the graph names the Bureau by its acronym",
        False,
    ),
    "exec-dept-doc-census-director-census-bureau": (
        "Director, Census Bureau",
        "Director, Bureau of the Census, Department of Commerce", "IV", "5315",
        "13 U.S.C. 21", "census_13_usc_21.html",
        "The Bureau shall be headed by a Director of the Census, appointed by the President, by and with the advice and consent of the Senate, without regard to political affiliation.",
        "the same office: 13 U.S.C. 21 puts a Director of the Census at the head of the Bureau, appointed by the President with the Senate's consent, and 5 U.S.C. 5315 places the Director of the Bureau of the Census at Level IV; the graph writes 'Census Bureau' where the Code writes 'Bureau of the Census'",
        False,
    ),
    "exec-eop-cea-chair-cea": (
        "Chair, CEA",
        "Chairman, Council of Economic Advisers", "II", "5313",
        "15 U.S.C. 1023", "cea_15_usc_1023.html",
        "The Council shall be composed of three members, of whom- (A) 1 shall be the chairman who shall be appointed by the President by and with the advice and consent of the Senate; and (B) 2 shall be appointed by the President.",
        "the same office: 15 U.S.C. 1023 composes the Council of Economic Advisers of three members, one of whom is the chairman appointed by the President with the Senate's consent, and 5 U.S.C. 5313 places that Chairman at Level II; the graph writes 'Chair' where the Code writes 'Chairman' and names the Council by its acronym",
        False,
    ),
    "exec-eop-cea-member-cea": (
        "Member, CEA",
        "Members, Council of Economic Advisers", "IV", "5315",
        "15 U.S.C. 1023", "cea_15_usc_1023.html",
        "The Council shall be composed of three members, of whom- (A) 1 shall be the chairman who shall be appointed by the President by and with the advice and consent of the Senate; and (B) 2 shall be appointed by the President.",
        "the same office: 15 U.S.C. 1023 composes the Council of Economic Advisers of three members, two of them appointed by the President beside the chairman, and 5 U.S.C. 5315 places 'Members, Council of Economic Advisers' at Level IV, the office each of the two holds; this graph draws the two as one node each, and the Code names the office once for both",
        False,
    ),
    "exec-eop-cea-member-cea-1": (
        "Member, CEA",
        "Members, Council of Economic Advisers", "IV", "5315",
        "15 U.S.C. 1023", "cea_15_usc_1023.html",
        "The Council shall be composed of three members, of whom- (A) 1 shall be the chairman who shall be appointed by the President by and with the advice and consent of the Senate; and (B) 2 shall be appointed by the President.",
        "the same office: 15 U.S.C. 1023 composes the Council of Economic Advisers of three members, two of them appointed by the President beside the chairman, and 5 U.S.C. 5315 places 'Members, Council of Economic Advisers' at Level IV, the office each of the two holds; this graph draws the two as one node each, and the Code names the office once for both",
        False,
    ),
    "exec-regulatory-cpsc-chair-cpsc": (
        "Chair, CPSC",
        "Chairman, Consumer Product Safety Commission", "III", "5314",
        "15 U.S.C. 2053", "cpsc_15_usc_2053.html",
        "The Chairman shall be appointed by the President, by and with the advice and consent of the Senate, from among the members of the Commission.",
        "the same office: 15 U.S.C. 2053 establishes the Consumer Product Safety Commission of five Commissioners and has the President appoint the Chairman from among them, and 5 U.S.C. 5314 places that Chairman at Level III; the graph writes 'Chair' where the Code writes 'Chairman' and names the Commission by its acronym",
        False,
    ),
    "exec-dept-dot-fhwa-administrator-fhwa": (
        "Administrator, FHWA",
        "Administrator, Federal Highway Administration", "II", "5313",
        "49 U.S.C. 104", "fhwa_49_usc_104.html",
        "The head of the Administration is the Administrator who is appointed by the President, by and with the advice and consent of the Senate.",
        "the same office: 49 U.S.C. 104 makes the Administrator the head of the Federal Highway Administration, appointed by the President with the Senate's consent, and 5 U.S.C. 5313 places that Administrator at Level II; the graph names the Administration by its acronym",
        False,
    ),
    "exec-dept-doc-uspto-director-under-secretary-for-ip": (
        "Director / Under Secretary for IP",
        "Under Secretary of Commerce for Intellectual Property and Director of the United States Patent and Trademark Office", "III", "5314",
        "35 U.S.C. 3", "uspto_35_usc_3.html",
        "The powers and duties of the United States Patent and Trademark Office shall be vested in an Under Secretary of Commerce for Intellectual Property and Director of the United States Patent and Trademark Office (in this title referred to as the \"Director\"), who shall be a citizen of the United States and who shall be appointed by the President, by and with the advice and consent of the Senate.",
        "the same office: 35 U.S.C. 3 vests the Office's powers and duties in one officer holding the joint title Under Secretary of Commerce for Intellectual Property and Director of the United States Patent and Trademark Office, and 5 U.S.C. 5314 places that joint title at Level III; the graph writes the two halves as 'Director / Under Secretary for IP'",
        False,
    ),
    "exec-dept-doi-bor-commissioner-bor": (
        "Commissioner, BOR",
        "Commissioner of Reclamation, Department of the Interior", "V", "5316",
        "43 U.S.C. 373a", "bor_43_usc_373a.html",
        "shall be administered by a Commissioner of Reclamation who shall be appointed by the President by and with the advice and consent of the Senate.",
        "the same office: 43 U.S.C. 373a puts the reclamation of arid lands under a Commissioner of Reclamation in the Department of the Interior, appointed by the President with the Senate's consent, and 5 U.S.C. 5316 places that Commissioner at Level V; the graph names the Bureau of Reclamation by its acronym",
        False,
    ),
    "leg-support-loc-copyright-register-of-copyrights-director": (
        "Register of Copyrights & Director",
        "Register of Copyrights", "III", "5314",
        "17 U.S.C. 701", "copyright_17_usc_701.html",
        "All administrative functions and duties under this title, except as otherwise specified, are the responsibility of the Register of Copyrights as director of the Copyright Office of the Library of Congress.",
        "the same office: 17 U.S.C. 701 makes the Register of Copyrights the director of the Copyright Office of the Library of Congress, and 5 U.S.C. 5314 places the Register of Copyrights at Level III; the graph's '& Director' is the Office's own styling of that one post",
        False,
    ),
    "exec-ind-nasa-administrator-nasa": (
        "Administrator, NASA",
        "Administrator of the National Aeronautics and Space Administration", "II", "5313",
        "51 U.S.C. 20111", "nasa_51_usc_20111.html",
        "The Administration shall be headed by an Administrator, who shall be appointed from civilian life by the President by and with the advice and consent of the Senate.",
        "the same office: 51 U.S.C. 20111 puts an Administrator at the head of the National Aeronautics and Space Administration, appointed by the President with the Senate's consent, and 5 U.S.C. 5313 places that Administrator at Level II; the graph names the Administration by its acronym",
        False,
    ),
    "exec-dept-dot-fta-administrator-fta": (
        "Administrator, FTA",
        "Federal Transit Administrator", "II", "5313",
        "49 U.S.C. 107", "fta_49_usc_107.html",
        "The head of the Administration is the Administrator who is appointed by the President, by and with the advice and consent of the Senate.",
        "the same office: 49 U.S.C. 107 makes the Administrator the head of the Federal Transit Administration, appointed by the President with the Senate's consent, and 5 U.S.C. 5313 places the Federal Transit Administrator at Level II; the graph names the Administration by its acronym",
        False,
    ),
    "exec-dept-dot-fra-administrator-fra": (
        "Administrator, FRA",
        "Administrator, Federal Railroad Administration", "III", "5314",
        "49 U.S.C. 103", "fra_49_usc_103.html",
        "The head of the Administration shall be the Administrator who shall be appointed by the President, by and with the advice and consent of the Senate,",
        "the same office: 49 U.S.C. 103 makes the Administrator the head of the Federal Railroad Administration, appointed by the President with the Senate's consent, and 5 U.S.C. 5314 places that Administrator at Level III; the graph names the Administration by its acronym",
        False,
    ),
    "exec-dept-dot-marad-administrator-marad": (
        "Administrator, MARAD",
        "Administrator, Maritime Administration", "III", "5314",
        "49 U.S.C. 109", "marad_49_usc_109.html",
        "The head of the Maritime Administration is the Maritime Administrator, who is appointed by the President by and with the advice and consent of the Senate.",
        "the same office: 49 U.S.C. 109 makes the Maritime Administrator the head of the Maritime Administration, appointed by the President with the Senate's consent, and 5 U.S.C. 5314 places that Administrator at Level III; the graph names the Administration by its acronym",
        False,
    ),
    "exec-dept-dol-msha-assistant-secretary-of-labor-for-mine-safety": (
        "Assistant Secretary of Labor for Mine Safety",
        "Assistant Secretary of Labor for Mine Safety and Health", "IV", "5315",
        "29 U.S.C. 557a", "msha_29_usc_557a.html",
        "There is established in the Department of Labor a Mine Safety and Health Administration to be headed by an Assistant Secretary of Labor for Mine Safety and Health appointed by the President, by and with the advice and consent of the Senate.",
        "the same office: 29 U.S.C. 557a puts the Mine Safety and Health Administration under an Assistant Secretary of Labor for Mine Safety and Health, and 5 U.S.C. 5315 places that Assistant Secretary at Level IV; the graph's name drops the words 'and Health'",
        False,
    ),
    "exec-dept-treasury-ofr-director-ofr": (
        "Director, OFR",
        "Director of the Office of Financial Research", "III", "5314",
        "12 U.S.C. 5342", "ofr_12_usc_5342.html",
        "The Office shall be headed by a Director, who shall be appointed by the President, by and with the advice and consent of the Senate.",
        "the same office: 12 U.S.C. 5342 puts a Director at the head of the Office of Financial Research in the Department of the Treasury and itself compensates that Director at Level III of the Executive Schedule, the level 5 U.S.C. 5314 prints for it; the graph names the Office by its acronym",
        False,
    ),
    "exec-regulatory-fmc-chair-fmc": (
        "Chair, FMC",
        "Chairman, Federal Maritime Commission", "III", "5314",
        "46 U.S.C. 46101", "fmc_46_usc_46101.html",
        "The President shall designate one of the Commissioners as Chairman.",
        "the same office: 46 U.S.C. 46101 composes the Federal Maritime Commission of five Commissioners and has the President designate one of them as Chairman, and 5 U.S.C. 5314 places that Chairman at Level III; the graph writes 'Chair' where the Code writes 'Chairman' and names the Commission by its acronym",
        False,
    ),
    "exec-regulatory-fmc-commissioner-4": (
        "Commissioner (×4)",
        "Members, Federal Maritime Commission", "IV", "5315",
        "46 U.S.C. 46101", "fmc_46_usc_46101.html",
        "The Commission is composed of 5 Commissioners, appointed by the President by and with the advice and consent of the Senate.",
        "a bench priced from its class title: 46 U.S.C. 46101 composes the Federal Maritime Commission of five Commissioners, one of whom the President designates as Chairman, so each of the other four is a member of the Commission, and 5 U.S.C. 5315 places 'Members, Federal Maritime Commission' at Level IV; the level is the office's and holds for each of the four alike",
        True,
    ),
    "exec-ind-misc-merit-systems-protection-board-mspb-director-administrator-chair-merit-systems-protection-board": (
        "Director / Administrator / Chair, Merit Systems Protection Board",
        "Chairman of the Merit Systems Protection Board", "III", "5314",
        "5 U.S.C. 1203", "mspb_5_usc_1203.html",
        "The President shall from time to time appoint, by and with the advice and consent of the Senate, one of the members of the Merit Systems Protection Board as the Chairman of the Board.",
        "the same office: 5 U.S.C. 1203 has the President appoint one member of the Merit Systems Protection Board as its Chairman, the Board's chief executive and administrative officer, and 5 U.S.C. 5314 places that Chairman at Level III; the graph names the post with its stamped 'Director / Administrator / Chair' template and the agency by name, and the Chairman is the head the template stands for",
        False,
    ),
    "exec-ind-misc-national-credit-union-administration-ncua-director-administrator-chair-national-credit-union-administration": (
        "Director / Administrator / Chair, National Credit Union Administration",
        "Chairman, National Credit Union Administration Board", "III", "5314",
        "12 U.S.C. 1752a", "ncua_12_usc_1752a.html",
        "In appointing the members of the Board, the President shall designate the Chairman.",
        "the same office: 12 U.S.C. 1752a puts the National Credit Union Administration under the management of a three-member Board whose Chairman the President designates, and 5 U.S.C. 5314 places that Chairman at Level III; the graph names the post with its stamped 'Director / Administrator / Chair' template and the agency by name, and the Board's Chairman is the head the template stands for",
        False,
    ),
    "exec-ind-misc-peace-corps-director-administrator-chair-peace-corps": (
        "Director / Administrator / Chair, Peace Corps",
        "Director of the Peace Corps", "III", "5314",
        "22 U.S.C. 2503", "peacecorps_22_usc_2503.html",
        "The President may appoint, by and with the advice and consent of the Senate, a Director of the Peace Corps and a Deputy Director of the Peace Corps.",
        "the same office: 22 U.S.C. 2503 provides for a Director of the Peace Corps appointed by the President with the Senate's consent, through whom the President exercises the chapter's functions, and 5 U.S.C. 5314 places that Director at Level III; the graph names the post with its stamped 'Director / Administrator / Chair' template and the agency by name, and the Director is the head the template stands for",
        False,
    ),
    "exec-ind-misc-selective-service-system-director-administrator-chair-selective-service-system": (
        "Director / Administrator / Chair, Selective Service System",
        "Director of Selective Service", "IV", "5315",
        "50 U.S.C. 3809", "sss_50_usc_3809.html",
        "There is established in the executive branch of the Government an agency to be known as the Selective Service System, and a Director of Selective Service who shall be the head thereof.",
        "the same office: 50 U.S.C. 3809 establishes the Selective Service System with a Director of Selective Service as its head, and 5 U.S.C. 5315 places that Director at Level IV; the graph names the post with its stamped 'Director / Administrator / Chair' template and the agency by name, and the Director is the head the template stands for",
        False,
    ),
    "exec-ind-misc-federal-labor-relations-authority-flra-director-administrator-chair-federal-labor-relations-authority": (
        "Director / Administrator / Chair, Federal Labor Relations Authority",
        "Chairman, Federal Labor Relations Authority", "IV", "5315",
        "5 U.S.C. 7104", "flra_5_usc_7104.html",
        "The President shall designate one member to serve as Chairman of the Authority.",
        "the same office: 5 U.S.C. 7104 composes the Federal Labor Relations Authority of three members and has the President designate one as Chairman, the Authority's chief executive and administrative officer, and 5 U.S.C. 5315 places that Chairman at Level IV; the graph names the post with its stamped 'Director / Administrator / Chair' template and the agency by name, and the Chairman is the head the template stands for",
        False,
    ),
    "exec-ind-misc-national-endowment-for-the-humanities-neh-director-administrator-chair-national-endowment-for-the-humanities": (
        "Director / Administrator / Chair, National Endowment for the Humanities",
        "Chairman of the National Endowment for the Humanities", "III", "5314",
        "20 U.S.C. 956", "neh_20_usc_956.html",
        "The Endowment shall be headed by a chairperson, who shall be appointed by the President, by and with the advice and consent of the Senate.",
        "the same office: 20 U.S.C. 956 puts a chairperson at the head of the National Endowment for the Humanities, appointed by the President with the Senate's consent, and 5 U.S.C. 5314 places the Chairman of the Endowment at Level III; the graph names the post with its stamped 'Director / Administrator / Chair' template and the agency by name, and the chairperson is the head the template stands for",
        False,
    ),
    "exec-ind-misc-national-transportation-safety-board-ntsb-director-administrator-chair-national-transportation-safety-board": (
        "Director / Administrator / Chair, National Transportation Safety Board",
        "Chairman, National Transportation Safety Board", "III", "5314",
        "49 U.S.C. 1111", "ntsb_49_usc_1111.html",
        "The President shall designate, by and with the advice and consent of the Senate, a Chairman of the Board.",
        "the same office: 49 U.S.C. 1111 composes the National Transportation Safety Board of five members and has the President designate a Chairman with the Senate's consent, and 5 U.S.C. 5314 places that Chairman at Level III; the graph names the post with its stamped 'Director / Administrator / Chair' template and the agency by name, and the Chairman is the head the template stands for",
        False,
    ),
    "exec-ind-misc-office-of-special-counsel-osc-director-administrator-chair-office-of-special-counsel": (
        "Director / Administrator / Chair, Office of Special Counsel",
        "Special Counsel of the Office of Special Counsel", "III", "5314",
        "5 U.S.C. 1211", "osc_5_usc_1211.html",
        "There is established the Office of Special Counsel, which shall be headed by the Special Counsel.",
        "the same office: 5 U.S.C. 1211 establishes the Office of Special Counsel headed by the Special Counsel, appointed by the President with the Senate's consent, and 5 U.S.C. 5314 places the Special Counsel at Level III; the graph names the post with its stamped 'Director / Administrator / Chair' template and the agency by name, and the Special Counsel is the head the template stands for",
        False,
    ),
    "exec-ind-misc-pension-benefit-guaranty-corporation-pbgc-director-administrator-chair-pension-benefit-guaranty-corporation": (
        "Director / Administrator / Chair, Pension Benefit Guaranty Corporation",
        "Director, Pension Benefit Guaranty Corporation", "III", "5314",
        "29 U.S.C. 1302", "pbgc_29_usc_1302.html",
        "the corporation shall be administered by a Director, who shall be appointed by the President, by and with the advice and consent of the Senate,",
        "the same office: 29 U.S.C. 1302 has the Pension Benefit Guaranty Corporation administered by a Director appointed by the President with the Senate's consent, and 5 U.S.C. 5314 places that Director at Level III; the graph names the post with its stamped 'Director / Administrator / Chair' template and the agency by name, and the Director is the head the template stands for",
        False,
    ),
    "exec-ind-misc-u-s-postal-rate-commission-postal-regulatory-commission-director-administrator-chair-u-s-postal-rate-commission-postal-regulatory-commission": (
        "Director / Administrator / Chair, U.S. Postal Rate Commission / Postal Regulatory Commission",
        "Chairman, Postal Regulatory Commission", "III", "5314",
        "39 U.S.C. 502", "prc_39_usc_502.html",
        "One of the Commissioners shall be designated as Chairman by, and shall serve in the position of Chairman at the pleasure of, the President.",
        "the same office: 39 U.S.C. 502 composes the Postal Regulatory Commission of five Commissioners, one of whom the President designates as Chairman, and 5 U.S.C. 5314 places that Chairman at Level III; the graph names the post with its stamped 'Director / Administrator / Chair' template and the agency by name with the Commission's former name beside its current one, and the Chairman is the head the template stands for",
        False,
    ),
    "exec-ind-misc-export-import-bank-of-the-u-s-director-administrator-chair-export-import-bank-of-the-u-s": (
        "Director / Administrator / Chair, Export-Import Bank of the U.S.",
        "President of the Export-Import Bank of Washington", "III", "5314",
        "12 U.S.C. 635a", "exim_12_usc_635a.html",
        "There shall be a President of the Export-Import Bank of the United States, who shall be appointed by the President of the United States by and with the advice and consent of the Senate, and who shall serve as chief executive officer",
        "the same office: 12 U.S.C. 635a creates a President of the Export-Import Bank of the United States as the Bank's chief executive officer, and 5 U.S.C. 5314 places the 'President of the Export-Import Bank of Washington' at Level III — the Schedule keeps the Bank's name before Pub. L. 90-267 renamed it in 1968, a rename the Code records in the notes to 12 U.S.C. 635 and this row relies on; the graph names the post with its stamped 'Director / Administrator / Chair' template and the agency by name, and the Bank's President is the head the template stands for",
        False,
    ),
    "exec-ind-misc-export-import-bank-of-the-u-s-deputy-director-vice-chair": (
        "Deputy Director / Vice Chair",
        "First Vice President of the Export-Import Bank of Washington", "IV", "5315",
        "12 U.S.C. 635a", "exim_12_usc_635a.html",
        "There shall be a Board of Directors of the Bank consisting of the President of the Export-Import Bank of the United States, who shall serve as Chairman, the First Vice President who shall serve as Vice Chairman, and three additional persons appointed by the President of the United States by and with the advice and consent of the Senate.",
        "the same office: 12 U.S.C. 635a(b) creates a First Vice President of the Export-Import Bank of the United States and 635a(c)(1) seats that officer on the Board as its Vice Chairman, and 5 U.S.C. 5315 places the 'First Vice President of the Export-Import Bank of Washington' at Level IV — the Schedule keeps the Bank's pre-1968 name, the rename the President's row already relies on; the graph names the post with its stamped 'Deputy Director / Vice Chair' template under the Bank, and the First Vice President is the Vice Chairman the template stands for",
        False,
    ),
    "exec-dept-doc-uspto-deputy-director": (
        "Deputy Director",
        "Deputy Under Secretary of Commerce for Intellectual Property and Deputy Director of the United States Patent and Trademark Office", "IV", "5315",
        "35 U.S.C. 3", "uspto_35_usc_3.html",
        "The Secretary of Commerce, upon nomination by the Director, shall appoint a Deputy Under Secretary of Commerce for Intellectual Property and Deputy Director of the United States Patent and Trademark Office",
        "the same office: 35 U.S.C. 3(b)(1) creates one officer holding the joint title Deputy Under Secretary of Commerce for Intellectual Property and Deputy Director of the United States Patent and Trademark Office, and 5 U.S.C. 5315 places that joint title at Level IV; the graph writes the bare 'Deputy Director' under the Office, and the row is keyed to that node by id",
        False,
    ),
    'exec-ind-misc-equal-employment-opportunity-commission-eeoc-director-administrator-chair-equal-employment-opportunity-commission': (
        'Director / Administrator / Chair, Equal Employment Opportunity Commission',
        'Chairman, Equal Employment Opportunity Commission', 'III', '5314',
        '42 U.S.C. 2000e-4', 'eeoc_42_usc_2000e-4.html',
        'The President shall designate one member to serve as Chairman of the Commission, and one member to serve as Vice Chairman.',
        "the same office: 42 U.S.C. 2000e-4(a) has the President designate one member of the Commission as its Chairman, and 5 U.S.C. 5314 places 'Chairman, Equal Employment Opportunity Commission' at Level III; the graph's stamped 'Director / Administrator / Chair' template stands for that Chairman, the only one of the three offices the Act creates",
        False,
    ),
    'exec-ind-misc-equal-employment-opportunity-commission-eeoc-deputy-director-vice-chair': (
        'Deputy Director / Vice Chair',
        'Members, Equal Employment Opportunity Commission (4)', 'IV', '5315',
        '42 U.S.C. 2000e-4', 'eeoc_42_usc_2000e-4.html',
        'The President shall designate one member to serve as Chairman of the Commission, and one member to serve as Vice Chairman.',
        "a Vice Chairman is a member of the Commission: 42 U.S.C. 2000e-4(a) has the President designate one member as Vice Chairman, 5 U.S.C. 5315 places the four members other than the Chairman at Level IV as 'Members, Equal Employment Opportunity Commission (4)', and only the Chairman is placed separately (5314); the graph's stamped 'Deputy Director / Vice Chair' template stands for that Vice Chairman, the one such office the Act creates",
        False,
    ),
    'exec-ind-misc-national-mediation-board-nmb-director-administrator-chair-national-mediation-board': (
        'Director / Administrator / Chair, National Mediation Board',
        'Chairman, National Mediation Board', 'III', '5314',
        '45 U.S.C. 154', 'nmb_45_usc_154.html',
        'The Mediation Board shall annually designate a member to act as chairman.',
        "the same office: 45 U.S.C. 154 Second has the Board annually designate a member to act as chairman, and 5 U.S.C. 5314 places 'Chairman, National Mediation Board' at Level III; the graph's stamped 'Director / Administrator / Chair' template stands for that chairman, the only one of the three offices the Act creates",
        False,
    ),
    'exec-ind-misc-national-endowment-for-the-arts-nea-director-administrator-chair-national-endowment-for-the-arts': (
        'Director / Administrator / Chair, National Endowment for the Arts',
        'Chairman of the National Endowment for the Arts the incumbent of which also serves as Chairman of the National Council on the Arts', 'III', '5314',
        '20 U.S.C. 954', 'nea_20_usc_954.html',
        'The Endowment shall be headed by a chairperson, to be known as the Chairperson of the National Endowment for the Arts, who shall be appointed by the President, by and with the advice and consent of the Senate.',
        "the same office: 20 U.S.C. 954(b)(1) has the Endowment headed by the Chairperson of the National Endowment for the Arts, and 5 U.S.C. 5314 places that Chairman at Level III; the graph's stamped 'Director / Administrator / Chair' template stands for that Chairperson, the only one of the three offices the Act creates, spelt with gender by the Schedule and without by the Act",
        False,
    ),
    'exec-dept-hud-ginnie-president-ginnie-mae': (
        'President, Ginnie Mae',
        'President, Government National Mortgage Association, Department of Housing and Urban Development', 'IV', '5315',
        '12 U.S.C. 1723', 'ginnie_12_usc_1723.html',
        'There is hereby established in the Department of Housing and Urban Development the position of President, Government National Mortgage Association, who shall be appointed by the President, by and with the advice and consent of the Senate.',
        'the same office: 12 U.S.C. 1723(a) establishes in the Department the position of President, Government National Mortgage Association, and 5 U.S.C. 5315 places it at Level IV; the graph names the Association by the name it trades under',
        False,
    ),
    'exec-dept-dol-whd-administrator-whd': (
        'Administrator, WHD',
        'Administrator, Wage and Hour Division, Department of Labor', 'IV', '5315',
        '29 U.S.C. 204', 'whd_29_usc_204.html',
        'There is created in the Department of Labor a Wage and Hour Division which shall be under the direction of an Administrator, to be known as the Administrator of the Wage and Hour Division',
        'the same office: 29 U.S.C. 204(a) creates the Wage and Hour Division under the direction of the Administrator of the Wage and Hour Division, and 5 U.S.C. 5315 places that Administrator at Level IV; the graph names the Division by its acronym',
        False,
    ),
    'exec-eop-omb-office-of-federal-procurement-policy-administrator-chief-office-of-federal-procurement-policy': (
        'Administrator / Chief, Office of Federal Procurement Policy',
        'Administrator for Federal Procurement Policy', 'III', '5314',
        '41 U.S.C. 1102', 'ofpp_41_usc_1102.html',
        'The head of the Office of Federal Procurement Policy is the Administrator for Federal Procurement Policy.',
        "the same office: 41 U.S.C. 1102(a) makes the Administrator for Federal Procurement Policy the head of the Office, and 5 U.S.C. 5314 places that Administrator at Level III; the graph's templated 'Administrator / Chief' stands for the head of the Office, which is that Administrator",
        False,
    ),
    'exec-eop-omb-office-of-federal-financial-management-administrator-chief-office-of-federal-financial-management': (
        'Administrator / Chief, Office of Federal Financial Management',
        'Controller, Office of Federal Financial Management, Office of Management and Budget', 'III', '5314',
        '31 U.S.C. 504', 'offm_31_usc_504.html',
        'There shall be at the head of the Office of Federal Financial Management a Controller, who shall be appointed by the President, by and with the advice and consent of the Senate.',
        "the same office: 31 U.S.C. 504(b) puts a Controller at the head of the Office of Federal Financial Management, and 5 U.S.C. 5314 places that Controller at Level III; the graph's templated 'Administrator / Chief' stands for the head of the Office, which the statute styles Controller",
        False,
    ),
    'exec-eop-omb-office-of-e-government-it-federal-cio-administrator-chief-office-of-e-government-it-federal-cio': (
        'Administrator / Chief, Office of E-Government & IT (Federal CIO)',
        'Administrator of the Office of Electronic Government', 'III', '5314',
        '44 U.S.C. 3602', 'egov_44_usc_3602.html',
        'There shall be at the head of the Office an Administrator who shall be appointed by the President.',
        "the same office: 44 U.S.C. 3602(a)-(b) establishes the Office of Electronic Government in the Office of Management and Budget with an Administrator at its head, and 5 U.S.C. 5314 places that Administrator at Level III; the graph's templated 'Administrator / Chief' stands for the head of the Office, which it names as the Office of E-Government & IT",
        False,
    ),
    'exec-eop-omb-director-omb': (
        'Director, OMB',
        'Director of the Office of Management and Budget', 'I', '5312',
        '31 U.S.C. 502', 'omb_31_usc_502.html',
        'The head of the Office of Management and Budget is the Director of the Office of Management and Budget.',
        'the same office: 31 U.S.C. 502(a) makes the Director the head of the Office, and 5 U.S.C. 5312 places the Director of the Office of Management and Budget at Level I; the graph names the Office by its acronym',
        False,
    ),
    'exec-eop-omb-deputy-director-omb': (
        'Deputy Director, OMB',
        'Deputy Director of the Office of Management and Budget', 'II', '5313',
        '31 U.S.C. 502', 'omb_31_usc_502.html',
        'The Office has a Deputy Director of the Office of Management and Budget, appointed by the President, by and with the advice and consent of the Senate.',
        'the same office: 31 U.S.C. 502(b) gives the Office a Deputy Director, and 5 U.S.C. 5313 places the Deputy Director of the Office of Management and Budget at Level II (the Deputy Director for Management is placed separately and is a separate node here); the graph names the Office by its acronym',
        False,
    ),
    'exec-dept-dot-phmsa-administrator-phmsa': (
        'Administrator, PHMSA',
        'Administrator, Pipeline and Hazardous Materials Safety Administration', 'III', '5314',
        '49 U.S.C. 108', 'phmsa_49_usc_108.html',
        'The head of the Administration shall be the Administrator who shall be appointed by the President, by and with the advice and consent of the Senate',
        "the same office: 49 U.S.C. 108(c) makes the Administrator the head of the Pipeline and Hazardous Materials Safety Administration, and 5 U.S.C. 5314 places that Administrator at Level III; the graph names the Administration by its acronym, and OPM's current export lists the post at EX-III under it",
        False,
    ),
    'exec-regulatory-cpsc-commissioner-4': (
        'Commissioner (×4)',
        'Members, Consumer Product Safety Commission (4)', 'IV', '5315',
        '15 U.S.C. 2053', 'cpsc_15_usc_2053.html',
        'An independent regulatory commission is hereby established, to be known as the Consumer Product Safety Commission, consisting of five Commissioners who shall be appointed by the President, by and with the advice and consent of the Senate.',
        "a class title: 5 U.S.C. 5315 places 'Members, Consumer Product Safety Commission (4)' at Level IV, the four Commissioners other than the Chairman (placed separately at 5314), and 15 U.S.C. 2053(a) composes the Commission of five Commissioners; the graph's bench of four is exactly the four the Code counts, and the count is checked on every run",
        True,
    ),
    'exec-regulatory-sec-commissioner-4': (
        'Commissioner (×4)',
        'Members, Securities and Exchange Commission', 'IV', '5315',
        '15 U.S.C. 78d', 'sec_15_usc_78d.html',
        'to be composed of five commissioners to be appointed by the President by and with the advice and consent of the Senate',
        "a class title: 5 U.S.C. 5315 places 'Members, Securities and Exchange Commission' at Level IV, and the Chairman separately at 5314; 15 U.S.C. 78d(a) composes the Commission of five commissioners, so the bench of four is the members other than the Chairman",
        True,
    ),
}
_US_CODE_OPERATIVE_CACHE = {}


def uscode_operative_text(path):
    """A committed uscode.house.gov page's OPERATIVE text, stdlib-only.

    Tags stripped, entities unescaped, whitespace folded, and cut at the first
    of the publisher's note headings -- "Historical and Revision Notes",
    "Editorial Notes", "Statutory Notes" -- so a sentence the page prints only
    as prior or repealed text is not on the law's side of the line. Written
    against the bytes rather than imported from the module it checks.
    """
    import html as _html

    key = str(path)
    if key not in _US_CODE_OPERATIVE_CACHE:
        try:
            raw = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            _US_CODE_OPERATIVE_CACHE[key] = ""
            return ""
        text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", raw)
        text = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", text))).strip()
        start = re.search(r"\u00a7\s?\d+[A-Za-z]?(?:[-\u2013]\d+)?\.", text)
        body = text[start.start():] if start else text
        cuts = [body.find(h) for h in ("Historical and Revision Notes", "Editorial Notes", "Statutory Notes")]
        cuts = [c for c in cuts if c > 0]
        _US_CODE_OPERATIVE_CACHE[key] = body[: min(cuts)].strip() if cuts else ""
    return _US_CODE_OPERATIVE_CACHE[key]

EXECUTIVE_SCHEDULE_PAY_PLAN = "EX"
EXECUTIVE_SCHEDULE_EFFECTIVE = "2026-01-01"
EXECUTIVE_SCHEDULE_EFFECTIVE_TEXT = "Effective January 2026"
# The page's own notes, mirrored for the same reason the rates are. The panel
# prints these inside quotation marks as "the table's own note", so an
# unchecked footnote list is a channel for a fabricated quotation attributed
# to OPM — a red team published "no pay freeze applies", the reverse of what
# the page says, and every other check passed.
EXECUTIVE_SCHEDULE_FOOTNOTES = (
    "Under a provision in the Continuing Appropriations Act, 2026 (November 12, 2025), the freeze "
    "on the payable pay rates for the Vice President and certain senior political appointees "
    "continues through January 30, 2026. Future Congressional action will determine whether these "
    "frozen rates continue beyond that date.",
)
# OPM's Salary Table 2026-GS, mirrored as the fifteen (step 1, step 10) pairs a
# published range can be checked against, and pinned to BOTH committed
# renderings of the table by tests/test_gs_pay.py -- the PDF the records cite
# and the HTML page beside it. A range published from a grade the mirror does
# not have, or with bounds the table does not print, is refused here. Base pay
# before locality: the table states no locality adjustment, and the block must
# say so in the words gs_pay.GS_BASE_BEFORE_LOCALITY carries.
GENERAL_SCHEDULE_TABLE = "Salary Table 2026-GS"
GENERAL_SCHEDULE_EFFECTIVE = "2026-01-01"
GENERAL_SCHEDULE_EFFECTIVE_TEXT = "Effective January 2026"
GENERAL_SCHEDULE_RANGES = {
    "1": (22_584.0, 28_248.0),
    "2": (25_393.0, 31_953.0),
    "3": (27_708.0, 36_024.0),
    "4": (31_103.0, 40_436.0),
    "5": (34_799.0, 45_239.0),
    "6": (38_791.0, 50_428.0),
    "7": (43_106.0, 56_039.0),
    "8": (47_738.0, 62_057.0),
    "9": (52_727.0, 68_549.0),
    "10": (58_064.0, 75_479.0),
    "11": (63_795.0, 82_938.0),
    "12": (76_463.0, 99_404.0),
    "13": (90_925.0, 118_204.0),
    "14": (107_446.0, 139_684.0),
    "15": (126_384.0, 164_301.0),
}
GENERAL_SCHEDULE_BASE_BEFORE_LOCALITY = (
    "base General Schedule rates before locality pay; the table states no locality adjustment"
)
# The SES and SL/ST structure tables: two rows each, a minimum and a maximum,
# for agencies with and without a certified performance appraisal system.
# Mirrored as the page prints them and pinned by tests/test_gs_pay.py. The two
# tables print identical figures, which is exactly why a block must name the
# table for its own pay plan: a SL/ST range citing the SES table would carry
# every right number and the wrong document.
PAY_STRUCTURE_TABLES = {
    "senior_executive_service": {
        "table": "Salary Table No. 2026-ES",
        "payPlans": ("ES",),
        "rows": (
            ("Agencies with a Certified SES Performance Appraisal System", 151_661.0, 228_000.0),
            ("Agencies without a Certified SES Performance Appraisal System", 151_661.0, 209_600.0),
        ),
    },
    "senior_level": {
        "table": "Salary Table No. 2026-SL/ST",
        "payPlans": ("SL", "ST"),
        "rows": (
            ("Agencies with a Certified SL/ST Performance Appraisal System", 151_661.0, 228_000.0),
            ("Agencies without a Certified SL/ST Performance Appraisal System", 151_661.0, 209_600.0),
        ),
    },
}
# The committed documents each kind of range cites, so the gate can recompute
# the digest a block names from the bytes on disk. The GS block cites the PDF
# and carries the HTML's digest as corroboration; both are checked.
GRADE_PAY_FIXTURES = {
    "general_schedule_grade": (
        Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "opm" / "pay" / "general_schedule_2026.pdf",
        Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "opm" / "pay" / "general_schedule_2026.html",
    ),
    "senior_executive_service": (
        Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "opm" / "pay" / "senior_executive_service_2026.html",
    ),
    "senior_level": (
        Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "opm" / "pay" / "senior_level_2026.html",
    ),
}
GRADE_PAY_UNITS_KIND = {
    "general_schedule_grade": "currency_mark_on_the_columns_first_figure",
    "senior_executive_service": "currency_mark_on_the_printed_figure",
    "senior_level": "currency_mark_on_the_printed_figure",
}
# OPM's CURRENT PLUM export (data_pipeline/verification/plum_current.py). The
# gate re-reads the committed file by each block's own keys, projecting ONLY
# these columns by header index: the two name columns and the unique-ID column
# are never materialised here any more than in the module, and
# tests/test_plum_current.py plants a sentinel in them to prove it.
PLUM_CURRENT_FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "opm" / "plum" / "escs_pbpub_download-data.csv"
PLUM_CURRENT_COLUMNS = (
    "Agency", "Organization", "Position Title", "Position Status", "Appointment Type", "Level, Grade, or Pay", "Pay Plan",
)
PLUM_CURRENT_LIVE_STATUSES = ("Filled", "Vacant")
PLUM_CURRENT_SOURCE = "opm_plum_current_export"
PLUM_CURRENT_METHOD = "listed_in_opm_current_plum_export"
PLUM_CURRENT_PLACEMENT_METHOD = "listed_under_organization_in_opm_current_plum_export"
PLUM_CURRENT_PAY_UNITS_KIND = "currency_mark_on_the_printed_figure"
_PLUM_CURRENT_CACHE = {}
_FIXTURE_DIGESTS = {}


def fixture_digest(path):
    """sha256 of a committed fixture, computed once per run."""
    import hashlib as _hashlib

    key = str(path)
    if key not in _FIXTURE_DIGESTS:
        try:
            _FIXTURE_DIGESTS[key] = _hashlib.sha256(Path(path).read_bytes()).hexdigest()
        except OSError:
            _FIXTURE_DIGESTS[key] = None
    return _FIXTURE_DIGESTS[key]


# The U.S. Courts' own Judicial Compensation table, mirrored for the same
# reason and pinned the same way: tests/test_judicial_pay.py parses
# tests/fixtures/uscourts/judicial_compensation.html and asserts equality.
JUDICIAL_COMPENSATION_YEAR = "2026"
JUDICIAL_COMPENSATION_TIERS = {
    "district judges": 249_900.0,
    "circuit judges": 264_900.0,
    "associate justices": 306_600.0,
    "chief justice": 320_700.0,
}
# The page carries a footnote (fn1) about two historical adjustments that
# does not apply to the current row; this module's records never carry it
# because it is about years this module does not price, but the field
# exists on every record and the gate checks whatever list is actually there
# against this mirror, empty or not.
JUDICIAL_COMPENSATION_FOOTNOTES: tuple[str, ...] = ()

# ---------------------------------------------------------------------------
# A figure NO document states: the four statutory parity provisions, mirrored
# by node id with the sentence each one prints and the tier it names. Keyed by
# id for a reason sharper than the Senate case: three of the four price the
# identical $249,900 from three different statutes, so a record moved between
# them keeps a correct figure, a correct tier and a real citation, and only
# the node's own identity tells them apart. Pinned against
# `derived_pay.PARITY_PROVISIONS` — and against the committed sections' own
# OPERATIVE text — by tests/test_derived_pay.py.
DERIVED_PAY_SOURCE = "statutory_parity_derived_pay"
DERIVED_PAY_METHOD = "parity_provision_joined_to_the_judicial_compensation_table"
DERIVED_PAY_TABLE_URL = (
    "https://www.uscourts.gov/about-federal-courts/about-federal-judges/judicial-compensation"
)
DERIVED_PAY_STATUTE_HOST = "uscode.house.gov"
#: The hosts a derived row's statute may be read from (mirrors
#: derived_pay.STATUTE_HOSTS): the OLRC's prelim edition, and since 2026-10-05
#: the Government Publishing Office's annual edition, read when the first host
#: served nothing but a maintenance page.
DERIVED_PAY_STATUTE_HOSTS = ("uscode.house.gov", "www.govinfo.gov")
#: node id -> (citation, tier, the sentence the section's operative text prints)
DERIVED_PAY_PROVISIONS = {
    "jud-specialized-tax-chief-judge-tax-court": (
        "26 U.S.C. 7443(c)(1)",
        "district judges",
        "Each judge shall receive salary at the same rate and in the same installments "
        "as judges of the district courts of the United States.",
    ),
    "jud-specialized-claims-chief-judge-cfc": (
        "28 U.S.C. 172(b)",
        "district judges",
        "Each judge shall receive a salary at the rate of pay, and in the same manner, "
        "as judges of the district courts of the United States.",
    ),
    "jud-specialized-caaf-chief-judge-caaf": (
        "10 U.S.C. 942(d)",
        "circuit judges",
        "Each judge of the court is entitled to the same salary and travel allowances as are, "
        "and from time to time may be, provided for judges of the United States Courts of Appeals.",
    ),
    "jud-specialized-cavc-chief-judge-cavc": (
        "38 U.S.C. 7253(e)",
        "district judges",
        "Each judge of the Court shall receive a salary at the same rate as is received by "
        "judges of the United States district courts.",
    ),
}
#: Each court's bench node takes its chief judge's provision: "Each judge"
#: covers them all. Mirrors derived_pay.BENCH_NODES.
DERIVED_PAY_BENCHES = {
    "jud-specialized-tax-judge-18": "jud-specialized-tax-chief-judge-tax-court",
    "jud-specialized-claims-judge-15": "jud-specialized-claims-chief-judge-cfc",
    "jud-specialized-caaf-judge-4": "jud-specialized-caaf-chief-judge-caaf",
    "jud-specialized-cavc-judge-8": "jud-specialized-cavc-chief-judge-cavc",
}
for _bench, _chief in DERIVED_PAY_BENCHES.items():
    DERIVED_PAY_PROVISIONS[_bench] = DERIVED_PAY_PROVISIONS[_chief]
#: Two judicial-branch offices paid at a judge's rate, since 2026-09-28. The
#: FJC row is a CHAIN: 28 U.S.C. 626 pays its Director what the Administrative
#: Office's Director is paid, and 28 U.S.C. 603 pays that Director as a
#: district judge -- so the row carries a fourth element, (citation, sentence)
#: of the middle statute, and the block must list THREE documents.
DERIVED_PAY_PROVISIONS["jud-support-aousc-director-aousc"] = (
    "28 U.S.C. 603",
    "district judges",
    "The salary of the Director shall be the same as the salary of a district judge.",
)
DERIVED_PAY_PROVISIONS["jud-support-fjc-director-fjc"] = (
    "28 U.S.C. 626",
    "district judges",
    "The compensation of the Director of the Federal Judicial Center shall be the same as that of "
    "the Director of the Administrative Office of the United States Courts",
    ("28 U.S.C. 603", "The salary of the Director shall be the same as the salary of a district judge."),
)
#: A percentage OF the tier, since 2026-09-30: 28 U.S.C. 153(a) pays "each
#: bankruptcy judge" 92 percent of a district judge's salary. The block carries
#: the arithmetic in the open and the figure is checked as base * percent /
#: 100 to the cent against the mirrored table; the row is keyed by node id and
#: the percentage mirrored beside it, so a parity row cannot acquire a
#: percentage and a percentage row cannot drop one. The magistrate judges'
#: section (28 U.S.C. 634(a)) is committed and deliberately NOT here: it sets a
#: CEILING ("up to" 92 percent), fixed by the Judicial Conference, not a rate.
DERIVED_PAY_BANKRUPTCY_SENTENCE = (
    "Each bankruptcy judge shall serve on a full-time basis and shall receive as full compensation "
    "for his services, a salary at an annual rate that is equal to 92 percent of the salary of a "
    "judge of the district court of the United States as determined pursuant to section 135"
)
for _node_id in ("jud-district-sdny-bankruptcy-judge-12", "jud-district-structure-bankruptcy-judge-varies"):
    DERIVED_PAY_PROVISIONS[_node_id] = ("28 U.S.C. 153(a)", "district judges", DERIVED_PAY_BANKRUPTCY_SENTENCE)
#: A percentage of a JOIN, since 2026-10-05 (the owner's decision): the Tax
#: Court's special trial judges at 26 U.S.C. 7443A(d)'s 90 percent of a Tax
#: Court judge's rate, which 7443(c)(1) sets at a district judge's; the AO's
#: Deputy at 28 U.S.C. 603's 92 percent of a Director paid as a district judge
#: (two sentences of one section, joined by " … "); and the FJC's Deputy, paid
#: by 28 U.S.C. 626 what the AO's Deputy is paid. A chain row's fourth element
#: is the middle statute; the percentage is mirrored beside each by node id.
DERIVED_PAY_SPECIAL_TRIAL_SENTENCE = (
    "Each special trial judge shall receive salary— (1) at a rate equal to 90 percent of the rate for "
    "judges of the Tax Court, and (2) in the same installments as such judges."
)
DERIVED_PAY_AO_SENTENCES = (
    "The salary of the Director shall be the same as the salary of a district judge. … "
    "The salary of the Deputy Director shall be 92 percent of the salary of the Director."
)
DERIVED_PAY_PROVISIONS["jud-specialized-tax-special-trial-judge-multiple"] = (
    "26 U.S.C. 7443A(d)",
    "district judges",
    DERIVED_PAY_SPECIAL_TRIAL_SENTENCE,
    ("26 U.S.C. 7443(c)(1)", DERIVED_PAY_PROVISIONS["jud-specialized-tax-chief-judge-tax-court"][2]),
)
DERIVED_PAY_PROVISIONS["jud-support-aousc-deputy-director"] = (
    "28 U.S.C. 603",
    "district judges",
    DERIVED_PAY_AO_SENTENCES,
)
DERIVED_PAY_PROVISIONS["jud-support-fjc-deputy-director"] = (
    "28 U.S.C. 626",
    "district judges",
    "The compensation of the Deputy Director of the Federal Judicial Center shall be the same as that of "
    "the Deputy Director of the Administrative Office of the United States Courts.",
    ("28 U.S.C. 603", DERIVED_PAY_AO_SENTENCES),
)
#: node id -> the whole percentage of the tier the statute pays. Every other
#: derived row is paid AT the tier and must carry no arithmetic block.
DERIVED_PAY_PERCENT_OF = {
    "jud-district-sdny-bankruptcy-judge-12": 92,
    "jud-district-structure-bankruptcy-judge-varies": 92,
    "jud-specialized-tax-special-trial-judge-multiple": 90,
    "jud-support-aousc-deputy-director": 92,
    "jud-support-fjc-deputy-director": 92,
}
#: The sentence 38 U.S.C. 7253's Amendments note prints as the section's PRIOR
#: text. It is on the page, it is not the law, and publishing it would put the
#: CAVC's chief judge at the circuit rate. Refused outright wherever it is
#: quoted, whatever else a record gets right.
DERIVED_PAY_REPEALED_TEXT = (
    "The chief judge of the Court shall receive a salary at the same rate as is received by "
    "judges of the United States Courts of Appeals."
)
#: The project's own source arithmetic as a whole percentage, mirrored so the
#: published figure cannot drift from the scale it names: one official
#: document 70, two 80, three 90, four or more 100.
DERIVED_PAY_STRENGTH_BY_COUNT = {1: 70, 2: 80, 3: 90, 4: 100}

# ---------------------------------------------------------------------------
# The document count on EVERY pay field, mirrored from
# `pay_documents.PAY_DOCUMENT_FIELDS` and pinned equal to it by
# tests/test_pay_documents.py. Two things are checked and they are different
# claims: the count is recomputed from the URLs the block itself carries, so a
# block cannot say "2 documents" while naming one; and the number of them that
# STATE the figure is the mirror's, so a derived figure cannot quietly start
# claiming a document prints it.
#: field -> where its documents' URLs live. A string is a top-level key, a
#: 2-tuple is (nested block, key), and ("documents", "*", "url") is a list of
#: document records.
PAY_DOCUMENT_URL_KEYS = {
    "positionPayRate": ("url", ("levelSource", "url")),
    "positionGradePay": ("url", ("listingSource", "url")),
    "positionSchedulePay": ("url", "statuteUrl", ("identification", "basisUrl")),
    "positionStatutoryPay": ("url",),
    "positionReportedPay": ("url",),
    "positionCurrentPay": ("url",),
    "positionTierPay": ("url",),
    "positionDerivedPay": (("documents", "*", "url"),),
    "positionTierReferencePay": (("documents", "*", "url"),),
}
#: How many of a field's documents print the figure itself. Every printed rate
#: or printed pair of bounds is 1; a derived figure is 0, and that difference
#: is the whole reason the field exists.
PAY_DOCUMENT_STATES_FIGURE = {
    "positionPayRate": 1,
    "positionGradePay": 1,
    "positionSchedulePay": 1,
    "positionStatutoryPay": 1,
    "positionReportedPay": 1,
    "positionCurrentPay": 1,
    "positionTierPay": 1,
    "positionDerivedPay": 0,
    "positionTierReferencePay": 0,
}

# The Senate's own year-by-year salary schedule, mirrored the same way and
# pinned by tests/test_congressional_pay.py against
# tests/fixtures/congress/senate_salaries_since_1789.html.
SENATE_SALARY_YEAR = "2026"
SENATE_SALARY_BASE_RATE = 174_000.0
SENATE_LEADERSHIP_RATE = 193_400.0
SENATE_LEADERSHIP_FOOTNOTE = (
    "Note: Since the early 1980s, Senate leaders–majority and minority leaders, and the "
    "president pro tempore–have received higher salaries than other members. Currently, "
    "leaders earn $193,400 per year."
)
# Which role each priced node stands for, so the gate can check the quoted
# footnote actually names that role rather than trusting the node's own say-so.
SENATE_LEADERSHIP_ROLE_PHRASES = {
    "president pro tempore": "president pro tempore",
    "majority leader": "majority and minority leaders",
    "minority leader": "majority and minority leaders",
}

# The weights the cascade may divide a share by. A pay rate appearing here
# would mean a rate of basic pay had become an apportionment basis.
KNOWN_COST_BASES = {
    "annual_budget_weight", "budget_weight", "direct_outlay_weight",
    "implied_budget_weight", "employee_weight", "implied_employee_weight",
    "subtree_weight",
}


def table_pay_violations(node, pay, listing, today, label):
    """Everything that must be true of a rate looked up from the salary table.

    The claim being checked is a join of two documents — *the archive reports
    this post at Level II; the January 2026 table pays Level II $228,000* — and
    every rule here exists to stop one half being published as if it were the
    other, or as if either were this unit's cost.
    """
    out = []
    say = lambda text: out.append("{} {}".format(label(node), text))
    if not isinstance(pay, dict):
        say("positionPayRate {!r} is not a record".format(pay))
        return out

    # Whose figure it is. A rate of basic pay is one post's rate; on an
    # organisation it would read as what the unit costs. This is the dual of
    # the gate's existing "a measured cost sits only on an organisation".
    type_text = str(node.get("type") or "").casefold()
    if not any(word in type_text for word in ("position", "role", "office holder")):
        say("carries a rate of basic pay but is a {!r}, not a post".format(node.get("type")))
    # A node standing for many posts has no single holder for a rate to be of,
    # and its own panel sentence says any figure shown is the group's.
    if node.get("representsPosts"):
        say("carries one post's rate but stands for several posts")

    # The level half. It must still be the level the archive publishes on this
    # very node: if positions.py withdrew or changed the listing, the rate is a
    # figure for a rank nothing now says this post holds.
    level = str(pay.get("payLevel") or "")
    plan = str(pay.get("payPlan") or "")
    if level not in EXECUTIVE_SCHEDULE_RATES:
        say("prices level {!r}, which the Executive Schedule does not have".format(level))
    if plan != EXECUTIVE_SCHEDULE_PAY_PLAN:
        # The archive carries Roman numerals on pay plans that are not the
        # Executive Schedule at all ("THE SECRETARY" on AD, "BOARD MEMBER -
        # CHAIR" on WC). Those are ranks in other systems and this table does
        # not price them.
        say("prices pay plan {!r}; only {!r} is the Executive Schedule".format(plan, EXECUTIVE_SCHEDULE_PAY_PLAN))
    if not isinstance(listing, dict):
        say("claims a table rate with no position listing beneath it to say what level the post is")
    else:
        if str(listing.get("payLevel") or "") != level:
            say("prices level {!r} but its listing reports {!r}".format(level, listing.get("payLevel")))
        if str(listing.get("payPlan") or "") != plan:
            say("prices pay plan {!r} but its listing reports {!r}".format(plan, listing.get("payPlan")))
        if listing.get("reportedPay") is not None:
            say("carries a table rate beside a rate the archive states; two rates for one post")
        if not listing.get("payPlanAndLevelOnOneRow"):
            # The module's central refusal, checkable from the published graph
            # alone. describe_listing aggregates the pay plan and the level
            # independently and ignores blanks, so without this a pair the
            # archive never printed on one row could be priced.
            say("prices a pay plan and level the archive never printed on one row")

    # The rate half. The mirrored table is the only thing that can catch a
    # figure that is simply wrong, and the printed text must agree with it too
    # — the panel prints the text and the JSON carries the number.
    amount = pay.get("amount")
    expected = EXECUTIVE_SCHEDULE_RATES.get(level)
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        say("publishes {!r} as a rate of basic pay".format(amount))
    elif expected is not None and abs(float(amount) - expected) > 0.005:
        say("publishes {:,.2f} for level {}, which the table pays {:,.2f}".format(float(amount), level, expected))
    # Everything below is a field the PANEL PRINTS VERBATIM. Checking the
    # machine-readable amount and leaving these free text would mean the gate
    # vouched for a figure while the sentence beside it said something else —
    # "pays $197,200 per month", "effective January 2031", "for Level I".
    if expected is not None:
        printed = "${:,.0f}".format(expected)
        if str(pay.get("rateText") or "") != printed:
            # Not a digit comparison: digits alone let arbitrary text ride
            # along into the money figure the reader sees.
            say("prints the rate as {!r}; the table prints {!r}".format(pay.get("rateText"), printed))
        scope = str(pay.get("amountScope") or "")
        if scope.casefold() != "level {}".format(level).casefold():
            # amountScope is the only field saying which level the printed
            # rate is for, and the panel prints it at the end of the sentence.
            say("prints the rate as being for {!r} while pricing level {!r}".format(scope, level))
    if str(pay.get("table") or "") != EXECUTIVE_SCHEDULE_TABLE:
        say("cites table {!r}, not {!r}".format(pay.get("table"), EXECUTIVE_SCHEDULE_TABLE))

    # Both dates, because the two-sourced claim is only auditable when a reader
    # can see that one source is older than the other. The table's effective
    # date is deliberately NOT required to be past: a table may be published
    # ahead of the date it takes effect.
    if str(pay.get("effective") or "") != EXECUTIVE_SCHEDULE_EFFECTIVE:
        say("dates the table {!r}, not {!r}".format(pay.get("effective"), EXECUTIVE_SCHEDULE_EFFECTIVE))
    if str(pay.get("effectiveText") or "") != EXECUTIVE_SCHEDULE_EFFECTIVE_TEXT:
        # The heading is what the panel prints; the ISO date is what the gate
        # would otherwise be checking. Both, or a reader and the machine are
        # being told different things.
        say("prints the effective heading as {!r}; the page prints {!r}".format(
            pay.get("effectiveText"), EXECUTIVE_SCHEDULE_EFFECTIVE_TEXT))
    checked = str(pay.get("checkedAt") or "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}", checked) or checked[:10] > today:
        say("claims a table rate without a past retrieval date ({!r})".format(checked))
    url = str(pay.get("url") or "")
    host = host_of(url)
    if not host.endswith((".gov", ".mil")):
        say("claims a table rate with no .gov/.mil document behind it")
    source = pay.get("levelSource") if isinstance(pay.get("levelSource"), dict) else {}
    if not str(source.get("edition") or "").strip():
        say("does not say which edition of the archive reported the level")
    src_url = str(source.get("url") or "")
    src_host = host_of(src_url)
    if not src_host.endswith((".gov", ".mil")):
        say("does not say which document reported the level")

    # The footnote. A pay freeze for the Vice President and certain senior
    # political appointees is the difference between the table's rate and what
    # was payable, so dropping it publishes a rate that may not have been paid.
    footnotes = pay.get("footnotes")
    if not isinstance(footnotes, list) or not any(str(f).strip() for f in footnotes):
        say("carries a table rate without the notes the table prints beside it")
    elif tuple(str(f).strip() for f in footnotes) != EXECUTIVE_SCHEDULE_FOOTNOTES:
        # The panel prints these in quotation marks as the table's own words,
        # so anything but the page's actual notes is a fabricated quotation.
        say("quotes notes the table does not carry")

    # It is not a cost, and it is not evidence that the post exists.
    if str(node.get("cost_status") or "") in ("official", "root_total", "scaled_official"):
        say("carries a table rate and a measured cost status {!r}".format(node.get("cost_status")))
    if str(node.get("costVerificationStatus") or "") == "verified":
        say("carries a table rate and claims a verified cost")
    basis = str(node.get("cost_basis") or "")
    if basis and basis not in KNOWN_COST_BASES:
        say("carries a table rate and an unknown cost basis {!r}".format(basis))
    method = str(pay.get("method") or "")
    if method and str(node.get("verificationMethod") or "") == method:
        say("verifies its own existence with a salary table that names no post")
    if method and str(node.get("placementMethod") or "") == method:
        say("places itself with a salary table that names no post")
    # And the table's URL must not be among the node's sources. pay_tables
    # deliberately writes no sourceUrls, but that was abstinence with nothing
    # enforcing it: `verify_node_sources` counts URLs and classifies hosts, so
    # one more .gov URL adds `official_site` and carries confidence 0.5 -> 0.8.
    # It happened — 29 posts published `verified` on a five-row table naming no
    # post, and the graph went 49 -> 78 verified with the gate reporting clean.
    # Worse, it would have been unwithdrawable: the sweep in evidence.py takes
    # back only the URLs a module recorded in `evidenceUrls`, and this module
    # records none. Checked from the artefact so the rule survives the module.
    if str(pay.get("url") or "") in [str(u) for u in (node.get("sourceUrls") or [])]:
        say("cites the salary table among the sources that it exists; five rank rates name no post")
    return out


#: Which mirror, which node kind, and which quoted footnote each source in
#: `positionStatutoryPay` must match. One shared checker for both judicial and
#: congressional pay — the shape they write is the same single-source claim
#: (see `judicial_pay.py`, `congressional_pay.py`), so one function checking
#: it against the right mirror by `source` is more auditable than two nearly
#: identical ones that could drift apart from each other.
#: Which tier or role each specific node is priced at. Checked against the
#: node's own id, not just against whether the quoted text happens to
#: contain the phrase for whatever tier the record claims — three Senate
#: leadership roles share one dollar figure and one shared footnote, so a
#: record for the Majority Leader that claimed to be the President Pro
#: Tempore instead would still quote a footnote naming that role and price
#: the same $193,400; only a check tied to the node's own identity catches
#: it. Pinned against `judicial_pay.classify_seat` and
#: `congressional_pay.LEADERSHIP_NODE_IDS` by
#: tests/test_judicial_pay.py and tests/test_congressional_pay.py.
STATUTORY_PAY_NODE_TIERS = {
    "jud-scotus-chief-justice-of-the-united-states": "chief justice",
    "jud-circuit-1st-circuit-chief-judge-1st-circuit": "circuit judges",
    "jud-circuit-2nd-circuit-chief-judge-2nd-circuit": "circuit judges",
    "jud-circuit-3rd-circuit-chief-judge-3rd-circuit": "circuit judges",
    "jud-circuit-4th-circuit-chief-judge-4th-circuit": "circuit judges",
    "jud-circuit-5th-circuit-chief-judge-5th-circuit": "circuit judges",
    "jud-circuit-6th-circuit-chief-judge-6th-circuit": "circuit judges",
    "jud-circuit-7th-circuit-chief-judge-7th-circuit": "circuit judges",
    "jud-circuit-8th-circuit-chief-judge-8th-circuit": "circuit judges",
    "jud-circuit-9th-circuit-chief-judge-9th-circuit": "circuit judges",
    "jud-circuit-10th-circuit-chief-judge-10th-circuit": "circuit judges",
    "jud-circuit-11th-circuit-chief-judge-11th-circuit": "circuit judges",
    "jud-circuit-d-c-circuit-chief-judge-d-c-circuit": "circuit judges",
    "jud-circuit-federal-circuit-chief-judge-federal-circuit": "circuit judges",
    "jud-district-sdny-chief-judge-sdny": "district judges",
    # Benches priced since 2026-09-23: every judge of the tier is paid the tier
    # rate, and the block's `holders` says so. Circuit benches are absent on
    # purpose -- each one's name bundles senior judges, whose salary 28 U.S.C.
    # 371(b)(2) sets by reference to a past year (adjusted under §461), not
    # necessarily the tier's current rate.
    "jud-scotus-associate-justice-8": "associate justices",
    "jud-district-sdny-district-judge-28-active": "district judges",
    "leg-senate-leadership-president-pro-tempore": "president pro tempore",
    "leg-senate-leadership-majority-leader": "majority leader",
    "leg-senate-leadership-minority-leader": "minority leader",
    # Schedule 6 of the annual pay-adjustment order, as 5 U.S.C. 5332's note
    # prints it. Keyed by id for the reason above and one sharper: the House
    # Majority and Minority Leaders are priced from ONE row that names them
    # together, so a record moved between them keeps a correct figure, a
    # correct quote and a real statutory row, and only the node's own
    # identity tells them apart. Pinned against
    # `us_code_pay_schedules.SCHEDULE_6_NODE_ROWS` by
    # tests/test_us_code_pay_schedules.py.
    "exec-vp": "vice president",
    "leg-house-leadership-speaker-of-the-house": "speaker of the house of representatives",
    "leg-house-leadership-majority-leader": "majority leader and minority leader of the house of representatives",
    "leg-house-leadership-minority-leader": "majority leader and minority leader of the house of representatives",
    # Schedule 7 of the same note, since 2026-10-05: the one judicial tier
    # uscourts.gov's table does not print. The chief judge is a judge of the
    # court and the bench of eight carries the rate for each holder; pinned
    # against `us_code_pay_schedules.SCHEDULE_7_NODE_ROWS`.
    "jud-specialized-intl-trade-chief-judge-cit": "judges of the court of international trade",
    "jud-specialized-intl-trade-judge-8": "judges of the court of international trade",
}

#: Schedule 6's own rows, mirrored stdlib-only the way EXECUTIVE_SCHEDULE_RATES
#: mirrors OPM's five. Pinned equal to what the committed note prints by
#: tests/test_us_code_pay_schedules.py, so the two cannot drift.
US_CODE_SCHEDULE_6_YEAR = "2026"
US_CODE_SCHEDULE_6_RATES = {
    "vice president": 292_300.0,
    "speaker of the house of representatives": 223_500.0,
    "majority leader and minority leader of the house of representatives": 193_400.0,
    # The seat rows, priced since 2026-09-30 for the offices Members hold
    # (committee chairs and ranking members, the whips, the conference and
    # caucus chairs) under the member-seat method below, never by node id.
    "senators": 174_000.0,
    "members of the house of representatives": 174_000.0,
}
#: The offices Members of Congress hold, priced at the SEAT rate of their
#: chamber's row since 2026-09-30 (the owner's decision; see
#: us_code_pay_schedules.py's docstring). Mirrored as a RULE rather than as
#: 461 ids: the method, the chamber rows, the role prefixes a committee post's
#: name must begin with, the parent types it must sit under, and the reviewed
#: leadership table by id. Pinned equal to the module's by
#: tests/test_us_code_pay_schedules.py.
US_CODE_MEMBER_SEAT_METHOD = (
    "member_of_congress_priced_at_the_seat_rate_of_schedule_6_of_the_annual_pay_adjustment_order"
)
US_CODE_MEMBER_SEAT_ROWS = {
    "leg-senate": "senators",
    "leg-house": "members of the house of representatives",
}
US_CODE_MEMBER_ROLE_PREFIXES = ("Chair, ", "Ranking Member, ")
US_CODE_MEMBER_COMMITTEE_TYPES = ("committee", "subcommittee")
US_CODE_MEMBER_LEADERSHIP_NODES = {
    "leg-senate-leadership-majority-whip": "leg-senate",
    "leg-senate-leadership-minority-whip": "leg-senate",
    "leg-senate-leadership-assistant-majority-leader": "leg-senate",
    "leg-senate-leadership-assistant-minority-leader": "leg-senate",
    "leg-senate-leadership-majority-conference-chair": "leg-senate",
    "leg-senate-leadership-minority-conference-chair": "leg-senate",
    "leg-senate-leadership-majority-conference-secretary": "leg-senate",
    "leg-senate-leadership-majority-policy-committee-chair": "leg-senate",
    "leg-senate-leadership-minority-policy-committee-chair": "leg-senate",
    "leg-senate-leadership-majority-steering-committee-chair": "leg-senate",
    "leg-senate-leadership-majority-campaign-committee-chair": "leg-senate",
    "leg-house-leadership-speaker-pro-tempore": "leg-house",
    "leg-house-leadership-majority-whip": "leg-house",
    "leg-house-leadership-minority-whip": "leg-house",
    "leg-house-leadership-chief-deputy-majority-whip": "leg-house",
    "leg-house-leadership-chief-deputy-minority-whip": "leg-house",
    "leg-house-leadership-democratic-caucus-chair": "leg-house",
    "leg-house-leadership-democratic-caucus-vice-chair": "leg-house",
    "leg-house-leadership-republican-conference-chair": "leg-house",
    "leg-house-leadership-republican-conference-vice-chair": "leg-house",
    "leg-house-leadership-republican-conference-secretary": "leg-house",
    "leg-house-leadership-democratic-steering-policy-committee-chair": "leg-house",
    "leg-house-leadership-republican-study-committee-chair": "leg-house",
    "leg-house-leadership-house-freedom-caucus-chair": "leg-house",
    "leg-house-leadership-new-democrat-coalition-chair": "leg-house",
}
#: Posts the rule refuses by name (the module's MEMBER_SEATS_NOT_PRICED).
US_CODE_MEMBER_SEATS_NOT_PRICED = (
    "leg-house-leadership-problem-solvers-caucus-co-chairs",
    "leg-senate-leadership-president-of-the-senate-vice-president",
    "leg-joint-econ-chair-alternates-senate-house",
    "leg-joint-econ-vice-chair",
)
#: The panel prints a member-seat block's `basis` as the reason the seat rate
#: applies, so an unmirrored basis would be a fabricated-reason channel (the
#: lesson the reviewed Schedule rows taught). Every basis must carry the
#: schedule's own list of the offices it prices separately, must say the
#: identification is a reviewed rule, and on a House seat must note the
#: Delegate and Resident Commissioner rows.
US_CODE_MEMBER_SEAT_SEPARATE_RATES = (
    "Schedule 6 prints a separate rate only for the Vice President, the Speaker, the majority and "
    "minority leaders of each chamber and the President pro tempore"
)
US_CODE_MEMBER_SEAT_REVIEWED_WORDS = "a reviewed rule, not a document naming this post"
US_CODE_HOUSE_SEAT_ROWS_NOTE = (
    "Schedule 6 prints the same 174,000 for Delegates to the House of Representatives and for the "
    "Resident Commissioner from Puerto Rico, so a seat held by either is priced the same."
)
#: The effective line the note prints beneath Schedule 6's heading. Every
#: record quotes it, and the gate requires the quote to carry it: a rate with
#: no effective date is a number, not a schedule entry.
US_CODE_SCHEDULE_6_EFFECTIVE = (
    "(Effective on the first day of the first applicable pay period beginning on or after January 1, 2026)"
)
#: The currency mark sits once, on the column's first figure. A record for a
#: bare row must quote this head, which is what makes its own bare figure
#: readable as dollars; see financial_evidence.COLUMN_HEAD_MARK_SOURCE_TYPES.
US_CODE_SCHEDULE_6_COLUMN_HEAD = "$292,300"
#: The schedule's own heading, as the note prints it. A record must quote it:
#: "193,400" appears three times in Schedule 6 and also in Schedule 5's
#: neighbourhood, and the heading is what ties a figure to this schedule.
SCHEDULE_6_HEADING = "Schedule 6 — Vice President and Members Of Congress"
#: Schedule 7 of the same note, mirrored for the one row it prices (since
#: 2026-10-05): "249,900" is also the District Judges row, so the heading,
#: the effective line and the marked head of ITS column ($320,700, the Chief
#: Justice's row) are what tie a record to this schedule and this row. Pinned
#: equal to the note by tests/test_us_code_pay_schedules.py.
SCHEDULE_7_HEADING = "Schedule 7 — Judicial Salaries"
US_CODE_SCHEDULE_7_RATES = {
    "judges of the court of international trade": 249_900.0,
}
US_CODE_SCHEDULE_7_EFFECTIVE = US_CODE_SCHEDULE_6_EFFECTIVE
US_CODE_SCHEDULE_7_COLUMN_HEAD = "$320,700"

STATUTORY_PAY_SOURCES = {
    "uscourts_judicial_compensation": {
        "url": "https://www.uscourts.gov/about-federal-courts/about-federal-judges/judicial-compensation",
        "year": JUDICIAL_COMPENSATION_YEAR,
        "tiers": JUDICIAL_COMPENSATION_TIERS,
        "footnotes": JUDICIAL_COMPENSATION_FOOTNOTES,
        "id_prefix": "jud-",
    },
    "senate_salary_schedule": {
        "url": "https://www.senate.gov/senators/SenateSalariesSince1789.htm",
        "year": SENATE_SALARY_YEAR,
        "tiers": {role: SENATE_LEADERSHIP_RATE for role in SENATE_LEADERSHIP_ROLE_PHRASES},
        "footnotes": (SENATE_LEADERSHIP_FOOTNOTE,),
        "id_prefix": "leg-",
    },
    # The one source here that reaches two branches: Schedule 6 prices the
    # Vice President under the executive and the House's leadership under the
    # legislature, so `id_prefix` is a tuple. It is still a prefix check and
    # not a free pass: nothing judicial may be priced from it.
    "us_code_pay_schedules": {
        "url": (
            "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title5-section5332"
            "&num=0&edition=prelim"
        ),
        "year": US_CODE_SCHEDULE_6_YEAR,
        "tiers": {**US_CODE_SCHEDULE_6_RATES, **US_CODE_SCHEDULE_7_RATES},
        "footnotes": None,  # the record quotes the schedule itself; checked below
        # Schedule 6 reaches the executive and the legislature; Schedule 7
        # (one row) the judiciary. Which schedule a record may price from is
        # decided by its tier below, and never crosses.
        "id_prefix": ("exec-", "leg-", "jud-"),
    },
}

# ---------------------------------------------------------------------------
# The White House Office's statutory annual personnel report — a roster, not a
# rate schedule, so it gets its own checker rather than reusing the statutory
# one above. See data_pipeline/verification/whitehouse_pay.py.
WHITEHOUSE_REPORT_URL = (
    "https://www.whitehouse.gov/wp-content/uploads/2026/07/"
    "2026-Annual-Report-to-Congress-on-White-House-Staff.pdf"
)
WHITEHOUSE_REPORT_AS_OF = "2026-07-01"
WHITEHOUSE_REPORT_AS_OF_TEXT = "Wednesday, July 1, 2026"
WHITEHOUSE_PAY_METHOD = "rate_reported_for_the_one_person_listed_under_this_title"
WHITEHOUSE_PAY_METHOD_UNIFORM = "rate_reported_for_each_of_the_people_listed_under_this_title"
WHITEHOUSE_REPORT_STATUSES = ("EMPLOYEE", "DETAILEE")
WHITEHOUSE_REPORT_PAY_BASIS = "Per Annum"
WHITEHOUSE_RANK_PREFIXES = (
    "DEPUTY ASSISTANT TO THE PRESIDENT AND ",
    "SPECIAL ASSISTANT TO THE PRESIDENT AND ",
    "ASSISTANT TO THE PRESIDENT AND ",
)

WHITEHOUSE_REPORT_FIXTURE = (
    Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "whitehouse" / "staff_report_2026.pdf"
)

#: The roster, read from the committed report itself rather than mirrored as a
#: literal. `EXECUTIVE_SCHEDULE_RATES` is a hand-kept mirror because it is five
#: rows; this is 233 titles, and a hand-kept copy of that would rot silently.
#:
#: The extraction below is deliberately a **second, independent**
#: implementation — this file imports nothing from `data_pipeline`, by design —
#: and `tests/test_whitehouse_pay.py` pins it equal to the module's own parser
#: on the real fixture, so the two cannot drift and a bug in one is caught by
#: the other. It is the same bargain the Executive Schedule mirror strikes.
_ROSTER_CACHE = {}


def whitehouse_roster(path=None):
    """canonical title -> (amount, how many people are listed under it).

    Returns {} when the fixture or its digest is missing, and the caller then
    refuses every reported-pay record rather than passing them unchecked.
    """
    fixture = Path(path) if path else WHITEHOUSE_REPORT_FIXTURE
    key = str(fixture)
    if key in _ROSTER_CACHE:
        return _ROSTER_CACHE[key]
    roster = {}
    try:
        raw = fixture.read_bytes()
        meta = json.loads(fixture.with_name(fixture.name + ".meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _ROSTER_CACHE[key] = roster
        return roster
    import hashlib
    import zlib
    if hashlib.sha256(raw).hexdigest() != str(meta.get("sha256") or "").lower():
        _ROSTER_CACHE[key] = roster
        return roster
    if b"/Encrypt" in raw:
        _ROSTER_CACHE[key] = roster
        return roster

    literal = re.compile(rb"\((?:\\.|[^\\()])*\)", re.S)

    def unescape(chunk):
        out = bytearray()
        i = 0
        simple = {0x6E: 10, 0x72: 13, 0x74: 9, 0x62: 8, 0x66: 12}
        while i < len(chunk):
            c = chunk[i]
            if c != 0x5C or i + 1 >= len(chunk):
                out.append(c)
                i += 1
                continue
            n = chunk[i + 1]
            if n in simple:
                out.append(simple[n])
                i += 2
            elif 0x30 <= n <= 0x37:
                j, digits = i + 1, b""
                while j < len(chunk) and len(digits) < 3 and 0x30 <= chunk[j] <= 0x37:
                    digits += bytes([chunk[j]])
                    j += 1
                out.append(int(digits, 8) & 0xFF)
                i = j
            else:
                out.append(n)
                i += 2
        return out.decode("latin-1")

    money = re.compile(r"^\$([\d,]+\.\d{2})$")
    person = re.compile(r"^[A-Z][A-Za-z.'\- ]*, [A-Z]")
    counts = {}
    for match in re.finditer(rb"stream\r?\n", raw):
        start = match.end()
        end = raw.find(b"endstream", start)
        if end < 0:
            continue
        try:
            stream = zlib.decompress(raw[start:end])
        except zlib.error:
            continue
        if b"TJ" not in stream and b"Tj" not in stream:
            continue
        rows, position = {}, None
        for token in re.finditer(
            rb"([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+Tm"
            rb"|\[(.*?)\]\s*TJ|\((?:\\.|[^\\()])*\)\s*Tj", stream, re.S):
            whole = token.group(0)
            if whole.rstrip().endswith(b"Tm"):
                position = round(float(whole.split()[5]), 1)
                continue
            if position is None:
                continue
            if token.group(7) is not None:
                text = "".join(unescape(x[1:-1]) for x in literal.findall(token.group(7)))
            else:
                found = literal.findall(whole)
                text = unescape(found[0][1:-1]) if found else ""
            if text.strip():
                rows.setdefault(position, []).append(text.strip())
        for cells in rows.values():
            amounts = [c for c in cells if money.match(c)]
            statuses = [c for c in cells if c in ("EMPLOYEE", "DETAILEE")]
            bases = [c for c in cells if c == "Per Annum"]
            rest = [c for c in cells
                    if not money.match(c) and c not in ("EMPLOYEE", "DETAILEE", "Per Annum")]
            names = [c for c in rest if person.match(c)]
            titles = [c for c in rest if not person.match(c)]
            if len(amounts) != 1 or len(statuses) != 1 or len(bases) != 1:
                continue
            if len(names) != 1 or len(titles) != 1:
                continue
            value = float(amounts[0][1:].replace(",", ""))
            entry = counts.setdefault(whitehouse_canonical(titles[0]), [value, 0, set(), set(), set()])
            entry[1] += 1
            entry[2].add(value)
            entry[3].add(statuses[0])
            entry[4].add(bases[0])
    # (the first amount seen, how many people hold the title, how many
    # DISTINCT amounts they are paid, the statuses printed, the pay bases
    # printed). A title several people hold prices a node only when the
    # distinct-amount figure is 1 -- every holder at one rate -- and the
    # block says so in `holders`; the status and basis a block publishes
    # must be the one the rows print, and a uniform claim needs one of each.
    roster = {title: (value, held, len(distinct), frozenset(statuses), frozenset(bases))
              for title, (value, held, distinct, statuses, bases) in counts.items()}
    _ROSTER_CACHE[key] = roster
    return roster


#: The multiplicity suffix the expanded White House subtree writes on a node
#: several people hold ("Special Assistant (×4)"); mirrors
#: whitehouse_pay._MULTIPLICITY_SUFFIX.
WHITEHOUSE_MULTIPLICITY_SUFFIX = re.compile(r"\s*\(\u00d7\s*(\d+)\s*\)\s*$")


def whitehouse_canonical(text):
    """The module's `canonical`, mirrored with the standard library alone."""
    upper = str(text or "").upper().replace("&", " AND ")
    return " ".join(re.sub(r"[^A-Z0-9 ]+", " ", upper).split())


def whitehouse_title_core(title):
    """The module's `title_core`, mirrored. A leading rank prefix only."""
    key = whitehouse_canonical(title)
    for prefix in WHITEHOUSE_RANK_PREFIXES:
        if key.startswith(prefix):
            folded = key[len(prefix):].strip()
            return folded if len(folded.split()) >= 2 else key
    return key


#: Mirrored from `data_pipeline.verification.usaspending.USASPENDING_NAME_ALIASES`
#: because this gate is stdlib-only and imports nothing from the pipeline it
#: checks. node id -> (the curated name the alias was written against, the name
#: the API prints). Keyed by id for the reason the Senate leadership case
#: established: an alias moved to another node would otherwise still name two
#: real strings. `tests/test_usaspending.py` asserts the mirror equals the
#: module's table, so the two cannot drift.
USASPENDING_NAME_ALIASES = {
    "exec-dept-dot-phmsa": ("Pipeline & Hazardous Materials Safety Admin (PHMSA)",
                            "Pipeline and Hazardous Materials Safety Administration"),
    "exec-dept-hud-fheo": ("Office of Fair Housing & Equal Opportunity (FHEO)",
                           "Fair Housing and Equal Opportunity"),
    "exec-ind-misc-chemical-safety-hazard-investigation-board-csb": (
        "Chemical Safety & Hazard Investigation Board (CSB)", "United States Chemical Safety Board"),
    "exec-ind-misc-americorps": ("AmeriCorps", "Corporation for National and Community Service"),
}


def usaspending_violations(node, block, today, label):
    """Everything that must be true of a File A gross-outlays block.

    The claim is narrow and the checks keep it that way: the block sits on an
    organisation, not a post; it is File A gross outlays, fiscal-year-to-date,
    dated, from api.usaspending.gov; the figure is the one the committed
    fixture prints for the key, re-read here from bytes whose digest still
    matches the block's; the name the API prints still reduces to this node's;
    the scale rests on the publisher's dictionary, whose digest is re-checked
    too; and -- the one that matters most -- it is not being published as the
    cost. A Treasury line is net and a File A figure is gross, so a node whose
    measured cost equals this figure to the cent is a node where the two were
    confused, and the gate says so.
    """
    import hashlib
    import json as _json
    import math
    from datetime import date

    out = []
    say = lambda text: out.append("{} {}".format(label(node), text))
    # The gate hands `today` in as an ISO string; the tests hand in a date.
    today_date = today if isinstance(today, date) else date.fromisoformat(str(today)[:10])
    if not isinstance(block, dict):
        say("usaspendingOutlays {!r} is not a record".format(block))
        return out
    if is_post(node) or node.get("synthetic"):
        say("carries a File A outlay but is a {!r}, not an organisation".format(node.get("type")))
    if block.get("source") != "usaspending_file_ab" or block.get("basis") != "gross_outlays":
        say("File A block claims source {!r} basis {!r}".format(block.get("source"), block.get("basis")))
        return out
    level = block.get("level")
    if level not in ("toptier", "bureau"):
        say("File A block has level {!r}".format(level))
        return out
    amount = block.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(float(amount)):
        say("publishes {!r} as a File A outlay".format(amount))
        return out
    if float(amount) == 0:
        say("publishes a File A outlay of zero, which is never published as a measurement")
    if block.get("periodCoverage") != "fiscal_year_to_date" or not isinstance(block.get("fiscalYear"), int):
        say("File A block is not a dated fiscal-year-to-date figure ({!r}, FY{!r})".format(
            block.get("periodCoverage"), block.get("fiscalYear")))
    for field in ("periodAsOf", "retrievedAt"):
        text = str(block.get(field) or "")[:10]
        try:
            when = date.fromisoformat(text)
        except ValueError:
            say("File A block {} {!r} is not an ISO date".format(field, block.get(field)))
            continue
        if when > today_date:
            say("File A block {} {!r} is in the future".format(field, block.get(field)))
    url = str(block.get("url") or "")
    if not url.startswith("https://api.usaspending.gov/"):
        say("File A block cites {!r}, not api.usaspending.gov".format(url))
    if block.get("unitsEvidenceKind") != "publishers_data_dictionary":
        say("File A block rests its scale on {!r}; this pipeline establishes it from the publisher's dictionary".format(
            block.get("unitsEvidenceKind")))
    source = block.get("unitsEvidenceSource") if isinstance(block.get("unitsEvidenceSource"), dict) else {}
    dictionary = PROJECT_ROOT / str(source.get("file") or "")
    if not str(source.get("file") or "").startswith("tests/fixtures/usaspending/") or not dictionary.is_file():
        say("File A block names a dictionary this repository does not carry: {!r}".format(source.get("file")))
    elif hashlib.sha256(dictionary.read_bytes()).hexdigest() != str(source.get("sha256") or "").lower():
        say("File A block names a dictionary whose digest does not match the committed workbook")
    fixture_rel = str(block.get("fixture") or "")
    fixture = PROJECT_ROOT / fixture_rel
    if not fixture_rel.startswith("tests/fixtures/usaspending/") or not fixture.is_file():
        say("File A block cites a fixture this repository does not carry: {!r}".format(fixture_rel))
        return out
    if hashlib.sha256(fixture.read_bytes()).hexdigest() != str(block.get("documentSha256") or "").lower():
        say("File A block cites a fixture whose digest does not match the bytes on disk")
        return out
    try:
        data = _json.loads(fixture.read_text(encoding="utf-8"))
    except ValueError:
        say("File A fixture {!r} is not JSON".format(fixture_rel))
        return out
    rows = data.get("results") or []
    if level == "toptier":
        rows = [r for r in rows if str(r.get("toptier_code")) == str(block.get("toptierCode"))]
        printed_amount = rows[0].get("outlay_amount") if len(rows) == 1 else None
        printed_name = rows[0].get("agency_name") if len(rows) == 1 else None
    else:
        rows = [r for r in rows if str(r.get("id")) == str(block.get("bureauId"))]
        printed_amount = rows[0].get("total_outlays") if len(rows) == 1 else None
        printed_name = rows[0].get("name") if len(rows) == 1 else None
    if len(rows) != 1:
        say("File A key {!r} matches {} rows of its fixture, not one".format(block.get("key"), len(rows)))
        return out
    if not isinstance(printed_amount, (int, float)) or abs(float(printed_amount) - float(amount)) > 0.005:
        say("publishes File A outlay {!r}; the fixture prints {!r} for {!r}".format(amount, printed_amount, block.get("key")))
    if canonical_key(block.get("apiName")) != canonical_key(printed_name):
        say("File A block records apiName {!r}; the fixture prints {!r}".format(block.get("apiName"), printed_name))
    alias = block.get("nameAlias") if isinstance(block.get("nameAlias"), dict) else None
    if alias is None:
        if canonical_key(printed_name) != canonical_key(node.get("name")):
            say("File A row is named {!r}, which no longer names this node".format(printed_name))
    else:
        # An alias says two names are one unit. It is only ever a claim about
        # names, so it may not buy a stronger grade, it must be one this
        # repository wrote down for THIS node, and it may not paper over a
        # name that already matches.
        node_id = str(node.get("id") or "")
        mirrored = USASPENDING_NAME_ALIASES.get(node_id)
        if mirrored is None:
            say("File A block claims a name alias this repository does not carry for it")
        else:
            graph_name, api_name = mirrored
            if canonical_key(alias.get("graphName")) != canonical_key(graph_name):
                say("File A alias was written against {!r}; this gate carries {!r}".format(
                    alias.get("graphName"), graph_name))
            if canonical_key(alias.get("apiName")) != canonical_key(api_name):
                say("File A alias names {!r}; this gate carries {!r}".format(alias.get("apiName"), api_name))
            if canonical_key(node.get("name")) != canonical_key(graph_name):
                say("File A alias was written against {!r}, and this node is now called {!r}".format(
                    graph_name, node.get("name")))
            if canonical_key(alias.get("apiName")) != canonical_key(printed_name):
                say("File A alias names {!r}; the fixture prints {!r}".format(alias.get("apiName"), printed_name))
        if canonical_key(printed_name) == canonical_key(node.get("name")):
            say("File A block carries a name alias, but the fixture already names this node")
        if str(block.get("financialEvidenceStatus") or "") != "partial":
            say("File A block rests on a name alias but is graded {!r}; an alias cannot earn 'verified'".format(
                block.get("financialEvidenceStatus")))
        if not str(alias.get("basis") or "").strip():
            say("File A alias carries no basis saying why the two names are one unit")
    # Never the cost. Gross is not net, and year-to-date is not a period the
    # Treasury line reports, so equality here means the figure leaked.
    measured = str(node.get("cost_status") or "") in ("official", "root_total")
    cost = node.get("resolved_total_amount")
    if measured and isinstance(cost, (int, float)) and abs(float(cost) - float(amount)) <= 0.005:
        say("publishes its File A gross outlay as its measured cost")
    return out


def grade_pay_violations(node, pay, listing, today, label):
    """Everything that must be true of a base-pay RANGE looked up from a
    salary table for the pay plan or grade the archive reports.

    The claim is a join, as positionPayRate's is -- *the archive files this
    post on pay plan GS at grade 15; Salary Table 2026-GS pays grade 15 from
    $126,384 to $164,301 before locality* -- and every rule here stops one
    half being published as if it were the other, a range being read as a
    rate, or either being read as this unit's cost.
    """
    out = []
    say = lambda text: out.append("{} {}".format(label(node), text))
    if not isinstance(pay, dict):
        say("positionGradePay {!r} is not a record".format(pay))
        return out

    type_text = str(node.get("type") or "").casefold()
    if not any(word in type_text for word in ("position", "role", "office holder")):
        say("carries a base-pay range but is a {!r}, not a post".format(node.get("type")))
    if node.get("representsPosts"):
        say("carries one post's pay range but stands for several posts")

    kind = str(pay.get("kind") or "")
    plan = str(pay.get("payPlan") or "")
    grade = str(pay.get("grade") or "")
    if kind == "general_schedule_grade":
        plans = ("GS",)
    elif kind in PAY_STRUCTURE_TABLES:
        plans = PAY_STRUCTURE_TABLES[kind]["payPlans"]
    else:
        say("publishes a range of kind {!r}, which this pipeline does not produce".format(kind))
        return out
    if plan not in plans:
        say("publishes a {} range for pay plan {!r}; that table covers {!r}".format(kind, plan, plans))

    # The listing half: the pay plan (and grade) must still be what the
    # archive publishes on this very node, and the archive must not itself
    # state a rate, which would make the range a second figure for one post.
    if not isinstance(listing, dict):
        say("claims a table range with no position listing beneath it to say what pay plan the post is on")
    else:
        if str(listing.get("payPlan") or "") != plan:
            say("ranges pay plan {!r} but its listing reports {!r}".format(plan, listing.get("payPlan")))
        if listing.get("reportedPay") is not None:
            say("carries a table range beside a rate the archive states; two figures for one post")
        if kind == "general_schedule_grade":
            if str(listing.get("payLevel") or "") != grade:
                say("ranges grade {!r} but its listing reports {!r}".format(grade, listing.get("payLevel")))
            if not listing.get("payPlanAndLevelOnOneRow"):
                say("ranges a pay plan and grade the archive never printed on one row")
        elif listing.get("payLevel"):
            say("ranges a pay system that has no levels beside a listing reporting level {!r}".format(listing.get("payLevel")))

    # The table half: the two bounds must be the figures the mirrored table
    # prints, as numbers AND as the printed digits the panel shows.
    minimum, maximum = pay.get("minimum"), pay.get("maximum")
    for name, value in (("minimum", minimum), ("maximum", maximum)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            say("publishes {!r} as the {} of a pay range".format(value, name))
    numeric = all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (minimum, maximum))
    if numeric and float(minimum) > float(maximum):
        say("publishes a minimum above its maximum; that is not a range")
    if kind == "general_schedule_grade":
        expected = GENERAL_SCHEDULE_RANGES.get(grade)
        if expected is None:
            say("ranges grade {!r}, which the General Schedule does not have".format(grade))
        elif numeric and (abs(float(minimum) - expected[0]) > 0.005 or abs(float(maximum) - expected[1]) > 0.005):
            say("publishes {:,.2f}-{:,.2f} for grade {}, which the table prints as {:,.2f}-{:,.2f}".format(
                float(minimum), float(maximum), grade, expected[0], expected[1]))
        if str(pay.get("table") or "") != GENERAL_SCHEDULE_TABLE:
            say("cites table {!r}, not {!r}".format(pay.get("table"), GENERAL_SCHEDULE_TABLE))
        if str(pay.get("effective") or "") != GENERAL_SCHEDULE_EFFECTIVE:
            say("dates the table {!r}, not {!r}".format(pay.get("effective"), GENERAL_SCHEDULE_EFFECTIVE))
        if str(pay.get("effectiveText") or "") != GENERAL_SCHEDULE_EFFECTIVE_TEXT:
            say("prints the effective heading as {!r}; the page prints {!r}".format(
                pay.get("effectiveText"), GENERAL_SCHEDULE_EFFECTIVE_TEXT))
        steps = pay.get("steps")
        if not isinstance(steps, list) or len(steps) != 10 or not all(
            isinstance(s, (int, float)) and not isinstance(s, bool) for s in steps
        ):
            say("does not carry the ten steps the table prints for the grade")
        elif numeric and (abs(float(steps[0]) - float(minimum)) > 0.005 or abs(float(steps[-1]) - float(maximum)) > 0.005):
            say("publishes bounds that are not its own step 1 and step 10")
        if str(pay.get("baseBeforeLocality") or "") != GENERAL_SCHEDULE_BASE_BEFORE_LOCALITY:
            # The panel prints this beside every GS range. A range without it
            # reads as what the post pays; with the locality adjustment it is
            # not, anywhere in the fifty states.
            say("publishes a General Schedule range without saying it is base pay before locality")
        footnotes = pay.get("footnotes")
        if not isinstance(footnotes, list) or any(str(f).strip() for f in footnotes):
            # The GS PDF prints no note beneath the table; a note attributed to
            # it is a fabricated quotation.
            say("quotes notes the General Schedule table does not carry")
        corroboration = pay.get("corroboration") if isinstance(pay.get("corroboration"), dict) else {}
        html_digest = fixture_digest(GRADE_PAY_FIXTURES[kind][1])
        if str(corroboration.get("documentSha256") or "").lower() != (html_digest or "-"):
            say("names an HTML corroboration digest that is not the committed page's")
        if not host_of(str(corroboration.get("url") or "")).endswith((".gov", ".mil")):
            say("corroborates the range from a document that is not on a .gov/.mil host")
    else:
        mirror = PAY_STRUCTURE_TABLES[kind]
        if str(pay.get("table") or "") != mirror["table"]:
            say("cites table {!r}, not {!r}".format(pay.get("table"), mirror["table"]))
        if str(pay.get("effective") or "") != GENERAL_SCHEDULE_EFFECTIVE:
            say("dates the table {!r}, not {!r}".format(pay.get("effective"), GENERAL_SCHEDULE_EFFECTIVE))
        if str(pay.get("effectiveText") or "") != GENERAL_SCHEDULE_EFFECTIVE_TEXT:
            say("prints the effective heading as {!r}; the page prints {!r}".format(
                pay.get("effectiveText"), GENERAL_SCHEDULE_EFFECTIVE_TEXT))
        rows = pay.get("rows")
        if not isinstance(rows, list) or len(rows) != len(mirror["rows"]):
            say("does not carry the two structure rows the table prints")
        else:
            for row, (m_label, m_min, m_max) in zip(rows, mirror["rows"]):
                if not isinstance(row, dict) or str(row.get("label") or "") != m_label:
                    say("prints a structure row labelled {!r}; the table prints {!r}".format(
                        (row or {}).get("label") if isinstance(row, dict) else row, m_label))
                    continue
                for name, expected_value in (("minimum", m_min), ("maximum", m_max)):
                    value = row.get(name)
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or abs(float(value) - expected_value) > 0.005:
                        say("publishes {!r} as the {} for {!r}, which the table prints as {:,.2f}".format(
                            value, name, m_label, expected_value))
        expected_min = mirror["rows"][0][1]
        expected_max = max(r[2] for r in mirror["rows"])
        if numeric and (abs(float(minimum) - expected_min) > 0.005 or abs(float(maximum) - expected_max) > 0.005):
            say("publishes {:,.2f}-{:,.2f} as the pay system's bounds, which the table prints as {:,.2f}-{:,.2f}".format(
                float(minimum), float(maximum), expected_min, expected_max))
        footnotes = pay.get("footnotes")
        if not isinstance(footnotes, list) or not any(str(f).strip() for f in footnotes):
            say("carries a table range without the notes the table prints beside it")
        elif tuple(str(f).strip() for f in footnotes) != EXECUTIVE_SCHEDULE_FOOTNOTES:
            say("quotes notes the table does not carry")
        if pay.get("baseBeforeLocality"):
            say("calls a {} range General Schedule base pay".format(kind))

    # The printed digits the panel shows must be the mirrored figures too.
    if numeric:
        for name, value in (("minimum", minimum), ("maximum", maximum)):
            printed = "{:,.0f}".format(float(value))
            if str(pay.get(name + "Printed") or "") != printed:
                say("prints the {} as {!r}; the table prints {!r}".format(name, pay.get(name + "Printed"), printed))

    # Which document, and that it is the committed one, byte for byte.
    cited = GRADE_PAY_FIXTURES[kind][0]
    if str(pay.get("documentSha256") or "").lower() != (fixture_digest(cited) or "-"):
        say("names a document digest that is not the committed {}'s".format(cited.name))
    if str(pay.get("unitsEvidenceKind") or "") != GRADE_PAY_UNITS_KIND[kind]:
        say("rests its scale on {!r}; a {} range rests on {!r}".format(
            pay.get("unitsEvidenceKind"), kind, GRADE_PAY_UNITS_KIND[kind]))
    if str(pay.get("scopeMatch") or "") != "proxy" or str(pay.get("financialEvidenceStatus") or "") != "partial":
        say("claims more than a proxy graded partial; a grade or a pay system names no post")
    checked = str(pay.get("checkedAt") or "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}", checked) or checked[:10] > today:
        say("claims a table range without a past retrieval date ({!r})".format(checked))
    if not host_of(str(pay.get("url") or "")).endswith((".gov", ".mil")):
        say("claims a table range with no .gov/.mil document behind it")
    source = pay.get("listingSource") if isinstance(pay.get("listingSource"), dict) else {}
    if not str(source.get("edition") or "").strip():
        say("does not say which edition of the archive reported the pay plan")
    if not host_of(str(source.get("url") or "")).endswith((".gov", ".mil")):
        say("does not say which document reported the pay plan")

    # It is not a cost, and it is not evidence that the post exists.
    if str(node.get("cost_status") or "") in ("official", "root_total", "scaled_official"):
        say("carries a table range and a measured cost status {!r}".format(node.get("cost_status")))
    if str(node.get("costVerificationStatus") or "") == "verified":
        say("carries a table range and a verified cost")
    if str(pay.get("url") or "") in [str(u) for u in (node.get("sourceUrls") or [])]:
        say("cites the salary table as a source of the post's existence")
    return out


def plum_current_export(path=None):
    """The current PLUM export re-read by the gate: its digest, its fetch
    record and an index (Agency, Organization, Position Title) -> live rows,
    each row exactly PLUM_CURRENT_COLUMNS and nothing else. Historical rows
    are counted per key and never read. Returns None when the fixture, its
    meta or its digest is missing or wrong, and every current-PLUM block is
    then refused rather than passed unchecked."""
    fixture = Path(path) if path else PLUM_CURRENT_FIXTURE
    key = str(fixture)
    if key in _PLUM_CURRENT_CACHE:
        return _PLUM_CURRENT_CACHE[key]
    out = None
    try:
        raw = fixture.read_bytes()
        meta = json.loads(fixture.with_name(fixture.name + ".meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _PLUM_CURRENT_CACHE[key] = out
        return out
    import csv as _csv
    import hashlib as _hashlib
    import io as _io

    digest = _hashlib.sha256(raw).hexdigest()
    if digest != str(meta.get("sha256") or "").lower():
        _PLUM_CURRENT_CACHE[key] = out
        return out
    reader = _csv.reader(_io.StringIO(raw.decode("utf-8-sig", errors="replace"), newline=""))
    header = [h.strip() for h in next(reader, [])]
    if any(column not in header for column in PLUM_CURRENT_COLUMNS):
        _PLUM_CURRENT_CACHE[key] = out
        return out
    positions = {column: header.index(column) for column in PLUM_CURRENT_COLUMNS}
    width = max(positions.values()) + 1
    index = {}
    for cells in reader:
        if len(cells) < width:
            continue
        row = {column: cells[i].strip() for column, i in positions.items()}
        entry = index.setdefault((row["Agency"], row["Organization"], row["Position Title"]), {"live": [], "historical": 0})
        if row["Position Status"] in PLUM_CURRENT_LIVE_STATUSES:
            entry["live"].append(row)
        else:
            entry["historical"] += 1
    out = {
        "sha256": digest,
        "url": str(meta.get("final_url") or meta.get("url") or ""),
        "fetched_at": str(meta.get("fetched_at") or ""),
        "index": index,
    }
    _PLUM_CURRENT_CACHE[key] = out
    return out


def plum_org_keys(value):
    """positions.organisation_name_keys mirrored stdlib-only: the canonical
    key and the 'department of (the) X' tolerance, the export's HTML entities
    resolved first. tests/test_plum_current.py pins the two together."""
    import html as _html

    key = canonical_key(_html.unescape(str(value or "")))
    if not key:
        return set()
    keys = {key}
    if key.startswith("department of the "):
        keys.add("department of " + key[len("department of the "):])
    elif key.startswith("department of "):
        keys.add("department of the " + key[len("department of "):])
    return keys


def _strip_plum_qualifier(text, qualifier_keys):
    if "," not in text:
        return text
    for index, char in enumerate(text):
        if char != ",":
            continue
        head, tail = text[:index].strip(), text[index + 1:].strip()
        if head and tail and canonical_key(tail) in qualifier_keys:
            return head
    return text


def plum_export_title_keys(title, organization):
    """positions.archive_title_keys mirrored: the title's own key and, when
    the tail after a comma is the organisation the row is filed under, the
    key of what is left."""
    import html as _html

    text = _html.unescape(str(title or "")).strip()
    keys = []
    for candidate in (text, _strip_plum_qualifier(text, plum_org_keys(organization))):
        key = canonical_key(candidate)
        if key and key not in keys:
            keys.append(key)
    return keys


def plum_agency_unit(agency):
    """The unit an agency string denotes: the whole string, or the half after
    ' - ' in the export's own '<parent> - <unit>' form."""
    import html as _html

    text = _html.unescape(str(agency or "")).strip()
    match = re.match(r"^(.+?)\s+-\s+(.+)$", text)
    return match.group(2).strip() if match else text


def plum_listing_parent_keys(listing):
    """The keys the tree parent must answer to: the organisation the export
    files the title under, or -- when that is the agency itself -- the agency
    as a whole and as its unit half."""
    org_keys = plum_org_keys(listing.get("organization"))
    agency_keys = plum_org_keys(listing.get("agency")) | plum_org_keys(plum_agency_unit(listing.get("agency")))
    if not org_keys or org_keys & agency_keys:
        return agency_keys
    return org_keys


def current_listing_violations(node, listing, today, label, parent_name, parent_alias_keys=()):
    """Everything that must be true of a listing from OPM's current PLUM
    export: a post, dated by the fetch, citing the committed file byte for
    byte, a Filled or Vacant row -- never Historical -- carrying every value
    the block publishes, filed under the node's own tree parent, and a title
    the node's name still answers to."""
    out = []
    say = lambda text: out.append("{} {}".format(label(node), text))
    if not isinstance(listing, dict):
        say("positionCurrentListing {!r} is not a record".format(listing))
        return out
    if not is_post(node):
        say("carries a current PLUM listing but is a {!r}, not a post".format(node.get("type")))
    if str(listing.get("source") or "") != PLUM_CURRENT_SOURCE or str(listing.get("method") or "") != PLUM_CURRENT_METHOD:
        say("names a source or method for its current PLUM listing that this pipeline does not produce")
    fetched = str(listing.get("exportFetchedAt") or "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}", fetched) or fetched[:10] > today:
        say("claims a current PLUM listing without a past fetch date ({!r})".format(fetched))
    if str(listing.get("checkedAt") or "") != fetched:
        say("dates its current PLUM listing {!r} but the export was fetched {!r}".format(listing.get("checkedAt"), fetched))
    url = str(listing.get("url") or "")
    if not host_of(url).endswith((".gov", ".mil")):
        say("claims a current PLUM listing with no .gov/.mil document behind it")
    export = plum_current_export()
    if export is None:
        say("claims a current PLUM listing but the committed export cannot be read or does not match its recorded digest")
        return out
    if str(listing.get("documentSha256") or "").lower() != export["sha256"]:
        say("names a document digest that is not the committed export's")
    if url != export["url"]:
        say("cites {!r}; the export was fetched from {!r}".format(url, export["url"]))
    if fetched != export["fetched_at"]:
        say("dates the export {!r}; its fetch record says {!r}".format(fetched, export["fetched_at"]))
    agency, organization, title = (str(listing.get(k) or "") for k in ("agency", "organization", "listedTitle"))
    # The parent: the organisation the export files the title under must be
    # the node's parent in the tree the gate is walking. Checked before the
    # row is looked up, so a block filed under the wrong organisation is
    # named as such rather than only as a row the export does not carry.
    if not ((plum_org_keys(parent_name) | set(parent_alias_keys)) & plum_listing_parent_keys(listing)):
        say("is filed by the export under {!r}, but its parent in the tree is {!r}".format(organization or agency, parent_name))
    # The name: the title must still be one the node's name answers to.
    if not (position_title_keys(node.get("name"), parent_name) & set(plum_export_title_keys(title, organization))):
        say("is listed as {!r}, which does not name it".format(title))
    # The row, by the block's own keys and nothing about who holds it.
    entry = export["index"].get((agency, organization, title))
    live = list((entry or {}).get("live") or [])
    if not live:
        say("lists {!r} under {!r} / {!r}, which the export carries no Filled or Vacant row for{}".format(
            title, agency, organization, " (Historical rows only)" if entry else ""))
        return out
    status = listing.get("positionStatus")
    statuses = {r["Position Status"] for r in live}
    if status is not None and (str(status) not in PLUM_CURRENT_LIVE_STATUSES or str(status) not in statuses):
        say("publishes position status {!r}; the export's live rows for this title read {!r}".format(status, sorted(statuses)))
    for claimed in (listing.get("positionStatusCounts") or {}):
        if str(claimed) not in PLUM_CURRENT_LIVE_STATUSES or str(claimed) not in statuses:
            say("counts a position status {!r} the export's live rows do not carry".format(claimed))
    plan = listing.get("payPlan")
    if plan is not None and str(plan) not in {r["Pay Plan"] for r in live}:
        say("publishes pay plan {!r}; no live row of this title carries it".format(plan))
    appointment = listing.get("appointmentType")
    if appointment is not None and str(appointment) not in {r["Appointment Type"] for r in live}:
        say("publishes appointment type {!r}; no live row of this title carries it".format(appointment))
    cells = {r["Level, Grade, or Pay"] for r in live}
    pay_level = listing.get("payLevel")
    if pay_level is not None and (not isinstance(pay_level, str) or "$" in pay_level or pay_level not in cells):
        say("publishes {!r} as a pay level; the export's cell(s) for this title read {!r}".format(pay_level, sorted(cells)))
    reported = listing.get("reportedPay")
    text = listing.get("reportedPayText")
    if reported is not None:
        if isinstance(reported, bool) or not isinstance(reported, (int, float)) or reported <= 0:
            say("publishes {!r} as a reported rate of pay".format(reported))
        elif str(text or "") not in cells:
            say("reports pay as {!r}, which no live row of this title prints".format(text))
        else:
            digits = re.sub(r"[^0-9]", "", str(text).split(".")[0])
            if not digits or abs(float(digits) - float(reported)) > 0.005:
                say("publishes {!r} as the rate but the row prints {!r}".format(reported, text))
        if pay_level is not None:
            say("publishes both a rate and a level for one listing")
    elif text is not None:
        # The one text a listing may carry with no figure is a printed zero:
        # the export's cell is quoted, and zero is never published as a rate.
        if not re.fullmatch(r"\$\s*0(?:,0+)*(?:\.0+)?", str(text)):
            say("carries reported-pay text {!r} with no figure".format(text))
        elif str(text) not in cells:
            say("quotes a zero rate {!r} that no live row of this title prints".format(text))
    return out


def current_pay_violations(node, pay, listing, today, label):
    """Everything that must be true of the rate the current PLUM export
    prints for the one row under a title: a post standing for one post, the
    very figure and text the node's current listing reports and a live row of
    the committed file prints, a proxy graded partial, never zero, never a
    cost, and dated by the fetch."""
    out = []
    say = lambda text: out.append("{} {}".format(label(node), text))
    if not isinstance(pay, dict):
        say("positionCurrentPay {!r} is not a record".format(pay))
        return out
    if not is_post(node):
        say("carries a rate of basic pay from the current PLUM export but is a {!r}, not a post".format(node.get("type")))
    if node.get("representsPosts"):
        say("carries one listing's rate but stands for several posts")
    amount = pay.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount <= 0:
        say("publishes {!r} as a rate of basic pay; zero or a non-number is never a rate".format(amount))
        amount = None
    text = str(pay.get("rateText") or "")
    if not re.fullmatch(r"\$[0-9][0-9,]*(?:\.\d{2})?", text):
        say("prints the rate as {!r}, which is not a dollar figure the export prints".format(text))
    elif amount is not None and abs(float(re.sub(r"[^0-9]", "", text.split(".")[0])) - float(amount)) > 0.005:
        say("prints the rate as {!r} but publishes {!r}".format(text, amount))
    if not isinstance(listing, dict):
        say("claims a rate from the current PLUM export with no current listing beneath it")
    else:
        if listing.get("reportedPay") != amount or str(listing.get("reportedPayText") or "") != text:
            say("publishes a rate its current listing does not report ({!r} against {!r})".format(text, listing.get("reportedPayText")))
        for field in ("listedTitle", "agency", "organization"):
            if str(pay.get(field) or "") != str(listing.get(field) or ""):
                say("names {} {!r} while its listing names {!r}".format(field, pay.get(field), listing.get(field)))
        if str(pay.get("documentSha256") or "").lower() != str(listing.get("documentSha256") or "").lower():
            say("cites a different digest from its listing")
    if str(pay.get("scopeMatch") or "") != "proxy" or str(pay.get("financialEvidenceStatus") or "") != "partial":
        say("claims more than a proxy graded partial; a row of the export is one listing's figure")
    if str(pay.get("costBasis") or "") != "basic_pay":
        say("files the rate under {!r}, not basic_pay".format(pay.get("costBasis")))
    if str(pay.get("unitsEvidenceKind") or "") != PLUM_CURRENT_PAY_UNITS_KIND:
        say("rests its scale on {!r}; the export states it by printing the figure with its mark".format(pay.get("unitsEvidenceKind")))
    if text and text not in str(pay.get("quote") or ""):
        say("quotes a row that does not print the rate it publishes")
    export = plum_current_export()
    if export is None:
        say("claims a rate from the current PLUM export but the committed export cannot be read or does not match its recorded digest")
    else:
        if str(pay.get("documentSha256") or "").lower() != export["sha256"]:
            say("names a document digest that is not the committed export's")
        entry = export["index"].get(tuple(str(pay.get(k) or "") for k in ("agency", "organization", "listedTitle")))
        if not entry or text not in {r["Level, Grade, or Pay"] for r in entry["live"]}:
            say("publishes {!r}, which no Filled or Vacant row of this title prints".format(text))
    checked = str(pay.get("checkedAt") or "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}", checked) or checked[:10] > today:
        say("claims a current-export rate without a past retrieval date ({!r})".format(checked))
    if not host_of(str(pay.get("url") or "")).endswith((".gov", ".mil")):
        say("claims a current-export rate with no .gov/.mil document behind it")
    if str(node.get("cost_status") or "") in ("official", "root_total", "scaled_official"):
        say("carries a rate of basic pay and a measured cost status {!r}".format(node.get("cost_status")))
    if str(node.get("costVerificationStatus") or "") == "verified":
        say("carries a rate of basic pay and a verified cost")
    return out


def reported_pay_violations(node, pay, today, label):
    """Everything that must be true of a reported-pay claim.

    A different shape from `statutory_pay_violations`, and deliberately not
    folded into it. A statutory rate attaches to the office and survives a
    change of holder; this is one listed person's pay on one date, so the
    checks are about the roster row: the figure the report prints for *this*
    node's title, a status and pay basis the report actually uses, a positive
    amount, and a title that still folds onto the node's current name.
    """
    out = []
    say = lambda text: out.append("{} {}".format(label(node), text))
    if not isinstance(pay, dict):
        say("positionReportedPay {!r} is not a record".format(pay))
        return out

    type_text = str(node.get("type") or "").casefold()
    if not any(word in type_text for word in ("position", "role", "office holder")):
        say("carries a reported rate of basic pay but is a {!r}, not a post".format(node.get("type")))
    out.extend(holders_violations(node, pay, "positionReportedPay", label))

    source = str(pay.get("source") or "")
    if source != "whitehouse_staff_report":
        say("prices from source {!r}, which this pipeline does not produce".format(source))
        return out

    node_id = str(node.get("id") or "")
    if not node_id.startswith("exec-eop-who-"):
        say("prices from the White House Office roster but sits outside that office")

    roster = whitehouse_roster()
    if not roster:
        say("prices from a roster this gate could not read or whose digest did not match")
        return out
    reported_title = str(pay.get("reportedTitle") or "")
    entry = roster.get(whitehouse_canonical(reported_title))
    if entry is None:
        say("reports title {!r}, which the committed report does not print".format(reported_title))
        return out
    expected_amount, held_by, distinct_amounts, row_statuses, row_bases = entry
    expected_title = reported_title
    holders = pay.get("holders") if isinstance(pay.get("holders"), dict) else None
    # A title several people hold prices a node only when the report lists
    # every one of them at the SAME rate and the block says so: then "each of
    # the N is paid $X" is what the roster states. Differing rates decide
    # nothing, and a uniform claim must count exactly the people listed.
    if held_by != 1:
        if holders is None or holders.get("uniformRate") is not True:
            say("prices a title the report lists {} people under".format(held_by))
        else:
            if distinct_amounts != 1:
                say("claims every one of the {} people under this title is paid the same; the report prints {} different rates".format(held_by, distinct_amounts))
            if len(row_statuses) != 1 or len(row_bases) != 1:
                say("claims every one of the {} people under this title is on the same terms; the report prints {} status(es) and {} pay basis(es)".format(
                    held_by, len(row_statuses), len(row_bases)))
            if isinstance(holders.get("count"), bool) or not isinstance(holders.get("count"), int):
                say("claims {!r} holders, which is not a whole number".format(holders.get("count")))
            elif holders.get("count") != held_by:
                say("claims {!r} holders; the report lists {}".format(holders.get("count"), held_by))
    elif holders is not None and holders.get("uniformRate") is True:
        say("claims a uniform rate across several holders for a title the report lists once")
    # The method string is published, and it says whose figure this is: one
    # listed person's, or each of the N listed people's. It must match the
    # block's own `holders` claim, mirrored from whitehouse_pay.PAY_METHOD and
    # PAY_METHOD_UNIFORM.
    uniform_block = holders is not None and holders.get("uniformRate") is True
    wanted_method = WHITEHOUSE_PAY_METHOD_UNIFORM if uniform_block else WHITEHOUSE_PAY_METHOD
    if str(pay.get("method") or "") != wanted_method:
        say("publishes method {!r} on a block whose holders claim calls for {!r}".format(pay.get("method"), wanted_method))
    # The quote's own "listed N times" suffix is a claim too, and it survives
    # a `holders` block being stripped: N must be the number of people the
    # report lists under the printed title, and a title listed once carries
    # no such suffix at all.
    listed = re.search(r"\u2014 listed (\d+) times, each at ", str(pay.get("quote") or ""))
    if listed and (int(listed.group(1)) != held_by or held_by == 1):
        say("quotes the title as listed {} times; the report lists {} people under it".format(
            listed.group(1), held_by))
    if held_by != 1 and holders is not None and holders.get("uniformRate") is True and not listed:
        say("claims a uniform rate across {} holders without quoting the roster's count".format(held_by))
    # The fold is what licensed the match in the first place, so the gate
    # re-derives it rather than trusting that it was applied: a title that no
    # longer folds onto this node's name is evidence for a different post.
    # Either spelling: the curated nodes are named for the function alone
    # ("Chief of Staff") and the nodes expanded from this same report are
    # named as it prints them ("Assistant to the President and Chief of
    # Staff"). Equality first, then the fold.
    node_name = str(node.get("name") or "")
    accepted_names = {whitehouse_canonical(node_name)}
    stated = WHITEHOUSE_MULTIPLICITY_SUFFIX.search(node_name)
    if stated and holders is not None and holders.get("count") == int(stated.group(1)):
        # "<title> (×N)" is how the expanded subtree names a title N people
        # hold; the suffix is the graph's, and is set aside only when it
        # counts exactly what the block claims.
        accepted_names.add(whitehouse_canonical(WHITEHOUSE_MULTIPLICITY_SUFFIX.sub("", node_name)))
    if not accepted_names & {whitehouse_canonical(reported_title), whitehouse_title_core(reported_title)}:
        say("reports a title that does not name this node, with or without its rank prefix")

    amount = pay.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        say("publishes {!r} as a reported rate of basic pay".format(amount))
    elif float(amount) <= 0:
        # Ten rows of the report read $0.00. Zero is never published here.
        say("publishes {!r}, and a rate of zero is never published as pay".format(amount))
    elif abs(float(amount) - expected_amount) > 0.005:
        say("publishes {:,.2f}; the report prints {:,.2f} for {!r}".format(
            float(amount), expected_amount, expected_title))

    rate_text = str(pay.get("rateText") or "")
    if rate_text != "${:,.2f}".format(expected_amount):
        say("prints the rate as {!r}; the report prints {!r}".format(
            rate_text, "${:,.2f}".format(expected_amount)))
    quote = str(pay.get("quote") or "")
    if rate_text and rate_text not in quote:
        say("quotes text that does not contain the figure it prices")
    if expected_title and expected_title not in quote:
        say("quotes text that does not contain the title it prices")

    status = str(pay.get("reportedStatus") or "")
    if status not in WHITEHOUSE_REPORT_STATUSES:
        say("reports status {!r}, which the report does not use".format(status))
    elif status not in row_statuses:
        # The status is published, so it is checked against the rows for THIS
        # title and not only against the report's vocabulary: an EMPLOYEE
        # title relabelled DETAILEE passed every other check.
        say("reports status {!r}; the report prints {} for this title".format(status, sorted(row_statuses)))
    basis = str(pay.get("payBasis") or "")
    if basis != WHITEHOUSE_REPORT_PAY_BASIS:
        say("reports pay basis {!r}, not {!r}".format(basis, WHITEHOUSE_REPORT_PAY_BASIS))
    elif basis not in row_bases:
        say("reports pay basis {!r}; the report prints {} for this title".format(basis, sorted(row_bases)))

    if str(pay.get("asOf") or "") != WHITEHOUSE_REPORT_AS_OF_TEXT:
        say("dates the roster {!r}, not {!r}".format(pay.get("asOf"), WHITEHOUSE_REPORT_AS_OF_TEXT))
    checked = str(pay.get("checkedAt") or "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}", checked) or checked[:10] > today:
        say("claims a reported rate without a past retrieval date ({!r})".format(checked))
    if WHITEHOUSE_REPORT_AS_OF > today:
        say("cites a roster dated in the future")

    url = str(pay.get("url") or "")
    if url != WHITEHOUSE_REPORT_URL:
        say("cites {!r}, not the report this pipeline reads".format(url))
    if not host_of(url).endswith((".gov", ".mil")):
        say("claims a reported rate with no .gov/.mil document behind it")

    if str(node.get("cost_status") or "") in ("official", "root_total", "scaled_official"):
        say("carries a reported rate and a measured cost status {!r}".format(node.get("cost_status")))
    if str(node.get("costVerificationStatus") or "") == "verified":
        say("carries a reported rate and claims a verified cost")
    method = str(pay.get("method") or "")
    if method and str(node.get("verificationMethod") or "") == method:
        say("verifies its own existence with a payroll roster")
    if method and str(node.get("placementMethod") or "") == method:
        say("places itself with a payroll roster")
    if url and url in [str(u) for u in (node.get("sourceUrls") or [])]:
        say("cites the payroll roster among the sources that it exists")
    # The report's NAME column must never reach the graph. The module drops it
    # at parse time; this is the artefact-side check that it stayed dropped.
    # The report prints names as "LAST, FIRST M." with the surname in capitals,
    # which is what this looks for — a looser "Word, Word" test matches the
    # report's own as-of text ("Wednesday, July 1, 2026") and fails every
    # honest record. The three fields that legitimately carry the report's
    # upper-case title text are exempt.
    for field, value in pay.items():
        if field in ("quote", "amountScope", "reportedTitle"):
            continue
        if isinstance(value, str) and re.search(r"\b[A-Z][A-Z.'\-]{1,}, +[A-Z][A-Z.'\-]*\b", value):
            say("carries {!r}, which looks like a person's name from the roster".format(field))
    return out


def reviewed_schedule_violations(node, pay, reviewed, today, label):
    """A reviewed row is a claim about WHICH office a node is, and it needs
    the second statute behind it: the sentence must be the row's, must be in
    the committed section's operative text now, the file must still be the
    bytes the fetch recorded, and the node must still carry the name the row
    was written against. A rename withdraws it, as it does everywhere else."""
    out = []
    say = lambda text: out.append("{} {}".format(label(node), text))
    node_name, title, level, section, citation, fixture, quote, basis, class_title = reviewed
    if str(pay.get("method") or "") != US_CODE_REVIEWED_METHOD:
        say("prices a reviewed identification under method {!r}, not {!r}".format(
            pay.get("method"), US_CODE_REVIEWED_METHOD))
    # A bench priced from the Code's class title says so on the block, and
    # only such a row may: the mark is what keeps the block on a multi-post
    # node, so an unmirrored mark would price a bench from a singular title.
    if class_title:
        if pay.get("classTitle") is not True:
            say("is priced from the class title {!r} without saying so (classTitle)".format(title))
        if not title.startswith(US_CODE_CLASS_TITLE_PREFIX):
            say("claims a class-title identification from {!r}, which is not a class title".format(title))
        if not node.get("representsPosts"):
            say("is priced from a class title as a bench but stands for one post")
    elif "classTitle" in pay:
        say("carries a classTitle mark on a reviewed row that prices one office")
    identification = pay.get("identification")
    if not isinstance(identification, dict):
        say("carries a level a reviewed identification assigned it and no identification block")
        return out
    if canonical_key(node.get("name")) != canonical_key(node_name):
        say("is now called {!r}, not {!r}, the name its reviewed identification was written against".format(
            node.get("name"), node_name))
    if str(identification.get("nodeName") or "") != node_name:
        say("records its identification against {!r}, not {!r}".format(identification.get("nodeName"), node_name))
    if str(identification.get("basisCitation") or "") != citation:
        say("cites {!r} as the basis of its identification; the row's basis is {!r}".format(
            identification.get("basisCitation"), citation))
    if str(identification.get("basisQuote") or "") != quote:
        say("quotes a basis sentence that is not the one {} prints for this row".format(citation))
    if not str(identification.get("basis") or "").strip():
        say("carries a reviewed identification with no stated basis")
    elif str(identification.get("basis")) != basis:
        say("states a basis for its identification that is not the reviewed row's")
    path = US_CODE_BASIS_FIXTURE_DIR / fixture
    digest = fixture_digest(path)
    if digest is None:
        say("cites basis section {!r}, which is not committed".format(fixture))
    elif str(identification.get("basisSha256") or "").lower() != digest:
        say("names a basis digest that is not the committed section's")
    operative = uscode_operative_text(path)
    if not operative:
        say("cites a basis section whose operative text this gate cannot separate from its notes")
    elif quote not in operative:
        say("rests on a sentence {} does not print in its operative text (only in the publisher's notes, or not at all)".format(citation))
    basis_url = str(identification.get("basisUrl") or "")
    # A section number may carry a letter and a dashed suffix (42 U.S.C.
    # 2000e-4, 2 U.S.C. 136a-2); the granule id prints both.
    parts = re.match(r"^(\d+) U\.S\.C\. (\d+[A-Za-z]?(?:-\d+)?)$", citation)
    expected_granule = "title{}-section{}".format(parts.group(1), parts.group(2)) if parts else ""
    if host_of(basis_url) != US_CODE_HOST or not expected_granule or expected_granule not in basis_url:
        say("does not link the section its identification rests on ({!r})".format(basis_url))
    checked = str(identification.get("basisCheckedAt") or "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}", checked) or checked[:10] > today:
        say("claims a reviewed identification without a past retrieval date ({!r})".format(checked))
    if pay.get("scopedOffice") or pay.get("scopedOrganisationId") or pay.get("scopedOrganisation"):
        say("claims a scope; a reviewed identification names the whole node and needs none")
    return out



def counted_class_member_name_reason(name, singular, department_words):
    """Mirror of `statutory_schedule.counted_class_member_name_reason`, stdlib
    only: the singular office first and whole, then a closed separator, and a
    name that says "of <department>" must name the class's own."""
    text = str(name or "")
    if US_CODE_STATED_MULTIPLICITY.search(text):
        return "names a bench, not one post"
    if "(" in text:
        return "carries a parenthetical qualifier"
    if not text.startswith(singular):
        return "does not begin with the class's singular office"
    rest = text[len(singular):]
    if not rest:
        return None
    separator = next((sep for sep in US_CODE_COUNTED_CLASS_SEPARATORS if rest.startswith(sep)), None)
    if separator is None:
        return "does not separate the office from its qualifier"
    if separator in (" of ", " of the "):
        after = rest[len(separator):]
        for word in department_words:
            if after == word or any(after.startswith(word + sep) for sep in US_CODE_COUNTED_CLASS_SEPARATORS):
                return None
        return "names a department that is not the class's own"
    return None


def counted_class_schedule_violations(node, pay, spec, today, label, tree_parents):
    """A member of a counted class: the Code places N offices at one level and
    names none, so everything that ties THIS node to the class is checked here
    -- the class is mirrored, the node id is a reviewed member, the name is the
    singular office, the node sits inside the class's organisation on the tree
    the gate is walking, no listing on it says otherwise, the class title with
    its count is what the section prints, and the composing statute, where
    there is one, still prints the sentence quoted. The count itself is
    checked across the whole graph after the walk."""
    out = []
    say = lambda text: out.append("{} {}".format(label(node), text))
    node_id = str(node.get("id") or "")
    counted = pay.get("countedClass")
    if not isinstance(counted, dict):
        say("prices under the counted-class method with no countedClass block")
        return out
    code_title = str(counted.get("codeTitle") or "")
    if spec is None:
        say("claims membership of counted class {!r}, which this pipeline has no table for".format(code_title))
        return out
    if str(pay.get("method") or "") != US_CODE_COUNTED_METHOD:
        say("prices a counted-class membership under method {!r}, not {!r}".format(pay.get("method"), US_CODE_COUNTED_METHOD))
    if node_id not in spec["members"]:
        say("is priced as a member of {!r}, a class the reviewed table does not list it in".format(code_title))
    if node.get("representsPosts"):
        say("is priced as one office of a counted class but stands for several posts")
    if "classTitle" in pay:
        say("carries a classTitle mark on a counted-class membership")
    if pay.get("scopedOffice") or pay.get("scopedOrganisationId") or pay.get("scopedOrganisation"):
        say("claims a scope; a counted-class membership names the whole node and needs none")
    why = counted_class_member_name_reason(node.get("name"), spec["singular"], tuple(spec["departmentWords"]))
    if why:
        say("is now called {!r}, which {} ({!r})".format(node.get("name"), why, spec["singular"]))
    # Placement, off the tree the gate is walking.
    seen = []
    current = tree_parents.get(node_id) if isinstance(tree_parents, dict) else None
    while current and current not in seen:
        seen.append(current)
        current = tree_parents.get(current)
    if spec["scopeId"] not in seen:
        say("sits outside {!r}, the organisation whose counted class it is priced from".format(spec["scopeId"]))
    if str(counted.get("scopeId") or "") != spec["scopeId"]:
        say("names {!r} as its class's organisation; the table says {!r}".format(counted.get("scopeId"), spec["scopeId"]))
    if str(counted.get("singular") or "") != spec["singular"]:
        say("names {!r} as its class's singular office; the table says {!r}".format(counted.get("singular"), spec["singular"]))
    # The class title, with its count, as the section prints it.
    section = spec["section"]
    printed = uscode_operative_text(US_CODE_BASIS_FIXTURE_DIR / "exec_schedule_{}.html".format(section))
    if not printed or code_title not in printed:
        say("is priced from {!r}, which §{} does not print in its operative text".format(code_title, section))
    found = re.search(r"\((\d+)\)", code_title)
    if not found:
        say("is priced from {!r}, which states no count".format(code_title))
    elif counted.get("statedPosts") != int(found.group(1)):
        say("says the Code counts {!r} offices; the title states {}".format(counted.get("statedPosts"), found.group(1)))
    members = counted.get("membersInGraph")
    if isinstance(members, bool) or not isinstance(members, int) or members < 1 or (found and members > int(found.group(1))):
        say("says this graph names {!r} members of the class; the Code counts {}".format(members, found.group(1) if found else "?"))
    # A listing on the node that says another pay plan or level wins.
    for field, level_key in (("positionListing", "payLevel"), ("positionCurrentListing", "level")):
        listing = node.get(field)
        if isinstance(listing, dict):
            plan = str(listing.get("payPlan") or "").strip().upper()
            listed = str(listing.get(level_key) or "").strip().upper()
            if plan and plan != "EX":
                say("is priced as one of {!r} while its {} reports pay plan {}".format(code_title, field, plan))
            if listed and listed != US_CODE_SECTIONS_LEVELS.get(section):
                say("is priced as one of {!r} while its {} reports Level {}".format(code_title, field, listed))
    # The composing statute, where the table has one; none where it has none.
    identification = pay.get("identification")
    if not isinstance(identification, dict):
        say("carries a counted-class membership with no identification block")
        return out
    if str(identification.get("basis") or "") != spec["basis"]:
        say("states a basis for its class membership that is not the reviewed table's")
    named_as = spec["members"].get(node_id)
    if (counted.get("namedAs") or None) != named_as:
        say("quotes {!r} as the sentence naming this office; the table records {!r}".format(counted.get("namedAs"), named_as))
    composition = spec["composition"]
    if composition is None:
        if identification.get("basisUrl") or identification.get("basisCitation") or identification.get("basisQuote"):
            say("cites a composing statute for a class the table records none for")
        return out
    citation, fixture, quote = composition
    if str(identification.get("basisCitation") or "") != citation:
        say("cites {!r} as composing its class; the table says {!r}".format(identification.get("basisCitation"), citation))
    if str(identification.get("basisQuote") or "") != quote:
        say("quotes a composing sentence that is not the one {} prints for this class".format(citation))
    path = US_CODE_BASIS_FIXTURE_DIR / fixture
    digest = fixture_digest(path)
    if digest is None:
        say("cites composing section {!r}, which is not committed".format(fixture))
    elif str(identification.get("basisSha256") or "").lower() != digest:
        say("names a composing-section digest that is not the committed section's")
    operative = uscode_operative_text(path)
    if not operative:
        say("cites a composing section whose operative text this gate cannot separate from its notes")
    else:
        if quote not in operative:
            say("rests on a composing sentence {} does not print in its operative text".format(citation))
        if named_as and named_as not in operative:
            say("rests on a naming sentence {} does not print in its operative text".format(citation))
    basis_url = str(identification.get("basisUrl") or "")
    parts = re.match(r"^(\d+) U\.S\.C\. (\d+[A-Za-z]?(?:-\d+)?)$", citation)
    expected_granule = "title{}-section{}".format(parts.group(1), parts.group(2)) if parts else ""
    if host_of(basis_url) != US_CODE_HOST or not expected_granule or expected_granule not in basis_url:
        say("does not link the section its class membership rests on ({!r})".format(basis_url))
    checked = str(identification.get("basisCheckedAt") or "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}", checked) or checked[:10] > today:
        say("claims a counted-class membership without a past retrieval date ({!r})".format(checked))
    return out

def schedule_pay_violations(node, pay, today, label, tree_parent=None, tree_parents=None):
    """A rate whose LEVEL is current law and whose FIGURE is OPM's table.

    A different claim from `positionPayRate`, which reads the level off the
    previous administration's PLUM archive, so a different field and a
    different checker. The two overlap in what they must not do -- neither is
    a cost, neither is evidence the post exists -- and differ in what backs
    the level: an archive edition there, a section of the United States Code
    here, which is why this one requires no `positionListing` and that one
    cannot be published without it.
    """
    out = []
    say = lambda text: out.append("{} {}".format(label(node), text))
    if not isinstance(pay, dict):
        say("positionSchedulePay {!r} is not a record".format(pay))
        return out

    node_id = str(node.get("id") or "")
    type_text = str(node.get("type") or "").casefold()
    if not any(word in type_text for word in ("position", "role", "office holder")):
        say("carries a statutory rate of basic pay but is a {!r}, not a post".format(node.get("type")))
    out.extend(holders_violations(node, pay, "positionSchedulePay", label))

    # Which post the Code actually names. Without this the figure is right and
    # the office is anybody's.
    expected = US_CODE_EXECUTIVE_SCHEDULE.get(node_id)
    reviewed = US_CODE_REVIEWED_IDENTIFICATIONS.get(node_id)
    counted_spec = None
    if isinstance(pay.get("countedClass"), dict) or str(pay.get("method") or "") == US_CODE_COUNTED_METHOD:
        # The fourth route: one office of a counted class. Its own checker
        # says whether the node is still a member; the rate half below is the
        # same table and the same rules as every other schedule record.
        counted_spec = US_CODE_COUNTED_CLASSES.get(str((pay.get("countedClass") or {}).get("codeTitle") or ""))
        out.extend(counted_class_schedule_violations(node, pay, counted_spec, today, label, tree_parents or {}))
        if counted_spec is None:
            return out
        expected = (str(pay["countedClass"].get("codeTitle") or ""), US_CODE_SECTIONS_LEVELS[counted_spec["section"]],
                    counted_spec["section"], None)
    elif reviewed is not None:
        # The third route: the row says which office the node is, and the
        # checker says whether the second statute still backs that.
        out.extend(reviewed_schedule_violations(node, pay, reviewed, today, label))
        expected = (reviewed[1], reviewed[2], reviewed[3], None)
    elif isinstance(pay.get("identification"), dict) or str(pay.get("method") or "") == US_CODE_REVIEWED_METHOD:
        say("claims a reviewed identification this pipeline has no row for")
    if reviewed is None and counted_spec is None and "classTitle" in pay:
        say("carries a classTitle mark outside a reviewed identification")
    if expected is None:
        say("carries a rate from the Executive Schedule; the Code names no such post for this node")
        return out
    title, level, section, scoped_org = expected
    if reviewed is None and counted_spec is None:
        # Each route publishes its own method string, and the panel prints a
        # different sentence for each; a scoped record wearing the whole-name
        # method would claim the Code names the node outright.
        wanted = US_CODE_SCHEDULE_SCOPED_METHOD if scoped_org is not None else US_CODE_SCHEDULE_METHOD
        if str(pay.get("method") or "") != wanted:
            say("prices under method {!r}, not {!r}".format(pay.get("method"), wanted))
    if str(pay.get("statutoryTitle") or "") != title:
        say("quotes the Code as naming {!r}; §{} prints {!r}".format(pay.get("statutoryTitle"), section, title))
    # The node must still BE the office the statute named. A rename in the
    # curated file cannot inherit a level looked up for a different post --
    # the same rename guard every evidence module here applies. Two routes,
    # two guards: a whole-name match must still equal the statutory title; a
    # scoped one must still carry the office half AND still sit under the body
    # the statute named, because that placement is half of what identified it.
    if scoped_org is None:
        # A reviewed row's rename guard is the row's own node name, checked
        # above; its whole name is by construction NOT the statutory title.
        if reviewed is None and counted_spec is None and canonical_key(node.get("name")) != canonical_key(title):
            say("is now called {!r}, which is not the statutory title {!r} its rate was looked up from".format(
                node.get("name"), title))
        if pay.get("scopedOffice") or pay.get("scopedOrganisationId"):
            say("claims a scope the Code did not need: its whole name is the statutory title")
    else:
        office = str(pay.get("scopedOffice") or "")
        if not office or canonical_key(node.get("name")) != canonical_key(office):
            say("is now called {!r}, which is not the office {!r} the Code names inside {!r}".format(
                node.get("name"), office, title))
        if str(pay.get("scopedOrganisationId") or "") != scoped_org:
            say("was priced as this office inside {!r}; it now claims {!r}".format(
                scoped_org, pay.get("scopedOrganisationId")))
        # Read off the tree the gate is walking, not off `parentId`: that
        # field is stamped on the exported node list only, so a check against
        # it would pass vacuously for most of the graph.
        parent_id = str(tree_parent or node.get("parentId") or "")
        if parent_id != scoped_org:
            say("sits under {!r}, not {!r}, which is half of what identified it".format(
                parent_id or "nothing", scoped_org))
        if canonical_key(office) not in canonical_key(title):
            say("names office {!r}, which is not part of the statutory title {!r}".format(office, title))
    if str(pay.get("payLevel") or "") != level:
        say("prices level {!r}; §{} places this post at level {!r}".format(pay.get("payLevel"), section, level))
    citation = str(pay.get("citation") or "")
    if citation != "5 U.S.C. \u00a7{}".format(section):
        say("cites {!r}; the section that names this post is §{}".format(citation, section))
    statute_url = str(pay.get("statuteUrl") or "")
    if host_of(statute_url) != US_CODE_HOST or "section{}".format(section) not in statute_url:
        say("does not link the section of the Code that names it ({!r})".format(statute_url))
    statute_checked = str(pay.get("statuteCheckedAt") or "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}", statute_checked) or statute_checked[:10] > today:
        say("claims a statutory level without a past retrieval date ({!r})".format(statute_checked))

    # The rate half: the same table, the same mirror, the same rules as
    # table_pay_violations, because it is literally the same document.
    amount = pay.get("amount")
    rate = EXECUTIVE_SCHEDULE_RATES.get(level)
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        say("publishes {!r} as a statutory rate of basic pay".format(amount))
    elif rate is not None and abs(float(amount) - rate) > 0.005:
        say("publishes {:,.2f} for level {}, which the table pays {:,.2f}".format(float(amount), level, rate))
    if rate is not None:
        printed = "${:,.0f}".format(rate)
        if str(pay.get("rateText") or "") != printed:
            say("prints the rate as {!r}; the table prints {!r}".format(pay.get("rateText"), printed))
        scope = str(pay.get("amountScope") or "")
        if scope.casefold() != "level {}".format(level).casefold():
            say("prints the rate as being for {!r} while pricing level {!r}".format(scope, level))
    if str(pay.get("table") or "") != EXECUTIVE_SCHEDULE_TABLE:
        say("cites table {!r}, not {!r}".format(pay.get("table"), EXECUTIVE_SCHEDULE_TABLE))
    if str(pay.get("effective") or "") != EXECUTIVE_SCHEDULE_EFFECTIVE:
        say("dates the table {!r}, not {!r}".format(pay.get("effective"), EXECUTIVE_SCHEDULE_EFFECTIVE))
    if str(pay.get("effectiveText") or "") != EXECUTIVE_SCHEDULE_EFFECTIVE_TEXT:
        say("prints the effective heading as {!r}; the page prints {!r}".format(
            pay.get("effectiveText"), EXECUTIVE_SCHEDULE_EFFECTIVE_TEXT))
    checked = str(pay.get("checkedAt") or "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}", checked) or checked[:10] > today:
        say("claims a table rate without a past retrieval date ({!r})".format(checked))
    if not host_of(str(pay.get("url") or "")).endswith((".gov", ".mil")):
        say("claims a table rate with no .gov/.mil document behind it")
    footnotes = pay.get("footnotes")
    if not isinstance(footnotes, list) or not any(str(f).strip() for f in footnotes):
        say("carries a statutory rate without the notes the table prints beside it")
    elif tuple(str(f).strip() for f in footnotes) != EXECUTIVE_SCHEDULE_FOOTNOTES:
        say("quotes notes the table does not carry")

    # It is not a cost, and it is not evidence that the post exists. The same
    # two refusals table_pay_violations makes, and for the same reason: the
    # 2026-09-11 failure in which a five-row table carried 29 positions to
    # `verified` went through exactly these fields.
    if str(node.get("cost_status") or "") in ("official", "root_total", "scaled_official"):
        say("carries a statutory rate and a measured cost status {!r}".format(node.get("cost_status")))
    if str(node.get("costVerificationStatus") or "") == "verified":
        say("carries a statutory rate and claims a verified cost")
    basis = str(node.get("cost_basis") or "")
    if basis and basis not in KNOWN_COST_BASES:
        say("carries a statutory rate and an unknown cost basis {!r}".format(basis))
    method = str(pay.get("method") or "")
    if method and str(node.get("verificationMethod") or "") == method:
        say("verifies its own existence with a statute that prices a rank")
    if method and str(node.get("placementMethod") or "") == method:
        say("places itself with a statute that prices a rank")
    if str(pay.get("scopeMatch") or "") != "proxy":
        say("claims scope {!r}; the table names a rank, not this post".format(pay.get("scopeMatch")))
    if str(pay.get("financialEvidenceStatus") or "") != "partial":
        say("grades itself {!r}; a rank priced for a post is partial".format(pay.get("financialEvidenceStatus")))
    if str(pay.get("costBasis") or "") != "basic_pay":
        say("files its figure as {!r} rather than basic_pay".format(pay.get("costBasis")))
    return out


#: The VA's Title 38 PAY TABLE 3, mirrored stdlib-only and pinned equal to
#: what the committed PDF prints by tests/test_va_title38_pay.py. Keyed by the
#: coverage title the table itself carries, because that is what a record
#: claims to have matched.
VA_TITLE38_TABLES = {
    "3": "PAY TABLE 3- CHIEF OF STAFF AND NETWORK CHIEF MEDICAL OFFICERS",
    "4": "PAY TABLE 4 \u0096 EXECUTIVE ASSIGNMENTS",
}
VA_TITLE38_EFFECTIVE = "2026-01-11"
VA_TITLE38_EFFECTIVE_TEXT = "Effective January 11, 2026"
VA_TITLE38_URL = "https://www.va.gov/OHRM/Pay/2026/PDOP/PayTables.pdf"
#: coverage title -> (table, tier, minimum, maximum), for the titles this
#: pipeline prices. Every one is a WHOLE printed item of that tier's coverage
#: list, which tests/test_va_title38_pay.py checks against the committed PDF.
VA_TITLE38_TIERS = {
    "Network Chief Medical Officer": ("3", 1, 220_000.0, 400_000.0),
    "Chief of Staff": ("3", 2, 200_000.0, 400_000.0),
    "Deputy Chief Medical Officer, Deputy Chief of Staff": ("3", 3, 180_000.0, 375_000.0),
    "Network Directors": ("4", 1, 145_000.0, 310_000.0),
    "Medical Center Directors": ("4", 1, 145_000.0, 310_000.0),
}
#: Which curated name may claim which coverage title, and under what parent.
#: A rule rather than a 36-row literal, because both families are
#: one-per-facility and a literal would have to be regenerated whenever the
#: VA opens or closes a medical centre -- but it is still keyed on the node's
#: own name and its own parent, so a record moved to another node is caught.
VA_TITLE38_WHOLE_NAME = {
    "VAMC Chief of Staff (Medical)": ("Chief of Staff", "VA Medical Centers"),
    "VAMC Director": ("Medical Center Directors", "VA Medical Centers"),
}
VA_TITLE38_SCOPED_OFFICE = {
    "Chief Medical Officer": ("Network Chief Medical Officer", "VISN"),
    "Network Director": ("Network Directors", "VISN"),
}
#: The document prints none of these anywhere, and a research pass claimed it
#: printed the first two. A record claiming a band for one of them is the
#: failure this check exists for.
VA_TITLE38_NEVER_PRICED = (
    "VAMC Associate Director (Administrative)",
    "Associate Director for Patient Care Services (CNO)",
)


def tier_pay_violations(node, pay, today, label, parent_name):
    """Everything that must be true of a pay-schedule TIER band.

    A band is a weaker claim than a rate and needs one check a rate does not:
    that it is never rendered, stored or described as a rate. The rest is the
    shape every other pay block gets -- the mirror's own figures for the tier
    claimed, the document's own words in the quote, a past retrieval date, the
    citation this pipeline can produce, and no leak into the node's sources.
    """
    out = []
    say = lambda text: out.append("{} {}".format(label(node), text))
    if not isinstance(pay, dict):
        say("positionTierPay {!r} is not a record".format(pay))
        return out

    type_text = str(node.get("type") or "").casefold()
    if not any(word in type_text for word in ("position", "role", "office holder")):
        say("carries a Title 38 pay band but is a {!r}, not a post".format(node.get("type")))
    out.extend(holders_violations(node, pay, "positionTierPay", label))

    if str(pay.get("source") or "") != "va_title38_pay_ranges":
        say("prices from source {!r}, which this pipeline does not produce for a tier band".format(pay.get("source")))
        return out
    if str(pay.get("kind") or "") != "title_38_tier":
        say("claims band kind {!r}, not 'title_38_tier'".format(pay.get("kind")))

    name = str(node.get("name") or "")
    if name in VA_TITLE38_NEVER_PRICED:
        say("carries a Title 38 band, and the schedule prints no title of this name at all")

    coverage = str(pay.get("coverageTitle") or "")
    rule = str(pay.get("matchRule") or "")
    if rule == "whole_name_under_its_scoped_parent":
        expected = VA_TITLE38_WHOLE_NAME.get(name)
        if expected is None:
            say("claims a whole-name Title 38 match on a name this pipeline does not price")
        else:
            if coverage != expected[0]:
                say("claims coverage {!r}; this name answers to {!r}".format(coverage, expected[0]))
            if str(parent_name or "") != expected[1]:
                say("is priced under parent {!r}, not {!r}".format(parent_name, expected[1]))
    elif rule == "office_scoped_to_its_own_parent":
        office = name.partition(", ")[0].strip()
        organisation = name.partition(", ")[2].strip()
        expected = VA_TITLE38_SCOPED_OFFICE.get(office)
        if expected is None:
            say("claims a scoped Title 38 match on office {!r}, which this pipeline does not price".format(office))
        elif coverage != expected[0]:
            say("claims coverage {!r}; office {!r} answers to {!r}".format(coverage, office, expected[0]))
        if not organisation or str(parent_name or "").strip() != organisation:
            say("names organisation {!r} that is not the parent the tree gives it ({!r})".format(organisation, parent_name))
    else:
        say("claims match rule {!r}, which this pipeline does not produce".format(rule))

    mirrored = VA_TITLE38_TIERS.get(coverage)
    if mirrored is None:
        say("claims coverage {!r}, which the mirrored tables do not print".format(coverage))
    else:
        table_number, tier, minimum, maximum = mirrored
        if str(pay.get("table") or "") != VA_TITLE38_TABLES[table_number]:
            say("cites table {!r}; {!r} is printed in {!r}".format(
                pay.get("table"), coverage, VA_TITLE38_TABLES[table_number]))
        if pay.get("tier") != tier:
            say("claims tier {!r}; the table prints {!r} at tier {}".format(pay.get("tier"), coverage, tier))
        for key, expected_value in (("minimum", minimum), ("maximum", maximum)):
            value = pay.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                say("publishes {!r} as the band's {}".format(value, key))
            elif abs(float(value) - expected_value) > 0.005:
                say("publishes {:,.2f} as the {} for {!r}; the table prints {:,.2f}".format(
                    float(value), key, coverage, expected_value))
        printed = "${:,.0f} – ${:,.0f}".format(minimum, maximum)
        if str(pay.get("rangeText") or "") != printed:
            say("prints the band as {!r}; the table prints {!r}".format(pay.get("rangeText"), printed))

    quote = str(pay.get("quote") or "")
    if not any(label in quote for label in VA_TITLE38_TABLES.values()):
        say("prices from the Title 38 schedule without quoting the table it read")
    if VA_TITLE38_EFFECTIVE_TEXT not in quote:
        say("prices a Title 38 band without quoting the effective line the schedule prints")
    if mirrored is not None and coverage not in quote:
        say("prices a coverage title its own quoted row does not name")

    # A band is not a rate, and must never be describable as one.
    for forbidden in ("amount", "rate", "rateText", "salary"):
        if forbidden in pay:
            say("carries {!r} beside a band; a range is never published as a rate".format(forbidden))
    if not str(pay.get("note") or "").strip():
        say("publishes a band with no sentence saying it is a band")

    if str(pay.get("effective") or "") != VA_TITLE38_EFFECTIVE:
        say("dates the band {!r}, not {!r}".format(pay.get("effective"), VA_TITLE38_EFFECTIVE))
    if str(pay.get("scopeMatch") or "") != "proxy":
        say("claims scope {!r}; which node a coverage title names is a reviewed rule, never more than a proxy".format(
            pay.get("scopeMatch")))
    if str(pay.get("financialEvidenceStatus") or "") != "partial":
        say("grades a Title 38 band {!r}, not 'partial'".format(pay.get("financialEvidenceStatus")))

    checked = str(pay.get("checkedAt") or "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}", checked) or checked[:10] > today:
        say("claims a Title 38 band without a past retrieval date ({!r})".format(checked))
    url = str(pay.get("url") or "")
    if url != VA_TITLE38_URL:
        say("cites {!r}, not the schedule this pipeline reads".format(url))

    if str(node.get("cost_status") or "") in ("official", "root_total", "scaled_official"):
        say("carries a Title 38 band and a measured cost status {!r}".format(node.get("cost_status")))
    method = str(pay.get("method") or "")
    if method and str(node.get("verificationMethod") or "") == method:
        say("verifies its own existence with a pay schedule that names no unit")
    if method and str(node.get("placementMethod") or "") == method:
        say("places itself with a pay schedule that names no unit")
    for source_url in node.get("sourceUrls") or []:
        if "va.gov/OHRM" in str(source_url):
            say("counts the pay schedule among the sources that it exists")
    return out


#: Pay fields whose claim is the OFFICE's or the TIER's and holds for every
#: holder alike, so a node standing for several posts may carry one -- with a
#: `holders` block the sweep stamps from the node's own stated multiplicity.
#: Mirrors pay_tables.OFFICE_RATE_PAY_FIELDS; pinned by tests/test_multi_post_pay.py.
OFFICE_RATE_PAY_FIELDS = ("positionStatutoryPay", "positionDerivedPay", "positionTierPay", "positionTierReferencePay")
#: A roster figure may sit on a multi-post node only when the block itself says
#: the roster lists every holder at one rate (mirrors pay_tables.UNIFORM_ROSTER_PAY_FIELDS).
UNIFORM_ROSTER_PAY_FIELDS = ("positionReportedPay",)
#: Never on a multi-post node: one listing's level, one listing's pay plan,
#: one row's rate, one named office's statutory level.
INCUMBENCY_PAY_FIELDS = ("positionPayRate", "positionGradePay", "positionCurrentPay", "positionSchedulePay")
#: The one exception, per record: a schedule block priced from the Code's
#: CLASS title ("Members, ...") is every member's level and stays with
#: `holders` (mirrors pay_tables.CLASS_TITLE_PAY_FIELD; the reviewed mirror
#: above says which rows may carry the mark).
CLASS_TITLE_PAY_FIELD = "positionSchedulePay"
#: A judicial name that bundles senior judges into its count. 28 U.S.C.
#: 371(b)(2) sets an uncertified senior judge's salary by reference to a past
#: year -- the salary last drawn in active service or when last certified,
#: adjusted under §461 -- so the tier's current rate cannot be claimed for
#: each holder.
SENIOR_JUDGE_MARKER = re.compile(r"\bsenior\b", re.IGNORECASE)


def holders_violations(node, pay, field, label):
    """What the multiplicity of a node requires of a pay block on it.

    On a node that stands for several posts, an office-rate block must carry a
    `holders` block that states the SAME multiplicity the node's name does and
    says the figure applies to each holder; a roster block must additionally
    say the roster listed every holder at one rate and count exactly what the
    name counts. On a single-post node no block may carry `holders` at all --
    that is a carry-over from a graph where the node stood for several.
    """
    out = []
    say = lambda text: out.append("{} {}".format(label(node), text))
    represents = node.get("representsPosts")
    holders = pay.get("holders") if isinstance(pay, dict) else None
    if represents:
        if not isinstance(represents, dict):
            # Truthy but not the record annotate_stated_counts writes: still
            # a node that stands for several posts, and nothing about it can
            # be checked, so nothing on it may carry a figure.
            say("stands for several posts ({!r}) in a form this gate cannot read, and carries {}".format(represents, field))
            return out
        if field in INCUMBENCY_PAY_FIELDS and not (
            field == CLASS_TITLE_PAY_FIELD and isinstance(pay, dict) and pay.get("classTitle") is True
        ):
            say("carries {} but stands for several posts; that figure is one listing's".format(field))
            return out
        if not isinstance(holders, dict):
            say("stands for several posts and its {} does not say the figure applies to each holder".format(field))
            return out
        if str(holders.get("text") or "") != str(represents.get("text") or ""):
            say("says its {} covers {!r} holders while its name states {!r}".format(
                field, holders.get("text"), represents.get("text")))
        # The whole record `pay_tables.holders_for` copies, not the text
        # alone: the panel prints `count` first and falls back to the text
        # only when it is absent, so a count of 17 on a name stating ×18
        # reads "stands for 17 posts" past a text-only check. Every key the
        # multiplicity states must be the block's, and none the name does
        # not state may appear.
        if str(holders.get("kind") or "") != str(represents.get("kind") or ""):
            say("files its {} holders as {!r} while its name's count is {!r}".format(
                field, holders.get("kind"), represents.get("kind")))
        for key in ("count", "low", "high", "as_written"):
            stated = represents.get(key)
            if stated is None:
                if key in holders:
                    say("says its {} holders have {} {!r}, which its name does not state".format(
                        field, key, holders.get(key)))
            elif holders.get(key) != stated:
                say("says its {} covers {} {!r} while its name states {!r}".format(
                    field, key, holders.get(key), stated))
        if holders.get("appliesToEachHolder") is not True:
            say("stands for several posts and its {} does not claim the figure for each holder".format(field))
        if field in UNIFORM_ROSTER_PAY_FIELDS:
            if holders.get("uniformRate") is not True:
                say("carries one person's reported pay but stands for several posts")
            if represents.get("kind") != "exact" or holders.get("count") != represents.get("count"):
                say("claims a uniform roster rate for {!r} holders while its name states {!r}".format(
                    holders.get("count"), represents.get("text")))
        if not str(holders.get("note") or "").strip():
            say("stands for several posts and its {} carries no sentence saying so".format(field))
    elif isinstance(holders, dict):
        say("carries a holders block on its {} but stands for one post".format(field))
    return out


def _pay_document_urls(block, keys):
    """The distinct document URLs a pay block carries, in the order its own
    declared keys hold them. Recomputed here rather than trusted, which is the
    point: a published count has to be a fact about the block."""
    seen = []
    for key in keys:
        values = []
        if isinstance(key, str):
            values = [block.get(key)]
        elif len(key) == 2:
            nested = block.get(key[0])
            values = [nested.get(key[1])] if isinstance(nested, dict) else []
        else:
            parent, marker, child = key
            records = block.get(parent) if marker == "*" else None
            if isinstance(records, list):
                values = [r.get(child) for r in records if isinstance(r, dict)]
        for value in values:
            text = str(value or "").strip()
            if text and text not in seen:
                seen.append(text)
    return seen


def pay_document_violations(node, field, block, label):
    """Everything that must be true of a pay block's document count.

    Stamped on every pay field by `pay_documents.annotate_pay_documents`. The
    count and the percentage are recomputed from the block's own URLs, and
    `documentsStatingTheFigure` is the mirror's -- a derived figure's 0 is the
    one thing on this block that makes its 80% readable as what it is.
    """
    out = []
    say = lambda text: out.append("{} {}".format(label(node), text))
    if not isinstance(block, dict):
        return out
    keys = PAY_DOCUMENT_URL_KEYS.get(field)
    if keys is None:
        say("carries pay field {!r}, which this pipeline does not count documents for".format(field))
        return out
    urls = _pay_document_urls(block, keys)
    verification = block.get("verification")
    if not isinstance(verification, dict):
        say("publishes {} with no statement of how many documents verify it".format(field))
        return out
    count = verification.get("documents")
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        say("publishes {!r} as {}'s document count".format(count, field))
        return out
    if count != len(urls):
        say("says {} documents verify its {} and carries {} citable URL(s)".format(count, field, len(urls)))
    expected_percent = DERIVED_PAY_STRENGTH_BY_COUNT.get(count)
    if expected_percent is None:
        say("publishes a document count of {} on {}, which this project's scale does not cover".format(count, field))
    elif verification.get("percent") != expected_percent:
        say("publishes {!r}% for {} documents on {}; this project's own scale gives {!r}%".format(
            verification.get("percent"), count, field, expected_percent))
    expected_stating = PAY_DOCUMENT_STATES_FIGURE[field]
    if verification.get("documentsStatingTheFigure") != expected_stating:
        say("claims {!r} of its {} documents state the figure; {} is {}".format(
            verification.get("documentsStatingTheFigure"), field, field, expected_stating))
    if not str(verification.get("scale") or "").strip():
        say("publishes a {} percentage without saying what scale it is on".format(field))
    if not str(verification.get("caution") or "").strip():
        say("publishes a {} percentage with no sentence saying what it does not measure".format(field))
    roles = verification.get("documentRoles")
    if not isinstance(roles, list) or len(roles) != len(urls):
        say("names {!r} document roles for {} URL(s) on {}".format(
            len(roles) if isinstance(roles, list) else roles, len(urls), field))
    else:
        for role in roles:
            if not isinstance(role, dict) or str(role.get("url") or "") not in urls:
                say("names a {} document role for a URL the block does not carry".format(field))
    return out


# A statute that sets a post's pay BY REFERENCE to an Executive Schedule level
# the post is not itself placed at, joined to OPM's table for the level. The
# derived shape from the other side of the Schedule, mirrored two ways: the
# GAO's two officers by node id, and the Inspector General Act's rate as a
# RULE whose scope is 5 U.S.C. 401(1)'s own list of establishments -- parsed
# here from the committed section with this file's own reader, independently
# of the module, and pinned equal to it by tests/test_tier_reference_pay.py.
# An Inspector General's figure is arithmetic on a printed one ($209,600 plus
# 3 percent), which no document prints; the block carries the arithmetic and
# the gate recomputes it.
TIER_REFERENCE_FIELD = "positionTierReferencePay"
TIER_REFERENCE_SOURCE = "statutory_tier_reference_pay"
TIER_REFERENCE_METHOD = "pay_set_by_reference_to_an_executive_schedule_level_joined_to_opm_table"
TIER_REFERENCE_METHOD_PERCENT = (
    "pay_set_by_reference_to_an_executive_schedule_level_plus_a_statutory_percentage_joined_to_opm_table"
)
TIER_REFERENCE_TABLE_URL = (
    "https://www.opm.gov/policy-data-oversight/pay-leave/salaries-wages/salary-tables/26Tables/exec/html/EX.aspx"
)
#: node id -> (node name the row was written against, office, citation,
#: fixture, level, the sentence 31 U.S.C. 703's operative text prints)
TIER_REFERENCE_ROWS = {
    "leg-support-gao-comptroller-general-of-the-united-states": (
        "Comptroller General of the United States", "Comptroller General", "31 U.S.C. 703(f)(1)",
        "gao_31_usc_703.html", "II",
        "Comptroller General is equal to the rate for level II of the Executive Schedule",
    ),
    "leg-support-gao-deputy-comptroller-general": (
        "Deputy Comptroller General", "Deputy Comptroller General", "31 U.S.C. 703(f)(2)",
        "gao_31_usc_703.html", "III",
        "Deputy Comptroller General is equal to the rate for level III of the Executive Schedule",
    ),
    "leg-support-gpo-director-gpo-public-printer": (
        "Director, GPO (Public Printer)", "Director of the Government Publishing Office", "44 U.S.C. 303",
        "gpo_44_usc_303.html", "II",
        "The annual rate of pay for the Director of the Government Publishing Office shall be a rate "
        "which is equal to the rate for level II of the Executive Schedule",
    ),
    "leg-support-gpo-deputy-director-coo": (
        "Deputy Director / COO", "Deputy Director of the Government Publishing Office", "44 U.S.C. 303",
        "gpo_44_usc_303.html", "III",
        "The annual rate of pay for the Deputy Director of the Government Publishing Office shall be a "
        "rate which is equal to the rate for level III of such Executive Schedule.",
    ),
    "exec-dept-ed-ies-director-ies": (
        "Director, IES", "Director of the Institute of Education Sciences", "20 U.S.C. 9514(c)",
        "ies_20_usc_9514.html", "II",
        "The Director shall receive the rate of basic pay for level II of the Executive Schedule.",
    ),
    "exec-dept-ed-ies-commissioner-national-center-for-education-statistics-nces": (
        "Commissioner — National Center for Education Statistics (NCES)", "Commissioner for Education Statistics",
        "20 U.S.C. 9517(b)(2)", "ies_20_usc_9517.html", "IV",
        "The National Center for Education Statistics shall be headed by a Commissioner for Education "
        "Statistics who shall be appointed by the President and who shall- (1) have substantial knowledge "
        "of programs assisted by the National Center for Education Statistics; (2) receive the rate of "
        "basic pay for level IV of the Executive Schedule;",
    ),
    "exec-dept-ed-ies-commissioner-national-center-for-education-research-ncer": (
        "Commissioner — National Center for Education Research (NCER)",
        "Commissioner of the National Center for Education Research", "20 U.S.C. 9517(a)(2)(A)",
        "ies_20_usc_9517.html", "IV",
        "each Commissioner shall- (A) receive the rate of basic pay for level IV of the Executive Schedule;",
    ),
    "exec-dept-ed-ies-commissioner-national-center-for-education-evaluation-ncee": (
        "Commissioner — National Center for Education Evaluation (NCEE)",
        "Commissioner of the National Center for Education Evaluation and Regional Assistance", "20 U.S.C. 9517(a)(2)(A)",
        "ies_20_usc_9517.html", "IV",
        "each Commissioner shall- (A) receive the rate of basic pay for level IV of the Executive Schedule;",
    ),
    "exec-ind-misc-farm-credit-administration-director-administrator-chair-farm-credit-administration": (
        "Director / Administrator / Chair, Farm Credit Administration", "Chairman of the Farm Credit Administration Board", "12 U.S.C. 2242(d)",
        "fca_12_usc_2242.html", "III",
        "The Chairman of the Board shall receive compensation at the rate prescribed for level III of the Executive Schedule under section 5314 of title 5",
    ),
    "leg-support-loc-librarian-of-congress": (
        "Librarian of Congress", "Librarian of Congress", "2 U.S.C. 136a-2(1)",
        "loc_2_usc_136a-2.html", "II",
        "the Librarian of Congress shall be compensated at an annual rate of pay which is equal to the annual rate of basic pay payable for positions at level II of the Executive Schedule under section 5313 of title 5",
    ),
}
#: Rows priced from 20 U.S.C. 9517(a)'s class sentence ("each Commissioner" of
#: the National Education Centers) carry 9511(c)(3), the sentence that names
#: those centers, as a third document. Mirrors tier_reference_pay.IES_COMPOSITION.
TIER_REFERENCE_IES_COMPOSITION = (
    "20 U.S.C. 9511(c)(3)", "ies_20_usc_9511.html",
    "The National Education Centers, which include- (A) the National Center for Education Research (as "
    "described in part B); (B) the National Center for Education Statistics (as described in part C); (C) "
    "the National Center for Education Evaluation and Regional Assistance (as described in part D); and "
    "(D) the National Center for Special Education Research (as described in part E).",
)
TIER_REFERENCE_COMPOSED_ROWS = {
    "exec-dept-ed-ies-commissioner-national-center-for-education-research-ncer",
    "exec-dept-ed-ies-commissioner-national-center-for-education-evaluation-ncee",
}
#: The Inspector General Act's rule: (citation, fixture, level, percent, the
#: sentence 5 U.S.C. 403's operative text prints, the establishments citation,
#: its fixture, the definition sentence 5 U.S.C. 401 prints).
TIER_REFERENCE_IG_RULE = (
    "5 U.S.C. 403(e)", "ig_5_usc_403.html", "III", 3,
    "The annual rate of basic pay for an Inspector General (as defined under section 401 of this "
    "title ) shall be the rate payable for level III of the Executive Schedule under section 5314 "
    "of this title , plus 3 percent.",
    "5 U.S.C. 401(1)", "ig_5_usc_401.html",
    'The term "Inspector General" means the Inspector General of an establishment.',
)
TIER_REFERENCE_IG_TITLE = "Inspector General"
_TIER_REFERENCE_ESTABLISHMENT_RE = re.compile(r'The term "establishment" means (.+?), as the case may be\.')


def tier_reference_establishments(operative_401):
    """The establishments 5 U.S.C. 401(1) names, read off the committed
    section's own definition sentence with this file's reader: the
    departments come compressed ("the Department of Agriculture, Commerce,
    ...") and are expanded one per item; the agencies follow written out."""
    match = _TIER_REFERENCE_ESTABLISHMENT_RE.search(operative_401 or "")
    if match is None:
        return []
    segments = [segment.strip() for segment in match.group(1).split(";")]
    if len(segments) != 2 or not segments[0].startswith("the Department of "):
        return []

    def items(text):
        out = []
        for part in text.split(","):
            part = part.strip()
            if part.startswith("or "):
                part = part[3:].strip()
            if part:
                out.append(part)
        return out

    names = ["Department of {}".format(item) for item in items(segments[0][len("the Department of "):])]
    names.extend(item[4:] if item.startswith("the ") else item for item in items(segments[1]))
    return names


def tier_reference_pay_violations(node, pay, today, label, tree_parent_name=None):
    """Everything that must be true of a figure set by reference to a level.

    Two shapes, one field. A GAO row is mirrored by node id and must quote
    the sentence 31 U.S.C. 703 prints now, price the level it names at OPM's
    rate for that level, and carry no arithmetic. An Inspector General's
    block must sit on a node named exactly "Inspector General" whose parent
    IN THE TREE reduces to one of the establishments 5 U.S.C. 401(1) lists --
    re-parsed here from the committed bytes -- must quote 403(e)'s sentence,
    and must publish the arithmetic the gate recomputes: Level III's rate
    plus 3 percent, to the cent. Neither shape may claim that any document
    states the figure.
    """
    out = []
    say = lambda text: out.append("{} {}".format(label(node), text))
    if not isinstance(pay, dict):
        say("{} {!r} is not a record".format(TIER_REFERENCE_FIELD, pay))
        return out
    type_text = str(node.get("type") or "").casefold()
    if not any(word in type_text for word in ("position", "role", "office holder")):
        say("carries a rate set by reference to a level but is a {!r}, not a post".format(node.get("type")))
    out.extend(holders_violations(node, pay, TIER_REFERENCE_FIELD, label))
    if str(pay.get("source") or "") != TIER_REFERENCE_SOURCE:
        say("prices from source {!r}, which this pipeline does not produce for a tier-reference rate".format(pay.get("source")))
        return out

    node_id = str(node.get("id") or "")
    identification = pay.get("identification") if isinstance(pay.get("identification"), dict) else {}
    row = TIER_REFERENCE_ROWS.get(node_id)
    arithmetic = pay.get("arithmetic")
    if row is not None:
        node_name, office, citation, fixture, level, sentence = row
        percent = 0
        if str(pay.get("method") or "") != TIER_REFERENCE_METHOD:
            say("prices a reviewed row under method {!r}, not {!r}".format(pay.get("method"), TIER_REFERENCE_METHOD))
        if canonical_key(node.get("name")) != canonical_key(node_name):
            say("is now called {!r}, not {!r}, the name its row was written against".format(node.get("name"), node_name))
        if identification.get("kind") != "reviewed_row" or str(identification.get("nodeName") or "") != node_name:
            say("does not identify itself as the reviewed row for {!r}".format(node_name))
        if arithmetic is not None:
            say("carries arithmetic on a row whose statute states the level's rate outright")
        if str(pay.get("office") or "") != office:
            say("names office {!r}; the row is {!r}".format(pay.get("office"), office))
        expected_documents = 2
        if node_id in TIER_REFERENCE_COMPOSED_ROWS:
            # 9517(a) prices "each Commissioner" of centers it does not name;
            # the block must carry 9511(c)(3), which does, and quote it as the
            # committed section prints it now.
            comp_citation, comp_fixture, comp_sentence = TIER_REFERENCE_IES_COMPOSITION
            comp_operative = uscode_operative_text(US_CODE_BASIS_FIXTURE_DIR / comp_fixture)
            if comp_sentence not in comp_operative:
                say("rests on a composing sentence {} no longer prints in its operative text".format(comp_citation))
            composing = [d for d in (pay.get("documents") or []) if isinstance(d, dict)
                         and str(d.get("citation") or "") == comp_citation]
            if len(composing) != 1 or str(composing[0].get("quote") or "") != comp_sentence:
                say("prices a Commissioner from 9517(a)'s class sentence without quoting {} as its third document".format(comp_citation))
            expected_documents = 3
    else:
        citation, fixture, level, percent, sentence, est_citation, est_fixture, definition = TIER_REFERENCE_IG_RULE
        if canonical_key(node.get("name")) != canonical_key(TIER_REFERENCE_IG_TITLE):
            say("carries the Inspector General Act's rate but is named {!r}".format(node.get("name")))
            return out
        if str(pay.get("method") or "") != TIER_REFERENCE_METHOD_PERCENT:
            say("prices an Inspector General under method {!r}, not {!r}".format(pay.get("method"), TIER_REFERENCE_METHOD_PERCENT))
        establishments = tier_reference_establishments(uscode_operative_text(US_CODE_BASIS_FIXTURE_DIR / est_fixture))
        if not establishments:
            say("rests on 5 U.S.C. 401(1)'s establishment list, which this gate cannot read from the committed section")
        keys = {canonical_key(name): name for name in establishments}
        parent_key = canonical_key(tree_parent_name or "")
        if not tree_parent_name or parent_key not in keys:
            say("sits under {!r}, which 5 U.S.C. 401(1) does not list as an establishment".format(tree_parent_name))
        elif str(identification.get("establishment") or "") != keys[parent_key]:
            say("names establishment {!r}; its organisation in the tree is 5 U.S.C. 401(1)'s {!r}".format(
                identification.get("establishment"), keys[parent_key]))
        if identification.get("kind") != "establishment_listed_in_5_usc_401":
            say("does not identify itself as an establishment's Inspector General")
        if canonical_key(identification.get("organisationName")) != parent_key:
            say("records its organisation as {!r}; the tree gives it {!r}".format(
                identification.get("organisationName"), tree_parent_name))
        definition_text = uscode_operative_text(US_CODE_BASIS_FIXTURE_DIR / est_fixture)
        if definition not in definition_text:
            say("rests on a definition 5 U.S.C. 401 no longer prints in its operative text")
        if not isinstance(arithmetic, dict):
            say("prices an Inspector General without publishing the arithmetic 403(e) requires")
        expected_documents = 3

    if str(pay.get("statute") or "") != citation:
        say("cites {!r}; this block's statute is {!r}".format(pay.get("statute"), citation))
    if str(pay.get("statuteQuote") or "") != sentence:
        say("quotes a sentence that is not the one {} prints for this rule".format(citation))
    operative = uscode_operative_text(US_CODE_BASIS_FIXTURE_DIR / fixture)
    if not operative:
        say("cites {!r}, whose operative text this gate cannot separate from its notes".format(fixture))
    elif sentence not in operative:
        say("rests on a sentence {} does not print in its operative text".format(citation))
    if str(pay.get("level") or "") != level:
        say("prices level {!r}; {} names {!r}".format(pay.get("level"), citation, level))
    if pay.get("percent") != percent:
        say("applies {!r} percent; {} states {!r}".format(pay.get("percent"), citation, percent))
    base = EXECUTIVE_SCHEDULE_RATES.get(level)
    expected_amount = round(base * (100 + percent) / 100.0, 2) if base is not None else None
    amount = pay.get("amount")
    if base is None:
        say("prices level {!r}, which the mirrored table does not have".format(level))
    elif isinstance(amount, bool) or not isinstance(amount, (int, float)):
        say("publishes {!r} as a rate of basic pay".format(amount))
    elif abs(float(amount) - expected_amount) > 0.005:
        say("publishes {:,.2f}; level {} at {:,.0f} plus {} percent is {:,.2f}".format(
            float(amount), level, base, percent, expected_amount))
    if base is not None:
        if pay.get("levelAmount") != base or str(pay.get("levelRateText") or "") != "${:,.0f}".format(base):
            say("states the level's rate as {!r}; the table prints {!r}".format(pay.get("levelRateText"), "${:,.0f}".format(base)))
        printed = "${:,.0f}".format(expected_amount) if float(expected_amount).is_integer() else "${:,.2f}".format(expected_amount)
        if str(pay.get("rateText") or "") != printed:
            say("prints the rate as {!r}; the computation gives {!r}".format(pay.get("rateText"), printed))
        derivation = str(pay.get("derivation") or "")
        if sentence not in derivation or "${:,.0f}".format(base) not in derivation:
            say("publishes a derivation that does not carry both the statute's sentence and the table's figure")
        if isinstance(arithmetic, dict):
            if arithmetic.get("operation") != "plus_percent" or arithmetic.get("percent") != percent:
                say("publishes arithmetic that is not 'plus {} percent'".format(percent))
            if arithmetic.get("baseAmount") != base or str(arithmetic.get("baseText") or "") != "${:,.0f}".format(base):
                say("computes from a base that is not the table's rate for level {}".format(level))
            if arithmetic.get("result") != expected_amount or arithmetic.get("result") != amount:
                say("publishes a computed result that is not the base plus the percentage, or not the amount published")
            if not str(arithmetic.get("note") or "").strip():
                say("publishes arithmetic without a sentence saying no document prints the result")
    if str(pay.get("table") or "") != EXECUTIVE_SCHEDULE_TABLE:
        say("cites table {!r}, not {!r}".format(pay.get("table"), EXECUTIVE_SCHEDULE_TABLE))
    if str(pay.get("effective") or "") != EXECUTIVE_SCHEDULE_EFFECTIVE:
        say("dates the rate {!r}, not {!r}".format(pay.get("effective"), EXECUTIVE_SCHEDULE_EFFECTIVE))
    if str(pay.get("tableUrl") or "") != TIER_REFERENCE_TABLE_URL:
        say("cites {!r} as the table, not the one this pipeline reads".format(pay.get("tableUrl")))

    documents = pay.get("documents")
    if not isinstance(documents, list) or len(documents) != expected_documents:
        say("names {!r} documents, not {}".format(len(documents) if isinstance(documents, list) else documents, expected_documents))
        documents = []
    urls = []
    for document in documents:
        if not isinstance(document, dict):
            say("publishes a document entry that is not a record")
            continue
        url = str(document.get("url") or "")
        urls.append(url)
        if not url.startswith("https://"):
            say("names a supporting document with no https citation ({!r})".format(url))
        if not re.fullmatch(r"[0-9a-f]{64}", str(document.get("documentSha256") or "")):
            say("names a supporting document with no digest")
        if not str(document.get("quote") or "").strip():
            say("names a supporting document it quotes nothing from")
        if not str(document.get("role") or "").strip():
            say("names a supporting document without saying what it supplies")
        if document.get("statesTheFigure"):
            say("claims a supporting document states the figure; none of them does")
    if urls and not any(US_CODE_HOST in url for url in urls):
        say("publishes a tier-reference figure with no statute behind it")
    if urls and TIER_REFERENCE_TABLE_URL not in urls:
        say("publishes a tier-reference figure with no OPM table behind it")
    if urls and str(pay.get("url") or "") not in urls:
        say("cites {!r} as its statute, which its own document list does not name".format(pay.get("url")))
    if urls and US_CODE_HOST not in str(pay.get("url") or ""):
        say("cites a statute on a host other than uscode.house.gov")

    verification = pay.get("verification")
    if not isinstance(verification, dict):
        say("publishes a tier-reference figure with no statement of how many documents verify it")
    else:
        count = verification.get("documents")
        if count != len(documents) or not isinstance(count, int) or isinstance(count, bool):
            say("says {!r} documents verify it and lists {}".format(count, len(documents)))
        elif verification.get("percent") != DERIVED_PAY_STRENGTH_BY_COUNT.get(count):
            say("publishes {!r}% for {} documents; this project's own scale gives {!r}%".format(
                verification.get("percent"), count, DERIVED_PAY_STRENGTH_BY_COUNT.get(count)))
        if verification.get("documentsStatingTheFigure") != 0:
            say("claims {!r} of its documents state the figure; none of them does".format(
                verification.get("documentsStatingTheFigure")))
        if not str(verification.get("scale") or "").strip():
            say("publishes a percentage without saying what scale it is on")
        if not str(verification.get("caution") or "").strip():
            say("publishes a percentage with no sentence saying what it does not measure")

    if str(pay.get("scopeMatch") or "") != "proxy":
        say("claims scope {!r}; a figure set by reference to a level is never more than a proxy".format(pay.get("scopeMatch")))
    if str(pay.get("financialEvidenceStatus") or "") != "partial":
        say("grades a tier-reference rate {!r}, not 'partial'".format(pay.get("financialEvidenceStatus")))
    checked = str(pay.get("checkedAt") or "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}", checked) or checked[:10] > today:
        say("claims a tier-reference rate without a past retrieval date ({!r})".format(checked))
    if str(node.get("cost_status") or "") in ("official", "root_total", "scaled_official"):
        say("carries a tier-reference rate and a measured cost status {!r}".format(node.get("cost_status")))
    method = str(pay.get("method") or "")
    if method and str(node.get("verificationMethod") or "") == method:
        say("verifies its own existence with a pay figure")
    if method and str(node.get("placementMethod") or "") == method:
        say("places itself with a pay figure")
    for source_url in node.get("sourceUrls") or []:
        text = str(source_url)
        if US_CODE_HOST in text or TIER_REFERENCE_TABLE_URL == text:
            say("counts a pay document among the sources that it exists")
    for other in ("positionStatutoryPay", "positionPayRate", "positionSchedulePay", "positionDerivedPay"):
        if isinstance(node.get(other), dict):
            say("carries a tier-reference rate beside {}; two figures for one post".format(other))
    return out


def derived_pay_violations(node, pay, today, label):
    """Everything that must be true of a figure NO document states.

    This is the only pay block in the project whose number is a join rather
    than a quotation, so it gets two checks no other block needs: the record
    must name BOTH documents and neither may claim to state the figure, and
    the published percentage must be exactly what the mirrored scale gives
    for the count of documents actually listed. A block that said "2
    documents, 95%" would be inventing a scale, and one that said "2
    documents" while listing one would be inventing a document.

    The third is the one this whole module exists for: the sentence the
    statute prints now, checked against the node's own id. 38 U.S.C. 7253's
    page carries its repealed subsection beneath the law, and the repealed
    text puts this court's chief judge at a different tier.
    """
    out = []
    say = lambda text: out.append("{} {}".format(label(node), text))
    if not isinstance(pay, dict):
        say("positionDerivedPay {!r} is not a record".format(pay))
        return out

    type_text = str(node.get("type") or "").casefold()
    if not any(word in type_text for word in ("position", "role", "office holder")):
        say("carries a derived rate of basic pay but is a {!r}, not a post".format(node.get("type")))
    out.extend(holders_violations(node, pay, "positionDerivedPay", label))

    if str(pay.get("source") or "") != DERIVED_PAY_SOURCE:
        say("prices from source {!r}, which this pipeline does not produce for a derived rate".format(pay.get("source")))
        return out
    if str(pay.get("method") or "") != DERIVED_PAY_METHOD:
        say("claims method {!r}, not {!r}".format(pay.get("method"), DERIVED_PAY_METHOD))

    node_id = str(node.get("id") or "")
    provision = DERIVED_PAY_PROVISIONS.get(node_id)
    if provision is None:
        say("carries a derived rate on a node this pipeline has no parity provision for")
        return out
    citation, tier, sentence = provision[:3]
    via = provision[3] if len(provision) > 3 else None
    if str(pay.get("statute") or "") != citation:
        say("cites {!r}; this node's parity provision is {!r}".format(pay.get("statute"), citation))
    quoted_statute = str(pay.get("statuteQuote") or "")
    if quoted_statute != sentence:
        say("quotes a parity sentence that is not the one {} prints now".format(citation))
    if str(pay.get("seatTier") or "") != tier:
        say("prices tier {!r}; {} names {!r}".format(pay.get("seatTier"), citation, tier))

    # The repealed text, refused wherever it appears in this block.
    blob = " ".join(
        str(value) for key, value in pay.items() if key != "documents" and isinstance(value, str)
    )
    documents = pay.get("documents")
    if isinstance(documents, list):
        for document in documents:
            if isinstance(document, dict):
                blob += " " + str(document.get("quote") or "")
    if DERIVED_PAY_REPEALED_TEXT in blob:
        say("quotes 38 U.S.C. 7253's REPEALED subsection, which the page prints beneath the law")

    tier_amount = JUDICIAL_COMPENSATION_TIERS.get(tier)
    percent_of = DERIVED_PAY_PERCENT_OF.get(node_id)
    arithmetic = pay.get("arithmetic")
    if tier_amount is None:
        expected = None
    elif percent_of is not None:
        expected = round(tier_amount * percent_of / 100.0, 2)
    else:
        expected = tier_amount
    amount = pay.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        say("publishes {!r} as a derived rate of basic pay".format(amount))
    elif expected is None:
        say("prices tier {!r}, which the mirrored table does not have".format(tier))
    elif abs(float(amount) - expected) > 0.005:
        if percent_of is not None:
            say("publishes {:,.2f} as {} percent of {!r}, which is {:,.2f}".format(
                float(amount), percent_of, tier, expected))
        else:
            say("publishes {:,.2f} for {!r}, which the table pays {:,.2f}".format(float(amount), tier, expected))
    if expected is not None:
        printed = "${:,.2f}".format(expected) if abs(expected - round(expected)) > 0.005 else "${:,.0f}".format(expected)
        tier_printed = "${:,.0f}".format(tier_amount)
        if str(pay.get("rateText") or "") != printed:
            say("prints the rate as {!r}; {} gives {!r}".format(
                pay.get("rateText"), "the arithmetic" if percent_of is not None else "the table", printed))
        derivation = str(pay.get("derivation") or "")
        if printed not in derivation or sentence not in derivation:
            say("publishes a derivation that does not carry both the statute's sentence and the figure")
        if percent_of is not None and tier_printed not in derivation:
            say("publishes a derivation that does not carry the table's own figure the percentage is taken of")

    # A percentage row carries its arithmetic in the open; a parity row
    # carries none. The block's own percentage is the mirrored one, its base
    # is the table's figure for the tier, and its result is the figure it
    # publishes.
    if percent_of is None:
        if arithmetic is not None or pay.get("percentOf") is not None:
            say("publishes arithmetic on a parity provision that pays the tier's rate itself")
    else:
        if pay.get("percentOf") != percent_of:
            say("claims {!r} percent of the tier; {} says {}".format(pay.get("percentOf"), citation, percent_of))
        if not isinstance(arithmetic, dict):
            say("publishes a percentage of a tier without showing the arithmetic")
        else:
            if str(arithmetic.get("operation") or "") != "percent_of":
                say("shows arithmetic of kind {!r}, not 'percent_of'".format(arithmetic.get("operation")))
            if arithmetic.get("percent") != percent_of:
                say("shows {!r} percent in its arithmetic; {} says {}".format(
                    arithmetic.get("percent"), citation, percent_of))
            base = arithmetic.get("baseAmount")
            if isinstance(base, bool) or not isinstance(base, (int, float)) or tier_amount is None \
                    or abs(float(base) - tier_amount) > 0.005:
                say("takes its percentage of {!r}, not the table's {!r} for {!r}".format(base, tier_amount, tier))
            if str(arithmetic.get("baseTier") or "") != tier:
                say("names {!r} as the tier its percentage is taken of, not {!r}".format(arithmetic.get("baseTier"), tier))
            result = arithmetic.get("result")
            if isinstance(result, bool) or not isinstance(result, (int, float)) or expected is None \
                    or abs(float(result) - expected) > 0.005 or (isinstance(amount, (int, float))
                                                                  and abs(float(result) - float(amount)) > 0.005):
                say("shows a result ({!r}) that is not the percentage of the base, or not the figure it publishes".format(result))
            if not str(arithmetic.get("note") or "").strip():
                say("shows arithmetic without saying that no document prints the result")
        scope = str(pay.get("amountScope") or "")
        if "{} percent".format(percent_of) not in scope:
            say("scopes the figure as {!r}, which does not say it is {} percent of the tier".format(scope, percent_of))

    if str(pay.get("year") or "") != JUDICIAL_COMPENSATION_YEAR:
        say("prices year {!r}, not {!r}".format(pay.get("year"), JUDICIAL_COMPENSATION_YEAR))
    if str(pay.get("effective") or "") != "{}-01-01".format(JUDICIAL_COMPENSATION_YEAR):
        say("dates the rate {!r}, not {!r}".format(
            pay.get("effective"), "{}-01-01".format(JUDICIAL_COMPENSATION_YEAR)))

    # Every document -- two, or three on a chain -- and none of them
    # claiming to state the figure.
    expected_documents = 3 if via else 2
    if via:
        via_citation, via_sentence = via
        if str(pay.get("viaStatute") or "") != via_citation or str(pay.get("viaQuote") or "") != via_sentence:
            say("prices through {} without quoting the sentence it prints now".format(via_citation))
        middle = [d for d in (documents if isinstance(documents, list) else []) if isinstance(d, dict)
                  and str(d.get("citation") or "") == via_citation]
        if len(middle) != 1 or str(middle[0].get("quote") or "") != via_sentence:
            say("names a chain through {} that its own document list does not carry".format(via_citation))
    elif pay.get("viaStatute") or pay.get("viaQuote"):
        say("claims a chain through {!r} that this node's provision does not make".format(pay.get("viaStatute")))
    if not isinstance(documents, list) or len(documents) != expected_documents:
        say("publishes a derived figure naming {!r} documents, not {}".format(
            len(documents) if isinstance(documents, list) else documents,
            "three" if expected_documents == 3 else "two"))
        documents = []
    urls = []
    for document in documents:
        if not isinstance(document, dict):
            say("publishes a document entry that is not a record")
            continue
        url = str(document.get("url") or "")
        urls.append(url)
        if not url.startswith("https://"):
            say("names a supporting document with no https citation ({!r})".format(url))
        if not re.fullmatch(r"[0-9a-f]{64}", str(document.get("documentSha256") or "")):
            say("names a supporting document with no digest")
        if not str(document.get("quote") or "").strip():
            say("names a supporting document it quotes nothing from")
        if not str(document.get("role") or "").strip():
            say("names a supporting document without saying what it supplies")
        if document.get("statesTheFigure"):
            say("claims a supporting document states the figure; neither of them does")
    if urls and not any(host in url for url in urls for host in DERIVED_PAY_STATUTE_HOSTS):
        say("publishes a derived figure with no parity provision behind it")
    for url in urls:
        if url != DERIVED_PAY_TABLE_URL and not any(host in url for host in DERIVED_PAY_STATUTE_HOSTS):
            say("cites a statute on {!r}, a host this pipeline does not read the Code from".format(url))
    if urls and DERIVED_PAY_TABLE_URL not in urls:
        say("publishes a derived figure with no compensation table behind it")
    if urls and str(pay.get("url") or "") not in urls:
        say("cites {!r} as its statute, which its own document list does not name".format(pay.get("url")))
    if str(pay.get("tableUrl") or "") != DERIVED_PAY_TABLE_URL:
        say("cites {!r} as the compensation table, not the one this pipeline reads".format(pay.get("tableUrl")))

    verification = pay.get("verification")
    if not isinstance(verification, dict):
        say("publishes a derived figure with no statement of how many documents verify it")
    else:
        count = verification.get("documents")
        if count != len(documents) or not isinstance(count, int) or isinstance(count, bool):
            say("says {!r} documents verify it and lists {}".format(count, len(documents)))
        elif verification.get("percent") != DERIVED_PAY_STRENGTH_BY_COUNT.get(count):
            say("publishes {!r}% for {} documents; this project's own scale gives {!r}%".format(
                verification.get("percent"), count, DERIVED_PAY_STRENGTH_BY_COUNT.get(count)))
        if verification.get("documentsStatingTheFigure") != 0:
            say("claims {!r} of its documents state the figure; none of them does".format(
                verification.get("documentsStatingTheFigure")))
        if not str(verification.get("scale") or "").strip():
            say("publishes a percentage without saying what scale it is on")
        if not str(verification.get("caution") or "").strip():
            say("publishes a percentage with no sentence saying what it does not measure")

    if str(pay.get("scopeMatch") or "") != "proxy":
        say("claims scope {!r}; a figure no document states is never more than a proxy".format(pay.get("scopeMatch")))
    if str(pay.get("financialEvidenceStatus") or "") != "partial":
        say("grades a derived rate {!r}, not 'partial'".format(pay.get("financialEvidenceStatus")))

    checked = str(pay.get("checkedAt") or "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}", checked) or checked[:10] > today:
        say("claims a derived rate without a past retrieval date ({!r})".format(checked))

    if str(node.get("cost_status") or "") in ("official", "root_total", "scaled_official"):
        say("carries a derived rate and a measured cost status {!r}".format(node.get("cost_status")))
    method = str(pay.get("method") or "")
    if method and str(node.get("verificationMethod") or "") == method:
        say("verifies its own existence with a pay figure no document states")
    if method and str(node.get("placementMethod") or "") == method:
        say("places itself with a pay figure no document states")
    for source_url in node.get("sourceUrls") or []:
        text = str(source_url)
        if any(host in text for host in DERIVED_PAY_STATUTE_HOSTS) or DERIVED_PAY_TABLE_URL == text:
            say("counts a pay document among the sources that it exists")
    return out


def member_seat_chamber(node_id, tree_parents):
    """The chamber grouping among a node's ancestors, off the tree the gate
    is walking; None outside both chambers (a joint committee)."""
    seen = set()
    current = tree_parents.get(node_id) if isinstance(tree_parents, dict) else None
    while current and current not in seen:
        if current in US_CODE_MEMBER_SEAT_ROWS:
            return current
        seen.add(current)
        current = tree_parents.get(current)
    return None


def member_seat_violations(node, pay, label, tree_parents, type_by_id, name_by_id):
    """Everything that must be true of a Schedule 6 block that prices an
    office a Member holds at the SEAT rate rather than at a row naming the
    office: the rule mirrored above, checked off the tree, plus the basis
    the panel prints."""
    out = []
    say = lambda text: out.append("{} {}".format(label(node), text))
    node_id = str(node.get("id") or "")
    name = str(node.get("name") or "")
    if str(pay.get("method") or "") != US_CODE_MEMBER_SEAT_METHOD:
        say("carries a memberSeat block under method {!r}, not the member-seat method".format(pay.get("method")))
    seat = pay.get("memberSeat")
    if not isinstance(seat, dict):
        say("is priced as a Member's seat with no memberSeat block saying whose seat and why")
        return out
    if str(pay.get("source") or "") != "us_code_pay_schedules":
        say("prices a Member's seat from {!r}, not Schedule 6".format(pay.get("source")))
    if node_id in STATUTORY_PAY_NODE_TIERS:
        say("has a Schedule 6 row of its own and may not be priced as a Member's seat")
    if node_id in US_CODE_MEMBER_SEATS_NOT_PRICED:
        say("is a post the member-seat rule refuses by name")
    if node.get("representsPosts"):
        say("stands for several posts and is priced as one Member's seat")
    if not isinstance(tree_parents, dict) or not isinstance(type_by_id, dict):
        say("is priced as a Member's seat and the gate was handed no tree to read its chamber off")
        return out
    chamber = member_seat_chamber(node_id, tree_parents)
    if chamber is None:
        say("sits under neither chamber grouping (a joint committee?) and is priced as a Member's seat")
    else:
        expected_row = US_CODE_MEMBER_SEAT_ROWS[chamber]
        if str(seat.get("chamber") or "") != chamber:
            say("says its seat is in {!r}; the tree puts it in {!r}".format(seat.get("chamber"), chamber))
        if str(seat.get("row") or "").casefold() != expected_row:
            say("names row {!r} for a seat in {!r}".format(seat.get("row"), chamber))
        if str(pay.get("seatTier") or "") != expected_row:
            say("prices tier {!r} for a seat in {!r}, whose row is {!r}".format(pay.get("seatTier"), chamber, expected_row))
        if str(pay.get("amountScope") or "").casefold() != expected_row:
            say("scopes the figure to {!r}, not the chamber's row".format(pay.get("amountScope")))
    kind = str(seat.get("kind") or "")
    parent_id = tree_parents.get(node_id) or ""
    parent_type = str(type_by_id.get(parent_id) or "").casefold()
    if node_id in US_CODE_MEMBER_LEADERSHIP_NODES:
        if kind != "leadership_office":
            say("is a listed leadership office filed as {!r}".format(kind))
        if chamber is not None and US_CODE_MEMBER_LEADERSHIP_NODES[node_id] != chamber:
            say("is a leadership office the table places in {!r}, now under {!r}".format(
                US_CODE_MEMBER_LEADERSHIP_NODES[node_id], chamber))
        if str(seat.get("role") or "") != name:
            say("names its office {!r}; the node is {!r}".format(seat.get("role"), name))
    else:
        if kind != "committee_post":
            say("is not a listed leadership office and is filed as {!r}".format(kind))
        prefix = next((p for p in US_CODE_MEMBER_ROLE_PREFIXES if name.startswith(p)), None)
        if prefix is None:
            say("is named {!r}, which begins with no Member-role prefix".format(name))
        else:
            if str(seat.get("role") or "") != prefix[:-2]:
                say("names its role {!r}; the name says {!r}".format(seat.get("role"), prefix[:-2]))
            if str(seat.get("body") or "") != name[len(prefix):].strip():
                say("names its body {!r}; the name says {!r}".format(seat.get("body"), name[len(prefix):].strip()))
        if parent_type not in US_CODE_MEMBER_COMMITTEE_TYPES:
            say("sits under a {!r} ({!r}), not a committee, and is priced as its chair or ranking member".format(
                type_by_id.get(parent_id), (name_by_id or {}).get(parent_id)))
    basis = str(seat.get("basis") or "")
    if US_CODE_MEMBER_SEAT_SEPARATE_RATES not in basis:
        say("gives a basis that does not carry the schedule's own list of the offices it prices separately")
    if US_CODE_MEMBER_SEAT_REVIEWED_WORDS not in basis:
        say("gives a basis that does not say the identification is a reviewed rule")
    if "never read" not in basis:
        say("gives a basis that does not say the holder is never read")
    if chamber == "leg-house" and US_CODE_HOUSE_SEAT_ROWS_NOTE not in basis:
        say("prices a House seat without noting the Delegate and Resident Commissioner rows")
    return out


def statutory_pay_violations(node, pay, today, label, tree_parents=None, type_by_id=None, name_by_id=None):
    """Everything that must be true of a single-source statutory pay claim.

    Unlike `table_pay_violations`, there is no archive underneath this to
    check for agreement with — the source names the rate directly — so the
    checks are simpler: the source is a known one, the figure is the mirror's
    own figure for the tier claimed, the quoted text really contains that
    figure and, where the source is a grouped claim about several roles
    (the Senate footnote), the quote actually names the specific role this
    node is.
    """
    out = []
    say = lambda text: out.append("{} {}".format(label(node), text))
    if not isinstance(pay, dict):
        say("positionStatutoryPay {!r} is not a record".format(pay))
        return out

    type_text = str(node.get("type") or "").casefold()
    if not any(word in type_text for word in ("position", "role", "office holder")):
        say("carries a statutory rate of basic pay but is a {!r}, not a post".format(node.get("type")))
    out.extend(holders_violations(node, pay, "positionStatutoryPay", label))
    if SENIOR_JUDGE_MARKER.search(str(node.get("name") or "")) and str(pay.get("source") or "") == "uscourts_judicial_compensation":
        say("bundles senior judges, whose salary 28 U.S.C. 371(b)(2) sets by reference to a past year "
            "(adjusted under \u00a7461), not necessarily the tier's current rate")

    source = str(pay.get("source") or "")
    mirror = STATUTORY_PAY_SOURCES.get(source)
    if mirror is None:
        say("prices from source {!r}, which this pipeline does not produce".format(source))
        return out
    node_id = str(node.get("id") or "")
    prefixes = mirror["id_prefix"]
    if isinstance(prefixes, str):
        prefixes = (prefixes,)
    if not node_id.startswith(tuple(prefixes)):
        say("prices from {!r}, which names no post outside the {!r} branch".format(source, mirror["id_prefix"]))

    if str(pay.get("year") or "") != mirror["year"]:
        say("prices year {!r}, not {!r}".format(pay.get("year"), mirror["year"]))
    if str(pay.get("effective") or "") != "{}-01-01".format(mirror["year"]):
        say("dates the rate {!r}, not {!r}".format(pay.get("effective"), "{}-01-01".format(mirror["year"])))

    tier = str(pay.get("seatTier") or "")
    member_seat = str(pay.get("method") or "") == US_CODE_MEMBER_SEAT_METHOD or isinstance(pay.get("memberSeat"), dict)
    if member_seat:
        # An office a Member holds, priced at the seat rate: the tier is the
        # chamber's row, read off the tree, and the rule is checked there.
        out.extend(member_seat_violations(node, pay, label, tree_parents, type_by_id, name_by_id))
        chamber = member_seat_chamber(node_id, tree_parents)
        expected_tier_for_node = US_CODE_MEMBER_SEAT_ROWS.get(chamber) if chamber else None
    else:
        expected_tier_for_node = STATUTORY_PAY_NODE_TIERS.get(node_id)
        if source == "us_code_pay_schedules" and tier in US_CODE_MEMBER_SEAT_ROWS.values():
            say("prices a Member's seat row without the member-seat method and its block")
    if expected_tier_for_node is None:
        say("prices a node this pipeline has no known tier for")
    elif tier != expected_tier_for_node:
        say("prices tier {!r} on a node that is a {!r}".format(tier, expected_tier_for_node))
    expected = mirror["tiers"].get(tier)
    amount = pay.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        say("publishes {!r} as a rate of basic pay".format(amount))
    elif expected is None:
        say("prices tier {!r}, which the mirrored table does not have".format(tier))
    elif abs(float(amount) - expected) > 0.005:
        say("publishes {:,.2f} for {!r}, which the table pays {:,.2f}".format(float(amount), tier, expected))
    if expected is not None:
        printed = "${:,.0f}".format(expected)
        rate_text = str(pay.get("rateText") or "")
        if not rate_text.startswith(printed):
            say("prints the rate as {!r}; the table prints {!r}".format(rate_text, printed))

    quote = str(pay.get("quote") or "")
    if expected is not None and "${:,.0f}".format(expected) not in quote:
        # Schedule 6 marks its column once, at the head, so every row beneath
        # prints a bare figure; that case is checked against the head below.
        if source != "us_code_pay_schedules":
            say("quotes text that does not contain the figure it prices")
        elif "{:,.0f}".format(expected) not in quote:
            say("quotes text that does not contain the figure it prices")
    if source == "senate_salary_schedule":
        phrase = SENATE_LEADERSHIP_ROLE_PHRASES.get(tier)
        if phrase is None or phrase not in quote.casefold():
            say("prices a Senate leadership role its own quoted footnote does not name")

    if source == "us_code_pay_schedules":
        # A schedule row, not a footnoted table: what stands in for the note
        # is the schedule's own heading and effective line, and the record
        # must quote both. Without the effective line a reader cannot tell
        # which year's order the figure comes from, and the figure alone is
        # the same number every source in this file prints. Which schedule
        # is decided by the tier: Schedule 7's one mirrored row is judicial
        # and nothing judicial may be priced from Schedule 6, or vice versa.
        judicial_tier = tier in US_CODE_SCHEDULE_7_RATES
        if judicial_tier:
            heading, effective, column_head, number = (
                SCHEDULE_7_HEADING, US_CODE_SCHEDULE_7_EFFECTIVE, US_CODE_SCHEDULE_7_COLUMN_HEAD, "7")
            if not node_id.startswith("jud-"):
                say("prices a Schedule 7 judicial salary row on a node outside the judiciary")
            if str(pay.get("schedule") or "") != "7":
                say("prices a Schedule 7 row without saying so")
        else:
            heading, effective, column_head, number = (
                SCHEDULE_6_HEADING, US_CODE_SCHEDULE_6_EFFECTIVE, US_CODE_SCHEDULE_6_COLUMN_HEAD, "6")
            if node_id.startswith("jud-"):
                say("prices a Schedule 6 row on a judicial node, outside the branches Schedule 6 names")
            if str(pay.get("schedule") or "6") != "6":
                say("claims a schedule other than 6 for an office Schedule 6 names")
        if heading.casefold() not in quote.casefold():
            say("prices from Schedule {} without quoting its heading".format(number))
        if effective.casefold() not in quote.casefold():
            say("prices from Schedule {} without quoting the effective line the note prints".format(number))
        if tier and tier not in quote.casefold():
            say("prices an office its own quoted schedule row does not name")
        # The bare rows are readable as dollars only because the column's
        # first figure carries the mark; the record must carry it too.
        if expected is not None and "${:,.0f}".format(expected) not in quote:
            if column_head not in quote:
                say("prices a bare schedule figure without quoting the marked head of its column")

    footnotes = pay.get("footnotes")
    if not isinstance(footnotes, list):
        say("footnotes is not a list")
    elif mirror["footnotes"] is None:
        # This source's "footnotes" is its own quote, checked above; what
        # must not happen is a record carrying notes from somewhere else.
        if tuple(str(f).strip() for f in footnotes) != (quote.strip(),):
            say("quotes notes that are not the schedule row it prices")
    elif tuple(str(f).strip() for f in footnotes) != mirror["footnotes"]:
        say("quotes notes the source does not carry")

    checked = str(pay.get("checkedAt") or "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}", checked) or checked[:10] > today:
        say("claims a statutory rate without a past retrieval date ({!r})".format(checked))
    url = str(pay.get("url") or "")
    if url != mirror["url"]:
        say("cites {!r}, not the source this pipeline reads for {!r}".format(url, source))
    host = host_of(url)
    if not host.endswith((".gov", ".mil")):
        say("claims a statutory rate with no .gov/.mil document behind it")

    if str(node.get("cost_status") or "") in ("official", "root_total", "scaled_official"):
        say("carries a statutory rate and a measured cost status {!r}".format(node.get("cost_status")))
    if str(node.get("costVerificationStatus") or "") == "verified":
        say("carries a statutory rate and claims a verified cost")
    method = str(pay.get("method") or "")
    if method and str(node.get("verificationMethod") or "") == method:
        say("verifies its own existence with a statutory pay source that names no post")
    if method and str(node.get("placementMethod") or "") == method:
        say("places itself with a statutory pay source that names no post")
    # Same rule as table_pay_violations, same reason: abstinence from
    # sourceUrls must be enforced from the artefact, not merely practised.
    if url and url in [str(u) for u in (node.get("sourceUrls") or [])]:
        say("cites the statutory pay source among the sources that it exists")
    return out


def alias_match_violations(node, label_of, by_id=None):
    """Everything a published alias match must be, checked against the
    mirrored table rather than against itself.

    The block is the weaker claim this project allows a name to carry, so
    each refusal below answers a way it could be made to read as the
    stronger one: a row moved to another node, a node renamed out from under
    its row, an alternative nobody reviewed, a claim with no basis, a
    `verified` badge resting on alias-derived documents alone, and an alias
    anywhere near a figure.
    """
    out = []
    block = node.get("verificationAliasMatch")
    node_id = str(node.get("id") or "")
    if block is None:
        if str(node.get("verificationMatchRule") or "") == MATCH_RULE_ALIAS:
            out.append("{} claims an alias match rule with no alias block".format(label_of(node)))
        return out
    if not isinstance(block, dict):
        out.append("{} verificationAliasMatch is not an object".format(label_of(node)))
        return out
    by_id = by_id or {}
    owner_id = str(block.get("owner") or "") or node_id
    known = NODE_ALIASES.get(owner_id)
    if known is None:
        out.append("{} publishes an alias match but the committed table has no row for {!r}".format(label_of(node), owner_id))
        return out
    recorded_name, allowed = known
    # The row is written against ONE curated name, and a rename withdraws it.
    # For a node-scoped match that is this node; for an organisation-scoped
    # one it is the ancestor whose name the source printed differently, and
    # the gate reads that node off the graph rather than off the block.
    owner_node = node if owner_id == node_id else by_id.get(owner_id)
    if owner_node is None:
        out.append("{} cites an alias row for {!r}, which is not in the graph".format(label_of(node), owner_id))
        return out
    if str(owner_node.get("name") or "") != recorded_name:
        out.append("{} carries an alias row written against {!r}, and that node is now named {!r}".format(
            label_of(node), recorded_name, owner_node.get("name")))
        return out
    matches = block.get("matches")
    if not isinstance(matches, list) or not matches:
        out.append("{} publishes an alias block with no matches behind it".format(label_of(node)))
        return out
    urls = [str(u) for u in (block.get("urls") or [])]
    node_urls = {str(u) for u in (node.get("sourceUrls") or [])}
    seen = []
    for entry in matches:
        if not isinstance(entry, dict):
            out.append("{} alias match entry is not an object".format(label_of(node)))
            continue
        entry_owner = str(entry.get("owner") or "") or node_id
        entry_known = NODE_ALIASES.get(entry_owner)
        alias = str(entry.get("alias") or "")
        if entry_known is None or alias not in entry_known[1]:
            out.append("{} quotes the alternative {!r}, which the committed table does not carry for {!r}".format(
                label_of(node), alias, entry_owner))
        if not str(entry.get("basis") or "").strip():
            out.append("{} publishes an alias match with no basis".format(label_of(node)))
        scope = str(entry.get("scope") or "")
        if scope not in ALIAS_SCOPES:
            out.append("{} alias match scope {!r} is not one this pipeline produces".format(
                label_of(node), entry.get("scope")))
        elif scope == "node" and entry_owner != node_id:
            out.append("{} claims another node's alternative as its own name".format(label_of(node)))
        elif scope == "organisation" and entry_owner == node_id:
            out.append("{} files its own alternative as its organisation's".format(label_of(node)))
        url = str(entry.get("url") or "")
        if not host_of(url).endswith((".gov", ".mil")):
            out.append("{} alias match cites {!r}, which is not an official host".format(label_of(node), url))
        elif url not in urls:
            out.append("{} alias match cites {!r}, which its own url list omits".format(label_of(node), url))
        elif url not in node_urls:
            out.append("{} alias match cites {!r}, which is not one of the node's sources".format(label_of(node), url))
        seen.append(url)
    if sorted(set(urls)) != sorted(set(seen)):
        out.append("{} alias urls {} are not the urls its matches name".format(label_of(node), urls))
    if str(block.get("alias") or "") not in allowed:
        out.append("{} alias block headline {!r} is not a reviewed alternative for it".format(
            label_of(node), block.get("alias")))
    if not str(block.get("basis") or "").strip():
        out.append("{} alias block headline carries no basis".format(label_of(node)))
    # The cap. A node every one of whose official sources was reached through
    # the table may not read `verified`: that is what two documents naming the
    # unit outright earn, and writing an identification down is not that.
    official = [u for u in node_urls if is_official_site(u)]
    alias_only = bool(official) and set(official) <= set(urls)
    graded = str(block.get("gradedAtMost") or "")
    if alias_only:
        if graded != "partial":
            out.append("{} rests only on alias-matched sources and does not say it is graded at most partial".format(label_of(node)))
        if str(node.get("verificationStatus") or "") == "verified":
            out.append("{} reads verified on alias-matched sources alone".format(label_of(node)))
        try:
            if float(node.get("confidenceScore") or 0.0) > 0.7:
                out.append("{} scores {} on alias-matched sources alone".format(label_of(node), node.get("confidenceScore")))
        except (TypeError, ValueError):
            out.append("{} has an unreadable confidenceScore beside an alias match".format(label_of(node)))
    elif graded:
        out.append("{} claims an alias grading cap while other sources name it too".format(label_of(node)))
    return out


def alias_on_a_figure_violations(node, label_of):
    """An alias may never appear on a block that lands a number."""
    out = []
    for field in ALIAS_FORBIDDEN_BLOCKS:
        blob = node.get(field)
        if blob is None:
            continue
        text = json.dumps(blob, default=str)
        for marker in ALIAS_MARKERS:
            if marker in text:
                out.append("{} carries {!r} inside {}, which lands a figure".format(label_of(node), marker, field))
                break
    return out


def walk(node, parent=None):
    """Yield (node, parent) for every dict node in the tree."""
    yield node, parent
    for child in node.get("children") or []:
        if isinstance(child, dict):
            yield from walk(child, node)


def amount_of(node):
    value = node.get("resolved_total_amount")
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def label(node):
    return "{} ({})".format(node.get("name") or "Unnamed Node", node.get("id") or "no-id")


class Gate:
    def __init__(self):
        self.failures = []

    def check(self, name, violations, detail=""):
        """Record a check. `violations` is a list of human-readable strings."""
        if violations:
            self.failures.append((name, violations))
            print("FAIL  {} — {} violation(s){}".format(name, len(violations), detail))
            for line in violations[:SAMPLE_LIMIT]:
                print("        {}".format(line))
            if len(violations) > SAMPLE_LIMIT:
                print("        … and {} more".format(len(violations) - SAMPLE_LIMIT))
        else:
            print("ok    {}{}".format(name, detail))


def check_review_queue(gate, queue_path, graph, nodes):
    """The review queue is served to the site too. A record the current
    discovery code could not produce must not be there."""
    try:
        records = json.loads(queue_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        gate.check("review queue is readable JSON", ["{}: {}".format(queue_path, error)])
        return
    if not isinstance(records, list):
        gate.check("review queue is a list", ["{} holds a {}".format(queue_path, type(records).__name__)])
        return
    published = {canonical_key(n.get("name")) for n in nodes}
    generated, duplicates, unchecked_dates, bad_parent_ids, duplicate_ids, fragments = [], [], [], [], [], []
    ids = Counter()
    node_ids = {str(n.get("id") or "") for n in nodes}
    for record in records:
        if not isinstance(record, dict):
            continue
        ids[str(record.get("id") or "")] += 1
        urls = [record.get("sourceUrl"), *(record.get("sourceUrls") if isinstance(record.get("sourceUrls"), list) else [])]
        if any(str(u or "").startswith("generated://") for u in urls):
            generated.append(label(record))
        if canonical_key(record.get("name")) in published:
            duplicates.append(label(record))
        elif is_federal_register_only(urls):
            extended = extends_published_name(canonical_key(record.get("name")), published)
            if extended:
                fragments.append("{} extends {!r}".format(label(record), extended))
        if record.get("lastVerified") and not (record.get("sourceUrls") or []):
            unchecked_dates.append(label(record))
        parent_id = record.get("possibleParentId")
        if parent_id and parent_id not in node_ids:
            bad_parent_ids.append("{} names parent id {!r}".format(label(record), parent_id))
    duplicate_ids = ["{} appears {} times".format(i, c) for i, c in ids.items() if c > 1]
    gate.check("review queue has no template-generated records", generated)
    gate.check("review queue has no records duplicating a published node", duplicates)
    gate.check("review queue has no Federal Register fragments extending a published name", fragments)
    gate.check("review queue claims no verification date without a source", unchecked_dates)
    gate.check("review queue parent ids exist in the graph", bad_parent_ids)
    gate.check("review queue has no duplicate ids", duplicate_ids)
    print("  review queue         : {:,} records".format(len(records)))


# A Federal Register notice names the agency it concerns and then goes on:
# "Office of Management and Budget Review", "... (OMB) Circular No". The old
# extractor kept such fragments. A name that is a published node's name plus
# trailing words is one, unless the trailing words open a unit of their own
# ("Department of Energy Office of Science").
ORG_UNIT_LEADING_WORDS = frozenset(
    "office bureau division directorate service administration center centre agency board "
    "commission institute laboratory program programme council corps command department".split()
)


def extends_published_name(name_key, published_keys):
    for published in published_keys:
        if published and name_key.startswith(published + " "):
            remainder = name_key[len(published) + 1 :].split()
            if remainder and remainder[0] not in ORG_UNIT_LEADING_WORDS:
                return published
    return None


def host_of(url):
    """The URL's real host, lowercased, or "".

    NOT `url.split("/")[2]`. That reads everything up to the first slash as the
    host, so `https://evil.com?x=.gov` and `https://evil.example.com#.gov` both
    passed the gate's `.gov`/`.mil` test, and `https://www.opm.gov@evil.com/`
    was read as opm.gov. `financial_evidence._validate_source_url` documents
    fixing exactly this in its own URL check; the gate still had the split in
    eight places, and a red team walked a non-government URL past the check
    literally named "claims a table rate with no .gov/.mil document behind it".
    """
    try:
        return (urlparse(str(url or "")).hostname or "").lower()
    except ValueError:
        return ""


def is_federal_register_only(urls):
    hosts = []
    for url in urls:
        text = str(url or "")
        if text.startswith(("http://", "https://")):
            hosts.append(host_of(text))
    return bool(hosts) and all(h.endswith("federalregister.gov") for h in hosts)


def _within(curated, official, tolerance):
    """Is the curated string within `tolerance` of the official count? The
    same first-number-with-magnitudes reading the cascade uses, kept local so
    the gate stays stdlib-only; a wildly different figure is the finding, not
    a violation, so this only feeds the report."""
    import re as _re

    text = str(curated or "").replace(",", "")
    match = _re.search(r"(\d+(?:\.\d+)?)\s*(million|thousand|k|m)?", text, _re.I)
    if not match or not official:
        return True
    value = float(match.group(1))
    suffix = (match.group(2) or "").lower()
    value *= {"million": 1e6, "m": 1e6, "thousand": 1e3, "k": 1e3}.get(suffix, 1)
    if not value:
        return True
    return abs(value - official) <= tolerance * max(value, official)


def parent_name_of(node, parent_of, by_id):
    parent = by_id.get(parent_of.get(str(node.get("id") or "")))
    return (parent or {}).get("name")


def position_title_keys(name, parent_name):
    """The keys a curated position name answers to: itself, itself without a
    trailing qualifier that is the parent's own name or acronym, and each
    slash-separated alternative. The same reduction
    data_pipeline/verification/positions.py makes, mirrored here so the gate
    stays stdlib-only; tests/test_positions.py pins the two together."""
    text = str(name or "").strip()
    parent_keys = set()
    parent_text = str(parent_name or "").strip()
    if parent_text:
        parent_keys.add(canonical_key(parent_text))
        acronyms = re.findall(r"\(([^)]+)\)", parent_text)
        parent_keys.update(canonical_key(a) for a in acronyms)
        without = canonical_key(re.sub(r"\([^)]*\)", " ", parent_text))
        if without:
            parent_keys.add(without)
    core = text
    if "," in text:
        for index, char in enumerate(text):
            if char != ",":
                continue
            head, tail = text[:index].strip(), text[index + 1:].strip()
            if head and tail and canonical_key(tail) in parent_keys:
                core = head
                break
    keys = set()
    for candidate in (text, core):
        key = canonical_key(candidate)
        if key:
            keys.add(key)
        for part in str(candidate).split("/"):
            part_key = canonical_key(part)
            if part_key:
                keys.add(part_key)
    return keys or {canonical_key(text)}


def directory_name_keys(value):
    """The Federal Register's agency directory writes the head noun last
    ("Prisons Bureau", "Energy Department", "Inspector General Office, Energy
    Department"); the curated file writes "Bureau of Prisons". The same
    rewrite data_pipeline/verification/directories.py matches by, mirrored
    here so the gate stays stdlib-only; tests pin the two together."""
    text = str(value or "")
    if "," in text:
        core, _, tail = text.rpartition(",")
        # A qualifier ("…, Energy Department") is a scope, not part of the name.
        if tail.strip().endswith(("Department", "President", "Congress", "Agency", "Administration", "Commission")):
            text = core
    key = canonical_key(text)
    if not key:
        return set()
    keys = {key}
    tokens = key.split()
    heads = ("department", "office", "bureau", "administration", "agency", "service", "commission", "board",
             "corporation", "council", "institute", "center", "division", "foundation", "authority", "committee")
    if len(tokens) > 1 and tokens[-1] in heads:
        head, rest = tokens[-1], " ".join(tokens[:-1])
        for prep in ("of", "of the", "for", "on"):
            keys.add("{} {} {}".format(head, prep, rest))
    for k in list(keys):
        if k.startswith("united states "):
            keys.add(k[len("united states "):])
        else:
            keys.add("united states " + k)
    return keys


COMMITTEE_TYPES = {"committee", "subcommittee"}
MATCH_RULE_COMMITTEE = "committee_scaffolding_folded"
MATCH_RULE_ALIAS = "matched_on_a_recorded_alternative_name"
ALIAS_SCOPES = {"node", "organisation"}
#: `data/curation/node_aliases.json`, mirrored BY NODE ID for the reason the
#: Executive Schedule and White House tables are: an alias moved to another
#: node keeps a real alternative name and a real basis, and only a check tied
#: to the node's own identity catches it. The name is mirrored too, because
#: the row is written against one curated name and a rename must withdraw it.
#: `tests/test_node_aliases.py` pins this equal to the committed table.
NODE_ALIASES = {
    "exec-ind-misc-americorps": ("AmeriCorps", ("Corporation for National and Community Service",)),
    "exec-vp": ("The Vice President of the United States", ("The Vice President",)),
    "jud-support-aousc": ("Administrative Office of U.S. Courts (AOUSC)",
                          ("Administrative Office of the United States Courts",)),
    "exec-dept-doc-noaa": ("NOAA — National Oceanic & Atmospheric Administration",
                           ("National Oceanic and Atmospheric Administration",)),
    "exec-dept-dot-fmcsa": ("Federal Motor Carrier Safety Admin (FMCSA)",
                            ("Federal Motor Carrier Safety Administration",)),
    "exec-dept-dot-nhtsa": ("National Highway Traffic Safety Admin (NHTSA)",
                            ("National Highway Traffic Safety Administration",)),
    "exec-dept-dot-phmsa": ("Pipeline & Hazardous Materials Safety Admin (PHMSA)",
                            ("Pipeline and Hazardous Materials Safety Administration",)),
    "exec-dept-defense-agency-darpa": ("DARPA", ("Defense Advanced Research Projects Agency",)),
    "exec-ind-misc-export-import-bank-of-the-u-s": ("Export-Import Bank of the U.S.",
                                                    ("Export-Import Bank",)),
    "exec-regulatory-bureau-of-consumer-financial-protection": (
        "Bureau of Consumer Financial Protection", ("Consumer Financial Protection Bureau",)),
    "exec-ind-misc-odni": ("Office of the Director of National Intelligence",
                           ("Office of the Director for National Intelligence",)),
    "exec-ind-misc-cigie": ("Council of the Inspectors General on Integrity and Efficiency",
                            ("Council of Inspectors General on Integrity and Efficiency",)),
    "exec-ind-misc-privacy-civil-liberties-oversight-board-pclob": (
        "Privacy & Civil Liberties Oversight Board (PCLOB)",
        ("Privacy and Civil Liberties and Oversight Board",)),
}
#: The blocks an alias may never appear on. An alias is a claim about two
#: NAMES, and every one of these lands a NUMBER; each already has its own
#: reviewed table where a figure is at stake, and `CLAUDE.md` records why one
#: table serving both kinds of claim is dangerous (FedScope's "DEPARTMENT OF
#: THE ARMY" is a civilian department, the graph's "U.S. Army" the uniformed
#: service). The check is a string scan of the block as published, so a field
#: nobody anticipated cannot smuggle one in.
ALIAS_FORBIDDEN_BLOCKS = (
    "usaspendingOutlays", "auditedNetCost", "ombBudget", "employeesOfficial",
    "employeesOfficialSource", "cost_weight_dispute", "positionPayRate",
    "positionGradePay", "positionStatutoryPay", "positionSchedulePay",
    "positionReportedPay", "positionCurrentPay", "positionDerivedPay",
    "positionTierReferencePay",
)
#: Deliberately only this feature's own rule and field. `usaspendingOutlays`
#: carries a `nameAlias` of its OWN -- `USASPENDING_NAME_ALIASES`, a separate
#: reviewed table mirrored by node id in this file -- and that separation is
#: the point rather than a violation: a figure's alias is reviewed where the
#: figure is at stake. What must never appear on a money block is a name
#: reached through the EXISTENCE table, which is what these two strings mean.
ALIAS_MARKERS = (MATCH_RULE_ALIAS, "verificationAliasMatch")


#: `normalize_nodes.GOVERNMENT_DATASET_HOSTS`, mirrored stdlib-only. The
#: grading cap turns on the difference between "a .gov URL" and "an official
#: SITE": a FiscalData dataset URL and a Federal Register agency page are
#: both `.gov` and neither earns the +0.3 that makes a node `verified`, so a
#: node carrying only one of those is exactly the node one aliased document
#: could otherwise carry from 0.4 to 0.8. `tests/test_node_aliases.py` pins
#: this function equal to `classify_source_url` on the published graph.
GOVERNMENT_DATASET_HOSTS = ("fiscaldata.treasury.gov", "api.fiscaldata.treasury.gov", "api.usaspending.gov")


def is_official_site(url):
    host = host_of(url)
    if "federalregister.gov" in host:
        return False
    if any(host == d or host.endswith("." + d) for d in GOVERNMENT_DATASET_HOSTS):
        return False
    return host.endswith((".gov", ".mil"))


def alias_keys_for(node_id, by_id):
    """The canonical keys a node also answers to, or an empty set.

    Empty unless the node still carries the exact name the row was written
    against: a rename withdraws every alternative, here as in the pipeline.
    """
    known = NODE_ALIASES.get(str(node_id or ""))
    if not known:
        return set()
    node = (by_id or {}).get(str(node_id or ""))
    if node is None or str(node.get("name") or "") != known[0]:
        return set()
    return {canonical_key(a) for a in known[1]}
# A post confirmed by a label in its own organisation's page content. Mirrors
# data_pipeline.verification.evidence.METHOD_POST_ON_ORG_PAGE; the checks
# below and the coverage report both key off it.
POST_PAGE_METHOD = "name_labelled_on_its_organisations_official_page"

# OMB's Public Budget Database. The gate re-derives the figures from the
# committed package itself -- a stdlib zip+XML read, importing nothing from
# data_pipeline -- for the reason whitehouse_roster() is independent.
OMB_PACKAGE = "BUDGET-2027-DB"
OMB_FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "omb" / (OMB_PACKAGE + ".zip")
OMB_ESTIMATE_SENTENCE = re.compile(
    r"Budget\s*estimates\s*for\s*the\s*current\s*fiscal\s*year\s*\(\s*((?:\d\s*){4})\)", re.I)


def _omb_sheet_rows(blob):
    """One xlsx member as a list of rows, stdlib only.

    An .xlsx is a zip of XML; the same fact `congress.read_xlsx_rows` uses,
    reimplemented here so the gate does not import the code it checks.
    """
    import xml.etree.ElementTree as _ET
    import zipfile as _zipfile

    book = _zipfile.ZipFile(io.BytesIO(blob))
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    shared = []
    if "xl/sharedStrings.xml" in book.namelist():
        for si in _ET.fromstring(book.read("xl/sharedStrings.xml")):
            shared.append("".join(t.text or "" for t in si.iter(ns + "t")))
    rows = []
    for row in _ET.fromstring(book.read("xl/worksheets/sheet1.xml")).iter(ns + "row"):
        cells = []
        for cell in row.iter(ns + "c"):
            ref = cell.get("r") or ""
            letters = "".join(ch for ch in ref if ch.isalpha())
            index = 0
            for ch in letters:
                index = index * 26 + (ord(ch.upper()) - 64)
            index -= 1
            value = cell.find(ns + "v")
            text = "" if value is None else (value.text or "")
            if cell.get("t") == "s" and text.isdigit() and int(text) < len(shared):
                text = shared[int(text)]
            elif cell.get("t") == "inlineStr":
                node = cell.find(ns + "is")
                text = "".join(t.text or "" for t in node.iter(ns + "t")) if node is not None else ""
            while len(cells) <= index:
                cells.append("")
            cells[index] = text
        rows.append(cells)
    return rows


def _omb_guide_text(pdf):
    """The user's guide as prose. Mirrors omb_budget.guide_text, stdlib only."""
    import zlib as _zlib

    token = re.compile(rb"\((?:\\.|[^\\()])*\)|-?\d+(?:\.\d+)?|TJ|Tj|BT|ET|Td|TD|T\*|Tm")
    out = []
    for stream in re.findall(rb"stream\r?\n(.*?)endstream", pdf, re.S):
        try:
            body = _zlib.decompress(stream)
        except _zlib.error:
            continue
        if b"BT" not in body:
            continue
        for m in token.finditer(body):
            t = m.group(0)
            if t.startswith(b"("):
                text = re.sub(rb"\\([()\\])", rb"\1", t[1:-1])
                out.append(text.replace(b"\\n", b" ").replace(b"\\r", b" ").decode("latin-1"))
            elif t in (b"Td", b"TD", b"T*", b"Tm", b"ET"):
                out.append(" ")
            elif t not in (b"TJ", b"Tj", b"BT"):
                try:
                    if float(t) <= -120:
                        out.append(" ")
                except ValueError:
                    continue
    return re.sub(r"[ \t]+", " ", "".join(out))


def omb_database():
    """(last actual fiscal year, {agency: total}, {(agency, bureau): total}) per measure.

    Raises OSError/ValueError, which the caller turns into a violation.
    """
    if "database" in _OMB_CACHE:
        return _OMB_CACHE["database"]
    import hashlib as _hashlib
    import zipfile as _zipfile

    raw = OMB_FIXTURE.read_bytes()
    digest = _hashlib.sha256(raw).hexdigest()
    meta_path = OMB_FIXTURE.with_suffix(OMB_FIXTURE.suffix + ".meta.json")
    if meta_path.exists():
        recorded = (json.loads(meta_path.read_text(encoding="utf-8")) or {}).get("sha256")
        if recorded and recorded != digest:
            raise ValueError("{}: sha256 on disk {} does not match the fetch record {}".format(
                OMB_FIXTURE.name, digest, recorded))
    archive = _zipfile.ZipFile(io.BytesIO(raw))
    guide = _omb_guide_text(archive.read("{}/pdf/{}-4.pdf".format(OMB_PACKAGE, OMB_PACKAGE)))
    found = OMB_ESTIMATE_SENTENCE.search(guide)
    if not found:
        raise ValueError("the OMB guide does not state which years are estimates")
    last_actual = int(re.sub(r"\s+", "", found.group(1))) - 1

    measures = {}
    for measure, member in (("budget_authority", "1"), ("outlays", "2")):
        rows = _omb_sheet_rows(archive.read("{}/xls/{}-{}.xlsx".format(OMB_PACKAGE, OMB_PACKAGE, member)))
        header = rows[0]
        a_i, b_i = header.index("Agency Name"), header.index("Bureau Name")
        c_i = header.index("CGAC Agency Code")
        y_i = header.index(str(last_actual))
        agency, bureau, counts, cgac = {}, {}, {}, {}
        for row in rows[1:]:
            def get(i):
                return str((row[i] if i < len(row) else "") or "").strip()
            try:
                value = float((get(y_i) or "0").replace(",", ""))
            except ValueError:
                value = 0.0
            agency[get(a_i)] = agency.get(get(a_i), 0.0) + value
            key = (get(a_i), get(b_i))
            bureau[key] = bureau.get(key, 0.0) + value
            counts[get(a_i)] = counts.get(get(a_i), 0) + 1
            counts[key] = counts.get(key, 0) + 1
            if get(c_i):
                cgac.setdefault(get(a_i), set()).add(get(c_i))
        measures[measure] = (agency, bureau, counts, cgac)
    _OMB_CACHE["database"] = (last_actual, measures, digest)
    return _OMB_CACHE["database"]


# A post listed in its own organisation's entry in the United States
# Government Manual. Mirrors data_pipeline.verification.govman.METHOD.
GOVMAN_METHOD = "listed_in_its_organisations_us_government_manual_entry"
GOVMAN_ORG_METHOD = "listed_in_us_government_manual"
GOVMAN_ORG_PLACEMENT_METHOD = "listed_under_parent_in_us_government_manual"
#: The top-level office route (govman.TOP_LEVEL_OFFICE_METHOD) and the one
#: extension a principal row may add to its entry's heading.
GOVMAN_OFFICE_METHOD = "listed_as_its_own_entry_in_us_government_manual"
GOVMAN_OFFICE_STYLE_SUFFIX = "of the united states"
GOVMAN_PACKAGE = "GOVMAN-2025-12-31"
GOVMAN_DETAILS = "https://www.govinfo.gov/app/details"
GOVMAN_FIXTURE = (
    Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "govman" / (GOVMAN_PACKAGE + ".xml")
)
GOVMAN_ENTITY_TAGS = ("Entity", "SubEntityLevelOne", "SubEntityLevelTwo", "SubEntityLevelThree")
GOVMAN_SEPARATORS = set("-\u2013\u2014_ ")


_GOVMAN_CACHE = {}
_OMB_CACHE = {}


def govman_entries():
    """granule id -> (agency name, {canonical title key: printed title}).

    A SECOND, independent extraction of the rule
    `data_pipeline/verification/govman.py` applies, written stdlib-only and
    importing nothing from the module it checks -- the reason
    `whitehouse_roster()` is independent, and the reason the Executive
    Schedule mirror is pinned against the committed sections rather than
    copied from the code. `tests/test_govman.py` asserts the two agree on
    the real fixture, so they cannot drift apart silently.

    Raises OSError/ValueError, which the caller turns into a violation.
    """
    if "entries" in _GOVMAN_CACHE:
        return _GOVMAN_CACHE["entries"]
    import hashlib as _hashlib
    import xml.etree.ElementTree as _ET

    raw = GOVMAN_FIXTURE.read_bytes()
    digest = _hashlib.sha256(raw).hexdigest()
    meta_path = GOVMAN_FIXTURE.with_suffix(GOVMAN_FIXTURE.suffix + ".meta.json")
    if meta_path.exists():
        recorded = (json.loads(meta_path.read_text(encoding="utf-8")) or {}).get("sha256")
        if recorded and recorded != digest:
            raise ValueError(
                "{}: sha256 on disk {} does not match the fetch record {}".format(
                    GOVMAN_FIXTURE.name, digest, recorded))

    def flat(value):
        return " ".join(str(value or "").split())

    def separator(text):
        return bool(text) and set(text) <= GOVMAN_SEPARATORS

    def all_caps(text):
        letters = [c for c in text if c.isalpha()]
        return bool(letters) and all(c.isupper() for c in letters)

    entries = {}
    parents = {}  # granule -> the enclosing entity's printed name, or None at the top
    # granule -> the two texts a description may be read from: the FIRST
    # MissionStatement record's paragraph, and the first non-empty
    # Detail/Paragraph under ProgramAndActivities in document order. Nothing
    # else in the entry is descriptive text, so nothing else is read.
    descriptions = {}

    def description_texts(element):
        mission = None
        statement = element.find("MissionStatement")
        if statement is not None:
            first = statement.find("Record")
            if first is not None:
                mission = flat(first.findtext("Paragraph")) or None
        opening = None
        programmes = element.find("ProgramAndActivities")
        if programmes is not None:
            for paragraph in programmes.findall(".//Detail/Paragraph"):
                text = flat(paragraph.text)
                if text:
                    opening = text
                    break
        return {"mission": mission, "opening": opening}

    def visit(element, parent_name=None):
        if element.tag in GOVMAN_ENTITY_TAGS:
            name = flat(element.findtext("AgencyName"))
            entity_id = (element.get("EntityId") or "").strip()
            if name and entity_id.isdigit():
                parents["{}-{:03d}".format(GOVMAN_PACKAGE, int(entity_id))] = parent_name
                parent_for_children = name
            else:
                parent_for_children = parent_name
        else:
            parent_for_children = parent_name
        if element.tag in GOVMAN_ENTITY_TAGS and (element.get("EntityId") or "").strip().isdigit() and flat(element.findtext("AgencyName")):
                titles = {}
                tables = element.find("LeaderShipTables")
                for table in (tables.findall("LeaderShipTable") if tables is not None else []):
                    if flat(table.findtext("Header")) not in ("", "*"):
                        continue
                    governed = False
                    for row in table.findall("LeaderShipTableValues/Values"):
                        # TitleColumnValue only. NameColumnValue is a living
                        # person and is never read, here or in the module.
                        title = flat(row.findtext("TitleColumnValue"))
                        if not title:
                            continue
                        if separator(title):
                            governed = False
                            continue
                        if all_caps(title):
                            # The caps row is a title in its own right (the
                            # principal's, as printed); it governs what follows.
                            titles.setdefault(canonical_key(title), []).append(title)
                            governed = True
                            continue
                        if governed:
                            continue
                        titles.setdefault(canonical_key(title), []).append(title)
                granule = "{}-{:03d}".format(GOVMAN_PACKAGE, int(entity_id))
                entries[granule] = (name, titles)
                descriptions[granule] = description_texts(element)
        children = element.find("Childrens")
        if children is not None:
            for sub in children:
                visit(sub, parent_for_children)

    for entity in _ET.parse(GOVMAN_FIXTURE).getroot():
        visit(entity, None)
    _GOVMAN_CACHE["entries"] = entries
    _GOVMAN_CACHE["parents"] = parents
    _GOVMAN_CACHE["descriptions"] = descriptions
    _GOVMAN_CACHE["digest"] = digest
    return entries


def govman_parents():
    """granule id -> the name of the entity the Manual files it under, from
    the same independent parse as govman_entries()."""
    govman_entries()
    return _GOVMAN_CACHE.get("parents", {})


def govman_descriptions():
    """granule id -> {"mission": ..., "opening": ...}, the two texts a
    description may be read from, and the package digest, from the same
    independent parse as govman_entries()."""
    govman_entries()
    return _GOVMAN_CACHE.get("descriptions", {}), _GOVMAN_CACHE.get("digest")


# Mirrors data_pipeline.verification.govman: the bound on a published
# description, the two kinds, and the element path each is read from.
GOVMAN_DESCRIPTION_MAX_CHARS = 600
GOVMAN_DESCRIPTION_PATHS = {
    "mission_statement": "MissionStatement/Record[1]/Paragraph",
    "opening_paragraph": "ProgramAndActivities//Detail/Paragraph[first non-empty]",
}
# An opening paragraph about the unit's website rather than the unit, mirrored
# from the module: a closed list that only ever withholds a description.
GOVMAN_NAVIGATION_NOTE_MARKERS = ("organizational chart", "organization chart", "web page", "website")
# A sentence boundary, mirrored from the module: a terminator after a
# lower-case letter, digit or closing mark, then whitespace and a capital.
GOVMAN_SENTENCE_BOUNDARY = re.compile(
    r'(?<=[a-z0-9\)\]"”’])[.!?]["”’)]*(?=\s+[A-Z"“(])'
)


# The signature block of a published Federal Register document. Mirrors
# data_pipeline.verification.federal_register_signatures; the reader below is
# a SECOND, independent stdlib extraction that imports nothing from the module
# it checks, the shape govman_entries() and whitehouse_roster() already use.
FR_SIGNATURE_METHOD = "signed_a_federal_register_document"
FR_SIGNATURE_SOURCE = "federal_register_signature"
FR_SIGNATURE_DIR = (
    Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "federal_register" / "signatures"
)
FR_DOCUMENT_URL = "https://www.federalregister.gov/d/{}"
FR_DOCUMENT_MEDIA_TYPE = "text/plain"
FR_MIN_POST_TOKENS = 2
FR_MAX_BLOCK_LINES = 8
FR_NAME_LINE = re.compile(r"^(?:[A-Z][A-Za-z'’.\-]*\.?)(?:\s+[A-Z][A-Za-z'’.\-]*\.?){0,4},$")
# Mirrors data_pipeline.verification.directories.HEAD_NOUNS /
# HEAD_PREPOSITIONS; tests/test_federal_register_signatures.py pins
# fr_agency_keys equal to federal_register_name_keys on every agency name the
# committed listings print, so the two cannot drift.
FR_HEAD_NOUNS = (
    "department", "office", "bureau", "administration", "agency", "service", "commission", "board",
    "corporation", "council", "institute", "center", "division", "foundation", "authority", "committee",
)
FR_HEAD_PREPOSITIONS = ("of", "of the", "for", "on")

_FR_SIGNATURE_CACHE = {}


def fr_agency_keys(name):
    """The canonical keys a Federal Register agency name may answer to."""
    key = canonical_key(name)
    if not key:
        return set()
    keys = {key}
    tokens = key.split()
    if len(tokens) > 1 and tokens[-1] in FR_HEAD_NOUNS:
        head, rest = tokens[-1], " ".join(tokens[:-1])
        for prep in FR_HEAD_PREPOSITIONS:
            keys.add("{} {} {}".format(head, prep, rest))
    for k in list(keys):
        if k.startswith("united states "):
            keys.add(k[len("united states "):])
        else:
            keys.add("united states " + k)
    return {k for k in keys if k}


def fr_signature_title(text, document_number):
    """The title a document's signature block prints, re-derived here.

    The name line is located ONLY so that the title can be taken from below
    it: what is returned is built from the lines after the name line, so this
    function cannot return the signer's name either.
    """
    marker = "[FR Doc. {} Filed".format(document_number)
    lines = text.split("\n")
    fr_doc_at = None
    for i, line in enumerate(lines):
        if line.strip().startswith(marker):
            fr_doc_at = i
            break
    if fr_doc_at is None:
        return None
    name_at = None
    for j in range(fr_doc_at - 1, max(-1, fr_doc_at - 1 - FR_MAX_BLOCK_LINES), -1):
        stripped = lines[j].strip()
        if not stripped:
            break
        if FR_NAME_LINE.match(stripped):
            name_at = j
            break
    if name_at is None:
        return None
    title = " ".join(" ".join(lines[name_at + 1:fr_doc_at]).split())
    # Mirrors federal_register_signatures.MARKUP_CHARACTERS / HTML_ENTITY: a
    # tag or an HTML entity is markup and refuses the block; a bare ampersand
    # is not, because this graph names units "Health & Human Services".
    if not title or "<" in title or ">" in title or re.search(r"&[#A-Za-z][A-Za-z0-9]*;", title):
        return None
    if not title.endswith("."):
        return None
    return title[:-1].strip() or None


def fr_signature_documents():
    """document number -> what the committed fixtures say about it.

    {"title": the signature title, "agencies": [names the API listing prints],
     "publicationDate", "signingDate", "sha256", "url"}. Every digest is
    recomputed from the bytes. Raises OSError/ValueError for the caller.
    """
    if "documents" in _FR_SIGNATURE_CACHE:
        return _FR_SIGNATURE_CACHE["documents"]
    import hashlib as _hashlib

    def read(path):
        meta_path = path.with_name(path.name + ".meta.json")
        if not meta_path.exists():
            raise ValueError("{} has no .meta.json beside it".format(path.name))
        meta = json.loads(meta_path.read_text(encoding="utf-8")) or {}
        raw = path.read_bytes()
        digest = _hashlib.sha256(raw).hexdigest()
        recorded = str(meta.get("sha256") or "").lower()
        if not recorded or recorded != digest:
            raise ValueError(
                "{}: sha256 on disk {} does not match the fetch record {!r}".format(
                    path.name, digest, recorded))
        return raw, digest, meta

    listed = {}
    for path in sorted((FR_SIGNATURE_DIR / "index").glob("*.json")):
        if path.name.endswith(".meta.json"):
            continue
        raw, _digest, _meta = read(path)
        payload = json.loads(raw.decode("utf-8"))
        for row in payload.get("results") or []:
            number = str((row or {}).get("document_number") or "").strip()
            if not number or number in listed:
                continue
            listed[number] = {
                "agencies": [" ".join(str((a or {}).get("name") or (a or {}).get("raw_name") or "").split())
                             for a in (row.get("agencies") or [])
                             if " ".join(str((a or {}).get("name") or (a or {}).get("raw_name") or "").split())],
                "publicationDate": row.get("publication_date") or None,
                "signingDate": row.get("signing_date") or None,
                "documentTitle": " ".join(str(row.get("title") or "").split()),
                "documentType": " ".join(str(row.get("type") or "").split()),
            }
    documents = {}
    for number, row in listed.items():
        path = FR_SIGNATURE_DIR / "documents" / (number + ".txt")
        if not path.exists():
            continue
        raw, digest, meta = read(path)
        if str(meta.get("content_type") or "").split(";")[0].strip() != FR_DOCUMENT_MEDIA_TYPE:
            continue
        entry = dict(row)
        entry.update({"title": fr_signature_title(raw.decode("utf-8", "replace"), number),
                      "sha256": digest, "url": str(meta.get("url") or "")})
        documents[number] = entry
    _FR_SIGNATURE_CACHE["documents"] = documents
    return documents


def list_subcommittee_key(key):
    """Mirror of data_pipeline.verification.congress.subcommittee_key on an
    already-canonical key: the type word set aside on either side and nothing
    else. 'subcommittee on the constitution' -> 'constitution'; 'east asia and
    pacific subcommittee' -> 'east asia and pacific'; a 'permanent
    subcommittee on ...' is untouched. tests/test_congress.py pins the two
    together."""
    text = str(key or "").strip()
    if text.startswith("subcommittee on "):
        text = text[len("subcommittee on "):]
    if text.startswith("the "):
        text = text[len("the "):]
    if text.endswith(" subcommittee"):
        text = text[: -len(" subcommittee")]
    return text.strip()


def is_committee(node):
    return str(node.get("type") or "").strip().casefold() in COMMITTEE_TYPES


def committee_core_key(key):
    """Mirror of data_pipeline.verification.evidence.committee_core_key, kept
    stdlib-only here; tests/test_committee_fold.py pins the two together.
    'house committee on armed services' -> 'armed services'; '' when fewer
    than two tokens remain."""
    text = str(key or "").strip()
    for prefix in ("house ", "senate "):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    for _ in range(2):
        for prefix in ("permanent select committee on ", "select committee on ", "special committee on ",
                       "joint committee on ", "subcommittee on ", "committee on "):
            if text.startswith(prefix):
                text = text[len(prefix):]
                break
        if text.startswith("the "):
            text = text[len("the "):]
    for suffix in (" subcommittee", " committee"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
            break
    text = text.strip()
    return text if len(text.split()) >= 2 else ""


def folded_label_names(node, matched_text):
    """Does the page's label name this committee once the type words are set
    aside on both sides? Only for a committee-typed node, only with two or
    more tokens left, and exact after the fold."""
    import re

    if not is_committee(node):
        return False
    core = committee_core_key(canonical_key(node.get("name")))
    if not core:
        return False
    for part in re.split(r"\s*[—–|·•:>›»/·]\s*|\s+[-–]\s+|\n+", str(matched_text or "")):
        if committee_core_key(canonical_key(part)) == core:
            return True
    return False


def is_post(node):
    """Mirror of data_pipeline.exporter.build_graph.is_post_node, stdlib-only.
    tests/test_position_evidence.py pins the two together."""
    type_text = str(node.get("type") or "").casefold()
    return any(word in type_text for word in ("position", "role", "office holder"))


#: Mirror of data_pipeline.verification.evidence.SCAFFOLD_TOKENS and
#: MAX_SCAFFOLD_TOKENS. tests/test_position_evidence.py pins the two
#: together, as tests/test_committee_fold.py does for the committee fold.
SCAFFOLD_TOKENS = frozenset(
    "about the a an our welcome to home homepage official website site page of us u s united states usa gov "
    "overview mission history contact leadership organization organisation".split()
)
MAX_SCAFFOLD_TOKENS = 5


def label_names(node, matched_text):
    """Is the quoted label this node's name, as the matcher reads a label?

    A stdlib mirror of `evidence.label_matches`, and it has to be that rather
    than plain equality. The first version here demanded equality on the
    whole fragment or one of its separator-split parts, which looked stricter
    and therefore safer — and it refused the Senate's own heading for its own
    officer, "U.S. Senate: About the Sergeant at Arms", because the split
    leaves "about the sergeant at arms" and the scaffolding is still on it.
    A gate that rejects what the matcher correctly accepted is not a stricter
    gate, it is a broken one: the invariant worth enforcing is "this label
    names this node", and the matcher's bounded scaffold allowance is part of
    what that means. What it still refuses is the thing it is for — a label
    that names a DIFFERENT office ("Deputy Secretary" for "Secretary"), since
    "deputy" is not a scaffold word and never becomes one.
    """
    import re

    key = canonical_key(node.get("name"))
    if not key:
        return False
    text = str(matched_text or "")
    # An address is never a label (mirrors the matcher's 2026-09-21 rule).
    if "@" in text:
        return False
    if canonical_key(text) == key:
        return True
    for part in re.split(r"\s*[—–|·•:>›»/·]\s*|\s+[-–]\s+|\n+", text):
        candidate = canonical_key(part)
        if not candidate:
            continue
        if candidate == key:
            return True
        if candidate.endswith(" " + key):
            prefix = candidate[: -len(key) - 1].split()
            if prefix and len(prefix) <= MAX_SCAFFOLD_TOKENS and all(t in SCAFFOLD_TOKENS for t in prefix):
                return True
        if candidate.startswith(key + " "):
            suffix = candidate[len(key) + 1:].split()
            if suffix and len(suffix) <= MAX_SCAFFOLD_TOKENS and all(t in SCAFFOLD_TOKENS for t in suffix):
                return True
    return False


def canonical_key(value):
    # Same reduction the exporter uses (kept local so the gate stays stdlib-only).
    import re

    text = str(value or "").casefold()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    text = re.sub(r"\bu s(?: a)?\b", "united states", text)
    for prefix in ("the ", "united states "):
        if text.startswith(prefix):
            text = text[len(prefix):]
    return text.strip()


def main(argv):
    graph_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_GRAPH
    if not graph_path.exists():
        print("FATAL: no graph at {}".format(graph_path))
        return 2

    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    nodes = [node for node, _ in walk(graph)]
    pairs = list(walk(graph))
    # The tree is the authority on placement. `parentId` is stamped only on the
    # exported node list, not on every tree node, so a check that read it would
    # silently pass for most of the graph -- which is exactly what the scoped
    # Executive Schedule claim cannot afford: it identifies a node by its name
    # AND the body above it, and "General Counsel" is the name of 84 nodes.
    tree_parents = {
        str(node.get("id") or ""): str((parent or {}).get("id") or "")
        for node, parent in pairs
    }
    # The parent's NAME, off the same walk, for the current PLUM export's
    # filing check: the export names the organisation it files a title under,
    # and the gate compares that with the parent the tree actually gives.
    name_by_id = {str(node.get("id") or ""): node.get("name") for node, _ in pairs}
    # The parent's TYPE, off the same walk, for the member-seat rule: a
    # committee's chair or ranking member is priced at the seat rate only
    # under a parent typed Committee or Subcommittee.
    type_by_id = {str(node.get("id") or ""): node.get("type") for node, _ in pairs}
    # The same index by node, built here rather than 600 lines down, because
    # the alias checks need to read the OWNER of a row off the graph: an
    # organisation-scoped match belongs to an ancestor, and the rename guard
    # is a fact about that ancestor's current name.
    by_id = {str(node.get("id") or ""): node for node, _ in pairs}
    print("Validating {} ({:,} nodes)\n".format(graph_path, len(nodes)))

    gate = Gate()

    # 1. Root identity.
    root_id = str(graph.get("id") or "")
    gate.check(
        "root id",
        [] if root_id == EXPECTED_ROOT_ID else ["root id is {!r}, expected {!r}".format(root_id, EXPECTED_ROOT_ID)],
    )

    # 2. A measured cost is the Treasury anchor on the root, or a Treasury
    #    outlay line applied to the one node it names (an official rollup with
    #    the FiscalData source on it). Anything else claiming measurement is an
    #    estimate wearing the wrong badge; a root that does not is a missing anchor.
    verified = [n for n in nodes if str(n.get("costVerificationStatus") or "").lower() == "verified"]
    illegitimate = []
    for node in verified:
        if node is graph:
            continue
        types = node.get("sourceTypes") if isinstance(node.get("sourceTypes"), list) else []
        urls_here = node.get("sourceUrls") if isinstance(node.get("sourceUrls"), list) else []
        backed = (
            str(node.get("cost_status") or "") == "official"
            and node.get("rollup_total_amount") is not None
            and "treasury_outlays" in types
            # The type is a label; the URL is the evidence. The evidence module
            # once stripped the FiscalData URL from 26 measured nodes and this
            # check, keyed on the type alone, let the Supreme Court cite a court
            # About page as the source of its outlays.
            and any("fiscaldata.treasury.gov" in str(u) for u in urls_here)
        )
        if not backed:
            illegitimate.append("{} claims a measured cost without a Treasury line and its URL".format(label(node)))
    measured_violations = list(illegitimate)
    if graph not in verified:
        measured_violations.insert(0, "root {} is not measured (no Treasury anchor)".format(label(graph)))
    gate.check(
        "measured costs are the root and Treasury lines only",
        measured_violations,
        " — root + {} Treasury line(s)".format(len(verified) - (1 if graph in verified else 0)) if not measured_violations else "",
    )

    # 3. Every amount carries a provenance label.
    gate.check(
        "every amount has a cost_status",
        [label(n) for n in nodes if amount_of(n) is not None and not n.get("cost_status")],
    )

    # 4. attachToRoot together with parentId asserts a discovered reporting line
    #    to the Constitution.
    gate.check(
        "no attachToRoot with a parentId",
        [label(n) for n in nodes if n.get("attachToRoot") and n.get("parentId")],
    )

    # 5. A part cannot cost more than the whole — less the whole's negative
    #    parts. Since the statement's receipts are carried as explicit
    #    negative lines, a positive child may reach the parent's figure plus
    #    what its negative siblings take back (CMS's $2.3T sits inside HHS's
    #    $1.7T net beside −$749B of Medicare premiums and transfers), and no
    #    further. A line the Treasury files under another section is outside
    #    the parent's total altogether and is checked in the report instead.
    def is_external(node):
        return node.get("treasury_external_section") is True

    over_parent = []
    for parent, _ in pairs:
        parent_amount = amount_of(parent)
        if parent_amount is None:
            continue
        kids = [c for c in (parent.get("children") or []) if isinstance(c, dict) and not is_external(c)]
        negatives = sum(a for a in (amount_of(c) for c in kids) if a is not None and a < 0)
        pool = parent.get("treasury_pool_negative")
        capacity = parent_amount - negatives + (-float(pool) if isinstance(pool, (int, float)) and pool < 0 else 0.0)
        for child in kids:
            child_amount = amount_of(child)
            if child_amount is None or child_amount <= 0:
                continue
            if child_amount > capacity * (1 + 1e-9) + 0.01:
                over_parent.append(
                    "{} = {:,.2f} > parent {} = {:,.2f} less its negative lines {:,.2f}".format(
                        label(child), child_amount, label(parent), parent_amount, negatives
                    )
                )
    gate.check("no child costs more than its parent less the parent's negative lines", over_parent)

    # 6. Direct children must not sum past the root total.
    root_amount = amount_of(graph)
    child_sum = sum(a for a in (amount_of(c) for c in (graph.get("children") or []) if isinstance(c, dict)) if a is not None)
    if root_amount is None:
        gate.check("children sum within the root total", ["root has no resolved_total_amount"])
    else:
        delta = child_sum - root_amount
        pct = (delta / root_amount * 100) if root_amount else 0.0
        detail = " — children {:,.2f} vs root {:,.2f} (delta {:+,.2f}, {:+.4f}%)".format(
            child_sum, root_amount, delta, pct
        )
        over = child_sum > root_amount * (1 + CHILD_SUM_TOLERANCE)
        gate.check(
            "children sum within the root total",
            ["children exceed the root total by {:,.2f} ({:.4f}%)".format(delta, pct)] if over else [],
            detail,
        )

    # 7. sourceCount and sourceUrls must never disagree.
    disagreements = []
    for node in nodes:
        try:
            count = int(node.get("sourceCount") or 0)
        except (TypeError, ValueError):
            count = 0
        urls = node.get("sourceUrls")
        urls = urls if isinstance(urls, list) else []
        if count > 0 and not urls:
            disagreements.append("{} claims {} source(s) with an empty sourceUrls".format(label(node), count))
        elif urls and count == 0:
            disagreements.append("{} has {} sourceUrls but sourceCount 0".format(label(node), len(urls)))
    gate.check("sourceCount agrees with sourceUrls", disagreements)

    # 8. Duplicate ids.
    id_counts = Counter(str(n.get("id") or "") for n in nodes)
    gate.check(
        "no duplicate node ids",
        ["{} appears {} times".format(node_id, count) for node_id, count in id_counts.items() if count > 1],
    )

    # 10. An amount of zero (or less) is a claim that the thing is free. A share
    #     the cascade could not resolve must say so with cost_status
    #     'unavailable' and no amount, never with $0.00.
    #     A negative figure is a different thing: net outlays below zero are
    #     what the Treasury reports for the Mint, the FDIC, the Executive
    #     Office of the President, and for the receipts it nets inside every
    #     section. Those may be negative — a Treasury line, a receipts line
    #     the exporter carries explicitly, or an estimate for a grouping whose
    #     measured members net below zero (stamped measured_net_beneath) —
    #     and nothing else may.
    non_positive = []
    unlabelled_missing = []
    for node in nodes:
        amount = amount_of(node)
        if amount is not None and amount == 0:
            non_positive.append("{} = 0.00".format(label(node)))
        elif amount is not None and amount < 0:
            measured_line = node.get("rollup_total_amount") is not None and str(node.get("treasury_row_name") or "")
            receipts_line = str(node.get("synthetic") or "") == "treasury_receipts"
            net_beneath = node.get("measured_net_beneath")
            negative_grouping = isinstance(net_beneath, (int, float)) and net_beneath < 0 and str(node.get("cost_status") or "") == "allocated"
            if not (measured_line or receipts_line or negative_grouping):
                non_positive.append("{} = {:,.2f} is negative without a Treasury line behind it".format(label(node), amount))
        elif amount is None and str(node.get("cost_status") or "") != "unavailable":
            unlabelled_missing.append("{} has no amount and cost_status {!r}".format(label(node), node.get("cost_status")))
    gate.check("no zero amounts, and no negative amount without a Treasury line behind it", non_positive)
    gate.check("a missing amount is labelled unavailable", unlabelled_missing)
    # A Treasury line is a measured figure; while the root is anchored, every
    # one is published, in full or capped, never as "not available". Six lines
    # under the independent-agencies grouping ($3.08B, the Peace Corps among
    # them) were hidden this way once, and the cap summary never counted them
    # because it counts only scaled_official nodes.
    hidden_lines = []
    if str(graph.get("cost_status") or "") == "root_total" and graph.get("resolved_total_amount") is not None:
        for node in nodes:
            if node is graph:
                continue
            line = node.get("rollup_total_amount")
            if isinstance(line, (int, float)) and line != 0 and str(node.get("cost_status") or "") == "unavailable":
                hidden_lines.append("{} carries a Treasury line of {:,.2f} but is published unavailable".format(label(node), line))
    gate.check("no Treasury line is hidden as unavailable", hidden_lines)

    # 11. Check 6, at every level: the parts of any node must fit inside it —
    #     signed, with two named exceptions the node itself declares. A line
    #     the Treasury files under another section is not part of this
    #     parent's total (treasury_external_section). And a netted unit whose
    #     lines exceed its net total by a negative line the graph has no node
    #     for carries treasury_pool_negative, the exact excess, and its
    #     unlined children publish nothing; the excess is allowed, to the cent.
    over_parent_sums = []
    external_lines = []
    negative_pools = []
    for parent, _ in pairs:
        parent_amount = amount_of(parent)
        if parent_amount is None:
            continue
        children = [c for c in (parent.get("children") or []) if isinstance(c, dict)]
        external_lines.extend(c for c in children if is_external(c))
        child_amounts = [a for a in (amount_of(c) for c in children if not is_external(c)) if a is not None]
        if not child_amounts:
            continue
        total = sum(child_amounts)
        allowance = 0.0
        pool = parent.get("treasury_pool_negative")
        if isinstance(pool, (int, float)) and pool < 0:
            allowance = -float(pool)
            negative_pools.append(parent)
        # A netted unit that declares `treasury_unapportioned` is saying, in a
        # figure of its own, exactly how much of its total reaches no node —
        # the statement's lines this graph has no unit for, going nowhere. Then
        # the parts DO account for the whole, and the honest test is the
        # identity rather than an inequality: children + unapportioned must
        # equal the parent, to the cent. That is strictly stronger than the
        # bound below wherever it applies, and it is what lets a unit whose net
        # total is NEGATIVE pass at all — the General Services Administration
        # nets -$1.06bn, carries one receipts line of -$274.8m and declares the
        # remaining -$789.2m unapportioned, and the one-sided bound read the
        # less-negative child sum as overshooting its more-negative parent.
        unapportioned = parent.get("treasury_unapportioned")
        if isinstance(unapportioned, (int, float)):
            drift = abs(total + float(unapportioned) - parent_amount)
            if drift > abs(parent_amount) * CHILD_SUM_TOLERANCE + 0.01:
                over_parent_sums.append(
                    "children of {} sum to {:,.2f} and it declares {:,.2f} unapportioned, "
                    "which comes to {:,.2f}, not its total {:,.2f}".format(
                        label(parent), total, float(unapportioned),
                        total + float(unapportioned), parent_amount)
                )
            continue
        if total > parent_amount + abs(parent_amount) * CHILD_SUM_TOLERANCE + allowance + 0.01:
            over_parent_sums.append(
                "children of {} sum to {:,.2f} > {:,.2f}{}".format(
                    label(parent), total, parent_amount, " + declared negative pool {:,.2f}".format(allowance) if allowance else ""
                )
            )
    gate.check("children sum within every parent's total", over_parent_sums)

    # 12. A cost source count is a claim of evidence for the figure. It needs a
    #     source URL, an official rollup on the node, or — for the root only —
    #     the Treasury summary the graph carries.
    unsupported_cost_sources = []
    for node in nodes:
        try:
            cost_sources = int(node.get("costSourceCount") or 0)
        except (TypeError, ValueError):
            cost_sources = 0
        if cost_sources <= 0:
            continue
        urls = node.get("sourceUrls") if isinstance(node.get("sourceUrls"), list) else []
        has_rollup = node.get("rollup_total_amount") is not None
        is_anchor = node is graph and isinstance(graph.get("__budgetSummary"), dict)
        if not (urls or has_rollup or is_anchor):
            unsupported_cost_sources.append(
                "{} claims {} cost source(s) with no sourceUrls and no rollup".format(label(node), cost_sources)
            )
    gate.check("costSourceCount is backed by evidence", unsupported_cost_sources)

    # 9. Root fan-out. 3,438 top-level children was the symptom that started this.
    top_level = graph.get("children") or []
    # The root's children are the three branches of the federal government.
    # A node published beside them claims to be a fourth. "At most 10" was a
    # size check, not a structural one, and it let one through.
    BRANCH_IDS = ("legislative-branch", "executive-branch", "judicial-branch")
    # One exception, by design: the government-wide offsetting receipts the
    # Treasury nets against Total Outlays without assigning them to any
    # branch. It is a Treasury accounting line, not a fourth branch, and it
    # is the only thing allowed beside the three.
    receipts_at_root = [
        c for c in top_level
        if isinstance(c, dict) and str(c.get("synthetic") or "") == "treasury_receipts"
        and str(c.get("id") or "") == "treasury-undistributed-offsetting-receipts"
    ]
    actual_top = tuple(str(c.get("id") or "") for c in top_level if c not in receipts_at_root)
    if len(receipts_at_root) > 1:
        actual_top = actual_top + ("treasury-undistributed-offsetting-receipts",) * (len(receipts_at_root) - 1)
    gate.check(
        "root's children are exactly the three branches",
        ["root has {}, expected {}".format(list(actual_top), list(BRANCH_IDS))] if actual_top != BRANCH_IDS else [],
        " — {}".format(len(top_level)),
    )

    # 13. A verification claim is a fetch that happened: a check date must be a
    # real, past ISO date, and a node that says how it was verified must carry
    # the URL it was verified against. The site draws "checked and failed"
    # from a date without a URL, so that pairing is allowed; a method without
    # a URL is not.
    today = datetime.now(timezone.utc).date().isoformat()
    bad_dates, method_without_url = [], []
    for node in nodes:
        stamp = node.get("lastVerified")
        if stamp is not None:
            text = str(stamp).strip()
            iso_ok = bool(re.match(r"^\d{4}-\d{2}-\d{2}", text))
            if not iso_ok or text[:10] > today:
                bad_dates.append("{} lastVerified {!r}".format(label(node), stamp))
        if node.get("verificationMethod") and not (node.get("sourceUrls") if isinstance(node.get("sourceUrls"), list) else []):
            method_without_url.append(label(node))
    gate.check("every lastVerified is a past ISO date", bad_dates)
    gate.check("every verification method is backed by a source URL", method_without_url)

    # A failed existence check and a source are contradictory claims about the
    # same node; the merge order between the evidence pass and the Treasury
    # pass is exactly what could produce both. And a node is only allowed to
    # call a source official when a .gov/.mil URL is actually there.
    KNOWN_METHODS = {
        "name_labelled_on_own_official_page",
        "name_labelled_on_parent_official_page",
        "name_labelled_on_its_organisations_official_page",
        "listed_in_federal_register_agency_directory",
        "listed_in_senate_committee_list",
        "listed_in_house_clerk_committee_list",
        "listed_in_opm_plum_archive",
        PLUM_CURRENT_METHOD,
        GOVMAN_METHOD,
        GOVMAN_ORG_METHOD,
        GOVMAN_OFFICE_METHOD,
        FR_SIGNATURE_METHOD,
    }
    # Placement claims that rest on reading a page, as opposed to consulting a
    # separate document. Only these are refused on a post; see below.
    PAGE_PLACEMENT_METHODS = {"name_labelled_on_parent_official_page", POST_PAGE_METHOD}
    KNOWN_FAILURES = {"not_found", "not_in_official_list"}
    # Mirrors evidence.UNREAD_KINDS, stdlib-only by design (this file imports
    # nothing from data_pipeline); tests/test_verification.py pins the two equal.
    UNREAD_KINDS = {
        "host_refuses_crawler", "robots_unreachable", "page_not_found",
        "page_below_readable_floor", "site_failing", "network_error", "other",
    }

    def _past_iso(text):
        from datetime import date  # local, as the lastVerified check above does
        try:
            when = date.fromisoformat(str(text or "")[:10])
        except ValueError:
            return False
        return when <= date.today()
    COMMITTEE_LIST_URLS = ("https://www.senate.gov/", "https://clerk.house.gov/")
    failure_beside_source, unofficial_official, unknown_method = [], [], []
    unread_violations = []
    # Kept apart from unknown_method deliberately: a pay defect printed under
    # "every verification method is one this pipeline can produce" would be
    # reported as the wrong kind of fault.
    bad_table_pay = []
    bad_grade_pay = []
    bad_statutory_pay = []
    bad_tier_pay = []
    bad_derived_pay = []
    bad_tier_reference_pay = []
    bad_pay_documents = []
    bad_schedule_pay = []
    bad_reported_pay = []
    bad_usaspending = []
    bad_current_listing = []
    bad_current_pay = []
    for node in nodes:
        urls = [str(u) for u in (node.get("sourceUrls") or []) if str(u).startswith(("http://", "https://"))]
        official = [u for u in urls if urlparse(u).netloc.lower().endswith((".gov", ".mil"))]
        if node.get("verificationFailure") and urls:
            failure_beside_source.append("{} claims {!r} beside {} source(s)".format(label(node), node["verificationFailure"], len(urls)))
        if node.get("verificationFailure") and str(node.get("verificationFailure")) not in KNOWN_FAILURES:
            unknown_method.append("{} verificationFailure {!r}".format(label(node), node.get("verificationFailure")))
        unread = node.get("verificationUnread")
        if unread is not None:
            # A page that went unread, and why. It may sit beside a directory
            # or Manual method (a different document) but never beside a page
            # method, since a page method means a page WAS read; every field
            # has to be the record's, and the host has to be the URL's own.
            if not isinstance(unread, dict):
                unread_violations.append("{} verificationUnread is not an object".format(label(node)))
            else:
                kind = str(unread.get("kind") or "")
                url = str(unread.get("url") or "")
                host = str(unread.get("host") or "")
                if kind not in UNREAD_KINDS:
                    unread_violations.append("{} verificationUnread.kind {!r} is not one this pipeline produces".format(label(node), kind))
                if not url.startswith("https://") and not url.startswith("http://"):
                    unread_violations.append("{} verificationUnread names no URL".format(label(node)))
                elif not urlparse(url).netloc.lower().endswith((".gov", ".mil")):
                    unread_violations.append("{} verificationUnread cites a non-official host {!r}".format(label(node), urlparse(url).netloc))
                if url and host != urlparse(url).netloc.lower():
                    unread_violations.append("{} verificationUnread.host {!r} is not the URL's host".format(label(node), host))
                if not _past_iso(unread.get("checkedAt")):
                    unread_violations.append("{} verificationUnread.checkedAt {!r} is not a past ISO date".format(label(node), unread.get("checkedAt")))
                if str(node.get("verificationMethod") or "").startswith("name_labelled_on_"):
                    unread_violations.append("{} says its page went unread beside a page method {!r}".format(label(node), node.get("verificationMethod")))
                # not_found means the unit's OWN page was read, which "went
                # unread" contradicts. not_in_official_list is a different
                # document -- a complete list that was read -- and a page that
                # could not be read beside it is two true facts, not one lie.
                if str(node.get("verificationFailure") or "") == "not_found":
                    unread_violations.append("{} says its page went unread beside a failed check on that same page".format(label(node)))
        # A confirmation made by setting the committee type words aside says
        # so, quotes the page, and is granted by the node's kind: the rule on
        # anything but a committee, or without the label, or with a label
        # whose core is not the name's, is refused.
        rule = node.get("verificationMatchRule")
        if rule is not None:
            matched_text = node.get("verificationMatchedText")
            if str(rule) == MATCH_RULE_ALIAS:
                # Checked in full by `alias_match_violations` below, against
                # the mirrored table. Here only the two things that tie it to
                # this node's own claim: the label is quoted, and there is an
                # alias block behind the rule.
                if not matched_text:
                    unknown_method.append("{} claims an alias match without quoting the label".format(label(node)))
                if not isinstance(node.get("verificationAliasMatch"), dict):
                    unknown_method.append("{} claims an alias match with no alias block".format(label(node)))
            elif str(rule) != MATCH_RULE_COMMITTEE:
                unknown_method.append("{} verificationMatchRule {!r}".format(label(node), rule))
            elif not is_committee(node):
                unknown_method.append("{} folds committee scaffolding but is typed {!r}".format(label(node), node.get("type")))
            elif not str(node.get("verificationMethod") or "").startswith("name_labelled_on_"):
                unknown_method.append("{} folds committee scaffolding under a method that read no page".format(label(node)))
            elif not matched_text or not folded_label_names(node, matched_text):
                unknown_method.append("{} folded label {!r} does not name it".format(label(node), matched_text))
        elif node.get("verificationMatchedText") is not None and not is_post(node):
            unknown_method.append("{} quotes a folded label without the rule".format(label(node)))
        # A post confirmed on its organisation's page. Four things are
        # required, and each of them failed at least once in development or
        # would have published something false:
        #   - the node is actually a post. The method's whole justification is
        #     that the page belongs to the post's organisation rather than to
        #     the post; on an organisation it would be a plain parent-page
        #     claim wearing a stronger name.
        #   - the label is quoted. "General Counsel" sits at 84 organisations
        #     and "Inspector General" at 72, so without the text a reader
        #     cannot tell this node's confirmation from another's.
        #   - the label still names the node. Same guard the committee fold
        #     gets: a rename must not inherit a badge earned by another name.
        #   - the match came from the page's body. A job title in site-wide
        #     chrome is the one match this design refuses, and a record that
        #     arrived saying `navigation` would be publishing exactly that.
        if str(node.get("verificationMethod") or "") == POST_PAGE_METHOD:
            matched_text = node.get("verificationMatchedText")
            if not is_post(node):
                unknown_method.append(
                    "{} claims a post's page method but is typed {!r}".format(label(node), node.get("type")))
            elif not matched_text:
                unknown_method.append("{} claims a post's page method without quoting the label".format(label(node)))
            elif not label_names(node, matched_text):
                unknown_method.append("{} post label {!r} does not name it".format(label(node), matched_text))
            elif str(node.get("verificationMatchedIn") or "") != "content":
                unknown_method.append(
                    "{} confirms a post from {!r}, not the page's content".format(
                        label(node), node.get("verificationMatchedIn")))
        if is_post(node) and str(node.get("placementMethod") or "") in PAGE_PLACEMENT_METHODS:
            # One fetch, one claim. The page that names a post is its
            # organisation's, and that read is already published as the
            # post's existence; recording it again as evidence for the edge
            # would present a single observation as two corroborating
            # findings. A placement from a different source is not affected —
            # OPM's PLUM archive filing a post under an organisation is a
            # second document, and 126 positions carry exactly that.
            unknown_method.append(
                "{} is a post whose placement rests on the same page read as its existence".format(label(node)))
        # A negative must be as auditable as a positive: it names the page or
        # the list it was checked against, and when. The panel prints that URL.
        failure_kind = str(node.get("verificationFailure") or "")
        if failure_kind:
            src = node.get("verificationFailureSource") if isinstance(node.get("verificationFailureSource"), dict) else {}
            src_url = str(src.get("url") or "")
            src_host = host_of(src_url)
            src_date = str(src.get("checkedAt") or "")
            if failure_kind == "not_in_official_list" and not src_url.startswith(COMMITTEE_LIST_URLS):
                unknown_method.append("{} claims not_in_official_list without the list's URL".format(label(node)))
            elif failure_kind == "not_found" and not src_host.endswith((".gov", ".mil")):
                unknown_method.append("{} claims its own page did not name it, without naming the page".format(label(node)))
            if not re.match(r"^\d{4}-\d{2}-\d{2}", src_date) or src_date[:10] > today:
                unknown_method.append("{} claims a failed check without a past date ({!r})".format(label(node), src_date))
        # An official headcount is a sourced number beside an uncited one; it
        # needs the file, the period and a past date, or it is just another
        # uncited number with a better name. The coverage sentence is
        # required too: the population is what makes it comparable at all.
        official_headcount = node.get("employeesOfficial")
        if official_headcount is not None:
            src = node.get("employeesOfficialSource") if isinstance(node.get("employeesOfficialSource"), dict) else {}
            src_url = str(src.get("url") or "")
            src_host = host_of(src_url)
            src_date = str(src.get("checkedAt") or "")
            if not isinstance(official_headcount, int) or official_headcount < 0:
                unknown_method.append("{} employeesOfficial {!r}".format(label(node), official_headcount))
            if not src_host.endswith((".gov", ".mil")) or not src.get("period") or not src.get("coverage"):
                unknown_method.append("{} claims an official headcount without a .gov file, a period and its coverage".format(label(node)))
            if not re.match(r"^\d{4}-\d{2}-\d{2}", src_date) or src_date[:10] > today:
                unknown_method.append("{} claims an official headcount without a past date ({!r})".format(label(node), src_date))
        # A position listing is a record of the archive's period, never of now.
        listing = node.get("positionListing")
        if listing is not None:
            if not isinstance(listing, dict):
                unknown_method.append("{} positionListing {!r}".format(label(node), listing))
            else:
                l_url = str(listing.get("url") or "")
                l_host = host_of(l_url)
                l_date = str(listing.get("checkedAt") or "")
                if not l_host.endswith((".gov", ".mil")) or not listing.get("edition"):
                    unknown_method.append("{} claims a position listing without a .gov file and the edition it came from".format(label(node)))
                if not re.match(r"^\d{4}-\d{2}-\d{2}", l_date) or l_date[:10] > today:
                    unknown_method.append("{} claims a position listing without a past date ({!r})".format(label(node), l_date))
                # The archive's LevelGradePay column is a rank for some rows
                # and a rate of basic pay for others. Once split, neither may
                # hold the other's kind of value: a rank that is a dollar
                # figure was the wrong claim about the right number, and a
                # rate that is not a positive number is not a rate at all.
                pay_level = listing.get("payLevel")
                if pay_level is not None and (not isinstance(pay_level, str) or "$" in pay_level):
                    unknown_method.append("{} publishes {!r} as a pay level".format(label(node), pay_level))
                reported_pay = listing.get("reportedPay")
                if reported_pay is not None:
                    if isinstance(reported_pay, bool) or not isinstance(reported_pay, (int, float)) or reported_pay <= 0:
                        unknown_method.append("{} publishes {!r} as a reported rate of pay".format(label(node), reported_pay))
                    elif "$" not in str(listing.get("reportedPayText") or ""):
                        unknown_method.append("{} reports pay without the text the archive prints".format(label(node)))
        # OPM's CURRENT PLUM export: a second listing beside the archive's,
        # re-read from the committed file by the block's own keys, and the
        # rate that export prints for the one row under the title.
        current_listing = node.get("positionCurrentListing")
        if current_listing is not None:
            _parent_id = tree_parents.get(str(node.get("id") or ""))
            bad_current_listing.extend(current_listing_violations(
                node, current_listing, today, label, name_by_id.get(_parent_id),
                alias_keys_for(_parent_id, by_id)))
        current_pay = node.get("positionCurrentPay")
        if current_pay is not None:
            bad_current_pay.extend(current_pay_violations(node, current_pay, current_listing, today, label))
        if str(node.get("placementMethod") or "") == PLUM_CURRENT_PLACEMENT_METHOD and not isinstance(current_listing, dict):
            bad_current_listing.append("{} claims a placement from the current PLUM export with no listing from it".format(label(node)))
        # Which listing a salary-table join hangs off: the one its own claim
        # names (positions.LISTING_FIELD_BY_SOURCE, mirrored here), so a rate
        # looked up for the current export's level is checked against the
        # current listing and never the archive's. A rate stated by the OTHER
        # listing is refused too: two figures for one post.
        listings_by_source = {"opm_plum_archive": listing, PLUM_CURRENT_SOURCE: current_listing}

        def _other_listing_states_a_rate(chosen):
            return any(
                isinstance(l, dict) and isinstance(l.get("reportedPay"), (int, float))
                for source, l in listings_by_source.items() if source != chosen
            )

        # A rate looked up from the salary table for the level the archive
        # reports. Two documents, neither of which says what this post pays: the
        # checks below are what keep the join from being read as one source.
        pay = node.get("positionPayRate")
        if pay is not None:
            level_source = pay.get("levelSource") if isinstance(pay, dict) and isinstance(pay.get("levelSource"), dict) else {}
            chosen = str(level_source.get("source") or "opm_plum_archive")
            bad_table_pay.extend(table_pay_violations(node, pay, listings_by_source.get(chosen), today, label))
            if _other_listing_states_a_rate(chosen):
                bad_table_pay.append("{} carries a table rate beside a rate a PLUM listing states; two rates for one post".format(label(node)))
        # A base-pay RANGE for the pay plan or grade the archive reports:
        # the same two-document join, a different shape of claim (two bounds
        # and no figure for the post), its own field and its own mirror.
        grade_pay = node.get("positionGradePay")
        if grade_pay is not None:
            listing_source = grade_pay.get("listingSource") if isinstance(grade_pay, dict) and isinstance(grade_pay.get("listingSource"), dict) else {}
            chosen = str(listing_source.get("source") or "opm_plum_archive")
            bad_grade_pay.extend(grade_pay_violations(node, grade_pay, listings_by_source.get(chosen), today, label))
            if _other_listing_states_a_rate(chosen):
                bad_grade_pay.append("{} carries a table range beside a rate a PLUM listing states; two figures for one post".format(label(node)))
        # A single-source statutory rate — judicial or congressional — beside
        # the two-source join above; a different field, a different set of
        # rules, checked against its own mirror.
        statutory_pay = node.get("positionStatutoryPay")
        if statutory_pay is not None:
            bad_statutory_pay.extend(statutory_pay_violations(
                node, statutory_pay, today, label,
                tree_parents=tree_parents, type_by_id=type_by_id, name_by_id=name_by_id))
        # A pay-schedule TIER band: the VA's Title 38 ranges, which name a
        # title and state bounds rather than a rate. Its parent is read off
        # the tree the gate is walking, never off `parentId`, because both of
        # its match rules are scope rules about that parent.
        tier_pay = node.get("positionTierPay")
        if tier_pay is not None:
            _tier_parent = tree_parents.get(str(node.get("id") or ""))
            bad_tier_pay.extend(tier_pay_violations(node, tier_pay, today, label, name_by_id.get(_tier_parent)))
        # The one figure in this project no document states: a parity
        # provision names the tier, the compensation table prices it. Checked
        # against the section's own current sentence, mirrored by node id,
        # and required to publish its document count and what that count is
        # worth on this project's own scale.
        derived_pay = node.get("positionDerivedPay")
        if derived_pay is not None:
            bad_derived_pay.extend(derived_pay_violations(node, derived_pay, today, label))
        # A rate set by REFERENCE to an Executive Schedule level: the GAO's
        # officers by node id, and an establishment's Inspector General by
        # 5 U.S.C. 401's own list, scoped to the parent the tree gives it.
        tier_reference_pay = node.get("positionTierReferencePay")
        if tier_reference_pay is not None:
            _reference_parent = tree_parents.get(str(node.get("id") or ""))
            bad_tier_reference_pay.extend(tier_reference_pay_violations(
                node, tier_reference_pay, today, label, name_by_id.get(_reference_parent)))
        # And, on every pay field alike, how many documents the figure rests
        # on: recomputed from the URLs the block itself carries, so a count
        # is a fact about the block rather than a number somebody wrote down.
        for _pay_field in PAY_DOCUMENT_URL_KEYS:
            _pay_block = node.get(_pay_field)
            if isinstance(_pay_block, dict):
                bad_pay_documents.extend(pay_document_violations(node, _pay_field, _pay_block, label))
        # The same Executive Schedule rate from the other direction: current
        # law names the level, OPM's table prices it. Its own field and its
        # own mirror, keyed by node id.
        schedule_pay = node.get("positionSchedulePay")
        if schedule_pay is not None:
            bad_schedule_pay.extend(schedule_pay_violations(
                node, schedule_pay, today, label,
                tree_parent=tree_parents.get(str(node.get("id") or "")), tree_parents=tree_parents))
        # A roster row — what one listed person is paid — beside both of the
        # above; again its own field, its own mirror, its own rules.
        reported_pay = node.get("positionReportedPay")
        if reported_pay is not None:
            bad_reported_pay.extend(reported_pay_violations(node, reported_pay, today, label))
        # File A gross outlays, in a block of their own beside the cost.
        usaspending = node.get("usaspendingOutlays")
        if usaspending is not None:
            bad_usaspending.extend(usaspending_violations(node, usaspending, today, label))
        # The same, for a page read that did not name the node and stands
        # beside a directory listing that did.
        read_not_named = node.get("pageReadNotNamed")
        if read_not_named is not None:
            if not isinstance(read_not_named, dict):
                unknown_method.append("{} pageReadNotNamed {!r}".format(label(node), read_not_named))
            else:
                rn_url = str(read_not_named.get("url") or "")
                rn_host = host_of(rn_url)
                rn_date = str(read_not_named.get("checkedAt") or "")
                if not rn_host.endswith((".gov", ".mil")) or not re.match(r"^\d{4}-\d{2}-\d{2}", rn_date) or rn_date[:10] > today:
                    unknown_method.append("{} records a page read that did not name it, without a .gov URL and a past date".format(label(node)))
        if "official_site" in (node.get("sourceTypes") or []) and not official:
            unofficial_official.append("{} claims an official source with no .gov/.mil URL".format(label(node)))
        method = node.get("verificationMethod")
        if method and str(method) not in KNOWN_METHODS:
            unknown_method.append("{} verificationMethod {!r}".format(label(node), method))
        region = node.get("verificationMatchedIn")
        if region is not None and str(region) not in ("navigation", "content"):
            unknown_method.append("{} verificationMatchedIn {!r}".format(label(node), region))
    # Placement: evidence for the parent -> child edge. A True claim must carry
    # an official URL and a date, and must name the parent the published tree
    # actually gives the node — evidence for a different edge is not evidence.
    placement_unbacked, placement_wrong_parent = [], []
    parent_of = {}
    by_id = {}
    stack_p = [(graph, None)]
    while stack_p:
        n, p = stack_p.pop()
        parent_of[str(n.get("id") or "")] = p
        by_id[str(n.get("id") or "")] = n
        for c in n.get("children", []) or []:
            if isinstance(c, dict):
                stack_p.append((c, str(n.get("id") or "")))
    for node in nodes:
        if node.get("placementVerified") is False:
            # "Read and not listed" is a statement about one parent's page on
            # one date; it must name the parent the tree has and a real date.
            stamp = str(node.get("placementVerifiedAt") or "")
            if not re.match(r"^\d{4}-\d{2}-\d{2}", stamp) or stamp[:10] > today:
                placement_unbacked.append("{} placementVerified false at {!r}".format(label(node), stamp))
            claimed = str(node.get("placementParentId") or "")
            actual = parent_of.get(str(node.get("id") or ""))
            if not claimed or claimed != actual:
                placement_wrong_parent.append("{} not-listed claims parent {!r}, tree has {!r}".format(label(node), claimed, actual))
        if node.get("placementVerified") is not None and node.get("placementCheckable") is False:
            placement_unbacked.append("{} says its placement could not be checked beside a placement result".format(label(node)))
        if node.get("placementVerified") is not True:
            continue
        url = str(node.get("placementUrl") or "")
        host = host_of(url)
        stamp = str(node.get("placementVerifiedAt") or "")
        if not host.endswith((".gov", ".mil")) or not re.match(r"^\d{4}-\d{2}-\d{2}", stamp) or stamp[:10] > today:
            placement_unbacked.append("{} placementUrl {!r} at {!r}".format(label(node), url, stamp))
        if str(node.get("placementMethod") or "") not in (
            "name_labelled_on_parent_official_page",
            "listed_under_parent_in_federal_register_agency_directory",
            GOVMAN_ORG_PLACEMENT_METHOD,
            "listed_under_committee_in_senate_committee_list",
            "listed_under_committee_in_house_clerk_committee_list",
            "listed_under_organization_in_opm_plum_archive",
            PLUM_CURRENT_PLACEMENT_METHOD,
        ):
            placement_unbacked.append("{} placementMethod {!r}".format(label(node), node.get("placementMethod")))
        matched = canonical_key(node.get("placementMatchedText"))
        name_key = canonical_key(node.get("name"))
        if str(node.get("placementMethod") or "") in ("listed_under_committee_in_senate_committee_list", "listed_under_committee_in_house_clerk_committee_list"):
            matched = list_subcommittee_key(matched)
            name_key = list_subcommittee_key(name_key)
        if str(node.get("placementMethod") or "") in ("listed_under_organization_in_opm_plum_archive", PLUM_CURRENT_PLACEMENT_METHOD):
            # A curated position name legitimately carries the parent's own
            # name or acronym ("Director, AHRQ" under AHRQ), and may offer
            # alternatives ("Director / Administrator / Chair"). The plain
            # substring test would refuse 25 of the 91 real matches, so the
            # gate mirrors the module's rule; a test pins the two together.
            # ANY alternative the text carries counts ("Deputy Director / Vice
            # Chair" is named by "DEPUTY DIRECTOR"), and the current export's
            # HTML entities are resolved first ("&amp;" is the file's "&").
            import html as _html

            matched = canonical_key(_html.unescape(str(node.get("placementMatchedText") or "")))
            keys = position_title_keys(node.get("name"), parent_name_of(node, parent_of, by_id))
            name_key = next((k for k in sorted(keys, key=len) if k in matched), min(keys, key=len, default=name_key))
        placement_rule = node.get("placementMatchRule")
        if placement_rule is not None:
            if str(placement_rule) != MATCH_RULE_COMMITTEE:
                placement_unbacked.append("{} placementMatchRule {!r}".format(label(node), placement_rule))
            elif not is_committee(node):
                placement_unbacked.append("{} folds committee scaffolding for placement but is typed {!r}".format(label(node), node.get("type")))
            elif str(node.get("placementMethod") or "") != "name_labelled_on_parent_official_page":
                placement_unbacked.append("{} folds committee scaffolding under a placement method that read no page".format(label(node)))
        if matched and name_key and name_key not in matched and name_key not in directory_name_keys(node.get("placementMatchedText")):
            # The fold is allowed only where the node says it used it, and only
            # for a committee: a mismatch anywhere else is still a mismatch.
            if not (placement_rule == MATCH_RULE_COMMITTEE and folded_label_names(node, node.get("placementMatchedText"))):
                placement_unbacked.append("{} placement text {!r} does not name it".format(label(node), node.get("placementMatchedText")))
        if node.get("placementMatchedIn") is not None and str(node.get("placementMatchedIn")) not in ("navigation", "content"):
            placement_unbacked.append("{} placementMatchedIn {!r}".format(label(node), node.get("placementMatchedIn")))
        claimed = str(node.get("placementParentId") or "")
        actual = parent_of.get(str(node.get("id") or ""))
        if not claimed or claimed != actual:
            placement_wrong_parent.append("{} claims parent {!r}, tree has {!r}".format(label(node), claimed, actual))
    gate.check("every placement claim has an official URL and a date", placement_unbacked)
    gate.check("every placement claim names the parent the tree actually has", placement_wrong_parent)

    gate.check("no node claims a failed check beside a source", failure_beside_source)
    gate.check("an unread page says which host, why, and when, and never beside a page method", unread_violations)
    gate.check("an official source type has a .gov/.mil URL behind it", unofficial_official)
    gate.check("every verification method is one this pipeline can produce", unknown_method)
    gate.check("a salary-table rate names a level the archive still reports and the rate that table prints", bad_table_pay)
    gate.check("a base-pay range names the pay plan and grade the archive still reports and the bounds that table prints", bad_grade_pay)
    gate.check("a statutory pay rate is the mirrored source's own figure for the tier or role it names", bad_statutory_pay)
    gate.check("a pay-schedule tier band is the schedule's own bounds for the title it names, and is never a rate", bad_tier_pay)
    gate.check(
        "a derived rate names both documents, neither of which states it, and prices the tier its own statute does",
        bad_derived_pay,
    )
    gate.check(
        "a rate set by reference to an Executive Schedule level is the table's rate for the level its statute names, "
        "an Inspector General's only under an establishment 5 U.S.C. 401 lists, with its arithmetic in the open",
        bad_tier_reference_pay,
    )
    gate.check(
        "every pay figure says how many documents it rests on, counted from the URLs it carries",
        bad_pay_documents,
    )
    # A counted class prices at most N members across the WHOLE graph: the
    # Code says how many such offices exist, and a graph carrying more nodes
    # priced as members than the Code counts is wrong about at least one.
    _counted_members = Counter()
    for _n in nodes:
        _sp = _n.get("positionSchedulePay")
        if isinstance(_sp, dict) and isinstance(_sp.get("countedClass"), dict):
            _counted_members[str(_sp["countedClass"].get("codeTitle") or "")] += 1
    for _title, _members in sorted(_counted_members.items()):
        _found = re.search(r"\((\d+)\)", _title)
        if _found and _members > int(_found.group(1)):
            bad_schedule_pay.append("counted class {!r}: {} nodes are priced as members; the Code counts {}".format(
                _title, _members, _found.group(1)))
    gate.check("an Executive Schedule rate names the post the U.S. Code names, at the level the Code sets", bad_schedule_pay)
    gate.check("a reported pay rate is the roster's own figure for the title it names, and never zero", bad_reported_pay)
    gate.check("a File A gross outlay is the fixture's own figure for the key it names, dated, and never the cost", bad_usaspending)
    gate.check("a current PLUM listing is a Filled or Vacant row of the committed export, filed under the node's own parent, naming it", bad_current_listing)
    gate.check("a current PLUM rate is the row's own printed figure for the listing beneath it, a proxy, never zero and never a cost", bad_current_pay)

    # A published disagreement is a claim like any other: it must name both
    # figures, sit on the estimate it actually affected, and be a real
    # disagreement. An empty or self-agreeing dispute block would read as a
    # caveat where there is none.
    bad_dispute = []
    for node in nodes:
        dispute = node.get("cost_weight_dispute")
        if dispute is None:
            continue
        if not isinstance(dispute, dict):
            bad_dispute.append("{} cost_weight_dispute is a {}".format(label(node), type(dispute).__name__))
            continue
        curated = dispute.get("curatedEmployeesParsed")
        official = dispute.get("officialEmployees")
        if not isinstance(curated, (int, float)) or isinstance(curated, bool) or curated <= 0:
            bad_dispute.append("{} dispute has no curated figure".format(label(node)))
            continue
        if not isinstance(official, (int, float)) or isinstance(official, bool) or official <= 0:
            bad_dispute.append("{} dispute has no official figure".format(label(node)))
            continue
        if official != node.get("employeesOfficial"):
            bad_dispute.append("{} dispute cites {!r}, the node carries {!r}".format(
                label(node), official, node.get("employeesOfficial")))
        if abs(curated - official) / official <= 0.10:
            bad_dispute.append("{} dispute between {} and {} is within 10%".format(label(node), curated, official))
        if str(node.get("cost_status") or "") != "allocated" or str(node.get("cost_basis") or "") != "employee_weight":
            bad_dispute.append("{} dispute on a {!r} cost with basis {!r}".format(
                label(node), node.get("cost_status"), node.get("cost_basis")))
        if not str(dispute.get("url") or "").startswith("https://"):
            bad_dispute.append("{} dispute has no source URL".format(label(node)))
    gate.check("every published weight dispute names both figures and is one", bad_dispute)

    # A measured cost belongs to an organisation. An outside review of an
    # older checkout of this project reported $463.2M of the Comptroller of
    # the Currency's outlays published on a node typed Position; that is not
    # true on this graph — apply_treasury_outlay_rows has excluded position,
    # committee, role and caucus types from name matching, and none of the
    # measured nodes is one — but nothing here forbade it, so a re-fed payload
    # or a future change could reintroduce exactly that. A Treasury line names
    # an organisation's outlays; publishing one as a post's cost would be a
    # measured figure about the wrong kind of thing.
    non_org_measured = []
    for node in nodes:
        if str(node.get("cost_status") or "") not in ("official", "scaled_official"):
            continue
        type_text = str(node.get("type") or "").casefold()
        if any(word in type_text for word in ("position", "role", "committee", "caucus", "office holder")):
            non_org_measured.append("{} is a {!r} carrying a measured cost".format(label(node), node.get("type")))
    gate.check("a measured cost sits only on an organisation", non_org_measured)

    # A unit the government has replaced. Nothing is deleted, so the site keeps
    # drawing it for anyone who asks — which makes the claim "this no longer
    # exists" a published claim like any other, and it needs a source that says
    # so in words the page really carries. It also must not be holding a share
    # of this year's money: the cascade takes a superseded node out of the
    # sibling weights entirely, and a share on one would mean that failed.
    superseded_violations = []
    node_ids = {str(n.get("id") or "") for n in nodes}
    for node in nodes:
        if str(node.get("lifecycle") or "") != "superseded":
            for field in ("supersededOn", "supersededBy", "supersededSource"):
                if node.get(field) is not None:
                    superseded_violations.append(
                        "{} carries {} without being marked superseded".format(label(node), field))
            continue
        source = node.get("supersededSource") or {}
        url = str(source.get("url") or "")
        if not (url.startswith("https://") and (".gov" in url or ".mil" in url)):
            superseded_violations.append("{} cites {!r}, not an official page".format(label(node), url))
        if not str(source.get("quote") or "").strip():
            superseded_violations.append("{} quotes nothing from its source".format(label(node)))
        on = str(node.get("supersededOn") or "")
        if not (len(on) == 10 and on[:4].isdigit() and on <= today):
            superseded_violations.append("{} gives supersededOn {!r}, not a past ISO date".format(label(node), on))
        for replacement in node.get("supersededBy") or []:
            if str(replacement) not in node_ids:
                superseded_violations.append(
                    "{} says it was replaced by {}, which is not a node".format(label(node), replacement))
        if str(node.get("cost_status") or "") == "allocated":
            superseded_violations.append(
                "{} is superseded and still carries an apportioned share".format(label(node)))
    gate.check("a superseded unit says who replaced it and holds no share", superseded_violations)

    # Treasury's audited Statement of Net Cost, published beside the cost and
    # never as it. The figure is re-derived here from the committed fixture --
    # digest recomputed from the bytes, the row found by the agency name the
    # block quotes -- so a block cannot carry a number the statement does not
    # print. It is audited ACCRUAL cost for a fiscal year that has ended, and
    # the graph's measured figure is cash outlays for the year to date, so a
    # block whose amount equals the node's cost to the cent means the two have
    # been confused and is refused outright.
    net_cost_violations = []
    net_cost_rows = {}
    net_cost_digest = None
    net_cost_path = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "treasury" / "net_cost" / "statement_net_cost_2025-09-30.json"
    try:
        import hashlib as _hashlib
        raw = net_cost_path.read_bytes()
        net_cost_digest = _hashlib.sha256(raw).hexdigest()
        payload = json.loads(raw.decode("utf-8"))
        rows = [r for r in (payload.get("data") or []) if isinstance(r, dict)]
        latest = max((str(r.get("stmt_fiscal_year") or "") for r in rows), default="")
        for row in rows:
            if str(row.get("stmt_fiscal_year") or "") == latest and str(row.get("restmt_flag") or "").upper() == "N":
                net_cost_rows[canonical_key(str(row.get("agency_nm") or ""))] = row
    except (OSError, ValueError) as error:
        net_cost_violations.append("the Statement of Net Cost fixture could not be read: {}".format(error))

    for node in nodes:
        block = node.get("auditedNetCost")
        if not isinstance(block, dict):
            continue
        type_text = str(node.get("type") or "").casefold()
        if any(word in type_text for word in ("position", "role", "office holder")):
            net_cost_violations.append("{} is a post carrying an audited net cost".format(label(node)))
            continue
        quoted = str(block.get("agencyName") or "")
        if canonical_key(quoted) != canonical_key(str(node.get("name") or "")):
            net_cost_violations.append(
                "{} carries a block naming {!r}, which is not this node's name".format(label(node), quoted))
            continue
        if net_cost_digest and str(block.get("documentSha256") or "") != net_cost_digest:
            net_cost_violations.append(
                "{} cites a document digest the committed statement does not have".format(label(node)))
        row = net_cost_rows.get(canonical_key(quoted))
        if row is None:
            if net_cost_rows:
                net_cost_violations.append(
                    "{} quotes {!r}, which the statement does not report".format(label(node), quoted))
            continue
        try:
            printed = round(float(row.get("net_cost_bil_amt")) * 1000000000, 2)
        except (TypeError, ValueError):
            printed = None
        if printed is None or abs(float(block.get("netCostUsd") or 0) - printed) > 0.01:
            net_cost_violations.append(
                "{} publishes {} where the statement prints {}".format(
                    label(node), block.get("netCostUsd"), printed))
        if not str(block.get("fiscalYear") or "").strip() or not str(block.get("statementDate") or "").strip():
            net_cost_violations.append("{}'s audited figure does not say which year it covers".format(label(node)))
        if not str(block.get("unitsEvidenceKind") or "").strip():
            net_cost_violations.append("{}'s audited figure does not say how its unit is known".format(label(node)))
        amount = node.get("resolved_total_amount")
        if isinstance(amount, (int, float)) and abs(float(amount) - float(block.get("netCostUsd") or 0)) < 0.01:
            net_cost_violations.append(
                "{} publishes its audited net cost as its cost — different basis, different period".format(label(node)))
    gate.check("an audited net cost is the statement's own figure, and never the cost", net_cost_violations)

    # The Government Manual's listing of a post, re-derived from the committed
    # package rather than trusted. The block quotes an agency and a title; the
    # check is that the Manual really prints that title in that agency's own
    # leadership table, that the node is still the post it was matched as, and
    # that the agency is still the node's parent -- read off the tree the gate
    # is walking, never off `parentId`, which is stamped on the exported node
    # list alone and would make the placement half of this check pass
    # vacuously. `General Counsel` names 84 nodes here and `Inspector General`
    # 72, so a record moved to another node keeps a real title, a real agency
    # and a real URL, and only the parent tells them apart.
    govman_violations = []
    govman_index = {}
    try:
        govman_index = govman_entries()
    except (OSError, ValueError) as error:
        govman_violations.append("the Government Manual fixture could not be read: {}".format(error))
    for node in nodes:
        block_data = node.get("govmanListing")
        if not isinstance(block_data, dict):
            continue
        type_text = str(node.get("type") or "").casefold()
        if not any(word in type_text for word in ("position", "role", "office holder")):
            govman_violations.append("{} is not a post but carries a Government Manual listing".format(label(node)))
            continue
        granule = str(block_data.get("granule") or "")
        entry = govman_index.get(granule)
        if govman_index and entry is None:
            govman_violations.append(
                "{} cites granule {!r}, which the committed Manual does not carry".format(label(node), granule))
            continue
        listed_under = str(block_data.get("listedUnder") or "")
        listed_title = str(block_data.get("listedTitle") or "")
        if entry is not None:
            agency, titles = entry
            if canonical_key(listed_under) != canonical_key(agency):
                govman_violations.append(
                    "{} cites {!r} under granule {}, which the Manual names {!r}".format(
                        label(node), listed_under, granule, agency))
                continue
            printed = titles.get(canonical_key(listed_title)) or []
            if not printed:
                govman_violations.append(
                    "{} quotes {!r}, which is not a title the Manual prints on its own face in {}".format(
                        label(node), listed_title, agency))
                continue
            if len(printed) > 1:
                govman_violations.append(
                    "{} quotes {!r}, which {} prints {} times -- it identifies no single row".format(
                        label(node), listed_title, agency, len(printed)))
                continue
        if canonical_key(node.get("name")) != canonical_key(listed_title):
            govman_violations.append(
                "{} carries a listing quoting {!r}, which is not this node's name".format(label(node), listed_title))
            continue
        parent_id = tree_parents.get(str(node.get("id") or "")) or ""
        parent = by_id.get(parent_id)
        parent_names = ({canonical_key(parent.get("name"))} | alias_keys_for(parent_id, by_id)) if parent is not None else set()
        if canonical_key(listed_under) not in parent_names:
            govman_violations.append(
                "{} was listed under {!r}, which is not the organisation the tree gives it".format(
                    label(node), listed_under))
            continue
        expected_url = "{}/{}/{}".format(GOVMAN_DETAILS, GOVMAN_PACKAGE, granule)
        if str(block_data.get("url") or "") != expected_url:
            govman_violations.append(
                "{} cites {!r}, which is not the Manual entry for granule {}".format(
                    label(node), block_data.get("url"), granule))
            continue
        edition = str(block_data.get("edition") or "")
        if not (len(edition) == 10 and edition[:4].isdigit() and edition <= today):
            govman_violations.append(
                "{} carries a Manual edition of {!r}".format(label(node), edition))
            continue
        if expected_url not in [str(u) for u in (node.get("sourceUrls") or [])]:
            govman_violations.append("{} cites the Manual without carrying its URL".format(label(node)))
            continue
        # One document was read and it yields one observation. Publishing
        # existence and placement from it would present a single finding as
        # two corroborating ones -- the rule a post confirmed on its own
        # organisation's page already follows.
        if str(node.get("placementMethod") or "").find("government_manual") >= 0:
            govman_violations.append(
                "{} claims placement from the Government Manual, which reads one entry".format(label(node)))
    gate.check("a Government Manual listing is a title that entry really prints", govman_violations)
    # The organisation route: an entry for the unit itself. Mirrors the post
    # block's discipline -- granule in the manifest, name as the Manual prints
    # it, the publisher's own URL -- and adds the hierarchy: the parent the
    # block quotes must be the one the independent parse finds around that
    # entry, and a placement claimed from it must name the parent the TREE
    # gives the node, read off the tree the gate is walking.
    govman_org_violations = []
    try:
        govman_parent_index = govman_parents()
    except (OSError, ValueError) as error:
        govman_parent_index = {}
        govman_org_violations.append("the Government Manual fixture could not be read: {}".format(error))
    for node in nodes:
        entry_block = node.get("govmanEntry")
        method_is_manual = str(node.get("verificationMethod") or "") == GOVMAN_ORG_METHOD
        if not isinstance(entry_block, dict):
            if method_is_manual:
                govman_org_violations.append("{} takes the Manual as its method and carries no entry block".format(label(node)))
            if str(node.get("placementMethod") or "") == GOVMAN_ORG_PLACEMENT_METHOD:
                govman_org_violations.append("{} is placed by the Manual and carries no entry block".format(label(node)))
            continue
        if is_post(node):
            govman_org_violations.append("{} is a post but carries a Government Manual entry of its own".format(label(node)))
            continue
        granule = str(entry_block.get("granule") or "")
        entry = govman_index.get(granule)
        if govman_index and entry is None:
            govman_org_violations.append("{} cites granule {!r}, which the committed Manual does not carry".format(label(node), granule))
            continue
        listed_name = str(entry_block.get("listedName") or "")
        if entry is not None and canonical_key(listed_name) != canonical_key(entry[0]):
            govman_org_violations.append("{} quotes {!r} for granule {}, which the Manual names {!r}".format(label(node), listed_name, granule, entry[0]))
            continue
        if canonical_key(listed_name) not in ({canonical_key(node.get("name"))} | alias_keys_for(node.get("id"), by_id)):
            govman_org_violations.append("{} carries an entry for {!r}, which is not this node's name".format(label(node), listed_name))
            continue
        expected_url = "{}/{}/{}".format(GOVMAN_DETAILS, GOVMAN_PACKAGE, granule)
        if str(entry_block.get("url") or "") != expected_url:
            govman_org_violations.append("{} cites {!r}, not the publisher's own address {!r}".format(label(node), entry_block.get("url"), expected_url))
            continue
        if not _past_iso(entry_block.get("edition")):
            govman_org_violations.append("{} cites a Manual edition {!r} that has not happened".format(label(node), entry_block.get("edition")))
            continue
        parent_listed = entry_block.get("parentListedName")
        if govman_parent_index and granule in govman_parent_index:
            printed_parent = govman_parent_index.get(granule)
            if canonical_key(str(parent_listed or "")) != canonical_key(str(printed_parent or "")):
                govman_org_violations.append("{} says the Manual files it under {!r}; the Manual files it under {!r}".format(label(node), parent_listed, printed_parent))
                continue
        if str(node.get("placementMethod") or "") == GOVMAN_ORG_PLACEMENT_METHOD:
            tree_parent = by_id.get(tree_parents.get(str(node.get("id") or "")) or "")
            if not parent_listed or tree_parent is None or canonical_key(tree_parent.get("name")) != canonical_key(str(parent_listed)):
                govman_org_violations.append("{} is placed by the Manual under {!r}, which is not the parent the tree gives it".format(label(node), parent_listed))
                continue
            if str(node.get("placementUrl") or "") != expected_url:
                govman_org_violations.append("{} is placed by the Manual but cites {!r} for it".format(label(node), node.get("placementUrl")))
                continue
    gate.check("a Government Manual entry names this unit, its parent as the Manual prints it, and places it only under that parent", govman_org_violations)
    # The narrow third route: a TOP-LEVEL Manual entry that IS an office.
    # Everything the organisation check asks, plus the three things that
    # make this route what it is -- the node is a post, the entry is
    # top-level (the Manual prints no parent for it), and no placement is
    # ever claimed from it, because one entry was read and it yields one
    # observation.
    govman_office_violations = []
    for node in nodes:
        block = node.get("govmanOfficeEntry")
        method_is_office = str(node.get("verificationMethod") or "") == GOVMAN_OFFICE_METHOD
        if not isinstance(block, dict):
            if method_is_office:
                govman_office_violations.append("{} takes a Manual office entry as its method and carries no block".format(label(node)))
            continue
        if not is_post(node):
            govman_office_violations.append("{} is not a post but carries a Manual office entry".format(label(node)))
            continue
        granule = str(block.get("granule") or "")
        entry = govman_index.get(granule)
        if govman_index and entry is None:
            govman_office_violations.append("{} cites granule {!r}, which the committed Manual does not carry".format(label(node), granule))
            continue
        listed_name = str(block.get("listedName") or "")
        if entry is not None and canonical_key(listed_name) != canonical_key(entry[0]):
            govman_office_violations.append("{} quotes {!r} for granule {}, which the Manual names {!r}".format(label(node), listed_name, granule, entry[0]))
            continue
        if govman_parent_index and canonical_key(str(govman_parent_index.get(granule) or "")):
            govman_office_violations.append("{} claims a top-level office entry the Manual files under {!r}".format(label(node), govman_parent_index.get(granule)))
            continue
        matched = str(block.get("matchedName") or "")
        recorded = NODE_ALIASES.get(str(node.get("id") or ""))
        allowed_names = {canonical_key(node.get("name"))}
        if recorded:
            allowed_names.update(canonical_key(a) for a in recorded[1])
        if canonical_key(matched) not in allowed_names:
            govman_office_violations.append("{} carries an office entry matched on {!r}, which is not its name or a reviewed alternative".format(label(node), matched))
            continue
        if canonical_key(matched) != canonical_key(listed_name) and canonical_key(matched) != "{} {}".format(canonical_key(listed_name), GOVMAN_OFFICE_STYLE_SUFFIX):
            govman_office_violations.append("{} matched on {!r}, which is neither the entry's name nor that name in its full style".format(label(node), matched))
            continue
        expected_url = "{}/{}/{}".format(GOVMAN_DETAILS, GOVMAN_PACKAGE, granule)
        if str(block.get("url") or "") != expected_url:
            govman_office_violations.append("{} cites {!r}, not the publisher's own address {!r}".format(label(node), block.get("url"), expected_url))
            continue
        if not _past_iso(block.get("edition")):
            govman_office_violations.append("{} cites a Manual edition {!r} that has not happened".format(label(node), block.get("edition")))
            continue
        if str(node.get("placementMethod") or "").endswith("us_government_manual") or node.get("placementVerified") is True and str(node.get("placementUrl") or "") == expected_url:
            govman_office_violations.append("{} claims a placement from the Manual entry that is its own existence".format(label(node)))
            continue
    gate.check("a Manual office entry is a top-level entry for the office itself, on a post, and never a placement", govman_office_violations)
    # Alternative names: the reviewed table, mirrored by node id, and the
    # grading cap that keeps what it buys from reading as more than it is.
    alias_violations = []
    alias_on_figures = []
    for node in nodes:
        alias_violations.extend(alias_match_violations(node, label, by_id))
        alias_on_figures.extend(alias_on_a_figure_violations(node, label))
    gate.check("an alias match quotes a reviewed alternative for this node, under the name the row was written against, and never reads verified alone", alias_violations)
    gate.check("no money or headcount block rests on an alternative name", alias_on_figures)
    aliased_nodes = [n for n in nodes if isinstance(n.get("verificationAliasMatch"), dict)]
    print("      {} node(s) carry a claim reached through a recorded alternative name; {} of them rest on nothing else".format(
        len(aliased_nodes), sum(1 for n in aliased_nodes if str((n.get("verificationAliasMatch") or {}).get("gradedAtMost") or ""))))
    # The entry's own description, re-derived from the committed package
    # rather than trusted. The block quotes text and names the element it came
    # from; the check is that the text is VERBATIM in exactly that element of
    # exactly that granule -- the whole of it, or a prefix ending at a
    # sentence boundary when the block says it was cut -- that the granule
    # names this node, that the package on disk is the one the block cites,
    # and that the curated prose was left exactly where it was: the Manual's
    # text sits beside `desc`, never in its place.
    govman_desc_violations = []
    govman_desc_index = {}
    govman_digest = None
    try:
        govman_desc_index, govman_digest = govman_descriptions()
    except (OSError, ValueError) as error:
        govman_desc_violations.append("the Government Manual fixture could not be read: {}".format(error))
    for node in nodes:
        block_data = node.get("descriptionOfficial")
        if not isinstance(block_data, dict):
            continue
        if is_post(node):
            govman_desc_violations.append("{} is a post but carries a Government Manual description".format(label(node)))
            continue
        if str(block_data.get("source") or "") != "us_government_manual":
            govman_desc_violations.append("{} carries an official description from {!r}, which is not a source this gate can check".format(label(node), block_data.get("source")))
            continue
        entry_block = node.get("govmanEntry")
        granule = str(block_data.get("granule") or "")
        if not isinstance(entry_block, dict) or str(entry_block.get("granule") or "") != granule:
            govman_desc_violations.append("{} carries a Manual description without the Manual entry it was read from".format(label(node)))
            continue
        text = str(block_data.get("text") or "")
        if not text.strip() or text != " ".join(text.split()):
            govman_desc_violations.append("{} carries an empty or un-normalised Manual description".format(label(node)))
            continue
        if len(text) > GOVMAN_DESCRIPTION_MAX_CHARS:
            govman_desc_violations.append("{} carries a Manual description of {} characters, past the {}-character bound".format(label(node), len(text), GOVMAN_DESCRIPTION_MAX_CHARS))
            continue
        kind = str(block_data.get("kind") or "")
        if kind not in GOVMAN_DESCRIPTION_PATHS:
            govman_desc_violations.append("{} carries a Manual description of kind {!r}".format(label(node), kind))
            continue
        if str(block_data.get("extractedFrom") or "") != GOVMAN_DESCRIPTION_PATHS[kind]:
            govman_desc_violations.append("{} says its {} came from {!r}, which is not where one is read".format(label(node), kind, block_data.get("extractedFrom")))
            continue
        if govman_digest and str(block_data.get("documentSha256") or "") != govman_digest:
            govman_desc_violations.append("{} cites a Manual digest {!r} that is not the committed package's".format(label(node), block_data.get("documentSha256")))
            continue
        entry = govman_index.get(granule)
        if govman_index and entry is None:
            govman_desc_violations.append("{} cites granule {!r}, which the committed Manual does not carry".format(label(node), granule))
            continue
        if entry is not None:
            if canonical_key(str(block_data.get("listedName") or "")) != canonical_key(entry[0]):
                govman_desc_violations.append("{} quotes a description under {!r} for granule {}, which the Manual names {!r}".format(label(node), block_data.get("listedName"), granule, entry[0]))
                continue
            if canonical_key(entry[0]) not in ({canonical_key(node.get("name"))} | alias_keys_for(node.get("id"), by_id)):
                govman_desc_violations.append("{} carries the Manual's description of {!r}, which is not this node's name".format(label(node), entry[0]))
                continue
        if govman_desc_index and granule in govman_desc_index:
            texts = govman_desc_index[granule]
            printed = texts.get("mission") if kind == "mission_statement" else texts.get("opening")
            if kind == "opening_paragraph" and texts.get("mission"):
                govman_desc_violations.append("{} publishes the opening paragraph where the Manual prints a mission statement".format(label(node)))
                continue
            if not printed:
                govman_desc_violations.append("{} quotes a {} that granule {} does not carry".format(label(node), kind, granule))
                continue
            if bool(block_data.get("truncated")):
                boundaries = {m.end() for m in GOVMAN_SENTENCE_BOUNDARY.finditer(printed)}
                if not (printed.startswith(text) and len(text) < len(printed) and len(text) in boundaries):
                    govman_desc_violations.append("{} says its description was cut at a sentence boundary, and the text is not such a prefix of what the Manual prints".format(label(node)))
                    continue
                if int(block_data.get("fullLength") or -1) != len(printed):
                    govman_desc_violations.append("{} states a full length of {!r} for a paragraph of {} characters".format(label(node), block_data.get("fullLength"), len(printed)))
                    continue
            elif text != printed:
                govman_desc_violations.append("{} quotes a {} that is not verbatim what granule {} prints".format(label(node), kind, granule))
                continue
            # Tested on the text PUBLISHED, not the whole paragraph: a name
            # that appears only after the cut is not on the reader's screen.
            if kind == "opening_paragraph" and entry is not None and entry[0] not in text:
                govman_desc_violations.append("{} publishes an opening paragraph that does not name the unit".format(label(node)))
                continue
            if kind == "opening_paragraph" and any(marker in text.casefold() for marker in GOVMAN_NAVIGATION_NOTE_MARKERS):
                govman_desc_violations.append("{} publishes a note about the unit's website as its description".format(label(node)))
                continue
        expected_url = "{}/{}/{}".format(GOVMAN_DETAILS, GOVMAN_PACKAGE, granule)
        if str(block_data.get("url") or "") != expected_url:
            govman_desc_violations.append("{} cites {!r} for its description, not the publisher's own address {!r}".format(label(node), block_data.get("url"), expected_url))
            continue
        if not _past_iso(block_data.get("edition")):
            govman_desc_violations.append("{} cites a Manual edition {!r} that has not happened".format(label(node), block_data.get("edition")))
            continue
        # The curated prose is untouched: it is never the Manual's text and it
        # keeps its own provenance label.
        if str(node.get("desc") or "") == text and not node.get("descriptionSource"):
            govman_desc_violations.append("{}'s curated description IS the Manual's text -- the official description must sit beside the prose, never replace it".format(label(node)))
            continue
    gate.check("a Government Manual description is that entry's own text, verbatim, beside the curated prose", govman_desc_violations)

    # The signature block of a published Federal Register document. Everything
    # is re-derived from the committed fixtures by the block's own document
    # number -- the digest, the title the document prints in its signature
    # position, and the agency list the API listing prints for it -- and the
    # agencies are resolved against the published organisations here, so the
    # scope the claim rests on is checked rather than copied. The parent is
    # read off the TREE this gate is walking and never off `parentId`, which
    # is stamped on the exported node list alone: `General Counsel` names 84
    # nodes here, so a record moved to another node would keep a real title, a
    # real document and a real URL, and only the parent tells them apart.
    fr_signature_violations = []
    fr_documents = {}
    try:
        fr_documents = fr_signature_documents()
    except (OSError, ValueError) as error:
        fr_signature_violations.append("the Federal Register signature fixtures could not be read: {}".format(error))
    fr_orgs_by_key = {}
    for node in nodes:
        if not is_post(node) and not node.get("synthetic"):
            key = canonical_key(node.get("name"))
            if key:
                fr_orgs_by_key.setdefault(key, set()).add(str(node.get("id") or ""))

    def fr_signature_problem(node, block_data):
        """The first thing wrong with this signature block, or None."""
        if not is_post(node):
            return "is not a post but carries a Federal Register signature"
        number = str(block_data.get("documentNumber") or "")
        listed_title = str(block_data.get("listedTitle") or "")
        document = fr_documents.get(number)
        if fr_documents and document is None:
            return "cites document {!r}, which is not in the committed fixtures".format(number)
        if document is not None:
            if document.get("title") != listed_title:
                return "quotes {!r}, which is not the title document {} prints in its signature position ({!r})".format(
                    listed_title, number, document.get("title"))
            if list(block_data.get("agenciesListed") or []) != list(document.get("agencies") or []):
                return "quotes an agency list document {} does not carry".format(number)
            if str(block_data.get("documentSha256") or "") != document["sha256"]:
                return "cites a digest the committed document {} does not have".format(number)
            if str(block_data.get("url") or "") != document["url"]:
                return "cites {!r}, which is not the URL that served document {}".format(block_data.get("url"), number)
            for field in ("publicationDate", "signingDate", "documentTitle", "documentType"):
                if (block_data.get(field) or None) != (document.get(field) or None):
                    return "carries a {} that document {} does not print".format(field, number)
        if canonical_key(node.get("name")) != canonical_key(listed_title):
            return "carries a signature quoting {!r}, which is not this node's name".format(listed_title)
        if len(canonical_key(listed_title).split()) < FR_MIN_POST_TOKENS:
            return "rests on a signature title of under {} tokens".format(FR_MIN_POST_TOKENS)
        for field in ("publicationDate", "signingDate"):
            when = block_data.get(field)
            if when and not _past_iso(when):
                return "cites a {} of {!r}, which has not happened".format(field, when)
        if not block_data.get("publicationDate"):
            return "cites a Federal Register document with no publication date"
        # The scope IS the claim, and it is re-resolved here against the
        # published organisations rather than taken from the block. The parent
        # is read off the TREE this gate is walking, never off `parentId`,
        # which is stamped on the exported node list alone and would make this
        # check pass vacuously while looking like a check.
        reached = set()
        for name in (block_data.get("agenciesListed") or []):
            for key in fr_agency_keys(name):
                reached |= fr_orgs_by_key.get(key, set())
        parent_id = tree_parents.get(str(node.get("id") or "")) or ""
        if len(reached) != 1 or parent_id not in reached:
            return ("rests on a document the Register files under {}, which does not resolve to exactly the "
                    "organisation the tree gives it".format(block_data.get("agenciesListed")))
        if str(block_data.get("documentUrl") or "") != FR_DOCUMENT_URL.format(number):
            return "cites {!r}, not the Register's own address for document {}".format(
                block_data.get("documentUrl"), number)
        if str(block_data.get("url") or "") not in [str(u) for u in (node.get("sourceUrls") or [])]:
            return "cites a Federal Register document without carrying its URL"
        if FR_SIGNATURE_SOURCE not in [str(t) for t in (node.get("sourceTypes") or [])]:
            return "cites a Federal Register document without saying so in its source types"
        # How many committed documents carry this title under this
        # organisation. The panel prints the number, so a block may not
        # inflate it. Bounded rather than pinned to an exact figure: the
        # derive step resolves agencies against the CURATED file and the gate
        # against the PUBLISHED tree, and a unit the export gate pruned would
        # make an exact equality fail for a reason that is not a lie.
        if fr_documents:
            carrying = 0
            for other in fr_documents.values():
                if other.get("title") != listed_title:
                    continue
                other_reached = set()
                for name in other.get("agencies") or []:
                    for key in fr_agency_keys(name):
                        other_reached |= fr_orgs_by_key.get(key, set())
                if reached <= other_reached:
                    carrying += 1
            stated = int(block_data.get("occurrences") or 0)
            if stated < 1 or stated > carrying:
                return "says {} committed documents carry this title under its organisation; at most {} do".format(
                    block_data.get("occurrences"), carrying)
        # One document was read and it yields one observation. Publishing
        # existence and placement from it would present a single finding as
        # two corroborating ones -- the rule the Manual's post route follows.
        if FR_SIGNATURE_SOURCE in str(node.get("placementMethod") or "") or \
                str(node.get("placementMethod") or "") == FR_SIGNATURE_METHOD:
            return "claims placement from a Federal Register signature, which reads one document"
        return None

    for node in nodes:
        block_data = node.get("federalRegisterSignature")
        if not isinstance(block_data, dict):
            if str(node.get("verificationMethod") or "") == FR_SIGNATURE_METHOD:
                fr_signature_violations.append(
                    "{} takes a Federal Register signature as its method and carries no signature block".format(label(node)))
            continue
        problem = fr_signature_problem(node, block_data)
        if problem:
            fr_signature_violations.append("{} {}".format(label(node), problem))
    gate.check(
        "a Federal Register signature is a title that document prints, under an agency list that resolves to the node's own parent",
        fr_signature_violations,
    )

    # OMB's Public Budget Database, re-derived from the committed package
    # rather than trusted. The check that matters most is the fiscal year: the
    # later columns of this file are the President's request, and an estimate
    # published beside figures this project calls measured would be the worst
    # thing this source could do. The boundary is read out of the package's own
    # user's guide here, independently of the module that wrote the block.
    omb_violations = []
    omb_last_actual = None
    omb_measures = {}
    omb_digest = None
    try:
        omb_last_actual, omb_measures, omb_digest = omb_database()
    except (OSError, ValueError, KeyError) as error:
        omb_violations.append("the OMB Public Budget Database fixture could not be read: {}".format(error))
    for node in nodes:
        block_data = node.get("ombBudget")
        if not isinstance(block_data, dict):
            continue
        type_text = str(node.get("type") or "").casefold()
        if any(word in type_text for word in ("position", "role", "office holder")):
            omb_violations.append("{} is a post carrying an OMB budget figure".format(label(node)))
            continue
        year = block_data.get("fiscalYear")
        if omb_last_actual is not None and year != omb_last_actual:
            omb_violations.append(
                "{} publishes FY{} where the guide's last completed year is FY{}".format(
                    label(node), year, omb_last_actual))
            continue
        level = str(block_data.get("level") or "")
        listed_agency = str(block_data.get("listedAgency") or "")
        listed_bureau = str(block_data.get("listedBureau") or "")
        if level not in ("agency", "bureau"):
            omb_violations.append("{} carries an OMB block at level {!r}".format(label(node), level))
            continue
        # The panel prints the name the block quotes. An agency-level block
        # carrying a bureau name would show one unit's name beside another
        # unit's figures, which is the only way this block can lie while every
        # number in it stays right.
        if level == "agency" and listed_bureau:
            omb_violations.append(
                "{} is an agency-level OMB block naming the bureau {!r}".format(label(node), listed_bureau))
            continue
        if level == "bureau" and not listed_bureau:
            omb_violations.append("{} is a bureau-level OMB block naming no bureau".format(label(node)))
            continue
        quoted = listed_bureau if level == "bureau" else listed_agency
        if canonical_key(quoted) != canonical_key(str(node.get("name") or "")):
            omb_violations.append(
                "{} carries a block naming {!r}, which is not this node's name".format(label(node), quoted))
            continue
        if omb_measures:
            ok = True
            for measure, field, rows_field in (("outlays", "outlays", "outlayAccountRows"),
                                               ("budget_authority", "budgetAuthority",
                                                "budgetAuthorityAccountRows")):
                agency_totals, bureau_totals, row_counts, _cgac = omb_measures[measure]
                key = (listed_agency, listed_bureau) if level == "bureau" else listed_agency
                published = bureau_totals.get(key) if level == "bureau" else agency_totals.get(key)
                claimed = block_data.get(field)
                if published is None or not published:
                    # The two member files do not cover the same set of units.
                    # An absent measure must be published as absent, never as
                    # zero, and never as a figure.
                    if claimed is not None:
                        omb_violations.append(
                            "{} publishes {} for {!r}, which the package carries no row for".format(
                                label(node), field, listed_bureau or listed_agency))
                        ok = False
                        break
                    continue
                if not isinstance(claimed, (int, float)) or round(float(claimed), 2) != round(published * 1000, 2):
                    omb_violations.append(
                        "{} publishes {} of {!r} where the package gives {}".format(
                            label(node), field, claimed, round(published * 1000, 2)))
                    ok = False
                    break
                # OMB prints no total row, so the figure is a SUM over account
                # rows and the count is what lets a reader check that claim.
                # A wrong count would make an honest figure read as a different
                # arithmetic than the one performed.
                claimed_rows = block_data.get(rows_field)
                if claimed_rows != row_counts.get(key, 0):
                    omb_violations.append(
                        "{} says its {} sums {} account rows where the package files {}".format(
                            label(node), field, claimed_rows, row_counts.get(key, 0)))
                    ok = False
                    break
            if not ok:
                continue
        measured = node.get("resolved_total_amount")
        if (str(node.get("cost_status") or "") == "official" and isinstance(measured, (int, float))
                and isinstance(block_data.get("outlays"), (int, float))
                and round(float(measured), 2) == round(float(block_data["outlays"]), 2)):
            omb_violations.append(
                "{}'s OMB outlays equal its measured cost to the cent, so the two have been confused".format(
                    label(node)))
            continue
        # The publisher's own statement of the unit, and of how far the figure
        # is actually precise, must ride on the block: without them a reader
        # cannot tell $1,892,935,000,000 from a number with six spurious digits.
        if not str(block_data.get("unitsQuote") or "").strip():
            omb_violations.append("{}'s OMB block does not say how its unit is known".format(label(node)))
            continue
        if not str(block_data.get("precisionNote") or "").strip():
            omb_violations.append("{}'s OMB block does not state its precision".format(label(node)))
            continue
        # A negative figure is normal here and must arrive with the publisher's
        # own explanation of why, or it reads as a bug.
        if not str(block_data.get("netQuote") or "").strip():
            omb_violations.append("{}'s OMB block does not say the figures are net of collections".format(label(node)))
            continue
        if omb_digest and str(block_data.get("documentSha256") or "") != omb_digest:
            omb_violations.append(
                "{}'s OMB block names digest {!r}, not the package's {}".format(
                    label(node), block_data.get("documentSha256"), omb_digest[:16]))
            continue
        if not str(block_data.get("rowSelection") or "").strip():
            omb_violations.append(
                "{}'s OMB block does not declare which rows it summed".format(label(node)))
            continue
        # The CGAC column is per account. OMB's "Agency" groups several
        # Treasury entities, so a code published for an agency that carries
        # more than one would be an identifier the file never assigns it.
        if omb_measures:
            _a, _b, _c, agency_codes = omb_measures["outlays"]
            codes = agency_codes.get(listed_agency) or set()
            claimed_code = block_data.get("cgacAgencyCode")
            if block_data.get("cgacAgencyCodeCount") != len(codes):
                omb_violations.append(
                    "{}'s OMB block says {} CGAC codes where the package has {}".format(
                        label(node), block_data.get("cgacAgencyCodeCount"), len(codes)))
                continue
            if len(codes) == 1:
                if claimed_code != sorted(codes)[0]:
                    omb_violations.append(
                        "{}'s OMB block gives CGAC {!r}, not the package's {!r}".format(
                            label(node), claimed_code, sorted(codes)[0]))
                    continue
            elif claimed_code is not None:
                omb_violations.append(
                    "{}'s OMB block publishes CGAC {!r} for an agency carrying {} codes".format(
                        label(node), claimed_code, len(codes)))
                continue
        url = str(block_data.get("url") or "")
        if not url.startswith("https://www.govinfo.gov/"):
            omb_violations.append("{}'s OMB block cites {!r}, not the package on govinfo".format(label(node), url))
    gate.check("an OMB budget figure is a completed year the package really prints", omb_violations)

    # A name that states how many things it stands for, against what the
    # graph carries. The claim is only ever "the name says N, we carry M";
    # it must be arithmetic, and it must not appear where it is not true.
    bad_counts = []
    for node, parent in walk(graph):
        stated, carried = node.get("statedChildCount"), node.get("carriedChildCount")
        if stated is None and carried is None and not node.get("childrenIncomplete"):
            continue
        if not isinstance(stated, int) or not isinstance(carried, int) or stated < 0 or carried < 0:
            bad_counts.append("{} states {!r} and carries {!r}".format(label(node), stated, carried))
            continue
        real = sum(1 for c in (node.get("children") or []) if isinstance(c, dict) and not c.get("synthetic"))
        if carried != real:
            bad_counts.append("{} says it carries {} children, the tree has {}".format(label(node), carried, real))
        if bool(node.get("childrenIncomplete")) != (carried < stated):
            bad_counts.append("{} flags incomplete={!r} with {} of {}".format(
                label(node), node.get("childrenIncomplete"), carried, stated))
        if str(stated) not in str(node.get("name") or ""):
            bad_counts.append("{} claims a stated count its name does not carry".format(label(node)))
    gate.check("a stated child count is the name's and the tree's", bad_counts)

    # A position standing for several posts. Where the name gives no number,
    # none may be published: an invented count is a figure nobody wrote.
    bad_multiplicity = []
    for node in nodes:
        represents = node.get("representsPosts")
        if represents is None:
            continue
        if not isinstance(represents, dict) or represents.get("kind") not in ("exact", "range", "unstated"):
            bad_multiplicity.append("{} representsPosts {!r}".format(label(node), represents))
            continue
        kind = represents["kind"]
        if kind == "exact" and not (isinstance(represents.get("count"), int) and represents["count"] > 1):
            bad_multiplicity.append("{} states {!r} posts".format(label(node), represents.get("count")))
        if kind == "range":
            low, high = represents.get("low"), represents.get("high")
            if not (isinstance(low, int) and isinstance(high, int) and 0 < low <= high):
                bad_multiplicity.append("{} states a range {!r}-{!r}".format(label(node), low, high))
        if kind == "unstated" and any(k in represents for k in ("count", "low", "high")):
            bad_multiplicity.append("{} invents a number for an unstated multiplicity".format(label(node)))
        if str(represents.get("text") or "") not in str(node.get("name") or ""):
            bad_multiplicity.append("{} quotes {!r}, which is not in its name".format(label(node), represents.get("text")))
    gate.check("a multiplicity is read from the name and never invented", bad_multiplicity)

    # 14. The review queue beside the graph, when there is one.
    queue_path = graph_path.parent / "candidate_nodes.json"
    if queue_path.exists():
        check_review_queue(gate, queue_path, graph, nodes)

    # Reported, never fatal.
    verification = Counter(str(n.get("verificationStatus") or "none") for n in nodes)
    cost_status = Counter(str(n.get("cost_status") or "none") for n in nodes)
    no_source = sum(
        1
        for n in nodes
        if not (n.get("sourceUrls") if isinstance(n.get("sourceUrls"), list) else []) and not n.get("lastVerified")
    )
    print("\n--- reported, not enforced ---")
    print("  nodes                : {:,}".format(len(nodes)))
    # "with a cost" is not "with a known cost". A record naming the node is
    # the only thing that makes a figure that node's own; everything else is
    # its share of an ancestor's total, divided by a weight. Reported as
    # nodes and as dollars, because the two say different things: a handful
    # of measured nodes can cover most of the money, and usually do.
    exact = [n for n in nodes if str(n.get("cost_status") or "") in ("official", "root_total")]
    estimated = [n for n in nodes if str(n.get("cost_status") or "") in ("allocated", "scaled_official")]
    anchor_total = amount_of(graph) or 0.0
    top_exact, seen_exact = [], set()

    def collect_exact(node, inside):
        node_id = str(node.get("id") or "")
        measured = str(node.get("cost_status") or "") == "official"
        if measured and not inside and node_id not in seen_exact:
            seen_exact.add(node_id)
            top_exact.append(node)
        for child in node.get("children") or []:
            if isinstance(child, dict):
                collect_exact(child, inside or measured)

    for branch in graph.get("children") or []:
        if isinstance(branch, dict):
            collect_exact(branch, False)
    # Signed: the government-wide offsetting receipts are a measured, negative
    # top-most line, and taking its magnitude would count $343B of receipts as
    # $343B of covered spending and push the coverage past 100%.
    exact_dollars = sum(amount_of(n) or 0.0 for n in top_exact)
    print("  cost identified for the node itself: {:,} of {:,} nodes ({:.1%}); {:,} are a share of an ancestor's total".format(
        len(exact), len(nodes), len(exact) / len(nodes) if nodes else 0, len(estimated)))
    print("  the measured nodes cover {:.1%} of the anchor ({:,.0f} of {:,.0f}), counting each only once".format(
        exact_dollars / anchor_total if anchor_total else 0, exact_dollars, anchor_total))
    print("  with a cost          : {:,}".format(sum(1 for n in nodes if amount_of(n) is not None)))
    print("  verification         : {}".format(dict(verification.most_common())))
    print("  cost_status          : {}".format(dict(cost_status.most_common())))
    print("  no source recorded   : {:,}".format(no_source))
    official = sum(
        1 for n in nodes
        if any(
            urlparse(str(u)).netloc.lower().endswith((".gov", ".mil"))
            for u in (n.get("sourceUrls") or [])
            if str(u).startswith(("http://", "https://"))
        )
    )
    methods = Counter(str(n.get("verificationMethod")) for n in nodes if n.get("verificationMethod"))
    checked_failed = sum(1 for n in nodes if n.get("verificationFailure"))
    print("  official source      : {:,} of {:,} ({:.1%})".format(official, len(nodes), official / len(nodes) if nodes else 0))
    print("  verified by          : {}".format(dict(methods) or "nothing yet"))
    print("  checked, not found   : {:,}".format(checked_failed))
    unread_orgs = [n for n in nodes if not is_post(n) and isinstance(n.get("verificationUnread"), dict) and not n.get("verificationMethod")]
    unread_kinds = Counter(str(n["verificationUnread"].get("kind")) for n in unread_orgs)
    print("  page unread          : {:,} organisations have a queued page that could not be read and no other method {}".format(
        len(unread_orgs), dict(unread_kinds) or ""))
    # Positions are 85% of this graph and carried no evidence of any kind
    # until 2026-09-15, so their coverage is reported on its own line rather
    # than buried in a total the organisations dominate.
    posts = [n for n in nodes if is_post(n)]
    posts_confirmed = [n for n in posts if str(n.get("verificationMethod") or "") == POST_PAGE_METHOD]
    print("  posts on their org's page: {:,} of {:,} positions confirmed by a label in their organisation's own page content ({:.1%})".format(
        len(posts_confirmed), len(posts), len(posts_confirmed) / len(posts) if posts else 0))
    folded_existence = sum(1 for n in nodes if n.get("verificationMatchRule") == MATCH_RULE_COMMITTEE)
    folded_placement = sum(1 for n in nodes if n.get("placementMatchRule") == MATCH_RULE_COMMITTEE)
    print("  committee labels     : {:,} confirmed and {:,} placed with the graph's \"Committee on\"/\"Subcommittee on\" prefix set aside".format(
        folded_existence, folded_placement))
    org_edges = [n for n in nodes if n is not graph and "position" not in str(n.get("type") or "").lower()]
    placed = sum(1 for n in org_edges if n.get("placementVerified") is True)
    placed_no = sum(1 for n in org_edges if n.get("placementVerified") is False)
    unreachable = sum(1 for n in org_edges if n.get("placementCheckable") is False)
    directory_listed = sum(1 for n in nodes if isinstance(n.get("directoryListing"), dict) and n["directoryListing"].get("source") not in ("senate_committee_list", "house_clerk_committee_list"))
    directory_placed = sum(1 for n in org_edges if str(n.get("placementMethod") or "") == "listed_under_parent_in_federal_register_agency_directory")
    directory_disagree = sum(1 for n in nodes if isinstance(n.get("placementDirectoryDisagreement"), dict))
    directory_ancestor = sum(1 for n in nodes if isinstance(n.get("placementDirectoryAncestor"), dict))
    print("  directory-listed     : {:,} in the Federal Register's agency directory; {:,} placements from it; {:,} filed under an ancestor here; {:,} filed elsewhere by it".format(
        directory_listed, directory_placed, directory_ancestor, directory_disagree))
    senate_listed = sum(1 for n in nodes if isinstance(n.get("directoryListing"), dict) and n["directoryListing"].get("source") == "senate_committee_list")
    senate_placed = sum(1 for n in org_edges if str(n.get("placementMethod") or "") == "listed_under_committee_in_senate_committee_list")
    senate_missing = sum(
        1 for n in nodes
        if str(n.get("verificationFailure") or "") == "not_in_official_list"
        and isinstance(n.get("verificationFailureSource"), dict) and n["verificationFailureSource"].get("source") == "senate_committee_list"
    )
    official_counts = [n for n in nodes if n.get("employeesOfficial") is not None]
    disagree = sum(
        1 for n in official_counts
        if str(n.get("employees") or "").strip() and not _within(n.get("employees"), n["employeesOfficial"], 0.10)
    )
    listings = [n for n in nodes if isinstance(n.get("positionListing"), dict)]
    disputed = [n for n in nodes if isinstance(n.get("cost_weight_dispute"), dict)]
    print("  OPM headcounts       : {:,} nodes carry one; {:,} differ from the curated figure by more than 10%".format(
        len(official_counts), disagree))
    print("  weights disputed     : {:,} allocated shares were apportioned by a headcount OPM's file contradicts".format(
        len(disputed)))
    file_a = [n for n in nodes if isinstance(n.get("usaspendingOutlays"), dict)]
    aliased = [n for n in file_a if isinstance(n["usaspendingOutlays"].get("nameAlias"), dict)]
    print("  USAspending File A   : {:,} organisations carry a gross-outlays figure ({:,} toptier, {:,} bureau), "
          "fiscal-year-to-date, beside the cost and never as it; {:,} of them rest on a recorded name alias "
          "and are graded partial".format(
        len(file_a),
        sum(1 for n in file_a if n["usaspendingOutlays"].get("level") == "toptier"),
        sum(1 for n in file_a if n["usaspendingOutlays"].get("level") == "bureau"),
        len(aliased)))
    with_rate = sum(1 for n in listings if isinstance(n["positionListing"].get("reportedPay"), (int, float)))
    with_level = sum(1 for n in listings if n["positionListing"].get("payLevel"))
    print("  archive pay          : {:,} positions carry a rate of basic pay the archive reports; {:,} carry a level or grade only".format(
        with_rate, with_level))
    table_paid = [n for n in nodes if isinstance(n.get("positionPayRate"), dict)]
    by_level = {}
    for n in table_paid:
        key = str(n["positionPayRate"].get("payLevel") or "?")
        by_level[key] = by_level.get(key, 0) + 1
    print("  salary table         : {:,} positions priced from {} for the level the archive reports ({}); "
          "{:,} not priced (a level on another pay plan)".format(
              len(table_paid), EXECUTIVE_SCHEDULE_TABLE,
              ", ".join("{} {}".format(k, by_level[k]) for k in sorted(by_level, key=len)) or "none",
              with_level - len(table_paid)))
    ranged = [n for n in nodes if isinstance(n.get("positionGradePay"), dict)]
    ranged_kinds = Counter(str(n["positionGradePay"].get("kind") or "?") for n in ranged)
    print("  pay ranges           : {:,} positions carry a base-pay RANGE, never a rate, for the pay plan the archive reports "
          "(General Schedule grade {:,}, base pay before locality; SES {:,}; SL/ST {:,})".format(
              len(ranged), ranged_kinds.get("general_schedule_grade", 0),
              ranged_kinds.get("senior_executive_service", 0), ranged_kinds.get("senior_level", 0)))
    schedule_paid = [n for n in nodes if isinstance(n.get("positionSchedulePay"), dict)]
    if schedule_paid or US_CODE_EXECUTIVE_SCHEDULE:
        sched_levels = Counter(str(n["positionSchedulePay"].get("payLevel") or "?") for n in schedule_paid)
        # The mirror holds the posts the Code names AND this graph has a node
        # for, which is a far smaller set than the Code's own list -- it
        # enumerates 415 positions across the five sections. Saying "the Code
        # names N" off the mirror's length would report this graph's coverage
        # as the statute's contents.
        counted_paid = [n for n in schedule_paid if isinstance(n["positionSchedulePay"].get("countedClass"), dict)]
        reviewed_paid = [n for n in schedule_paid if isinstance(n["positionSchedulePay"].get("identification"), dict)
                         and n not in counted_paid]
        print("  U.S. Code schedule   : {:,} positions priced at the level 5 U.S.C. §§{}-{} sets for them ({}); "
              "{:,} are mirrored here, which is how many of the Code's positions this graph has a node for; "
              "{:,} of them rest on a reviewed identification a second statute backs ({:,} rows mirrored); "
              "{:,} are members of a counted class the Code places without naming them ({:,} classes, {:,} members mirrored)".format(
                  len(schedule_paid), US_CODE_SECTIONS[0], US_CODE_SECTIONS[-1],
                  ", ".join("{} {}".format(k, sched_levels[k]) for k in ("I", "II", "III", "IV", "V") if sched_levels.get(k)) or "none",
                  len(US_CODE_EXECUTIVE_SCHEDULE) + len(US_CODE_REVIEWED_IDENTIFICATIONS) + sum(len(c["members"]) for c in US_CODE_COUNTED_CLASSES.values()),
                  len(reviewed_paid), len(US_CODE_REVIEWED_IDENTIFICATIONS),
                  len(counted_paid), len(US_CODE_COUNTED_CLASSES), sum(len(c["members"]) for c in US_CODE_COUNTED_CLASSES.values())))
    statutory_paid = [n for n in nodes if isinstance(n.get("positionStatutoryPay"), dict)]
    by_source = Counter(str(n["positionStatutoryPay"].get("source") or "?") for n in statutory_paid)
    member_seats = [n for n in statutory_paid if isinstance(n["positionStatutoryPay"].get("memberSeat"), dict)]
    seat_kinds = Counter(str(n["positionStatutoryPay"]["memberSeat"].get("kind") or "?") for n in member_seats)
    print("  statutory pay         : {:,} positions priced from a single primary source naming the seat directly ({}); "
          "{:,} of them are offices a Member of Congress holds, priced at the SEAT rate by rule ({}; {:,} leadership "
          "offices mirrored by id), not at a row naming the office".format(
        len(statutory_paid), dict(by_source) or "none", len(member_seats), dict(seat_kinds) or "none",
        len(US_CODE_MEMBER_LEADERSHIP_NODES)))
    derived_paid = [n for n in nodes if isinstance(n.get("positionDerivedPay"), dict)]
    if derived_paid or DERIVED_PAY_PROVISIONS:
        derived_counts = Counter(
            int((n["positionDerivedPay"].get("verification") or {}).get("documents") or 0) for n in derived_paid)
        print("  derived pay          : {:,} positions carry a figure NO document states — a statutory parity provision "
              "names the tier, the compensation table prices it ({}); {:,} parity provisions are mirrored here, and the "
              "Court of International Trade is not among them because 28 U.S.C. 252 states no parity".format(
                  len(derived_paid),
                  "; ".join("{} on {} documents, {}% on this project's own source scale".format(
                      derived_counts[count], count, DERIVED_PAY_STRENGTH_BY_COUNT.get(count)) for count in sorted(derived_counts)) or "none",
                  len(DERIVED_PAY_PROVISIONS)))
    reference_paid = [n for n in nodes if isinstance(n.get("positionTierReferencePay"), dict)]
    reference_igs = [n for n in reference_paid if (n["positionTierReferencePay"].get("identification") or {}).get("kind") != "reviewed_row"]
    print("  tier-reference pay   : {:,} positions priced from a statute that sets pay by reference to an Executive Schedule "
          "level ({:,} reviewed rows mirrored by id — the GAO's, the GPO's and the IES's officers; {:,} Inspectors General of an establishment 5 U.S.C. 401(1) lists, each "
          "Level III plus 3 percent, arithmetic no document prints); 0 documents state any figure".format(
              len(reference_paid), len(reference_paid) - len(reference_igs), len(reference_igs)))
    reported_paid = [n for n in nodes if isinstance(n.get("positionReportedPay"), dict)]
    uniform_paid = [n for n in reported_paid
                    if isinstance(n["positionReportedPay"].get("holders"), dict)
                    and n["positionReportedPay"]["holders"].get("uniformRate") is True]
    print("  reported pay         : {:,} White House Office positions carrying what the July 1 roster reports: "
          "{:,} for the one person under that title, {:,} for every one of the N people listed under it at one rate".format(
              len(reported_paid), len(reported_paid) - len(uniform_paid), len(uniform_paid)))
    print("  PLUM archive         : {:,} positions listed in the previous administration's archive; {:,} placements from it".format(
        len(listings), sum(1 for n in nodes if str(n.get("placementMethod") or "") == "listed_under_organization_in_opm_plum_archive")))
    current_listings = [n for n in nodes if isinstance(n.get("positionCurrentListing"), dict)]
    current_paid = [n for n in nodes if isinstance(n.get("positionCurrentPay"), dict)]
    print("  current Plum Book    : {:,} positions listed in OPM's current PLUM export (fetched {}); {:,} placements from it; "
          "{:,} carry the rate of basic pay the export prints for the one row under the title, graded partial".format(
              len(current_listings),
              next((str(n["positionCurrentListing"].get("exportFetchedAt") or "")[:10] for n in current_listings), "n/a"),
              sum(1 for n in nodes if str(n.get("placementMethod") or "") == PLUM_CURRENT_PLACEMENT_METHOD),
              len(current_paid)))
    # Reported on its own line, like every other source, so "740 with an
    # official source" cannot be read as 740 independently confirmed units.
    # The stale-table count is printed beside it because 26 of these tables
    # carry a "Sources of Information were updated" footer older than the
    # edition, and that is the first thing a reader should know about them.
    govman_nodes = [n for n in nodes if isinstance(n.get("govmanListing"), dict)]
    govman_method = sum(1 for n in govman_nodes if str(n.get("verificationMethod") or "") == GOVMAN_METHOD)
    govman_dated = sum(1 for n in govman_nodes if str((n.get("govmanListing") or {}).get("tableFooter") or "").strip())
    manual_orgs = [n for n in nodes if not is_post(n) and isinstance(n.get("govmanEntry"), dict)]
    manual_org_method = sum(1 for n in manual_orgs if str(n.get("verificationMethod") or "") == GOVMAN_ORG_METHOD)
    manual_org_placed = sum(1 for n in manual_orgs if str(n.get("placementMethod") or "") == GOVMAN_ORG_PLACEMENT_METHOD)
    manual_org_disagree = sum(1 for n in manual_orgs if isinstance(n.get("placementDirectoryDisagreement"), dict) and n["placementDirectoryDisagreement"].get("source") == "us_government_manual")
    print("  Manual (organisations): {:,} organisations carry the Manual's own entry for them; {:,} take it as their method; {:,} placed under their parent by the Manual's hierarchy; {:,} filed elsewhere by it".format(
        len(manual_orgs), manual_org_method, manual_org_placed, manual_org_disagree))
    # Reported on its own line so a reader can see how many of the 5,155
    # "uncited prose" descriptions now have the Manual's own words beside
    # them -- beside, never instead: the curated count does not move.
    manual_desc = [n for n in manual_orgs if isinstance(n.get("descriptionOfficial"), dict)]
    manual_desc_mission = sum(1 for n in manual_desc if n["descriptionOfficial"].get("kind") == "mission_statement")
    manual_desc_cut = sum(1 for n in manual_desc if n["descriptionOfficial"].get("truncated"))
    print("  Manual (descriptions): {:,} organisations carry the Manual's own description beside their curated prose ({:,} mission statements, {:,} opening paragraphs, {:,} cut at a sentence boundary); no curated description was replaced".format(
        len(manual_desc), manual_desc_mission, len(manual_desc) - manual_desc_mission, manual_desc_cut))
    print("  Government Manual    : {:,} positions listed in their own organisation's entry across {:,} agencies; {:,} take it as their method and grade partial; {:,} carry the leadership table's own 'updated' footer; no placement is claimed from it".format(
        len(govman_nodes),
        len({str((n.get("govmanListing") or {}).get("listedUnder") or "") for n in govman_nodes}),
        govman_method, govman_dated))
    # The signature blocks, on their own line for the reason the post page
    # method has one: this is a claim about positions, 85% of the graph, and
    # the number it reaches is small enough that burying it in a total would
    # read as more than it is.
    fr_signature_nodes = [n for n in nodes if isinstance(n.get("federalRegisterSignature"), dict)]
    fr_signature_method = sum(
        1 for n in fr_signature_nodes if str(n.get("verificationMethod") or "") == FR_SIGNATURE_METHOD)
    fr_signature_docs = {str((n.get("federalRegisterSignature") or {}).get("documentNumber") or "")
                         for n in fr_signature_nodes}
    print("  FR signatures        : {:,} of {:,} positions carry the title their signing official stated on a published Federal Register document, from {:,} distinct documents; {:,} take it as their method, which scores 0.4 alone because the Register is not the unit's own site; the signer's name is never read and no placement is claimed from it".format(
        len(fr_signature_nodes), len(posts), len(fr_signature_docs), fr_signature_method))
    # Reported on its own line so "133 units with an OMB figure" can never be
    # read as 133 more measured costs. The negative count is printed because a
    # minus sign here is normal -- the figures are net of collections -- and an
    # unexplained one reads as a defect.
    omb_nodes = [n for n in nodes if isinstance(n.get("ombBudget"), dict)]
    if omb_nodes:
        omb_year = omb_nodes[0]["ombBudget"].get("fiscalYear")
        omb_negative = sum(1 for n in omb_nodes if (n["ombBudget"].get("outlays") or 0) < 0)
        omb_uncosted = sum(1 for n in omb_nodes if str(n.get("cost_status") or "") != "official")
        print("  OMB budget database  : {:,} organisations carry FY{} budget authority and outlays ({:,} agency, {:,} bureau), each the sum of the account rows OMB files under it and never the cost; {:,} of them publish no measured cost of their own; {:,} net below zero, which is what 'net of offsetting collections' means".format(
            len(omb_nodes), omb_year,
            sum(1 for n in omb_nodes if n["ombBudget"].get("level") == "agency"),
            sum(1 for n in omb_nodes if n["ombBudget"].get("level") == "bureau"),
            omb_uncosted, omb_negative))
    print("  Senate list          : {:,} committees and subcommittees listed; {:,} placements from it; {:,} curated names the list does not carry".format(
        senate_listed, senate_placed, senate_missing))
    house_listed = sum(1 for n in nodes if isinstance(n.get("directoryListing"), dict) and n["directoryListing"].get("source") == "house_clerk_committee_list")
    house_placed = sum(1 for n in org_edges if str(n.get("placementMethod") or "") == "listed_under_committee_in_house_clerk_committee_list")
    house_missing = sum(
        1 for n in nodes
        if str(n.get("verificationFailure") or "") == "not_in_official_list"
        and isinstance(n.get("verificationFailureSource"), dict) and n["verificationFailureSource"].get("source") == "house_clerk_committee_list"
    )
    print("  House Clerk list     : {:,} committees and subcommittees listed; {:,} placements from it; {:,} curated names the list does not carry".format(
        house_listed, house_placed, house_missing))
    print("  placement evidenced  : {:,} of {:,} organisation edges ({:.1%}); {:,} checked and not listed; {:,} unreachable (parent has no page)".format(
        placed, len(org_edges), placed / len(org_edges) if org_edges else 0, placed_no, unreachable))
    # A capped Treasury line publishes below the figure the statement reported.
    # Each node says so in the panel; this is the total, which nothing showed.
    # Only the top-most capped node in a branch: a capped department and its
    # capped bureaus are the same dollars, and adding both overstates it ~4x.
    cap_nodes = cap_reported = cap_published = 0
    def walk_capped(node, inside):
        nonlocal cap_nodes, cap_reported, cap_published
        capped = str(node.get("cost_status") or "") == "scaled_official"
        if capped and not inside:
            line = node.get("rollup_total_amount")
            try:
                line = float(line)
            except (TypeError, ValueError):
                line = 0.0
            if line > 0:
                cap_nodes += 1
                cap_reported += line
                cap_published += amount_of(node) or 0.0
        for child in node.get("children", []) or []:
            if isinstance(child, dict):
                walk_capped(child, inside or capped)
    walk_capped(graph, False)
    if cap_reported:
        print("  Treasury lines capped: {:,} top-most nodes · ${:,.0f} reported vs ${:,.0f} published · {:.1%} shown, ${:,.0f} withheld".format(
            cap_nodes, cap_reported, cap_published, cap_published / cap_reported, cap_reported - cap_published))
    summary = graph.get("__budgetSummary") if isinstance(graph.get("__budgetSummary"), dict) else {}
    print("  anchor               : {} {}".format(
        summary.get("label") or "none",
        "(reused from a previous build)" if summary.get("reused_from_previous_build") else "",
    ).rstrip())

    print()
    if gate.failures:
        total = sum(len(v) for _, v in gate.failures)
        print("FAILED: {} check(s), {} violation(s) total".format(len(gate.failures), total))
        return 1
    print("PASSED: all checks clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
