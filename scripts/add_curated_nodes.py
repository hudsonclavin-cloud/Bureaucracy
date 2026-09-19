"""Add an organisation the graph has no node for, licensed by an official source.

`CLAUDE.md`'s "Known base-graph gaps" lists Monthly Treasury Statement Table 5
lines whose unit this graph simply has no node for — the Administration for
Children and Families at $65.6B, the Corps of Engineers at $10.9B, the Railroad
Retirement Board, the General Services Administration and a dozen more. No alias
can reach them: an alias maps a statement line to a node, and there is no node.
Adding one was recorded as "curation work, not pipeline work" because the curated
file is never hand-edited and nothing was allowed to write a new node.

This is that writer, and it is the fourth sanctioned writer of the curated file,
beside `rename_templated_post_titles.py`, `expand_whitehouse_office.py` and
`rename_units_to_official_wording.py`. It follows the same discipline as the last
of those: **the table proposes and an official source decides.** A row in
`data/curation/new_nodes.json` is a reviewed proposal; nothing is written until
this run re-checks it against the source, live.

A node is added only under one of two licences, named on the row and verified
here rather than trusted:

  - `treasury_statement_line` — the Monthly Treasury Statement itself names the
    unit. The statement is an official record of the United States, and a unit it
    reports outlays for exists. This run fetches the current statement and
    requires exactly ONE non-header row whose canonical name equals the node's;
    two rows of that name, or none, and the row is refused. The section the
    statement files it under is stamped on the node, so a reviewer can see
    whether the parent the row claims agrees with where the Treasury puts it —
    and if it does not, the export gate's same-section rule refuses the line
    later, loudly, rather than publishing a cost across sections.
  - `official_page_label` — an official page carries the name as a label of its
    own, tested with the verifier's own `find_label_region_rule`, under its
    robots policy, User-Agent and readable-text floor. This is the same test
    `verify_base_graph.py` will run, so a node added this way is one that can
    actually earn a source.

Refused before either licence is checked: an id already in the file, a parent
that is not in the file, a name that collides with one of its own siblings, a
name of fewer than two canonical tokens or on the generic list, and a name
`uncheckable_reason` says could never be evidence — there is no point creating a
node the verifier can never confirm.

It is idempotent: a row whose id is already present is a no-op, so re-running
adds nothing twice. It only ever ADDS. It never renames, re-types, re-parents or
removes an existing node — those are other scripts' jobs, or nobody's.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from data_pipeline.crawler.official_directory import USER_AGENT, request_text  # noqa: E402
from data_pipeline.exporter.build_graph import (  # noqa: E402
    DEFAULT_BASE_GRAPH,
    canonical_name_key,
    index_tree,
    load_base_graph,
)
from data_pipeline.exporter.treasury_sections import SectionTree  # noqa: E402
from data_pipeline.json_io import write_json_file  # noqa: E402
from data_pipeline.verification.evidence import (  # noqa: E402
    REGION_CONTENT,
    find_label_region_rule,
    parse_page,
    uncheckable_reason,
)
from data_pipeline.verification.politeness import RobotsPolicy  # noqa: E402

DEFAULT_TABLE = PROJECT_ROOT / "data" / "curation" / "new_nodes.json"

LICENCE_TREASURY = "treasury_statement_line"
LICENCE_PAGE = "official_page_label"
LICENCES = (LICENCE_TREASURY, LICENCE_PAGE)

#: Stamped on every node this script creates, so the panel can say the node
#: exists because an official source named it — not because somebody typed it.
STRUCTURE_SOURCE = {
    LICENCE_TREASURY: "named_in_the_monthly_treasury_statement",
    LICENCE_PAGE: "named_on_an_official_page",
}
DESCRIPTION_SOURCE = {
    LICENCE_TREASURY: "generated_from_the_monthly_treasury_statement",
    LICENCE_PAGE: "generated_from_its_official_page",
}

MIN_NAME_TOKENS = 2
#: The same list `rename_units_to_official_wording.py` refuses, for the same
#: reason: a name that many units answer to identifies none of them.
GENERIC_NAMES = frozenset({
    "inspector general", "office of the inspector general", "general counsel",
    "office of the general counsel", "chief financial officer", "chief of staff",
    "chief information officer", "office of communications", "office of public affairs",
    "about us", "leadership", "our mission", "contact us", "headquarters",
})

DEFAULT_COLOR = "#c84a4a"


def load_table(path: Path) -> list[dict]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("nodes") if isinstance(payload, dict) else payload
    return list(rows or [])


def static_refusal(row: dict, node_map: dict, siblings: dict) -> tuple[str, str] | None:
    """Everything decidable without touching the network."""
    node_id = str(row.get("id") or "")
    parent_id = str(row.get("parentId") or "")
    name = str(row.get("name") or "").strip()
    if not node_id or not name or not parent_id:
        return "row_is_incomplete", "a row needs id, parentId and name"
    if node_id in node_map:
        return "already_added", "the graph already carries this id"
    if parent_id not in node_map:
        return "no_such_parent", f"{parent_id} is not a node in the curated file"
    if str(row.get("licence") or "") not in LICENCES:
        return "unknown_licence", f"licence must be one of {LICENCES}"
    if not str(row.get("basis") or "").strip():
        return "row_states_no_basis", "a row with no basis is an assertion, not an identification"
    key = canonical_name_key(name)
    if len(key.split()) < MIN_NAME_TOKENS:
        return "name_too_short", f"{key!r} is fewer than {MIN_NAME_TOKENS} tokens"
    if key in GENERIC_NAMES:
        return "name_is_generic", f"{name!r} names many units and identifies none"
    reason = uncheckable_reason(name)
    if reason:
        return "name_could_never_be_evidence", reason
    owner = siblings.get(key)
    if owner:
        return "name_collides_with_a_sibling", f"{owner} is already a child of {parent_id} reducing to {key!r}"
    return None


def treasury_rows_by_key(payload: dict) -> dict[str, list[dict]]:
    """Statement rows that could name a unit, indexed by canonical name.

    Two kinds of row are dropped, for the reasons the exporter drops them:

      - a HEADER row, which is the section's title and carries no amount. A
        unit's header line beside its own `Total--` line is one unit reported
        twice, which `CLAUDE.md` already names as the allowed exception to the
        one-line-one-node rule — counting both would make every unit ambiguous.
      - a row inside a RECEIPTS-type subtree. "Corps of Engineers" appears once
        as the agency and once under a receipts heading, where it means receipts
        *of* the Corps rather than the Corps; `SectionTree.receipts_component_ids`
        is the exporter's own answer to which rows those are, so this uses it
        rather than reimplementing the distinction and drifting from it.

    What survives is the set of rows that genuinely name a unit, so "exactly one"
    means what it should: the statement reports this unit, once.
    """
    rows = list(payload.get("outlayRows") or [])
    tree = SectionTree.from_rows(rows)
    receipts = tree.receipts_component_ids()
    index: dict[str, list[dict]] = {}
    for row in rows:
        if row.get("is_header"):
            continue
        if str(row.get("classification_id") or "") in receipts:
            continue
        section = tree.top_section_of(row)
        row = dict(row)
        row["treasurySection"] = str((section or {}).get("name") or "")
        index.setdefault(canonical_name_key(row.get("name")), []).append(row)
    return index


def describe_from_treasury(name: str, row: dict, period: str) -> str:
    section = str(row.get("treasurySection") or "").strip()
    where = f" under {section}" if section else ""
    return (f"The Monthly Treasury Statement reports outlays for {name}{where} "
            f"({period}). This node exists because the statement names the unit; "
            f"nothing further about it has been read.")


def describe_from_page(name: str, url: str, matched: str) -> str:
    return (f"{name} is named on {url}, which labels it as {matched!r}. This node "
            f"exists because that page names the unit; nothing further about it "
            f"has been read.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    parser.add_argument("--dry-run", action="store_true", help="decide everything, write nothing")
    parser.add_argument("--ids", nargs="*", default=[])
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv[1:] if argv else None)

    root = load_base_graph(args.base_graph)
    node_map, _ = index_tree(root)
    rows = load_table(args.table)
    if args.ids:
        wanted = set(args.ids)
        rows = [r for r in rows if str(r.get("id")) in wanted]

    #: A new node may not be indistinguishable from one of its own siblings.
    #: Scoped to siblings for the reason the rename table's rule is: two units
    #: under different parents may honestly share a name.
    sibling_keys: dict[str, dict[str, str]] = {}
    for parent in node_map.values():
        pid = str(parent.get("id") or "")
        sibling_keys[pid] = {
            canonical_name_key(c.get("name")): str(c.get("id") or "")
            for c in (parent.get("children") or [])
        }

    needs_treasury = any(str(r.get("licence")) == LICENCE_TREASURY for r in rows)
    statement: dict = {}
    if needs_treasury:
        from probe_treasury_rows import fetch_payload  # noqa: PLC0415 — only when a row needs it
        statement = fetch_payload(args.timeout)
    by_key = treasury_rows_by_key(statement)
    period = str((statement.get("budgetSummary") or {}).get("label") or "the current statement")

    robots = RobotsPolicy(user_agent=USER_AGENT, timeout=args.timeout)
    pages: dict[str, tuple[str, object]] = {}
    results: list[dict] = []
    added: list[tuple[str, str]] = []
    last_fetch = 0.0

    for row in rows:
        node_id = str(row.get("id") or "")
        parent_id = str(row.get("parentId") or "")
        name = str(row.get("name") or "").strip()
        verdict = static_refusal(row, node_map, sibling_keys.get(parent_id, {}))
        if verdict:
            results.append({"id": node_id, "added": False, "reason": verdict[0], "detail": verdict[1]})
            continue

        licence = str(row.get("licence"))
        node_desc, structure_detail = None, None

        if licence == LICENCE_TREASURY:
            matches = by_key.get(canonical_name_key(name)) or []
            if len(matches) != 1:
                results.append({"id": node_id, "added": False,
                                "reason": "statement_does_not_name_one_such_unit",
                                "detail": f"{len(matches)} rows in the current statement carry this name"})
                continue
            hit = matches[0]
            node_desc = describe_from_treasury(name, hit, period)
            structure_detail = str(hit.get("name") or "")
            row_section = str(hit.get("treasurySection") or "")
        else:
            url = str(row.get("url") or "")
            if url not in pages:
                allowed, why = robots.allows(url)
                if not allowed:
                    pages[url] = ("refused", why)
                else:
                    wait = max(args.sleep, robots.crawl_delay(url)) - (time.monotonic() - last_fetch)
                    if wait > 0:
                        time.sleep(wait)
                    try:
                        pages[url] = ("page", parse_page(request_text(url, timeout=args.timeout)))
                    except Exception as error:  # noqa: BLE001 — a failed fetch adds nothing
                        pages[url] = ("failed", f"{error.__class__.__name__}: {error}")
                    last_fetch = time.monotonic()
            kind, value = pages[url]
            if kind != "page":
                results.append({"id": node_id, "added": False,
                                "reason": f"page_{kind}", "detail": str(value)})
                continue
            page = value
            if not page.readable:
                results.append({"id": node_id, "added": False, "reason": "page_below_the_readable_floor",
                                "detail": f"{page.content_chars} readable chars"})
                continue
            hit = find_label_region_rule(name, page, is_post=False, regions_allowed=(REGION_CONTENT,))
            if not hit:
                results.append({"id": node_id, "added": False,
                                "reason": "page_does_not_label_the_name", "detail": url})
                continue
            node_desc = describe_from_page(name, url, hit[0])
            structure_detail = url
            row_section = ""

        node = {
            "id": node_id,
            "name": name,
            "type": str(row.get("type") or "Agency"),
            "desc": str(row.get("desc") or node_desc),
            "structureSource": STRUCTURE_SOURCE[licence],
            "structureSourceDetail": structure_detail,
            "employees": None,
            "budget": None,
            "color": str(row.get("color") or DEFAULT_COLOR),
            "children": [],
        }
        if not row.get("desc"):
            node["descriptionSource"] = DESCRIPTION_SOURCE[licence]
        if licence == LICENCE_TREASURY and row_section:
            node["treasurySectionAtAdd"] = row_section

        results.append({"id": node_id, "added": True, "name": name, "parentId": parent_id,
                        "licence": licence, "detail": structure_detail})
        added.append((node_id, parent_id))
        if not args.dry_run:
            node_map[parent_id].setdefault("children", []).append(node)
            node_map[node_id] = node
            sibling_keys.setdefault(parent_id, {})[canonical_name_key(name)] = node_id

    if args.json:
        print(json.dumps({"added": len(added), "results": results}, indent=1))
    else:
        for item in results:
            if item.get("added"):
                print(f"  + {item['name']!r}\n      under {item['parentId']}   [{item['licence']}]  {item['detail']}")
        refused = [r for r in results if not r.get("added")]
        if refused:
            print(f"\nnot added ({len(refused)}):")
            for item in refused:
                print(f"  {str(item['id'])[:56]:58s} {item['reason']}")
                if item.get("detail"):
                    print(f"      {str(item['detail'])[:150]}")
        print(f"\nadded {len(added)}  refused {len(results) - len(added)}  of {len(rows)} rows")
    if args.dry_run:
        print("dry run: nothing written.")
        return 0
    if added:
        write_json_file(args.base_graph, root)
        print(f"wrote {args.base_graph}")
    else:
        print("nothing to do; the curated file is unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
