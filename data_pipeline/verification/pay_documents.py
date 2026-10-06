"""How many documents a pay figure rests on, and what that count is worth.

`derived_pay.py` introduced this for the one field whose figure no document
states. The owner then asked for it on the rest, and the reason is the same:
`positionPayRate` is a two-document join and `positionStatutoryPay` is one
document's printed figure, and until now the site said so only in prose that
a reader had to assemble for themselves.

## The count is read off the block, not written down

Every pay block already carries the URL of each document it rests on -- the
salary table in `url`, the listing that supplied the level in
`levelSource.url`, the statute in `statuteUrl`, both of a derived figure's in
`documents[].url`. `PAY_DOCUMENT_FIELDS` names those keys per field and
`count_documents` collects the DISTINCT URLs they hold, so the published
count is a fact about the block rather than a constant somebody could edit
away from the truth. A block whose second document went missing publishes 1
and 70%, not 2 and 80%.

## The percentage is this project's own arithmetic

`document_strength_percent` lives in `derived_pay.py` and is imported here
rather than restated: `verify_node_sources` scores one official document
0.4 + 0.3 and each further one +0.1 to a cap of 0.3, so one document is 70%,
two 80%, three 90%. It measures how much official documentation the figure
rests on and NOT the probability that the figure is right, which is why the
next field exists.

## `documentsStatingTheFigure` is the field that keeps the percentage honest

Two documents scoring 80% sounds stronger than one scoring 70% in every case,
and on one of these fields it is weaker: a derived figure's two documents
between them imply a number NEITHER of them prints. So each field declares,
with its reason, how many of its documents state the figure itself:

- every field that quotes a printed rate or a printed pair of bounds declares
  **1** -- the table or the roster prints the number, and the second document,
  where there is one, supplies the level or pay plan that says WHICH printed
  number applies;
- `positionDerivedPay` declares **0**.

The panel prints the two together, and the gate refuses a block whose count,
percentage or stating-count is not what its own URLs and this table give.

Nothing here reads or writes a cost field, a source URL or a verification
method. It annotates blocks that already exist.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from data_pipeline.verification.derived_pay import STRENGTH_SCALE, document_strength_percent

#: Per pay field: where its documents' URLs live, what each one supplies, how
#: many of them state the figure itself, and the sentence the panel prints
#: about what the percentage does not measure.
#:
#: A URL key is either a top-level key holding a string, a (parent, child)
#: pair holding one inside a nested block, or the marker `("documents", "*",
#: "url")` for a list of document records.
PAY_DOCUMENT_FIELDS: dict[str, dict[str, Any]] = {
    "positionPayRate": {
        "urlKeys": ("url", ("levelSource", "url")),
        "roles": {
            "url": "states what that Executive Schedule level pays",
            ("levelSource", "url"): "states the level this post is at",
        },
        "statesTheFigure": 1,
        "caution": (
            "One document states the rate and the other states which level this post is at. "
            "The percentage measures how much official documentation the figure rests on, not "
            "the chance that it is right, and neither document is dated now: the level comes "
            "from a listing and the rate from a table that took effect afterwards."
        ),
    },
    "positionGradePay": {
        "urlKeys": ("url", ("listingSource", "url")),
        "roles": {
            "url": "states the pay system's or grade's printed bounds",
            ("listingSource", "url"): "states the pay plan this post is on",
        },
        "statesTheFigure": 1,
        "caution": (
            "One document prints the bounds and the other states which pay plan this post is "
            "on. The percentage measures how much official documentation the range rests on, "
            "not the chance that it is right -- and a range is not a rate: neither document "
            "says what this post is paid."
        ),
    },
    "positionSchedulePay": {
        # The third key is present only on a reviewed identification
        # (`statutory_schedule.REVIEWED_TITLE_ROWS`): the Code places
        # "Members, Board of Governors" at Level II, and what makes the Vice
        # Chair a member is a second statute. It is a document the level
        # assignment rests on, so it is counted; the count is read off the
        # block, so an ordinary record still counts two.
        "urlKeys": ("url", "statuteUrl", ("identification", "basisUrl")),
        "roles": {
            "url": "states what that Executive Schedule level pays",
            "statuteUrl": "places this post at that level",
            ("identification", "basisUrl"): "identifies this post as the office the Code places at that level",
        },
        "statesTheFigure": 1,
        "caution": (
            "One document states the rate and another is the statute that puts this post at "
            "that level; where a third is listed, it is the statute that says this post is the "
            "office the Code names, because the Code's title is not this node's name. The "
            "percentage measures how much official documentation the figure rests on, not the "
            "chance that it is right."
        ),
        # The same block priced from the Code's CLASS title on a node that
        # stands for a bench (`classTitle`): the level is every member's, and
        # the sentences must not call it "this post's" beside a holders count.
        "classRoles": {
            "url": "states what that Executive Schedule level pays",
            "statuteUrl": "places every member of this body at that level",
            ("identification", "basisUrl"): "composes the body of the members this node stands for",
        },
        "classCaution": (
            "One document states the rate, another is the statute that places every member of "
            "this body at that level, and the third is the statute that composes the body of "
            "those members. The figure is each holder's by the Code's own class title, not one "
            "appointment's; the percentage measures how much official documentation it rests "
            "on, not the chance that it is right."
        ),
        # A single post priced as one member of a COUNTED class ("Assistant
        # Attorneys General (11)"): the Code places the class and names no
        # member, so which post this is rests on the node's own name and
        # placement, reviewed; where a third document is listed it composes
        # the class, and it may also name this office.
        "countedRoles": {
            "url": "states what that Executive Schedule level pays",
            "statuteUrl": "places every office of this class at that level, and counts them",
            ("identification", "basisUrl"): "composes the class of offices this post is one of",
        },
        "countedCaution": (
            "One document states the rate and another is the statute that places every office "
            "of this class at that level without naming any of them; where a third is listed, it "
            "is the statute that composes the class. That this post is one of the class rests on "
            "its own name and where it sits, which a reviewed table records and every build "
            "re-checks. The percentage measures how much official documentation the figure "
            "rests on, not the chance that it is right."
        ),
    },
    "positionStatutoryPay": {
        "urlKeys": ("url",),
        "roles": {"url": "states what this seat or role is paid"},
        "statesTheFigure": 1,
        "caution": (
            "One document states the figure outright. The percentage measures how much "
            "official documentation it rests on, not the chance that it is right, and the "
            "source names a tier or a group of roles rather than this post by name."
        ),
        # The same block on an office a Member of Congress holds (a committee
        # chair, a whip), priced at the SEAT rate since 2026-09-30: Schedule 6
        # states what a Senator or a Member is paid, and that this post is a
        # Member's is a reviewed rule, not anything the schedule says.
        "memberSeatRoles": {"url": "states what a seat in this chamber is paid"},
        "memberSeatCaution": (
            "One document states the figure outright, for the SEAT: Schedule 6 prints what a "
            "Senator or a Member of the House is paid and no separate rate for this office. "
            "That this post is a Member's, and so is paid the seat rate and nothing more, is a "
            "reviewed rule this project applies, not a document naming the post. The percentage "
            "measures how much official documentation the figure rests on, not the chance that "
            "it is right."
        ),
        # The same block where the section names the office itself and states
        # its salary (3 U.S.C. 102, the President, since 2026-10-05): the
        # sentence must not say the source names only a tier.
        "statesOfficeRoles": {"url": "names the office and states what it is paid"},
        "statesOfficeCaution": (
            "One document states the figure outright and names the office itself. Which node of "
            "this graph that office is remains a reviewed identification, so the claim is graded a "
            "proxy. The percentage measures how much official documentation the figure rests on, "
            "not the chance that it is right."
        ),
    },
    "positionReportedPay": {
        "urlKeys": ("url",),
        "roles": {"url": "states what the one person listed under this title is paid"},
        "statesTheFigure": 1,
        "caution": (
            "One document states the figure outright. The percentage measures how much "
            "official documentation it rests on, not the chance that it is right -- and what "
            "the roster reports is what one listed person is paid, not what the post pays "
            "whoever holds it."
        ),
        # The same block on a node the roster lists N times at one rate
        # (`holders.uniformRate`): the figure is each listed person's, and the
        # sentences must not call it one person's beside a count of six.
        "uniformRoles": {"url": "states what each of the people listed under this title is paid"},
        "uniformCaution": (
            "One document states the figure outright. The percentage measures how much "
            "official documentation it rests on, not the chance that it is right -- and what "
            "the roster reports is what each of the people listed under this title is paid, "
            "every one of them at this same figure, not what the post pays whoever holds it."
        ),
    },
    "positionCurrentPay": {
        "urlKeys": ("url",),
        "roles": {"url": "prints the rate for the one row listed under this title now"},
        "statesTheFigure": 1,
        "caution": (
            "One document states the figure outright. The percentage measures how much "
            "official documentation it rests on, not the chance that it is right -- and a row "
            "in that export is an incumbency, not the post's own rate."
        ),
    },
    "positionTierPay": {
        "urlKeys": ("url",),
        "roles": {"url": "prints the tier's minimum and maximum"},
        "statesTheFigure": 1,
        "caution": (
            "One document prints the bounds. The percentage measures how much official "
            "documentation the band rests on, not the chance that it is right -- and a band is "
            "not a rate: the schedule publishes no figure for any holder."
        ),
    },
    "positionDerivedPay": {
        "urlKeys": (("documents", "*", "url"),),
        "roles": {},
        "statesTheFigure": 0,
        "caution": (
            "The percentage measures how much official documentation this figure rests on, "
            "not the chance that it is right. No document here states the figure: one names "
            "the tier this post is paid at, the other states what that tier pays."
        ),
        # A record carrying `arithmetic` (28 U.S.C. 153(a)'s bankruptcy judges,
        # 92 percent of the district-judge rate) rests on the same two
        # documents and is one step further from either: the table prints the
        # base, and the result is this project's multiplication.
        "percentCaution": (
            "The percentage measures how much official documentation this figure rests on, "
            "not the chance that it is right. No document here states the figure: one states "
            "the percentage of a tier this post is paid, the other states what that tier pays, "
            "and the figure is that arithmetic, which neither prints."
        ),
    },
    "positionTierReferencePay": {
        # The derived shape again, from the other side of the Executive
        # Schedule: a statute sets the post's pay by reference to a level the
        # post is not itself placed at, OPM's table prices the level, and --
        # for an Inspector General -- the statute adds 3 percent, which no
        # document prints. Three documents on an IG record: 5 U.S.C. 401(1)'s
        # establishment list is what scopes the claim to this post's
        # organisation.
        "urlKeys": (("documents", "*", "url"),),
        "roles": {},
        "statesTheFigure": 0,
        "caution": (
            "The percentage measures how much official documentation this figure rests on, "
            "not the chance that it is right. No document here states the figure for this post: "
            "a statute sets its pay by reference to an Executive Schedule level, and OPM's table "
            "states what that level pays; where the statute adds a percentage, the result is "
            "arithmetic this project performed and no document prints."
        ),
        # Since 2026-10-07: a Reorganization Plan or a chamber's pay order,
        # which the Code prints outside its sections, sets the pay instead of
        # a statute (notes_instruments.py).
        "instrumentCaution": (
            "The percentage measures how much official documentation this figure rests on, "
            "not the chance that it is right. No document here states the figure for this post: "
            "an instrument the United States Code prints outside its sections -- a Reorganization "
            "Plan, or a chamber's pay order reprinted in a Statutory Note -- sets its pay by reference "
            "to an Executive Schedule level, and OPM's table states what that level pays."
        ),
    },
    "positionMilitaryPay": {
        # Schedule 8 of the pay-adjustment order prints the uniformed services'
        # basic pay BY THE MONTH. A grade-route record rests on three documents
        # (the statute fixing the post's grade, 37 U.S.C. 201 assigning it a
        # pay grade, the schedule pricing the pay grade); a footnote-route
        # record on the schedule alone, whose footnote names the post. Neither
        # states the ANNUAL figure the block publishes: it is twelve times a
        # printed monthly rate, arithmetic the block carries in the open.
        "urlKeys": (("documents", "*", "url"),),
        "roles": {},
        "statesTheFigure": 0,
        "caution": (
            "The percentage measures how much official documentation this figure rests on, "
            "not the chance that it is right. No document here states the annual figure: a "
            "statute fixes the post's grade, 37 U.S.C. 201 assigns that grade a pay grade, and "
            "Schedule 8 prints what that pay grade is paid BY THE MONTH; the annual figure is "
            "twelve times the printed monthly rate, arithmetic this project performed."
        ),
        # The same block on a senior enlisted adviser the schedule's own
        # footnote names: one document, which names the post and prints its
        # monthly rate, and the annual figure is still the multiplication.
        "footnoteCaution": (
            "The percentage measures how much official documentation this figure rests on, "
            "not the chance that it is right. One document, Schedule 8, names this post in its "
            "own footnote and prints its monthly basic pay; no document states the annual "
            "figure, which is twelve times the printed monthly rate, arithmetic this project "
            "performed."
        ),
    },
}

#: Every pay field, in the order the panel prints them. Kept beside the table
#: so a new pay field cannot be added without deciding what its document count
#: is; `tests/test_pay_documents.py` asserts the two lists are the same set as
#: `pay_tables.withdraw_pay_from_multi_post_nodes` sweeps.
PAY_FIELDS = tuple(PAY_DOCUMENT_FIELDS)


def _urls_at(block: Mapping[str, Any], key: Any) -> Iterable[str]:
    """The URL or URLs one declared key holds, skipping anything absent."""
    if isinstance(key, str):
        value = block.get(key)
        if isinstance(value, str) and value.strip():
            yield value.strip()
        return
    if len(key) == 2:
        nested = block.get(key[0])
        if isinstance(nested, Mapping):
            value = nested.get(key[1])
            if isinstance(value, str) and value.strip():
                yield value.strip()
        return
    parent, marker, child = key
    if marker != "*":
        return
    records = block.get(parent)
    if not isinstance(records, list):
        return
    for record in records:
        if isinstance(record, Mapping):
            value = record.get(child)
            if isinstance(value, str) and value.strip():
                yield value.strip()


def _class_title(block: Mapping[str, Any]) -> bool:
    """A schedule block priced from the Code's class title says so itself."""
    return block.get("classTitle") is True


