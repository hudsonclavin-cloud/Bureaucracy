"""Instruments the United States Code prints OUTSIDE its sections, pinned in
both directions (since 2026-10-07, the owner's decision in CURATION.md
§19.20): the Reorganization Plans in Title 5's Appendix, and the two chambers'
pay orders reprinted in the Statutory Notes to 2 U.S.C. 4571 and 4532.

What is asserted, against the committed bytes and against doctored copies:

- each quoted sentence IS inside its one instrument, by the module's reader
  and the gate's independent one, and the two readers agree on the text;
- a sentence printed elsewhere on the same page -- another plan, an older
  note, the Amendments note's struck-out law, a planted "Prior to amendment"
  passage, the publisher's square-bracketed insertions -- is refused;
- a doctored fixture makes its rows fall;
- nothing a person's name is printed in (a date line, a signature) reaches
  anything either reader returns;
- the gate mirrors every row by node id and refuses a block moved between a
  post and the office of the same name, a pay order record without its
  later-order caution, and every other corruption tried here.
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from data_pipeline.exporter.build_graph import index_tree
from data_pipeline.verification import financial_evidence as fe
from data_pipeline.verification import notes_instruments as ni
from data_pipeline.verification import statutory_schedule as ss
from data_pipeline.verification.pay_documents import annotate_pay_documents
from data_pipeline.verification.pay_tables import (
    DEFAULT_PAY_TABLE_HTML,
    federal_fiscal_year_of,
    load_executive_schedule,
)
from data_pipeline.verification.tier_reference_pay import (
    FIELD,
    INSTRUMENT_NOT_PRICED,
    INSTRUMENT_PROVISIONS,
    PAY_METHOD,
    apply_pay_evidence,
    build_records,
)
import scripts.validate_published_graph as gate
from scripts.validate_published_graph import (
    EXECUTIVE_SCHEDULE_RATES,
    NOTES_INSTRUMENT_LATER_ORDER_CAUTION,
    NOTES_INSTRUMENTS,
    TIER_REFERENCE_INSTRUMENT_ROWS,
    US_CODE_REVIEWED_IDENTIFICATIONS,
    US_CODE_REVIEWED_INSTRUMENT_IDENTIFICATIONS,
    notes_instrument_caution,
    notes_instrument_text,
    notes_quote_problem,
    schedule_pay_violations,
    tier_reference_pay_violations,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GRAPH = PROJECT_ROOT / "output" / "graph.json"
TODAY = date.today().isoformat()
APPENDIX = "reorganization_plans_5_usc_app_govinfo2024.html"
SENATE = "senate_pay_order_2_usc_4571_govinfo2024.html"
HOUSE = "house_pay_order_2_usc_4532_govinfo2024.html"
SENATE_ORDER = "order-of-the-president-pro-tempore-2024-03-25"
HOUSE_ORDER = "order-of-the-speaker-2025-01-17"
PLAN_4_1970 = "reorganization-plan-no-4-of-1970"
SEC_CHAIR = "exec-regulatory-sec-chair-sec"

#: The sentence the 4571 Amendments note prints as struck-out law: on the
#: page, inside the notes, and not the law.
REPEALED_4571 = (
    "No rate of pay shall be adjusted under the provisions of this section to an amount in excess of the rate "
    "of basic pay for level III of the Executive Schedule contained in section 5314 of title 5"
)


def _label(node):
    return "node {!r}".format(node.get("id"))


def _every_instrument_quote():
    """(instrument id, quote) for every sentence a row rests on."""
    out = []
    for row in INSTRUMENT_PROVISIONS.values():
        out.append((row["instrument"], row["quote"]))
        if row.get("definitionQuote"):
            out.append((row["instrument"], row["definitionQuote"]))
    for row in ss.REVIEWED_INSTRUMENT_ROWS.values():
        out.append((row["basisInstrument"], row["basisQuote"]))
    return out


def _doctored(fixture, transform):
    """A temporary copy of every committed uscode fixture with one page
    rewritten by `transform` and its recorded digest updated to match, so the
    only thing that changed is what the page prints."""
    tmp = Path(tempfile.mkdtemp())
    for path in ni.FIXTURE_DIR.iterdir():
        shutil.copy(path, tmp / path.name)
    page = tmp / fixture
    raw = page.read_text(encoding="utf-8")
    doctored = transform(raw)
    assert doctored != raw, "the transform changed nothing"
    page.write_text(doctored, encoding="utf-8")
    meta_path = tmp / (fixture + ".meta.json")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["sha256"] = hashlib.sha256(doctored.encode("utf-8")).hexdigest()
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    return tmp


class _GateFixtureDir:
    """Point the gate's own reader at a doctored directory for one block."""

    def __init__(self, directory):
        self.directory = directory

    def __enter__(self):
        self.saved = gate.US_CODE_BASIS_FIXTURE_DIR
        gate.US_CODE_BASIS_FIXTURE_DIR = self.directory
        gate._NOTES_INSTRUMENT_CACHE.clear()
        gate._FIXTURE_DIGESTS.clear()
        return self

    def __exit__(self, *exc):
        gate.US_CODE_BASIS_FIXTURE_DIR = self.saved
        gate._NOTES_INSTRUMENT_CACHE.clear()
        gate._FIXTURE_DIGESTS.clear()
        return False


