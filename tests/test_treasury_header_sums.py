"""A unit the statement prints lines beneath and totals nowhere, on the real
2026-08-31 Table 5.

Table 5 prints some sub-agencies as a HEADER row (null amount) with lines
beneath and no "Total--" line of their own. `collect_treasury_outlay_rows`
drops every row whose amount is None, so until 2026-10-06 such a unit never
reached the matcher: nine of them -- the Veterans Health Administration at
$100.4B among them, about $151bn in all -- were apportioned by headcount and
subtree size while the statement printed their money line by line under the
unit's own name. The exporter now prices such a header by the sum of the
lines beneath it, the statement's own arithmetic, and stamps the node so the
claim is exact: `treasury_header_sum`, the lines by printed name and amount,
and a sentence saying the statement prints no total and the figure is that
sum. Every number asserted here is read off the fixture, and the nine sums
are the ones the finding stated to the cent.
"""

from __future__ import annotations

import io
import json
import shutil
import sys
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT, PROJECT_ROOT / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from data_pipeline.crawler.treasury_outlays import parse_outlay_rows  # noqa: E402
from data_pipeline.exporter.build_graph import (  # noqa: E402
    MINIMAL_GRAPH_FIELDS,
    TREASURY_HEADER_SUM_FIELDS,
    TREASURY_ROW_ALIASES,
    build_graph,
    canonical_name_key,
    derive_header_sum_rows,
    header_sum_note,
    index_tree,
    prune_graph_for_viewer,
)
from data_pipeline.exporter.treasury_sections import (  # noqa: E402
    RECEIPTS_LABELS,
    UNDISTRIBUTED_LABEL,
    SectionTree,
    is_header_row,
    is_total_row,
    plain_label,
)
from add_curated_nodes import treasury_rows_by_key  # noqa: E402
from scripts import validate_published_graph as gate  # noqa: E402

FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "mts_table5_2026-08-31.json"
TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
ROOT_ID = "the-constitution-of-the-united-states"

#: The nine headers the finding named, with the sums it stated to the cent
#: (FYTD net outlays through 2026-08-31) and the number of lines beneath each.
NINE = {
    "exec-dept-usda-nrcs": ("Natural Resources Conservation Service:", 5_270_811_519.50, 3),
    "exec-dept-doe-nnsa": ("National Nuclear Security Administration:", 23_763_992_947.05, 4),
    "exec-dept-doi-blm": ("Bureau of Land Management:", 1_364_367_888.40, 2),
    "exec-dept-doi-bor": ("Bureau of Reclamation:", 2_987_056_641.15, 2),
    "exec-dept-doj-office-justice-programs": ("Office of Justice Programs:", 4_518_129_781.85, 4),
    "exec-dept-treasury-ttb": ("Alcohol and Tobacco Tax and Trade Bureau:", 512_977_431.15, 2),
    "exec-dept-va-vha": ("Veterans Health Administration:", 100_361_712_221.24, 5),
    "exec-regulatory-fcc": ("Federal Communications Commission:", 9_879_942_633.73, 3),
    "exec-ind-usps": ("Postal Service:", 2_055_857_347.93, 3),
}

