"""Rename a templated cabinet post to the title an official document gives it.

    python scripts/rename_templated_post_titles.py --dry-run   # what would change
    python scripts/rename_templated_post_titles.py             # write the curated file

The curated file is never hand-edited; this script is the only writer of
these names, as `expand_whitehouse_office.py` is the only writer of the White
House Office subtree. It is idempotent, it never creates, re-types or removes
a node, and it renames nothing it cannot cite.

**The defect.** 839 position nodes contain their parent organisation's name
verbatim. In 28 of them the template produces a title no official page or
document will ever carry: every cabinet department except Defense has a
`Secretary of Department of <the department's full name>` node and a
`Deputy Secretary of ...` beside it. The first position verification pass
(2026-09-15) is what surfaced it — the most recognisable posts in the
federal government came back `inconclusive` against their own departments'
pages, because the graph calls them something nobody says.

**Why the obvious fix is wrong.** The names are one string operation away
from correct: drop "Department of" and the parenthetical, and
"Secretary of Department of Energy (DOE)" becomes "Secretary of Energy".
That transform is right thirteen times and catastrophically wrong once —
the head of the Department of Justice is the **Attorney General**, and
"Secretary of Justice" is not a lesser spelling of it but an office that
does not exist. A second case breaks it the other way: OPM's own archive
spells the DHS post "SECRETARY OF THE DEPARTMENT OF HOMELAND SECURITY",
keeping the words the transform would strip. So the transform is used only
to *recognise* a templated name, never to produce the replacement.

**What produces the replacement.** Three official sources, in that order:

1. **The United States Code** — 5 U.S.C. §§5312-5316, the Executive
   Schedule, committed verbatim under `tests/fixtures/uscode/` and read by
   `data_pipeline/verification/statutory_schedule.py` with its digests
   checked. Added 2026-09-18, and placed first because it is the strongest
   of the three by some distance: it is *current law naming the office*,
   where the archive is a snapshot of the previous administration and a page
   is a publisher's wording. It is also what closed the gap this script
   documented and could not fix — thirteen departments' heads stayed
   templated because "no source in hand names them", and §5312 names every
   one.

   **It is used exactly as the other two are: it selects, it never
   produces.** The transform ("Secretary of Department of X" → "Secretary of
   X") is still only a recogniser, and here it can only ever pick a string
   the statute actually prints — which is what makes it safe in the one case
   that breaks it. The transform yields "Secretary of Justice"; the
   Executive Schedule does not carry that title, because the office does not
   exist, so nothing is proposed and DOJ falls through. A second guard
   narrows it further: the statutory title's "of …" remainder must be part
   of the department's own name, so a title naming a *different* department
   can never be selected for this one.
2. **OPM's PLUM archive** (`tests/fixtures/opm/plum/`, the previous
   administration's reported positions — the same document `positions.py`
   already matches against). A title filed under this department, of the
   right kind, and *qualified*: the archive files several departments' heads
   as a bare "SECRETARY", which is no better than what is there and is
   refused by the post floor anyway.
3. **The department's own official page**, read only when neither of the
   above carries a qualified title, under the same robots policy as the
   verifier. This is what supplied "Secretary of Energy" before the statute
   was readable.

Where several qualified titles exist, the general one wins **only** if every
other is a refinement of it — "Deputy Secretary of State" against "Deputy
Secretary of State for Management and Resources". Anything else is reported
ambiguous and left alone. A name this cannot cite is not changed and is
listed at the end, for CURATION.md.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_pipeline.crawler.official_directory import USER_AGENT, request_text  # noqa: E402
from data_pipeline.exporter.build_graph import (  # noqa: E402
    DEFAULT_BASE_GRAPH,
    canonical_name_key,
    index_tree,
    is_post_node,
    load_base_graph,
)
from data_pipeline.json_io import write_json_file  # noqa: E402
from data_pipeline.verification.evidence import (  # noqa: E402
    DEFAULT_SITES_PATH,
    load_official_sites,
    parse_page,
)
from data_pipeline.verification.politeness import RobotsPolicy  # noqa: E402
from data_pipeline.verification.statutory_schedule import (  # noqa: E402
    Unreadable as ScheduleUnreadable,
    load_schedule,
)

DEFAULT_ARCHIVE = PROJECT_ROOT / "tests" / "fixtures" / "opm" / "plum" / "plum-archive-biden-administration.csv"
ARCHIVE_URL = "https://www.opm.gov/policy-data-oversight/senior-executive-service/plum-archive/"

#: The two kinds of post this script touches, and the titles that can name
#: each. Deputy is listed first so "Deputy Secretary" never matches the head's
#: pattern. `Attorney General` is here because the whole point is that a
#: department's head is not always a Secretary.
ROLE_PATTERNS = (
    ("deputy", re.compile(r"^(deputy secretary(?: of .+)?|deputy attorney general)$")),
    ("head", re.compile(r"^(secretary(?: of .+)?|attorney general)$")),
)
#: The curated shape this script recognises, and nothing else: the role word,
#: then the parent organisation's own name. Matched on canonical keys, so
#: "(DOE)" and "&" spelling never matter.
TEMPLATE_PREFIXES = {"head": "secretary of ", "deputy": "deputy secretary of "}


#: Where a reader checks the statute for themselves. The section a given
#: title came from rides on the record; this is the Code's own front door for
#: the chapter, which is what a citation in a description should point at.
STATUTE_URL = "https://uscode.house.gov/view.xhtml?req=granuleid%3AUSC-prelim-title5-chapter53-subchapterII"


def role_of(name: str, parent_name: str) -> str | None:
    """'head', 'deputy', or None if this is not a templated cabinet title."""
    key = canonical_name_key(name)
    parent_key = canonical_name_key(parent_name)
    if not key or not parent_key:
        return None
    for role, prefix in TEMPLATE_PREFIXES.items():
        if key == prefix + parent_key:
            return role
    return None


#: Offices whose own name distinguishes them without naming a department.
NAMED_OFFICES = frozenset({"attorney general", "deputy attorney general"})


def qualified(title: str) -> bool:
    """Does this title distinguish the post, or is it just the role word?

    Two tokens is not the test, and using it was a real bug caught on the
    first dry run: the archive files Commerce, Transportation and Education
    deputies as a bare "DEPUTY SECRETARY", which cleared a token count and
    would have renamed three nodes to "Deputy Secretary" — dropping the one
    word that says which department, and leaving a title so generic that any
    page carrying those two words anywhere would answer to it. That is the
    hazard the verifier's own post floor exists to refuse; a rename must not
    manufacture it.

    So: either the title says which department it belongs to (it has an
    "of ..." part), or the office has a name of its own that needs no
    department after it — the Attorney General is not "the Secretary of
    Justice" and never was.
    """
    key = canonical_name_key(title)
    if key in NAMED_OFFICES:
        return True
    role, _, rest = key.partition(" of ")
    return bool(role and rest.strip())


def pick(candidates: list[str]) -> tuple[str | None, str]:
    """The general title, when every other candidate refines it."""
    unique = sorted({c.strip() for c in candidates if c and c.strip()}, key=lambda c: (len(canonical_name_key(c)), c))
    if not unique:
        return None, "no_qualified_title"
    shortest = unique[0]
    key = canonical_name_key(shortest)
    if all(canonical_name_key(c) == key or canonical_name_key(c).startswith(key + " ") for c in unique):
        return shortest, "ok"
    return None, "ambiguous: " + "; ".join(repr(c) for c in unique)


def title_case(title: str) -> str:
    """The archive shouts; the graph does not. Small words stay lowercase, as
    they do in "Secretary of the Treasury"."""
    small = {"of", "the", "for", "and", "a", "an", "to", "in", "on"}
    words = title.strip().split()
    out = []
    for index, word in enumerate(words):
        lowered = word.lower()
        if index and lowered in small:
            out.append(lowered)
        elif word.isupper() or word.islower():
            out.append(lowered.capitalize())
        else:
            out.append(word)
    return " ".join(out)


def archive_titles(archive_rows: list[dict[str, str]], dept_name: str) -> dict[str, list[str]]:
    """Qualified head and deputy titles the archive files under this department."""
    key = canonical_name_key(dept_name)
    found: dict[str, list[str]] = {"head": [], "deputy": []}
    for row in archive_rows:
        if canonical_name_key(row.get("AgencyName")) != key:
            continue
        title = str(row.get("PositionTitle") or "").strip()
        lowered = canonical_name_key(title)
        for role, pattern in ROLE_PATTERNS:
            if pattern.match(lowered):
                if qualified(title):
                    found[role].append(title)
                break
    return found


def statute_titles(schedule: dict, dept_name: str) -> dict[str, list[str]]:
    """Head and deputy titles the Executive Schedule prints for this department.

    Two guards, and the pairing is what makes the statute safe to put first.

    The title must match the role pattern AND its "of ..." remainder must be
    part of the department's own canonical name. The remainder test is what
    stops a title naming a different department being selected for this one:
    "Secretary of Education" can never answer for Health and Human Services,
    because "education" is not in that department's name. And because the
    only titles considered are ones the statute actually prints, the
    transform that breaks on Justice cannot break here either -- the
    Executive Schedule carries no "Secretary of Justice", so DOJ selects
    nothing and falls through to the sources below it.
    """
    dept_key = canonical_name_key(dept_name)
    found: dict[str, list[str]] = {"head": [], "deputy": []}
    if not dept_key:
        return found
    for position in schedule["index"].values():
        title = str(position["title"])
        key = canonical_name_key(title)
        for role, pattern in ROLE_PATTERNS:
            # First pattern that matches wins, exactly as archive_titles and
            # page_titles do it. The deputy pattern is tried first and must
            # not stop the search when it fails, or every head title in the
            # statute goes unseen -- which is precisely what it did on the
            # first dry run, renaming the four deputies and none of the nine
            # Secretaries the Code names explicitly.
            if not pattern.match(key):
                continue
            _, _, remainder = key.partition(" of ")
            remainder = remainder.strip()
            if remainder and remainder in dept_key and qualified(title):
                found[role].append(title)
            break
    return found


def page_titles(page, dept_name: str) -> dict[str, list[str]]:
    """The same, read off the department's own page. Every fragment and
    region is scanned: this proposes a NAME for a curated node, which is
    curation, not the evidence the verifier publishes — and a post
    confirmation still has to be earned separately, from page content."""
    found: dict[str, list[str]] = {"head": [], "deputy": []}
    for fragment in list(page.fragments) + list(page.loose_fragments):
        for part in re.split(r"\s*[—–|·•:>›»/·]\s*|\s+[-–]\s+|\n+", fragment):
            text = part.strip()
            lowered = canonical_name_key(text)
            if lowered.startswith("the "):
                lowered = lowered[4:]
                text = text.strip()[4:].strip() if text.lower().startswith("the ") else text
            for role, pattern in ROLE_PATTERNS:
                if pattern.match(lowered) and qualified(text):
                    found[role].append(text)
                    break
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-graph", type=Path, default=DEFAULT_BASE_GRAPH)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--sites", type=Path, default=DEFAULT_SITES_PATH)
    parser.add_argument("--no-pages", action="store_true", help="use the archive only; fetch nothing")
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--dry-run", action="store_true", help="print what would change; write nothing")
    args = parser.parse_args(argv[1:] if argv else None)

    root = load_base_graph(args.base_graph)
    node_map, parent_map = index_tree(root)
    with args.archive.open(encoding="utf-8-sig", newline="") as handle:
        archive_rows = list(csv.DictReader(handle))
    sites = load_official_sites(args.sites) if not args.no_pages else {}
    try:
        schedule = load_schedule()
    except ScheduleUnreadable as error:
        # A statute that cannot be trusted proposes nothing; the two older
        # sources still run, exactly as they did before it existed.
        print(f"  the Executive Schedule was not read: {error}")
        schedule = {"index": {}}

    templated: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    for node in node_map.values():
        if not is_post_node(node):
            continue
        parent = node_map.get(parent_map.get(str(node.get("id") or "")) or "")
        if not parent:
            continue
        role = role_of(str(node.get("name") or ""), str(parent.get("name") or ""))
        if role:
            templated.append((node, parent, role))
    templated.sort(key=lambda item: str(item[0].get("id")))
    print(f"templated cabinet titles found: {len(templated)}")

    robots = RobotsPolicy(user_agent=USER_AGENT, timeout=args.timeout, enabled=True)
    page_cache: dict[str, Any] = {}
    last_fetch = 0.0

    def titles_from_page(parent_id: str, dept_name: str) -> dict[str, list[str]]:
        nonlocal last_fetch
        if parent_id not in page_cache:
            merged: dict[str, list[str]] = {"head": [], "deputy": []}
            for url in sites.get(parent_id, []):
                allowed, _ = robots.allows(url)
                if not allowed:
                    continue
                wait = max(args.sleep, robots.crawl_delay(url)) - (time.monotonic() - last_fetch)
                if wait > 0:
                    time.sleep(wait)
                try:
                    found = page_titles(parse_page(request_text(url, timeout=args.timeout)), dept_name)
                except Exception:  # noqa: BLE001 — a failed fetch proposes nothing
                    found = {"head": [], "deputy": []}
                last_fetch = time.monotonic()
                for role in merged:
                    merged[role].extend(found[role])
            page_cache[parent_id] = merged
        return page_cache[parent_id]

    renames: list[tuple[str, str, str, str]] = []
    refused: list[tuple[str, str]] = []
    for node, parent, role in templated:
        node_id, name = str(node.get("id")), str(node.get("name"))
        dept_name = str(parent.get("name"))
        chosen, why = pick(statute_titles(schedule, dept_name)[role])
        source, detail = "named_in_5_usc_5312_5316", STATUTE_URL
        if not chosen:
            from_archive = archive_titles(archive_rows, dept_name)[role]
            chosen, why = pick(from_archive)
            source, detail = "listed_in_opm_plum_archive", ARCHIVE_URL
        if not chosen and not args.no_pages:
            # Only when the archive carries no qualified title. Preferring one
            # source outright avoids having to adjudicate a disagreement
            # between two officials documents, which this script has no basis
            # to do: OPM says "Secretary of the Department of Homeland
            # Security" where a page might say "Secretary of Homeland
            # Security", and neither is wrong.
            urls = sites.get(str(parent.get("id")), [])
            chosen, why = pick(titles_from_page(str(parent.get("id")), dept_name)[role])
            source, detail = "named_on_its_organisations_official_page", (urls[0] if urls else "")
        if not chosen:
            refused.append((f"{name} ({node_id})", why))
            continue
        new_name = title_case(chosen)
        if new_name == name:
            continue  # already correct: the script is idempotent
        renames.append((node_id, name, new_name, source))
        if not args.dry_run:
            node["name"] = new_name
            node["nameSource"] = source
            node["nameSourceDetail"] = detail

    for node_id, old, new, source in renames:
        print(f"  {old!r}\n      -> {new!r}   ({source})")
    if refused:
        print(f"\nleft alone, no official source names the title ({len(refused)}):")
        for label, why in refused:
            print(f"  {label}  [{why}]")
    print(f"\nrenamed {len(renames)}  refused {len(refused)}  of {len(templated)}")
    if args.dry_run:
        print("dry run: nothing written.")
        return 0
    if renames:
        write_json_file(args.base_graph, root)
        print(f"wrote {args.base_graph}")
    else:
        print("nothing to do; the curated file is unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
