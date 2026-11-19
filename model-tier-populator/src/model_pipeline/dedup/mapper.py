"""Dedup orchestration: provider model name -> canonical identity."""

from __future__ import annotations

import sys

from model_pipeline.config import Config
from model_pipeline.dedup.jev import JevClient
from model_pipeline.dedup.normalize import CanonicalIndex
from model_pipeline.dedup.prefilter import shortlist
from model_pipeline.dedup.variant import parse_variant
from model_pipeline.models import CanonicalModel, Mapping, RawModel

_MATCH_INSTRUCTIONS = (
    "Which canonical model does this provider model name refer to? Match the "
    "EXACT model. "
    # A class/tier token names a DIFFERENT model, not a variant of one. This
    # used to be absent, so a cheap flash sibling was mapped onto the measured
    # pro model and silently inherited its intelligence score.
    "A class or tier token is part of a model's identity, never decoration: "
    "flash, lite, mini, nano, micro, air, pro, max, ultra, plus, turbo, "
    "small, medium, large, thinking, reasoning, instruct. "
    "Never merge across a class token in either direction: a flash model is "
    "NOT its pro/max sibling (tencent-hy4-flash is not tencent-hy4), and a "
    "pro model is NOT its flash/lite sibling. The chosen option must carry "
    "the same class token as the provider name; if no option carries it, "
    "choose 'unmapped' instead of the nearest model. "
    "Also never merge different parameter sizes (qwen3-4b is not qwen3-26b) "
    "or different effort levels (mimo-2.6 is not mimo-2.6-high). "
    # The old wording licensed the bug: it let any bare name fall back to the
    # base model, which is exactly the direction that crosses class boundaries.
    "Only a name with NO class token of its own may map to the base/default "
    "variant, and only when that action does not add or drop a class token. "
    "A serving token (fast/highspeed/ultraspeed/turbo/prime) means the same "
    "model served faster - it never justifies crossing a class boundary. "
    # Make "unmapped" a first-class answer so an unmeasured sibling does not
    # borrow a measured one's score.
    "'unmapped' is a correct and preferred answer. A model that does not "
    "exist in the options must stay unmapped: inheriting a sibling's "
    "intelligence score is worse than having none."
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

        # 0. Configured provider override (takes precedence over exact and Jev).
        providers_dict = getattr(cfg, "providers", {}) or {}
        pcfg = providers_dict.get(m.provider)
        override_slug = None
        if pcfg:
            model_mappings = getattr(pcfg, "model_mappings", {}) or {}
            override_slug = (
                model_mappings.get(m.model_id)
                or model_mappings.get(m.model_id.strip())
                or model_mappings.get(m.display_name)
            )

        if override_slug:
            clean_slug = override_slug.strip()
            target_canonical = by_slug.get(clean_slug)
            if target_canonical is None:
                print(
                    f"warning: providers.{m.provider}.model_mappings: target slug {override_slug!r} "
                    f"for {m.model_id!r} not found in canonical models; leaving unmapped",
                    file=sys.stderr,
                )
                mappings.append(
                    Mapping(
                        provider=m.provider,
                        model_id=m.model_id,
                        canonical_slug=None,
                        canonical_name=None,
                        variant=variant,
                        method="unmapped",
                        confidence=0.0,
                        probabilities={"_error": f"Unknown canonical slug: {override_slug}"},
                    )
                )
            else:
                mappings.append(
                    Mapping(
                        provider=m.provider,
                        model_id=m.model_id,
                        canonical_slug=target_canonical.slug,
                        canonical_name=target_canonical.name,
                        variant=variant,
                        method="override",
                        confidence=1.0,
                        probabilities={target_canonical.slug: 1.0},
                        override=target_canonical.slug,
                    )
                )
            continue

        # 1. Exact match (100% confidence, no classifier call). The provider's
        # own canonical id wins because it carries the dated/serving variant.
        hint = getattr(m, "canonical_hint", "")
        exact = (
            (index.exact(hint) if hint else None)
            or index.exact(m.display_name)
            or index.exact(m.model_id)
        )
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
