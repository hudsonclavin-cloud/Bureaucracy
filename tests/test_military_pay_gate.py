"""The release gate's half of military basic pay (`positionMilitaryPay`), pinned
in both directions: the gate's mirrors equal the module's tables, the gate's
own stdlib reader re-parses Schedule 8 out of the committed note to the same
three figures, every honest block built from the real records passes, and
every way a block can be faked is refused with its own sentence."""

from __future__ import annotations

import copy
import json
import re
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from data_pipeline.exporter.build_graph import (
    DEFAULT_BASE_GRAPH,
    annotate_stated_counts,
    index_tree,
    is_post_node,
    load_base_graph,
)
from data_pipeline.verification import financial_evidence as fe
from data_pipeline.verification import military_pay as mp
from data_pipeline.verification.pay_documents import PAY_DOCUMENT_FIELDS, annotate_pay_documents
from data_pipeline.verification.pay_tables import (
    OFFICE_RATE_PAY_FIELDS,
    federal_fiscal_year_of,
    withdraw_pay_from_multi_post_nodes,
)
from scripts import validate_published_graph as gate

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GRAPH = PROJECT_ROOT / "output" / "graph.json"
TODAY = date.today().isoformat()
FIELD = mp.FIELD

ARMY_CHIEF = "exec-dept-defense-army-chief-of-staff-of-the-army-4-star-general"
ARMY_VICE = "exec-dept-defense-army-vice-chief-of-staff-of-the-army"
SPACE_CHIEF = "exec-dept-defense-sf-chief-of-space-operations-4-star-general"
JCS_COPY_OF_ARMY_CHIEF = "exec-dept-defense-jcs-chief-of-staff-of-the-army"
AIR_FORCE_CMSAF = "exec-dept-defense-af-chief-master-sergeant-of-the-air-force"
COAST_GUARD_MCPO = "exec-dept-dhs-uscg-master-chief-petty-officer-of-the-coast-guard"


def _label(node):
    return "node {!r}".format(node.get("id"))


_BUILT = {}


def _built():
    """The real records applied to the real base graph, once per test run:
    `build_records` on the curated file, `apply_pay_evidence`, the multi-post
    sweep and the document-count pass, exactly the order the exporter uses."""
    if not _BUILT:
        tree = load_base_graph(DEFAULT_BASE_GRAPH)
        node_map, parent_map = index_tree(tree)
        loaded = mp.load_schedule_8()
        fiscal_year = federal_fiscal_year_of(date(int(loaded["schedule"]["year"]), 1, 1))
        records, report = mp.build_records(node_map, parent_map, loaded, fiscal_year=fiscal_year)
        mp.apply_pay_evidence(tree, records, index_tree=index_tree)
        annotate_stated_counts(tree)
        withdraw_pay_from_multi_post_nodes(tree)
        annotate_pay_documents(tree)
        node_map, parent_map = index_tree(tree)
        _BUILT.update({
            "tree": tree, "node_map": node_map, "parent_map": parent_map,
            "records": records, "report": report, "loaded": loaded,
        })
    return _BUILT


