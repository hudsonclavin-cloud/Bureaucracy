"""Alternative names a node answers to, and the narrow licence they carry.

A node keeps the name the graph displays. `data/curation/node_aliases.json`
records, per node, the other names an official document may print for the same
unit -- OPM's current PLUM export files AmeriCorps' 31 live rows under
"CORPORATION FOR NATIONAL AND COMMUNITY SERVICE"; the United States
Government Manual prints "Federal Motor Carrier Safety Administration" where
this graph writes "Admin"; its entry for the Vice President is headed "The
Vice President". None of those is a document failing to name the unit. They
are this graph's own typography, or a name this repository has written down
as denoting the same unit.

The table is the same shape as `unit_renames.json`, `TREASURY_ROW_ALIASES` and
`USASPENDING_NAME_ALIASES`: a reviewed identification with the basis written
beside it, checked rather than trusted. Per row: the node id, the node's
CURRENT name (so a rename by any route invalidates the row rather than
letting it carry a badge earned by a name the node no longer has), the
alternative, and a `basis` naming the authority on which the two denote one
unit.

Refusals, all of them decidable offline and all of them applied on every run:

  - `no_such_node` / `row_is_incomplete` / `basis_missing`
  - `curated_name_has_changed`   the node no longer carries the stated name
  - `alias_is_a_no_op`           the alternative already reduces to the node's
                                 own key, so it changes no outcome
  - `alias_too_short`            a canonical key of one token. "president" is
                                 a word on thousands of .gov pages, and the
                                 alias is consulted by the page-label test;
                                 this is the same floor
                                 `uncheckable_reason(..., is_post=True)` puts
                                 under a bare job title, for the same reason.
  - `alias_is_generic`           `GENERIC_NAMES`: "Inspector General" names 72
                                 nodes here and sits in every .gov footer
  - `alias_collides_with_a_sibling`  the alternative reduces to a SIBLING's
                                 name or to a sibling's accepted alias.
                                 Sibling-scoped exactly as
                                 `rename_units_to_official_wording.py` scopes
                                 it, and for the reason recorded there: two
                                 nodes under one parent sharing a name is a
                                 real ambiguity nothing downstream could
                                 resolve, while the same name under two
                                 different parents is what the chambers call
                                 two appropriations subcommittees.

**What may consult this, and what may not.** The alias is a claim about two
NAMES. It is consulted only by evidence that a unit exists and is named --
the page-label test in `evidence.py`, the Government Manual's entry join, the
chambers' committee lists, and the current PLUM export's agency scoping. It
is never consulted by a join that lands a number: not `headcounts.py`, not
the Treasury row matching, not `usaspending.py`, `net_cost.py` or
`omb_budget.py`. Each of those already has its own reviewed table where a
figure is at stake, and `CLAUDE.md` records why a shared one would be
dangerous: FedScope's "DEPARTMENT OF THE ARMY" is a civilian department and
the graph's "U.S. Army" the uniformed service, so one table serving both
kinds of claim would let a name written down for a badge start dividing
money. The rule is structural rather than a matter of discipline -- the
modules above do not import this one, and `tests/test_node_aliases.py`
asserts the whole repository's import list against a whitelist.

**A confirmation obtained this way is weaker and says so.** The record
carries `matchRule: matched_on_a_recorded_alternative_name` with the
alternative and its basis; the node publishes `verificationAliasMatch`; and
`cap_alias_only_confirmations` holds a node whose every official source was
reached through an alias at `partial`, never `verified`. That is the same
deliberate downgrade `usaspending.py` makes for an aliased key: `verified` is
what two independent documents naming the unit earn, and "somebody wrote down
that these two names are the same unit" is not that.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from data_pipeline.exporter.build_graph import canonical_name_key

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ALIAS_TABLE = PROJECT_ROOT / "data" / "curation" / "node_aliases.json"

#: The rule stamped on a record whose match needed the table. A different
#: string from `evidence.MATCH_RULE_COMMITTEE` because it is a different
#: claim: the fold sets aside words the chambers' own sites demonstrably
#: omit, while this says the source printed another name entirely.
MATCH_RULE_ALIAS = "matched_on_a_recorded_alternative_name"

#: The field the node publishes. One block per node, accumulating every
#: alias-derived source, so `cap_alias_only_confirmations` can see the whole
#: set rather than whichever module wrote first.
ALIAS_FIELD = "verificationAliasMatch"

#: Whose name the alias stood in for. "node" is the unit itself: the page or
#: the entry printed another name for this node. "organisation" is the
#: scoping case: the current PLUM export files a post's row under an agency
#: name that reached this node's ancestor through the table, while the post's
#: own title matched directly.
ALIAS_SCOPE_NODE = "node"
ALIAS_SCOPE_ORGANISATION = "organisation"
ALIAS_SCOPES = (ALIAS_SCOPE_NODE, ALIAS_SCOPE_ORGANISATION)

#: The ceiling a node reaches on alias-derived evidence alone. 0.4 for one
#: URL plus 0.3 for an official site is 0.70 in `verify_node_sources`, which
#: is already `partial`; the cap bites when a second alias-derived document
#: would otherwise add 0.1 and cross 0.80.
ALIAS_CONFIDENCE_CEILING = 0.7
ALIAS_STATUS_CEILING = "partial"

#: An alternative reducing to fewer than this many tokens is refused.
MIN_ALIAS_TOKENS = 2

#: Names too generic to identify a unit even when a document carries them.
#: The stamped administrative titles `CLAUDE.md` records recurring 92, 81,
#: 80, 71 and 47 times across 76 organisations, plus the words a `.gov`
#: footer carries as standard furniture. `rename_units_to_official_wording.py`
#: imports this list rather than keeping a second copy.
GENERIC_NAMES = frozenset({
    "inspector general", "office of the inspector general", "general counsel",
    "office of the general counsel", "chief financial officer", "chief of staff",
    "chief information officer", "office of communications", "office of public affairs",
    "about us", "leadership", "our mission", "contact us", "headquarters",
})


@dataclass(frozen=True)
class Alias:
    """One accepted row: this node answers to this other name, on this basis."""

    node_id: str
    node_name: str
    alias: str
    key: str
    basis: str
    added_on: str = ""

    def block(self, *, source: str, url: str, matched_text: str, scope: str = ALIAS_SCOPE_NODE) -> dict[str, Any]:
        """The shape a module hands to `stamp_alias_match`."""
        return {
            "source": str(source),
            "url": str(url),
            "alias": self.alias,
            "basis": self.basis,
            "matchedText": str(matched_text),
            "scope": scope if scope in ALIAS_SCOPES else ALIAS_SCOPE_NODE,
            # Whose row this is. For an organisation-scoped match the row
            # belongs to an ancestor rather than to the node carrying the
            # block, and the gate has to look the alternative up under the
            # node that actually owns it.
            "owner": self.node_id,
        }


class AliasTable:
    """The accepted rows, indexed both ways, with every refusal kept."""

    def __init__(self, accepted: Mapping[str, Sequence[Alias]], refusals: Sequence[Mapping[str, Any]]):
        self._by_node: dict[str, tuple[Alias, ...]] = {k: tuple(v) for k, v in accepted.items() if v}
        self._by_key: dict[str, tuple[str, ...]] = {}
        for node_id, rows in self._by_node.items():
            for row in rows:
                self._by_key[row.key] = self._by_key.get(row.key, ()) + (node_id,)
        self.refusals = [dict(r) for r in refusals]

    def __len__(self) -> int:
        return sum(len(v) for v in self._by_node.values())

    @property
    def node_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_node))

    def for_node(self, node_id: Any) -> tuple[Alias, ...]:
        return self._by_node.get(str(node_id or ""), ())

    def keys_for(self, node_id: Any) -> tuple[str, ...]:
        return tuple(a.key for a in self.for_node(node_id))

    def nodes_for_key(self, key: Any) -> tuple[str, ...]:
        """Which nodes answer to this canonical key. A key reaching two nodes
        is returned as two, and every caller refuses it -- the rule every
        name-matched source in this project already applies."""
        return self._by_key.get(str(key or ""), ())

    def by_key(self, node_id: Any, key: Any) -> Alias | None:
        for row in self.for_node(node_id):
            if row.key == str(key or ""):
                return row
        return None

    def by_alias(self, node_id: Any, alias: Any) -> Alias | None:
        """The row whose alternative is exactly this string. Used by the
        exporter and mirrored by the gate: a published claim must quote an
        alternative the committed table really carries for that node."""
        text = str(alias or "").strip()
        for row in self.for_node(node_id):
            if row.alias == text:
                return row
        return None

    def matching(self, node_id: Any, text: Any) -> Alias | None:
        """The row whose alternative this text reduces to."""
        return self.by_key(node_id, canonical_name_key(text))

    def extra_keys(self, node_id: Any, node_name: Any) -> tuple[str, ...]:
        """The alias keys a name index should file this node under besides its
        own, with the node's own key never repeated."""
        own = canonical_name_key(node_name)
        return tuple(k for k in self.keys_for(node_id) if k and k != own)


