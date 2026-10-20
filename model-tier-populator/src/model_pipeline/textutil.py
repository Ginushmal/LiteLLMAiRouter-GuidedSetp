"""Small text/HTML helpers shared across the pipeline."""

from __future__ import annotations

import re
from typing import Optional

_TAG_RE = re.compile(r"<[^>]+>")


def normkey(s: str) -> str:
    """Normalize a model name to a comparison key (lowercase, alphanumeric).

    "GLM-5.3-Flash" -> "glm53flash"; "glm-5.3-flash" -> "glm53flash".
    """
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def strip_tags(html: str) -> str:
    text = _TAG_RE.sub(" ", html or "")
    return unescape(text)


def unescape(s: str) -> str:
    return (
        (s or "")
        .replace("&amp;", "&")
        .replace("&#x27;", "'")
        .replace("&#39;", "'")
        .replace("&nbsp;", " ")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&le;", "\u2264")
        .replace("&ge;", "\u2265")
    )


def clean_text(html: str) -> str:
    """Strip tags/entities and collapse whitespace."""
    return re.sub(r"\s+", " ", strip_tags(html)).strip()


def parse_money(cell: str) -> Optional[float]:
    """Parse a dollar price from a cell. Handles "$0.80 $0.14" (list then
    effective) and "Free". Returns the effective (last) price, 0.0 for free,
    or None when absent/dash.
    """
    text = cell.strip()
    if not text or text in {"-", "\u2014", "\u2013"}:
        return None
    if "free" in text.lower():
        return 0.0
    # Only match dollar-prefixed numbers so plan suffixes ("+ 1") are ignored.
    prices = re.findall(r"\$\s*(\d+(?:\.\d+)?)", text)
    if not prices:
        return None
    return float(prices[-1])
