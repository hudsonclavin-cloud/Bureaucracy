"""A post's title, read off the signature block of a document it signed.

Three things make this source worth having and dangerous in the same breath,
and each is pinned here in both directions:

  - the block pairs a TITLE with a LIVING PERSON, on the line directly above
    it, and the person is never read. That is not a promise here, it is a
    slice: `signature_title` finds the name line's index and builds the title
    out of the lines BELOW it. The test that matters reads every committed
    document, collects every name line in it, and asserts none of them is
    anywhere in what the module returns, writes or prints;
  - the scope is the Federal Register's own `agencies` field, not the words
    in the signature. A rule the Coast Guard signs is filed under two
    agencies that are both nodes here, and is refused;
  - the titles this graph carries are stamped ones -- `General Counsel` names
    84 nodes and `Inspector General` 72 -- so a record that drifts to another
    node keeps a real title, a real document and a real URL, and only the
    parent tells them apart.

The join rules and the gate rules are exercised against fixtures WRITTEN here,
not against the committed ones. That is deliberate: the Federal Register
publishes whatever it publishes, so a corpus fetched today may trip a given
rule once or never, and a rule that is only tested when the host happens to
cooperate is not pinned at all. The committed fixtures are still read, and
what they yield is checked -- the digests, the media type, the signer's name,
the scope, and the gate accepting whatever records they really produce.
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.exporter.build_graph import (  # noqa: E402
    DEFAULT_BASE_GRAPH,
    MINIMAL_GRAPH_FIELDS,
    canonical_name_key,
    index_tree,
    load_base_graph,
)
from data_pipeline.verification.directories import federal_register_name_keys  # noqa: E402
from data_pipeline.verification.evidence import EVIDENCE_OWNED_FIELDS  # noqa: E402
from data_pipeline.verification.federal_register_signatures import (  # noqa: E402
    DOCUMENT_DIR,
    DOCUMENT_URL,
    INDEX_DIR,
    METHOD,
    MIN_POST_TOKENS,
    NAME_LINE,
    SOURCE_TYPE,
    Unreadable,
    apply_signature_evidence,
    build_records,
    load_fixture,
    read_documents,
    read_index,
    signature_title,
)

PUBLISHED = PROJECT_ROOT / "output" / "graph.json"


def index_files():
    return [p for p in sorted(INDEX_DIR.glob("*.json")) if not p.name.endswith(".meta.json")]


def document_files():
    return sorted(DOCUMENT_DIR.glob("*.txt"))


def require_fixtures():
    if not index_files() or not document_files():
        raise unittest.SkipTest("the Federal Register signature fixtures are not committed")


class FixtureIntegrityTests(unittest.TestCase):
    """The bytes on disk are the publisher's, and the code says so before reading."""

    def setUp(self):
        require_fixtures()

    def test_every_fixture_matches_its_fetch_record(self):
        for path in index_files() + document_files():
            meta_path = path.with_name(path.name + ".meta.json")
            self.assertTrue(meta_path.exists(), f"{path.name} has no fetch record beside it")
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), meta["sha256"],
                             f"{path.name} does not match the digest its fetch recorded")
            self.assertTrue(str(meta["url"]).startswith("https://www.federalregister.gov/"))
            self.assertEqual(meta["status"], 200)
            self.assertIsNone(meta["error"])

    def test_every_committed_document_is_the_plain_text_rendering(self):
        # The host answers this path with an HTML "Request Access" page at
        # random. Such a response is not the document: it is refused and
        # retried, and none is ever committed.
        for path in document_files():
            meta = json.loads(path.with_name(path.name + ".meta.json").read_text(encoding="utf-8"))
            self.assertEqual(str(meta["content_type"]).split(";")[0].strip(), "text/plain",
                             f"{path.name} was served as markup and should not be committed")

    def test_a_tampered_document_is_refused(self):
        import tempfile

        path = document_files()[0]
        meta = json.loads(path.with_name(path.name + ".meta.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / path.name
            fake.write_bytes(path.read_bytes() + b"\nHarold Aardvark,\nGrand Vizier.\n")
            fake.with_name(fake.name + ".meta.json").write_text(json.dumps(meta), encoding="utf-8")
            with self.assertRaises(Unreadable):
                load_fixture(fake)

    def test_a_refusal_leaves_a_record_and_no_fixture(self):
        # The counterpart of the rule above: where the host never served the
        # document, the meta file says so and nothing was written beside it.
        orphans = [p for p in DOCUMENT_DIR.glob("*.meta.json")
                   if not p.with_name(p.name[: -len(".meta.json")]).exists()]
        for path in orphans:
            meta = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(meta.get("error"), f"{path.name} claims a fetch but no document is beside it")
            self.assertIsNone(meta.get("sha256"))


class SignatureParsingTests(unittest.TestCase):
    """The block's shape, and the one thing that must never come out of it."""

    BLOCK = (
        "    (d) Enforcement period. This section will be enforced from 8:30 \n"
        "p.m. until 9:10 p.m. on September 26, 2026.\n"
        "\n"
        "R.N. Macon,\n"
        "Captain, U.S. Coast Guard, Captain of the Port, Lake Michigan.\n"
        "[FR Doc. 2026-19270 Filed 9-18-26; 8:45 am]\n"
        "BILLING CODE 9110-04-P\n"
    )

    def test_the_title_is_read_and_the_name_is_not(self):
        title, why = signature_title(self.BLOCK, "2026-19270")
        self.assertEqual(why, "ok")
        self.assertEqual(title, "Captain, U.S. Coast Guard, Captain of the Port, Lake Michigan")
        self.assertNotIn("Macon", title)
        self.assertNotIn("R.N.", title)

    def test_a_title_wrapped_over_two_lines_is_rejoined(self):
        text = ("Alice M. Kottmyer,\n"
                "Attorney-Adviser, Office of the Legal Adviser, U.S. Department of \n"
                "State.\n"
                "[FR Doc. 2026-19223 Filed 9-18-26; 8:45 am]\n")
        title, why = signature_title(text, "2026-19223")
        self.assertEqual(why, "ok")
        self.assertEqual(title, "Attorney-Adviser, Office of the Legal Adviser, U.S. Department of State")

    def test_a_document_with_no_signature_block_yields_nothing(self):
        text = ("----------------------------------------------------------\n"
                "\n"
                "[FR Doc. 2026-19150 Filed 9-17-26; 8:45 am]\n")
        title, why = signature_title(text, "2026-19150")
        self.assertIsNone(title)
        self.assertEqual(why, "no_signature_block_above_the_fr_doc_line")

    def test_the_fr_doc_line_must_carry_this_documents_number(self):
        title, why = signature_title(self.BLOCK, "2026-00001")
        self.assertIsNone(title)
        self.assertEqual(why, "document_prints_no_fr_doc_line_for_this_number")

    def test_markup_in_the_block_is_refused_rather_than_cleaned(self):
        text = ('John Q. Smith,\n'
                'Director, <a href="x">Office</a> of Things.\n'
                '[FR Doc. 2026-00002 Filed 9-17-26; 8:45 am]\n')
        title, why = signature_title(text, "2026-00002")
        self.assertIsNone(title)
        self.assertEqual(why, "markup_inside_the_signature_block")

    def test_a_block_that_does_not_end_in_a_full_stop_is_refused(self):
        text = ("John Q. Smith,\n"
                "Director, Office of Things\n"
                "[FR Doc. 2026-00003 Filed 9-17-26; 8:45 am]\n")
        title, why = signature_title(text, "2026-00003")
        self.assertIsNone(title)
        self.assertEqual(why, "the_title_does_not_end_in_a_full_stop")

    def test_the_search_stops_at_a_blank_line_rather_than_walking_into_the_body(self):
        # Without the stop, "Some Body," several paragraphs up would be taken
        # for the signer and the whole intervening text for the title.
        text = ("Some Body,\n"
                "\n"
                "The agency has determined that this action is not significant.\n"
                "[FR Doc. 2026-00004 Filed 9-17-26; 8:45 am]\n")
        title, why = signature_title(text, "2026-00004")
        self.assertIsNone(title)
        self.assertEqual(why, "no_signature_block_above_the_fr_doc_line")


class TheSignersNameIsNeverReadTests(unittest.TestCase):
    """The rule, tested over every committed document rather than asserted.

    `positions.py` never reads the PLUM archive's incumbent columns and
    `whitehouse_pay.py` discards its report's NAME column at parse time. Here
    the equivalent is structural, so the test is the strongest of the three:
    collect every line in every committed document that the module's own name
    pattern matches, and assert that not one of them appears in anything the
    module returns.
    """

    @classmethod
    def setUpClass(cls):
        require_fixtures()
        cls.documents, _ = read_documents()
        cls.base = load_base_graph(DEFAULT_BASE_GRAPH)
        cls.records, _ = build_records(cls.documents, cls.base)

    def names_printed(self):
        """Exactly the line the module locates and steps over, per document.

        Collected the same way the module finds it -- from the document's own
        `[FR Doc. <number> Filed …]` line, upwards to the first line with the
        shape of a signer's name -- so this is the precise string that must
        never appear in anything published, rather than every capitalised
        phrase in the corpus.
        """
        found = set()
        for path in document_files():
            number = path.name[: -len(".txt")]
            lines = path.read_bytes().decode("utf-8", "replace").split("\n")
            marker = f"[FR Doc. {number} Filed"
            at = next((i for i, line in enumerate(lines) if line.strip().startswith(marker)), None)
            if at is None:
                continue
            for j in range(at - 1, max(-1, at - 9), -1):
                stripped = lines[j].strip()
                if not stripped:
                    break
                if NAME_LINE.match(stripped):
                    found.add(stripped.rstrip(",").strip())
                    break
        return {n for n in found if len(n) > 4}

    def test_no_published_string_is_a_name_the_documents_print(self):
        names = self.names_printed()
        self.assertTrue(names, "no signer names were found to test against")
        published = json.dumps({"documents": self.documents, "records": self.records})
        for name in names:
            self.assertNotIn(name, published,
                             f"{name!r} is a signer's name and it reached what this module publishes")

    def test_a_listed_title_is_never_the_line_above_it_in_its_own_document(self):
        # The shape of a name is not a usable test on the title: "Attorney
        # General," matches it, and that is a real post. What must hold is
        # that the published title is not the line the module stepped over
        # in the document the record cites.
        for record in self.records.values():
            number = record["documentNumber"]
            path = DOCUMENT_DIR / f"{number}.txt"
            lines = path.read_bytes().decode("utf-8", "replace").split("\n")
            marker = f"[FR Doc. {number} Filed"
            at = next(i for i, line in enumerate(lines) if line.strip().startswith(marker))
            signer = None
            for j in range(at - 1, max(-1, at - 9), -1):
                stripped = lines[j].strip()
                if not stripped:
                    break
                if NAME_LINE.match(stripped):
                    signer = stripped.rstrip(",").strip()
                    break
            self.assertIsNotNone(signer, number)
            self.assertNotEqual(record["listedTitle"], signer,
                                f"{number}: the published title is the signer's line")


class BuiltFixtureTests(unittest.TestCase):
    """Every join rule, on a fixture set written here.

    The committed documents are whatever the Register happened to publish, so
    on their own they cannot exercise a rule nothing in them trips. These
    fixtures are built to trip each one exactly once, in both directions.
    """

    AGENCIES = {
        "one": [{"name": "Widget Commission"}],
        "two": [{"name": "Widget Commission"}, {"name": "Gadget Bureau"}],
        "none": [{"name": "Nowhere Authority"}],
    }

    def build(self, rows, graph):
        """A temporary fixture tree, and the records it yields."""
        import tempfile

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        (root / "index").mkdir()
        (root / "documents").mkdir()
        results = []
        for number, agencies, body in rows:
            results.append({
                "document_number": number,
                "raw_text_url": f"https://www.federalregister.gov/documents/full_text/text/2026/01/01/{number}.txt",
                "html_url": DOCUMENT_URL.format(number),
                "agencies": self.AGENCIES[agencies],
                "signing_date": None,
                "publication_date": "2026-01-01",
                "title": f"A notice numbered {number}",
                "type": "Notice",
            })
            self.write(root / "documents" / f"{number}.txt", body.encode("utf-8"), "text/plain",
                       results[-1]["raw_text_url"])
        self.write(root / "index" / "widget.json",
                   json.dumps({"results": results}).encode("utf-8"), "application/json",
                   "https://www.federalregister.gov/api/v1/documents.json?per_page=2")
        documents, read_stats = read_documents(root / "index", root / "documents")
        records, stats = build_records(documents, graph)
        return records, {**read_stats, **stats}

    @staticmethod
    def write(path, body, content_type, url):
        path.write_bytes(body)
        path.with_name(path.name + ".meta.json").write_text(json.dumps({
            "fetched_at": "2026-01-02T00:00:00Z", "url": url, "status": 200,
            "final_url": url, "content_type": content_type,
            "user_agent": "bureaucracy-data-pipeline/1.0", "robots": "allows /",
            "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(), "error": None,
        }), encoding="utf-8")

    @staticmethod
    def signature(number, title, name="Jane Q. Public"):
        return (f"Some body text about the matter at hand.\n\n{name},\n{title}.\n"
                f"[FR Doc. {number} Filed 1-1-26; 8:45 am]\nBILLING CODE 0000-00-P\n")

    @staticmethod
    def graph(children):
        return {
            "id": "root", "name": "Root", "type": "Branch",
            "children": [{
                "id": "widget", "name": "Widget Commission", "type": "Agency",
                "children": children,
            }, {
                "id": "gadget", "name": "Gadget Bureau", "type": "Agency", "children": [
                    {"id": "gadget-gc", "name": "General Counsel", "type": "Position", "children": []},
                ],
            }],
        }

    POST = {"id": "widget-gc", "name": "General Counsel", "type": "Position", "children": []}

    def test_one_agency_one_post_is_matched(self):
        records, stats = self.build(
            [("2026-00001", "one", self.signature("2026-00001", "General Counsel"))],
            self.graph([dict(self.POST)]))
        self.assertEqual(list(records), ["widget-gc"])
        record = records["widget-gc"]
        self.assertEqual(record["listedTitle"], "General Counsel")
        self.assertEqual(record["organisationId"], "widget")
        self.assertEqual(record["occurrences"], 1)
        self.assertEqual(record["documentUrl"], DOCUMENT_URL.format("2026-00001"))
        self.assertNotIn("Jane", json.dumps(record))
        self.assertEqual(stats["signatures_matched"], 1)

    def test_two_agencies_that_both_name_a_node_reach_nothing(self):
        records, stats = self.build(
            [("2026-00002", "two", self.signature("2026-00002", "General Counsel"))],
            self.graph([dict(self.POST)]))
        self.assertEqual(records, {})
        self.assertEqual(stats["refused_agencies_reach_several_organisations"], 1)

    def test_an_agency_that_names_no_node_reaches_nothing(self):
        records, stats = self.build(
            [("2026-00003", "none", self.signature("2026-00003", "General Counsel"))],
            self.graph([dict(self.POST)]))
        self.assertEqual(records, {})
        self.assertEqual(stats["refused_agencies_reach_no_organisation"], 1)

    def test_a_title_naming_its_organisation_is_never_split(self):
        # "General Counsel, Widget Commission" is the common form, and
        # splitting it to reach the node named "General Counsel" would be
        # producing a title rather than selecting one.
        records, stats = self.build(
            [("2026-00004", "one", self.signature("2026-00004", "General Counsel, Widget Commission"))],
            self.graph([dict(self.POST)]))
        self.assertEqual(records, {})
        self.assertEqual(stats["refused_organisation_carries_no_post_of_that_name"], 1)

    def test_a_title_is_never_matched_by_containment(self):
        # "Press Secretary" inside "Assistant Press Secretary": the deputy's
        # title must not price or confirm the principal, or the reverse.
        records, _ = self.build(
            [("2026-00005", "one", self.signature("2026-00005", "Assistant Press Secretary"))],
            self.graph([{"id": "widget-ps", "name": "Press Secretary", "type": "Position", "children": []}]))
        self.assertEqual(records, {})

    def test_a_one_token_title_is_refused(self):
        records, stats = self.build(
            [("2026-00006", "one", self.signature("2026-00006", "Administrator"))],
            self.graph([{"id": "widget-adm", "name": "Administrator", "type": "Position", "children": []}]))
        self.assertEqual(records, {})
        self.assertEqual(stats["refused_title_under_two_tokens"], 1)

    def test_two_siblings_of_that_name_claim_neither(self):
        records, stats = self.build(
            [("2026-00007", "one", self.signature("2026-00007", "General Counsel"))],
            self.graph([dict(self.POST),
                        {"id": "widget-gc2", "name": "General Counsel", "type": "Position", "children": []}]))
        self.assertEqual(records, {})
        self.assertEqual(stats["refused_siblings_share_the_name"], 1)

    def test_a_descendant_that_is_not_a_direct_child_is_not_reached(self):
        records, stats = self.build(
            [("2026-00008", "one", self.signature("2026-00008", "General Counsel"))],
            self.graph([{"id": "widget-div", "name": "Enforcement Division", "type": "Office",
                         "children": [dict(self.POST)]}]))
        self.assertEqual(records, {})
        self.assertEqual(stats["refused_organisation_carries_no_post_of_that_name"], 1)

    def test_an_organisation_of_that_name_is_not_a_post(self):
        records, stats = self.build(
            [("2026-00009", "one", self.signature("2026-00009", "Office of General Counsel"))],
            self.graph([{"id": "widget-ogc", "name": "Office of General Counsel", "type": "Office",
                         "children": []}]))
        self.assertEqual(records, {})
        self.assertEqual(stats["refused_organisation_carries_no_post_of_that_name"], 1)

    def test_several_documents_carrying_one_title_are_counted_and_the_latest_cited(self):
        rows = [("2026-00010", "one", self.signature("2026-00010", "General Counsel")),
                ("2026-00011", "one", self.signature("2026-00011", "General Counsel", "A. N. Other"))]
        records, _ = self.build(rows, self.graph([dict(self.POST)]))
        self.assertEqual(records["widget-gc"]["occurrences"], 2)
        self.assertEqual(records["widget-gc"]["documentNumber"], "2026-00011")

    def test_a_response_that_is_not_plain_text_is_never_parsed(self):
        import tempfile

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "index").mkdir()
        (root / "documents").mkdir()
        number = "2026-00012"
        url = f"https://www.federalregister.gov/documents/full_text/text/2026/01/01/{number}.txt"
        self.write(root / "index" / "widget.json", json.dumps({"results": [{
            "document_number": number, "raw_text_url": url, "html_url": DOCUMENT_URL.format(number),
            "agencies": self.AGENCIES["one"], "signing_date": None,
            "publication_date": "2026-01-01", "title": "A notice", "type": "Notice",
        }]}).encode("utf-8"), "application/json", "https://www.federalregister.gov/api/v1/documents.json")
        body = ("<html><body><h1>Request Access</h1>"
                + self.signature(number, "General Counsel") + "</body></html>").encode("utf-8")
        self.write(root / "documents" / f"{number}.txt", body, "text/html; charset=utf-8", url)
        documents, stats = read_documents(root / "index", root / "documents")
        self.assertEqual(documents, [])
        self.assertEqual(stats["documents_refused_by_the_host"], 1)


class ScopingTests(unittest.TestCase):
    """The API's agency list decides, and only when it decides one thing."""

    @classmethod
    def setUpClass(cls):
        require_fixtures()
        cls.documents, cls.read_stats = read_documents()
        cls.base = load_base_graph(DEFAULT_BASE_GRAPH)
        cls.node_map, cls.parent_map = index_tree(cls.base)
        cls.records, cls.stats = build_records(cls.documents, cls.base)

    def test_every_record_names_a_post_that_is_a_direct_child_of_the_scoped_organisation(self):
        for node_id, record in self.records.items():
            node = self.node_map[node_id]
            self.assertIn("position", str(node.get("type") or "").casefold())
            self.assertEqual(self.parent_map.get(node_id), record["organisationId"])
            self.assertEqual(canonical_name_key(node["name"]), canonical_name_key(record["listedTitle"]))

    def test_the_agency_list_of_every_record_reaches_exactly_the_scoped_organisation(self):
        org_by_key = {}
        for node_id, node in self.node_map.items():
            if "position" not in str(node.get("type") or "").casefold():
                key = canonical_name_key(node.get("name"))
                if key:
                    org_by_key.setdefault(key, set()).add(node_id)
        for record in self.records.values():
            reached = set()
            for name in record["agenciesListed"]:
                for key in federal_register_name_keys(name):
                    reached |= org_by_key.get(key, set())
            self.assertEqual(reached, {record["organisationId"]})

    def test_a_title_under_two_tokens_is_refused(self):
        for record in self.records.values():
            self.assertGreaterEqual(len(canonical_name_key(record["listedTitle"]).split()), MIN_POST_TOKENS)

    def test_a_document_listing_two_graph_organisations_reaches_nothing(self):
        # The Coast Guard case: the Register files its rules under both
        # "Homeland Security Department" and "Coast Guard", and both are
        # nodes here, so the document is refused rather than assigned.
        cited = {r["documentNumber"] for r in self.records.values()}
        org_by_key = {}
        for node_id, node in self.node_map.items():
            if "position" not in str(node.get("type") or "").casefold():
                key = canonical_name_key(node.get("name"))
                if key:
                    org_by_key.setdefault(key, set()).add(node_id)
        for document in self.documents:
            reached = set()
            for name in document["agenciesListed"]:
                for key in federal_register_name_keys(name):
                    reached |= org_by_key.get(key, set())
            if len(reached) > 1:
                self.assertNotIn(document["documentNumber"], cited)

    def test_the_refusals_are_counted_rather_than_silent(self):
        for reason in ("refused_no_signature_title",
                       "refused_agencies_reach_no_organisation",
                       "refused_agencies_reach_several_organisations",
                       "refused_title_under_two_tokens",
                       "refused_organisation_carries_no_post_of_that_name",
                       "refused_siblings_share_the_name"):
            self.assertIn(reason, self.stats)
        counted = sum(self.stats[r] for r in self.stats if r.startswith("refused_"))
        self.assertEqual(counted + self.stats["signatures_matched"], self.stats["documents_considered"])

    def test_a_document_the_host_never_served_is_counted_not_dropped(self):
        listed, _ = read_index()
        self.assertEqual(
            self.read_stats["documents_read"]
            + self.read_stats["documents_refused_by_the_host"]
            + self.read_stats["documents_not_fetched"], len(listed))


class ApplicationTests(unittest.TestCase):
    """What reaches a node, and what may never."""

    @classmethod
    def setUpClass(cls):
        require_fixtures()
        documents, _ = read_documents()
        cls.base = load_base_graph(DEFAULT_BASE_GRAPH)
        cls.records, _ = build_records(documents, cls.base)
        if not cls.records:
            raise unittest.SkipTest("no signature reaches a node on the committed fixtures")

    def applied(self, records=None):
        graph = copy.deepcopy(self.base)
        stats = apply_signature_evidence(graph, records if records is not None else self.records)
        node_map, _ = index_tree(graph)
        return graph, node_map, stats

    def test_a_signature_stamps_its_block_its_url_and_its_method(self):
        _graph, node_map, stats = self.applied()
        self.assertEqual(stats["listed"], len(self.records))
        for node_id, record in self.records.items():
            node = node_map[node_id]
            block = node["federalRegisterSignature"]
            self.assertEqual(block["documentNumber"], record["documentNumber"])
            self.assertIn(record["url"], node["sourceUrls"])
            self.assertIn(record["url"], node["evidenceUrls"])
            self.assertIn(SOURCE_TYPE, node["sourceTypes"])
            self.assertEqual(node["verificationMethod"], METHOD)
            self.assertEqual(node["lastVerified"], record["publicationDate"])

    def test_no_placement_is_ever_claimed(self):
        _graph, node_map, _ = self.applied()
        for node_id in self.records:
            node = node_map[node_id]
            for field in ("placementVerified", "placementUrl", "placementMethod",
                          "placementParentId", "placementVerifiedAt"):
                self.assertNotIn(field, node, f"{node_id} gained {field} from one document")

    def test_nothing_writes_a_cost(self):
        # The curated file already carries `budget: None` on a post, so the
        # test is what this module CHANGES, not what the node happens to hold.
        before = index_tree(copy.deepcopy(self.base))[0]
        _graph, node_map, _ = self.applied()
        for node_id in self.records:
            node, was = node_map[node_id], before[node_id]
            for field in ("resolved_total_amount", "rollup_total_amount", "cost_status",
                          "budget", "costVerificationStatus", "cost_basis"):
                self.assertEqual(node.get(field), was.get(field),
                                 f"{node_id}: a signature changed {field}")

    def test_an_existing_method_is_kept_and_this_goes_beside_it(self):
        node_id = next(iter(self.records))
        graph = copy.deepcopy(self.base)
        node_map, _ = index_tree(graph)
        node_map[node_id]["verificationMethod"] = "name_labelled_on_its_organisations_official_page"
        apply_signature_evidence(graph, self.records)
        node_map, _ = index_tree(graph)
        self.assertEqual(node_map[node_id]["verificationMethod"],
                         "name_labelled_on_its_organisations_official_page")
        self.assertIsInstance(node_map[node_id]["federalRegisterSignature"], dict)

    def test_a_renamed_node_loses_the_claim(self):
        node_id = next(iter(self.records))
        graph = copy.deepcopy(self.base)
        node_map, _ = index_tree(graph)
        node_map[node_id]["name"] = "Grand Vizier of Somewhere Else"
        stats = apply_signature_evidence(graph, self.records)
        node_map, _ = index_tree(graph)
        self.assertNotIn("federalRegisterSignature", node_map[node_id])
        self.assertEqual(stats["stale_name"], 1)

    def test_a_record_for_a_node_that_is_no_longer_a_post_is_refused(self):
        node_id = next(iter(self.records))
        graph = copy.deepcopy(self.base)
        node_map, _ = index_tree(graph)
        node_map[node_id]["type"] = "Office"
        stats = apply_signature_evidence(graph, self.records)
        node_map, _ = index_tree(graph)
        self.assertNotIn("federalRegisterSignature", node_map[node_id])
        self.assertEqual(stats["not_a_post"], 1)

    def test_a_confirmation_here_alone_is_not_even_partial(self):
        # `classify_source_url` files a federalregister.gov URL as
        # `federal_register` and NOT as `official_site` -- a notice documents
        # an office, it is not the office's own site -- so this scores the
        # bare 0.4 and grades `unverified` with a source recorded. That is
        # the existing arithmetic and this module does not touch it.
        _graph, node_map, _ = self.applied()
        for node_id in self.records:
            node = node_map[node_id]
            if len(node.get("sourceUrls") or []) == 1:
                self.assertNotIn("official_site", node.get("sourceTypes") or [],
                                 f"{node_id}: the Register is not the unit's own site")
                self.assertEqual(node.get("verificationStatus"), "unverified", node_id)


class WithdrawalTests(unittest.TestCase):
    """A record dropped since the last build stops being published."""

    def test_the_field_is_evidence_owned_and_kept_for_the_viewer(self):
        self.assertIn("federalRegisterSignature", EVIDENCE_OWNED_FIELDS)
        self.assertIn("federalRegisterSignature", MINIMAL_GRAPH_FIELDS)

    def test_the_evidence_sweep_removes_the_block(self):
        from data_pipeline.verification.evidence import apply_evidence_to_tree

        require_fixtures()
        documents, _ = read_documents()
        base = load_base_graph(DEFAULT_BASE_GRAPH)
        records, _ = build_records(documents, base)
        if not records:
            self.skipTest("no signature reaches a node on the committed fixtures")
        graph = copy.deepcopy(base)
        apply_signature_evidence(graph, records)
        apply_evidence_to_tree(graph, {})
        node_map, _ = index_tree(graph)
        for node_id in records:
            self.assertNotIn("federalRegisterSignature", node_map[node_id])

    def test_the_field_is_named_in_the_viewer(self):
        for name in ("js/ui.js", "js/atlas.js"):
            text = (PROJECT_ROOT / name).read_text(encoding="utf-8")
            self.assertIn("federalRegisterSignature", text, f"{name} never reads the block")
            self.assertIn(METHOD, text, f"{name} has no sentence for this method")


class GateMirrorTests(unittest.TestCase):
    """The gate's own reader is independent, and its mirrors do not drift."""

    def test_the_gate_imports_nothing_from_the_pipeline(self):
        import ast

        source = (PROJECT_ROOT / "scripts" / "validate_published_graph.py").read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertFalse(alias.name.startswith("data_pipeline"), alias.name)
            elif isinstance(node, ast.ImportFrom):
                self.assertFalse(str(node.module or "").startswith("data_pipeline"), node.module)

    def test_the_agency_key_mirror_agrees_on_every_name_the_listings_print(self):
        require_fixtures()
        from scripts.validate_published_graph import fr_agency_keys

        listed, _ = read_index()
        names = {name for row in listed.values() for name in row["agenciesListed"]}
        self.assertTrue(names)
        for name in names:
            self.assertEqual(fr_agency_keys(name), federal_register_name_keys(name), name)

    def test_the_gate_re_derives_the_same_titles(self):
        require_fixtures()
        from scripts.validate_published_graph import fr_signature_documents

        documents, _ = read_documents()
        gate = fr_signature_documents()
        self.assertEqual(len(gate), len(documents))
        for document in documents:
            self.assertEqual(gate[document["documentNumber"]]["title"], document["listedTitle"],
                             document["documentNumber"])

    def test_the_gates_constants_mirror_the_modules(self):
        from scripts.validate_published_graph import (
            FR_DOCUMENT_URL,
            FR_MIN_POST_TOKENS,
            FR_SIGNATURE_METHOD,
            FR_SIGNATURE_SOURCE,
        )
        from data_pipeline.verification.federal_register_signatures import SOURCE

        self.assertEqual(FR_SIGNATURE_METHOD, METHOD)
        self.assertEqual(FR_SIGNATURE_SOURCE, SOURCE)
        self.assertEqual(FR_MIN_POST_TOKENS, MIN_POST_TOKENS)
        self.assertEqual(FR_DOCUMENT_URL, DOCUMENT_URL)


class GateCorruptionTests(unittest.TestCase):
    """Every dimension of the claim, corrupted in turn.

    The fixtures here are WRITTEN, not the committed ones, and the gate is
    pointed at them for the length of the test. That is deliberate: the
    Federal Register publishes whatever it publishes, so a corpus fetched
    today may trip a given rule once, or never, and a gate rule that is only
    exercised when the host happens to cooperate is not pinned at all. The
    record is still applied to a copy of the PUBLISHED graph, on a real post
    under its real parent, so every other check in the gate runs beside this
    one exactly as it will on the next build.
    """

    CHECK = ("a Federal Register signature is a title that document prints, "
             "under an agency list that resolves to the node's own parent")
    NUMBER = "2026-90001"
    RAW_URL = ("https://www.federalregister.gov/documents/full_text/text/2026/01/02/"
               + NUMBER + ".txt")

    @classmethod
    def setUpClass(cls):
        import tempfile

        if not PUBLISHED.exists():
            raise unittest.SkipTest("output/graph.json is not built")
        graph = json.loads(PUBLISHED.read_text(encoding="utf-8"))
        chosen = cls.choose(graph)
        if chosen is None:
            raise unittest.SkipTest("the published graph carries no post this fixture could name")
        post, parent = chosen
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        (root / "index").mkdir()
        (root / "documents").mkdir()
        body = (
            "A notice about a matter.\n\n"
            "Jane Q. Public,\n"
            + str(post["name"]) + ".\n"
            "[FR Doc. " + cls.NUMBER + " Filed 1-1-26; 8:45 am]\n"
            "BILLING CODE 0000-00-P\n"
        ).encode("utf-8")
        BuiltFixtureTests.write(root / "documents" / (cls.NUMBER + ".txt"), body, "text/plain", cls.RAW_URL)
        listing = json.dumps({"results": [{
            "document_number": cls.NUMBER,
            "raw_text_url": cls.RAW_URL,
            "html_url": DOCUMENT_URL.format(cls.NUMBER),
            "agencies": [{"name": str(parent["name"])}],
            "signing_date": None,
            "publication_date": "2026-01-02",
            "title": "A notice about a matter",
            "type": "Notice",
        }]}).encode("utf-8")
        BuiltFixtureTests.write(root / "index" / "written.json", listing, "application/json",
                                "https://www.federalregister.gov/api/v1/documents.json")
        cls.fixture_root = root

        documents, _ = read_documents(root / "index", root / "documents")
        records, _ = build_records(documents, graph)
        assert records, "the written fixture reached no node of the published graph"
        applied = apply_signature_evidence(graph, records)
        assert applied["listed"] == 1, applied
        cls.graph = graph

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    @staticmethod
    def choose(graph):
        """A real post whose name and whose parent's name are unambiguous.

        The parent's name must reach exactly one organisation in the tree and
        the post's name exactly one direct child of it, because those are the
        two conditions the join requires; anything else would be testing the
        fixture rather than the gate.
        """
        pairs, stack = [], [(graph, None)]
        while stack:
            node, parent = stack.pop()
            pairs.append((node, parent))
            for child in node.get("children") or []:
                if isinstance(child, dict):
                    stack.append((child, node))
        orgs = {}
        for node, _ in pairs:
            if "position" not in str(node.get("type") or "").casefold() and not node.get("synthetic"):
                orgs.setdefault(canonical_name_key(node.get("name")), []).append(node)
        for node, parent in sorted(pairs, key=lambda p: str(p[0].get("id") or "")):
            if parent is None or "position" not in str(node.get("type") or "").casefold():
                continue
            key = canonical_name_key(node.get("name"))
            if len(key.split()) < MIN_POST_TOKENS:
                continue
            parent_key = canonical_name_key(parent.get("name"))
            if len(orgs.get(parent_key) or []) != 1:
                continue
            if federal_register_name_keys(parent.get("name")) & (set(orgs) - {parent_key}):
                continue
            siblings = [c for c in parent.get("children") or []
                        if isinstance(c, dict) and canonical_name_key(c.get("name")) == key]
            if len(siblings) != 1:
                continue
            if node.get("federalRegisterSignature") or node.get("placementMethod"):
                continue
            return node, parent
        return None

    def run_gate(self, graph):
        import tempfile
        from scripts import validate_published_graph as gate_module

        with mock.patch.object(gate_module, "FR_SIGNATURE_DIR", self.fixture_root):
            gate_module._FR_SIGNATURE_CACHE.clear()
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / "graph.json"
                    path.write_text(json.dumps(graph), encoding="utf-8")
                    buffer = io.StringIO()
                    with redirect_stdout(buffer):
                        code = gate_module.main(["gate", str(path)])
                    return code, buffer.getvalue()
            finally:
                gate_module._FR_SIGNATURE_CACHE.clear()

    def corrupt(self, mutate):
        graph = copy.deepcopy(self.graph)
        stack = [graph]
        while stack:
            node = stack.pop()
            if isinstance(node.get("federalRegisterSignature"), dict):
                mutate(node)
                return graph
            stack.extend([c for c in (node.get("children") or []) if isinstance(c, dict)])
        self.fail("no node carries a Federal Register signature")

    def assert_refused(self, mutate, because):
        code, output = self.run_gate(self.corrupt(mutate))
        self.assertEqual(code, 1, f"the gate accepted a graph where {because}")
        self.assertIn("FAIL  " + self.CHECK, output)

    def test_the_untouched_graph_passes(self):
        code, output = self.run_gate(copy.deepcopy(self.graph))
        self.assertIn("ok    " + self.CHECK, output)
        self.assertEqual(code, 0, output[-3000:])

    def test_a_title_the_document_does_not_print(self):
        self.assert_refused(
            lambda n: n["federalRegisterSignature"].update(listedTitle="Supreme Widget Officer"),
            "the quoted title is not in the document")

    def test_a_document_that_is_not_committed(self):
        self.assert_refused(
            lambda n: n["federalRegisterSignature"].update(documentNumber="2026-00000"),
            "the document is not in the committed fixtures")

    def test_a_digest_the_document_does_not_have(self):
        self.assert_refused(
            lambda n: n["federalRegisterSignature"].update(documentSha256="0" * 64),
            "the digest is not the committed document's")

    def test_an_agency_list_the_document_does_not_carry(self):
        self.assert_refused(
            lambda n: n["federalRegisterSignature"].update(agenciesListed=["Energy Department"]),
            "the agency list is not the one the Register prints")

    def test_a_block_on_a_node_that_is_not_a_post(self):
        self.assert_refused(lambda n: n.update(type="Office"),
                            "the node is not a post")

    def test_a_renamed_node(self):
        self.assert_refused(lambda n: n.update(name="Grand Vizier of Somewhere Else"),
                            "the node no longer carries the quoted title")

    def test_a_publication_date_that_has_not_happened(self):
        self.assert_refused(
            lambda n: n["federalRegisterSignature"].update(publicationDate="2099-01-01"),
            "the document is dated in the future")

    def test_a_signing_date_that_has_not_happened(self):
        self.assert_refused(
            lambda n: n["federalRegisterSignature"].update(signingDate="2099-01-01"),
            "the signature is dated in the future")

    def test_a_placement_claimed_from_one_document(self):
        def mutate(node):
            node["placementMethod"] = METHOD
            node["placementVerified"] = True
            node["placementUrl"] = node["federalRegisterSignature"]["url"]
            node["placementVerifiedAt"] = node["federalRegisterSignature"]["publicationDate"]
        self.assert_refused(mutate, "a placement was claimed from a single document")

    def test_a_url_that_did_not_serve_the_document(self):
        self.assert_refused(
            lambda n: n["federalRegisterSignature"].update(
                url="https://www.federalregister.gov/documents/full_text/text/2026/01/01/2026-00001.txt"),
            "the cited URL is not the one that served the bytes")

    def test_a_document_url_that_is_not_the_registers_own(self):
        self.assert_refused(
            lambda n: n["federalRegisterSignature"].update(documentUrl="https://example.gov/doc"),
            "the reader-facing address is invented")

    def test_an_inflated_occurrence_count(self):
        self.assert_refused(lambda n: n["federalRegisterSignature"].update(occurrences=99),
                            "the block claims more documents than the fixtures carry")

    def test_an_occurrence_count_of_zero(self):
        self.assert_refused(lambda n: n["federalRegisterSignature"].update(occurrences=0),
                            "the block claims no document carries the title it quotes")

    def test_the_source_type_dropped(self):
        def mutate(node):
            node["sourceTypes"] = [t for t in node.get("sourceTypes") or [] if t != SOURCE_TYPE]
        self.assert_refused(mutate, "the document is cited without saying so in the source types")

    def test_the_method_without_the_block(self):
        def mutate(node):
            node.pop("federalRegisterSignature")
            node["verificationMethod"] = METHOD
        self.assert_refused(mutate, "the method is claimed with no block behind it")

    def test_the_block_without_its_url_on_the_node(self):
        def mutate(node):
            url = node["federalRegisterSignature"]["url"]
            node["sourceUrls"] = [u for u in node.get("sourceUrls") or [] if u != url]
        self.assert_refused(mutate, "the document is cited without its URL")

    def test_a_tampered_document_is_refused(self):
        path = self.fixture_root / "documents" / (self.NUMBER + ".txt")
        original = path.read_bytes()
        self.addCleanup(path.write_bytes, original)
        path.write_bytes(original.replace(b"Jane Q. Public,", b"Jane Q. Public, Esq.,"))
        code, output = self.run_gate(copy.deepcopy(self.graph))
        self.assertEqual(code, 1, "the gate read a document whose bytes are not the ones fetched")
        self.assertIn("FAIL  " + self.CHECK, output)

    def test_a_record_moved_to_another_node_of_the_same_name(self):
        # `General Counsel` names 84 nodes here, so a drifted record keeps a
        # real title, a real document and a real URL. Only the parent -- read
        # off the tree, never off `parentId` -- tells them apart.
        graph = copy.deepcopy(self.graph)
        carrier, by_name = None, {}
        stack = [(graph, None)]
        while stack:
            node, parent = stack.pop()
            by_name.setdefault(canonical_name_key(node.get("name")), []).append((node, parent))
            if carrier is None and isinstance(node.get("federalRegisterSignature"), dict):
                carrier = (node, parent)
            for child in node.get("children") or []:
                if isinstance(child, dict):
                    stack.append((child, node))
        self.assertIsNotNone(carrier)
        source_node, source_parent = carrier
        twins = [(n, p) for n, p in by_name[canonical_name_key(source_node["name"])]
                 if n is not source_node and p is not source_parent and p is not None]
        if not twins:
            self.skipTest("no second node of this name to move the record to")
        target, _ = twins[0]
        target["federalRegisterSignature"] = copy.deepcopy(source_node["federalRegisterSignature"])
        target["sourceUrls"] = list(target.get("sourceUrls") or []) + [target["federalRegisterSignature"]["url"]]
        target["sourceTypes"] = list(target.get("sourceTypes") or []) + [SOURCE_TYPE]
        source_node.pop("federalRegisterSignature")
        code, output = self.run_gate(graph)
        self.assertEqual(code, 1, "the gate accepted a record moved to another node of the same name")
        self.assertIn("FAIL  " + self.CHECK, output)


class LiveFixtureGateTests(unittest.TestCase):
    """And the committed fixtures, whatever they yielded, against the gate."""

    @classmethod
    def setUpClass(cls):
        require_fixtures()
        if not PUBLISHED.exists():
            raise unittest.SkipTest("output/graph.json is not built")
        documents, _ = read_documents()
        records, _ = build_records(documents, load_base_graph(DEFAULT_BASE_GRAPH))
        if not records:
            raise unittest.SkipTest("no signature reaches a node on the committed fixtures")
        graph = json.loads(PUBLISHED.read_text(encoding="utf-8"))
        applied = apply_signature_evidence(graph, records)
        if not applied["listed"]:
            raise unittest.SkipTest("no signature reaches a node of the published graph")
        cls.graph = graph
        cls.applied = applied

    def test_the_committed_records_pass_the_gate(self):
        import tempfile
        from scripts.validate_published_graph import main as gate_main

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "graph.json"
            path.write_text(json.dumps(self.graph), encoding="utf-8")
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = gate_main(["gate", str(path)])
        self.assertIn("ok    " + GateCorruptionTests.CHECK, buffer.getvalue())
        self.assertEqual(code, 0, buffer.getvalue()[-3000:])


class CoverageLineTests(unittest.TestCase):
    """The number is reported on its own line, as a small number."""

    def test_the_gate_prints_a_signature_coverage_line(self):
        source = (PROJECT_ROOT / "scripts" / "validate_published_graph.py").read_text(encoding="utf-8")
        self.assertIn("FR signatures", source)
        self.assertIn("the signer's name is never read and no placement is claimed from it", source)


class DryRunTests(unittest.TestCase):
    def test_the_derive_script_writes_nothing_on_a_dry_run(self):
        require_fixtures()
        from scripts.derive_fr_signature_evidence import main as derive_main
        from data_pipeline.verification.federal_register_signatures import DEFAULT_EVIDENCE_PATH

        before = DEFAULT_EVIDENCE_PATH.read_bytes() if DEFAULT_EVIDENCE_PATH.exists() else None
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = derive_main(["derive", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("--dry-run: nothing written", buffer.getvalue())
        self.assertIn("the signer's name is never read", buffer.getvalue())
        after = DEFAULT_EVIDENCE_PATH.read_bytes() if DEFAULT_EVIDENCE_PATH.exists() else None
        self.assertEqual(before, after)

    def test_the_dry_run_prints_no_signer_name(self):
        require_fixtures()
        from scripts.derive_fr_signature_evidence import main as derive_main

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            derive_main(["derive", "--dry-run"])
        printed = buffer.getvalue()
        for name in TheSignersNameIsNeverReadTests.names_printed(self):
            self.assertNotIn(name, printed, f"{name!r} is a signer's name and the dry run printed it")


if __name__ == "__main__":
    unittest.main()
