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
from model_pipeline.scoring.nmb import Group, assign_orders, calibrate_mu, nmb, rank_groups
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
    mu: float = 0.0
    rho: float = 0.0
    spread: float = 0.0
    median_latency: float = 0.0
    deployments: list[Deployment] = field(default_factory=list)
    ranking: list[RankedModel] = field(default_factory=list)
    # canonical slug -> [provider:model_id] tags removed from this tier by
    # tier-scoped exclusion patterns (floor-ineligible models are not listed).
    excluded_by_config: dict[str, list[str]] = field(default_factory=dict)
    # canonical slug -> order for models force-included by `pins.tiers`.
    pinned: dict[str, int] = field(default_factory=dict)


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
    # "provider:model" -> token-limit flags, for the explainability report.
    limit_flags: dict[str, list[str]] = field(default_factory=dict)
    # Pin problems that did not stop the run (unknown/excluded/duplicate slugs).
    pin_warnings: list[str] = field(default_factory=list)

    def all_deployments(self) -> list[Deployment]:
        return [d for t in self.tiers for d in t.deployments]


def _raw_for(d: Deployment) -> RawModel:
    return RawModel(
        provider=d.provider,
        model_id=d.model_id,
        display_name=d.display_name,
        endpoint_type=d.endpoint_type,
        context_tokens=d.context_tokens,
        input_tokens=d.input_tokens,
        output_tokens=d.output_tokens,
        limits_source=d.limits_source,
        limits_flags=list(d.limits_flags),
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
                latency_seconds=canonical.latency_seconds,
                cost_per_task=cost.cost_per_task,
                cost_method=cost.method,
                context_tokens=model.context_tokens,
                input_tokens=model.input_tokens,
                output_tokens=model.output_tokens,
                limits_source=model.limits_source,
                limits_flags=list(model.limits_flags),
                effective_prices=cost.prices.as_dict(),
                provider_pricing=model.pricing,
            )
        )
    return deployments, {k: v for k, v in excluded.items() if v}


def _tier_eligible(
    deployments: list[Deployment],
    tier_name: str,
    floors: dict[str, float],
    tier_order: list[str],
    patterns: list[str],
) -> tuple[list[Deployment], dict[str, list[str]]]:
    """One tier's candidate pool: floor eligibility minus tier-scoped exclusions.

    Returns copied eligible deployments (a model can belong to several tiers and
    each tier stamps its own order / model group on its own copy) and, per
    canonical slug, the ``provider:model_id`` tags that were floor-eligible but
    excluded by configuration. A model below the floor is not a candidate at
    all, so it is never reported as excluded.
    """
    eligible: list[Deployment] = []
    excluded: dict[str, list[str]] = {}
    for d in deployments:
        if tier_name not in eligible_tiers(d.intelligence, floors, tier_order):
            continue
        if _excluded_by_config(
            [d.provider, d.model_id, d.display_name, d.canonical_slug, d.canonical_name],
            patterns,
        ):
            excluded.setdefault(d.canonical_slug, []).append(f"{d.provider}:{d.model_id}")
            continue
        eligible.append(dataclasses.replace(d))
    return eligible, excluded


def _norm_slug(value: str) -> str:
    """Canonical-slug comparison key (case-insensitive, trimmed)."""
    return value.strip().lower()


def _globally_excluded_slugs(
    mappings: list[Mapping], excluded: dict[str, list[str]]
) -> set[str]:
    """Canonical slugs whose every mapping was dropped by a global pattern."""
    tags = set(excluded.get("excluded_by_config", []))
    return {
        _norm_slug(mp.effective_slug)
        for mp in mappings
        if mp.effective_slug and f"{mp.provider}:{mp.model_id}" in tags
    }


