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
import re
import unittest
import unittest.mock
from datetime import date
from pathlib import Path

from data_pipeline.exporter.build_graph import canonical_name_key, index_tree
from data_pipeline.exporter.build_graph import annotate_stated_counts
from data_pipeline.verification import statutory_schedule as ss
from data_pipeline.verification.pay_tables import holders_for
from scripts.validate_published_graph import (
    EXECUTIVE_SCHEDULE_EFFECTIVE,
    EXECUTIVE_SCHEDULE_EFFECTIVE_TEXT,
    EXECUTIVE_SCHEDULE_FOOTNOTES,
    EXECUTIVE_SCHEDULE_RATES,
    EXECUTIVE_SCHEDULE_TABLE,
    US_CODE_BASIS_FIXTURE_DIR,
    US_CODE_COUNTED_CLASSES,
    US_CODE_EXECUTIVE_SCHEDULE,
    US_CODE_HOST,
    US_CODE_REVIEWED_IDENTIFICATIONS,
    US_CODE_REVIEWED_METHOD,
    US_CODE_SCHEDULE_METHOD,
    US_CODE_SCHEDULE_SCOPED_METHOD,
    US_CODE_SECTIONS,
    fixture_digest,
    reviewed_schedule_violations,
    schedule_pay_violations,
    us_code_url_names_section,
    uscode_operative_text,
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


# --------------------------------------------------------------------------
# 2026-10-06: a footnote mark standing where the full stop should be. Four
# footnote-reference elements sit in the five committed sections, and the
# parser used to read each as a digit -- "...Human Services 1" failed the
# full-stop rule and three real titles were invisible to the index. The Code's
# own footnotes on two of them read "So in original. Probably should be
# followed by a period." A CLOSING mark is now stripped and closes the item;
# a mark anywhere else is kept as printed, because a reviewed row keys on it.


class FootnoteMarkTests(unittest.TestCase):
    FDA = "Commissioner of Food and Drugs, Department of Health and Human Services"
    EDUCATION = "Under Secretary of Education"
    PRINCIPAL_DEPUTY = "Principal Deputy Under Secretary of Defense for Acquisition, Technology, and Logistics"
    BLS = "The 2 Commissioner of Labor Statistics, Department of Labor"
    FOOTNOTE = "So in original. Probably should be followed by a period."
    MARK = '<sup><a href="#{section}_{n}_target" name="{section}_{n}">{n}</a></sup>'

    @classmethod
    def setUpClass(cls) -> None:
        cls.schedule = ss.load_schedule()
        cls.raw = {s: (US_CODE_BASIS_FIXTURE_DIR / f"exec_schedule_{s}.html").read_text(encoding="utf-8")
                   for s in ss.SECTION_LEVELS}

    def test_the_marks_are_what_the_pages_print(self) -> None:
        """Four marks in all, each the same element: an anchor inside a <sup>.
        Two stand where the full stop should be, one follows it, one sits
        mid-title. Pinned so a re-fetched section that prints them otherwise
        fails here rather than silently changing what the parser sees."""
        self.assertIn("Human Services&nbsp;" + self.MARK.format(section="5315", n="1") + "\n</p>", self.raw["5315"])
        self.assertIn("Under Secretary of Education&nbsp;" + self.MARK.format(section="5314", n="2") + "\n</p>", self.raw["5314"])
        self.assertIn("Technology, and Logistics." + self.MARK.format(section="5314", n="1") + "\n</p>", self.raw["5314"])
        self.assertIn("The&nbsp;" + self.MARK.format(section="5315", n="2") + " Commissioner of Labor Statistics, Department of Labor.</p>",
                      self.raw["5315"])
        self.assertEqual(sum(raw.count('<sup><a href="#') for raw in self.raw.values()), 4)
        self.assertEqual(self.raw["5314"].count(self.FOOTNOTE), 1)
        self.assertEqual(self.raw["5315"].count(self.FOOTNOTE), 1)
        # Read as text, the digit survives and the full-stop rule refuses the item.
        for section, needle in (("5315", "Human Services&nbsp;<sup>"), ("5314", "Education&nbsp;<sup>"),
                                ("5314", "Logistics.<sup>")):
            start = self.raw[section].rfind('<p class="statutory-body', 0, self.raw[section].find(needle))
            end = self.raw[section].find("</p>", start)
            fragment = ss._BODY.findall(self.raw[section][start:end + 4])[0]
            with self.subTest(needle=needle):
                self.assertFalse(ss._text_of(fragment).endswith("."))
                body, closed = ss._strip_trailing_footnote_reference(fragment)
                self.assertTrue(closed)
                self.assertNotIn("<sup>", body)

    def test_the_three_titles_the_code_closes_with_a_footnote_mark_are_indexed(self) -> None:
        for title, level, section in ((self.FDA, "IV", "5315"), (self.EDUCATION, "III", "5314"),
                                      (self.PRINCIPAL_DEPUTY, "III", "5314")):
            with self.subTest(title=title):
                position = self.schedule["index"].get(canonical_name_key(title))
                self.assertIsNotNone(position, f"{title!r} is not indexed")
                self.assertEqual((position["title"], position["level"], position["section"], position["statedPosts"]),
                                 (title, level, section, 1))
                self.assertNotIn(canonical_name_key(title), self.schedule["ambiguous"])

    def test_a_mark_after_a_full_stop_yields_the_title_without_the_digit(self) -> None:
        self.assertIn(canonical_name_key(self.PRINCIPAL_DEPUTY), self.schedule["index"])
        titles = [p["title"] for b in self.schedule["sections"].values() for p in b["positions"]]
        self.assertNotIn(self.PRINCIPAL_DEPUTY + "1", titles)
        self.assertNotIn(self.PRINCIPAL_DEPUTY + ".1", titles)
        # No indexed title ends in a bare digit: the mark is never read as text.
        self.assertEqual([t for t in titles if re.search(r"\s\d+$", t)], [])

    def test_a_mark_in_the_middle_of_a_title_is_kept_as_printed(self) -> None:
        """The Bureau of Labor Statistics' row keys on the printed words; a
        rule that dropped every mark would have felled it (measured: 236 -> 235
        records, `reviewed_row_title_not_printed_by_the_code`)."""
        position = self.schedule["index"].get(canonical_name_key(self.BLS))
        self.assertIsNotNone(position)
        self.assertEqual((position["title"], position["key"], position["level"]),
                         (self.BLS, "2 commissioner of labor statistics department of labor", "IV"))
        self.assertNotIn(canonical_name_key("The Commissioner of Labor Statistics, Department of Labor"), self.schedule["index"])
        self.assertEqual(ss.REVIEWED_TITLE_ROWS["exec-dept-dol-bls-commissioner-bls"]["statutoryTitle"], self.BLS)
        self.assertEqual(US_CODE_REVIEWED_IDENTIFICATIONS["exec-dept-dol-bls-commissioner-bls"][1], self.BLS)
        start = self.raw["5315"].find('<p class="statutory-body-1em">The&nbsp;<sup>')
        fragment = ss._BODY.findall(self.raw["5315"][start:self.raw["5315"].find("</p>", start) + 4])[0]
        body, closed = ss._strip_trailing_footnote_reference(fragment)
        self.assertEqual((body, closed), (fragment, False))

    def test_skipped_fell_from_nine_to_six_and_the_proviso_stays_skipped(self) -> None:
        """Measured on 2026-10-06: 415 positions / 413 titles / 9 skipped
        before, 418 / 416 / 6 after, 1 ambiguous either way. The 213-character
        Chief Information Officer proviso in §5315 is still over
        MAX_TITLE_CHARS and still skipped; that rule did not move."""
        skipped = {s: b["skipped"] for s, b in self.schedule["sections"].items()}
        self.assertEqual({s: len(v) for s, v in skipped.items()}, {"5312": 0, "5313": 0, "5314": 2, "5315": 4, "5316": 0})
        self.assertEqual((self.schedule["positions"], len(self.schedule["index"]), len(self.schedule["ambiguous"])),
                         (418, 416, 1))
        flat = [s for v in skipped.values() for s in v]
        for title in (self.FDA, self.EDUCATION, self.PRINCIPAL_DEPUTY):
            self.assertFalse(any(s.startswith(title) for s in flat), title)
        self.assertTrue(any(s.startswith("Chief Information Officer, Department of Defense (unless") for s in skipped["5315"]))
        self.assertGreater(len(DefenseComptrollerRowTests.CIO_TITLE), ss.MAX_TITLE_CHARS)
        self.assertEqual(ss.MAX_TITLE_CHARS, 140)

    def test_the_rule_is_the_element_and_nothing_looser(self) -> None:
        """On synthetic paragraphs: a closing element closes the item, with or
        without a full stop before it; a mid-text element is kept as text; a
        bare trailing digit, a <sup> that is not the Code's element, and a
        closing element on an over-long item or a heading each change nothing."""
        mark = self.MARK.format(section="5315", n="7")
        html = (
            '<p class="statutory-body">Level IV of the Executive Schedule applies to&nbsp;' + mark + '\n</p>'
            '<p class="statutory-body-1em">Director of Example Affairs&nbsp;' + mark + '\n</p>'
            '<p class="statutory-body-1em">Deputy Director of Example Affairs.' + mark + '</p>'
            '<p class="statutory-body-1em">The&nbsp;' + mark + ' Keeper of Example Records.</p>'
            '<p class="statutory-body-1em">Assistant Keeper of Example Records 7</p>'
            '<p class="statutory-body-1em">Second Assistant Keeper of Example Records<sup>7</sup></p>'
            '<p class="statutory-body-1em">Third Assistant Keeper of Example Records<sup><a href="#note7">7</a></sup></p>'
            '<p class="statutory-body-1em">' + ("Very " * 30) + 'Long Office of Example Affairs&nbsp;' + mark + '</p>'
            '<p class="statutory-body-1em">Keeper of Nothing</p>'
        )
        parsed = ss.parse_section(html, section="5315")
        self.assertEqual([p["title"] for p in parsed["positions"]],
                         ["Director of Example Affairs", "Deputy Director of Example Affairs", "The 7 Keeper of Example Records"])
        self.assertEqual(len(parsed["skipped"]), 5)
        self.assertTrue(parsed["skipped"][0].startswith("Assistant Keeper of Example Records 7"))
        self.assertTrue(parsed["skipped"][1].startswith("Second Assistant Keeper of Example Records7"))
        self.assertTrue(parsed["skipped"][2].startswith("Third Assistant Keeper of Example Records7"))
        self.assertTrue(parsed["skipped"][3].startswith("Very Very"))
        self.assertEqual(parsed["skipped"][4], "Keeper of Nothing")

    def test_the_three_titles_reach_no_node_on_their_own(self) -> None:
        """An indexed title reaches a node only by key equality or through a
        reviewed row keyed by id; measured on the real base graph, the three
        titles the mark hid reach nothing by the whole-name or scoped route,
        and the derived records are the same 236 as before plus the FDA
        Commissioner's reviewed row."""
        from data_pipeline.exporter.build_graph import DEFAULT_BASE_GRAPH, load_base_graph

        node_map, _ = index_tree(load_base_graph(DEFAULT_BASE_GRAPH))
        whole = ss.match_positions(node_map, self.schedule)["matched"]
        scoped = ss.match_scoped_positions(node_map, self.schedule, already_matched=whole)
        for title in (self.FDA, self.EDUCATION, self.PRINCIPAL_DEPUTY):
            key = canonical_name_key(title)
            with self.subTest(title=title):
                self.assertEqual([n for n, p in whole.items() if p["key"] == key], [])
                self.assertEqual([n for n, p in scoped["matched"].items() if p["key"] == key], [])
        self.assertIn(self.FDA, scoped["refusals"]["no_such_post_directly_under_that_organisation"])


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
        # Since 2026-09-30 the fourth route prices the reviewed members of a
        # COUNTED class; those are mirrored by class rather than by row.
        counted = {i for spec in US_CODE_COUNTED_CLASSES.values() for i in spec["members"]}
        counted_published = {i for i in published
                             if isinstance(node_map[i]["positionSchedulePay"].get("countedClass"), dict)}
        self.assertTrue(counted_published <= counted, "a counted-class member the table does not list")
        self.assertEqual(published - counted_published,
                         set(US_CODE_EXECUTIVE_SCHEDULE) | set(US_CODE_REVIEWED_IDENTIFICATIONS),
                         "a node carries a schedule rate the gate has no mirror for, or the reverse")
        self.assertFalse(set(US_CODE_EXECUTIVE_SCHEDULE) & set(US_CODE_REVIEWED_IDENTIFICATIONS),
                         "a node is in both mirrors; the routes are exclusive")
        self.assertFalse(counted & (set(US_CODE_EXECUTIVE_SCHEDULE) | set(US_CODE_REVIEWED_IDENTIFICATIONS)),
                         "a counted-class member is also mirrored by row; the routes are exclusive")

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
                    "scopedOrganisationId": self.org, "method": ss.METHOD_SCOPED})
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
        for node_id in list(US_CODE_EXECUTIVE_SCHEDULE) + list(US_CODE_REVIEWED_IDENTIFICATIONS):
            node = node_map.get(node_id)
            if node is None:
                continue
            with self.subTest(node=node_id):
                for url in node.get("sourceUrls") or []:
                    self.assertNotIn(US_CODE_HOST, url,
                                     "the Code's URL reached sourceUrls, where it counts toward confidence")
                self.assertNotEqual(node.get("verificationMethod"), ss.METHOD)
                self.assertNotEqual(node.get("placementMethod"), ss.METHOD)
                self.assertNotEqual(node.get("verificationMethod"), ss.METHOD_REVIEWED)
                self.assertNotEqual(node.get("placementMethod"), ss.METHOD_REVIEWED)

    @unittest.skipUnless(GRAPH.exists(), "no published graph")
    def test_no_priced_node_carries_the_figure_as_a_cost(self) -> None:
        node_map, _ = index_tree(json.loads(GRAPH.read_text(encoding="utf-8")))
        for node_id in list(US_CODE_EXECUTIVE_SCHEDULE) + list(US_CODE_REVIEWED_IDENTIFICATIONS):
            node = node_map.get(node_id)
            if node is None:
                continue
            with self.subTest(node=node_id):
                self.assertNotIn(str(node.get("cost_status") or ""), ("official", "root_total", "scaled_official"))
                self.assertNotEqual(node.get("resolved_total_amount"), node["positionSchedulePay"]["amount"])


