from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.scheduler.nightly_update import run_once, run_succeeded


def main() -> int:
    result = run_once()
    print(json.dumps(result, indent=2))
    # Nonzero when the run refused to publish, so a cron or CI wrapper around
    # the documented entry point cannot mistake "outputs left untouched" for
    # success.
    return 0 if run_succeeded(result) else 1


if __name__ == "__main__":
    raise SystemExit(main())
