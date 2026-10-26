"""Reviewed decisions to keep a name an official document was read and does not carry.

`docs/DEFINITION_OF_DONE.md` criterion 3 names three ways to settle a negative
("checked and not found"): a rename to the document's wording, a supersession, or
a recorded decision to keep the name. The first two change the graph and need a
page that states the change. This module is the third.

Two tables feed it and the rule for both is the same: the node exists and still
carries the name the row was written against.

- `data/curation/name_decisions.json` (this module's own): a grouping the graph
  made, which no document is expected to name, or a unit whose own page headlines
  it in other words, the headline quoted.
- the `curatedNames` rows of `data/curation/list_dispositions.json`: a curated
  committee name a complete committee list does not carry, already re-adjudicated
  against the committed list on every run.

A decision EXPLAINS a negative; it never removes it. The node still publishes
`verificationFailure`, the panel still says what was read, and nothing here is
evidence that the unit exists. What changes is only how criterion 3's report
counts the node: as a decided negative rather than an open one.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TABLE = PROJECT_ROOT / "data" / "curation" / "name_decisions.json"
DISPOSITIONS_TABLE = PROJECT_ROOT / "data" / "curation" / "list_dispositions.json"

KINDS = ("graphs_own_grouping", "page_prints_another_wording")


def _collapse(text: Any) -> str:
    return " ".join(str(text or "").split())


def _load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load_rows(table: Path = DEFAULT_TABLE, dispositions: Path = DISPOSITIONS_TABLE) -> dict[str, dict[str, Any]]:
    """node id -> {name, kind, basis, source}: every row of both tables, unadjudicated."""
    rows: dict[str, dict[str, Any]] = {}
    for row in _load(dispositions).get("curatedNames") or []:
        if isinstance(row, dict) and row.get("nodeId"):
            rows[str(row["nodeId"])] = {"name": _collapse(row.get("name")), "kind": str(row.get("disposition") or ""),
                                        "basis": _collapse(row.get("basis")), "source": "list_dispositions"}
    for row in _load(table).get("decisions") or []:
        if isinstance(row, dict) and row.get("nodeId"):
            rows[str(row["nodeId"])] = {"name": _collapse(row.get("name")), "kind": str(row.get("kind") or ""),
                                        "basis": _collapse(row.get("basis")), "source": "name_decisions"}
    return rows


def refusal(row: dict[str, Any], node: dict[str, Any] | None) -> str | None:
    """Why a row does not stand against this node, or None."""
    if node is None:
        return "the node is not in the graph"
    if _collapse(node.get("name")) != row["name"]:
        return "the node no longer carries the name the row was written against"
    if not row["basis"]:
        return "a decision with no basis is an assertion"
    if row["source"] == "name_decisions" and row["kind"] not in KINDS:
        return f"kind {row['kind']!r} is not in the vocabulary"
    if not node.get("verificationFailure"):
        return "the node carries no negative for the decision to explain"
    return None


def decided_ids(nodes: Iterable[dict[str, Any]], rows: dict[str, dict[str, Any]] | None = None) -> tuple[set[str], dict[str, str]]:
    """The ids of nodes a standing row explains, and the refusals {id: why}."""
    rows = load_rows() if rows is None else rows
    by_id = {str(n.get("id")): n for n in nodes}
    decided: set[str] = set()
    refused: dict[str, str] = {}
    for node_id, row in rows.items():
        why = refusal(row, by_id.get(node_id))
        if why is None:
            decided.add(node_id)
        elif node_id in by_id and by_id[node_id].get("verificationFailure"):
            refused[node_id] = why
    return decided, refused