def _percent_of_tier(block: Mapping[str, Any]) -> bool:
    """A derived block that is a percentage of the tier carries the arithmetic."""
    arithmetic = block.get("arithmetic")
    return isinstance(arithmetic, Mapping) and arithmetic.get("operation") == "percent_of"


def _counted_class(block: Mapping[str, Any]) -> bool:
    """A schedule block priced as one member of a counted class says so itself."""
    return isinstance(block.get("countedClass"), Mapping)


def _member_seat(block: Mapping[str, Any]) -> bool:
    """A statutory block that prices an office a Member holds at the seat rate
    says so in `memberSeat`."""
    return isinstance(block.get("memberSeat"), Mapping)


def _states_the_office(block: Mapping[str, Any]) -> bool:
    """A statutory block whose section names the office itself says so."""
    return block.get("statesTheOffice") is True


def _named_in_footnote(block: Mapping[str, Any]) -> bool:
    """A military block priced from Schedule 8's own footnote says so in its
    identification."""
    identification = block.get("identification")
    return isinstance(identification, Mapping) and identification.get("kind") == "named_in_footnote"


def _instrument_based(block: Mapping[str, Any]) -> bool:
    """A block whose pay an instrument outside the Code's sections sets (a
    Reorganization Plan, a chamber's pay order) carries the instrument."""
    return isinstance(block.get("instrument"), Mapping)


