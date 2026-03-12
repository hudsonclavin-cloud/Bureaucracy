from __future__ import annotations

import unittest

from data_pipeline.processors.normalize_edges import normalize_edge
from data_pipeline.processors.normalize_nodes import normalize_node


class NormalizerTests(unittest.TestCase):
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

    def test_normalize_edge_normalizes_unknown_relationship_to_manages(self) -> None:
        edge = normalize_edge(
            {
                "source": "alpha",
                "target": "beta",
                "type": "custom relationship",
            }
        )

        self.assertEqual(edge["type"], "manages")


if __name__ == "__main__":
    unittest.main()
