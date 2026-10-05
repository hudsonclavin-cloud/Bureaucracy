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


# ---------------------------------------------------------------------------
# Members of Congress, priced at the seat rate (since 2026-09-30, the owner's
# decision). A committee's chair and ranking member, the whips and the
# conference chairs are Members; Schedule 6 prints no separate rate for those
# offices, so each is priced at its chamber's seat row. Both directions: the
# rule prices exactly what it should, and every way of forging a seat is caught.

from data_pipeline.verification.us_code_pay_schedules import (  # noqa: E402
    CHAMBER_SEAT_ROWS,
    HOUSE_SEAT_ROWS_NOTE,
    MEMBER_COMMITTEE_TYPES,
    MEMBER_LEADERSHIP_NODES,
    MEMBER_ROLE_PREFIXES,
    MEMBER_SEATS_NOT_PRICED,
    METHOD_MEMBER_SEAT,
    SEPARATE_RATES_SENTENCE,
    match_member_seats,
)
from scripts.validate_published_graph import (  # noqa: E402
    US_CODE_HOUSE_SEAT_ROWS_NOTE,
    US_CODE_MEMBER_COMMITTEE_TYPES,
    US_CODE_MEMBER_LEADERSHIP_NODES,
    US_CODE_MEMBER_ROLE_PREFIXES,
    US_CODE_MEMBER_SEAT_METHOD,
    US_CODE_MEMBER_SEAT_ROWS,
    US_CODE_MEMBER_SEAT_SEPARATE_RATES,
    US_CODE_MEMBER_SEATS_NOT_PRICED,
)


def _member_tree():
    """A tree with both chambers, a joint committee, staff beside the chairs,
    and a chair-shaped name outside any committee."""
    return {
        "id": "the-constitution-of-the-united-states",
        "name": "The Constitution",
        "type": "Foundation",
        "children": [
            {
                "id": "legislative-branch", "name": "Legislative Branch", "type": "Branch",
                "children": [
                    {
                        "id": "leg-senate", "name": "U.S. Senate", "type": "Chamber",
                        "children": [
                            {
                                "id": "leg-senate-cmte-x", "name": "Senate Committee on X", "type": "Committee",
                                "children": [
                                    {"id": "leg-senate-cmte-x-chair", "name": "Chair, X", "type": "Position"},
                                    {"id": "leg-senate-cmte-x-rm", "name": "Ranking Member, X", "type": "Position"},
                                    {"id": "leg-senate-cmte-x-sd", "name": "Staff Director", "type": "Position"},
                                    {
                                        "id": "leg-senate-cmte-x-sub-y", "name": "Subcommittee on Y", "type": "Subcommittee",
                                        "children": [
                                            {"id": "leg-senate-cmte-x-sub-y-chair", "name": "Chair, Subcommittee on Y", "type": "Position"},
                                            {"id": "leg-senate-cmte-x-sub-y-msd", "name": "Minority Staff Director", "type": "Position"},
                                        ],
                                    },
                                ],
                            },
                            {
                                "id": "leg-senate-leadership", "name": "Senate Leadership", "type": "Office",
                                "children": [
                                    {"id": "leg-senate-leadership-majority-whip", "name": "Majority Whip", "type": "Position"},
                                    {"id": "leg-senate-leadership-majority-leader", "name": "Majority Leader", "type": "Position"},
                                    {"id": "leg-senate-leadership-president-of-the-senate-vice-president", "name": "President of the Senate (Vice President)", "type": "Position"},
                                ],
                            },
                        ],
                    },
                    {
                        "id": "leg-house", "name": "U.S. House of Representatives", "type": "Chamber",
                        "children": [
                            {
                                "id": "leg-house-cmte-z", "name": "House Committee on Z", "type": "Committee",
                                "children": [
                                    {"id": "leg-house-cmte-z-chair", "name": "Chair, Z", "type": "Position"},
                                    {"id": "leg-house-cmte-z-rm", "name": "Ranking Member, Z", "type": "Position"},
                                    {"id": "leg-house-cmte-z-many", "name": "Chair, Z (×2)", "type": "Position",
                                     "representsPosts": {"text": "×2", "kind": "exact", "count": 2}},
                                ],
                            },
                            {
                                "id": "leg-house-leadership", "name": "House Leadership", "type": "Office",
                                "children": [
                                    {"id": "leg-house-leadership-majority-whip", "name": "Majority Whip", "type": "Position"},
                                    {"id": "leg-house-leadership-speaker-of-the-house", "name": "Speaker of the House", "type": "Position"},
                                    {"id": "leg-house-leadership-problem-solvers-caucus-co-chairs", "name": "Problem Solvers Caucus Co-Chairs", "type": "Position"},
                                ],
                            },
                        ],
                    },
                    {
                        "id": "leg-joint", "name": "Joint Committees", "type": "Grouping",
                        "children": [
                            {
                                "id": "leg-joint-econ", "name": "Joint Economic Committee", "type": "Committee",
                                "children": [
                                    {"id": "leg-joint-econ-chair-alternates-senate-house", "name": "Chair (alternates Senate/House)", "type": "Position"},
                                    {"id": "leg-joint-econ-vice-chair", "name": "Vice Chair", "type": "Position"},
                                ],
                            },
                            {
                                "id": "leg-joint-other", "name": "Joint Committee on W", "type": "Committee",
                                "children": [
                                    {"id": "leg-joint-other-chair", "name": "Chair, W", "type": "Position"},
                                ],
                            },
                        ],
                    },
                ],
            },
            {
                "id": "executive-branch", "name": "Executive Branch", "type": "Branch",
                "children": [
                    {
                        "id": "exec-ind-board", "name": "Some Board", "type": "Independent Agency",
                        "children": [
                            {"id": "exec-ind-board-chair", "name": "Chair, Some Board", "type": "Position"},
                        ],
                    },
                ],
            },
        ],
    }


