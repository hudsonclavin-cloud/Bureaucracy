from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.run_pipeline import run_pipeline


def main() -> None:
    result = run_pipeline()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
