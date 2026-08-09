from __future__ import annotations

import json
import os
import sys
import traceback
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
    DEFAULT_VALIDITY_REPORT_OUTPUT,
    build_graph,
)


DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"
DEFAULT_STATS_OUTPUT = DEFAULT_OUTPUT_DIR / "pipeline_stats.json"


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
        print(f"Stage failed: {stage_name}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return None, f"{stage_name}: {error.__class__.__name__}: {error}"


def format_pipeline_summary(stats: dict[str, Any]) -> str:
    verification = stats.get("verification_breakdown", {})
    lines = [
        "PIPELINE SUMMARY",
        "----------------",
        f"nodes_before: {stats['nodes_before']}",
        f"nodes_after: {stats['nodes_after']}",
        f"new_nodes_added: {stats['new_nodes_added']}",
        f"verification_breakdown: {json.dumps(verification, sort_keys=True)}",
    ]
    stage_errors = stats.get("stage_errors") or []
    if stage_errors:
        lines.append(f"stage_errors ({len(stage_errors)}):")
        lines.extend(f"  - {error}" for error in stage_errors)
    if stats.get("all_fetch_stages_failed"):
        lines.append("ALL FETCH STAGES FAILED OR RETURNED NO DATA: existing outputs were left untouched")
    elif stats.get("publication_blocked"):
        lines.append("PUBLICATION BLOCKED: existing outputs were left untouched")
    return "\n".join(lines)


def run_pipeline(
    *,
    base_graph_path: str | Path = DEFAULT_BASE_GRAPH,
    candidate_output_path: str | Path = DEFAULT_CANDIDATE_OUTPUT,
    graph_output_path: str | Path = DEFAULT_GRAPH_OUTPUT,
    nodes_output_path: str | Path = DEFAULT_NODES_OUTPUT,
    edges_output_path: str | Path = DEFAULT_EDGES_OUTPUT,
    validity_report_output_path: str | Path = DEFAULT_VALIDITY_REPORT_OUTPUT,
    enforce_export_gate: bool = True,
    stats_output_path: str | Path = DEFAULT_STATS_OUTPUT,
    direct_payload_fetchers: list[Callable[[], dict[str, list[dict[str, Any]]]]] | None = None,
    discovery_fetchers: dict[str, Callable[[], list[dict[str, Any]]]] | None = None,
) -> dict[str, Any]:
    fiscal_year = getenv_int("PIPELINE_FISCAL_YEAR", datetime.now(tz=timezone.utc).year)
    lobbying_year = getenv_int("PIPELINE_LOBBYING_YEAR", fiscal_year)
    existing_nodes = load_existing_graph_nodes(base_graph_path)
    nodes_before = len(existing_nodes)

    direct_fetchers = direct_payload_fetchers or [
        # First: this is the cost anchor. Without its budgetSummary the cost
        # cascade has nothing to apportion, every node fails CostValidator on
        # missing_cost, and the publication guard blocks the run outright.
        lambda: crawl_treasury_outlays(
            fiscal_year=fiscal_year,
            timeout=getenv_int("PIPELINE_HTTP_TIMEOUT", 30),
        ),
        lambda: crawl_usaspending(
            limit_agencies=getenv_int("PIPELINE_USASPENDING_AGENCIES", 20),
            awards_per_agency=getenv_int("PIPELINE_USASPENDING_AWARDS", 25),
            fiscal_year=fiscal_year,
        ),
        lambda: crawl_wikidata(
            hierarchy_limit=getenv_int("PIPELINE_WIKIDATA_HIERARCHY_LIMIT", 500),
            office_holder_limit=getenv_int("PIPELINE_WIKIDATA_HOLDER_LIMIT", 250),
            subunit_limit=getenv_int("PIPELINE_WIKIDATA_SUBUNIT_LIMIT", 500),
        ),
        lambda: crawl_lobbying(
            year=lobbying_year,
            pages=getenv_int("PIPELINE_LOBBYING_PAGES", 5),
            page_size=getenv_int("PIPELINE_LOBBYING_PAGE_SIZE", 50),
        ),
    ]
    raw_discovery_fetchers = discovery_fetchers or {
        "wikidata_records": lambda: crawl_wikidata_discovery_records(
            hierarchy_limit=getenv_int("PIPELINE_WIKIDATA_HIERARCHY_LIMIT", 500),
            office_holder_limit=getenv_int("PIPELINE_WIKIDATA_HOLDER_LIMIT", 250),
            subunit_limit=getenv_int("PIPELINE_WIKIDATA_SUBUNIT_LIMIT", 500),
        ),
        "official_directory_records": lambda: crawl_official_directory(
            max_records_per_source=getenv_int("PIPELINE_OFFICIAL_DIRECTORY_LIMIT", 150),
        ),
        "federal_register_records": lambda: crawl_federal_register(
            pages=getenv_int("PIPELINE_FEDERAL_REGISTER_PAGES", 3),
            per_page=getenv_int("PIPELINE_FEDERAL_REGISTER_PAGE_SIZE", 100),
        ),
    }

    payloads: list[dict[str, list[dict[str, Any]]]] = []
    stage_errors: list[str] = []
    for fetcher in direct_fetchers:
        payload, error = safe_stage("direct_payload", fetcher)
        if error:
            stage_errors.append(error)
            continue
        if isinstance(payload, dict):
            payloads.append(payload)

    discovery_inputs: dict[str, list[dict[str, Any]]] = {}
    for input_name, fetcher in raw_discovery_fetchers.items():
        records, error = safe_stage(input_name, fetcher)
        if error:
            stage_errors.append(error)
            discovery_inputs[input_name] = []
            continue
        discovery_inputs[input_name] = records if isinstance(records, list) else []

    total_fetch_stages = len(direct_fetchers) + len(raw_discovery_fetchers)
    # The crawlers degrade gracefully on network failure: they log a warning and
    # return empty results instead of raising, so a total outage can present as
    # "no stage errors, no data" rather than as raised exceptions. Either signal
    # means there is nothing to export beyond the base graph, so treat both as
    # total fetch failure.
    any_fetch_data = any(
        payload.get("nodes") or payload.get("edges") for payload in payloads
    ) or any(records for records in discovery_inputs.values())
    all_fetch_stages_failed = total_fetch_stages > 0 and (
        len(stage_errors) >= total_fetch_stages or not any_fetch_data
    )
    # A partial outage is more dangerous than a total one. If only the Treasury
    # stage fails, all_fetch_stages_failed stays False and the run proceeds — but
    # with no budget summary the cost cascade assigns nothing, CostValidator
    # blocks every node on missing_cost, and the export gate prunes the entire
    # tree. The result is a near-empty graph.json overwriting a good one and
    # deploying. Refuse to publish a graph that lost effectively everything.
    # Not reported when every stage already failed: there the Treasury summary is
    # simply one more casualty, not an independent second cause.
    cost_basis_missing = enforce_export_gate and not all_fetch_stages_failed and not any(
        isinstance(payload, dict)
        and isinstance(payload.get("budgetSummary"), dict)
        and payload["budgetSummary"].get("government_total_outlay_amount") is not None
        for payload in payloads
    )
    if cost_basis_missing:
        stage_errors.append(
            "No Treasury budget summary in any payload. With the export gate on, "
            "the cost cascade would assign no cost and the gate would prune the "
            "whole tree. Refusing to overwrite existing outputs."
        )

    if all_fetch_stages_failed or cost_basis_missing:
        # Every fetcher failed (e.g. a network outage): refuse to overwrite the
        # published outputs with a base-graph-only export and report the failure.
        stats = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "nodes_before": nodes_before,
            "nodes_after": nodes_before,
            "new_nodes_added": 0,
            "candidate_nodes_written": 0,
            "promoted_nodes_written": 0,
            "promotion_stats": {},
            "verification_breakdown": {},
            "average_confidence_score": 0.0,
            "verified_node_count": 0,
            "build_validation": {"exported_edge_count": 0},
            "stage_errors": stage_errors,
            "all_fetch_stages_failed": all_fetch_stages_failed,
            "publication_blocked": True,
            "outputs": {
                "graph": str(graph_output_path),
                "expanded_nodes": str(nodes_output_path),
                "expanded_edges": str(edges_output_path),
                "candidate_nodes": str(candidate_output_path),
            },
        }
        stats_path = Path(stats_output_path)
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        with stats_path.open("w", encoding="utf-8") as handle:
            json.dump(stats, handle, indent=2)
        return stats

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
    if promoted_nodes:
        payloads.append({"nodes": promoted_nodes, "edges": []})

    build_result = build_graph(
        payloads,
        base_graph_path=base_graph_path,
        graph_output_path=graph_output_path,
        nodes_output_path=nodes_output_path,
        edges_output_path=edges_output_path,
        validity_report_output_path=validity_report_output_path,
        enforce_export_gate=enforce_export_gate,
    )
    nodes_after = count_tree_nodes(build_result.graph)
    stats = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "nodes_before": nodes_before,
        "nodes_after": nodes_after,
        "new_nodes_added": max(0, nodes_after - nodes_before),
        "candidate_nodes_written": len(candidates),
        "promoted_nodes_written": len(promoted_nodes),
        "promotion_stats": promotion_stats,
        "verification_breakdown": build_result.validation.get("verification_status_counts", {}),
        "average_confidence_score": build_result.validation.get("average_confidence_score", 0.0),
        "verified_node_count": build_result.validation.get("verified_node_count", 0),
        "build_validation": build_result.validation,
        "stage_errors": stage_errors,
        "all_fetch_stages_failed": False,
        "publication_blocked": False,
        "outputs": {
            "graph": str(build_result.graph_path),
            "expanded_nodes": str(build_result.nodes_path),
            "expanded_edges": str(build_result.edges_path),
            "candidate_nodes": str(candidate_path),
        },
    }

    stats_path = Path(stats_output_path)
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    with stats_path.open("w", encoding="utf-8") as handle:
        json.dump(stats, handle, indent=2)
    return stats


def main() -> int:
    stats = run_pipeline()
    print(format_pipeline_summary(stats))
    print(f"Wrote pipeline stats to {DEFAULT_STATS_OUTPUT}")
    return 1 if stats.get("all_fetch_stages_failed") or stats.get("publication_blocked") else 0


if __name__ == "__main__":
    raise SystemExit(main())
