"""Federal Workforce Data as the headline headcount: what it matches, how it sits beside FedScope's records, how the
payroll keeps its own source, and every way the gate's mirror refuses a claim that is not the aggregate's."""

from __future__ import annotations

import copy
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT, PROJECT_ROOT / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import validate_published_graph as gate  # noqa: E402
from data_pipeline.exporter.build_graph import index_tree, load_base_graph  # noqa: E402
from data_pipeline.verification import fedscope_payroll as fp  # noqa: E402
from data_pipeline.verification import fwd  # noqa: E402
from data_pipeline.verification import headcounts as hc  # noqa: E402

GRAPH = PROJECT_ROOT / "output" / "graph.json"
BASE = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"


def label(node):
    return node.get("id")


def walk(node):
    yield node
    for child in node.get("children") or []:
        yield from walk(child)


class MirrorTests(unittest.TestCase):
    def test_the_gate_s_constants_are_the_module_s(self):
        self.assertEqual(gate.FWD_HEADCOUNT_SOURCE, hc.FWD_SOURCE)
        self.assertEqual(gate.FWD_HEADCOUNT_SOURCE, fwd.FWD_SOURCE)
        self.assertEqual(gate.FWD_AGGREGATE_KIND, fwd.AGGREGATE_KIND)
        self.assertEqual(gate.FWD_COUNT_DEFINITION, fwd.COUNT_DEFINITION)
        self.assertEqual(gate.FWD_COVERAGE, fwd.COVERAGE_STATEMENT)
        self.assertEqual(gate.FWD_COVERAGE_SOURCE, fwd.COVERAGE_SOURCE)
        self.assertEqual(gate.FWD_EXCLUSION_MARKERS, fwd.EXCLUSION_LIST_MARKERS)
        self.assertEqual(gate.FWD_FIXTURE_DIR, fwd.FWD_FIXTURE_DIR)

    def test_the_two_readers_agree_on_the_committed_aggregate(self):
        docs = gate.fwd_headcount_documents()
        payload = fwd.load_aggregate(sorted(p for p in fwd.FWD_FIXTURE_DIR.glob("fwd_employment_agency_subelement_*.json")
                                            if not p.name.endswith(".meta.json"))[-1])
        mine = {(r["agency_code"], r["subagency_code"]): (r["agency_name"], r["subagency_name"], r["employees"])
                for r in fwd.periods_from_aggregate(payload)["2026-08"]}
        self.assertEqual(docs["rows"], mine)
        self.assertEqual(docs["period"], "2026-08")
        self.assertEqual(docs["stream"], payload["stream"])

    def test_the_gate_pins_the_included_bodies_the_name_rule_and_the_coverage_source(self):
        self.assertEqual(gate.FWD_INCLUDED_OUTSIDE_EXECUTIVE, fwd.INCLUDED_OUTSIDE_EXECUTIVE)
        self.assertEqual(gate.FEDSCOPE_COVERAGE_SOURCE, hc.COVERAGE_SOURCE)
        self.assertEqual(gate.FEDSCOPE_HEADCOUNT_SOURCE, hc.FEDSCOPE_SOURCE)
        self.assertEqual(gate.FEDSCOPE_SUPPRESSED_CODE, hc.SUPPRESSED_CODE)
        for name in ("Department of the Treasury", "DEPARTMENT OF ENERGY", "NAT AERONAUTICS AND SPACE ADMINISTRATION",
                     "Internal Revenue Service (IRS)", "U.S. Tax Court", "Government Publishing Office (GPO)", "", None):
            self.assertEqual(gate.headcount_name_keys(name), hc.headcount_name_keys(name), name)

    def test_the_gate_s_counted_rows_are_the_module_s_agency_totals_for_both_tables(self):
        fed = hc.load_fedscope_agency_subagency(hc.DEFAULT_FEDSCOPE_ZIP)["2025-03"]
        rows = [r for r in fed if r["agency_code"] != hc.SUPPRESSED_CODE]
        docs = gate.fedscope_headcount_documents()
        paths = sorted(p for p in fwd.FWD_FIXTURE_DIR.glob("fwd_employment_agency_subelement_*.json") if not p.name.endswith(".meta.json"))
        fwd_rows = fwd.periods_from_aggregate(fwd.load_aggregate(paths[-1]))["2026-08"]
        for table_rows, table in ((rows, docs["periods"]["2025-03"]), (fwd_rows, gate.fwd_headcount_documents()["periods"]["2026-08"])):
            totals = hc.agency_totals(table_rows)
            for code, total in totals.items():
                name, counted, total_key = gate.headcount_counted_rows(table, code)
                self.assertEqual(name, total["name"], code)
                self.assertEqual(sorted(k[1] for k in counted), sorted(c["subagencyCode"] for c in total["components"]), code)
                self.assertEqual(sum(v[2] for v in counted.values()), total["employees"], code)
                self.assertEqual(total_key is not None, total["total_row"] is not None, code)

    def test_both_sources_are_headcount_sources_and_nothing_else_is(self):
        self.assertEqual(set(hc.HEADCOUNT_SOURCES), {hc.FEDSCOPE_SOURCE, hc.FWD_SOURCE})