# The graph's own spellings for the nine (the real graph's names), so the test
# exercises canonical_name_key exactly as the build does: parentheticals, "&",
# "U.S." all set aside.
BASE = {
    "id": ROOT_ID, "name": "The Constitution of the United States", "type": "Foundation",
    "children": [
        {"id": "legislative-branch", "name": "Legislative Branch", "type": "Branch", "children": [
            {"id": "leg-senate", "name": "Senate", "type": "Chamber", "children": []},
        ]},
        {"id": "executive-branch", "name": "Executive Branch", "type": "Branch", "children": [
            {"id": "exec-cabinet", "name": "The Cabinet — Executive Departments", "type": "Division", "children": [
                {"id": "exec-dept-usda", "name": "Department of Agriculture (USDA)", "type": "Cabinet Department", "children": [
                    {"id": "exec-dept-usda-nrcs", "name": "Natural Resources Conservation Service (NRCS)", "type": "Component Agency", "children": []},
                    # A unit the statement prints WITH a Total-- line: the ordinary rule reads it.
                    {"id": "exec-dept-usda-fs", "name": "Forest Service", "type": "Component Agency", "children": []},
                ]},
                {"id": "exec-dept-doe", "name": "Department of Energy (DOE)", "type": "Cabinet Department", "children": [
                    {"id": "exec-dept-doe-nnsa", "name": "National Nuclear Security Administration (NNSA)", "type": "Component Agency", "children": []},
                    {"id": "exec-dept-doe-unlined", "name": "Office of Nothing in Particular", "type": "Office", "children": []},
                ]},
                {"id": "exec-dept-doi", "name": "Department of the Interior (DOI)", "type": "Cabinet Department", "children": [
                    {"id": "exec-dept-doi-blm", "name": "Bureau of Land Management (BLM)", "type": "Component Agency", "children": []},
                    {"id": "exec-dept-doi-bor", "name": "Bureau of Reclamation (BOR)", "type": "Component Agency", "children": []},
                ]},
                {"id": "exec-dept-doj", "name": "Department of Justice (DOJ)", "type": "Cabinet Department", "children": [
                    {"id": "exec-dept-doj-office-justice-programs", "name": "Office of Justice Programs", "type": "Component Agency", "children": []},
                ]},
                {"id": "exec-dept-treasury", "name": "Department of the Treasury", "type": "Cabinet Department", "children": [
                    {"id": "exec-dept-treasury-ttb", "name": "Alcohol & Tobacco Tax & Trade Bureau (TTB)", "type": "Component Agency", "children": []},
                    {"id": "exec-dept-treasury-irs", "name": "Internal Revenue Service", "type": "Component Agency", "children": []},
                ]},
                {"id": "exec-dept-va", "name": "Department of Veterans Affairs (VA)", "type": "Cabinet Department", "children": [
                    {"id": "exec-dept-va-vha", "name": "Veterans Health Administration (VHA)", "type": "Component Agency", "children": [
                        {"id": "exec-dept-va-vha-under", "name": "Under Secretary for Health", "type": "Position", "children": []},
                    ]},
                ]},
                {"id": "exec-dept-hud", "name": "Department of Housing and Urban Development (HUD)", "type": "Cabinet Department", "children": [
                    # The statement's header is "Government National Mortgage Association:"; this name does not reduce to it.
                    {"id": "exec-dept-hud-ginnie", "name": "Ginnie Mae", "type": "Agency", "children": []},
                ]},
                {"id": "exec-dept-defense", "name": "Department of Defense (DoD)", "type": "Cabinet Department", "children": [
                    # "Defense Agencies" is a total-less header AND a line the statement prints nine more times.
                    {"id": "exec-dept-defense-agencies", "name": "Defense Agencies", "type": "Division", "children": []},
                ]},
                {"id": "exec-dept-hhs", "name": "Department of Health and Human Services (HHS)", "type": "Cabinet Department", "children": [
                    # Filled in by setUp: a header that appears ONLY inside receipts-type subtrees.
                    {"id": "exec-dept-hhs-receipts-control", "name": None, "type": "Program", "children": []},
                ]},
            ]},
            {"id": "exec-regulatory", "name": "Independent Regulatory Commissions", "type": "Division", "children": [
                {"id": "exec-regulatory-fcc", "name": "Federal Communications Commission (FCC)", "type": "Independent Regulatory Commission", "children": []},
            ]},
            {"id": "exec-independent", "name": "Independent Agencies and Corporations", "type": "Division", "children": [
                {"id": "exec-ind-usps", "name": "U.S. Postal Service (USPS)", "type": "Independent Agency", "children": []},
                {"id": "exec-ind-misc", "name": "Other Independent Agencies", "type": "Division", "children": [
                    {"id": "exec-ind-misc-americorps", "name": "AmeriCorps", "type": "Independent Agency", "children": []},
                ]},
            ]},
        ]},
        {"id": "judicial-branch", "name": "Judicial Branch", "type": "Branch", "children": [
            {"id": "jud-scotus", "name": "Supreme Court of the United States", "type": "Court", "children": []},
        ]},
    ],
}


def raw_rows():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["rows"]


def statement_payload():
    rows, summary = parse_outlay_rows(raw_rows())
    return {"nodes": [], "edges": [], "budgetSummary": dict(summary), "outlayRows": rows}


def section_tree():
    rows, _ = parse_outlay_rows(raw_rows())
    return SectionTree.from_rows(rows)


def row_amount(name):
    matches = [r for r in raw_rows() if r["classification_desc"] == name]
    assert len(matches) == 1, (name, len(matches))
    return float(matches[0]["current_fytd_net_outly_amt"])


