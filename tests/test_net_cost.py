"""Audited net cost: the statement's own figure, beside the cost and never as it.

Treasury's Statement of Net Cost is the strongest cost evidence in this project
— the only figure an auditor outside the reporting agency has checked — and it
is also the easiest to publish dishonestly, because it looks like a cost and is
not one. It is accrual accounting for a fiscal year that has ENDED; the graph's
measured figure is cash outlays for the year to date. Same units, same agencies,
different meaning.

So these tests pin the separation as hard as the arithmetic: the module reads
the committed statement and refuses what does not name a unit, and the gate
refuses a block that has drifted from the document, moved to another node, or
been published as the node's cost.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.exporter.build_graph import (  # noqa: E402
    DEFAULT_BASE_GRAPH,
    canonical_name_key,
    index_tree,
    load_base_graph,
)
from data_pipeline.verification.evidence import EVIDENCE_OWNED_FIELDS  # noqa: E402
from data_pipeline.verification.net_cost import (  # noqa: E402
    DEFAULT_FIXTURE,
    NOT_A_UNIT,
    apply_net_cost_evidence,
    build_records,
    current_rows,
    fixture_digest,
    load_statement,
)

PUBLISHED = PROJECT_ROOT / "output" / "graph.json"


def walk(node):
    yield node
    for child in node.get("children") or []:
        yield from walk(child)


class FixtureTests(unittest.TestCase):
    def test_the_statement_is_committed_and_its_digest_matches_the_bytes(self) -> None:
        """The check that makes `documentSha256` a claim rather than a copied
        string: a hand-entered table under a treasury.gov URL would otherwise
        read exactly like a fetched one."""
        statement = load_statement()
        self.assertEqual(statement["sha256"], fixture_digest(DEFAULT_FIXTURE))
        self.assertIn("fiscaldata.treasury.gov", str(statement["url"]))

    def test_a_tampered_statement_is_refused(self) -> None:
        tampered = PROJECT_ROOT / "tests" / "fixtures" / "treasury" / "net_cost" / "_tampered.json"
        try:
            payload = json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))
            payload["data"][0]["net_cost_bil_amt"] = "999999.9"
            tampered.write_text(json.dumps(payload), encoding="utf-8")
            meta = tampered.with_suffix(tampered.suffix + ".meta.json")
            meta.write_text(json.dumps({"sha256": "0" * 64, "url": "https://x"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_statement(tampered)
        finally:
            tampered.unlink(missing_ok=True)
            tampered.with_suffix(tampered.suffix + ".meta.json").unlink(missing_ok=True)

    def test_only_the_reporting_year_is_read_not_the_restated_prior_year(self) -> None:
        """The file carries each agency twice — the year reported and the prior
        year restated beside it. Publishing both gives one unit two costs."""
        payload = load_statement()["payload"]
        rows = current_rows(payload)
        years = {r["stmt_fiscal_year"] for r in rows}
        flags = {r["restmt_flag"] for r in rows}
        self.assertEqual(len(years), 1, years)
        self.assertEqual(flags, {"N"})
        names = [r["agency_nm"] for r in rows]
        self.assertEqual(len(names), len(set(names)), "an agency appears twice in one year")


class MatchingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.node_map, _ = index_tree(load_base_graph(DEFAULT_BASE_GRAPH))
        cls.records, cls.report = build_records(cls.node_map)

    def test_the_counts_are_what_the_statement_supports(self) -> None:
        self.assertEqual(self.report["rows_considered"], 40)
        self.assertEqual(self.report["applied"], 33)
        self.assertEqual(self.report["refused"], {
            "no_node_carries_this_name": 2,
            "row_names_no_unit_of_government": 5,
        })

    def test_every_record_names_the_node_it_sits_on(self) -> None:
        for node_id, record in self.records.items():
            with self.subTest(node=node_id):
                node = self.node_map[node_id]
                self.assertEqual(canonical_name_key(node["name"]), canonical_name_key(record["agencyName"]))

    def test_the_consolidated_total_never_reaches_a_node(self) -> None:
        """$7.3 trillion for the whole government, one row of the same file.
        Matched to the nearest-looking node it would be one agency's cost."""
        self.assertIn("total", NOT_A_UNIT)
        quoted = {r["agencyName"].casefold() for r in self.records.values()}
        for refused in NOT_A_UNIT:
            self.assertNotIn(refused, quoted)

    def test_a_figure_is_the_statement_times_a_billion_and_says_so(self) -> None:
        """The publisher states the unit in the column name, `net_cost_bil_amt`,
        which is a third way a scale can be known and is recorded per record."""
        payload = load_statement()["payload"]
        printed = {r["agency_nm"]: r for r in current_rows(payload)}
        for record in self.records.values():
            with self.subTest(agency=record["agencyName"]):
                row = printed[record["agencyName"]]
                self.assertAlmostEqual(record["netCostUsd"], float(row["net_cost_bil_amt"]) * 1e9, places=2)
                self.assertTrue(record["unitsEvidenceKind"])
                self.assertIn("bil", record["printedUnit"])

    def test_no_record_is_zero(self) -> None:
        for record in self.records.values():
            self.assertNotEqual(record["netCostUsd"], 0)