def _uniform_roster(block: Mapping[str, Any]) -> bool:
    """A roster block that lists every holder at one rate says so in `holders`."""
    holders = block.get("holders")
    return isinstance(holders, Mapping) and holders.get("uniformRate") is True


def count_documents(field: str, block: Mapping[str, Any]) -> tuple[int, list[dict[str, str]]]:
    """How many DISTINCT documents this block names, and what each supplies.

    Distinct rather than a key count: `positionSchedulePay` names the statute
    and the table, and a build that somehow put the same URL in both would be
    resting on one document, not two.
    """
    spec = PAY_DOCUMENT_FIELDS.get(field)
    if spec is None:
        return 0, []
    seen: list[str] = []
    roles: list[dict[str, str]] = []
    role_words = spec["roles"]
    if _uniform_roster(block) and spec.get("uniformRoles"):
        role_words = spec["uniformRoles"]
    elif _class_title(block) and spec.get("classRoles"):
        role_words = spec["classRoles"]
    elif _counted_class(block) and spec.get("countedRoles"):
        role_words = spec["countedRoles"]
    elif _member_seat(block) and spec.get("memberSeatRoles"):
        role_words = spec["memberSeatRoles"]
    elif _states_the_office(block) and spec.get("statesOfficeRoles"):
        role_words = spec["statesOfficeRoles"]
    for key in spec["urlKeys"]:
        for url in _urls_at(block, key):
            if url in seen:
                continue
            seen.append(url)
            role = role_words.get(key)
            roles.append({"url": url, "role": role} if role else {"url": url})
    return len(seen), roles