def _member_records(tree):
    node_map, parent_map = index_tree(tree)
    return build_records(
        node_map, parse_pay_schedules(PAGE)["schedules"],
        url=SCHEDULE_URL, sha256="a" * 64, retrieved_at="2026-09-30T00:00:00Z", parent_map=parent_map,
    )


class MemberSeatMirrorTests(unittest.TestCase):
    """The gate mirrors the RULE, not 461 ids; the two copies cannot drift."""

    def test_the_gate_s_rule_equals_the_module_s(self):
        self.assertEqual(METHOD_MEMBER_SEAT, US_CODE_MEMBER_SEAT_METHOD)
        self.assertEqual({k: v.casefold() for k, v in CHAMBER_SEAT_ROWS.items()}, US_CODE_MEMBER_SEAT_ROWS)
        self.assertEqual(tuple(MEMBER_ROLE_PREFIXES), tuple(US_CODE_MEMBER_ROLE_PREFIXES))
        self.assertEqual(tuple(MEMBER_COMMITTEE_TYPES), tuple(US_CODE_MEMBER_COMMITTEE_TYPES))
        self.assertEqual(dict(MEMBER_LEADERSHIP_NODES), dict(US_CODE_MEMBER_LEADERSHIP_NODES))
        self.assertEqual(tuple(sorted(MEMBER_SEATS_NOT_PRICED)), tuple(sorted(US_CODE_MEMBER_SEATS_NOT_PRICED)))
        self.assertEqual(SEPARATE_RATES_SENTENCE, US_CODE_MEMBER_SEAT_SEPARATE_RATES)
        self.assertEqual(HOUSE_SEAT_ROWS_NOTE, US_CODE_HOUSE_SEAT_ROWS_NOTE)

    def test_the_seat_rows_are_what_the_note_prints(self):
        rows = {r["office"]: r["amount"] for r in parse_pay_schedules(PAGE)["schedules"]["6"]["rows"]}
        for chamber, office in CHAMBER_SEAT_ROWS.items():
            self.assertEqual(rows[office], US_CODE_SCHEDULE_6_RATES[office.casefold()], office)
            self.assertEqual(rows[office], 174_000.0)
        # The House rows the basis note names print the same figure.
        self.assertEqual(rows["Delegates to the House of Representatives"], 174_000.0)
        self.assertEqual(rows["Resident Commissioner from Puerto Rico"], 174_000.0)

    def test_the_leadership_table_is_twenty_five_offices_in_two_chambers(self):
        self.assertEqual(25, len(MEMBER_LEADERSHIP_NODES))
        self.assertEqual(11, sum(1 for c in MEMBER_LEADERSHIP_NODES.values() if c == "leg-senate"))
        self.assertEqual(14, sum(1 for c in MEMBER_LEADERSHIP_NODES.values() if c == "leg-house"))
        for node_id, chamber in MEMBER_LEADERSHIP_NODES.items():
            self.assertTrue(node_id.startswith(chamber + "-leadership-"), node_id)
            self.assertNotIn(node_id, STATUTORY_PAY_NODE_TIERS, node_id)
            self.assertNotIn(node_id, SCHEDULE_6_NODE_ROWS, node_id)

    def test_a_leadership_office_with_its_own_row_is_never_in_the_seat_table(self):
        for node_id in list(SCHEDULE_6_NODE_ROWS) + list(STATUTORY_PAY_NODE_TIERS):
            self.assertNotIn(node_id, MEMBER_LEADERSHIP_NODES)


