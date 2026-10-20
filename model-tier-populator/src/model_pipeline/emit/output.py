"""tier-output.json + tier-output.md generation.

The JSON is self-contained: every deployment carries its full LiteLLM payload
(``litellm_params``), so `populate` can run from it alone without re-fetching or
re-scoring.
"""

from __future__ import annotations

import json
from pathlib import Path

from model_pipeline.config import Config
from model_pipeline.scoring.pipeline import ScoreResult


def build_payload(result: ScoreResult, cfg: Config) -> dict:
    return {
        "generated_at": result.generated_at,
        "sota_intelligence": result.sota_intelligence,
        "parameters": result.parameters,
        "cost_methods": result.cost_methods,
        "pareto": {
            "frontier_count": result.pareto_kept,
            "dominated_count": result.pareto_dropped,
            "note": "advisory only — dominated models are ranked, not dropped",
        },
        "excluded": result.excluded,
        "pin_warnings": result.pin_warnings,
        "limit_flags": result.limit_flags,
        "tiers": [
            {
                "name": t.name,
                "model_group": t.model_group,
                "floor_intelligence": t.floor_intelligence,
                "floor_frac": t.floor_frac,
                "lam": t.lam,
                "mu": t.mu,
                "rho": t.rho,
                "spread": t.spread,
                "median_latency": t.median_latency,
                "pool_size": t.pool_size,
                "backup_count": t.backup_count,
                "excluded_by_config": t.excluded_by_config,
                "pinned": t.pinned,
                "deployments": [d.to_dict() for d in t.deployments],
            }
            for t in result.tiers
        ],
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _latency(value: float | None) -> str:
    """Render a latency in seconds, or ``unknown`` when AA has no measurement."""
    return "unknown" if value is None else f"{value:.1f}s"


def build_markdown(payload: dict) -> str:
    lines: list[str] = []
    lines.append("# Model pipeline — tier suggestions\n")
    lines.append(f"_Generated: {payload['generated_at']}_\n")
    lines.append(f"**SOTA intelligence:** {payload['sota_intelligence']}\n")
    lines.append(
        f"**Cost methods:** "
        + ", ".join(f"{k}={v}" for k, v in payload.get("cost_methods", {}).items())
        + "\n"
    )

    for tier in payload["tiers"]:
        lines.append(f"\n## {tier['name']}  ->  `{tier['model_group']}`\n")
        lines.append(
            f"_Floor {tier['floor_intelligence']:.2f} "
            f"({tier['floor_frac']:.2f}x SOTA) · lambda {tier['lam']} · "
            f"rho {tier.get('rho')} → mu {tier.get('mu')} · "
            f"pool {tier['pool_size']} · {len(tier['deployments'])} deployments · "
            f"backups {tier.get('backup_count', 0)}_\n"
        )
        deps = tier["deployments"]
        tier_excluded = tier.get("excluded_by_config") or {}
        if tier_excluded:
            lines.append(
                f"_Excluded by config: {', '.join(sorted(tier_excluded))}._\n"
            )
        pinned = tier.get("pinned") or {}
        if pinned:
            shown = ", ".join(f"{slug} (order {order})" for slug, order in pinned.items())
            lines.append(f"_Pinned by config: {shown}._\n")
        if not deps:
            lines.append("_No qualifying models._\n")
            continue
        lines.append(
            "| # | Model | Provider | Model ID | Intel | Cost/task $ | Latency | NMB | Kind | API base |"
        )
        lines.append("|---|-------|----------|----------|-------|-------------|--------:|-----|------|----------|")
        for d in deps:
            if d.get("is_pinned"):
                kind = "pinned"
            elif d.get("is_backup"):
                kind = "backup"
            else:
                kind = "primary"
            lines.append(
                f"| {d['order']} | {d['display_name']} | {d['provider']} | `{d['model_id']}` "
                f"| {d['intelligence']} | {d['cost_per_task']:.6f} "
                f"| {_latency(d.get('latency_seconds'))} | {d['nmb']:.6f} "
                f"| {kind} | `{d['api_base']}` |"
            )
        lines.append("")

    excluded = payload.get("excluded", {})
    if excluded:
        lines.append("\n## Excluded\n")
        for reason, items in excluded.items():
            lines.append(f"**{reason}** ({len(items)}): {', '.join(items[:12])}")
            if len(items) > 12:
                lines.append(f"  … and {len(items) - 12} more")
            lines.append("")

    warnings = payload.get("pin_warnings", [])
    if warnings:
        lines.append("\n## Warnings\n")
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")

    return "\n".join(lines)


def write_markdown(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_markdown(payload), encoding="utf-8")