# ---------------------------------------------------------------------------
# The third route: a reviewed identification backed by a second statute


def reviewed_node(node_id):
    """The node a reviewed row was written against -- with the multiplicity
    the exporter would stamp on it, read from the name by the exporter's own
    `annotate_stated_counts`, because a class-title row prices a bench."""
    node_name = US_CODE_REVIEWED_IDENTIFICATIONS[node_id][0]
    node = {"id": node_id, "name": node_name, "type": "Position"}
    probe = {"id": "root", "name": "Root", "type": "Foundation", "children": [dict(node)]}
    annotate_stated_counts(probe)
    if probe["children"][0].get("representsPosts"):
        node["representsPosts"] = probe["children"][0]["representsPosts"]
    return node


def class_rows():
    return sorted(node_id for node_id, row in US_CODE_REVIEWED_IDENTIFICATIONS.items() if row[8])


def single_rows():
    return sorted(node_id for node_id, row in US_CODE_REVIEWED_IDENTIFICATIONS.items() if not row[8])


fed_node = reviewed_node  # the first three rows were the Federal Reserve's


def basis_url_for(citation):
    """The uscode.house.gov granule a citation names -- derived, so a row
    citing 47 U.S.C. 154 is not tested against the Fed's section."""
    title, section = citation.split(" U.S.C. ")
    return ("https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title{}-section{}"
            "&num=0&edition=prelim".format(title, section))


