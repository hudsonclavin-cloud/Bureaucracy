"""Alternative names a node answers to: the table, the scope, the grading,
and the wall between this and every join that lands a figure.

The feature is a way to publish MORE evidence, which is the direction in
which this repository has published things that were false before, so every
test here is written in both directions: a good row applies and buys exactly
what it should, and each of the ways it could over-claim is refused by name.

Four properties carry the whole design, and each has its own class:

  - the table refuses what it cannot adjudicate (`TableTests`), including the
    one-token floor that is the reason `The President` is NOT a row;
  - an alias is consulted by name and existence evidence only, and the
    separation from money and headcount joins is STRUCTURAL rather than a
    matter of discipline (`IsolationTests`);
  - a confirmation reached this way reads as the weaker claim it is, and a
    node resting on nothing else is held at `partial` (`GradingTests`);
  - the gate refuses a record moved between nodes, a node renamed out from
    under its row, an unreviewed alternative, a missing basis, a `verified`
    badge on alias evidence alone, and an alias on a money block
    (`GateCorruptionTests`).
"""

from __future__ import annotations

import ast
import copy
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
import sys  # noqa: E402

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.exporter.build_graph import (  # noqa: E402
    DEFAULT_BASE_GRAPH,
    canonical_name_key,
    index_tree,
    load_base_graph,
)
from data_pipeline.verification import aliases as al  # noqa: E402
from data_pipeline.verification.evidence import (  # noqa: E402
    MATCH_RULE_ALIAS,
    PageText,
    REGION_CONTENT,
    REGION_NAVIGATION,
    evidence_names_this_node,
    find_label_region_rule,
    verify_node,
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


def tiny_tree():
    """Two siblings under one parent, which is all the sibling-collision rule
    needs, plus a post beneath one of them for the organisation scope."""
    return {
        "id": "root", "name": "Root", "type": "Branch",
        "children": [
            {"id": "alpha", "name": "Alpha Administration (AA)", "type": "Agency",
             "children": [{"id": "alpha-gc", "name": "Deputy Administrator", "type": "Position", "children": []}]},
            {"id": "beta", "name": "Beta Bureau", "type": "Bureau", "children": []},
        ],
    }


def table_for(rows, root=None):
    node_map, parent_map = index_tree(root or tiny_tree())
    return al.build_alias_table(rows, node_map, parent_map)


GOOD_ROW = {
    "id": "alpha",
    "name": "Alpha Administration (AA)",
    "alias": "Alpha Administration Service",
    "basis": "A document this test pretends to have read.",
}


class TableTests(unittest.TestCase):
    """The reviewed table, adjudicated against the tree on every run."""

    def test_a_good_row_is_accepted_and_indexed_both_ways(self):
        table = table_for([GOOD_ROW])
        self.assertEqual(len(table), 1)
        row = table.by_alias("alpha", "Alpha Administration Service")
        self.assertIsNotNone(row)
        self.assertEqual(row.basis, GOOD_ROW["basis"])
        self.assertEqual(table.nodes_for_key(canonical_name_key(GOOD_ROW["alias"])), ("alpha",))
        self.assertEqual(table.extra_keys("alpha", "Alpha Administration (AA)"),
                         (canonical_name_key(GOOD_ROW["alias"]),))
        self.assertEqual(table.refusals, [])

    def refusal(self, row, root=None):
        table = table_for([row], root)
        self.assertEqual(len(table), 0, "the row was accepted")
        self.assertEqual(len(table.refusals), 1)
        return table.refusals[0]["reason"]

    def test_a_row_for_a_node_that_is_not_there(self):
        self.assertEqual(self.refusal({**GOOD_ROW, "id": "nowhere"}), "no_such_node")

    def test_a_row_written_against_a_name_the_node_no_longer_carries(self):
        self.assertEqual(self.refusal({**GOOD_ROW, "name": "Alpha Administration"}),
                         "curated_name_has_changed")

    def test_a_row_with_no_basis_is_an_assertion_not_an_identification(self):
        self.assertEqual(self.refusal({**GOOD_ROW, "basis": "  "}), "basis_missing")

    def test_an_alternative_that_changes_no_outcome(self):
        # canonical_name_key drops the parenthetical and folds "&"/"and", so
        # this reduces to exactly what the node's own name does.
        self.assertEqual(self.refusal({**GOOD_ROW, "alias": "Alpha Administration"}), "alias_is_a_no_op")

    def test_a_one_token_alternative_is_refused_which_is_why_the_president_has_no_row(self):
        # "The President" reduces to the single token "president" -- a label
        # on thousands of .gov pages, and the alias IS consulted by the page
        # test. The floor is the whole reason that row is not in the table.
        self.assertEqual(self.refusal({**GOOD_ROW, "alias": "The President"}), "alias_too_short")
        self.assertEqual(canonical_name_key("The President"), "president")
        self.assertEqual(len(canonical_name_key("The President").split()), 1)

    def test_a_generic_alternative_is_refused(self):
        self.assertEqual(self.refusal({**GOOD_ROW, "alias": "Inspector General"}), "alias_is_generic")

    def test_an_alternative_that_collides_with_a_sibling(self):
        self.assertEqual(self.refusal({**GOOD_ROW, "alias": "Beta Bureau"}),
                         "alias_collides_with_a_sibling")

    def test_an_alternative_that_collides_with_a_siblings_accepted_alias(self):
        first = {**GOOD_ROW, "id": "beta", "name": "Beta Bureau", "alias": "Beta Administration Service"}
        table = table_for([first, {**GOOD_ROW, "alias": "Beta Administration Service"}])
        self.assertEqual(len(table), 1)
        self.assertEqual([r["reason"] for r in table.refusals], ["alias_collides_with_a_sibling"])

    def test_the_same_alternative_twice_for_one_node(self):
        table = table_for([GOOD_ROW, dict(GOOD_ROW)])
        self.assertEqual(len(table), 1)
        self.assertEqual([r["reason"] for r in table.refusals], ["duplicate_row"])


class CommittedTableTests(unittest.TestCase):
    """The table this repository ships, against the curated file it names."""

    @classmethod
    def setUpClass(cls):
        cls.rows = al.load_rows()
        cls.root = load_base_graph(DEFAULT_BASE_GRAPH)
        cls.table = al.load_alias_table(cls.root)

    def test_every_committed_row_is_accepted_now(self):
        self.assertEqual(self.table.refusals, [], "a committed row no longer adjudicates")
        self.assertEqual(len(self.table), len(self.rows))
        self.assertGreaterEqual(len(self.rows), 8)

    def test_every_row_states_a_basis_and_the_node_s_current_name(self):
        node_map, _ = index_tree(self.root)
        for row in self.rows:
            with self.subTest(node=row.get("id")):
                node = node_map.get(str(row.get("id")))
                self.assertIsNotNone(node, f"{row.get('id')} is not in the curated file")
                self.assertEqual(str(node.get("name")), str(row.get("name")))
                self.assertGreater(len(str(row.get("basis") or "").strip()), 40,
                                   "a basis is where the identification is argued, not a label")
                self.assertTrue(str(row.get("addedOn") or ""))

    def test_the_army_case_is_deliberately_absent_and_the_file_says_why(self):
        # CLAUDE.md records twice that the civilian department and the
        # uniformed service are different units with different populations.
        for row in self.rows:
            self.assertNotIn("department of the army", canonical_name_key(row.get("alias")))
            self.assertNotIn("department of the navy", canonical_name_key(row.get("alias")))
            self.assertNotIn("department of the air force", canonical_name_key(row.get("alias")))
        payload = json.loads(al.DEFAULT_ALIAS_TABLE.read_text(encoding="utf-8"))
        comment = " ".join(payload.get("_comment") or [])
        self.assertIn("DELIBERATELY ABSENT", comment)
        self.assertIn("uniformed service", comment)

    def test_the_gate_mirrors_the_official_site_rule_the_cap_turns_on(self):
        """The cap's whole effect is the difference between a `.gov` URL and
        an official SITE, so the gate's stdlib mirror of that rule must agree
        with the pipeline's on every host either of them sees."""
        from data_pipeline.processors.normalize_nodes import (
            GOVERNMENT_DATASET_HOSTS,
            classify_source_url,
        )
        from scripts.validate_published_graph import (
            GOVERNMENT_DATASET_HOSTS as MIRRORED,
            is_official_site,
        )

        self.assertEqual(MIRRORED, GOVERNMENT_DATASET_HOSTS)
        hosts = [
            "https://fiscaldata.treasury.gov/x", "https://api.fiscaldata.treasury.gov/x",
            "https://api.usaspending.gov/x", "https://www.federalregister.gov/agencies/x",
            "https://www.govinfo.gov/app/details/x", "https://www.darpa.mil/",
            "https://escs.opm.gov/x", "https://www.senate.gov/x", "https://example.com/x",
            "https://www.wikidata.org/x",
        ]
        for url in hosts:
            with self.subTest(url=url):
                self.assertEqual(is_official_site(url), classify_source_url(url) == "official_site")

    def test_the_gate_mirrors_the_table_by_node_id(self):
        from scripts.validate_published_graph import NODE_ALIASES

        expected = {}
        for row in self.rows:
            node_id = str(row["id"])
            name, names = expected.get(node_id, (str(row["name"]), ()))
            expected[node_id] = (name, names + (str(row["alias"]),))
        self.assertEqual(NODE_ALIASES, expected,
                         "the gate's mirror has drifted from data/curation/node_aliases.json")


class IsolationTests(unittest.TestCase):
    """The wall between an existence alias and anything that lands a figure.

    Structural rather than a matter of discipline: the money and headcount
    modules do not import this one, and nothing may add them to the list
    without this test saying so.
    """

    #: Everything that may consult the table. Name and existence evidence,
    #: the scripts that derive it, the curation writers that share its
    #: vocabulary, and the exporter's final grading pass.
    ALLOWED = {
        "data_pipeline/verification/aliases.py",
        "data_pipeline/verification/evidence.py",
        "data_pipeline/verification/govman.py",
        "data_pipeline/verification/congress.py",
        "data_pipeline/verification/plum_current.py",
        "data_pipeline/exporter/build_graph.py",
        "scripts/verify_base_graph.py",
        "scripts/derive_govman_evidence.py",
        "scripts/derive_directory_evidence.py",
        "scripts/derive_plum_current_evidence.py",
        "scripts/rename_units_to_official_wording.py",
        "tests/test_node_aliases.py",
        "tests/test_govman.py",
    }
    #: Every join in this project that publishes a NUMBER. Each already has
    #: its own reviewed table where a figure is at stake.
    FORBIDDEN = (
        "data_pipeline/verification/headcounts.py",
        "data_pipeline/verification/usaspending.py",
        "data_pipeline/verification/net_cost.py",
        "data_pipeline/verification/omb_budget.py",
        "data_pipeline/verification/financial_evidence.py",
        "data_pipeline/verification/pay_tables.py",
        "data_pipeline/verification/gs_pay.py",
        "data_pipeline/verification/statutory_schedule.py",
        "data_pipeline/verification/judicial_pay.py",
        "data_pipeline/verification/congressional_pay.py",
        "data_pipeline/verification/whitehouse_pay.py",
        "data_pipeline/crawler/treasury_outlays.py",
    )

    def importers(self):
        """Every file in the repository that imports the alias module."""
        out = set()
        for path in sorted(PROJECT_ROOT.rglob("*.py")):
            rel = path.relative_to(PROJECT_ROOT).as_posix()
            if rel.startswith((".git/", "node_modules/")):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "verification.aliases" in text or "verification import aliases" in text:
                out.add(rel)
        return out

    def test_only_name_and_existence_evidence_may_consult_the_table(self):
        self.assertEqual(self.importers() - self.ALLOWED, set(),
                         "a module outside the whitelist imports the alias table")

    def test_no_money_or_headcount_module_imports_it(self):
        importers = self.importers()
        for module in self.FORBIDDEN:
            with self.subTest(module=module):
                self.assertTrue((PROJECT_ROOT / module).exists())
                self.assertNotIn(module, importers)

    def test_the_treasury_row_matching_in_the_exporter_takes_no_alias(self):
        """`build_graph` imports the module for one thing only -- the final
        grading cap -- and never hands it to the Treasury row matcher."""
        source = (PROJECT_ROOT / "data_pipeline" / "exporter" / "build_graph.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        uses = [
            node.func.id for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        ]
        self.assertIn("cap_alias_only_confirmations", uses)
        self.assertNotIn("load_alias_table", source.split("cap_alias_only_confirmations")[0])

    def test_the_money_and_headcount_matchers_have_nowhere_to_put_one(self):
        """The wall is not only "they do not import it": none of these
        matchers takes a parameter an alias table could be handed to, so
        wiring one in would be an edit this test sees."""
        from data_pipeline.verification import headcounts, net_cost, omb_budget, usaspending

        for func in (headcounts.match_fedscope, net_cost.build_records,
                     omb_budget.build_records, usaspending.build_records):
            with self.subTest(func=func.__qualname__):
                names = func.__code__.co_varnames[: func.__code__.co_argcount + func.__code__.co_kwonlyargcount]
                self.assertFalse([n for n in names if "alias" in n.casefold()])


class PageMatchingTests(unittest.TestCase):
    """The page-label test, with and without the table."""

    def page(self, *fragments, region=REGION_CONTENT):
        return PageText(fragments=list(fragments), regions=[region] * len(fragments))

    def test_an_alias_confirms_where_the_name_does_not(self):
        table = table_for([GOOD_ROW])
        page = self.page("Alpha Administration Service")
        self.assertIsNone(find_label_region_rule("Alpha Administration (AA)", page))
        found = find_label_region_rule("Alpha Administration (AA)", page,
                                       aliases=table.for_node("alpha"))
        self.assertEqual(found, ("Alpha Administration Service", REGION_CONTENT, MATCH_RULE_ALIAS))

    def test_the_plain_match_always_wins_and_is_never_recorded_as_an_alias(self):
        table = table_for([GOOD_ROW])
        page = self.page("Alpha Administration Service", "Alpha Administration")
        found = find_label_region_rule("Alpha Administration (AA)", page,
                                       aliases=table.for_node("alpha"))
        self.assertEqual(found[2], None)
        self.assertEqual(found[0], "Alpha Administration")

    def test_no_table_means_exactly_the_behaviour_that_was_there_before(self):
        page = self.page("Alpha Administration Service")
        self.assertIsNone(find_label_region_rule("Alpha Administration (AA)", page))
        self.assertIsNone(find_label_region_rule("Alpha Administration (AA)", page, aliases=()))

    def test_a_post_still_cannot_be_confirmed_from_site_navigation(self):
        row = {"id": "alpha-gc", "name": "Deputy Administrator", "alias": "Deputy Chief Administrator",
               "basis": "A document this test pretends to have read."}
        table = table_for([row])
        page = self.page("Deputy Chief Administrator", region=REGION_NAVIGATION)
        self.assertIsNone(find_label_region_rule("Deputy Administrator", page, is_post=True,
                                                 regions_allowed=(REGION_CONTENT,),
                                                 aliases=table.for_node("alpha-gc")))

    def test_verify_node_records_which_alternative_and_on_what_basis(self):
        table = table_for([GOOD_ROW])
        node = {"id": "alpha", "name": "Alpha Administration (AA)", "type": "Agency"}
        record = verify_node(node, ["https://alpha.gov/about"],
                             fetch=lambda url: "<h1>Alpha Administration Service</h1>" + "x " * 400,
                             now="2026-09-21T00:00:00Z", is_own_page=True,
                             aliases=table.for_node("alpha"))
        self.assertEqual(record["status"], "confirmed")
        source = record["sources"][0]
        self.assertEqual(source["matchRule"], MATCH_RULE_ALIAS)
        self.assertEqual(source["matchedAlias"], GOOD_ROW["alias"])
        self.assertEqual(source["aliasBasis"], GOOD_ROW["basis"])

    def test_the_rename_guard_accepts_an_alias_only_while_the_row_stands(self):
        table = table_for([GOOD_ROW])
        rows = table.for_node("alpha")
        self.assertTrue(evidence_names_this_node("Alpha Administration (AA)",
                                                 "Alpha Administration Service", None, rows))
        self.assertFalse(evidence_names_this_node("Alpha Administration (AA)",
                                                  "Alpha Administration Service", None, ()))


class GradingTests(unittest.TestCase):
    """The cap: alias-derived evidence alone never reads `verified`."""

    def node(self, urls):
        return {"id": "alpha", "name": "Alpha", "sourceUrls": list(urls),
                "confidenceScore": 0.8, "verificationStatus": "verified",
                al.ALIAS_FIELD: {"alias": "A", "basis": "b", "matchedText": "A",
                                 "scope": al.ALIAS_SCOPE_NODE, "source": "s",
                                 "urls": ["https://a.gov/1", "https://b.gov/2"], "matches": []}}

    def test_a_node_resting_only_on_alias_matches_is_held_at_partial(self):
        node = self.node(["https://a.gov/1", "https://b.gov/2"])
        root = {"id": "root", "name": "Root", "children": [node]}
        stats = al.cap_alias_only_confirmations(root)
        self.assertEqual(stats["capped_to_partial"], 1)
        self.assertEqual(node["verificationStatus"], "partial")
        self.assertEqual(node["confidenceScore"], al.ALIAS_CONFIDENCE_CEILING)
        self.assertEqual(node[al.ALIAS_FIELD]["gradedAtMost"], "partial")

    def test_a_node_something_else_also_names_is_not_held_back(self):
        node = self.node(["https://a.gov/1", "https://b.gov/2", "https://c.gov/3"])
        root = {"id": "root", "name": "Root", "children": [node]}
        stats = al.cap_alias_only_confirmations(root)
        self.assertEqual(stats["capped_to_partial"], 0)
        self.assertEqual(stats["not_capped_other_evidence"], 1)
        self.assertEqual(node["verificationStatus"], "verified")
        self.assertNotIn("gradedAtMost", node[al.ALIAS_FIELD])

    def test_the_cap_is_withdrawn_when_other_evidence_arrives(self):
        node = self.node(["https://a.gov/1", "https://b.gov/2"])
        node[al.ALIAS_FIELD]["gradedAtMost"] = "partial"
        node["sourceUrls"].append("https://c.gov/3")
        root = {"id": "root", "name": "Root", "children": [node]}
        al.cap_alias_only_confirmations(root)
        self.assertNotIn("gradedAtMost", node[al.ALIAS_FIELD])


class PublishedGraphTests(unittest.TestCase):
    """What the alias table actually buys on the graph this repo publishes."""

    @classmethod
    def setUpClass(cls):
        cls.pairs = published_nodes()
        if not cls.pairs:
            raise unittest.SkipTest("output/graph.json is not built")
        if not any(isinstance(n.get(al.ALIAS_FIELD), dict) for n, _ in cls.pairs):
            # The evidence files and the graph are rebuilt by different
            # steps, so a checkout can sit for one commit with the table
            # applied and the graph not yet regenerated. Nothing here can be
            # measured against a graph that predates the feature.
            raise unittest.SkipTest("output/graph.json predates the alias table; regenerate it")
        cls.by_id = {n["id"]: n for n, _ in cls.pairs if n.get("id")}

    def carrying(self):
        return [n for n, _ in self.pairs if isinstance(n.get(al.ALIAS_FIELD), dict)]

    def test_some_nodes_carry_one_and_every_one_names_a_committed_row(self):
        from scripts.validate_published_graph import NODE_ALIASES

        carrying = self.carrying()
        self.assertGreaterEqual(len(carrying), 8)
        for node in carrying:
            block = node[al.ALIAS_FIELD]
            for entry in block["matches"]:
                owner = entry.get("owner") or node["id"]
                self.assertIn(owner, NODE_ALIASES)
                self.assertIn(entry["alias"], NODE_ALIASES[owner][1])
                self.assertTrue(entry["basis"].strip())

    def test_none_of_them_reads_verified_on_alias_evidence_alone(self):
        for node in self.carrying():
            if node[al.ALIAS_FIELD].get("gradedAtMost") == "partial":
                self.assertNotEqual(node.get("verificationStatus"), "verified", node["id"])

    def test_a_node_scoped_alias_never_publishes_a_placement(self):
        """Where the alias stood in for THIS node's own name, no placement
        rests on it: the claim would be "the parent's own page lists it by
        name", and a page printing a name the graph does not use is a weaker
        thing with no honest wording. `evidence.apply_evidence_to_tree` and
        `govman.apply_govman_org_evidence` both refuse it and count it.

        An ORGANISATION-scoped match is the other case and is deliberately
        allowed: there the post's own title matched outright and the source's
        own filing is the edge claim, with the panel saying in words that the
        agency is named differently. The same URL then sits in both blocks,
        which is why this test is scoped rather than blanket.
        """
        for node in self.carrying():
            if node[al.ALIAS_FIELD].get("scope") == al.ALIAS_SCOPE_NODE:
                urls = set(node[al.ALIAS_FIELD].get("urls") or [])
                self.assertNotIn(str(node.get("placementUrl") or ""), urls, node["id"])

    def test_no_money_or_headcount_block_mentions_this_feature(self):
        from scripts.validate_published_graph import ALIAS_FORBIDDEN_BLOCKS, ALIAS_MARKERS

        for node, _ in self.pairs:
            for field in ALIAS_FORBIDDEN_BLOCKS:
                if node.get(field) is None:
                    continue
                text = json.dumps(node[field], default=str)
                for marker in ALIAS_MARKERS:
                    self.assertNotIn(marker, text, f"{node.get('id')} {field}")

    def test_the_president_and_the_vice_president_are_listed_at_last(self):
        """The narrow top-level-office route, which is the only way either is
        reachable: `match_organisations` skips every post, and the post route
        needs the post's own parent to have a Manual entry."""
        president = self.by_id.get("exec-president")
        vice = self.by_id.get("exec-vp")
        self.assertIsNotNone(president)
        self.assertIsNotNone(vice)
        for node in (president, vice):
            block = node.get("govmanOfficeEntry")
            self.assertIsInstance(block, dict, node["id"])
            self.assertEqual(node.get("verificationMethod"),
                             "listed_as_its_own_entry_in_us_government_manual")
            self.assertIn(block["url"], node.get("sourceUrls") or [])
            self.assertIsNot(node.get("placementVerified"), True,
                             "one entry was read; it yields one observation")
        # The President needs no alias: the Manual's own principal row prints
        # the office in the full style this graph uses. The Vice President
        # does, and says so.
        self.assertEqual(president["govmanOfficeEntry"]["matchedName"],
                         "THE PRESIDENT OF THE UNITED STATES")
        self.assertIsNone(president.get(al.ALIAS_FIELD))
        self.assertEqual(vice[al.ALIAS_FIELD]["alias"], "The Vice President")

    def test_both_panels_say_in_words_that_another_name_was_used(self):
        for name in ("js/ui.js", "js/atlas.js"):
            source = (PROJECT_ROOT / name).read_text(encoding="utf-8")
            with self.subTest(file=name):
                self.assertIn("verificationAliasMatch", source)
                self.assertIn("by a different recorded name", source)
                self.assertIn("graded no higher than partial", source)
                self.assertIn("listed_as_its_own_entry_in_us_government_manual", source)

    def test_the_viewer_copy_carries_the_block(self):
        from data_pipeline.exporter.build_graph import MINIMAL_GRAPH_FIELDS

        self.assertIn(al.ALIAS_FIELD, MINIMAL_GRAPH_FIELDS)
        self.assertIn("govmanOfficeEntry", MINIMAL_GRAPH_FIELDS)

    def test_both_fields_are_withdrawn_on_every_build(self):
        from data_pipeline.verification.evidence import EVIDENCE_OWNED_FIELDS

        self.assertIn(al.ALIAS_FIELD, EVIDENCE_OWNED_FIELDS)
        self.assertIn("govmanOfficeEntry", EVIDENCE_OWNED_FIELDS)


class GateCorruptionTests(unittest.TestCase):
    """Every dimension of the published claim, corrupted in turn."""

    CHECK = "an alias match quotes a reviewed alternative for this node, under the name the row was written against, and never reads verified alone"

    @classmethod
    def setUpClass(cls):
        if not PUBLISHED.exists():
            raise unittest.SkipTest("output/graph.json is not built")
        cls.graph = json.loads(PUBLISHED.read_text(encoding="utf-8"))
        if not any(isinstance(n.get(al.ALIAS_FIELD), dict) for n, _ in published_nodes()):
            raise unittest.SkipTest("output/graph.json predates the alias table; regenerate it")

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

    def corrupt(self, mutate, scope=al.ALIAS_SCOPE_NODE, capped=False):
        graph = copy.deepcopy(self.graph)
        stack = [graph]
        while stack:
            node = stack.pop()
            block = node.get(al.ALIAS_FIELD)
            if (isinstance(block, dict) and block.get("scope") == scope
                    and (not capped or block.get("gradedAtMost") == "partial")):
                mutate(node)
                return graph
            stack.extend([c for c in (node.get("children") or []) if isinstance(c, dict)])
        self.fail(f"no node carries a {scope}-scoped alias match")

    def assert_refused(self, mutate, because, scope=al.ALIAS_SCOPE_NODE, check=None, capped=False):
        code, output = self.run_gate(self.corrupt(mutate, scope, capped))
        self.assertEqual(code, 1, f"the gate accepted a graph where {because}")
        self.assertIn("FAIL  " + (check or self.CHECK), output)

    def test_the_untouched_graph_passes(self):
        code, output = self.run_gate(copy.deepcopy(self.graph))
        self.assertIn("ok    " + self.CHECK, output)
        self.assertEqual(code, 0, output[-3000:])

    def test_an_alternative_the_table_does_not_carry(self):
        def mutate(node):
            node[al.ALIAS_FIELD]["alias"] = "Ministry of Widgets"
            node[al.ALIAS_FIELD]["matches"][0]["alias"] = "Ministry of Widgets"

        self.assert_refused(mutate, "the alternative is not in the committed table")

    def test_a_row_moved_to_another_node(self):
        def mutate(node):
            node[al.ALIAS_FIELD]["matches"][0]["owner"] = "the-constitution-of-the-united-states"
            node[al.ALIAS_FIELD]["owner"] = "the-constitution-of-the-united-states"

        self.assert_refused(mutate, "the row belongs to another node")

    def test_a_node_renamed_out_from_under_its_row(self):
        self.assert_refused(lambda n: n.update(name=n["name"] + " (Renamed)"),
                            "the node no longer carries the name the row was written against")

    def test_a_match_with_no_basis(self):
        def mutate(node):
            node[al.ALIAS_FIELD]["matches"][0]["basis"] = ""

        self.assert_refused(mutate, "the identification is asserted rather than argued")

    def test_verified_on_alias_evidence_alone(self):
        def mutate(node):
            node["verificationStatus"] = "verified"
            node["confidenceScore"] = 0.9

        self.assert_refused(mutate, "a node resting only on the table reads verified", capped=True)

    def test_a_url_the_matches_do_not_name(self):
        def mutate(node):
            node[al.ALIAS_FIELD]["urls"].append("https://example.gov/invented")

        self.assert_refused(mutate, "the block cites a URL nothing behind it names")

    def test_a_non_official_host(self):
        def mutate(node):
            node[al.ALIAS_FIELD]["matches"][0]["url"] = "https://example.com/page"
            node[al.ALIAS_FIELD]["urls"] = ["https://example.com/page"]

        self.assert_refused(mutate, "the alias cites a host that is not official")

    def test_an_organisation_scoped_match_filed_as_the_node_s_own(self):
        def mutate(node):
            node[al.ALIAS_FIELD]["matches"][0]["scope"] = al.ALIAS_SCOPE_NODE

        self.assert_refused(mutate, "an ancestor's alternative is published as this node's own name",
                            scope=al.ALIAS_SCOPE_ORGANISATION)

    def test_an_alias_on_a_money_block(self):
        graph = copy.deepcopy(self.graph)
        stack = [graph]
        while stack:
            node = stack.pop()
            if isinstance(node.get("ombBudget"), dict):
                node["ombBudget"]["matchRule"] = MATCH_RULE_ALIAS
                code, output = self.run_gate(graph)
                self.assertEqual(code, 1)
                self.assertIn("FAIL  no money or headcount block rests on an alternative name", output)
                return
            stack.extend([c for c in (node.get("children") or []) if isinstance(c, dict)])
        self.skipTest("no node carries an OMB budget block")

    def test_an_office_entry_moved_onto_an_organisation(self):
        graph = copy.deepcopy(self.graph)
        stack = [graph]
        holder = None
        target = None
        while stack:
            node = stack.pop()
            if holder is None and isinstance(node.get("govmanOfficeEntry"), dict):
                holder = node
            elif target is None and "position" not in str(node.get("type") or "").casefold() and node.get("id") != "the-constitution-of-the-united-states":
                target = node
            stack.extend([c for c in (node.get("children") or []) if isinstance(c, dict)])
        self.assertIsNotNone(holder)
        self.assertIsNotNone(target)
        target["govmanOfficeEntry"] = copy.deepcopy(holder["govmanOfficeEntry"])
        code, output = self.run_gate(graph)
        self.assertEqual(code, 1)
        self.assertIn("FAIL  a Manual office entry is a top-level entry for the office itself, on a post, and never a placement", output)


if __name__ == "__main__":
    unittest.main()