def _resolve_pins(
    pin_slugs: list[str],
    deployments: list[Deployment],
    known_slugs: set[str],
    globally_excluded: set[str],
    tier_name: str,
    tier_patterns: list[str],
    warnings: list[str],
) -> list[tuple[str, list[Deployment]]]:
    """Resolve one tier's pins to deployments, warning instead of failing.

    Returns ``(canonical_slug, surviving_deployments)`` in configuration order.
    Pins bypass the floor by design; tier exclusion patterns still apply per
    deployment. Duplicates, unknown slugs, unscored models, and fully excluded
    pins are skipped with a warning so the run can continue.
    """
    by_slug: dict[str, list[Deployment]] = {}
    for d in deployments:
        by_slug.setdefault(_norm_slug(d.canonical_slug), []).append(d)

    resolved: list[tuple[str, list[Deployment]]] = []
    seen: set[str] = set()
    for raw in pin_slugs:
        slug = _norm_slug(raw)
        if slug in seen:
            warnings.append(
                f"pins.tiers.{tier_name}: {raw!r} is listed more than once; "
                "using the first occurrence"
            )
            continue
        seen.add(slug)

        deps = by_slug.get(slug)
        if not deps:
            if slug in globally_excluded:
                reason = "is globally excluded"
            elif slug in known_slugs:
                reason = "has no scored deployment (missing pricing/intelligence or unsupported endpoint)"
            else:
                reason = "matches no canonical model"
            warnings.append(f"pins.tiers.{tier_name}: {raw!r} {reason}; ignored")
            continue

        allowed = [
            d
            for d in deps
            if not _excluded_by_config(
                [d.provider, d.model_id, d.display_name, d.canonical_slug, d.canonical_name],
                tier_patterns,
            )
        ]
        if not allowed:
            warnings.append(
                f"pins.tiers.{tier_name}: {raw!r} is excluded from {tier_name} "
                "by exclude.tiers; ignored"
            )
            continue
        resolved.append((slug, allowed))
    return resolved


def _pinned_deployments(
    resolved: list[tuple[str, list[Deployment]]], lam: float, mu: float
) -> tuple[list[Deployment], dict[str, int]]:
    """Stamp the pinned copies with orders 1..P and the tier's calibrated NMB."""
    pins: list[Deployment] = []
    orders: dict[str, int] = {}
    for order, (slug, deps) in enumerate(resolved, start=1):
        orders[slug] = order
        for d in deps:
            pin = dataclasses.replace(d)
            pin.order = order
            pin.is_pinned = True
            pin.is_backup = False
            pin.nmb = nmb(pin.intelligence, pin.cost_per_task, pin.latency_seconds, lam, mu)
            pins.append(pin)
    return pins, orders


def _rank_row(group: Group, frontier: bool, status: str, order: int) -> RankedModel:
    first = group.members[0]
    return RankedModel(
        canonical_slug=group.canonical_slug,
        canonical_name=first.canonical_name,
        display_name=first.display_name,
        providers=sorted({m.provider for m in group.members}),
        intelligence=first.intelligence,
        latency_seconds=first.latency_seconds,
        cost_per_task=group.cost,
        nmb=group.nmb,
        on_frontier=frontier,
        status=status,
        order=order,
    )