class MemberSeatMatchingTests(unittest.TestCase):
    def test_chairs_and_ranking_members_under_both_chambers_are_priced_at_their_chamber_s_row(self):
        records, report = _member_records(_member_tree())
        self.assertEqual(records["leg-senate-cmte-x-chair"]["memberSeat"]["row"], "Senators")
        self.assertEqual(records["leg-senate-cmte-x-rm"]["memberSeat"]["role"], "Ranking Member")
        self.assertEqual(records["leg-senate-cmte-x-sub-y-chair"]["memberSeat"]["body"], "Subcommittee on Y")
        self.assertEqual(records["leg-house-cmte-z-chair"]["memberSeat"]["row"], "Members of the House of Representatives")
        self.assertEqual(records["leg-house-cmte-z-chair"]["role"], "members of the house of representatives")
        self.assertEqual(records["leg-house-cmte-z-chair"]["amount"], 174_000.0)
        self.assertEqual(records["leg-house-cmte-z-chair"]["method"], METHOD_MEMBER_SEAT)
        self.assertEqual(records["leg-house-cmte-z-chair"]["scopeMatch"], "proxy")
        self.assertEqual(report["memberSeats"]["byChamber"], {"leg-senate": 4, "leg-house": 3})

    def test_staff_beside_the_chairs_are_never_reached(self):
        records, _ = _member_records(_member_tree())
        self.assertNotIn("leg-senate-cmte-x-sd", records)
        self.assertNotIn("leg-senate-cmte-x-sub-y-msd", records)

    def test_a_chair_shaped_name_outside_a_committee_is_not_considered(self):
        records, _ = _member_records(_member_tree())
        self.assertNotIn("exec-ind-board-chair", records)

    def test_the_joint_committees_are_refused_for_want_of_a_chamber(self):
        node_map, parent_map = index_tree(_member_tree())
        matches, refusals, reasons = match_member_seats(node_map, parent_map)
        self.assertNotIn("leg-joint-other-chair", matches)
        self.assertEqual(reasons["leg-joint-other-chair"], "chamber_not_determinable_from_the_tree")
        self.assertTrue(reasons["leg-joint-econ-chair-alternates-senate-house"].startswith("refused_by_name:"))
        self.assertTrue(reasons["leg-joint-econ-vice-chair"].startswith("refused_by_name:"))

    def test_the_leadership_table_prices_the_whips_and_refuses_by_name(self):
        records, _ = _member_records(_member_tree())
        self.assertEqual(records["leg-senate-leadership-majority-whip"]["memberSeat"]["kind"], "leadership_office")
        self.assertEqual(records["leg-senate-leadership-majority-whip"]["memberSeat"]["role"], "Majority Whip")
        self.assertEqual(records["leg-house-leadership-majority-whip"]["role"], "members of the house of representatives")
        self.assertNotIn("leg-house-leadership-problem-solvers-caucus-co-chairs", records)
        self.assertNotIn("leg-senate-leadership-president-of-the-senate-vice-president", records)
        # The leaders with their own row keep it; the Senate's is senate.gov's.
        self.assertNotIn("leg-senate-leadership-majority-leader", records)
        self.assertEqual(records["leg-house-leadership-speaker-of-the-house"]["role"], "speaker of the house of representatives")
        self.assertNotIn("memberSeat", records["leg-house-leadership-speaker-of-the-house"])

    def test_a_node_standing_for_several_posts_is_refused(self):
        node_map, parent_map = index_tree(_member_tree())
        _, _, reasons = match_member_seats(node_map, parent_map)
        self.assertEqual(reasons["leg-house-cmte-z-many"], "stands_for_several_posts")

    def test_a_leadership_office_moved_to_the_other_chamber_is_refused(self):
        tree = _member_tree()
        node_map, parent_map = index_tree(tree)
        parent_map = dict(parent_map)
        parent_map["leg-senate-leadership-majority-whip"] = "leg-house-leadership"
        _, _, reasons = match_member_seats(node_map, parent_map)
        self.assertEqual(reasons["leg-senate-leadership-majority-whip"], "leadership_office_moved_to_another_chamber")

    def test_without_the_tree_no_seat_is_priced(self):
        records, report = build_records(
            index_tree(_member_tree())[0], parse_pay_schedules(PAGE)["schedules"],
            url=SCHEDULE_URL, sha256="a" * 64, retrieved_at="2026-09-30T00:00:00Z",
        )
        self.assertFalse([n for n, r in records.items() if "memberSeat" in r])
        self.assertFalse(report["memberSeats"]["treeGiven"])

    def test_the_basis_says_it_is_a_rule_and_quotes_the_schedule_s_own_list(self):
        records, _ = _member_records(_member_tree())
        for node_id, record in records.items():
            seat = record.get("memberSeat")
            if not seat:
                continue
            with self.subTest(node=node_id):
                self.assertIn(SEPARATE_RATES_SENTENCE, seat["basis"])
                self.assertIn("a reviewed rule, not a document naming this post", seat["basis"])
                self.assertIn("never read", seat["basis"])
                if seat["chamber"] == "leg-house":
                    self.assertIn(HOUSE_SEAT_ROWS_NOTE, seat["basis"])
                else:
                    self.assertNotIn("Delegates", seat["basis"])

    def test_apply_stamps_the_block_with_its_own_method(self):
        tree = _member_tree()
        records, _ = _member_records(tree)
        stats = apply_pay_evidence(tree, records)
        self.assertEqual(stats["member_seats"], 7)
        node_map = index_tree(tree)[0]
        pay = node_map["leg-senate-cmte-x-chair"]["positionStatutoryPay"]
        self.assertEqual(pay["method"], METHOD_MEMBER_SEAT)
        self.assertEqual(pay["memberSeat"]["row"], "Senators")
        self.assertNotIn("sourceUrls", node_map["leg-senate-cmte-x-chair"])
        self.assertNotIn("memberSeat", node_map["leg-house-leadership-speaker-of-the-house"]["positionStatutoryPay"])


