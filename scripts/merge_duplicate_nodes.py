#!/usr/bin/env python
"""Merge the two duplicate units the node audit found, in the curated file.

    python scripts/merge_duplicate_nodes.py --dry-run   # what would change; writes nothing
    python scripts/merge_duplicate_nodes.py             # apply

The curated file is never hand-edited; a script writes it, so the change is
reviewable, repeatable and idempotent. That rule exists because an earlier
agent session in this owner's work deleted 5,165 lines while "cleaning up",
and it holds here even though the edits are small.

Phase 1a recorded exactly four `blocking` findings, and they are two pairs:
one organisation published twice, each copy carrying its own apportioned
dollar figure. A blocking finding is one where the site is currently saying
something false, and "this unit costs $3.28B" beside "this unit costs $9.64B"
for the same unit is the clearest kind. `CURATION.md` §3 set both out as the
owner's call; this script is that call being made, and it takes the option
that document already framed.

**The Coast Guard.** `exec-dept-defense-cg` sits under the Department of
Defense's "Military Departments & Services" grouping and `exec-dept-dhs-uscg`
under Homeland Security. Both are named "U.S. Coast Guard", both carry a
Commandant, a Vice Commandant and a Master Chief Petty Officer of the Coast
Guard, both state ~55,000 active and reserve, and the two published
$4,147,600,209.29 and $9,379,959,609.56 for the same service. There is one
Coast Guard. By statute it is one of the six armed forces at all times and it
sits in the Department of Homeland Security, transferring to the Navy only
when Congress or the President directs — so the DHS placement is the
organisational fact and the DoD copy is the duplicate. The DHS subtree is
also strictly the richer of the two: seventeen children including the nine
districts named individually, against nine with a single "District Commander
(×9 Districts)" standing for all of them.

So the DoD copy goes, and the grouping it sat in gets the cross-reference
`CURATION.md` §3 proposed instead of a second subtree — which it needs on its
own account, because its description reads "The six armed services organized
under three military departments" and it would otherwise be left describing
six children while carrying five.

The Treasury's own Table 5 prints one line, "United States Coast Guard". The
pipeline has been reporting it **ambiguous** and applying it to neither node,
because a line is applied only when the name identifies one line and one
node. With one node of that name the ambiguity is gone, and the honest
expectation is that the line lands and the Coast Guard's figure stops being
an estimate at all. That is not asserted here: the exporter decides on the
next build and the release gate checks it.

**The House intelligence committee.** `leg-house-cmte-intelligence` ("House
Committee on Intelligence") and
`leg-house-cmte-permanent-select-committee-on-intelligence` ("House Committee
on Permanent Select Committee on Intelligence") sit under the same parent and
both carry that one committee's four leadership posts. The House Clerk's own
committee list, committed at `tests/fixtures/directories/house/committees.xlsx`,
carries exactly one: "Permanent Select Committee on Intelligence", code
`IG00`, and it types it **Select**.

The survivor is the node the Clerk's list already matched, which is why it
keeps its id and its evidence. What it lacks is the four subcommittees, which
are on the duplicate, so those move across; its four leadership posts are the
same four posts the survivor already carries under better names, and they go
with the duplicate.

Two corrections ride along, both citable to the same list:

- the survivor is renamed to "House Permanent Select Committee on
  Intelligence", the body's actual name. `congress.committee_key` folds a
  leading chamber word and a "Committee on" prefix, so the old and new names
  reduce to the same key and the Clerk match survives the rename — the
  script asserts that rather than trusting it;
- both descriptions call it a "Standing committee", and it is a select
  committee. The Clerk's list says `Select` in its own type column.

**Ids are never rewritten.** The four subcommittees keep their
`leg-house-cmte-intelligence-sub-…` ids after moving, because the audit
ledger, the evidence files and the nomination ledgers are all keyed by id,
and renaming an id would orphan every record that names it. An id is an
opaque handle here, not a statement about the parent.

Running this twice is a no-op: each merge checks whether it has already been
applied and reports that instead of doing it again. Every precondition is
checked before anything is written, and a precondition that does not hold
stops the whole run rather than applying half of it.
"""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.json_io import write_json_file  # noqa: E402
from data_pipeline.verification.congress import committee_key  # noqa: E402

DEFAULT_BASE_GRAPH = PROJECT_ROOT / "data" / "federal_gov_complete_1.json"

