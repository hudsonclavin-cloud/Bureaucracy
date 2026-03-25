from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.run_pipeline import run_pipeline


DEFAULT_SLEEP_SECONDS = 6 * 60 * 60


def getenv_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def run_forever(*, sleep_seconds: int = DEFAULT_SLEEP_SECONDS) -> None:
    while True:
        started_at = datetime.now(tz=timezone.utc)
        try:
            result = run_pipeline()
            print(
                f"[{started_at.isoformat()}] complete: "
                f"{result['new_nodes_added']} new graph nodes, "
                f"{result['candidate_nodes_written']} candidates, "
                f"{result.get('frontier_targets_written', 0)} frontier targets"
            )
        except Exception as error:  # noqa: BLE001
            print(f"[{started_at.isoformat()}] pipeline failed: {error}")
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    run_forever(sleep_seconds=getenv_int("PIPELINE_CONTINUOUS_SLEEP_SECONDS", DEFAULT_SLEEP_SECONDS))
