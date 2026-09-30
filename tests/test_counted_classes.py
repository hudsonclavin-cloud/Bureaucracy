"""The fourth Executive Schedule route: one office of a COUNTED class.

5 U.S.C. 5315 places "Assistant Attorneys General (11)" at Level IV and
names none of the eleven. `statutory_schedule.COUNTED_CLASSES` is the
reviewed table of which nodes are members of which class, and this file pins
it in both directions: the gate's mirror equals it, every class title with
its count is what the section prints, every composing sentence is in its
section's operative text, every member's name is the class's singular office
and sits inside the class's organisation on the real base graph, no class
names more members than the Code counts -- and, corrupted one dimension at a
time, the gate refuses the record.
"""

from __future__ import annotations

import copy
import json
import unittest
import unittest.mock
from pathlib import Path

from data_pipeline.exporter.build_graph import DEFAULT_BASE_GRAPH, index_tree, load_base_graph
from data_pipeline.verification import statutory_schedule as ss
from data_pipeline.verification.pay_documents import annotate_pay_documents, count_documents
from data_pipeline.verification.pay_tables import load_executive_schedule
from scripts.validate_published_graph import (
    EXECUTIVE_SCHEDULE_RATES,
    US_CODE_BASIS_FIXTURE_DIR,
    US_CODE_COUNTED_CLASS_SEPARATORS,
    US_CODE_COUNTED_CLASSES,
    US_CODE_COUNTED_METHOD,
    US_CODE_SECTIONS_LEVELS,
    counted_class_member_name_reason as gate_name_reason,
    fixture_digest,
    schedule_pay_violations,
    uscode_operative_text,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GRAPH = PROJECT_ROOT / "output" / "graph.json"
TODAY = "2026-10-01"


def _label(node):
    return "node {!r}".format(node.get("id"))


class MirrorTests(unittest.TestCase):
    def test_the_gate_mirror_equals_the_module_table(self):
        self.assertEqual(set(US_CODE_COUNTED_CLASSES), set(ss.COUNTED_CLASSES))
        for title, spec in ss.COUNTED_CLASSES.items():
            with self.subTest(title):
                mirrored = US_CODE_COUNTED_CLASSES[title]
                self.assertEqual(spec["section"], mirrored["section"])
                self.assertEqual(spec["singular"], mirrored["singular"])
                self.assertEqual(spec["scopeId"], mirrored["scopeId"])
                self.assertEqual(tuple(spec["departmentWords"]), tuple(mirrored["departmentWords"]))
                self.assertEqual(spec["basis"], mirrored["basis"])
                self.assertEqual(dict(spec["members"]), dict(mirrored["members"]))
                if spec["composition"] is None:
                    self.assertIsNone(mirrored["composition"])
                else:
                    self.assertEqual((spec["composition"]["citation"], spec["composition"]["fixture"],
                                      spec["composition"]["quote"]), tuple(mirrored["composition"]))
        self.assertEqual(US_CODE_COUNTED_METHOD, ss.METHOD_COUNTED)
        self.assertEqual(tuple(US_CODE_COUNTED_CLASS_SEPARATORS), tuple(ss.COUNTED_CLASS_SEPARATORS))
        self.assertEqual(dict(US_CODE_SECTIONS_LEVELS), dict(ss.SECTION_LEVELS))

    def test_every_class_title_is_printed_by_its_section_with_its_count(self):
        for title, spec in ss.COUNTED_CLASSES.items():
            with self.subTest(title):
                operative = ss.load_basis_section("exec_schedule_{}.html".format(spec["section"]))["operative"]
                self.assertIn(title, operative)
                self.assertIsNotNone(ss.counted_class_count(title))
                self.assertGreaterEqual(ss.counted_class_count(title), len(spec["members"]))

    def test_every_composing_and_naming_sentence_is_in_the_operative_text(self):
        for title, spec in ss.COUNTED_CLASSES.items():
            composition = spec["composition"]
            if composition is None:
                self.assertTrue(all(named is None for named in spec["members"].values()), title)
                continue
            with self.subTest(title):
                loaded = ss.load_basis_section(composition["fixture"])
                self.assertIn(composition["quote"], loaded["operative"])
                # And the gate's own reader agrees, so the two cannot drift.
                gate_text = uscode_operative_text(US_CODE_BASIS_FIXTURE_DIR / composition["fixture"])
                self.assertIn(composition["quote"], gate_text)
                for node_id, named in spec["members"].items():
                    if named:
                        self.assertIn(named, loaded["operative"], node_id)
                        self.assertIn(named, gate_text, node_id)

    def test_every_member_is_a_post_named_as_the_singular_inside_the_organisation(self):
        node_map, parent_map = index_tree(load_base_graph(DEFAULT_BASE_GRAPH))
        seen = set()
        for title, spec in ss.COUNTED_CLASSES.items():
            for node_id in spec["members"]:
                with self.subTest(node_id):
                    self.assertNotIn(node_id, seen, "a node in two classes")
                    seen.add(node_id)
                    node = node_map[node_id]
                    self.assertTrue(ss.is_post_node(node))
                    self.assertIsNone(ss.counted_class_member_name_reason(
                        node["name"], spec["singular"], tuple(spec["departmentWords"])))
                    self.assertIsNone(gate_name_reason(node["name"], spec["singular"], tuple(spec["departmentWords"])))
                    self.assertIn(spec["scopeId"], ss._ancestor_ids(node_id, parent_map))

    def test_the_name_rule_in_both_directions(self):
        for reason_fn in (ss.counted_class_member_name_reason, gate_name_reason):
            self.assertIsNone(reason_fn("Assistant Attorney General, Tax Division", "Assistant Attorney General", ()))
            self.assertIsNone(reason_fn("Assistant Secretary of Labor for EBSA", "Assistant Secretary", ("Labor",)))
            self.assertIsNone(reason_fn("Assistant Secretary — Global Markets", "Assistant Secretary", ("Commerce",)))
            self.assertIsNone(reason_fn("Assistant Secretary for Housing / FHA Commissioner", "Assistant Secretary", ("HUD",)))
            self.assertIsNone(reason_fn("Assistant Secretary", "Assistant Secretary", ("Labor",)))
            # Another department's office, a deputy, a bench, a parenthetical, a run-on.
            self.assertEqual("names a department that is not the class's own",
                             reason_fn("Assistant Secretary of Defense for Policy", "Assistant Secretary", ("Labor",)))
            self.assertEqual("does not begin with the class's singular office",
                             reason_fn("Deputy Assistant Secretary for EBSA", "Assistant Secretary", ("Labor",)))
            self.assertEqual("names a bench, not one post",
                             reason_fn("Assistant Secretary (×3)", "Assistant Secretary", ("Labor",)))
            self.assertEqual("carries a parenthetical qualifier",
                             reason_fn("Assistant Secretary for Mental Health & Substance Use (dual-hat)", "Assistant Secretary", ()))
            self.assertEqual("does not separate the office from its qualifier",
                             reason_fn("Assistant Secretaryship", "Assistant Secretary", ()))


def _fixture_tree():
    """A department with three members of a counted class, a deputy, a member
    with a parenthetical, a bench, and a like-named post outside the
    department."""
    return {
        "id": "the-constitution-of-the-united-states", "name": "The Constitution", "type": "Foundation",
        "children": [
            {"id": "executive-branch", "name": "Executive Branch", "type": "Branch", "children": [
                {"id": "exec-cabinet", "name": "The Cabinet", "type": "Grouping", "children": [
                    {"id": "exec-dept-doj", "name": "Department of Justice (DOJ)", "type": "Cabinet Department", "children": [
                        {"id": "exec-dept-doj-div-tax", "name": "Tax Division", "type": "Division", "children": [
                            {"id": "exec-dept-doj-div-tax-assistant-attorney-general-tax-division",
                             "name": "Assistant Attorney General, Tax Division", "type": "Position"},
                            {"id": "exec-dept-doj-div-tax-deputy-assistant-attorney-general-3-5",
                             "name": "Deputy Assistant Attorney General (×3-5)", "type": "Position"},
                        ]},
                        {"id": "exec-dept-doj-div-civil", "name": "Civil Division", "type": "Division", "children": [
                            {"id": "exec-dept-doj-div-civil-assistant-attorney-general-civil-division",
                             "name": "Assistant Attorney General, Civil Division", "type": "Position"},
                        ]},
                        {"id": "exec-dept-doj-div-criminal", "name": "Criminal Division", "type": "Division", "children": [
                            {"id": "exec-dept-doj-div-criminal-assistant-attorney-general-criminal-division",
                             "name": "Assistant Attorney General, Criminal Division", "type": "Position"},
                        ]},
                    ]},
                    {"id": "exec-dept-state", "name": "Department of State", "type": "Cabinet Department", "children": [
                        {"id": "exec-dept-state-bureau-of-african-affairs", "name": "Bureau of African Affairs", "type": "Bureau", "children": [
                            {"id": "exec-dept-state-bureau-of-african-affairs-assistant-secretary-bureau-of-african-affairs",
                             "name": "Assistant Secretary, Bureau of African Affairs", "type": "Position"},
                        ]},
                        {"id": "stray-aag", "name": "Stray Office", "type": "Office", "children": [
                            {"id": "exec-dept-doj-div-antitrust-assistant-attorney-general-antitrust-division",
                             "name": "Assistant Attorney General, Antitrust Division", "type": "Position"},
                        ]},
                    ]},
                ]},
            ]},
        ],
    }


def _matched(tree=None):
    node_map, parent_map = index_tree(tree or _fixture_tree())
    return ss.match_counted_classes(node_map, parent_map, ss.load_schedule()), node_map, parent_map


def _records(tree=None):
    found, node_map, parent_map = _matched(tree)
    loaded = load_executive_schedule()
    records, report = ss.build_records(
        found["matched"], loaded["table"], table_url=loaded["url"], table_sha256=loaded["sha256"],
        retrieved_at=loaded["fetched_at"], fiscal_year=2026)
    return records, found, node_map


class MatchingTests(unittest.TestCase):
    def test_members_are_matched_and_the_rest_refused_with_a_reason(self):
        found, _, _ = _matched()
        matched = found["matched"]
        self.assertEqual({
            "exec-dept-doj-div-tax-assistant-attorney-general-tax-division",
            "exec-dept-doj-div-civil-assistant-attorney-general-civil-division",
            "exec-dept-doj-div-criminal-assistant-attorney-general-criminal-division",
            "exec-dept-state-bureau-of-african-affairs-assistant-secretary-bureau-of-african-affairs",
        }, set(matched))
        entry = matched["exec-dept-doj-div-tax-assistant-attorney-general-tax-division"]
        self.assertEqual(ss.METHOD_COUNTED, entry["method"])
        self.assertEqual("IV", entry["level"])
        self.assertEqual(11, entry["countedClass"]["statedPosts"])
        self.assertEqual(3, entry["countedClass"]["membersInGraph"])
        self.assertEqual("28 U.S.C. 506", entry["identification"]["basisCitation"])
        self.assertIsNone(entry["countedClass"]["namedAs"])
        state = matched["exec-dept-state-bureau-of-african-affairs-assistant-secretary-bureau-of-african-affairs"]
        self.assertEqual("22 U.S.C. 2651a", state["identification"]["basisCitation"])
        self.assertIn("head of the Bureau of African Affairs", state["countedClass"]["namedAs"])
        # The member listed for the Antitrust Division sits under State here.
        self.assertIn("exec-dept-doj-div-antitrust-assistant-attorney-general-antitrust-division",
                      found["refusals"]["counted_class_member_outside_the_class_organisation"])
        # Members the fixture does not carry are reported, not invented.
        self.assertIn("exec-dept-doj-div-enrd-assistant-attorney-general-environment-natural-resources-division",
                      found["refusals"]["counted_class_member_names_no_node"])
        self.assertEqual({"count": 11, "members": 3}, found["classes"]["Assistant Attorneys General (11)"])

    def test_a_listing_on_the_node_that_says_another_plan_or_level_wins(self):
        tree = _fixture_tree()
        node_map, _ = index_tree(tree)
        node_map["exec-dept-doj-div-tax-assistant-attorney-general-tax-division"]["positionCurrentListing"] = {"payPlan": "ES", "level": ""}
        node_map["exec-dept-doj-div-civil-assistant-attorney-general-civil-division"]["positionListing"] = {"payPlan": "EX", "payLevel": "III"}
        found, _, _ = _matched(tree)
        self.assertNotIn("exec-dept-doj-div-tax-assistant-attorney-general-tax-division", found["matched"])
        self.assertNotIn("exec-dept-doj-div-civil-assistant-attorney-general-civil-division", found["matched"])
        self.assertEqual(2, len(found["refusals"]["counted_class_member_listing_contradicts_the_class"]))
        # An EX listing at the class's own level corroborates and is kept.
        node_map["exec-dept-doj-div-criminal-assistant-attorney-general-criminal-division"]["positionListing"] = {"payPlan": "EX", "payLevel": "IV"}
        found, _, _ = _matched(tree)
        self.assertIn("exec-dept-doj-div-criminal-assistant-attorney-general-criminal-division", found["matched"])

    def test_a_class_the_graph_over_counts_prices_nobody(self):
        tree = _fixture_tree()
        doj = tree["children"][0]["children"][0]["children"][0]
        extra = {}
        for i in range(12):
            doj["children"].append({"id": "div-{}".format(i), "name": "Division {}".format(i), "type": "Division",
                                    "children": [{"id": "aag-{}".format(i), "name": "Assistant Attorney General, Division {}".format(i), "type": "Position"}]})
            extra["aag-{}".format(i)] = None
        table = copy.deepcopy(ss.COUNTED_CLASSES)
        table["Assistant Attorneys General (11)"]["members"].update(extra)
        with unittest.mock.patch.object(ss, "COUNTED_CLASSES", table):
            found, _, _ = _matched(tree)
        self.assertFalse([i for i in found["matched"] if i.startswith("aag-") or "doj" in i])
        self.assertEqual(15, len(found["refusals"]["counted_class_graph_names_more_offices_than_the_code_counts"]))

    def test_a_node_another_route_priced_is_left_to_it(self):
        node_map, parent_map = index_tree(_fixture_tree())
        found = ss.match_counted_classes(node_map, parent_map, ss.load_schedule(),
                                         already_matched={"exec-dept-doj-div-tax-assistant-attorney-general-tax-division": {}})
        self.assertNotIn("exec-dept-doj-div-tax-assistant-attorney-general-tax-division", found["matched"])
        self.assertIn("exec-dept-doj-div-tax-assistant-attorney-general-tax-division",
                      found["refusals"]["counted_class_member_already_matched"])

    def test_the_records_carry_the_class_and_the_composing_statute(self):
        records, _, node_map = _records()
        record = records["exec-dept-doj-div-tax-assistant-attorney-general-tax-division"]
        self.assertEqual(EXECUTIVE_SCHEDULE_RATES["IV"], record["amount"])
        claim = record["levelClaim"]
        self.assertEqual(ss.METHOD_COUNTED, claim["method"])
        self.assertEqual("Assistant Attorneys General (11)", claim["statutoryTitle"])
        self.assertEqual(11, claim["countedClass"]["statedPosts"])
        self.assertNotIn("classTitle", claim)


class ApplyTests(unittest.TestCase):
    def _applied(self, tree=None):
        tree = tree or _fixture_tree()
        records, _, _ = _records(tree)
        stats = ss.apply_schedule_pay(tree, records, index_tree=index_tree)
        annotate_pay_documents(tree)
        node_map, parent_map = index_tree(tree)
        return stats, node_map, parent_map

    def test_the_block_is_stamped_with_the_class_and_counted_on_two_or_three_documents(self):
        stats, node_map, _ = self._applied()
        self.assertEqual(4, stats["priced"])
        pay = node_map["exec-dept-doj-div-tax-assistant-attorney-general-tax-division"]["positionSchedulePay"]
        self.assertEqual(ss.METHOD_COUNTED, pay["method"])
        self.assertEqual("Assistant Attorneys General (11)", pay["countedClass"]["codeTitle"])
        self.assertEqual(3, pay["verification"]["documents"])
        self.assertEqual(90, pay["verification"]["percent"])
        self.assertEqual(1, pay["verification"]["documentsStatingTheFigure"])
        self.assertIn("composes the class", pay["verification"]["caution"])
        roles = {r["url"]: r.get("role") for r in pay["verification"]["documentRoles"]}
        self.assertIn("composes the class of offices this post is one of", roles.values())
        self.assertNotIn("classTitle", pay)

    def test_a_class_with_no_composing_statute_counts_two(self):
        records, _, _ = _records()
        record = copy.deepcopy(records["exec-dept-doj-div-tax-assistant-attorney-general-tax-division"])
        for key in ("basisCitation", "basisQuote", "basisUrl", "basisSha256", "basisCheckedAt"):
            record["levelClaim"]["identification"][key] = None
        tree = _fixture_tree()
        ss.apply_schedule_pay(tree, {record["nodeId"]: record}, index_tree=index_tree)
        node_map, _ = index_tree(tree)
        pay = node_map[record["nodeId"]]["positionSchedulePay"]
        count, _ = count_documents("positionSchedulePay", pay)
        self.assertEqual(2, count)

    def test_a_rename_a_reparenting_and_a_contradicting_listing_each_withdraw_it(self):
        records, _, _ = _records()
        tree = _fixture_tree()
        node_map, _ = index_tree(tree)
        node_map["exec-dept-doj-div-tax-assistant-attorney-general-tax-division"]["name"] = "Deputy Assistant Attorney General, Tax Division"
        node_map["exec-dept-doj-div-civil-assistant-attorney-general-civil-division"]["positionCurrentListing"] = {"payPlan": "ES", "level": ""}
        # Move the Criminal Division under State.
        doj = node_map["exec-dept-doj"]
        criminal = next(c for c in doj["children"] if c["id"] == "exec-dept-doj-div-criminal")
        doj["children"].remove(criminal)
        node_map["exec-dept-state"]["children"].append(criminal)
        stats = ss.apply_schedule_pay(tree, records, index_tree=index_tree)
        self.assertEqual(1, stats["priced"])
        self.assertEqual(1, stats["renamed_since_the_match"])
        self.assertEqual(1, stats["reparented_since_the_match"])
        self.assertEqual(1, stats["listing_contradicts_the_class"])


class GateTests(unittest.TestCase):
    NODE_ID = "exec-dept-doj-div-tax-assistant-attorney-general-tax-division"

    def setUp(self):
        tree = _fixture_tree()
        records, _, _ = _records(tree)
        ss.apply_schedule_pay(tree, records, index_tree=index_tree)
        annotate_pay_documents(tree)
        self.node_map, self.parents = index_tree(tree)
        self.node = self.node_map[self.NODE_ID]
        self.pay = self.node["positionSchedulePay"]

    def _check(self, node=None, pay=None, parents=None):
        node = node or self.node
        return schedule_pay_violations(node, pay if pay is not None else node["positionSchedulePay"], TODAY, _label,
                                       tree_parent=(parents or self.parents).get(node["id"]),
                                       tree_parents=parents or self.parents)

    def test_an_honest_member_passes(self):
        self.assertEqual([], self._check())
        state = self.node_map["exec-dept-state-bureau-of-african-affairs-assistant-secretary-bureau-of-african-affairs"]
        self.assertEqual([], self._check(state))

    def _corrupt(self, mutate, phrase, node=None, parents=None):
        pay = copy.deepcopy(self.pay)
        mutate(pay)
        found = self._check(node, pay, parents)
        self.assertTrue(any(phrase in v for v in found), "expected {!r} in {}".format(phrase, found))

    def test_each_corruption_is_caught(self):
        self._corrupt(lambda p: p.__setitem__("method", ss.METHOD_REVIEWED), "not " + repr(ss.METHOD_COUNTED))
        # A class the table does not carry stops the checker at once: nothing
        # else about the block can be checked against a table row that is not
        # there, and the section-print check needs the row's section.
        self._corrupt(lambda p: p["countedClass"].__setitem__("codeTitle", "Assistant Attorneys General (12)"),
                      "has no table for")
        self._corrupt(lambda p: p["countedClass"].__setitem__("statedPosts", 12), "the title states 11")
        self._corrupt(lambda p: p["countedClass"].__setitem__("membersInGraph", 12), "the Code counts 11")
        self._corrupt(lambda p: p["countedClass"].__setitem__("scopeId", "exec-dept-state"), "as its class's organisation")
        self._corrupt(lambda p: p["countedClass"].__setitem__("singular", "Attorney General"), "singular office")
        self._corrupt(lambda p: p["countedClass"].__setitem__("namedAs", "some sentence"), "sentence naming this office")
        self._corrupt(lambda p: p.__setitem__("classTitle", True), "classTitle mark")
        self._corrupt(lambda p: p.__setitem__("scopedOffice", "Assistant Attorney General"), "claims a scope")
        self._corrupt(lambda p: p["identification"].__setitem__("basisQuote", "eleven Assistant Attorneys General"),
                      "composing sentence that is not the one")
        self._corrupt(lambda p: p["identification"].__setitem__("basisCitation", "28 U.S.C. 507"), "as composing its class")
        self._corrupt(lambda p: p["identification"].__setitem__("basisSha256", "0" * 64), "digest that is not the committed")
        self._corrupt(lambda p: p["identification"].__setitem__("basisUrl", "https://example.gov/x"), "does not link the section")
        self._corrupt(lambda p: p["identification"].__setitem__("basis", "because"), "not the reviewed table's")
        self._corrupt(lambda p: p.__setitem__("identification", None), "no identification block")
        self._corrupt(lambda p: p.__setitem__("payLevel", "III"), "places this post at level")
        self._corrupt(lambda p: p.__setitem__("statutoryTitle", "Assistant Attorney General"), "prints")

    def test_a_record_moved_to_a_node_the_table_does_not_list_is_caught(self):
        stranger = dict(self.node_map["exec-dept-doj-div-tax-deputy-assistant-attorney-general-3-5"],
                        representsPosts={"text": "\u00d73-5", "kind": "range", "min": 3, "max": 5})
        found = self._check(stranger, copy.deepcopy(self.pay))
        self.assertTrue(any("does not list it" in v for v in found))
        self.assertTrue(any("stands for several posts" in v for v in found))

    def test_a_renamed_or_moved_node_is_caught_off_the_tree(self):
        renamed = dict(self.node, name="Deputy Assistant Attorney General, Tax Division")
        self.assertTrue(any("is now called" in v for v in self._check(renamed)))
        parents = dict(self.parents)
        parents["exec-dept-doj-div-tax"] = "exec-dept-state"
        self.assertTrue(any("sits outside" in v for v in self._check(parents=parents)))

    def test_a_listing_that_contradicts_the_class_is_caught(self):
        listed = dict(self.node, positionCurrentListing={"payPlan": "ES", "level": ""})
        self.assertTrue(any("reports pay plan ES" in v for v in self._check(listed)))
        listed = dict(self.node, positionListing={"payPlan": "EX", "payLevel": "III"})
        self.assertTrue(any("reports Level III" in v for v in self._check(listed)))

    def test_a_composing_statute_on_a_class_that_has_none_is_caught(self):
        node = self.node_map["exec-dept-doj-div-civil-assistant-attorney-general-civil-division"]
        pay = copy.deepcopy(node["positionSchedulePay"])
        pay["countedClass"]["codeTitle"] = "Assistant Secretaries of Commerce (11)"
        found = self._check(node, pay)
        self.assertTrue(any("a class the reviewed table does not list it in" in v for v in found))
        self.assertTrue(any("cites a composing statute for a class the table records none for" in v for v in found))


@unittest.skipUnless(GRAPH.exists(), "no published graph")
class PublishedGraphTests(unittest.TestCase):
    def setUp(self):
        self.node_map, self.parents = index_tree(json.loads(GRAPH.read_text(encoding="utf-8")))
        self.counted = {i: n for i, n in self.node_map.items()
                        if isinstance(n.get("positionSchedulePay"), dict)
                        and isinstance(n["positionSchedulePay"].get("countedClass"), dict)}

    def test_every_published_member_passes_the_gate_and_no_class_exceeds_its_count(self):
        from datetime import date

        self.assertTrue(self.counted)
        per_class = {}
        for node_id, node in self.counted.items():
            with self.subTest(node_id):
                self.assertEqual([], schedule_pay_violations(
                    node, node["positionSchedulePay"], date.today().isoformat(), _label,
                    tree_parent=self.parents.get(node_id), tree_parents=self.parents))
            title = node["positionSchedulePay"]["countedClass"]["codeTitle"]
            per_class[title] = per_class.get(title, 0) + 1
        for title, members in per_class.items():
            self.assertLessEqual(members, ss.counted_class_count(title), title)
            self.assertEqual(members, self.counted[next(i for i, n in self.counted.items()
                                                        if n["positionSchedulePay"]["countedClass"]["codeTitle"] == title)]
                             ["positionSchedulePay"]["countedClass"]["membersInGraph"])

    def test_no_member_gained_a_uscode_url_as_a_source(self):
        for node_id, node in self.counted.items():
            self.assertFalse([u for u in (node.get("sourceUrls") or []) if "uscode.house.gov" in str(u)], node_id)
            self.assertNotEqual(node.get("verificationMethod"), ss.METHOD_COUNTED, node_id)


if __name__ == "__main__":
    unittest.main()