def annotate_pay_documents(root: dict[str, Any]) -> dict[str, int]:
    """Stamp `verification` on every pay block in the tree.

    Run after the last pay pass and after the multi-post sweep, so a block that
    was withdrawn is never counted and a block that survived is counted from
    the URLs it actually ends up carrying.
    """
    stats: dict[str, int] = {"annotated": 0, "no_document": 0}
    stack = [root]
    while stack:
        node = stack.pop()
        for field in PAY_FIELDS:
            block = node.get(field)
            if not isinstance(block, dict):
                continue
            spec = PAY_DOCUMENT_FIELDS[field]
            documents, roles = count_documents(field, block)
            if documents <= 0:
                # A pay block with no citable document is not something this
                # pipeline produces; say so in the stats rather than publish a
                # percentage for nothing.
                block.pop("verification", None)
                stats["no_document"] += 1
                continue
            block["verification"] = {
                "documents": documents,
                "documentsStatingTheFigure": int(spec["statesTheFigure"]),
                "percent": document_strength_percent(documents),
                "scale": STRENGTH_SCALE,
                "caution": (
                    (spec.get("uniformCaution") or spec["caution"]) if _uniform_roster(block)
                    else (spec.get("classCaution") or spec["caution"]) if _class_title(block)
                    else (spec.get("countedCaution") or spec["caution"]) if _counted_class(block)
                    else (spec.get("percentCaution") or spec["caution"]) if _percent_of_tier(block)
                    else (spec.get("memberSeatCaution") or spec["caution"]) if _member_seat(block)
                    else (spec.get("statesOfficeCaution") or spec["caution"]) if _states_the_office(block)
                    else (spec.get("footnoteCaution") or spec["caution"]) if _named_in_footnote(block)
                    else (spec.get("instrumentCaution") or spec["caution"]) if _instrument_based(block)
                    else spec["caution"]
                ),
                "documentRoles": roles,
            }
            stats["annotated"] += 1
            stats[field] = stats.get(field, 0) + 1
        stack.extend(node.get("children") or [])
    return stats
