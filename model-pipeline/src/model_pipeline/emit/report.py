"""Ranking explainability report (``output/tier-ranking.md``).

Unlike ``tier-output.json`` (the machine artifact), this explains the ranking
in plain language: every scored model, the tiers it was eligible for, the tiers
it was selected in, the full per-tier NMB ranking (with the cut line), and a
Pareto table naming what dominates each dominated model. It exists so a user can
answer "why isn't model X in tier Y?" without reading code.
"""

from __future__ import annotations

from pathlib import Path

from model_pipeline.config import Config
from model_pipeline.scoring.pipeline import ScoreResult


def _money(value: float | None) -> str:
    return "—" if value is None else f"${value:.4f}"


def _canon_index(result: ScoreResult) -> dict[str, dict]:
    """slug -> {name, intel, cost(best), frontier, eligible[], selected[]}."""
    index: dict[str, dict] = {}
    for tier in result.tiers:
        for row in tier.ranking:
            entry = index.get(row.canonical_slug)
            if entry is None:
                entry = {
                    "name": row.display_name,
                    "intel": row.intelligence,
                    "cost": row.cost_per_task,
                    "frontier": row.on_frontier,
                    "eligible": [],
                    "selected": [],
                }
                index[row.canonical_slug] = entry
            if row.cost_per_task < entry["cost"]:
                entry["cost"] = row.cost_per_task
            if tier.name not in entry["eligible"]:
                entry["eligible"].append(tier.name)
    for tier in result.tiers:
        for dep in tier.deployments:
            entry = index.get(dep.canonical_slug)
            if entry is not None and tier.name not in entry["selected"]:
                entry["selected"].append(tier.name)
    return index


def build_report(result: ScoreResult, cfg: Config) -> str:
    top_k = result.parameters["top_k_per_tier"]
    mu = result.parameters["latency_penalty_mu"]
    index = _canon_index(result)
    lines: list[str] = []

    lines.append("# Model pipeline — ranking report\n")
    lines.append(f"_Generated: {result.generated_at}_\n")
    lines.append(f"**SOTA intelligence:** {result.sota_intelligence}\n")
    lines.append(f"**NMB** = lambda * intelligence - cost_per_task - mu * latency   (mu = {mu})\n")
    lines.append("A model is eligible for **every** tier whose floor it meets:\n")
    lines.append("| Tier | Model group | Floor (x SOTA) | lambda | top-K |")
    lines.append("|------|-------------|----------------|--------|-------|")
    for tier in result.tiers:
        lines.append(
            f"| {tier.name} | `{tier.model_group}` | "
            f"{tier.floor_intelligence:.2f} ({tier.floor_frac:.2f}x) | {tier.lam} | {top_k} |"
        )

    lines.append("\n## Model index\n")
    lines.append("Every scored model, where it was eligible, and where it was selected.\n")
    lines.append("| Model | Intel | Best cost/task | Pareto | Eligible tiers | Selected in |")
    lines.append("|-------|------:|---------------:|--------|----------------|-------------|")
    for _slug, row in sorted(index.items(), key=lambda kv: -kv[1]["intel"]):
        lines.append(
            f"| {row['name']} | {row['intel']} | {_money(row['cost'])} | "
            f"{'frontier' if row['frontier'] else 'dominated'} | "
            f"{', '.join(row['eligible']) or '—'} | {', '.join(row['selected']) or '—'} |"
        )

    for tier in result.tiers:
        lines.append(f"\n## {tier.name}  ->  `{tier.model_group}`\n")
        lines.append(
            f"_lambda {tier.lam}, floor {tier.floor_intelligence:.2f}, top-K {top_k} — "
            f"{tier.pool_size} eligible models; {tier.backup_count} backup fill(s)._\n"
        )
        lines.append(
            "Ranked by NMB — frontier (primary) candidates first, then dominated "
            "(backup) candidates. Rows past the top-K are **cut**.\n"
        )
        lines.append("| # | Model | Provider(s) | Intel | Cost/task | NMB | Pareto | Result |")
        lines.append("|--:|-------|-------------|------:|----------:|----:|--------|--------|")
        if not tier.ranking:
            lines.append("| | _no eligible models_ | | | | | | |")
        for row in tier.ranking:
            result_txt = "cut" if row.status == "cut" else f"{row.status} · order {row.order}"
            lines.append(
                f"| {row.order or '—'} | {row.display_name} | {', '.join(row.providers)} | "
                f"{row.intelligence} | {_money(row.cost_per_task)} | {row.nmb:.2f} | "
                f"{'frontier' if row.on_frontier else 'dominated'} | {result_txt} |"
            )

    lines.append("\n## Pareto frontier\n")
    lines.append(
        f"**{result.pareto_kept}** efficient models on the frontier; "
        f"**{result.pareto_dropped}** dominated (another model is both smarter and cheaper).\n"
    )
    if result.dominators:
        lines.append("Dominated models — and a model that beats them on both axes:\n")
        lines.append("| Model | Intel | Cost/task | Beaten by | Its intel | Its cost |")
        lines.append("|-------|------:|----------:|-----------|----------:|---------:|")
        for slug, (dom, dom_intel, dom_cost) in sorted(
            result.dominators.items(), key=lambda kv: -index.get(kv[0], {}).get("intel", 0)
        ):
            me = index.get(slug, {})
            dom_name = index.get(dom, {}).get("name", dom)
            lines.append(
                f"| {me.get('name', slug)} | {me.get('intel')} | {_money(me.get('cost'))} | "
                f"{dom_name} | {dom_intel} | {_money(dom_cost)} |"
            )

    if result.excluded:
        lines.append("\n## Excluded (could not be scored)\n")
        for reason, items in result.excluded.items():
            shown = ", ".join(items[:20]) + (" …" if len(items) > 20 else "")
            lines.append(f"**{reason}** ({len(items)}): {shown}\n")

    return "\n".join(lines) + "\n"


def write_report(path: Path, result: ScoreResult, cfg: Config) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_report(result, cfg), encoding="utf-8")
