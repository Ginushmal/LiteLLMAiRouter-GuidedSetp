"""Scoring pipeline: mappings + prices -> ranked tiers -> deployments.

Ranking flow:
  1. Build one deployment per (mapping, provider model) with a cost-per-task.
  2. Mark the Pareto frontier. Frontier models are PRIMARY candidates; the rest
     are BACKUP (a dominated model is never picked as a primary).
  3. Compute SOTA-relative floors. A model is eligible for EVERY tier whose
     floor it meets (floors are minimums), so a cheap capable model can serve
     several tiers (multi-tier membership).
  4. Per tier: rank eligible primary groups by NMB, take top-K; if short, fill
     from the tier's own backup (dominated) groups (marked as backup). The full
     ranked list (selected + cut) is kept for the explainability report.
  5. Build the LiteLLM payload for each selected deployment.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import datetime, timezone

from model_pipeline.config import Config
from model_pipeline.models import (
    CanonicalModel,
    Deployment,
    Mapping,
    RankedModel,
    RawModel,
)
from model_pipeline.providers.base import ProviderAdapter
from model_pipeline.scoring.cost import cost_per_task
from model_pipeline.scoring.nmb import Group, assign_orders, rank_groups
from model_pipeline.scoring.pareto import dominator_map, pareto_survivors
from model_pipeline.scoring.tiers import absolute_floors, eligible_tiers, sota_intelligence


@dataclass
class ScoredTier:
    name: str
    model_group: str
    floor_intelligence: float
    floor_frac: float
    lam: float
    pool_size: int
    backup_count: int
    deployments: list[Deployment] = field(default_factory=list)
    ranking: list[RankedModel] = field(default_factory=list)


@dataclass
class ScoreResult:
    generated_at: str
    sota_intelligence: float
    tiers: list[ScoredTier]
    excluded: dict[str, list[str]]
    parameters: dict
    cost_methods: dict[str, int]
    pareto_kept: int
    pareto_dropped: int
    dominators: dict[str, tuple[str, float, float]] = field(default_factory=dict)

    def all_deployments(self) -> list[Deployment]:
        return [d for t in self.tiers for d in t.deployments]


def _raw_for(d: Deployment) -> RawModel:
    return RawModel(
        provider=d.provider,
        model_id=d.model_id,
        display_name=d.display_name,
        endpoint_type=d.endpoint_type,
        context_tokens=d.context_tokens,
    )


def _excluded_by_config(parts: list[str], patterns: list[str]) -> bool:
    """True when any pattern is a case-insensitive substring of the joined parts."""
    if not patterns:
        return False
    hay = " ".join(p for p in parts if p).lower()
    return any(pat.lower() in hay for pat in patterns if pat)


def _build_deployments(
    mappings: list[Mapping],
    models_index: dict[tuple[str, str], RawModel],
    canonical_by_slug: dict[str, CanonicalModel],
    adapters: dict[str, ProviderAdapter],
    cfg: Config,
) -> tuple[list[Deployment], dict[str, list[str]]]:
    deployments: list[Deployment] = []
    excluded: dict[str, list[str]] = {
        "excluded_by_config": [],
        "unmapped": [],
        "no_pricing": [],
        "no_intelligence": [],
    }

    for mp in mappings:
        slug = mp.effective_slug
        tag = f"{mp.provider}:{mp.model_id}"
        if not slug:
            excluded["unmapped"].append(tag)
            continue
        canonical = canonical_by_slug.get(slug)
        if canonical is None:
            excluded["unmapped"].append(f"{tag} -> {slug} (unknown slug)")
            continue
        model = models_index.get((mp.provider, mp.model_id))
        if _excluded_by_config(
            [
                mp.provider,
                mp.model_id,
                model.display_name if model else "",
                canonical.slug,
                canonical.name,
            ],
            cfg.exclude_patterns,
        ):
            excluded["excluded_by_config"].append(tag)
            continue
        if model is None or model.pricing is None:
            excluded["no_pricing"].append(tag)
            continue
        if canonical.intelligence is None:
            excluded["no_intelligence"].append(tag)
            continue

        cost = cost_per_task(model.pricing, canonical, cfg.task_profile)
        adapter = adapters[mp.provider]
        deployments.append(
            Deployment(
                canonical_slug=slug,
                canonical_name=canonical.name,
                provider=mp.provider,
                model_id=mp.model_id,
                display_name=model.display_name,
                endpoint_type=model.endpoint_type,
                api_base="",  # filled from the adapter payload below
                api_key_env=adapter.pcfg.api_key_env,
                intelligence=canonical.intelligence,
                cost_per_task=cost.cost_per_task,
                cost_method=cost.method,
                context_tokens=model.context_tokens,
                effective_prices=cost.prices.as_dict(),
                provider_pricing=model.pricing,
            )
        )
    return deployments, {k: v for k, v in excluded.items() if v}


def _rank_row(group: Group, frontier: bool, status: str, order: int) -> RankedModel:
    first = group.members[0]
    return RankedModel(
        canonical_slug=group.canonical_slug,
        canonical_name=first.canonical_name,
        display_name=first.display_name,
        providers=sorted({m.provider for m in group.members}),
        intelligence=first.intelligence,
        cost_per_task=group.cost,
        nmb=group.nmb,
        on_frontier=frontier,
        status=status,
        order=order,
    )


def _select_and_rank(
    primary: list[Deployment], backup: list[Deployment], lam: float, mu: float, top_k: int
) -> tuple[list[RankedModel], list[Deployment], int]:
    """Rank primary groups, take top-K, fill from backup, and return the full ranking."""
    prim = rank_groups(primary, lam, mu)
    back = rank_groups(backup, lam, mu)
    n_primary = min(len(prim), top_k)
    selected_primary = prim[:n_primary]
    selected_backup = back[: max(0, top_k - n_primary)]
    for group in selected_backup:
        group.backup = True

    selected = assign_orders(selected_primary + selected_backup)

    ranking: list[RankedModel] = []
    for i, group in enumerate(prim):
        chosen = i < n_primary
        ranking.append(
            _rank_row(group, True, "primary" if chosen else "cut", i + 1 if chosen else 0)
        )
    for i, group in enumerate(back):
        chosen = i < len(selected_backup)
        ranking.append(
            _rank_row(
                group, False, "backup" if chosen else "cut", n_primary + i + 1 if chosen else 0
            )
        )
    return ranking, selected, len(selected_backup)


def score(
    mappings: list[Mapping],
    models_index: dict[tuple[str, str], RawModel],
    canonical_models: list[CanonicalModel],
    adapters: dict[str, ProviderAdapter],
    cfg: Config,
) -> ScoreResult:
    canonical_by_slug = {c.slug: c for c in canonical_models}
    deployments, excluded = _build_deployments(
        mappings, models_index, canonical_by_slug, adapters, cfg
    )

    # 1. Pareto: frontier = primary, dominated = backup.
    frontier = pareto_survivors(deployments)
    for d in deployments:
        d.pareto_frontier = d.canonical_slug in frontier
    dominators = dominator_map(deployments)

    # 2. SOTA-relative floors (minimums -> multi-tier eligibility).
    sota = sota_intelligence(deployments)
    floors = absolute_floors(cfg.nmb.tier_floors, sota)
    tier_order = list(cfg.nmb.tier_floors.keys())
    top_k = cfg.nmb.top_k_per_tier
    mu = cfg.nmb.latency_penalty_mu

    cost_methods: dict[str, int] = {}
    tiers: list[ScoredTier] = []
    for tier_name in tier_order:
        lam = cfg.nmb.tier_lambdas[tier_name]
        model_group = cfg.litellm.tier_model_groups[tier_name]

        # Copy per tier: a model can belong to several tiers, and each tier sets
        # its own order / model_group / payload on its own Deployment copy.
        eligible = [
            dataclasses.replace(d)
            for d in deployments
            if tier_name in eligible_tiers(d.intelligence, floors, tier_order)
        ]
        primary = [d for d in eligible if d.canonical_slug in frontier]
        backup = [d for d in eligible if d.canonical_slug not in frontier]
        pool_size = len({d.canonical_slug for d in eligible})

        ranking, selected, backup_count = _select_and_rank(primary, backup, lam, mu, top_k)

        for d in selected:
            d.tier = tier_name
            d.model_group = model_group
            payload = adapters[d.provider].to_litellm_deployment(
                _raw_for(d), d.provider_pricing, model_group, d.order
            )
            d.litellm_params = payload
            d.api_base = payload["litellm_params"]["api_base"]
            cost_methods[d.cost_method] = cost_methods.get(d.cost_method, 0) + 1

        tiers.append(
            ScoredTier(
                name=tier_name,
                model_group=model_group,
                floor_intelligence=floors[tier_name],
                floor_frac=cfg.nmb.tier_floors[tier_name],
                lam=lam,
                pool_size=pool_size,
                backup_count=backup_count,
                deployments=selected,
                ranking=ranking,
            )
        )

    all_slugs = {d.canonical_slug for d in deployments}
    kept = len(frontier & all_slugs)
    return ScoreResult(
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        sota_intelligence=sota,
        tiers=tiers,
        excluded=excluded,
        parameters={
            "tier_floors": cfg.nmb.tier_floors,
            "tier_lambdas": cfg.nmb.tier_lambdas,
            "latency_penalty_mu": mu,
            "top_k_per_tier": top_k,
            "task_profile": {
                "cache_hit_rate": cfg.task_profile.cache_hit_rate,
                "input_output_ratio": cfg.task_profile.input_output_ratio,
                "requests_per_task": cfg.task_profile.requests_per_task,
            },
        },
        cost_methods=cost_methods,
        pareto_kept=kept,
        pareto_dropped=len(all_slugs) - kept,
        dominators=dominators,
    )
