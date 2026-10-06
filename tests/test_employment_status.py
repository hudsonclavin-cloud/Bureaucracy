"""The posts of DOE's sixteen contractor-operated laboratories, published as
not federally paid, pinned in both directions: what the three committed
documents print (and what they do not), what the module derives, what the
exporter stamps, what the gate accepts, and every way a block can be faked.
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
import shutil
import tempfile
import unittest
import uuid
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

from data_pipeline.exporter.build_graph import (
    DEFAULT_BASE_GRAPH,
    MINIMAL_GRAPH_FIELDS,
    build_graph,
    index_tree,
    load_base_graph,
)
from data_pipeline.verification import employment_status as es
from data_pipeline.verification.evidence import EVIDENCE_OWNED_FIELDS, clear_evidence_fields
from data_pipeline.verification.pay_tables import (
    INCUMBENCY_PAY_FIELDS as MODULE_INCUMBENCY,
    OFFICE_RATE_PAY_FIELDS as MODULE_OFFICE_RATE,
    UNIFORM_ROSTER_PAY_FIELDS as MODULE_UNIFORM,
)
from scripts import derive_employment_status_evidence
from scripts import validate_published_graph as gate
from scripts.validate_published_graph import main as gate_main

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"
GRAPH = PROJECT_ROOT / "output" / "graph.json"
TODAY = date.today().isoformat()
ARGONNE = "exec-dept-doe-argonne-national-laboratory"
ARGONNE_DIRECTOR = "exec-dept-doe-argonne-national-laboratory-laboratory-director-argonne-national-laboratory"
BROOKHAVEN = "exec-dept-doe-brookhaven-national-laboratory"
NETL = es.NETL_ID


def _label(node):
    return "node {!r}".format(node.get("id"))


def _walk(node):
    yield node
    for child in node.get("children") or []:
        yield from _walk(child)


def _part_970_text():
    import html
    import re

    raw = (es.FIXTURE_DIR / "dear_48_cfr_970_govinfo2025.xml").read_text(encoding="utf-8")
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def _copy_fixtures(tmp: Path) -> None:
    for spec in es.DOCUMENTS.values():
        for name in (spec["fixture"], spec["fixture"] + ".meta.json"):
            shutil.copy(es.FIXTURE_DIR / name, tmp / name)


def _doctor(tmp: Path, fixture: str, old: bytes, new: bytes, *, fix_digest: bool = True) -> None:
    path = tmp / fixture
    raw = path.read_bytes()
    assert old in raw, old
    path.write_bytes(raw.replace(old, new))
    if fix_digest:
        meta_path = tmp / (fixture + ".meta.json")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        meta_path.write_text(json.dumps(meta), encoding="utf-8")


_BASE = None


def _base_tree():
    global _BASE
    if _BASE is None:
        _BASE = load_base_graph(DEFAULT_BASE_GRAPH)
    return copy.deepcopy(_BASE)


def _records_on(tree, **kwargs):
    node_map, parent_map = index_tree(tree)
    return es.build_records(node_map, parent_map, read_on=TODAY, **kwargs)


def _stamped_tree():
    tree = _base_tree()
    records, _ = _records_on(tree)
    stats = es.apply_employment_status(tree, records, index_tree=index_tree)
    return tree, stats


class DocumentTests(unittest.TestCase):
    """What the committed bytes print, read by the module and by the gate."""

    def test_every_digest_is_the_one_its_fetch_recorded(self):
        for spec in es.DOCUMENTS.values():
            path = es.FIXTURE_DIR / spec["fixture"]
            meta = json.loads((es.FIXTURE_DIR / (spec["fixture"] + ".meta.json")).read_text(encoding="utf-8"))
            self.assertEqual(meta["sha256"], hashlib.sha256(path.read_bytes()).hexdigest(), spec["fixture"])
            self.assertEqual(200, meta["status"])
            self.assertEqual(meta["url"], meta["final_url"])

    def test_both_readers_find_every_quote_and_seventeen_labels(self):
        documents = es.load_documents()
        self.assertEqual(17, len(documents["laboratories"]["laboratoryLabels"]))
        reading = gate.employer_reading()
        self.assertEqual([], reading["problems"])
        self.assertEqual(documents["laboratories"]["laboratoryLabels"], reading["labels"])
        self.assertIn(es.NETL_LISTED_AS, reading["labels"])

    def test_the_netl_page_says_what_the_brief_says_it_says(self):
        quotes = [q["text"] for q in es.DOCUMENTS["operator"]["quotes"]]
        self.assertIn("The other 16 are government-owned, contractor-operated.", quotes[0])
        self.assertIn("NETL is the only government-owned, government-operated facility.", quotes[0])
        self.assertEqual("May 22, 2023", es.DOCUMENTS["operator"]["dated"])

    def test_part_970_never_says_in_words_that_an_operators_staff_are_not_federal_employees(self):
        """The hidden assumption, pinned as a negative against the bytes: the
        regulation says whose judgment sets an M&O contractor employee's pay
        and who finances the contract, and nowhere says 'not Federal
        employees'. The published sentences are worded to that."""
        text = _part_970_text()
        for absent in ("not Federal employees", "not Government employees", "not federal employees",
                       "are not employees of the Government", "not employees of the United States"):
            self.assertNotIn(absent, text)
        self.assertIn("left to the judgment of contractors", text)
        self.assertIn("The contracts are totally financed by DOE advance payments", text)
        self.assertIn("the money is DOE's, through the contract", es.NOT_ESTABLISHED)
        self.assertIn("No document here names who holds this post", es.NOT_ESTABLISHED)

    def test_a_cfr_quote_must_sit_in_the_section_it_names(self):
        wrong = copy.deepcopy(es.DOCUMENTS)
        wrong["regulation"]["quotes"][0]["section"] = "970.0371-7"
        original = es.DOCUMENTS
        es.DOCUMENTS = wrong
        try:
            with self.assertRaisesRegex(es.Unreadable, "970.0371-7 no longer prints"):
                es.load_documents()
        finally:
            es.DOCUMENTS = original

    def test_a_doctored_quote_is_refused_by_both_readers(self):
        cases = (
            ("netl_operating_model.html", b"The other 16 are government-owned, contractor-operated.",
             b"The other 16 are government-owned, government-operated."),
            ("dear_48_cfr_970_govinfo2025.xml", b"left to the judgment of contractors", b"left to the judgment of OPM"),
            ("national_laboratories.html", b"17 National Labs", b"18 National Labs"),
        )
        for fixture, old, new in cases:
            with self.subTest(fixture=fixture), tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                _copy_fixtures(tmp)
                _doctor(tmp, fixture, old, new)
                with self.assertRaises(es.Unreadable):
                    es.load_documents(tmp)
                self.assertTrue(gate.employer_reading(tmp)["problems"])

    def test_bytes_changed_without_their_digest_are_refused_by_both_readers(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            _copy_fixtures(tmp)
            _doctor(tmp, "national_laboratories.html", b"Savannah River", b"Savannah  River", fix_digest=False)
            with self.assertRaisesRegex(es.Unreadable, "sha256"):
                es.load_documents(tmp)
            self.assertTrue(any("sha256" in p for p in gate.employer_reading(tmp)["problems"]))

    def test_an_index_labelling_an_eighteenth_laboratory_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            _copy_fixtures(tmp)
            _doctor(tmp, "national_laboratories.html", b"Savannah River National Laboratory\n",
                    b"Savannah River National Laboratory\n</button></span><button type=\"button\" "
                    b"class=\"usa-accordion__button\" aria-controls=\"energy-accordion-99\">Invented Laboratory\n")
            with self.assertRaisesRegex(es.Unreadable, "labels 18"):
                es.load_documents(tmp)
            self.assertTrue(any("labels 18" in p for p in gate.employer_reading(tmp)["problems"]))


class MirrorTests(unittest.TestCase):
    def test_the_gate_mirrors_the_sixteen_laboratories_by_node_id(self):
        self.assertEqual(
            {lab_id: (row["nodeName"], row["listedAs"]) for lab_id, row in es.CONTRACTOR_OPERATED_LABS.items()},
            gate.EMPLOYER_LABS,
        )
        self.assertEqual(16, len(gate.EMPLOYER_LABS))
        self.assertNotIn(NETL, gate.EMPLOYER_LABS)
        self.assertEqual(es.NETL_ID, gate.EMPLOYER_NETL_ID)
        self.assertEqual(es.NETL_LISTED_AS, gate.EMPLOYER_NETL_LISTED_AS)

    def test_the_gate_mirrors_the_documents_the_constants_and_the_sentences(self):
        mirrored = []
        for role, spec in es.DOCUMENTS.items():
            meta = json.loads((es.FIXTURE_DIR / (spec["fixture"] + ".meta.json")).read_text(encoding="utf-8"))
            mirrored.append((role, spec["fixture"], meta["url"], spec["title"], spec["dated"],
                             tuple((q.get("section"), q["text"]) for q in spec["quotes"])))
        self.assertEqual(tuple(mirrored), gate.EMPLOYER_DOCUMENTS)
        self.assertEqual((es.FIELD, es.KIND, es.METHOD),
                         (gate.EMPLOYER_FIELD, gate.EMPLOYER_KIND, gate.EMPLOYER_METHOD))
        self.assertEqual(es.HEADLINE_TEMPLATE, gate.EMPLOYER_HEADLINE)
        self.assertEqual(es.NOT_ESTABLISHED, gate.EMPLOYER_NOT_ESTABLISHED)
        self.assertEqual(es.LABORATORY_COUNT, gate.EMPLOYER_LABORATORY_COUNT)

    def test_every_pay_field_is_refused_beside_the_block(self):
        every = set(MODULE_INCUMBENCY) | set(MODULE_OFFICE_RATE) | set(MODULE_UNIFORM)
        self.assertEqual(every, set(es.PAY_FIELDS))
        self.assertEqual(every, set(gate.EMPLOYER_PAY_FIELDS))
        self.assertEqual(
            set(gate.INCUMBENCY_PAY_FIELDS) | set(gate.OFFICE_RATE_PAY_FIELDS) | set(gate.UNIFORM_ROSTER_PAY_FIELDS),
            set(gate.EMPLOYER_PAY_FIELDS),
        )

    def test_the_field_is_withdrawn_each_build_and_kept_in_the_viewer_copy(self):
        self.assertIn("positionEmployer", EVIDENCE_OWNED_FIELDS)
        self.assertIn("positionEmployer", MINIMAL_GRAPH_FIELDS)
        node = {"id": "x", "type": "Position", "positionEmployer": {"federallyPaid": False}}
        self.assertTrue(clear_evidence_fields(node, set()))
        self.assertNotIn("positionEmployer", node)


class BuildTests(unittest.TestCase):
    def test_every_post_of_the_sixteen_and_none_of_netls(self):
        tree = _base_tree()
        records, report = _records_on(tree)
        node_map, parent_map = index_tree(tree)
        self.assertEqual({}, report["laboratoriesRefused"])
        self.assertEqual(16, len({r["laboratoryId"] for r in records.values()}))
        expected = sorted(
            child for child, parent in parent_map.items()
            if parent in es.CONTRACTOR_OPERATED_LABS and es._is_post(node_map[child])
        )
        self.assertEqual(expected, sorted(records))
        self.assertEqual(112, len(records))
        self.assertEqual(7, report["netlPostsLeftAlone"])
        self.assertFalse(any(parent_map[post] == NETL for post in records))
        record = records[ARGONNE_DIRECTOR]
        self.assertIs(False, record["federallyPaid"])
        self.assertEqual(3, record["documentCount"])
        self.assertEqual(
            "Not on a federal pay schedule: Argonne National Laboratory is one of the 16 DOE laboratories "
            "operated by a contractor (DOE, NETL page, May 22, 2023).",
            record["headline"],
        )

    def test_a_renamed_moved_or_retyped_laboratory_is_refused(self):
        for change, reason in (
            (lambda n, p: n.__setitem__("name", "Argonne Lab"), "renamed"),
            (lambda n, p: n.__setitem__("type", "Office"), "typed"),
            (lambda n, p: n.__setitem__("lifecycle", "superseded"), "superseded"),
        ):
            with self.subTest(reason=reason):
                tree = _base_tree()
                node_map, _ = index_tree(tree)
                change(node_map[ARGONNE], None)
                records, report = _records_on(tree)
                self.assertIn(reason, report["laboratoriesRefused"][ARGONNE])
                self.assertFalse(any(r["laboratoryId"] == ARGONNE for r in records.values()))
                self.assertEqual(105, len(records))

    def test_a_missing_netl_refuses_the_whole_derivation(self):
        tree = _base_tree()
        node_map, _ = index_tree(tree)
        node_map[NETL]["name"] = "Some Other Laboratory"
        with self.assertRaisesRegex(es.Unreadable, "NETL"):
            _records_on(tree)


class ApplyTests(unittest.TestCase):
    def test_the_block_is_stamped_and_nothing_else_is(self):
        before = _base_tree()
        tree, stats = _stamped_tree()
        self.assertEqual(112, stats["stamped"])
        node_map, _ = index_tree(tree)
        old_map, _ = index_tree(before)
        for node_id, node in node_map.items():
            if "positionEmployer" in node:
                changed = {k for k in set(node) | set(old_map[node_id]) if node.get(k) != old_map[node_id].get(k)}
                self.assertEqual({"positionEmployer"}, changed, node_id)
        netl_posts = [node_id for node_id in node_map if node_id.startswith(NETL + "-")]
        self.assertEqual(7, len(netl_posts))
        self.assertFalse(any("positionEmployer" in node_map[node_id] for node_id in netl_posts))

    def test_a_priced_post_a_moved_post_and_a_renamed_post_are_left_alone(self):
        tree = _base_tree()
        records, _ = _records_on(tree)
        node_map, parent_map = index_tree(tree)
        node_map[ARGONNE_DIRECTOR]["positionGradePay"] = {"minimum": 1}
        moved = "exec-dept-doe-brookhaven-national-laboratory-deputy-laboratory-director"
        brookhaven = node_map[BROOKHAVEN]
        node = next(c for c in brookhaven["children"] if c["id"] == moved)
        brookhaven["children"].remove(node)
        node_map[NETL]["children"].append(node)
        renamed = "exec-dept-doe-argonne-national-laboratory-deputy-laboratory-director"
        node_map[renamed]["name"] = "Chief Operating Officer"
        stats = es.apply_employment_status(tree, records, index_tree=index_tree)
        self.assertEqual(1, stats["carries_a_pay_claim"])
        self.assertEqual(1, stats["under_netl"])
        self.assertEqual(1, stats["renamed_since_the_derivation"])
        self.assertEqual(109, stats["stamped"])
        node_map, _ = index_tree(tree)
        for node_id in (ARGONNE_DIRECTOR, moved, renamed):
            self.assertNotIn("positionEmployer", node_map[node_id])


class GateTests(unittest.TestCase):
    def setUp(self):
        self.tree, _ = _stamped_tree()
        self.node_map, self.parents = index_tree(self.tree)
        self.node = self.node_map[ARGONNE_DIRECTOR]
        self.block = self.node["positionEmployer"]

    def _violations(self, node=None, block=None, parent_id=None, reading=None):
        node = node if node is not None else self.node
        block = block if block is not None else node.get("positionEmployer")
        parent_id = parent_id if parent_id is not None else self.parents.get(node["id"])
        return gate.employer_violations(node, block, TODAY, _label, parent_id, self.node_map.get(parent_id), reading)

    def test_every_honest_block_passes(self):
        for node_id, node in self.node_map.items():
            if "positionEmployer" in node:
                self.assertEqual([], self._violations(node), node_id)

    def assertRefused(self, violations, fragment):
        self.assertTrue(any(fragment in v for v in violations), violations)

    def test_the_block_on_a_netl_post_is_refused(self):
        netl_post = next(c for c in self.node_map[NETL]["children"] if es._is_post(c))
        netl_post = copy.deepcopy(netl_post)
        netl_post["positionEmployer"] = copy.deepcopy(self.block)
        self.assertRefused(self._violations(netl_post, parent_id=NETL), "NETL")

    def test_the_block_on_a_non_post_is_refused(self):
        lab = copy.deepcopy(self.node_map[ARGONNE])
        lab["children"] = []
        lab["positionEmployer"] = copy.deepcopy(self.block)
        self.assertRefused(self._violations(lab, parent_id=es.LABS_GROUP_ID), "is not a post")

    def test_the_block_moved_to_another_laboratorys_post_is_refused(self):
        other = copy.deepcopy(self.node_map["exec-dept-doe-brookhaven-national-laboratory-deputy-laboratory-director"])
        other["positionEmployer"] = copy.deepcopy(self.block)
        self.assertRefused(self._violations(other), "the tree gives it parent")

    def test_each_way_a_block_can_be_faked_is_refused(self):
        def doc(block, role):
            return next(d for d in block["documents"] if d["role"] == role)

        cases = {
            "federallyPaid true": (lambda b: b.__setitem__("federallyPaid", True), "federallyPaid"),
            "federallyPaid missing": (lambda b: b.pop("federallyPaid"), "federallyPaid"),
            "another kind": (lambda b: b.__setitem__("kind", "university_employee"), "kind/method"),
            "another method": (lambda b: b.__setitem__("method", "x"), "kind/method"),
            "a headline of its own": (lambda b: b.__setitem__("headline", "Not federally paid: trust us."), "headline"),
            "no qualifier": (lambda b: b.__setitem__("notEstablished", ""), "no document here establishes"),
            "a paraphrase nothing checks": (lambda b: b.__setitem__("established", "OPM confirms none of these staff are federal."), "keys the module never writes"),
            "an extra document key": (lambda b: doc(b, "regulation").__setitem__("says", "they are not federal employees"), "keys the module never writes"),
            "an extra quote key": (lambda b: doc(b, "regulation")["quotes"][0].__setitem__("gloss", "not federal"), "quotes the regulation document with keys"),
            "another listed label": (lambda b: b.__setitem__("laboratoryListedAs", "Argonne"), "reviewed label"),
            "another laboratory name": (lambda b: b.__setitem__("laboratoryName", "Brookhaven National Laboratory"), "names laboratory"),
            "another laboratory id": (lambda b: b.__setitem__("laboratoryId", BROOKHAVEN), "the tree gives it parent"),
            "a dropped document": (lambda b: b["documents"].pop(), "lists documents"),
            "reordered documents": (lambda b: b["documents"].reverse(), "lists documents"),
            "an edited quote": (lambda b: doc(b, "regulation")["quotes"][1].__setitem__("text", "Employees of a management and operating contractor are not Federal employees."), "quotes the regulation"),
            "a moved section": (lambda b: doc(b, "regulation")["quotes"][0].__setitem__("section", "970.0100"), "quotes the regulation"),
            "another digest": (lambda b: doc(b, "operator").__setitem__("sha256", "0" * 64), "cites digest"),
            "another url": (lambda b: doc(b, "laboratories").__setitem__("url", "https://www.energy.gov/labs"), "cites https://www.energy.gov/labs"),
            "another fetch date": (lambda b: doc(b, "operator").__setitem__("fetchedAt", "2026-01-01T00:00:00Z"), "dates the operator"),
            "another title": (lambda b: doc(b, "regulation").__setitem__("title", "OPM's ruling that lab staff are unpaid"), "names the regulation"),
            "another page date": (lambda b: doc(b, "operator").__setitem__("dated", "May 22, 2026"), "names the operator"),
            "an inflated count": (lambda b: b.__setitem__("documentCount", 4), "counts 4"),
            "a future date": (lambda b: b.__setitem__("readOn", "2999-01-01"), "not a past ISO date"),
        }
        for name, (corrupt, fragment) in cases.items():
            with self.subTest(case=name):
                block = copy.deepcopy(self.block)
                corrupt(block)
                self.assertRefused(self._violations(block=block), fragment)

    def test_beside_any_pay_field_or_a_measured_cost_it_is_refused(self):
        for field in gate.EMPLOYER_PAY_FIELDS:
            with self.subTest(field=field):
                node = copy.deepcopy(self.node)
                node[field] = {"amount": 1.0}
                self.assertRefused(self._violations(node), "carries a pay claim")
        node = copy.deepcopy(self.node)
        node["cost_status"] = "official"
        self.assertRefused(self._violations(node), "beside a measured cost")

    def test_a_document_among_the_nodes_own_sources_is_refused(self):
        for _role, _fixture, url, _title, _dated, _quotes in gate.EMPLOYER_DOCUMENTS:
            with self.subTest(url=url):
                node = copy.deepcopy(self.node)
                node["sourceUrls"] = [url]
                self.assertRefused(self._violations(node), "among its own sources")
        node = copy.deepcopy(self.node)
        node["verificationMethod"] = gate.EMPLOYER_METHOD
        self.assertRefused(self._violations(node), "claims a verification")

    def test_a_renamed_laboratory_refuses_its_posts_blocks(self):
        self.node_map[ARGONNE]["name"] = "Argonne Lab"
        self.assertRefused(self._violations(), "renamed from")

    def test_a_document_the_gate_cannot_read_refuses_every_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            _copy_fixtures(tmp)
            _doctor(tmp, "dear_48_cfr_970_govinfo2025.xml", b"totally financed by DOE", b"partly financed by DOE")
            reading = gate.employer_reading(tmp)
        self.assertRefused(self._violations(reading=reading), "cannot read as cited")

    def test_a_non_dict_block_is_refused(self):
        self.assertRefused(self._violations(block="not federally paid"), "carries a str")


class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TEST_TMP_ROOT / f"employment-{uuid.uuid4().hex}"
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _small_base(self):
        full_map, _ = index_tree(_base_tree())
        labs = [copy.deepcopy(full_map[ARGONNE]), copy.deepcopy(full_map[NETL])]
        group = {"id": es.LABS_GROUP_ID, "name": "National Laboratories", "type": "Division", "children": labs}
        doe = {"id": "exec-dept-doe", "name": "Department of Energy", "type": "Cabinet Department", "children": [group]}
        return {
            "id": "the-constitution-of-the-united-states", "name": "The Constitution of the United States",
            "type": "Foundation", "children": [
                {"id": "legislative-branch", "name": "Legislative Branch", "type": "Branch", "children": []},
                {"id": "executive-branch", "name": "Executive Branch", "type": "Branch", "children": [doe]},
                {"id": "judicial-branch", "name": "Judicial Branch", "type": "Branch", "children": []},
            ],
        }

    def test_derive_then_build_then_gate(self):
        base = self.tmp / "base.json"
        base.write_text(json.dumps(self._small_base()), encoding="utf-8")
        out_path = self.tmp / "employment_status_evidence.json"
        out = io.StringIO()
        with redirect_stdout(out):
            code = derive_employment_status_evidence.main(["d", "--base-graph", str(base), "--out", str(out_path), "--dry-run"])
        self.assertEqual(0, code, out.getvalue())
        self.assertFalse(out_path.exists())
        with redirect_stdout(out):
            code = derive_employment_status_evidence.main(["d", "--base-graph", str(base), "--out", str(out_path), "--read-on", TODAY])
        self.assertEqual(0, code, out.getvalue())
        result = build_graph(
            [{"nodes": [], "edges": [], "budgetSummary": {"government_total_outlay_amount": 1_000_000, "record_date": "2026-06-30"}}],
            base_graph_path=base, graph_output_path=self.tmp / "graph.json", nodes_output_path=self.tmp / "n.json",
            edges_output_path=self.tmp / "e.json", validity_report_output_path=self.tmp / "v.json",
            reuse_existing_graph_payload=False, enforce_export_gate=True,
            evidence_path=None, sites_path=None, employment_status_evidence_path=out_path,
        )
        out2 = io.StringIO()
        with redirect_stdout(out2):
            code = gate_main(["gate", str(result.graph_path)])
        self.assertEqual(0, code, out2.getvalue())
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        stamped = sorted(n["id"] for n in _walk(graph) if "positionEmployer" in n)
        self.assertEqual(7, len(stamped))
        self.assertTrue(all(i.startswith(ARGONNE + "-") for i in stamped))
        self.assertFalse(any("positionEmployer" in n for n in _walk(graph) if n["id"].startswith(NETL + "-")))
        for node in _walk(graph):
            if "positionEmployer" in node:
                self.assertEqual([], node.get("sourceUrls") or [])
                self.assertNotIn("verificationMethod", node)
                self.assertEqual("unavailable", node.get("cost_status"))
        viewer = json.loads((self.tmp / "graph.min.json").read_text(encoding="utf-8"))
        self.assertEqual(7, sum(1 for n in _walk(viewer) if "positionEmployer" in n))

        # Withdrawn on rebuild: the same build handed no evidence publishes none.
        result = build_graph(
            [{"nodes": [], "edges": [], "budgetSummary": {"government_total_outlay_amount": 1_000_000, "record_date": "2026-06-30"}}],
            base_graph_path=base, graph_output_path=self.tmp / "graph.json", nodes_output_path=self.tmp / "n.json",
            edges_output_path=self.tmp / "e.json", validity_report_output_path=self.tmp / "v.json",
            reuse_existing_graph_payload=True, enforce_export_gate=True,
            evidence_path=None, sites_path=None, employment_status_evidence_path=None,
        )
        graph = json.loads(result.graph_path.read_text(encoding="utf-8"))
        self.assertFalse(any("positionEmployer" in n for n in _walk(graph)))


class PublishedGraphTests(unittest.TestCase):
    @unittest.skipUnless(GRAPH.exists(), "no published graph")
    def test_every_published_block_passes_and_none_sits_under_netl(self):
        graph = json.loads(GRAPH.read_text(encoding="utf-8"))
        node_map, parents = index_tree(graph)
        blocks = {i: n for i, n in node_map.items() if "positionEmployer" in n}
        if not blocks:
            self.skipTest("the published graph has not been rebuilt with this evidence yet")
        self.assertEqual(112, len(blocks))
        for node_id, node in blocks.items():
            self.assertNotEqual(NETL, parents[node_id])
            parent = parents[node_id]
            self.assertEqual([], gate.employer_violations(
                node, node["positionEmployer"], TODAY, _label, parent, node_map.get(parent)), node_id)


if __name__ == "__main__":
    unittest.main()
