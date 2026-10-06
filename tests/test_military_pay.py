"""Military basic pay from Schedule 8 of the pay-adjustment order, pinned in
both directions: what the committed note prints, what the grade statutes say
in their operative text, what the module derives, and every way a record is
refused."""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from data_pipeline.exporter.build_graph import (
    DEFAULT_BASE_GRAPH,
    MINIMAL_GRAPH_FIELDS,
    build_graph,
    canonical_name_key,
    index_tree,
    load_base_graph,
)
from data_pipeline.verification import financial_evidence as fe
from data_pipeline.verification.derived_pay import load_section
from data_pipeline.verification.evidence import EVIDENCE_OWNED_FIELDS
from data_pipeline.verification.military_pay import (
    ARITHMETIC_OPERATION,
    FIELD,
    GRADE_PROVISIONS,
    GRADE_WORD_TO_PAY_GRADE,
    MAPPING_FIXTURE,
    MONTHS_IN_A_YEAR,
    NOT_PRICED,
    PAY_GRADE_ROWS,
    PAY_METHOD_GRADE,
    PAY_METHOD_NAMED,
    PAY_SOURCE,
    SPACE_FORCE_MAPPING_QUOTE,
    Unreadable8,
    apply_pay_evidence,
    build_records,
    footnote_titles,
    load_schedule_8,
    parse_schedule_8,
)
from data_pipeline.verification.pay_documents import PAY_DOCUMENT_FIELDS, PAY_FIELDS, annotate_pay_documents
from data_pipeline.verification.pay_tables import OFFICE_RATE_PAY_FIELDS, withdraw_pay_from_multi_post_nodes
from data_pipeline.verification.us_code_pay_schedules import DEFAULT_SCHEDULE_HTML

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "uscode"
GRAPH = PROJECT_ROOT / "output" / "graph.json"
EVIDENCE = PROJECT_ROOT / "data" / "verification" / "military_pay_evidence.json"

JCS_COPIES = (
    "exec-dept-defense-jcs-chief-of-staff-of-the-army",
    "exec-dept-defense-jcs-chief-of-naval-operations",
    "exec-dept-defense-jcs-commandant-of-the-marine-corps",
    "exec-dept-defense-jcs-chief-of-staff-of-the-air-force",
    "exec-dept-defense-jcs-chief-of-space-operations",
    "exec-dept-defense-jcs-commandant-of-the-coast-guard",
)
CJCS = "exec-dept-defense-jcs-chairman-of-the-joint-chiefs-of-staff-cjcs"
SMA = "exec-dept-defense-army-sergeant-major-of-the-army"
MCPOCG = "exec-dept-dhs-uscg-master-chief-petty-officer-of-the-coast-guard"


def _real_records():
    node_map, parent_map = index_tree(load_base_graph(DEFAULT_BASE_GRAPH))
    loaded = load_schedule_8(DEFAULT_SCHEDULE_HTML)
    records, report = build_records(node_map, parent_map, loaded, fiscal_year=2026)
    return node_map, parent_map, loaded, records, report


