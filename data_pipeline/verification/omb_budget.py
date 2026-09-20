"""Budget authority and outlays, as the President's Budget reports them.

`docs/EXACT_NODE_COSTS.md` section 1 asks for "a reviewed identifier crosswalk
(CGAC, TAS, toptier and OMB codes, names proposing candidates and never
publishing facts)" as the first step toward more exact-node costs. The OMB
**Public Budget Database** is that crosswalk with the money already attached:
one row per budget account, carrying the account's agency, bureau, Treasury
agency code, CGAC agency code, subfunction and BEA category, and a figure for
every fiscal year from 1962 to 2031.

`www.govinfo.gov` answers `robots.txt` 200 and allows the path. The package
(BUDGET-2027-DB, 3.9 MB) is committed verbatim at `tests/fixtures/omb/` with
its `.meta.json`, and the digest is recomputed from the bytes before anything
is read -- the refusal `pay_tables`, `net_cost` and `govman` make.

**Only the last COMPLETED fiscal year is ever published, and the boundary is
read out of the document rather than assumed.** This file is a *Budget*: the
later columns are the President's request, not history. The user's guide says
so in as many words --

    "Budget estimates for the current fiscal year (2026), the budget year
     (2027), and each subsequent year are prepared by agencies, based on the
     definitions and guidance contained in OMB Circular A-11"

-- so FY2025 is the last actual and FY2026 onward are projections. Publishing
an estimate beside figures this project calls measured would be the single
worst thing this source could do, so `estimate_boundary` parses that sentence
out of the committed guide on every run and `load_database` refuses to return
anything if it cannot find it. The boundary is not a constant anyone can edit;
it is what the publisher printed.

**The unit is the publisher's own, and it is thousands -- not millions.**

    "Data for budget authority, outlays, offsetting receipts, and governmental
     receipts are shown in thousands of dollars."

with a caveat that rides on every record because it bounds the precision:

    "the file data from FY 1995 through FY 2031 represent the Budget amounts
     multiplied by one thousand to convert the amounts to thousands; detail
     below millions is not available."

So a figure here is exact to the million and no further, whatever its trailing
digits suggest. Summing the FY2025 outlay column over every row gives
7,011,105,000 thousands = $7.011 trillion, which is the right order for the
year and corroborates the stated unit without replacing the publisher's
statement of it.

**The publisher states no figure for any unit, and the record says so.** There
is no total row anywhere in this database -- every one of the 5,760 outlay rows
is a budget account -- so a unit's figure here is not something OMB prints, it
is this repository's **sum over the account rows OMB files under that unit**.
The Department of the Treasury's $1.46 trillion is 368 rows added together.
Every record therefore carries `outlayAccountRows` and
`budgetAuthorityAccountRows`, and the panel says "the account rows OMB files
under this unit sum to" rather than "OMB reports", because the second would
attribute an arithmetic result to a publisher who never performed it.

**A negative figure is normal here and is published as it stands**, for the
reason the Treasury's own negative lines are: OMB says "Budget authority and
outlay amounts are reported net of any offsetting collections, such as fees,
fines, and penalties", and that "Outlays are usually positive values.
Offsetting receipts are usually negative values." Ten of the 133 units net
below zero -- the FDIC at -$31.2bn, the SEC, the NCUA, the Export-Import Bank --
because they collect more in premiums and fees than they spend. Both sentences
ride on every record so the panel can explain a minus sign rather than leave a
reader to assume a bug.

**It is not this graph's cost, and nothing here writes a cost field.** Three
differences ride on every record, exactly as they do for `usaspending.py` and
`net_cost.py`:

  - **Period.** A completed fiscal year. The graph's anchor is the current
    year to date. Not comparable.
  - **Measure.** OMB's own guide says its totals are "generally consistent
    with data published in the Monthly Treasury Statement by the Treasury
    Fiscal Service", and then says why they are not identical: "a small number
    of reporting and classification corrections made subsequent to the
    Treasury publications and some conceptual differences between OMB and
    Treasury reporting." *Generally consistent* is not *the same*, and the
    publisher is the one saying so, so the figure is published beside the cost
    and never as it.
  - **Composition.** A bureau's figure here is the sum of the account rows OMB
    files under it, which includes negative offsetting-receipt rows. That is
    the bureau's net, and the record says it is a sum over accounts.

**Matching, scoped the way a FedScope row is.** An agency name must reduce to
exactly one organisation in the graph; a bureau name must reduce to exactly
one organisation AND that node must be the agency's node or sit beneath it.
Three guards earn their place on the real data:

  - a **type guard**, the one `statutory_schedule` needed: without it OMB's
    agency "Legislative Branch" reaches the Senate Appropriations
    *Subcommittee on the Legislative Branch* -- a real node with a unique name
    in entirely the wrong branch -- and would then scope every legislative
    bureau underneath a subcommittee.
  - a **uniqueness guard on the bureau name across the whole file**: "Bureau of
    Labor Statistics" appears under both Commerce and Labor in this database,
    which restates history onto the current account structure, so the name
    alone identifies no single row.
  - the **subtree guard**, which after the other two refuses exactly one pair:
    OMB files the Pension Benefit Guaranty Corporation under the Department of
    Labor and this graph curates it as an independent agency. Both placements
    are defensible -- the PBGC's board is chaired by the Secretary of Labor --
    so nothing is resolved: the row is refused and `CURATION.md` records the
    disagreement, the same treatment the Treasury's Tax Court line gets.

62 agencies and 134 bureau rows match, reaching 134 distinct nodes, 39 of which
publish no measured cost of their own today.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
import zlib
from pathlib import Path
from typing import Any

from data_pipeline.exporter.build_graph import canonical_name_key, is_post_node
from data_pipeline.verification.congress import read_xlsx_rows

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACKAGE = PROJECT_ROOT / "tests" / "fixtures" / "omb" / "BUDGET-2027-DB.zip"

SOURCE = "omb_public_budget_database"
SOURCE_TYPE = "omb_public_budget_database"
#: Said by the publisher, in the user's guide, in a sentence this module parses
#: rather than paraphrases.
UNITS_EVIDENCE = "publisher_states_the_unit_in_its_users_guide"
THOUSAND = 1000

MEMBER_OUTLAYS = "outlays"
MEMBER_AUTHORITY = "budget_authority"
#: file 1 is Budget Authority, file 2 is Outlays; file 3 is Receipts, which
#: names sources of revenue rather than units and is not read here.
MEMBER_FILES = {
    MEMBER_AUTHORITY: "xls/BUDGET-{year}-DB-1.xlsx",
    MEMBER_OUTLAYS: "xls/BUDGET-{year}-DB-2.xlsx",
}
GUIDE_FILE = "pdf/BUDGET-{year}-DB-4.pdf"

#: A budget account is never a committee, a court seat or a post. Without this
#: OMB's "Legislative Branch" reaches a Senate appropriations subcommittee.
NON_BUDGET_TYPE_WORDS = ("committee", "subcommittee", "caucus", "position", "role", "office holder", "court")

#: Quoted verbatim on every record, because each bounds what the figure means.
QUOTE_UNITS = ("Data for budget authority, outlays, offsetting receipts, and governmental "
               "receipts are shown in thousands of dollars.")
QUOTE_PRECISION = ("the file data from FY 1995 through FY 2031 represent the Budget amounts "
                   "multiplied by one thousand to convert the amounts to thousands ; detail "
                   "below millions is not available.")
#: Cut before "by the Treasury Fiscal Service": the PDF splits that word and
#: the extractor recovers it as "Fi scal", so quoting it would publish a typo
#: the document does not contain. The clause is complete as it stands, and the
#: sentence that follows -- which says WHY the two differ -- rides beside it.
QUOTE_TREASURY = ("The totals are generally consistent with data published in the Monthly "
                  "Treasury Statement")
#: Why a unit's figure can be negative, and why summing account rows is the
#: only way to get one: OMB prints no total row anywhere in this database.
QUOTE_NET = ("Budget authority and outlay amounts are reported net of any offsetting "
             "collections, such as fees, fines, and penalties.")
QUOTE_SIGN = "Outlays are usually positive values. Offsetting receipts are usually negative values ."
QUOTE_TREASURY_DIFFERENCES = (
    "Differences between the Treasury publications and the Budget arise from a small number "
    "of reporting and classification corrections made subsequent to the Treasury publications "
    "and some conceptual differences between OMB and Treasury reporting.")

#: The guide's own sentence. The year digits are kerning-split in the PDF
#: ("( 2 02 6)"), so the pattern tolerates spaces INSIDE a year and the spaces
#: are stripped before the number is read -- the same reason `guide_text`
#: exists at all.
ESTIMATE_SENTENCE = re.compile(
    r"Budget\s*estimates\s*for\s*the\s*current\s*fiscal\s*year\s*\(\s*((?:\d\s*){4})\)\s*,?\s*"
    r"the\s*budget\s*year\s*\(\s*((?:\d\s*){4})\)", re.I)
PDF_TOKEN = re.compile(rb"\((?:\\.|[^\\()])*\)|-?\d+(?:\.\d+)?|TJ|Tj|BT|ET|Td|TD|T\*|Tm")
#: A SECOND, independent statement of the same boundary, in the guide's
#: per-file field tables: "79-84 | 2026-2031 values | Estimated amounts, in
#: thousands of dollars, for FY 2026 through FY 2031". The narrative sentence
#: and this table are written by different parts of the document and must
#: agree; `estimate_boundary` refuses the package if they do not. This is the
#: one property of this source worth two independent reads, because every
#: other check would pass happily on a projection.
FIELD_TABLE_SENTENCE = re.compile(
    r"Estimated\s*amounts,\s*in\s*thousands\s*of\s*dollars,\s*for\s*FY\s*((?:\d\s*){4})"
    r"through\s*FY\s*((?:\d\s*){4})", re.I)


def _year(text: str) -> int:
    return int(re.sub(r"\s+", "", text))


def fixture_digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def guide_text(pdf: bytes) -> str:
    """The user's guide as readable prose.

    Written here rather than reused from `whitehouse_pay.extract_text_runs`
    because this PDF is typeset differently: it splits words across literal
    strings and spaces them with TJ kerning offsets, so that extractor returns
    nothing at all for it. Strings are concatenated with no separator and a
    space is emitted only where the kerning is wide enough to be a word gap,
    which is what turns "t hous a nds" back into "thousands".
    """
    out: list[str] = []
    for stream in re.findall(rb"stream\r?\n(.*?)endstream", pdf, re.S):
        try:
            body = zlib.decompress(stream)
        except zlib.error:
            continue
        if b"BT" not in body:
            continue
        for match in PDF_TOKEN.finditer(body):
            token = match.group(0)
            if token.startswith(b"("):
                text = re.sub(rb"\\([()\\])", rb"\1", token[1:-1])
                text = text.replace(b"\\n", b" ").replace(b"\\r", b" ").replace(b"\\t", b" ")
                out.append(text.decode("latin-1"))
            elif token in (b"Td", b"TD", b"T*", b"Tm", b"ET"):
                out.append(" ")
            elif token not in (b"TJ", b"Tj", b"BT"):
                try:
                    if float(token) <= -120:
                        out.append(" ")
                except ValueError:
                    continue
    return re.sub(r"[ \t]+", " ", "".join(out))


def estimate_boundary(text: str) -> tuple[int, int]:
    """(first estimated year, budget year), read out of the guide's own sentence.

    Raises when the sentence is absent: a boundary this module could not read
    is one it must not guess, because everything after it is a projection.
    """
    match = ESTIMATE_SENTENCE.search(text)
    if not match:
        raise ValueError("the user's guide does not state which years are estimates")
    first_estimate, budget_year = _year(match.group(1)), _year(match.group(2))

    # The field tables say the same thing in a different place and a different
    # form. They must agree: a boundary this module reads only once is one it
    # is trusting a single sentence for, and every figure after that boundary
    # is a projection that would publish as history.
    table = FIELD_TABLE_SENTENCE.search(text)
    if not table:
        raise ValueError("the user's guide's field tables do not name the estimated years")
    table_first, table_last = _year(table.group(1)), _year(table.group(2))
    if table_first != first_estimate:
        raise ValueError(
            f"the guide's narrative says estimates begin in {first_estimate} and its field "
            f"table says {table_first}")
    if table_last < budget_year:
        raise ValueError(
            f"the guide's field table ends the estimates at {table_last}, before the "
            f"budget year {budget_year}")
    return first_estimate, budget_year


def package_year(name: str) -> int:
    match = re.search(r"BUDGET-(\d{4})-DB", str(name))
    if not match:
        raise ValueError(f"{name!r} is not a Public Budget Database package")
    return int(match.group(1))


def load_database(path: Path | str | None = None) -> dict[str, Any]:
    """The committed package, with its digest recomputed and its own guide read.

    Returns the two member tables keyed by measure, the last ACTUAL fiscal
    year, and the sentences the record quotes.
    """
    path = Path(path or DEFAULT_PACKAGE)
    meta_path = path.with_suffix(path.suffix + ".meta.json")
    digest = fixture_digest(path)
    meta: dict[str, Any] = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8")) or {}
    recorded = meta.get("sha256")
    if recorded and recorded != digest:
        raise ValueError(
            f"{path.name}: sha256 on disk {digest} does not match the fetch record {recorded}")

    year = package_year(path.name)
    archive = zipfile.ZipFile(path)
    root = f"BUDGET-{year}-DB"
    guide = guide_text(archive.read(f"{root}/{GUIDE_FILE.format(year=year)}"))
    first_estimate, budget_year = estimate_boundary(guide)
    if budget_year != year:
        raise ValueError(
            f"{path.name}: the guide calls {budget_year} the budget year, the package says {year}")
    last_actual = first_estimate - 1

    tables: dict[str, list[list[str]]] = {}
    for measure, member in MEMBER_FILES.items():
        raw = archive.read(f"{root}/{member.format(year=year)}")
        tables[measure] = list(read_xlsx_rows(io.BytesIO(raw)))
    return {
        "package": root, "sha256": digest, "url": meta.get("url"),
        "fetchedAt": meta.get("fetched_at"),
        "lastActualYear": last_actual, "firstEstimateYear": first_estimate,
        "budgetYear": budget_year, "tables": tables,
        "quotes": {"units": QUOTE_UNITS, "precision": QUOTE_PRECISION,
                   "treasury": QUOTE_TREASURY, "treasuryDifferences": QUOTE_TREASURY_DIFFERENCES,
                   "net": QUOTE_NET, "sign": QUOTE_SIGN},
    }


def _column(header: list[str], name: str) -> int:
    try:
        return header.index(name)
    except ValueError as error:
        raise ValueError(f"the table has no {name!r} column") from error


def _amount(value: Any) -> float:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def totals_for_year(rows: list[list[str]], year: int) -> tuple[dict[str, float], dict[tuple[str, str], float], dict[str, set[str]], dict[Any, int]]:
    """Sum one year's column by agency and by (agency, bureau), with row counts.

    The count matters as much as the sum. **OMB prints no total row anywhere in
    this database** -- every row is an account -- so a unit's figure here is not
    something the publisher states, it is this repository's sum over the account
    rows OMB files under that unit. Saying how many rows were added is what
    turns that from an assertion into something a reader can check.

    Every account row is summed, negative offsetting-receipt rows included,
    because a unit's figure here IS the net of the accounts OMB files under it.
    The record says so rather than silently dropping the negatives.
    """
    header = rows[0]
    a_i = _column(header, "Agency Name")
    b_i = _column(header, "Bureau Name")
    cgac_i = _column(header, "CGAC Agency Code")
    y_i = _column(header, str(year))
    agency: dict[str, float] = {}
    bureau: dict[tuple[str, str], float] = {}
    cgac: dict[str, set[str]] = {}
    counts: dict[Any, int] = {}
    for row in rows[1:]:
        def get(index: int) -> str:
            return str((row[index] if index < len(row) else "") or "").strip()
        agency_name, bureau_name = get(a_i), get(b_i)
        value = _amount(row[y_i] if y_i < len(row) else "")
        agency[agency_name] = agency.get(agency_name, 0.0) + value
        bureau[(agency_name, bureau_name)] = bureau.get((agency_name, bureau_name), 0.0) + value
        counts[agency_name] = counts.get(agency_name, 0) + 1
        counts[(agency_name, bureau_name)] = counts.get((agency_name, bureau_name), 0) + 1
        code = get(cgac_i)
        if code:
            # The CGAC column is PER ACCOUNT, not per agency: 20 of the 160
            # agencies carrying one carry several -- the Treasury nine, the
            # Legislative Branch twenty-two -- because OMB's "Agency" is a
            # budget-presentation grouping over several Treasury entities.
            # Taking the first seen would publish an identifier the file does
            # not assign to the unit, so the whole set is collected and the
            # record publishes a code only where there is exactly one.
            cgac.setdefault(agency_name, set()).add(code)
    return agency, bureau, cgac, counts


def _organisation_index(node_map: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for node in node_map.values():
        if is_post_node(node):
            continue
        type_text = str(node.get("type") or "").casefold()
        if any(word in type_text for word in NON_BUDGET_TYPE_WORDS):
            continue
        key = canonical_name_key(node.get("name"))
        if key:
            index.setdefault(key, []).append(node)
    return index


def _one(index: dict[str, list[dict[str, Any]]], name: str) -> dict[str, Any] | None:
    hits = index.get(canonical_name_key(name)) or []
    return hits[0] if len(hits) == 1 else None


def build_records(
    database: dict[str, Any],
    root: dict[str, Any],
    *,
    index_tree=None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """One record per organisation OMB reports a completed year's figures for."""
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, parent_map = index_tree(root)
    organisations = _organisation_index(node_map)

    year = int(database["lastActualYear"])
    outlay_rows = database["tables"][MEMBER_OUTLAYS]
    authority_rows = database["tables"][MEMBER_AUTHORITY]
    o_agency, o_bureau, cgac, o_counts = totals_for_year(outlay_rows, year)
    a_agency, a_bureau, _, a_counts = totals_for_year(authority_rows, year)

    #: A bureau name several of OMB's agencies use identifies no single row.
    #: This database restates history onto the current account structure, so
    #: "Bureau of Labor Statistics" appears under Commerce as well as Labor.
    bureau_name_owners: dict[str, set[tuple[str, str]]] = {}
    for pair in set(o_bureau) | set(a_bureau):
        bureau_name_owners.setdefault(canonical_name_key(pair[1]), set()).add(pair)

    def ancestors(node_id: str) -> set[str]:
        out: set[str] = set()
        current = parent_map.get(node_id)
        while current:
            out.add(current)
            current = parent_map.get(current)
        return out

    stats: dict[str, Any] = {
        "fiscalYear": year, "agencies": len(o_agency), "bureaus": len(o_bureau),
        "agencies_matched": 0, "bureaus_matched": 0, "records": 0,
        "refused_agency_name_reaches_no_single_organisation": 0,
        "refused_bureau_name_reaches_no_single_organisation": 0,
        "refused_bureau_name_used_by_several_agencies": 0,
        "refused_its_agency_matched_no_node": 0,
        "refused_node_sits_outside_its_agencys_subtree": [],
        "refused_zero_on_both_measures": 0,
        "measure_absent_outlays": 0, "measure_absent_budget_authority": 0,
    }

    agency_node: dict[str, dict[str, Any]] = {}
    for name in o_agency:
        node = _one(organisations, name)
        if node is None:
            stats["refused_agency_name_reaches_no_single_organisation"] += 1
            continue
        agency_node[name] = node
    stats["agencies_matched"] = len(agency_node)

    records: dict[str, dict[str, Any]] = {}

    def stamp(node: dict[str, Any], *, listed_agency: str, listed_bureau: str | None,
              outlays: float | None, authority: float | None, level: str,
              outlay_rows_summed: int = 0, authority_rows_summed: int = 0) -> None:
        node_id = str(node.get("id") or "")
        if not node_id or node_id in records:
            return
        # A measure the package carries no row for is ABSENT, not zero. The two
        # files do not cover the same set of units -- the Farm Credit
        # Administration has outlay rows and no budget-authority rows -- and
        # defaulting the missing one to 0.0 published a measurement that does
        # not exist. Zero is never published here, the rule `usaspending.py`
        # applies to a File A figure of 0.0, and "no row" is not zero either.
        if not outlays and not authority:
            stats["refused_zero_on_both_measures"] += 1
            return
        if outlays is not None and not outlays:
            outlays = None
            stats["measure_absent_outlays"] += 1
        if authority is not None and not authority:
            authority = None
            stats["measure_absent_budget_authority"] += 1
        records[node_id] = {
            "source": SOURCE,
            "nodeName": node.get("name"),
            "level": level,
            "listedAgency": listed_agency,
            "listedBureau": listed_bureau,
            # Published only where OMB's agency maps to exactly one Treasury
            # entity; otherwise the count, so a reader knows why there is none.
            "cgacAgencyCode": (sorted(cgac.get(listed_agency) or ())[0]
                               if len(cgac.get(listed_agency) or ()) == 1 else None),
            "cgacAgencyCodeCount": len(cgac.get(listed_agency) or ()),
            # 2. The selection rule, declared. Summing every row rather than
            # the on-budget ones alone is worth 13x on the Social Security
            # Administration ($1,646.5bn against $125.6bn), so a figure whose
            # rule is not stated cannot be audited.
            "rowSelection": ("every account row OMB files under this unit for the year, "
                             "on-budget and off-budget together, including the negative "
                             "offsetting-receipt rows"),
            "fiscalYear": year,
            "fiscalYearIsActual": True,
            "outlays": None if outlays is None else round(outlays * THOUSAND, 2),
            "budgetAuthority": None if authority is None else round(authority * THOUSAND, 2),
            "units": "thousands_of_dollars_as_published",
            "unitsEvidenceKind": UNITS_EVIDENCE,
            "outlayAccountRows": outlay_rows_summed,
            "budgetAuthorityAccountRows": authority_rows_summed,
            "precisionNote": database["quotes"]["precision"],
            "netQuote": database["quotes"]["net"],
            "signQuote": database["quotes"]["sign"],
            "unitsQuote": database["quotes"]["units"],
            "treasuryQuote": database["quotes"]["treasury"],
            "treasuryDifferencesQuote": database["quotes"]["treasuryDifferences"],
            "package": database["package"],
            "documentSha256": database["sha256"],
            "url": database["url"],
        }
        stats["records"] += 1

    for name, node in agency_node.items():
        stamp(node, listed_agency=name, listed_bureau=None,
              outlays=o_agency.get(name), authority=a_agency.get(name), level="agency",
              outlay_rows_summed=o_counts.get(name, 0), authority_rows_summed=a_counts.get(name, 0))

    for pair in sorted(set(o_bureau) | set(a_bureau)):
        listed_agency, listed_bureau = pair
        node = _one(organisations, listed_bureau)
        if node is None:
            stats["refused_bureau_name_reaches_no_single_organisation"] += 1
            continue
        if len(bureau_name_owners.get(canonical_name_key(listed_bureau), ())) > 1:
            stats["refused_bureau_name_used_by_several_agencies"] += 1
            continue
        parent = agency_node.get(listed_agency)
        if parent is None:
            stats["refused_its_agency_matched_no_node"] += 1
            continue
        node_id = str(node.get("id") or "")
        if node_id != str(parent.get("id") or "") and str(parent.get("id") or "") not in ancestors(node_id):
            # A name is only evidence of placement when something else already
            # placed it. Nothing is resolved either way; the disagreement is
            # recorded and the row is refused.
            stats["refused_node_sits_outside_its_agencys_subtree"].append(
                {"agency": listed_agency, "bureau": listed_bureau, "nodeId": node_id})
            continue
        if node_id in records:
            continue
        stats["bureaus_matched"] += 1
        stamp(node, listed_agency=listed_agency, listed_bureau=listed_bureau,
              outlays=o_bureau.get(pair), authority=a_bureau.get(pair), level="bureau",
              outlay_rows_summed=o_counts.get(pair, 0), authority_rows_summed=a_counts.get(pair, 0))

    return records, stats