class MatchTests(unittest.TestCase):
    """What the one matcher makes of the committed August 2026 aggregate, pinned so a change is noticed."""

    @classmethod
    def setUpClass(cls):
        cls.root = load_base_graph(BASE)
        cls.node_map, cls.parent_map = index_tree(cls.root)
        paths = sorted(p for p in fwd.FWD_FIXTURE_DIR.glob("fwd_employment_agency_subelement_*.json") if not p.name.endswith(".meta.json"))
        cls.payload = fwd.load_aggregate(paths[-1])
        meta = fwd.load_fwd_meta(paths[-1])
        cls.records, cls.report = hc.match_fedscope(
            fwd.periods_from_aggregate(cls.payload), cls.node_map, cls.parent_map, root_id=str(cls.root["id"]),
            url=meta["url"], fetched_at=meta["fetched_at"], file=paths[-1].name,
            coverage=fwd.COVERAGE_STATEMENT, source=hc.FWD_SOURCE, coverage_source=fwd.COVERAGE_SOURCE,
            included_outside=fwd.INCLUDED_OUTSIDE_EXECUTIVE,
        )

    def test_the_counts(self):
        self.assertEqual(len(self.records), 186)
        self.assertEqual((self.report["agencies_matched"], self.report["subagencies_matched"]), (85, 101))
        self.assertEqual(self.report["total_employees"], 2_024_832)
        self.assertEqual(self.report["matched_employees"], 1_476_824)
        self.assertEqual(self.report["period"], "2026-08")
        self.assertIsNone(self.report["previous_period"])

    def test_every_record_names_its_source_its_period_and_the_pages_own_coverage(self):
        for node_id, record in self.records.items():
            self.assertEqual(record["source"], hc.FWD_SOURCE, node_id)
            self.assertEqual(record["period"], "2026-08", node_id)
            self.assertEqual(record["coverage"], fwd.COVERAGE_STATEMENT, node_id)
            self.assertEqual(record["coverageSource"], fwd.COVERAGE_SOURCE, node_id)
            self.assertIsNone(record["previous"], node_id)

    def test_the_page_s_included_bodies_are_not_called_outside_its_coverage(self):
        """GPO and the Tax Court sit outside the Executive Branch and the page lists both as included in the dataset."""
        for node_id in ("leg-support-gpo", "jud-specialized-tax"):
            rec = self.records[node_id] if node_id in self.records else None
            self.assertIsNotNone(rec, node_id)
        self.assertNotIn("outsideStatedCoverage", self.records["leg-support-gpo"])
        self.assertEqual(self.records["leg-support-gpo"]["listedAsIncludedOutsideExecutive"], "Government Printing Office")
        self.assertEqual(self.records["jud-specialized-tax"]["listedAsIncludedOutsideExecutive"], "U.S. Tax Court")
        self.assertEqual(self.report["matched_outside_executive_branch"], [])
        self.assertEqual({r["node"] for r in self.report["listed_as_included_outside_executive_branch"]},
                         {"leg-support-gpo", "jud-specialized-tax"})

    def test_without_the_table_the_old_rule_still_flags_a_body_outside_the_executive_branch(self):
        paths = sorted(p for p in fwd.FWD_FIXTURE_DIR.glob("fwd_employment_agency_subelement_*.json") if not p.name.endswith(".meta.json"))
        records, report = hc.match_fedscope(
            fwd.periods_from_aggregate(fwd.load_aggregate(paths[-1])), self.node_map, self.parent_map, root_id=str(self.root["id"]),
            source=hc.FWD_SOURCE, coverage=fwd.COVERAGE_STATEMENT, coverage_source=fwd.COVERAGE_SOURCE)
        self.assertTrue(records["leg-support-gpo"]["outsideStatedCoverage"])
        self.assertNotIn("listedAsIncludedOutsideExecutive", records["leg-support-gpo"])
        self.assertEqual(len(report["matched_outside_executive_branch"]), 2)

    def test_the_reviewed_included_table_names_labels_the_page_prints_and_nodes_that_exist(self):
        listed = fwd.included_outside_executive_labels()
        self.assertEqual(len(listed), 8)
        for node_id, label_text in fwd.INCLUDED_OUTSIDE_EXECUTIVE.items():
            self.assertIn(label_text, listed)
            self.assertIn(node_id, self.node_map)

    def test_nine_small_bodies_gain_a_headcount_and_five_units_keep_fedscope_s(self):
        fedscope = json.loads((PROJECT_ROOT / "data" / "verification" / "fedscope_headcount_evidence.json").read_text(encoding="utf-8"))["nodes"]
        self.assertEqual(len(set(self.records) - set(fedscope)), 9)
        self.assertEqual(sorted(set(fedscope) - set(self.records)), [
            "exec-dept-defense-agency-defense-acquisition-university", "exec-dept-doc-national-technical-information-service",
            "exec-dept-doi-boem", "exec-dept-doi-bsee", "exec-ind-smithsonian-woodrow-wilson-international-center-scholars"])


