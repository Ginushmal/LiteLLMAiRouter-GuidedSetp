"""Tests for cost-per-task, Pareto, tier assignment, and NMB selection."""

from model_pipeline.config import TaskProfile, load_config
from model_pipeline.emit.output import build_markdown, build_payload
from model_pipeline.emit.report import build_report
from model_pipeline.models import (
    CanonicalModel,
    Deployment,
    Mapping,
    RawModel,
    ResolvedPricing,
)
from model_pipeline.scoring.cost import cost_per_task
from model_pipeline.scoring.nmb import select_tier
from model_pipeline.scoring.pareto import pareto_survivors
from model_pipeline.scoring.pipeline import (
    _excluded_by_config,
    _select_and_rank,
    _tier_eligible,
    score,
)
from model_pipeline.scoring.tiers import absolute_floors, eligible_tiers

TP = TaskProfile(
    input=800,
    cached=50000,
    output=200,
    reasoning=500,
    cache_write=2000,
    requests_per_task=5,
    cache_hit_rate=0.98,
    input_output_ratio=4.0,
    reasoning_price_multiplier=1.0,
)


def _dep(slug: str, cost: float, intel: float, provider: str = "p1") -> Deployment:
    return Deployment(
        canonical_slug=slug,
        canonical_name=slug,
        provider=provider,
        model_id=f"{slug}-{provider}",
        display_name=slug,
        endpoint_type="chat",
        api_base="",
        api_key_env="K",
        intelligence=intel,
        cost_per_task=cost,
    )


# -- cost per task --------------------------------------------------------
def test_strategy_b_prefers_cheaper_cache_read():
    canonical = CanonicalModel(
        slug="x", name="X", intelligence=50, aa_input=2.0, aa_output=10.0, aa_cost_per_task=0.5
    )
    cheap = ResolvedPricing(input=2.0, output=10.0, cache_read=0.1)
    pricey = ResolvedPricing(input=2.0, output=10.0, cache_read=1.0)
    c_cheap = cost_per_task(cheap, canonical, TP)
    c_pricey = cost_per_task(pricey, canonical, TP)
    assert c_cheap.method == "aa_free"
    assert c_cheap.cost_per_task < c_pricey.cost_per_task


def test_strategy_selection():
    no_cost = CanonicalModel(slug="y", name="Y", intelligence=30, aa_input=1.0, aa_output=2.0)
    result = cost_per_task(ResolvedPricing(input=1.0, output=2.0), no_cost, TP)
    assert result.method == "task_profile"


def test_price_provenance_marks_aa_fallback():
    canonical = CanonicalModel(
        slug="z", name="Z", intelligence=40, aa_input=2.0, aa_output=8.0,
        aa_cost_per_task=0.4, aa_cache_read=0.2,
    )
    # Provider omits cache_read -> AA value is used and flagged.
    pricing = ResolvedPricing(input=2.0, output=8.0, cache_read=None)
    result = cost_per_task(pricing, canonical, TP)
    assert result.prices.provenance["cache_read"] == "aa_fallback"
    assert result.prices.provenance["input"] == "provider"


# -- Pareto ---------------------------------------------------------------
def test_pareto_drops_dominated_canonical():
    # A is cheaper AND smarter than B -> B is dominated.
    deps = [_dep("a", 0.10, 50), _dep("b", 0.20, 40)]
    assert pareto_survivors(deps) == {"a"}


def test_pareto_keeps_expensive_variant_that_trades_cost_for_quality():
    # a2 is smarter but pricier -> both survive.
    deps = [_dep("a1", 0.10, 40), _dep("a2", 0.30, 55)]
    assert pareto_survivors(deps) == {"a1", "a2"}


def test_pareto_aggregates_provider_variants_of_same_canonical():
    # Same canonical at two prices: the expensive copy must NOT be dropped as a
    # separate point (it is one canonical, judged by its cheapest provider).
    deps = [_dep("a", 0.10, 50, "p1"), _dep("a", 0.50, 50, "p2"), _dep("b", 0.60, 40)]
    assert pareto_survivors(deps) == {"a"}


