from __future__ import annotations

import json
import re
import sys
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.processors.normalize_edges import EdgeRegistry
from data_pipeline.json_io import load_json_file, write_json_file
from data_pipeline.processors.normalize_nodes import (
    NodeRegistry,
    load_existing_node_ids,
    merge_node,
    verify_node_sources,
)
from data_pipeline.validators.cost_validator import CostValidator
from data_pipeline.validators.node_requirements import NodeRequirements, generate_audit_report


DEFAULT_BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"
DEFAULT_GRAPH_OUTPUT = DEFAULT_OUTPUT_DIR / "graph.json"
DEFAULT_MIN_GRAPH_OUTPUT = DEFAULT_OUTPUT_DIR / "graph.min.json"
DEFAULT_NODES_OUTPUT = DEFAULT_OUTPUT_DIR / "expanded_nodes.json"
DEFAULT_EDGES_OUTPUT = DEFAULT_OUTPUT_DIR / "expanded_edges.json"
DEFAULT_VALIDITY_REPORT_OUTPUT = DEFAULT_OUTPUT_DIR / "node_validity_report.json"
HIERARCHICAL_RELATIONSHIPS = {"reports_to", "subsidiary_of"}
COST_NUMBER_PATTERN = re.compile(r"(-?\d[\d,]*(?:\.\d+)?)\s*(trillion|billion|million|thousand|t|b|m|k)?", re.IGNORECASE)
COST_EXPORT_FIELDS = (
    "resolved_total_amount",
    "cost_status",
    "cost_basis",
    "cost_validation",
    "costVerificationStatus",
    "costConfidenceScore",
    "costVerificationReason",
    "costSourceCount",
)
DERIVED_NODE_TYPE_KEYWORDS = (
    "office",
    "division",
    "position",
    "role",
    "staff",
    "employee",
    "leadership",
)


@dataclass
class BuildResult:
    nodes: list[dict[str, Any]]
    edges: list[dict[str, str]]
    graph: dict[str, Any]
    graph_path: Path
    min_graph_path: Path | None
    nodes_path: Path
    edges_path: Path
    validation: dict[str, Any]
    validity_report_path: Path | None = None


