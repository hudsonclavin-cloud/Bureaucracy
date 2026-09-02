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
import sys
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
)
from data_pipeline.json_io import write_json_file  # noqa: E402
from data_pipeline.run_pipeline import (  # noqa: E402
    AUDIT_REPORT_FILENAME,
    DEFAULT_STATS_OUTPUT,
    count_tree_nodes,
    usable_budget_total,
)
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
    graph_path = output_dir / DEFAULT_GRAPH_OUTPUT.name
    stats_path = output_dir / DEFAULT_STATS_OUTPUT.name
    audit_path = output_dir / AUDIT_REPORT_FILENAME

    result = build_graph(
        [{"nodes": [], "edges": [], "budgetSummary": anchor}],
        base_graph_path=args.base_graph,
        graph_output_path=graph_path,
        nodes_output_path=output_dir / DEFAULT_NODES_OUTPUT.name,
        edges_output_path=output_dir / DEFAULT_EDGES_OUTPUT.name,
        validity_report_output_path=output_dir / DEFAULT_VALIDITY_REPORT_OUTPUT.name,
        # The base graph is the whole input here. Re-feeding the previous
        # output would only re-import what this rebuild is replacing.
        reuse_existing_graph_payload=False,
        enforce_export_gate=True,
    )
    write_json_file(audit_path, result.validation.get("audit_report", {}))

    validation = dict(result.validation)
    validation["audit_report"] = {"summary": validation.get("audit_report", {}).get("summary", {})}
    validation["budget_summary_reused_from_previous_build"] = True

    def relative(path: Path) -> str:
        # Paths in a committed file are for a reader, not this machine.
        try:
            return str(Path(path).resolve().relative_to(PROJECT_ROOT))
        except ValueError:
            return str(path)
    node_count = count_tree_nodes(result.graph)
    base_count = count_tree_nodes(json.loads(Path(args.base_graph).read_text(encoding="utf-8")))
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
        "candidate_nodes_written": 0,
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
            "graph": relative(result.graph_path),
            "expanded_nodes": relative(result.nodes_path),
            "expanded_edges": relative(result.edges_path),
            "candidate_nodes": None,
            "audit_report": relative(audit_path),
        },
    }
    write_json_file(stats_path, stats)
    print(f"Rebuilt {node_count:,} nodes into {graph_path}")
    print(f"Anchor: {anchor.get('label') or anchor.get('record_date')} (reused from {args.anchor})")
    print()
    return run_release_gate(["validate_published_graph.py", str(graph_path)])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
