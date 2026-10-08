"""FedScope payroll: the module, the gate mirror, and the gate in both directions."""
from __future__ import annotations

import copy
import json
import re
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import validate_published_graph as gate  # noqa: E402
from data_pipeline.verification import fedscope_payroll as fp  # noqa: E402
from data_pipeline.verification.headcounts import COVERAGE_STATEMENT, DEFAULT_FEDSCOPE_ZIP  # noqa: E402
from data_pipeline.verification.omb_budget import guide_text  # noqa: E402

GRAPH = PROJECT_ROOT / "output" / "graph.json"
DICTIONARY = PROJECT_ROOT / "tests" / "fixtures" / "opm" / "fedscope" / "fedscope_employment_summary_2025-03_data_dictionary.pdf"


def label(node):
    return node.get("id")


def walk(node):
    yield node
    for child in node.get("children") or []:
        yield from walk(child)


class MirrorTests(unittest.TestCase):
    def test_constants_pinned(self):
        self.assertEqual(gate.FEDSCOPE_PAYROLL_SOURCE, fp.PAYROLL_SOURCE)
        self.assertEqual(gate.FEDSCOPE_AVGSAL_DEFINITION, fp.AVGSAL_DEFINITION)
        self.assertEqual(gate.FEDSCOPE_PAYROLL_COVERAGE, COVERAGE_STATEMENT)
        self.assertEqual(gate.FEDSCOPE_PAYROLL_ZIP, DEFAULT_FEDSCOPE_ZIP)

    def test_rows_readers_agree(self):
        rows, digest = gate.fedscope_payroll_rows()
        self.assertEqual(rows, fp.load_avgsal_rows())
        self.assertEqual(digest, fp.file_sha256(DEFAULT_FEDSCOPE_ZIP))

    def test_definition_is_printed_by_the_dictionary(self):
        text = re.sub(r"\s+", " ", guide_text(DICTIONARY.read_bytes()))
        self.assertIn("AVGSAL Average Employee Salary " + fp.AVGSAL_DEFINITION, text)


class BlockTests(unittest.TestCase):
    def test_sum_and_average(self):
        rows = {("2025-03", "A1"): (10, 100000), ("2025-03", "A2"): (5, 70001)}
        src = {"period": "2025-03", "level": "agency", "components": [{"subagencyCode": "A1"}, {"subagencyCode": "A2"}],
               "coverage": COVERAGE_STATEMENT, "url": "https://www.opm.gov/x.zip"}
        block = fp.payroll_block(src, 15, rows, sha256="d")
        self.assertEqual(block["totalAnnualPay"], 10 * 100000 + 5 * 70001)
        self.assertEqual(block["average"], round(block["totalAnnualPay"] / 15))
        self.assertEqual(block["rowAverageRange"], [70001, 100000])
        self.assertIsNone(fp.payroll_block(src, 16, rows, sha256="d"), "headcount must equal the rows' count")
        self.assertIsNone(fp.payroll_block(dict(src, components=[{"subagencyCode": "ZZ"}]), 15, rows, sha256="d"))


class GateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = json.loads(GRAPH.read_text(encoding="utf-8"))
        cls.rows, cls.digest = gate.fedscope_payroll_rows()
        cls.node = next(n for n in walk(cls.graph) if n.get("id") == "exec-dept-va")

    def check(self, node):
        return gate.fedscope_payroll_violations(node, node["payrollOfficial"], self.rows, self.digest, label)

    def test_published_graph_passes(self):
        carrying = [n for n in walk(self.graph) if "payrollOfficial" in n]
        self.assertGreater(len(carrying), 100)
        for node in carrying:
            self.assertEqual(self.check(node), [], node.get("id"))
            self.assertNotIn("position", str(node.get("type") or "").casefold())

    def corrupt(self, mutate):
        node = copy.deepcopy(self.node)
        mutate(node)
        self.assertTrue(self.check(node))

    def test_corruptions_fail(self):
        self.corrupt(lambda n: n.update(type="Position"))
        self.corrupt(lambda n: n["payrollOfficial"].update(totalAnnualPay=n["payrollOfficial"]["totalAnnualPay"] + 1))
        self.corrupt(lambda n: n["payrollOfficial"].update(average=n["payrollOfficial"]["average"] + 1))
        self.corrupt(lambda n: n["payrollOfficial"].update(period=None))
        self.corrupt(lambda n: n["payrollOfficial"].update(coverage=""))
        self.corrupt(lambda n: n["payrollOfficial"].update(definition="Average total compensation."))
        self.corrupt(lambda n: n["payrollOfficial"].update(sha256="0" * 64))
        self.corrupt(lambda n: n["payrollOfficial"]["rows"][0].__setitem__(2, 1))
        self.corrupt(lambda n: n["payrollOfficial"].update(rowAverageRange=[1, 2]))
        self.corrupt(lambda n: n.update(employeesOfficial=1))
        self.corrupt(lambda n: n.update(cost_status="official", resolved_total_amount=n["payrollOfficial"]["totalAnnualPay"]))


if __name__ == "__main__":
    unittest.main()