def tiny_tree():
    return {
        "id": "root", "name": "Root", "type": "Constitution", "children": [{
            "id": "exec", "name": "Executive Branch", "type": "Branch", "children": [
                {"id": "unit", "name": "Unit One", "type": "Agency", "children": []},
                {"id": "post", "name": "Unit One Director", "type": "Position", "children": []},
            ]}],
    }


def record(source, employees, **extra):
    base = {"source": source, "listedName": "UNIT ONE", "level": "subagency", "agencyCode": "AA", "subagencyCode": "AA01",
            "period": "2026-08" if source == hc.FWD_SOURCE else "2025-03", "coverage": "c", "coverageSource": "s",
            "url": "https://data.opm.gov/x", "checkedAt": "2026-11-03T00:00:00Z", "employees": employees}
    base.update(extra)
    return base


class ApplyTests(unittest.TestCase):
    def test_fwd_over_fedscope_where_both_name_a_unit_and_fedscope_alone_where_fwd_does_not(self):
        tree = tiny_tree()
        fed = {"unit": record(hc.FEDSCOPE_SOURCE, 100)}
        hc.apply_headcount_evidence(tree, fed)
        node = tree["children"][0]["children"][0]
        self.assertEqual((node["employeesOfficial"], node["employeesOfficialSource"]["source"]), (100, hc.FEDSCOPE_SOURCE))
        hc.apply_headcount_evidence(tree, {"unit": record(hc.FWD_SOURCE, 90)})
        self.assertEqual((node["employeesOfficial"], node["employeesOfficialSource"]["source"]), (90, hc.FWD_SOURCE))
        self.assertEqual(node["employeesOfficialSource"]["period"], "2026-08")

    def test_a_fedscope_only_unit_keeps_fedscope_s_dated_count(self):
        tree = tiny_tree()
        hc.apply_headcount_evidence(tree, {"unit": record(hc.FEDSCOPE_SOURCE, 100)})
        hc.apply_headcount_evidence(tree, {})
        node = tree["children"][0]["children"][0]
        self.assertEqual(node["employeesOfficialSource"]["period"], "2025-03")

    def test_an_unknown_source_publishes_nothing(self):
        tree = tiny_tree()
        stats = hc.apply_headcount_evidence(tree, {"unit": record("some_other_table", 5)})
        self.assertNotIn("employeesOfficial", tree["children"][0]["children"][0])
        self.assertEqual(stats["undated"], 1)