class ReaderTests(unittest.TestCase):
    """What the committed pages print, read one instrument at a time."""

    def test_every_instrument_loads_from_bytes_whose_digest_its_fetch_recorded(self):
        for instrument_id, spec in ni.INSTRUMENTS.items():
            with self.subTest(instrument=instrument_id):
                loaded = ni.load_instrument(instrument_id)
                meta = json.loads((ni.FIXTURE_DIR / (spec["fixture"] + ".meta.json")).read_text(encoding="utf-8"))
                self.assertEqual(meta["sha256"], loaded["sha256"])
                self.assertIn("www.govinfo.gov", loaded["url"])
                self.assertEqual("2024 edition of the United States Code", loaded["edition"])
                self.assertTrue(loaded["text"])

    def test_the_two_readers_agree_on_every_instruments_text(self):
        for instrument_id in ni.INSTRUMENTS:
            with self.subTest(instrument=instrument_id):
                module = ni.load_instrument(instrument_id)
                gate_read = notes_instrument_text(instrument_id)
                self.assertIsInstance(gate_read, dict, gate_read)
                self.assertEqual(module["text"], gate_read["text"])
                self.assertEqual(module["amendments"], gate_read["amendments"])

    def test_every_quote_a_row_rests_on_is_inside_its_instrument_by_both_readers(self):
        for instrument_id, quote in _every_instrument_quote():
            with self.subTest(quote=quote[:60]):
                instrument = ni.load_instrument(instrument_id)
                self.assertIsNone(ni.where_is(instrument, quote))
                self.assertIsNone(notes_quote_problem(instrument_id, quote))

    def test_a_plan_runs_from_its_heading_to_the_next_and_stops_at_the_presidents_message(self):
        plan = ni.load_instrument(PLAN_4_1970)["text"]
        self.assertTrue(plan.startswith(ni.INSTRUMENTS[PLAN_4_1970]["effective"]))
        # The next plan on the page (No. 1 of 1971, the "Action" agency) and
        # the message printed with this one are not the plan.
        self.assertNotIn("REORGANIZATION PLAN NO. 1 OF 1971", plan)
        self.assertNotIn("Action", plan)
        self.assertNotIn("I transmit herewith", plan)
        # The page itself carries both, so the boundary is doing work.
        page = (ni.FIXTURE_DIR / APPENDIX).read_text(encoding="utf-8")
        self.assertIn("I transmit herewith Reorganization Plan No. 4 of 1970", page)

    def test_a_sentence_from_another_plan_on_the_same_page_is_refused_by_both_readers(self):
        epa_deputy = (
            "There shall be in the Agency a Deputy Administrator of the Environmental Protection Agency who shall "
            "be appointed by the President, by and with the advice and consent of the Senate."
        )
        self.assertIsNone(ni.where_is(ni.load_instrument("reorganization-plan-no-3-of-1970"), epa_deputy))
        self.assertEqual("on the page but outside the instrument",
                         ni.where_is(ni.load_instrument(PLAN_4_1970), epa_deputy))
        self.assertIsNotNone(notes_quote_problem(PLAN_4_1970, epa_deputy))

    def test_the_publishers_bracketed_insertions_are_not_the_instruments_words(self):
        bracket = "[As amended Pub. L. 95–219, §3(a)(1), Dec. 28, 1977, 91 Stat. 1613.]"
        plan = ni.load_instrument(PLAN_4_1970)
        self.assertIn(bracket, plan["text"])
        self.assertEqual("only inside the publisher's square-bracketed editorial insertions",
                         ni.where_is(plan, bracket))
        self.assertIsNotNone(notes_quote_problem(PLAN_4_1970, bracket))
        # A sentence that merely CONTAINS an insertion is still the plan's own.
        self.assertTrue(ni.quote_outside_brackets(
            "a [b] c", "a [b] c"))

    def test_the_amendments_notes_struck_out_law_is_refused_by_both_readers(self):
        senate = ni.load_instrument(SENATE_ORDER)
        page = (ni.FIXTURE_DIR / SENATE).read_text(encoding="utf-8")
        self.assertIn("struck out former subsec. (d) which read as follows", page.replace("\n", " "))
        self.assertEqual("only in an Amendments note, which prints the law as it used to read",
                         ni.where_is(senate, REPEALED_4571))
        self.assertIn("Amendments note", notes_quote_problem(SENATE_ORDER, REPEALED_4571))

    def test_an_older_note_on_the_same_page_is_outside_the_order(self):
        older = ("the rates of gross compensation of the Secretary for the Majority of the Senate, the Secretary for "
                 "the Minority of the Senate")
        senate = ni.load_instrument(SENATE_ORDER)
        self.assertEqual("on the page but outside the instrument", ni.where_is(senate, older))
        self.assertIsNotNone(notes_quote_problem(SENATE_ORDER, older))
        house = ni.load_instrument(HOUSE_ORDER)["text"]
        self.assertNotIn("Effective Date of 2019 Amendment", house)
        self.assertNotIn("Amendments", house)

    def test_no_name_a_date_line_or_a_signature_prints_reaches_either_reader(self):
        """Plant a sentinel where each page prints a person's name -- the
        Speaker's date line, the President pro tempore's signature, a plan's
        signature -- and assert it reaches nothing either reader returns."""
        sentinel = "ZZSENTINELNAMEZZ"
        cases = {
            HOUSE: (HOUSE_ORDER, lambda raw: raw.replace(
                '<h4 class="note-head">Speaker ', '<h4 class="note-head">Speaker {} '.format(sentinel), 1)),
            SENATE: (SENATE_ORDER, lambda raw: raw.replace(
                '<p class="presidential-signature">', '<p class="presidential-signature">{} '.format(sentinel), 1)),
            APPENDIX: ("reorganization-plan-no-10-of-1950", lambda raw: raw.replace(
                '<p class="presidential-signature">Harry', '<p class="presidential-signature">{} Harry'.format(sentinel), 1)),
        }
        for fixture, (instrument_id, transform) in cases.items():
            with self.subTest(fixture=fixture):
                tmp = _doctored(fixture, transform)
                self.assertIn(sentinel, (tmp / fixture).read_text(encoding="utf-8"))
                loaded = ni.load_instrument(instrument_id, tmp)
                self.assertNotIn(sentinel, json.dumps(loaded))
                with _GateFixtureDir(tmp):
                    self.assertNotIn(sentinel, json.dumps(notes_instrument_text(instrument_id)))
        # And on the committed pages, the printed names themselves, in the
        # instrument's own text and particulars. (`page` is the rest of the
        # GPO page with signatures and the date line removed, kept only to say
        # where a stray quote was found; other plans' prose on the Appendix
        # page may mention a president by name, which is not this
        # instrument's signer and is never published.)
        for instrument_id in (HOUSE_ORDER, SENATE_ORDER, "reorganization-plan-no-10-of-1950", PLAN_4_1970):
            loaded = ni.load_instrument(instrument_id)
            own = json.dumps({k: v for k, v in loaded.items() if k != "page"})
            for name in ("Johnson", "Murray", "Truman", "Nixon"):
                self.assertNotIn(name, own)
        for instrument_id, name in ((HOUSE_ORDER, "Johnson"), (SENATE_ORDER, "Murray")):
            self.assertNotIn(name, ni.load_instrument(instrument_id)["page"])
            self.assertNotIn(name, json.dumps(ni.instrument_block(ni.load_instrument(instrument_id))))

    def test_each_instrument_records_its_name_date_and_issuer_as_printed(self):
        for instrument_id, spec in ni.INSTRUMENTS.items():
            with self.subTest(instrument=instrument_id):
                block = ni.instrument_block(ni.load_instrument(instrument_id))
                for key in ("name", "date", "issuer", "effective", "printedIn", "kind"):
                    self.assertTrue(block[key])
                if spec["kind"] == ni.KIND_CHAMBER_PAY_ORDER:
                    self.assertIn("2024 edition of the United States Code", block["laterOrderCaution"])
                    self.assertIn("later order", block["laterOrderCaution"])
                else:
                    self.assertNotIn("laterOrderCaution", block)

    def test_a_wrong_date_a_missing_heading_or_a_heading_inside_an_amendments_note_is_unreadable(self):
        doctorings = {
            "the order redated": (SENATE, SENATE_ORDER, lambda raw: raw.replace(
                '<h4 class="note-head">March 25, 2024</h4>', '<h4 class="note-head">March 26, 2024</h4>')),
            "the order's heading respelled": (HOUSE, HOUSE_ORDER, lambda raw: raw.replace(
                "Order of the Speaker of the House of Representatives</h4>", "Order of the Speaker</h4>")),
            "the order's heading moved into the Amendments note": (SENATE, SENATE_ORDER, lambda raw: raw.replace(
                '<h4 class="note-head">Amendments</h4>',
                '<h4 class="note-head">Amendments</h4><h4 class="note-head">Order of the President Pro Tempore of the United States Senate</h4><h4 class="note-head">March 25, 2024</h4>').replace(
                '<!-- field-start:miscellaneous-note -->\n<h4 class="note-head">Order of the President Pro Tempore of the United States Senate</h4>',
                '<!-- field-start:miscellaneous-note -->\n<h4 class="note-head">Order (moved)</h4>')),
            "a second plan printed under the same heading": (APPENDIX, PLAN_4_1970, lambda raw: raw.replace(
                "<strong>REORGANIZATION PLAN NO. 1 OF 1971</strong>", "<strong>REORGANIZATION PLAN NO. 4 OF 1970</strong>")),
        }
        for name, (fixture, instrument_id, transform) in doctorings.items():
            with self.subTest(case=name):
                tmp = _doctored(fixture, transform)
                with self.assertRaises(ni.Unreadable):
                    ni.load_instrument(instrument_id, tmp)
                with _GateFixtureDir(tmp):
                    self.assertNotIsInstance(notes_instrument_text(instrument_id), dict)