class MirrorTests(unittest.TestCase):
    """The gate imports nothing from the module, so each table it mirrors is
    pinned equal here, field by field."""

    def test_the_gate_mirrors_every_grade_row_field_by_field(self):
        self.assertEqual(set(mp.GRADE_PROVISIONS), set(gate.MILITARY_GRADE_ROWS))
        for node_id, row in mp.GRADE_PROVISIONS.items():
            with self.subTest(node=node_id):
                mirrored = gate.MILITARY_GRADE_ROWS[node_id]
                self.assertEqual(9, len(mirrored))
                node_name, office, citation, fixture, grade, pay_grade, quote, office_quote, space_force = mirrored
                self.assertEqual(row["nodeName"], node_name)
                self.assertEqual(row["office"], office)
                self.assertEqual(row["citation"], citation)
                self.assertEqual(row["fixture"], fixture)
                self.assertEqual(row["grade"], grade)
                self.assertEqual(mp.GRADE_WORD_TO_PAY_GRADE[row["grade"]], pay_grade)
                self.assertEqual("O-10", pay_grade)
                self.assertEqual(row["quote"], quote)
                self.assertEqual(row.get("officeQuote"), office_quote)
                self.assertEqual(bool(row.get("spaceForce")), space_force)

    def test_the_gate_mirrors_the_strings_the_module_publishes(self):
        self.assertEqual(mp.FIELD, gate.MILITARY_PAY_FIELD)
        self.assertEqual(mp.PAY_SOURCE, gate.MILITARY_PAY_SOURCE)
        self.assertEqual(mp.PAY_METHOD_GRADE, gate.MILITARY_PAY_METHOD_GRADE)
        self.assertEqual(mp.PAY_METHOD_NAMED, gate.MILITARY_PAY_METHOD_NAMED)
        self.assertEqual(mp.ARITHMETIC_OPERATION, gate.MILITARY_PAY_OPERATION)
        self.assertEqual(mp.MONTHS_IN_A_YEAR, gate.MILITARY_PAY_FACTOR)
        self.assertEqual(mp.MAPPING_FIXTURE, gate.MILITARY_MAPPING_FIXTURE)
        self.assertEqual(mp.MAPPING_CITATION, gate.MILITARY_MAPPING_CITATION)
        self.assertEqual(mp.SPACE_FORCE_MAPPING_CITATION, gate.MILITARY_SPACE_FORCE_MAPPING_CITATION)
        self.assertEqual(mp.PAY_GRADE_ROWS["O-10"], gate.MILITARY_MAPPING_ROW)
        # The en dash and the word joiner are the publisher's, not a typo.
        self.assertIn("–⁠", gate.MILITARY_MAPPING_ROW)
        self.assertEqual(mp.SPACE_FORCE_MAPPING_QUOTE, gate.MILITARY_SPACE_FORCE_SENTENCE)
        self.assertEqual(mp._NAVY_OR_COAST_GUARD.pattern, gate.MILITARY_FOOTNOTE_ITEM_RULE.pattern)
        self.assertEqual(mp.SCHEDULE_NUMBER, gate.MILITARY_SCHEDULE_NUMBER)
        self.assertEqual(mp.SCHEDULE_TITLE, gate.MILITARY_SCHEDULE_TITLE)
        self.assertEqual(mp.PART_I_HEADING, gate.MILITARY_SCHEDULE_PART_HEADING)
        self.assertEqual(tuple(mp._SECOND_BLOCK_HEAD), gate.MILITARY_SCHEDULE_SECOND_BLOCK_HEAD)
        self.assertEqual(mp._FOOTNOTE_OPEN, gate.MILITARY_FOOTNOTE_OPEN)
        self.assertEqual(mp._CAP_FOOTNOTE_OPEN, gate.MILITARY_CAP_FOOTNOTE_OPEN)
        self.assertEqual(
            PROJECT_ROOT / "tests" / "fixtures" / "uscode" / "pay_schedules_5_usc_5332.html",
            Path(gate.MILITARY_SCHEDULE_FIXTURE),
        )

    def test_the_gates_not_priced_ids_cover_the_modules_and_name_real_posts(self):
        node_map, _ = index_tree(load_base_graph(DEFAULT_BASE_GRAPH))
        module_node_ids = {key for key in mp.NOT_PRICED if key in node_map}
        # 2026-10-07: 2 -> 1; the Space Force's adviser was renamed and priced.
        self.assertEqual(1, len(module_node_ids), module_node_ids)
        self.assertNotIn("exec-dept-defense-sf-senior-enlisted-advisor", gate.MILITARY_NOT_PRICED_NODE_IDS)
        self.assertTrue(module_node_ids <= gate.MILITARY_NOT_PRICED_NODE_IDS)
        # The nine combatant commanders without a grade statute and the six
        # JCS copies of the service chiefs are named by id here, and every id
        # is a post in the curated file.
        commanders = {i for i in gate.MILITARY_NOT_PRICED_NODE_IDS if "-cocom-" in i}
        copies = {i for i in gate.MILITARY_NOT_PRICED_NODE_IDS if i.startswith("exec-dept-defense-jcs-")}
        self.assertEqual(9, len(commanders))
        self.assertEqual(6, len(copies))
        self.assertEqual(16, len(gate.MILITARY_NOT_PRICED_NODE_IDS))  # 17 until 2026-10-07
        for node_id in gate.MILITARY_NOT_PRICED_NODE_IDS:
            with self.subTest(node=node_id):
                self.assertIn(node_id, node_map)
                self.assertTrue(is_post_node(node_map[node_id]))
                self.assertNotIn(node_id, gate.MILITARY_GRADE_ROWS)
        # The two combatant commanders whose grade a statute fixes are priced,
        # not refused.
        for node_id in ("exec-dept-defense-cocom-ussocom-commander-ccdr-ussocom",
                        "exec-dept-defense-cocom-uscybercom-commander-ccdr-uscybercom"):
            self.assertIn(node_id, gate.MILITARY_GRADE_ROWS)
            self.assertNotIn(node_id, gate.MILITARY_NOT_PRICED_NODE_IDS)

    def test_the_gate_mirrors_the_office_rate_classes(self):
        self.assertEqual(set(OFFICE_RATE_PAY_FIELDS), set(gate.OFFICE_RATE_PAY_FIELDS))
        self.assertIn(FIELD, gate.OFFICE_RATE_PAY_FIELDS)
        self.assertNotIn(FIELD, gate.INCUMBENCY_PAY_FIELDS)

    def test_the_document_count_mirrors_carry_the_field(self):
        self.assertEqual((("documents", "*", "url"),), gate.PAY_DOCUMENT_URL_KEYS[FIELD])
        self.assertEqual(0, gate.PAY_DOCUMENT_STATES_FIGURE[FIELD])
        self.assertEqual(tuple(PAY_DOCUMENT_FIELDS[FIELD]["urlKeys"]), gate.PAY_DOCUMENT_URL_KEYS[FIELD])
        self.assertEqual(PAY_DOCUMENT_FIELDS[FIELD]["statesTheFigure"], gate.PAY_DOCUMENT_STATES_FIGURE[FIELD])

    def test_an_alias_may_never_appear_on_the_block(self):
        self.assertIn(FIELD, gate.ALIAS_FORBIDDEN_BLOCKS)

    def test_a_citations_section_is_read_without_its_subsection(self):
        self.assertEqual("10 U.S.C. 167b", gate._military_section_of("10 U.S.C. 167b(c)"))
        self.assertEqual("10 U.S.C. 10502", gate._military_section_of("10 U.S.C. 10502(e)(1)"))
        self.assertEqual("14 U.S.C. 302", gate._military_section_of("14 U.S.C. 302"))
        # A trailing word is not part of the section the URL must address.
        self.assertEqual("5 U.S.C. 5332", gate._military_section_of("5 U.S.C. 5332 note"))
        self.assertEqual("", gate._military_section_of("Schedule 8"))


