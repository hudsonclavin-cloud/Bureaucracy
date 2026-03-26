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

from data_pipeline.crawler.federal_register import crawl as crawl_federal_register
from data_pipeline.crawler.lobbying import crawl as crawl_lobbying
from data_pipeline.crawler.official_directory import crawl as crawl_official_directory
from data_pipeline.crawler.treasury_outlays import crawl as crawl_treasury_outlays
from data_pipeline.crawler.usaspending import crawl as crawl_usaspending
from data_pipeline.crawler.wikidata import crawl as crawl_wikidata
from data_pipeline.crawler.wikidata import crawl_discovery_records as crawl_wikidata_discovery_records
from data_pipeline.discovery.source_discovery import (
    DEFAULT_OUTPUT_PATH as DEFAULT_CANDIDATE_OUTPUT,
    discover_candidates,
    load_existing_graph_nodes,
    promote_candidates,
    write_review_queue,
)
from data_pipeline.exporter.build_graph import (
    DEFAULT_BASE_GRAPH,
    DEFAULT_GRAPH_OUTPUT,
    DEFAULT_NODES_OUTPUT,
    DEFAULT_EDGES_OUTPUT,
    build_graph,
)
from data_pipeline.processors.enrichment import enrich_nodes
from data_pipeline.state.pipeline_state import (
    DEFAULT_FRONTIER_OUTPUT,
    DEFAULT_STATE_PATH,
    build_frontier_targets,
    load_pipeline_state,
    update_pipeline_state,
    write_frontier_targets,
    write_pipeline_state,
)


DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"
DEFAULT_STATS_OUTPUT = DEFAULT_OUTPUT_DIR / "pipeline_stats.json"
DEFAULT_ENRICHMENT_STATS_OUTPUT = DEFAULT_OUTPUT_DIR / "enrichment_stats.json"


def getenv_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def count_tree_nodes(node: dict[str, Any]) -> int:
    total = 1
    for child in node.get("children", []):
        if isinstance(child, dict):
            total += count_tree_nodes(child)
    return total


def safe_stage(stage_name: str, fn: Callable[[], Any]) -> tuple[Any, str | None]:
    try:
        return fn(), None
    except Exception as error:  # noqa: BLE001
        return None, f"{stage_name}: {error}"


def format_pipeline_summary(stats: dict[str, Any]) -> str:
    verification = stats.get("verification_breakdown", {})
    return "\n".join(
        [
            "PIPELINE SUMMARY",
            "----------------",
            f"nodes_before: {stats['nodes_before']}",
            f"nodes_after: {stats['nodes_after']}",
            f"new_nodes_added: {stats['new_nodes_added']}",
            f"verification_breakdown: {json.dumps(verification, sort_keys=True)}",
        ]
    )