COAST_GUARD_GROUPING_DESC = (
    "Five of the six armed services, organised under three military departments: "
    "the Department of the Army; the Department of the Navy, which includes the Marine "
    "Corps; and the Department of the Air Force, which includes the Space Force. "
    "The sixth armed service, the U.S. Coast Guard, is not a Defense Department "
    "component: it sits in the Department of Homeland Security, where this graph "
    "carries it, and transfers to the Navy only when Congress or the President directs."
)

HPSCI_NAME = "House Permanent Select Committee on Intelligence"
HPSCI_DESC = (
    "Select committee of the U.S. House of Representatives with jurisdiction over the "
    "intelligence community. The House Clerk's committee list carries it as the "
    "\"Permanent Select Committee on Intelligence\", code IG00, and types it Select "
    "rather than standing."
)

#: Each merge names the node that goes, the node that stays, the children to
#: carry across, and the text corrections the removal makes necessary. Nothing
#: is inferred at run time; a merge that does not match the file exactly is
#: refused rather than guessed at.
MERGES: list[dict[str, Any]] = [
    {
        "what": "the Coast Guard, published twice with two different costs",
        "remove": "exec-dept-defense-cg",
        "remove_from": "exec-dept-defense-branches",
        "keep": "exec-dept-dhs-uscg",
        "move_children": [],
        "rename_keep": None,
        "describe_keep": None,
        "describe_others": {"exec-dept-defense-branches": COAST_GUARD_GROUPING_DESC},
    },
    {
        "what": "the House intelligence committee, published twice",
        "remove": "leg-house-cmte-intelligence",
        "remove_from": "leg-house-committees",
        "keep": "leg-house-cmte-permanent-select-committee-on-intelligence",
        "move_children": [
            "leg-house-cmte-intelligence-sub-central-intelligence-agency",
            "leg-house-cmte-intelligence-sub-defense-intelligence-warfighter-support",
            "leg-house-cmte-intelligence-sub-nsa-cybersecurity",
            "leg-house-cmte-intelligence-sub-strategic-technologies-advanced-research",
        ],
        "rename_keep": HPSCI_NAME,
        "describe_keep": HPSCI_DESC,
        "describe_others": {},
    },
]


class Refused(Exception):
    """A precondition did not hold; nothing is written."""


def index(root: dict[str, Any]) -> tuple[dict[str, dict], dict[str, dict]]:
    """Every node by id, and every node's parent by the child's id."""
    nodes: dict[str, dict] = {}
    parents: dict[str, dict] = {}

    def walk(node: dict[str, Any], parent: dict[str, Any] | None) -> None:
        node_id = str(node.get("id") or "")
        if node_id:
            if node_id in nodes:
                raise Refused(f"{node_id} appears twice in the curated file")
            nodes[node_id] = node
            if parent is not None:
                parents[node_id] = parent
        for child in node.get("children") or []:
            if isinstance(child, dict):
                walk(child, node)

    walk(root, None)
    return nodes, parents


def subtree_size(node: dict[str, Any]) -> int:
    return 1 + sum(subtree_size(c) for c in node.get("children") or [] if isinstance(c, dict))


def plan(root: dict[str, Any]) -> list[dict[str, Any]]:
    """What each merge would do, after checking it can be done at all."""
    nodes, parents = index(root)
    steps: list[dict[str, Any]] = []
    for merge in MERGES:
        remove_id, keep_id = merge["remove"], merge["keep"]
        if remove_id not in nodes:
            steps.append({**merge, "state": "already applied", "removes": 0, "moves": []})
            continue
        if keep_id not in nodes:
            raise Refused(f"{merge['what']}: the node to keep, {keep_id}, is not in the curated file")
        actual_parent = parents.get(remove_id, {}).get("id")
        if actual_parent != merge["remove_from"]:
            raise Refused(
                f"{merge['what']}: {remove_id} sits under {actual_parent!r}, not the expected "
                f"{merge['remove_from']!r}; the file has moved under this script"
            )
        for child_id in merge["move_children"]:
            if child_id not in nodes:
                raise Refused(f"{merge['what']}: child {child_id} is not in the curated file")
            if parents.get(child_id, {}).get("id") != remove_id:
                raise Refused(f"{merge['what']}: {child_id} is not a child of {remove_id}")
        for other_id in merge["describe_others"]:
            if other_id not in nodes:
                raise Refused(f"{merge['what']}: {other_id} is not in the curated file")
        # A rename may not cost the node the evidence it already earned: the
        # committee fold is what the Clerk's match rests on, so the old and
        # the new name must reduce to the same key.
        if merge["rename_keep"]:
            before, after = committee_key(nodes[keep_id].get("name")), committee_key(merge["rename_keep"])
            if before != after:
                raise Refused(
                    f"{merge['what']}: renaming {keep_id} to {merge['rename_keep']!r} changes its committee "
                    f"key from {before!r} to {after!r}, which would drop the evidence it earned"
                )
        removed = subtree_size(nodes[remove_id]) - sum(
            subtree_size(nodes[c]) for c in merge["move_children"]
        )
        steps.append({
            **merge,
            "state": "to apply",
            "removes": removed,
            "moves": [(c, nodes[c].get("name")) for c in merge["move_children"]],
            "remove_name": nodes[remove_id].get("name"),
            "keep_name": nodes[keep_id].get("name"),
        })
    return steps


