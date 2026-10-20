"""Tests for pricing normalization."""

from model_pipeline.pricing import (
    effective_price,
    normalize_context_tiers,
    weighted_price,
)


def test_weighted_price_srilanka_window():
    # 08:00-18:00 Asia/Colombo == 02:30-12:30 UTC.
    # Peak bands 01:00-04:00 and 06:00-10:00 UTC overlap 1.5h + 4h = 5.5h of 10h.
    got = weighted_price(
        peak_price=0.30,
        off_peak_price=0.15,
        peak_windows=[("01:00", "04:00"), ("06:00", "10:00")],
        active_window=("02:30", "12:30"),
        active_days=[0, 1, 2, 3, 4],
    )
    # 0.55*0.30 + 0.45*0.15 = 0.165 + 0.0675 = 0.2325
    assert abs(got - 0.2325) < 1e-9


def test_weighted_price_no_peak():
    got = weighted_price(1.0, 0.5, [], ("02:30", "12:30"), [0, 1, 2, 3, 4])
    assert got == 0.5


def test_weighted_price_all_peak():
    got = weighted_price(1.0, 0.5, [("00:00", "23:59")], ("02:30", "12:30"), [0])
    # nearly all peak
    assert got > 0.99


def test_context_tier_average():
    assert normalize_context_tiers([2.0, 4.0], "average") == 3.0
    assert normalize_context_tiers([2.0, 4.0], "base") == 2.0
    assert normalize_context_tiers([2.0, 4.0], "high") == 4.0
    assert normalize_context_tiers([], "average") is None


def test_effective_price_prefers_discount():
    assert effective_price(0.80, 0.14) == 0.14
    assert effective_price(0.80, None) == 0.80