class PlantedRepealTests(unittest.TestCase):
    """A repealed sentence planted in the same notes is refused, and a
    "Prior to amendment" marker planted inside an order cuts it there."""

    def test_a_repealed_variant_planted_in_the_amendments_note_is_refused(self):
        repealed = "The annual rate of compensation of the Chaplain shall be equal to the annual rate for level III."
        tmp = _doctored(SENATE, lambda raw: raw.replace(
            '<h4 class="note-head">Amendments</h4>',
            '<h4 class="note-head">Amendments</h4>\n<p class="note-body">Prior to amendment, sec. 3 read as follows: '
            '&quot;{}&quot;</p>'.format(repealed), 1))
        loaded = ni.load_instrument(SENATE_ORDER, tmp)
        self.assertEqual("only in an Amendments note, which prints the law as it used to read",
                         ni.where_is(loaded, repealed))
        with _GateFixtureDir(tmp):
            self.assertIn("Amendments note", notes_quote_problem(SENATE_ORDER, repealed))
            # The real rows still stand: the plant is in the notes, not the order.
            for row in INSTRUMENT_PROVISIONS.values():
                if row["instrument"] == SENATE_ORDER:
                    self.assertIsNone(notes_quote_problem(SENATE_ORDER, row["quote"]))

    def test_a_prior_text_marker_planted_inside_the_order_cuts_every_sentence_after_it(self):
        tmp = _doctored(HOUSE, lambda raw: raw.replace(
            '<p class="note-body"><i>Ordered,</i></p>',
            '<p class="note-body"><i>Ordered,</i></p>\n<p class="note-body">Prior to amendment, text read as follows:</p>', 1))
        records, report = _records(directory=tmp)
        for node_id, row in INSTRUMENT_PROVISIONS.items():
            if row["instrument"] == HOUSE_ORDER:
                self.assertNotIn(node_id, records)
                self.assertIn("does not carry the quoted sentence", report["refused"][node_id])
        with _GateFixtureDir(tmp):
            self.assertIsNotNone(notes_quote_problem(HOUSE_ORDER, TIER_REFERENCE_INSTRUMENT_ROWS[
                "leg-house-clerk-clerk-of-the-house"][6]))


def _tree():
    """The posts the instrument rows price, the Office nodes of the same names
    beside them, and the same-named posts elsewhere that no row may reach."""
    return {
        "id": "the-constitution-of-the-united-states", "name": "The Constitution", "type": "Foundation",
        "children": [
            {"id": "exec-dept-doc", "name": "Department of Commerce (DOC)", "type": "Cabinet Department", "children": [
                {"id": "exec-dept-doc-deputy-secretary-of-department-of-commerce",
                 "name": "Deputy Secretary of Department of Commerce", "type": "Position"},
                {"id": "exec-dept-doc-noaa", "name": "NOAA — National Oceanic & Atmospheric Administration", "type": "Bureau",
                 "children": [
                     {"id": "exec-dept-doc-noaa-deputy-administrator", "name": "Deputy Administrator", "type": "Position"},
                     {"id": "exec-dept-doc-noaa-chief-scientist", "name": "Chief Scientist", "type": "Position"},
                 ]},
            ]},
            {"id": "leg-senate", "name": "U.S. Senate", "type": "Chamber", "children": [
                {"id": "leg-senate-admin", "name": "Senate Administration", "type": "Division", "children": [
                    {"id": "leg-senate-admin-secretary", "name": "Secretary of the Senate", "type": "Office", "children": [
                        {"id": "leg-senate-admin-secretary-secretary-of-the-senate", "name": "Secretary of the Senate", "type": "Position"},
                    ]},
                    {"id": "leg-senate-admin-saa", "name": "Sergeant at Arms of the Senate", "type": "Office", "children": [
                        {"id": "leg-senate-admin-saa-sergeant-at-arms", "name": "Sergeant at Arms", "type": "Position"},
                    ]},
                ]},
                {"id": "leg-senate-offices", "name": "Individual Senator Offices (100)", "type": "Division", "children": [
                    {"id": "leg-senate-offices-legislative-counsel", "name": "Legislative Counsel", "type": "Position"},
                ]},
            ]},
            {"id": "leg-house", "name": "U.S. House of Representatives", "type": "Chamber", "children": [
                {"id": "leg-house-admin", "name": "House Administration", "type": "Division", "children": [
                    {"id": "leg-house-clerk", "name": "Clerk of the House", "type": "Office", "children": [
                        {"id": "leg-house-clerk-clerk-of-the-house", "name": "Clerk of the House", "type": "Position"},
                    ]},
                    {"id": "leg-house-cao", "name": "Chief Administrative Officer", "type": "Office", "children": [
                        {"id": "leg-house-cao-chief-administrative-officer", "name": "Chief Administrative Officer", "type": "Position"},
                    ]},
                ]},
            ]},
            {"id": "leg-support-gao", "name": "Government Accountability Office (GAO)", "type": "Agency", "children": [
                {"id": "leg-support-gao-chief-administrative-officer", "name": "Chief Administrative Officer", "type": "Position"},
            ]},
            {"id": "exec-regulatory-sec", "name": "Securities and Exchange Commission (SEC)", "type": "Independent Agency", "children": [
                {"id": SEC_CHAIR, "name": "Chair, SEC", "type": "Position"},
            ]},
        ],
    }


