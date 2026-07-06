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

from data_pipeline.json_io import remove_file, replace_file, write_json_file
from data_pipeline.crawler.federal_register import crawl as crawl_federal_register
from data_pipeline.crawler.lobbying import crawl as crawl_lobbying
from data_pipeline.crawler.official_directory import crawl as crawl_official_directory
from data_pipeline.crawler.treasury_outlays import crawl as crawl_treasury_outlays
from data_pipeline.crawler.usaspending import crawl as crawl_usaspending
from data_pipeline.crawler.wikidata import crawl_combined as crawl_wikidata_combined
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
from data_pipeline.processors.budget_reconciliation import build_budget_vs_actual_report
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
from data_pipeline.validators.node_requirements import generate_audit_report


DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"
DEFAULT_STATS_OUTPUT = DEFAULT_OUTPUT_DIR / "pipeline_stats.json"
DEFAULT_ENRICHMENT_STATS_OUTPUT = DEFAULT_OUTPUT_DIR / "enrichment_stats.json"
DEFAULT_AUDIT_REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "audit_report.json"
DEFAULT_BUDGET_RECONCILIATION_OUTPUT = DEFAULT_OUTPUT_DIR / "budget_vs_actual.json"


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


def staging_path(path: str | Path) -> Path:
    output_path = Path(path)
    return output_path.with_name(f".staging.{output_path.name}")


def stage_error_name(error_message: str) -> str:
    return str(error_message).split(":", 1)[0].strip()