def load_rows(path: str | Path | None = None) -> list[dict[str, Any]]:
    resolved = Path(path or DEFAULT_ALIAS_TABLE)
    if not resolved.exists():
        return []
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    rows = payload.get("aliases") if isinstance(payload, dict) else payload
    return [dict(r) for r in (rows or []) if isinstance(r, dict)]


def check_row(
    row: Mapping[str, Any],
    node: Mapping[str, Any] | None,
    sibling_keys: Mapping[str, str],
) -> tuple[str, str] | None:
    """Everything a row must clear. Returns (reason, detail) or None.

    `sibling_keys` maps every canonical key already spoken for under this
    node's parent -- a sibling's own name, or a sibling's already-accepted
    alias -- to the node that owns it.
    """
    node_id = str(row.get("id") or "")
    alias = str(row.get("alias") or "").strip()
    expected = str(row.get("name") or "").strip()
    basis = str(row.get("basis") or "").strip()
    if not node:
        return "no_such_node", node_id
    if not alias or not expected:
        return "row_is_incomplete", "a row needs both 'name' (the node's current name) and 'alias'"
    if not basis:
        return "basis_missing", "a row with no basis is an assertion, not an identification"
    name = str(node.get("name") or "")
    if name != expected:
        return "curated_name_has_changed", f"the row was written against {expected!r}, the node now reads {name!r}"
    key = canonical_name_key(alias)
    if not key:
        return "alias_is_empty", alias
    if key == canonical_name_key(name):
        return "alias_is_a_no_op", f"both names reduce to {key!r}, so no matcher outcome changes"
    if len(key.split()) < MIN_ALIAS_TOKENS:
        return "alias_too_short", f"{key!r} is fewer than {MIN_ALIAS_TOKENS} tokens"
    if key in GENERIC_NAMES:
        return "alias_is_generic", f"{alias!r} names many units and identifies none"
    owner = sibling_keys.get(key)
    if owner and owner != node_id:
        return "alias_collides_with_a_sibling", f"{owner} already answers to {key!r} under the same parent"
    return None