def _records(tree=None, directory=ni.FIXTURE_DIR):
    loaded = load_executive_schedule()
    node_map, parent_map = index_tree(tree or _tree())
    fiscal_year = federal_fiscal_year_of(date.fromisoformat(str(loaded["table"]["effective"])))
    return build_records(node_map, parent_map, loaded, fiscal_year=fiscal_year, directory=directory)


class MirrorTests(unittest.TestCase):
    def test_the_gate_mirrors_every_instrument(self):
        self.assertEqual(set(ni.INSTRUMENTS), set(NOTES_INSTRUMENTS))
        for instrument_id, spec in ni.INSTRUMENTS.items():
            with self.subTest(instrument=instrument_id):
                mirrored = NOTES_INSTRUMENTS[instrument_id]
                self.assertEqual(
                    (spec["kind"], spec["fixture"], spec["heading"], spec["name"], spec["issuer"], spec["date"],
                     spec["effective"], spec["printedIn"], spec.get("notesSection"), spec.get("officer")),
                    mirrored)
                self.assertEqual(ni.later_order_caution(spec) if spec["kind"] == ni.KIND_CHAMBER_PAY_ORDER else None,
                                 notes_instrument_caution(instrument_id))
        self.assertEqual(ni._LATER_ORDER_CAUTION, NOTES_INSTRUMENT_LATER_ORDER_CAUTION)

    def test_the_gate_mirrors_every_instrument_row_by_node_id(self):
        self.assertEqual(set(INSTRUMENT_PROVISIONS), set(TIER_REFERENCE_INSTRUMENT_ROWS))
        for node_id, row in INSTRUMENT_PROVISIONS.items():
            with self.subTest(node=node_id):
                self.assertEqual(
                    (row["nodeName"], row["office"], row["citation"], row["instrument"], row["subsection"],
                     row["level"], row["quote"], row.get("definitionQuote")),
                    TIER_REFERENCE_INSTRUMENT_ROWS[node_id])
                self.assertEqual(0, row["percent"])

    def test_the_gate_mirrors_the_plan_based_reviewed_row(self):
        self.assertEqual(set(ss.REVIEWED_INSTRUMENT_ROWS), set(US_CODE_REVIEWED_INSTRUMENT_IDENTIFICATIONS))
        self.assertFalse(set(ss.REVIEWED_INSTRUMENT_ROWS) & set(ss.REVIEWED_TITLE_ROWS))
        self.assertFalse(set(US_CODE_REVIEWED_INSTRUMENT_IDENTIFICATIONS) & set(US_CODE_REVIEWED_IDENTIFICATIONS))
        schedule = ss.load_schedule()
        for node_id, row in ss.REVIEWED_INSTRUMENT_ROWS.items():
            node_name, title, level, section, citation, fixture, quote, basis, class_title, instrument_id = \
                US_CODE_REVIEWED_INSTRUMENT_IDENTIFICATIONS[node_id]
            self.assertEqual((row["nodeName"], row["statutoryTitle"], row["basisCitation"], row["basisFixture"],
                              row["basisQuote"], row["basis"], row["basisInstrument"]),
                             (node_name, title, citation, fixture, quote, basis, instrument_id))
            self.assertFalse(class_title)
            position = schedule["index"][ss.canonical_name_key(title)]
            self.assertEqual((title, level, section), (position["title"], position["level"], position["section"]))

    def test_no_row_prices_an_office_node_or_a_same_named_post_elsewhere(self):
        node_map, _ = index_tree(_tree())
        for node_id in INSTRUMENT_PROVISIONS:
            self.assertEqual("Position", node_map[node_id]["type"])
        for office_id in ("leg-senate-admin-secretary", "leg-senate-admin-saa", "leg-house-clerk", "leg-house-cao",
                          "leg-senate-offices-legislative-counsel", "leg-support-gao-chief-administrative-officer"):
            self.assertNotIn(office_id, INSTRUMENT_PROVISIONS)
            self.assertNotIn(office_id, TIER_REFERENCE_INSTRUMENT_ROWS)
        self.assertIn("leg-senate-offices-legislative-counsel", INSTRUMENT_NOT_PRICED)


