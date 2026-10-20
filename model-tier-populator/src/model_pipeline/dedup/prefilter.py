"""Candidate shortlisting before the Jev call.

Jev's Choice question accepts up to 255 options but AA has hundreds of models.
We shortlist purely by name similarity — no variant-based exclusion — and let
Jev pick among a relevant set (plus an "unmapped" option).

Casting a wide, name-only net keeps the correct candidate in Jev's options,
including AA entries whose display names carry an effort parenthetical (e.g.
"Claude Haiku 4.5 (Max, Default Fallback)"), which a strict variant filter used
to drop before Jev ever saw them.
"""

from __future__ import annotations

from rapidfuzz import fuzz

from model_pipeline.dedup.normalize import normalize_key
from model_pipeline.models import CanonicalModel


def shortlist(
    provider_name: str,
    canonical_models: list[CanonicalModel],
    size: int,
    strip_suffixes: list[str],
) -> list[CanonicalModel]:
    pkey = normalize_key(provider_name, strip_suffixes)

    scored: list[tuple[float, CanonicalModel]] = []
    exact_slug: str | None = None
    for cm in canonical_models:
        ckey = normalize_key(cm.slug or cm.name, strip_suffixes)
        if ckey == pkey and exact_slug is None:
            exact_slug = cm.slug
        scored.append((fuzz.token_set_ratio(pkey, ckey), cm))

    scored.sort(key=lambda t: (-t[0], t[1].slug))
    top = [cm for _, cm in scored[:size]]

    # Never let the obvious candidate (an exact normalized-slug match) be lost
    # to ranking noise: swap it in for the weakest entry if it is missing.
    if exact_slug is not None and all(cm.slug != exact_slug for cm in top):
        exact_cm = next(cm for _, cm in scored if cm.slug == exact_slug)
        if top:
            top[-1] = exact_cm
        else:
            top.append(exact_cm)
    return top
