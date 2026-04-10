from __future__ import annotations

import shutil
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from data_pipeline.discovery.source_discovery import load_existing_graph_nodes
from data_pipeline.scheduler import nightly_update
from data_pipeline.state.pipeline_state import load_pipeline_state


TEST_TMP_ROOT = Path(__file__).resolve().parent / ".tmp"


class PipelineIntegrityTests(unittest.TestCase):
    def test_load_pipeline_state_recovers_from_invalid_json(self) -> None:
        tmp_path = TEST_TMP_ROOT / f"pipeline-state-{uuid.uuid4().hex}"
        tmp_path.mkdir(parents=True, exist_ok=True)
        try:
            state_path = tmp_path / "pipeline_state.json"
            state_path.write_text("{not valid json", encoding="utf-8")

            state = load_pipeline_state(state_path)

            self.assertEqual(state["version"], 1)
            self.assertEqual(state["runCount"], 0)
            self.assertEqual(state["frontier"], {})
            self.assertEqual(state["entities"], {})
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)

    def test_load_existing_graph_nodes_recovers_from_invalid_json(self) -> None:
        tmp_path = TEST_TMP_ROOT / f"graph-state-{uuid.uuid4().hex}"
        tmp_path.mkdir(parents=True, exist_ok=True)
        try:
            graph_path = tmp_path / "graph.json"
            graph_path.write_text("{not valid json", encoding="utf-8")

            nodes = load_existing_graph_nodes(graph_path)

            self.assertEqual(nodes, [])
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)

    def test_nightly_update_reports_pipeline_counts(self) -> None:
        printed: list[str] = []

        def fake_print(*args: object, **kwargs: object) -> None:
            del kwargs
            printed.append(" ".join(str(arg) for arg in args))

        with (
            patch.object(
                nightly_update,
                "run_once",
                return_value={
                    "promoted_nodes_written": 3,
                    "candidate_nodes_written": 7,
                },
            ),
            patch.object(nightly_update.time, "sleep", side_effect=RuntimeError("stop")),
            patch("builtins.print", new=fake_print),
        ):
            with self.assertRaises(RuntimeError):
                nightly_update.run_forever(sleep_seconds=0)

        self.assertTrue(
            any(
                "pipeline complete:" in line
                and "3 promoted nodes" in line
                and "7 candidates" in line
                for line in printed
            )
        )
        self.assertFalse(any("pipeline failed:" in line for line in printed))


if __name__ == "__main__":
    unittest.main()
