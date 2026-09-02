from __future__ import annotations

import json
import math
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
    pending_review_queue,
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
    parse_cost_amount,
)
from data_pipeline.json_io import write_json_file


DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"
DEFAULT_STATS_OUTPUT = DEFAULT_OUTPUT_DIR / "pipeline_stats.json"
AUDIT_REPORT_FILENAME = "audit_report.json"

DirectFetcher = Callable[[], dict[str, list[dict[str, Any]]]]
NamedDirectFetcher = tuple[str, DirectFetcher]


def getenv_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def getenv_float(name: str, default: float) -> float:
    """Tolerant like getenv_int: a malformed knob falls back rather than
    crashing a run halfway through, after files have already been written."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if math.isfinite(value) else default


def federal_fiscal_year(moment: datetime) -> int:
    """FY N runs 1 October N-1 to 30 September N."""
    return moment.year + 1 if moment.month >= 10 else moment.year


def count_tree_nodes(node: dict[str, Any]) -> int:
    total = 1
    for child in node.get("children", []):
        if isinstance(child, dict):
            total += count_tree_nodes(child)
    return total


def _count_published_nodes(graph_output_path: str | Path) -> int | None:
    path = Path(graph_output_path)
    if not path.exists():
        return None
    try:
        graph = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return count_tree_nodes(graph) if isinstance(graph, dict) and graph.get("id") else None


def safe_stage(stage_name: str, fn: Callable[[], Any]) -> tuple[Any, str | None]:
    try:
        return fn(), None
    except Exception as error:  # noqa: BLE001
        print(f"Stage failed: {stage_name}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return None, f"{stage_name}: {error.__class__.__name__}: {error}"


def usable_budget_total(payload: Any) -> float | None:
    """The Treasury total the cascade can actually anchor on, or None.

    The guard used to test only `is not None`, while the cascade parses the
    value with parse_cost_amount and would happily anchor on 0, a negative
    number or a string it could not read — publishing an uncosted or all-zero
    graph, which is the exact outcome the guard exists to prevent.
    """
    if not isinstance(payload, dict):
        return None
    summary = payload.get("budgetSummary")
    if not isinstance(summary, dict):
        return None
    total = parse_cost_amount(summary.get("government_total_outlay_amount"))
    if total is None or not math.isfinite(total) or total <= 0:
        return None
    return total


def format_pipeline_summary(stats: dict[str, Any]) -> str:
    verification = stats.get("verification_breakdown", {})
    lines = [
        "PIPELINE SUMMARY",
        "----------------",
        f"nodes_before: {stats['nodes_before']}",
        f"nodes_after: {stats['nodes_after']}",
        f"new_nodes_added: {stats['new_nodes_added']}",
        f"nodes_delta: {stats.get('nodes_delta', 0):+d}",
        f"treasury_total_fetched: {stats.get('treasury_total_fetched', False)}",
        f"verification_breakdown: {json.dumps(verification, sort_keys=True)}",
    ]
    stage_errors = stats.get("stage_errors") or []
    if stage_errors:
        lines.append(f"stage_errors ({len(stage_errors)}):")
        lines.extend(f"  - {error}" for error in stage_errors)
    stage_warnings = stats.get("stage_warnings") or []
    if stage_warnings:
        lines.append(f"stage_warnings ({len(stage_warnings)}):")
        lines.extend(f"  - {warning}" for warning in stage_warnings)
    if stats.get("all_fetch_stages_failed"):
        lines.append("ALL FETCH STAGES FAILED OR RETURNED NO DATA: existing outputs were left untouched")
    elif stats.get("publication_blocked"):
        lines.append("PUBLICATION BLOCKED: existing outputs were left untouched")
    return "\n".join(lines)


def _name_direct_fetchers(
    fetchers: list[NamedDirectFetcher | DirectFetcher],
) -> list[NamedDirectFetcher]:
    """Accept both (name, fn) pairs and bare callables.

    Every crawler used to run under the one stage name "direct_payload", so a
    failed Treasury stage — the only one the cost cascade cannot do without —
    was unidentifiable in stage_errors.
    """
    named: list[NamedDirectFetcher] = []
    for index, item in enumerate(fetchers):
        if isinstance(item, tuple) and len(item) == 2 and callable(item[1]):
            named.append((str(item[0]), item[1]))
        elif callable(item):
            label = getattr(item, "__name__", "") or ""
            if not label or label == "<lambda>":
                label = f"direct_payload_{index + 1}"
            named.append((label, item))
    return named


def _compact_validation(validation: dict[str, Any]) -> dict[str, Any]:
    """Stats keep the audit summary only. The per-node audit is 13 MB for the
    current graph and made pipeline_stats.json uncommittable, so the tracked
    copy described a graph five months and one merge older than the site."""
    compact = dict(validation)
    audit = compact.get("audit_report")
    if isinstance(audit, dict):
        compact["audit_report"] = {"summary": audit.get("summary", {})}
    return compact


def _write_stats(stats_output_path: str | Path, stats: dict[str, Any]) -> None:
    write_json_file(stats_output_path, stats)


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
    audit_report_output_path: str | Path | None = None,
    direct_payload_fetchers: list[NamedDirectFetcher | DirectFetcher] | None = None,
    discovery_fetchers: dict[str, Callable[[], list[dict[str, Any]]]] | None = None,
) -> dict[str, Any]:
    # The federal fiscal year, not the calendar year: FY N starts 1 October N-1.
    fiscal_year = getenv_int("PIPELINE_FISCAL_YEAR", federal_fiscal_year(datetime.now(tz=timezone.utc)))
    # Lobbying filings are calendar-year; default to the calendar year the FY started in.
    lobbying_year = getenv_int("PIPELINE_LOBBYING_YEAR", datetime.now(tz=timezone.utc).year)
    http_timeout = getenv_int("PIPELINE_HTTP_TIMEOUT", 30)
    promotion_threshold = getenv_float("PIPELINE_PROMOTION_THRESHOLD", 0.7)
    existing_nodes = load_existing_graph_nodes(base_graph_path)
    nodes_before = len(existing_nodes)
    # nodes_before is the curated base graph. The number a maintainer wants to
    # compare against is what was published last time.
    published_nodes_before = _count_published_nodes(graph_output_path)
    stats_path = Path(stats_output_path)
    audit_path = Path(audit_report_output_path) if audit_report_output_path else stats_path.parent / AUDIT_REPORT_FILENAME

    direct_fetchers = _name_direct_fetchers(
        direct_payload_fetchers
        if direct_payload_fetchers is not None
        else [
            # First: this is the cost anchor. Without its budgetSummary the cost
            # cascade has nothing to apportion, every node fails CostValidator on
            # missing_cost, and the publication guard blocks the run outright.
            (
                "treasury_outlays",
                # No fiscal-year filter: the anchor is the latest Monthly
                # Treasury Statement, and the first one of a new FY only
                # appears in November. Its own record_fiscal_year is reported.
                lambda: crawl_treasury_outlays(timeout=http_timeout),
            ),
            (
                "usaspending",
                lambda: crawl_usaspending(
                    limit_agencies=getenv_int("PIPELINE_USASPENDING_AGENCIES", 20),
                    awards_per_agency=getenv_int("PIPELINE_USASPENDING_AWARDS", 25),
                    fiscal_year=fiscal_year,
                    timeout=http_timeout,
                ),
            ),
            (
                "wikidata",
                lambda: crawl_wikidata(
                    hierarchy_limit=getenv_int("PIPELINE_WIKIDATA_HIERARCHY_LIMIT", 500),
                    office_holder_limit=getenv_int("PIPELINE_WIKIDATA_HOLDER_LIMIT", 250),
                    subunit_limit=getenv_int("PIPELINE_WIKIDATA_SUBUNIT_LIMIT", 500),
                    timeout=max(http_timeout, 45),
                ),
            ),
            (
                "lobbying",
                lambda: crawl_lobbying(
                    year=lobbying_year,
                    pages=getenv_int("PIPELINE_LOBBYING_PAGES", 5),
                    page_size=getenv_int("PIPELINE_LOBBYING_PAGE_SIZE", 50),
                    timeout=http_timeout,
                ),
            ),
        ]
    )
    raw_discovery_fetchers = discovery_fetchers or {
        "wikidata_records": lambda: crawl_wikidata_discovery_records(
            hierarchy_limit=getenv_int("PIPELINE_WIKIDATA_HIERARCHY_LIMIT", 500),
            office_holder_limit=getenv_int("PIPELINE_WIKIDATA_HOLDER_LIMIT", 250),
            subunit_limit=getenv_int("PIPELINE_WIKIDATA_SUBUNIT_LIMIT", 500),
            timeout=max(http_timeout, 45),
        ),
        "official_directory_records": lambda: crawl_official_directory(
            max_records_per_source=getenv_int("PIPELINE_OFFICIAL_DIRECTORY_LIMIT", 150),
            timeout=http_timeout,
        ),
        "federal_register_records": lambda: crawl_federal_register(
            pages=getenv_int("PIPELINE_FEDERAL_REGISTER_PAGES", 3),
            per_page=getenv_int("PIPELINE_FEDERAL_REGISTER_PAGE_SIZE", 100),
            timeout=http_timeout,
        ),
    }

    payloads: list[dict[str, list[dict[str, Any]]]] = []
    stage_errors: list[str] = []
    stage_warnings: list[str] = []
    stage_results: dict[str, str] = {}
    for stage_name, fetcher in direct_fetchers:
        payload, error = safe_stage(stage_name, fetcher)
        if error:
            stage_errors.append(error)
            stage_results[stage_name] = "error"
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
            has_data = bool(payload.get("nodes") or payload.get("edges") or usable_budget_total(payload) is not None)
            stage_results[stage_name] = "data" if has_data else "empty"
            if payload.get("partial"):
                # Degraded, not failed: some of the stage's queries returned nothing.
                stage_results[stage_name] = "partial"
                stage_warnings.append(f"{stage_name}: partial result, failed queries: {', '.join(map(str, payload['partial']))}")
        else:
            stage_results[stage_name] = "empty"

    discovery_inputs: dict[str, list[dict[str, Any]]] = {}
    for input_name, fetcher in raw_discovery_fetchers.items():
        records, error = safe_stage(input_name, fetcher)
        if error:
            stage_errors.append(error)
            stage_results[input_name] = "error"
            discovery_inputs[input_name] = []
            continue
        discovery_inputs[input_name] = records if isinstance(records, list) else []
        stage_results[input_name] = "data" if discovery_inputs[input_name] else "empty"

    treasury_total = next((total for total in (usable_budget_total(payload) for payload in payloads) if total is not None), None)
    total_fetch_stages = len(direct_fetchers) + len(raw_discovery_fetchers)
    # The crawlers degrade gracefully on network failure: they log a warning and
    # return empty results instead of raising, so a total outage can present as
    # "no stage errors, no data" rather than as raised exceptions. Either signal
    # means there is nothing to export beyond the base graph, so treat both as
    # total fetch failure. A fresh Treasury total counts as data: it is the one
    # thing a nightly run can change while the crawl contributes no nodes.
    any_fetch_data = (
        any(payload.get("nodes") or payload.get("edges") for payload in payloads)
        or any(records for records in discovery_inputs.values())
        or treasury_total is not None
    )
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
    cost_basis_missing = enforce_export_gate and not all_fetch_stages_failed and treasury_total is None
    if cost_basis_missing:
        stage_errors.append(
            "No usable Treasury budget summary in any payload (missing, zero, negative "
            "or non-numeric government_total_outlay_amount). With the export gate on, "
            "the cost cascade would assign no cost and the gate would prune the "
            "whole tree. Refusing to overwrite existing outputs."
        )

    outputs = {
        "graph": str(graph_output_path),
        "expanded_nodes": str(nodes_output_path),
        "expanded_edges": str(edges_output_path),
        "candidate_nodes": str(candidate_output_path),
        "audit_report": str(audit_path),
    }

    def blocked_stats() -> dict[str, Any]:
        # No audit is written on this path; naming the file would point at a
        # stale one from an earlier success.
        blocked_outputs = dict(outputs, audit_report=None)
        return {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "nodes_before": nodes_before,
            "nodes_after": nodes_before,
            "new_nodes_added": 0,
            "nodes_delta": 0,
            "published_nodes_before": published_nodes_before,
            "nodes_delta_vs_published": 0,
            "candidate_nodes_written": 0,
            "promoted_nodes_written": 0,
            "promotion_stats": {},
            "verification_breakdown": {},
            "average_confidence_score": 0.0,
            "verified_node_count": 0,
            "treasury_total_fetched": treasury_total is not None,
            "build_validation": {"exported_edge_count": 0},
            "stage_errors": list(stage_errors),
            "stage_warnings": list(stage_warnings),
            "stage_results": dict(stage_results),
            "all_fetch_stages_failed": all_fetch_stages_failed,
            "publication_blocked": True,
            "outputs": blocked_outputs,
        }

    if all_fetch_stages_failed or cost_basis_missing:
        # Every fetcher failed (e.g. a network outage), or the anchor is gone:
        # refuse to overwrite the published outputs and report the failure.
        stats = blocked_stats()
        _write_stats(stats_path, stats)
        return stats

    candidates = discover_candidates(
        existing_nodes=existing_nodes,
        base_graph_path=base_graph_path,
        **discovery_inputs,
    )
    promoted_nodes, promotion_stats = promote_candidates(
        candidates,
        existing_nodes=existing_nodes,
        min_confidence_score=promotion_threshold,
    )
    if promoted_nodes:
        payloads.append({"nodes": promoted_nodes, "edges": []})

    try:
        build_result = build_graph(
            payloads,
            base_graph_path=base_graph_path,
            graph_output_path=graph_output_path,
            nodes_output_path=nodes_output_path,
            edges_output_path=edges_output_path,
            validity_report_output_path=validity_report_output_path,
            enforce_export_gate=enforce_export_gate,
        )
    except Exception as error:  # noqa: BLE001
        # Leave a stats file that says what happened rather than the previous
        # run's, and do not touch the review queue: a candidate list next to a
        # graph it does not correspond to is a partial write the site would fetch.
        stats = blocked_stats()
        stats["stage_errors"].append(f"build_graph: {error.__class__.__name__}: {error}")
        stats["stage_results"]["build_graph"] = "error"
        _write_stats(stats_path, stats)
        raise

    # The review queue is a file the site fetches; write it only once the graph
    # it accompanies exists, and without the records this run already promoted
    # or merged into it.
    review_queue = pending_review_queue(candidates, promotion_stats)
    candidate_path = write_review_queue(review_queue, output_path=candidate_output_path)
    write_json_file(audit_path, build_result.validation.get("audit_report", {}))

    nodes_after = count_tree_nodes(build_result.graph)
    stats = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "nodes_before": nodes_before,
        "nodes_after": nodes_after,
        "new_nodes_added": max(0, nodes_after - nodes_before),
        # Signed, so a shrinking graph is visible: the 13,359 -> 5,170
        # regeneration reported new_nodes_added 0 and nothing else.
        "nodes_delta": nodes_after - nodes_before,
        "published_nodes_before": published_nodes_before,
        "nodes_delta_vs_published": (nodes_after - published_nodes_before) if published_nodes_before is not None else None,
        "candidate_nodes_written": len(review_queue),
        "candidates_discovered": len(candidates),
        "promoted_nodes_written": len(promoted_nodes),
        "promotion_stats": {key: value for key, value in promotion_stats.items() if key != "consumed_candidate_ids"},
        "verification_breakdown": build_result.validation.get("verification_status_counts", {}),
        "average_confidence_score": build_result.validation.get("average_confidence_score", 0.0),
        "verified_node_count": build_result.validation.get("verified_node_count", 0),
        "treasury_total_fetched": treasury_total is not None,
        "build_validation": _compact_validation(build_result.validation),
        "stage_errors": stage_errors,
        "stage_warnings": stage_warnings,
        "stage_results": stage_results,
        "all_fetch_stages_failed": False,
        "publication_blocked": False,
        "outputs": {
            "graph": str(build_result.graph_path),
            "expanded_nodes": str(build_result.nodes_path),
            "expanded_edges": str(build_result.edges_path),
            "candidate_nodes": str(candidate_path),
            "audit_report": str(audit_path),
        },
    }

    _write_stats(stats_path, stats)
    return stats


def main() -> int:
    stats = run_pipeline()
    print(format_pipeline_summary(stats))
    print(f"Wrote pipeline stats to {DEFAULT_STATS_OUTPUT}")
    return 1 if stats.get("all_fetch_stages_failed") or stats.get("publication_blocked") else 0


if __name__ == "__main__":
    raise SystemExit(main())