def _select_and_rank(
    primary: list[Deployment],
    backup: list[Deployment],
    lam: float,
    mu: float,
    top_k: int,
    order_offset: int = 0,
) -> tuple[list[RankedModel], list[Deployment], int]:
    """Rank primary groups, take top-K, fill from backup, and return the full ranking.

    ``order_offset`` reserves the first N order values for pinned deployments;
    scored groups are numbered after them and their report rows match.
    """
    prim = rank_groups(primary, lam, mu)
    back = rank_groups(backup, lam, mu)
    n_primary = min(len(prim), top_k)
    selected_primary = prim[:n_primary]
    selected_backup = back[: max(0, top_k - n_primary)]
    for group in selected_backup:
        group.backup = True

    selected = assign_orders(selected_primary + selected_backup, start=order_offset + 1)

    ranking: list[RankedModel] = []
    for i, group in enumerate(prim):
        chosen = i < n_primary
        ranking.append(
            _rank_row(
                group,
                True,
                "primary" if chosen else "cut",
                order_offset + i + 1 if chosen else 0,
            )
        )
    for i, group in enumerate(back):
        chosen = i < len(selected_backup)
        ranking.append(
            _rank_row(
                group,
                False,
                "backup" if chosen else "cut",
                order_offset + n_primary + i + 1 if chosen else 0,
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
    # The configured value is a share (rho); the per-second weight (mu) is
    # derived per tier from that tier's NMB spread and median latency.
    rho_by_tier = {name: cfg.nmb.rho_for(name) for name in tier_order}

    known_slugs = {_norm_slug(c.slug) for c in canonical_models}
    globally_excluded = _globally_excluded_slugs(mappings, excluded)
    pin_warnings: list[str] = []

    cost_methods: dict[str, int] = {}
    tiers: list[ScoredTier] = []
    for tier_name in tier_order:
        lam = cfg.nmb.tier_lambdas[tier_name]
        model_group = cfg.litellm.tier_model_groups[tier_name]
        tier_patterns = cfg.exclude_tier_patterns.get(tier_name, [])

        # Copy per tier: a model can belong to several tiers, and each tier sets
        # its own order / model_group / payload on its own Deployment copy.
        # Tier-scoped exclusions run here, after cost/Pareto/SOTA, so an excluded
        # model stays fully scored and can still compete in its other tiers.
        eligible, tier_excluded = _tier_eligible(
            deployments,
            tier_name,
            floors,
            tier_order,
            tier_patterns,
        )

        # Resolve pins before selection. Calibration still uses the normal
        # floor-eligible pool (pins included), so mu and every non-pinned
        # model's NMB are exactly what they were before pinning. Pinned
        # canonicals are then removed from the selection pool only.
        resolved = _resolve_pins(
            cfg.pin_slugs.get(tier_name, []),
            deployments,
            known_slugs,
            globally_excluded,
            tier_name,
            tier_patterns,
            pin_warnings,
        )
        mu, spread, median_latency = calibrate_mu(eligible, lam, rho_by_tier[tier_name])

        pinned_slugs = {slug for slug, _ in resolved}
        eligible = [
            d for d in eligible if _norm_slug(d.canonical_slug) not in pinned_slugs
        ]

        scored_top_k = max(0, top_k - len(resolved))
        if resolved and len(resolved) >= top_k:
            pin_word = "pin" if len(resolved) == 1 else "pins"
            pin_warnings.append(
                f"pins.tiers.{tier_name}: {len(resolved)} {pin_word} configured but "
                f"top_k_per_tier={top_k}; no NMB-selected picks"
            )

        primary = [d for d in eligible if d.canonical_slug in frontier]
        backup = [d for d in eligible if d.canonical_slug not in frontier]
        pool_size = len({d.canonical_slug for d in eligible})

        ranking, selected, backup_count = _select_and_rank(
            primary, backup, lam, mu, scored_top_k, order_offset=len(resolved)
        )
        pins, pinned_orders = _pinned_deployments(resolved, lam, mu)
        selected = pins + selected

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
                mu=mu,
                rho=rho_by_tier[tier_name],
                spread=spread,
                median_latency=median_latency,
                pool_size=pool_size,
                backup_count=backup_count,
                excluded_by_config=tier_excluded,
                pinned=pinned_orders,
                deployments=selected,
                ranking=ranking,
            )
        )

    all_slugs = {d.canonical_slug for d in deployments}
    kept = len(frontier & all_slugs)
    limit_flags = {
        f"{m.provider}:{m.model_id}": list(m.limits_flags)
        for m in models_index.values()
        if m.limits_flags
    }
    return ScoreResult(
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        sota_intelligence=sota,
        tiers=tiers,
        excluded=excluded,
        parameters={
            "tier_floors": cfg.nmb.tier_floors,
            "tier_lambdas": cfg.nmb.tier_lambdas,
            "latency_rho": rho_by_tier,
            "latency_penalty_mu": {tier.name: tier.mu for tier in tiers},
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
        limit_flags=limit_flags,
        pin_warnings=pin_warnings,
    )