class ScheduleTests(unittest.TestCase):
    """What the committed note prints, read off the bytes rather than remembered."""

    @classmethod
    def setUpClass(cls):
        cls.loaded = load_schedule_8(DEFAULT_SCHEDULE_HTML)
        cls.schedule = cls.loaded["schedule"]

    def test_the_o_10_row_is_flat_and_blank_in_the_first_block(self):
        row = self.schedule["officerRows"]["O-10"]
        self.assertTrue(row["flat"])
        self.assertEqual("18,999.90", row["flatAmountRaw"])
        self.assertEqual(11, row["populatedColumns"])
        self.assertEqual(0, row["firstBlockPopulatedColumns"])
        self.assertTrue(all(f["marked"] for f in row["figures"]), "the O-10 row is the marked head of the second block")
        self.assertIn("O–⁠10", row["rowText"])

    def test_most_grades_are_not_flat_and_so_cannot_be_priced_by_one_figure(self):
        rows = self.schedule["officerRows"]
        self.assertFalse(rows["O-8"]["flat"])
        self.assertFalse(rows["O-7"]["flat"])
        # O-1 to O-4 are flat ACROSS the second block but print figures in
        # the first, so they vary with years of service and are refused.
        self.assertFalse(rows["O-3"]["flat"])
        self.assertIsNone(rows["O-3"]["flatAmount"])
        # The E-9 row varies too, which is why the senior enlisted advisers
        # are priced from the footnote that names them and never from it.
        self.assertFalse(self.schedule["enlistedRows"]["E-9"]["flat"])

    def test_the_cap_footnote_disagrees_with_the_row_by_one_hundred_dollars(self):
        cap = self.schedule["capFootnote"]
        self.assertEqual("$18,899.90", cap["monthlyAsPrinted"])
        self.assertAlmostEqual(100.0, self.schedule["officerRows"]["O-10"]["flatAmount"] - cap["monthlyAmount"], places=2)
        self.assertIn("Chief of the National Guard Bureau", cap["text"])
        self.assertIn("commander of a unified or specified combatant command", cap["text"])

    def test_the_enlisted_footnote_names_seven_items_and_eight_offices(self):
        footnote = self.schedule["seniorEnlistedFootnote"]
        self.assertEqual("$11,166.90", footnote["monthlyAsPrinted"])
        self.assertEqual(7, len(footnote["items"]))
        titles = [t["title"] for t in footnote["titles"]]
        self.assertEqual(8, len(titles))
        self.assertIn("Master Chief Petty Officer of the Navy", titles)
        self.assertIn("Master Chief Petty Officer of the Coast Guard", titles)
        self.assertIn("Chief Master Sergeant of the Space Force", titles)
        self.assertIn("Senior Enlisted Advisor to the Chairman of the Joint Chiefs of Staff", titles)
        both = [t for t in footnote["titles"] if t["printedItem"] == "Master Chief Petty Officer of the Navy or Coast Guard"]
        self.assertEqual(2, len(both))

    def test_the_navy_or_coast_guard_rule_expands_only_that_shape(self):
        self.assertEqual(
            [{"title": "Sergeant Major of the Army", "printedItem": "Sergeant Major of the Army"}],
            footnote_titles(["Sergeant Major of the Army"]),
        )
        self.assertEqual(2, len(footnote_titles(["X of the Navy or Coast Guard"])))
        self.assertEqual(1, len(footnote_titles(["X of the Navy"])))

    def test_the_enlisted_table_prints_e_1_twice_and_the_reader_keeps_both(self):
        rows = self.schedule["enlistedRows"]
        self.assertIn("E-1", rows)
        self.assertTrue(any(key.startswith("E-1/") for key in rows), sorted(rows))

    def test_a_reshaped_note_is_refused_rather_than_guessed(self):
        raw = DEFAULT_SCHEDULE_HTML.read_text(encoding="utf-8")
        for bad in (
            raw.replace("Pay of the Uniformed Services", "Pay of the Uniformed Services and Others"),
            raw.replace("part i-monthly basic pay", "part i-annual basic pay"),
            raw.replace("For noncommissioned officers serving as", "For officers serving as"),
        ):
            with self.assertRaises(Unreadable8):
                parse_schedule_8(bad)

    def test_a_tampered_fixture_is_refused_by_its_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / DEFAULT_SCHEDULE_HTML.name
            shutil.copy(DEFAULT_SCHEDULE_HTML, target)
            shutil.copy(DEFAULT_SCHEDULE_HTML.with_name(DEFAULT_SCHEDULE_HTML.name + ".meta.json"),
                        target.with_name(target.name + ".meta.json"))
            target.write_text(target.read_text(encoding="utf-8").replace("$18,999.90", "$19,999.90", 1), encoding="utf-8")
            with self.assertRaises(Unreadable8):
                load_schedule_8(target)