def iter_payload_items(payloads: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    for payload in payloads:
        if isinstance(payload, dict):
            yield payload


def count_payload_nodes(payloads: Iterable[dict[str, Any]]) -> int:
    total = 0
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        total += sum(1 for node in payload.get("nodes", []) if isinstance(node, dict))
    return total


def extract_budget_summary(payloads: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    selected_summary: dict[str, Any] | None = None
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        summary = payload.get("budgetSummary")
        if isinstance(summary, dict) and summary.get("government_total_outlay_amount") is not None:
            selected_summary = dict(summary)
    return selected_summary


def format_pipeline_summary(summary: dict[str, int]) -> str:
    return "\n".join(
        [
            "PIPELINE SUMMARY",
            "----------------",
            f"Initial node count: {summary['initial_node_count']}",
            f"Raw nodes loaded: {summary['raw_nodes_loaded']}",
            f"After normalization: {summary['nodes_after_normalization']}",
            f"After merge: {summary['nodes_after_merge']}",
            f"Nodes removed missing parent: {summary['nodes_removed_missing_parent']}",
            f"Nodes reattached to root: {summary['nodes_reattached_to_root']}",
            f"Nodes removed structural errors: {summary['nodes_removed_structural_errors']}",
            f"Final node count: {summary['final_node_count']}",
        ]
    )


def build_parent_index(edges: list[dict[str, str]]) -> dict[str, str]:
    parent_by_child: dict[str, str] = {}
    for edge in edges:
        if edge["type"] not in HIERARCHICAL_RELATIONSHIPS:
            continue
        parent_by_child.setdefault(edge["source"], edge["target"])
    return parent_by_child


def split_hierarchical_edges(edges: list[dict[str, str]], parent_by_child: dict[str, str]) -> list[dict[str, str]]:
    exported_edges: list[dict[str, str]] = []
    for edge in edges:
        if edge["type"] in HIERARCHICAL_RELATIONSHIPS and parent_by_child.get(edge["source"]) == edge["target"]:
            continue
        exported_edges.append(edge)
    return exported_edges


def load_base_graph(base_graph_path: str | Path) -> dict[str, Any]:
    path = Path(base_graph_path)
    if path.exists():
        payload = load_json_file(path, default_factory=dict)
        if isinstance(payload, dict):
            return payload
    return {
        "id": "root",
        "name": "Root",
        "type": "Foundation",
        "color": "#c8a84a",
        "desc": "Root of the graph.",
        "children": [],
    }


def load_existing_graph_payload(graph_path: str | Path) -> dict[str, Any]:
    path = Path(graph_path)
    if not path.exists():
        return {"nodes": [], "edges": []}

    payload = load_json_file(path, default_factory=dict)
    if not isinstance(payload, dict):
        return {"nodes": [], "edges": []}

    nodes: list[dict[str, Any]] = []
    for node, parent in walk_tree(payload):
        normalized = deepcopy(node)
        normalized["children"] = []
        if parent and parent.get("id"):
            normalized["parentId"] = str(parent["id"])
        nodes.append(normalized)

    edges = list(payload.get("relationships", [])) if isinstance(payload.get("relationships"), list) else []
    result: dict[str, Any] = {"nodes": nodes, "edges": edges}
    budget_summary = payload.get("__budgetSummary") or payload.get("budgetSummary")
    if isinstance(budget_summary, dict):
        result["budgetSummary"] = budget_summary
    return result


MINIMAL_GRAPH_FIELDS = (
    "id",
    "name",
    "type",
    "color",
    "children",
    "resolved_total_amount",
)


def prune_graph_for_viewer(node: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        key: deepcopy(node[key]) for key in MINIMAL_GRAPH_FIELDS if key in node
    }
    children: list[dict[str, Any]] = []
    for child in node.get("children", []):
        if isinstance(child, dict):
            children.append(prune_graph_for_viewer(child))
    result["children"] = children
    return result


def is_placeholder_generated_node(node: dict[str, Any], *, existing_ids: set[str]) -> bool:
    node_id = str(node.get("id") or "").strip()
    node_name = str(node.get("name") or "").strip()
    if node_id in existing_ids:
        return False
    return node_id == "unnamed-node" and node_name == "Unnamed Node"


def walk_tree(root: dict[str, Any]) -> Iterable[tuple[dict[str, Any], dict[str, Any] | None]]:
    stack: list[tuple[dict[str, Any], dict[str, Any] | None]] = [(root, None)]
    while stack:
        current, parent = stack.pop()
        yield current, parent
        children = [child for child in current.get("children", []) if isinstance(child, dict)]
        stack.extend((child, current) for child in reversed(children))


def index_tree(root: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    node_map: dict[str, dict[str, Any]] = {}
    parent_map: dict[str, str] = {}
    for node, parent in walk_tree(root):
        node_id = str(node.get("id") or "").strip()
        if not node_id:
            continue
        node_map[node_id] = node
        if parent and parent.get("id"):
            parent_map[node_id] = str(parent["id"])
    return node_map, parent_map


def safe_attach_child(
    parent: dict[str, Any],
    child: dict[str, Any],
    *,
    parent_map: dict[str, str],
) -> bool:
    parent_id = str(parent.get("id") or "").strip()
    child_id = str(child.get("id") or "").strip()
    if not parent_id or not child_id or parent_id == child_id:
        return False
    if any(str(existing.get("id") or "") == child_id for existing in parent.get("children", [])):
        parent_map[child_id] = parent_id
        return True

    if child_id in parent_map:
        # Already attached elsewhere in the tree; attaching again duplicates the subtree.
        return False

    cursor_id = parent_id
    while cursor_id:
        if cursor_id == child_id:
            return False
        cursor_id = parent_map.get(cursor_id, "")

    parent.setdefault("children", []).append(child)
    parent_map[child_id] = parent_id
    return True


def build_graph_tree(
    *,
    base_graph_path: str | Path,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, str]],
    stats: dict[str, int] | None = None,
) -> dict[str, Any]:
    root = deepcopy(load_base_graph(base_graph_path))
    node_map, parent_map = index_tree(root)
    root_id = str(root.get("id") or "root")
    cycle_fallback_root_attachments = 0

    for node in nodes:
        normalized_node = dict(node)
        normalized_node["children"] = []
        node_id = normalized_node["id"]
        existing = node_map.get(node_id)
        if existing:
            merge_node(existing, normalized_node)
        else:
            node_map[node_id] = normalized_node

    for node in nodes:
        node_id = node["id"]
        attached_node = node_map[node_id]
        parent_id = str(node.get("parentId") or "").strip()
        if parent_id and parent_id in node_map and parent_id != node_id:
            if safe_attach_child(node_map[parent_id], attached_node, parent_map=parent_map):
                attached_node["parentId"] = parent_id
                attached_node.pop("attachToRoot", None)
            elif node_id in parent_map:
                # Node already lives in the tree; keep that placement, drop the stale hint.
                attached_node.pop("parentId", None)
                attached_node.pop("attachToRoot", None)
            elif node_id != root_id and safe_attach_child(root, attached_node, parent_map=parent_map):
                # Attaching under the named parent would create a cycle. Falling back to
                # root keeps the cluster in the tree rather than dropping it silently.
                attached_node.pop("parentId", None)
                attached_node.pop("attachToRoot", None)
                cycle_fallback_root_attachments += 1
            continue
        if node.get("attachToRoot") and node_id != root_id:
            safe_attach_child(root, attached_node, parent_map=parent_map)

    if stats is not None:
        stats["cycle_fallback_root_attachments"] = cycle_fallback_root_attachments

    root["relationships"] = list(edges)
    return root


def round_currency(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def parse_cost_amount(value: Any) -> float | None:
    if value in (None, "", "null"):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    matches = COST_NUMBER_PATTERN.findall(text.replace("$", " "))
    if matches:
        parsed_values: list[float] = []
        for number_text, suffix in matches:
            if not number_text:
                continue
            try:
                number = float(number_text.replace(",", ""))
            except ValueError:
                continue
            normalized_suffix = str(suffix or "").strip().lower()
            multiplier = {
                "k": 1e3,
                "thousand": 1e3,
                "m": 1e6,
                "million": 1e6,
                "b": 1e9,
                "billion": 1e9,
                "t": 1e12,
                "trillion": 1e12,
            }.get(normalized_suffix, 1.0)
            parsed_values.append(number * multiplier)
        if parsed_values:
            return max(parsed_values, key=abs)

    normalized = re.sub(r"[^0-9.\-]", "", text)
    if not normalized:
        return None
    try:
        return float(normalized)
    except ValueError:
        return None


def compute_subtree_sizes(root: dict[str, Any]) -> dict[str, int]:
    sizes: dict[str, int] = {}

    def visit(node: dict[str, Any]) -> int:
        total = 1
        for child in node.get("children", []):
            if isinstance(child, dict):
                total += visit(child)
        node_id = str(node.get("id") or "").strip()
        if node_id:
            sizes[node_id] = total
        return total

    visit(root)
    return sizes


def normalize_type_key(value: Any) -> str:
    return str(value or "").strip().lower()


def is_derived_node_type(node: dict[str, Any]) -> bool:
    type_name = normalize_type_key(node.get("type"))
    return any(keyword in type_name for keyword in DERIVED_NODE_TYPE_KEYWORDS)


def annotate_proof_tree(
    node: dict[str, Any],
    *,
    parent_is_proven: bool,
    is_root: bool = False,
    trusted_node_ids: set[str] | None = None,
    prune_unproven: bool = True,
) -> tuple[dict[str, int], bool]:
    verify_node_sources(node)
    trusted_node_ids = trusted_node_ids or set()
    node_id = str(node.get("id") or "").strip()
    is_trusted_baseline = node_id in trusted_node_ids
    node["parentProven"] = bool(parent_is_proven)
    direct_proven = bool(node.get("existsProven"))
    proof_source_count = int(node.get("proofSourceCount") or 0)

    if is_root:
        node["existsProven"] = True
        node["parentProven"] = True
        node["proofStatus"] = "root"
        node["proofReason"] = "graph_root"
        keep_node = True
    elif direct_proven:
        node["proofStatus"] = "proven"
        node["proofReason"] = node.get("proofReason") or "official_source_recorded"
        keep_node = True
    elif is_trusted_baseline:
        node["proofStatus"] = "baseline"
        node["proofReason"] = "trusted_base_graph"
        keep_node = True
    elif parent_is_proven and is_derived_node_type(node):
        node["proofStatus"] = "derived"
        node["proofReason"] = "derived_from_proven_parent"
        keep_node = True
    else:
        node["proofStatus"] = "unproven"
        if proof_source_count == 0:
            node["proofReason"] = "no_evidence_recorded"
        else:
            node["proofReason"] = "insufficient_direct_proof"
        keep_node = False

    counts = {str(node["proofStatus"]): 1}
    kept_children: list[dict[str, Any]] = []
    for child in node.get("children", []):
        if not isinstance(child, dict):
            continue
        child_counts, child_keep = annotate_proof_tree(
            child,
            parent_is_proven=keep_node,
            is_root=False,
            trusted_node_ids=trusted_node_ids,
            prune_unproven=prune_unproven,
        )
        for key, value in child_counts.items():
            counts[key] = counts.get(key, 0) + value
        if child_keep or not prune_unproven:
            kept_children.append(child)
    node["children"] = kept_children
    return counts, keep_node if prune_unproven else True


def filter_relationships_to_kept_nodes(root: dict[str, Any]) -> None:
    kept_node_ids = {
        str(node.get("id") or "").strip()
        for node, _ in walk_tree(root)
        if str(node.get("id") or "").strip()
    }
    relationships = root.get("relationships")
    if not isinstance(relationships, list):
        root["relationships"] = []
        return
    root["relationships"] = [
        edge
        for edge in relationships
        if isinstance(edge, dict)
        and str(edge.get("source") or "").strip() in kept_node_ids
        and str(edge.get("target") or "").strip() in kept_node_ids
    ]


def get_node_official_total(node: dict[str, Any]) -> float | None:
    return parse_cost_amount(node.get("rollup_total_amount"))


def get_node_weight(node: dict[str, Any], subtree_sizes: dict[str, int]) -> tuple[float, str]:
    for key, basis in (
        ("annual_budget", "annual_budget_weight"),
        ("budget", "budget_weight"),
        ("direct_outlay_amount", "direct_outlay_weight"),
    ):
        amount = parse_cost_amount(node.get(key))
        if amount is not None and amount != 0:
            return max(abs(amount), 1.0), basis

    employees = parse_cost_amount(node.get("employees"))
    if employees is not None and employees > 0:
        return max(abs(employees), 1.0), "employee_weight"

    node_id = str(node.get("id") or "").strip()
    subtree_weight = float(max(subtree_sizes.get(node_id, 1), 1))
    return subtree_weight, "subtree_weight"


def costs_nearly_equal(left: float | None, right: float | None, tolerance: float = 0.01) -> bool:
    if left is None or right is None:
        return False
    return abs(left - right) <= max(tolerance, max(abs(left), abs(right)) * 1e-9)


def official_rollups_exceed_total(official_sum: float, allocated_total: float | None) -> bool:
    if allocated_total is None or official_sum == 0:
        return False
    if official_sum > 0 and allocated_total >= 0:
        return official_sum > allocated_total
    if official_sum < 0 and allocated_total <= 0:
        return abs(official_sum) > abs(allocated_total)
    return False


def classify_cost_verification(
    node: dict[str, Any],
    *,
    has_budget_summary: bool,
) -> tuple[str, float, str, int]:
    cost_status = str(node.get("cost_status") or "unverified").strip().lower()
    cost_validation = str(node.get("cost_validation") or "").strip().lower()
    resolved_total = parse_cost_amount(node.get("resolved_total_amount"))
    official_total = get_node_official_total(node)
    budget_amount = parse_cost_amount(node.get("annual_budget"))
    if budget_amount is None:
        budget_amount = parse_cost_amount(node.get("budget"))

    if resolved_total is None or cost_status == "unavailable":
        return "unverified", 0.0, "missing_cost", 0
    if cost_status == "root_total":
        if has_budget_summary:
            return "verified", 1.0, "treasury_total_outlays", 1
        return "partial", 0.7, "summed_from_child_totals", 0
    if cost_status == "official":
        if official_total is not None:
            return "verified", 0.95, "matched_official_rollup", 1
        if budget_amount is not None:
            return "partial", 0.75, "matched_budget_record", 1
        return "partial", 0.7, cost_validation or "matched_official_rollup", 0
    if cost_status == "scaled_official":
        source_count = 1 if official_total is not None else 0
        return "partial", 0.72, "scaled_from_official_rollup", source_count
    if cost_status == "allocated":
        source_count = 1 if budget_amount is not None or official_total is not None else 0
        return "unverified", 0.35 if source_count else 0.2, "estimated_from_parent", source_count
    return "unverified", 0.0, cost_validation or "unknown_cost_verification", 0


def prune_tree_to_allowed_ids(
    node: dict[str, Any],
    allowed_ids: set[str],
    *,
    is_root: bool = False,
) -> list[dict[str, Any]]:
    promoted_children: list[dict[str, Any]] = []
    for child in list(node.get("children", [])):
        if isinstance(child, dict):
            promoted_children.extend(prune_tree_to_allowed_ids(child, allowed_ids, is_root=False))
    node["children"] = promoted_children

    if is_root or node.get("id") in allowed_ids:
        return [node]
    return promoted_children


NAME_KEY_PARENTHETICAL_PATTERN = re.compile(r"\([^)]*\)")
NAME_KEY_NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")
NAME_KEY_US_PATTERN = re.compile(r"\bu s(?: a)?\b")


def canonical_name_key(value: Any) -> str:
    """Reduce a display name to a comparison key.

    Treasury/crawler records and the curated base graph name the same entity
    differently ("U.S. Fish & Wildlife Service (FWS)" vs "United States Fish
    and Wildlife Service"), so parentheticals, punctuation, "U.S." spelling,
    and leading articles must not affect equality.
    """
    text = str(value or "").casefold()
    text = NAME_KEY_PARENTHETICAL_PATTERN.sub(" ", text)
    text = text.replace("&", " and ")
    text = NAME_KEY_NON_ALNUM_PATTERN.sub(" ", text).strip()
    text = NAME_KEY_US_PATTERN.sub("united states", text)
    for prefix in ("the ", "united states "):
        if text.startswith(prefix):
            text = text[len(prefix):]
    return text.strip()


def merge_source_provenance(target: dict[str, Any], source: dict[str, Any]) -> None:
    for field_name in ("sourceUrls", "sourceTypes"):
        merged = [str(value) for value in (target.get(field_name) or []) if str(value)]
        for value in source.get(field_name) or []:
            text = str(value)
            if text and text not in merged:
                merged.append(text)
        if merged:
            target[field_name] = merged


REJECTED_NODE_SAMPLE_LIMIT = 200


def summarize_export_policy(policy: dict[str, Any], *, sample_limit: int = REJECTED_NODE_SAMPLE_LIMIT) -> dict[str, Any]:
    """Bound the per-node rejection detail kept in the published report.

    Thousands of rejected candidates would otherwise dominate the committed
    validity report; the counts stay exact while only a sample of node-level
    detail is retained.
    """
    rejected = policy.get("rejected_nodes") or []
    return {
        "summary": deepcopy(policy.get("summary", {})),
        "rejected_node_count": len(rejected),
        "rejected_nodes_sample": deepcopy(rejected[:sample_limit]),
    }


def drop_duplicate_child_rollups(root: dict[str, Any]) -> int:
    """Clear a node's Treasury rollup when an ancestor carries the same amount.

    Name-based merging can stamp one Treasury row onto several nodes (an
    agency and its same-named leadership position, or a branch total and the
    appropriations subcommittee named after it). A cent-exact match with an
    ancestor's rollup is that same row counted twice; the duplicate would
    oversubscribe the ancestor's total and force every sibling's official
    amount to be rescaled, so the descendant's copy is dropped before
    annotation and the ancestor stays authoritative.
    """
    dropped = 0

    def recurse(node: dict[str, Any], ancestor_rollups: frozenset[float]) -> None:
        nonlocal dropped
        rollup = parse_cost_amount(node.get("rollup_total_amount"))
        if rollup is not None:
            rollup = round(rollup, 2)
            if rollup in ancestor_rollups:
                node.pop("rollup_total_amount", None)
                dropped += 1
                rollup = None
        child_ancestors = ancestor_rollups if rollup is None else ancestor_rollups | {rollup}
        for child in node.get("children", []):
            if isinstance(child, dict):
                recurse(child, child_ancestors)

    recurse(root, frozenset())
    return dropped


def resolve_root_orphans(
    root: dict[str, Any],
    *,
    trusted_node_ids: set[str],
) -> dict[str, Any]:
    """Fold promoted crawler orphans at the root back into the canonical tree.

    Pruning promotes children of culled nodes upward, so crawler-derived slugs
    that duplicate base-graph entities (or belong beneath them) can land as
    direct children of the root. Duplicates by canonical name are merged into
    their counterpart; unmatched orphans are reattached under the canonical
    parent inferred from their id prefix, keeping the root's children limited
    to curated top-level structure.
    """
    root_id = str(root.get("id") or "")
    orphans = [
        child
        for child in root.get("children", [])
        if isinstance(child, dict)
        and str(child.get("id") or "")
        and str(child.get("id") or "") not in trusted_node_ids
    ]
    summary = {
        "root_orphans_processed": len(orphans),
        "duplicates_removed": 0,
        "orphans_reattached": 0,
    }
    result = {"summary": summary, "duplicates_removed": [], "orphans_reattached": []}
    if not orphans:
        return result

    orphan_ids = {str(child.get("id")) for child in orphans}
    root["children"] = [
        child
        for child in root.get("children", [])
        if not (isinstance(child, dict) and str(child.get("id") or "") in orphan_ids)
    ]

    node_map, parent_map = index_tree(root)
    name_index: dict[str, dict[str, Any]] = {}
    for node_id, node in node_map.items():
        if node_id == root_id:
            continue
        name_key = canonical_name_key(node.get("name"))
        if name_key and name_key not in name_index:
            name_index[name_key] = node

    def find_prefix_parent(node_id: str) -> dict[str, Any] | None:
        tokens = [token for token in node_id.split("-") if token]
        for cut in range(len(tokens) - 1, 1, -1):
            counterpart = name_index.get(canonical_name_key(" ".join(tokens[:cut])))
            if counterpart is not None:
                return counterpart
        return None

    queue: list[tuple[dict[str, Any], dict[str, Any]]] = [(orphan, root) for orphan in orphans]
    while queue:
        node, fallback_parent = queue.pop(0)
        node_id = str(node.get("id") or "")
        name_key = canonical_name_key(node.get("name"))
        counterpart = name_index.get(name_key) if name_key else None
        if counterpart is not None and str(counterpart.get("id") or "") != node_id:
            merge_source_provenance(counterpart, node)
            for child in node.get("children", []):
                if isinstance(child, dict):
                    queue.append((child, counterpart))
            node["children"] = []
            result["duplicates_removed"].append(
                {"id": node_id, "name": node.get("name"), "merged_into": counterpart.get("id")}
            )
            continue

        parent = find_prefix_parent(node_id) or fallback_parent
        if not safe_attach_child(parent, node, parent_map=parent_map):
            parent = root
            safe_attach_child(root, node, parent_map=parent_map)
        parent_id = str(parent.get("id") or "")
        if parent_id == root_id:
            # Root attachment is expressed by `attachToRoot`, not by a parentId
            # pointing at the root. Setting both makes the node look like it has
            # a discovered reporting line to the Constitution.
            node.pop("parentId", None)
            node["attachToRoot"] = True
        else:
            node["parentId"] = parent_id
        node_map[node_id] = node
        if name_key and name_key not in name_index:
            name_index[name_key] = node
        if parent_id != root_id:
            result["orphans_reattached"].append(
                {"id": node_id, "name": node.get("name"), "attached_to": parent_id}
            )

    summary["duplicates_removed"] = len(result["duplicates_removed"])
    summary["orphans_reattached"] = len(result["orphans_reattached"])
    return result


def annotate_resolved_costs(
    root: dict[str, Any],
    *,
    budget_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    subtree_sizes = compute_subtree_sizes(root)
    budget_total = parse_cost_amount((budget_summary or {}).get("government_total_outlay_amount"))

    if budget_total is None:
        child_totals = [amount for amount in (get_node_official_total(child) for child in root.get("children", [])) if amount is not None]
        budget_total = sum(child_totals) if child_totals else None

    def recurse(
        node: dict[str, Any],
        allocated_total: float | None,
        *,
        inherited_basis: str | None,
        inherited_validation: str | None,
        is_root: bool = False,
    ) -> None:
        official_total = get_node_official_total(node)
        node["resolved_total_amount"] = round_currency(allocated_total)

        if is_root:
            node["cost_status"] = "root_total" if allocated_total is not None else "unavailable"
            node["cost_basis"] = "treasury_total_outlays" if budget_summary else "summed_child_official_totals"
            node["cost_validation"] = "verified_with_treasury_total" if budget_summary else "summed_from_child_totals"
        elif allocated_total is None:
            node["cost_status"] = "unavailable"
            node["cost_basis"] = inherited_basis
            node["cost_validation"] = inherited_validation or "missing_cost"
        elif official_total is not None and costs_nearly_equal(allocated_total, official_total):
            node["cost_status"] = "official"
            node["cost_basis"] = "treasury_rollup"
            node["cost_validation"] = "matched_official_rollup"
        elif official_total is not None:
            node["cost_status"] = "scaled_official"
            node["cost_basis"] = "treasury_rollup"
            node["cost_validation"] = inherited_validation or "scaled_to_parent_total"
        else:
            node["cost_status"] = "allocated"
            node["cost_basis"] = inherited_basis or "equal_split"
            node["cost_validation"] = inherited_validation or "estimated_from_parent"

        children = [child for child in node.get("children", []) if isinstance(child, dict)]
        if not children or allocated_total is None:
            return

        anchored_children: list[tuple[dict[str, Any], float]] = []
        weighted_children: list[tuple[dict[str, Any], float, str]] = []
        for child in children:
            official_child_total = get_node_official_total(child)
            if official_child_total is not None:
                anchored_children.append((child, official_child_total))
            else:
                weight, weight_basis = get_node_weight(child, subtree_sizes)
                weighted_children.append((child, weight, weight_basis))

        official_child_sum = sum(amount for _, amount in anchored_children)
        anchor_scale = 1.0
        scaled_to_fit_parent = False
        if anchored_children and official_rollups_exceed_total(official_child_sum, allocated_total):
            anchor_scale = abs(allocated_total) / abs(official_child_sum) if official_child_sum else 1.0
            scaled_to_fit_parent = True

        assigned_anchor_total = sum(amount * anchor_scale for _, amount in anchored_children)
        remainder_total = allocated_total - assigned_anchor_total

        total_weight = sum(weight for _, weight, _ in weighted_children) or float(len(weighted_children) or 1)
        weighted_remaining = len(weighted_children)
        remainder_left = remainder_total
        for child, weight, weight_basis in weighted_children:
            weighted_remaining -= 1
            if weighted_remaining <= 0:
                child_total = remainder_left
            else:
                child_total = remainder_total * (weight / total_weight)
                remainder_left -= child_total
            recurse(
                child,
                child_total,
                inherited_basis=weight_basis,
                inherited_validation="estimated_from_parent",
            )

        for child, official_child_total in anchored_children:
            recurse(
                child,
                official_child_total * anchor_scale,
                inherited_basis="treasury_rollup",
                inherited_validation="scaled_to_parent_total" if scaled_to_fit_parent else "matched_official_rollup",
            )

    recurse(
        root,
        budget_total,
        inherited_basis="treasury_total_outlays",
        inherited_validation="verified_with_treasury_total",
        is_root=True,
    )

    validity_nodes: list[dict[str, Any]] = []
    verification_status_counts: dict[str, int] = {}
    cost_status_counts: dict[str, int] = {}
    cost_validation_counts: dict[str, int] = {}
    cost_verification_status_counts: dict[str, int] = {}
    nodes_with_sources = 0
    nodes_without_sources = 0
    resolved_cost_node_count = 0
    unresolved_cost_node_count = 0
    estimated_cost_node_count = 0
    official_cost_node_count = 0
    verified_cost_node_count = 0
    partial_cost_node_count = 0
    unverified_cost_node_count = 0
    proof_status_counts: dict[str, int] = {}

    for node, parent in walk_tree(root):
        verification_status = str(node.get("verificationStatus") or "unverified")
        cost_status = str(node.get("cost_status") or "unavailable")
        cost_validation = str(node.get("cost_validation") or "missing_cost")
        proof_status = str(node.get("proofStatus") or "unproven")
        cost_verification_status, cost_confidence_score, cost_verification_reason, cost_source_count = classify_cost_verification(
            node,
            has_budget_summary=budget_summary is not None,
        )
        node["costVerificationStatus"] = cost_verification_status
        node["costConfidenceScore"] = cost_confidence_score
        node["costVerificationReason"] = cost_verification_reason
        node["costSourceCount"] = cost_source_count
        verification_status_counts[verification_status] = verification_status_counts.get(verification_status, 0) + 1
        cost_status_counts[cost_status] = cost_status_counts.get(cost_status, 0) + 1
        cost_validation_counts[cost_validation] = cost_validation_counts.get(cost_validation, 0) + 1
        cost_verification_status_counts[cost_verification_status] = cost_verification_status_counts.get(cost_verification_status, 0) + 1
        proof_status_counts[proof_status] = proof_status_counts.get(proof_status, 0) + 1

        source_count = int(node.get("sourceCount") or 0)
        if source_count > 0:
            nodes_with_sources += 1
        else:
            nodes_without_sources += 1

        resolved_total = node.get("resolved_total_amount")
        if resolved_total is not None:
            resolved_cost_node_count += 1
        else:
            unresolved_cost_node_count += 1

        if cost_status in {"allocated", "scaled_official"}:
            estimated_cost_node_count += 1
        if cost_status in {"official", "root_total"}:
            official_cost_node_count += 1
        if cost_verification_status == "verified":
            verified_cost_node_count += 1
        elif cost_verification_status == "partial":
            partial_cost_node_count += 1
        else:
            unverified_cost_node_count += 1

        issues: list[str] = []
        if source_count == 0:
            issues.append("no_sources")
        if verification_status == "unverified":
            issues.append("unverified")
        if proof_status == "unproven":
            issues.append("unsupported_node")
        if cost_status == "unavailable":
            issues.append("missing_cost")
        elif cost_status != "official" and cost_status != "root_total":
            issues.append("estimated_cost")
        if cost_verification_status == "partial":
            issues.append("cost_partially_verified")
        elif cost_verification_status == "unverified" and resolved_total is not None:
            issues.append("cost_unverified")

        validity_nodes.append(
            {
                "id": node.get("id"),
                "name": node.get("name"),
                "type": node.get("type"),
                "parentId": parent.get("id") if isinstance(parent, dict) else None,
                "verificationStatus": verification_status,
                "confidenceScore": node.get("confidenceScore"),
                "sourceCount": source_count,
                "proofStatus": proof_status,
                "proofReason": node.get("proofReason"),
                "proofSourceCount": node.get("proofSourceCount"),
                "resolved_total_amount": resolved_total,
                "rollup_total_amount": node.get("rollup_total_amount"),
                "cost_status": cost_status,
                "cost_basis": node.get("cost_basis"),
                "cost_validation": cost_validation,
                "costVerificationStatus": cost_verification_status,
                "costConfidenceScore": cost_confidence_score,
                "costVerificationReason": cost_verification_reason,
                "costSourceCount": cost_source_count,
                "issues": issues,
            }
        )

    return {
        "summary": {
            "verified_treasury_total": round_currency(budget_total),
            "verification_status_counts": verification_status_counts,
            "cost_status_counts": cost_status_counts,
            "cost_validation_counts": cost_validation_counts,
            "cost_verification_status_counts": cost_verification_status_counts,
            "proof_status_counts": proof_status_counts,
            "nodes_with_sources": nodes_with_sources,
            "nodes_without_sources": nodes_without_sources,
            "resolved_cost_node_count": resolved_cost_node_count,
            "unresolved_cost_node_count": unresolved_cost_node_count,
            "estimated_cost_node_count": estimated_cost_node_count,
            "official_cost_node_count": official_cost_node_count,
            "verified_cost_node_count": verified_cost_node_count,
            "partial_cost_node_count": partial_cost_node_count,
            "unverified_cost_node_count": unverified_cost_node_count,
        },
        "nodes": validity_nodes,
    }


def validate_and_prepare_graph(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, str]],
    *,
    existing_ids: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, Any]]:
    node_ids = {node["id"] for node in nodes}
    all_known_ids = node_ids | set(existing_ids)
    kept_nodes: list[dict[str, Any]] = []
    kept_edges: list[dict[str, str]] = []

    relationship_counts: dict[str, int] = {}
    related_node_ids: set[str] = set()
    orphaned_parent_ids = 0
    orphan_nodes_detected = 0
    dropped_edges_missing_source = 0
    dropped_edges_missing_target = 0
    verification_status_counts: dict[str, int] = {}
    structural_error_nodes_removed = 0
    assigned_parent_by_child: dict[str, str] = {}

    for edge in edges:
        relationship_counts[edge["type"]] = relationship_counts.get(edge["type"], 0) + 1
        source_known = edge["source"] in all_known_ids
        target_known = edge["target"] in all_known_ids
        if not source_known:
            dropped_edges_missing_source += 1
            continue
        if not target_known:
            dropped_edges_missing_target += 1
            continue
        kept_edges.append(edge)
        related_node_ids.add(edge["source"])
        related_node_ids.add(edge["target"])

    parent_by_child = build_parent_index(kept_edges)
    root_attached_missing_parent_nodes = 0
    explicitly_root_attached_nodes = 0

    for node in nodes:
        prepared = verify_node_sources(dict(node))
        if is_placeholder_generated_node(prepared, existing_ids=existing_ids):
            structural_error_nodes_removed += 1
            continue

        node_already_in_tree = prepared["id"] in existing_ids
        parent_id = prepared.get("parentId") or parent_by_child.get(prepared["id"])
        # A node that names a parent we have not discovered yet is a frontier
        # node: the reporting line is evidenced, the target simply is not in the
        # graph. That is materially different from a node that references
        # nothing at all, and the two must not share a fate.
        had_unresolvable_parent_reference = False

        if node_already_in_tree:
            prepared.pop("parentId", None)
        elif parent_id:
            if parent_id == prepared["id"] or parent_id not in all_known_ids:
                orphaned_parent_ids += 1
                orphan_nodes_detected += 1
                had_unresolvable_parent_reference = True
                prepared.pop("parentId", None)
                fallback_parent = parent_by_child.get(prepared["id"])
                if (
                    fallback_parent
                    and fallback_parent != parent_id
                    and fallback_parent != prepared["id"]
                ):
                    prepared["parentId"] = fallback_parent
                    assigned_parent_by_child[prepared["id"]] = fallback_parent
            else:
                prepared["parentId"] = parent_id
                assigned_parent_by_child[prepared["id"]] = parent_id
        else:
            prepared.pop("parentId", None)

        explicitly_attached_to_root = False
        if "attachToRoot" in prepared:
            prepared["attachToRoot"] = bool(prepared["attachToRoot"])
            explicitly_attached_to_root = prepared["attachToRoot"]
            if explicitly_attached_to_root:
                explicitly_root_attached_nodes += 1

        if node_already_in_tree:
            prepared.pop("attachToRoot", None)
        elif "parentId" not in prepared:
            if (
                prepared["id"] in related_node_ids
                or explicitly_attached_to_root
                or had_unresolvable_parent_reference
            ):
                prepared["attachToRoot"] = True
            else:
                # A node whose parent cannot be resolved is not evidence of an
                # organisational unit hanging off the Constitution — it is a node
                # we failed to place. Bolting it to the root produces a
                # meaningless orphan pile and asserts a reporting line no source
                # supports. Drop it and count it; the count is published.
                root_attached_missing_parent_nodes += 1
                continue

        kept_nodes.append(prepared)
        status = prepared.get("verificationStatus", "unverified")
        verification_status_counts[status] = verification_status_counts.get(status, 0) + 1

    # Primary hierarchical edges become parentId fields; split them out only after
    # they have been counted and endpoint-validated above.
    kept_edges = split_hierarchical_edges(kept_edges, assigned_parent_by_child)

    validation = {
        "initial_node_count": len(nodes),
        "input_node_count": len(nodes),
        "input_edge_count": len(edges),
        "exported_node_count": len(kept_nodes),
        "exported_edge_count": len(kept_edges),
        "nodes_removed_missing_parent": 0,
        "nodes_reattached_to_root": sum(1 for node in kept_nodes if node.get("attachToRoot")),
        "nodes_removed_structural_errors": structural_error_nodes_removed,
        "final_node_count": len(kept_nodes),
        "orphan_nodes_detected": orphan_nodes_detected,
        "recovered_orphan_nodes": root_attached_missing_parent_nodes,
        "root_attached_missing_parent_nodes": root_attached_missing_parent_nodes,
        "dropped_edges_missing_source": dropped_edges_missing_source,
        "dropped_edges_missing_target": dropped_edges_missing_target,
        "orphaned_parent_ids": orphaned_parent_ids,
        "attached_to_root": sum(1 for node in kept_nodes if node.get("attachToRoot")),
        "explicitly_root_attached_nodes": explicitly_root_attached_nodes,
        "relationship_counts": relationship_counts,
        "verification_status_counts": verification_status_counts,
        "verified_node_count": verification_status_counts.get("verified", 0),
        "dropped_placeholder_nodes": structural_error_nodes_removed,
        "average_confidence_score": round(
            sum(float(node.get("confidenceScore") or 0.0) for node in kept_nodes) / max(len(kept_nodes), 1),
            2,
        ),
    }
    return kept_nodes, kept_edges, validation


