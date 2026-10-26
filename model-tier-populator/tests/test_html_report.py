"""Tests for the self-contained HTML tier report."""

import re

from model_pipeline.emit.html_report import (
    _pareto_points,
    _pareto_svg,
    _place_labels,
    build_html,
)
from model_pipeline.models import Deployment, Mapping, RankedModel
from model_pipeline.scoring.pipeline import ScoredTier, ScoreResult


def _dep(slug, provider="p1", backup=False, order=1, pinned=False):
    return Deployment(
        canonical_slug=slug,
        canonical_name=slug.upper(),
        provider=provider,
        model_id=f"{slug}-id",
        display_name=f"Name {slug}",
        endpoint_type="chat",
        api_base="https://provider.example/v1",
        api_key_env="K",
        intelligence=50.0,
        cost_per_task=0.10,
        latency_seconds=10.0,
        nmb=49.9,
        tier="Ultra",
        model_group="ultra-tier",
        order=order,
        pareto_frontier=True,
        is_backup=backup,
        is_pinned=pinned,
    )


def _row(slug, status="primary", order=1, frontier=True):
    return RankedModel(
        canonical_slug=slug,
        canonical_name=slug.upper(),
        display_name=f"Name {slug}",
        providers=["p1"],
        intelligence=50.0,
        cost_per_task=0.10,
        nmb=49.9,
        on_frontier=frontier,
        status=status,
        order=order,
        latency_seconds=10.0,
    )


def _result():
    tier = ScoredTier(
        name="Ultra",
        model_group="ultra-tier",
        floor_intelligence=40.0,
        floor_frac=0.8,
        lam=1.0,
        pool_size=2,
        backup_count=0,
        mu=0.0,
        rho=0.0,
        spread=1.0,
        median_latency=10.0,
        deployments=[_dep("a")],
        ranking=[_row("a"), _row("b", status="cut", order=0, frontier=False)],
    )
    return ScoreResult(
        generated_at="2026-10-23T17:01:53+00:00",
        sota_intelligence=50.0,
        tiers=[tier],
        excluded={"unmapped": ["p1:ghost"]},
        parameters={"top_k_per_tier": 10},
        cost_methods={"aa_free": 1},
        pareto_kept=1,
        pareto_dropped=1,
        dominators={"b": ("a", 50.0, 0.10)},
        limit_flags={"p1:a-id": ["unresolved"]},
        pin_warnings=["pins.tiers.Ultra: 'nope' matches no canonical model; ignored"],
    )


def test_html_covers_every_reporting_section():
    page = build_html(_result())
    for section in (
        "Model pipeline — tier report",
        "SOTA intelligence",
        "Cost methods",
        "ultra-tier",
        "Model index",
        "Per-tier rankings",
        "Pareto frontier",
        "Excluded",
        "Token limits",
        "Warnings",
        "cut line",
        "Dominated by",
    ):
        assert section in page


def test_html_escapes_hostile_model_names():
    result = _result()
    result.tiers[0].deployments[0].display_name = '<script>alert("x")</script> & co'
    page = build_html(result)
    assert "<script>alert" not in page
    assert "&lt;script&gt;" in page
    assert "&amp; co" in page


def test_html_has_no_external_resource_references():
    page = build_html(_result())
    assert "<link" not in page
    assert "src=" not in page
    assert "@import" not in page
    assert "url(" not in page


def test_tier_rankings_are_collapsible():
    page = build_html(_result())
    assert "<details><summary>" in page


def test_low_confidence_banner_points_at_mappings_csv():
    rows = [
        Mapping(
            provider="p1",
            model_id="x-p1",
            canonical_slug="x",
            canonical_name="X",
            confidence=0.3,
            low_confidence=True,
        )
    ]
    page = build_html(_result(), rows)
    assert "low-confidence mapping" in page
    assert "output/mappings.csv" in page


def test_no_banner_without_low_confidence_rows():
    assert "low-confidence mapping" not in build_html(_result())
    assert "low-confidence mapping" not in build_html(_result(), [])