class MemberSeatGateTests(unittest.TestCase):
    def _apply(self):
        tree = _member_tree()
        records, _ = _member_records(tree)
        apply_pay_evidence(tree, records)
        node_map, parent_map = index_tree(tree)
        type_by_id = {k: v.get("type") for k, v in node_map.items()}
        name_by_id = {k: v.get("name") for k, v in node_map.items()}
        return node_map, dict(parent_map), type_by_id, name_by_id

    def _check(self, node, pay, parents, types, names):
        return statutory_pay_violations(node, pay, "2026-09-30", _label,
                                        tree_parents=parents, type_by_id=types, name_by_id=names)

    def test_every_honest_seat_passes(self):
        node_map, parents, types, names = self._apply()
        for node_id, node in node_map.items():
            pay = node.get("positionStatutoryPay")
            if not isinstance(pay, dict) or "memberSeat" not in pay:
                continue
            with self.subTest(node=node_id):
                self.assertEqual(self._check(node, pay, parents, types, names), [])

    def test_the_four_named_offices_still_pass_with_the_tree_given(self):
        node_map, parents, types, names = self._apply()
        node = node_map["leg-house-leadership-speaker-of-the-house"]
        self.assertEqual(self._check(node, node["positionStatutoryPay"], parents, types, names), [])

    def test_every_forgery_the_seat_rule_makes_possible_is_caught(self):
        node_map, parents, types, names = self._apply()
        house = node_map["leg-house-cmte-z-chair"]
        base = house["positionStatutoryPay"]
        seat = base["memberSeat"]
        attacks = {
            "the other chamber's row": {**base, "seatTier": "senators", "amountScope": "Senators",
                                        "memberSeat": {**seat, "row": "Senators", "chamber": "leg-senate"}},
            "the seat block dropped": {k: v for k, v in base.items() if k != "memberSeat"},
            "the method dropped": {**base, "method": "office_named_in_schedule_6_of_the_annual_pay_adjustment_order"},
            "a basis without the schedule's own list": {**base, "memberSeat": {**seat, "basis": "because"}},
            "a basis that does not say it is a rule": {**base, "memberSeat": {**seat, "basis": SEPARATE_RATES_SENTENCE + " never read " + HOUSE_SEAT_ROWS_NOTE}},
            "a House basis without the Delegate note": {**base, "memberSeat": {**seat, "basis": seat["basis"].replace(HOUSE_SEAT_ROWS_NOTE, "")}},
            "a body the name does not say": {**base, "memberSeat": {**seat, "body": "Something Else"}},
            "a role the name does not say": {**base, "memberSeat": {**seat, "role": "Ranking Member"}},
            "filed as a leadership office": {**base, "memberSeat": {**seat, "kind": "leadership_office"}},
            "another source": {**base, "source": "senate_salary_schedule"},
        }
        for name, pay in attacks.items():
            with self.subTest(attack=name):
                self.assertTrue(self._check(house, pay, parents, types, names), f"{name} was not caught")

    def test_a_seat_on_a_leader_with_its_own_row_is_caught(self):
        node_map, parents, types, names = self._apply()
        chair = node_map["leg-house-cmte-z-chair"]
        speaker = node_map["leg-house-leadership-speaker-of-the-house"]
        forged = dict(chair["positionStatutoryPay"])
        forged["memberSeat"] = {**forged["memberSeat"], "kind": "leadership_office", "role": "Speaker of the House"}
        out = self._check(speaker, forged, parents, types, names)
        self.assertTrue(any("row of its own" in v for v in out), out)

    def test_a_seat_priced_without_the_method_is_caught(self):
        node_map, parents, types, names = self._apply()
        chair = node_map["leg-house-cmte-z-chair"]
        pay = {k: v for k, v in chair["positionStatutoryPay"].items() if k != "memberSeat"}
        pay["method"] = "office_named_in_schedule_6_of_the_annual_pay_adjustment_order"
        out = self._check(chair, pay, parents, types, names)
        self.assertTrue(any("without the member-seat method" in v for v in out), out)

    def test_a_post_moved_off_its_committee_is_caught(self):
        node_map, parents, types, names = self._apply()
        chair = node_map["leg-house-cmte-z-chair"]
        types = dict(types)
        types["leg-house-cmte-z"] = "Office"
        out = self._check(chair, chair["positionStatutoryPay"], parents, types, names)
        self.assertTrue(any("not a committee" in v for v in out), out)

    def test_a_post_moved_out_of_both_chambers_is_caught(self):
        node_map, parents, types, names = self._apply()
        chair = node_map["leg-house-cmte-z-chair"]
        parents = dict(parents)
        parents["leg-house-cmte-z"] = "leg-joint"
        out = self._check(chair, chair["positionStatutoryPay"], parents, types, names)
        self.assertTrue(any("neither chamber" in v for v in out), out)

    def test_a_renamed_post_is_caught(self):
        node_map, parents, types, names = self._apply()
        chair = dict(node_map["leg-house-cmte-z-chair"])
        chair["name"] = "Staff Director, Z"
        out = self._check(chair, chair["positionStatutoryPay"], parents, types, names)
        self.assertTrue(any("no Member-role prefix" in v for v in out), out)

    def test_a_seat_on_a_node_standing_for_several_posts_is_caught(self):
        node_map, parents, types, names = self._apply()
        chair = dict(node_map["leg-house-cmte-z-chair"])
        chair["representsPosts"] = {"text": "×2", "kind": "exact", "count": 2}
        out = self._check(chair, chair["positionStatutoryPay"], parents, types, names)
        self.assertTrue(any("several posts" in v for v in out), out)

    def test_a_post_the_rule_refuses_by_name_is_caught(self):
        node_map, parents, types, names = self._apply()
        chair = node_map["leg-house-cmte-z-chair"]
        refused = dict(node_map["leg-house-leadership-problem-solvers-caucus-co-chairs"])
        pay = dict(chair["positionStatutoryPay"])
        pay["memberSeat"] = {**pay["memberSeat"], "kind": "leadership_office", "role": refused["name"]}
        out = self._check(refused, pay, parents, types, names)
        self.assertTrue(any("refuses by name" in v for v in out), out)

    def test_a_leadership_office_moved_to_the_other_chamber_is_caught(self):
        node_map, parents, types, names = self._apply()
        whip = node_map["leg-senate-leadership-majority-whip"]
        parents = dict(parents)
        parents["leg-senate-leadership"] = "leg-house"
        out = self._check(whip, whip["positionStatutoryPay"], parents, types, names)
        self.assertTrue(any("table places in" in v for v in out), out)

    def test_without_the_tree_the_seat_cannot_be_checked_and_is_refused(self):
        node_map, _, _, _ = self._apply()
        chair = node_map["leg-house-cmte-z-chair"]
        out = statutory_pay_violations(chair, chair["positionStatutoryPay"], "2026-09-30", _label)
        self.assertTrue(any("no tree" in v for v in out), out)


class MemberSeatPublishedGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = PROJECT_ROOT / "output" / "graph.json"
        if not path.exists():
            raise unittest.SkipTest("no published graph to check")
        cls.tree = json.loads(path.read_text(encoding="utf-8"))
        cls.nodes, cls.parents = index_tree(cls.tree)

    def _chamber(self, node_id):
        current = self.parents.get(node_id)
        while current:
            if current in CHAMBER_SEAT_ROWS:
                return current
            current = self.parents.get(current)
        return None

    def test_every_chair_and_ranking_member_under_a_chamber_s_committee_carries_a_seat(self):
        expected = set()
        for node_id, node in self.nodes.items():
            parent = self.nodes.get(self.parents.get(node_id) or "")
            if parent is None or str(parent.get("type") or "").casefold() not in MEMBER_COMMITTEE_TYPES:
                continue
            if str(node.get("type") or "").casefold() != "position" or node.get("representsPosts"):
                continue
            if not str(node.get("name") or "").startswith(MEMBER_ROLE_PREFIXES):
                continue
            if self._chamber(node_id) is None:
                continue
            expected.add(node_id)
        self.assertGreaterEqual(len(expected), 400)
        for node_id in expected:
            pay = self.nodes[node_id].get("positionStatutoryPay")
            with self.subTest(node=node_id):
                self.assertIsInstance(pay, dict)
                self.assertEqual(pay.get("method"), METHOD_MEMBER_SEAT)
                self.assertEqual(pay["memberSeat"]["kind"], "committee_post")
                self.assertEqual(pay["seatTier"], CHAMBER_SEAT_ROWS[self._chamber(node_id)].casefold())
                self.assertEqual(pay["amount"], 174_000.0)

    def test_the_leadership_table_is_priced_and_the_named_refusals_are_not(self):
        for node_id, chamber in MEMBER_LEADERSHIP_NODES.items():
            pay = self.nodes[node_id].get("positionStatutoryPay")
            with self.subTest(node=node_id):
                self.assertIsInstance(pay, dict)
                self.assertEqual(pay["memberSeat"]["kind"], "leadership_office")
                self.assertEqual(pay["memberSeat"]["chamber"], chamber)
        for node_id in MEMBER_SEATS_NOT_PRICED:
            with self.subTest(node=node_id):
                self.assertIn(node_id, self.nodes)
                self.assertNotIn("positionStatutoryPay", self.nodes[node_id])

    def test_staff_directors_are_never_priced_as_members(self):
        for node_id, node in self.nodes.items():
            if "Staff Director" in str(node.get("name") or ""):
                self.assertNotIn("positionStatutoryPay", node, node_id)

    def test_the_seat_block_counts_one_document_that_states_the_figure_for_the_seat(self):
        seen = 0
        for node in self.nodes.values():
            pay = node.get("positionStatutoryPay")
            if not isinstance(pay, dict) or "memberSeat" not in pay:
                continue
            seen += 1
            verification = pay.get("verification") or {}
            self.assertEqual(verification.get("documents"), 1)
            self.assertEqual(verification.get("documentsStatingTheFigure"), 1)
            self.assertIn("SEAT", str(verification.get("caution")))
            self.assertFalse([u for u in (node.get("sourceUrls") or []) if "uscode.house.gov" in str(u)])
            self.assertNotIn(node.get("cost_status"), ("official", "root_total", "scaled_official"))
        self.assertEqual(seen, 461)


