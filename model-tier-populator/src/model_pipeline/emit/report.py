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
from model_pipeline.limits import (
    FLAG_OUTPUT_EQUALS_CONTEXT,
    FLAG_OUTPUT_NOT_BELOW_CONTEXT,
    FLAG_UNRESOLVED,
)
from model_pipeline.scoring.pipeline import ScoreResult


def _money(value: float | None) -> str:
    return "—" if value is None else f"${value:.4f}"


def _canon_index(result: ScoreResult) -> dict[str, dict]:
    """slug -> {name, intel, cost(best), frontier, eligible[], pinned[], excluded[], selected[]}."""
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
                    "pinned": [],
                    "excluded": [],
                    "selected": [],
                }
                index[row.canonical_slug] = entry
            if row.cost_per_task < entry["cost"]:
                entry["cost"] = row.cost_per_task
            if tier.name not in entry["eligible"]:
                entry["eligible"].append(tier.name)
    for tier in result.tiers:
        for dep in tier.deployments:
            if dep.is_pinned:
                continue
            entry = index.get(dep.canonical_slug)
            if entry is not None and tier.name not in entry["selected"]:
                entry["selected"].append(tier.name)
    # A tier-scoped exclusion can leave a model out of every ranking (it may
    # only be floor-eligible for the tier it is excluded from). Merge those so
    # the index still answers "why isn't X in tier Y?".
    for tier in result.tiers:
        for slug in tier.excluded_by_config:
            entry = index.get(slug)
            if entry is None:
                entry = {
                    "name": slug,
                    "intel": None,
                    "cost": None,
                    "frontier": None,
                    "eligible": [],
                    "pinned": [],
                    "excluded": [],
                    "selected": [],
                }
                index[slug] = entry
            if tier.name not in entry["excluded"]:
                entry["excluded"].append(tier.name)
    # Pinned models are removed from the scored pool, so they may have no
    # ranking row at all. Merge their deployment data and mark the tier.
    for tier in result.tiers:
        for dep in tier.deployments:
            if not dep.is_pinned:
                continue
            entry = index.get(dep.canonical_slug)
            if entry is None:
                entry = {
                    "name": dep.display_name,
                    "intel": dep.intelligence,
                    "cost": dep.cost_per_task,
                    "frontier": dep.pareto_frontier,
                    "eligible": [],
                    "pinned": [],
                    "excluded": [],
                    "selected": [],
                }
                index[dep.canonical_slug] = entry
            if entry["cost"] is None or dep.cost_per_task < entry["cost"]:
                entry["cost"] = dep.cost_per_task
            if tier.name not in entry["pinned"]:
                entry["pinned"].append(tier.name)
    return index