def apply(root: dict[str, Any]) -> list[str]:
    nodes, parents = index(root)
    done: list[str] = []
    for merge in MERGES:
        remove_id, keep_id = merge["remove"], merge["keep"]
        if remove_id not in nodes:
            continue
        keep = nodes[keep_id]
        removed = nodes[remove_id]
        # Carry the children across first, so nothing is dropped with the node.
        for child_id in merge["move_children"]:
            child = nodes[child_id]
            removed["children"] = [c for c in removed.get("children") or [] if c.get("id") != child_id]
            keep.setdefault("children", []).append(copy.deepcopy(child))
            done.append(f"moved {child_id} to {keep_id}")
        parent = parents[remove_id]
        parent["children"] = [c for c in parent.get("children") or [] if c.get("id") != remove_id]
        done.append(f"removed {remove_id} from {parent.get('id')}")
        if merge["rename_keep"]:
            done.append(f"renamed {keep_id}: {keep.get('name')!r} -> {merge['rename_keep']!r}")
            keep["name"] = merge["rename_keep"]
        if merge["describe_keep"]:
            keep["desc"] = merge["describe_keep"]
            done.append(f"re-described {keep_id}")
        for other_id, text in merge["describe_others"].items():
            nodes[other_id]["desc"] = text
            done.append(f"re-described {other_id}")
    return done


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--dry-run", action="store_true", help="report what would change; write nothing")
    args = parser.parse_args((argv or sys.argv)[1:])

    import json

    root = json.loads(args.base_graph.read_text(encoding="utf-8"))
    before = subtree_size(root)
    try:
        steps = plan(root)
    except Refused as error:
        print(f"refused: {error}")
        return 1

    pending = 0
    for step in steps:
        print(f"\n{step['what']}")
        if step["state"] == "already applied":
            print("  already applied; nothing to do")
            continue
        pending += 1
        print(f"  remove   {step['remove']}  {step['remove_name']!r}  ({step['removes']} nodes, from {step['remove_from']})")
        print(f"  keep     {step['keep']}  {step['keep_name']!r}")
        for child_id, name in step["moves"]:
            print(f"  move     {child_id}  {name!r}")
        if step["rename_keep"]:
            print(f"  rename   {step['keep']} -> {step['rename_keep']!r}  (committee key unchanged)")
        if step["describe_keep"]:
            print(f"  describe {step['keep']}")
        for other_id in step["describe_others"]:
            print(f"  describe {other_id}")

    if not pending:
        print("\nnothing to do; the curated file already carries both merges")
        return 0
    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0

    done = apply(root)
    after = subtree_size(root)
    # Every node removed must be one this script named, and the arithmetic has
    # to close: a silent extra deletion is the failure this check exists for.
    expected = sum(s["removes"] for s in steps if s["state"] == "to apply")
    if before - after != expected:
        print(f"refused: would have changed the node count by {before - after}, not the {expected} planned")
        return 1
    index(root)  # re-index: refuses a duplicate id introduced by a move
    write_json_file(args.base_graph, root)
    print()
    for line in done:
        print(f"  {line}")
    print(f"\nnodes {before:,} -> {after:,} (-{expected}); wrote {args.base_graph}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
