"""Derive post evidence from the United States Government Manual.

    python scripts/derive_govman_evidence.py --dry-run   # what would apply; writes nothing
    python scripts/derive_govman_evidence.py             # writes data/verification/govman_evidence.json

Reads the Manual committed verbatim under `tests/fixtures/govman/` (digest
recomputed from the bytes before anything is read) and matches each agency's
own leadership table to the post nodes that are that agency's direct children.

Two limits are structural rather than tuned, and both are argued in
`data_pipeline/verification/govman.py`: only rows that are complete titles on
their own face are eligible, because the Manual qualifies a group heading with
bare fragments and assembling them would produce a title rather than select
one; and a post is matched only under its own parent, because the stamped
administrative titles this graph carries would otherwise be confirmed for a
dozen Defense agencies out of the Department of Defense's single row.

The incumbent's name is never read. Each leadership row pairs a person with a
post; this reads the post.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.exporter.build_graph import DEFAULT_BASE_GRAPH, load_base_graph  # noqa: E402
from data_pipeline.json_io import write_json_file  # noqa: E402
from data_pipeline.verification.aliases import load_alias_table  # noqa: E402
from data_pipeline.verification.govman import (  # noqa: E402
    DEFAULT_PACKAGE,
    DESCRIPTION_MAX_CHARS,
    SOURCE,
    build_office_records,
    build_org_records,
    build_records,
    read_manual,
)

DEFAULT_OUT = PROJECT_ROOT / "data" / "verification" / "govman_evidence.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv[1:] if argv else None)

    manual = read_manual(args.fixture)
    base = load_base_graph(args.base_graph)
    # The reviewed alternative names a document may print for a node,
    # adjudicated against the curated file as it is now.
    alias_table = load_alias_table(base)
    records, stats = build_records(manual, base, alias_table=alias_table)
    org_records, org_stats = build_org_records(manual, base, alias_table=alias_table)
    office_records, office_stats = build_office_records(manual, base, alias_table=alias_table)

    print(f"  manual              : {manual['package']} (edition {manual['edition']})")
    print(f"  agency entries      : {stats['entries']}")
    print(f"  matched to a node   : {stats['organisations_matched']}")
    print(f"  no curated node     : {stats['entry_names_no_node']}")
    print(f"  posts listed        : {stats['posts_listed']}")
    for reason in ("refused_title_not_listed", "refused_title_listed_twice",
                   "refused_siblings_share_the_name", "refused_name_too_short",
                   "refused_no_access_id", "entry_names_several_entries",
                   "entry_names_several_nodes"):
        print(f"  {reason:34s}: {stats[reason]}")
    print(f"  organisations listed: {org_stats['organisations_listed']} (top-level entries {org_stats['top_level_entries']})")
    print(f"  matched via an alias: {org_stats['organisations_matched_by_alias']} organisations, "
          f"{stats['posts_under_an_aliased_organisation']} posts beneath one")
    print(f"  top-level offices   : {office_stats['offices_listed']} "
          f"({office_stats['offices_matched_by_alias']} via an alias); refused "
          f"{office_stats['refused_entry_is_an_agency']} agency entries and "
          f"{office_stats['refused_caps_row_is_not_the_entrys_own_name']} caps rows that are not the entry's own name")
    # The entry's own description, beside the curated prose (govman.py,
    # last section of the module docstring). Refusals are printed with the
    # count because the name guard costs real entries and a reader should
    # see that number, not only the gain.
    print(f"  official descriptions: {org_stats['descriptions_extracted']} of {org_stats['organisations_listed']} organisations "
          f"({org_stats['descriptions_mission_statement']} mission statements, "
          f"{org_stats['descriptions_opening_paragraph']} opening paragraphs, "
          f"{org_stats['descriptions_truncated']} cut at a sentence boundary within {DESCRIPTION_MAX_CHARS} characters)")
    for reason in ("descriptions_refused_opening_paragraph_does_not_name_the_unit",
                   "descriptions_refused_opening_paragraph_is_a_navigation_note",
                   "descriptions_refused_no_descriptive_text",
                   "descriptions_refused_no_sentence_boundary_within_bound"):
        print(f"  {reason:60s}: {org_stats[reason]}")
    print(f"  document sha256     : {manual['sha256'][:16]}...")
    if args.dry_run:
        # Three examples, one of each shape the rule produces, so a reader of
        # the dry run sees the text and the element it came from.
        shown: dict[tuple[str, bool], tuple[str, dict]] = {}
        for record in org_records.values():
            block = record.get("description")
            if not block:
                continue
            shape = (block["kind"], bool(block["truncated"]))
            shown.setdefault(shape, (record["listedName"], block))
        print("\nExamples (the Manual's own words, verbatim):")
        for (kind, truncated), (name, block) in list(shown.items())[:3]:
            cut = f", cut at a sentence boundary after {len(block['text'])} of {block['fullLength']} characters" if truncated else ""
            print(f"  - {name} [{kind}, from {block['extractedFrom']}{cut}]")
            print(f'    "{block["text"]}"')
    print("\nA listing is evidence the post exists and that the Manual files it under this")
    print("agency. It says nothing about who holds it: the incumbent column is never read,")
    print("and a leadership table carries its own 'Sources of Information' date, which rides")
    print("on every record. One official URL grades a node partial, never verified.")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0

    store = {
        "_note": (
            "Derived by scripts/derive_govman_evidence.py from the United States Government "
            "Manual, the official handbook of the federal government, committed verbatim under "
            "tests/fixtures/govman/ with its digest. Each record says that the Manual's entry for "
            "an organisation lists a post of this name in that organisation's own leadership "
            "table. The office holder's name is never read. Only rows that are complete titles "
            "on their own face are eligible -- the Manual qualifies a group heading with bare "
            "fragments, and assembling those would produce a title rather than select one -- and "
            "a post is matched only under its own parent, never a further ancestor."
        ),
        "source": {"kind": SOURCE, "package": manual["package"], "edition": manual["edition"],
                   "url": manual["url"], "documentSha256": manual["sha256"],
                   "fetchedAt": manual["fetchedAt"],
                   "derivedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "fixture": str(Path(args.fixture).relative_to(PROJECT_ROOT))},
        "report": stats,
        "organisationsReport": org_stats,
        "nodes": records,
        # The organisation route (govman.build_org_records): one record per
        # unit the Manual carries an entry for, with the parent entry's name
        # so the exporter can compare where the Manual files it with the tree.
        "organisations": org_records,
        # The top-level office route (govman.build_office_records): a Manual
        # entry that IS an office rather than an agency, which is the only
        # route by which the President and the Vice President are reachable.
        "offices": office_records,
        "officesReport": office_stats,
    }
    write_json_file(args.out, store)
    print(f"\nwrote {len(records)} post records, {len(org_records)} organisation records "
          f"and {len(office_records)} top-level office records -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
