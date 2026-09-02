"""The served review queue is repaired by stated rules and gated afterwards."""

from __future__ import annotations

import io
import json
import shutil
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path

from scripts.repair_review_queue import is_foreign, is_generated, repair, unmangle_name
from scripts.validate_published_graph import main as gate_main


TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"


def _record(name, *, parent="Department of Energy", url="https://www.energy.gov/x", method="official_directory_leadership_scan", **extra):
    return {
        "id": f"cand-{name.lower().replace(' ', '-')}",
        "name": name,
        "type": "Organization",
        "sourceUrl": url,
        "sourceUrls": [url],
        "sourceTypes": ["official_site", "candidate_discovery"],
        "possibleParent": parent,
        "discoveryMethod": method,
        "confidenceEstimate": 0.9,
        "lastVerified": "2026-03-12",
        "isCandidate": True,
        **extra,
    }


class RepairRulesTests(unittest.TestCase):
    def test_predicates(self) -> None:
        self.assertTrue(is_generated(_record("Director", url="generated://leadership/x")))
        self.assertFalse(is_generated(_record("Office of Science")))
        self.assertTrue(is_foreign(_record("Ministry of Finance", parent="Government of India")))
        self.assertTrue(is_foreign(_record("Tax Office", parent="Oberfinanzdirektion Karlsruhe")))
        self.assertFalse(is_foreign(_record("Office of Foreign Assets Control", parent="Department of the Treasury")))
        self.assertFalse(is_foreign(_record("Consulate General in Toronto", parent="Department of State")))
        self.assertEqual(unmangle_name("United States Department of Homeland SECurity"), "United States Department of Homeland Security")
        self.assertEqual(unmangle_name("Securities and Exchange Commission (SEC)"), "Securities and Exchange Commission (SEC)")

    def test_repair_drops_what_the_current_pipeline_could_not_produce(self) -> None:
        published = {"office of science", "department of energy"}
        ids_by_name = {"department of energy": "exec-dept-doe"}
        records = [
            _record("Director", url="generated://leadership/office-of-science", method="leadership_template_expansion"),
            _record("Ministry of Foreign Affairs", parent="People's Republic of China", method="wikidata_government_entity_scan"),
            _record("Office of Science"),
            _record("Office of Grid Deployment"),
            _record("Office of Grid Deployment"),
            _record("Energy and Climate SECurity Panel", parent="Unnamed Node"),
            _record("Q48759685", parent="Department of Energy", method="wikidata_government_entity_scan"),
            _record(
                "Office of Management and Budget for Review",
                url="https://www.federalregister.gov/documents/2026/x",
                method="federal_register_listing_scan",
                confidenceEstimate=0.71,
            ),
        ]
        kept, report = repair(records, published_names=published, ids_by_name=ids_by_name)
        names = [r["name"] for r in kept]
        self.assertEqual(names, ["Office of Grid Deployment", "Energy and Climate Security Panel", "Office of Management and Budget for Review"])
        self.assertEqual(report["dropped"], {
            "template_generated_source": 1,
            "non_us_public_body": 1,
            "duplicates_published_node": 1,
            "duplicate_name_and_parent": 1,
            "unlabelled_wikidata_item": 1,
        })
        self.assertEqual(report["renamed"], 1)
        grid = kept[0]
        self.assertEqual(grid["possibleParentId"], "exec-dept-doe")
        self.assertIsNone(grid["lastVerified"])
        self.assertEqual(grid["sourceCount"], 1)
        panel = kept[1]
        self.assertIsNone(panel["possibleParent"])
        self.assertIsNone(panel["possibleParentId"])
        # Rescored under the fixed classifier: a lone Federal Register notice is below 0.7.
        fr = kept[2]
        self.assertLess(fr["confidenceEstimate"], 0.7)
        self.assertGreaterEqual(report["rescored"], 1)


class ReviewQueueGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = TEST_TMP_ROOT / f"queue-gate-{uuid.uuid4().hex}"
        self.tmp_path.mkdir(parents=True, exist_ok=True)
        self.graph_path = self.tmp_path / "graph.json"
        self.graph_path.write_text(
            json.dumps(
                {
                    "id": "the-constitution-of-the-united-states",
                    "name": "The Constitution of the United States",
                    "resolved_total_amount": 100.0,
                    "cost_status": "root_total",
                    "costVerificationStatus": "verified",
                    "costSourceCount": 1,
                    "__budgetSummary": {"government_total_outlay_amount": 100.0},
                    "children": [
                        {"id": "exec-dept-doe", "name": "Department of Energy", "resolved_total_amount": 100.0, "cost_status": "allocated", "children": []}
                    ],
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_path, ignore_errors=True)

    def _gate(self, queue):
        (self.tmp_path / "candidate_nodes.json").write_text(json.dumps(queue), encoding="utf-8")
        out = io.StringIO()
        with redirect_stdout(out):
            code = gate_main(["gate", str(self.graph_path)])
        return code, out.getvalue()

    def test_a_clean_queue_passes(self) -> None:
        clean = _record("Office of Grid Deployment", possibleParentId="exec-dept-doe")
        clean.pop("lastVerified")
        code, out = self._gate([clean])
        self.assertEqual(code, 0, out)
        self.assertIn("review queue         : 1 records", out)

    def test_each_queue_violation_is_named(self) -> None:
        cases = {
            "generated": [_record("Director", url="generated://leadership/x")],
            "duplicate of published": [_record("Department of Energy")],
            "date without source": [dict(_record("Office X"), sourceUrls=[])],
            "unknown parent id": [_record("Office X", possibleParentId="nope")],
            "duplicate ids": [_record("Office X"), _record("Office X")],
        }
        for name, queue in cases.items():
            with self.subTest(case=name):
                code, out = self._gate(queue)
                self.assertEqual(code, 1, out)


if __name__ == "__main__":
    unittest.main()
