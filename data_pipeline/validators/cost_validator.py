from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Mapping


SUSPICIOUS_EXACT_COSTS = {
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

ALLOWED_COST_STATUSES = {
    "root_total",
    "official",
    "scaled_official",
}

ALLOWED_COST_VERIFICATION_STATUSES = {
    "verified",
    "partial",
}

TRUSTED_EXCEPTION_PROOF_STATUSES = {
    "root",
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

FINANCIAL_SOURCE_TYPES = {
    "official_financial_record",
    "treasury_outlays",
    "usaspending_direct",
    "usaspending_parent",
}


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [text for text in (_as_text(item) for item in value) if text]
    text = _as_text(value)
    return [text] if text else []


@dataclass(frozen=True)
class CostValidationIssue:
    code: str
    severity: str
    message: str
    field: str
    value: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "field": self.field,
            "value": self.value,
        }


class CostValidator:
    """Strict export gate for node cost fields."""

    def is_trusted_exception_node(self, node: Mapping[str, Any], trusted_node_ids: set[str]) -> bool:
        node_id = _as_text(node.get("id"))
        node_type = _as_text(node.get("type"))
        proof_status = _as_text(node.get("proofStatus")).lower()
        if proof_status in TRUSTED_EXCEPTION_PROOF_STATUSES:
            return True
        return node_id in trusted_node_ids and node_type in TRUSTED_BASE_EXCEPTION_TYPES

    def is_suspicious_amount(self, amount: float | None) -> bool:
        if amount is None:
            return False
        normalized = round(float(amount), 2)
        return normalized in SUSPICIOUS_EXACT_COSTS

    def has_verifiable_cost_source(self, node: Mapping[str, Any]) -> bool:
        source_types = {text.casefold() for text in _as_list(node.get("sourceTypes"))}
        budget_source = _as_text(node.get("budget_source")).casefold()
        cost_source_count = int(_as_float(node.get("costSourceCount")) or 0)
        cost_verification_reason = _as_text(node.get("costVerificationReason")).casefold()

        if cost_source_count > 0:
            return True
        if source_types & FINANCIAL_SOURCE_TYPES:
            return True
        if "treasury" in budget_source or "usaspending" in budget_source or "omb" in budget_source:
            return True
        if "treasury" in cost_verification_reason or "budget" in cost_verification_reason or "rollup" in cost_verification_reason:
            return True
        return False

    def validate_node_cost(
        self,
        node: Mapping[str, Any],
        *,
        trusted_exception: bool = False,
    ) -> dict[str, Any]:
        resolved_total = _as_float(node.get("resolved_total_amount"))
        cost_status = _as_text(node.get("cost_status")).lower()
        cost_validation = _as_text(node.get("cost_validation"))
        cost_verification_status = _as_text(node.get("costVerificationStatus")).lower() or "unverified"
        cost_confidence = _as_float(node.get("costConfidenceScore")) or 0.0
        proof_status = _as_text(node.get("proofStatus")).lower() or "unproven"
        issues: list[CostValidationIssue] = []

        if resolved_total is None:
            issues.append(
                CostValidationIssue(
                    code="missing_cost",
                    severity="error",
                    message="Node does not have a resolved total cost.",
                    field="resolved_total_amount",
                    value=node.get("resolved_total_amount"),
                )
            )
        elif resolved_total == 0:
            issues.append(
                CostValidationIssue(
                    code="zero_cost",
                    severity="error",
                    message="Node cost is zero and cannot be treated as verified.",
                    field="resolved_total_amount",
                    value=resolved_total,
                )
            )

        if self.is_suspicious_amount(resolved_total) and cost_verification_status != "verified":
            issues.append(
                CostValidationIssue(
                    code="suspicious_cost_value",
                    severity="error",
                    message="Node cost looks like a placeholder or obviously synthetic round value.",
                    field="resolved_total_amount",
                    value=resolved_total,
                )
            )

        if cost_status not in ALLOWED_COST_STATUSES:
            issues.append(
                CostValidationIssue(
                    code="non_authoritative_cost_status",
                    severity="error",
                    message="Node cost status is estimated, unavailable, or otherwise not authoritative enough for export.",
                    field="cost_status",
                    value=cost_status,
                )
            )

        if cost_verification_status not in ALLOWED_COST_VERIFICATION_STATUSES:
            issues.append(
                CostValidationIssue(
                    code="cost_not_verified",
                    severity="error",
                    message="Node cost is not separately verified or partially verified.",
                    field="costVerificationStatus",
                    value=cost_verification_status,
                )
            )

        if not self.has_verifiable_cost_source(node):
            issues.append(
                CostValidationIssue(
                    code="missing_verifiable_cost_source",
                    severity="error",
                    message="Node cost has no verifiable financial source.",
                    field="sourceTypes",
                    value=_as_list(node.get("sourceTypes")),
                )
            )

        if cost_confidence <= 0:
            issues.append(
                CostValidationIssue(
                    code="missing_cost_confidence",
                    severity="error",
                    message="Node cost has no confidence score.",
                    field="costConfidenceScore",
                    value=cost_confidence,
                )
            )

        blocking_issues = [issue for issue in issues if issue.severity == "error"]
        export_allowed = not blocking_issues
        exception_applied = False
        exception_reason = None

        if trusted_exception and blocking_issues:
            export_allowed = True
            exception_applied = True
            exception_reason = "trusted_base_graph_exception"

        return {
            "id": _as_text(node.get("id")),
            "name": _as_text(node.get("name")) or "Unnamed Node",
            "proofStatus": proof_status,
            "cost_status": cost_status or None,
            "cost_validation": cost_validation or None,
            "costVerificationStatus": cost_verification_status,
            "costConfidenceScore": cost_confidence,
            "resolved_total_amount": resolved_total,
            "has_verifiable_cost_source": self.has_verifiable_cost_source(node),
            "export_allowed": export_allowed,
            "trusted_exception": bool(trusted_exception),
            "exception_applied": exception_applied,
            "exception_reason": exception_reason,
            "blocking_issue_codes": [issue.code for issue in blocking_issues],
            "issues": [issue.to_dict() for issue in issues],
        }

    def evaluate_nodes(
        self,
        nodes: Iterable[Mapping[str, Any]],
        *,
        trusted_node_ids: set[str] | None = None,
    ) -> dict[str, Any]:
        trusted_node_ids = trusted_node_ids or set()
        decisions: list[dict[str, Any]] = []
        decision_counts: Counter[str] = Counter()
        issue_counts: Counter[str] = Counter()
        exception_count = 0

        for node in nodes:
            trusted_exception = self.is_trusted_exception_node(node, trusted_node_ids)
            decision = self.validate_node_cost(node, trusted_exception=trusted_exception)
            decisions.append(decision)
            decision_counts["allowed" if decision["export_allowed"] else "rejected"] += 1
            if decision["exception_applied"]:
                exception_count += 1
            issue_counts.update(decision["blocking_issue_codes"])

        allowed_ids = {decision["id"] for decision in decisions if decision["export_allowed"]}
        rejected = [decision for decision in decisions if not decision["export_allowed"]]
        return {
            "summary": {
                "nodes_checked": len(decisions),
                "nodes_allowed": decision_counts.get("allowed", 0),
                "nodes_rejected": decision_counts.get("rejected", 0),
                "trusted_exceptions_applied": exception_count,
                "blocking_issue_counts": dict(issue_counts),
            },
            "allowed_ids": allowed_ids,
            "rejected_nodes": rejected,
            "decisions": decisions,
        }
