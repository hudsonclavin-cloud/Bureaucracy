from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from data_pipeline.processors.normalize_nodes import normalize_name


GREEN = "#4ac88a"
GRAY = "#666666"


def iter_nodes(root: dict[str, Any]):
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.get("children", [])))


def is_expandable_company(node: dict[str, Any]) -> bool:
    node_type = (node.get("type") or "").lower()
    node_name = (node.get("name") or "").lower()
    greenish = (node.get("color") or "").lower() == GREEN
    keywords = ("corporation", "corp", "company", "postal service", "finance")

    return (
        "government corporation" in node_type
        or (
            greenish
            and any(keyword in node_name for keyword in keywords)
            and node_type not in {"position", "office", "division"}
        )
    )


def slugify(value: str) -> str:
    cleaned = []
    for char in value.lower():
        cleaned.append(char if char.isalnum() else "-")
    slug = "".join(cleaned)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "node"


def normalize_text(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        text = fallback
    return text


def normalize_label(value: Any, fallback: str) -> str:
    text = normalize_name(value)
    if not text or text == "Unnamed Node":
        return fallback
    return text


def normalize_type(value: Any, fallback: str) -> str:
    return normalize_label(value, fallback)


def normalized_template_items(values: tuple[str, ...], fallback: tuple[str, ...]) -> tuple[str, ...]:
    cleaned = tuple(normalize_text(value, "") for value in values if normalize_text(value, ""))
    return cleaned or fallback


def safe_node_id(*parts: Any) -> str:
    slug_parts = [slugify(normalize_text(part, "")) for part in parts if normalize_text(part, "")]
    return "-".join(part for part in slug_parts if part) or "node"


def iter_generated_nodes(root_nodes: list[dict[str, Any]]):
    stack = list(root_nodes)
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.get("children", [])))


def make_node(
    node_id: str,
    name: str,
    node_type: str,
    desc: str,
    *,
    employees: str | None = None,
    budget: str | None = None,
    color: str = GREEN,
    children: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized_name = normalize_label(name, "Unnamed Node")
    return {
        "id": safe_node_id(node_id),
        "name": normalized_name,
        "type": normalize_type(node_type, "Organization"),
        "desc": normalize_text(desc, ""),
        "employees": employees,
        "budget": budget,
        "color": color,
        "children": children or [],
    }


@dataclass(frozen=True)
class CorporateTemplate:
    name: str
    divisions: tuple[str, ...]
    roles: tuple[str, ...]


DEFAULT_TEMPLATE = CorporateTemplate(
    name="Corporate Structure",
    divisions=(
        "Executive Leadership",
        "Operations",
        "Finance & Risk",
        "Technology",
    ),
    roles=(
        "Chief Executive Officer",
        "Chief Financial Officer",
        "Chief Operating Officer",
        "Chief Information Officer",
    ),
)


def normalize_template(template: CorporateTemplate) -> CorporateTemplate:
    return CorporateTemplate(
        name=normalize_text(template.name, DEFAULT_TEMPLATE.name),
        divisions=normalized_template_items(template.divisions, DEFAULT_TEMPLATE.divisions),
        roles=normalized_template_items(template.roles, DEFAULT_TEMPLATE.roles),
    )


TEMPLATES: dict[str, CorporateTemplate] = {
    "u-s-postal-service-usps": CorporateTemplate(
        name="Postal Structure",
        divisions=(
            "Package & Mail Operations",
            "Retail Network",
            "Logistics Technology",
            "Government Affairs",
        ),
        roles=(
            "Chief Logistics Officer",
            "Chief Retail Officer",
            "Chief Technology Officer",
            "SVP Government Affairs",
        ),
    ),
    "federal-deposit-insurance-corporation-fdic": CorporateTemplate(
        name="Bank Resolution Structure",
        divisions=(
            "Receivership Management",
            "Supervision Technology",
            "Deposit Insurance Services",
            "Risk Analytics",
        ),
        roles=(
            "Chief Resolution Officer",
            "Chief Supervisory Officer",
            "Chief Insurance Officer",
            "Chief Risk Officer",
        ),
    ),
}


def pick_template(node: dict[str, Any]) -> CorporateTemplate:
    template = TEMPLATES.get(slugify(normalize_text(node.get("name", ""), "")), DEFAULT_TEMPLATE)
    return normalize_template(template)


def build_expansion_for_node(node: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    base_name = normalize_label(node.get("name"), "Unnamed Corporate Node")
    base_id = safe_node_id(node.get("id") or base_name)
    template = pick_template(node)

    roles = []
    for role in template.roles:
        role_name = normalize_label(role, "Corporate Officer")
        roles.append(
            make_node(
                safe_node_id(base_id, "corp", role),
                role_name,
                normalize_type("Corporate Officer", "Corporate Officer"),
                f"{role_name} role associated with {base_name}.",
                color=GRAY,
            )
        )

    divisions = []
    relationship_edges = []

    for division_name in template.divisions:
        division_id = safe_node_id(base_id, "corp", division_name)
        division_roles = []
        for suffix, label in (
            ("head", f"Head of {division_name}"),
            ("director", f"Director, {division_name}"),
            ("manager", f"Manager, {division_name}"),
        ):
            normalized_label = normalize_label(label, "Corporate Position")
            division_roles.append(
                make_node(
                    safe_node_id(division_id, suffix),
                    normalized_label,
                    normalize_type("Position", "Position"),
                    f"{normalized_label} within {division_name} at {base_name}.",
                    color=GRAY,
                )
            )
        divisions.append(
            make_node(
                division_id,
                division_name,
                "Corporate Division",
                f"Expanded corporate division generated for {base_name}.",
                color=GREEN,
                children=division_roles,
            )
        )

    expansion_root = make_node(
        base_id,
        base_name,
        normalize_type(node.get("type"), "Independent Company"),
        normalize_text(node.get("desc"), f"Expanded corporate structure for {base_name}."),
        employees=node.get("employees"),
        budget=node.get("budget"),
        color=node.get("color") or GREEN,
        children=roles + divisions,
    )

    if roles and divisions:
        for index, division in enumerate(divisions):
            source_id = roles[index % len(roles)]["id"]
            relationship_edges.append(
                {
                    "source": source_id,
                    "target": division["id"],
                    "type": "relationship",
                }
            )

    for division in divisions:
        director_id = f"{division['id']}-director"
        relationship_edges.append(
            {
                "source": division["id"],
                "target": director_id,
                "type": "relationship",
            }
        )

    return expansion_root, relationship_edges


def build_corporate_expansion(root: dict[str, Any]) -> dict[str, Any]:
    nodes = []
    edges = []

    for node in iter_nodes(root):
        if not is_expandable_company(node):
            continue
        expanded_node, relationship_edges = build_expansion_for_node(node)
        nodes.append(expanded_node)
        edges.extend(relationship_edges)

    all_generated_ids = {generated_node["id"] for generated_node in iter_generated_nodes(nodes)}
    edges = [
        edge
        for edge in edges
        if edge.get("source") in all_generated_ids and edge.get("target") in all_generated_ids
    ]

    return {
        "nodes": nodes,
        "edges": edges,
    }
