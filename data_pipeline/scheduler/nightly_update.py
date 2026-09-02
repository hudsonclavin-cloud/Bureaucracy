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
    # A refusal to publish must travel with the result. This used to return
    # node_count alone, so a run that left output/ untouched because the
    # Treasury anchor was missing reported 5,170 nodes and exited 0.
    return {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "node_count": result["nodes_after"],
        "edge_count": result["build_validation"]["exported_edge_count"],
        "nodes_path": result["outputs"]["expanded_nodes"],
        "edges_path": result["outputs"]["expanded_edges"],
        "graph_path": result["outputs"]["graph"],
        "candidate_nodes_path": result["outputs"]["candidate_nodes"],
        "publication_blocked": bool(result.get("publication_blocked")),
        "all_fetch_stages_failed": bool(result.get("all_fetch_stages_failed")),
        "stage_errors": list(result.get("stage_errors") or []),
    }


def run_succeeded(result: dict[str, Any]) -> bool:
    return not (result.get("publication_blocked") or result.get("all_fetch_stages_failed"))


def run_forever(*, sleep_seconds: int = DEFAULT_SLEEP_SECONDS) -> None:
    while True:
        started_at = datetime.now(tz=timezone.utc)
        try:
            result = run_once()
            if run_succeeded(result):
                print(
                    f"[{started_at.isoformat()}] pipeline complete: "
                    f"{result['node_count']} nodes, {result['edge_count']} edges"
                )
            else:
                print(
                    f"[{started_at.isoformat()}] PUBLICATION BLOCKED, outputs untouched: "
                    + "; ".join(result["stage_errors"])
                )
        except Exception as error:  # noqa: BLE001
            print(f"[{started_at.isoformat()}] pipeline failed: {error}")
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    if os.environ.get("PIPELINE_RUN_ONCE", "1") == "1":
        outcome = run_once()
        print(outcome)
        raise SystemExit(0 if run_succeeded(outcome) else 1)
    run_forever()