# -- tiers ----------------------------------------------------------------
def test_tier_eligibility_is_floor_based_multi_tier():
    floors = absolute_floors({"Ultra": 0.9, "Pro": 0.8, "Flash": 0.5, "Flash Lite": 0.0}, 57.6)
    order = ["Ultra", "Pro", "Flash", "Flash Lite"]
    # A cheap capable model (e.g. MiMo at 46.3) is eligible for every tier below Ultra.
    assert eligible_tiers(46.3, floors, order) == ["Pro", "Flash", "Flash Lite"]
    assert eligible_tiers(57.6, floors, order) == ["Ultra", "Pro", "Flash", "Flash Lite"]
    assert eligible_tiers(40.0, floors, order) == ["Flash", "Flash Lite"]
    assert eligible_tiers(10.0, floors, order) == ["Flash Lite"]


# -- primary vs backup ----------------------------------------------------
def test_primary_preferred_over_higher_nmb_backup():
    # Backup b has lower cost (higher NMB) but must NOT take the only primary slot.
    primary = [_dep("a", 0.10, 50, "p1")]
    backup = [_dep("b", 0.01, 40, "p1")]
    _ranking, selected, backups = _select_and_rank(primary, backup, lam=1.0, mu=0.0, top_k=1)
    assert [d.canonical_slug for d in selected] == ["a"]
    assert backups == 0


def test_backup_fills_thin_tier_and_is_marked():
    primary = [_dep("a", 0.10, 50, "p1")]
    backup = [_dep("b", 0.50, 40, "p1"), _dep("c", 0.60, 30, "p1")]
    _ranking, selected, backups = _select_and_rank(primary, backup, lam=1.0, mu=0.0, top_k=3)
    assert sorted(d.canonical_slug for d in selected) == ["a", "b", "c"]
    assert backups == 2
    by_slug = {d.canonical_slug: d for d in selected}
    assert by_slug["a"].is_backup is False
    assert by_slug["b"].is_backup is True and by_slug["c"].is_backup is True


# -- NMB selection --------------------------------------------------------
def test_same_price_deployments_share_order_and_count_once():
    deps = [
        _dep("a", 0.10, 50, "p1"),
        _dep("a", 0.10, 50, "p2"),  # same canonical + same cost -> same group
        _dep("b", 0.20, 40, "p1"),
    ]
    selected = select_tier(deps, lam=1.0, mu=0.0, top_k=2)
    a = [d for d in selected if d.canonical_slug == "a"]
    b = [d for d in selected if d.canonical_slug == "b"]
    assert len(a) == 2 and {d.order for d in a} == {1}
    assert len(b) == 1 and b[0].order == 2


def test_different_price_variants_compete_separately():
    deps = [_dep("a", 0.10, 50, "p1"), _dep("a", 0.30, 50, "p2")]
    selected = select_tier(deps, lam=1.0, mu=0.0, top_k=5)
    assert {d.order for d in selected} == {1, 2}


def test_topk_filters_uncompetitive_expensive_variant():
    deps = [
        _dep("a", 0.10, 50, "p1"),  # NMB 49.9
        _dep("b", 0.20, 40, "p1"),  # NMB 39.8
        _dep("a", 20.0, 50, "p2"),  # NMB 30.0 -> below the cut
    ]
    selected = select_tier(deps, lam=1.0, mu=0.0, top_k=2)
    assert ("a", "p2") not in [(d.canonical_slug, d.provider) for d in selected]

# -- config exclusion -----------------------------------------------------
def test_excluded_by_config_matches_any_field():
    parts = [
        "commandcode",
        "meta/muse-spark-1.3-contributor",
        "Muse Spark 1.3 Contributor",
        "muse-spark-1-3-contributor",
        "Muse Spark 1.3 Contributor (High)",
    ]
    assert _excluded_by_config(parts, ["contributor"])
    assert _excluded_by_config(parts, ["muse-spark-1.3-contributor"])
    assert not _excluded_by_config(["commandcode", "meta/muse-spark-1.3", "Muse Spark 1.3"], ["contributor"])
    assert not _excluded_by_config(parts, [])