def load_omb_budget_evidence(path: Path | str | None = None) -> dict[str, dict[str, Any]]:
    resolved = Path(path or (PROJECT_ROOT / "data" / "verification" / "omb_budget_evidence.json"))
    if not resolved.exists():
        return {}
    store = json.loads(resolved.read_text(encoding="utf-8")) or {}
    return {str(k): v for k, v in (store.get("nodes") or {}).items() if isinstance(v, dict)}


def apply_omb_budget_evidence(
    root: dict[str, Any],
    records: dict[str, dict[str, Any]],
    *,
    index_tree=None,
) -> dict[str, Any]:
    """Stamp OMB's completed-year figures beside the cost, never into it.

    Writes no cost field, no `sourceUrls`, no `sourceTypes`, no `lastVerified`
    and no `verificationMethod`. That channel is exactly how a five-row pay
    table carried 29 positions to `verified` on 2026-09-11, and a budget
    account is not evidence that a unit exists as the graph draws it.
    """
    if index_tree is None:
        from data_pipeline.exporter.build_graph import index_tree as _index_tree

        index_tree = _index_tree
    node_map, _ = index_tree(root)
    stats = {"applied": 0, "unknown_node": 0, "stale_name": 0, "is_a_post": 0,
             "estimated_year_refused": 0, "equals_the_measured_cost": 0}
    for node_id, record in records.items():
        node = node_map.get(node_id)
        if node is None:
            stats["unknown_node"] += 1
            continue
        if is_post_node(node):
            # No federal financial system reports on a post, and an account is
            # not a person's salary.
            stats["is_a_post"] += 1
            continue
        if canonical_name_key(node.get("name")) != canonical_name_key(record.get("nodeName")):
            stats["stale_name"] += 1
            continue
        if not record.get("fiscalYearIsActual"):
            stats["estimated_year_refused"] += 1
            continue
        outlays = record.get("outlays")
        measured = node.get("resolved_total_amount")
        if (str(node.get("cost_status") or "") == "official"
                and isinstance(measured, (int, float)) and isinstance(outlays, (int, float))
                and round(float(measured), 2) == round(float(outlays), 2)):
            # A completed year on OMB's basis cannot equal the current year to
            # date on Treasury's to the cent. Equality means the figure leaked
            # into the cost, which is the check `usaspending.py` makes.
            stats["equals_the_measured_cost"] += 1
            continue
        node["ombBudget"] = {
            "source": record.get("source"),
            "level": record.get("level"),
            "listedAgency": record.get("listedAgency"),
            "listedBureau": record.get("listedBureau"),
            "cgacAgencyCode": record.get("cgacAgencyCode"),
            "cgacAgencyCodeCount": record.get("cgacAgencyCodeCount"),
            "rowSelection": record.get("rowSelection"),
            # So a reader can tie the figure to the committed bytes and the
            # gate can check the digest the block itself names, the way
            # net_cost.py does.
            "documentSha256": record.get("documentSha256"),
            "fiscalYear": record.get("fiscalYear"),
            "outlays": outlays,
            "budgetAuthority": record.get("budgetAuthority"),
            "unitsQuote": record.get("unitsQuote"),
            "precisionNote": record.get("precisionNote"),
            "treasuryQuote": record.get("treasuryQuote"),
            "treasuryDifferencesQuote": record.get("treasuryDifferencesQuote"),
            "netQuote": record.get("netQuote"),
            "signQuote": record.get("signQuote"),
            "outlayAccountRows": record.get("outlayAccountRows"),
            "budgetAuthorityAccountRows": record.get("budgetAuthorityAccountRows"),
            "package": record.get("package"),
            "url": record.get("url"),
        }
        stats["applied"] += 1
    return stats