def build_graph(
    payloads: Iterable[dict[str, Any]],
    *,
    base_graph_path: str | Path = DEFAULT_BASE_GRAPH,
    graph_output_path: str | Path = DEFAULT_GRAPH_OUTPUT,
    min_graph_output_path: str | Path | None = None,
    nodes_output_path: str | Path = DEFAULT_NODES_OUTPUT,
    edges_output_path: str | Path = DEFAULT_EDGES_OUTPUT,
    validity_report_output_path: str | Path = DEFAULT_VALIDITY_REPORT_OUTPUT,
    reuse_existing_graph_payload: bool = True,
    existing_graph_payload_path: str | Path | None = None,
    enforce_export_gate: bool = True,
) -> BuildResult:
    payload_list = list(iter_payload_items(payloads))
    if reuse_existing_graph_payload:
        existing_graph_payload = load_existing_graph_payload(existing_graph_payload_path or graph_output_path)
        if existing_graph_payload["nodes"] or existing_graph_payload["edges"]:
            payload_list.insert(0, existing_graph_payload)
    raw_nodes_loaded = count_payload_nodes(payload_list)
    existing_ids = load_existing_node_ids(base_graph_path)
    node_registry = NodeRegistry(existing_ids=set(existing_ids))
    edge_registry = EdgeRegistry()
    normalized_node_count = 0

    for payload in payload_list:
        normalized_nodes = node_registry.add_many(payload.get("nodes", []))
        normalized_node_count += len(normalized_nodes)
        edge_registry.add_many(payload.get("edges", []))

    raw_edges = edge_registry.values()
    parent_by_child = build_parent_index(raw_edges)
    nodes = node_registry.values()
    merged_node_count = len(nodes)
    for node in nodes:
        parent_id = parent_by_child.get(node["id"])
        if parent_id and parent_id != node["id"]:
            node["parentId"] = parent_id

    # Hand validate_and_prepare_graph the RAW edges. Splitting the primary
    # hierarchical edges out here — before validation — means they are never
    # counted in input_edge_count, never endpoint-checked, and unavailable as a
    # fallback when a node's own parentId turns out to be unusable.
    export_nodes, export_edges, validation = validate_and_prepare_graph(
        nodes,
        raw_edges,
        existing_ids=existing_ids,
    )
    pipeline_summary = {
        "initial_node_count": raw_nodes_loaded,
        "raw_nodes_loaded": raw_nodes_loaded,
        "nodes_after_normalization": normalized_node_count,
        "nodes_after_merge": merged_node_count,
        "nodes_removed_missing_parent": validation["nodes_removed_missing_parent"],
        "nodes_reattached_to_root": validation["nodes_reattached_to_root"],
        "nodes_removed_structural_errors": validation["nodes_removed_structural_errors"],
        "final_node_count": len(export_nodes),
    }
    validation["pipeline_summary"] = pipeline_summary

    graph_path = Path(graph_output_path)
    min_graph_path = Path(min_graph_output_path) if min_graph_output_path is not None else None
    nodes_path = Path(nodes_output_path)
    edges_path = Path(edges_output_path)
    validity_report_path = Path(validity_report_output_path)
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    nodes_path.parent.mkdir(parents=True, exist_ok=True)
    edges_path.parent.mkdir(parents=True, exist_ok=True)
    validity_report_path.parent.mkdir(parents=True, exist_ok=True)
    if min_graph_path is not None:
        min_graph_path.parent.mkdir(parents=True, exist_ok=True)

    tree_stats: dict[str, int] = {}
    graph = build_graph_tree(
        base_graph_path=base_graph_path,
        nodes=export_nodes,
        edges=export_edges,
        stats=tree_stats,
    )
    validation["cycle_fallback_root_attachments"] = tree_stats.get("cycle_fallback_root_attachments", 0)
    proof_status_counts, _ = annotate_proof_tree(
        graph,
        parent_is_proven=True,
        is_root=True,
        trusted_node_ids=set(existing_ids),
        prune_unproven=enforce_export_gate,
    )
    filter_relationships_to_kept_nodes(graph)
    budget_summary = extract_budget_summary(payload_list)
    if budget_summary:
        graph["__budgetSummary"] = budget_summary
        validation["budget_summary"] = budget_summary

    duplicate_child_rollups_dropped = drop_duplicate_child_rollups(graph)
    annotate_resolved_costs(graph, budget_summary=budget_summary)
    pre_export_graph_node_map, _ = index_tree(graph)
    audit_report = generate_audit_report(pre_export_graph_node_map.values())
    node_export_policy = NodeRequirements().evaluate_export_nodes(
        pre_export_graph_node_map.values(),
        trusted_node_ids=set(existing_ids),
    )
    cost_export_policy = CostValidator().evaluate_nodes(
        pre_export_graph_node_map.values(),
        trusted_node_ids=set(existing_ids),
    )
    if enforce_export_gate:
        allowed_graph_ids = (
            set(cost_export_policy["allowed_ids"])
            & set(node_export_policy["allowed_ids"])
        )
        pruned_roots = prune_tree_to_allowed_ids(graph, allowed_graph_ids, is_root=True)
        graph = pruned_roots[0] if pruned_roots else graph
    orphan_resolution = resolve_root_orphans(graph, trusted_node_ids=set(existing_ids))
    filter_relationships_to_kept_nodes(graph)
    validity_report = annotate_resolved_costs(graph, budget_summary=budget_summary)
    validity_report["audit_report"] = {"summary": deepcopy(audit_report.get("summary", {}))}
    validity_report["root_orphan_resolution"] = orphan_resolution
    validity_report["cost_export_policy"] = summarize_export_policy(cost_export_policy)
    validity_report["node_export_policy"] = summarize_export_policy(node_export_policy)
    graph_node_map, _ = index_tree(graph)
    kept_graph_ids = set(graph_node_map)
    export_nodes = [node for node in export_nodes if node["id"] in kept_graph_ids]
    export_edges = [
        edge
        for edge in export_edges
        if edge["source"] in kept_graph_ids and edge["target"] in kept_graph_ids
    ]
    for node in export_nodes:
        graph_node = graph_node_map.get(node["id"])
        if not graph_node:
            continue
        if graph_node.get("parentId"):
            node["parentId"] = deepcopy(graph_node.get("parentId"))
        for field_name in COST_EXPORT_FIELDS:
            node[field_name] = deepcopy(graph_node.get(field_name))
        node["proofStatus"] = deepcopy(graph_node.get("proofStatus"))
        node["proofReason"] = deepcopy(graph_node.get("proofReason"))
        node["proofSourceCount"] = deepcopy(graph_node.get("proofSourceCount"))
        node["existsProven"] = deepcopy(graph_node.get("existsProven"))
        node["parentProven"] = deepcopy(graph_node.get("parentProven"))
    validation.update(validity_report["summary"])
    validation["graph_summary"] = deepcopy(validity_report["summary"])
    validation["audit_report"] = deepcopy(audit_report)
    validation["node_export_policy"] = deepcopy(node_export_policy["summary"])
    validation["export_verification_status_counts"] = deepcopy(validity_report["summary"].get("verification_status_counts", {}))
    validation["export_verified_node_count"] = int(validity_report["summary"].get("verification_status_counts", {}).get("verified", 0))
    validation["export_average_confidence_score"] = validation.get("average_confidence_score")
    validation["pre_export_audit_summary"] = deepcopy(audit_report["summary"])
    validation["cost_export_policy"] = deepcopy(cost_export_policy["summary"])
    validation["node_validation_rejected_nodes"] = int(node_export_policy["summary"].get("nodes_rejected", 0))
    validation["cost_validation_rejected_nodes"] = int(cost_export_policy["summary"].get("nodes_rejected", 0))
    validation["root_orphan_resolution"] = deepcopy(orphan_resolution["summary"])
    validation["duplicate_child_rollups_dropped"] = duplicate_child_rollups_dropped
    validation["proof_status_counts_before_cull"] = proof_status_counts
    validation["exported_node_count"] = len(export_nodes)
    validation["exported_edge_count"] = len(export_edges)
    validation["pipeline_summary"]["final_node_count"] = len(export_nodes)
    validation["pipeline_summary"]["nodes_removed_cost_validation"] = int(cost_export_policy["summary"].get("nodes_rejected", 0))

    write_json_file(graph_path, graph)
    if min_graph_path is not None:
        write_json_file(min_graph_path, prune_graph_for_viewer(graph), compact=True)
    write_json_file(nodes_path, export_nodes)
    write_json_file(edges_path, export_edges)
    write_json_file(validity_report_path, validity_report)

    return BuildResult(
        nodes=export_nodes,
        edges=export_edges,
        graph=graph,
        graph_path=graph_path,
        min_graph_path=min_graph_path,
        nodes_path=nodes_path,
        edges_path=edges_path,
        validation=validation,
        validity_report_path=validity_report_path,
    )


def main() -> None:
    result = build_graph(payloads=[])
    print(format_pipeline_summary(result.validation["pipeline_summary"]))
    print(f"Wrote graph to {result.graph_path}")
    print(f"Wrote {len(result.nodes)} nodes to {result.nodes_path}")
    print(f"Wrote {len(result.edges)} edges to {result.edges_path}")
    print(json.dumps(result.validation, indent=2))


if __name__ == "__main__":
    main()
