"""The VA's Title 38 pay RANGES: the parser, exactly which 36 nodes it bands
and why nothing else, and every way a forged band could reach the release gate.

Both directions throughout: an honest band is published, and each way of
forging one is caught.

One test here exists because a research pass reported a title the document
does not print. It asserts the absence directly, so if the VA ever does add
"Medical Center Director" to this schedule the test fails and somebody looks,
rather than the graph quietly continuing to withhold a band it could give.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from data_pipeline.exporter.build_graph import index_tree
from data_pipeline.verification.va_title38_pay import (
    DEFAULT_PAY_PDF,
    NODE_NAME_PARENT,
    NODE_NAME_TO_COVERAGE,
    SCOPED_OFFICE_TO_COVERAGE,
    TABLE_4_LABEL,
    TABLE_LABEL,
    Unreadable,
    _text_runs,
    apply_pay_evidence,
    build_records,
    load_pay_tables,
    parse_pay_tables,
)
from scripts.validate_published_graph import (
    VA_TITLE38_EFFECTIVE_TEXT,
    VA_TITLE38_NEVER_PRICED,
    VA_TITLE38_TABLES,
    VA_TITLE38_TIERS,
    VA_TITLE38_URL,
    tier_pay_violations,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PDF = DEFAULT_PAY_PDF.read_bytes()
DOC_TEXT = " ".join(" ".join(run.split()) for run in _text_runs(PDF))


def _label(node):
    return "node {!r}".format(node.get("id"))


def _base_tree():
    return {
        "id": "the-constitution-of-the-united-states",
        "name": "The Constitution",
        "type": "Foundation",
        "children": [
            {
                "id": "vha",
                "name": "Veterans Health Administration (VHA)",
                "type": "Administration",
                "children": [
                    {
                        "id": "vamcs",
                        "name": "VA Medical Centers",
                        "type": "Facility Group",
                        "children": [
                            {"id": "cos-1", "name": "VAMC Chief of Staff (Medical)", "type": "Position"},
                            {"id": "dir-1", "name": "VAMC Director", "type": "Position"},
                            {"id": "nope-1", "name": "VAMC Deputy Director of Nothing", "type": "Position"},
                            {"id": "ad-1", "name": "VAMC Associate Director (Administrative)", "type": "Position"},
                            {"id": "svc-1", "name": "Chief — Surgery Service", "type": "Position"},
                            {"id": "fin-1", "name": "Chief — Finance", "type": "Position"},
                        ],
                    },
                    {
                        "id": "visn-1",
                        "name": "VISN 1 — New England",
                        "type": "VISN",
                        "children": [
                            {"id": "cmo-1", "name": "Chief Medical Officer, VISN 1 — New England", "type": "Position"},
                            {"id": "nd-1", "name": "Network Director, VISN 1 — New England", "type": "Position"},
                        ],
                    },
                    {"id": "vha-cos", "name": "Chief of Staff, VHA", "type": "Position"},
                ],
            },
        ],
    }


def _parents(root):
    out = {}

    def walk(node):
        for child in node.get("children") or []:
            out[child["id"]] = node["id"]
            walk(child)

    walk(root)
    return out


class DocumentTests(unittest.TestCase):
    def test_the_committed_pdf_yields_both_read_tables_with_three_tiers_each(self):
        tables = parse_pay_tables(PDF)["tables"]
        self.assertEqual(sorted(tables), ["3", "4"])
        self.assertEqual(tables["3"]["table"], TABLE_LABEL)
        self.assertEqual(tables["4"]["table"], TABLE_4_LABEL)
        for number, table in tables.items():
            self.assertEqual(len(table["rows"]), 3, number)

    def test_the_gate_s_mirror_equals_what_the_schedule_prints(self):
        tables = parse_pay_tables(PDF)["tables"]
        for coverage, (number, tier, minimum, maximum) in VA_TITLE38_TIERS.items():
            rows = [r for r in tables[number]["rows"] if coverage in r["coverageItems"]]
            self.assertEqual(len(rows), 1, f"{coverage!r} is not one whole printed item of table {number}")
            self.assertEqual(rows[0]["tier"], tier, coverage)
            self.assertEqual(rows[0]["minimum"], minimum, coverage)
            self.assertEqual(rows[0]["maximum"], maximum, coverage)

    def test_the_gate_s_tables_and_effective_line_are_the_document_s_own(self):
        self.assertEqual(VA_TITLE38_TABLES["3"], TABLE_LABEL)
        self.assertEqual(VA_TITLE38_TABLES["4"], TABLE_4_LABEL)
        self.assertIn(VA_TITLE38_EFFECTIVE_TEXT, DOC_TEXT)

    def test_every_priced_title_is_printed_and_every_refused_one_is_not(self):
        # A first pass at this module asserted the opposite of the first half
        # -- that the schedule prints no "Medical Center Director" and no
        # "Network Director" -- and refused 36 nodes on an ad-hoc grep whose
        # text reconstruction had dropped runs. Both directions are asserted
        # against the committed bytes here so neither claim can rest on
        # anybody's memory of a search again.
        for printed in ("Medical Center Directors", "Network Directors", "Chief of Staff",
                        "Network Chief Medical Officer"):
            self.assertIn(printed, DOC_TEXT, f"the schedule no longer prints {printed!r}")
        for absent in ("Associate Director", "VISN"):
            self.assertNotIn(absent, DOC_TEXT, f"the schedule now prints {absent!r}; the refusals need revisiting")

    def test_an_encrypted_or_reshaped_document_yields_nothing(self):
        # The text lives in zlib streams, so a byte replace on the file is a
        # no-op; these corrupt the container instead, which is what a reshaped
        # publication actually looks like from here.
        attacks = {
            "not a pdf": b"hello",
            "encrypted": b"%PDF-1.6\n/Encrypt 1 0 R\n",
            "no text streams": b"%PDF-1.6\n" + b"x" * 400,
        }
        for name, corrupted in attacks.items():
            with self.subTest(attack=name):
                with self.assertRaises(Unreadable):
                    parse_pay_tables(corrupted)

    def test_a_tampered_fixture_is_refused_by_digest(self):
        import shutil
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / DEFAULT_PAY_PDF.name
            shutil.copy(DEFAULT_PAY_PDF, copy)
            shutil.copy(DEFAULT_PAY_PDF.with_name(DEFAULT_PAY_PDF.name + ".meta.json"),
                        copy.with_name(copy.name + ".meta.json"))
            copy.write_bytes(PDF + b"\n% tampered")
            with self.assertRaises(Unreadable):
                load_pay_tables(copy)


class ScopeTests(unittest.TestCase):
    def _records(self, tree=None):
        tree = tree or _base_tree()
        node_map, _ = index_tree(tree)
        return tree, build_records(
            node_map, _parents(tree), parse_pay_tables(PDF),
            url=VA_TITLE38_URL, sha256="a" * 64, retrieved_at="2026-09-23T00:00:00Z",
        )

    def test_only_the_families_the_schedule_names_are_banded(self):
        _, (records, _report) = self._records()
        self.assertEqual(sorted(records), ["cmo-1", "cos-1", "dir-1", "nd-1"])

    def test_the_titles_the_schedule_does_not_print_get_nothing(self):
        _, (records, _report) = self._records()
        for node_id in ("ad-1", "nope-1"):
            self.assertNotIn(node_id, records, node_id)

    def test_the_service_chief_family_is_refused_whole(self):
        # Specialty-dependent in two tables at different ranges, and the same
        # family includes Finance, which is in neither.
        _, (records, _report) = self._records()
        self.assertNotIn("svc-1", records)
        self.assertNotIn("fin-1", records)

    def test_a_chief_of_staff_outside_the_medical_centres_is_refused(self):
        _, (records, _report) = self._records()
        self.assertNotIn("vha-cos", records)

    def test_the_right_name_under_the_wrong_parent_is_refused(self):
        tree = _base_tree()
        tree["children"][0]["children"][0]["name"] = "Somewhere Else"
        _, (records, report) = self._records(tree)
        self.assertNotIn("cos-1", records)
        self.assertIn("name_matches_but_parent_is_not_the_scoped_one", report["refused"])

    def test_a_scoped_office_whose_parent_is_not_a_visn_is_refused(self):
        tree = _base_tree()
        tree["children"][0]["children"][1]["type"] = "Office"
        _, (records, report) = self._records(tree)
        self.assertNotIn("cmo-1", records)
        self.assertIn("scoped_office_whose_parent_is_not_the_expected_kind", report["refused"])

    def test_a_node_standing_for_several_posts_is_refused(self):
        tree = _base_tree()
        tree["children"][0]["children"][0]["children"][0]["representsPosts"] = 3
        _, (records, report) = self._records(tree)
        self.assertNotIn("cos-1", records)
        self.assertIn("stands_for_several_posts", report["refused"])


class GateTests(unittest.TestCase):
    def _apply(self):
        tree = _base_tree()
        node_map, _ = index_tree(tree)
        records, _ = build_records(
            node_map, _parents(tree), parse_pay_tables(PDF),
            url=VA_TITLE38_URL, sha256="a" * 64, retrieved_at="2026-09-23T00:00:00Z",
        )
        apply_pay_evidence(tree, records)
        return tree, index_tree(tree)[0]

    def test_an_honest_band_passes(self):
        _, node_map = self._apply()
        for node_id, parent in (("cos-1", "VA Medical Centers"), ("dir-1", "VA Medical Centers"),
                                ("cmo-1", "VISN 1 — New England"), ("nd-1", "VISN 1 — New England")):
            with self.subTest(node=node_id):
                node = node_map[node_id]
                self.assertEqual(tier_pay_violations(node, node["positionTierPay"], "2026-09-24", _label, parent), [])

    def test_a_band_moved_to_a_node_the_schedule_does_not_name_is_caught(self):
        _, node_map = self._apply()
        band = node_map["cos-1"]["positionTierPay"]
        forged = dict(node_map["ad-1"])
        forged["positionTierPay"] = band
        violations = tier_pay_violations(forged, band, "2026-09-24", _label, "VA Medical Centers")
        self.assertTrue(any("prints no title of this name at all" in v for v in violations))

    def test_a_band_from_the_wrong_table_is_caught(self):
        _, node_map = self._apply()
        node = node_map["dir-1"]
        forged = {**node["positionTierPay"], "table": TABLE_LABEL}
        violations = tier_pay_violations(forged if False else node, forged, "2026-09-24", _label, "VA Medical Centers")
        self.assertTrue(any("is printed in" in v for v in violations))

    def test_a_band_swapped_between_the_two_families_is_caught(self):
        _, node_map = self._apply()
        chief_of_staff = node_map["cos-1"]
        network_band = node_map["cmo-1"]["positionTierPay"]
        violations = tier_pay_violations(chief_of_staff, network_band, "2026-09-24", _label, "VA Medical Centers")
        self.assertTrue(violations, "a tier-1 network band on a tier-2 chief of staff was not caught")

    def test_a_scoped_band_whose_parent_is_not_its_own_is_caught(self):
        _, node_map = self._apply()
        node = node_map["cmo-1"]
        violations = tier_pay_violations(node, node["positionTierPay"], "2026-09-24", _label, "VISN 9 — Mid South")
        self.assertTrue(any("not the parent the tree gives it" in v for v in violations))

    def test_every_forgery_this_module_makes_possible_is_caught(self):
        _, node_map = self._apply()
        node = node_map["cos-1"]
        base = node["positionTierPay"]
        attacks = {
            "wrong minimum": {**base, "minimum": 1.0},
            "wrong maximum": {**base, "maximum": 9_000_000.0},
            "wrong tier": {**base, "tier": 1},
            "range text disagrees": {**base, "rangeText": "$1 – $2"},
            "unknown source": {**base, "source": "made_up"},
            "unknown kind": {**base, "kind": "something_else"},
            "unknown match rule": {**base, "matchRule": "vibes"},
            "wrong url": {**base, "url": "https://example.com/"},
            "future retrieval date": {**base, "checkedAt": "2099-01-01T00:00:00Z"},
            "quote without the table": {**base, "quote": "nothing like this"},
            "quote without the effective line": {**base, "quote": base["quote"].replace(VA_TITLE38_EFFECTIVE_TEXT, "")},
            "published as a rate": {**base, "amount": 200000.0},
            "carries a rateText": {**base, "rateText": "$200,000"},
            "no sentence saying it is a band": {**base, "note": ""},
            "claims more than a proxy": {**base, "scopeMatch": "exact"},
            "graded verified": {**base, "financialEvidenceStatus": "verified"},
        }
        for name, band in attacks.items():
            with self.subTest(attack=name):
                self.assertTrue(
                    tier_pay_violations(node, band, "2026-09-24", _label, "VA Medical Centers"),
                    f"{name} was not caught",
                )

    def test_the_sourceUrls_leak_this_module_must_never_repeat_is_caught(self):
        _, node_map = self._apply()
        node = node_map["cos-1"]
        node["sourceUrls"] = [VA_TITLE38_URL]
        violations = tier_pay_violations(node, node["positionTierPay"], "2026-09-24", _label, "VA Medical Centers")
        self.assertTrue(any("among the sources that it exists" in v for v in violations))


class PublishedGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = PROJECT_ROOT / "output" / "graph.json"
        if not path.exists():
            raise unittest.SkipTest("no published graph to check")
        cls.nodes = []

        def walk(node):
            cls.nodes.append(node)
            for child in node.get("children") or []:
                walk(child)

        walk(json.loads(path.read_text(encoding="utf-8")))

    def test_the_bands_reach_the_published_graph(self):
        banded = [n for n in self.nodes if isinstance(n.get("positionTierPay"), dict)]
        self.assertEqual(len(banded), 72)
        self.assertEqual({n["positionTierPay"]["source"] for n in banded}, {"va_title38_pay_ranges"})

    def test_no_banded_node_gained_a_va_pay_url_among_its_sources(self):
        for node in self.nodes:
            if isinstance(node.get("positionTierPay"), dict):
                urls = node.get("sourceUrls") or []
                self.assertFalse([u for u in urls if "va.gov/OHRM" in str(u)], node.get("id"))

    def test_no_banded_node_publishes_a_rate_or_a_cost(self):
        for node in self.nodes:
            band = node.get("positionTierPay")
            if isinstance(band, dict):
                self.assertNotIn("amount", band, node.get("id"))
                self.assertNotIn("rateText", band, node.get("id"))
                self.assertNotIn(node.get("cost_status"), ("official", "root_total", "scaled_official"))

    def test_the_titles_the_schedule_does_not_print_carry_no_band(self):
        for node in self.nodes:
            if str(node.get("name") or "") in VA_TITLE38_NEVER_PRICED:
                self.assertNotIn("positionTierPay", node, node.get("id"))


if __name__ == "__main__":
    unittest.main()
