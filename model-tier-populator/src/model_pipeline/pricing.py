"""Pricing normalization.

Providers publish prices in several shapes:
  * context-tiered (a cheaper price for short context, higher for long),
  * peak / off-peak (time-of-day dependent),
  * discounted / promotional (a strikethrough list price plus an effective one).

This module collapses those into a single effective price per component so the
scorer can compare models fairly.

Time-of-day prices have three evaluation modes (``time_price_mode``):

  average   weighted over the whole configured week (active window x active
            days) - the original behaviour.
  today     weighted over today's slice of the active window using that date's
            own weekday; a weekday-only schedule therefore comes out as plain
            off-peak on a weekend run.
  instant   the single price that applies at the evaluation instant, no
            averaging.

Some providers publish hours per model (``pricing.overrides[]``). Those bands
are evaluated with the model's own windows and day masks - never with the
globally configured peak windows.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import pairwise

TIME_PRICE_MODES = ("average", "today", "instant")

_DAY_NAMES = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

_FULL_DAY = 1440


def hhmm_to_minutes(value: int | str) -> int:
    """Convert ``"HH:MM"`` or an HHMM number (``100``) to minutes after midnight.

    ``0`` stays ``0`` (midnight); callers that use ``utc_end`` treat a zero end
    as end-of-day (see :func:`band_price`).
    """
    if isinstance(value, str):
        text = value.strip()
        if ":" in text:
            hours, minutes = text.split(":", 1)
            return int(hours) * 60 + int(minutes)
        value = int(text)
    hours, minutes = divmod(int(value), 100)
    if minutes >= 60:
        raise ValueError(f"invalid HHMM value {value!r}: minutes must be < 60")
    return hours * 60 + minutes


def days_from_names(names: Sequence[str]) -> frozenset[int]:
    """Weekday names (``["monday", ...]``) to ISO weekday numbers (0=Mon).

    ISO numbers are accepted as-is. Unknown names fail loudly: a silent skip
    would put a price window on the wrong days, which is worse than failing the
    fetch phase.
    """
    result: set[int] = set()
    for name in names:
        if isinstance(name, int):
            if not 0 <= name <= 6:
                raise ValueError(f"weekday number out of range: {name!r}")
            result.add(name)
            continue
        key = str(name).strip().lower()
        if key not in _DAY_NAMES:
            raise ValueError(f"unknown weekday name {name!r}")
        result.add(_DAY_NAMES[key])
    return frozenset(result)


@dataclass(frozen=True)
class PriceBand:
    """One published price that applies inside a time window.

    ``start``/``end`` are minutes after midnight UTC (``end`` exclusive), and
    ``days`` is a set of ISO weekdays. ``None`` means "all day" / "every day".
    A band that ends at 00:00 is an end-of-day band, and a band whose end is
    before its start wraps past midnight.
    """

    price: float
    start: int | None = None
    end: int | None = None
    days: frozenset[int] | None = None

    def ranges(self) -> tuple[tuple[int, int], ...]:
        """The band's intraday ranges as ``[start, end)`` minute pairs."""
        if self.start is None or self.end is None:
            return ((0, _FULL_DAY),)
        start, end = self.start, self.end
        if end == 0:
            end = _FULL_DAY
        if start == end:
            return ((0, _FULL_DAY),)
        if end > start:
            return ((start, end),)
        return ((start, _FULL_DAY), (0, end))


def band_price(
    price: float,
    start: int | str | None = None,
    end: int | str | None = None,
    days: Sequence[str] | frozenset[int] | None = None,
) -> PriceBand:
    """Build a :class:`PriceBand` from provider-shaped values.

    ``start``/``end`` accept ``"HH:MM"`` or HHMM numbers (``1600``); a zero
    ``end`` means end of day. ``days`` accepts weekday names or ISO numbers.
    """
    start_minutes = None if start is None else hhmm_to_minutes(start)
    end_minutes = None if end is None else hhmm_to_minutes(end)
    if end_minutes == 0:
        end_minutes = _FULL_DAY
    if isinstance(days, frozenset):
        day_set: frozenset[int] | None = days
    elif days is None:
        day_set = None
    else:
        day_set = days_from_names(days)
    return PriceBand(price=price, start=start_minutes, end=end_minutes, days=day_set)


def _window_minutes(active_window: tuple[str, str]) -> tuple[int, int]:
    return hhmm_to_minutes(active_window[0]), hhmm_to_minutes(active_window[1])


def _band_covers(band: PriceBand, minute: int) -> bool:
    return any(start <= minute < end for start, end in band.ranges())