def good_reviewed_pay(node_id):
    node_name, title, level, section, citation, fixture, quote, basis, class_title = US_CODE_REVIEWED_IDENTIFICATIONS[node_id]
    row = ss.REVIEWED_TITLE_ROWS[node_id]
    pay = {
        "scopedOffice": None, "scopedOrganisation": None, "scopedOrganisationId": None,
        "source": ss.SOURCE, "method": ss.METHOD_REVIEWED,
        "identification": {
            "nodeName": node_name,
            "basis": basis,
            "basisCitation": citation,
            "basisQuote": quote,
            "basisUrl": basis_url_for(citation),
            "basisSha256": fixture_digest(US_CODE_BASIS_FIXTURE_DIR / fixture),
            "basisCheckedAt": "2026-09-23T19:48:44Z",
        },
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
    if class_title:
        # What the derive step stamps and what the sweep adds on the bench.
        pay["classTitle"] = True
        pay["holders"] = holders_for(reviewed_node(node_id)["representsPosts"])
    return pay


# The reviewed rows' basis sections were fetched on 2026-09-23 (the Fed's) and
# 2026-09-27 (the six that followed); the gate's own clock is the real date,
# and a record can never be older than the fetch it rests on.
REVIEWED_TODAY = date.today().isoformat()


class ReviewedMirrorTests(unittest.TestCase):
    """The reviewed rows are the one place a node is priced from a title
    that is NOT its name, so a hand-kept copy that drifts from the module's
    table would let the gate vouch for an identification nobody reviewed."""

    def test_the_gate_mirror_equals_the_module_rows(self) -> None:
        self.assertEqual(set(US_CODE_REVIEWED_IDENTIFICATIONS), set(ss.REVIEWED_TITLE_ROWS))
        for node_id, row in ss.REVIEWED_TITLE_ROWS.items():
            with self.subTest(node=node_id):
                node_name, title, level, section, citation, fixture, quote, basis, class_title = US_CODE_REVIEWED_IDENTIFICATIONS[node_id]
                self.assertEqual(row["nodeName"], node_name)
                self.assertEqual(row.get("classTitle") is True, class_title)
                # A class-title row cites the Code's "Members, ..." form and
                # nothing else, and prices a node whose own name states a
                # bench; a single post may be identified as a member too (the
                # Vice Chairs), which is why the first check is one-way.
                if class_title:
                    self.assertTrue(ss.is_class_title(title))
                self.assertEqual(ss.states_a_multiplicity(node_name), class_title)
                self.assertEqual(row["basis"], basis)
                self.assertEqual(row["statutoryTitle"], title)
                self.assertEqual(row["basisCitation"], citation)
                self.assertEqual(row["basisFixture"], fixture)
                self.assertEqual(row["basisQuote"], quote)
                self.assertTrue(row["basis"].strip())
        self.assertEqual(US_CODE_REVIEWED_METHOD, ss.METHOD_REVIEWED)
        self.assertEqual(US_CODE_SCHEDULE_METHOD, ss.METHOD)
        self.assertEqual(US_CODE_SCHEDULE_SCOPED_METHOD, ss.METHOD_SCOPED)

    def test_every_reviewed_title_is_printed_by_the_code_at_that_level(self) -> None:
        schedule = ss.load_schedule()
        for node_id, (node_name, title, level, section, *_rest) in sorted(US_CODE_REVIEWED_IDENTIFICATIONS.items()):
            with self.subTest(node=node_id):
                position = schedule["index"].get(canonical_name_key(title))
                self.assertIsNotNone(position, f"the Code does not print {title!r}")
                self.assertEqual(position["title"], title)
                self.assertEqual(position["level"], level)
                self.assertEqual(position["section"], section)
                # What makes this a reviewed row and not a whole-name match.
                self.assertNotEqual(canonical_name_key(node_name), canonical_name_key(title))

    def test_every_basis_quote_is_in_the_committed_sections_operative_text_by_both_readers(self) -> None:
        for node_id, (*_head, citation, fixture, quote, _basis, _class) in sorted(US_CODE_REVIEWED_IDENTIFICATIONS.items()):
            with self.subTest(node=node_id):
                path = US_CODE_BASIS_FIXTURE_DIR / fixture
                self.assertTrue(path.exists(), f"{fixture} is not committed")
                gate_text = uscode_operative_text(path)
                module = ss.load_basis_section(fixture)
                self.assertEqual(gate_text, module["operative"], "the two operative-text readers disagree")
                self.assertIn(quote, gate_text)
                self.assertEqual(module["sha256"], fixture_digest(path))
                for heading in ("Editorial Notes", "Statutory Notes", "Historical and Revision Notes"):
                    self.assertNotIn(heading, gate_text, "the cut left the publisher's notes on the law's side")

    def test_the_cut_is_load_bearing_on_the_real_page(self) -> None:
        """12 U.S.C. 242's page prints each designation sentence twice -- once
        as the law and once beneath it in the Amendments note -- so a reader
        that did not cut would accept a quote from either. The rule is worth
        having only because the notes really do carry such text."""
        import html as html_module
        import re

        raw = (US_CODE_BASIS_FIXTURE_DIR / "fed_12_usc_242.html").read_text(encoding="utf-8")
        flat = re.sub(r"\s+", " ", html_module.unescape(re.sub(r"<[^>]+>", " ", raw)))
        cut = flat.find("Editorial Notes")
        self.assertGreater(cut, 0)
        beneath = flat[cut:]
        self.assertTrue(any(row[6] in beneath for row in US_CODE_REVIEWED_IDENTIFICATIONS.values()),
                        "no basis sentence appears beneath the cut; the operative rule would be doing nothing here")

    def test_the_section_prints_no_salary_figure(self) -> None:
        """A research pass reported 12 U.S.C. 242 as printing '$203,500 per
        annum'. It prints no dollar figure at all; the rate comes from
        5 U.S.C. 5312/5313 joined to OPM's table, which is why the row is an
        identification and not a pay claim of its own."""
        text = uscode_operative_text(US_CODE_BASIS_FIXTURE_DIR / "fed_12_usc_242.html")
        self.assertNotIn("$", text)
        self.assertNotIn("203,500", text)

    @unittest.skipUnless(GRAPH.exists(), "no published graph")
    def test_the_benches_are_priced_from_their_class_title_for_each_holder(self) -> None:
        """Until 2026-09-27 'Governor (×4 members)' was deliberately left
        unpriced, because positionSchedulePay is incumbency-class and the
        sweep stripped it. The owner's decision: 'Members, Board of Governors'
        is the office every Governor holds, so the bench is priced from the
        class title and the block says it holds for each holder."""
        node_map, _ = index_tree(json.loads(GRAPH.read_text(encoding="utf-8")))
        self.assertIn("exec-regulatory-fed-governor-4-members", class_rows())
        for node_id in class_rows():
            with self.subTest(node=node_id):
                node = node_map[node_id]
                self.assertTrue(node.get("representsPosts"))
                pay = node.get("positionSchedulePay")
                self.assertIsInstance(pay, dict)
                self.assertIs(pay.get("classTitle"), True)
                self.assertTrue(pay["statutoryTitle"].startswith("Members, "))
                holders = pay.get("holders")
                self.assertIsInstance(holders, dict)
                self.assertIs(holders.get("appliesToEachHolder"), True)
                self.assertEqual(holders.get("text"), node["representsPosts"].get("text"))
                self.assertEqual(pay["verification"]["documents"], 3)
        for node_id in single_rows():
            with self.subTest(node=node_id):
                pay = node_map[node_id].get("positionSchedulePay")
                self.assertIsInstance(pay, dict)
                self.assertNotIn("classTitle", pay)
                self.assertNotIn("holders", pay)

    @unittest.skipUnless(GRAPH.exists(), "no published graph")
    def test_every_reviewed_post_is_published_under_the_reviewed_method(self) -> None:
        node_map, _ = index_tree(json.loads(GRAPH.read_text(encoding="utf-8")))
        for node_id, (node_name, title, level, *_rest) in sorted(US_CODE_REVIEWED_IDENTIFICATIONS.items()):
            with self.subTest(node=node_id):
                pay = node_map[node_id].get("positionSchedulePay")
                self.assertIsInstance(pay, dict)
                self.assertEqual(pay["method"], ss.METHOD_REVIEWED)
                self.assertEqual(pay["statutoryTitle"], title)
                self.assertEqual(pay["payLevel"], level)
                self.assertEqual(pay["identification"]["nodeName"], node_name)
                self.assertEqual(pay["financialEvidenceStatus"], "partial")
                self.assertEqual(pay["scopeMatch"], "proxy")
                self.assertEqual(schedule_pay_violations(node_map[node_id], pay, REVIEWED_TODAY, label), [])


class ReviewedMatchTests(unittest.TestCase):
    """`match_reviewed_rows` re-adjudicates every row on every run."""

    def setUp(self) -> None:
        self.schedule = ss.load_schedule()
        self.node_map = {
            "exec-regulatory-fed": {"id": "exec-regulatory-fed", "name": "Federal Reserve System", "type": "Agency"},
        }
        for node_id in ss.REVIEWED_TITLE_ROWS:
            self.node_map[node_id] = dict(fed_node(node_id), parentId="exec-regulatory-fed")

    def test_every_row_matches_and_carries_the_identification(self) -> None:
        result = ss.match_reviewed_rows(self.node_map, self.schedule)
        self.assertEqual(set(result["matched"]), set(ss.REVIEWED_TITLE_ROWS))
        self.assertEqual(result["refusals"], {})
        for node_id, entry in result["matched"].items():
            with self.subTest(node=node_id):
                row = ss.REVIEWED_TITLE_ROWS[node_id]
                self.assertEqual(entry["method"], ss.METHOD_REVIEWED)
                self.assertEqual(entry["title"], row["statutoryTitle"])
                ident = entry["identification"]
                self.assertEqual(ident["nodeName"], row["nodeName"])
                self.assertEqual(ident["basisCitation"], row["basisCitation"])
                self.assertEqual(ident["basisQuote"], row["basisQuote"])
                # The URL is the one the basis fixture's own fetch record
                # names -- the OLRC granule for most rows, GPO's link service
                # on govinfo for a section read while the OLRC host was under
                # maintenance (the OSTP Director's, 2026-10-05) -- and either
                # way it must address the section the citation names.
                meta = json.loads((US_CODE_BASIS_FIXTURE_DIR / (row["basisFixture"] + ".meta.json")).read_text(encoding="utf-8"))
                self.assertEqual(ident["basisUrl"], meta["url"])
                self.assertTrue(us_code_url_names_section(ident["basisUrl"], row["basisCitation"]), ident["basisUrl"])
                self.assertEqual(ident["basisSha256"], fixture_digest(US_CODE_BASIS_FIXTURE_DIR / row["basisFixture"]))
                self.assertTrue(ident["basisCheckedAt"])

    def test_a_renamed_node_is_refused(self) -> None:
        self.node_map["exec-regulatory-fed-chair-board-of-governors"]["name"] = "Chairman of the Board"
        result = ss.match_reviewed_rows(self.node_map, self.schedule)
        self.assertNotIn("exec-regulatory-fed-chair-board-of-governors", result["matched"])
        self.assertEqual(result["refusals"]["reviewed_row_node_renamed"], ["exec-regulatory-fed-chair-board-of-governors"])

    def test_a_node_that_is_not_a_post_is_refused(self) -> None:
        self.node_map["exec-regulatory-fed-chair-board-of-governors"]["type"] = "Office"
        result = ss.match_reviewed_rows(self.node_map, self.schedule)
        self.assertEqual(result["refusals"]["reviewed_row_names_a_non_post"], ["exec-regulatory-fed-chair-board-of-governors"])

    def test_a_missing_node_is_refused_not_invented(self) -> None:
        del self.node_map["exec-regulatory-fed-vice-chair-for-supervision"]
        result = ss.match_reviewed_rows(self.node_map, self.schedule)
        self.assertEqual(result["refusals"]["reviewed_row_names_no_node"], ["exec-regulatory-fed-vice-chair-for-supervision"])

    def test_a_class_title_row_needs_a_bench_and_a_bench_needs_a_class_title(self) -> None:
        """The two refusals that keep a class title where it belongs: a
        row marked classTitle on a node whose name states one post, and a
        plain row on a node whose name states several."""
        bench = "exec-regulatory-fcc-commissioner-4"
        single = "exec-regulatory-fcc-chair-fcc"
        self.node_map[bench]["name"] = "Commissioner"  # the (×4) dropped
        self.node_map[single]["name"] = "Chair, FCC (×2)"
        result = ss.match_reviewed_rows(self.node_map, self.schedule)
        self.assertEqual(result["refusals"]["reviewed_row_class_title_on_a_single_post"], [bench])
        self.assertEqual(result["refusals"]["reviewed_row_names_a_bench_without_a_class_title"], [single])
        self.assertNotIn(bench, result["matched"])
        self.assertNotIn(single, result["matched"])
        # The bench rows that were left alone carry the mark into the entry.
        for node_id in class_rows():
            if node_id != bench:
                self.assertIs(result["matched"][node_id].get("classTitle"), True)
        for node_id in single_rows():
            if node_id != single:
                self.assertNotIn("classTitle", result["matched"][node_id])

    def test_a_class_title_row_on_a_singular_statutory_title_is_refused(self) -> None:
        """Even with the (×4) in the name, a row may not call a singular
        title a class: the Code names one office and the node stands for N."""
        rows = ss.REVIEWED_TITLE_ROWS
        doctored = dict(rows)
        doctored["exec-regulatory-fcc-commissioner-4"] = dict(
            rows["exec-regulatory-fcc-commissioner-4"], statutoryTitle="Chairman, Federal Communications Commission")
        with unittest.mock.patch.object(ss, "REVIEWED_TITLE_ROWS", doctored):
            result = ss.match_reviewed_rows(self.node_map, self.schedule)
        self.assertEqual(result["refusals"]["reviewed_row_class_title_is_not_a_class_title"],
                         ["exec-regulatory-fcc-commissioner-4"])

    def test_a_node_another_route_already_priced_is_refused(self) -> None:
        result = ss.match_reviewed_rows(self.node_map, self.schedule,
                                        already_matched={"exec-regulatory-fed-chair-board-of-governors": {}})
        self.assertEqual(result["refusals"]["reviewed_row_node_already_matched"],
                         ["exec-regulatory-fed-chair-board-of-governors"])
        self.assertEqual(len(result["matched"]), len(ss.REVIEWED_TITLE_ROWS) - 1)

    FED_ROWS = frozenset(n for n, r in ss.REVIEWED_TITLE_ROWS.items() if r["basisFixture"] == "fed_12_usc_242.html")

    def _copy_basis_fixtures(self, tmp):
        """Every basis section the rows name, verbatim, so a test that
        doctors one fixture says something about that fixture alone."""
        for row in ss.REVIEWED_TITLE_ROWS.values():
            for name in (row["basisFixture"], row["basisFixture"] + ".meta.json"):
                (tmp / name).write_bytes((US_CODE_BASIS_FIXTURE_DIR / name).read_bytes())

    def _doctored_directory(self, transform):
        import hashlib
        import tempfile
        from pathlib import Path as _Path

        tmp = _Path(tempfile.mkdtemp())
        self._copy_basis_fixtures(tmp)
        # The five Executive Schedule sections are read from the real
        # directory; only the Fed's basis section is doctored.
        raw = (tmp / "fed_12_usc_242.html").read_text(encoding="utf-8")
        doctored = transform(raw)
        (tmp / "fed_12_usc_242.html").write_text(doctored, encoding="utf-8")
        meta = json.loads((tmp / "fed_12_usc_242.html.meta.json").read_text(encoding="utf-8"))
        meta["sha256"] = hashlib.sha256(doctored.encode("utf-8")).hexdigest()
        (tmp / "fed_12_usc_242.html.meta.json").write_text(json.dumps(meta), encoding="utf-8")
        return tmp

    def test_a_quote_the_section_prints_only_in_its_notes_is_refused(self) -> None:
        """The CAVC lesson: uscode.house.gov prints prior text beneath the law.
        Move the Chairman's sentence out of the operative text and leave it in
        the Amendments note, re-sign the digest, and the row must fall."""
        quote = ss.REVIEWED_TITLE_ROWS["exec-regulatory-fed-chair-board-of-governors"]["basisQuote"]

        def transform(raw):
            head, sep, tail = raw.partition("<strong>Editorial Notes</strong>")
            self.assertTrue(sep)
            self.assertIn(quote, head)
            return head.replace(quote, "1 shall be designated to serve as Chairman") + sep + tail

        directory = self._doctored_directory(transform)
        result = ss.match_reviewed_rows(self.node_map, self.schedule, directory=directory)
        self.assertNotIn("exec-regulatory-fed-chair-board-of-governors", result["matched"])
        self.assertEqual(result["refusals"]["reviewed_row_basis_quote_not_in_operative_text"],
                         ["exec-regulatory-fed-chair-board-of-governors"])
        # The doctored page still carries the sentence beneath the cut.
        self.assertIn(quote, (directory / "fed_12_usc_242.html").read_text(encoding="utf-8"))
        # Every other row, whose sentence was not moved, still matches.
        self.assertEqual(set(result["matched"]), set(ss.REVIEWED_TITLE_ROWS) - {"exec-regulatory-fed-chair-board-of-governors"})

    def test_an_edited_basis_section_is_refused_rather_than_rehashed(self) -> None:
        import tempfile
        from pathlib import Path as _Path

        tmp = _Path(tempfile.mkdtemp())
        self._copy_basis_fixtures(tmp)
        with (tmp / "fed_12_usc_242.html").open("a", encoding="utf-8") as handle:
            handle.write("<!-- one byte more -->")
        result = ss.match_reviewed_rows(self.node_map, self.schedule, directory=tmp)
        # The three Fed rows fall with their section; the six resting on
        # other sections are untouched by it.
        self.assertEqual(set(result["refusals"]["reviewed_row_basis_unreadable"]), self.FED_ROWS)
        self.assertEqual(set(result["matched"]), set(ss.REVIEWED_TITLE_ROWS) - self.FED_ROWS)
        self.assertEqual(len(self.FED_ROWS), 3)


class ReviewedGateTests(unittest.TestCase):
    NODE_ID = "exec-regulatory-fed-vice-chair-for-supervision"

    def setUp(self) -> None:
        self.node = fed_node(self.NODE_ID)

    def test_a_true_reviewed_record_passes(self) -> None:
        self.assertEqual(schedule_pay_violations(self.node, good_reviewed_pay(self.NODE_ID), REVIEWED_TODAY, label), [])
        for node_id in US_CODE_REVIEWED_IDENTIFICATIONS:
            with self.subTest(node=node_id):
                self.assertEqual(schedule_pay_violations(fed_node(node_id), good_reviewed_pay(node_id), REVIEWED_TODAY, label), [])

    def test_a_basis_read_from_govinfo_passes_when_it_names_the_section(self) -> None:
        # Since 2026-10-05 a reviewed row's basis may have been read from GPO's
        # rendering of the Code on www.govinfo.gov (the OLRC host was under
        # maintenance); the gate accepts its link-service URL and the granule
        # it resolves to, and only for the section the citation names.
        good = good_reviewed_pay(self.NODE_ID)
        for url in ("https://www.govinfo.gov/link/uscode/12/242?link-type=html",
                    "https://www.govinfo.gov/content/pkg/USCODE-2024-title12/html/USCODE-2024-title12-chap3-subchapII-sec242.htm"):
            with self.subTest(url=url):
                pay = {**good, "identification": {**good["identification"], "basisUrl": url}}
                self.assertEqual(schedule_pay_violations(self.node, pay, REVIEWED_TODAY, label), [])
        self.assertTrue(us_code_url_names_section("https://www.govinfo.gov/link/uscode/42/2000e-4?link-type=html", "42 U.S.C. 2000e-4"))
        self.assertFalse(us_code_url_names_section("https://www.govinfo.gov/link/uscode/42/2000e?link-type=html", "42 U.S.C. 2000e-4"))

    def test_each_way_a_reviewed_record_can_be_faked_is_refused(self) -> None:
        good = good_reviewed_pay(self.NODE_ID)
        ident = good["identification"]
        cases = {
            # Both Vice Chairs are Level II from one "Members" row: figure,
            # title, level and citation all survive a swap, and only the
            # node's own identity and recorded name catch it.
            "a record swapped onto the other vice chair": (
                fed_node("exec-regulatory-fed-vice-chair-board-of-governors"), good),
            "a record on a node the table has no row for": (
                {"id": "exec-regulatory-fed-governor-4-members", "name": "Governor (×4 members)", "type": "Position"}, good),
            "a node renamed since the row was written": (
                {**self.node, "name": "Vice Chairman for Regulation"}, good),
            "the ordinary method on a reviewed node": (None, {**good, "method": ss.METHOD}),
            "no identification block": (None, {k: v for k, v in good.items() if k != "identification"}),
            "an identification against another name": (None, {**good, "identification": {**ident, "nodeName": "Vice Chair, Board of Governors"}}),
            "a different basis statute": (None, {**good, "identification": {**ident, "basisCitation": "12 U.S.C. 241"}}),
            "a basis sentence the row does not carry": (None, {**good, "identification": {
                **ident, "basisQuote": "2 shall be designated by the President, by and with the advice and consent of the Senate, to serve as Vice Chairmen of the Board"}}),
            "a basis sentence found only in the notes": (None, {**good, "identification": {
                **ident, "basisQuote": "Vice Chairman for Supervision"}}),
            "no stated basis": (None, {**good, "identification": {**ident, "basis": ""}}),
            "a basis stating the opposite legal reading": (None, {**good, "identification": {
                **ident, "basis": "5 U.S.C. 5313 places the Vice Chairman at Level V and 12 U.S.C. 242 says nothing about members"}}),
            "a digest that is not the committed section's": (None, {**good, "identification": {**ident, "basisSha256": "0" * 64}}),
            "a basis URL on another host": (None, {**good, "identification": {**ident, "basisUrl": "https://www.law.cornell.edu/uscode/text/12/242"}}),
            "a basis URL for another section": (None, {**good, "identification": {
                **ident, "basisUrl": "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title12-section241&num=0&edition=prelim"}}),
            "a govinfo link for another section": (None, {**good, "identification": {
                **ident, "basisUrl": "https://www.govinfo.gov/link/uscode/12/241?link-type=html"}}),
            "a govinfo page that is not the Code": (None, {**good, "identification": {
                **ident, "basisUrl": "https://www.govinfo.gov/app/details/GOVMAN-2025-12-31/GOVMAN-2025-12-31-072"}}),
            "a basis read in the future": (None, {**good, "identification": {**ident, "basisCheckedAt": "2027-01-01T00:00:00Z"}}),
            "a scope claimed on a reviewed row": (None, {**good, "scopedOffice": "Vice Chair for Supervision", "scopedOrganisationId": "exec-regulatory-fed"}),
            "a statutory title the Code prints for another level": (None, {**good, "statutoryTitle": "Chairman, Board of Governors of the Federal Reserve System"}),
            "a level the Code does not set for members": (None, {**good, "payLevel": "I", "amount": EXECUTIVE_SCHEDULE_RATES["I"],
                                                                 "rateText": "${:,.0f}".format(EXECUTIVE_SCHEDULE_RATES["I"]),
                                                                 "amountScope": "Level I", "quote": "Level I  ${:,.0f}".format(EXECUTIVE_SCHEDULE_RATES["I"])}),
            "an exact scope": (None, {**good, "scopeMatch": "exact"}),
            "a verified grade": (None, {**good, "financialEvidenceStatus": "verified"}),
            "a class-title mark on a row that prices one office": (None, {**good, "classTitle": True}),
        }
        for name, (node, pay) in cases.items():
            with self.subTest(case=name):
                self.assertNotEqual(schedule_pay_violations(node or self.node, pay, REVIEWED_TODAY, label), [], name)

    def test_each_way_a_class_title_bench_can_be_faked_is_refused(self) -> None:
        bench_id = "exec-regulatory-fcc-commissioner-4"
        bench = reviewed_node(bench_id)
        good = good_reviewed_pay(bench_id)
        self.assertEqual(schedule_pay_violations(bench, good, REVIEWED_TODAY, label), [])
        single = {k: v for k, v in bench.items() if k != "representsPosts"}
        single["name"] = "Commissioner"
        cases = {
            # The mark is what keeps the block on the bench; without it the
            # block is one appointment's level standing for four.
            "the bench without the class-title mark": (bench, {k: v for k, v in good.items() if k != "classTitle"}),
            "the bench without a holders block": (bench, {k: v for k, v in good.items() if k != "holders"}),
            "holders stating a count the name does not": (bench, {**good, "holders": {**good["holders"], "count": 5}}),
            "the class title on a node that stands for one post": (single, good),
            # Swapped onto the Chair: same Commission, Level IV against the
            # Chair's Level III row, and the name check catches it too.
            "the bench block on the Chair": (reviewed_node("exec-regulatory-fcc-chair-fcc"), good),
            "the class title relabelled as the Chairman's title": (bench, {**good, "statutoryTitle": "Chairman, Federal Communications Commission"}),
            "an ordinary-route record on the bench": (bench, {k: v for k, v in good.items() if k not in ("identification", "classTitle", "holders")} | {"method": ss.METHOD}),
        }
        for name, (node, pay) in cases.items():
            with self.subTest(case=name):
                self.assertNotEqual(schedule_pay_violations(node, pay, REVIEWED_TODAY, label), [], name)

    def test_a_reviewed_identification_on_an_ordinary_node_is_refused(self) -> None:
        node_id = GateTests.NODE_ID
        title, _, _, _ = US_CODE_EXECUTIVE_SCHEDULE[node_id]
        node = {"id": node_id, "name": title, "type": "Position"}
        pay = good_pay(node_id)
        self.assertEqual(schedule_pay_violations(node, pay, TODAY, label), [])
        with self.subTest(case="identification block"):
            self.assertNotEqual(schedule_pay_violations(node, {**pay, "identification": dict(good_reviewed_pay(self.NODE_ID)["identification"])}, TODAY, label), [])
        with self.subTest(case="reviewed method"):
            self.assertNotEqual(schedule_pay_violations(node, {**pay, "method": ss.METHOD_REVIEWED}, TODAY, label), [])
        with self.subTest(case="an unknown method"):
            self.assertNotEqual(schedule_pay_violations(node, {**pay, "method": "assigned_by_review"}, TODAY, label), [])

    def test_the_checker_reads_the_basis_from_the_bytes_not_the_block(self) -> None:
        """The record's own digest is a claim; the gate recomputes it."""
        good = good_reviewed_pay(self.NODE_ID)
        self.assertEqual(good["identification"]["basisSha256"], fixture_digest(US_CODE_BASIS_FIXTURE_DIR / "fed_12_usc_242.html"))
        out = reviewed_schedule_violations(self.node, good, US_CODE_REVIEWED_IDENTIFICATIONS[self.NODE_ID], REVIEWED_TODAY, label)
        self.assertEqual(out, [])


# --------------------------------------------------------------------------
# The twelfth batch's Defense cluster (2026-10-06): the Department's Chief
# Financial Officer, priced as the Under Secretary of Defense (Comptroller) --
# and the Chief Information Officer the parser refuses.


class DefenseComptrollerRowTests(unittest.TestCase):
    """'Chief Financial Officer' names 81 nodes in this graph, so the row is
    keyed to the Department of Defense's node and everything that ties the
    figure to THAT node is pinned here: the title the Code prints and its
    level, the sentence 10 U.S.C. 135(b) prints in its OPERATIVE text, the
    derived record applied the way the exporter applies it and passing the
    gate, the gate's refusal of the same record on every other Chief Financial
    Officer, and the parser's refusal of the Department's Chief Information
    Officer, whose §5315 entry is a title with a 164-character proviso."""

    NODE_ID = "exec-dept-defense-chief-financial-officer"
    CIO_ID = "exec-dept-defense-chief-information-officer"
    FIXTURE = "dod_10_usc_135_govinfo2024.html"
    TITLE = "Under Secretary of Defense (Comptroller)"
    QUOTE = ("The Under Secretary of Defense (Comptroller) is the agency Chief Financial Officer "
             "of the Department of Defense for the purposes of chapter 9 of title 31.")
    CIO_TITLE = ("Chief Information Officer, Department of Defense (unless the official designated as the "
                 "Chief Information Officer of the Department of Defense is an official listed under "
                 "section 5312, 5313, or 5314 of this title)")

    @classmethod
    def setUpClass(cls) -> None:
        from data_pipeline.exporter.build_graph import DEFAULT_BASE_GRAPH, load_base_graph

        cls.schedule = ss.load_schedule()
        cls.node_map, cls.parent_map = index_tree(load_base_graph(DEFAULT_BASE_GRAPH))

    @staticmethod
    def _flat(name):
        import html as html_module
        import re

        raw = (US_CODE_BASIS_FIXTURE_DIR / name).read_text(encoding="utf-8")
        return re.sub(r"\s+", " ", html_module.unescape(re.sub(r"<[^>]+>", " ", raw)))

    def test_the_row_is_what_the_code_and_its_own_history_print(self) -> None:
        row = ss.REVIEWED_TITLE_ROWS[self.NODE_ID]
        self.assertEqual(row["nodeName"], "Chief Financial Officer")
        self.assertEqual(row["statutoryTitle"], self.TITLE)
        self.assertEqual((row["basisCitation"], row["basisFixture"], row["basisQuote"]),
                         ("10 U.S.C. 135", self.FIXTURE, self.QUOTE))
        self.assertNotIn("classTitle", row)
        position = self.schedule["index"][canonical_name_key(self.TITLE)]
        self.assertEqual((position["title"], position["level"], position["section"], position["statedPosts"]),
                         (self.TITLE, "III", "5314", 1))
        # The Code prints no "Chief Financial Officer, Department of Defense"
        # in force: the only place those words appear is §5315's Amendments
        # note, as an item inserted in 1990 and struck in 1993 -- the history
        # the row's basis leans on, so the notes must really print it.
        self.assertNotIn(canonical_name_key("Chief Financial Officer, Department of Defense"), self.schedule["index"])
        notes_5315 = self._flat("exec_schedule_5315.html")
        self.assertIn("struck out item relating to Chief Financial Officer, Department of Defense", notes_5315)
        self.assertIn("Pub. L. 101–576 inserted items relating to Chief Financial Officer of Departments of "
                      "Agriculture, Commerce, Defense", notes_5315)
        notes_5314 = self._flat("exec_schedule_5314.html")
        self.assertIn("Pub. L. 103–160 inserted items relating to Comptroller of the Department of Defense", notes_5314)
        self.assertIn('Pub. L. 103–337 substituted "Under Secretary of Defense (Comptroller)" for '
                      '"Comptroller of the Department of Defense"', notes_5314)
        # And the basis sentence is the law, not the notes, by both readers.
        self.assertIn(self.QUOTE, ss.load_basis_section(self.FIXTURE)["operative"])
        self.assertIn(self.QUOTE, uscode_operative_text(US_CODE_BASIS_FIXTURE_DIR / self.FIXTURE))

    def test_the_row_matches_on_the_real_graph_and_only_through_the_reviewed_route(self) -> None:
        whole = ss.match_positions(self.node_map, self.schedule)["matched"]
        scoped = ss.match_scoped_positions(self.node_map, self.schedule, already_matched=whole)["matched"]
        self.assertNotIn(self.NODE_ID, whole)
        self.assertNotIn(self.NODE_ID, scoped)
        result = ss.match_reviewed_rows(self.node_map, self.schedule, already_matched={**whole, **scoped})
        self.assertIn(self.NODE_ID, result["matched"])
        entry = result["matched"][self.NODE_ID]
        self.assertEqual(entry["method"], ss.METHOD_REVIEWED)
        self.assertEqual((entry["title"], entry["level"], entry["section"]), (self.TITLE, "III", "5314"))
        self.assertNotIn("classTitle", entry)
        ident = entry["identification"]
        self.assertEqual(ident["nodeName"], "Chief Financial Officer")
        self.assertEqual(ident["basisCitation"], "10 U.S.C. 135")
        self.assertEqual(ident["basisQuote"], self.QUOTE)
        # Read from GPO's rendering through its link service, which is the URL
        # the fixture's own fetch record names.
        self.assertEqual(ident["basisUrl"], "https://www.govinfo.gov/link/uscode/10/135?link-type=html")
        self.assertTrue(us_code_url_names_section(ident["basisUrl"], "10 U.S.C. 135"))
        self.assertEqual(ident["basisSha256"], fixture_digest(US_CODE_BASIS_FIXTURE_DIR / self.FIXTURE))
        # The node is one post, directly under the Department.
        self.assertEqual(self.parent_map[self.NODE_ID], "exec-dept-defense")
        self.assertFalse(ss.states_a_multiplicity(self.node_map[self.NODE_ID]["name"]))

    def test_the_derived_record_applied_to_the_node_passes_the_gate(self) -> None:
        """The published graph is rebuilt by the coordinator, so the record is
        checked here the way the exporter would publish it: built from the
        real statute and the real table, validated, applied, and gated."""
        from data_pipeline.verification import financial_evidence as fe
        from data_pipeline.verification.pay_tables import (
            DEFAULT_PAY_TABLE_HTML,
            federal_fiscal_year_of,
            load_executive_schedule,
        )

        loaded = load_executive_schedule(DEFAULT_PAY_TABLE_HTML)
        matched = ss.match_reviewed_rows(self.node_map, self.schedule)["matched"]
        fiscal_year = federal_fiscal_year_of(date.fromisoformat(str(loaded["table"]["effective"])))
        records, _report = ss.build_records(
            {self.NODE_ID: matched[self.NODE_ID]}, loaded["table"],
            table_url=loaded["url"], table_sha256=loaded["sha256"],
            retrieved_at=loaded["fetched_at"], fiscal_year=fiscal_year,
        )
        node = {k: v for k, v in self.node_map[self.NODE_ID].items() if k != "children"}
        record = fe.validate_record(records[self.NODE_ID], node)
        self.assertEqual(fe.classify(record), "partial")
        record["financialEvidenceStatus"] = "partial"
        for key in ("levelClaim", "rateText", "effectiveText", "table", "tableFootnotes"):
            record[key] = records[self.NODE_ID][key]
        probe = {"id": "root", "name": "Root", "type": "Foundation", "children": [
            {"id": "exec-dept-defense", "name": "Department of Defense (DoD)", "type": "Cabinet Department",
             "children": [node]}]}
        stats = ss.apply_schedule_pay(probe, {self.NODE_ID: record})
        self.assertEqual(stats["priced"], 1)
        applied = probe["children"][0]["children"][0]
        pay = applied["positionSchedulePay"]
        self.assertEqual((pay["payLevel"], pay["amount"], pay["statutoryTitle"], pay["method"]),
                         ("III", EXECUTIVE_SCHEDULE_RATES["III"], self.TITLE, ss.METHOD_REVIEWED))
        self.assertEqual((pay["scopeMatch"], pay["financialEvidenceStatus"]), ("proxy", "partial"))
        self.assertNotIn("classTitle", pay)
        self.assertEqual(schedule_pay_violations(applied, pay, REVIEWED_TODAY, label), [])
        # Nothing the rate wrote reads as evidence that the post exists.
        for field in ("sourceUrls", "sourceTypes", "lastVerified", "verificationMethod"):
            self.assertNotIn(field, applied)

    def _doctored_directory(self, transform):
        import hashlib
        import tempfile

        tmp = Path(tempfile.mkdtemp())
        for row in ss.REVIEWED_TITLE_ROWS.values():
            for name in (row["basisFixture"], row["basisFixture"] + ".meta.json"):
                (tmp / name).write_bytes((US_CODE_BASIS_FIXTURE_DIR / name).read_bytes())
        raw = (tmp / self.FIXTURE).read_text(encoding="utf-8")
        doctored = transform(raw)
        (tmp / self.FIXTURE).write_text(doctored, encoding="utf-8")
        meta_path = tmp / (self.FIXTURE + ".meta.json")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["sha256"] = hashlib.sha256(doctored.encode("utf-8")).hexdigest()
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        return tmp

    def test_the_sentence_moved_beneath_the_notes_cut_fells_the_row(self) -> None:
        """The CAVC lesson, on GPO's rendering: move 135(b)'s sentence out of
        the law and into the Editorial Notes, re-sign the digest, and the row
        must fall while the page still carries the sentence -- by the module's
        reader and by the gate's independent one."""
        def transform(raw):
            head, sep, tail = raw.partition("<strong>Editorial Notes</strong>")
            self.assertTrue(sep)
            self.assertIn(self.QUOTE, head)
            self.assertNotIn(self.QUOTE, tail)
            return (head.replace(self.QUOTE, "The Under Secretary performs the duties the Secretary prescribes.")
                    + sep + "</h4><p>" + self.QUOTE + "</p><h4>" + tail)

        directory = self._doctored_directory(transform)
        node_map = {self.NODE_ID: dict(self.node_map[self.NODE_ID])}
        result = ss.match_reviewed_rows(node_map, self.schedule, directory=directory)
        self.assertNotIn(self.NODE_ID, result["matched"])
        self.assertEqual(result["refusals"]["reviewed_row_basis_quote_not_in_operative_text"], [self.NODE_ID])
        doctored = (directory / self.FIXTURE).read_text(encoding="utf-8")
        self.assertIn(self.QUOTE, doctored)
        self.assertNotIn(self.QUOTE, ss.load_basis_section(self.FIXTURE, directory)["operative"])
        self.assertNotIn(self.QUOTE, uscode_operative_text(directory / self.FIXTURE))
        # The committed page, untouched, still prints it as the law.
        self.assertIn(self.QUOTE, uscode_operative_text(US_CODE_BASIS_FIXTURE_DIR / self.FIXTURE))
        # An unsigned edit is refused before the quote is even looked for.
        with (directory / self.FIXTURE).open("a", encoding="utf-8") as handle:
            handle.write("<!-- one byte more -->")
        result = ss.match_reviewed_rows(node_map, self.schedule, directory=directory)
        self.assertEqual(result["refusals"]["reviewed_row_basis_unreadable"], [self.NODE_ID])

    def test_the_record_on_any_other_chief_financial_officer_is_refused(self) -> None:
        """81 nodes carry this name and the record for one would keep a real
        title, a real section, a real sentence and the right figure on any of
        them; only the node's own id tells them apart, and the gate keys on it."""
        good = good_reviewed_pay(self.NODE_ID)
        self.assertEqual(schedule_pay_violations(reviewed_node(self.NODE_ID), good, REVIEWED_TODAY, label), [])
        self.assertEqual(schedule_pay_violations(self.node_map[self.NODE_ID], good, REVIEWED_TODAY, label), [])
        govinfo = {**good, "identification": {**good["identification"],
                                              "basisUrl": "https://www.govinfo.gov/link/uscode/10/135?link-type=html"}}
        self.assertEqual(schedule_pay_violations(self.node_map[self.NODE_ID], govinfo, REVIEWED_TODAY, label), [])
        others = sorted(i for i, n in self.node_map.items()
                        if n.get("name") == "Chief Financial Officer" and i != self.NODE_ID)
        self.assertGreaterEqual(len(others), 60)
        for other in others:
            with self.subTest(node=other):
                self.assertNotEqual(schedule_pay_violations(self.node_map[other], good, REVIEWED_TODAY, label), [])
        # On the Department's own Chief Information Officer -- the post the
        # same cluster surfaced and this table deliberately has no row for.
        self.assertNotEqual(schedule_pay_violations(self.node_map[self.CIO_ID], good, REVIEWED_TODAY, label), [])
        # And on the Deputy, whom the Code places separately at Level IV.
        self.assertNotEqual(schedule_pay_violations(self.node_map["exec-dept-defense-deputy-cfo-controller"], good,
                                                    REVIEWED_TODAY, label), [])
        # Module side: the node renamed, or gone, prices nothing.
        renamed = {self.NODE_ID: {**self.node_map[self.NODE_ID], "name": "Comptroller"}}
        self.assertEqual(ss.match_reviewed_rows(renamed, self.schedule)["refusals"]["reviewed_row_node_renamed"],
                         [self.NODE_ID])
        self.assertIn(self.NODE_ID, ss.match_reviewed_rows({}, self.schedule)["refusals"]["reviewed_row_names_no_node"])

    def test_the_chief_information_officer_is_refused_by_the_parser_and_has_no_row(self) -> None:
        """§5315 prints the Department's Chief Information Officer as a title
        with a proviso -- Level IV only while the designated official is not
        also one the Code lists at a higher level -- and the parser refuses
        anything over MAX_TITLE_CHARS as a sentence, because reading the
        proviso would be reading law. Pinned in both directions: the page
        prints it in those words, and no table here names the node."""
        self.assertGreater(len(self.CIO_TITLE), ss.MAX_TITLE_CHARS)
        self.assertEqual(len(self.CIO_TITLE), 213)
        raw = (US_CODE_BASIS_FIXTURE_DIR / "exec_schedule_5315.html").read_text(encoding="utf-8")
        self.assertIn(self.CIO_TITLE + ".", ss._text_of(raw))
        parsed = ss.parse_section(raw, section="5315")
        self.assertTrue(any(s.startswith("Chief Information Officer, Department of Defense (unless") for s in parsed["skipped"]))
        self.assertNotIn(canonical_name_key(self.CIO_TITLE), self.schedule["index"])
        self.assertNotIn(canonical_name_key(self.CIO_TITLE), self.schedule["ambiguous"])
        self.assertEqual(self.node_map[self.CIO_ID]["name"], "Chief Information Officer")
        self.assertEqual(self.parent_map[self.CIO_ID], "exec-dept-defense")
        for table in (ss.REVIEWED_TITLE_ROWS, US_CODE_REVIEWED_IDENTIFICATIONS, US_CODE_EXECUTIVE_SCHEDULE):
            self.assertNotIn(self.CIO_ID, table)
        self.assertNotIn(self.CIO_ID, {i for spec in US_CODE_COUNTED_CLASSES.values() for i in spec["members"]})


# --------------------------------------------------------------------------
# The twelfth batch's judiciary cluster (2026-10-06): the IRS's Chief Counsel,
# priced from 5 U.S.C. 5316's own title through 26 U.S.C. 7803(b)(1) -- and
# the Tax Court subtree's copy of the same office, which must never be.


class IrsChiefCounselRowTests(unittest.TestCase):
    """'Chief Counsel' is a stamped title this graph carries under nine
    bureaus, and the Tax Court subtree draws the IRS's own Chief Counsel a
    second time as 'Chief Counsel — IRS (opposing)', the office where it
    litigates. The row is keyed to the Internal Revenue Service's node alone,
    and everything that ties the figure to THAT node is pinned here: the
    title §5316 prints and its level, the sentence 7803(b)(1) prints in its
    OPERATIVE text (the same section the Commissioner's row cites, a
    different sentence), the record applied as the exporter applies it and
    passing the gate, and the gate's refusal of the same record on the Tax
    Court's copy and on every other Chief Counsel."""

    NODE_ID = "exec-dept-treasury-irs-chief-counsel"
    OPPOSING_ID = "jud-specialized-tax-chief-counsel-irs-opposing"
    COMMISSIONER_ID = "exec-dept-treasury-irs-commissioner-irs"
    FIXTURE = "irs_26_usc_7803.html"
    TITLE = "Chief Counsel for the Internal Revenue Service, Department of the Treasury"
    QUOTE = ("There shall be in the Department of the Treasury a Chief Counsel for the Internal Revenue Service "
             "who shall be appointed by the President, by and with the consent of the Senate.")

    @classmethod
    def setUpClass(cls) -> None:
        from data_pipeline.exporter.build_graph import DEFAULT_BASE_GRAPH, load_base_graph

        cls.schedule = ss.load_schedule()
        cls.node_map, cls.parent_map = index_tree(load_base_graph(DEFAULT_BASE_GRAPH))

    def test_the_row_is_what_the_code_prints(self) -> None:
        row = ss.REVIEWED_TITLE_ROWS[self.NODE_ID]
        self.assertEqual(row["nodeName"], "Chief Counsel")
        self.assertEqual(row["statutoryTitle"], self.TITLE)
        self.assertEqual((row["basisCitation"], row["basisFixture"], row["basisQuote"]),
                         ("26 U.S.C. 7803", self.FIXTURE, self.QUOTE))
        self.assertNotIn("classTitle", row)
        self.assertIn("Level V", row["basis"])
        position = self.schedule["index"][canonical_name_key(self.TITLE)]
        self.assertEqual((position["title"], position["level"], position["section"], position["statedPosts"]),
                         (self.TITLE, "V", "5316", 1))
        self.assertNotIn(canonical_name_key(self.TITLE), self.schedule["ambiguous"])
        # The sentence is the law, not the notes, by both readers -- and it is
        # a different sentence of the section the Commissioner's row already
        # cites: 7803(a)(1) creates the Commissioner, 7803(b)(1) the Chief
        # Counsel, and the Chief Counsel's is appointed "by and with the
        # consent of the Senate", without the word "advice" the Commissioner's
        # carries, which is why the quote is the page's words and not a tidied copy.
        operative = ss.load_basis_section(self.FIXTURE)["operative"]
        self.assertIn(self.QUOTE, operative)
        self.assertIn(self.QUOTE, uscode_operative_text(US_CODE_BASIS_FIXTURE_DIR / self.FIXTURE))
        commissioner = ss.REVIEWED_TITLE_ROWS[self.COMMISSIONER_ID]
        self.assertEqual(commissioner["basisFixture"], self.FIXTURE)
        self.assertNotEqual(commissioner["basisQuote"], self.QUOTE)
        self.assertIn(commissioner["basisQuote"], operative)
        self.assertIn("(b) Chief Counsel for the Internal Revenue Service (1) Appointment", operative)
        self.assertEqual(US_CODE_REVIEWED_IDENTIFICATIONS[self.NODE_ID][:4], ("Chief Counsel", self.TITLE, "V", "5316"))

    def test_the_row_matches_on_the_real_graph_and_only_through_the_reviewed_route(self) -> None:
        whole = ss.match_positions(self.node_map, self.schedule)["matched"]
        scoped = ss.match_scoped_positions(self.node_map, self.schedule, already_matched=whole)["matched"]
        self.assertNotIn(self.NODE_ID, whole)
        self.assertNotIn(self.NODE_ID, scoped)
        result = ss.match_reviewed_rows(self.node_map, self.schedule, already_matched={**whole, **scoped})
        self.assertIn(self.NODE_ID, result["matched"])
        entry = result["matched"][self.NODE_ID]
        self.assertEqual(entry["method"], ss.METHOD_REVIEWED)
        self.assertEqual((entry["title"], entry["level"], entry["section"]), (self.TITLE, "V", "5316"))
        self.assertNotIn("classTitle", entry)
        ident = entry["identification"]
        self.assertEqual(ident["nodeName"], "Chief Counsel")
        self.assertEqual(ident["basisCitation"], "26 U.S.C. 7803")
        self.assertEqual(ident["basisQuote"], self.QUOTE)
        self.assertTrue(us_code_url_names_section(ident["basisUrl"], "26 U.S.C. 7803"))
        self.assertEqual(ident["basisSha256"], fixture_digest(US_CODE_BASIS_FIXTURE_DIR / self.FIXTURE))
        # One post, directly under the Service.
        self.assertEqual(self.parent_map[self.NODE_ID], "exec-dept-treasury-irs")
        self.assertFalse(ss.states_a_multiplicity(self.node_map[self.NODE_ID]["name"]))
        # The Tax Court's copy of the office is reached by no route at all.
        self.assertEqual(self.node_map[self.OPPOSING_ID]["name"], "Chief Counsel — IRS (opposing)")
        self.assertEqual(self.parent_map[self.OPPOSING_ID], "jud-specialized-tax")
        for table in (ss.REVIEWED_TITLE_ROWS, US_CODE_REVIEWED_IDENTIFICATIONS, US_CODE_EXECUTIVE_SCHEDULE,
                      whole, scoped, result["matched"]):
            self.assertNotIn(self.OPPOSING_ID, table)
        self.assertNotIn(self.OPPOSING_ID, {i for spec in US_CODE_COUNTED_CLASSES.values() for i in spec["members"]})

    def test_the_derived_record_applied_to_the_node_passes_the_gate(self) -> None:
        """Built from the real statute and the real table, validated, applied
        the way the exporter applies it, and gated -- Level V, $184,900."""
        from data_pipeline.verification import financial_evidence as fe
        from data_pipeline.verification.pay_tables import (
            DEFAULT_PAY_TABLE_HTML,
            federal_fiscal_year_of,
            load_executive_schedule,
        )

        loaded = load_executive_schedule(DEFAULT_PAY_TABLE_HTML)
        matched = ss.match_reviewed_rows(self.node_map, self.schedule)["matched"]
        fiscal_year = federal_fiscal_year_of(date.fromisoformat(str(loaded["table"]["effective"])))
        records, _report = ss.build_records(
            {self.NODE_ID: matched[self.NODE_ID]}, loaded["table"],
            table_url=loaded["url"], table_sha256=loaded["sha256"],
            retrieved_at=loaded["fetched_at"], fiscal_year=fiscal_year,
        )
        node = {k: v for k, v in self.node_map[self.NODE_ID].items() if k != "children"}
        record = fe.validate_record(records[self.NODE_ID], node)
        self.assertEqual(fe.classify(record), "partial")
        record["financialEvidenceStatus"] = "partial"
        for key in ("levelClaim", "rateText", "effectiveText", "table", "tableFootnotes"):
            record[key] = records[self.NODE_ID][key]
        probe = {"id": "root", "name": "Root", "type": "Foundation", "children": [
            {"id": "exec-dept-treasury-irs", "name": "Internal Revenue Service (IRS)", "type": "Bureau",
             "children": [node]}]}
        stats = ss.apply_schedule_pay(probe, {self.NODE_ID: record})
        self.assertEqual(stats["priced"], 1)
        applied = probe["children"][0]["children"][0]
        pay = applied["positionSchedulePay"]
        self.assertEqual((pay["payLevel"], pay["amount"], pay["statutoryTitle"], pay["method"]),
                         ("V", EXECUTIVE_SCHEDULE_RATES["V"], self.TITLE, ss.METHOD_REVIEWED))
        self.assertEqual((pay["scopeMatch"], pay["financialEvidenceStatus"]), ("proxy", "partial"))
        self.assertNotIn("classTitle", pay)
        self.assertEqual(schedule_pay_violations(applied, pay, REVIEWED_TODAY, label), [])
        for field in ("sourceUrls", "sourceTypes", "lastVerified", "verificationMethod"):
            self.assertNotIn(field, applied)

    def test_the_record_on_the_tax_courts_copy_and_on_every_other_chief_counsel_is_refused(self) -> None:
        """The Tax Court subtree's 'Chief Counsel — IRS (opposing)' IS this
        office, drawn where it litigates, and pricing it would publish one
        salary twice; the eight other Chief Counsels are other bureaus' posts
        with the same stamped name. Only the node's own id keeps the figure
        on the Service's node, and the gate keys on it."""
        good = good_reviewed_pay(self.NODE_ID)
        self.assertEqual(schedule_pay_violations(reviewed_node(self.NODE_ID), good, REVIEWED_TODAY, label), [])
        self.assertEqual(schedule_pay_violations(self.node_map[self.NODE_ID], good, REVIEWED_TODAY, label), [])
        opposing = self.node_map[self.OPPOSING_ID]
        out = schedule_pay_violations(opposing, good, REVIEWED_TODAY, label)
        self.assertNotEqual(out, [])
        self.assertTrue(any("no row for" in v or "names no such post" in v for v in out), out)
        # Renamed to the bare title it would need to match the row's name, it
        # is still refused: the row is keyed by id, not by name.
        self.assertNotEqual(schedule_pay_violations({**opposing, "name": "Chief Counsel"}, good, REVIEWED_TODAY, label), [])
        others = sorted(i for i, n in self.node_map.items() if n.get("name") == "Chief Counsel" and i != self.NODE_ID)
        self.assertEqual(8, len(others))
        for other in others:
            with self.subTest(node=other):
                self.assertNotEqual(schedule_pay_violations(self.node_map[other], good, REVIEWED_TODAY, label), [])
        # On the Commissioner, whose row cites the same section at Level III.
        self.assertNotEqual(schedule_pay_violations(self.node_map[self.COMMISSIONER_ID], good, REVIEWED_TODAY, label), [])
        # The Commissioner's record on the Chief Counsel: same basis section,
        # a different sentence and a different level.
        self.assertNotEqual(schedule_pay_violations(self.node_map[self.NODE_ID], good_reviewed_pay(self.COMMISSIONER_ID),
                                                    REVIEWED_TODAY, label), [])
        # Module side: renamed or gone, the row prices nothing.
        renamed = {self.NODE_ID: {**self.node_map[self.NODE_ID], "name": "Chief Counsel, IRS"}}
        self.assertEqual(ss.match_reviewed_rows(renamed, self.schedule)["refusals"]["reviewed_row_node_renamed"],
                         [self.NODE_ID])
        self.assertIn(self.NODE_ID, ss.match_reviewed_rows({}, self.schedule)["refusals"]["reviewed_row_names_no_node"])

    def test_the_sentence_moved_beneath_the_notes_cut_fells_the_row_and_leaves_the_commissioners(self) -> None:
        """Move 7803(b)(1)'s sentence into the Editorial Notes, re-sign the
        digest, and the Chief Counsel's row falls while the page still carries
        the sentence -- and the Commissioner's row, whose sentence in the same
        section is untouched, stands."""
        import hashlib
        import tempfile

        tmp = Path(tempfile.mkdtemp())
        for row in ss.REVIEWED_TITLE_ROWS.values():
            for name in (row["basisFixture"], row["basisFixture"] + ".meta.json"):
                (tmp / name).write_bytes((US_CODE_BASIS_FIXTURE_DIR / name).read_bytes())
        raw = (tmp / self.FIXTURE).read_text(encoding="utf-8")
        head, sep, tail = raw.partition("<strong>Editorial Notes</strong>")
        self.assertTrue(sep)
        self.assertIn(self.QUOTE, head)
        self.assertNotIn(self.QUOTE, tail)
        doctored = (head.replace(self.QUOTE, "The Chief Counsel shall be appointed as the Secretary prescribes.")
                    + sep + "<p>" + self.QUOTE + "</p>" + tail)
        (tmp / self.FIXTURE).write_text(doctored, encoding="utf-8")
        meta_path = tmp / (self.FIXTURE + ".meta.json")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["sha256"] = hashlib.sha256(doctored.encode("utf-8")).hexdigest()
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        node_map = {self.NODE_ID: dict(self.node_map[self.NODE_ID]),
                    self.COMMISSIONER_ID: dict(self.node_map[self.COMMISSIONER_ID])}
        result = ss.match_reviewed_rows(node_map, self.schedule, directory=tmp)
        self.assertNotIn(self.NODE_ID, result["matched"])
        self.assertIn(self.COMMISSIONER_ID, result["matched"])
        self.assertEqual(result["refusals"]["reviewed_row_basis_quote_not_in_operative_text"], [self.NODE_ID])
        self.assertIn(self.QUOTE, (tmp / self.FIXTURE).read_text(encoding="utf-8"))
        self.assertNotIn(self.QUOTE, ss.load_basis_section(self.FIXTURE, tmp)["operative"])
        self.assertNotIn(self.QUOTE, uscode_operative_text(tmp / self.FIXTURE))
        self.assertIn(self.QUOTE, uscode_operative_text(US_CODE_BASIS_FIXTURE_DIR / self.FIXTURE))


# --------------------------------------------------------------------------
# The twelfth batch's health cluster (2026-10-06): the Commissioner of Food and
# Drugs, priced from 5 U.S.C. 5315's own title through 21 U.S.C. 393(d)(1).
# Reviewed rows 97 -> 98, Schedule-priced nodes 236 -> 237. The two
# published-graph comparisons above -- MirrorTests.test_the_mirror_covers_
# exactly_the_published_nodes and ItIsNotEvidenceThePostExistsTests.test_no_
# priced_node_carries_the_figure_as_a_cost -- read output/graph.json and pass
# only once the graph is regenerated with the new evidence file.


class FdaCommissionerRowTests(unittest.TestCase):
    """§5315 prints 'Commissioner of Food and Drugs, Department of Health and
    Human Services' with a footnote mark where its full stop should be, so
    until the parser read a closing mark the title was not in the index and no
    row could cite it. The graph names the post 'Commissioner, FDA', which no
    route reaches by name. Pinned here: the title and its level, the sentence
    393(d)(1) prints in its OPERATIVE text by both readers, the section's
    provenance (govinfo's 2024 edition, the OLRC host being under
    maintenance), the record applied as the exporter applies it and passing
    the gate, the gate's refusal of the same record on the Deputy Commissioner
    and on other commissioners, and a doctored basis fixture felling the row."""

    NODE_ID = "exec-dept-hhs-fda-commissioner-fda"
    PARENT_ID = "exec-dept-hhs-fda"
    DEPUTY_ID = "exec-dept-hhs-fda-deputy-commissioner"
    FIXTURE = "fda_21_usc_393_govinfo2024.html"
    TITLE = "Commissioner of Food and Drugs, Department of Health and Human Services"
    QUOTE = ('There shall be in the Administration a Commissioner of Food and Drugs (hereinafter in this section '
             'referred to as the "Commissioner") who shall be appointed by the President by and with the advice '
             'and consent of the Senate.')

    @classmethod
    def setUpClass(cls) -> None:
        from data_pipeline.exporter.build_graph import DEFAULT_BASE_GRAPH, load_base_graph

        cls.schedule = ss.load_schedule()
        cls.node_map, cls.parent_map = index_tree(load_base_graph(DEFAULT_BASE_GRAPH))

    def test_the_row_is_what_the_code_prints(self) -> None:
        row = ss.REVIEWED_TITLE_ROWS[self.NODE_ID]
        self.assertEqual(row["nodeName"], "Commissioner, FDA")
        self.assertEqual(row["statutoryTitle"], self.TITLE)
        self.assertEqual((row["basisCitation"], row["basisFixture"], row["basisQuote"]),
                         ("21 U.S.C. 393", self.FIXTURE, self.QUOTE))
        self.assertNotIn("classTitle", row)
        self.assertIn("Level IV", row["basis"])
        self.assertIn("So in original. Probably should be followed by a period.", row["basis"])
        position = self.schedule["index"][canonical_name_key(self.TITLE)]
        self.assertEqual((position["title"], position["level"], position["section"], position["statedPosts"]),
                         (self.TITLE, "IV", "5315", 1))
        self.assertNotIn(canonical_name_key(self.TITLE), self.schedule["ambiguous"])
        # The sentence is the law, not the notes, by both readers, and it is
        # 393(d)(1)'s own words -- the parenthetical and "by and with the
        # advice and consent" included, because a tidied copy is not a quote.
        operative = ss.load_basis_section(self.FIXTURE)["operative"]
        self.assertIn(self.QUOTE, operative)
        self.assertIn("(d) Commissioner (1) Appointment " + self.QUOTE, operative)
        self.assertIn(self.QUOTE, uscode_operative_text(US_CODE_BASIS_FIXTURE_DIR / self.FIXTURE))
        self.assertNotIn("Editorial Notes", operative)
        self.assertEqual(US_CODE_REVIEWED_IDENTIFICATIONS[self.NODE_ID][:4], ("Commissioner, FDA", self.TITLE, "IV", "5315"))
        self.assertEqual(US_CODE_REVIEWED_IDENTIFICATIONS[self.NODE_ID][4:7], ("21 U.S.C. 393", self.FIXTURE, self.QUOTE))
        self.assertEqual(US_CODE_REVIEWED_IDENTIFICATIONS[self.NODE_ID][7:], (row["basis"], False))

    def test_the_section_is_govinfos_2024_edition_and_not_a_maintenance_page(self) -> None:
        meta = json.loads((US_CODE_BASIS_FIXTURE_DIR / (self.FIXTURE + ".meta.json")).read_text(encoding="utf-8"))
        self.assertEqual(meta["url"], "https://www.govinfo.gov/link/uscode/21/393?link-type=html")
        self.assertEqual(meta["status"], 200)
        self.assertIn("USCODE-2024-title21", meta["final_url"])
        self.assertTrue(meta["final_url"].endswith("-sec393.htm"))
        self.assertTrue(us_code_url_names_section(meta["url"], "21 U.S.C. 393"))
        raw = (US_CODE_BASIS_FIXTURE_DIR / self.FIXTURE).read_text(encoding="utf-8")
        self.assertNotIn("Under Maintenance", raw)
        self.assertNotIn("Page Not Found", raw)
        self.assertIn("<strong>Editorial Notes</strong>", raw)
        self.assertEqual(fixture_digest(US_CODE_BASIS_FIXTURE_DIR / self.FIXTURE), meta["sha256"])

    def test_the_row_matches_on_the_real_graph_and_only_through_the_reviewed_route(self) -> None:
        whole = ss.match_positions(self.node_map, self.schedule)["matched"]
        scoped = ss.match_scoped_positions(self.node_map, self.schedule, already_matched=whole)
        self.assertNotIn(self.NODE_ID, whole)
        self.assertNotIn(self.NODE_ID, scoped["matched"])
        # The scoped route splits the title at its comma, finds the Department
        # and no direct child of it called "Commissioner of Food and Drugs".
        self.assertIn(self.TITLE, scoped["refusals"]["no_such_post_directly_under_that_organisation"])
        result = ss.match_reviewed_rows(self.node_map, self.schedule, already_matched={**whole, **scoped["matched"]})
        self.assertIn(self.NODE_ID, result["matched"])
        entry = result["matched"][self.NODE_ID]
        self.assertEqual(entry["method"], ss.METHOD_REVIEWED)
        self.assertEqual((entry["title"], entry["level"], entry["section"]), (self.TITLE, "IV", "5315"))
        self.assertNotIn("classTitle", entry)
        ident = entry["identification"]
        self.assertEqual(ident["nodeName"], "Commissioner, FDA")
        self.assertEqual(ident["basisCitation"], "21 U.S.C. 393")
        self.assertEqual(ident["basisQuote"], self.QUOTE)
        self.assertTrue(us_code_url_names_section(ident["basisUrl"], "21 U.S.C. 393"))
        self.assertEqual(ident["basisSha256"], fixture_digest(US_CODE_BASIS_FIXTURE_DIR / self.FIXTURE))
        # One post, directly under the Administration.
        self.assertEqual(self.parent_map[self.NODE_ID], self.PARENT_ID)
        self.assertEqual(self.node_map[self.PARENT_ID]["name"], "Food & Drug Administration (FDA)")
        self.assertFalse(ss.states_a_multiplicity(self.node_map[self.NODE_ID]["name"]))
        self.assertNotIn(self.NODE_ID, US_CODE_EXECUTIVE_SCHEDULE)
        self.assertNotIn(self.NODE_ID, {i for spec in US_CODE_COUNTED_CLASSES.values() for i in spec["members"]})

    def test_the_derived_record_applied_to_the_node_passes_the_gate(self) -> None:
        """Built from the real statute and the real table, validated, applied
        the way the exporter applies it, and gated -- Level IV, $197,200."""
        from data_pipeline.verification import financial_evidence as fe
        from data_pipeline.verification.pay_tables import (
            DEFAULT_PAY_TABLE_HTML,
            federal_fiscal_year_of,
            load_executive_schedule,
        )

        loaded = load_executive_schedule(DEFAULT_PAY_TABLE_HTML)
        matched = ss.match_reviewed_rows(self.node_map, self.schedule)["matched"]
        fiscal_year = federal_fiscal_year_of(date.fromisoformat(str(loaded["table"]["effective"])))
        records, _report = ss.build_records(
            {self.NODE_ID: matched[self.NODE_ID]}, loaded["table"],
            table_url=loaded["url"], table_sha256=loaded["sha256"],
            retrieved_at=loaded["fetched_at"], fiscal_year=fiscal_year,
        )
        node = {k: v for k, v in self.node_map[self.NODE_ID].items() if k != "children"}
        record = fe.validate_record(records[self.NODE_ID], node)
        self.assertEqual(fe.classify(record), "partial")
        record["financialEvidenceStatus"] = "partial"
        for key in ("levelClaim", "rateText", "effectiveText", "table", "tableFootnotes"):
            record[key] = records[self.NODE_ID][key]
        probe = {"id": "root", "name": "Root", "type": "Foundation", "children": [
            {"id": self.PARENT_ID, "name": "Food & Drug Administration (FDA)", "type": "Agency",
             "children": [node]}]}
        stats = ss.apply_schedule_pay(probe, {self.NODE_ID: record})
        self.assertEqual(stats["priced"], 1)
        applied = probe["children"][0]["children"][0]
        pay = applied["positionSchedulePay"]
        self.assertEqual((pay["payLevel"], pay["amount"], pay["statutoryTitle"], pay["method"]),
                         ("IV", EXECUTIVE_SCHEDULE_RATES["IV"], self.TITLE, ss.METHOD_REVIEWED))
        self.assertEqual(pay["amount"], 197_200.0)
        self.assertEqual((pay["scopeMatch"], pay["financialEvidenceStatus"]), ("proxy", "partial"))
        self.assertNotIn("classTitle", pay)
        self.assertEqual(schedule_pay_violations(applied, pay, REVIEWED_TODAY, label), [])
        for field in ("sourceUrls", "sourceTypes", "lastVerified", "verificationMethod"):
            self.assertNotIn(field, applied)

    def test_the_record_on_the_deputy_and_on_other_commissioners_is_refused(self) -> None:
        good = good_reviewed_pay(self.NODE_ID)
        self.assertEqual(schedule_pay_violations(reviewed_node(self.NODE_ID), good, REVIEWED_TODAY, label), [])
        self.assertEqual(schedule_pay_violations(self.node_map[self.NODE_ID], good, REVIEWED_TODAY, label), [])
        deputy = self.node_map[self.DEPUTY_ID]
        self.assertEqual((deputy["name"], self.parent_map[self.DEPUTY_ID]), ("Deputy Commissioner", self.PARENT_ID))
        out = schedule_pay_violations(deputy, good, REVIEWED_TODAY, label)
        self.assertNotEqual(out, [])
        self.assertTrue(any("no row for" in v or "names no such post" in v for v in out), out)
        # Renamed to the row's own name, the Deputy is still refused: keyed by id.
        self.assertNotEqual(schedule_pay_violations({**deputy, "name": "Commissioner, FDA"}, good, REVIEWED_TODAY, label), [])
        for other in ("exec-dept-treasury-irs-commissioner-irs", "exec-dept-hhs-cms-administrator-cms",
                      "exec-dept-doi-bor-commissioner-bor", "exec-ind-ssa-commissioner-ssa"):
            with self.subTest(node=other):
                self.assertNotEqual(schedule_pay_violations(self.node_map[other], good, REVIEWED_TODAY, label), [])
        # And another commissioner's record on this node.
        self.assertNotEqual(schedule_pay_violations(self.node_map[self.NODE_ID],
                                                    good_reviewed_pay("exec-dept-doi-bor-commissioner-bor"),
                                                    REVIEWED_TODAY, label), [])
        # Module side: renamed or gone, the row prices nothing.
        renamed = {self.NODE_ID: {**self.node_map[self.NODE_ID], "name": "Commissioner of Food and Drugs"}}
        self.assertEqual(ss.match_reviewed_rows(renamed, self.schedule)["refusals"]["reviewed_row_node_renamed"],
                         [self.NODE_ID])
        self.assertIn(self.NODE_ID, ss.match_reviewed_rows({}, self.schedule)["refusals"]["reviewed_row_names_no_node"])

    def test_the_sentence_moved_beneath_the_notes_cut_fells_the_row_and_leaves_the_others(self) -> None:
        """Move 393(d)(1)'s sentence into the Editorial Notes, re-sign the
        digest, and the row falls while the page still carries the sentence;
        the NHTSA Administrator's row, read from the same publisher's rendering
        of another section, stands."""
        import hashlib
        import tempfile

        tmp = Path(tempfile.mkdtemp())
        for row in ss.REVIEWED_TITLE_ROWS.values():
            for name in (row["basisFixture"], row["basisFixture"] + ".meta.json"):
                (tmp / name).write_bytes((US_CODE_BASIS_FIXTURE_DIR / name).read_bytes())
        raw = (tmp / self.FIXTURE).read_text(encoding="utf-8")
        head, sep, tail = raw.partition("<strong>Editorial Notes</strong>")
        self.assertTrue(sep)
        # The page prints the sentence's quotation marks as &quot;, so the raw
        # HTML is searched and edited in that form; both readers unescape.
        printed = self.QUOTE.replace('"', "&quot;")
        self.assertIn(printed, head)
        self.assertNotIn(self.QUOTE, raw)
        self.assertNotIn(printed, tail)
        doctored = (head.replace(printed, "The Commissioner shall be appointed as the Secretary prescribes.")
                    + sep + "<p>" + printed + "</p>" + tail)
        (tmp / self.FIXTURE).write_text(doctored, encoding="utf-8")
        meta_path = tmp / (self.FIXTURE + ".meta.json")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["sha256"] = hashlib.sha256(doctored.encode("utf-8")).hexdigest()
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        nhtsa = "exec-dept-dot-nhtsa-administrator-nhtsa"
        node_map = {self.NODE_ID: dict(self.node_map[self.NODE_ID]), nhtsa: dict(self.node_map[nhtsa])}
        result = ss.match_reviewed_rows(node_map, self.schedule, directory=tmp)
        self.assertNotIn(self.NODE_ID, result["matched"])
        self.assertIn(nhtsa, result["matched"])
        self.assertEqual(result["refusals"]["reviewed_row_basis_quote_not_in_operative_text"], [self.NODE_ID])
        self.assertIn(printed, (tmp / self.FIXTURE).read_text(encoding="utf-8"))
        self.assertNotIn(self.QUOTE, ss.load_basis_section(self.FIXTURE, tmp)["operative"])
        self.assertNotIn(self.QUOTE, uscode_operative_text(tmp / self.FIXTURE))
        self.assertIn(self.QUOTE, uscode_operative_text(US_CODE_BASIS_FIXTURE_DIR / self.FIXTURE))
        # The gate refuses the same misquote on the committed fixture.
        bad = good_reviewed_pay(self.NODE_ID)
        bad["identification"]["basisQuote"] = "The Commissioner shall be appointed as the Secretary prescribes."
        out = schedule_pay_violations(self.node_map[self.NODE_ID], bad, REVIEWED_TODAY, label)
        self.assertTrue(any("not the one 21 U.S.C. 393 prints" in v for v in out), out)


if __name__ == "__main__":
    unittest.main()
