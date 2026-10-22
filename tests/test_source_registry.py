"""The source registry (criterion 6): every row re-adjudicates against the
fixtures and the graph, the module and the gate derive the same block, the
status arithmetic turns over on the right day, the published graph carries the
block on its root alone, the gate refuses each corruption, and the committed
document is what the script renders."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT, PROJECT_ROOT / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import validate_published_graph as gate  # noqa: E402
from data_pipeline import freshness as fr  # noqa: E402
from data_pipeline.exporter.build_graph import MINIMAL_GRAPH_ROOT_FIELDS  # noqa: E402
from scripts.report_source_registry import render  # noqa: E402

PUBLISHED = PROJECT_ROOT / "output" / "graph.json"
DOC = PROJECT_ROOT / "docs" / "SOURCE_REGISTRY.md"


class DateArithmeticTests(unittest.TestCase):
    def test_period_ends_roll_to_month_ends(self):
        self.assertEqual(fr.add_months_to_period_end(date(2026, 8, 31), 1), date(2026, 9, 30))
        self.assertEqual(fr.add_months_to_period_end(date(2026, 1, 31), 1), date(2026, 2, 28))
        self.assertEqual(fr.add_months_to_period_end(date(2026, 6, 30), 3), date(2026, 9, 30))
        self.assertEqual(fr.add_months_to_period_end(date(2025, 9, 30), 12), date(2026, 9, 30))

    def test_fixed_month_day_is_strictly_after_the_copy(self):
        self.assertEqual(fr.next_fixed_month_day(date(2026, 7, 1), 7, 1), date(2027, 7, 1))
        self.assertEqual(fr.next_fixed_month_day(date(2026, 6, 30), 7, 1), date(2026, 7, 1))

    def test_transforms(self):
        self.assertEqual(fr.transform_date("2025", "fiscal_year_end"), date(2025, 9, 30))
        self.assertEqual(fr.transform_date("2025-03", "month_end"), date(2025, 3, 31))
        self.assertEqual(fr.transform_date("2026-09-17T16:18:33Z", None), date(2026, 9, 17))
        self.assertIsNone(fr.transform_date("", None))

    def test_status_turns_over_on_the_stated_days(self):
        cadence = {"kind": "period_end_monthly", "lagDays": 20, "overdueMarginDays": 30}
        expected = fr.expected_of(cadence, date(2026, 8, 31), None)
        self.assertEqual(expected, {"next": "2026-09-30", "expectedBy": "2026-10-20", "overdueAfter": "2026-11-19", "recheckDue": None})
        self.assertEqual(fr.status_at(date(2026, 10, 20), "period_end_monthly", date(2026, 8, 31), expected), fr.STATUS_CURRENT)
        self.assertEqual(fr.status_at(date(2026, 10, 21), "period_end_monthly", date(2026, 8, 31), expected), fr.STATUS_EXPECTED)
        self.assertEqual(fr.status_at(date(2026, 11, 19), "period_end_monthly", date(2026, 8, 31), expected), fr.STATUS_EXPECTED)
        self.assertEqual(fr.status_at(date(2026, 11, 20), "period_end_monthly", date(2026, 8, 31), expected), fr.STATUS_OVERDUE)
        recheck = fr.expected_of({"kind": "on_republication", "recheckDays": 90}, date(2026, 9, 21), date(2026, 9, 21))
        self.assertEqual(recheck["recheckDue"], "2026-12-20")
        self.assertEqual(fr.status_at(date(2026, 12, 20), "on_republication", date(2026, 9, 21), recheck), fr.STATUS_CURRENT)
        self.assertEqual(fr.status_at(date(2026, 12, 21), "on_republication", date(2026, 9, 21), recheck), fr.STATUS_RECHECK)
        self.assertEqual(fr.status_at(date(2030, 1, 1), "closed_record", None, {}), fr.STATUS_CLOSED)
        self.assertEqual(fr.status_at(date(2030, 1, 1), "period_end_monthly", None, {}), fr.STATUS_UNKNOWN)

    def test_a_refusal_record_is_not_a_copy(self):
        # dfas/ holds only refusals (no sha256): no copy, no fetch date
        self.assertEqual(fr.fixture_metas(["dfas"]), [])
        self.assertTrue(fr.fixture_metas(["opm/pay"]))


class RegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not PUBLISHED.is_file():
            raise unittest.SkipTest("no published graph")
        cls.graph = json.loads(PUBLISHED.read_text(encoding="utf-8"))
        cls.registry = fr.load_registry()
        cls.as_of = fr.parse_date(cls.graph[fr.ROOT_FIELD]["asOf"])
        cls.block, cls.refused = fr.derive(cls.graph, cls.registry, cls.as_of)

    def test_every_row_re_adjudicates_and_the_vocabularies_are_closed(self):
        self.assertEqual(self.refused, [], self.refused)
        ids = [r["id"] for r in self.registry["sources"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(ids), 20)
        for row in self.registry["sources"]:
            with self.subTest(row=row["id"]):
                self.assertEqual(fr.validate_row(row), [])
                self.assertIn(row["cadence"]["kind"], fr.CADENCE_KINDS)
                self.assertIn(row["copy"]["kind"], fr.COPY_KINDS)
                self.assertIn(row["fetch"]["kind"], fr.FETCH_KINDS)

    def test_every_source_feeds_a_field_some_node_carries(self):
        nodes = list(fr.walk(self.graph))
        self.assertEqual(self.block["unused"], [], "every registry row reaches the published graph")
        for entry in self.block["sources"]:
            with self.subTest(source=entry["id"]):
                self.assertTrue(any(fr.node_uses_source(n, entry["graphFields"]) for n in nodes))

    def test_a_source_the_graph_does_not_use_is_listed_unused_not_published(self):
        small = {"id": "the-constitution-of-the-united-states", "name": "R", "type": "Foundation", "cost_status": "root_total",
                 "__budgetSummary": {"record_date": "2026-06-30"}, "children": []}
        block, refused = fr.derive(small, self.registry, date(2026, 10, 22))
        self.assertEqual(refused, [])
        self.assertEqual([e["id"] for e in block["sources"]], ["monthly_treasury_statement"])
        self.assertIn("opm_fedscope_employment", block["unused"])
        gate_block, _ = gate.source_registry_expected(small, self.registry, date(2026, 10, 22))
        self.assertEqual(gate_block, block)

    def test_the_published_root_block_is_the_derivation_and_sits_on_the_root_alone(self):
        self.assertIn(fr.ROOT_FIELD, MINIMAL_GRAPH_ROOT_FIELDS)
        self.assertEqual(self.graph[fr.ROOT_FIELD], self.block)
        for node in fr.walk(self.graph):
            if node is not self.graph:
                self.assertNotIn(fr.ROOT_FIELD, node)
        self.assertEqual(gate.source_registry_violations(self.graph, gate.label), [])

    def test_the_gate_mirror_equals_the_module(self):
        for as_of in (self.as_of, date(2026, 12, 1), date(2027, 6, 1), date(2028, 1, 1)):
            with self.subTest(as_of=as_of):
                mine, refused = fr.derive(self.graph, self.registry, as_of)
                theirs, refused_gate = gate.source_registry_expected(self.graph, self.registry, as_of)
                self.assertEqual(theirs, mine)
                self.assertEqual([r["id"] for r in refused_gate], [r["id"] for r in refused])

    def test_the_known_states_on_the_published_graph(self):
        by_id = {e["id"]: e for e in self.block["sources"]}
        mts = by_id["monthly_treasury_statement"]
        self.assertEqual(mts["copy"]["date"], str(self.graph["__budgetSummary"]["record_date"])[:10])
        self.assertEqual(mts["expected"]["next"], fr.add_months_to_period_end(fr.parse_date(mts["copy"]["date"]), 1).isoformat())
        self.assertEqual(by_id["opm_plum_archive"]["statusAtBuild"], fr.STATUS_CLOSED)
        self.assertEqual(by_id["whitehouse_staff_report"]["copy"]["graphCheck"], "holds")
        self.assertEqual(by_id["official_pages"]["perNodeDate"], "lastVerified")
        self.assertIsNone(by_id["monthly_treasury_statement"]["perNodeDate"])
        # the two sources whose next edition is past the margin as of this build
        self.assertEqual(by_id["opm_fedscope_employment"]["statusAtBuild"], fr.STATUS_OVERDUE)
        self.assertEqual(by_id["doj_usao_ad_pay_plan"]["statusAtBuild"], fr.STATUS_OVERDUE)

    def test_the_committed_document_is_what_the_script_renders(self):
        if not DOC.exists():
            self.skipTest("no committed document")
        self.assertEqual(DOC.read_text(encoding="utf-8"), render(self.block, self.refused))


class GateCorruptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not PUBLISHED.is_file():
            raise unittest.SkipTest("no published graph")
        cls.graph = json.loads(PUBLISHED.read_text(encoding="utf-8"))

    def _violations(self, corrupt):
        graph = copy.deepcopy(self.graph)
        corrupt(graph, graph[fr.ROOT_FIELD])
        return gate.source_registry_violations(graph, gate.label)

    def test_each_corruption_is_refused(self):
        def entry(block, source_id):
            return next(e for e in block["sources"] if e["id"] == source_id)
        cases = {
            "the block removed": lambda g, b: g.pop(fr.ROOT_FIELD),
            "not an object": lambda g, b: g.__setitem__(fr.ROOT_FIELD, "yes"),
            "a source dropped": lambda g, b: b["sources"].pop(),
            "a source invented": lambda g, b: b["sources"].append(dict(b["sources"][0], id="made_up")),
            "a copy date changed": lambda g, b: entry(b, "monthly_treasury_statement")["copy"].__setitem__("date", "2026-09-30"),
            "an expected date changed": lambda g, b: entry(b, "monthly_treasury_statement")["expected"].__setitem__("expectedBy", "2030-01-01"),
            "a status relabelled": lambda g, b: entry(b, "opm_fedscope_employment").__setitem__("statusAtBuild", "current"),
            "a status outside the vocabulary": lambda g, b: entry(b, "opm_plum_archive").__setitem__("statusAtBuild", "fresh"),
            "a cadence changed": lambda g, b: entry(b, "opm_fedscope_employment")["cadence"].__setitem__("lagDays", 900),
            "a label changed": lambda g, b: entry(b, "us_government_manual").__setitem__("label", "Some other book"),
            "graphFields widened": lambda g, b: entry(b, "va_title38_pay_tables")["graphFields"].append("positionStatutoryPay"),
            "counts altered": lambda g, b: b["counts"].__setitem__("overdue", 0),
            "asOf moved to the future": lambda g, b: b.__setitem__("asOf", "2099-01-01"),
            "asOf moved": lambda g, b: b.__setitem__("asOf", "2026-01-01"),
            "an extra key on the block": lambda g, b: b.__setitem__("note", "x"),
            "an unused source invented": lambda g, b: b["unused"].append("made_up"),
            "an extra key on an entry": lambda g, b: entry(b, "omb_public_budget_database").__setitem__("sentence", "x"),
            "the block copied onto a child": lambda g, b: g["children"][0].__setitem__(fr.ROOT_FIELD, dict(b)),
            "lastReadAfterExpected flipped": lambda g, b: entry(b, "opm_fedscope_employment").__setitem__("lastReadAfterExpected", False),
            "perNodeDate invented": lambda g, b: entry(b, "monthly_treasury_statement").__setitem__("perNodeDate", "lastVerified"),
        }
        for name, corrupt in cases.items():
            with self.subTest(case=name):
                self.assertNotEqual(self._violations(corrupt), [], name)

    def test_a_registry_row_that_does_not_re_adjudicate_is_refused(self):
        registry = copy.deepcopy(fr.load_registry())
        registry["sources"][0]["cadence"]["kind"] = "whenever"
        registry["sources"].append(dict(registry["sources"][1], id=registry["sources"][1]["id"]))
        stated = next(r for r in registry["sources"] if r["copy"]["kind"] == "stated")
        stated["copy"]["graphCheck"]["equals"] = "not what the graph says"
        block, refused = fr.derive(self.graph, registry, date(2026, 10, 22))
        reasons = {r["id"]: r["problems"] for r in refused}
        self.assertIn(registry["sources"][0]["id"], reasons)
        self.assertTrue(any("second row" in p or "duplicate" in p for ps in reasons.values() for p in ps))
        self.assertTrue(any("graphCheck" in p for p in reasons.get(stated["id"], [])))
        self.assertNotIn(stated["id"], {e["id"] for e in block["sources"]})


if __name__ == "__main__":
    unittest.main()
