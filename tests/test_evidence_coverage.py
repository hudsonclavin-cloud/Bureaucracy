"""The evidence-coverage inventory: every current organisation in exactly one
class, the criterion-3 gap as one number, and the committed document equal to
what the script renders from the published graph."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from data_pipeline.verification.no_document import FIELD, is_current_organisation
from data_pipeline.verification import name_decisions
from scripts.report_evidence_coverage import CLASSES, GAP_CLASSES, ROOT_ID, classify, collect, render, walk

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GRAPH = PROJECT_ROOT / "output" / "graph.json"
DOC = PROJECT_ROOT / "docs" / "EVIDENCE_COVERAGE.md"


def _graph():
    if not GRAPH.exists():
        return None
    return json.loads(GRAPH.read_text(encoding="utf-8"))


class PartitionTests(unittest.TestCase):
    def test_every_current_organisation_lands_in_exactly_one_known_class(self):
        graph = _graph()
        if graph is None:
            self.skipTest("no published graph")
        rows = collect(graph)
        self.assertEqual(rows.get("other", []), [], "an organisation fell outside every class")
        counted = sum(len(v) for v in rows.values())
        population = sum(1 for n, _ in walk(graph) if n.get("id") != ROOT_ID and is_current_organisation(n))
        self.assertEqual(counted, population)
        self.assertTrue(set(rows) <= set(CLASSES))

    def test_the_gap_is_the_gates_own_count(self):
        """The report's gap and the gate's "evidence gap" line count the same
        organisations: no method, no unread record, no recorded reason."""
        graph = _graph()
        if graph is None:
            self.skipTest("no published graph")
        rows = collect(graph)
        gap = {r["id"] for cls in GAP_CLASSES for r in rows.get(cls, [])}
        nodes = [n for n, _ in walk(graph)]
        decided, _refused = name_decisions.decided_ids(nodes)
        expected = {
            str(n.get("id"))
            for n in nodes
            if n.get("id") != ROOT_ID and is_current_organisation(n)
            and not n.get("verificationMethod") and not isinstance(n.get("verificationUnread"), dict)
            and (n.get("verificationFailure") or not isinstance(n.get(FIELD), dict))
            and str(n.get("id")) not in decided
        }
        self.assertEqual(gap, expected)

    def test_classify_in_both_directions(self):
        self.assertEqual(classify({"verificationMethod": "name_labelled_on_own_official_page"}), "method_page")
        self.assertEqual(classify({"verificationMethod": "listed_in_us_government_manual"}), "method_list")
        self.assertEqual(classify({"verificationUnread": {"kind": "host_refuses_crawler"}}), "unread")
        self.assertEqual(classify({FIELD: {"kind": "editorial_grouping"}}), "no_document_editorial_grouping")
        self.assertEqual(classify({FIELD: {"kind": "curated_count_label"}}), "no_document_curated_count_label")
        self.assertEqual(classify({"verificationFailure": "not_found"}), "negative_read")
        # a read document's negative outranks a recorded reason on the same node
        self.assertEqual(classify({"verificationFailure": "not_in_official_list", FIELD: {"kind": "name_too_generic"}}), "negative_read")
        self.assertEqual(classify({}), "unrecorded")
        # a standing decision explains a negative; it never removes one and
        # never stands in for one that is not there
        self.assertEqual(classify({"id": "a", "verificationFailure": "not_found"}, frozenset({"a"})), "decided_negative")
        self.assertEqual(classify({"id": "b", "verificationFailure": "not_found"}, frozenset({"a"})), "negative_read")
        self.assertEqual(classify({"id": "a"}, frozenset({"a"})), "unrecorded")
        self.assertEqual(classify({"id": "a", "verificationMethod": "listed_in_us_government_manual", "verificationFailure": "not_found"}, frozenset({"a"})), "method_list")
        # a method wins over everything; an unread record over a block; an
        # invented kind is not a recorded reason
        self.assertEqual(classify({"verificationMethod": "listed_in_us_government_manual", FIELD: {"kind": "editorial_grouping"}}), "method_list")
        self.assertEqual(classify({"verificationUnread": {"kind": "page_not_found"}, FIELD: {"kind": "editorial_grouping"}}), "unread")
        self.assertEqual(classify({FIELD: {"kind": "vibes"}}), "unrecorded")
        self.assertEqual(classify({"sourceUrls": ["https://x.gov/"]}), "other")


class DocumentTests(unittest.TestCase):
    def test_the_committed_document_is_what_the_graph_renders(self):
        graph = _graph()
        if graph is None or not DOC.exists():
            self.skipTest("no published graph or no committed document")
        self.assertEqual(DOC.read_text(encoding="utf-8"), render(collect(graph)))

    def test_the_document_names_every_class_that_has_a_node_and_the_gap(self):
        graph = _graph()
        if graph is None:
            self.skipTest("no published graph")
        rows = collect(graph)
        text = render(rows)
        for cls, (heading, _, _) in CLASSES.items():
            if rows.get(cls):
                self.assertIn(heading, text)
        self.assertIn("criterion 3 gap", text)
        self.assertNotIn("Unclassified", text)


if __name__ == "__main__":
    unittest.main()
