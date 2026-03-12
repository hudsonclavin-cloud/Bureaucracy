from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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
    return {
        "id": node_id,
        "name": name,
        "type": node_type,
        "desc": desc,
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
    return TEMPLATES.get(slugify(node.get("name", "")), DEFAULT_TEMPLATE)


def build_expansion_for_node(node: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    base_id = node["id"]
    base_name = node["name"]
    template = pick_template(node)

    roles = [
        make_node(
            f"{base_id}-corp-{slugify(role)}",
            role,
            "Corporate Officer",
            f"{role} role associated with {base_name}.",
            color=GRAY,
        )
        for role in template.roles
    ]

    divisions = []
    relationship_edges = []

    for index, division_name in enumerate(template.divisions):
        division_id = f"{base_id}-corp-{slugify(division_name)}"
        division_roles = [
            make_node(
                f"{division_id}-{suffix}",
                label,
                "Position",
                f"{label} within {division_name} at {base_name}.",
                color=GRAY,
            )
            for suffix, label in (
                ("head", f"Head of {division_name}"),
                ("director", f"Director, {division_name}"),
                ("manager", f"Manager, {division_name}"),
            )
        ]
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
        relationship_edges.append(
            {
                "source": roles[index % len(roles)]["id"],
                "target": division_id,
                "type": "relationship",
            }
        )

    expansion_root = make_node(
        base_id,
        base_name,
        node.get("type") or "Independent Company",
        node.get("desc") or f"Expanded corporate structure for {base_name}.",
        employees=node.get("employees"),
        budget=node.get("budget"),
        color=node.get("color") or GREEN,
        children=roles + divisions,
    )

    for division in divisions:
        relationship_edges.append(
            {
                "source": division["id"],
                "target": f"{division['id']}-director",
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

    return {
        "nodes": nodes,
        "edges": edges,
    }