def lines_beneath(header_id):
    """The statement's own lines beneath a header, read straight off the raw
    API rows with no help from the module under test: every non-Total child,
    a child header descended into, a receipts-type child kept as one item at
    the sum of its own lines. Mirrors nothing by import."""
    rows = raw_rows()
    by_parent = {}
    for row in sorted(rows, key=lambda r: int(r["print_order_nbr"])):
        by_parent.setdefault(row["parent_id"], []).append(row)

    def label(row):
        text = row["classification_desc"].strip()
        return (text[len("Total--"):] if text.startswith("Total--") else text).rstrip(":").strip()

    def value(row):
        if row["current_fytd_net_outly_amt"] != "null":
            return float(row["current_fytd_net_outly_amt"])
        return sum(value(k) for k in by_parent.get(row["classification_id"], []) if not k["classification_desc"].startswith("Total--"))

    def walk(parent_id):
        out = []
        for kid in by_parent.get(parent_id, []):
            if kid["classification_desc"].startswith("Total--"):
                continue
            if kid["current_fytd_net_outly_amt"] == "null" and label(kid) not in RECEIPTS_LABELS:
                out.extend(walk(kid["classification_id"]))
            else:
                out.append((label(kid), round(value(kid), 2)))
        return out

    return walk(header_id)


def receipts_only_header_name():
    """A header printed only inside receipts-type subtrees -- never as a
    section or line of its own -- so a node of that name can be priced by
    nothing but a mistake."""
    tree = section_tree()
    components = tree.receipts_component_ids()
    keys_outside = {canonical_name_key(plain_label(r)) for cid, r in tree.rows.items() if cid not in components}
    for cid, row in tree.rows.items():
        if cid in components and is_header_row(row) and tree.total_row(row) is None and tree.header_components(row):
            if canonical_name_key(plain_label(row)) not in keys_outside:
                return plain_label(row), cid
    raise AssertionError("the fixture no longer prints a header that exists only inside receipts subtrees")


class HeaderSumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipts_name, cls.receipts_header_id = receipts_only_header_name()

    def setUp(self) -> None:
        self.tmp = TEST_TMP_ROOT / f"header-sums-{uuid.uuid4().hex}"
        self.tmp.mkdir(parents=True, exist_ok=True)
        base = json.loads(json.dumps(BASE))
        for node in index_tree(base)[0].values():
            if node.get("id") == "exec-dept-hhs-receipts-control":
                node["name"] = self.receipts_name
        self.base = self.tmp / "base.json"
        self.base.write_text(json.dumps(base), encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build(self, payloads, *, reuse=False):
        return build_graph(
            payloads, base_graph_path=self.base, graph_output_path=self.tmp / "graph.json",
            nodes_output_path=self.tmp / "expanded_nodes.json", edges_output_path=self.tmp / "expanded_edges.json",
            validity_report_output_path=self.tmp / "v.json", reuse_existing_graph_payload=reuse,
            existing_graph_payload_path=self.tmp / "graph.json", enforce_export_gate=True, evidence_path=None, sites_path=None,
        )

    def _gate(self, path):
        out = io.StringIO()
        with redirect_stdout(out):
            code = gate.main(["gate", str(path)])
        return code, out.getvalue()

    def _graph(self, result):
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        return graph, index_tree(graph)[0]

    # -- the exporter -------------------------------------------------------

    def test_the_nine_headers_price_their_nodes_by_the_statement_s_own_lines(self) -> None:
        result = self._build([statement_payload()])
        stats = result.validation["treasury_outlay_rows"]
        self.assertTrue(stats["treasury_netting"]["identity"]["holds"], stats["treasury_netting"])
        self.assertEqual(stats["header_sums_applied"], 9, stats["header_sums"])
        # The one ambiguous name is the control this BASE plants: "Defense
        # Agencies" is a total-less header AND a line printed nine more times,
        # and every one of those rows is reported, the header's among them.
        self.assertEqual({name.rstrip(":") for name in stats["ambiguous_sample"]}, {"Defense Agencies"}, stats["ambiguous_sample"])
        self.assertIn("Defense Agencies:", stats["ambiguous_sample"])
        graph, nodes = self._graph(result)
        tree = section_tree()
        for node_id, (printed, amount, line_count) in NINE.items():
            with self.subTest(node=node_id):
                node = nodes[node_id]
                self.assertEqual(node["cost_status"], "official")
                self.assertEqual(node["costVerificationStatus"], "verified")
                self.assertIs(node["treasury_header_sum"], True)
                self.assertEqual(node["treasury_row_name"], printed)
                self.assertAlmostEqual(node["rollup_total_amount"], amount, places=2)
                self.assertAlmostEqual(node["resolved_total_amount"], amount, places=2)
                self.assertEqual(len(node["treasury_component_rows"]), line_count)
                # The recorded lines ARE the statement's lines beneath the header, read off the raw rows.
                header_id = node["treasury_classification_id"]
                self.assertEqual(
                    sorted((c["name"], round(c["amount"], 2)) for c in node["treasury_component_rows"]),
                    sorted(lines_beneath(header_id)),
                )
                self.assertAlmostEqual(sum(c["amount"] for c in node["treasury_component_rows"]), amount, places=2)
                self.assertEqual(node["treasury_header_sum_note"], header_sum_note(line_count))
                self.assertIn("prints no total line for this unit", node["treasury_header_sum_note"])
                self.assertIn("listed below", node["treasury_header_sum_note"])
                self.assertTrue(any("fiscaldata.treasury.gov" in u for u in node["sourceUrls"]))
                self.assertIn("treasury_outlays", node["sourceTypes"])
                self.assertEqual(node["budget_as_of"], "2026-08-31")
                # The header's own top section, as the exporter files it.
                header = tree.rows[header_id]
                self.assertEqual(node["treasury_section"], plain_label(tree.top_section_of(header)))

    def test_the_postal_service_sum_descends_into_the_off_budget_sub_header(self) -> None:
        """"Postal Service:" prints one line beside an "Off-Budget:" header
        with two lines beneath it; the sum is all three, as the statement's
        own arithmetic has it, and the sub-header is never a component."""
        _, nodes = self._graph(self._build([statement_payload()]))
        usps = nodes["exec-ind-usps"]
        names = [c["name"] for c in usps["treasury_component_rows"]]
        self.assertEqual(sorted(names), ["Other", "Other", "Public Enterprise Funds"])
        self.assertNotIn("Off-Budget", names)
        self.assertAlmostEqual(usps["resolved_total_amount"], 2_055_857_347.93, places=2)

    def test_a_header_with_a_total_line_is_priced_by_the_total_and_not_twice(self) -> None:
        _, nodes = self._graph(self._build([statement_payload()]))
        for node_id, total in (("exec-dept-treasury-irs", "Total--Internal Revenue Service"), ("exec-dept-usda-fs", "Total--Forest Service")):
            with self.subTest(node=node_id):
                node = nodes[node_id]
                self.assertEqual(node["cost_status"], "official")
                self.assertEqual(node["treasury_row_name"], total)
                self.assertEqual(node["resolved_total_amount"], row_amount(total))
                for field in TREASURY_HEADER_SUM_FIELDS:
                    self.assertNotIn(field, node)

    def test_a_header_inside_a_receipts_subtree_prices_nothing(self) -> None:
        tree = section_tree()
        self.assertIn(self.receipts_header_id, tree.receipts_component_ids())
        self.assertNotIn(self.receipts_header_id, {str(r["classification_id"]) for r in derive_header_sum_rows(tree)})
        _, nodes = self._graph(self._build([statement_payload()]))
        control = nodes["exec-dept-hhs-receipts-control"]
        self.assertEqual(control["name"], self.receipts_name)
        self.assertIsNone(control.get("rollup_total_amount"))
        self.assertNotEqual(control["cost_status"], "official")
        for field in TREASURY_HEADER_SUM_FIELDS:
            self.assertNotIn(field, control)

    def test_a_name_several_rows_carry_prices_nothing_and_a_name_that_does_not_reduce_prices_nothing(self) -> None:
        _, nodes = self._graph(self._build([statement_payload()]))
        # "Defense Agencies:" is a total-less header and a line printed nine more times.
        self.assertIsNone(nodes["exec-dept-defense-agencies"].get("rollup_total_amount"))
        # "Government National Mortgage Association:" is a total-less header; "Ginnie Mae" is not that name.
        ginnie = nodes["exec-dept-hud-ginnie"]
        self.assertIsNone(ginnie.get("rollup_total_amount"))
        self.assertNotIn("treasury_header_sum", ginnie)
        self.assertIn("government national mortgage association", {canonical_name_key(r["name"]) for r in derive_header_sum_rows(section_tree())})

    def test_a_header_sum_never_lands_on_a_post_even_when_only_a_post_carries_the_name(self) -> None:
        base = json.loads(self.base.read_text(encoding="utf-8"))
        for node in index_tree(base)[0].values():
            if node.get("id") == "exec-regulatory-fcc":
                node["type"] = "Position"
        self.base.write_text(json.dumps(base), encoding="utf-8")
        _, nodes = self._graph(self._build([statement_payload()]))
        fcc = nodes["exec-regulatory-fcc"]
        self.assertIsNone(fcc.get("rollup_total_amount"))
        self.assertNotIn("treasury_header_sum", fcc)

    def test_the_parent_s_arithmetic_stays_honest(self) -> None:
        """The header sum sits inside its department's total exactly as a line
        does: the department publishes the Treasury's net figure, and its
        lines, its receipts and the estimate for its unlined children sum to
        it to the cent, with the header-sum unit among the lines."""
        result = self._build([statement_payload()])
        graph, nodes = self._graph(result)
        energy = nodes["exec-dept-doe"]
        self.assertEqual(energy["cost_status"], "official")
        self.assertEqual(energy["resolved_total_amount"], row_amount("Total--Department of Energy"))
        kids = [c for c in energy["children"] if c.get("resolved_total_amount") is not None and not c.get("treasury_external_section")]
        self.assertIn("exec-dept-doe-nnsa", {c["id"] for c in kids})
        self.assertAlmostEqual(sum(c["resolved_total_amount"] for c in kids) + float(energy.get("treasury_unapportioned") or 0.0),
                               energy["resolved_total_amount"], places=2)
        # The unlined sibling's pool shrank by the header sum: its estimate is
        # exactly the department's net figure less the receipts the statement
        # nets, less the NNSA's lines, less whatever reaches no node -- not the
        # whole remainder it drew before the header was priced.
        unlined = nodes["exec-dept-doe-unlined"]
        self.assertEqual(unlined["cost_status"], "allocated")
        receipts = sum(c["resolved_total_amount"] for c in kids if c.get("synthetic") == "treasury_receipts")
        self.assertLess(receipts, 0)
        pool_before_the_header = energy["resolved_total_amount"] - receipts
        self.assertAlmostEqual(
            unlined["resolved_total_amount"],
            pool_before_the_header - nodes["exec-dept-doe-nnsa"]["resolved_total_amount"] - float(energy.get("treasury_unapportioned") or 0.0),
            places=2,
        )
        self.assertLess(unlined["resolved_total_amount"], pool_before_the_header)
        # A post beneath a header-sum unit still gets nothing.
        self.assertEqual(nodes["exec-dept-va-vha-under"]["cost_status"], "unavailable")
        code, out = self._gate(result.graph_path)
        self.assertEqual(code, 0, out)
        self.assertIn("9 of them the sum of the lines beneath a header the statement totals nowhere", out)
        self.assertIn("Treasury header sums : 9 units", out)

    def test_header_sums_are_carried_forward_and_replaced_never_duplicated(self) -> None:
        first = self._build([statement_payload()])
        _, nodes = self._graph(first)
        before = {i: json.loads(json.dumps({k: nodes[i].get(k) for k in ("rollup_total_amount", *TREASURY_HEADER_SUM_FIELDS)})) for i in NINE}
        # No statement: the figures and their stamps ride along with the other Treasury lines.
        carried = self._build([{"nodes": [], "edges": [], "budgetSummary": statement_payload()["budgetSummary"]}], reuse=True)
        self.assertEqual(carried.validation["treasury_outlay_rows"]["header_sums_derived"], 0)
        _, nodes = self._graph(carried)
        for node_id in NINE:
            with self.subTest(node=node_id, pass_="carried"):
                self.assertEqual(nodes[node_id]["cost_status"], "official")
                self.assertEqual({k: nodes[node_id].get(k) for k in before[node_id]}, before[node_id])
        # A fresh statement replaces them: the same stamp once, the lines once.
        again = self._build([statement_payload()], reuse=True)
        self.assertEqual(again.validation["treasury_outlay_rows"]["header_sums_applied"], 9)
        self.assertGreater(again.validation["treasury_outlay_rows"]["stale_rollups_cleared"], 0)
        _, nodes = self._graph(again)
        for node_id in NINE:
            with self.subTest(node=node_id, pass_="replaced"):
                self.assertEqual({k: nodes[node_id].get(k) for k in before[node_id]}, before[node_id])
                self.assertEqual(len(nodes[node_id]["treasury_component_rows"]), NINE[node_id][2])

    def test_a_fresh_statement_clears_a_stale_header_sum(self) -> None:
        """A unit the statement stops printing lines for must not keep last
        month's stamp. The stamp fields are cleared with the other Treasury
        fields on any build handed a statement, before the new ones land."""
        first = self._build([statement_payload()])
        stale = json.loads(first.graph_path.read_text(encoding="utf-8"))
        for node in index_tree(stale)[0].values():
            if node.get("id") == "exec-dept-usda-fs":
                node.update({"treasury_header_sum": True, "treasury_component_rows": [{"name": "Invented", "amount": 1.0}],
                             "treasury_header_sum_note": header_sum_note(1)})
        first.graph_path.write_text(json.dumps(stale), encoding="utf-8")
        again = self._build([statement_payload()], reuse=True)
        _, nodes = self._graph(again)
        for field in TREASURY_HEADER_SUM_FIELDS:
            self.assertNotIn(field, nodes["exec-dept-usda-fs"])
        self.assertEqual(nodes["exec-dept-usda-fs"]["treasury_row_name"], "Total--Forest Service")

    # -- the alias row ------------------------------------------------------

    def test_the_corporation_for_national_and_community_service_line_reaches_americorps(self) -> None:
        self.assertEqual(TREASURY_ROW_ALIASES["corporation for national and community service"], "exec-ind-misc-americorps")
        _, nodes = self._graph(self._build([statement_payload()]))
        americorps = nodes["exec-ind-misc-americorps"]
        self.assertEqual(americorps["cost_status"], "official")
        self.assertEqual(americorps["treasury_row_name"], "Corporation for National and Community Service")
        self.assertEqual(americorps["resolved_total_amount"], row_amount("Corporation for National and Community Service"))
        self.assertAlmostEqual(americorps["resolved_total_amount"], 941_240_516.35, places=2)
        # The same-section rule: the line is filed under Independent Agencies, and no lined ancestor disagrees.
        self.assertEqual(americorps["treasury_section"], "Independent Agencies")
        self.assertNotIn("treasury_external_section", americorps)
        self.assertNotIn("treasury_header_sum", americorps)

    def test_an_alias_is_never_stacked_on_a_header_sum(self) -> None:
        """A header sum reaches a node by name equality or not at all. Give
        the GNMA header an alias and it must still price nothing."""
        tree = section_tree()
        derived = {canonical_name_key(r["name"]): r for r in derive_header_sum_rows(tree)}
        self.assertIn("government national mortgage association", derived)
        from data_pipeline.exporter import build_graph as module
        original = dict(module.TREASURY_ROW_ALIASES)
        module.TREASURY_ROW_ALIASES["government national mortgage association"] = "exec-dept-hud-ginnie"
        try:
            _, nodes = self._graph(self._build([statement_payload()]))
        finally:
            module.TREASURY_ROW_ALIASES.clear()
            module.TREASURY_ROW_ALIASES.update(original)
        self.assertIsNone(nodes["exec-dept-hud-ginnie"].get("rollup_total_amount"))

    # -- the gate -----------------------------------------------------------

    def test_the_gate_refuses_each_way_a_header_sum_can_be_faked(self) -> None:
        result = self._build([statement_payload()])
        code, out = self._gate(result.graph_path)
        self.assertEqual(code, 0, out)
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        tree = section_tree()

        def corrupt(mutate):
            corrupted = json.loads(json.dumps(graph))
            mutate(corrupted, index_tree(corrupted)[0])
            path = self.tmp / f"{uuid.uuid4().hex}.json"
            path.write_text(json.dumps(corrupted), encoding="utf-8")
            return self._gate(path)

        def move_block(source, target, n):
            block = {k: json.loads(json.dumps(n[source][k])) for k in (
                "treasury_header_sum", "treasury_component_rows", "treasury_header_sum_note",
                "treasury_classification_id", "treasury_row_name", "rollup_total_amount", "resolved_total_amount",
                "budget_as_of", "cost_status", "costVerificationStatus", "sourceUrls", "sourceTypes", "budget_source")}
            n[target].update(block)

        irs_header_id = next(cid for cid, r in tree.rows.items() if r["originalName"] == "Internal Revenue Service:")
        receipts_header_id = self.receipts_header_id
        receipts_components = [{"name": plain_label(r), "amount": round(a, 2)} for r, a in tree.header_components(tree.rows[receipts_header_id])]

        def stamp_receipts_control(g, n):
            node = n["exec-dept-hhs-receipts-control"]
            total = round(sum(c["amount"] for c in receipts_components), 2)
            node.update({
                "treasury_header_sum": True, "treasury_component_rows": receipts_components,
                "treasury_header_sum_note": header_sum_note(len(receipts_components)),
                "treasury_classification_id": receipts_header_id, "treasury_row_name": tree.rows[receipts_header_id]["originalName"],
                "rollup_total_amount": total, "resolved_total_amount": total, "budget_as_of": "2026-08-31",
                "cost_status": "official", "costVerificationStatus": "verified", "budget_source": "Treasury MTS Table 5",
                "sourceUrls": list(n["exec-dept-va-vha"]["sourceUrls"]), "sourceTypes": list(n["exec-dept-va-vha"]["sourceTypes"]),
            })

        cases = {
            "a component amount the statement does not print": lambda g, n: n["exec-dept-va-vha"]["treasury_component_rows"][0].__setitem__("amount", 1.0),
            "a component line dropped": lambda g, n: n["exec-dept-va-vha"]["treasury_component_rows"].pop(),
            "a component line renamed": lambda g, n: n["exec-dept-va-vha"]["treasury_component_rows"][1].__setitem__("name", "Medical Everything"),
            "a component line added": lambda g, n: n["exec-dept-va-vha"]["treasury_component_rows"].append({"name": "Other", "amount": 0.0}),
            "the stamp sentence missing": lambda g, n: n["exec-dept-va-vha"].pop("treasury_header_sum_note"),
            "the stamp sentence for the wrong count": lambda g, n: n["exec-dept-va-vha"].__setitem__("treasury_header_sum_note", header_sum_note(4)),
            "the stamp sentence calling it a line the Treasury prints": lambda g, n: n["exec-dept-va-vha"].__setitem__(
                "treasury_header_sum_note", "The Treasury prints this line for the unit."),
            "a figure that is not the lines' sum": lambda g, n: n["exec-dept-va-vha"].update(
                {"rollup_total_amount": 100_000_000_000.0, "resolved_total_amount": 100_000_000_000.0}),
            "a header sum on a post": lambda g, n: n["exec-dept-va-vha"].__setitem__("type", "Position"),
            "a header sum on a node the header's name does not reduce to": lambda g, n: move_block("exec-dept-usda-nrcs", "exec-dept-usda-fs", n),
            "a header that has a Total-- line of its own": lambda g, n: n["exec-dept-treasury-irs"].update({
                "treasury_header_sum": True, "treasury_classification_id": irs_header_id, "treasury_row_name": "Internal Revenue Service:",
                "treasury_component_rows": [{"name": plain_label(r), "amount": round(a, 2)} for r, a in tree.header_components(tree.rows[irs_header_id])],
                "treasury_header_sum_note": header_sum_note(len(tree.header_components(tree.rows[irs_header_id])))}),
            "a printed line rather than a header": lambda g, n: n["exec-dept-treasury-irs"].update({
                "treasury_header_sum": True, "treasury_component_rows": [{"name": "Internal Revenue Service", "amount": n["exec-dept-treasury-irs"]["rollup_total_amount"]}],
                "treasury_header_sum_note": header_sum_note(1), "treasury_row_name": "Total--Internal Revenue Service"}),
            "a header inside a receipts-type subtree": stamp_receipts_control,
            "a statement nobody committed": lambda g, n: n["exec-dept-va-vha"].__setitem__("budget_as_of", "2031-01-31"),
            "a classification id the statement does not print": lambda g, n: n["exec-dept-va-vha"].__setitem__("treasury_classification_id", "1"),
            "component lines on an organisation without the stamp": lambda g, n: n["exec-dept-usda-fs"].__setitem__(
                "treasury_component_rows", [{"name": "Forest Service", "amount": 1.0}]),
            "the stamp sentence without the stamp": lambda g, n: n["exec-dept-usda-fs"].__setitem__("treasury_header_sum_note", header_sum_note(1)),
            "a stamp that is not True": lambda g, n: n["exec-dept-va-vha"].__setitem__("treasury_header_sum", "yes"),
            "a header sum of zero": lambda g, n: n["exec-dept-va-vha"].update({
                "rollup_total_amount": 0.0, "resolved_total_amount": 0.0,
                "treasury_component_rows": [{"name": c["name"], "amount": 0.0} for c in n["exec-dept-va-vha"]["treasury_component_rows"]]}),
        }
        for name, mutate in cases.items():
            with self.subTest(case=name):
                code, out = corrupt(mutate)
                self.assertEqual(code, 1, f"{name}:\n{out}")
                if name not in ("a header sum on a post", "a figure that is not the lines' sum", "a header sum of zero"):
                    # The header-sum check itself fires, not only a neighbour.
                    self.assertIn("a Treasury header sum is the statement's own lines", "".join(
                        line for line in out.splitlines() if line.startswith("FAIL")), f"{name}:\n{out}")

    # -- the mirrors --------------------------------------------------------

    def test_the_gate_mirrors_the_exporter_s_labels_sentence_and_arithmetic(self) -> None:
        self.assertEqual(gate.TREASURY_RECEIPTS_LABELS, RECEIPTS_LABELS)
        self.assertEqual(gate.TREASURY_UNDISTRIBUTED_LABEL, UNDISTRIBUTED_LABEL)
        for count in range(1, 10):
            self.assertEqual(gate.treasury_header_sum_note(count), header_sum_note(count))
        tree = section_tree()
        reading = gate.TreasuryStatementRows(raw_rows())
        headers = tree.total_less_headers()
        self.assertGreaterEqual(len(headers), 9)
        for header in headers:
            cid = str(header["classification_id"])
            with self.subTest(header=header["originalName"]):
                self.assertEqual(
                    sorted((plain_label(r), round(a, 2)) for r, a in tree.header_components(header)),
                    sorted(reading.components(reading.rows[cid])),
                )
                self.assertFalse(reading.has_total_child(reading.rows[cid]))
                self.assertFalse(reading.inside_receipts_subtree(reading.rows[cid]))
        # And the gate's reading of a receipts-subtree header agrees with the exporter's exclusion.
        for cid in tree.receipts_component_ids():
            if cid in reading.rows:
                self.assertTrue(reading.inside_receipts_subtree(reading.rows[cid]), cid)

    def test_a_receipts_type_child_is_one_component_at_its_own_netted_amount(self) -> None:
        """"Military Sales Program:" prints a "Proprietary Receipts from the
        Public" line beneath it; the sum includes it once, as the statement's
        arithmetic does, and the header's amount is the components' sum."""
        tree = section_tree()
        header = next(r for r in tree.rows.values() if r["originalName"] == "Military Sales Program:")
        components = tree.header_components(header)
        self.assertIn("Proprietary Receipts from the Public", [plain_label(r) for r, _ in components])
        self.assertEqual(len(components), 3)
        self.assertAlmostEqual(sum(a for _, a in components), tree.amount(header), places=2)

    def test_zero_is_never_derived_and_a_negative_sum_is_kept(self) -> None:
        def row(cid, parent, label, amount, order):
            return {"name": label.rstrip(":"), "originalName": label, "rollup_total_amount": amount, "is_header": amount is None,
                    "classification_id": cid, "parent_id": parent, "print_order": order, "sequence_level": 1 if parent is None else 2}
        rows = [
            row("1", None, "Agency Zero:", None, 1), row("2", "1", "Up", 5.0, 2), row("3", "1", "Down", -5.0, 3),
            row("4", None, "Agency Negative:", None, 4), row("5", "4", "A", -3.0, 5), row("6", "4", "B", -4.0, 6),
            row("7", None, "Agency Totalled:", None, 7), row("8", "7", "C", 2.0, 8), row("9", "7", "Total--Agency Totalled", 2.0, 9),
            row("10", None, "Agency Empty:", None, 10), row("11", "10", "Sub:", None, 11),
        ]
        derived = {r["originalName"]: r for r in derive_header_sum_rows(SectionTree.from_rows(rows))}
        self.assertEqual(set(derived), {"Agency Negative:"})
        self.assertEqual(derived["Agency Negative:"]["rollup_total_amount"], -7.0)
        self.assertEqual([c["name"] for c in derived["Agency Negative:"]["treasury_component_rows"]], ["A", "B"])

    # -- the neighbours -----------------------------------------------------

    def test_the_curated_node_licence_still_skips_header_rows(self) -> None:
        """`add_curated_nodes.py`'s treasury_statement_line licence indexes
        the rows that could NAME a unit, and a header is not one: it is the
        section's title, and a unit's header beside its own Total-- line is one
        unit reported twice. Left exactly as it was -- the nine total-less
        headers license no new node, and the alias line still does."""
        index = treasury_rows_by_key(statement_payload())
        for _node_id, (printed, _amount, _lines) in NINE.items():
            self.assertNotIn(canonical_name_key(printed.rstrip(":")), index, printed)
        self.assertIn("corporation for national and community service", index)
        self.assertIn("forest service", index)

    def test_the_viewer_copy_carries_the_stamp_the_lines_and_the_sentence(self) -> None:
        for field in TREASURY_HEADER_SUM_FIELDS:
            self.assertIn(field, MINIMAL_GRAPH_FIELDS)
        _, nodes = self._graph(self._build([statement_payload()]))
        pruned = index_tree(prune_graph_for_viewer(json.loads(json.dumps({"id": ROOT_ID, "children": [nodes["exec-dept-va-vha"]]}))))[0]
        vha = pruned["exec-dept-va-vha"]
        self.assertIs(vha["treasury_header_sum"], True)
        self.assertEqual(len(vha["treasury_component_rows"]), 5)
        self.assertEqual(vha["treasury_header_sum_note"], header_sum_note(5))
        self.assertNotIn("treasury_row_name", vha)


if __name__ == "__main__":
    unittest.main()