class ProvisionTests(unittest.TestCase):
    """Every quote the rows carry is in its section's OPERATIVE text now."""

    def test_every_grade_sentence_is_in_the_operative_text(self):
        for node_id, row in GRADE_PROVISIONS.items():
            with self.subTest(node_id):
                sec = load_section(row["fixture"])
                self.assertIn(row["quote"], sec["operative"])
                if row.get("officeQuote"):
                    self.assertIn(row["officeQuote"], sec["operative"])
                self.assertIn(row["grade"], GRADE_WORD_TO_PAY_GRADE)
                self.assertIn("grade of", row["quote"])

    def test_the_mapping_row_and_the_space_force_sentence_are_in_37_usc_201(self):
        sec = load_section(MAPPING_FIXTURE)
        self.assertIn(PAY_GRADE_ROWS["O-10"], sec["operative"])
        self.assertIn(SPACE_FORCE_MAPPING_QUOTE, sec["operative"])
        # O-9 is printed too and deliberately priced for nobody.
        self.assertIn("O–9 Lieutenant general Vice admiral", sec["operative"])

    def test_the_rows_name_seventeen_posts_and_no_combatant_commander_without_a_grade_statute(self):
        self.assertEqual(17, len(GRADE_PROVISIONS))
        for node_id in GRADE_PROVISIONS:
            self.assertNotIn(node_id, JCS_COPIES)
            self.assertFalse(re.search(r"cocom-(usafricom|uscentcom|useucom|usindopacom|usnorthcom|ussouthcom|usspacecom|usstratcom|ustranscom)", node_id), node_id)


class RecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node_map, cls.parent_map, cls.loaded, cls.records, cls.report = _real_records()

    def test_twenty_two_posts_are_priced_seventeen_by_grade_and_five_by_the_footnote(self):
        self.assertEqual(22, len(self.records))
        self.assertEqual(17, self.report["pricedByGrade"])
        self.assertEqual(5, self.report["pricedByFootnote"])
        self.assertEqual({}, self.report["refused"])

    def test_the_space_force_adviser_and_the_jcs_copies_are_not_priced(self):
        for node_id in JCS_COPIES + ("exec-dept-defense-sf-senior-enlisted-advisor",
                                     "exec-dept-defense-agency-nga-director-national-geospatial-intelligence-agency-nga"):
            self.assertNotIn(node_id, self.records)
        self.assertIn("Chief Master Sergeant of the Space Force", self.report["footnoteTitlesUnmatched"])
        self.assertIn("exec-dept-defense-sf-senior-enlisted-advisor", NOT_PRICED)

    def test_every_annual_figure_is_twelve_months_of_a_printed_one_and_no_document_states_it(self):
        for node_id, record in self.records.items():
            with self.subTest(node_id):
                monthly = record["monthly"]["amount"]
                self.assertAlmostEqual(round(monthly * MONTHS_IN_A_YEAR, 2), record["amount"], places=2)
                self.assertEqual(ARITHMETIC_OPERATION, record["arithmetic"]["operation"])
                self.assertEqual(12, record["arithmetic"]["factor"])
                self.assertEqual("proxy", record["scopeMatch"])
                self.assertEqual("partial", record["financialEvidenceStatus"])
                self.assertFalse(any(d["statesTheFigure"] for d in record["documents"]))
                self.assertIn("$", record["unitsEvidence"])
                self.assertNotIn(record["amountRaw"], record["unitsEvidence"])

    def test_a_grade_record_rests_on_three_documents_and_a_footnote_record_on_one(self):
        cjcs = self.records[CJCS]
        self.assertEqual(3, len({d["url"] for d in cjcs["documents"]}))
        self.assertEqual("O-10", cjcs["payGrade"])
        self.assertEqual("18,999.90", cjcs["monthly"]["amountRaw"])
        self.assertAlmostEqual(227998.80, cjcs["amount"], places=2)
        self.assertEqual(PAY_METHOD_GRADE, cjcs["method"])
        self.assertIn("2024 edition", cjcs["documents"][0]["edition"])
        sma = self.records[SMA]
        self.assertEqual(1, len(sma["documents"]))
        self.assertEqual("11,166.90", sma["monthly"]["amountRaw"])
        self.assertAlmostEqual(134002.80, sma["amount"], places=2)
        self.assertEqual(PAY_METHOD_NAMED, sma["method"])
        self.assertFalse(sma["identification"]["readsTwoOffices"])
        self.assertTrue(self.records[MCPOCG]["identification"]["readsTwoOffices"])
        self.assertEqual("Master Chief Petty Officer of the Navy or Coast Guard", self.records[MCPOCG]["footnote"]["printedItem"])

    def test_the_cap_discrepancy_rides_on_every_record_unreconciled(self):
        for record in self.records.values():
            self.assertEqual("$18,899.90", record["capFootnote"]["monthlyAsPrinted"])
            self.assertIn("$100.00", record["capFootnote"]["note"])
            self.assertIn("rather than reconciling", record["capFootnote"]["note"])

    def test_every_record_passes_the_financial_evidence_validator_as_a_proxy(self):
        for node_id, record in self.records.items():
            with self.subTest(node_id):
                out = fe.validate_record(record, self.node_map[node_id])
                self.assertEqual("partial", fe.classify(out))
                self.assertEqual("currency_mark_on_the_figure_the_record_is_computed_from", out["unitsEvidenceKind"])

    def test_the_validator_refuses_arithmetic_that_is_not_twelve_months(self):
        record = copy.deepcopy(self.records[CJCS])
        record["arithmetic"]["factor"] = 13
        with self.assertRaises(fe.Rejected):
            fe.validate_record(record, self.node_map[CJCS])
        record = copy.deepcopy(self.records[CJCS])
        record["amount"] = 227998.80 + 1
        record["amountRaw"] = "227,999.80"
        with self.assertRaises(fe.Rejected):
            fe.validate_record(record, self.node_map[CJCS])
        record = copy.deepcopy(self.records[CJCS])
        record["amount"] = record["monthly"]["amount"]
        record["amountRaw"] = record["monthly"]["amountRaw"]
        with self.assertRaises(fe.Rejected):
            fe.validate_record(record, self.node_map[CJCS])

    def test_a_quote_moved_beneath_the_notes_cut_refuses_the_row(self):
        row = GRADE_PROVISIONS[CJCS]
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for fixture in sorted({r["fixture"] for r in GRADE_PROVISIONS.values()} | {MAPPING_FIXTURE}):
                shutil.copy(FIXTURE_DIR / fixture, directory / fixture)
                shutil.copy(FIXTURE_DIR / (fixture + ".meta.json"), directory / (fixture + ".meta.json"))
            target = directory / row["fixture"]
            raw = target.read_text(encoding="utf-8")
            doctored = raw.replace(row["quote"], "The Chairman serves at the pleasure of the President.", 1)
            heading = doctored.find("Editorial Notes")
            self.assertGreater(heading, 0)
            # Beneath the heading's closing tag: in the notes, not above the cut.
            cut = doctored.find("</h4>", heading) + len("</h4>")
            doctored = doctored[:cut] + "<p>" + row["quote"] + "</p>" + doctored[cut:]
            target.write_text(doctored, encoding="utf-8")
            meta_path = directory / (row["fixture"] + ".meta.json")
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
            meta_path.write_text(json.dumps(meta), encoding="utf-8")
            records, report = build_records(self.node_map, self.parent_map, self.loaded, fiscal_year=2026, directory=directory)
        self.assertNotIn(CJCS, records)
        self.assertIn("only in the publisher's notes", report["refused"][CJCS])
        self.assertEqual(21, len(records))

    def test_a_renamed_node_refuses_the_row(self):
        node_map = {k: dict(v) for k, v in self.node_map.items()}
        node_map[CJCS]["name"] = "Chairman of the Joint Chiefs"
        records, report = build_records(node_map, self.parent_map, self.loaded, fiscal_year=2026)
        self.assertNotIn(CJCS, records)
        self.assertIn("renamed", report["refused"][CJCS])

    def test_a_row_that_varies_with_years_of_service_is_refused(self):
        raw = DEFAULT_SCHEDULE_HTML.read_text(encoding="utf-8")
        # Change the LAST O-10 cell: the row is no longer flat.
        idx = raw.rfind("$18,999.90")
        doctored = raw[:idx] + "$19,100.00" + raw[idx + len("$18,999.90"):]
        schedule = parse_schedule_8(doctored)
        # The O-9 row (bare figures) follows; make sure it was O-10's cell.
        if schedule["officerRows"]["O-10"]["flat"]:
            self.skipTest("the doctored cell was not in the O-10 row")
        loaded = dict(self.loaded, schedule=schedule)
        records, report = build_records(self.node_map, self.parent_map, loaded, fiscal_year=2026)
        self.assertEqual(5, len(records), "only the footnote route survives a non-flat O-10 row")
        self.assertIn("varies with years of service", report["refused"][CJCS])

    def test_a_footnote_title_reaching_two_nodes_prices_neither(self):
        node_map = {k: dict(v) for k, v in self.node_map.items()}
        node_map["twin"] = {"id": "twin", "name": "Sergeant Major of the Army", "type": "Position"}
        records, report = build_records(node_map, self.parent_map, self.loaded, fiscal_year=2026)
        self.assertNotIn(SMA, records)
        self.assertNotIn("twin", records)
        self.assertIn("footnote:Sergeant Major of the Army", report["refused"])


class ApplyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node_map, cls.parent_map, cls.loaded, cls.records, cls.report = _real_records()

    def _tree(self):
        return copy.deepcopy(load_base_graph(DEFAULT_BASE_GRAPH))

    def test_the_blocks_land_on_the_twenty_two_nodes_and_nowhere_else(self):
        tree = self._tree()
        stats = apply_pay_evidence(tree, self.records, index_tree=index_tree)
        self.assertEqual(22, stats["priced"])
        self.assertEqual(17, stats["priced_by_grade"])
        self.assertEqual(5, stats["priced_by_footnote"])
        node_map, _ = index_tree(tree)
        carrying = {node_id for node_id, node in node_map.items() if isinstance(node.get(FIELD), dict)}
        self.assertEqual(set(self.records), carrying)
        block = node_map[CJCS][FIELD]
        self.assertEqual(PAY_SOURCE, block["source"])
        self.assertAlmostEqual(227998.80, block["amount"], places=2)
        self.assertEqual("$227,998.80", block["rateText"])
        self.assertEqual("$18,999.90 per month", block["monthly"]["text"])
        self.assertEqual("grade_fixed_by_statute", block["identification"]["kind"])
        for key in ("arithmetic", "documents", "capFootnote", "scheduleRow", "schedule", "url", "scheduleUrl"):
            self.assertIn(key, block)
        for field in ("sourceUrls", "sourceTypes", "lastVerified", "verificationMethod", "resolved_total_amount", "cost_status"):
            self.assertIsNone(node_map[CJCS].get(field))

    def test_a_node_another_source_priced_is_left_alone(self):
        tree = self._tree()
        node_map, _ = index_tree(tree)
        node_map[CJCS]["positionStatutoryPay"] = {"amount": 1.0}
        stats = apply_pay_evidence(tree, self.records, index_tree=index_tree)
        self.assertEqual(21, stats["priced"])
        self.assertEqual(1, stats["already_priced_by_another_source"])
        self.assertNotIn(FIELD, node_map[CJCS])

    def test_a_renamed_node_is_skipped_at_apply_time(self):
        tree = self._tree()
        node_map, _ = index_tree(tree)
        node_map[SMA]["name"] = "Sergeant Major"
        stats = apply_pay_evidence(tree, self.records, index_tree=index_tree)
        self.assertEqual(1, stats["renamed_since_the_match"])
        self.assertNotIn(FIELD, node_map[SMA])

    def test_the_field_is_office_rate_class_and_keeps_holders_on_a_bench(self):
        self.assertIn(FIELD, OFFICE_RATE_PAY_FIELDS)
        tree = self._tree()
        node_map, _ = index_tree(tree)
        apply_pay_evidence(tree, self.records, index_tree=index_tree)
        node = node_map[SMA]
        node["representsPosts"] = {"kind": "exact", "count": 2, "text": "×2"}
        withdraw_pay_from_multi_post_nodes(tree)
        self.assertIn(FIELD, node)
        self.assertEqual(2, node[FIELD]["holders"]["count"])
        self.assertTrue(node[FIELD]["holders"]["appliesToEachHolder"])

    def test_the_document_count_is_read_off_the_block(self):
        tree = self._tree()
        node_map, _ = index_tree(tree)
        apply_pay_evidence(tree, self.records, index_tree=index_tree)
        annotate_pay_documents(tree)
        cjcs = node_map[CJCS][FIELD]["verification"]
        self.assertEqual(3, cjcs["documents"])
        self.assertEqual(90, cjcs["percent"])
        self.assertEqual(0, cjcs["documentsStatingTheFigure"])
        self.assertIn("BY THE MONTH", cjcs["caution"])
        sma = node_map[SMA][FIELD]["verification"]
        self.assertEqual(1, sma["documents"])
        self.assertEqual(70, sma["percent"])
        self.assertIn("names this post in its own footnote", sma["caution"])