def run_pipeline(
    *,
    base_graph_path: str | Path = DEFAULT_BASE_GRAPH,
    candidate_output_path: str | Path = DEFAULT_CANDIDATE_OUTPUT,
    graph_output_path: str | Path = DEFAULT_GRAPH_OUTPUT,
    nodes_output_path: str | Path = DEFAULT_NODES_OUTPUT,
    edges_output_path: str | Path = DEFAULT_EDGES_OUTPUT,
    stats_output_path: str | Path = DEFAULT_STATS_OUTPUT,
    enrichment_stats_output_path: str | Path = DEFAULT_ENRICHMENT_STATS_OUTPUT,
    frontier_output_path: str | Path = DEFAULT_FRONTIER_OUTPUT,
    state_output_path: str | Path = DEFAULT_STATE_PATH,
    direct_payload_fetchers: dict[str, Callable[[], dict[str, list[dict[str, Any]]]]] | list[Callable[[], dict[str, list[dict[str, Any]]]]] | None = None,
    discovery_fetchers: dict[str, Callable[[], list[dict[str, Any]]]] | None = None,
) -> dict[str, Any]:
    fiscal_year = getenv_int("PIPELINE_FISCAL_YEAR", datetime.now(tz=timezone.utc).year)
    lobbying_year = getenv_int("PIPELINE_LOBBYING_YEAR", fiscal_year)
    existing_graph_path = Path(graph_output_path)
    existing_nodes = load_existing_graph_nodes(existing_graph_path if existing_graph_path.exists() else base_graph_path)
    nodes_before = len(existing_nodes)
    pipeline_state = load_pipeline_state(state_output_path)
    frontier_targets = build_frontier_targets(
        existing_nodes,
        state=pipeline_state,
        limit=getenv_int("PIPELINE_FRONTIER_LIMIT", 80),
    )
    frontier_path = write_frontier_targets(frontier_targets, frontier_output_path)

    if direct_payload_fetchers is None:
        direct_fetchers = {
            "usaspending": lambda: crawl_usaspending(
                limit_agencies=getenv_int("PIPELINE_USASPENDING_AGENCIES", 20),
                awards_per_agency=getenv_int("PIPELINE_USASPENDING_AWARDS", 25),
                fiscal_year=fiscal_year,
            ),
            "treasury_outlays": lambda: crawl_treasury_outlays(
                fiscal_year=fiscal_year,
                timeout=getenv_int("PIPELINE_HTTP_TIMEOUT", 30),
            ),
            "wikidata": lambda: crawl_wikidata(
                hierarchy_limit=getenv_int("PIPELINE_WIKIDATA_HIERARCHY_LIMIT", 500),
                office_holder_limit=getenv_int("PIPELINE_WIKIDATA_HOLDER_LIMIT", 250),
                subunit_limit=getenv_int("PIPELINE_WIKIDATA_SUBUNIT_LIMIT", 500),
            ),
            "lobbying": lambda: crawl_lobbying(
                year=lobbying_year,
                pages=getenv_int("PIPELINE_LOBBYING_PAGES", 5),
                page_size=getenv_int("PIPELINE_LOBBYING_PAGE_SIZE", 50),
            ),
        }
    else:
        direct_fetchers = direct_payload_fetchers
    if isinstance(direct_fetchers, list):
        direct_fetchers = {f"payload_{index + 1}": fetcher for index, fetcher in enumerate(direct_fetchers)}
    if discovery_fetchers is None:
        raw_discovery_fetchers = {
            "wikidata_records": lambda: crawl_wikidata_discovery_records(
                hierarchy_limit=getenv_int("PIPELINE_WIKIDATA_HIERARCHY_LIMIT", 500),
                office_holder_limit=getenv_int("PIPELINE_WIKIDATA_HOLDER_LIMIT", 250),
                subunit_limit=getenv_int("PIPELINE_WIKIDATA_SUBUNIT_LIMIT", 500),
            ),
            "official_directory_records": lambda: crawl_official_directory(
                sources=frontier_targets,
                max_records_per_source=getenv_int("PIPELINE_OFFICIAL_DIRECTORY_LIMIT", 150),
                return_metadata=True,
            ),
            "federal_register_records": lambda: crawl_federal_register(
                pages=getenv_int("PIPELINE_FEDERAL_REGISTER_PAGES", 3),
                per_page=getenv_int("PIPELINE_FEDERAL_REGISTER_PAGE_SIZE", 100),
            ),
        }
    else:
        raw_discovery_fetchers = discovery_fetchers

    payloads: list[dict[str, list[dict[str, Any]]]] = []
    stage_errors: list[str] = []
    direct_payload_results: dict[str, dict[str, list[dict[str, Any]]]] = {}
    successful_sources: list[str] = []
    for payload_name, fetcher in direct_fetchers.items():
        payload, error = safe_stage(payload_name, fetcher)
        if error:
            stage_errors.append(error)
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
            direct_payload_results[payload_name] = payload
            successful_sources.append(payload_name)

    discovery_inputs: dict[str, list[dict[str, Any]]] = {}
    discovery_record_counts: dict[str, int] = {}
    frontier_metrics: list[dict[str, Any]] = []
    for input_name, fetcher in raw_discovery_fetchers.items():
        records, error = safe_stage(input_name, fetcher)
        if error:
            stage_errors.append(error)
            discovery_inputs[input_name] = []
            discovery_record_counts[input_name] = 0
            continue
        if input_name == "official_directory_records" and isinstance(records, dict):
            frontier_metrics = [
                metric
                for metric in records.get("sourceMetrics", [])
                if isinstance(metric, dict)
            ]
            normalized_records = [
                record
                for record in records.get("records", [])
                if isinstance(record, dict)
            ]
        else:
            normalized_records = records if isinstance(records, list) else []
        discovery_inputs[input_name] = normalized_records
        discovery_record_counts[input_name] = len(normalized_records)
        successful_sources.append(input_name)

    candidates = discover_candidates(
        existing_nodes=existing_nodes,
        base_graph_path=base_graph_path,
        **discovery_inputs,
    )
    candidate_path = write_review_queue(candidates, output_path=candidate_output_path)
    promoted_nodes, promotion_stats = promote_candidates(
        candidates,
        existing_nodes=existing_nodes,
        min_confidence_score=float(os.environ.get("PIPELINE_PROMOTION_THRESHOLD", "0.7")),
    )
    enrichment_stats = {
        "nodes_enriched": 0,
        "relationships_added": 0,
        "leadership_positions_added": 0,
        "budgets_linked": 0,
        "verification_score_changes": 0,
    }
    enriched_nodes: list[dict[str, Any]] = []
    enriched_edges: list[dict[str, Any]] = []
    enrichment_result, enrichment_error = safe_stage(
        "enrichment",
        lambda: enrich_nodes(
            existing_nodes=existing_nodes,
            direct_payload_nodes=[
                *promoted_nodes,
                *[
                    node
                    for payload in direct_payload_results.values()
                    for node in payload.get("nodes", [])
                    if isinstance(node, dict)
                ],
            ],
            wikidata_records=discovery_inputs.get("wikidata_records", []),
            official_directory_records=discovery_inputs.get("official_directory_records", []),
            federal_register_records=discovery_inputs.get("federal_register_records", []),
            usaspending_payload=direct_payload_results.get("usaspending"),
            treasury_outlay_payload=direct_payload_results.get("treasury_outlays"),
            max_http_nodes=getenv_int("PIPELINE_ENRICHMENT_HTTP_LIMIT", 18),
            http_timeout=getenv_int("PIPELINE_HTTP_TIMEOUT", 10),
        ),
    )
    if enrichment_error:
        stage_errors.append(enrichment_error)
    elif enrichment_result:
        enriched_nodes, enriched_edges, enrichment_stats = enrichment_result

    if promoted_nodes or enriched_nodes or enriched_edges:
        payloads.append(
            {
                "nodes": [*promoted_nodes, *enriched_nodes],
                "edges": enriched_edges,
            }
        )

    build_result = build_graph(
        payloads,
        base_graph_path=base_graph_path,
        graph_output_path=graph_output_path,
        nodes_output_path=nodes_output_path,
        edges_output_path=edges_output_path,
    )
    nodes_after = count_tree_nodes(build_result.graph)
    timestamp = datetime.now(tz=timezone.utc).isoformat()
    next_state = update_pipeline_state(
        pipeline_state,
        frontier_targets=frontier_targets,
        frontier_metrics=frontier_metrics,
        promoted_nodes=promoted_nodes,
        enriched_nodes=enriched_nodes,
        timestamp=timestamp,
    )
    state_path = write_pipeline_state(next_state, state_output_path)
    stats = {
        "timestamp": timestamp,
        "nodes_before": nodes_before,
        "nodes_after": nodes_after,
        "new_nodes_added": max(0, nodes_after - nodes_before),
        "candidate_nodes_written": len(candidates),
        "promoted_nodes_written": len(promoted_nodes),
        "promotion_stats": promotion_stats,
        "enrichment_stats": enrichment_stats,
        "verification_breakdown": build_result.validation.get("verification_status_counts", {}),
        "average_confidence_score": build_result.validation.get("average_confidence_score", 0.0),
        "verified_node_count": build_result.validation.get("verified_node_count", 0),
        "build_validation": build_result.validation,
        "discovery_sources_used": successful_sources,
        "discovery_record_counts": discovery_record_counts,
        "frontier_targets_written": len(frontier_targets),
        "frontier_success_count": sum(1 for metric in frontier_metrics if metric.get("success")),
        "frontier_failure_count": sum(1 for metric in frontier_metrics if not metric.get("success")),
        "budget_summary": direct_payload_results.get("treasury_outlays", {}).get("budgetSummary"),
        "direct_payload_counts": {
            source_name: {
                "nodes": len(payload.get("nodes", [])),
                "edges": len(payload.get("edges", [])),
                **({"outlayRows": len(payload.get("outlayRows", []))} if isinstance(payload.get("outlayRows"), list) else {}),
            }
            for source_name, payload in direct_payload_results.items()
        },
        "stage_errors": stage_errors,
        "outputs": {
            "graph": str(build_result.graph_path),
            "expanded_nodes": str(build_result.nodes_path),
            "expanded_edges": str(build_result.edges_path),
            "node_validity_report": str(build_result.validity_report_path) if build_result.validity_report_path else None,
            "candidate_nodes": str(candidate_path),
            "enrichment_stats": str(enrichment_stats_output_path),
            "frontier_targets": str(frontier_path),
            "pipeline_state": str(state_path),
        },
    }

    stats_path = Path(stats_output_path)
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    with stats_path.open("w", encoding="utf-8") as handle:
        json.dump(stats, handle, indent=2)

    enrichment_path = Path(enrichment_stats_output_path)
    enrichment_path.parent.mkdir(parents=True, exist_ok=True)
    with enrichment_path.open("w", encoding="utf-8") as handle:
        json.dump(enrichment_stats, handle, indent=2)
    return stats


def main() -> None:
    stats = run_pipeline()
    print(format_pipeline_summary(stats))
    print(f"Wrote pipeline stats to {DEFAULT_STATS_OUTPUT}")


if __name__ == "__main__":
    main()
