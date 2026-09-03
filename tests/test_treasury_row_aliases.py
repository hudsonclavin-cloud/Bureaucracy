"""The alias table is fitted to the real statement, and stays fitted.

TREASURY_ROW_ALIASES is the one place a Treasury line is pointed at a node by
hand, so it is the one place a wrong answer is stamped "measured" rather than
merely estimated. Three ways it can rot silently:

- an alias whose node id no longer exists (a rename in the base graph). The
  matcher falls through to name matching and the line quietly stops landing,
  or lands somewhere else.
- an alias key that ``canonical_name_key`` can never produce, which simply
  never fires.
- an alias added for a unit the graph does not actually carry, which is how a
  line ends up on the wrong node.

Each is checked below in both directions: the fitted table routes the lines it
was written for, and a line whose unit the graph lacks still finds nothing.
"""

from __future__ import annotations

import json
import shutil
import unittest
import unittest.mock
import uuid
from pathlib import Path

from data_pipeline.exporter.build_graph import (
    DEFAULT_BASE_GRAPH,
    TREASURY_ROW_ALIASES,
    apply_treasury_outlay_rows,
    build_graph_tree,
    canonical_name_key,
    index_tree,
    load_base_graph,
    payloads_carry_treasury_statement,
)


TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"

# The names below are copied from the Monthly Treasury Statement fetched on
# 2026-09-03 (FYTD through 2026-07-31); "Total--" is stripped by the crawler
# before the row reaches the matcher, exactly as reproduced here.
FITTED = {
    "National Oceanic and Atmospheric Administration": "exec-dept-doc-noaa",
    "National Institute of Standards and Technology": "exec-dept-doc-nist",
    "Bureau of the Census": "exec-dept-doc-census",
    "National Telecommunications and Information Administration": "exec-dept-doc-ntia",
    "National Highway Traffic Safety Administration": "exec-dept-dot-nhtsa",
    "Federal Motor Carrier Safety Administration": "exec-dept-dot-fmcsa",
    "Substance Abuse and Mental Health Services Administration": "exec-dept-hhs-samhsa",
    "Comptroller of the Currency": "exec-dept-treasury-occ",
    "United States Attorneys": "exec-dept-doj-usao",
    "Bureau of Indian Affairs and Bureau of Indian Education": "exec-dept-doi-bia",
    "Federal Prison System": "exec-dept-doj-bop",
    "Public and Indian Housing Programs": "exec-dept-hud-pih",
    "Community Planning and Development": "exec-dept-hud-cpd",
    "Energy Efficiency and Renewable Energy": "exec-dept-doe-eere",
    "The White House": "exec-eop-who",
    "Legislative Branch": "legislative-branch",
    "Judicial Branch": "judicial-branch",
}

# Lines the statement really carries whose unit the base graph has no node for
# (the first three) or which name a Treasury grouping rather than an
# organisation (the rest). Every one of these must stay unmatched: its amount
# belongs in the remainder the cascade apportions, not on a node.
UNOWNED = [
    "General Services Administration",
    "Railroad Retirement Board",
    "Corps of Engineers",
    "Fish and Wildlife and Parks",
    "Other Defense Civil Programs",
    "International Assistance Programs",
    "Operation and Maintenance",
    "Interest on the Public Debt",
]


def row(name: str, amount: float, level: int = 3) -> dict:
    return {
        "name": name,
        "originalName": name,
        "rollup_total_amount": amount,
        "sequence_level": level,
        "budget_source": "Treasury MTS Table 5",
        "sourceUrls": ["https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/outlays-of-the-u-s-government"],
        "sourceTypes": ["treasury_outlays"],
    }


def base_node_ids() -> set[str]:
    ids: set[str] = set()
    stack = [load_base_graph(DEFAULT_BASE_GRAPH)]
    while stack:
        node = stack.pop()
        ids.add(str(node.get("id") or ""))
        stack.extend(child for child in node.get("children", []) if isinstance(child, dict))
    return ids