def has_blocking_stage_errors(stage_errors: list[str]) -> bool:
    non_blocking_stages = {"lobbying"}
    return any(stage_error_name(error_message) not in non_blocking_stages for error_message in stage_errors)


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
    validity_report_output_path: str | Path | None = None,
    stats_output_path: str | Path = DEFAULT_STATS_OUTPUT,
    enrichment_stats_output_path: str | Path = DEFAULT_ENRICHMENT_STATS_OUTPUT,
    audit_output_path: str | Path = DEFAULT_AUDIT_REPORT_OUTPUT,
    budget_reconciliation_output_path: str | Path = DEFAULT_BUDGET_RECONCILIATION_OUTPUT,
    frontier_output_path: str | Path = DEFAULT_FRONTIER_OUTPUT,
    state_output_path: str | Path = DEFAULT_STATE_PATH,
    direct_payload_fetchers: dict[str, Callable[[], dict[str, list[dict[str, Any]]]]] | list[Callable[[], dict[str, list[dict[str, Any]]]]] | None = None,
    discovery_fetchers: dict[str, Callable[[], list[dict[str, Any]]]] | None = None,
    reuse_existing_graph_payload: bool = False,
) -> dict[str, Any]:
    fiscal_year = getenv_int("PIPELINE_FISCAL_YEAR", datetime.now(tz=timezone.utc).year)
    lobbying_year = getenv_int("PIPELINE_LOBBYING_YEAR", fiscal_year)
    existing_graph_path = Path(graph_output_path)
    base_graph_path = Path(base_graph_path)
    existing_nodes = load_existing_graph_nodes(existing_graph_path if existing_graph_path.exists() else base_graph_path)
    if not existing_nodes and existing_graph_path.exists():
        fallback_nodes = load_existing_graph_nodes(base_graph_path)
        if fallback_nodes:
            existing_nodes = fallback_nodes
    nodes_before = len(existing_nodes)
    pipeline_state = load_pipeline_state(state_output_path)
    frontier_targets = build_frontier_targets(
        existing_nodes,
        state=pipeline_state,
        limit=getenv_int("PIPELINE_FRONTIER_LIMIT", 80),
    )
    frontier_output_path = Path(frontier_output_path)
    state_output_path = Path(state_output_path)
    graph_output_path = Path(graph_output_path)
    nodes_output_path = Path(nodes_output_path)
    edges_output_path = Path(edges_output_path)
    candidate_output_path = Path(candidate_output_path)
    stats_output_path = Path(stats_output_path)
    enrichment_stats_output_path = Path(enrichment_stats_output_path)
    audit_output_path = Path(audit_output_path)
    budget_reconciliation_output_path = Path(budget_reconciliation_output_path)
    validity_report_output_path = (
        Path(validity_report_output_path)
        if validity_report_output_path is not None
        else graph_output_path.with_name("node_validity_report.json")
    )

    staged_frontier_path = staging_path(frontier_output_path)
    staged_state_path = staging_path(state_output_path)
    staged_graph_path = staging_path(graph_output_path)
    staged_min_graph_path = staging_path(graph_output_path.with_name("graph.min.json"))
    staged_nodes_path = staging_path(nodes_output_path)
    staged_edges_path = staging_path(edges_output_path)
    staged_candidate_path = staging_path(candidate_output_path)
    staged_validity_report_path = staging_path(validity_report_output_path)

    frontier_path = write_frontier_targets(frontier_targets, staged_frontier_path)

    _wikidata_combined_cache: list[dict[str, Any]] = []

    def _get_wikidata_combined() -> dict[str, Any]:
        if not _wikidata_combined_cache:
            _wikidata_combined_cache.append(crawl_wikidata_combined(
                hierarchy_limit=getenv_int("PIPELINE_WIKIDATA_HIERARCHY_LIMIT", 500),
                office_holder_limit=getenv_int("PIPELINE_WIKIDATA_HOLDER_LIMIT", 250),
                subunit_limit=getenv_int("PIPELINE_WIKIDATA_SUBUNIT_LIMIT", 500),
            ))
        return _wikidata_combined_cache[0]

    if direct_payload_fetchers is None:
        direct_fetchers = {
            "usaspending": lambda: crawl_usaspending(
                limit_agencies=getenv_int("PIPELINE_USASPENDING_AGENCIES", 150),
                fiscal_year=fiscal_year,
            ),
            "treasury_outlays": lambda: crawl_treasury_outlays(
                fiscal_year=fiscal_year,
                timeout=getenv_int("PIPELINE_HTTP_TIMEOUT", 30),
            ),
            "wikidata": lambda: _get_wikidata_combined()["direct"],
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
            "wikidata_records": lambda: _get_wikidata_combined()["discovery"],
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
            max_http_nodes=getenv_int("PIPELINE_ENRICHMENT_HTTP_LIMIT", 48),
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
        graph_output_path=staged_graph_path,
        min_graph_output_path=staged_min_graph_path,
        nodes_output_path=staged_nodes_path,
        edges_output_path=staged_edges_path,
        validity_report_output_path=staged_validity_report_path,
        reuse_existing_graph_payload=reuse_existing_graph_payload,
        existing_graph_payload_path=graph_output_path,
    )
    nodes_after = count_tree_nodes(build_result.graph)
    timestamp = datetime.now(tz=timezone.utc).isoformat()
    publish_skipped = has_blocking_stage_errors(stage_errors)
    blocking_stage_errors = [error_message for error_message in stage_errors if stage_error_name(error_message) != "lobbying"]
    audit_report = build_result.validation.get("audit_report") or generate_audit_report(build_result.nodes)
    audit_report["summary"]["timestamp"] = timestamp
    audit_report["summary"]["publish_skipped"] = publish_skipped
    audit_report["summary"]["blocking_stage_errors"] = blocking_stage_errors
    if build_result.validation.get("cost_export_policy"):
        audit_report["cost_export_policy"] = build_result.validation.get("cost_export_policy")
    if build_result.validation.get("node_export_policy"):
        audit_report["node_export_policy"] = build_result.validation.get("node_export_policy")
    budget_vs_actual_report = build_budget_vs_actual_report(build_result.nodes)
    budget_vs_actual_report["summary"]["timestamp"] = timestamp
    budget_vs_actual_report["summary"]["publish_skipped"] = publish_skipped
    budget_vs_actual_report["summary"]["blocking_stage_errors"] = blocking_stage_errors
    if publish_skipped:
        state_path = state_output_path
        candidate_path = candidate_output_path
        frontier_path = frontier_output_path
        for path in (
            staged_frontier_path,
            staged_state_path,
            staged_graph_path,
            staged_min_graph_path,
            staged_nodes_path,
            staged_edges_path,
            staged_candidate_path,
            staged_validity_report_path,
        ):
            remove_file(path)
    else:
        next_state = update_pipeline_state(
            pipeline_state,
            frontier_targets=frontier_targets,
            frontier_metrics=frontier_metrics,
            promoted_nodes=promoted_nodes,
            enriched_nodes=enriched_nodes,
            timestamp=timestamp,
        )
        state_path = write_pipeline_state(next_state, staged_state_path)
        candidate_path = write_review_queue(candidates, output_path=staged_candidate_path)
        replace_file(staged_frontier_path, frontier_output_path)
        replace_file(staged_state_path, state_output_path)
        replace_file(staged_graph_path, graph_output_path)
        replace_file(staged_min_graph_path, graph_output_path.with_name("graph.min.json"))
        replace_file(staged_nodes_path, nodes_output_path)
        replace_file(staged_edges_path, edges_output_path)
        replace_file(staged_candidate_path, candidate_output_path)
        replace_file(staged_validity_report_path, validity_report_output_path)
        frontier_path = frontier_output_path
        state_path = state_output_path
        candidate_path = candidate_output_path
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
        "cost_verification_breakdown": build_result.validation.get("cost_verification_status_counts", {}),
        "average_confidence_score": build_result.validation.get("average_confidence_score", 0.0),
        "verified_node_count": build_result.validation.get("verified_node_count", 0),
        "build_validation": build_result.validation,
        "audit_report": {
            "total_nodes_checked": audit_report["summary"].get("total_nodes", 0),
            "nodes_with_errors": audit_report["summary"].get("nodes_with_errors", 0),
            "nodes_with_warnings": audit_report["summary"].get("nodes_with_warnings", 0),
            "warning_only_nodes": audit_report["summary"].get("warning_only_nodes", 0),
            "node_validation_rejected_nodes": build_result.validation.get("node_validation_rejected_nodes", 0),
            "cost_validation_rejected_nodes": build_result.validation.get("cost_validation_rejected_nodes", 0),
            "report_file": str(audit_output_path),
        },
        "budget_vs_actual": {
            "rows_emitted": budget_vs_actual_report["summary"].get("rows_emitted", 0),
            "complete_rows": budget_vs_actual_report["summary"].get("complete_rows", 0),
            "incomplete_rows": budget_vs_actual_report["summary"].get("incomplete_rows", 0),
            "report_file": str(budget_reconciliation_output_path),
        },
        "discovery_sources_used": successful_sources,
        "discovery_record_counts": discovery_record_counts,
        "frontier_targets_written": len(frontier_targets),
        "frontier_success_count": sum(1 for metric in frontier_metrics if metric.get("success")),
        "frontier_failure_count": sum(1 for metric in frontier_metrics if not metric.get("success")),
        "budget_summary": direct_payload_results.get("treasury_outlays", {}).get("budgetSummary"),
        "publish_skipped": publish_skipped,
        "blocking_stage_errors": blocking_stage_errors,
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
            "graph": str(graph_output_path),
            "expanded_nodes": str(nodes_output_path),
            "expanded_edges": str(edges_output_path),
            "node_validity_report": str(validity_report_output_path),
            "audit_report": str(audit_output_path),
            "budget_vs_actual": str(budget_reconciliation_output_path),
            "candidate_nodes": str(candidate_path),
            "enrichment_stats": str(enrichment_stats_output_path),
            "frontier_targets": str(frontier_path),
            "pipeline_state": str(state_path),
        },
    }

    write_json_file(audit_output_path, audit_report)
    write_json_file(budget_reconciliation_output_path, budget_vs_actual_report)
    write_json_file(stats_output_path, stats)
    write_json_file(enrichment_stats_output_path, enrichment_stats)
    create_snapshot(stats, PROJECT_ROOT)
    return stats


