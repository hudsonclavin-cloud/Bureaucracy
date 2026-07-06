from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable


SUSPICIOUS_COST_VALUES = {
    0.0,
    1.0,
    10.0,
    100.0,
    1000.0,
    10000.0,
    100000.0,
    1000000.0,
    1000000000.0,
    1000000000000.0,
}

GENERIC_TYPES = {
    "",
    "unknown",
    "other",
    "organization",
    "organisation",
    "entity",
    "node",
}

TRUSTED_BASE_EXCEPTION_TYPES = {
    "Foundation",
    "Branch",
    "Department",
    "Agency",
    "Bureau",
    "Cabinet Department",
    "Independent Agency",
    "Executive Department",
}

WARNING_COST_STATUSES = {
    "allocated",
    "scaled_official",
}

NON_BLOCKING_COST_STATUSES = {
    "official",
    "root_total",
    "allocated",
    "scaled_official",
    "unavailable",
}


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_list_of_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [item for item in (_as_text(entry) for entry in value) if item]
    text = _as_text(value)
    return [text] if text else []


def _dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


@dataclass(frozen=True)
class AuditIssue:
    code: str
    severity: str
    field: str
    message: str
    value: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "field": self.field,
            "message": self.message,
            "value": self.value,
        }


class NodeRequirements:
    """Non-blocking audit helper for normalized/export-ready graph nodes."""

    def __init__(self) -> None:
        self.warning_cost_statuses = set(WARNING_COST_STATUSES)
        self.non_blocking_cost_statuses = set(NON_BLOCKING_COST_STATUSES)

    def audit_node(self, node: dict[str, Any]) -> dict[str, Any]:
        """Return a serializable audit record for a single node."""
        name = _as_text(node.get("name")) or "Unnamed Node"
        node_type = _as_text(node.get("type"))
        source_urls = _dedupe_preserve_order(_as_list_of_strings(node.get("sourceUrls")))
        source_count = node.get("sourceCount")
        source_count = int(source_count) if isinstance(source_count, int) or str(source_count).isdigit() else len(source_urls)
        resolved_total = _as_float(node.get("resolved_total_amount"))
        confidence = _as_float(node.get("confidenceScore")) or 0.0
        cost_status = _as_text(node.get("cost_status")).lower()
        cost_validation = _as_text(node.get("cost_validation"))
        cost_verification_status = _as_text(node.get("costVerificationStatus")).lower() or "unverified"
        cost_confidence = _as_float(node.get("costConfidenceScore")) or 0.0
        cost_verification_reason = _as_text(node.get("costVerificationReason"))
        cost_source_count = node.get("costSourceCount")
        cost_source_count = int(cost_source_count) if isinstance(cost_source_count, int) or str(cost_source_count).isdigit() else 0
        verification_status = _as_text(node.get("verificationStatus")).lower() or "unverified"
        proof_status = _as_text(node.get("proofStatus")).lower() or "unproven"

        issues: list[AuditIssue] = []

        if not name or name.lower() in {"unnamed node", "unknown", "placeholder", "temp", "dummy"}:
            issues.append(
                AuditIssue(
                    code="placeholder_name",
                    severity="error",
                    field="name",
                    message="Node name looks like a placeholder or unnamed record.",
                    value=name,
                )
            )

        if not node_type or node_type.lower() in GENERIC_TYPES:
            issues.append(
                AuditIssue(
                    code="generic_or_missing_type",
                    severity="warning",
                    field="type",
                    message="Node type is missing or too generic to support strong auditing.",
                    value=node_type,
                )
            )

        if resolved_total is None:
            issues.append(
                AuditIssue(
                    code="missing_cost",
                    severity="error",
                    field="resolved_total_amount",
                    message="Node does not have a resolved cost value.",
                    value=node.get("resolved_total_amount"),
                )
            )
        elif resolved_total in SUSPICIOUS_COST_VALUES:
            issues.append(
                AuditIssue(
                    code="suspicious_exact_cost_value",
                    severity="warning",
                    field="resolved_total_amount",
                    message="Resolved cost is an exact round value that should be reviewed.",
                    value=resolved_total,
                )
            )

        if cost_status not in self.non_blocking_cost_statuses and cost_status:
            issues.append(
                AuditIssue(
                    code="unknown_cost_status",
                    severity="warning",
                    field="cost_status",
                    message="Cost status is not one of the known non-blocking statuses.",
                    value=cost_status,
                )
            )
        elif not cost_status:
            issues.append(
                AuditIssue(
                    code="unavailable_cost_status",
                    severity="error",
                    field="cost_status",
                    message="Node does not have a usable cost status.",
                    value=cost_status,
                )
            )

        if cost_status == "unavailable":
            issues.append(
                AuditIssue(
                    code="unavailable_cost_status",
                    severity="error",
                    field="cost_status",
                    message="Node cost is marked unavailable.",
                    value=cost_status,
                )
            )

        if cost_status in self.warning_cost_statuses:
            issues.append(
                AuditIssue(
                    code="estimated_cost",
                    severity="warning",
                    field="cost_status",
                    message="Node uses an estimated cost path and should be reviewed as a non-blocking warning.",
                    value=cost_status,
                )
            )

        if cost_verification_status == "unverified" and resolved_total is not None and cost_status != "unavailable":
            issues.append(
                AuditIssue(
                    code="cost_unverified",
                    severity="warning",
                    field="costVerificationStatus",
                    message="Node cost exists but the cost basis is not separately verified.",
                    value=cost_verification_status,
                )
            )
        elif cost_verification_status == "partial":
            issues.append(
                AuditIssue(
                    code="cost_partially_verified",
                    severity="warning",
                    field="costVerificationStatus",
                    message="Node cost is partially verified and should be reviewed separately from node existence.",
                    value=cost_verification_status,
                )
            )

        if resolved_total is not None and cost_confidence < 0.5:
            issues.append(
                AuditIssue(
                    code="low_cost_confidence",
                    severity="warning",
                    field="costConfidenceScore",
                    message="Cost confidence score is low.",
                    value=cost_confidence,
                )
            )

        if not source_urls:
            issues.append(
                AuditIssue(
                    code="missing_source_urls",
                    severity="error",
                    field="sourceUrls",
                    message="Node has no recorded source URLs.",
                    value=[],
                )
            )

        if source_count == 0 and source_urls:
            issues.append(
                AuditIssue(
                    code="missing_source_count",
                    severity="warning",
                    field="sourceCount",
                    message="Source count is zero even though source URLs are present.",
                    value=0,
                )
            )

        if confidence < 0.2:
            issues.append(
                AuditIssue(
                    code="low_confidence",
                    severity="warning",
                    field="confidenceScore",
                    message="Confidence score is low and should be reviewed.",
                    value=confidence,
                )
            )

        if verification_status == "unverified":
            issues.append(
                AuditIssue(
                    code="unverified",
                    severity="warning",
                    field="verificationStatus",
                    message="Verification status is unverified.",
                    value=verification_status,
                )
            )

        if proof_status == "unproven":
            issues.append(
                AuditIssue(
                    code="unproven",
                    severity="warning",
                    field="proofStatus",
                    message="Proof status is unproven.",
                    value=proof_status,
                )
            )

        if not cost_validation:
            issues.append(
                AuditIssue(
                    code="missing_cost_validation",
                    severity="warning",
                    field="cost_validation",
                    message="Node is missing a cost validation note.",
                    value=cost_validation,
                )
            )

        severity_counts = Counter(issue.severity for issue in issues)
        issue_counts = Counter(issue.code for issue in issues)
        has_errors = severity_counts.get("error", 0) > 0
        has_warnings = severity_counts.get("warning", 0) > 0

        return {
            "id": _as_text(node.get("id")),
            "name": name,
            "type": node_type,
            "resolved_total_amount": resolved_total,
            "cost_status": cost_status or None,
            "cost_validation": cost_validation or None,
            "costVerificationStatus": cost_verification_status,
            "costConfidenceScore": cost_confidence,
            "costVerificationReason": cost_verification_reason or None,
            "costSourceCount": cost_source_count,
            "verificationStatus": verification_status,
            "confidenceScore": confidence,
            "sourceCount": source_count,
            "sourceUrls": source_urls,
            "proofStatus": proof_status,
            "issues": [issue.to_dict() for issue in issues],
            "issue_codes": [issue.code for issue in issues],
            "severity_counts": dict(severity_counts),
            "issue_counts": dict(issue_counts),
            "has_errors": has_errors,
            "has_warnings": has_warnings,
            "is_warning_only": has_warnings and not has_errors,
            "cost_status_is_warning": cost_status in self.warning_cost_statuses,
        }

    def audit_nodes(self, nodes: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.audit_node(node) for node in nodes if isinstance(node, dict)]

    def is_trusted_exception_node(self, node: dict[str, Any], trusted_node_ids: set[str]) -> bool:
        node_id = str(node.get("id") or "")
        node_type = str(node.get("type") or "")
        proof_status = str(node.get("proofStatus") or "").lower()
        if proof_status == "root":
            return True
        return node_id in trusted_node_ids and node_type in TRUSTED_BASE_EXCEPTION_TYPES

    def evaluate_export_nodes(
        self,
        nodes: Iterable[dict[str, Any]],
        *,
        trusted_node_ids: set[str] | None = None,
        strict_mode: bool = False,
    ) -> dict[str, Any]:
        trusted_node_ids = trusted_node_ids or set()
        findings = self.audit_nodes(nodes)
        allowed_ids: set[str] = set()
        rejected_nodes: list[dict[str, Any]] = []
        exception_count = 0

        for finding in findings:
            trusted_exception = self.is_trusted_exception_node(finding, trusted_node_ids)
            blocking = bool(finding.get("has_errors")) or (strict_mode and bool(finding.get("has_warnings")))
            if blocking and not trusted_exception:
                rejected_nodes.append(
                    {
                        "id": finding.get("id"),
                        "name": finding.get("name"),
                        "issue_codes": finding.get("issue_codes", []),
                        "severity_counts": finding.get("severity_counts", {}),
                    }
                )
                continue
            if blocking and trusted_exception:
                exception_count += 1
            allowed_ids.add(str(finding.get("id") or ""))

        return {
            "summary": {
                "nodes_checked": len(findings),
                "nodes_allowed": len(allowed_ids),
                "nodes_rejected": len(rejected_nodes),
                "trusted_exceptions_applied": exception_count,
            },
            "allowed_ids": {node_id for node_id in allowed_ids if node_id},
            "rejected_nodes": rejected_nodes,
            "findings": findings,
        }