class BuildTests(unittest.TestCase):
    def test_the_seven_instrument_rows_are_priced_at_the_level_their_instrument_states(self):
        records, report = _records()
        self.assertEqual(set(INSTRUMENT_PROVISIONS), {k for k, v in records.items() if v.get("instrument")})
        self.assertEqual(7, report["pricedByInstrument"])
        expected = {
            "exec-dept-doc-noaa-deputy-administrator": "IV",
            "exec-dept-doc-noaa-chief-scientist": "V",
            "exec-dept-doc-deputy-secretary-of-department-of-commerce": "II",
            "leg-senate-admin-secretary-secretary-of-the-senate": "II",
            "leg-senate-admin-saa-sergeant-at-arms": "II",
            "leg-house-clerk-clerk-of-the-house": "II",
            "leg-house-cao-chief-administrative-officer": "II",
        }
        node_map, _ = index_tree(_tree())
        for node_id, level in expected.items():
            with self.subTest(node=node_id):
                record = records[node_id]
                self.assertEqual(level, record["level"])
                self.assertEqual(EXECUTIVE_SCHEDULE_RATES[level], record["amount"])
                self.assertIsNone(record["arithmetic"])
                self.assertEqual(PAY_METHOD, record["method"])
                self.assertEqual(2, len(record["documents"]))
                self.assertTrue(all(document["statesTheFigure"] is False for document in record["documents"]))
                instrument = record["instrument"]
                spec = ni.INSTRUMENTS[INSTRUMENT_PROVISIONS[node_id]["instrument"]]
                self.assertEqual((spec["name"], spec["date"], spec["issuer"]),
                                 (instrument["name"], instrument["date"], instrument["issuer"]))
                if spec["kind"] == ni.KIND_CHAMBER_PAY_ORDER:
                    self.assertEqual(ni.later_order_caution(spec), instrument["laterOrderCaution"])
                    self.assertEqual(ni.later_order_caution(spec), record["documents"][0]["laterOrderCaution"])
                out = fe.validate_record(record, node_map[node_id])
                self.assertEqual("partial", fe.classify(out))
        self.assertEqual(ni.INSTRUMENTS[SENATE_ORDER]["name"],
                         records["leg-senate-admin-saa-sergeant-at-arms"]["statute"])
        self.assertEqual(INSTRUMENT_PROVISIONS["leg-senate-admin-saa-sergeant-at-arms"]["definitionQuote"],
                         records["leg-senate-admin-saa-sergeant-at-arms"]["identification"]["instrumentDefines"])
        self.assertNotIn("instrumentDefines", records["leg-house-clerk-clerk-of-the-house"]["identification"])
        # The EPA Administrator's plan states no rate, and the NOAA
        # Administrator is priced from 15 U.S.C. 1503b: both are read and
        # declined with the reason on the record.
        for node_id in INSTRUMENT_NOT_PRICED:
            self.assertEqual(INSTRUMENT_NOT_PRICED[node_id], report["notPriced"][node_id])

    def test_a_doctored_instrument_makes_its_rows_fall(self):
        # The needle names NOAA's Deputy Administrator: the same Level IV
        # wording is printed for other plans' officers on the same page.
        needle = ("Deputy Administrator of the National Oceanic and Atmospheric Administration who shall be appointed "
                  "by the President, by and with the advice and consent of the Senate, and shall be compensated at the "
                  "rate now or hereafter provided for Level IV")
        tmp = _doctored(APPENDIX, lambda raw: raw.replace(needle, needle[: -len("Level IV")] + "Level III", 1))
        records, report = _records(directory=tmp)
        self.assertNotIn("exec-dept-doc-noaa-deputy-administrator", records)
        self.assertIn("does not carry the quoted sentence", report["refused"]["exec-dept-doc-noaa-deputy-administrator"])
        self.assertIn("exec-dept-doc-noaa-chief-scientist", records)
        # The SEC's reviewed row rests on another plan on the same page and
        # falls only when THAT plan stops printing its sentence.
        node_map, _ = index_tree(_tree())
        self.assertIn(SEC_CHAIR, ss.match_reviewed_rows(node_map, ss.load_schedule(), directory=tmp)["matched"])
        tmp2 = _doctored(APPENDIX, lambda raw: raw.replace(
            "choosing a Chairman from among the Commissioners composing the Commission are hereby transferred to "
            "the President", "choosing a Chairman from among the Commissioners composing the Commission are hereby "
            "reserved to the Commission", 1))
        result = ss.match_reviewed_rows(node_map, ss.load_schedule(), directory=tmp2)
        self.assertNotIn(SEC_CHAIR, result["matched"])
        self.assertIn(SEC_CHAIR, result["refusals"]["reviewed_row_basis_quote_not_in_its_instrument"])
        # A page whose bytes are not the fetch's is not read at all.
        bad = Path(tempfile.mkdtemp())
        for path in ni.FIXTURE_DIR.iterdir():
            shutil.copy(path, bad / path.name)
        (bad / HOUSE).write_text((bad / HOUSE).read_text(encoding="utf-8") + " ", encoding="utf-8")
        with self.assertRaises(ni.Unreadable):
            ni.load_instrument(HOUSE_ORDER, bad)

    def test_a_renamed_or_retyped_node_is_refused(self):
        tree = _tree()
        node_map, _ = index_tree(tree)
        node_map["leg-house-clerk-clerk-of-the-house"]["name"] = "Clerk"
        node_map["leg-senate-admin-saa-sergeant-at-arms"]["type"] = "Office"
        records, report = _records(tree)
        self.assertNotIn("leg-house-clerk-clerk-of-the-house", records)
        self.assertIn("renamed", report["refused"]["leg-house-clerk-clerk-of-the-house"])
        self.assertEqual("not a position", report["refused"]["leg-senate-admin-saa-sergeant-at-arms"])


class ApplyTests(unittest.TestCase):
    def test_the_block_carries_the_instrument_and_no_source_url(self):
        records, _ = _records()
        tree = _tree()
        apply_pay_evidence(tree, records, index_tree=index_tree)
        annotate_pay_documents(tree)
        node_map, _ = index_tree(tree)
        for node_id in INSTRUMENT_PROVISIONS:
            node = node_map[node_id]
            pay = node[FIELD]
            self.assertEqual(records[node_id]["instrument"], pay["instrument"])
            self.assertEqual(2, pay["verification"]["documents"])
            self.assertEqual(80, pay["verification"]["percent"])
            self.assertEqual(0, pay["verification"]["documentsStatingTheFigure"])
            self.assertIn("Reorganization Plan", pay["verification"]["caution"])
            for field in ("sourceUrls", "sourceTypes", "lastVerified", "verificationMethod"):
                self.assertIsNone(node.get(field))
        for office_id in ("leg-senate-admin-secretary", "leg-house-clerk", "leg-house-cao",
                          "leg-senate-offices-legislative-counsel", "leg-support-gao-chief-administrative-officer"):
            self.assertNotIn(FIELD, node_map[office_id])