def _instant_price(
    base_price: float, bands: Sequence[PriceBand], instant: datetime
) -> float:
    minute = instant.hour * 60 + instant.minute
    weekday = instant.weekday()
    price = base_price
    for band in bands:
        if band.days is not None and weekday not in band.days:
            continue
        if _band_covers(band, minute):
            # The last matching band wins when schedules overlap.
            price = band.price
    return price


def _day_span(
    base_price: float,
    bands: Sequence[PriceBand],
    weekday: int,
    start: int,
    end: int,
) -> tuple[float, int]:
    """Weighted price sum and minutes for one day's slice of the active window."""
    minutes = end - start
    if minutes <= 0:
        return 0.0, 0

    applicable = [b for b in bands if b.days is None or weekday in b.days]
    if not applicable:
        return base_price * minutes, minutes

    boundaries = {start, end}
    for band in applicable:
        for band_start, band_end in band.ranges():
            if band_end <= start or band_start >= end:
                continue
            boundaries.add(max(band_start, start))
            boundaries.add(min(band_end, end))

    points = sorted(boundaries)
    total = 0.0
    for seg_start, seg_end in pairwise(points):
        if seg_end <= seg_start:
            continue
        middle = (seg_start + seg_end) / 2
        price = base_price
        for band in applicable:
            if _band_covers(band, middle):
                price = band.price
        total += price * (seg_end - seg_start)
    return total, minutes


def time_price(
    base_price: float,
    bands: Sequence[PriceBand] = (),
    mode: str = "average",
    active_window: tuple[str, str] = ("00:00", "24:00"),
    active_days: Sequence[int] = (0, 1, 2, 3, 4, 5, 6),
    as_of: datetime | None = None,
) -> float:
    """Collapse a time-of-day schedule into one price using ``mode``.

    ``base_price`` is the published price outside every band. ``as_of`` fixes
    the evaluation instant (default: now); it must be timezone-aware.
    """
    if mode not in TIME_PRICE_MODES:
        raise ValueError(
            f"time_price_mode must be one of {', '.join(TIME_PRICE_MODES)}; got {mode!r}"
        )
    instant = as_of or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("as_of must be timezone-aware (e.g. 2026-10-22T18:00Z)")

    if mode == "instant":
        return _instant_price(base_price, bands, instant)

    days = [instant.weekday()] if mode == "today" else sorted(set(active_days))
    start, end = _window_minutes(active_window)

    total = 0.0
    minutes = 0
    for weekday in days:
        day_total, day_minutes = _day_span(base_price, bands, weekday, start, end)
        total += day_total
        minutes += day_minutes
    return total / minutes if minutes else base_price


def collapse_tiers(
    tiers: Sequence[tuple[float, Sequence[PriceBand]]],
    mode: str = "average",
    active_window: tuple[str, str] = ("00:00", "24:00"),
    active_days: Sequence[int] = (0, 1, 2, 3, 4, 5, 6),
    as_of: datetime | None = None,
    policy: str = "average",
) -> float | None:
    """Resolve the time dimension per context tier, then collapse the tiers.

    Each tier is ``(base_price, time_bands)``. This is the order the spec
    requires: time first (it depends on the run's instant), then context
    (which depends on the request size, unknown to the pipeline).
    """
    values = [
        time_price(base, bands, mode, active_window, active_days, as_of)
        for base, bands in tiers
    ]
    return normalize_context_tiers(values, policy)


def weighted_price(
    peak_price: float,
    off_peak_price: float,
    peak_windows: Sequence[tuple[str, str]],
    active_window: tuple[str, str],
    active_days: Sequence[int],
    all_days: int = 7,
    mode: str = "average",
    as_of: datetime | None = None,
) -> float:
    """Weighted average of a peak and an off-peak price.

    Kept for the two-band providers (OpenCode publishes only "Peak"/"Off-Peak"
    labels plus the configured windows). A band's day mask is the configured
    ``active_days``, so the same schedule produces the historical average in
    ``average`` mode and plain off-peak on a weekend in ``today`` mode.

    Example: active window 02:30-12:30 UTC (08:00-18:00 Asia/Colombo) against
    peak bands 01:00-04:00 and 06:00-10:00 UTC gives 5.5 peak hours out of 10,
    so the result is ``0.55 * peak + 0.45 * off_peak``.
    """
    peak_days = frozenset(active_days)
    bands = [
        band_price(peak_price, start, end, peak_days) for start, end in peak_windows
    ]
    return time_price(
        off_peak_price,
        bands,
        mode=mode,
        active_window=active_window,
        active_days=active_days,
        as_of=as_of,
    )


def normalize_context_tiers(
    tiers: Sequence[float], policy: str = "average"
) -> float | None:
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


def effective_price(list_price: float | None, discounted: float | None) -> float | None:
    """Prefer the discounted price when the provider publishes one."""
    if discounted is not None:
        return discounted
    return list_price
