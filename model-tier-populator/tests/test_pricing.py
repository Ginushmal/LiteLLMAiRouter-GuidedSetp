"""Tests for pricing normalization."""

from datetime import datetime, timezone

import pytest

from model_pipeline.pricing import (
    PriceBand,
    band_price,
    collapse_tiers,
    effective_price,
    normalize_context_tiers,
    time_price,
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


# -- time-of-day modes ----------------------------------------------------
# Weekday schedule: peak 01:00-04:00 and 06:00-10:00, off-peak otherwise.
WINDOW = ("02:30", "12:30")
WEEKDAYS = [0, 1, 2, 3, 4]
WEDNESDAY = datetime(2026, 10, 21, 9, 14, tzinfo=timezone.utc)
SATURDAY = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)


def _weekday_bands() -> list[PriceBand]:
    return [
        band_price(0.30, "01:00", "04:00", WEEKDAYS),
        band_price(0.30, "06:00", "10:00", WEEKDAYS),
    ]


def test_instant_picks_the_band_at_the_exact_instant():
    bands = _weekday_bands()
    assert time_price(0.15, bands, "instant", WINDOW, WEEKDAYS, WEDNESDAY) == 0.30
    evening = datetime(2026, 10, 21, 18, 0, tzinfo=timezone.utc)
    assert time_price(0.15, bands, "instant", WINDOW, WEEKDAYS, evening) == 0.15


def test_today_weights_this_weekday_but_not_the_weekend():
    bands = _weekday_bands()
    # Wednesday 02:30-12:30 contains 5.5 peak hours out of 10.
    assert abs(time_price(0.15, bands, "today", WINDOW, WEEKDAYS, WEDNESDAY) - 0.2325) < 1e-9
    # Saturday: the weekday-only bands do not apply, so it is plain off-peak.
    assert time_price(0.15, bands, "today", WINDOW, WEEKDAYS, SATURDAY) == 0.15


def test_average_uses_the_whole_configured_week():
    bands = _weekday_bands()
    assert abs(time_price(0.15, bands, "average", WINDOW, WEEKDAYS, SATURDAY) - 0.2325) < 1e-9


def test_weighted_price_honours_the_configured_mode():
    # OpenCode's peak/off-peak goes through this two-band wrapper.
    peak, off, peak_windows = 0.30, 0.15, [("01:00", "04:00")]
    # Wednesday: 1.5h of the 10h window is peak.
    got = weighted_price(
        peak, off, peak_windows, WINDOW, WEEKDAYS, mode="today", as_of=WEDNESDAY
    )
    assert abs(got - (1.5 * peak + 8.5 * off) / 10) < 1e-9
    # Saturday: the peak band only applies on active days (Mon-Fri).
    got = weighted_price(
        peak, off, peak_windows, WINDOW, WEEKDAYS, mode="today", as_of=SATURDAY
    )
    assert got == off
    # Instant is the exact rate at that moment.
    got = weighted_price(
        peak,
        off,
        peak_windows,
        WINDOW,
        WEEKDAYS,
        mode="instant",
        as_of=datetime(2026, 10, 21, 2, 0, tzinfo=timezone.utc),
    )
    assert got == peak


def test_bands_without_a_day_mask_apply_every_day():
    bands = [band_price(0.30, 0, 1600)]  # 00:00-16:00 daily
    assert time_price(0.10, bands, "today", WINDOW, WEEKDAYS, SATURDAY) == 0.30
    assert time_price(0.10, bands, "instant", WINDOW, WEEKDAYS, WEDNESDAY) == 0.30
    evening = datetime(2026, 10, 21, 20, 0, tzinfo=timezone.utc)
    assert time_price(0.10, bands, "instant", WINDOW, WEEKDAYS, evening) == 0.10


def test_base_price_applies_outside_every_band():
    # 01:00-04:00 only; the rest of the active window is uncovered.
    bands = [band_price(0.30, "01:00", "04:00")]
    assert time_price(0.15, bands, "instant", WINDOW, WEEKDAYS, WEDNESDAY) == 0.15
    # 1.5h of 10h at 0.30, the rest at 0.15.
    got = time_price(0.15, bands, "today", WINDOW, WEEKDAYS, WEDNESDAY)
    assert abs(got - (1.5 * 0.30 + 8.5 * 0.15) / 10) < 1e-9


def test_hhmm_numbers_and_end_of_day():
    band = band_price(0.10, 1600, 0)  # 16:00-00:00
    assert band.start == 960 and band.end == 1440
    assert not any(start <= 900 < end for start, end in band.ranges())
    assert any(start <= 1200 < end for start, end in band.ranges())


def test_unknown_mode_and_naive_instant_are_rejected():
    with pytest.raises(ValueError, match="time_price_mode"):
        time_price(1.0, [], "tomorrow")
    with pytest.raises(ValueError, match="timezone-aware"):
        time_price(1.0, [], "instant", WINDOW, WEEKDAYS, datetime(2026, 10, 21, 9, 0))


# -- context x time collapse ---------------------------------------------
def test_collapse_tiers_resolves_time_before_context():
    # Base tier: 0.10 with a peak band; high-context tier: flat 0.50.
    tiers = [
        (0.10, [band_price(0.30, "01:00", "04:00")]),
        (0.50, []),
    ]
    # Instant inside the band: (0.30 + 0.50) / 2.
    in_band = datetime(2026, 10, 21, 2, 0, tzinfo=timezone.utc)
    got = collapse_tiers(
        tiers, "instant", WINDOW, WEEKDAYS, in_band, policy="average"
    )
    assert abs(got - 0.40) < 1e-9
    # Outside the band: (0.10 + 0.50) / 2.
    evening = datetime(2026, 10, 21, 18, 0, tzinfo=timezone.utc)
    got = collapse_tiers(tiers, "instant", WINDOW, WEEKDAYS, evening, policy="average")
    assert abs(got - 0.30) < 1e-9


def test_collapse_tiers_honours_the_context_policy():
    tiers = [(0.10, []), (0.50, [])]
    assert collapse_tiers(tiers, "today", WINDOW, WEEKDAYS, WEDNESDAY, "average") == 0.30
    assert collapse_tiers(tiers, "today", WINDOW, WEEKDAYS, WEDNESDAY, "base") == 0.10
    assert collapse_tiers(tiers, "today", WINDOW, WEEKDAYS, WEDNESDAY, "high") == 0.50
