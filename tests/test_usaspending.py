"""USAspending File A, applied beside the cost and never over it.

Pinned in both directions throughout: a key whose API name reduces to the
node's canonical key is applied and the fixture's own figure is what is
published; a key that rests on anything looser is held for review with the
proposer's confidence and nothing is published; a tampered fixture, a post, a
renamed node, a zero and a figure that equals the measured cost are each
refused by the module or the gate, and the block is withdrawn with everything
else the evidence modules own.
"""

from __future__ import annotations

import copy
import json
import shutil
import sys
import unittest
import uuid
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.exporter.build_graph import index_tree, load_base_graph  # noqa: E402
from data_pipeline.verification import usaspending  # noqa: E402
from data_pipeline.verification.evidence import EVIDENCE_OWNED_FIELDS, apply_evidence_to_tree  # noqa: E402
from data_pipeline.verification.financial_evidence import (  # noqa: E402
    DICTIONARY_SCALED_SOURCE_TYPES,
    Rejected,
    validate_record,
)
from scripts.validate_published_graph import usaspending_violations  # noqa: E402

TEST_TMP_ROOT = PROJECT_ROOT / "tests" / ".tmp"
BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"
TODAY = date(2026, 9, 17)


def _label(node):
    return "{} ({})".format(node.get("name"), node.get("id"))


