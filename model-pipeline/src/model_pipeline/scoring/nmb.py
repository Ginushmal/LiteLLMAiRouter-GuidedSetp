"""NMB (Net Monetary Benefit) ranking and per-tier group selection.

    NMB = lambda * intelligence - cost_per_task - mu * latency

Deployments are ranked by their own NMB. Deployments that share a canonical
model AND cost share ONE group -> one order, and count once toward top-K.
Deployments with different costs each compete independently.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from model_pipeline.models import Deployment


def nmb(
    intelligence: float,
    cost_per_task: float,
    latency: float | None,
    lam: float,
    mu: float,
) -> float:
    penalty = mu * latency if (mu and latency is not None) else 0.0
    return lam * intelligence - cost_per_task - penalty


@dataclass
class Group:
    """One NMB group: a canonical model at one effective cost."""

    canonical_slug: str
    cost: float
    nmb: float
    members: list[Deployment] = field(default_factory=list)
    backup: bool = False

    @property
    def key(self) -> tuple[str, float]:
        return (self.canonical_slug, round(self.cost, 9))


def rank_groups(deployments: list[Deployment], lam: float, mu: float) -> list[Group]:
    """Group deployments by (canonical, cost) and rank groups by NMB."""
    buckets: dict[tuple[str, float], list[Deployment]] = {}
    for d in deployments:
        key = (d.canonical_slug, round(d.cost_per_task, 9))
        buckets.setdefault(key, []).append(d)

    groups: list[Group] = []
    for (slug, cost), members in buckets.items():
        score = nmb(members[0].intelligence, cost, None, lam, mu)
        groups.append(Group(canonical_slug=slug, cost=cost, nmb=score, members=members))
    groups.sort(key=lambda g: (-g.nmb, g.canonical_slug, g.cost))
    return groups


def assign_orders(groups: list[Group]) -> list[Deployment]:
    """Stamp each group's members with its order (1-based) and NMB."""
    selected: list[Deployment] = []
    for rank, group in enumerate(groups, start=1):
        for d in group.members:
            d.nmb = group.nmb
            d.order = rank
            if group.backup:
                d.is_backup = True
        selected.extend(group.members)
    return selected


def select_tier(
    deployments: list[Deployment], lam: float, mu: float, top_k: int
) -> list[Deployment]:
    """Rank, group, take the top-K groups, and stamp order/nmb on members."""
    return assign_orders(rank_groups(deployments, lam, mu)[:top_k])
