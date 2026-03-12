from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.run_pipeline import run_pipeline


DEFAULT_SLEEP_SECONDS = 24 * 60 * 60


def getenv_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def run_once() -> dict[str, Any]:
    result = run_pipeline()
    return {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "node_count": result["nodes_after"],
        "edge_count": result["build_validation"]["exported_edge_count"],
        "nodes_path": result["outputs"]["expanded_nodes"],
        "edges_path": result["outputs"]["expanded_edges"],
        "graph_path": result["outputs"]["graph"],
        "candidate_nodes_path": result["outputs"]["candidate_nodes"],
    }


def run_forever(*, sleep_seconds: int = DEFAULT_SLEEP_SECONDS) -> None:
    while True:
        started_at = datetime.now(tz=timezone.utc)
        try:
            result = run_once()
            print(
                f"[{started_at.isoformat()}] pipeline complete: "
                f"{result['node_count']} nodes, {result['edge_count']} edges"
            )
        except Exception as error:  # noqa: BLE001
            print(f"[{started_at.isoformat()}] pipeline failed: {error}")
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    if os.environ.get("PIPELINE_RUN_ONCE", "1") == "1":
        print(run_once())
    else:
        run_forever()
