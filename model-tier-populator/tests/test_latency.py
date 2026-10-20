"""Tests for latency capture, the per-tier latency weight, and the NMB penalty."""

import pytest

from model_pipeline.config import NmbConfig
from model_pipeline.emit.report import build_report
from model_pipeline.models import Deployment, RankedModel
from model_pipeline.scoring.aa import to_canonical
from model_pipeline.scoring.nmb import calibrate_mu, rank_groups
from model_pipeline.scoring.pipeline import ScoreResult, ScoredTier


# -- AA capture ------------------------------------------------------------
def test_to_canonical_reads_end_to_end_latency():
    raw = {
        "slug": "gpt-6-luna",
        "name": "GPT-6 Luna",
        "performance": {"median_end_to_end_response_time_seconds": 12.5},
    }
    assert to_canonical(raw).latency_seconds == 12.5


def test_to_canonical_without_performance_leaves_latency_none():
    assert to_canonical({"slug": "x", "name": "X"}).latency_seconds is None
    assert (
        to_canonical({"slug": "y", "name": "Y", "performance": {}}).latency_seconds is None
    )


def _dep(slug: str, intel: float, cost: float, latency: float | None) -> Deployment:
    return Deployment(
        canonical_slug=slug,
        canonical_name=slug,
        provider="p1",
        model_id=f"{slug}-p1",
        display_name=slug,
        endpoint_type="chat",
        api_base="",
        api_key_env="K",
        intelligence=intel,
        cost_per_task=cost,
        latency_seconds=latency,
    )


def test_deployment_record_carries_latency():
    assert _dep("m", 50, 1.0, 12.5).to_dict()["latency_seconds"] == 12.5
    assert _dep("m", 50, 1.0, None).to_dict()["latency_seconds"] is None


# -- per-tier config -------------------------------------------------------
def _nmb(rho, floors: dict[str, float] | None = None) -> NmbConfig:
    return NmbConfig(
        tier_lambdas={"Ultra": 1.0, "Flash": 0.005},
        latency_rho=rho,
        tier_floors=floors or {"Ultra": 0.8, "Flash": 0.35},
        top_k_per_tier=5,
    )


def test_rho_is_read_per_tier():
    cfg = _nmb({"Ultra": 0.15, "Flash": 0.4})
    assert cfg.rho_for("Ultra") == 0.15
    assert cfg.rho_for("Flash") == 0.4


def test_rho_scalar_applies_to_every_tier():
    cfg = _nmb(0.2)
    assert cfg.rho_for("Ultra") == cfg.rho_for("Flash") == 0.2


def test_rho_missing_tier_names_the_tier_and_configured_keys():
    cfg = _nmb({"Ultra": 0.15})
    with pytest.raises(ValueError) as exc:
        cfg.rho_for("Flash")
    message = str(exc.value)
    assert "Flash" in message
    assert "Ultra" in message


# -- calibration -----------------------------------------------------------
def test_calibrate_mu_from_share_spread_and_median_latency():
    deps = [
        _dep("a", 50, 0.0, 10.0),
        _dep("b", 40, 0.0, 20.0),
        _dep("c", 30, 0.0, 30.0),
    ]
    # lam=1, cost=0 -> NMB 50/40/30 -> spread 20; latencies 10/20/30 -> median 20.
    mu, spread, median_latency = calibrate_mu(deps, lam=1.0, rho=0.2)
    assert (spread, median_latency) == (20.0, 20.0)
    assert mu == pytest.approx(0.2)
    # A median-latency model loses exactly rho * spread.
    assert mu * median_latency == pytest.approx(0.2 * spread)


def test_calibrate_mu_scales_with_the_share():
    deps = [_dep("a", 50, 0.0, 10.0), _dep("b", 40, 0.0, 30.0)]
    low, _, _ = calibrate_mu(deps, lam=1.0, rho=0.1)
    high, _, _ = calibrate_mu(deps, lam=1.0, rho=0.5)
    assert high == pytest.approx(low * 5)


def test_calibrate_mu_is_zero_without_latency_data():
    deps = [_dep("a", 50, 0.0, None), _dep("b", 40, 0.0, None)]
    mu, spread, median_latency = calibrate_mu(deps, lam=1.0, rho=0.4)
    assert (mu, median_latency) == (0.0, 0.0)
    assert spread == 10.0  # the ranking range still exists, it just is not charged


def test_calibrate_mu_is_zero_without_spread():
    deps = [_dep("a", 50, 0.0, 10.0)]
    assert calibrate_mu(deps, lam=1.0, rho=0.4) == (0.0, 0.0, 10.0)


# -- ranking ---------------------------------------------------------------
def _rank(deps: list[Deployment], mu: float) -> list[str]:
    return [group.canonical_slug for group in rank_groups(deps, lam=1.0, mu=mu)]


def test_slower_model_loses_rank_when_mu_is_positive():
    fast = _dep("a-fast", 50, 1.0, 5)
    slow = _dep("z-slow", 50, 1.0, 100)
    assert _rank([slow, fast], 0.01) == ["a-fast", "z-slow"]


def test_mu_zero_ignores_latency():
    fast = _dep("a-fast", 50, 1.0, 5)
    slow = _dep("z-slow", 50, 1.0, 100)
    # Equal NMB -> the deterministic slug tie-break decides, not the latency.
    assert _rank([slow, fast], 0.0) == ["a-fast", "z-slow"]


def test_missing_latency_gets_no_penalty():
    fast = _dep("a-fast", 50, 1.0, 5)
    unknown = _dep("z-unknown", 50, 1.0, None)
    # The unknown-latency model is not invented as slow, so it ranks first.
    assert _rank([fast, unknown], 0.01) == ["z-unknown", "a-fast"]


def test_penalty_does_not_override_a_clearly_better_model():
    slow_smart = _dep("z-smart", 60, 1.0, 600)
    fast_weak = _dep("a-fast", 50, 1.0, 500)
    # 60 - 1 - 6 = 53 vs 50 - 1 - 5 = 44: latency is a penalty, not a filter.
    assert _rank([fast_weak, slow_smart], 0.01) == ["z-smart", "a-fast"]


# -- report ----------------------------------------------------------------
def test_report_shows_per_tier_mu_latency_and_penalty():
    row = RankedModel(
        canonical_slug="m",
        canonical_name="M",
        display_name="M",
        providers=["p1"],
        intelligence=50.0,
        cost_per_task=1.0,
        nmb=10.0,
        on_frontier=True,
        status="primary",
        order=1,
        latency_seconds=100.0,
    )
    tier = ScoredTier(
        name="Ultra",
        model_group="ultra-tier",
        floor_intelligence=46.0,
        floor_frac=0.8,
        lam=1.0,
        pool_size=1,
        backup_count=0,
        mu=0.02,
        rho=0.2,
        spread=10.0,
        median_latency=100.0,
        ranking=[row],
    )
    result = ScoreResult(
        generated_at="now",
        sota_intelligence=57.6,
        tiers=[tier],
        excluded={},
        parameters={
            "top_k_per_tier": 5,
            "tier_lambdas": {"Ultra": 1.0},
            "latency_rho": {"Ultra": 0.2},
            "latency_penalty_mu": {"Ultra": 0.02},
        },
        cost_methods={},
        pareto_kept=1,
        pareto_dropped=0,
    )
    report = build_report(result, cfg=None)
    assert "mu = rho × tier NMB spread" in report
    assert "rho 0.2 → mu 0.02" in report
    assert "spread 10.00 ÷ median 100.0 s" in report
    assert "100.0s" in report  # the model's latency
    assert "2.00" in report  # 0.02 * 100 = penalty
