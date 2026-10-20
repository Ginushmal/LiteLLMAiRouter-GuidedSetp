"""Name normalization and exact matching.

``normalize_key`` produces a comparison key by dropping provider prefixes,
parentheticals, dates, and configured noise suffixes, then reducing to
lowercase alphanumerics. ``CanonicalIndex`` maps those keys to canonical
models so exact matches resolve without a classifier call.
"""

from __future__ import annotations

import re

from model_pipeline.models import CanonicalModel
from model_pipeline.textutil import normkey

_PAREN_RE = re.compile(r"\([^)]*\)")
_DATE_RE = re.compile(r"\b20\d{2}[-.]?\d{2}[-.]?\d{2}\b")


def normalize_key(name: str, strip_suffixes: list[str] | None = None) -> str:
    s = (name or "").lower()
    s = _PAREN_RE.sub(" ", s)  # drop "(latest)", "(max)", "(high)", ...
    if "/" in s:  # drop provider prefix (e.g. "openai/xiaomi/mimo" -> "mimo")
        s = s.split("/")[-1]
    s = _DATE_RE.sub(" ", s)
    for suffix in strip_suffixes or []:
        s = s.replace(suffix.lower(), " ")
    return normkey(s)


class CanonicalIndex:
    """Lookup from normalized key to canonical model.

    AA lists multiple effort variants per base model (e.g. claude-sonnet-5-5,
    claude-sonnet-5-5-medium, ...). Display names drop their parenthetical
    effort and so collide; slugs stay unique. Exact match therefore prefers a
    slug hit, and falls back to a display-name hit only when it is unambiguous.

    A trailing serving token (`-fast`, `-highspeed`, ...) does not change a
    model's identity, so it is retried with the token stripped — but only after
    the full name fails, so a distinct entry like ``grok-4-fast`` wins first.
    """

    def __init__(
        self,
        models: list[CanonicalModel],
        strip_suffixes: list[str],
        speed_suffixes: list[str] | None = None,
    ):
        self.strip_suffixes = strip_suffixes
        self.speed_suffixes = tuple(speed_suffixes or ())
        self.by_slug: dict[str, CanonicalModel] = {}
        self.by_name: dict[str, list[CanonicalModel]] = {}
        for m in models:
            if m.slug:
                self.by_slug.setdefault(normalize_key(m.slug, strip_suffixes), m)
            if m.name:
                self.by_name.setdefault(normalize_key(m.name, strip_suffixes), []).append(m)

    def _lookup(self, name: str) -> CanonicalModel | None:
        key = normalize_key(name, self.strip_suffixes)
        if not key:
            return None
        if key in self.by_slug:
            return self.by_slug[key]
        candidates = self.by_name.get(key, [])
        if len(candidates) == 1:
            return candidates[0]
        return None  # ambiguous (or absent) -> let the classifier decide

    def exact(self, provider_name: str) -> CanonicalModel | None:
        # Full-name match first: a canonical that owns a serving token
        # (e.g. "grok-4-fast") must not be collapsed into the base.
        hit = self._lookup(provider_name)
        if hit is not None:
            return hit
        lowered = (provider_name or "").lower()
        for suffix in self.speed_suffixes:
            token = suffix.lower().strip()
            if token and lowered.endswith(token):
                return self._lookup(provider_name[: -len(token)])
        return None
