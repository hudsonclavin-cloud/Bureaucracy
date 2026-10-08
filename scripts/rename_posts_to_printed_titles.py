"""Rename a post to the title a committed official document prints for it.

    python scripts/rename_posts_to_printed_titles.py --dry-run   # what would change
    python scripts/rename_posts_to_printed_titles.py             # write the curated file

**The sanctioned writer for this class of rename** (since 2026-10-07): a
POST whose curated name is an abbreviation or a generic stand-in for an
office that a document this repository has already committed prints in full.
The curated file is never hand-edited; `rename_templated_post_titles.py`
renames templated cabinet heads, `rename_units_to_official_wording.py`
renames organisations from their own pages, and this script renames the
posts `data/curation/post_renames.json` lists, and nothing else. It only
renames: it never creates, re-types, re-parents or removes a node.

Why it exists. The pay routes that price a post join by name, and they are
deliberately strict -- equality, never containment. Two sets of posts the
documents in hand price could not be reached for want of the name:

  - the Space Force's "Senior Enlisted Advisor", where Schedule 8 of the
    pay-adjustment order (the note to 5 U.S.C. 5332) prints "Chief Master
    Sergeant of the Space Force" in the enlisted footnote `military_pay.py`
    reads by equality; and
  - the three "Deputy USTR — <portfolio>" nodes, where 5 U.S.C. 5314 prints
    the class "Deputy United States Trade Representatives (3)" and the
    counted-class rule needs the class's singular office first and whole.

Loosening either matcher would be the wrong fix -- this repository refuses
that by name -- so the names are fixed where names are fixed.

**The table proposes; the committed document decides.** It is used the way
`rename_templated_post_titles.py` uses the Code: it selects, it never
produces. A row is applied only when all of these hold, and the reason is
printed for every one that does not:

  - the node exists, is a post, still carries the exact name the row was
    written against (`from`) and still sits under the parent it was written
    against (`parentId`), so a rename or a move by any other route is never
    overwritten on a stale reading;
  - the licensing document is the committed fixture, its digest recomputed
    from the bytes against the `.meta.json` its fetch wrote, and it prints the
    licensing string now:
      * `schedule_8_footnote_title` -- `printed` is one printed item of
        Schedule 8's enlisted footnote, parsed by `military_pay.load_schedule_8`
        exactly as the pay route parses it, and `to` IS that item;
      * `opm_current_plum_export_title` (since 2026-10-08) -- `printed` is
        a title OPM's committed current PLUM export prints, verbatim, on ONE
        live (Filled or Vacant) listing filed under exactly the row's
        `agency` and `organization`, read through
        `plum_current.load_plum_export` (`READ_COLUMNS` only, never the
        incumbent columns) with the file's digest recomputed; `to` must
        reduce under `canonical_name_key` to it -- the casing is the
        reviewer's, the words are the export's;
      * `us_code_counted_class_title` -- `printed` is a counted class title
        ("... (N)") in the section's OPERATIVE text (never the publisher's
        notes beneath it, which print repealed and superseded titles); the
        row's `singular` is that title's noun phrase with its count and one
        trailing "s" removed, the only plural this licence accepts; `to` is
        the singular, a separator from `COUNTED_CLASS_SEPARATORS`, and the
        qualifier the node ALREADY carries after the same separator -- so
        the rename changes only the office half, and the qualifier stays the
        graph's own and uncited; the composing section (`composedBy`) prints
        its quote in its operative text; and no more rows cite the class than
        its title counts;
  - the rename buys something (`canonical_name_key` differs), the proposed
    name is at least two tokens and is not a bare generic title, and it does
    not collide with a SIBLING's name.

It is idempotent: a row whose node already carries the proposed name is
reported as already applied and touches nothing. It reads no person's name:
the fixtures it reads are a statute's text, a pay schedule and the current
PLUM export's seven READ_COLUMNS, which name no person.

What a rename costs is measured, not assumed: evidence keyed on the old name
(a page check, a PLUM listing, a Government Manual row) stops applying under
the rename guard each module keeps, and the run that applies a row must say
what it lost as well as what it bought.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.exporter.build_graph import (  # noqa: E402
    DEFAULT_BASE_GRAPH,
    canonical_name_key,
    index_tree,
    is_post_node,
    load_base_graph,
)
from data_pipeline.json_io import write_json_file  # noqa: E402
from data_pipeline.verification.aliases import GENERIC_NAMES  # noqa: E402
from data_pipeline.verification.derived_pay import Unreadable as SectionUnreadable  # noqa: E402
from data_pipeline.verification.military_pay import load_schedule_8  # noqa: E402
from data_pipeline.verification.plum_current import (  # noqa: E402
    Unreadable as ExportUnreadable,
    load_plum_export,
)
from data_pipeline.verification.statutory_schedule import (  # noqa: E402
    COUNTED_CLASS_SEPARATORS,
    Unreadable as ScheduleUnreadable,
    counted_class_count,
    load_basis_section,
)

DEFAULT_TABLE = PROJECT_ROOT / "data" / "curation" / "post_renames.json"

LICENCE_FOOTNOTE = "schedule_8_footnote_title"
LICENCE_COUNTED_CLASS = "us_code_counted_class_title"
LICENCE_CURRENT_EXPORT = "opm_current_plum_export_title"
LICENCES = (LICENCE_FOOTNOTE, LICENCE_COUNTED_CLASS, LICENCE_CURRENT_EXPORT)

#: What this script stamps on a node it renames, per licence, so the site and
#: a reviewer can see where the name came from -- the same two fields the
#: other renaming scripts write, plus the string the document prints.
NAME_SOURCES = {
    LICENCE_FOOTNOTE: "named_in_schedule_8_of_the_pay_adjustment_order",
    LICENCE_COUNTED_CLASS: "office_spelled_as_the_executive_schedule_class_title_prints_it",
    LICENCE_CURRENT_EXPORT: "title_as_the_opm_current_plum_export_prints_it",
}

#: One token is a word, not an office.
MIN_NAME_TOKENS = 2

_COUNT_SUFFIX = re.compile(r"\s*\((\d+)\)\s*$")


def load_table(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("renames") if isinstance(payload, dict) else payload
    return [dict(row) for row in rows or []]


def _resolve(fixture: str, root: Path) -> Path:
    path = Path(str(fixture or ""))
    return path if path.is_absolute() else root / path


def plural_of(singular: str) -> str:
    """The one plural this licence accepts: a trailing "s". "Assistant
    Attorneys General" would need a second rule, and none is granted until a
    row needs it -- an unrecognised plural refuses rather than guesses."""
    return f"{singular}s"


def split_office(name: str) -> tuple[str, str, str] | None:
    """(office, separator, qualifier) at the first separator from the closed
    list that occurs in the name, or None."""
    best: tuple[int, str] | None = None
    for separator in COUNTED_CLASS_SEPARATORS:
        index = name.find(separator)
        if index > 0 and (best is None or index < best[0]):
            best = (index, separator)
    if best is None:
        return None
    index, separator = best
    return name[:index], separator, name[index + len(separator):]


def check_static(row: dict[str, Any], node: dict[str, Any] | None, parent_id: str,
                 sibling_keys: dict[str, str]) -> tuple[str, str] | None:
    """Everything decidable without reading a document."""
    node_id = str(row.get("id") or "")
    proposed = str(row.get("to") or "").strip()
    expected = str(row.get("from") or "").strip()
    if node is None:
        return "no_such_node", node_id
    if not proposed or not expected or not row.get("printed") or not row.get("fixture"):
        return "row_is_incomplete", "a row needs 'from', 'to', 'printed' and 'fixture'"
    if str(row.get("licence") or "") not in LICENCES:
        return "unknown_licence", str(row.get("licence"))
    if not str(row.get("basis") or "").strip():
        return "row_states_no_basis", "a rename with no basis written down is a hand-edit"
    name = str(node.get("name") or "")
    if name == proposed:
        return "already_applied", "the node already carries the proposed name"
    if name != expected:
        return "curated_name_has_changed", f"the row was written against {expected!r}, the node now reads {name!r}"
    if not is_post_node(node):
        return "node_is_not_a_post", "this script renames posts only"
    if str(row.get("parentId") or "") != parent_id:
        return "node_has_moved", f"the row was written under {row.get('parentId')!r}, the node now sits under {parent_id!r}"
    key = canonical_name_key(proposed)
    if key == canonical_name_key(name):
        return "rename_is_a_no_op", f"both names reduce to {key!r}"
    if len(key.split()) < MIN_NAME_TOKENS:
        return "proposed_name_too_short", f"{key!r} is fewer than {MIN_NAME_TOKENS} tokens"
    if key in GENERIC_NAMES:
        return "proposed_name_is_generic", f"{proposed!r} names many offices and identifies none"
    owner = sibling_keys.get(key)
    if owner and owner != node_id:
        return "proposed_name_collides_with_a_sibling", f"{owner} already reduces to {key!r}"
    return None


def check_footnote(row: dict[str, Any], root: Path, cache: dict[str, Any]) -> tuple[str, str] | dict[str, Any]:
    path = _resolve(row["fixture"], root)
    cache_key = f"footnote:{path}"
    if cache_key not in cache:
        try:
            cache[cache_key] = load_schedule_8(path)
        except (SectionUnreadable, OSError, ValueError) as error:
            cache[cache_key] = error
    loaded = cache[cache_key]
    if isinstance(loaded, Exception):
        return "document_unreadable", f"{path.name}: {loaded}"
    items = list(loaded["schedule"]["seniorEnlistedFootnote"]["items"])
    printed = str(row["printed"])
    if printed not in items:
        return "document_does_not_print_the_title", f"Schedule 8's enlisted footnote lists {items!r}"
    if str(row["to"]).strip() != printed:
        return "proposed_name_is_not_the_printed_title", f"the footnote prints {printed!r}"
    return {"url": loaded["url"], "sha256": loaded["sha256"], "fetchedAt": loaded["fetched_at"]}


def check_current_export(row: dict[str, Any], root: Path, cache: dict[str, Any]) -> tuple[str, str] | dict[str, Any]:
    """A row of OPM's committed current PLUM export, read through
    `plum_current.load_plum_export` -- its digest recomputed from the bytes,
    `READ_COLUMNS` only, Historical rows dropped -- must carry exactly the
    row's agency, organization and title verbatim, as ONE listing (one pay
    plan and level; several rows for one position fold into one), and the
    proposed name must reduce under `canonical_name_key` to that title. The
    casing is the reviewer's; the words are the export's."""
    path = _resolve(row["fixture"], root)
    cache_key = f"export:{path}"
    if cache_key not in cache:
        try:
            cache[cache_key] = load_plum_export(path)
        except (ExportUnreadable, OSError, ValueError) as error:
            cache[cache_key] = error
    loaded = cache[cache_key]
    if isinstance(loaded, Exception):
        return "document_unreadable", f"{path.name}: {loaded}"
    agency = str(row.get("agency") or "")
    organization = str(row.get("organization") or "")
    printed = str(row["printed"])
    if not agency or not organization:
        return "row_is_incomplete", "an export row needs the 'agency' and 'organization' it is filed under"
    group = (loaded.get("groups") or {}).get((agency, organization))
    if not group:
        return "document_does_not_print_the_title", f"the export has no live rows filed under {agency!r} / {organization!r}"
    listings = [r for r in group if r["title"] == printed]
    if not listings:
        return "document_does_not_print_the_title", f"no Filled or Vacant row under {organization!r} prints {printed!r}"
    if len(listings) != 1:
        return "export_lists_the_title_more_than_once", (
            f"{len(listings)} listings under {organization!r} print {printed!r} at different pay plans or levels")
    if canonical_name_key(str(row["to"])) != canonical_name_key(printed):
        return "proposed_name_is_not_the_printed_title", (
            f"{row['to']!r} reduces to {canonical_name_key(row['to'])!r}; the export prints {printed!r}")
    return {"url": loaded["url"], "sha256": loaded["sha256"], "fetchedAt": loaded["fetched_at"]}


def _section(fixture: str, root: Path, cache: dict[str, Any]) -> dict[str, Any] | Exception:
    path = _resolve(fixture, root)
    cache_key = f"section:{path}"
    if cache_key not in cache:
        try:
            cache[cache_key] = load_basis_section(path.name, path.parent)
        except (ScheduleUnreadable, OSError, ValueError) as error:
            cache[cache_key] = error
    return cache[cache_key]


def check_counted_class(row: dict[str, Any], node_name: str, root: Path,
                        cache: dict[str, Any]) -> tuple[str, str] | dict[str, Any]:
    printed = str(row["printed"])
    count_match = _COUNT_SUFFIX.search(printed)
    if count_match is None or counted_class_count(printed) is None:
        return "printed_title_states_no_count", f"{printed!r} is not a counted class title"
    singular = str(row.get("singular") or "").strip()
    if not singular or plural_of(singular) != printed[: count_match.start()].strip():
        return "singular_is_not_the_class_titles_singular", (
            f"{singular!r} + 's' is not {printed[: count_match.start()].strip()!r}")
    section = _section(row["fixture"], root, cache)
    if isinstance(section, Exception):
        return "document_unreadable", f"{row['fixture']}: {section}"
    if printed not in section["operative"]:
        return "document_does_not_print_the_title", f"{printed!r} is not in the section's operative text"
    proposed = str(row["to"]).strip()
    split_to = split_office(proposed)
    if split_to is None or split_to[0] != singular:
        return "proposed_name_does_not_begin_with_the_singular", (
            f"{proposed!r} is not {singular!r}, a separator from the closed list, and a qualifier")
    _office, separator, qualifier = split_to
    split_from = split_office(node_name)
    if split_from is None or split_from[1] != separator or split_from[2] != qualifier:
        return "qualifier_is_not_the_nodes_own", (
            f"{node_name!r} does not carry {qualifier!r} after {separator!r}; the rename may change only the office")
    composed = row.get("composedBy")
    if not isinstance(composed, dict) or not composed.get("fixture") or not composed.get("quote"):
        return "row_names_no_composing_section", "a counted class rename needs the section that composes the class"
    basis = _section(str(composed["fixture"]), root, cache)
    if isinstance(basis, Exception):
        return "composing_section_unreadable", f"{composed['fixture']}: {basis}"
    if str(composed["quote"]) not in basis["operative"]:
        return "composing_quote_not_in_operative_text", str(composed.get("citation") or composed["fixture"])
    return {"url": section["url"], "sha256": section["sha256"], "fetchedAt": section["fetchedAt"],
            "composedBy": {"citation": composed.get("citation"), "url": basis["url"], "sha256": basis["sha256"]}}


def adjudicate(root_node: dict[str, Any], rows: list[dict[str, Any]], *, apply: bool,
               project_root: Path = PROJECT_ROOT) -> list[dict[str, Any]]:
    """Decide every row; rename the nodes whose rows pass when `apply`."""
    node_map, parent_map = index_tree(root_node)
    sibling_keys: dict[str, dict[str, str]] = {}
    for parent in node_map.values():
        pid = str(parent.get("id") or "")
        for child in parent.get("children") or []:
            sibling_keys.setdefault(pid, {}).setdefault(canonical_name_key(child.get("name")), str(child.get("id") or ""))

    # No more rows may cite one counted class than the class title counts:
    # the Code says how many such offices exist.
    per_class: dict[str, int] = {}
    for row in rows:
        if str(row.get("licence") or "") == LICENCE_COUNTED_CLASS:
            per_class[str(row.get("printed") or "")] = per_class.get(str(row.get("printed") or ""), 0) + 1

    cache: dict[str, Any] = {}
    results: list[dict[str, Any]] = []
    for row in rows:
        node_id = str(row.get("id") or "")
        node = node_map.get(node_id)
        parent_id = str(parent_map.get(node_id) or "")
        verdict = check_static(row, node, parent_id, sibling_keys.get(parent_id, {}))
        if verdict:
            results.append({"id": node_id, "applied": False, "reason": verdict[0], "detail": verdict[1]})
            continue
        licence = str(row["licence"])
        if licence == LICENCE_COUNTED_CLASS:
            stated = counted_class_count(str(row["printed"]))
            # A title stating no count is refused for that, below.
            if stated is not None and per_class.get(str(row["printed"]), 0) > stated:
                results.append({"id": node_id, "applied": False, "reason": "more_rows_than_the_class_counts",
                                "detail": f"{per_class[str(row['printed'])]} rows cite {row['printed']!r}"})
                continue
            found = check_counted_class(row, str(node.get("name") or ""), project_root, cache)
        elif licence == LICENCE_CURRENT_EXPORT:
            found = check_current_export(row, project_root, cache)
        else:
            found = check_footnote(row, project_root, cache)
        if isinstance(found, tuple):
            results.append({"id": node_id, "applied": False, "reason": found[0], "detail": found[1]})
            continue
        old = str(node.get("name") or "")
        new = str(row["to"]).strip()
        results.append({"id": node_id, "applied": True, "from": old, "to": new, "licence": licence,
                        "printed": str(row["printed"]), "url": found["url"], "sha256": found["sha256"]})
        if apply:
            node["name"] = new
            node["nameSource"] = NAME_SOURCES[licence]
            node["nameSourceDetail"] = found["url"]
            node["nameMatchedText"] = str(row["printed"])
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    parser.add_argument("--dry-run", action="store_true", help="decide everything, write nothing")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv[1:] if argv else None)

    root = load_base_graph(args.base_graph)
    rows = load_table(args.table)
    results = adjudicate(root, rows, apply=not args.dry_run)
    applied = [r for r in results if r.get("applied")]
    if args.json:
        print(json.dumps({"applied": len(applied), "results": results}, indent=1, ensure_ascii=False))
    else:
        for item in applied:
            print(f"  {item['from']!r}\n      -> {item['to']!r}   [{item['licence']}]  {item['url']}")
        refused = [r for r in results if not r.get("applied")]
        if refused:
            print(f"\nleft alone ({len(refused)}):")
            for item in refused:
                print(f"  {str(item['id'])[:58]:60s} {item['reason']}")
                if item.get("detail"):
                    print(f"      {str(item['detail'])[:160]}")
        print(f"\nrenamed {len(applied)}  left alone {len(results) - len(applied)}  of {len(rows)} rows")
    if args.dry_run:
        print("dry run: nothing written.")
        return 0
    if applied:
        write_json_file(args.base_graph, root)
        print(f"wrote {args.base_graph}")
    else:
        print("nothing to do; the curated file is unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