# ---------------------------------------------------------------------------
# Schedule 7, since 2026-10-05: the one judicial tier uscourts.gov's table does
# not print. The Court of International Trade's chief judge and bench are priced
# from "Judges of the Court of International Trade"; nothing else judicial may be
# priced from this note, and nothing from Schedule 7 may land outside the
# judiciary.

from data_pipeline.verification.pay_tables import withdraw_pay_from_multi_post_nodes  # noqa: E402
from data_pipeline.verification.us_code_pay_schedules import (  # noqa: E402
    SCHEDULE_7_LABEL,
    SCHEDULE_7_NODE_ROWS,
    SCHEDULE_7_ROWS_NOT_PRICED,
)
from scripts.validate_published_graph import (  # noqa: E402
    SCHEDULE_7_HEADING,
    US_CODE_SCHEDULE_7_COLUMN_HEAD,
    US_CODE_SCHEDULE_7_EFFECTIVE,
    US_CODE_SCHEDULE_7_RATES,
)


def _cit_tree():
    return {
        "id": "the-constitution-of-the-united-states",
        "name": "The Constitution",
        "type": "Foundation",
        "children": [
            {
                "id": "judicial-branch", "name": "Judicial Branch", "type": "Branch",
                "children": [
                    {
                        "id": "jud-specialized", "name": "Specialized Courts", "type": "Grouping",
                        "children": [
                            {
                                "id": "jud-specialized-intl-trade", "name": "U.S. Court of International Trade (CIT)",
                                "type": "Specialized Court",
                                "children": [
                                    {"id": "jud-specialized-intl-trade-chief-judge-cit", "name": "Chief Judge, CIT", "type": "Position"},
                                    {"id": "jud-specialized-intl-trade-judge-8", "name": "Judge (×8)", "type": "Position",
                                     "representsPosts": {"text": "×8", "kind": "exact", "count": 8}},
                                    {"id": "jud-specialized-intl-trade-clerk-of-the-court", "name": "Clerk of the Court", "type": "Position"},
                                ],
                            },
                            {
                                "id": "jud-specialized-tax", "name": "U.S. Tax Court", "type": "Specialized Court",
                                "children": [
                                    {"id": "jud-specialized-tax-chief-judge-tax-court", "name": "Chief Judge, Tax Court", "type": "Position"},
                                ],
                            },
                        ],
                    },
                ],
            },
        ],
    }


