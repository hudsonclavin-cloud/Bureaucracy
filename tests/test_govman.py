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
from data_pipeline.verification.govman import (
    is_post_node,  # noqa: E402
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


def alias_names_for(node):
    """The reviewed alternatives a node answers to, from the committed table
    and only while it still carries the name the row was written against."""
    from data_pipeline.verification.aliases import load_rows

    return [
        str(row.get("alias") or "")
        for row in load_rows()
        if str(row.get("id") or "") == str((node or {}).get("id") or "")
        and str(row.get("name") or "") == str((node or {}).get("name") or "")
    ]


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
        self.assertEqual([t["title"] for t in titles], ["ADMINISTRATOR", "Chief of Staff"],
                         "the ALL-CAPS row is a title itself; the row after it is governed; a separator resets")
        self.assertTrue(titles[0].get("allCaps"))
        self.assertNotIn("allCaps", titles[1])

    def test_a_caps_row_is_the_principals_title_and_a_plural_heading_claims_nothing(self):
        """Nine department heads sit in the Manual as ALL-CAPS rows
        ("SECRETARY OF STATE", "ATTORNEY GENERAL") and were refused as group
        headings until 2026-09-21. The join is equality with exactly one
        curated post, so a plural heading ("DEPUTY ADMINISTRATORS") is
        admitted as a row and reaches nothing."""
        manual = read_manual()
        graph = load_base_graph(DEFAULT_BASE_GRAPH)
        records, _ = build_records(manual, graph)
        by_title = {r["listedTitle"] for r in records.values()}
        for printed in ("SECRETARY OF STATE", "ATTORNEY GENERAL", "SECRETARY OF THE TREASURY", "LIBRARIAN OF CONGRESS"):
            self.assertIn(printed, by_title, printed)
        # Plural caps headings the Manual prints in tables with no header
        # (so they are admitted as rows), none of which names a post.
        plural_headings = {"DIRECTORS", "CHIEF OFFICERS", "ASSOCIATE DIRECTORS", "ASSISTANT SECRETARIES",
                           "DEPUTY ASSISTANT SECRETARIES", "REGIONAL DIRECTORS"}
        admitted = {t["title"] for e in manual["entities"] for t in e["titles"] if t.get("allCaps")}
        self.assertTrue(plural_headings & admitted, "the fixture no longer prints a plural caps heading as a row")
        self.assertFalse(plural_headings & by_title, "no plural caps heading may reach a post")

    def test_the_real_fixture_refuses_every_qualifier_epa_prints(self):
        """EPA's entry is the worked example in the module docstring."""
        manual = read_manual()
        epa = next(e for e in manual["entities"] if e["name"] == "Environmental Protection Agency")
        printed = {t["title"] for t in epa["titles"] if not t.get("allCaps")}
        # Kept: rows in tables that carry no header at all, or only the
        # footnote mark, and that nothing ALL-CAPS governs. The ALL-CAPS
        # rows themselves ("ADMINISTRATOR") are titles too since 2026-09-21
        # and are set aside here to keep the qualifier assertions exact.
        self.assertEqual(printed, {"General Counsel", "Inspector General",
                                   "Chief Financial Officer", "Agency Science Advisor"})
        # EPA's own "ADMINISTRATOR" sits in a table headed "Office of the
        # Administrator", so the header rule still refuses it, caps or not.
        self.assertNotIn("ADMINISTRATOR", {t["title"] for t in epa["titles"]})
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
            # The parent's own name, or an alternative the reviewed table
            # records for it: the Manual prints "Administrative Office of the
            # United States Courts" where the graph writes "U.S. Courts", and
            # `data/curation/node_aliases.json` is where that identification
            # is written down. The node carrying the listing then says so
            # (verificationAliasMatch, scope "organisation").
            answers_to = {canonical_name_key(parent["name"])}
            answers_to.update(canonical_name_key(a) for a in alias_names_for(parent))
            self.assertIn(canonical_name_key(block["listedUnder"]), answers_to)
            self.assertIn(block["url"], node.get("sourceUrls") or [])

    def test_no_post_claims_placement_from_the_manual(self):
        """The post route reads one entry and yields one observation, so it
        never publishes existence and placement as two findings. The
        ORGANISATION route (since 2026-09-20) does claim placement, the way
        the Federal Register directory does: an entry's name is existence
        and its printed parent is a separate claim about the edge, recorded
        as a disagreement where the tree differs. So the rule is scoped to
        posts, and the organisation method may sit only on non-posts."""
        for node, _ in self.pairs:
            if is_post_node(node):
                self.assertNotIn("government_manual", str(node.get("placementMethod") or ""))
        published = json.loads((Path(__file__).resolve().parent.parent / "output" / "graph.json").read_text(encoding="utf-8"))
        root = published.get("tree") or published.get("root") or published
        stack = [root]
        while stack:
            n = stack.pop()
            if str(n.get("placementMethod") or "") == "listed_under_parent_in_us_government_manual":
                self.assertFalse(is_post_node(n), n.get("id"))
                self.assertIsInstance(n.get("govmanEntry"), dict, n.get("id"))
            stack.extend(n.get("children") or [])

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



class OrganisationRouteTests(unittest.TestCase):
    """The Manual's entry for a unit ITSELF, since 2026-09-20 -- the one route
    to evidence for organisations on the 67 hosts that refuse the page as they
    refuse robots.txt (docs/NETWORK_ACCESS.md 11)."""

    def setUp(self):
        from data_pipeline.verification.govman import build_org_records
        self.build_org_records = build_org_records
        self.manual = read_manual()
        self.graph = load_base_graph(DEFAULT_BASE_GRAPH)

    def test_the_real_join_names_the_unit_as_the_manual_prints_it(self):
        records, stats = self.build_org_records(self.manual, self.graph)
        self.assertGreater(len(records), 120)
        self.assertEqual(stats["entry_names_several_entries"], 0)
        self.assertEqual(stats["entry_names_several_nodes"], 0)
        node_map, _ = index_tree(self.graph)
        for node_id, record in records.items():
            self.assertEqual(canonical_name_key(node_map[node_id]["name"]), canonical_name_key(record["listedName"]))
            self.assertFalse(is_post_node(node_map[node_id]), node_id)
            self.assertTrue(record["url"].startswith("https://www.govinfo.gov/app/details/GOVMAN-"))
            self.assertRegex(record["granule"], r"^GOVMAN-\d{4}-\d{2}-\d{2}-\d{3}$")

    def test_the_parent_on_a_record_is_the_manuals_own_and_never_invented(self):
        records, _ = self.build_org_records(self.manual, self.graph)
        by_id = {e["entityId"]: e for e in self.manual["entities"]}
        for record in records.values():
            entry = by_id[record["entityId"]]
            parent = by_id.get(entry.get("parentId") or "")
            self.assertEqual(record["parentListedName"], parent["name"] if parent else None)

    def test_the_two_routes_agree_on_which_entry_is_which_agency(self):
        posts, _ = build_records(self.manual, self.graph)
        orgs, _ = self.build_org_records(self.manual, self.graph)
        for post in posts.values():
            org = orgs.get(post["organisationId"])
            self.assertIsNotNone(org, post["organisationId"])
            self.assertEqual(org["listedName"], post["listedUnder"])

    def _tree(self):
        return {"id": "root", "name": "Root", "type": "Foundation", "children": [
            {"id": "dod", "name": "Department of Defense (DoD)", "type": "Cabinet Department", "children": [
                {"id": "def-agencies", "name": "Defense Agencies & Field Activities", "type": "Division", "children": [
                    {"id": "dca", "name": "Defense Commissary Agency", "type": "Defense Agency", "children": []},
                ]},
                {"id": "sec-def", "name": "Secretary of Defense", "type": "Position", "children": []},
            ]},
            {"id": "elsewhere", "name": "Somewhere Else", "type": "Agency", "children": [
                {"id": "dcaa", "name": "Defense Contract Audit Agency (DCAA)", "type": "Defense Agency", "children": []},
            ]},
        ]}

    def _record(self, listed, parent, granule="GOVMAN-2025-12-31-216"):
        return {"source": "us_government_manual", "nodeName": listed, "listedName": listed, "entityId": granule[-3:].lstrip("0"),
                "parentListedName": parent, "parentEntityId": "206", "package": "GOVMAN-2025-12-31", "edition": "2025-12-31",
                "granule": granule, "url": f"https://www.govinfo.gov/app/details/GOVMAN-2025-12-31/{granule}", "documentSha256": "x"}

    def test_apply_sets_the_method_only_where_none_and_places_only_under_the_printed_parent(self):
        from data_pipeline.verification.govman import apply_govman_org_evidence, ORG_METHOD, ORG_PLACEMENT_METHOD
        tree = self._tree()
        stats = apply_govman_org_evidence(tree, {
            "dca": self._record("Defense Commissary Agency", "Defense Agencies"),          # scaffolding parent: no placement claim
            "dcaa": self._record("Defense Contract Audit Agency", "Department of Defense", "GOVMAN-2025-12-31-217"),  # names another node: disagreement
            "sec-def": self._record("Secretary of Defense", "Department of Defense", "GOVMAN-2025-12-31-114"),       # a post: refused
        })
        node_map, _ = index_tree(tree)
        dca = node_map["dca"]
        self.assertEqual(dca["verificationMethod"], ORG_METHOD)
        self.assertEqual(dca["govmanEntry"]["parentListedName"], "Defense Agencies")
        self.assertIn("https://www.govinfo.gov/app/details/GOVMAN-2025-12-31/GOVMAN-2025-12-31-216", dca["sourceUrls"])
        self.assertEqual(dca["lastVerified"], "2025-12-31")
        self.assertNotIn("placementVerified", dca)
        self.assertEqual(stats["placements_unresolved"], 1)
        dcaa = node_map["dcaa"]
        self.assertEqual(dcaa["placementDirectoryDisagreement"]["directoryParentId"], "dod")
        self.assertEqual(dcaa["placementDirectoryDisagreement"]["source"], "us_government_manual")
        self.assertNotIn("placementVerified", dcaa)
        self.assertEqual(stats["placements_disagree"], 1)
        self.assertEqual(stats["is_a_post"], 1)
        self.assertNotIn("govmanEntry", node_map["sec-def"])
        # A page claim already there is kept; the Manual sits beside it.
        tree2 = self._tree(); index_tree(tree2)[0]["dca"].update({"verificationMethod": "name_labelled_on_own_official_page", "sourceUrls": ["https://www.commissaries.com/x"], "sourceCount": 1})
        s2 = apply_govman_org_evidence(tree2, {"dca": self._record("Defense Commissary Agency", "Defense Agencies")})
        self.assertEqual(index_tree(tree2)[0]["dca"]["verificationMethod"], "name_labelled_on_own_official_page")
        self.assertEqual(s2["method_kept"], 1)
        # Placement is claimed exactly when the Manual's parent IS the tree parent.
        tree3 = self._tree()
        apply_govman_org_evidence(tree3, {"dca": self._record("Defense Commissary Agency", "Defense Agencies & Field Activities")})
        dca3 = index_tree(tree3)[0]["dca"]
        self.assertTrue(dca3["placementVerified"]); self.assertEqual(dca3["placementMethod"], ORG_PLACEMENT_METHOD)
        self.assertEqual(dca3["placementParentId"], "def-agencies")
        self.assertEqual(dca3["placementMatchedText"], "Defense Commissary Agency", "the matched text names the child, as every placement route stamps it")

    def test_a_renamed_node_and_a_missing_record_both_withdraw(self):
        from data_pipeline.verification.govman import apply_govman_org_evidence
        from data_pipeline.verification.evidence import apply_evidence_to_tree
        tree = self._tree()
        apply_govman_org_evidence(tree, {"dca": self._record("Defense Commissary Agency", "Defense Agencies")})
        self.assertIn("govmanEntry", index_tree(tree)[0]["dca"])
        apply_evidence_to_tree(tree, {})  # the owned-field sweep of the next build
        self.assertNotIn("govmanEntry", index_tree(tree)[0]["dca"])
        self.assertNotIn("verificationMethod", index_tree(tree)[0]["dca"])
        tree = self._tree(); index_tree(tree)[0]["dca"]["name"] = "Defense Commissary Service"
        s = apply_govman_org_evidence(tree, {"dca": self._record("Defense Commissary Agency", "Defense Agencies")})
        self.assertEqual(s["stale_name"], 1); self.assertNotIn("govmanEntry", index_tree(tree)[0]["dca"])


class OrganisationRouteGateTests(unittest.TestCase):
    """The gate re-derives the entry, its name and its printed parent from an
    independent parse, and refuses each way the block could lie."""

    def setUp(self):
        import io, json, tempfile, uuid
        from contextlib import redirect_stdout
        from scripts.validate_published_graph import main as gate_main, govman_parents
        self.io, self.json, self.uuid, self.redirect = io, json, uuid, redirect_stdout
        self.gate_main = gate_main
        self.tmp = Path(tempfile.mkdtemp())
        self.published = Path(__file__).resolve().parent.parent / "output" / "graph.json"
        if not self.published.exists():
            self.skipTest("no published graph on disk")
        self.graph = json.loads(self.published.read_text(encoding="utf-8"))
        self.root = self.graph.get("tree") or self.graph.get("root") or self.graph
        self.node = None
        def walk(n):
            if isinstance(n.get("govmanEntry"), dict) and self.node is None and n.get("placementMethod") == "listed_under_parent_in_us_government_manual":
                self.node = n
            for c in n.get("children") or []: walk(c)
        walk(self.root)
        if self.node is None:
            self.skipTest("the published graph carries no Manual-placed organisation yet")
        self.parents = govman_parents()

    def _gate(self, graph):
        path = self.tmp / f"{self.uuid.uuid4().hex}.json"
        path.write_text(self.json.dumps(graph), encoding="utf-8")
        out = self.io.StringIO()
        with self.redirect(out):
            code = self.gate_main(["gate", str(path)])
        return code, out.getvalue()

    def test_the_gates_parent_mirror_equals_the_modules(self):
        from data_pipeline.verification.govman import build_org_records
        records, _ = build_org_records(read_manual(), load_base_graph(DEFAULT_BASE_GRAPH))
        for r in records.values():
            self.assertEqual(canonical_name_key(str(self.parents.get(r["granule"]) or "")), canonical_name_key(str(r["parentListedName"] or "")), r["granule"])

    def test_the_published_graph_passes_and_each_corruption_fails(self):
        code, out = self._gate(self.graph)
        self.assertEqual(code, 0, out)
        self.assertIn("Manual (organisations):", out)
        nid = self.node["id"]
        def find(g):
            r = g.get("tree") or g.get("root") or g
            stack=[r]
            while stack:
                n=stack.pop()
                if n.get("id")==nid: return n
                stack.extend(n.get("children") or [])
        cases = {
            "invented granule": lambda n: n["govmanEntry"].__setitem__("granule", "GOVMAN-2025-12-31-999"),
            "another agency's name": lambda n: n["govmanEntry"].__setitem__("listedName", "Department of Energy"),
            "node renamed": lambda n: n.__setitem__("name", "Renamed Unit"),
            "wrong url": lambda n: n["govmanEntry"].__setitem__("url", "https://www.govinfo.gov/content/pkg/x.htm"),
            "future edition": lambda n: n["govmanEntry"].__setitem__("edition", "2999-01-01"),
            "invented parent": lambda n: n["govmanEntry"].__setitem__("parentListedName", "The Moon"),
            "placed under a parent the tree does not give": lambda n: n.__setitem__("placementMethod", "listed_under_parent_in_us_government_manual") or n["govmanEntry"].__setitem__("parentListedName", self.parents.get(n["govmanEntry"]["granule"])) or n.__setitem__("id", n["id"]),
            "on a post": lambda n: n.__setitem__("type", "Position"),
            "method without a block": lambda n: n.pop("govmanEntry"),
        }
        for name, mutate in cases.items():
            with self.subTest(case=name):
                g = self.json.loads(self.json.dumps(self.graph)); n = find(g); mutate(n)
                if name == "placed under a parent the tree does not give":
                    # move the node's claimed parent name to something the tree does not have above it
                    n["govmanEntry"]["parentListedName"] = "The Moon"; n["placementMatchedText"] = "The Moon"
                code, out = self._gate(g)
                self.assertEqual(code, 1, f"{name} should fail the gate:\n{out[-1500:]}")

class DescriptionExtractionTests(unittest.TestCase):
    """The entry's own description, since 2026-09-21: two elements and
    nothing else, a name guard on the opening paragraph, a bound cut only at
    a sentence boundary, and the curated prose never touched."""

    def setUp(self):
        from data_pipeline.verification.govman import (
            DESCRIPTION_KIND_MISSION, DESCRIPTION_KIND_OPENING, DESCRIPTION_MAX_CHARS,
            entity_description_texts, entry_description, sentence_bounded,
        )
        self.MISSION, self.OPENING, self.MAX = DESCRIPTION_KIND_MISSION, DESCRIPTION_KIND_OPENING, DESCRIPTION_MAX_CHARS
        self.texts, self.describe, self.bounded = entity_description_texts, entry_description, sentence_bounded

    def test_a_short_text_is_published_whole(self):
        self.assertEqual(self.bounded("The Agency protects human health.", 600),
                         ("The Agency protects human health.", False))

    def test_a_long_text_is_cut_at_the_last_sentence_boundary_within_the_bound(self):
        sentence = "The court was created by act of June 10, 1890 (19 U.S.C. ch. 4). "
        text = (sentence * 20).strip()
        cut, truncated = self.bounded(text, 600)
        self.assertTrue(truncated)
        self.assertLessEqual(len(cut), 600)
        self.assertTrue(text.startswith(cut))
        self.assertTrue(cut.endswith("(19 U.S.C. ch. 4)."), cut[-40:])
        # The last boundary at or before 600, not the first.
        self.assertGreater(len(cut), 600 - len(sentence))

    def test_an_abbreviation_is_never_taken_for_a_sentence_end(self):
        # "U.S.C." is followed by a digit, "ch." by a digit: neither is a
        # boundary, so a paragraph with no real sentence end inside the bound
        # yields nothing rather than a sentence the Manual never wrote.
        self.assertEqual(self.bounded("Authority under 15 U.S.C. 271 and ch. 872 and " + "x" * 700, 600), (None, True))
        cut, _ = self.bounded("Created by Public Law 95–91, the \"Energy Act.\" President Carter " + "y" * 700, 600)
        self.assertEqual(cut, "Created by Public Law 95–91, the \"Energy Act.\"")

    def test_the_mission_statement_wins_and_the_opening_paragraph_needs_the_units_name(self):
        entity = ET.fromstring("""
        <Entity><AgencyName>Widget Commission</AgencyName>
          <MissionStatement><Heading/><Record><Paragraph MissionStatmentId="1">The Widget Commission regulates widgets.</Paragraph></Record>
            <Record><Paragraph>The first Commission met in 1901.</Paragraph></Record></MissionStatement>
          <ProgramAndActivities><ProgramAndActivity><Activity><Details>
            <Detail><Paragraph></Paragraph></Detail>
            <Detail><Paragraph>The Widget Commission was established in 1900.</Paragraph></Detail>
          </Details></Activity></ProgramAndActivity></ProgramAndActivities>
        </Entity>""")
        texts = self.texts(entity)
        self.assertEqual(texts, {"mission": "The Widget Commission regulates widgets.",
                                 "opening": "The Widget Commission was established in 1900."},
                         "the FIRST record and the first NON-EMPTY paragraph")
        block, why = self.describe("Widget Commission", texts)
        self.assertEqual(why, "extracted")
        self.assertEqual(block["kind"], self.MISSION)
        self.assertEqual(block["extractedFrom"], "MissionStatement/Record[1]/Paragraph")
        self.assertFalse(block["truncated"])
        block, why = self.describe("Widget Commission", {"mission": None, "opening": texts["opening"]})
        self.assertEqual((why, block["kind"]), ("extracted", self.OPENING))
        block, why = self.describe("Widget Commission", {"mission": None, "opening": "The Commission posts an organizational chart online."})
        self.assertIsNone(block)
        self.assertEqual(why, "opening_paragraph_does_not_name_the_unit")
        # Names the unit in full and describes its website: the closed marker
        # list withholds it. A mission statement is never subject to the list.
        block, why = self.describe("Widget Commission", {"mission": None, "opening": "The Widget Commission (WC) posts an organizational chart in Portable Document Format (PDF)."})
        self.assertIsNone(block)
        self.assertEqual(why, "opening_paragraph_is_a_navigation_note")
        block, why = self.describe("Widget Commission", {"mission": "The Widget Commission runs the website of record.", "opening": None})
        self.assertEqual((why, block["kind"]), ("extracted", self.MISSION))
        self.assertEqual(self.describe("Widget Commission", {"mission": None, "opening": None}), (None, "no_descriptive_text"))

    def test_the_name_guard_is_tested_on_the_published_text(self):
        # The Court of International Trade's opening paragraph names the court
        # only after the 600-character cut; a reader sees the cut.
        tail = " The United States Court of International Trade was so renamed in 1980."
        head = ("The court was created by act of June 10, 1890, as the Board of General Appraisers. " * 8).strip()
        self.assertGreater(len(head), 600)
        block, why = self.describe("United States Court of International Trade", {"mission": None, "opening": head + tail})
        self.assertIsNone(block)
        self.assertEqual(why, "opening_paragraph_does_not_name_the_unit")

    def test_leadership_rows_footers_and_addresses_are_never_descriptive_text(self):
        entity = ET.fromstring("""
        <Entity><AgencyName>Widget Commission</AgencyName>
          <MissionStatement><Heading/></MissionStatement>
          <LeaderShipTables><LeaderShipTable><Header/><LeaderShipTableValues>
            <Values><NameColumnValue>A Person</NameColumnValue><TitleColumnValue>Chair of the Widget Commission</TitleColumnValue></Values>
          </LeaderShipTableValues></LeaderShipTable></LeaderShipTables>
          <Addresses><Address><Address>1 Widget Way, Washington, DC. The Widget Commission is here.</Address></Address></Addresses>
          <FooterDetails><Footer>The Widget Commission updated its Sources of Information 2-2019.</Footer></FooterDetails>
          <ProgramAndActivities/>
        </Entity>""")
        self.assertEqual(self.texts(entity), {"mission": None, "opening": None})
        self.assertEqual(self.describe("Widget Commission", self.texts(entity)), (None, "no_descriptive_text"))

    def test_the_real_fixture_is_verbatim_bounded_and_names_no_person(self):
        from data_pipeline.verification.govman import build_org_records
        manual = read_manual()
        records, stats = build_org_records(manual, load_base_graph(DEFAULT_BASE_GRAPH))
        by_entity = {e["entityId"]: e for e in manual["entities"]}
        # Office holders, read here in the TEST only, to assert that no
        # published description names one.
        people = set()
        for entity in iter_entities(ET.parse(DEFAULT_PACKAGE).getroot()):
            for row in entity.findall(".//LeaderShipTableValues/Values"):
                name = normalise(row.findtext("NameColumnValue"))
                if name:
                    people.add(name)
        self.assertGreater(len(people), 500)
        described = {k: r for k, r in records.items() if r.get("description")}
        self.assertGreaterEqual(len(described), 140, "the real join should describe most matched units")
        self.assertEqual(len(described), stats["descriptions_extracted"])
        self.assertGreater(stats["descriptions_mission_statement"], 80)
        self.assertGreater(stats["descriptions_opening_paragraph"], 40)
        self.assertGreater(stats["descriptions_truncated"], 0, "the bound should be doing work on the real Manual")
        self.assertGreater(stats["descriptions_refused_opening_paragraph_does_not_name_the_unit"], 0,
                           "the name guard should be doing work on the real Manual")
        for node_id, record in described.items():
            block = record["description"]
            texts = by_entity[record["entityId"]]["descriptionTexts"]
            printed = texts["mission"] if block["kind"] == self.MISSION else texts["opening"]
            self.assertLessEqual(len(block["text"]), self.MAX, node_id)
            self.assertEqual(block["text"], " ".join(block["text"].split()), node_id)
            if block["truncated"]:
                self.assertTrue(printed.startswith(block["text"]) and len(block["text"]) < len(printed), node_id)
                self.assertRegex(block["text"], r'[.!?]["”’)]*$', f"{node_id}: a cut must end at a sentence boundary")
                self.assertEqual(block["fullLength"], len(printed))
            else:
                self.assertEqual(block["text"], printed, f"{node_id}: not verbatim")
            if block["kind"] == self.OPENING:
                self.assertIsNone(texts["mission"], f"{node_id}: the mission statement wins where one is printed")
                self.assertIn(record["listedName"], block["text"], node_id)
            for person in people:
                self.assertNotIn(person, block["text"], f"{node_id} publishes a description naming {person!r}")
        # The guard's worked example: a navigation note is not a description.
        acf = next(r for r in records.values() if r["listedName"] == "Administration for Children and Families")
        self.assertIsNone(acf["description"])
        # And the one the name guard cannot see, because it names the unit in
        # full: "The Centers for Medicare and Medicaid Services (CMS) posts an
        # organizational chart in Portable Document Format".
        cms = next(r for r in records.values() if r["listedName"] == "Centers for Medicare and Medicaid Services")
        self.assertIsNone(cms["description"])
        self.assertEqual(stats["descriptions_refused_opening_paragraph_is_a_navigation_note"], 4)
        for record in described.values():
            self.assertNotIn("organizational chart", record["description"]["text"].casefold())
            self.assertNotIn("organization chart", record["description"]["text"].casefold())

    def test_a_record_lacking_a_description_still_records_the_entry(self):
        from data_pipeline.verification.govman import build_org_records
        records, _ = build_org_records(read_manual(), load_base_graph(DEFAULT_BASE_GRAPH))
        self.assertTrue(any(r["description"] is None for r in records.values()))
        for record in records.values():
            self.assertIn("granule", record)


class DescriptionApplyTests(unittest.TestCase):
    """`descriptionOfficial` sits beside `desc` and never in its place."""

    def setUp(self):
        from data_pipeline.verification.govman import apply_govman_org_evidence
        self.apply = apply_govman_org_evidence

    def tree(self):
        return {"id": "root", "name": "Root", "type": "Foundation", "children": [
            {"id": "fmc", "name": "Federal Maritime Commission", "type": "Independent Agency",
             "desc": "Curated prose about the FMC.", "children": []},
        ]}

    def record(self, description):
        return {"fmc": {
            "source": "us_government_manual", "nodeName": "Federal Maritime Commission",
            "listedName": "Federal Maritime Commission", "entityId": "144", "parentListedName": None,
            "parentEntityId": None, "package": "GOVMAN-2025-12-31", "edition": "2025-12-31",
            "granule": "GOVMAN-2025-12-31-144",
            "url": "https://www.govinfo.gov/app/details/GOVMAN-2025-12-31/GOVMAN-2025-12-31-144",
            "documentSha256": "abc", "description": description,
        }}

    def good(self):
        return {"kind": "mission_statement", "extractedFrom": "MissionStatement/Record[1]/Paragraph",
                "text": "The Federal Maritime Commission promotes an efficient, fair, and reliable supply system.",
                "truncated": False, "fullLength": 89}

    def test_the_block_is_published_beside_the_curated_prose(self):
        tree = self.tree()
        stats = self.apply(tree, self.record(self.good()))
        node = tree["children"][0]
        self.assertEqual(stats["descriptions_published"], 1)
        block = node["descriptionOfficial"]
        self.assertEqual(block["text"], self.good()["text"])
        self.assertEqual(block["kind"], "mission_statement")
        self.assertEqual(block["source"], "us_government_manual")
        self.assertEqual(block["granule"], "GOVMAN-2025-12-31-144")
        self.assertEqual(block["url"], self.record(None)["fmc"]["url"])
        self.assertEqual(block["documentSha256"], "abc")
        self.assertEqual(block["edition"], "2025-12-31")
        self.assertEqual(node["desc"], "Curated prose about the FMC.", "the curated prose is never overwritten")
        self.assertNotIn("descriptionSource", node, "the curated prose keeps its own, uncited, label")

    def test_no_description_on_the_record_publishes_nothing(self):
        tree = self.tree()
        stats = self.apply(tree, self.record(None))
        self.assertEqual(stats["descriptions_published"], 0)
        self.assertNotIn("descriptionOfficial", tree["children"][0])
        self.assertIn("govmanEntry", tree["children"][0])

    def test_an_over_long_or_unknown_kind_block_is_refused(self):
        for bad in (dict(self.good(), text="x" * 601), dict(self.good(), kind="footer"), dict(self.good(), text="  ")):
            tree = self.tree()
            self.apply(tree, self.record(bad))
            self.assertNotIn("descriptionOfficial", tree["children"][0], bad.get("kind"))

    def test_a_renamed_node_keeps_nothing(self):
        tree = self.tree()
        tree["children"][0]["name"] = "Federal Maritime Board"
        self.apply(tree, self.record(self.good()))
        self.assertNotIn("descriptionOfficial", tree["children"][0])
        self.assertEqual(tree["children"][0]["desc"], "Curated prose about the FMC.")

    def test_the_field_is_withdrawn_by_the_evidence_sweep_and_kept_for_the_viewer(self):
        from data_pipeline.exporter.build_graph import MINIMAL_GRAPH_FIELDS
        from data_pipeline.verification.evidence import apply_evidence_to_tree
        self.assertIn("descriptionOfficial", EVIDENCE_OWNED_FIELDS)
        self.assertIn("descriptionOfficial", MINIMAL_GRAPH_FIELDS)
        tree = self.tree()
        self.apply(tree, self.record(self.good()))
        apply_evidence_to_tree(tree, {})
        self.assertNotIn("descriptionOfficial", tree["children"][0])
        self.assertEqual(tree["children"][0]["desc"], "Curated prose about the FMC.")


class DescriptionGateTests(unittest.TestCase):
    """The gate re-derives the text from the committed package with its own
    parse, and refuses each way the block could lie."""

    @classmethod
    def setUpClass(cls):
        if not PUBLISHED.exists():
            raise unittest.SkipTest("output/graph.json is not built")
        from data_pipeline.verification.govman import build_org_records
        cls.graph = json.loads(PUBLISHED.read_text(encoding="utf-8"))
        cls.records, _ = build_org_records(read_manual(), load_base_graph(DEFAULT_BASE_GRAPH))

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

    def block_for(self, record):
        block = record["description"]
        return {
            "text": block["text"], "kind": block["kind"], "extractedFrom": block["extractedFrom"],
            "truncated": block["truncated"], "fullLength": block["fullLength"],
            "source": "us_government_manual", "listedName": record["listedName"],
            "edition": record["edition"], "package": record["package"], "granule": record["granule"],
            "url": record["url"], "documentSha256": record["documentSha256"],
        }

    def stamped(self, want_truncated=False):
        """A copy of the published graph with one node carrying a block the
        module would have written, exactly as apply_govman_org_evidence
        writes it; returns the graph and that node."""
        graph = copy.deepcopy(self.graph)
        stack = [graph]
        while stack:
            node = stack.pop()
            entry = node.get("govmanEntry")
            record = self.records.get(str(node.get("id") or ""))
            if (isinstance(entry, dict) and record and record.get("description")
                    and record["granule"] == entry.get("granule")
                    and bool(record["description"]["truncated"]) == want_truncated):
                node["descriptionOfficial"] = self.block_for(record)
                return graph, node
            stack.extend([c for c in (node.get("children") or []) if isinstance(c, dict)])
        self.skipTest("no published node matches a record with the wanted description")

    LINE = "a Government Manual description is that entry's own text, verbatim, beside the curated prose"

    def assert_refused(self, mutate, because, want_truncated=False):
        graph, node = self.stamped(want_truncated)
        mutate(node)
        code, output = self.run_gate(graph)
        self.assertEqual(code, 1, f"the gate accepted a graph where {because}")
        self.assertIn("FAIL  " + self.LINE, output, because)

    def test_a_block_the_module_would_write_passes(self):
        for want in (False, True):
            graph, node = self.stamped(want)
            code, output = self.run_gate(graph)
            self.assertIn("ok    " + self.LINE, output)
            self.assertEqual(code, 0, output[-2000:])
            # The published graph carries the module's own blocks already, so
            # the count is whatever the stamped graph holds, never a literal.
            carrying = 0
            stack = [graph]
            while stack:
                item = stack.pop()
                carrying += 1 if isinstance(item.get("descriptionOfficial"), dict) else 0
                stack.extend([c for c in (item.get("children") or []) if isinstance(c, dict)])
            self.assertGreaterEqual(carrying, 1)
            self.assertIn(f"Manual (descriptions): {carrying:,} organisations", output)

    def test_the_gates_parser_agrees_with_the_module_on_every_entry(self):
        from scripts.validate_published_graph import (
            GOVMAN_DESCRIPTION_MAX_CHARS, GOVMAN_DESCRIPTION_PATHS, GOVMAN_SENTENCE_BOUNDARY, govman_descriptions,
        )
        from data_pipeline.verification.govman import DESCRIPTION_MAX_CHARS, DESCRIPTION_PATHS, SENTENCE_BOUNDARY
        theirs, digest = govman_descriptions()
        manual = read_manual()
        self.assertEqual(digest, manual["sha256"])
        self.assertEqual(GOVMAN_DESCRIPTION_MAX_CHARS, DESCRIPTION_MAX_CHARS)
        self.assertEqual(GOVMAN_DESCRIPTION_PATHS, DESCRIPTION_PATHS)
        self.assertEqual(GOVMAN_SENTENCE_BOUNDARY.pattern, SENTENCE_BOUNDARY.pattern)
        self.assertEqual(len(theirs), len(manual["entities"]))
        for entry in manual["entities"]:
            granule = access_id(manual["package"], entry["entityId"])
            self.assertEqual(theirs[granule], entry["descriptionTexts"], f"{entry['name']}: the two parsers disagree")

    def test_text_altered(self):
        self.assert_refused(lambda n: n["descriptionOfficial"].update(text=n["descriptionOfficial"]["text"] + " It also makes widgets."),
                            "the text is not verbatim in the entry")

    def test_text_from_another_entry(self):
        other = next(r for r in self.records.values() if r.get("description") and r["description"]["kind"] == "mission_statement"
                     and r["listedName"] == "Environmental Protection Agency")
        self.assert_refused(lambda n: n["descriptionOfficial"].update(text=other["description"]["text"]) if n["descriptionOfficial"]["text"] != other["description"]["text"] else n["descriptionOfficial"].update(text="The Agency does other things."),
                            "the text is another entry's")

    def test_granule_swapped_for_another_real_one(self):
        self.assert_refused(lambda n: (n["descriptionOfficial"].update(granule="GOVMAN-2025-12-31-135"), n["govmanEntry"].update(granule="GOVMAN-2025-12-31-135")),
                            "the granule names a different agency")

    def test_granule_differs_from_the_entry_block(self):
        self.assert_refused(lambda n: n["descriptionOfficial"].update(granule="GOVMAN-2025-12-31-135"),
                            "the description cites a granule its own entry block does not")

    def test_entry_block_removed(self):
        self.assert_refused(lambda n: n.pop("govmanEntry"), "a description outlives the entry it was read from")

    def test_url_not_the_granules(self):
        self.assert_refused(lambda n: n["descriptionOfficial"].update(url="https://www.govinfo.gov/content/pkg/x.htm"),
                            "the URL does not address the granule")

    def test_digest_mismatch(self):
        self.assert_refused(lambda n: n["descriptionOfficial"].update(documentSha256="0" * 64),
                            "the digest is not the committed package's")

    def test_on_a_post(self):
        self.assert_refused(lambda n: n.update(type="Position"), "a description sits on a post")

    def test_node_renamed(self):
        self.assert_refused(lambda n: n.update(name="Renamed Unit"), "the node no longer carries the matched name")

    def test_edition_in_the_future(self):
        self.assert_refused(lambda n: n["descriptionOfficial"].update(edition="2999-01-01"), "the edition has not happened")

    def test_unknown_kind_and_wrong_element_path(self):
        self.assert_refused(lambda n: n["descriptionOfficial"].update(kind="footer"), "the kind is not one that is read")
        self.assert_refused(lambda n: n["descriptionOfficial"].update(extractedFrom="FooterDetails/Footer"), "the element path is not where a description is read")

    def test_over_the_bound(self):
        self.assert_refused(lambda n: n["descriptionOfficial"].update(text=n["descriptionOfficial"]["text"] + " x" * 400), "the text is past the bound")

    def test_a_cut_not_at_a_sentence_boundary(self):
        self.assert_refused(lambda n: n["descriptionOfficial"].update(text=n["descriptionOfficial"]["text"][:-3]),
                            "a cut text does not end at a sentence boundary", want_truncated=True)

    def test_a_whole_text_flagged_as_cut(self):
        self.assert_refused(lambda n: n["descriptionOfficial"].update(truncated=True),
                            "a whole text says it was cut")

    def test_the_curated_prose_replaced_by_the_manuals_text(self):
        self.assert_refused(lambda n: (n.update(desc=n["descriptionOfficial"]["text"]), n.pop("descriptionSource", None)),
                            "the curated prose was overwritten with the Manual's text")

    def test_a_navigation_note_that_is_verbatim_and_names_the_unit_is_still_refused(self):
        """CMS's opening paragraph is the Manual's own words, under the
        bound, and names the unit in full -- every other check passes -- and
        it describes a website. Only the marker list refuses it."""
        from data_pipeline.verification.govman import read_manual as _read
        manual = _read()
        cms = next(e for e in manual["entities"] if e["name"] == "Centers for Medicare and Medicaid Services")
        opening = cms["descriptionTexts"]["opening"]
        self.assertIn("organizational chart", opening)
        graph = copy.deepcopy(self.graph)
        stack = [graph]
        target = None
        while stack:
            node = stack.pop()
            entry = node.get("govmanEntry")
            if isinstance(entry, dict) and entry.get("granule") == access_id(manual["package"], cms["entityId"]):
                target = node
                break
            stack.extend([c for c in (node.get("children") or []) if isinstance(c, dict)])
        if target is None:
            self.skipTest("the published graph carries no CMS entry")
        record = self.records[target["id"]]
        target["descriptionOfficial"] = dict(self.block_for(dict(record, description={
            "kind": "opening_paragraph", "extractedFrom": "ProgramAndActivities//Detail/Paragraph[first non-empty]",
            "text": opening, "truncated": False, "fullLength": len(opening)})))
        code, output = self.run_gate(graph)
        self.assertEqual(code, 1)
        self.assertIn("FAIL  " + self.LINE, output)
        self.assertIn("publishes a note about the unit's website", output)


if __name__ == "__main__":
    unittest.main()
