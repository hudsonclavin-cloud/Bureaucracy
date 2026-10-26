"""A rebuild handed no Monthly Treasury Statement must publish the same graph as
one handed the statement it already carries. The first scheduled run on GitHub's
runner found that it did not: nothing was due, so the rebuild read no statement,
took the carry-forward path and dropped `attachToRoot` from the government-wide
receipts line, so 62 nodes differed with no new data. The budget now holds such a
build (`rebuilt_without_a_statement`); this pins the cause."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.exporter.build_graph import UNDISTRIBUTED_NODE_ID, mark_government_wide_receipts_attached  # noqa: E402

PUBLISHED = PROJECT_ROOT / "output" / "graph.json"


def nodes_of(graph):
    out, stack = {}, [graph]
    while stack:
        node = stack.pop()
        out[node["id"]] = node
        stack.extend(node.get("children") or [])
    return out


class MarkTests(unittest.TestCase):
    def test_the_line_is_attached_to_the_root_and_nothing_else_is(self):
        root = {"id": "root", "children": [{"id": "a", "children": []}, {"id": UNDISTRIBUTED_NODE_ID, "children": []}]}
        self.assertEqual(mark_government_wide_receipts_attached(root), 1)
        self.assertTrue(root["children"][1]["attachToRoot"])
        self.assertNotIn("attachToRoot", root["children"][0])
        self.assertEqual(mark_government_wide_receipts_attached(root), 0, "idempotent")

    def test_the_line_is_only_marked_where_it_is_a_child_of_the_root(self):
        root = {"id": "root", "children": [{"id": "a", "children": [{"id": UNDISTRIBUTED_NODE_ID, "children": []}]}]}
        self.assertEqual(mark_government_wide_receipts_attached(root), 0)


class RebuildEqualityTests(unittest.TestCase):
    def test_a_rebuild_with_no_statement_equals_the_published_graph_node_for_node(self):
        if not PUBLISHED.is_file():
            self.skipTest("no published graph")
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / "regenerate_published_graph.py"), "--output-dir", tmp],
                                    cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=900)
            self.assertEqual(result.returncode, 0, result.stdout[-800:] + result.stderr[-800:])
            rebuilt = json.loads((Path(tmp) / "graph.json").read_text(encoding="utf-8"))
        published = json.loads(PUBLISHED.read_text(encoding="utf-8"))
        a, b = nodes_of(published), nodes_of(rebuilt)
        self.assertEqual(set(a), set(b))
        different = []
        for node_id in a:
            fields = [k for k in set(a[node_id]) | set(b[node_id]) if k != "children" and a[node_id].get(k) != b[node_id].get(k)]
            if fields and node_id != published["id"]:
                different.append((node_id, fields))
        self.assertEqual(different, [])
        # at the root only the two things that say how this build was made may differ
        root_fields = {k for k in set(published) | set(rebuilt) if k != "children" and published.get(k) != rebuilt.get(k)}
        self.assertLessEqual(root_fields, {"__budgetSummary", "__sourceRegistry"})
        stamped = {k for k in set(published["__budgetSummary"]) | set(rebuilt["__budgetSummary"])
                   if published["__budgetSummary"].get(k) != rebuilt["__budgetSummary"].get(k)}
        self.assertEqual(stamped, {"reused_from_previous_build"})


if __name__ == "__main__":
    unittest.main()
