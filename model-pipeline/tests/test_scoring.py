"""Tests for cost-per-task, Pareto, tier assignment, and NMB selection."""

from model_pipeline.config import TaskProfile
from model_pipeline.models import CanonicalModel, Deployment, ResolvedPricing
from model_pipeline.scoring.cost import cost_per_task
from model_pipeline.scoring.nmb import select_tier
from model_pipeline.scoring.pareto import pareto_survivors
from model_pipeline.scoring.pipeline import _excluded_by_config, _select_and_rank
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
