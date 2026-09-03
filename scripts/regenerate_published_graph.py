#!/usr/bin/env python3
"""Rebuild output/ from the curated base graph without any network access.

The crawlers need the network; the exporter does not. When the cascade, the
gate or the base graph changes, the published files must be regenerated even
where no crawl can run — this repository has needed exactly that three times.
This script rebuilds graph.json, expanded_nodes.json and expanded_edges.json
from data/federal_gov_complete_1.json and the Treasury anchor already carried
by the published graph, writes a pipeline_stats.json that says what it did,
then runs the release gate and exits nonzero if the result fails it.

Nothing here claims a fetch happened: the anchor in the rebuilt graph carries
`reused_from_previous_build: true`, and the stats file carries
`mode: offline_regeneration` and `treasury_total_fetched: false`.

Usage:
    python scripts/regenerate_published_graph.py [--anchor path/to/graph.json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.exporter.build_graph import (  # noqa: E402
    DEFAULT_BASE_GRAPH,
    DEFAULT_EDGES_OUTPUT,
    DEFAULT_GRAPH_OUTPUT,
    DEFAULT_NODES_OUTPUT,
    DEFAULT_VALIDITY_REPORT_OUTPUT,
    build_graph,
    extract_budget_summary,
    load_existing_graph_payload,
    walk_tree,
)
from data_pipeline.json_io import load_json_file, write_json_file  # noqa: E402
from data_pipeline.run_pipeline import (  # noqa: E402
    AUDIT_REPORT_FILENAME,
    DEFAULT_STATS_OUTPUT,
    count_tree_nodes,
    usable_budget_total,
)
from scripts.repair_review_queue import load_published_names, repair as repair_review_queue  # noqa: E402
from scripts.validate_published_graph import main as run_release_gate  # noqa: E402


def load_anchor(anchor_path: Path) -> dict:
    payload = load_existing_graph_payload(anchor_path)
    summary = extract_budget_summary([payload])
    if summary is None or usable_budget_total({"budgetSummary": summary}) is None:
        raise SystemExit(f"No usable Treasury budget summary in {anchor_path}; nothing to anchor the cascade on.")
    anchor = dict(summary)
    anchor["reused_from_previous_build"] = True
    return anchor


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--anchor", type=Path, default=DEFAULT_GRAPH_OUTPUT, help="graph.json to take the Treasury anchor from")
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_GRAPH_OUTPUT.parent)
    args = parser.parse_args(argv[1:])

    anchor = load_anchor(args.anchor)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = output_dir / "candidate_nodes.json"
    # Build somewhere else first. build_graph writes as it goes, so building
    # straight into output/ left a gate-failing graph on disk next to the
    # exit code that said not to publish it.
    with tempfile.TemporaryDirectory(prefix="regen-", dir=str(output_dir)) as staging:
        staging_dir = Path(staging)
        graph_path = staging_dir / DEFAULT_GRAPH_OUTPUT.name
        stats_path = staging_dir / DEFAULT_STATS_OUTPUT.name
        audit_path = staging_dir / AUDIT_REPORT_FILENAME
        result = build_graph(
            [{"nodes": [], "edges": [], "budgetSummary": anchor}],
            base_graph_path=args.base_graph,
            graph_output_path=graph_path,
            nodes_output_path=staging_dir / DEFAULT_NODES_OUTPUT.name,
            edges_output_path=staging_dir / DEFAULT_EDGES_OUTPUT.name,
            validity_report_output_path=staging_dir / DEFAULT_VALIDITY_REPORT_OUTPUT.name,
            # The previous graph is re-fed so nodes a crawl earned survive a
            # rebuild; base nodes without crawler provenance are not
            # re-imported (build_graph drops them), the base file supplies those.
            reuse_existing_graph_payload=True,
            existing_graph_payload_path=args.anchor,
            enforce_export_gate=True,
        )
        write_json_file(audit_path, result.validation.get("audit_report", {}))
        queue_report = None
        if candidate_path.exists():
            # The queue is served next to the graph; a regeneration repairs it
            # against the graph it will sit beside (see repair_review_queue.py).
            records = json.loads(candidate_path.read_text(encoding="utf-8"))
            published_names, ids_by_name = load_published_names(graph_path)
            kept, queue_report = repair_review_queue(records, published_names=published_names, ids_by_name=ids_by_name)
            write_json_file(staging_dir / candidate_path.name, kept)
        code = _finish(args, result, anchor, staging_dir, output_dir, stats_path, audit_path, candidate_path, queue_report)
    return code


def _finish(args, result, anchor, staging_dir: Path, output_dir: Path, stats_path: Path, audit_path: Path, candidate_path: Path, queue_report) -> int:

    validation = dict(result.validation)
    validation["audit_report"] = {"summary": validation.get("audit_report", {}).get("summary", {})}
    validation["budget_summary_reused_from_previous_build"] = True
    # build_graph's counters describe the payload (crawler-earned nodes only);
    # the published tree gets its own explicit keys rather than relabelled ones.
    published_count = count_tree_nodes(result.graph)
    validation["published_node_count"] = published_count
    validation["treasury_lines_carried_forward"] = sum(
        1 for node, _ in walk_tree(result.graph) if str(node.get("budget_source") or "").startswith("Treasury")
    )

    def relative(path: Path) -> str:
        # Paths in a committed file are for a reader, not this machine.
        try:
            return str(Path(path).resolve().relative_to(PROJECT_ROOT))
        except ValueError:
            return str(path)
    node_count = count_tree_nodes(result.graph)
    base_count = count_tree_nodes(json.loads(Path(args.base_graph).read_text(encoding="utf-8")))
    previous = load_json_file(args.anchor, default_factory=dict)
    published_before = count_tree_nodes(previous) if isinstance(previous, dict) and previous.get("id") else None
    stats = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "mode": "offline_regeneration",
        "note": (
            "Rebuilt from the curated base graph and the Treasury anchor already "
            "published; no crawler ran. See scripts/regenerate_published_graph.py."
        ),
        "nodes_before": base_count,
        "nodes_after": node_count,
        "new_nodes_added": max(0, node_count - base_count),
        "nodes_delta": node_count - base_count,
        "published_nodes_before": published_before,
        "nodes_delta_vs_published": (node_count - published_before) if published_before is not None else None,
        "candidate_nodes_written": queue_report["output_records"] if queue_report else 0,
        "review_queue_repair": queue_report,
        "promoted_nodes_written": 0,
        "promotion_stats": {},
        "verification_breakdown": validation.get("verification_status_counts", {}),
        "average_confidence_score": validation.get("average_confidence_score", 0.0),
        "verified_node_count": validation.get("verified_node_count", 0),
        "treasury_total_fetched": False,
        "build_validation": validation,
        "stage_errors": [],
        "stage_results": {"offline_regeneration": "data"},
        "all_fetch_stages_failed": False,
        "publication_blocked": False,
        "outputs": {
            "graph": relative(output_dir / result.graph_path.name),
            "expanded_nodes": relative(output_dir / result.nodes_path.name),
            "expanded_edges": relative(output_dir / result.edges_path.name),
            "candidate_nodes": relative(candidate_path) if candidate_path.exists() else None,
            "audit_report": relative(output_dir / audit_path.name) + " (untracked diagnostic)",
        },
    }
    write_json_file(stats_path, stats)
    print(f"Rebuilt {node_count:,} nodes (staged in {staging_dir})")
    if queue_report:
        print(f"Review queue: {queue_report['input_records']:,} -> {queue_report['output_records']:,} records; dropped {queue_report['dropped']}")
    print(f"Anchor: {anchor.get('label') or anchor.get('record_date')} (reused from {args.anchor})")
    print()
    code = run_release_gate(["validate_published_graph.py", str(result.graph_path)])
    if code != 0:
        print(f"\nNot published: {output_dir} left untouched.")
        return code
    # The graph and the queue the site fetches go last, together; if the
    # loop dies on a diagnostic file the served pair is still the old pair.
    staged_files = sorted(staging_dir.iterdir(), key=lambda p: (p.name in {"graph.json", "candidate_nodes.json"}, p.name))
    for staged in staged_files:
        os.replace(staged, output_dir / staged.name)
    print(f"\nPublished to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