class GateTests(unittest.TestCase):
    """Each dimension corrupted in turn, against blocks the gate accepts."""

    def setUp(self):
        records, _ = _records()
        self.tree = _tree()
        apply_pay_evidence(self.tree, records, index_tree=index_tree)
        annotate_pay_documents(self.tree)
        self.node_map, self.parent_map = index_tree(self.tree)

    def _check(self, node_id, pay=None):
        node = self.node_map[node_id]
        parent = self.node_map.get(self.parent_map.get(node_id) or "")
        return tier_reference_pay_violations(node, pay if pay is not None else node[FIELD], TODAY, _label,
                                             parent.get("name") if parent else None)

    def test_every_honest_block_passes(self):
        for node_id in INSTRUMENT_PROVISIONS:
            with self.subTest(node=node_id):
                self.assertEqual([], self._check(node_id))

    def test_each_way_an_instrument_block_can_be_faked_is_refused(self):
        clerk_id = "leg-house-clerk-clerk-of-the-house"
        secretary_id = "leg-senate-admin-secretary-secretary-of-the-senate"
        deputy_id = "exec-dept-doc-noaa-deputy-administrator"
        clerk = self.node_map[clerk_id][FIELD]
        secretary = self.node_map[secretary_id][FIELD]
        deputy = self.node_map[deputy_id][FIELD]
        no_caution = {k: v for k, v in clerk["instrument"].items() if k != "laterOrderCaution"}
        cases = {
            # The post and the office of the same name: the block cannot move
            # onto the Office node, and the CAO's cannot move onto the GAO's
            # post of the same name, nor the Senate's Legislative Counsel's
            # sentence onto a Senator's staff post of that name.
            "the Clerk's block on the Clerk's Office node": ("leg-house-clerk", clerk),
            "the Secretary's block on the Secretary's Office node": ("leg-senate-admin-secretary", secretary),
            "the House CAO's block on the GAO's CAO": ("leg-support-gao-chief-administrative-officer",
                                                       self.node_map["leg-house-cao-chief-administrative-officer"][FIELD]),
            "the Senate order's block on a Senator's Legislative Counsel": ("leg-senate-offices-legislative-counsel", secretary),
            # Two Level II blocks from two orders: keyed by id, never by figure.
            "the Senate block moved onto the Clerk": (clerk_id, secretary),
            "the House block moved onto the Secretary": (secretary_id, clerk),
            # The caution.
            "a pay order record without its later-order caution": (clerk_id, {**clerk, "instrument": no_caution}),
            "a later-order caution rewritten to reassure": (clerk_id, {**clerk, "instrument": {
                **clerk["instrument"], "laterOrderCaution": "This order is current."}}),
            "the caution dropped from the order's document": (clerk_id, {**clerk, "documents": [
                {k: v for k, v in clerk["documents"][0].items() if k != "laterOrderCaution"}] + clerk["documents"][1:]}),
            "a later-order caution on a plan": (deputy_id, {**deputy, "instrument": {
                **deputy["instrument"], "laterOrderCaution": clerk["instrument"]["laterOrderCaution"]}}),
            # The instrument's own particulars.
            "the order redated": (clerk_id, {**clerk, "instrument": {**clerk["instrument"], "date": "January 3, 2027"}}),
            "the issuer changed": (clerk_id, {**clerk, "instrument": {**clerk["instrument"], "issuer": "the Clerk"}}),
            "the instrument named as another": (deputy_id, {**deputy, "instrument": {
                **deputy["instrument"], "name": "Reorganization Plan No. 3 of 1970"}}),
            "no instrument block at all": (deputy_id, {k: v for k, v in deputy.items() if k != "instrument"}),
            "a digest that is not the committed page's": (deputy_id, {**deputy, "instrument": {
                **deputy["instrument"], "documentSha256": "0" * 64}}),
            # The quote: the Amendments note's struck-out law, another plan's
            # sentence, a level the instrument does not state.
            "a quote from the Amendments note": (secretary_id, {**secretary, "statuteQuote": REPEALED_4571}),
            "the Deputy priced at the Administrator's level": (deputy_id, {**deputy, "level": "III"}),
            "the Senate's definition dropped": (secretary_id, {**secretary, "identification": {
                k: v for k, v in secretary["identification"].items() if k != "instrumentDefines"}}),
            "a definition the order does not print": (secretary_id, {**secretary, "identification": {
                **secretary["identification"], "instrumentDefines": "the term level II means level III"}}),
            "a definition on a row that needs none": (clerk_id, {**clerk, "identification": {
                **clerk["identification"], "instrumentDefines": secretary["identification"]["instrumentDefines"]}}),
            "a document claiming to state the figure": (clerk_id, {**clerk, "documents": [
                {**clerk["documents"][0], "statesTheFigure": True}] + clerk["documents"][1:]}),
            "the instrument document cited to another section": (clerk_id, {**clerk, "documents": [
                {**clerk["documents"][0], "citation": "Order of the Speaker, sec. 2(a)"}] + clerk["documents"][1:]}),
            "arithmetic on an instrument row": (deputy_id, {**deputy, "arithmetic": {"operation": "plus_percent", "percent": 3}}),
            "a verified grade": (deputy_id, {**deputy, "financialEvidenceStatus": "verified"}),
        }
        for name, (node_id, pay) in cases.items():
            with self.subTest(case=name):
                self.assertNotEqual([], self._check(node_id, pay), name)

    def test_an_instrument_block_on_a_statute_row_is_refused(self):
        node = {"id": "leg-support-gao-comptroller-general-of-the-united-states",
                "name": "Comptroller General of the United States", "type": "Position"}
        pay = copy.deepcopy(self.node_map["leg-house-clerk-clerk-of-the-house"][FIELD])
        self.assertTrue(any("instrument" in v for v in tier_reference_pay_violations(
            node, pay, TODAY, _label, "Government Accountability Office (GAO)")))

    def test_a_quote_the_gate_reads_from_a_doctored_amendments_note_is_refused(self):
        """Move the order's sentence into the Amendments note on a doctored
        page: the published block quotes it exactly, and the gate's own reader
        refuses it because it is no longer the order's."""
        secretary_id = "leg-senate-admin-secretary-secretary-of-the-senate"
        sentence = TIER_REFERENCE_INSTRUMENT_ROWS[secretary_id][6]
        marker = "The annual rates of compensation of the Secretary of the Senate, the Sergeant at Arms and"

        def move(raw):
            raw = raw.replace(marker, "The annual rates of compensation of the Secretary for the Majority", 1)
            return raw.replace('<h4 class="note-head">Amendments</h4>',
                               '<h4 class="note-head">Amendments</h4>\n<p class="note-body">Prior to amendment, '
                               'sec. 2(a) read as follows: &quot;{}&quot;</p>'.format(sentence), 1)

        tmp = _doctored(SENATE, move)
        with _GateFixtureDir(tmp):
            out = self._check(secretary_id)
        self.assertTrue(any("Amendments note" in v for v in out), out)


