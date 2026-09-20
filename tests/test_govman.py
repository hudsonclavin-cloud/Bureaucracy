"""The Government Manual: a post's title, read off its own agency's entry.

The Manual is the best-scoped post evidence this project has -- one official
document that names an agency and then names that agency's officers -- and it
is also the easiest to over-read, for three reasons these tests pin:

  - each leadership row pairs a POST with a LIVING PERSON, and the person is
    never read;
  - the tables are typeset rather than tabular, so a group heading is
    completed by bare qualifier rows ("Water" under "Assistant
    Administrators"), and assembling those would produce a title rather than
    select one;
  - the titles it does print are the stamped administrative ones this graph
    carries 84 and 72 times over, so a record that drifts to another node
    keeps a real title, a real agency and a real URL.

Both directions throughout: the real fixture yields the records it should,
and every corruption is refused.
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
import sys
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
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
from data_pipeline.verification.govman import (  # noqa: E402
    DEFAULT_MODS,
    DEFAULT_PACKAGE,
    METHOD,
    SOURCE_TYPE,
    access_id,
    apply_govman_evidence,
    build_records,
    entity_titles,
    iter_entities,
    load_govman_evidence,
    manifest_access_ids,
    normalise,
    read_manual,
)

PUBLISHED = PROJECT_ROOT / "output" / "graph.json"


def published_nodes():
    if not PUBLISHED.exists():
        return []
    graph = json.loads(PUBLISHED.read_text(encoding="utf-8"))
    out, stack = [], [(graph, None)]
    while stack:
        node, parent = stack.pop()
        out.append((node, parent))
        for child in node.get("children") or []:
            if isinstance(child, dict):
                stack.append((child, node))
    return out


class FixtureIntegrityTests(unittest.TestCase):
    """The bytes on disk are the publisher's, and the code says so before reading."""

    def test_each_fixture_matches_its_fetch_record(self):
        for path in (DEFAULT_PACKAGE, DEFAULT_MODS):
            meta = json.loads(path.with_suffix(path.suffix + ".meta.json").read_text(encoding="utf-8"))
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(), meta["sha256"],
                f"{path.name} does not match the digest its fetch recorded")
            self.assertTrue(str(meta["url"]).startswith("https://www.govinfo.gov/"))
            self.assertEqual(meta["status"], 200)

    def test_a_tampered_package_is_refused(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            copy_path = Path(tmp) / DEFAULT_PACKAGE.name
            copy_path.write_bytes(DEFAULT_PACKAGE.read_bytes().replace(
                b"<AgencyName>Department of Energy</AgencyName>",
                b"<AgencyName>Department of Widgets</AgencyName>", 1))
            meta = json.loads((DEFAULT_PACKAGE.with_suffix(DEFAULT_PACKAGE.suffix + ".meta.json")).read_text())
            (Path(tmp) / (DEFAULT_PACKAGE.name + ".meta.json")).write_text(json.dumps(meta))
            with self.assertRaises(ValueError):
                read_manual(copy_path)


class AccessIdTests(unittest.TestCase):
    """The citation's granule id is the publisher's, not a construction we hope is right."""

    def test_the_construction_reproduces_every_id_in_the_manifest(self):
        manifest = manifest_access_ids(ET.parse(DEFAULT_MODS).getroot())
        self.assertGreater(len(manifest), 200)
        manual = read_manual()
        checked = 0
        for entry in manual["entities"]:
            granule = access_id(manual["package"], entry["entityId"])
            self.assertIsNotNone(granule, entry["name"])
            self.assertIn(granule, manifest,
                          f"{entry['name']}: constructed {granule}, which the manifest does not carry")
            self.assertEqual(normalise(manifest[granule]), entry["name"],
                             f"{granule} names a different agency in the manifest")
            checked += 1
        self.assertEqual(checked, len(manual["entities"]))

    def test_the_id_is_zero_padded_to_three_digits(self):
        # ".../GOVMAN-2025-12-31-72" serves a page titled with the raw id;
        # "...-072" serves the House of Representatives. Measured, not assumed.
        self.assertEqual(access_id("GOVMAN-2025-12-31", "72"), "GOVMAN-2025-12-31-072")
        self.assertEqual(access_id("GOVMAN-2025-12-31", "202"), "GOVMAN-2025-12-31-202")
        self.assertIsNone(access_id("GOVMAN-2025-12-31", "front-matter"))


class IncumbentNamesAreNeverReadTests(unittest.TestCase):
    """Each row names a living person beside the post. The person is not read."""

    def test_no_published_title_is_a_name_the_manual_prints(self):
        people = set()
        for entity in iter_entities(ET.parse(DEFAULT_PACKAGE).getroot()):
            for row in entity.findall(".//LeaderShipTableValues/Values"):
                name = normalise(row.findtext("NameColumnValue"))
                if name:
                    people.add(canonical_name_key(name))
        self.assertGreater(len(people), 500, "the fixture should carry hundreds of office holders")
        records = load_govman_evidence()
        self.assertTrue(records, "expected derived records to test against")
        for node_id, record in records.items():
            self.assertNotIn(canonical_name_key(record["listedTitle"]), people,
                             f"{node_id} publishes something the Manual prints as a person's name")

    def test_the_module_reads_the_title_column_only(self):
        source = (PROJECT_ROOT / "data_pipeline" / "verification" / "govman.py").read_text(encoding="utf-8")
        code = [line for line in source.splitlines()
                if "NameColumnValue" in line and not line.strip().startswith("#")]
        # It may be named in the docstring and in the test above; it must never
        # be fetched out of a row by the module itself.
        self.assertFalse([line for line in code if "findtext" in line or "find(" in line],
                         "govman.py must never read NameColumnValue")


class EligibilityTests(unittest.TestCase):
    """Only rows that are complete titles on their own face."""

    def entity(self, xml):
        return ET.fromstring(xml)

    def test_a_table_with_a_header_governs_its_rows(self):
        titles = entity_titles(self.entity("""
        <Entity><LeaderShipTables><LeaderShipTable>
          <Header>Assistant Administrators</Header>
          <LeaderShipTableValues>
            <Values><NameColumnValue>A Person</NameColumnValue><TitleColumnValue>Water</TitleColumnValue></Values>
            <Values><NameColumnValue>B Person</NameColumnValue><TitleColumnValue>Air and Radiation</TitleColumnValue></Values>
          </LeaderShipTableValues>
        </LeaderShipTable></LeaderShipTables></Entity>"""))
        self.assertEqual(titles, [], "a qualifier under a group heading is not a title")

    def test_an_empty_or_footnote_header_governs_nothing(self):
        for header in ("", "*"):
            titles = entity_titles(self.entity(f"""
            <Entity><LeaderShipTables><LeaderShipTable>
              <Header>{header}</Header>
              <LeaderShipTableValues>
                <Values><TitleColumnValue>General Counsel</TitleColumnValue></Values>
              </LeaderShipTableValues>
            </LeaderShipTable></LeaderShipTables></Entity>"""))
            self.assertEqual([t["title"] for t in titles], ["General Counsel"])

    def test_an_all_caps_row_governs_what_follows_until_a_separator(self):
        titles = entity_titles(self.entity("""
        <Entity><LeaderShipTables><LeaderShipTable><Header></Header>
          <LeaderShipTableValues>
            <Values><TitleColumnValue>ADMINISTRATOR</TitleColumnValue></Values>
            <Values><TitleColumnValue>Deputy Administrator</TitleColumnValue></Values>
            <Values><TitleColumnValue>-----------------------------</TitleColumnValue></Values>
            <Values><TitleColumnValue>Chief of Staff</TitleColumnValue></Values>
          </LeaderShipTableValues>
        </LeaderShipTable></LeaderShipTables></Entity>"""))
        self.assertEqual([t["title"] for t in titles], ["Chief of Staff"],
                         "a row after ALL CAPS is governed; a separator resets")

    def test_the_real_fixture_refuses_every_qualifier_epa_prints(self):
        """EPA's entry is the worked example in the module docstring."""
        manual = read_manual()
        epa = next(e for e in manual["entities"] if e["name"] == "Environmental Protection Agency")
        printed = {t["title"] for t in epa["titles"]}
        # Kept: rows in tables that carry no header at all, or only the
        # footnote mark, and that nothing ALL-CAPS governs.
        self.assertEqual(printed, {"General Counsel", "Inspector General",
                                   "Chief Financial Officer", "Agency Science Advisor"})
        # Refused under the header "Assistant Administrators": assembling
        # "Assistant Administrator for Water" would produce a title rather
        # than select one.
        self.assertNotIn("Water", printed)
        self.assertNotIn("Air and Radiation", printed)
        # Refused under "Regional Administrators".
        self.assertFalse([t for t in printed if t.startswith("Region ")])
        # Governed by the ALL-CAPS "ADMINISTRATOR" above it, and so is
        # "Chief of Staff" by its table's "Office of the Administrator"
        # header. Both are real titles and both are lost: that is what the
        # blunt rule costs, recorded here rather than argued away.
        self.assertNotIn("Deputy Administrator", printed)
        self.assertNotIn("Chief of Staff", printed)


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.manual = read_manual()
        self.graph = load_base_graph(DEFAULT_BASE_GRAPH)

    def test_the_real_join_is_unambiguous_on_both_sides(self):
        records, stats = build_records(self.manual, self.graph)
        self.assertGreater(len(records), 40)
        self.assertEqual(stats["entry_names_several_entries"], 0)
        self.assertEqual(stats["entry_names_several_nodes"], 0)
        self.assertEqual(stats["refused_title_listed_twice"], 0)
        self.assertEqual(stats["refused_siblings_share_the_name"], 0)
        for node_id, record in records.items():
            self.assertEqual(canonical_name_key(record["nodeName"]),
                             canonical_name_key(record["listedTitle"]))
            self.assertTrue(record["url"].startswith("https://www.govinfo.gov/app/details/"))
            self.assertGreaterEqual(len(canonical_name_key(record["listedTitle"]).split()), 2)

    def test_every_record_sits_under_the_organisation_it_was_read_from(self):
        records, _ = build_records(self.manual, self.graph)
        node_map, parent_map = index_tree(self.graph)
        for node_id, record in records.items():
            self.assertEqual(parent_map.get(node_id), record["organisationId"])
            parent = node_map[record["organisationId"]]
            self.assertEqual(canonical_name_key(parent["name"]),
                             canonical_name_key(record["listedUnder"]))

    def test_a_one_token_title_is_refused(self):
        _, stats = build_records(self.manual, self.graph)
        self.assertGreater(stats["refused_name_too_short"], 0,
                           "the two-token floor should be doing work on the real graph")

    def test_a_post_is_never_matched_past_its_own_parent(self):
        # Measured: nearest-ancestor scoping lifts 64 to 86, and the 22 extra
        # are Defense agencies' General Counsels confirmed from the
        # Department of Defense's single row.
        records, _ = build_records(self.manual, self.graph)
        node_map, parent_map = index_tree(self.graph)
        manual_org_ids = {r["organisationId"] for r in records.values()}
        for node_id, record in records.items():
            parent_id = parent_map.get(node_id)
            self.assertIn(parent_id, manual_org_ids)
            self.assertEqual(parent_id, record["organisationId"])


class ApplyTests(unittest.TestCase):
    def tree(self):
        return {
            "id": "root", "name": "Root", "type": "Branch",
            "children": [{
                "id": "agency", "name": "Government Accountability Office", "type": "Agency",
                "children": [{"id": "ig", "name": "Inspector General", "type": "Position", "children": []}],
            }],
        }

    def record(self):
        return {"ig": {
            "source": "us_government_manual", "nodeName": "Inspector General",
            "listedTitle": "Inspector General", "listedUnder": "Government Accountability Office",
            "organisationId": "agency", "package": "GOVMAN-2025-12-31", "edition": "2025-12-31",
            "granule": "GOVMAN-2025-12-31-075",
            "url": "https://www.govinfo.gov/app/details/GOVMAN-2025-12-31/GOVMAN-2025-12-31-075",
            "tableFooter": "The key personnel table was updated 2-2019.",
            "documentSha256": "x",
        }}

    def test_a_listing_is_published_with_its_url_and_date(self):
        tree = self.tree()
        stats = apply_govman_evidence(tree, self.record())
        node = tree["children"][0]["children"][0]
        self.assertEqual(stats["listed"], 1)
        self.assertEqual(node["verificationMethod"], METHOD)
        self.assertIn(SOURCE_TYPE, node["sourceTypes"])
        self.assertIn(self.record()["ig"]["url"], node["sourceUrls"])
        self.assertIn(self.record()["ig"]["url"], node["evidenceUrls"])
        self.assertEqual(node["lastVerified"], "2025-12-31")
        self.assertEqual(node["govmanListing"]["tableFooter"],
                         "The key personnel table was updated 2-2019.")

    def test_no_placement_is_ever_claimed(self):
        tree = self.tree()
        apply_govman_evidence(tree, self.record())
        node = tree["children"][0]["children"][0]
        for field in ("placementVerified", "placementMethod", "placementUrl", "placementParentId"):
            self.assertNotIn(field, node,
                             "one entry was read; it yields one observation, never two")

    def test_a_renamed_node_keeps_nothing(self):
        tree = self.tree()
        tree["children"][0]["children"][0]["name"] = "Deputy Inspector General"
        stats = apply_govman_evidence(tree, self.record())
        self.assertEqual(stats["stale_name"], 1)
        self.assertNotIn("govmanListing", tree["children"][0]["children"][0])

    def test_a_reparented_node_keeps_nothing(self):
        tree = self.tree()
        post = tree["children"][0]["children"].pop()
        tree["children"].append({"id": "other", "name": "Somewhere Else", "type": "Agency",
                                 "children": [post]})
        stats = apply_govman_evidence(tree, self.record())
        self.assertEqual(stats["reparented"], 1)
        self.assertNotIn("govmanListing", post)

    def test_a_node_retyped_away_from_a_post_keeps_nothing(self):
        tree = self.tree()
        tree["children"][0]["children"][0]["type"] = "Office"
        stats = apply_govman_evidence(tree, self.record())
        self.assertEqual(stats["not_a_post"], 1)
        self.assertNotIn("govmanListing", tree["children"][0]["children"][0])

    def test_a_page_confirmation_is_kept_and_the_manual_sits_beside_it(self):
        tree = self.tree()
        node = tree["children"][0]["children"][0]
        node["verificationMethod"] = "name_labelled_on_its_organisations_official_page"
        node["sourceUrls"] = ["https://www.gao.gov/about"]
        stats = apply_govman_evidence(tree, self.record())
        self.assertEqual(stats["method_kept_from_page"], 1)
        self.assertEqual(node["verificationMethod"], "name_labelled_on_its_organisations_official_page")
        self.assertIn("https://www.gao.gov/about", node["sourceUrls"])
        self.assertIn(self.record()["ig"]["url"], node["sourceUrls"])

    def test_the_field_is_withdrawn_by_the_evidence_sweep(self):
        self.assertIn("govmanListing", EVIDENCE_OWNED_FIELDS)


class GateMirrorTests(unittest.TestCase):
    """The gate parses the Manual itself; the two extractions must agree."""

    def test_the_gates_independent_parser_agrees_with_the_module(self):
        from scripts.validate_published_graph import govman_entries

        gate_index = govman_entries()
        manual = read_manual()
        self.assertEqual(len(gate_index), len(manual["entities"]))
        for entry in manual["entities"]:
            granule = access_id(manual["package"], entry["entityId"])
            self.assertIn(granule, gate_index)
            agency, titles = gate_index[granule]
            self.assertEqual(agency, entry["name"])
            mine = sorted(canonical_name_key(t["title"]) for t in entry["titles"])
            theirs = sorted(k for k, rows in titles.items() for _ in rows)
            self.assertEqual(mine, theirs, f"{entry['name']}: the two parsers disagree")

    def test_the_gate_does_not_import_the_module_it_checks(self):
        source = (PROJECT_ROOT / "scripts" / "validate_published_graph.py").read_text(encoding="utf-8")
        start = source.index("def govman_entries")
        body = source[start:source.index("\ndef ", start + 10)]
        # The docstring names the module it mirrors, which is the point; what
        # it must not do is import it. A mirror copied from the code it checks
        # checks nothing.
        code = [line for line in body.splitlines()
                if "import" in line and "data_pipeline" in line]
        self.assertEqual(code, [])


class PublishedGraphTests(unittest.TestCase):
    def setUp(self):
        self.pairs = published_nodes()
        if not self.pairs:
            self.skipTest("output/graph.json is not built")

    def test_only_posts_carry_a_listing_and_each_sits_under_the_agency_quoted(self):
        by_id = {n["id"]: n for n, _ in self.pairs if n.get("id")}
        parent_of = {n["id"]: (p or {}).get("id") for n, p in self.pairs if n.get("id")}
        carrying = [n for n, _ in self.pairs if isinstance(n.get("govmanListing"), dict)]
        self.assertGreater(len(carrying), 40)
        for node in carrying:
            self.assertIn("position", str(node.get("type") or "").casefold())
            block = node["govmanListing"]
            parent = by_id.get(parent_of.get(node["id"]) or "")
            self.assertIsNotNone(parent)
            self.assertEqual(canonical_name_key(parent["name"]),
                             canonical_name_key(block["listedUnder"]))
            self.assertIn(block["url"], node.get("sourceUrls") or [])

    def test_no_node_claims_placement_from_the_manual(self):
        for node, _ in self.pairs:
            self.assertNotIn("government_manual", str(node.get("placementMethod") or ""))

    def test_a_manual_listing_alone_grades_partial_not_verified(self):
        for node, _ in self.pairs:
            if not isinstance(node.get("govmanListing"), dict):
                continue
            if len(node.get("sourceUrls") or []) == 1:
                self.assertNotEqual(node.get("verificationStatus"), "verified",
                                    f"{node.get('id')}: one official URL is 0.4 + 0.3, which is partial")


class GateCorruptionTests(unittest.TestCase):
    """Every dimension of the claim, corrupted in turn."""

    @classmethod
    def setUpClass(cls):
        if not PUBLISHED.exists():
            raise unittest.SkipTest("output/graph.json is not built")
        cls.graph = json.loads(PUBLISHED.read_text(encoding="utf-8"))

    def run_gate(self, graph):
        import tempfile
        from scripts.validate_published_graph import main as gate_main

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "graph.json"
            path.write_text(json.dumps(graph), encoding="utf-8")
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = gate_main(["gate", str(path)])
            return code, buffer.getvalue()

    def corrupt(self, mutate):
        graph = copy.deepcopy(self.graph)
        stack = [graph]
        while stack:
            node = stack.pop()
            if isinstance(node.get("govmanListing"), dict):
                mutate(node)
                return graph
            stack.extend([c for c in (node.get("children") or []) if isinstance(c, dict)])
        self.fail("no node carries a Government Manual listing")

    def assert_refused(self, mutate, because):
        code, output = self.run_gate(self.corrupt(mutate))
        self.assertEqual(code, 1, f"the gate accepted a graph where {because}")
        self.assertIn("FAIL  a Government Manual listing is a title that entry really prints", output)

    def test_the_untouched_graph_passes(self):
        code, output = self.run_gate(copy.deepcopy(self.graph))
        self.assertIn("ok    a Government Manual listing is a title that entry really prints", output)
        self.assertEqual(code, 0, output[-2000:])

    def test_a_title_the_entry_does_not_print(self):
        self.assert_refused(lambda n: n["govmanListing"].update(listedTitle="Supreme Widget Officer"),
                            "the quoted title is not in the Manual")

    def test_the_agency_swapped_for_another_real_one(self):
        self.assert_refused(lambda n: n["govmanListing"].update(listedUnder="Department of Energy"),
                            "the listing names an agency that is not the node's parent")

    def test_the_granule_swapped_for_another_real_one(self):
        self.assert_refused(lambda n: n["govmanListing"].update(granule="GOVMAN-2025-12-31-214"),
                            "the granule cited is a different agency's entry")

    def test_a_url_that_is_not_that_granules_entry(self):
        self.assert_refused(lambda n: n["govmanListing"].update(url="https://www.govinfo.gov/app/details/X/Y"),
                            "the URL does not address the granule quoted")

    def test_an_edition_in_the_future(self):
        self.assert_refused(lambda n: n["govmanListing"].update(edition="2099-01-01"),
                            "the edition has not happened")

    def test_a_node_that_is_not_a_post(self):
        self.assert_refused(lambda n: n.update(type="Office"),
                            "a listing sits on something that is not a post")

    def test_a_placement_claimed_from_the_manual(self):
        self.assert_refused(lambda n: n.update(placementMethod="listed_in_government_manual"),
                            "one entry was published as two findings")

    def test_the_source_url_removed_from_the_node(self):
        self.assert_refused(lambda n: n.update(sourceUrls=[]),
                            "the node cites the Manual without carrying its URL")


if __name__ == "__main__":
    unittest.main()
