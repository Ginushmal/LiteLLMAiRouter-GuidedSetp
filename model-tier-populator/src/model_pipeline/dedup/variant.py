"""Variant signals.

A canonical identity is (base model, variant): the parameter count and the effort
level can differ between otherwise same-named models ("qwen3-4b" vs "qwen3-26b",
"mimo-2.6" vs "mimo-2.6-high").

This module only *parses* those signals, to decorate option text. Variant
disambiguation is delegated to the Jev classifier (via its instructions and
option descriptions) rather than a programmatic filter, which would drop correct
candidates whose AA display names carry an effort parenthetical.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_PARAM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[bB]\b")
_DATE_RE = re.compile(r"\b(20\d{2})[-]?(\d{2})[-]?(\d{2})\b")


@dataclass(frozen=True)
class Variant:
    params: str | None = None
    effort: str | None = None

    def is_empty(self) -> bool:
        return not self.params and not self.effort

    def label(self) -> str:
        parts = [p for p in (self.params, self.effort) if p]
        return "+".join(parts)


def parse_variant(name: str, effort_tokens: list[str]) -> Variant:
    lowered = (name or "").lower()
    # Strip dates first so a version like 2024-08-06 is not read as a param count.
    without_dates = _DATE_RE.sub(" ", lowered)

    params: str | None = None
    # Prefer the FIRST parameter token (models usually lead with size, e.g. "20B").
    m = _PARAM_RE.search(without_dates)
    if m:
        params = f"{m.group(1)}b"

    effort: str | None = None
    for token in effort_tokens:
        if re.search(rf"(?<![a-z0-9]){re.escape(token.lower())}(?![a-z0-9])", lowered):
            # "highspeed" contains "high"; prefer the longest matching token.
            if effort is None or len(token) > len(effort):
                effort = token.lower()
    return Variant(params=params, effort=effort)