def build_alias_table(
    rows: Iterable[Mapping[str, Any]],
    node_map: Mapping[str, Mapping[str, Any]],
    parent_map: Mapping[str, str | None],
) -> AliasTable:
    """Adjudicate the rows against the tree as it is now."""
    children_of: dict[str, list[str]] = {}
    for node_id in node_map:
        parent = parent_map.get(node_id)
        if parent:
            children_of.setdefault(str(parent), []).append(str(node_id))
    # Every key already spoken for, per parent: a sibling's own name first,
    # then aliases as they are accepted, so two rows cannot both take one key.
    spoken_for: dict[str, dict[str, str]] = {}
    for parent, kids in children_of.items():
        taken: dict[str, str] = {}
        for kid in kids:
            key = canonical_name_key(node_map[kid].get("name"))
            if key:
                taken.setdefault(key, kid)
        spoken_for[parent] = taken

    accepted: dict[str, list[Alias]] = {}
    refusals: list[dict[str, Any]] = []
    for row in rows:
        node_id = str(row.get("id") or "")
        node = node_map.get(node_id)
        parent = str(parent_map.get(node_id) or "")
        siblings = spoken_for.setdefault(parent, {}) if parent else {}
        verdict = check_row(row, node, siblings)
        if verdict:
            refusals.append({"id": node_id, "alias": row.get("alias"), "reason": verdict[0], "detail": verdict[1]})
            continue
        assert node is not None  # check_row refuses a missing node
        alias = Alias(
            node_id=node_id,
            node_name=str(node.get("name") or ""),
            alias=str(row.get("alias") or "").strip(),
            key=canonical_name_key(row.get("alias")),
            basis=str(row.get("basis") or "").strip(),
            added_on=str(row.get("addedOn") or ""),
        )
        if any(existing.key == alias.key for existing in accepted.get(node_id, [])):
            refusals.append({"id": node_id, "alias": alias.alias, "reason": "duplicate_row",
                             "detail": f"{alias.key!r} is already recorded for this node"})
            continue
        accepted.setdefault(node_id, []).append(alias)
        if parent:
            siblings.setdefault(alias.key, node_id)
    return AliasTable(accepted, refusals)