# -- layout: warnings at the bottom ----------------------------------------


def test_warnings_section_comes_after_the_ranked_content():
    page = build_html(_result(), [])
    warnings_at = page.index('id="warnings"')
    assert warnings_at > page.index('id="rankings"')
    assert warnings_at > page.index('id="index-nav"')
    assert warnings_at > page.index('id="tiers"')
    assert warnings_at > page.index('id="pareto"')
    # No low-confidence block anywhere when none were reported.
    assert "low-confidence mapping" not in page


def test_low_confidence_block_sits_inside_the_warnings_section():
    rows = [
        Mapping(
            provider="p1", model_id="x-p1", canonical_slug="x",
            canonical_name="X", confidence=0.3, low_confidence=True,
        )
    ]
    page = build_html(_result(), rows)
    warnings_at = page.index('id="warnings"')
    assert page.index("low-confidence mapping") > warnings_at


def test_warnings_absent_when_there_is_nothing_to_warn_about():
    result = _result()
    result.pin_warnings = []
    page = build_html(result, [])
    assert 'id="warnings"' not in page
    assert "<h2>Warnings</h2>" not in page


# -- top-pick highlighting -------------------------------------------------


def test_top_pick_rows_are_highlighted():
    page = build_html(_result())
    # One highlighted row in the tier table, one in the per-tier ranking.
    assert page.count('class="top-pick"') == 2
    assert "&#9733;" in page  # the star marker legend


def test_non_top_picks_are_not_highlighted():
    page = build_html(_result())
    # The cut row must not carry the top-pick class.
    assert not re.search(r'<tr class="top-pick"><td>&mdash;</td>', page)


# -- dominated-by moves into the model index -------------------------------


def test_model_index_names_the_dominator():
    page = build_html(_result())
    assert "<th>Dominated by</th>" in page
    # Dominator "Name a" is named inside the index, with its intel and cost.
    assert re.search(r"Dominated by</th>.*Name a", page, re.DOTALL)
    assert "intel 50.0" in page


def test_the_old_dominated_models_table_is_gone():
    page = build_html(_result())
    assert "Dominated models" not in page
    assert "Beaten by" not in page


def test_quick_picks_section_is_gone():
    assert "Quick picks" not in build_html(_result())


# -- visuals: interactive Pareto chart -------------------------------------


def _chart_dep(slug, intel, cost, order=1, pinned=False):
    return Deployment(
        canonical_slug=slug,
        canonical_name=slug.upper(),
        provider="p1",
        model_id=f"{slug}-id",
        display_name=f"Name {slug}",
        endpoint_type="chat",
        api_base="https://provider.example/v1",
        api_key_env="K",
        intelligence=intel,
        cost_per_task=cost,
        nmb=1.0,
        tier="Ultra",
        model_group="ultra-tier",
        order=order,
        pareto_frontier=True,
        is_pinned=pinned,
    )


def _chart_row(slug, intel, cost, frontier, status="primary", order=1):
    return RankedModel(
        canonical_slug=slug,
        canonical_name=slug.upper(),
        display_name=f"Name {slug}",
        providers=["p1"],
        intelligence=intel,
        cost_per_task=cost,
        nmb=1.0,
        on_frontier=frontier,
        status=status,
        order=order,
        latency_seconds=10.0,
    )


def _chart_result():
    tier = ScoredTier(
        name="Ultra",
        model_group="ultra-tier",
        floor_intelligence=20.0,
        floor_frac=0.4,
        lam=1.0,
        pool_size=5,
        backup_count=0,
        deployments=[_chart_dep("big", 55.0, 2.0, pinned=True)],
        ranking=[
            _chart_row("big", 55.0, 2.0, True, "primary", 1),
            _chart_row("mid", 45.0, 0.2, True, "primary", 2),
            _chart_row("small", 35.0, 0.02, True, "primary", 3),
            _chart_row("pricey", 50.0, 5.0, False, "cut", 0),
            _chart_row("freebie", 25.0, 0.0, True, "backup", 4),
        ],
    )
    return ScoreResult(
        generated_at="2026-10-23T17:01:53+00:00",
        sota_intelligence=55.0,
        tiers=[tier],
        excluded={},
        parameters={"top_k_per_tier": 10},
        cost_methods={},
        pareto_kept=4,
        pareto_dropped=1,
        dominators={"pricey": ("big", 55.0, 2.0)},
        limit_flags={},
        pin_warnings=[],
    )