def create_snapshot(stats: dict[str, Any], project_root: Path) -> Path | None:
    import shutil
    if not os.environ.get("PIPELINE_CREATE_SNAPSHOT"):
        return None
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    snapshot_dir = project_root / "saved_pages" / ts
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(project_root / "index.html", snapshot_dir / "index.html")
    shutil.copytree(project_root / "js", snapshot_dir / "js", dirs_exist_ok=True)
    shutil.copytree(project_root / "data_expansion", snapshot_dir / "data_expansion",
                    dirs_exist_ok=True)
    out_dst = snapshot_dir / "output"
    out_dst.mkdir(exist_ok=True)
    for fname in (
        "graph.json",
        "expanded_nodes.json",
        "expanded_edges.json",
        "candidate_nodes.json",
        "pipeline_stats.json",
        "audit_report.json",
        "budget_vs_actual.json",
    ):
        src = project_root / "output" / fname
        if src.exists():
            shutil.copy2(src, out_dst / fname)
    (snapshot_dir / "README.md").write_text(
        f"# Snapshot {ts}\nNodes: {stats.get('nodes_after', '?')} | "
        f"Run: {stats.get('timestamp', ts)}\n", encoding="utf-8",
    )
    return snapshot_dir


def main() -> None:
    stats = run_pipeline()
    print(format_pipeline_summary(stats))
    print(f"Wrote pipeline stats to {DEFAULT_STATS_OUTPUT}")


if __name__ == "__main__":
    main()