class ReviewedScheduleGateTests(unittest.TestCase):
    """The SEC Chairman: a reviewed Schedule row whose basis is a plan."""

    def setUp(self):
        loaded = load_executive_schedule(DEFAULT_PAY_TABLE_HTML)
        self.tree = _tree()
        node_map, _ = index_tree(self.tree)
        matched = ss.match_reviewed_rows(node_map, ss.load_schedule())["matched"]
        fiscal_year = federal_fiscal_year_of(date.fromisoformat(str(loaded["table"]["effective"])))
        records, _ = ss.build_records({SEC_CHAIR: matched[SEC_CHAIR]}, loaded["table"], table_url=loaded["url"],
                                      table_sha256=loaded["sha256"], retrieved_at=loaded["fetched_at"],
                                      fiscal_year=fiscal_year)
        node = node_map[SEC_CHAIR]
        record = fe.validate_record(records[SEC_CHAIR], node)
        record["financialEvidenceStatus"] = fe.classify(record)
        for key in ("levelClaim", "rateText", "effectiveText", "table", "tableFootnotes"):
            record[key] = records[SEC_CHAIR][key]
        self.assertEqual(1, ss.apply_schedule_pay(self.tree, {SEC_CHAIR: record})["priced"])
        annotate_pay_documents(self.tree)
        self.node = index_tree(self.tree)[0][SEC_CHAIR]
        self.pay = self.node["positionSchedulePay"]

    def test_the_block_is_level_iii_from_the_code_with_the_plan_as_its_basis(self):
        self.assertEqual(("III", EXECUTIVE_SCHEDULE_RATES["III"], "Chairman, Securities and Exchange Commission"),
                         (self.pay["payLevel"], self.pay["amount"], self.pay["statutoryTitle"]))
        identification = self.pay["identification"]
        self.assertEqual("reorganization_plan", identification["basisDocumentKind"])
        self.assertEqual("Reorganization Plan No. 10 of 1950", identification["basisInstrument"]["name"])
        self.assertEqual("March 13, 1950", identification["basisInstrument"]["date"])
        self.assertEqual("the President", identification["basisInstrument"]["issuer"])
        self.assertEqual(3, self.pay["verification"]["documents"])
        self.assertEqual([], schedule_pay_violations(self.node, self.pay, TODAY, _label))
        for field in ("sourceUrls", "sourceTypes", "lastVerified", "verificationMethod"):
            self.assertNotIn(field, self.node)

    def test_each_way_the_plan_basis_can_be_faked_is_refused(self):
        identification = self.pay["identification"]
        cases = {
            "no document kind": {k: v for k, v in identification.items() if k != "basisDocumentKind"},
            "the kind called a section": {**identification, "basisDocumentKind": "us_code_section"},
            "no instrument block": {k: v for k, v in identification.items() if k != "basisInstrument"},
            "the plan redated": {**identification, "basisInstrument": {**identification["basisInstrument"], "date": "May 24, 1950"}},
            "a sentence from another plan": {**identification, "basisQuote": (
                "There shall be in the Agency a Deputy Administrator of the Environmental Protection Agency who "
                "shall be appointed by the President, by and with the advice and consent of the Senate.")},
            "the President's message quoted as the plan": {**identification, "basisQuote": (
                "I transmit herewith Reorganization Plan No. 10 of 1950, prepared in accordance with the "
                "Reorganization Act of 1949 and providing for reorganizations in the Securities and Exchange "
                "Commission.")},
            "a basis link that is not the page": {**identification, "basisUrl": "https://www.govinfo.gov/link/uscode/15/78d"},
        }
        for name, ident in cases.items():
            with self.subTest(case=name):
                self.assertNotEqual([], schedule_pay_violations(self.node, {**self.pay, "identification": ident},
                                                                TODAY, _label), name)
        # The block moved onto a node of a section-based row is refused too.
        other = {"id": "exec-regulatory-sec-commissioner-4", "name": "Commissioner (×4)", "type": "Position",
                 "representsPosts": {"text": "×4", "kind": "exact", "count": 4}}
        self.assertNotEqual([], schedule_pay_violations(other, self.pay, TODAY, _label))
        # And an instrument basis may not ride on a section-based row.
        fed_id = next(iter(US_CODE_REVIEWED_IDENTIFICATIONS))
        self.assertTrue(any("instrument" in v for v in gate.reviewed_schedule_violations(
            {"id": fed_id, "name": US_CODE_REVIEWED_IDENTIFICATIONS[fed_id][0], "type": "Position"},
            {**self.pay, "method": gate.US_CODE_REVIEWED_METHOD}, US_CODE_REVIEWED_IDENTIFICATIONS[fed_id], TODAY,
            _label)))


class PublishedGraphTests(unittest.TestCase):
    """Pass only after the coordinator's regenerate (2026-10-07): the seven
    instrument rows and the SEC Chairman published, nothing on an Office."""

    @unittest.skipUnless(GRAPH.exists(), "no published graph")
    def test_the_instrument_rows_are_published_and_no_office_node_carries_one(self):
        node_map, _ = index_tree(json.loads(GRAPH.read_text(encoding="utf-8")))
        for node_id in INSTRUMENT_PROVISIONS:
            self.assertIsInstance(node_map[node_id].get(FIELD), dict, node_id)
            self.assertIsInstance(node_map[node_id][FIELD].get("instrument"), dict, node_id)
        self.assertEqual("reorganization_plan",
                         node_map[SEC_CHAIR]["positionSchedulePay"]["identification"]["basisDocumentKind"])
        for office_id in ("leg-senate-admin-secretary", "leg-senate-admin-saa", "leg-house-clerk", "leg-house-cao",
                          "leg-senate-offices-legislative-counsel", "leg-support-gao-chief-administrative-officer"):
            self.assertNotIn(FIELD, node_map[office_id])
        for node in node_map.values():
            block = node.get(FIELD)
            if isinstance(block, dict) and isinstance(block.get("instrument"), dict) \
                    and block["instrument"].get("kind") == ni.KIND_CHAMBER_PAY_ORDER:
                self.assertIn("later order", block["instrument"]["laterOrderCaution"])


# ---------------------------------------------------------------------------
# The chambers' pay orders read in full (2026-10-08): every post node beneath
# the four officers they price is reached only by a ceiling, and each is
# declined with the order's own words, re-found on every run.

from data_pipeline.exporter.build_graph import DEFAULT_BASE_GRAPH, load_base_graph  # noqa: E402
from data_pipeline.verification.tier_reference_pay import INSTRUMENT_CEILINGS, ceiling_reason  # noqa: E402