def load_alias_table(
    root: Mapping[str, Any] | None = None,
    *,
    path: str | Path | None = None,
    index_tree=None,
    node_map: Mapping[str, Mapping[str, Any]] | None = None,
    parent_map: Mapping[str, str | None] | None = None,
) -> AliasTable:
    """The committed table, adjudicated against a tree (or an index of one)."""
    if node_map is None or parent_map is None:
        if root is None:
            return AliasTable({}, [])
        if index_tree is None:
            from data_pipeline.exporter.build_graph import index_tree as _index_tree

            index_tree = _index_tree
        node_map, parent_map = index_tree(root)
    return build_alias_table(load_rows(path), node_map, parent_map)


# --------------------------------------------------------------------------
# What a node publishes


def stamp_alias_match(node: dict[str, Any], entry: Mapping[str, Any]) -> None:
    """Record that a claim on this node was reached through an alternative
    name. The first entry supplies the block's headline fields; every entry
    is kept in `matches` and every URL in `urls`, because the cap below has
    to see the whole set -- a node reached by two alias-derived documents is
    exactly the case that would otherwise cross into `verified`."""
    block = node.get(ALIAS_FIELD)
    if not isinstance(block, dict):
        block = {
            "alias": str(entry.get("alias") or ""),
            "basis": str(entry.get("basis") or ""),
            "matchedText": str(entry.get("matchedText") or ""),
            "scope": str(entry.get("scope") or ALIAS_SCOPE_NODE),
            "source": str(entry.get("source") or ""),
            "owner": str(entry.get("owner") or ""),
            "urls": [],
            "matches": [],
        }
        node[ALIAS_FIELD] = block
    url = str(entry.get("url") or "")
    if url and url not in block["urls"]:
        block["urls"].append(url)
    block["matches"].append({
        "source": str(entry.get("source") or ""),
        "url": url,
        "alias": str(entry.get("alias") or ""),
        "basis": str(entry.get("basis") or ""),
        "matchedText": str(entry.get("matchedText") or ""),
        "scope": str(entry.get("scope") or ALIAS_SCOPE_NODE),
        "owner": str(entry.get("owner") or ""),
    })


def cap_alias_only_confirmations(root: Mapping[str, Any], *, index_tree=None) -> dict[str, int]:
    """Hold a node whose every official source was reached through an alias at
    `partial`. Runs after the last evidence module, because `verify_node_sources`
    recomputes the status from the URL count on every stamp and would undo it."""
    from data_pipeline.processors.normalize_nodes import classify_source_url

    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, _ = index_tree(root)
    stats = {"nodes_with_an_alias_match": 0, "capped_to_partial": 0, "not_capped_other_evidence": 0}
    for node in node_map.values():
        block = node.get(ALIAS_FIELD)
        if not isinstance(block, dict):
            continue
        stats["nodes_with_an_alias_match"] += 1
        alias_urls = {str(u) for u in (block.get("urls") or [])}
        # `official_site` exactly, not any `.gov` host, because the two
        # differ on the URLs that decide this. `classify_source_url` files
        # the FiscalData dataset as `government_dataset` and a Federal
        # Register agency page as `federal_register`, and neither earns the
        # +0.3 that makes a node `verified` -- so NOAA, FMCSA and NHTSA sat
        # at 0.4 on a Treasury cost URL alone, and ONE aliased Manual entry
        # took each of them to 0.8. Those are the nodes this cap exists for.
        # A genuine official site the table had no part in (darpa.mil) still
        # lifts the cap, which is the honest reading. The gate mirrors the
        # same three rules, pinned equal by a test.
        official = [
            str(u) for u in (node.get("sourceUrls") or [])
            if classify_source_url(str(u)) == "official_site"
        ]
        if not official or not set(official) <= alias_urls:
            # Something the table had no part in also names this unit; that
            # evidence is worth what it is worth and is not held back.
            block.pop("gradedAtMost", None)
            stats["not_capped_other_evidence"] += 1
            continue
        block["gradedAtMost"] = ALIAS_STATUS_CEILING
        if float(node.get("confidenceScore") or 0.0) > ALIAS_CONFIDENCE_CEILING:
            node["confidenceScore"] = ALIAS_CONFIDENCE_CEILING
        if str(node.get("verificationStatus") or "") == "verified":
            node["verificationStatus"] = ALIAS_STATUS_CEILING
        stats["capped_to_partial"] += 1
    return stats