class WiringTests(unittest.TestCase):
    def test_the_field_is_declared_everywhere_a_pay_field_must_be(self):
        self.assertIn(FIELD, PAY_FIELDS)
        self.assertIn(FIELD, PAY_DOCUMENT_FIELDS)
        self.assertEqual(0, PAY_DOCUMENT_FIELDS[FIELD]["statesTheFigure"])
        self.assertIn(FIELD, EVIDENCE_OWNED_FIELDS)
        self.assertIn(FIELD, MINIMAL_GRAPH_FIELDS)
        self.assertIn(FIELD, OFFICE_RATE_PAY_FIELDS)
        self.assertIn("military_pay_evidence_path", inspect.signature(build_graph).parameters)

    def test_the_validator_knows_the_source_type_and_the_operation(self):
        self.assertIn(PAY_SOURCE, fe.SOURCE_TYPES)
        self.assertIn(PAY_SOURCE, fe.COMPUTED_FROM_MARKED_FIGURE_SOURCE_TYPES)
        self.assertIn(ARITHMETIC_OPERATION, fe.COMPUTED_OPERATIONS)
        self.assertEqual({"basic_pay"}, fe.SOURCE_BASES[PAY_SOURCE])
        self.assertNotIn(PAY_SOURCE, fe.SCALE_PRINTED_SOURCE_TYPES, "the record's own figure is printed nowhere")

    def test_the_runbook_documents_the_source_type(self):
        text = (PROJECT_ROOT / "docs" / "COST_NOMINATION_RUNBOOK.md").read_text(encoding="utf-8")
        self.assertIn("`military_basic_pay_schedule`", text)


class PublishedGraphTests(unittest.TestCase):
    """What the committed graph carries, so a regeneration that lost the field
    fails here rather than silently."""

    @classmethod
    def setUpClass(cls):
        if not GRAPH.exists():
            raise unittest.SkipTest("no published graph")
        cls.root = json.loads(GRAPH.read_text(encoding="utf-8"))
        cls.nodes = {}
        stack = [cls.root]
        while stack:
            node = stack.pop()
            cls.nodes[node["id"]] = node
            stack.extend(node.get("children") or [])

    def test_twenty_two_posts_carry_the_field_and_the_jcs_copies_do_not(self):
        carrying = {node_id for node_id, node in self.nodes.items() if isinstance(node.get(FIELD), dict)}
        self.assertEqual(22, len(carrying), sorted(carrying))
        for node_id in JCS_COPIES:
            self.assertNotIn(FIELD, self.nodes[node_id])
        self.assertAlmostEqual(227998.80, self.nodes[CJCS][FIELD]["amount"], places=2)
        self.assertAlmostEqual(134002.80, self.nodes[SMA][FIELD]["amount"], places=2)

    def test_no_priced_node_gained_a_statute_or_schedule_url_as_a_source(self):
        for node_id, node in self.nodes.items():
            block = node.get(FIELD)
            if not isinstance(block, dict):
                continue
            with self.subTest(node_id):
                for url in node.get("sourceUrls") or []:
                    self.assertNotIn("uscode.house.gov", url)
                    self.assertNotIn("USCODE-", url)
                self.assertEqual(0, block["verification"]["documentsStatingTheFigure"])
                self.assertNotEqual("verified", block.get("financialEvidenceStatus"))

    def test_the_evidence_file_and_the_graph_agree(self):
        if not EVIDENCE.exists():
            self.skipTest("no evidence file")
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))["nodes"]
        carrying = {node_id for node_id, node in self.nodes.items() if isinstance(node.get(FIELD), dict)}
        self.assertEqual(set(evidence), carrying)


if __name__ == "__main__":
    unittest.main()
