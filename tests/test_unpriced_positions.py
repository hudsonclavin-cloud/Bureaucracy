"""The unpriced-position report: complete coverage, and nothing priced in it.

The claim the prompt pack makes is that it covers EVERY position with no pay
claim. That is checkable rather than assertable, so it is checked here against
the published graph and against the generated documents themselves.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from data_pipeline.verification.pay_documents import PAY_FIELDS
from scripts.report_unpriced_positions import (
    REASONS,
    classify,
    collect,
    render_inventory,
    render_prompts,
    shard,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GRAPH = PROJECT_ROOT / "output" / "graph.json"
PROMPTS = PROJECT_ROOT / "docs" / "PAY_SOURCE_RESEARCH_PROMPT_3.md"
INVENTORY = PROJECT_ROOT / "docs" / "UNPRICED_POSITIONS.md"


def _graph():
    if not GRAPH.exists():
        return None
    return json.loads(GRAPH.read_text(encoding="utf-8"))


class CollectTests(unittest.TestCase):
    def test_a_priced_position_is_never_listed(self):
        graph = _graph()
        if graph is None:
            self.skipTest("no published graph")
        groups, positions, priced = collect(graph)
        listed = {row["id"] for rows in groups.values() for row in rows}
        stack = [graph]
        while stack:
            node = stack.pop()
            if any(isinstance(node.get(field), dict) for field in PAY_FIELDS):
                self.assertNotIn(node.get("id"), listed, "a priced position is in the unpriced list")
            stack.extend(node.get("children") or [])
        self.assertEqual(positions, priced + len(listed))

    def test_every_unpriced_position_is_listed(self):
        graph = _graph()
        if graph is None:
            self.skipTest("no published graph")
        groups, _, _ = collect(graph)
        listed = {row["id"] for rows in groups.values() for row in rows}
        stack = [graph]
        missing = []
        while stack:
            node = stack.pop()
            if "position" in str(node.get("type") or "").casefold() and not any(
                isinstance(node.get(field), dict) for field in PAY_FIELDS
            ):
                if node.get("id") not in listed:
                    missing.append(node.get("id"))
            stack.extend(node.get("children") or [])
        self.assertEqual([], missing)

    def test_every_reason_is_one_the_documents_explain(self):
        graph = _graph()
        if graph is None:
            self.skipTest("no published graph")
        groups, _, _ = collect(graph)
        for rows in groups.values():
            for row in rows:
                self.assertIn(row["reason"], REASONS)

    def test_a_multiplicity_node_is_classified_as_one(self):
        self.assertEqual("multiplicity", classify({"representsPosts": {"text": "×18"}}))

    def test_a_listed_node_with_no_rate_is_classified_as_one(self):
        self.assertEqual("listed_no_rate", classify({"positionListing": {"payLevel": "IV"}}))
        self.assertEqual("listed_no_rate", classify({"positionCurrentListing": {"payPlan": "ES"}}))

    def test_an_unreached_node_is_classified_as_one(self):
        self.assertEqual("unreached", classify({"name": "Canteen Chief"}))


class ShardTests(unittest.TestCase):
    def test_sharding_is_complete_and_disjoint(self):
        groups = {
            ("a", "A"): [{"id": "a{}".format(i), "name": "x", "reason": "unreached"} for i in range(50)],
            ("b", "B"): [{"id": "b{}".format(i), "name": "x", "reason": "unreached"} for i in range(80)],
            ("c", "C"): [{"id": "c{}".format(i), "name": "x", "reason": "unreached"} for i in range(5)],
        }
        shards = shard(groups, 60)
        seen = [row["id"] for entries in shards for _, rows in entries for row in rows]
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(sorted(seen), sorted(row["id"] for rows in groups.values() for row in rows))

    def test_an_organisation_is_never_split_across_two_shards(self):
        """The pay system is a fact about the employer, so one agency's titles
        are asked about together or the same structural question gets asked
        twice and answered twice."""
        groups = {
            ("a", "A"): [{"id": "a{}".format(i), "name": "x", "reason": "unreached"} for i in range(200)],
            ("b", "B"): [{"id": "b{}".format(i), "name": "x", "reason": "unreached"} for i in range(10)],
        }
        shards = shard(groups, 60)
        for entries in shards:
            keys = [key for key, _ in entries]
            self.assertEqual(len(keys), len(set(keys)))
        placed = {}
        for index, entries in enumerate(shards):
            for key, _ in entries:
                self.assertNotIn(key, placed, "{} appears in two shards".format(key))
                placed[key] = index


class GeneratedDocumentTests(unittest.TestCase):
    """The committed documents are the ones this code produces right now."""

    def test_the_prompt_pack_is_current(self):
        graph = _graph()
        if graph is None or not PROMPTS.exists():
            self.skipTest("no published graph or no prompt pack")
        groups, positions, priced = collect(graph)
        rows = [row for group in groups.values() for row in group]
        counts: dict[str, int] = {}
        for row in rows:
            counts[row["reason"]] = counts.get(row["reason"], 0) + 1
        expected = render_prompts(shard(groups, 110), (positions, priced, len(rows), counts))
        self.assertEqual(
            expected, PROMPTS.read_text(encoding="utf-8"),
            "docs/PAY_SOURCE_RESEARCH_PROMPT_3.md is stale; re-run scripts/report_unpriced_positions.py")

    def test_the_inventory_is_current(self):
        graph = _graph()
        if graph is None or not INVENTORY.exists():
            self.skipTest("no published graph or no inventory")
        groups, positions, priced = collect(graph)
        rows = [row for group in groups.values() for row in group]
        counts: dict[str, int] = {}
        for row in rows:
            counts[row["reason"]] = counts.get(row["reason"], 0) + 1
        expected = render_inventory(groups, (positions, priced, len(rows), counts))
        self.assertEqual(
            expected, INVENTORY.read_text(encoding="utf-8"),
            "docs/UNPRICED_POSITIONS.md is stale; re-run scripts/report_unpriced_positions.py")

    def test_every_unpriced_node_id_appears_in_the_prompt_pack(self):
        graph = _graph()
        if graph is None or not PROMPTS.exists():
            self.skipTest("no published graph or no prompt pack")
        text = PROMPTS.read_text(encoding="utf-8")
        groups, _, _ = collect(graph)
        missing = [row["id"] for rows in groups.values() for row in rows if row["id"] not in text]
        self.assertEqual([], missing[:20])

    def test_the_pack_refuses_third_party_salary_sites(self):
        if not PROMPTS.exists():
            self.skipTest("no prompt pack")
        text = PROMPTS.read_text(encoding="utf-8")
        self.assertIn("FederalPay.org", text)
        self.assertIn("third-party republication", text)

    def test_the_pack_asks_for_the_document_and_not_only_the_figure(self):
        if not PROMPTS.exists():
            self.skipTest("no prompt pack")
        text = PROMPTS.read_text(encoding="utf-8")
        self.assertIn("document URL", text)
        self.assertIn("A missing answer is a result", text)
        self.assertIn("Never estimate, never average, never interpolate", text)

    def test_only_the_lead_prompt_carries_the_follow_up_directive(self):
        """Enumeration passes are exempt from the chain directive; expansion
        there buries the per-title verdicts the shard exists to produce."""
        if not PROMPTS.exists():
            self.skipTest("no prompt pack")
        text = PROMPTS.read_text(encoding="utf-8")
        self.assertEqual(1, text.count("FOLLOW-UP CHAIN DIRECTIVE"))
        self.assertLess(text.index("FOLLOW-UP CHAIN DIRECTIVE"), text.index("## Prompt 1"))


if __name__ == "__main__":
    unittest.main()
