"""Dedup orchestration: provider model name -> canonical identity."""

from __future__ import annotations

from model_pipeline.config import Config
from model_pipeline.dedup.jev import JevClient
from model_pipeline.dedup.normalize import CanonicalIndex
from model_pipeline.dedup.prefilter import shortlist
from model_pipeline.dedup.variant import parse_variant
from model_pipeline.models import CanonicalModel, Mapping, RawModel

_MATCH_INSTRUCTIONS = (
    "Which canonical model does this provider model name refer to? Match the "
    "EXACT model and its exact variant. Do NOT merge variants: different "
    "parameter sizes (qwen3-4b is not qwen3-26b) and different effort/thinking "
    "levels (mimo-2.6 is not mimo-2.6-high) are different models. A bare "
    "provider name maps to the base/default variant, never to a low/high "
    "sub-variant unless the provider name says so. A serving token "
    "(fast/highspeed/ultraspeed/turbo) on an otherwise-identical name is the "
    "SAME model served faster — choose the base model unless the options "
    "contain a distinct entry for that exact serving variant. If none match "
    "exactly, choose 'unmapped'."
)


def _option_text(cm: CanonicalModel, effort_tokens: list[str]) -> str:
    """Option description carrying the canonical's variant, so Jev can disambiguate."""
    variant = parse_variant(cm.name or cm.slug, effort_tokens).label()
    label = f" [{variant}]" if variant else ""
    return f"{cm.name}{label} by {cm.creator}"


def map_models(
    models: list[RawModel],
    canonical_models: list[CanonicalModel],
    cfg: Config,
    jev: JevClient,
) -> list[Mapping]:
    index = CanonicalIndex(
        canonical_models, cfg.dedup.strip_suffixes, cfg.dedup.speed_suffixes
    )
    by_slug = {cm.slug: cm for cm in canonical_models}
    mappings: list[Mapping] = []

    for m in models:
        variant = parse_variant(m.display_name, cfg.dedup.effort_tokens).label()

        # 1. Exact match (100% confidence, no classifier call).
        exact = index.exact(m.display_name) or index.exact(m.model_id)
        if exact is not None:
            mappings.append(
                Mapping(
                    provider=m.provider,
                    model_id=m.model_id,
                    canonical_slug=exact.slug,
                    canonical_name=exact.name,
                    variant=variant,
                    method="exact",
                    confidence=1.0,
                    probabilities={exact.slug: 1.0},
                )
            )
            continue

        # 2. Jev choice over a shortlist.
        candidates = shortlist(
            m.display_name,
            canonical_models,
            cfg.jev.candidate_shortlist_size,
            cfg.dedup.strip_suffixes,
        )
        if not candidates:
            mappings.append(
                Mapping(
                    provider=m.provider,
                    model_id=m.model_id,
                    canonical_slug=None,
                    canonical_name=None,
                    variant=variant,
                    method="unmapped",
                    confidence=0.0,
                )
            )
            continue

        criteria = {
            cm.slug: _option_text(cm, cfg.dedup.effort_tokens) for cm in candidates
        }
        criteria["unmapped"] = "No matching model in the canonical list"
        try:
            answer = jev.choose(m.display_name, _MATCH_INSTRUCTIONS, criteria)
        except Exception as exc:  # a Jev failure maps nothing rather than guessing
            mappings.append(
                Mapping(
                    provider=m.provider,
                    model_id=m.model_id,
                    canonical_slug=None,
                    canonical_name=None,
                    variant=variant,
                    method="unmapped",
                    confidence=0.0,
                    probabilities={"_error": str(exc)[:120]},
                )
            )
            continue

        if answer.choice == "unmapped" or answer.choice not in by_slug:
            mappings.append(
                Mapping(
                    provider=m.provider,
                    model_id=m.model_id,
                    canonical_slug=None,
                    canonical_name=None,
                    variant=variant,
                    method="unmapped",
                    confidence=answer.confidence,
                    probabilities=answer.probabilities,
                )
            )
            continue

        cm = by_slug[answer.choice]
        mappings.append(
            Mapping(
                provider=m.provider,
                model_id=m.model_id,
                canonical_slug=cm.slug,
                canonical_name=cm.name,
                variant=variant,
                method="jev",
                confidence=answer.confidence,
                probabilities=answer.probabilities,
                low_confidence=answer.confidence < cfg.jev.review_confidence_threshold,
            )
        )
    return mappings
