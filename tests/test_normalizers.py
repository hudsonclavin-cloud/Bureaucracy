from __future__ import annotations

import unittest

from data_pipeline.processors.normalize_edges import normalize_edge
from data_pipeline.processors.normalize_nodes import (
    coerce_nullable_number,
    merge_node,
    normalize_name,
    normalize_node,
    verify_node_sources,
)


class NormalizerTests(unittest.TestCase):
    def test_normalize_node_preserves_description_aliases_and_unknown_fields(self) -> None:
        node = normalize_node(
            {
                "name": "Deputy Director",
                "type": "Role",
                "description": "Leads the office when the director is absent.",
                "bio": "Career civil servant.",
                "customField": {"source": "imported"},
            }
        )

        self.assertEqual(node["type"], "Role")
        self.assertEqual(node["desc"], "Leads the office when the director is absent.")
        self.assertEqual(node["description"], "Leads the office when the director is absent.")
        self.assertEqual(node["bio"], "Career civil servant.")
        self.assertEqual(node["customField"], {"source": "imported"})

    def test_normalize_node_preserves_attach_to_root_flag(self) -> None:
        node = normalize_node(
            {
                "name": "Acme Corp",
                "type": "Corporation",
                "attachToRoot": True,
            }
        )

        self.assertTrue(node["attachToRoot"])
        self.assertEqual(node["id"], "acme-corp")

    def test_normalize_edge_rejects_self_loop(self) -> None:
        edge = normalize_edge(
            {
                "source": "same-node",
                "target": "same-node",
                "type": "contracts_with",
            }
        )

        self.assertIsNone(edge)

    def test_normalize_edge_keeps_unknown_relationship_neutral(self) -> None:
        edge = normalize_edge(
            {
                "source": "alpha",
                "target": "beta",
                "type": "custom relationship",
            }
        )

        # Not "manages": an unrecognised type must not become a claim.
        self.assertEqual(edge["type"], "related_to")
        self.assertEqual(normalize_edge({"source": "a", "target": "b", "type": "part_of"})["type"], "related_to")
        self.assertEqual(normalize_edge({"source": "a", "target": "b"})["type"], "related_to")
        self.assertEqual(normalize_edge({"source": "a", "target": "b", "type": "Reports To"})["type"], "reports_to")

    def test_normalize_name_does_not_rewrite_words_containing_acronyms(self) -> None:
        self.assertEqual(
            normalize_name("Department of Homeland Security"),
            "Department of Homeland Security",
        )
        self.assertEqual(normalize_name("Office of the Secretary"), "Office of the Secretary")
        self.assertEqual(normalize_name("John Doe"), "John Doe")
        self.assertEqual(normalize_name("Hudson Institute Liaison"), "Hudson Institute Liaison")
        self.assertEqual(
            normalize_name("DEPARTMENT OF HOMELAND SECURITY"),
            "Department of Homeland Security",
        )
        self.assertEqual(normalize_name("DEPARTMENT OF HOMELAND SECURITY (DHS)"), "Department of Homeland Security (DHS)")
        self.assertEqual(normalize_name("OFFICE OF THE SECRETARY"), "Office of the Secretary")
        self.assertEqual(normalize_name("FBI"), "FBI")
        # Lower-case input carries no evidence of an acronym: "ice" stays a word.
        self.assertEqual(normalize_name("ice cream office"), "Ice Cream Office")
        self.assertEqual(normalize_name("The Office"), "The Office")

    def test_normalize_name_restores_acronyms_after_title_casing(self) -> None:
        self.assertEqual(normalize_name("nasa"), "NASA")
        self.assertEqual(
            normalize_name("DEPARTMENT OF ENERGY (DOE)"),
            "Department of Energy (DOE)",
        )

    def test_normalize_node_infers_type_color_when_color_missing(self) -> None:
        department = normalize_node({"name": "Department of Energy", "type": "Department"})
        person = normalize_node({"name": "Jane Roe", "type": "Person"})

        self.assertEqual(department["color"], "#c84a4a")
        self.assertEqual(person["color"], "#8a4ac8")

    def test_normalize_node_keeps_explicit_color(self) -> None:
        node = normalize_node({"name": "Custom Agency", "type": "Agency", "color": "#123456"})

        self.assertEqual(node["color"], "#123456")

    def test_merge_node_keeps_existing_color_over_default_gray(self) -> None:
        existing = normalize_node({"id": "agency-alpha", "name": "Agency Alpha", "color": "#4a8ac8"})
        incoming = normalize_node({"id": "agency-alpha", "name": "Agency Alpha", "type": "Organization"})

        merged = merge_node(existing, incoming)

        self.assertEqual(merged["color"], "#4a8ac8")

    def test_coerce_nullable_number_parses_first_number_token(self) -> None:
        self.assertEqual(coerce_nullable_number("3,800 (2023)"), 3800)
        self.assertEqual(coerce_nullable_number("approx. 1,200"), 1200)
        self.assertEqual(coerce_nullable_number("12500"), 12500)
        self.assertEqual(coerce_nullable_number(42), 42)
        self.assertIsNone(coerce_nullable_number("unknown"))
        self.assertIsNone(coerce_nullable_number(None))

    def test_coerce_nullable_number_applies_magnitude_suffixes(self) -> None:
        self.assertEqual(coerce_nullable_number("~2.9 million (including contractors)"), 2900000)
        self.assertEqual(coerce_nullable_number("$4.5 billion"), 4500000000)
        self.assertEqual(coerce_nullable_number("1.3M"), 1300000)

    def test_verify_node_sources_scores_official_and_wikidata_sources(self) -> None:
        node = verify_node_sources(
            {
                "id": "office-nuclear-energy",
                "sourceUrls": [
                    "https://energy.gov/ne",
                    "https://www.wikidata.org/wiki/Q123",
                ],
            }
        )

        self.assertEqual(node["sourceCount"], 2)
        self.assertEqual(node["verificationStatus"], "verified")
        self.assertGreaterEqual(node["confidenceScore"], 0.9)
        self.assertIn("official_site", node["sourceTypes"])
        self.assertIn("wikidata", node["sourceTypes"])


if __name__ == "__main__":
    unittest.main()
