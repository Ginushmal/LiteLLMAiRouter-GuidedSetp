"""Pareto frontier at the canonical level.

Provider variants of the same canonical model are collapsed to one point
(the cheapest provider) before filtering, so an expensive provider's copy of a
good model survives as a failover option instead of being dominated by its
cheaper sibling. A canonical is dropped only when another canonical beats it on
BOTH intelligence and best cost.
"""

from __future__ import annotations

from model_pipeline.models import Deployment


def best_cost_per_canonical(deployments: list[Deployment]) -> dict[str, tuple[float, float]]:
    """canonical_slug -> (intelligence, best cost_per_task)."""
    best: dict[str, tuple[float, float]] = {}
    for d in deployments:
        if d.intelligence is None:
            continue
        current = best.get(d.canonical_slug)
        if current is None or d.cost_per_task < current[1]:
            best[d.canonical_slug] = (d.intelligence, d.cost_per_task)
    return best


def pareto_survivors(deployments: list[Deployment]) -> set[str]:
    best = best_cost_per_canonical(deployments)
    survivors: set[str] = set()
    for slug, (intel, cost) in best.items():
        dominated = False
        for other_slug, (other_intel, other_cost) in best.items():
            if other_slug == slug:
                continue
            if other_intel >= intel and other_cost <= cost and (
                other_intel > intel or other_cost < cost
            ):
                dominated = True
                break
        if not dominated:
            survivors.add(slug)
    return survivors


def dominator_map(
    deployments: list[Deployment],
) -> dict[str, tuple[str, float, float]]:
    """slug -> (dominator_slug, dominator_intelligence, dominator_cost).

    A dominator is another canonical that is at least as smart AND at least as
    cheap (strictly better on one axis). We keep the smartest dominator so the
    report can explain why a model was only ever a backup.
    """
    best = best_cost_per_canonical(deployments)
    result: dict[str, tuple[str, float, float]] = {}
    for slug, (intel, cost) in best.items():
        dominator: tuple[str, float, float] | None = None
        for other_slug, (other_intel, other_cost) in best.items():
            if other_slug == slug:
                continue
            if other_intel >= intel and other_cost <= cost and (
                other_intel > intel or other_cost < cost
            ):
                if dominator is None or other_intel > dominator[1]:
                    dominator = (other_slug, other_intel, other_cost)
        if dominator is not None:
            result[slug] = dominator
    return result
