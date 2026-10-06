"""Research prompt pack 4: every unpriced post and every estimate covered once.

The pack claims the top-100 prompt and the remainder shards together name
every position with no pay claim exactly once, and every organisation that
publishes an apportioned estimate. Checked against the published graph and
against the committed documents, which must equal a fresh render byte for byte.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from data_pipeline.verification.pay_documents import PAY_FIELDS
from scripts.report_unpriced_positions import NOT_RESEARCHED, collect as collect_unpriced
from scripts.report_research_prompts import (
    ORG_CLASSES,
    TOP_FAMILIES,
    build,
    family_name,
    rank_families,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GRAPH = PROJECT_ROOT / "output" / "graph.json"
TOP = PROJECT_ROOT / "docs" / "RESEARCH_PROMPT_4_TOP100.md"
REMAINDER = PROJECT_ROOT / "docs" / "RESEARCH_PROMPT_4_REMAINDER.md"


def _graph():
    if not GRAPH.exists():
        return None
    return json.loads(GRAPH.read_text(encoding="utf-8"))


class FamilyNameTests(unittest.TestCase):
    def test_copies_of_one_title_share_a_family(self):
        self.assertEqual(family_name("Physician (×multiple)"), "Physician")
        self.assertEqual(family_name("Chief Medical Officer, VISN 12"), "Chief Medical Officer")
        self.assertEqual(
            family_name("Regional Counsel, Region IV — Southeast"), "Regional Counsel"
        )
        self.assertEqual(family_name("Inspector General (DoJ IG covers FBI)"), "Inspector General")

    def test_a_different_title_is_a_different_family(self):
        # The dash qualifier names the post, so it is kept.
        self.assertNotEqual(family_name("Chief — Medicine Service"), family_name("Chief — Surgery Service"))
        self.assertNotEqual(family_name("Deputy Director"), family_name("Director"))

    def test_ranking_is_by_nodes_held_then_organisations(self):
        posts = [
            {"id": f"a{i}", "name": "Alpha", "family": "Alpha", "reason": "unreached",
             "parentId": f"p{i}", "parentName": f"P{i}", "grandName": "G", "replaced": False}
            for i in range(3)
        ] + [
            {"id": f"b{i}", "name": "Beta", "family": "Beta", "reason": "unreached",
             "parentId": "q", "parentName": "Q", "grandName": "G", "replaced": False}
            for i in range(3)
        ] + [
            {"id": "c0", "name": "Gamma", "family": "Gamma", "reason": "unreached",
             "parentId": "r", "parentName": "R", "grandName": "G", "replaced": False}
        ]
        families = rank_families(posts)
        self.assertEqual([f["name"] for f in families], ["Alpha", "Beta", "Gamma"])
        self.assertEqual([f["code"] for f in families], ["F001", "F002", "F003"])


class PublishedPackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = _graph()
        if cls.graph is None:
            raise unittest.SkipTest("no published graph")
        cls.posts, cls.orgs, cls.families, cls.top_text, cls.remainder_text = build(cls.graph)

    def test_committed_documents_equal_a_fresh_render(self):
        self.assertEqual(TOP.read_text(encoding="utf-8"), self.top_text,
                         "RESEARCH_PROMPT_4_TOP100.md is stale; run scripts/report_research_prompts.py")
        self.assertEqual(REMAINDER.read_text(encoding="utf-8"), self.remainder_text,
                         "RESEARCH_PROMPT_4_REMAINDER.md is stale; run scripts/report_research_prompts.py")

    def test_every_unpriced_post_is_named_exactly_once(self):
        expected = set()
        stack = [self.graph]
        while stack:
            node = stack.pop()
            stack.extend(node.get("children") or [])
            if "position" not in str(node.get("type") or "").casefold():
                continue
            if any(isinstance(node.get(field), dict) for field in PAY_FIELDS):
                continue
            expected.add(node["id"])
        # Paused and unpaid posts are not research work (the owner's decisions of
        # 2026-10-07); the unpriced inventory still lists them.
        groups, _, _, _ = collect_unpriced(self.graph)
        not_asked = {row["id"] for rows in groups.values() for row in rows if row["reason"] in NOT_RESEARCHED}
        self.assertGreater(len(not_asked), 0)
        expected -= not_asked
        self.assertEqual({p["id"] for p in self.posts}, expected)

        appendix = self.top_text.split("## Appendix", 1)[1]
        in_top = re.findall(r"^- `([^`]+)` — ", appendix, flags=re.M)
        part_a = self.remainder_text.split("# Part B", 1)[0]
        in_rest = re.findall(r"^- ([^\s|]+) \| ", part_a, flags=re.M)
        named = in_top + in_rest
        self.assertEqual(len(named), len(set(named)), "a post is named twice")
        self.assertEqual(set(named), expected)

    def test_no_priced_post_is_named(self):
        priced = set()
        stack = [self.graph]
        while stack:
            node = stack.pop()
            stack.extend(node.get("children") or [])
            if any(isinstance(node.get(field), dict) for field in PAY_FIELDS):
                priced.add(node["id"])
        for node_id in priced:
            self.assertNotIn(f"`{node_id}`", self.top_text)
            self.assertNotIn(f"- {node_id} |", self.remainder_text)

    def test_top_prompt_names_the_top_families_in_rank_order(self):
        prompt = self.top_text.split("```", 2)[1]
        codes = re.findall(r"^(F\d{3}) \| ", prompt, flags=re.M)
        self.assertEqual(codes, [f"F{i:03d}" for i in range(1, min(TOP_FAMILIES, len(self.families)) + 1)])
        sizes = [len(f["rows"]) for f in self.families[:TOP_FAMILIES]]
        self.assertEqual(sizes, sorted(sizes, reverse=True))
        rest = self.families[TOP_FAMILIES:]
        if rest:
            self.assertGreaterEqual(sizes[-1], len(rest[0]["rows"]))

    def test_every_estimate_organisation_is_named_once(self):
        part_b = self.remainder_text.split("# Part B", 1)[1]
        named = re.findall(r"^- ([^\s|]+) \| ", part_b, flags=re.M)
        self.assertEqual(len(named), len(set(named)))
        self.assertEqual(set(named), {o["id"] for o in self.orgs})
        self.assertEqual({o["class"] for o in self.orgs} - set(ORG_CLASSES), set())

    def test_the_big_prompt_carries_the_directive_and_the_shards_do_not(self):
        prompt = self.top_text.split("```", 2)[1]
        self.assertIn("FOLLOW-UP CHAIN DIRECTIVE", prompt)
        self.assertIn("MORE THAN ONE family", prompt)
        self.assertNotIn("FOLLOW-UP CHAIN DIRECTIVE", self.remainder_text)
        self.assertEqual(self.remainder_text.count("END with a section titled LOAD-BEARING NUMBERS"),
                         self.remainder_text.count("## Prompt "))

    def test_no_aggregator_is_offered_as_an_authority(self):
        for text in (self.top_text, self.remainder_text):
            # Hard-wrapped, so judge each bullet or paragraph, not each line.
            for block in re.split(r"\n(?=\s*-\s)|\n\s*\n", text):
                if "federalpay.org" in block.casefold() or "govsalaries" in block.casefold():
                    self.assertRegex(block.casefold(), r"\bnot\b|never|republication")


if __name__ == "__main__":
    unittest.main()
