from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.crawler.congressional_committees import discover_candidates as discover_committees
from data_pipeline.crawler.federal_register import discover_candidates as discover_federal_register
from data_pipeline.crawler.gov_directory import discover_candidates as discover_gov_directory
from data_pipeline.crawler.opm import discover_candidates as discover_opm
from data_pipeline.crawler.org_charts import discover_candidates as discover_org_charts
from data_pipeline.crawler.usaspending import discover_candidates as discover_usaspending
from data_pipeline.crawler.wikidata import discover_candidates as discover_wikidata
from data_pipeline.exporter.build_graph import build_graph
from data_pipeline.processors.candidate_nodes import (
    CandidateRegistry,
    ReferenceNodeIndex,
    promote_candidates,
)


OUTPUT_DIR = PROJECT_ROOT / "output"
CANDIDATE_NODES_OUTPUT = OUTPUT_DIR / "candidate_nodes.json"
PIPELINE_STATS_OUTPUT = OUTPUT_DIR / "pipeline_stats.json"
DEFAULT_PROMOTION_THRESHOLD = 0.7


def getenv_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def getenv_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def discover_from_sources() -> tuple[list[dict[str, Any]], list[str], dict[str, str]]:
    sources: list[tuple[str, Callable[[], dict[str, list[dict[str, Any]]]]]] = [
        (
            "wikidata",
            lambda: discover_wikidata(
                hierarchy_limit=getenv_int("PIPELINE_WIKIDATA_HIERARCHY_LIMIT", 800),
                office_holder_limit=getenv_int("PIPELINE_WIKIDATA_HOLDER_LIMIT", 400),
                subunit_limit=getenv_int("PIPELINE_WIKIDATA_SUBUNIT_LIMIT", 800),
            ),
        ),
        ("gov_directory", lambda: discover_gov_directory(timeout=getenv_int("PIPELINE_HTTP_TIMEOUT", 45))),
        (
            "federal_register",
            lambda: discover_federal_register(
                per_page=getenv_int("PIPELINE_FEDERAL_REGISTER_PER_PAGE", 100),
            ),
        ),
        (
            "usaspending_agency_registry",
            lambda: discover_usaspending(
                limit_agencies=getenv_int("PIPELINE_USASPENDING_AGENCIES", 100),
            ),
        ),
        ("opm", lambda: discover_opm(timeout=getenv_int("PIPELINE_HTTP_TIMEOUT", 45))),
        (
            "congressional_committees",
            lambda: discover_committees(timeout=getenv_int("PIPELINE_HTTP_TIMEOUT", 45)),
        ),
        ("agency_org_charts", lambda: discover_org_charts(timeout=getenv_int("PIPELINE_HTTP_TIMEOUT", 45))),
    ]

    candidates: list[dict[str, Any]] = []
    sources_used: list[str] = []
    errors: dict[str, str] = {}

    for source_name, loader in sources:
        try:
            payload = loader() or {}
            batch = payload.get("candidates", [])
            if batch:
                candidates.extend(batch)
                sources_used.append(source_name)
        except Exception as error:  # noqa: BLE001
            errors[source_name] = str(error)

    return candidates, sources_used, errors


def build_metrics(
    *,
    nodes_before: int,
    nodes_after: int,
    new_nodes_added: int,
    duplicates_merged: int,
    candidates: list[dict[str, Any]],
    discovery_sources_used: list[str],
    discovery_errors: dict[str, str],
) -> dict[str, Any]:
    verification_breakdown = {
        "verified": 0,
        "partial": 0,
        "unverified": 0,
    }
    for candidate in candidates:
        status = candidate.get("verificationStatus", "unverified")
        if status not in verification_breakdown:
            verification_breakdown[status] = 0
        verification_breakdown[status] += 1

    return {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "nodes_before": nodes_before,
        "nodes_after": nodes_after,
        "new_nodes_added": new_nodes_added,
        "duplicates_merged": duplicates_merged,
        "candidates_discovered": len(candidates),
        "verification_breakdown": verification_breakdown,
        "discovery_sources_used": discovery_sources_used,
        "discovery_errors": discovery_errors,
    }


def run_pipeline() -> dict[str, Any]:
    references = ReferenceNodeIndex.load()
    nodes_before = len(references.by_id)

    raw_candidates, discovery_sources_used, discovery_errors = discover_from_sources()
    registry = CandidateRegistry(references=references)
    registry.add_many(raw_candidates)
    candidates = registry.values()
    write_json(CANDIDATE_NODES_OUTPUT, candidates)

    promotion_threshold = getenv_float("PIPELINE_PROMOTION_THRESHOLD", DEFAULT_PROMOTION_THRESHOLD)
    promoted_nodes, promoted_edges, skipped_duplicates = promote_candidates(
        candidates,
        references,
        promotion_threshold=promotion_threshold,
    )

    build_result = build_graph(
        [
            {
                "nodes": promoted_nodes,
                "edges": promoted_edges,
            }
        ]
    )

    nodes_after = nodes_before + len(promoted_nodes)
    metrics = build_metrics(
        nodes_before=nodes_before,
        nodes_after=nodes_after,
        new_nodes_added=len(promoted_nodes),
        duplicates_merged=registry.merges + skipped_duplicates,
        candidates=candidates,
        discovery_sources_used=discovery_sources_used,
        discovery_errors=discovery_errors,
    )
    write_json(PIPELINE_STATS_OUTPUT, metrics)

    return {
        "timestamp": metrics["timestamp"],
        "candidate_nodes": len(candidates),
        "promoted_nodes": len(promoted_nodes),
        "promoted_edges": len(promoted_edges),
        "expanded_nodes_path": str(build_result.nodes_path),
        "expanded_edges_path": str(build_result.edges_path),
        "candidate_nodes_path": str(CANDIDATE_NODES_OUTPUT),
        "pipeline_stats_path": str(PIPELINE_STATS_OUTPUT),
        "nodes_before": nodes_before,
        "nodes_after": nodes_after,
        "duplicates_merged": metrics["duplicates_merged"],
        "discovery_sources_used": discovery_sources_used,
        "discovery_errors": discovery_errors,
    }


def main() -> None:
    print(json.dumps(run_pipeline(), indent=2))


if __name__ == "__main__":
    main()