class ApplyTests(unittest.TestCase):
    def tree(self) -> dict:
        return {"id": "root", "name": "Root", "type": "Branch", "children": [
            {"id": "a", "name": "Department of Energy", "type": "Department", "children": []},
            {"id": "p", "name": "Secretary of Energy", "type": "Position", "children": []},
        ]}

    def record(self, name="Department of Energy"):
        return {"agencyName": name, "netCostUsd": 1.0, "fiscalYear": "2025",
                "statementDate": "2025-09-30", "documentSha256": "x", "unitsEvidenceKind": "k"}

    def test_it_stamps_beside_the_cost_and_writes_no_cost_field(self) -> None:
        root = self.tree()
        apply_net_cost_evidence(root, {"a": self.record()})
        node = root["children"][0]
        self.assertEqual(node["auditedNetCost"]["netCostUsd"], 1.0)
        for field in ("resolved_total_amount", "cost_status", "rollup_total_amount", "cost_basis"):
            self.assertNotIn(field, node, f"the audited figure wrote {field}")

    def test_a_post_never_carries_one(self) -> None:
        root = self.tree()
        apply_net_cost_evidence(root, {"p": self.record("Secretary of Energy")})
        self.assertNotIn("auditedNetCost", root["children"][1])

    def test_a_renamed_node_loses_it(self) -> None:
        root = self.tree()
        root["children"][0]["name"] = "Department of Something Else"
        report = apply_net_cost_evidence(root, {"a": self.record()})
        self.assertNotIn("auditedNetCost", root["children"][0])
        self.assertEqual(report["refused_renamed"], 1)

    def test_a_withdrawn_record_stops_being_published(self) -> None:
        """The exporter re-feeds the previous graph.json as a payload, so a
        block must be cleared before the table is applied or a retraction could
        never reach the site."""
        root = self.tree()
        apply_net_cost_evidence(root, {"a": self.record()})
        self.assertIn("auditedNetCost", root["children"][0])
        report = apply_net_cost_evidence(root, {})
        self.assertNotIn("auditedNetCost", root["children"][0])
        self.assertEqual(report["withdrawn_first"], 1)

    def test_the_field_is_owned_so_the_sweep_can_withdraw_it(self) -> None:
        self.assertIn("auditedNetCost", EVIDENCE_OWNED_FIELDS)


@unittest.skipUnless(PUBLISHED.is_file(), "no published graph")
class PublishedGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.nodes = list(walk(json.loads(PUBLISHED.read_text(encoding="utf-8"))))

    def test_the_published_graph_carries_them(self) -> None:
        carried = [n for n in self.nodes if n.get("auditedNetCost")]
        self.assertGreaterEqual(len(carried), 30)

    def test_no_published_block_equals_the_node_s_cost(self) -> None:
        """Different basis and different period, so equality to the cent means
        the two have been confused. The gate refuses it; this asserts the live
        graph has none."""
        for node in self.nodes:
            block = node.get("auditedNetCost")
            amount = node.get("resolved_total_amount")
            if not block or not isinstance(amount, (int, float)):
                continue
            with self.subTest(node=node.get("id")):
                self.assertNotAlmostEqual(float(amount), float(block["netCostUsd"]), places=2)

    def test_no_published_block_sits_on_a_post(self) -> None:
        for node in self.nodes:
            if node.get("auditedNetCost"):
                self.assertNotIn("position", str(node.get("type") or "").casefold())


@unittest.skipUnless(PUBLISHED.is_file(), "no published graph")
class GateRefusalTests(unittest.TestCase):
    """The gate accepts the true blocks and refuses each way one can be faked.

    A check only ever tested with good input is not known to refuse anything.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = json.loads(PUBLISHED.read_text(encoding="utf-8"))
        cls.tmp = PROJECT_ROOT / "tests" / "_net_cost_gate_tmp"
        cls.tmp.mkdir(exist_ok=True)

    @classmethod
    def tearDownClass(cls) -> None:
        for path in cls.tmp.glob("*"):
            path.unlink()
        cls.tmp.rmdir()

    def gate(self, graph) -> tuple[int, str]:
        import io
        from contextlib import redirect_stdout
        from scripts.validate_published_graph import main as gate_main
        path = self.tmp / "graph.json"
        path.write_text(json.dumps(graph), encoding="utf-8")
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = gate_main(["gate", str(path)])
        return code, buffer.getvalue()

    def corrupt(self, mutate):
        graph = json.loads(json.dumps(self.graph))
        nodes = {n["id"]: n for n in walk(graph) if n.get("id")}
        carrier = next(n for n in nodes.values() if n.get("auditedNetCost"))
        mutate(carrier, nodes)
        return self.gate(graph)

    def test_the_true_graph_passes(self) -> None:
        code, out = self.gate(json.loads(json.dumps(self.graph)))
        self.assertEqual(code, 0, out)

    def test_each_corruption_is_refused(self) -> None:
        cases = {
            "a figure the statement does not print":
                lambda node, nodes: node["auditedNetCost"].__setitem__("netCostUsd", 12345.0),
            "a block moved to another node":
                lambda node, nodes: node["auditedNetCost"].__setitem__("agencyName", "Department of Energy")
                if node["auditedNetCost"]["agencyName"] != "Department of Energy"
                else node["auditedNetCost"].__setitem__("agencyName", "Department of Defense"),
            "a document digest the committed statement does not have":
                lambda node, nodes: node["auditedNetCost"].__setitem__("documentSha256", "0" * 64),
            "the year it covers removed":
                lambda node, nodes: node["auditedNetCost"].__setitem__("fiscalYear", ""),
            "how the unit is known removed":
                lambda node, nodes: node["auditedNetCost"].__setitem__("unitsEvidenceKind", ""),
            "published as the node's own cost":
                lambda node, nodes: node.__setitem__("resolved_total_amount", node["auditedNetCost"]["netCostUsd"]),
        }
        for name, mutate in cases.items():
            with self.subTest(case=name):
                code, out = self.corrupt(mutate)
                self.assertEqual(code, 1, f"{name} was accepted:\n{out[-2000:]}")


if __name__ == "__main__":
    unittest.main()