# -- tier-scoped exclusion ------------------------------------------------
def test_tier_scoped_exclusion_only_affects_the_named_tier():
    floors = absolute_floors({"Ultra": 0.5, "Pro": 0.0}, 50)
    order = ["Ultra", "Pro"]
    deps = [_dep("a", 0.10, 50), _dep("b", 0.20, 40)]

    ultra, ultra_excluded = _tier_eligible(deps, "Ultra", floors, order, ["a"])
    pro, pro_excluded = _tier_eligible(deps, "Pro", floors, order, [])

    assert [d.canonical_slug for d in ultra] == ["b"]
    assert ultra_excluded == {"a": ["p1:a-p1"]}
    assert sorted(d.canonical_slug for d in pro) == ["a", "b"]
    assert pro_excluded == {}


def test_tier_exclusion_scope_is_canonical_or_provider():
    floors = {"Pro": 0.0}
    order = ["Pro"]
    deps = [
        _dep("a", 0.10, 50, "p1"),
        _dep("a", 0.20, 50, "p2"),
        _dep("b", 0.30, 40, "p1"),
    ]

    eligible, excluded = _tier_eligible(deps, "Pro", floors, order, ["a"])
    assert [d.canonical_slug for d in eligible] == ["b"]
    assert sorted(excluded["a"]) == ["p1:a-p1", "p2:a-p2"]

    eligible, excluded = _tier_eligible(deps, "Pro", floors, order, ["p2"])
    assert sorted((d.canonical_slug, d.provider) for d in eligible) == [
        ("a", "p1"),
        ("b", "p1"),
    ]
    assert excluded == {"a": ["p2:a-p2"]}


class _StubAdapter:
    """Minimal provider adapter so score() needs no network or LiteLLM."""

    class _Pcfg:
        api_key_env = "TEST_KEY"

    pcfg = _Pcfg()

    def to_litellm_deployment(self, model, pricing, model_group, order):
        return {
            "model_name": model_group,
            "litellm_params": {"api_base": "http://stub"},
            "model_info": {"id": f"mp::{model_group}::{model.model_id}"},
        }


def _score_inputs():
    mappings = [
        Mapping(provider="p1", model_id="a-p1", canonical_slug="a", canonical_name="A"),
        Mapping(provider="p1", model_id="b-p1", canonical_slug="b", canonical_name="B"),
        Mapping(provider="p1", model_id="c-p1", canonical_slug="c", canonical_name="C"),
    ]
    models = {
        ("p1", "a-p1"): RawModel(
            provider="p1",
            model_id="a-p1",
            display_name="A",
            pricing=ResolvedPricing(input=1.0, output=2.0),
        ),
        ("p1", "b-p1"): RawModel(
            provider="p1",
            model_id="b-p1",
            display_name="B",
            pricing=ResolvedPricing(input=1.0, output=2.0),
        ),
        ("p1", "c-p1"): RawModel(
            provider="p1",
            model_id="c-p1",
            display_name="C",
            pricing=ResolvedPricing(input=1.0, output=2.0),
        ),
    }
    canonicals = [
        CanonicalModel(
            slug="a", name="A", intelligence=50, latency_seconds=10,
            aa_input=1.0, aa_output=2.0,
        ),
        CanonicalModel(
            slug="b", name="B", intelligence=40, latency_seconds=20,
            aa_input=1.0, aa_output=2.0,
        ),
        CanonicalModel(
            slug="c", name="C", intelligence=20, latency_seconds=30,
            aa_input=1.0, aa_output=2.0,
        ),
        # Known to the catalog but never fetched: used for the "no scored
        # deployment" warning path.
        CanonicalModel(slug="ghost", name="Ghost", intelligence=30),
    ]
    return mappings, models, canonicals, {"p1": _StubAdapter()}


