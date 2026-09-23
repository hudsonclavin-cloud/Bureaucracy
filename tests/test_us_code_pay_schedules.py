"""Schedule 6 of the annual pay-adjustment order, as 5 U.S.C. 5332's note
prints it: the parser, exactly which four offices it prices and why nothing
else, and every way a forged rate could reach the release gate.

Both directions throughout: an honest rate is published, and each way of
forging one is caught.

The gate mirrors this schedule as literals because it is stdlib-only and
cannot import the module it checks. That mirror is pinned equal to what the
committed note actually prints, here, so the two cannot drift.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from data_pipeline.exporter.build_graph import index_tree
from data_pipeline.verification.us_code_pay_schedules import (
    DEFAULT_SCHEDULE_HTML,
    SCHEDULE_6_NODE_ROWS,
    SCHEDULE_LABEL,
    Unreadable,
    apply_pay_evidence,
    build_records,
    load_pay_schedules,
    parse_pay_schedules,
)
from scripts.validate_published_graph import (
    EXECUTIVE_SCHEDULE_RATES,
    JUDICIAL_COMPENSATION_TIERS,
    SCHEDULE_6_HEADING,
    STATUTORY_PAY_NODE_TIERS,
    US_CODE_SCHEDULE_6_COLUMN_HEAD,
    US_CODE_SCHEDULE_6_EFFECTIVE,
    US_CODE_SCHEDULE_6_RATES,
    US_CODE_SCHEDULE_6_YEAR,
    statutory_pay_violations,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PAGE = DEFAULT_SCHEDULE_HTML.read_text(encoding="utf-8", errors="replace")
SCHEDULE_URL = (
    "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title5-section5332&num=0&edition=prelim"
)


def _label(node):
    return "node {!r}".format(node.get("id"))


def _base_tree():
    """A minimal tree carrying the four nodes Schedule 6 reaches."""
    return {
        "id": "the-constitution-of-the-united-states",
        "name": "The Constitution",
        "type": "Foundation",
        "children": [
            {
                "id": "exec-branch",
                "name": "Executive Branch",
                "type": "Branch",
                "children": [
                    {"id": "exec-vp", "name": "The Vice President of the United States", "type": "Position"},
                ],
            },
            {
                "id": "leg-branch",
                "name": "Legislative Branch",
                "type": "Branch",
                "children": [
                    {
                        "id": "leg-house-leadership",
                        "name": "House Leadership",
                        "type": "Office",
                        "children": [
                            {"id": "leg-house-leadership-speaker-of-the-house", "name": "Speaker of the House", "type": "Position"},
                            {"id": "leg-house-leadership-majority-leader", "name": "Majority Leader", "type": "Position"},
                            {"id": "leg-house-leadership-minority-leader", "name": "Minority Leader", "type": "Position"},
                        ],
                    },
                ],
            },
        ],
    }


class ParserTests(unittest.TestCase):
    def test_the_committed_note_carries_all_three_schedules(self):
        schedules = parse_pay_schedules(PAGE)["schedules"]
        self.assertEqual(sorted(schedules), ["5", "6", "7"])
        self.assertEqual(schedules["6"]["year"], US_CODE_SCHEDULE_6_YEAR)

    def test_the_gate_s_mirror_equals_what_the_note_prints(self):
        rows = {r["office"].casefold(): r["amount"] for r in parse_pay_schedules(PAGE)["schedules"]["6"]["rows"]}
        for tier, amount in US_CODE_SCHEDULE_6_RATES.items():
            self.assertIn(tier, rows, f"the note does not print a row for {tier!r}")
            self.assertEqual(rows[tier], amount, f"the mirror and the note disagree about {tier!r}")

    def test_the_gate_s_effective_line_and_column_head_are_the_note_s_own(self):
        schedule = parse_pay_schedules(PAGE)["schedules"]["6"]
        self.assertEqual(schedule["effective"], US_CODE_SCHEDULE_6_EFFECTIVE)
        self.assertEqual(schedule["columnHead"]["text"], US_CODE_SCHEDULE_6_COLUMN_HEAD)
        self.assertEqual("Schedule {} — {}".format(schedule["number"], schedule["title"]), SCHEDULE_6_HEADING)

    def test_the_mark_sits_once_at_the_head_of_the_column(self):
        rows = parse_pay_schedules(PAGE)["schedules"]["6"]["rows"]
        self.assertTrue(rows[0]["marked"])
        self.assertFalse(any(row["marked"] for row in rows[1:]))

    def test_a_reshaped_schedule_yields_nothing_rather_than_a_guess(self):
        # Every occurrence, not the first: the note reproduces several years'
        # orders and the first effective line on the page belongs to a
        # schedule this parser does not read, so a single replacement would
        # corrupt nothing it looks at and the test would pass vacuously.
        attacks = {
            "no effective line": PAGE.replace(US_CODE_SCHEDULE_6_EFFECTIVE, "Sometime around 2026"),
            "the head loses its mark": PAGE.replace("$292,300", "292,300", 1),
        }
        for name, corrupted in attacks.items():
            with self.subTest(attack=name):
                with self.assertRaises(Unreadable):
                    parse_pay_schedules(corrupted)

    def test_a_schedule_6_under_another_heading_is_refused_rather_than_priced(self):
        # The reviewed table identifies nodes by the words a row prints, and
        # those words only mean what they say inside this schedule.
        corrupted = PAGE.replace("Vice President and Members Of Congress", "Something Else", 1)
        schedules = parse_pay_schedules(corrupted)["schedules"]
        with self.assertRaises(Unreadable):
            build_records(
                index_tree(_base_tree())[0], schedules,
                url=SCHEDULE_URL, sha256="a" * 64, retrieved_at="2026-09-23T00:00:00Z",
            )

    def test_a_second_marked_row_is_refused(self):
        # If the page ever marked every figure this would not be the
        # typesetting COLUMN_HEAD_MARK_SOURCE_TYPES is written for, and a
        # record built from it would quote the wrong thing as its head.
        corrupted = PAGE.replace(">223,500<", ">$223,500<", 1)
        if corrupted == PAGE:  # the markup differs; mark the figure wherever it sits
            corrupted = PAGE.replace("223,500", "$223,500", 1)
        with self.assertRaises(Unreadable):
            parse_pay_schedules(corrupted)

    def test_a_tampered_fixture_is_refused_by_digest(self):
        import shutil
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / DEFAULT_SCHEDULE_HTML.name
            shutil.copy(DEFAULT_SCHEDULE_HTML, copy)
            shutil.copy(DEFAULT_SCHEDULE_HTML.with_name(DEFAULT_SCHEDULE_HTML.name + ".meta.json"),
                        copy.with_name(copy.name + ".meta.json"))
            copy.write_text(PAGE.replace("223,500", "999,999"), encoding="utf-8")
            with self.assertRaises(Unreadable):
                load_pay_schedules(copy)


class CorroborationTests(unittest.TestCase):
    """The same document carries the schedules two other modules price from.
    Nothing is published from either; the agreement is the point."""

    def test_schedule_5_agrees_with_opm_s_executive_schedule_table(self):
        rows = {r["office"]: r["amount"] for r in parse_pay_schedules(PAGE)["schedules"]["5"]["rows"]}
        for level, amount in EXECUTIVE_SCHEDULE_RATES.items():
            self.assertEqual(rows[f"Level {level}"], amount)

    def test_schedule_7_agrees_with_uscourts_gov_s_own_table(self):
        rows = {r["office"]: r["amount"] for r in parse_pay_schedules(PAGE)["schedules"]["7"]["rows"]}
        self.assertEqual(rows["Chief Justice of the United States"], JUDICIAL_COMPENSATION_TIERS["chief justice"])
        self.assertEqual(rows["Associate Justices of the Supreme Court"], JUDICIAL_COMPENSATION_TIERS["associate justices"])
        self.assertEqual(rows["Circuit Judges"], JUDICIAL_COMPENSATION_TIERS["circuit judges"])
        self.assertEqual(rows["District Judges"], JUDICIAL_COMPENSATION_TIERS["district judges"])


class ScopeTests(unittest.TestCase):
    def test_exactly_the_four_offices_the_reviewed_table_names_are_priced(self):
        tree = _base_tree()
        records, report = build_records(
            index_tree(tree)[0], parse_pay_schedules(PAGE)["schedules"],
            url=SCHEDULE_URL, sha256="a" * 64, retrieved_at="2026-09-23T00:00:00Z",
        )
        self.assertEqual(sorted(records), sorted(SCHEDULE_6_NODE_ROWS))
        self.assertEqual(report["priced"], 4)
        self.assertEqual(report["schedule7Priced"], 0)

    def test_no_senate_leadership_node_is_priced_from_this_source(self):
        # Schedule 6 names them, senate.gov already prices them, and the
        # field holds one source.
        for node_id in SCHEDULE_6_NODE_ROWS:
            self.assertFalse(node_id.startswith("leg-senate-"), node_id)

    def test_the_vice_president_is_priced_once_though_the_graph_carries_the_office_twice(self):
        self.assertIn("exec-vp", SCHEDULE_6_NODE_ROWS)
        self.assertNotIn(
            "leg-senate-leadership-president-of-the-senate-vice-president", SCHEDULE_6_NODE_ROWS
        )

    def test_a_node_another_source_already_priced_is_left_alone(self):
        tree = _base_tree()
        records, _ = build_records(
            index_tree(tree)[0], parse_pay_schedules(PAGE)["schedules"],
            url=SCHEDULE_URL, sha256="a" * 64, retrieved_at="2026-09-23T00:00:00Z",
        )
        node_map = index_tree(tree)[0]
        node_map["leg-house-leadership-speaker-of-the-house"]["positionStatutoryPay"] = {"source": "somebody_else"}
        stats = apply_pay_evidence(tree, records)
        self.assertEqual(stats["already_priced_by_another_source"], 1)
        self.assertEqual(
            index_tree(tree)[0]["leg-house-leadership-speaker-of-the-house"]["positionStatutoryPay"]["source"],
            "somebody_else",
        )

    def test_a_node_standing_for_several_posts_is_refused(self):
        tree = _base_tree()
        node_map = index_tree(tree)[0]
        node_map["leg-house-leadership-speaker-of-the-house"]["representsPosts"] = 2
        records, _ = build_records(
            node_map, parse_pay_schedules(PAGE)["schedules"],
            url=SCHEDULE_URL, sha256="a" * 64, retrieved_at="2026-09-23T00:00:00Z",
        )
        self.assertNotIn("leg-house-leadership-speaker-of-the-house", records)


class GateTests(unittest.TestCase):
    def _apply(self):
        tree = _base_tree()
        records, _ = build_records(
            index_tree(tree)[0], parse_pay_schedules(PAGE)["schedules"],
            url=SCHEDULE_URL, sha256="a" * 64, retrieved_at="2026-09-23T00:00:00Z",
        )
        apply_pay_evidence(tree, records)
        return tree, index_tree(tree)[0]

    def test_every_priced_node_has_a_known_tier_in_the_gate_s_mirror(self):
        for node_id, office in SCHEDULE_6_NODE_ROWS.items():
            self.assertIn(node_id, STATUTORY_PAY_NODE_TIERS)
            self.assertEqual(STATUTORY_PAY_NODE_TIERS[node_id], office.casefold())

    def test_an_honest_record_passes(self):
        _, node_map = self._apply()
        for node_id in SCHEDULE_6_NODE_ROWS:
            with self.subTest(node=node_id):
                node = node_map[node_id]
                self.assertEqual(statutory_pay_violations(node, node["positionStatutoryPay"], "2026-09-24", _label), [])

    def test_a_swap_between_the_two_leaders_priced_from_one_row_is_caught(self):
        # The House Majority and Minority Leaders are priced from a single row
        # that names them together, so they share a figure, a quote, a tier
        # and a citation. Only the node's own identity tells them apart --
        # and here even the tier is identical, so what catches the swap is
        # that the record is keyed by node id at all.
        _, node_map = self._apply()
        majority = node_map["leg-house-leadership-majority-leader"]
        minority = node_map["leg-house-leadership-minority-leader"]
        self.assertEqual(majority["positionStatutoryPay"]["amount"], minority["positionStatutoryPay"]["amount"])
        self.assertEqual(majority["positionStatutoryPay"]["seatTier"], minority["positionStatutoryPay"]["seatTier"])
        # A tier from the OTHER schedule row, however, is caught.
        forged = {**majority["positionStatutoryPay"], "seatTier": "speaker of the house of representatives"}
        violations = statutory_pay_violations(majority, forged, "2026-09-24", _label)
        self.assertTrue(any("on a node that is a" in v for v in violations))

    def test_every_forgery_this_module_makes_possible_is_caught(self):
        _, node_map = self._apply()
        node = node_map["leg-house-leadership-speaker-of-the-house"]
        base = node["positionStatutoryPay"]
        attacks = {
            "wrong amount": {**base, "amount": 1.0},
            "wrong year": {**base, "year": "1999", "effective": "1999-01-01"},
            "wrong url": {**base, "url": "https://example.com/"},
            "future retrieval date": {**base, "checkedAt": "2099-01-01T00:00:00Z"},
            "unknown source": {**base, "source": "made_up_source"},
            "quote without the figure": {**base, "quote": "irrelevant text", "footnotes": ["irrelevant text"]},
            "quote without the schedule's heading": {
                **base,
                "quote": base["quote"].replace(SCHEDULE_6_HEADING, "Schedule 99 — Something Else"),
                "footnotes": [base["quote"].replace(SCHEDULE_6_HEADING, "Schedule 99 — Something Else")],
            },
            "quote without the effective line": {
                **base,
                "quote": base["quote"].replace(US_CODE_SCHEDULE_6_EFFECTIVE, ""),
                "footnotes": [base["quote"].replace(US_CODE_SCHEDULE_6_EFFECTIVE, "")],
            },
            "bare figure with no marked column head quoted": {
                **base,
                "quote": base["quote"].replace(US_CODE_SCHEDULE_6_COLUMN_HEAD, "292,300"),
                "footnotes": [base["quote"].replace(US_CODE_SCHEDULE_6_COLUMN_HEAD, "292,300")],
            },
            "footnotes that are not the quote": {**base, "footnotes": ["something else entirely"]},
            "rate text disagrees with the amount": {**base, "rateText": "$1"},
        }
        for name, pay in attacks.items():
            with self.subTest(attack=name):
                self.assertTrue(statutory_pay_violations(node, pay, "2026-09-24", _label), f"{name} was not caught")

    def test_a_judicial_node_cannot_be_priced_from_this_source(self):
        _, node_map = self._apply()
        node = dict(node_map["leg-house-leadership-speaker-of-the-house"])
        node["id"] = "jud-scotus-chief-justice-of-the-united-states"
        violations = statutory_pay_violations(node, node_map[
            "leg-house-leadership-speaker-of-the-house"]["positionStatutoryPay"], "2026-09-24", _label)
        self.assertTrue(any("outside the" in v for v in violations))

    def test_the_sourceUrls_leak_this_module_must_never_repeat_is_caught(self):
        _, node_map = self._apply()
        node = node_map["leg-house-leadership-speaker-of-the-house"]
        node["sourceUrls"] = [SCHEDULE_URL]
        violations = statutory_pay_violations(node, node["positionStatutoryPay"], "2026-09-24", _label)
        self.assertTrue(any("among the sources that it exists" in v for v in violations))


class PublishedGraphTests(unittest.TestCase):
    """What the site actually carries."""

    @classmethod
    def setUpClass(cls):
        path = PROJECT_ROOT / "output" / "graph.json"
        if not path.exists():
            raise unittest.SkipTest("no published graph to check")
        cls.nodes = {}

        def walk(node):
            cls.nodes[node.get("id")] = node
            for child in node.get("children") or []:
                walk(child)

        walk(json.loads(path.read_text(encoding="utf-8")))

    def test_the_four_offices_are_priced_on_the_published_graph(self):
        for node_id in SCHEDULE_6_NODE_ROWS:
            node = self.nodes.get(node_id)
            self.assertIsNotNone(node, node_id)
            pay = node.get("positionStatutoryPay")
            self.assertIsInstance(pay, dict, node_id)
            self.assertEqual(pay.get("source"), "us_code_pay_schedules", node_id)

    def test_no_priced_node_gained_a_uscode_url_among_its_sources(self):
        # The exact channel by which a five-row pay table carried 29
        # positions to `verified` on 2026-09-11.
        for node_id in SCHEDULE_6_NODE_ROWS:
            urls = self.nodes[node_id].get("sourceUrls") or []
            self.assertFalse([u for u in urls if "uscode.house.gov" in str(u)], node_id)

    def test_the_three_senate_leaders_still_carry_the_senate_s_own_claim(self):
        for node_id in (
            "leg-senate-leadership-president-pro-tempore",
            "leg-senate-leadership-majority-leader",
            "leg-senate-leadership-minority-leader",
        ):
            pay = self.nodes[node_id].get("positionStatutoryPay")
            self.assertEqual(pay.get("source"), "senate_salary_schedule", node_id)

    def test_no_priced_node_carries_a_cost(self):
        for node_id in SCHEDULE_6_NODE_ROWS:
            node = self.nodes[node_id]
            self.assertNotIn(node.get("cost_status"), ("official", "root_total", "scaled_official"))


if __name__ == "__main__":
    unittest.main()