class PayrollRecordsTests(unittest.TestCase):
    """The payroll is applied from FedScope's own records, whatever the headline headcount is."""

    def test_the_payroll_comes_from_the_fedscope_record_and_carries_its_own_count_and_period(self):
        tree = tiny_tree()
        rows = {("2025-03", "AA01"): (100, 70000)}
        fed = record(hc.FEDSCOPE_SOURCE, 100)
        original = fp.load_avgsal_rows
        fp.load_avgsal_rows = lambda zip_path=None: rows
        try:
            stats = fp.apply_payroll_evidence(tree, {"unit": fed})
        finally:
            fp.load_avgsal_rows = original
        node = tree["children"][0]["children"][0]
        self.assertEqual(stats["published"], 1)
        self.assertEqual((node["payrollOfficial"]["period"], node["payrollOfficial"]["employees"], node["payrollOfficial"]["totalAnnualPay"]),
                         ("2025-03", 100, 7_000_000))

    def test_an_fwd_record_never_prices_a_payroll_and_a_post_never_carries_one(self):
        tree = tiny_tree()
        stats = fp.apply_payroll_evidence(tree, {"unit": record(hc.FWD_SOURCE, 100), "post": record(hc.FEDSCOPE_SOURCE, 1)})
        self.assertEqual(stats["published"], 0)
        self.assertEqual(stats["post_refused"], 1)
        self.assertNotIn("payrollOfficial", tree["children"][0]["children"][0])

    def test_a_renamed_unit_keeps_no_payroll_earned_by_its_old_name(self):
        tree = tiny_tree()
        tree["children"][0]["children"][0]["name"] = "Something Else Entirely"
        stats = fp.apply_payroll_evidence(tree, {"unit": record(hc.FEDSCOPE_SOURCE, 100)})
        self.assertEqual((stats["stale_name"], stats["published"]), (1, 0))

    def test_no_records_clears_every_payroll(self):
        tree = tiny_tree()
        tree["children"][0]["children"][0]["payrollOfficial"] = {"stale": True}
        fp.apply_payroll_evidence(tree, {})
        self.assertNotIn("payrollOfficial", tree["children"][0]["children"][0])