def _run_score(
    inputs, tier_patterns=None, global_patterns=None, pins=None, top_k=None, rho=None
):
    cfg = load_config()
    cfg.exclude_patterns = list(global_patterns or [])
    cfg.exclude_tier_patterns = dict(tier_patterns or {})
    cfg.pin_slugs = dict(pins or {})
    if top_k is not None:
        cfg.nmb.top_k_per_tier = top_k
    if rho is not None:
        cfg.nmb.latency_rho = rho
    mappings, models, canonicals, adapters = inputs
    return score(mappings, models, canonicals, adapters, cfg), cfg


def _scored(tier_patterns=None, global_patterns=None, pins=None, top_k=None, rho=None):
    return _run_score(
        _score_inputs(),
        tier_patterns=tier_patterns,
        global_patterns=global_patterns,
        pins=pins,
        top_k=top_k,
        rho=rho,
    )


def test_global_pattern_wins_over_tier_scope():
    result, _ = _scored(tier_patterns={"Ultra": ["a"]}, global_patterns=["a"])

    assert result.excluded["excluded_by_config"] == ["p1:a-p1"]
    assert all(not tier.excluded_by_config for tier in result.tiers)
    assert all(
        "a" not in {d.canonical_slug for d in tier.deployments} for tier in result.tiers
    )


def test_tier_exclusion_keeps_sota_and_floors_global():
    baseline, _ = _scored()
    result, _ = _scored(tier_patterns={"Ultra": ["a"]})

    assert result.sota_intelligence == baseline.sota_intelligence == 50
    assert [t.floor_intelligence for t in result.tiers] == [
        t.floor_intelligence for t in baseline.tiers
    ]

    ultra = next(t for t in result.tiers if t.name == "Ultra")
    pro = next(t for t in result.tiers if t.name == "Pro")
    assert "a" not in {d.canonical_slug for d in ultra.deployments}
    assert ultra.excluded_by_config == {"a": ["p1:a-p1"]}
    assert "a" in {d.canonical_slug for d in pro.deployments}


def test_absent_and_empty_tier_maps_do_not_change_the_ranking():
    absent, _ = _scored()
    empty, _ = _scored(tier_patterns={"Ultra": [], "Pro": []})

    assert [[d.deployment_id for d in t.deployments] for t in absent.tiers] == [
        [d.deployment_id for d in t.deployments] for t in empty.tiers
    ]
    assert [t.pool_size for t in absent.tiers] == [t.pool_size for t in empty.tiers]
    assert [
        [(r.canonical_slug, r.status, r.order) for r in t.ranking] for t in absent.tiers
    ] == [
        [(r.canonical_slug, r.status, r.order) for r in t.ranking] for t in empty.tiers
    ]


def test_report_names_tier_scoped_exclusions():
    result, cfg = _scored(tier_patterns={"Ultra": ["a"]})
    report = build_report(result, cfg)

    assert "Excluded in" in report
    assert "Excluded by config: a" in report


# -- tier model pins -------------------------------------------------------
def _tier(result, name):
    return next(t for t in result.tiers if t.name == name)


def test_pin_below_floor_is_included_at_order_one():
    baseline, _ = _scored()
    result, _ = _scored(pins={"Ultra": ["c"]})
    ultra = _tier(result, "Ultra")

    assert ultra.pinned == {"c": 1}
    assert ultra.deployments[0].canonical_slug == "c"
    assert ultra.deployments[0].order == 1
    assert ultra.deployments[0].is_pinned is True
    assert "c" not in {r.canonical_slug for r in ultra.ranking}

    assert result.sota_intelligence == baseline.sota_intelligence == 50
    assert [t.floor_intelligence for t in result.tiers] == [
        t.floor_intelligence for t in baseline.tiers
    ]


