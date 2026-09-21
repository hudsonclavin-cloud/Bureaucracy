"""Static contracts for the accessible six-generation directory view.

The directory (`js/atlas.js`) is a second reader of the same published graph
the 3D universe draws, and it may not claim more than the info panel in
`js/ui.js` does. These tests pin the wording the two share by reading it out
of both files rather than restating it here, so a hedge tightened in the
panel cannot quietly loosen in the directory.
"""

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
ATLAS = (ROOT / "js" / "atlas.js").read_text(encoding="utf-8")
UI = (ROOT / "js" / "ui.js").read_text(encoding="utf-8")
STYLES = (ROOT / "css" / "atlas.css").read_text(encoding="utf-8")
SMOKE = (ROOT / "scripts" / "frontend_smoke.mjs").read_text(encoding="utf-8")


def _string_map(source: str, name: str) -> dict[str, str]:
    """The `key: "text"` pairs of the object literal `const <name> = {...}`."""
    # A literal ends either as a statement (`};`) or as an indexed lookup
    # (`}[String(...)]`), the form both files use for `directoryPlacement`.
    match = re.search(rf"const {name} = \{{(.*?)\n\s*\}}[;\[]", source, re.S)
    assert match, f"{name} not found"
    body = re.sub(r"^\s*//.*$", "", match.group(1), flags=re.M)
    pairs = re.findall(r"(\w+):\s*(?:`([^`]*)`|\"([^\"]*)\")", body)
    return {key: backtick or plain for key, backtick, plain in pairs}


def test_universe_is_the_default_but_the_directory_remains_available():
    assert '<body class="atlas-mode">' not in INDEX
    assert 'data-view="atlas"' in INDEX
    assert 'class="view-switch active" data-view="universe" aria-pressed="true"' in INDEX
    assert "body:not(.atlas-mode) #atlas" in STYLES


def test_directory_has_a_hard_six_generation_product_boundary():
    assert "const MAX_GENERATION = 6;" in ATLAS
    assert 'data-atlas-depth="6"' in INDEX
    assert "Math.min(MAX_GENERATION" in ATLAS


def test_primary_controls_use_native_interactive_elements():
    assert '<input id="atlas-search" type="search"' in INDEX
    assert '<button type="button" class="view-switch' in INDEX
    assert 'aria-label="Organization browser"' in INDEX
    assert 'aria-live="polite"' in INDEX
    assert '<input id="atlas-show-superseded" type="checkbox">' in INDEX


def test_measured_means_what_the_pipeline_means_and_nothing_else():
    # `cost_status: reported` does not exist in this pipeline; the old view
    # tested for it and would have called a figure measured on a value no
    # build ever writes. Measured is official/root_total with the cost verified.
    assert '"reported"' not in ATLAS
    assert 'status === "official" || status === "root_total"' in ATLAS
    assert 'String(node.costVerificationStatus || "").toLowerCase() === "verified"' in ATLAS


def test_apportioned_estimates_are_withheld_in_the_panels_words():
    assert 'if (status === "allocated") {' in ATLAS
    assert '"Estimate withheld"' in ATLAS
    # The first two sentences of the panel's own note, as the panel's source
    # splits them across string literals.
    for fragment in (
        "No record names this node's own cost. The figure this graph could otherwise show is its share of an ancestor's ",
        "measured total, divided among siblings by budget, headcount or subtree size — a number nobody measured, so it is ",
        "not shown here.",
    ):
        assert fragment in UI, fragment
    assert "a number nobody measured, so it is not shown here" in ATLAS
    # Nothing formats an allocated amount: the only money formatter is the
    # exact one, reached from the measured branch alone.
    assert "formatExactMoney" in ATLAS
    assert ATLAS.count("formatExactMoney(") == 2  # the definition and the measured branch


def test_a_post_says_the_panels_sentence_and_shows_pay_under_its_own_heading():
    post_sentence = "This is a post, not a unit of government. No federal financial system reports spending for an individual post"
    assert post_sentence in UI
    assert post_sentence in ATLAS
    assert 'validation === "post_is_not_a_budget_unit"' in ATLAS
    for field in ("positionPayRate", "positionSchedulePay", "positionStatutoryPay", "positionReportedPay", "positionListing"):
        assert field in ATLAS, field
    assert 'row("Pay"' in ATLAS
    assert "not a share of federal outlays, which is what every other figure in this graph means" in ATLAS