#: The thirteenth batch's uscode.house.gov leads, every one a post the orders
#: reach only by a ceiling.
BATCH_13_SENATE_IDS = (
    "leg-senate-admin-saa-assistant-saa-capitol-division",
    "leg-senate-admin-saa-assistant-saa-senate-division",
    "leg-senate-admin-saa-capitol-police-liaison-officer",
    "leg-senate-admin-saa-deputy-sergeant-at-arms",
    "leg-senate-admin-saa-director-of-capitol-services",
    "leg-senate-admin-saa-director-of-doorkeeper-operations",
    "leg-senate-admin-saa-director-of-id-credentialing",
    "leg-senate-admin-saa-director-of-mailing-services",
    "leg-senate-admin-saa-director-of-senate-hair-care-services",
    "leg-senate-admin-saa-director-of-senate-parking",
    "leg-senate-admin-saa-director-of-senate-photo-studio",
    "leg-senate-admin-saa-director-of-senate-post-office",
    "leg-senate-admin-saa-director-of-senate-recording-studio",
    "leg-senate-admin-saa-director-of-telecommunications",
    "leg-senate-admin-saa-director-of-web-technology-innovation",
    "leg-senate-admin-secretary-assistant-secretary-of-the-senate",
    "leg-senate-admin-secretary-bill-clerk",
    "leg-senate-admin-secretary-deputy-secretary-of-the-senate",
    "leg-senate-admin-secretary-director-of-public-records",
    "leg-senate-admin-secretary-director-of-the-capitol-printing-folding-room",
    "leg-senate-admin-secretary-director-of-the-page-program",
    "leg-senate-admin-secretary-enrolling-clerk",
    "leg-senate-admin-secretary-executive-clerk",
    "leg-senate-admin-secretary-journal-clerk",
    "leg-senate-admin-secretary-legislative-information-officer",
    "leg-senate-admin-secretary-senate-curator",
    "leg-senate-admin-secretary-senate-historian",
    "leg-senate-admin-secretary-senate-librarian",
)

#: The offices each order states a RATE for beyond the four priced, which this
#: graph carries as no post node (an Office node, or nothing). If a post node
#: of one of these names is ever curated under a chamber, this test says so,
#: since the order would then price it.
RATE_OFFICES_WITH_NO_POST_NODE = (
    "Secretary for the Majority", "Secretary for the Minority", "Deputy Legislative Counsel", "Senior Counsel",
    "Chaplain", "Senate Legal Counsel", "Deputy Senate Legal Counsel", "General Counsel to the House",
    "Director of Interparliamentary Affairs", "Attending Physician",
)


def _base_tree():
    return load_base_graph(DEFAULT_BASE_GRAPH)


class OrderCeilingDeclineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = _base_tree()
        cls.nodes, cls.parents = index_tree(cls.tree)
        cls.records, cls.report = _records(tree=cls.tree)

    def test_each_ceiling_is_the_order_s_own_words_and_is_a_ceiling(self):
        for group_id, group in INSTRUMENT_CEILINGS.items():
            with self.subTest(group=group_id):
                instrument = ni.load_instrument(group["instrument"])
                self.assertEqual(ni.KIND_CHAMBER_PAY_ORDER, instrument["kind"])
                self.assertIsNone(ni.where_is(instrument, group["quote"]))
                self.assertTrue(any(word in group["quote"] for word in ("maximum", "shall not exceed", "in excess of")))
                # The quote states no rate: "shall each be equal to" is the
                # orders' rate wording, and a ceiling group never quotes it.
                self.assertNotIn("shall each be equal to", group["quote"])

    def test_each_declined_node_is_a_single_post_in_the_office_its_group_names(self):
        seen = set()
        for group_id, group in INSTRUMENT_CEILINGS.items():
            for node_id in group["nodes"]:
                with self.subTest(group=group_id, node=node_id):
                    self.assertNotIn(node_id, seen, "declined twice")
                    seen.add(node_id)
                    node = self.nodes[node_id]
                    self.assertEqual("Position", node["type"])
                    self.assertNotIn("representsPosts", node)
                    self.assertIn(self.parents[node_id], group["office"])
                    self.assertNotIn(node_id, INSTRUMENT_PROVISIONS)
                    self.assertNotIn(node_id, INSTRUMENT_NOT_PRICED)
        # Every unpriced post the four offices carry is accounted for.
        offices = {office for group in INSTRUMENT_CEILINGS.values() for office in group["office"]}
        for node_id, parent in self.parents.items():
            if parent in offices and self.nodes[node_id]["type"] == "Position" and node_id not in INSTRUMENT_PROVISIONS:
                self.assertIn(node_id, seen, node_id)

    def test_the_batch_s_senate_leads_are_all_declined_and_none_priced(self):
        for node_id in BATCH_13_SENATE_IDS:
            with self.subTest(node=node_id):
                self.assertNotIn(node_id, self.records)
                self.assertIn(node_id, self.report["notPriced"])
                self.assertIn("a ceiling is not a rate", self.report["notPriced"][node_id])

    def test_the_derive_records_each_decline_with_the_order_s_words(self):
        for group_id, group in INSTRUMENT_CEILINGS.items():
            name = ni.INSTRUMENTS[group["instrument"]]["name"]
            for node_id in group["nodes"]:
                with self.subTest(node=node_id):
                    self.assertEqual(ceiling_reason(group, name), self.report["notPriced"][node_id])
                    self.assertIn(group["quote"], self.report["notPriced"][node_id])
        self.assertFalse([k for k in self.report["refused"] if k in INSTRUMENT_CEILINGS])

    def test_a_ceiling_the_order_no_longer_prints_is_a_refusal_not_a_silent_decline(self):
        needle = "be paid gross compensation at an annual rate that is in excess of the annual rate for level II"
        tmp = _doctored(SENATE, lambda raw: raw.replace(needle, "be paid at a rate set by the Secretary", 1))
        _, report = _records(tree=self.tree, directory=tmp)
        self.assertIn("senate-order-sec-4b", report["refused"])
        self.assertIn("does not carry the ceiling", report["refused"]["senate-order-sec-4b"])
        for node_id in INSTRUMENT_CEILINGS["senate-order-sec-4b"]["nodes"]:
            self.assertNotIn(node_id, report["notPriced"])
        # The other groups are untouched.
        for node_id in INSTRUMENT_CEILINGS["senate-order-sec-2c"]["nodes"]:
            self.assertIn(node_id, report["notPriced"])

    def test_the_offices_the_orders_set_a_rate_for_have_no_post_node_here(self):
        for node_id, node in self.nodes.items():
            if not node_id.startswith(("leg-senate", "leg-house")) or node.get("type") != "Position":
                continue
            name = str(node.get("name") or "")
            for office in RATE_OFFICES_WITH_NO_POST_NODE:
                with self.subTest(node=node_id, office=office):
                    self.assertNotEqual(office.casefold(), name.casefold())


if __name__ == "__main__":
    unittest.main()
