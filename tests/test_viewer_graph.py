"""The pruned copy the browser fetches, and the rule that keeps it honest.

`output/graph.json` is two things at once: the site's data and the pipeline's
own state file. It is re-fed as a payload on the next build, `merge_node`
carries forward any key it does not handle, and the Treasury family,
`synthetic` and the cost anchor exist nowhere else on disk — so a field
stripped from it is data lost, not bytes saved. The release gate,
`scripts/node_audit.py` and `scripts/nominate.py` read it too.

So it stays whole, and `output/graph.min.json` is what the browser gets:
the same tree with every field `js/` never reads removed and the whitespace
dropped. These tests pin the two halves of that bargain — the viewer copy
carries everything the page reads, and the full copy keeps everything the
pipeline needs back.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from data_pipeline.exporter.build_graph import (
    MINIMAL_GRAPH_FIELDS,
    MINIMAL_GRAPH_ROOT_FIELDS,
    prune_graph_for_viewer,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GRAPH = PROJECT_ROOT / "output" / "graph.json"
VIEWER = PROJECT_ROOT / "output" / "graph.min.json"
JS_DIR = PROJECT_ROOT / "js"

#: Fields the pipeline must get back when it re-reads its own published graph.
#: Treasury lines survive a build that was handed no statement only because
#: they are carried forward from here; `synthetic` is what keeps the receipts
#: nodes trusted by the export gate.
ROUND_TRIP_CRITICAL = (
    "rollup_total_amount", "budget_source", "treasury_row_name", "budget_as_of",
    "budget_year", "amount_kind", "source_system", "allocation_basis",
    "treasury_section", "treasury_netted", "treasury_classification_id",
    "treasury_receipts_child_id", "treasury_component_rows", "synthetic",
    "sourceUrls", "sourceTypes",
)


def walk(node):
    yield node
    for child in node.get("children") or []:
        yield from walk(child)


def js_sources() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(JS_DIR.glob("*.js")))


class PrunerTests(unittest.TestCase):
    def test_it_keeps_listed_fields_and_drops_everything_else(self):
        tree = {
            "id": "root", "name": "Root", "type": "Foundation",
            "__budgetSummary": {"label": "x"},
            "proofReason": "a build diagnostic", "costSourceCount": 3,
            "children": [{
                "id": "kid", "name": "Kid", "type": "Agency",
                "cost_status": "allocated", "resolved_total_amount": 1.0,
                "proofReason": "another", "treasury_row_name": "a line",
                "children": [],
            }],
        }
        pruned = prune_graph_for_viewer(tree)
        self.assertNotIn("proofReason", pruned)
        self.assertNotIn("costSourceCount", pruned)
        self.assertIn("__budgetSummary", pruned)
        kid = pruned["children"][0]
        self.assertEqual(kid["cost_status"], "allocated")
        self.assertNotIn("proofReason", kid)
        self.assertNotIn("treasury_row_name", kid)

    def test_root_only_fields_do_not_leak_onto_children(self):
        tree = {
            "id": "root", "name": "Root", "type": "Foundation",
            "__budgetSummary": {"label": "x"}, "relationships": [],
            "children": [{
                "id": "kid", "name": "Kid", "type": "Agency",
                "__budgetSummary": {"label": "should not survive"},
                "relationships": [{"a": 1}],
                "children": [],
            }],
        }
        pruned = prune_graph_for_viewer(tree)
        for field in MINIMAL_GRAPH_ROOT_FIELDS:
            self.assertIn(field, pruned)
            self.assertNotIn(field, pruned["children"][0])

    def test_every_node_survives_pruning(self):
        tree = {"id": "root", "name": "R", "type": "F", "children": [
            {"id": f"n{i}", "name": str(i), "type": "Agency", "children": []} for i in range(25)
        ]}
        self.assertEqual(len(list(walk(prune_graph_for_viewer(tree)))), 26)


class FieldListMatchesTheFrontendTests(unittest.TestCase):
    """The list is only safe because `js/` names every field it reads.

    There is no `Object.keys`, no `for...in` and no variable-key access on node
    data anywhere in `js/`, so a field is read only if it appears by name. If
    that ever stops being true, or if someone starts reading a field this list
    drops, these tests fail rather than the site silently losing a panel.
    """

    def test_the_frontend_does_not_enumerate_node_keys(self):
        source = js_sources()
        for construct in ("Object.keys(", "Object.entries(", "Object.values(", "hasOwnProperty"):
            self.assertNotIn(construct, source, f"{construct} in js/ would defeat the pruned copy")
        self.assertIsNone(
            re.search(r"\bfor\s*\(\s*(?:const|let|var)\s+\w+\s+in\s+", source),
            "a for...in over node data would defeat the pruned copy",
        )

    #: Names that appear in `js/` but are not a node field read off the tree.
    #: Each was checked by hand; the reason is what makes it safe to drop.
    NAMED_IN_JS_BUT_NOT_A_TREE_FIELD = {
        # graphLoader.js:167 reads it off a *raw expansion node*, and the
        # expansion overlays are not fetched. If they are ever turned back on
        # they come from expanded_nodes.json, which is not pruned.
        "attachToRoot": "read off expansion payload nodes, never off the tree",
        # graph.js uses `parentId` as a local parameter and a Map name
        # (`parentIdById`); it never reads `node.parentId` from the data.
        "parentId": "a local variable name in graph.js, not a field read",
        # ui.js reads `pay.reportedTitle` — a sub-key of positionReportedPay,
        # which is kept whole. The node-level field of the same name is the
        # one the White House expansion writes, and the panel never reads it.
        "reportedTitle": "a sub-key of positionReportedPay, not the node field",
        # ui.js compares it as a *value* of cost_validation
        # (`validation === "treasury_pool_negative"`), not as a field.
        "treasury_pool_negative": "compared as a cost_validation value, not read as a field",
    }

    def test_no_dropped_field_is_read_by_the_frontend(self):
        if not GRAPH.exists():  # pragma: no cover - the published graph is tracked
            self.skipTest("no published graph")
        graph = json.loads(GRAPH.read_text(encoding="utf-8"))
        published = set()
        for node in walk(graph):
            published.update(node.keys())
        dropped = published - set(MINIMAL_GRAPH_FIELDS) - set(MINIMAL_GRAPH_ROOT_FIELDS) - {"children"}
        self.assertTrue(dropped, "expected the viewer copy to drop something")
        source = js_sources()
        for field in sorted(dropped):
            if field in self.NAMED_IN_JS_BUT_NOT_A_TREE_FIELD:
                continue
            self.assertNotIn(
                f".{field}", source,
                f"js/ reads {field!r}, which the viewer copy drops — add it to MINIMAL_GRAPH_FIELDS",
            )
            self.assertNotIn(f'"{field}"', source, f"js/ names {field!r}, which the viewer copy drops")

    def test_the_exemptions_are_still_the_only_ones_needed(self):
        """If an exemption stops appearing in js/, drop it from the list rather
        than leaving a stale excuse that would hide a real read later."""
        source = js_sources()
        for field, reason in self.NAMED_IN_JS_BUT_NOT_A_TREE_FIELD.items():
            self.assertTrue(
                f".{field}" in source or f'"{field}"' in source,
                f"{field!r} is exempted as {reason!r} but no longer appears in js/",
            )


class PublishedViewerCopyTests(unittest.TestCase):
    def setUp(self):
        if not (GRAPH.exists() and VIEWER.exists()):  # pragma: no cover
            self.skipTest("no published graph")
        self.graph = json.loads(GRAPH.read_text(encoding="utf-8"))
        self.viewer = json.loads(VIEWER.read_text(encoding="utf-8"))

    def test_it_carries_every_node(self):
        self.assertEqual(
            [n["id"] for n in walk(self.viewer)], [n["id"] for n in walk(self.graph)])

    def test_it_is_smaller_and_minified(self):
        self.assertLess(VIEWER.stat().st_size, GRAPH.stat().st_size / 2)
        # Minified: no pretty-print newline after the opening brace.
        self.assertNotIn(b"{\n ", VIEWER.read_bytes()[:200])

    def test_the_full_graph_keeps_what_the_next_build_needs_back(self):
        """The point of having two files: this one is not pruned."""
        published = set()
        for node in walk(self.graph):
            published.update(node.keys())
        for field in ROUND_TRIP_CRITICAL:
            self.assertIn(
                field, published,
                f"{field!r} is carried forward by the next build and must stay in graph.json")

    def test_the_viewer_copy_drops_the_round_trip_fields_it_can(self):
        """...and equally, the browser has no use for them."""
        seen = set()
        for node in walk(self.viewer):
            seen.update(node.keys())
        for field in ("treasury_row_name", "treasury_component_rows", "budget_source",
                      "proofReason", "proofStatus", "existsProven", "costSourceCount"):
            self.assertNotIn(field, seen, f"{field!r} should not be shipped to the browser")

    def test_values_are_unchanged_for_the_fields_it_keeps(self):
        by_id = {n["id"]: n for n in walk(self.graph)}
        checked = 0
        for node in walk(self.viewer):
            original = by_id[node["id"]]
            for key, value in node.items():
                if key == "children":
                    continue
                self.assertEqual(value, original.get(key), f"{node['id']}.{key}")
                checked += 1
        self.assertGreater(checked, 10_000)


if __name__ == "__main__":
    unittest.main()