def test_two_pins_offset_the_scored_orders():
    result, _ = _scored(pins={"Ultra": ["c", "b"]})
    ultra = _tier(result, "Ultra")
    by_slug = {d.canonical_slug: d for d in ultra.deployments}

    assert ultra.pinned == {"c": 1, "b": 2}
    assert by_slug["c"].order == 1 and by_slug["c"].is_pinned
    assert by_slug["b"].order == 2 and by_slug["b"].is_pinned
    assert by_slug["a"].order == 3 and not by_slug["a"].is_pinned
    assert [r.order for r in ultra.ranking if r.canonical_slug == "a"] == [3]


def test_pins_consume_top_k_slots_and_warn_when_exhausted():
    result, _ = _scored(pins={"Ultra": ["c"]}, top_k=2)
    ultra = _tier(result, "Ultra")
    scored = [d for d in ultra.deployments if not d.is_pinned]
    assert ultra.pinned == {"c": 1}
    assert len(scored) == 1
    assert result.pin_warnings == []

    result, _ = _scored(pins={"Ultra": ["c", "a"]}, top_k=2)
    ultra = _tier(result, "Ultra")
    assert len(ultra.pinned) == 2
    assert [d for d in ultra.deployments if not d.is_pinned] == []
    assert any("no NMB-selected picks" in w for w in result.pin_warnings)


def test_pin_warnings_for_unknown_unscored_and_duplicate_slugs():
    result, _ = _scored(pins={"Ultra": ["nope", "ghost", "a", "a"]})
    ultra = _tier(result, "Ultra")
    joined = " | ".join(result.pin_warnings)

    assert ultra.pinned == {"a": 1}
    assert "nope" in joined and "matches no canonical model" in joined
    assert "ghost" in joined and "no scored deployment" in joined
    assert "listed more than once" in joined


def test_global_and_tier_exclusions_win_over_pins():
    global_result, _ = _scored(pins={"Ultra": ["a"]}, global_patterns=["a"])
    ultra = _tier(global_result, "Ultra")
    assert ultra.pinned == {}
    assert any("globally excluded" in w for w in global_result.pin_warnings)

    tier_result, _ = _scored(pins={"Pro": ["a"]}, tier_patterns={"Pro": ["a"]})
    pro = _tier(tier_result, "Pro")
    assert pro.pinned == {}
    assert any("excluded from Pro" in w for w in tier_result.pin_warnings)


def _inputs_with_second_provider():
    mappings, models, canonicals, adapters = _score_inputs()
    mappings.append(
        Mapping(provider="p2", model_id="a-p2", canonical_slug="a", canonical_name="A")
    )
    models[("p2", "a-p2")] = RawModel(
        provider="p2",
        model_id="a-p2",
        display_name="A",
        pricing=ResolvedPricing(input=2.0, output=4.0),
    )
    return mappings, models, canonicals, {**adapters, "p2": _StubAdapter()}


def test_pinned_canonical_shares_one_order_across_providers():
    result, _ = _run_score(
        _inputs_with_second_provider(), pins={"Pro": ["a"]}
    )
    pro = _tier(result, "Pro")
    a_deps = [d for d in pro.deployments if d.canonical_slug == "a"]
    assert {d.provider for d in a_deps} == {"p1", "p2"}
    assert {d.order for d in a_deps} == {1}
    assert all(d.is_pinned for d in a_deps)

    # A provider removed by the tier's exclusion pattern is not pinned.
    result, _ = _run_score(
        _inputs_with_second_provider(),
        pins={"Pro": ["a"]},
        tier_patterns={"Pro": ["p2"]},
    )
    pro = _tier(result, "Pro")
    a_deps = [d for d in pro.deployments if d.canonical_slug == "a"]
    assert {d.provider for d in a_deps} == {"p1"}
    assert {d.order for d in a_deps} == {1}

    # All deployments excluded -> pin skipped with a warning.
    result, _ = _run_score(
        _inputs_with_second_provider(),
        pins={"Pro": ["a"]},
        tier_patterns={"Pro": ["a"]},
    )
    pro = _tier(result, "Pro")
    assert pro.pinned == {}
    assert any("excluded from Pro" in w for w in result.pin_warnings)


