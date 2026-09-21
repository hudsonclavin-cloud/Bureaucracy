"""Static contracts for the accessible six-generation directory view."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "index.html").read_text(encoding="utf-8")
ATLAS = (ROOT / "js" / "atlas.js").read_text(encoding="utf-8")
STYLES = (ROOT / "css" / "atlas.css").read_text(encoding="utf-8")


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


def test_directory_does_not_present_allocated_estimates_as_financial_facts():
    assert 'node.cost_status === "official" || node.cost_status === "reported"' in ATLAS
    assert "No directly reported figure shown" in ATLAS
    assert "measured`" in ATLAS


def test_directory_exposes_coverage_and_claim_level_cues():
    assert "verified records" in ATLAS
    assert "partially supported" in ATLAS
    assert "reported financial figures" in ATLAS
    assert "No source recorded" in ATLAS
