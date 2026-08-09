#!/usr/bin/env python3
"""Release gate for the published graph.

Reads output/graph.json (or a path given as the first argument) and exits
nonzero if any node asserts more than its evidence supports. This runs over the
real artefact rather than a fixture, which is the only way it could have caught
the three validator failures of this week: each one produced a plausible number
and passed its own unit tests.

The gate never writes. Run it before every push that touches output/.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GRAPH = PROJECT_ROOT / "output" / "graph.json"

EXPECTED_ROOT_ID = "the-constitution-of-the-united-states"
MAX_TOP_LEVEL_CHILDREN = 10
CHILD_SUM_TOLERANCE = 0.005  # 0.5%, for rounding in the apportionment cascade
SAMPLE_LIMIT = 20


def walk(node, parent=None):
    """Yield (node, parent) for every dict node in the tree."""
    yield node, parent
    for child in node.get("children") or []:
        if isinstance(child, dict):
            yield from walk(child, node)


def amount_of(node):
    value = node.get("resolved_total_amount")
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def label(node):
    return "{} ({})".format(node.get("name") or "Unnamed Node", node.get("id") or "no-id")


class Gate:
    def __init__(self):
        self.failures = []

    def check(self, name, violations, detail=""):
        """Record a check. `violations` is a list of human-readable strings."""
        if violations:
            self.failures.append((name, violations))
            print("FAIL  {} — {} violation(s){}".format(name, len(violations), detail))
            for line in violations[:SAMPLE_LIMIT]:
                print("        {}".format(line))
            if len(violations) > SAMPLE_LIMIT:
                print("        … and {} more".format(len(violations) - SAMPLE_LIMIT))
        else:
            print("ok    {}{}".format(name, detail))


def main(argv):
    graph_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_GRAPH
    if not graph_path.exists():
        print("FATAL: no graph at {}".format(graph_path))
        return 2

    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    nodes = [node for node, _ in walk(graph)]
    pairs = list(walk(graph))
    print("Validating {} ({:,} nodes)\n".format(graph_path, len(nodes)))

    gate = Gate()

    # 1. Root identity.
    root_id = str(graph.get("id") or "")
    gate.check(
        "root id",
        [] if root_id == EXPECTED_ROOT_ID else ["root id is {!r}, expected {!r}".format(root_id, EXPECTED_ROOT_ID)],
    )

    # 2. Exactly one measured cost. More than one means something other than the
    #    Treasury anchor claimed measurement; zero means the anchor is missing.
    verified = [n for n in nodes if str(n.get("costVerificationStatus") or "").lower() == "verified"]
    if len(verified) == 1:
        gate.check("exactly one measured cost", [], " — {}".format(label(verified[0])))
    else:
        gate.check(
            "exactly one measured cost",
            ["{} nodes claim costVerificationStatus 'verified'".format(len(verified))]
            + [label(n) for n in verified],
        )

    # 3. Every amount carries a provenance label.
    gate.check(
        "every amount has a cost_status",
        [label(n) for n in nodes if amount_of(n) is not None and not n.get("cost_status")],
    )

    # 4. attachToRoot together with parentId asserts a discovered reporting line
    #    to the Constitution.
    gate.check(
        "no attachToRoot with a parentId",
        [label(n) for n in nodes if n.get("attachToRoot") and n.get("parentId")],
    )

    # 5. A part cannot cost more than the whole.
    over_parent = []
    for node, parent in pairs:
        if parent is None:
            continue
        child_amount = amount_of(node)
        parent_amount = amount_of(parent)
        if child_amount is None or parent_amount is None:
            continue
        if child_amount > parent_amount * (1 + 1e-9):
            over_parent.append(
                "{} = {:,.2f} > parent {} = {:,.2f}".format(
                    label(node), child_amount, label(parent), parent_amount
                )
            )
    gate.check("no child costs more than its parent", over_parent)

    # 6. Direct children must not sum past the root total.
    root_amount = amount_of(graph)
    child_sum = sum(a for a in (amount_of(c) for c in (graph.get("children") or []) if isinstance(c, dict)) if a is not None)
    if root_amount is None:
        gate.check("children sum within the root total", ["root has no resolved_total_amount"])
    else:
        delta = child_sum - root_amount
        pct = (delta / root_amount * 100) if root_amount else 0.0
        detail = " — children {:,.2f} vs root {:,.2f} (delta {:+,.2f}, {:+.4f}%)".format(
            child_sum, root_amount, delta, pct
        )
        over = child_sum > root_amount * (1 + CHILD_SUM_TOLERANCE)
        gate.check(
            "children sum within the root total",
            ["children exceed the root total by {:,.2f} ({:.4f}%)".format(delta, pct)] if over else [],
            detail,
        )

    # 7. sourceCount and sourceUrls must never disagree.
    disagreements = []
    for node in nodes:
        try:
            count = int(node.get("sourceCount") or 0)
        except (TypeError, ValueError):
            count = 0
        urls = node.get("sourceUrls")
        urls = urls if isinstance(urls, list) else []
        if count > 0 and not urls:
            disagreements.append("{} claims {} source(s) with an empty sourceUrls".format(label(node), count))
        elif urls and count == 0:
            disagreements.append("{} has {} sourceUrls but sourceCount 0".format(label(node), len(urls)))
    gate.check("sourceCount agrees with sourceUrls", disagreements)

    # 8. Duplicate ids.
    id_counts = Counter(str(n.get("id") or "") for n in nodes)
    gate.check(
        "no duplicate node ids",
        ["{} appears {} times".format(node_id, count) for node_id, count in id_counts.items() if count > 1],
    )

    # 9. Root fan-out. 3,438 top-level children was the symptom that started this.
    top_level = graph.get("children") or []
    gate.check(
        "root has at most {} direct children".format(MAX_TOP_LEVEL_CHILDREN),
        ["root has {} direct children".format(len(top_level))] if len(top_level) > MAX_TOP_LEVEL_CHILDREN else [],
        " — {}".format(len(top_level)),
    )

    # Reported, never fatal.
    verification = Counter(str(n.get("verificationStatus") or "none") for n in nodes)
    cost_status = Counter(str(n.get("cost_status") or "none") for n in nodes)
    no_source = sum(
        1
        for n in nodes
        if not (n.get("sourceUrls") if isinstance(n.get("sourceUrls"), list) else []) and not n.get("lastVerified")
    )
    print("\n--- reported, not enforced ---")
    print("  nodes                : {:,}".format(len(nodes)))
    print("  with a cost          : {:,}".format(sum(1 for n in nodes if amount_of(n) is not None)))
    print("  verification         : {}".format(dict(verification.most_common())))
    print("  cost_status          : {}".format(dict(cost_status.most_common())))
    print("  no source recorded   : {:,}".format(no_source))

    print()
    if gate.failures:
        total = sum(len(v) for _, v in gate.failures)
        print("FAILED: {} check(s), {} violation(s) total".format(len(gate.failures), total))
        return 1
    print("PASSED: all checks clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
