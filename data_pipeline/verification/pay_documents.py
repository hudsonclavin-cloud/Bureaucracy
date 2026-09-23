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
    role_words = spec.get("uniformRoles") if _uniform_roster(block) and spec.get("uniformRoles") else spec["roles"]
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
                "caution": (spec.get("uniformCaution") or spec["caution"]) if _uniform_roster(block) else spec["caution"],
                "documentRoles": roles,
            }
            stats["annotated"] += 1
            stats[field] = stats.get(field, 0) + 1
        stack.extend(node.get("children") or [])
    return stats
