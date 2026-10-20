"""NMB (Net Monetary Benefit) ranking and per-tier group selection.

    NMB = lambda * intelligence - cost_per_task - mu * latency

Deployments are ranked by their own NMB. Deployments that share a canonical
model AND cost share ONE group -> one order, and count once toward top-K.
Deployments with different costs each compete independently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median

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
        score = nmb(members[0].intelligence, cost, members[0].latency_seconds, lam, mu)
        groups.append(Group(canonical_slug=slug, cost=cost, nmb=score, members=members))
    groups.sort(key=lambda g: (-g.nmb, g.canonical_slug, g.cost))
    return groups


def nmb_spread(deployments: list[Deployment], lam: float) -> float:
    """NMB range of a tier's eligible groups, measured without the latency term."""
    groups = rank_groups(deployments, lam, 0.0)
    if len(groups) < 2:
        return 0.0
    values = [group.nmb for group in groups]
    return max(values) - min(values)


def calibrate_mu(
    deployments: list[Deployment], lam: float, rho: float
) -> tuple[float, float, float]:
    """Derive the per-second latency weight from a share of the tier's NMB spread.

    A model at the tier's median latency loses ``rho * spread`` NMB, so
    ``mu = rho * spread / median_latency``. Returns ``(mu, spread,
    median_latency)``. ``mu`` is 0 when the tier has no spread or no latency
    data — there is nothing to calibrate against, and no value is invented.
    """
    spread = nmb_spread(deployments, lam)
    latencies = [d.latency_seconds for d in deployments if d.latency_seconds is not None]
    median_latency = median(latencies) if latencies else 0.0
    if rho <= 0 or spread <= 0 or median_latency <= 0:
        return 0.0, spread, median_latency
    return rho * spread / median_latency, spread, median_latency


def assign_orders(groups: list[Group], start: int = 1) -> list[Deployment]:
    """Stamp each group's members with its order (1-based unless ``start`` is set)."""
    selected: list[Deployment] = []
    for rank, group in enumerate(groups, start=start):
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