def test_pareto_points_cover_every_scored_model():
    pts = {p["slug"]: p for p in _pareto_points(_chart_result())}
    assert set(pts) == {"big", "mid", "small", "pricey", "freebie"}
    assert pts["big"]["frontier"] is True
    assert pts["pricey"]["frontier"] is False
    assert pts["pricey"]["dom"] == "Name big"
    assert pts["pricey"]["dom_intel"] == 55.0
    assert pts["big"]["dom"] == ""


def test_every_point_has_a_hover_hit_area_with_data():
    svg = _pareto_svg(_chart_result())
    assert svg.count('class="hit"') == 5
    assert 'data-name="Name pricey"' in svg
    assert 'data-dom="Name big"' in svg
    assert 'data-domcost="$2.0000"' in svg
    # Interactive panel rather than a native <title> tooltip.
    assert 'id="tip"' in svg
    assert "<title>" not in svg


def test_tooltip_javascript_reads_the_data_attributes():
    page = build_html(_chart_result())
    assert "tipDom.textContent='dominated by '" in page
    assert "#chart .hit" in page


def test_free_models_are_pinned_to_the_left_edge():
    svg = _pareto_svg(_chart_result())
    assert svg.count("<polygon") == 1
    assert 'data-free="1"' in svg
    assert "left edge" in svg
    # The diamond sits at the plot's left border (ml = 90 + 3).
    assert 'points="93.0,' in svg


def test_pareto_svg_log_scale_separates_decades_along_x():
    svg = _pareto_svg(_chart_result())
    cx = {}
    for tag in re.findall(r'<circle class="hit"[^>]*>', svg):
        name = re.search(r'data-name="Name ([^"]+)"', tag).group(1)
        cx[name] = float(re.search(r'cx="([\d.]+)"', tag).group(1))
    # Cheaper models sit further left: $0.02 < $0.2 < $2 < $5.
    assert cx["small"] < cx["mid"] < cx["big"] < cx["pricey"]


def test_intelligence_increases_upward():
    svg = _pareto_svg(_chart_result())
    cy = {}
    for tag in re.findall(r'<circle class="hit"[^>]*>', svg):
        name = re.search(r'data-name="Name ([^"]+)"', tag).group(1)
        cy[name] = float(re.search(r'cy="([\d.]+)"', tag).group(1))
    # Higher intelligence -> smaller y (closer to the top).
    assert cy["big"] < cy["mid"] < cy["small"]


def test_frontier_labels_never_overlap():
    frontier = [
        {"name": "Model number " + str(i), "intel": 20.0 + i * 4, "cost": 0.1, "frontier": True}
        for i in range(8)
    ]
    placed = _place_labels(
        frontier,
        lambda p: 100.0 + p["intel"] * 10,
        lambda p: 300.0 - p["intel"] * 2,
        (80.0, 30.0, 900.0, 500.0),
    )
    boxes = [
        (p["x"], p["y"] - 13, p["x"] + 6.0 * len(p["name"]) + 8, p["y"] + 4)
        for p in placed
    ]
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            assert not (
                a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
            ), "labels overlap"


def test_chart_labels_only_frontier_models():
    svg = _pareto_svg(_chart_result())
    labels = re.findall(r'class="lbl"[^>]*>([^<]+)', svg)
    assert len(labels) == 4
    assert "Name pricey" not in labels


def test_visual_sections_are_in_the_page():
    page = build_html(_chart_result())
    assert "<svg" in page
    assert "Pareto frontier" in page
