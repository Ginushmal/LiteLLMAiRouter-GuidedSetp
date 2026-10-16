"""SOTA-relative tier eligibility.

Tier floors are fractions of the current best intelligence, so tiers re-scale
automatically as new models ship. A floor is a *minimum*: a model is eligible
for **every** tier whose floor it meets, not just the highest one. That lets a
cheap, capable model serve both lower and higher tiers (multi-tier membership).
"""

from __future__ import annotations

from model_pipeline.models import Deployment


def sota_intelligence(
    deployments: list[Deployment], allowed: set[str] | None = None
) -> float:
    values = [
        d.intelligence
        for d in deployments
        if d.intelligence is not None and (allowed is None or d.canonical_slug in allowed)
    ]
    return max(values) if values else 0.0


def absolute_floors(tier_floors: dict[str, float], sota: float) -> dict[str, float]:
    return {name: frac * sota for name, frac in tier_floors.items()}


def eligible_tiers(
    intelligence: float, floors: dict[str, float], order: list[str]
) -> list[str]:
    """Every tier whose floor the intelligence meets (floor = minimum)."""
    return [name for name in order if intelligence >= floors[name]]