def generate_audit_report(nodes: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Build a serializable non-blocking audit report for a node collection."""
    auditor = NodeRequirements()
    findings = auditor.audit_nodes(nodes)

    severity_counts: Counter[str] = Counter()
    issue_counts: Counter[str] = Counter()
    cost_status_counts: Counter[str] = Counter()
    cost_verification_status_counts: Counter[str] = Counter()
    verification_status_counts: Counter[str] = Counter()
    proof_status_counts: Counter[str] = Counter()

    nodes_with_errors = 0
    nodes_with_warnings = 0
    warning_only_nodes = 0

    for finding in findings:
        severity_counts.update(finding.get("severity_counts", {}))
        issue_counts.update(finding.get("issue_counts", {}))
        if finding.get("cost_status"):
            cost_status_counts[str(finding["cost_status"])] += 1
        if finding.get("costVerificationStatus"):
            cost_verification_status_counts[str(finding["costVerificationStatus"])] += 1
        verification_status_counts[str(finding.get("verificationStatus") or "unverified")] += 1
        proof_status_counts[str(finding.get("proofStatus") or "unproven")] += 1
        if finding.get("has_errors"):
            nodes_with_errors += 1
        if finding.get("has_warnings"):
            nodes_with_warnings += 1
        if finding.get("is_warning_only"):
            warning_only_nodes += 1

    return {
        "summary": {
            "total_nodes": len(findings),
            "nodes_with_errors": nodes_with_errors,
            "nodes_with_warnings": nodes_with_warnings,
            "warning_only_nodes": warning_only_nodes,
            "severity_counts": dict(severity_counts),
            "issue_counts": dict(issue_counts),
            "cost_status_counts": dict(cost_status_counts),
            "cost_verification_status_counts": dict(cost_verification_status_counts),
            "verification_status_counts": dict(verification_status_counts),
            "proof_status_counts": dict(proof_status_counts),
            "warning_cost_statuses": sorted(WARNING_COST_STATUSES),
        },
        "nodes": findings,
    }