class AliasTableShapeTests(unittest.TestCase):
    def test_every_alias_points_at_a_node_the_base_graph_really_has(self) -> None:
        ids = base_node_ids()
        missing = {key: node_id for key, node_id in TREASURY_ROW_ALIASES.items() if node_id not in ids}
        self.assertEqual(missing, {}, "an alias may only name a curated node that exists")

    def test_every_alias_key_is_one_canonical_name_key_can_produce(self) -> None:
        # canonical_name_key is applied to the row name before the lookup, so
        # a key it would never emit ("U.S. Attorneys", "The White House") is
        # dead weight that silently never fires.
        unreachable = {key for key in TREASURY_ROW_ALIASES if canonical_name_key(key) != key}
        self.assertEqual(unreachable, set())

    def test_no_two_aliases_claim_the_same_node(self) -> None:
        # Two lines on one node would make the second superseded and the
        # published figure depend on row ordering.
        targets = list(TREASURY_ROW_ALIASES.values())
        self.assertEqual(len(targets), len(set(targets)))


class AliasRoutingTests(unittest.TestCase):
    """Good evidence lands, absent evidence does not."""

    def setUp(self) -> None:
        self.root = build_graph_tree(base_graph_path=DEFAULT_BASE_GRAPH, nodes=[], edges=[])
        self.trusted = base_node_ids()

    def apply(self, rows: list[dict]) -> dict:
        return apply_treasury_outlay_rows(
            self.root,
            rows,
            root_id=str(self.root.get("id") or ""),
            trusted_node_ids=self.trusted,
            sample_limit=len(rows) + 1,
        )

    def test_the_fitted_lines_land_on_the_nodes_they_were_fitted_to(self) -> None:
        amounts = {name: 1_000_000.0 + index for index, name in enumerate(FITTED)}
        stats = self.apply([row(name, amount) for name, amount in amounts.items()])
        landed = {hit["row"]: hit["id"] for hit in stats["applied"]}
        self.assertEqual(landed, FITTED)
        self.assertEqual(stats["rows_applied"], len(FITTED))
        self.assertEqual(stats["rows_unmatched"], 0)
        self.assertEqual(stats["rows_ambiguous"], 0)

        node_map, _ = index_tree(self.root)
        for name, node_id in FITTED.items():
            node = node_map[node_id]
            self.assertEqual(node["rollup_total_amount"], amounts[name])
            self.assertEqual(node["treasury_row_name"], name)
            # The measured figure has to arrive carrying its provenance;
            # annotate_resolved_costs reads these to mark the node verified.
            self.assertEqual(node["budget_source"], "Treasury MTS Table 5")
            self.assertIn("treasury_outlays", node["sourceTypes"])
            self.assertTrue(any("fiscaldata.treasury.gov" in url for url in node["sourceUrls"]))

    def test_a_line_whose_unit_the_graph_lacks_still_lands_nowhere(self) -> None:
        stats = self.apply([row(name, 9_000_000_000.0) for name in UNOWNED])
        self.assertEqual(stats["rows_applied"], 0)
        self.assertEqual(stats["rows_unmatched"], len(UNOWNED))
        self.assertEqual(sorted(stats["unmatched_sample"]), sorted(UNOWNED))

    def test_the_department_grouping_lines_do_not_double_count_their_bureaus(self) -> None:
        # "Fish and Wildlife and Parks" is the Interior grouping that contains
        # both bureaus below it. If it were aliased onto either one, that
        # bureau would carry its siblings' spending as its own.
        stats = self.apply(
            [
                row("Fish and Wildlife and Parks", 6_934_000_000.0),
                row("National Park Service", 4_030_000_000.0),
                row("United States Fish and Wildlife Service", 2_910_000_000.0),
            ]
        )
        landed = {hit["row"]: hit["id"] for hit in stats["applied"]}
        self.assertEqual(
            landed,
            {"National Park Service": "exec-dept-doi-nps", "United States Fish and Wildlife Service": "exec-dept-doi-fws"},
        )
        self.assertEqual(stats["unmatched_sample"], ["Fish and Wildlife and Parks"])


