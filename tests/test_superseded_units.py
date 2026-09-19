"""A unit the government has replaced: kept, not deleted, and not counted.

Governments reorganise. Until 2026-09-19 this graph had no way to say so — a
replaced unit either sat in the tree as though it still existed, which is the
site claiming something false, or would have had to be deleted, which throws
away a real record along with every source, cost and placement earned for it.

The mechanism keeps everything and marks it. What these tests pin, in both
directions, is that the marking actually does the three things it promises:
the node survives untouched, it stops taking a share of this year's money, and
the claim cannot be made without a source that says it.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from data_pipeline.exporter.build_graph import (  # noqa: E402
    LIFECYCLE_SUPERSEDED,
    MINIMAL_GRAPH_FIELDS,
    annotate_resolved_costs,
    compute_subtree_sizes,
    is_superseded_node,
)
from mark_superseded_units import OWNED_FIELDS, normalise, static_refusal  # noqa: E402


def org(node_id: str, name: str, **extra) -> dict:
    node = {"id": node_id, "name": name, "type": "Agency", "children": [], "employees": None, "budget": None}
    node.update(extra)
    return node


def tree() -> dict:
    """One parent with three children, the third replaced."""
    root = org("root", "Root")
    root["children"] = [
        org("live-a", "Live A"),
        org("live-b", "Live B"),
        org("gone", "Gone", lifecycle=LIFECYCLE_SUPERSEDED, supersededOn="2025-01-01",
            supersededBy=["live-a"], supersededSource={"url": "https://x.gov/p", "quote": "q", "readAt": "2026-09-19"}),
    ]
    return root


class PredicateTests(unittest.TestCase):
    def test_only_the_explicit_marker_counts(self) -> None:
        self.assertTrue(is_superseded_node({"lifecycle": "superseded"}))
        self.assertFalse(is_superseded_node({"lifecycle": "current"}))
        self.assertFalse(is_superseded_node({}))
        self.assertFalse(is_superseded_node(None))

    def test_it_is_never_inferred_from_a_name_or_a_type(self) -> None:
        """The marker is set by one script, from a quoted source. A node whose
        name or description merely sounds historical is not superseded."""
        self.assertFalse(is_superseded_node({"name": "Former Office of Something", "type": "Agency"}))
        self.assertFalse(is_superseded_node({"desc": "abolished in 1994", "type": "Agency"}))


class SubtreeSizeTests(unittest.TestCase):
    def test_a_replaced_unit_adds_nothing_to_its_ancestors_size(self) -> None:
        sizes = compute_subtree_sizes(tree())
        self.assertEqual(sizes["gone"], 0)
        # root counts itself and the two living children, not the third.
        self.assertEqual(sizes["root"], 3)

    def test_nothing_beneath_it_counts_either(self) -> None:
        root = tree()
        gone = next(c for c in root["children"] if c["id"] == "gone")
        gone["children"] = [org("gone-kid", "Gone Kid"), org("gone-kid-2", "Gone Kid 2")]
        sizes = compute_subtree_sizes(root)
        self.assertEqual(sizes["gone"], 0)
        self.assertEqual(sizes["root"], 3, "a replaced unit's children are history too")


class CascadeTests(unittest.TestCase):
    """The load-bearing half: a replaced unit must not divide a real pool."""

    def apply(self, root: dict) -> dict:
        annotate_resolved_costs(root, budget_summary={"government_total_outlay_amount": 300.0})
        return {node["id"]: node for node in self.walk(root)}

    @staticmethod
    def walk(node):
        yield node
        for child in node.get("children") or []:
            yield from CascadeTests.walk(child)

    def test_it_holds_no_share_and_says_why(self) -> None:
        nodes = self.apply(tree())
        gone = nodes["gone"]
        self.assertEqual(gone["cost_status"], "unavailable")
        self.assertEqual(gone["cost_validation"], "unit_superseded")
        self.assertIsNone(gone.get("resolved_total_amount"))

    def test_the_living_siblings_split_the_whole_pool(self) -> None:
        """The point of taking it out of the WEIGHTS rather than merely denying
        it a share: two live siblings get half each, not a third each with the
        remaining third going nowhere."""
        nodes = self.apply(tree())
        a, b = nodes["live-a"]["resolved_total_amount"], nodes["live-b"]["resolved_total_amount"]
        self.assertAlmostEqual(a, 150.0, places=2)
        self.assertAlmostEqual(b, 150.0, places=2)
        self.assertAlmostEqual(a + b, 300.0, places=2)

    def test_without_the_marker_the_third_sibling_dilutes_the_other_two(self) -> None:
        """The other direction, so the test cannot pass by the marker doing
        nothing: unmarked, the same tree splits three ways."""
        root = tree()
        for child in root["children"]:
            child.pop("lifecycle", None)
        nodes = self.apply(root)
        self.assertAlmostEqual(nodes["live-a"]["resolved_total_amount"], 100.0, places=2)
        self.assertAlmostEqual(nodes["gone"]["resolved_total_amount"], 100.0, places=2)


class NothingIsDeletedTests(unittest.TestCase):
    def test_the_node_keeps_everything_it_had(self) -> None:
        root = tree()
        gone = next(c for c in root["children"] if c["id"] == "gone")
        gone["desc"] = "what it did"
        gone["sourceUrls"] = ["https://x.gov/p"]
        before = {k: v for k, v in gone.items() if k != "children"}
        annotate_resolved_costs(root, budget_summary={"government_total_outlay_amount": 300.0})
        for key, value in before.items():
            if key.startswith("cost") or key in ("resolved_total_amount",):
                continue
            self.assertEqual(gone[key], value, f"{key} was changed on a replaced unit")

    def test_it_is_still_in_the_tree(self) -> None:
        root = tree()
        annotate_resolved_costs(root, budget_summary={"government_total_outlay_amount": 300.0})
        self.assertIn("gone", [c["id"] for c in root["children"]])


class ViewerFieldTests(unittest.TestCase):
    def test_the_browser_is_sent_what_it_needs_to_hide_and_explain(self) -> None:
        for field in ("lifecycle", "supersededOn", "supersededBy", "supersededSource"):
            self.assertIn(field, MINIMAL_GRAPH_FIELDS,
                          f"{field} is pruned, so the viewer could not act on it")


class WriterRefusalTests(unittest.TestCase):
    """A supersession is a positive claim. Each way of making it without a
    source is refused by name."""

    NODES = {"n1": {"id": "n1", "name": "N"}, "n2": {"id": "n2", "name": "M"}}
    TODAY = "2026-09-19"

    def row(self, **over):
        row = {"id": "n1", "url": "https://agency.gov/page", "quote": "was replaced",
               "supersededOn": "2025-01-01", "supersededBy": ["n2"]}
        row.update(over)
        return row

    def test_a_good_row_passes(self) -> None:
        self.assertIsNone(static_refusal(self.row(), self.NODES, self.TODAY))

    def test_a_missing_node_is_refused(self) -> None:
        self.assertEqual(static_refusal(self.row(id="nope"), self.NODES, self.TODAY)[0], "no_such_node")

    def test_an_unofficial_source_is_refused(self) -> None:
        for url in ("https://example.com/p", "http://agency.gov/p", ""):
            with self.subTest(url=url):
                self.assertEqual(static_refusal(self.row(url=url), self.NODES, self.TODAY)[0],
                                 "source_is_not_official")

    def test_a_row_that_quotes_nothing_is_refused(self) -> None:
        self.assertEqual(static_refusal(self.row(quote="  "), self.NODES, self.TODAY)[0], "row_quotes_nothing")

    def test_a_future_or_malformed_date_is_refused(self) -> None:
        self.assertEqual(static_refusal(self.row(supersededOn="2099-01-01"), self.NODES, self.TODAY)[0],
                         "date_is_in_the_future")
        self.assertEqual(static_refusal(self.row(supersededOn="last year"), self.NODES, self.TODAY)[0],
                         "date_is_not_an_iso_date")

    def test_a_replacement_that_is_not_a_node_is_refused(self) -> None:
        self.assertEqual(static_refusal(self.row(supersededBy=["ghost"]), self.NODES, self.TODAY)[0],
                         "replacement_is_not_a_node")

    def test_a_node_cannot_replace_itself(self) -> None:
        self.assertEqual(static_refusal(self.row(supersededBy=["n1"]), self.NODES, self.TODAY)[0],
                         "node_replaces_itself")

    def test_the_quote_is_whitespace_folded_not_otherwise_altered(self) -> None:
        """Official pages are hard-wrapped; an honest sentence-length quote
        crosses a newline. Nothing else about it is normalised."""
        self.assertEqual(normalise("the  Agency\n was   replaced"), "the Agency was replaced")
        self.assertEqual(normalise("Case-Sensitive Words"), "Case-Sensitive Words")


class TableTests(unittest.TestCase):
    def test_the_committed_table_is_well_formed_and_every_row_would_be_checked(self) -> None:
        path = PROJECT_ROOT / "data" / "curation" / "superseded.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("superseded")
        self.assertIsInstance(rows, list)
        for row in rows:
            with self.subTest(node=row.get("id")):
                for field in ("id", "url", "quote", "supersededOn"):
                    self.assertTrue(str(row.get(field) or "").strip(), f"row is missing {field}")

    def test_the_writer_owns_exactly_the_four_published_fields(self) -> None:
        """So a withdrawal is a real withdrawal: the fields it clears are the
        fields the viewer and the gate read."""
        self.assertEqual(set(OWNED_FIELDS),
                         {"lifecycle", "supersededOn", "supersededBy", "supersededSource"})


if __name__ == "__main__":
    unittest.main()