class Schedule7MirrorTests(unittest.TestCase):
    def test_the_gate_s_schedule_7_mirror_equals_the_note(self):
        schedule = parse_pay_schedules(PAGE)["schedules"]["7"]
        self.assertEqual("Schedule 7 — {}".format(schedule["title"]), SCHEDULE_7_HEADING)
        self.assertEqual(SCHEDULE_7_LABEL, SCHEDULE_7_HEADING)
        self.assertEqual(schedule["effective"], US_CODE_SCHEDULE_7_EFFECTIVE)
        self.assertEqual(schedule["columnHead"]["text"], US_CODE_SCHEDULE_7_COLUMN_HEAD)
        rows = {r["office"].casefold(): r["amount"] for r in schedule["rows"]}
        for tier, rate in US_CODE_SCHEDULE_7_RATES.items():
            self.assertEqual(rows[tier], rate)
        # Every row the module prices is one the gate mirrors, and the rows
        # it does not price are accounted for by name.
        for node_id, office in SCHEDULE_7_NODE_ROWS.items():
            self.assertEqual(STATUTORY_PAY_NODE_TIERS[node_id], office.casefold())
            self.assertIn(office.casefold(), US_CODE_SCHEDULE_7_RATES)
            self.assertTrue(node_id.startswith("jud-"))
        self.assertEqual(
            set(SCHEDULE_7_ROWS_NOT_PRICED) | set(SCHEDULE_7_NODE_ROWS.values()),
            {r["office"] for r in schedule["rows"]},
        )

    def test_the_cit_row_prints_the_district_judge_figure(self):
        # The same number as the District Judges row, which is why the
        # heading and the marked head of Schedule 7's column are required.
        rows = {r["office"]: r["amount"] for r in parse_pay_schedules(PAGE)["schedules"]["7"]["rows"]}
        self.assertEqual(rows["Judges of the Court of International Trade"], rows["District Judges"])
        self.assertEqual(rows["Judges of the Court of International Trade"], 249_900.0)