class RealFixturePinTests(unittest.TestCase):
    """What the committed fixtures and crosswalk actually yield, pinned."""

    @classmethod
    def setUpClass(cls):
        root = load_base_graph(BASE_GRAPH)
        cls.node_map, _ = index_tree(root)
        cls.dictionary = usaspending.load_dictionary()
        cls.crosswalk = usaspending.load_crosswalk()
        cls.records, cls.report = usaspending.build_records(cls.node_map, cls.crosswalk, dictionary=cls.dictionary)

    def test_the_dictionary_row_names_both_the_element_and_the_field(self) -> None:
        self.assertIn("GrossOutlayAmountByTAS_CPE", self.dictionary["line"])
        self.assertIn("gross_outlay_amount", self.dictionary["line"])
        self.assertRegex(self.dictionary["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            (self.dictionary["field"], self.dictionary["element"]),
            DICTIONARY_SCALED_SOURCE_TYPES["usaspending_file_ab"]["gross_outlays"],
            "the module and the validator must name the same mapping",
        )

    def test_what_the_first_pass_applied_and_held(self) -> None:
        self.assertEqual(self.report["crosswalk_identifiers"], 47)
        self.assertEqual(self.report["applied"], 43)
        self.assertEqual(self.report["applied_by_level"], {"toptier": 20, "bureau": 23})
        held = self.report["refused"]
        # Nothing is held on spelling any more: the six that were are aliased
        # with a recorded basis, and AmeriCorps fell through to the real
        # blocker underneath its spelling, which is that the row prints 0.0.
        self.assertNotIn("awaiting_review_name_not_equal", held)
        self.assertEqual(held.get("zero_outlay_reported"), 2, "the FTC and CNCS rows print 0.0 and zero is never published")
        # The two that stay held are not spelling at all: the API's entity is a
        # larger thing that contains the node, which no alias can fix.
        self.assertEqual(held.get("awaiting_review_api_entity_is_broader"), 2, held)
        broader = {item["nodeId"] for item in self.report["refused_detail"]["awaiting_review_api_entity_is_broader"]}
        self.assertEqual(broader, {"exec-dept-va-vba", "exec-eop-nsc"})
        for item in self.report["refused_detail"]["awaiting_review_api_entity_is_broader"]:
            self.assertIn(item["confidence"], ("likely", "speculative"))

    def test_every_record_is_the_fixture_s_own_figure_and_graded_by_the_validator(self) -> None:
        for node_id, record in self.records.items():
            # A record whose names agree is graded verified; one resting on a
            # recorded alias is graded down, because an alias is a claim about
            # two names and cannot earn what name equality earns.
            aliased = isinstance(record.get("nameAlias"), dict)
            self.assertEqual(record["financialEvidenceStatus"], "partial" if aliased else "verified", node_id)
            self.assertEqual(record["scopeMatch"], "proxy" if aliased else "exact", node_id)
            self.assertEqual(record["unitsEvidenceKind"], "publishers_data_dictionary", node_id)
            self.assertIn(record["amountRaw"].replace(",", ""), record["quote"].replace(",", ""), node_id)
            self.assertEqual(record["periodCoverage"], "fiscal_year_to_date")
            self.assertTrue(str(record["sourceUrl"]).startswith("https://api.usaspending.gov/"))
            self.assertNotEqual(float(record["amount"]), 0.0)

    def test_a_negative_outlay_is_published_as_the_api_prints_it_when_one_exists(self) -> None:
        negatives = [r for r in self.records.values() if float(r["amount"]) < 0]
        for record in negatives:
            self.assertTrue(str(record["amountRaw"]).startswith("-"), record["nodeId"])


class MatchingTests(unittest.TestCase):
    def setUp(self) -> None:
        root = load_base_graph(BASE_GRAPH)
        self.node_map, _ = index_tree(root)
        self.dictionary = usaspending.load_dictionary()

    def _ident(self, key, confidence="likely", metric="gross_outlays"):
        return {"system": "usaspending_file_ab", "key": key, "basis": "test", "confidence": confidence, "metric": metric}

    def test_a_name_equal_key_is_applied_and_an_unequal_one_is_held_with_its_confidence(self) -> None:
        # The Department of Energy pointed at Agriculture's toptier code: the
        # names do not agree, no alias says they are one unit, so nothing is
        # published and the proposer's confidence rides along for the curator.
        records, report = usaspending.build_records(
            self.node_map,
            {"exec-dept-usda": self._ident("012"), "exec-dept-doe": self._ident("012", "speculative")},
            dictionary=self.dictionary,
        )
        self.assertIn("exec-dept-usda", records)
        self.assertNotIn("exec-dept-doe", records)
        held = report["refused_detail"]["awaiting_review_name_not_equal"]
        self.assertEqual(held[0]["nodeId"], "exec-dept-doe")
        self.assertEqual(held[0]["confidence"], "speculative")

    def test_a_post_an_unknown_node_and_another_metric_are_refused(self) -> None:
        post = next(i for i, n in self.node_map.items() if "position" in str(n.get("type")).lower())
        records, report = usaspending.build_records(
            self.node_map,
            {post: self._ident("012"), "no-such-node": self._ident("012"),
             "exec-dept-usda": self._ident("012", metric="obligations")},
            dictionary=self.dictionary,
        )
        self.assertEqual(records, {})
        self.assertEqual(report["refused"], {"metric_not_gross_outlays": 1, "not_an_organisation": 1, "unknown_node": 1})

    def test_a_tampered_fixture_is_refused_before_a_figure_is_read_out_of_it(self) -> None:
        tmp = TEST_TMP_ROOT / f"usaspending-{uuid.uuid4().hex}"
        tmp.mkdir(parents=True, exist_ok=True)
        try:
            src = usaspending.TOPTIER_FIXTURE
            copy_path = tmp / src.name
            shutil.copy(src, copy_path)
            shutil.copy(src.with_name(src.name + ".meta.json"), tmp / (src.name + ".meta.json"))
            usaspending.load_json_fixture(copy_path)  # the untouched copy reads
            # The API serves compact JSON; one appended byte leaves it valid
            # JSON and changes the digest, which is the only thing that matters.
            copy_path.write_text(copy_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            with self.assertRaises(usaspending.Unreadable) as caught:
                usaspending.load_json_fixture(copy_path)
            self.assertIn("does not match", str(caught.exception))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_the_validator_refuses_the_dictionary_rule_without_the_workbook_s_digest(self) -> None:
        records, _ = usaspending.build_records(self.node_map, {"exec-dept-usda": self._ident("012")}, dictionary=self.dictionary)
        record = dict(records["exec-dept-usda"])
        node = self.node_map["exec-dept-usda"]
        validate_record(record, node)  # as built, it passes
        broken = dict(record)
        broken["unitsEvidenceSource"] = {"file": self.dictionary["file"]}  # no sha256
        with self.assertRaises(Rejected):
            validate_record(broken, node)
        broken = dict(record)
        broken["unitsEvidence"] = "GrossOutlayAmountByTAS_CPE"  # the element without the field it maps to
        with self.assertRaises(Rejected):
            validate_record(broken, node)
        broken = dict(record)
        broken["sourceType"] = "treasury_mts"  # the rule is granted to one source type
        with self.assertRaises(Rejected):
            validate_record(broken, node)


class NameAliasTests(unittest.TestCase):
    """An alias says two names are one unit. It may never say more than that.

    Six of the nine proposals held on the first pass differed from the API by
    an abbreviation, an "Office of" prefix or a rename the graph records both
    sides of; refusing those was a mechanical name test, not a doubt about
    identity. Two others were not spelling at all — USAspending's entity was a
    larger thing containing the node — and no alias can fix that, so they stay
    held under a reason that says which problem it is.
    """

    def setUp(self) -> None:
        root = load_base_graph(BASE_GRAPH)
        self.node_map, _ = index_tree(root)
        self.dictionary = usaspending.load_dictionary()

    def _ident(self, key):
        return {"system": "usaspending_file_ab", "key": key, "basis": "t", "confidence": "likely",
                "metric": "gross_outlays"}

    def test_the_gate_mirror_equals_the_module_s_table(self) -> None:
        from scripts.validate_published_graph import USASPENDING_NAME_ALIASES as mirror

        self.assertEqual(
            {k: (v["graphName"], v["apiName"]) for k, v in usaspending.USASPENDING_NAME_ALIASES.items()},
            dict(mirror),
            "the gate is stdlib-only and mirrors the table; the two must not drift",
        )

    def test_every_alias_names_a_real_node_and_the_name_it_still_carries(self) -> None:
        for node_id, alias in usaspending.USASPENDING_NAME_ALIASES.items():
            node = self.node_map.get(node_id)
            self.assertIsNotNone(node, f"{node_id} is not in the curated file")
            self.assertEqual(node.get("name"), alias["graphName"],
                             f"{node_id} no longer carries the name its alias was written against")
            self.assertTrue(alias["basis"].strip(), f"{node_id}'s alias states no basis")

    def test_an_aliased_key_applies_and_is_graded_down(self) -> None:
        node_id = "exec-dept-dot-phmsa"
        alias = usaspending.USASPENDING_NAME_ALIASES[node_id]
        records, report = usaspending.build_records(
            self.node_map, {node_id: self._ident("069/pipeline-and-hazardous-materials-safety-administration")},
            dictionary=self.dictionary,
        )
        record = records[node_id]
        self.assertEqual(record["financialEvidenceStatus"], "partial")
        self.assertEqual(record["scopeMatch"], "proxy")
        self.assertEqual(record["nameAlias"]["apiName"], alias["apiName"])
        self.assertEqual(report["applied"], 1)

    def test_an_alias_written_against_another_name_does_not_apply(self) -> None:
        node_id = "exec-dept-dot-phmsa"
        self.node_map[node_id]["name"] = "Pipeline Office"
        records, report = usaspending.build_records(
            self.node_map, {node_id: self._ident("069/pipeline-and-hazardous-materials-safety-administration")},
            dictionary=self.dictionary,
        )
        self.assertEqual(records, {})
        self.assertEqual(report["refused"], {"alias_names_a_different_node": 1})

    def test_a_broader_api_entity_is_held_and_never_aliased(self) -> None:
        for node_id, key in (("exec-dept-va-vba", "036/benefits-programs"),
                             ("exec-eop-nsc", "1100/national-security-council-and-homeland-security-council")):
            records, report = usaspending.build_records(
                self.node_map, {node_id: self._ident(key)}, dictionary=self.dictionary)
            self.assertEqual(records, {}, node_id)
            self.assertEqual(report["refused"], {"awaiting_review_api_entity_is_broader": 1}, node_id)
            self.assertNotIn(node_id, usaspending.USASPENDING_NAME_ALIASES,
                             "a bureau broader than the node must never be aliased into it")


class ApplyToTheTreeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = load_base_graph(BASE_GRAPH)
        self.node_map, _ = index_tree(self.root)
        records, _ = usaspending.build_records(
            self.node_map, {"exec-dept-usda": {"system": "usaspending_file_ab", "key": "012", "confidence": "likely", "metric": "gross_outlays"}},
            dictionary=usaspending.load_dictionary(),
        )
        self.records = records
        node = self.node_map["exec-dept-usda"]
        node["cost_status"] = "official"
        node["resolved_total_amount"] = 123456789.0

    def test_the_figure_sits_beside_the_cost_and_the_cost_is_untouched(self) -> None:
        before = copy.deepcopy({k: self.node_map["exec-dept-usda"].get(k) for k in ("cost_status", "resolved_total_amount")})
        stats = usaspending.apply_usaspending_evidence(self.root, self.records, index_tree=index_tree)
        node = index_tree(self.root)[0]["exec-dept-usda"]
        self.assertEqual(stats["applied"], 1)
        block = node["usaspendingOutlays"]
        self.assertEqual(block["level"], "toptier")
        self.assertEqual(block["apiName"], "Department of Agriculture")
        self.assertEqual(block["basis"], "gross_outlays")
        self.assertEqual({k: node.get(k) for k in before}, before, "no cost field is read or written")

    def test_a_renamed_node_keeps_no_figure_earned_by_its_old_name(self) -> None:
        self.node_map["exec-dept-usda"]["name"] = "Department of Farming"
        stats = usaspending.apply_usaspending_evidence(self.root, self.records, index_tree=index_tree)
        self.assertEqual(stats["stale_name"], 1)
        self.assertNotIn("usaspendingOutlays", index_tree(self.root)[0]["exec-dept-usda"])

    def test_a_record_moved_onto_a_post_publishes_nothing(self) -> None:
        post = next(i for i, n in self.node_map.items() if "position" in str(n.get("type")).lower())
        moved = {post: dict(self.records["exec-dept-usda"], nodeId=post)}
        stats = usaspending.apply_usaspending_evidence(self.root, moved, index_tree=index_tree)
        self.assertEqual(stats["not_an_organisation"], 1)
        self.assertNotIn("usaspendingOutlays", index_tree(self.root)[0][post])

    def test_it_is_withdrawn_on_the_next_build_and_with_everything_else_the_modules_own(self) -> None:
        self.assertIn("usaspendingOutlays", EVIDENCE_OWNED_FIELDS)
        usaspending.apply_usaspending_evidence(self.root, self.records, index_tree=index_tree)
        self.assertIn("usaspendingOutlays", index_tree(self.root)[0]["exec-dept-usda"])
        usaspending.apply_usaspending_evidence(self.root, {}, index_tree=index_tree)
        self.assertNotIn("usaspendingOutlays", index_tree(self.root)[0]["exec-dept-usda"], "an empty evidence file withdraws it")
        usaspending.apply_usaspending_evidence(self.root, self.records, index_tree=index_tree)
        apply_evidence_to_tree(self.root, {})
        self.assertNotIn("usaspendingOutlays", index_tree(self.root)[0]["exec-dept-usda"], "the page module's sweep withdraws it too")


class GateTests(unittest.TestCase):
    """The release gate re-reads the fixture by the block's own key and digest."""

    def setUp(self) -> None:
        root = load_base_graph(BASE_GRAPH)
        node_map, _ = index_tree(root)
        records, _ = usaspending.build_records(
            node_map, {"exec-dept-usda": {"system": "usaspending_file_ab", "key": "012", "confidence": "likely", "metric": "gross_outlays"},
                       "exec-dept-doi-blm": {"system": "usaspending_file_ab", "key": "014/bureau-of-land-management",
                                             "confidence": "likely", "metric": "gross_outlays"}},
            dictionary=usaspending.load_dictionary(),
        )
        usaspending.apply_usaspending_evidence(root, records, index_tree=index_tree)
        node_map, _ = index_tree(root)
        self.usda = node_map["exec-dept-usda"]
        self.blm = node_map["exec-dept-doi-blm"]

    def test_a_block_the_module_wrote_passes(self) -> None:
        for node in (self.usda, self.blm):
            self.assertEqual(usaspending_violations(node, node["usaspendingOutlays"], TODAY, _label), [])

    def test_each_corruption_is_caught(self) -> None:
        cases = {
            "amount": lambda n, b: b.__setitem__("amount", float(b["amount"]) + 1000.0),
            "name": lambda n, b: n.__setitem__("name", "Department of Farming"),
            "apiName": lambda n, b: b.__setitem__("apiName", "Something Else"),
            "digest": lambda n, b: b.__setitem__("documentSha256", "0" * 64),
            "dictionary": lambda n, b: b["unitsEvidenceSource"].__setitem__("sha256", "0" * 64),
            "post": lambda n, b: n.__setitem__("type", "Position"),
            "zero": lambda n, b: b.__setitem__("amount", 0.0),
            "future": lambda n, b: b.__setitem__("periodAsOf", "2099-01-01"),
            "host": lambda n, b: b.__setitem__("url", "https://example.com/x"),
            "kind": lambda n, b: b.__setitem__("unitsEvidenceKind", "currency_mark_on_the_printed_figure"),
            "as_the_cost": lambda n, b: (n.__setitem__("cost_status", "official"),
                                         n.__setitem__("resolved_total_amount", float(b["amount"]))),
        }
        for name, corrupt in cases.items():
            node = copy.deepcopy(self.blm)
            block = node["usaspendingOutlays"]
            corrupt(node, block)
            problems = usaspending_violations(node, block, TODAY, _label)
            self.assertTrue(problems, "corruption {!r} passed the gate".format(name))


if __name__ == "__main__":
    unittest.main()