def test_pins_do_not_change_scored_mu_nmb_or_status():
    baseline, _ = _scored(rho=0.4)
    below_floor, _ = _scored(rho=0.4, pins={"Ultra": ["c"]})
    eligible_pin, _ = _scored(rho=0.4, pins={"Ultra": ["a"]})

    base_ultra = _tier(baseline, "Ultra")
    for result in (below_floor, eligible_pin):
        ultra = _tier(result, "Ultra")
        assert ultra.mu == base_ultra.mu
        assert ultra.spread == base_ultra.spread
        assert ultra.median_latency == base_ultra.median_latency

    base_rows = {r.canonical_slug: r for r in base_ultra.ranking}
    below_rows = {r.canonical_slug: r for r in _tier(below_floor, "Ultra").ranking}
    for slug in ("a", "b"):
        assert below_rows[slug].nmb == base_rows[slug].nmb
        assert below_rows[slug].status == base_rows[slug].status
        assert below_rows[slug].order == base_rows[slug].order + 1

    # Pinning a floor-eligible model keeps mu and the other models' NMB and
    # status unchanged; the pinned model simply is not a scored row.
    pin_rows = {r.canonical_slug: r for r in _tier(eligible_pin, "Ultra").ranking}
    assert "a" not in pin_rows
    assert pin_rows["b"].nmb == base_rows["b"].nmb
    assert pin_rows["b"].status == base_rows["b"].status
    assert pin_rows["b"].order == base_rows["b"].order


def test_absent_and_empty_pins_do_not_change_the_ranking():
    absent, _ = _scored()
    empty, _ = _scored(pins={})
    explicit_empty, _ = _scored(pins={"Ultra": []})

    for other in (empty, explicit_empty):
        assert [[d.deployment_id for d in t.deployments] for t in absent.tiers] == [
            [d.deployment_id for d in t.deployments] for t in other.tiers
        ]
        assert [t.pool_size for t in absent.tiers] == [t.pool_size for t in other.tiers]
        assert [
            [(r.canonical_slug, r.status, r.order) for r in t.ranking]
            for t in absent.tiers
        ] == [
            [(r.canonical_slug, r.status, r.order) for r in t.ranking]
            for t in other.tiers
        ]


def test_pin_artifacts_and_reports():
    result, cfg = _scored(pins={"Ultra": ["c"]})
    payload = build_payload(result, cfg)
    ultra = payload["tiers"][0]

    assert ultra["pinned"] == {"c": 1}
    assert payload["pin_warnings"] == []
    by_slug = {d["canonical_slug"]: d for d in ultra["deployments"]}
    assert by_slug["c"]["is_pinned"] is True
    assert by_slug["a"]["is_pinned"] is False

    markdown = build_markdown(payload)
    assert "Pinned by config: c (order 1)" in markdown
    assert "| pinned |" in markdown

    report = build_report(result, cfg)
    assert "**Pinned by config**" in report
    assert "Pinned in" in report
    assert "| 1 | C |" in report


def test_pin_warnings_reach_the_artifacts():
    result, cfg = _scored(pins={"Ultra": ["nope"]})
    payload = build_payload(result, cfg)

    assert payload["pin_warnings"]
    assert "Warnings" in build_report(result, cfg)
    assert "Warnings" in build_markdown(payload)


def test_tier_output_markdown_shows_latency():
    result, cfg = _scored()
    markdown = build_markdown(build_payload(result, cfg))

    assert "| Latency |" in markdown
    for latency in ("10.0s", "20.0s", "30.0s"):
        assert f"| {latency} |" in markdown


def test_tier_output_markdown_marks_unknown_latency():
    inputs = _score_inputs()
    inputs[2][0].latency_seconds = None  # model "a"
    result, cfg = _run_score(inputs)

    markdown = build_markdown(build_payload(result, cfg))
    assert "| unknown |" in markdown