@unittest.skipUnless(GRAPH.exists(), "no published graph")
class PublishedGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = json.loads(GRAPH.read_text(encoding="utf-8"))
        cls.pairs = []
        stack = [(cls.graph, None)]
        while stack:
            node, parent = stack.pop()
            cls.pairs.append((node, parent))
            stack.extend((c, node) for c in node.get("children") or [])
        cls.nodes = [n for n, _ in cls.pairs]
        cls.by_id = {n["id"]: n for n in cls.nodes}
        cls.parents = {n["id"]: str((p or {}).get("id") or "") for n, p in cls.pairs}
        cls.fwd_docs = gate.fwd_headcount_documents()
        cls.fed_docs = gate.fedscope_headcount_documents()
        cls.docs = {hc.FWD_SOURCE: cls.fwd_docs, hc.FEDSCOPE_SOURCE: cls.fed_docs}
        cls.ctx = gate.headcount_gate_context(cls.nodes, cls.parents, cls.by_id)

    def test_the_mix_of_sources_on_the_graph(self):
        counts = {}
        for node in self.nodes:
            if isinstance(node.get("employeesOfficial"), int):
                src = node["employeesOfficialSource"]["source"]
                counts[src] = counts.get(src, 0) + 1
        self.assertEqual(counts, {hc.FWD_SOURCE: 186, hc.FEDSCOPE_SOURCE: 5})

    def test_a_node_fwd_names_carries_fwd_and_the_payroll_still_says_march_2025(self):
        both = [n for n in self.nodes if n.get("payrollOfficial") and n.get("employeesOfficialSource", {}).get("source") == hc.FWD_SOURCE]
        self.assertGreater(len(both), 100)
        for node in both:
            self.assertEqual(node["payrollOfficial"]["period"], "2025-03", node["id"])
            self.assertEqual(node["employeesOfficialSource"]["period"], "2026-08", node["id"])

    def test_every_published_headcount_passes_the_gate_with_its_tree_context(self):
        for node in self.nodes:
            src = node.get("employeesOfficialSource")
            if isinstance(src, dict):
                self.assertEqual(gate.headcount_table_violations(node, self.docs[src["source"]], label, self.ctx), [], node["id"])

    def test_the_union_of_published_source_keys_is_inside_the_gate_s_list(self):
        keys = set()
        for node in self.nodes:
            if isinstance(node.get("employeesOfficialSource"), dict):
                keys |= set(node["employeesOfficialSource"])
        self.assertLessEqual(keys, set(gate.HEADCOUNT_SOURCE_KEYS))

    # -- corruption helpers ------------------------------------------------------------------------------

    def sample(self, source, level, components_min=0):
        for node in self.nodes:
            src = node.get("employeesOfficialSource") or {}
            if src.get("source") == source and src.get("level") == level and len(src.get("components") or []) >= components_min:
                return node
        self.fail(f"no {source} node at level {level}")

    def refused(self, node, mutate, source=None, ctx=None):
        clone = copy.deepcopy(node)
        mutate(clone)
        found = gate.headcount_table_violations(clone, self.docs[source or node["employeesOfficialSource"]["source"]], label, ctx or self.ctx)
        self.assertTrue(found, "the corruption was not refused")
        return found

    # -- the count, the name and the coverage ------------------------------------------------------------

    def test_each_way_a_subagency_headcount_can_be_wrong_is_refused(self):
        node = self.sample(hc.FWD_SOURCE, "subagency")
        for mutate in (
            lambda n: n.update(employeesOfficial=n["employeesOfficial"] + 1),
            lambda n: n.update(employeesOfficial=0),
            lambda n: n.update(employeesOfficial=True),
            lambda n: n["employeesOfficialSource"].update(subagencyCode="ZZZZ"),
            lambda n: n["employeesOfficialSource"].update(listedName="SOME OTHER UNIT"),
            lambda n: n["employeesOfficialSource"].update(period="2025-03"),
            lambda n: n["employeesOfficialSource"].update(coverage="an active pay status"),
            lambda n: n["employeesOfficialSource"].update(coverageSource="another page"),
            lambda n: n["employeesOfficialSource"].update(url="https://data.opm.gov/other"),
            lambda n: n["employeesOfficialSource"].update(checkedAt="2026-01-01T00:00:00Z"),
            lambda n: n["employeesOfficialSource"].update(previous={"period": "2025-03", "employees": 1}),
            lambda n: n["employeesOfficialSource"].update(level="region"),
            lambda n: n["employeesOfficialSource"].update(components=[{"subagencyCode": "X", "listedName": "Y", "employees": 1}]),
            lambda n: n["employeesOfficialSource"].update(invented="a key the pipeline never writes"),
            lambda n: n["employeesOfficialSource"].update(wholeAgency=not n["employeesOfficialSource"].get("wholeAgency", False)),
            lambda n: n["employeesOfficialSource"].update(subtreeRecordsExceedIt=10**9),
            lambda n: n["employeesOfficialSource"].update(outsideStatedCoverage=True),
            lambda n: n["employeesOfficialSource"].update(agencyMatched="exec-dept-defense-army-chief-of-staff-of-the-army-4-star-general"),
            lambda n: n.update(type="Position"),
            lambda n: n.update(synthetic="treasury_receipts"),
        ):
            with self.subTest(mutate=mutate):
                self.refused(node, mutate)

    def test_each_way_an_agency_headcount_can_be_wrong_is_refused(self):
        node = self.sample(hc.FWD_SOURCE, "agency", components_min=2)
        for mutate in (
            lambda n: n.update(employeesOfficial=n["employeesOfficial"] + 5),
            lambda n: n["employeesOfficialSource"]["components"].pop(),
            lambda n: n["employeesOfficialSource"]["components"].append(dict(n["employeesOfficialSource"]["components"][0])),
            lambda n: n["employeesOfficialSource"]["components"][0].update(employees=1),
            lambda n: n["employeesOfficialSource"]["components"][0].update(listedName="OTHER"),
            lambda n: n["employeesOfficialSource"]["components"][0].update(subagencyCode="ZZZZ"),
            lambda n: n["employeesOfficialSource"]["components"][0].update(extra=1),
            lambda n: n["employeesOfficialSource"].update(components=[]),
            lambda n: n["employeesOfficialSource"].update(agencyCode="ZZ"),
            lambda n: n["employeesOfficialSource"].update(listedName="NOT THE AGENCY"),
            lambda n: n["employeesOfficialSource"].update(subagencyCode="X"),
        ):
            with self.subTest(mutate=mutate):
                self.refused(node, mutate)

    # -- the identity of the node a block sits on (the review's F1, F3 and F4) -----------------------------

    def test_a_whole_block_moved_to_another_node_is_refused_on_both_nodes(self):
        a = self.by_id["exec-dept-treasury-irs"] if "exec-dept-treasury-irs" in self.by_id else None
        subs = [n for n in self.nodes if (n.get("employeesOfficialSource") or {}).get("source") == hc.FWD_SOURCE
                and n["employeesOfficialSource"].get("level") == "subagency"]
        a, b = subs[0], subs[1]
        self.assertNotEqual(canon(a["name"]), canon(b["name"]))
        a_copy, b_copy = copy.deepcopy(a), copy.deepcopy(b)
        a_copy["employeesOfficial"], a_copy["employeesOfficialSource"] = b["employeesOfficial"], copy.deepcopy(b["employeesOfficialSource"])
        b_copy["employeesOfficial"], b_copy["employeesOfficialSource"] = a["employeesOfficial"], copy.deepcopy(a["employeesOfficialSource"])
        for moved in (a_copy, b_copy):
            self.assertTrue(gate.headcount_table_violations(moved, self.fwd_docs, label, self.ctx), moved["id"])

    def test_an_agency_block_copied_onto_an_unrelated_organisation_is_refused(self):
        va = self.sample(hc.FWD_SOURCE, "agency", components_min=2)
        gao = copy.deepcopy(self.by_id["leg-support-gao"] if "leg-support-gao" in self.by_id else next(n for n in self.nodes if "Government Accountability" in str(n.get("name"))))
        gao["employeesOfficial"], gao["employeesOfficialSource"] = va["employeesOfficial"], copy.deepcopy(va["employeesOfficialSource"])
        found = gate.headcount_table_violations(gao, self.fwd_docs, label, self.ctx)
        self.assertTrue(any("does not name this node" in f for f in found), found)

    def test_a_renamed_node_keeps_no_headcount_earned_by_its_old_name(self):
        node = self.sample(hc.FWD_SOURCE, "subagency")
        found = self.refused(node, lambda n: n.update(name="Totally Different Unit"))
        self.assertTrue(any("does not name this node" in f for f in found), found)

    def test_a_row_carried_by_two_nodes_is_refused(self):
        node = self.sample(hc.FWD_SOURCE, "subagency")
        clone = copy.deepcopy(node)
        clone["id"] = "clone-of-" + node["id"]
        parents = dict(self.parents)
        parents[clone["id"]] = self.parents[node["id"]]
        by_id = dict(self.by_id)
        by_id[clone["id"]] = clone
        ctx = gate.headcount_gate_context(self.nodes + [clone], parents, by_id)
        found = gate.headcount_table_violations(node, self.fwd_docs, label, ctx)
        self.assertTrue(any("carried by 2 nodes" in f for f in found), found)

    def test_the_outside_the_branch_flags_follow_the_page(self):
        gpo = self.by_id["leg-support-gpo"]
        self.assertIn("listedAsIncludedOutsideExecutive", gpo["employeesOfficialSource"])
        self.refused(gpo, lambda n: n["employeesOfficialSource"].pop("listedAsIncludedOutsideExecutive"))
        self.refused(gpo, lambda n: n["employeesOfficialSource"].update(outsideStatedCoverage=True))
        self.refused(gpo, lambda n: n["employeesOfficialSource"].update(listedAsIncludedOutsideExecutive="Some Other Body"))
        ordinary = self.sample(hc.FWD_SOURCE, "subagency")
        self.refused(ordinary, lambda n: n["employeesOfficialSource"].update(listedAsIncludedOutsideExecutive="Government Printing Office"))

    # -- the FedScope-sourced headcounts, re-read against the committed zip (F3 and F5) ----------------------

    def test_a_fedscope_headcount_is_re_read_against_the_committed_table(self):
        node = self.sample(hc.FEDSCOPE_SOURCE, "subagency")
        self.assertEqual(gate.headcount_table_violations(node, self.fed_docs, label, self.ctx), [])
        for mutate in (
            lambda n: n.update(employeesOfficial=n["employeesOfficial"] + 1),
            lambda n: n["employeesOfficialSource"].update(period="2024-09"),
            lambda n: n["employeesOfficialSource"].update(period="2026-08"),
            lambda n: n["employeesOfficialSource"].update(listedName="SOMETHING ELSE"),
            lambda n: n["employeesOfficialSource"].update(coverage=fwd.COVERAGE_STATEMENT),
            lambda n: n["employeesOfficialSource"].update(previous={"period": "2019-01", "employees": 1}),
            lambda n: n.update(name="Totally Different Unit"),
            lambda n: n.update(type="Position"),
        ):
            with self.subTest(mutate=mutate):
                self.refused(node, mutate)

    def test_relabelling_a_block_as_the_other_table_s_is_refused(self):
        fed = self.sample(hc.FEDSCOPE_SOURCE, "subagency")
        found = self.refused(fed, lambda n: n["employeesOfficialSource"].update(source=hc.FWD_SOURCE), source=hc.FWD_SOURCE)
        self.assertTrue(found)
        fwd_node = self.sample(hc.FWD_SOURCE, "subagency")
        self.refused(fwd_node, lambda n: n["employeesOfficialSource"].update(source=hc.FEDSCOPE_SOURCE), source=hc.FEDSCOPE_SOURCE)

    # -- the payroll's tie to its node (F4) ------------------------------------------------------------------

    def payroll_violations(self, node):
        rows, digest = gate.fedscope_payroll_rows()
        return gate.fedscope_payroll_violations(node, node["payrollOfficial"], rows, digest, label, self.fed_docs["periods"])

    def test_every_published_payroll_passes_with_its_tie(self):
        for node in self.nodes:
            if "payrollOfficial" in node:
                self.assertEqual(self.payroll_violations(node), [], node["id"])

    def test_a_payroll_moved_to_another_unit_is_refused(self):
        with_payroll = [n for n in self.nodes if "payrollOfficial" in n]
        a, b = with_payroll[0], next(n for n in with_payroll if canon(n["name"]) != canon(with_payroll[0]["name"]))
        moved = copy.deepcopy(a)
        moved["payrollOfficial"] = copy.deepcopy(b["payrollOfficial"])
        found = self.payroll_violations(moved)
        self.assertTrue(any("do not name this node" in f for f in found), found)

    def test_a_payroll_copied_onto_a_node_no_table_row_names_is_refused(self):
        a = next(n for n in self.nodes if "payrollOfficial" in n)
        stranger = copy.deepcopy(next(n for n in self.nodes if n.get("type") == "Agency" and "payrollOfficial" not in n
                                      and isinstance(n.get("employeesOfficial"), int)))
        stranger["payrollOfficial"] = copy.deepcopy(a["payrollOfficial"])
        self.assertTrue(self.payroll_violations(stranger))

    def test_an_agency_payroll_missing_a_row_is_refused(self):
        node = next(n for n in self.nodes if "payrollOfficial" in n and len(n["payrollOfficial"]["rows"]) > 2)
        clone = copy.deepcopy(node)
        clone["payrollOfficial"]["rows"].pop()
        found = self.payroll_violations(clone)
        self.assertTrue(any("not exactly the agency's counted rows" in f for f in found), found)

    def test_a_payroll_beside_a_boolean_headcount_is_refused(self):
        node = copy.deepcopy(next(n for n in self.nodes if "payrollOfficial" in n))
        node["employeesOfficial"] = True
        self.assertTrue(any("no official headcount" in f for f in self.payroll_violations(node)))

    # -- the full gate: a dispute cites the headcount beside it (F6) -----------------------------------------

    def test_the_full_gate_refuses_a_dispute_that_cites_another_source_or_period(self):
        graph = json.loads(GRAPH.read_text(encoding="utf-8"))
        target = next(n for n, _ in walk_pairs(graph) if isinstance(n.get("cost_weight_dispute"), dict))
        target["cost_weight_dispute"]["source"] = hc.FEDSCOPE_SOURCE
        target["cost_weight_dispute"]["period"] = "2025-03"
        tmp = PROJECT_ROOT / "tests" / "_fwd_gate_tmp.json"
        try:
            tmp.write_text(json.dumps(graph), encoding="utf-8")
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = gate.main(["gate", str(tmp)])
        finally:
            tmp.unlink(missing_ok=True)
        self.assertEqual(code, 1)
        self.assertIn("other than the headcount beside it", buffer.getvalue())

    def test_the_full_gate_refuses_an_official_headcount_with_no_source_block(self):
        graph = json.loads(GRAPH.read_text(encoding="utf-8"))
        target = next(n for n, _ in walk_pairs(graph) if isinstance(n.get("employeesOfficialSource"), dict))
        del target["employeesOfficialSource"]
        tmp = PROJECT_ROOT / "tests" / "_fwd_gate_tmp2.json"
        try:
            tmp.write_text(json.dumps(graph), encoding="utf-8")
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = gate.main(["gate", str(tmp)])
        finally:
            tmp.unlink(missing_ok=True)
        self.assertEqual(code, 1)
        self.assertIn("carries an official headcount with no source block", buffer.getvalue())


