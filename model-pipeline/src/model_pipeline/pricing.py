"""Pricing normalization.

Providers publish prices in several shapes:
  * context-tiered (a cheaper price for short context, higher for long),
  * peak / off-peak (time-of-day dependent),
  * discounted / promotional (a strikethrough list price plus an effective one).

This module collapses those into a single effective price per component so the
scorer can compare models fairly.
"""

from __future__ import annotations

from typing import Optional, Sequence


def _to_minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def _overlap_minutes(
    a_start: int, a_end: int, b_start: int, b_end: int
) -> int:
    return max(0, min(a_end, b_end) - max(a_start, b_start))


def weighted_price(
    peak_price: float,
    off_peak_price: float,
    peak_windows: Sequence[tuple[str, str]],
    active_window: tuple[str, str],
    active_days: Sequence[int],
    all_days: int = 7,
) -> float:
    """Weighted average of a peak and an off-peak price.

    The weight is the fraction of the *active window* (the hours you actually
    send traffic on the given days) that falls inside a peak band.

    Example: active window 02:30-12:30 UTC (08:00-18:00 Asia/Colombo) against
    peak bands 01:00-04:00 and 06:00-10:00 UTC gives 5.5 peak hours out of 10,
    so the result is ``0.55 * peak + 0.45 * off_peak``.

    Windows that wrap past midnight are not modelled (none of our providers use
    them); a window is treated as [start, end) within a single day.
    """
    a_start, a_end = _to_minutes(active_window[0]), _to_minutes(active_window[1])
    day_span = max(0, a_end - a_start)
    if day_span == 0 or not active_days:
        return off_peak_price

    total_minutes = day_span * len(active_days)
    peak_minutes = 0
    for band in peak_windows:
        b_start, b_end = _to_minutes(band[0]), _to_minutes(band[1])
        peak_minutes += _overlap_minutes(a_start, a_end, b_start, b_end) * len(
            active_days
        )

    peak_fraction = peak_minutes / total_minutes if total_minutes else 0.0
    return peak_fraction * peak_price + (1.0 - peak_fraction) * off_peak_price


def normalize_context_tiers(
    tiers: Sequence[float], policy: str = "average"
) -> Optional[float]:
    """Collapse context-tiered prices into one value.

    policy: ``average`` (mean of the tiers), ``base`` (first/cheapest tier),
    or ``high`` (last/most expensive tier).
    """
    values = [t for t in tiers if t is not None]
    if not values:
        return None
    if policy == "base":
        return values[0]
    if policy == "high":
        return values[-1]
    return sum(values) / len(values)


def effective_price(list_price: Optional[float], discounted: Optional[float]) -> Optional[float]:
    """Prefer the discounted price when the provider publishes one."""
    if discounted is not None:
        return discounted
    return list_price