class RepeatedLineNameTests(unittest.TestCase):
    """A name several lines carry is reported, never guessed at.

    Table 5 lists "Department of the Navy" eight times — the Navy's slice of
    Military Personnel, of Operation and Maintenance, of Procurement, of
    RDT&E. Each is a fragment. Before this rule the ranker's tie-break took
    the largest and published $73B as the Navy's measured total, on whichever
    node answered to the name; nothing in the output said it was a fragment.
    """

    def base(self, payload: dict) -> Path:
        path = TEST_TMP_ROOT / f"repeat-{uuid.uuid4().hex}"
        path.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, path, True)
        target = path / "base.json"
        target.write_text(json.dumps(payload), encoding="utf-8")
        return target

    GRAPH = {
        "id": "root",
        "name": "Root",
        "type": "Foundation",
        "children": [
            {"id": "navy", "name": "Department of the Navy", "type": "Military Branch", "children": []},
            {"id": "solo", "name": "Bureau of One Line", "type": "Bureau", "children": []},
        ],
    }

    def apply(self, rows: list[dict]) -> tuple[dict, dict]:
        root = build_graph_tree(base_graph_path=self.base(self.GRAPH), nodes=[], edges=[])
        stats = apply_treasury_outlay_rows(root, rows, root_id="root", sample_limit=20)
        node_map, _ = index_tree(root)
        return stats, node_map

    def test_a_name_carried_by_several_lines_lands_on_no_node(self) -> None:
        stats, node_map = self.apply(
            [
                row("Department of the Navy", 73_356_816_090.14),
                row("Department of the Navy", 61_288_000_000.0),
                row("Department of the Navy", 22_946_000_000.0),
                row("Bureau of One Line", 1_000_000.0),
            ]
        )
        self.assertNotIn("rollup_total_amount", node_map["navy"])
        self.assertEqual(stats["rows_ambiguous"], 3)
        self.assertEqual(stats["ambiguous_sample"], ["Department of the Navy"] * 3)
        # The other direction: a name only one line carries still lands.
        self.assertEqual(node_map["solo"]["rollup_total_amount"], 1_000_000.0)
        self.assertEqual(stats["rows_applied"], 1)

    def test_one_line_with_that_name_is_still_applied(self) -> None:
        stats, node_map = self.apply([row("Department of the Navy", 73_356_816_090.14)])
        self.assertEqual(node_map["navy"]["rollup_total_amount"], 73_356_816_090.14)
        self.assertEqual(stats["rows_applied"], 1)
        self.assertEqual(stats["rows_ambiguous"], 0)

    def test_a_header_line_beside_its_own_total_line_still_resolves(self) -> None:
        # The shape treasury_row_rank was written for: a department prints a
        # header line and a "Total--" line under the same name. That is one
        # unit reported twice, not two siblings, and the total wins.
        header = row("Bureau of One Line", 100.0, level=2)
        total = row("Bureau of One Line", 900_000_000.0, level=2)
        total["originalName"] = "Total--Bureau of One Line"
        stats, node_map = self.apply([header, total])
        self.assertEqual(node_map["solo"]["rollup_total_amount"], 900_000_000.0)
        self.assertEqual(stats["rows_applied"], 1)
        self.assertEqual(stats["rows_ambiguous"], 0)
        self.assertEqual(stats["rows_superseded"], 1)

    def test_two_total_lines_under_one_name_are_not_guessed_between(self) -> None:
        first = row("Bureau of One Line", 900_000_000.0, level=2)
        first["originalName"] = "Total--Bureau of One Line"
        second = row("Bureau of One Line", 400_000_000.0, level=3)
        second["originalName"] = "Total--Bureau of One Line"
        stats, node_map = self.apply([first, second])
        self.assertNotIn("rollup_total_amount", node_map["solo"])
        self.assertEqual(stats["rows_applied"], 0)
        self.assertEqual(stats["rows_ambiguous"], 2)

    def test_an_alias_still_resolves_a_repeated_name(self) -> None:
        # The rule refuses to guess; it does not refuse an answer that was
        # given explicitly.
        with unittest.mock.patch.dict(TREASURY_ROW_ALIASES, {"department of the navy": "navy"}, clear=False):
            stats, node_map = self.apply(
                [row("Department of the Navy", 73_356_816_090.14), row("Department of the Navy", 61_288_000_000.0)]
            )
        self.assertEqual(node_map["navy"]["rollup_total_amount"], 73_356_816_090.14)
        self.assertEqual(stats["rows_applied"], 1)
        self.assertEqual(stats["rows_superseded"], 1)