class Schedule7Tests(unittest.TestCase):
    def _records(self, tree):
        node_map, parent_map = index_tree(tree)
        return build_records(
            node_map, parse_pay_schedules(PAGE)["schedules"],
            url=SCHEDULE_URL, sha256="a" * 64, retrieved_at="2026-10-05T00:00:00Z", parent_map=parent_map,
        )

    def test_the_chief_judge_and_the_bench_are_priced_and_nothing_else_judicial_is(self):
        records, report = self._records(_cit_tree())
        self.assertEqual(sorted(n for n in records if n.startswith("jud-")), sorted(SCHEDULE_7_NODE_ROWS))
        self.assertEqual(report["schedule7Priced"], 2)
        chief = records["jud-specialized-intl-trade-chief-judge-cit"]
        self.assertEqual(chief["amount"], 249_900.0)
        self.assertEqual(chief["role"], "judges of the court of international trade")
        self.assertEqual(chief["schedule"], "7")
        self.assertIn(SCHEDULE_7_HEADING, chief["quote"])
        self.assertIn(US_CODE_SCHEDULE_7_COLUMN_HEAD, chief["quote"])
        self.assertEqual(chief["scopeMatch"], "proxy")
        self.assertNotIn("jud-specialized-intl-trade-clerk-of-the-court", records)
        self.assertNotIn("jud-specialized-tax-chief-judge-tax-court", records)

    def test_the_bench_is_applied_and_keeps_the_rate_for_each_holder(self):
        tree = _cit_tree()
        records, _ = self._records(tree)
        stats = apply_pay_evidence(tree, records)
        self.assertEqual(stats["schedule_7"], 2)
        withdraw_pay_from_multi_post_nodes(tree)
        node_map = index_tree(tree)[0]
        bench = node_map["jud-specialized-intl-trade-judge-8"]["positionStatutoryPay"]
        self.assertEqual(bench["schedule"], "7")
        self.assertEqual(bench["holders"]["count"], 8)
        self.assertTrue(bench["holders"]["appliesToEachHolder"])
        self.assertNotIn("holders", node_map["jud-specialized-intl-trade-chief-judge-cit"]["positionStatutoryPay"])
        self.assertNotIn("sourceUrls", node_map["jud-specialized-intl-trade-chief-judge-cit"])

    def _applied(self):
        tree = _cit_tree()
        records, _ = self._records(tree)
        apply_pay_evidence(tree, records)
        withdraw_pay_from_multi_post_nodes(tree)
        node_map, parent_map = index_tree(tree)
        return node_map, dict(parent_map)

    def test_honest_schedule_7_records_pass_the_gate(self):
        node_map, parents = self._applied()
        for node_id in SCHEDULE_7_NODE_ROWS:
            node = node_map[node_id]
            self.assertEqual(statutory_pay_violations(node, node["positionStatutoryPay"], "2026-10-05", _label,
                                                      tree_parents=parents, type_by_id={}, name_by_id={}), [])

    def test_every_forgery_schedule_7_makes_possible_is_caught(self):
        node_map, parents = self._applied()
        chief = node_map["jud-specialized-intl-trade-chief-judge-cit"]
        base = chief["positionStatutoryPay"]
        attacks = {
            "the schedule mark dropped": {k: v for k, v in base.items() if k != "schedule"},
            "the District Judges row claimed instead": {**base, "seatTier": "district judges", "amountScope": "District Judges"},
            "quote without Schedule 7's heading": {**base, "quote": base["quote"].replace(SCHEDULE_7_HEADING, SCHEDULE_6_HEADING),
                                                   "footnotes": [base["quote"].replace(SCHEDULE_7_HEADING, SCHEDULE_6_HEADING)]},
            "quote without the marked head of Schedule 7's column": {
                **base, "quote": base["quote"].replace(US_CODE_SCHEDULE_7_COLUMN_HEAD, "320,700"),
                "footnotes": [base["quote"].replace(US_CODE_SCHEDULE_7_COLUMN_HEAD, "320,700")]},
            "a Schedule 6 office claimed on a judge": {**base, "seatTier": "vice president", "schedule": "6"},
        }
        for name, pay in attacks.items():
            with self.subTest(attack=name):
                out = statutory_pay_violations(chief, pay, "2026-10-05", _label, tree_parents=parents, type_by_id={}, name_by_id={})
                self.assertTrue(out, f"{name} was not caught")

    def test_a_schedule_7_record_moved_to_another_court_s_judge_is_caught(self):
        node_map, parents = self._applied()
        chief = node_map["jud-specialized-intl-trade-chief-judge-cit"]
        tax = node_map["jud-specialized-tax-chief-judge-tax-court"]
        out = statutory_pay_violations(tax, chief["positionStatutoryPay"], "2026-10-05", _label,
                                       tree_parents=parents, type_by_id={}, name_by_id={})
        self.assertTrue(any("no known tier" in v for v in out), out)

    def test_a_schedule_7_record_on_a_non_judicial_node_is_caught(self):
        node_map, parents = self._applied()
        chief = dict(node_map["jud-specialized-intl-trade-chief-judge-cit"])
        chief["id"] = "exec-vp"
        out = statutory_pay_violations(chief, chief["positionStatutoryPay"], "2026-10-05", _label,
                                       tree_parents=parents, type_by_id={}, name_by_id={})
        self.assertTrue(any("outside the judiciary" in v for v in out), out)


class Schedule7PublishedGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = PROJECT_ROOT / "output" / "graph.json"
        if not path.exists():
            raise unittest.SkipTest("no published graph to check")
        cls.nodes = index_tree(json.loads(path.read_text(encoding="utf-8")))[0]

    def test_the_cit_s_chief_judge_and_bench_carry_schedule_7_and_nothing_else_judicial_does(self):
        for node_id in SCHEDULE_7_NODE_ROWS:
            pay = self.nodes[node_id].get("positionStatutoryPay")
            self.assertIsInstance(pay, dict, node_id)
            self.assertEqual(pay.get("source"), "us_code_pay_schedules")
            self.assertEqual(pay.get("schedule"), "7")
            self.assertEqual(pay.get("amount"), 249_900.0)
            self.assertFalse([u for u in (self.nodes[node_id].get("sourceUrls") or []) if "uscode.house.gov" in str(u)])
        self.assertEqual(self.nodes["jud-specialized-intl-trade-judge-8"]["positionStatutoryPay"]["holders"]["count"], 8)
        for node_id, node in self.nodes.items():
            pay = node.get("positionStatutoryPay")
            if node_id.startswith("jud-") and isinstance(pay, dict) and pay.get("source") == "us_code_pay_schedules":
                self.assertIn(node_id, SCHEDULE_7_NODE_ROWS)
