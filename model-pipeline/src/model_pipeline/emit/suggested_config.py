"""Derive a suggested task profile from provider-published request estimates.

Both providers publish a typical agentic request shape (fresh input, cached
input, output). We average them and suggest:
  * cache_hit_rate = cached / (fresh + cached)
  * input_output_ratio = (fresh + cached) / output

The result is written to output/suggested_config.yaml for a human to review;
it is never applied automatically.
"""

from __future__ import annotations

import re

import yaml

_ESTIMATE_RE = re.compile(
    r"([\d,]+)\s*(?:fresh\s+)?input[,;]?\s*"
    r"([\d,]+)\s*(?:cache-read|cache hits|cached)[^0-9]*?[,;]?\s*"
    r"(?:and\s+)?([\d,]+)\s*output",
    re.IGNORECASE,
)
_ROUGH_RE = re.compile(
    r"~?([\d,]+)\s*fresh input tokens?,\s*~?([\d,]+)\s*cache-read tokens?,[^0-9]*?"
    r"([\d,]+)(?:\s*-\s*([\d,]+))?\s*output tokens?",
    re.IGNORECASE,
)


def _num(s: str) -> int:
    return int(s.replace(",", ""))


def extract_estimates(html: str) -> list[tuple[int, int, int]]:
    estimates: list[tuple[int, int, int]] = []
    for m in _ESTIMATE_RE.finditer(html or ""):
        try:
            estimates.append((_num(m.group(1)), _num(m.group(2)), _num(m.group(3))))
        except ValueError:
            continue
    for m in _ROUGH_RE.finditer(html or ""):
        try:
            out = _num(m.group(4)) if m.group(4) else _num(m.group(3))
            estimates.append((_num(m.group(1)), _num(m.group(2)), out))
        except ValueError:
            continue
    return estimates


def build_suggested(htmls: list[str], current_cache_hit_rate: float, current_ratio: float) -> dict:
    estimates: list[tuple[int, int, int]] = []
    for html in htmls:
        estimates.extend(extract_estimates(html))
    if not estimates:
        return {
            "note": "No provider per-request estimates found; current config values kept.",
            "task_profile": {
                "cache_hit_rate": current_cache_hit_rate,
                "input_output_ratio": current_ratio,
            },
        }
    avg_in = sum(e[0] for e in estimates) / len(estimates)
    avg_cached = sum(e[1] for e in estimates) / len(estimates)
    avg_out = sum(e[2] for e in estimates) / len(estimates) or 1.0
    return {
        "note": (
            "Derived from provider-published per-request estimates "
            f"({len(estimates)} samples). Review before copying into config.yaml."
        ),
        "samples": [{"fresh_input": a, "cached_input": b, "output": c} for a, b, c in estimates],
        "task_profile": {
            "per_request": {
                "input": round(avg_in),
                "cached": round(avg_cached),
                "output": round(avg_out),
            },
            "cache_hit_rate": round(avg_cached / (avg_in + avg_cached), 4) if (avg_in + avg_cached) else current_cache_hit_rate,
            "input_output_ratio": round((avg_in + avg_cached) / avg_out, 3),
        },
    }


def dump_suggested(path, suggested: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Suggested task-profile values derived from provider docs.\n"
        "# Review and copy into config.yaml if they differ from your workload.\n"
        "# This file is advisory only; the pipeline never applies it automatically.\n\n"
    )
    path.write_text(header + yaml.safe_dump(suggested, sort_keys=False), encoding="utf-8")