def canon(name):
    return gate.canonical_key(name)


def walk_pairs(node, parent=None):
    yield node, parent
    for child in node.get("children") or []:
        yield from walk_pairs(child, node)


class DocumentCorruptionTests(unittest.TestCase):
    def test_the_gate_reader_refuses_a_changed_aggregate(self):
        import hashlib
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for source in fwd.FWD_FIXTURE_DIR.iterdir():
                if source.is_file():
                    (directory / source.name).write_bytes(source.read_bytes())
            original = gate.FWD_FIXTURE_DIR
            gate.FWD_FIXTURE_DIR = directory
            try:
                gate.fwd_headcount_documents()
                aggregate = sorted(p for p in directory.glob("fwd_employment_agency_subelement_*.json") if not p.name.endswith(".meta.json"))[-1]
                aggregate.write_bytes(aggregate.read_bytes().replace(b'"records": 1', b'"records": 2', 1))
                with self.assertRaises(ValueError):
                    gate.fwd_headcount_documents()
                # a re-digested aggregate whose rows no longer sum to the stream's count is refused on that ground
                meta = aggregate.with_name(aggregate.name + ".meta.json")
                data = json.loads(meta.read_text())
                data["sha256"] = hashlib.sha256(aggregate.read_bytes()).hexdigest()
                meta.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    gate.fwd_headcount_documents()
            finally:
                gate.FWD_FIXTURE_DIR = original


if __name__ == "__main__":
    unittest.main()