class ReaderTests(unittest.TestCase):
    """The gate's second, independent reader of Schedule 8."""

    def test_the_committed_note_reparses_to_the_three_figures(self):
        schedule = gate.military_schedule_8()
        self.assertIsNone(schedule.get("error"))
        self.assertTrue(schedule["digestMatches"])
        meta = json.loads(Path(str(gate.MILITARY_SCHEDULE_FIXTURE) + ".meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["sha256"], schedule["sha256"])
        self.assertEqual(meta["url"], schedule["url"])
        self.assertEqual("(Effective January 1, 2026)", schedule["effective"])
        self.assertEqual("2026", schedule["year"])
        o10 = schedule["o10"]
        self.assertTrue(o10["flat"])
        self.assertEqual("18,999.90", o10["amountRaw"])
        self.assertEqual(11, o10["populated"])
        self.assertEqual(0, o10["firstBlockPopulated"])
        self.assertEqual(["1"], o10["marks"])
        self.assertTrue(o10["allMarked"])
        self.assertEqual(["$18,999.90"] * 11, o10["figures"])
        self.assertEqual("O–⁠10", o10["label"])
        self.assertEqual("11,166.90", schedule["footnote"]["amountRaw"])
        self.assertEqual("$11,166.90", schedule["footnote"]["amountAsPrinted"])
        self.assertEqual("E-9", schedule["footnote"]["grade"])
        self.assertEqual(7, len(schedule["footnote"]["items"]))
        self.assertEqual(8, len(schedule["footnote"]["titles"]))
        self.assertEqual("18,899.90", schedule["cap"]["amountRaw"])
        self.assertIn("$18,899.90 per month", schedule["cap"]["text"])
        self.assertTrue(schedule["cap"]["text"].startswith(gate.MILITARY_CAP_FOOTNOTE_OPEN))
        self.assertTrue(schedule["footnote"]["text"].startswith(gate.MILITARY_FOOTNOTE_OPEN))

    def test_the_two_readers_agree_on_the_bytes(self):
        ours = gate.military_schedule_8()
        theirs = mp.load_schedule_8()["schedule"]
        self.assertEqual(theirs["officerRows"]["O-10"]["flatAmountRaw"], ours["o10"]["amountRaw"])
        self.assertEqual(theirs["officerRows"]["O-10"]["rowText"], ours["o10"]["rowText"])
        self.assertEqual(theirs["seniorEnlistedFootnote"]["text"], ours["footnote"]["text"])
        self.assertEqual(theirs["seniorEnlistedFootnote"]["items"], ours["footnote"]["items"])
        self.assertEqual(theirs["seniorEnlistedFootnote"]["monthlyAmountRaw"], ours["footnote"]["amountRaw"])
        self.assertEqual(theirs["seniorEnlistedFootnote"]["titles"], ours["footnote"]["titles"])
        self.assertEqual(theirs["capFootnote"]["text"], ours["cap"]["text"])
        self.assertEqual(theirs["capFootnote"]["monthlyAsPrinted"], ours["cap"]["amountAsPrinted"])
        self.assertEqual(theirs["effective"], ours["effective"])

    def test_the_navy_or_coast_guard_item_reads_as_two_offices_by_the_mirrored_rule(self):
        items = gate.military_schedule_8()["footnote"]["items"]
        self.assertIn("Master Chief Petty Officer of the Navy or Coast Guard", items)
        titles = gate.military_footnote_titles(items)
        self.assertEqual(mp.footnote_titles(items), titles)
        navy = [t for t in titles if t["title"] == "Master Chief Petty Officer of the Navy"]
        coast_guard = [t for t in titles if t["title"] == "Master Chief Petty Officer of the Coast Guard"]
        self.assertEqual(1, len(navy))
        self.assertEqual(1, len(coast_guard))
        self.assertEqual("Master Chief Petty Officer of the Navy or Coast Guard", navy[0]["printedItem"])
        self.assertEqual(navy[0]["printedItem"], coast_guard[0]["printedItem"])
        # Every other item names one office and is quoted whole.
        for entry in titles:
            if entry not in navy + coast_guard:
                self.assertEqual(entry["title"], entry["printedItem"])

    def test_a_doctored_note_is_refused_or_read_as_not_flat(self):
        source = Path(gate.MILITARY_SCHEDULE_FIXTURE)
        meta = source.with_name(source.name + ".meta.json")
        with tempfile.TemporaryDirectory() as tmp:
            # One O-10 cell altered: the digest no longer matches and the row
            # is no longer one figure, so no monthly rate can stand for it.
            copy_path = Path(tmp) / source.name
            raw = source.read_bytes()
            self.assertIn(b"$18,999.90", raw)
            copy_path.write_bytes(raw.replace(b"$18,999.90", b"$18,999.91", 1))
            shutil.copy(meta, Path(tmp) / meta.name)
            doctored = gate.military_schedule_8(copy_path)
            self.assertIsNone(doctored.get("error"))
            self.assertFalse(doctored["digestMatches"])
            self.assertFalse(doctored["o10"]["flat"])
            self.assertIsNone(doctored["o10"]["amountRaw"])
            # The schedule's title changed: nothing is read at all.
            retitled = Path(tmp) / "retitled.html"
            retitled.write_bytes(raw.replace(b"Pay of the Uniformed Services", b"Pay of Somebody Else", 1))
            shutil.copy(meta, Path(tmp) / "retitled.html.meta.json")
            self.assertIn("error", gate.military_schedule_8(retitled))
            # No .meta.json beside it: an undated fetch cannot be cited.
            undated = Path(tmp) / "undated.html"
            undated.write_bytes(raw)
            self.assertIn("error", gate.military_schedule_8(undated))


class GateTests(unittest.TestCase):
    """Every honest block passes; each dimension corrupted in turn is refused
    with its own sentence."""

    def setUp(self):
        built = _built()
        self.node_map = built["node_map"]
        self.parent_map = built["parent_map"]
        self.records = built["records"]

    def _check(self, node_id, pay=None, node=None):
        node = node if node is not None else self.node_map[node_id]
        parent = self.node_map.get(self.parent_map.get(node_id) or "")
        return gate.military_pay_violations(
            node, pay if pay is not None else node[FIELD], TODAY, _label, parent.get("name") if parent else None)

    def test_the_real_records_price_seventeen_grades_and_six_footnote_posts(self):
        # 22 and 5 until the 2026-10-07 rename of the Space Force's adviser.
        self.assertEqual(23, len(self.records))
        kinds = [r["identification"]["kind"] for r in self.records.values()]
        self.assertEqual(17, kinds.count("grade_fixed_by_statute"))
        self.assertEqual(6, kinds.count("named_in_footnote"))
        self.assertEqual(set(mp.GRADE_PROVISIONS), {i for i, r in self.records.items() if r["identification"]["kind"] == "grade_fixed_by_statute"})
        for node_id in gate.MILITARY_NOT_PRICED_NODE_IDS:
            self.assertNotIn(node_id, self.records)
            self.assertNotIn(FIELD, self.node_map[node_id])

    def test_every_honest_block_passes_both_checkers(self):
        for node_id in self.records:
            with self.subTest(node=node_id):
                node = self.node_map[node_id]
                self.assertIsInstance(node.get(FIELD), dict)
                self.assertEqual([], self._check(node_id))
                self.assertEqual([], gate.pay_document_violations(node, FIELD, node[FIELD], _label))
                self.assertEqual([], gate.holders_violations(node, node[FIELD], FIELD, _label))

    def test_every_record_passes_the_financial_validator_as_a_proxy(self):
        for node_id, record in self.records.items():
            with self.subTest(node=node_id):
                out = fe.validate_record(record, self.node_map[node_id])
                self.assertEqual("partial", fe.classify(out))
                self.assertEqual("proxy", out["scopeMatch"])

    def test_the_published_block_writes_no_source_url(self):
        for node_id in self.records:
            node = self.node_map[node_id]
            for url in node.get("sourceUrls") or []:
                self.assertFalse(gate.is_us_code_document_url(url), (node_id, url))
            self.assertNotEqual(node.get("verificationMethod"), node[FIELD]["method"])

    def test_each_way_a_block_can_be_faked_is_refused(self):
        army = self.node_map[ARMY_CHIEF][FIELD]
        space = self.node_map[SPACE_CHIEF][FIELD]
        cmsaf = self.node_map[AIR_FORCE_CMSAF][FIELD]
        good_arith = army["arithmetic"]
        cases = {
            # The record moved onto the JCS grouping's copy of the same office.
            "a grade block on a JCS copy of a service chief": (
                JCS_COPY_OF_ARMY_CHIEF, army, "deliberately does not price"),
            # The node's own row is what the block is checked against, so the
            # Chief's block on the Vice Chief's node fails the identification,
            # the office, the statute and the quote at once.
            "a grade block on another grade row's node": (
                ARMY_VICE, army, "does not identify itself as the grade row"),
            "pay grade O-9": (
                ARMY_CHIEF, {**army, "payGrade": "O-9", "identification": {**army["identification"], "payGrade": "O-9"}},
                "prices pay grade"),
            "the ceiling's figure published as the row's": (
                ARMY_CHIEF, {**army, "monthly": {**army["monthly"], "amountRaw": "18,899.90"}}, "states a monthly figure of"),
            "a dropped document": (
                ARMY_CHIEF, {**army, "documents": army["documents"][:2]}, "documents, not 3"),
            "a document claiming to state the figure": (
                ARMY_CHIEF, {**army, "documents": [{**army["documents"][0], "statesTheFigure": True}] + army["documents"][1:]},
                "states the annual figure"),
            "a factor of thirteen": (
                ARMY_CHIEF, {**army, "arithmetic": {**good_arith, "factor": 13}}, "not twelve"),
            "the monthly figure published as the annual rate": (
                ARMY_CHIEF, {**army, "amount": army["monthly"]["amount"]}, "publishes the monthly figure"),
            "a verified grade": (
                ARMY_CHIEF, {**army, "financialEvidenceStatus": "verified"}, "not 'partial'"),
            "an exact scope": (
                ARMY_CHIEF, {**army, "scopeMatch": "exact"}, "never more than a proxy"),
            "the ceiling footnote altered": (
                ARMY_CHIEF, {**army, "capFootnote": {**army["capFootnote"], "text": army["capFootnote"]["text"].replace("$18,899.90", "$18,999.90")}},
                "not the one Schedule 8 prints"),
            "the ceiling footnote dropped": (
                ARMY_CHIEF, {**army, "capFootnote": None}, "ceiling footnote"),
            "an unknown source": (
                ARMY_CHIEF, {**army, "source": "somewhere"}, "prices from source"),
            "an unknown route": (
                ARMY_CHIEF, {**army, "identification": {**army["identification"], "kind": "guessed"}}, "identifies its route as"),
            "a grade block under the footnote method": (
                ARMY_CHIEF, {**army, "method": mp.PAY_METHOD_NAMED}, "under method"),
            "a grade sentence the section does not print": (
                ARMY_CHIEF, {**army, "statuteQuote": "The Chief of Staff has the grade of admiral.",
                             "identification": {**army["identification"], "statuteQuote": "The Chief of Staff has the grade of admiral."}},
                "not the one 10 U.S.C. 7033(b) prints"),
            "the office sentence dropped on a row that has one": (
                ARMY_CHIEF, {**army, "identification": {**army["identification"], "officeQuote": None}}, "does not quote the sentence of"),
            "another office": (
                ARMY_CHIEF, {**army, "office": "Chief of Staff of the Navy", "identification": {**army["identification"], "office": "Chief of Staff of the Navy"}},
                "names office"),
            "another statute": (
                ARMY_CHIEF, {**army, "statute": "10 U.S.C. 7034(b)"}, "this row's statute is"),
            "the 201(a)(1) row misquoted": (
                ARMY_CHIEF, {**army, "identification": {**army["identification"], "mappingQuote": "O-10 General Admiral"}},
                "does not quote 37 U.S.C. 201(a)(1)'s own row"),
            "a Space Force row without the Space Force sentence": (
                SPACE_CHIEF, {**space, "identification": {**space["identification"], "spaceForceMapping": None}},
                "is a Space Force post and does not quote"),
            "the Space Force sentence on an Army row": (
                ARMY_CHIEF, {**army, "identification": {**army["identification"], "spaceForceMapping": mp.SPACE_FORCE_MAPPING_QUOTE}},
                "on a post that is not one"),
            "the rate text misprinted": (
                ARMY_CHIEF, {**army, "rateText": "$227,998.00"}, "prints the rate as"),
            "a result that is not the monthly figure times twelve": (
                ARMY_CHIEF, {**army, "amount": army["amount"] + 1, "arithmetic": {**good_arith, "result": army["amount"] + 1}},
                "times twelve is"),
            "a base that is not the monthly figure": (
                ARMY_CHIEF, {**army, "arithmetic": {**good_arith, "baseAmountRaw": "1.00", "baseAmount": 1.0}},
                "not the monthly figure it states"),
            "the arithmetic dropped": (
                ARMY_CHIEF, {**army, "arithmetic": None}, "without the arithmetic"),
            "another operation": (
                ARMY_CHIEF, {**army, "arithmetic": {**good_arith, "operation": "plus_percent"}}, "not 'monthly times 12'"),
            "a summary claiming a document states the figure": (
                ARMY_CHIEF, {**army, "verification": {**army["verification"], "documentsStatingTheFigure": 1}},
                "claims 1 of its documents state"),
            "an inflated percentage": (
                ARMY_CHIEF, {**army, "verification": {**army["verification"], "percent": 95}}, "publishes 95%"),
            "a statute on a host this pipeline does not read": (
                ARMY_CHIEF, {**army, "url": "https://www.law.cornell.edu/uscode/text/10/7033",
                             "documents": [{**army["documents"][0], "url": "https://www.law.cornell.edu/uscode/text/10/7033"}] + army["documents"][1:]},
                "a host this pipeline does not read the Code from"),
            "a future retrieval": (
                ARMY_CHIEF, {**army, "checkedAt": "2099-01-01T00:00:00Z"}, "without a past retrieval date"),
            "the enlisted footnote on a grade row": (
                ARMY_CHIEF, {**army, "footnote": cmsaf["footnote"]}, "carries the enlisted footnote on a grade row"),
            # The footnote route.
            "a footnote block on a post the footnote does not name": (
                ARMY_CHIEF, cmsaf, "does not list as a title"),
            "a footnote block moved onto another named post": (
                COAST_GUARD_MCPO, cmsaf, "the footnote's title for this post is"),
            "a printed item the footnote does not carry": (
                AIR_FORCE_CMSAF, {**cmsaf, "identification": {**cmsaf["identification"], "printedItem": "Chief Master Sergeant of the Air Force Reserve"}},
                "quotes printed item"),
            "the footnote text altered": (
                AIR_FORCE_CMSAF, {**cmsaf, "footnote": {**cmsaf["footnote"], "text": cmsaf["footnote"]["text"].replace("$11,166.90", "$11,166.00")}},
                "not the one Schedule 8 prints"),
            "the officer row's figure on a footnote post": (
                AIR_FORCE_CMSAF, {**cmsaf, "monthly": {**cmsaf["monthly"], "amountRaw": "18,999.90"}}, "states a monthly figure of"),
            "a footnote block under the grade method": (
                AIR_FORCE_CMSAF, {**cmsaf, "method": mp.PAY_METHOD_GRADE}, "under method"),
            "a footnote block naming three documents": (
                AIR_FORCE_CMSAF, {**cmsaf, "documents": army["documents"]}, "documents, not 1"),
            "an officer row on a footnote post": (
                AIR_FORCE_CMSAF, {**cmsaf, "scheduleRow": army["scheduleRow"]}, "carries an officer row on a footnote post"),
            "the footnote's pay grade misfiled": (
                AIR_FORCE_CMSAF, {**cmsaf, "payGrade": "E-8", "identification": {**cmsaf["identification"], "grade": "E-8"}},
                "files the footnote's rate under pay grade"),
        }
        for name, (node_id, pay, sentence) in cases.items():
            with self.subTest(case=name):
                out = self._check(node_id, pay)
                self.assertNotEqual([], out, name)
                self.assertTrue(any(sentence in line for line in out), (name, sentence, out))

    def test_a_renamed_node_a_leak_a_measured_cost_and_a_second_figure_are_refused(self):
        # A parenthetical is dropped by canonical_key, so "(General)" for
        # "(4-star General)" is not a rename; a changed title is.
        node = copy.deepcopy(self.node_map[ARMY_CHIEF])
        node["name"] = "Chief of Staff of the Army (General)"
        self.assertEqual([], self._check(ARMY_CHIEF, node=node))
        node["name"] = "Chief of Staff, Army"
        out = self._check(ARMY_CHIEF, node=node)
        self.assertTrue(any("is now called" in line for line in out), out)
        node = copy.deepcopy(self.node_map[ARMY_CHIEF])
        node["sourceUrls"] = [node[FIELD]["url"]]
        out = self._check(ARMY_CHIEF, node=node)
        self.assertTrue(any("counts a pay document among the sources" in line for line in out), out)
        node = copy.deepcopy(self.node_map[ARMY_CHIEF])
        node["sourceUrls"] = [node[FIELD]["scheduleUrl"]]
        out = self._check(ARMY_CHIEF, node=node)
        self.assertTrue(any("counts a pay document among the sources" in line for line in out), out)
        node = copy.deepcopy(self.node_map[ARMY_CHIEF])
        node["cost_status"] = "official"
        out = self._check(ARMY_CHIEF, node=node)
        self.assertTrue(any("measured cost status" in line for line in out), out)
        node = copy.deepcopy(self.node_map[ARMY_CHIEF])
        node["positionSchedulePay"] = {"amount": 1.0}
        out = self._check(ARMY_CHIEF, node=node)
        self.assertTrue(any("two figures for one post" in line for line in out), out)
        node = copy.deepcopy(self.node_map[ARMY_CHIEF])
        node["verificationMethod"] = node[FIELD]["method"]
        out = self._check(ARMY_CHIEF, node=node)
        self.assertTrue(any("verifies its own existence" in line for line in out), out)
        # The footnote route's rename: the post is no longer a title the
        # footnote lists.
        node = copy.deepcopy(self.node_map[AIR_FORCE_CMSAF])
        node["name"] = "Chief Master Sergeant of the Air Force Reserve"
        out = self._check(AIR_FORCE_CMSAF, node=node)
        self.assertTrue(any("does not list as a title" in line for line in out), out)

    def test_a_block_on_an_organisation_is_refused(self):
        army = self.node_map[ARMY_CHIEF][FIELD]
        organisation = {"id": "exec-dept-defense-army", "name": "U.S. Army", "type": "Military Department", FIELD: army}
        out = gate.military_pay_violations(organisation, army, TODAY, _label, "Department of Defense (DoD)")
        self.assertTrue(any("not a post" in line for line in out), out)

    def test_a_holders_block_on_a_single_post_is_refused(self):
        army = self.node_map[ARMY_CHIEF][FIELD]
        out = self._check(ARMY_CHIEF, {**army, "holders": {"text": "×2", "kind": "exact", "count": 2}})
        self.assertTrue(any("stands for one post" in line for line in out), out)


class PublishedGraphTests(unittest.TestCase):
    """Whatever the published graph carries under the field must pass; the
    graph may carry nothing yet, and then nothing is asserted about it."""

    def test_every_published_block_passes(self):
        if not GRAPH.exists():
            self.skipTest("no published graph")
        graph = json.loads(GRAPH.read_text(encoding="utf-8"))
        pairs = list(gate.walk(graph))
        name_by_id = {str(n.get("id") or ""): n.get("name") for n, _ in pairs}
        for node, parent in pairs:
            block = node.get(FIELD)
            if block is None:
                continue
            with self.subTest(node=node.get("id")):
                parent_name = name_by_id.get(str((parent or {}).get("id") or ""))
                self.assertEqual([], gate.military_pay_violations(node, block, TODAY, _label, parent_name))
                self.assertEqual([], gate.pay_document_violations(node, FIELD, block, _label))


if __name__ == "__main__":
    unittest.main()
