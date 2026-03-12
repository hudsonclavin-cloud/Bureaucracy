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

from data_pipeline.crawler.lobbying import crawl as crawl_lobbying
from data_pipeline.crawler.usaspending import crawl as crawl_usaspending
from data_pipeline.crawler.wikidata import crawl as crawl_wikidata
from data_pipeline.exporter.build_graph import build_graph


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
    fiscal_year = getenv_int("PIPELINE_FISCAL_YEAR", datetime.now(tz=timezone.utc).year)
    lobbying_year = getenv_int("PIPELINE_LOBBYING_YEAR", fiscal_year)

    payloads = [
        crawl_usaspending(
            limit_agencies=getenv_int("PIPELINE_USASPENDING_AGENCIES", 20),
            awards_per_agency=getenv_int("PIPELINE_USASPENDING_AWARDS", 25),
            fiscal_year=fiscal_year,
        ),
        crawl_wikidata(
            hierarchy_limit=getenv_int("PIPELINE_WIKIDATA_HIERARCHY_LIMIT", 500),
            office_holder_limit=getenv_int("PIPELINE_WIKIDATA_HOLDER_LIMIT", 250),
            subunit_limit=getenv_int("PIPELINE_WIKIDATA_SUBUNIT_LIMIT", 500),
        ),
        crawl_lobbying(
            year=lobbying_year,
            pages=getenv_int("PIPELINE_LOBBYING_PAGES", 5),
            page_size=getenv_int("PIPELINE_LOBBYING_PAGE_SIZE", 50),
        ),
    ]

    result = build_graph(payloads)
    return {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "node_count": len(result.nodes),
        "edge_count": len(result.edges),
        "nodes_path": str(result.nodes_path),
        "edges_path": str(result.edges_path),
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
