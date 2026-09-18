"""The Executive Schedule as current law sets it, and the gate that guards it.

Until 2026-09-18 the LEVEL half of every Executive Schedule rate in this graph
came from one place: OPM's PLUM archive of the PREVIOUS administration. That
archive says who held what between January 2021 and January 2025, so the claim
it supports is two snapshots joined, and it reached 29 positions. 5 U.S.C.
5312-5316 is the Executive Schedule itself -- current law, naming the office
rather than an incumbent -- and uscode.house.gov serves it.

Two properties are pinned here, and they are the two the project has been
burned on before.

The mirror the stdlib-only gate checks against must equal what the committed
sections actually print, or the gate vouches for a title Congress never wrote.
And the rate must never become evidence that the post EXISTS: on 2026-09-11 a
five-row salary table took 29 positions to `verificationStatus: verified`
because a second .gov URL in `sourceUrls` carried confidence past the
threshold. Nothing here writes that field, and a test says so.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from data_pipeline.exporter.build_graph import canonical_name_key, index_tree
from data_pipeline.verification import statutory_schedule as ss
from scripts.validate_published_graph import (
    EXECUTIVE_SCHEDULE_EFFECTIVE,
    EXECUTIVE_SCHEDULE_EFFECTIVE_TEXT,
    EXECUTIVE_SCHEDULE_FOOTNOTES,
    EXECUTIVE_SCHEDULE_RATES,
    EXECUTIVE_SCHEDULE_TABLE,
    US_CODE_EXECUTIVE_SCHEDULE,
    US_CODE_HOST,
    US_CODE_SECTIONS,
    schedule_pay_violations,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GRAPH = PROJECT_ROOT / "output" / "graph.json"
TODAY = "2026-09-18"


def label(node):
    return "{} ({})".format(node.get("name"), node.get("id"))


class StatuteParsingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schedule = ss.load_schedule()

    def test_all_five_sections_are_committed_and_their_digests_still_match(self) -> None:
        """load_schedule recomputes each digest from the bytes on disk. A
        fixture edited after the fetch would otherwise carry a digest that
        vouches for bytes nobody served."""
        self.assertEqual(sorted(self.schedule["sections"]), sorted(ss.SECTION_LEVELS))
        for section, block in self.schedule["sections"].items():
            with self.subTest(section=section):
                self.assertEqual(block["level"], ss.SECTION_LEVELS[section])
                self.assertTrue(block["positions"], f"§{section} parsed no positions at all")
                self.assertTrue(block["url"].startswith("https://uscode.house.gov/"))
                self.assertEqual(len(block["sha256"]), 64)

    def test_an_edited_section_is_refused_rather_than_rehashed(self) -> None:
        import shutil
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            for section in ss.SECTION_LEVELS:
                for suffix in ("", ".meta.json"):
                    shutil.copy(ss.FIXTURE_DIR / f"exec_schedule_{section}.html{suffix}",
                                target / f"exec_schedule_{section}.html{suffix}")
            edited = target / "exec_schedule_5312.html"
            edited.write_bytes(edited.read_bytes() + b"<!-- a level nobody served -->")
            with self.assertRaises(ss.Unreadable):
                ss.load_schedule(target)

    def test_the_statute_names_the_offices_it_is_famous_for(self) -> None:
        index = self.schedule["index"]
        for title, level in (
            ("Secretary of State", "I"),
            ("Attorney General", "I"),
            ("Secretary of Defense", "I"),
            ("Secretary of the Treasury", "I"),
            ("Deputy Secretary of Defense", "II"),
        ):
            with self.subTest(title=title):
                self.assertIn(canonical_name_key(title), index)
                self.assertEqual(index[canonical_name_key(title)]["level"], level)

    def test_a_title_the_code_places_at_two_levels_is_priced_for_nobody(self) -> None:
        """The Archivist of the United States appears in both §5314 and
        §5316. Picking one would be adjudicating an amendment, which this
        module has no basis to do."""
        self.assertIn("archivist of the united states", self.schedule["ambiguous"])
        self.assertNotIn("archivist of the united states", self.schedule["index"])

    def test_a_heading_is_never_read_as_a_position(self) -> None:
        for block in self.schedule["sections"].values():
            for position in block["positions"]:
                with self.subTest(title=position["title"]):
                    self.assertFalse(position["title"].lower().startswith("level "))


class MatchingTests(unittest.TestCase):
    """Equality of the canonical key, never containment and never a fold."""

    def setUp(self) -> None:
        self.schedule = ss.load_schedule()

    def test_a_longer_title_is_never_priced_from_a_shorter_one(self) -> None:
        index = self.schedule["index"]
        secretary = index[canonical_name_key("Secretary of the Army")]
        under = index[canonical_name_key("Under Secretary of the Army")]
        self.assertNotEqual(secretary["level"], under["level"])
        node_map = {
            "a": {"id": "a", "name": "Under Secretary of the Army", "type": "Position"},
        }
        matched = ss.match_positions(node_map, self.schedule)["matched"]
        self.assertEqual(matched["a"]["level"], under["level"],
                         "a containment test would have priced the Under Secretary as the Secretary")

    def test_a_statutory_title_reaching_two_nodes_prices_neither(self) -> None:
        node_map = {
            "a": {"id": "a", "name": "Attorney General", "type": "Position"},
            "b": {"id": "b", "name": "Attorney General", "type": "Position"},
        }
        result = ss.match_positions(node_map, self.schedule)
        self.assertEqual(result["matched"], {})
        self.assertEqual(sorted(result["refusals"]["statutory_title_matches_several_nodes"]), ["a", "b"])

    def test_an_organisation_is_never_matched(self) -> None:
        node_map = {"a": {"id": "a", "name": "Attorney General", "type": "Office"}}
        self.assertEqual(ss.match_positions(node_map, self.schedule)["matched"], {})

    def test_a_title_the_statute_states_several_of_prices_none(self) -> None:
        """"Assistant Secretaries of Commerce (11)" is eleven posts sharing one
        level. This graph's node is one of them or none of them, and the
        statute does not say which."""
        index = self.schedule["index"]
        many = [p for p in index.values() if p["statedPosts"] != 1]
        self.assertTrue(many, "no multi-post statutory titles were parsed at all")
        sample = many[0]
        node_map = {"a": {"id": "a", "name": sample["title"], "type": "Position"}}
        result = ss.match_positions(node_map, self.schedule)
        self.assertEqual(result["matched"], {})
        self.assertIn("statute_states_several_posts_at_this_title", result["refusals"])


class MirrorTests(unittest.TestCase):
    """The gate is stdlib-only and cannot parse the sections; the mirror is
    how it can tell §5312's Secretary of Agriculture from §5313's Deputy. A
    hand-kept copy that drifts is worse than none, so it is pinned here."""

    def test_every_mirrored_entry_is_what_the_code_actually_prints(self) -> None:
        schedule = ss.load_schedule()
        by_key = {p["key"]: p for p in schedule["index"].values()}
        for node_id, (title, level, section, scoped) in sorted(US_CODE_EXECUTIVE_SCHEDULE.items()):
            with self.subTest(node=node_id):
                position = by_key.get(canonical_name_key(title))
                self.assertIsNotNone(position, f"the Code does not print {title!r}")
                self.assertEqual(position["title"], title)
                self.assertEqual(position["level"], level)
                self.assertEqual(position["section"], section)
                self.assertIn(section, US_CODE_SECTIONS)
                if scoped is not None:
                    self.assertNotEqual(canonical_name_key(title), canonical_name_key(scoped),
                                        "a scoped entry names an office inside a body, not the body")

    @unittest.skipUnless(GRAPH.exists(), "no published graph")
    def test_every_scoped_entry_still_sits_under_the_body_the_code_named(self) -> None:
        """The scoped route identifies a node by its name AND its parent --
        "General Counsel" is the name of 84 nodes here, and only the body it
        sits under says which one the Code meant."""
        node_map, _ = index_tree(json.loads(GRAPH.read_text(encoding="utf-8")))
        scoped = {k: v for k, v in US_CODE_EXECUTIVE_SCHEDULE.items() if v[3] is not None}
        self.assertTrue(scoped, "no scoped entries at all")
        parents = {}
        stack = [(json.loads(GRAPH.read_text(encoding="utf-8")), None)]
        while stack:
            current, parent = stack.pop()
            parents[str(current.get("id") or "")] = str((parent or {}).get("id") or "")
            for child in current.get("children") or []:
                stack.append((child, current))
        for node_id, (_, _, _, org_id) in sorted(scoped.items()):
            node = node_map.get(node_id)
            if node is None:
                continue
            with self.subTest(node=node_id):
                self.assertEqual(parents.get(node_id), org_id)
                self.assertEqual(node["positionSchedulePay"].get("scopedOrganisationId"), org_id)

    @unittest.skipUnless(GRAPH.exists(), "no published graph")
    def test_the_mirror_covers_exactly_the_published_nodes(self) -> None:
        node_map, _ = index_tree(json.loads(GRAPH.read_text(encoding="utf-8")))
        published = {i for i, n in node_map.items() if isinstance(n.get("positionSchedulePay"), dict)}
        self.assertEqual(published, set(US_CODE_EXECUTIVE_SCHEDULE),
                         "a node carries a schedule rate the gate has no mirror for, or the reverse")

    @unittest.skipUnless(GRAPH.exists(), "no published graph")
    def test_fifteen_nodes_share_one_figure_which_is_why_the_mirror_is_keyed_by_id(self) -> None:
        node_map, _ = index_tree(json.loads(GRAPH.read_text(encoding="utf-8")))
        level_one = [n for n in node_map.values()
                     if isinstance(n.get("positionSchedulePay"), dict)
                     and n["positionSchedulePay"].get("payLevel") == "I"]
        self.assertGreaterEqual(len(level_one), 10)
        self.assertEqual({n["positionSchedulePay"]["amount"] for n in level_one},
                         {EXECUTIVE_SCHEDULE_RATES["I"]})


def good_pay(node_id):
    title, level, section, scoped = US_CODE_EXECUTIVE_SCHEDULE[node_id]
    return {
        "scopedOffice": None, "scopedOrganisation": None, "scopedOrganisationId": None,
        "source": ss.SOURCE, "method": ss.METHOD,
        "payLevel": level, "citation": "5 U.S.C. §{}".format(section),
        "statutoryTitle": title,
        "statuteUrl": "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title5-section{}&num=0&edition=prelim".format(section),
        "statuteCheckedAt": "2026-09-18T20:34:00Z",
        "amount": EXECUTIVE_SCHEDULE_RATES[level],
        "rateText": "${:,.0f}".format(EXECUTIVE_SCHEDULE_RATES[level]),
        "table": EXECUTIVE_SCHEDULE_TABLE,
        "effectiveText": EXECUTIVE_SCHEDULE_EFFECTIVE_TEXT,
        "effective": EXECUTIVE_SCHEDULE_EFFECTIVE,
        "fiscalYear": 2026, "costBasis": "basic_pay", "scopeMatch": "proxy",
        "financialEvidenceStatus": "partial",
        "amountScope": "Level {}".format(level),
        "quote": "Level {}  ${:,.0f}".format(level, EXECUTIVE_SCHEDULE_RATES[level]),
        "footnotes": list(EXECUTIVE_SCHEDULE_FOOTNOTES),
        "url": "https://www.opm.gov/policy-data-oversight/pay-leave/salaries-wages/salary-tables/26Tables/exec/html/EX.aspx",
        "checkedAt": "2026-09-11T00:00:00Z",
    }


class GateTests(unittest.TestCase):
    NODE_ID = "exec-dept-va-secretary-of-department-of-veterans-affairs-va"

    def setUp(self) -> None:
        self.assertIn(self.NODE_ID, US_CODE_EXECUTIVE_SCHEDULE)
        title, _, _, _ = US_CODE_EXECUTIVE_SCHEDULE[self.NODE_ID]
        self.node = {"id": self.NODE_ID, "name": title, "type": "Position"}

    def test_a_true_record_passes(self) -> None:
        self.assertEqual(schedule_pay_violations(self.node, good_pay(self.NODE_ID), TODAY, label), [])

    def test_each_way_it_can_be_faked_is_refused(self) -> None:
        cases = {
            # The figure moved to another Level I post: correct rate, correct
            # citation, real statutory title, wrong office.
            "a record swapped onto another node": (
                {"id": "exec-dept-ed-secretary-of-department-of-education", "name": "Secretary of Veterans Affairs", "type": "Position"},
                good_pay(self.NODE_ID)),
            "a node the Code does not name": (
                {"id": "made-up-node", "name": "Secretary of Veterans Affairs", "type": "Position"},
                good_pay(self.NODE_ID)),
            "a title the Code does not print": (None, {**good_pay(self.NODE_ID), "statutoryTitle": "Secretary of Justice"}),
            "a level the Code does not set for it": (None, {**good_pay(self.NODE_ID), "payLevel": "III"}),
            "a citation to the wrong section": (None, {**good_pay(self.NODE_ID), "citation": "5 U.S.C. §5316"}),
            "a figure the table does not print": (None, {**good_pay(self.NODE_ID), "amount": 300000.0}),
            "printed text that disagrees with the figure": (None, {**good_pay(self.NODE_ID), "rateText": "$999,999"}),
            "a rate printed as being for another level": (None, {**good_pay(self.NODE_ID), "amountScope": "Level V"}),
            "a fabricated footnote": (None, {**good_pay(self.NODE_ID), "footnotes": ["No pay freeze applies."]}),
            "no footnote at all": (None, {**good_pay(self.NODE_ID), "footnotes": []}),
            "a statute link to somewhere else": (None, {**good_pay(self.NODE_ID), "statuteUrl": "https://example.gov/x"}),
            "a retrieval date in the future": (None, {**good_pay(self.NODE_ID), "statuteCheckedAt": "2099-01-01"}),
            "a claim of exact scope": (None, {**good_pay(self.NODE_ID), "scopeMatch": "exact"}),
            "a claim of verified evidence": (None, {**good_pay(self.NODE_ID), "financialEvidenceStatus": "verified"}),
            "filed as something other than basic pay": (None, {**good_pay(self.NODE_ID), "costBasis": "net_outlays"}),
            "on an organisation": (
                {"id": self.NODE_ID, "name": "Secretary of Veterans Affairs", "type": "Cabinet Department"},
                good_pay(self.NODE_ID)),
            "on a node standing for several posts": (
                {"id": self.NODE_ID, "name": "Secretary of Veterans Affairs", "type": "Position", "representsPosts": 4},
                good_pay(self.NODE_ID)),
            "renamed since the level was looked up": (
                {"id": self.NODE_ID, "name": "Secretary of Something Else", "type": "Position"},
                good_pay(self.NODE_ID)),
            # The 2026-09-11 failure, in the shape it would take here.
            "used as evidence that the post exists": (
                {"id": self.NODE_ID, "name": "Secretary of Veterans Affairs", "type": "Position",
                 "verificationMethod": ss.METHOD}, good_pay(self.NODE_ID)),
            "used as evidence of where it sits": (
                {"id": self.NODE_ID, "name": "Secretary of Veterans Affairs", "type": "Position",
                 "placementMethod": ss.METHOD}, good_pay(self.NODE_ID)),
            "beside a measured cost": (
                {"id": self.NODE_ID, "name": "Secretary of Veterans Affairs", "type": "Position",
                 "cost_status": "official"}, good_pay(self.NODE_ID)),
            "not a record at all": (None, "$253,100"),
        }
        for name, (node, pay) in cases.items():
            with self.subTest(case=name):
                self.assertTrue(schedule_pay_violations(node or self.node, pay, TODAY, label),
                                f"{name} was accepted")


class ScopedGateTests(unittest.TestCase):
    """The scoped route identifies a node by its NAME and its PARENT.

    "General Counsel" is the name of 84 nodes in this graph, so the body it
    sits under is not decoration -- it is half of what says which General
    Counsel the Code meant. Every case below keeps a correct figure, a real
    statutory title and a correct citation, and changes only the thing that
    identifies the office.
    """

    def setUp(self) -> None:
        scoped = {k: v for k, v in US_CODE_EXECUTIVE_SCHEDULE.items() if v[3] is not None}
        self.assertTrue(scoped, "no scoped entries to test")
        self.node_id = sorted(scoped)[0]
        self.title, self.level, self.section, self.org = US_CODE_EXECUTIVE_SCHEDULE[self.node_id]
        # The office half is whatever the Code's title carries beyond the body.
        self.office = None
        for separator in ss.SCOPE_SEPARATORS:
            if separator in self.title:
                self.office = self.title.partition(separator)[0]
                break
        self.assertIsNotNone(self.office)
        self.node = {"id": self.node_id, "name": self.office, "type": "Position"}

    def _pay(self, **overrides):
        pay = good_pay(self.node_id)
        pay.update({"scopedOffice": self.office, "scopedOrganisation": self.org,
                    "scopedOrganisationId": self.org})
        pay.update(overrides)
        return pay

    def test_a_true_scoped_record_passes(self) -> None:
        self.assertEqual(
            schedule_pay_violations(self.node, self._pay(), TODAY, label, tree_parent=self.org), [])

    def test_the_parent_is_checked_against_the_tree_not_a_stamped_field(self) -> None:
        """parentId is stamped on the exported node list only, so a check that
        read it would pass vacuously for most of the graph."""
        violations = schedule_pay_violations(
            self.node, self._pay(), TODAY, label, tree_parent="some-other-organisation")
        self.assertTrue(violations)
        self.assertIn("half of what identified it", " ".join(violations))

    def test_a_missing_parent_is_a_violation_rather_than_a_pass(self) -> None:
        self.assertTrue(schedule_pay_violations(self.node, self._pay(), TODAY, label, tree_parent=None))

    def test_each_way_a_scoped_record_can_be_faked_is_refused(self) -> None:
        cases = {
            "the record claims a different organisation": self._pay(scopedOrganisationId="exec-dept-doe"),
            "the office half is dropped": self._pay(scopedOffice=""),
            "the office half is not part of the statutory title": self._pay(scopedOffice="Chief of Staff"),
            "the node was renamed to another office": None,
        }
        for name, pay in cases.items():
            with self.subTest(case=name):
                node = self.node
                if pay is None:
                    node = {"id": self.node_id, "name": "Something Else Entirely", "type": "Position"}
                    pay = self._pay()
                self.assertTrue(
                    schedule_pay_violations(node, pay, TODAY, label, tree_parent=self.org),
                    f"{name} was accepted")

    def test_a_whole_name_match_may_not_claim_a_scope(self) -> None:
        """The two routes are exclusive: a node whose own name is the statutory
        title needs no organisation to identify it, and claiming one would
        present a single reading as two."""
        direct = sorted(k for k, v in US_CODE_EXECUTIVE_SCHEDULE.items() if v[3] is None)
        self.assertTrue(direct)
        node_id = direct[0]
        title = US_CODE_EXECUTIVE_SCHEDULE[node_id][0]
        node = {"id": node_id, "name": title, "type": "Position"}
        pay = good_pay(node_id)
        pay.update({"scopedOffice": title, "scopedOrganisationId": "exec-dept-doe"})
        self.assertTrue(schedule_pay_violations(node, pay, TODAY, label))


class ItIsNotEvidenceThePostExistsTests(unittest.TestCase):
    @unittest.skipUnless(GRAPH.exists(), "no published graph")
    def test_no_priced_node_gained_a_source_url_from_the_statute(self) -> None:
        node_map, _ = index_tree(json.loads(GRAPH.read_text(encoding="utf-8")))
        for node_id in US_CODE_EXECUTIVE_SCHEDULE:
            node = node_map.get(node_id)
            if node is None:
                continue
            with self.subTest(node=node_id):
                for url in node.get("sourceUrls") or []:
                    self.assertNotIn(US_CODE_HOST, url,
                                     "the Code's URL reached sourceUrls, where it counts toward confidence")
                self.assertNotEqual(node.get("verificationMethod"), ss.METHOD)
                self.assertNotEqual(node.get("placementMethod"), ss.METHOD)

    @unittest.skipUnless(GRAPH.exists(), "no published graph")
    def test_no_priced_node_carries_the_figure_as_a_cost(self) -> None:
        node_map, _ = index_tree(json.loads(GRAPH.read_text(encoding="utf-8")))
        for node_id in US_CODE_EXECUTIVE_SCHEDULE:
            node = node_map.get(node_id)
            if node is None:
                continue
            with self.subTest(node=node_id):
                self.assertNotIn(str(node.get("cost_status") or ""), ("official", "root_total", "scaled_official"))
                self.assertNotEqual(node.get("resolved_total_amount"), node["positionSchedulePay"]["amount"])


if __name__ == "__main__":
    unittest.main()