class CarryForwardTests(unittest.TestCase):
    """A rebuild that fetched no statement must not un-measure the graph.

    scripts/regenerate_published_graph.py rebuilds output/ offline from the
    base graph and the anchor already in the published graph; it hands the
    exporter no outlay rows. The stale-rollup sweep ran anyway and stripped
    every measured cost, and the release gate passed the result — a graph with
    no Treasury lines breaks no rule it checks. Both directions below: no
    statement carries the lines forward, a statement replaces them.
    """

    GRAPH = {
        "id": "root",
        "name": "Root",
        "type": "Foundation",
        "children": [{"id": "agency", "name": "Bureau of One Line", "type": "Bureau", "children": []}],
    }

    def tree(self) -> dict:
        path = TEST_TMP_ROOT / f"carry-{uuid.uuid4().hex}"
        path.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, path, True)
        base = path / "base.json"
        base.write_text(json.dumps(self.GRAPH), encoding="utf-8")
        root = build_graph_tree(base_graph_path=base, nodes=[], edges=[])
        node_map, _ = index_tree(root)
        node_map["agency"].update(
            {
                "rollup_total_amount": 900_000_000.0,
                "budget_source": "Treasury MTS Table 5",
                "treasury_row_name": "Bureau of One Line",
                "sourceUrls": ["https://fiscaldata.treasury.gov/datasets/monthly-treasury-statement/outlays-of-the-u-s-government"],
                "sourceTypes": ["treasury_outlays"],
            }
        )
        return root, node_map

    def test_no_statement_leaves_the_published_lines_alone(self) -> None:
        root, node_map = self.tree()
        stats = apply_treasury_outlay_rows(root, [], root_id="root", statement_present=False)
        self.assertEqual(node_map["agency"]["rollup_total_amount"], 900_000_000.0)
        self.assertEqual(node_map["agency"]["budget_source"], "Treasury MTS Table 5")
        self.assertEqual(stats["stale_rollups_cleared"], 0)

    def test_a_statement_that_no_longer_names_the_node_clears_it(self) -> None:
        # The other direction: a real statement is authoritative, so a node it
        # has stopped reporting must not keep last month's figure.
        root, node_map = self.tree()
        stats = apply_treasury_outlay_rows(
            root, [row("Some Other Bureau", 5_000.0)], root_id="root", statement_present=True
        )
        self.assertNotIn("rollup_total_amount", node_map["agency"])
        self.assertNotIn("budget_source", node_map["agency"])
        self.assertEqual(stats["stale_rollups_cleared"], 1)

    def test_the_default_reads_the_rows_it_was_given(self) -> None:
        root, node_map = self.tree()
        apply_treasury_outlay_rows(root, [], root_id="root")
        self.assertEqual(node_map["agency"]["rollup_total_amount"], 900_000_000.0)

    def test_a_payload_declaring_an_empty_statement_still_counts_as_one(self) -> None:
        self.assertTrue(payloads_carry_treasury_statement([{"outlayRows": []}]))
        self.assertFalse(payloads_carry_treasury_statement([{"nodes": [], "budgetSummary": {}}]))
        self.assertFalse(payloads_carry_treasury_statement([]))


class DeadAliasTests(unittest.TestCase):
    """An alias that names nothing must not become a wildcard."""

    def base(self, payload: dict) -> Path:
        path = TEST_TMP_ROOT / f"alias-{uuid.uuid4().hex}"
        path.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, path, True)
        target = path / "base.json"
        target.write_text(json.dumps(payload), encoding="utf-8")
        return target

    def test_an_alias_naming_a_missing_node_stamps_no_node_at_all(self) -> None:
        graph = {
            "id": "root",
            "name": "Root",
            "type": "Foundation",
            "children": [{"id": "kept", "name": "Bureau of Kept Things", "type": "Bureau", "children": []}],
        }
        root = build_graph_tree(base_graph_path=self.base(graph), nodes=[], edges=[])
        with unittest.mock.patch.dict(TREASURY_ROW_ALIASES, {"vanished bureau": "no-such-node"}, clear=False):
            stats = apply_treasury_outlay_rows(
                root, [row("Vanished Bureau", 1_000.0)], root_id="root", sample_limit=10
            )
        self.assertEqual(stats["rows_applied"], 0)
        self.assertEqual(stats["rows_unmatched"], 1)
        node_map, _ = index_tree(root)
        self.assertNotIn("rollup_total_amount", node_map["kept"])


if __name__ == "__main__":
    unittest.main()
