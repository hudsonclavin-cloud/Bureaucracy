from __future__ import annotations

import unittest
from unittest.mock import patch

from data_expansion import expand_corporate_nodes


class ExpandCorporateNodesTests(unittest.TestCase):
    def iter_nodes(self, root: dict[str, object]) -> list[dict[str, object]]:
        stack = [root]
        nodes: list[dict[str, object]] = []
        while stack:
            current = stack.pop()
            nodes.append(current)
            stack.extend(reversed(current.get("children", [])))
        return nodes

    def test_build_corporate_expansion_normalizes_fields_and_keeps_edges_valid(self) -> None:
        root = {
            "id": "",
            "name": "Acme Corporation",
            "type": "government corporation",
            "color": expand_corporate_nodes.GREEN,
            "children": [],
        }
        empty_template = expand_corporate_nodes.CorporateTemplate(
            name="",
            divisions=("", "  "),
            roles=("",),
        )

        with patch.dict(
            expand_corporate_nodes.TEMPLATES,
            {expand_corporate_nodes.slugify("Acme Corporation"): empty_template},
            clear=False,
        ):
            result = expand_corporate_nodes.build_corporate_expansion(root)

        self.assertEqual(len(result["nodes"]), 1)

        generated_root = result["nodes"][0]
        all_nodes = self.iter_nodes(generated_root)
        all_ids = {node["id"] for node in all_nodes}

        self.assertEqual(generated_root["id"], "acme-corporation")
        self.assertEqual(generated_root["name"], "Acme Corporation")
        self.assertEqual(generated_root["type"], "Government Corporation")
        self.assertTrue(all(node["id"] for node in all_nodes))
        self.assertTrue(all(node["name"] for node in all_nodes))
        self.assertTrue(all(node["type"] for node in all_nodes))
        self.assertTrue(
            all(edge["source"] in all_ids and edge["target"] in all_ids for edge in result["edges"])
        )


if __name__ == "__main__":
    unittest.main()