def test_evidence_states_mirror_the_panel_word_for_word():
    ui_methods = _string_map(UI, "METHOD_TEXT")
    atlas_methods = _string_map(ATLAS, "METHOD_TEXT")
    assert ui_methods, "ui.js METHOD_TEXT unreadable"
    for key, text in ui_methods.items():
        assert atlas_methods.get(key) == text, key
    # The archive's own method, which the panel words in its listing block.
    assert "listed_in_opm_plum_archive" in atlas_methods
    ui_unread = _string_map(UI, "UNREAD_TEXT")
    atlas_unread = _string_map(ATLAS, "UNREAD_TEXT")
    assert set(ui_unread) == {"host_refuses_crawler", "robots_unreachable", "page_not_found", "page_below_readable_floor", "site_failing", "network_error", "other"}
    assert atlas_unread == ui_unread
    assert _string_map(UI, "SOURCE_TEXT") == _string_map(ATLAS, "SOURCE_TEXT")
    # The failed checks, worded as what was tested.
    assert 'node.verificationFailure === "not_in_official_list"' in ATLAS
    assert 'node.verificationFailure === "not_found"' in ATLAS
    assert "does not name it as a heading or link" in ATLAS
    assert 'it carries no unit of this name under "' in ATLAS
    # "No source recorded" is reached only by the never-checked rule, after
    # the failed and unread branches have had their say.
    assert ATLAS.index('verificationFailure === "not_found"') < ATLAS.index("if (isNeverChecked(node))")
    assert ATLAS.index("node.verificationUnread") < ATLAS.index("if (isNeverChecked(node))")
    assert "return sourceCount === 0 && !node.lastVerified;" in ATLAS


def test_descriptions_are_labelled_as_the_panel_labels_them():
    ui_labels = dict(re.findall(r'descriptionSource \|\| ""\) === "(\w+)"\) \{(?:[^}]*?)"DESCRIPTION: ([^"]+)"', UI, re.S))
    atlas_labels = _string_map(ATLAS, "DESCRIPTION_SOURCE_TEXT")
    assert ui_labels, "ui.js description labels unreadable"
    assert atlas_labels == ui_labels
    assert "uncited prose from the base graph — not checked against any source" in UI
    assert "uncited prose from the base graph — not checked against any source" in ATLAS


def test_placement_is_the_path_and_the_evidence_for_the_edge_separately():
    assert 'row("Filed under"' in ATLAS
    assert 'row("Placement", describePlacement(node))' in ATLAS
    for branch in (
        "node.placementVerified === true",
        "node.placementVerified === false",
        "node.placementCheckable === false",
        "placementDirectoryDisagreement",
        "placementDirectoryAncestor",
    ):
        assert branch in ATLAS, branch
    for sentence in (
        "does not list it as a heading or link — no claim either way",
        "Could not be checked — its parent is a curated grouping with no official page of its own",
        "No evidence recorded for where this sits in the hierarchy",
        "the two sources disagree, and neither is resolved",
        "Not claimed separately — the page that names a post is its organisation's own",
    ):
        assert sentence in ATLAS, sentence
    ui_placements = _string_map(UI, "directoryPlacement")
    atlas_placements = _string_map(ATLAS, "directoryPlacement")
    for key, text in ui_placements.items():
        assert atlas_placements.get(key) == text, key


def test_the_cost_source_is_kept_apart_from_the_existence_evidence():
    assert "Open primary evidence" not in ATLAS
    assert "sourceUrls || [])[0]" not in ATLAS
    assert "function isCostSourceUrl" in ATLAS
    assert 'row("Cost source"' in ATLAS
    assert "Evidence of the cost, not of the unit's existence." in ATLAS
    assert "!isCostSourceUrl(url)" in ATLAS


def test_superseded_units_are_hidden_by_default_and_labelled_when_shown():
    assert "showSuperseded: false" in ATLAS
    assert 'String(node?.lifecycle || "") === "superseded"' in ATLAS
    assert "REPLACED — the government no longer has this unit as drawn" in UI
    assert "REPLACED — the government no longer has this unit as drawn" in ATLAS
    assert "also show units the government has replaced" in INDEX
    # Search and the columns both go through the visibility rule.
    assert "&& isVisible(node))" in ATLAS
    assert "visibleChildren(state.root)" in ATLAS


def test_candidates_never_appear_in_the_directory():
    # The directory reads the pruned viewer copy only, which carries no
    # review-queue record, so it has no candidate state to get wrong.
    assert "isCandidate" not in ATLAS
    assert "candidate_nodes" not in ATLAS
    served = ROOT / "output" / "graph.min.json"
    if served.exists():
        stack = [json.loads(served.read_text(encoding="utf-8"))]
        while stack:
            node = stack.pop()
            assert "isCandidate" not in node, node.get("id")
            stack.extend(child for child in node.get("children", []) if isinstance(child, dict))


def test_coverage_strip_uses_the_panels_definitions_and_no_others():
    assert "verified records" not in ATLAS
    assert "reported financial figures" not in ATLAS
    assert "partially supported" not in ATLAS
    assert "costs measured from the Monthly Treasury Statement" in UI
    assert "costs measured from the Monthly Treasury Statement" in ATLAS
    assert "apportioned estimates, withheld" in ATLAS
    assert "nodes carry a source" in ATLAS
    # The same three counting rules as summariseGraph, and the smoke check
    # recomputes each from the served graph.
    assert 'if (status === "allocated") count.allocated += 1;' in ATLAS
    assert "if (Array.isArray(node.sourceUrls) && node.sourceUrls.length) count.sourced += 1;" in ATLAS
    assert 'else if (status === "official" || status === "root_total") count.measured += 1;' in ATLAS
    assert "the directory's measured count is the graph's own" in SMOKE
    assert "the directory's sourced count is the graph's own" in SMOKE
    assert "the directory's estimate count is the graph's own" in SMOKE
