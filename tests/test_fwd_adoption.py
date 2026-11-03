"""Federal Workforce Data as the headline headcount: what it matches, how it sits beside FedScope's records, how the
payroll keeps its own source, and every way the gate's mirror refuses a claim that is not the aggregate's."""

from __future__ import annotations

import copy
import json
import sys
import unittest
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
        cls.nodes = list(walk(cls.graph))
        cls.docs = gate.fwd_headcount_documents()

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

    def test_every_fwd_headcount_passes_the_mirror(self):
        for node in self.nodes:
            if node.get("employeesOfficialSource", {}).get("source") == hc.FWD_SOURCE:
                self.assertEqual(gate.fwd_headcount_violations(node, self.docs, label), [], node["id"])

    def sample(self, level, components_min=0):
        for node in self.nodes:
            src = node.get("employeesOfficialSource") or {}
            if src.get("source") == hc.FWD_SOURCE and src.get("level") == level and len(src.get("components") or []) >= components_min:
                return node
        self.fail(f"no FWD node at level {level}")

    def corrupt(self, node, mutate):
        clone = copy.deepcopy(node)
        mutate(clone)
        found = gate.fwd_headcount_violations(clone, self.docs, label)
        self.assertTrue(found, "the corruption was not refused")
        return found

    def test_each_way_a_subagency_headcount_can_be_wrong_is_refused(self):
        node = self.sample("subagency")
        self.corrupt(node, lambda n: n.update(employeesOfficial=n["employeesOfficial"] + 1))
        self.corrupt(node, lambda n: n.update(employeesOfficial=0))
        self.corrupt(node, lambda n: n["employeesOfficialSource"].update(subagencyCode="ZZZZ"))
        self.corrupt(node, lambda n: n["employeesOfficialSource"].update(listedName="SOME OTHER UNIT"))
        self.corrupt(node, lambda n: n["employeesOfficialSource"].update(period="2025-03"))
        self.corrupt(node, lambda n: n["employeesOfficialSource"].update(coverage="an active pay status"))
        self.corrupt(node, lambda n: n["employeesOfficialSource"].update(coverageSource="another page"))
        self.corrupt(node, lambda n: n["employeesOfficialSource"].update(url="https://data.opm.gov/other"))
        self.corrupt(node, lambda n: n["employeesOfficialSource"].update(checkedAt="2026-01-01T00:00:00Z"))
        self.corrupt(node, lambda n: n["employeesOfficialSource"].update(previous={"period": "2025-03", "employees": 1}))
        self.corrupt(node, lambda n: n["employeesOfficialSource"].update(level="region"))
        self.corrupt(node, lambda n: n.update(type="Position"))
        self.corrupt(node, lambda n: n.update(synthetic="treasury_receipts"))

    def test_each_way_an_agency_headcount_can_be_wrong_is_refused(self):
        node = self.sample("agency", components_min=2)
        self.corrupt(node, lambda n: n.update(employeesOfficial=n["employeesOfficial"] + 5))
        self.corrupt(node, lambda n: n["employeesOfficialSource"]["components"].pop())
        self.corrupt(node, lambda n: n["employeesOfficialSource"]["components"][0].update(employees=1))
        self.corrupt(node, lambda n: n["employeesOfficialSource"]["components"][0].update(listedName="OTHER"))
        self.corrupt(node, lambda n: n["employeesOfficialSource"]["components"][0].update(subagencyCode="ZZZZ"))
        self.corrupt(node, lambda n: n["employeesOfficialSource"].update(components=[]))
        self.corrupt(node, lambda n: n["employeesOfficialSource"].update(agencyCode="ZZ"))
        self.corrupt(node, lambda n: n["employeesOfficialSource"].update(listedName="NOT THE AGENCY"))

    def test_a_node_moved_between_two_units_of_one_agency_is_refused(self):
        """Two sub-elements of one agency print different counts, so a record moved from one node to the other keeps
        a real code, a real name and a real period; only the node's own count tells them apart."""
        subs = [n for n in self.nodes if (n.get("employeesOfficialSource") or {}).get("source") == hc.FWD_SOURCE
                and n["employeesOfficialSource"].get("level") == "subagency"]
        by_agency = {}
        for n in subs:
            by_agency.setdefault(n["employeesOfficialSource"]["agencyCode"], []).append(n)
        pair = next(v for v in by_agency.values() if len(v) >= 2 and v[0]["employeesOfficial"] != v[1]["employeesOfficial"])
        a, b = pair[0], pair[1]
        self.corrupt(a, lambda n: n.update(employeesOfficial=b["employeesOfficial"]))

    def test_the_gate_names_an_unknown_source_and_accepts_the_published_graph(self):
        gate_nodes = [n for n in self.nodes if isinstance(n.get("employeesOfficialSource"), dict)]
        known = {hc.FWD_SOURCE, hc.FEDSCOPE_SOURCE}
        self.assertTrue(all(n["employeesOfficialSource"]["source"] in known for n in gate_nodes))


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