def build_report(result: ScoreResult, cfg: Config) -> str:
    top_k = result.parameters["top_k_per_tier"]
    index = _canon_index(result)
    lines: list[str] = []

    lines.append("# Model pipeline — ranking report\n")
    lines.append(f"_Generated: {result.generated_at}_\n")
    lines.append(f"**SOTA intelligence:** {result.sota_intelligence}\n")
    lines.append(
        "**NMB** = lambda * intelligence - cost_per_task - mu * latency   "
        "(mu = rho × tier NMB spread ÷ median latency — see the tier table)\n"
    )
    lines.append("A model is eligible for **every** tier whose floor it meets:\n")
    lines.append("| Tier | Model group | Floor (x SOTA) | lambda | rho | mu | top-K |")
    lines.append("|------|-------------|----------------|--------|-----|----|-------|")
    for tier in result.tiers:
        lines.append(
            f"| {tier.name} | `{tier.model_group}` | "
            f"{tier.floor_intelligence:.2f} ({tier.floor_frac:.2f}x) | {tier.lam} | "
            f"{tier.rho} | {tier.mu:.5g} | {top_k} |"
        )

    lines.append("\n## Model index\n")
    lines.append("Every scored model, where it was eligible, and where it was selected.\n")
    lines.append("| Model | Intel | Best cost/task | Pareto | Eligible tiers | Pinned in | Excluded in | Selected in |")
    lines.append("|-------|------:|---------------:|--------|----------------|-----------|-------------|-------------|")
    for _slug, row in sorted(index.items(), key=lambda kv: -(kv[1]["intel"] or 0)):
        intel_txt = "—" if row["intel"] is None else str(row["intel"])
        if row["frontier"] is None:
            pareto_txt = "—"
        else:
            pareto_txt = "frontier" if row["frontier"] else "dominated"
        lines.append(
            f"| {row['name']} | {intel_txt} | {_money(row['cost'])} | "
            f"{pareto_txt} | "
            f"{', '.join(row['eligible']) or '—'} | "
            f"{', '.join(row['pinned']) or '—'} | "
            f"{', '.join(row['excluded']) or '—'} | "
            f"{', '.join(row['selected']) or '—'} |"
        )

    for tier in result.tiers:
        lines.append(f"\n## {tier.name}  ->  `{tier.model_group}`\n")
        lines.append(
            f"_lambda {tier.lam}, rho {tier.rho} → mu {tier.mu:.5g} "
            f"(spread {tier.spread:.2f} ÷ median {tier.median_latency:.1f} s), "
            f"floor {tier.floor_intelligence:.2f}, "
            f"top-K {top_k} — {tier.pool_size} eligible scored models; "
            f"{len(tier.pinned)} pinned; {tier.backup_count} backup fill(s)._\n"
        )
        if tier.excluded_by_config:
            shown = ", ".join(sorted(tier.excluded_by_config))
            lines.append(f"_Excluded by config: {shown}._\n")
        if tier.pinned:
            lines.append(
                "\n**Pinned by config** — force-included ahead of NMB. They are "
                "removed from the scored pool, so their NMB is reference only:\n"
            )
            lines.append("| # | Model | Provider(s) | Intel | Cost/task | NMB | Pareto |")
            lines.append("|--:|-------|-------------|------:|----------:|----:|--------|")
            for order in tier.pinned.values():
                deps = [d for d in tier.deployments if d.is_pinned and d.order == order]
                if not deps:
                    continue
                best = min(deps, key=lambda d: d.cost_per_task)
                providers = ", ".join(sorted({d.provider for d in deps}))
                lines.append(
                    f"| {order} | {best.display_name} | {providers} | "
                    f"{best.intelligence} | {_money(best.cost_per_task)} | "
                    f"{best.nmb:.2f} | "
                    f"{'frontier' if best.pareto_frontier else 'dominated'} |"
                )
        lines.append(
            "\nScored models — ranked by NMB, frontier (primary) candidates first, "
            "then dominated (backup) candidates. Rows past the top-K are **cut**.\n"
        )
        lines.append(
            "| # | Model | Provider(s) | Intel | Cost/task | Latency | Penalty | NMB | Pareto | Result |"
        )
        lines.append(
            "|--:|-------|-------------|------:|----------:|--------:|--------:|----:|--------|--------|"
        )
        if not tier.ranking:
            lines.append("| | _no eligible models_ | | | | | | | | |")
        for row in tier.ranking:
            result_txt = "cut" if row.status == "cut" else f"{row.status} · order {row.order}"
            if row.latency_seconds is None:
                latency_txt, penalty_txt = "unknown", "—"
            else:
                latency_txt = f"{row.latency_seconds:.1f}s"
                penalty_txt = f"{tier.mu * row.latency_seconds:.2f}"
            lines.append(
                f"| {row.order or '—'} | {row.display_name} | {', '.join(row.providers)} | "
                f"{row.intelligence} | {_money(row.cost_per_task)} | {latency_txt} | "
                f"{penalty_txt} | {row.nmb:.2f} | "
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

    if result.pin_warnings:
        lines.append("\n## Warnings\n")
        for warning in result.pin_warnings:
            lines.append(f"- {warning}")
        lines.append("")

    lines.append("\n## Token limits\n")
    lines.append(
        "Output limits come from the models.dev catalog; input limits are "
        "`context - output` (the provider's context window stays authoritative). "
        "Nothing is invented — anything missing or suspicious is listed here.\n"
    )
    hints = {
        FLAG_UNRESOLVED: "no catalog entry published an output limit; the value is left unset",
        FLAG_OUTPUT_EQUALS_CONTEXT: (
            "catalog entry reports output == its own context window (likely copied)"
        ),
        FLAG_OUTPUT_NOT_BELOW_CONTEXT: (
            "output limit is not smaller than the provider's context window"
        ),
    }
    if not result.limit_flags:
        lines.append("Every fetched model resolved an output limit.\n")
    for flag, hint in hints.items():
        items = sorted(key for key, flags in result.limit_flags.items() if flag in flags)
        if not items:
            continue
        shown = ", ".join(items[:20]) + (" …" if len(items) > 20 else "")
        lines.append(f"**{flag}** ({len(items)}) — {hint}: {shown}\n")

    return "\n".join(lines) + "\n"


def write_report(path: Path, result: ScoreResult, cfg: Config) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_report(result, cfg), encoding="utf-8")
