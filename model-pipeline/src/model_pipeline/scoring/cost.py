"""Cost-per-task computation.

Converts provider per-token prices into the dollar cost of one representative
task, capturing:
  * model efficiency  - from AA's benchmark (a smarter model used fewer tokens),
  * cache effects     - a configurable share of input tokens are cache reads,
  * provider pricing  - the specific provider's per-token rates.

Three strategies, picked by data availability:
  A. AA Pro per-token re-price   (needs AA per-task token counts)
  B. AA free effective-token     (default: backs out token counts from AA cost)
  C. Fixed task profile          (fallback when AA has nothing for the model)

Missing provider price components fall back to AA's price for that component,
and the artifact records which values are provider vs fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from model_pipeline.config import TaskProfile
from model_pipeline.models import CanonicalModel, ResolvedPricing

_MILLION = 1_000_000.0


@dataclass
class EffectivePrices:
    input: Optional[float] = None
    output: Optional[float] = None
    cache_read: Optional[float] = None
    cache_write: Optional[float] = None
    provenance: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "input": self.input,
            "output": self.output,
            "cache_read": self.cache_read,
            "cache_write": self.cache_write,
            "provenance": self.provenance,
        }


@dataclass
class CostResult:
    cost_per_task: float
    method: str  # "aa_pro" | "aa_free" | "task_profile"
    prices: EffectivePrices
    notes: list[str] = field(default_factory=list)


def effective_prices(
    pricing: ResolvedPricing, canonical: CanonicalModel
) -> EffectivePrices:
    """Provider prices, with AA used for any component the provider omits."""
    provenance: dict[str, str] = {}

    def pick(component: str, aa_value: Optional[float]) -> Optional[float]:
        value = getattr(pricing, component)
        if value is None and aa_value is not None:
            provenance[component] = "aa_fallback"
            return aa_value
        if value is not None:
            provenance[component] = "provider"
        return value

    return EffectivePrices(
        input=pick("input", canonical.aa_input),
        output=pick("output", canonical.aa_output),
        cache_read=pick("cache_read", canonical.aa_cache_read),
        cache_write=pick("cache_write", canonical.aa_cache_write),
        provenance=provenance,
    )


def cost_per_task(
    pricing: ResolvedPricing, canonical: CanonicalModel, tp: TaskProfile
) -> CostResult:
    prices = effective_prices(pricing, canonical)
    if canonical.aa_token_counts:
        return _strategy_a(prices, canonical, tp)
    if (
        canonical.aa_cost_per_task is not None
        and canonical.aa_input is not None
        and canonical.aa_output is not None
    ):
        return _strategy_b(prices, canonical, tp)
    return _strategy_c(prices, tp)


def _cost_of(prices: EffectivePrices, tp: TaskProfile, tokens: dict[str, float]) -> float:
    """Blend token counts with effective per-token prices (all in dollars/token)."""
    p_in = (prices.input or 0.0) / _MILLION
    p_out = (prices.output or 0.0) / _MILLION
    p_cache_read = (
        prices.cache_read if prices.cache_read is not None else prices.input or 0.0
    ) / _MILLION
    p_cache_write = (
        prices.cache_write if prices.cache_write is not None else prices.input or 0.0
    ) / _MILLION
    p_reasoning = p_out * (tp.reasoning_price_multiplier or 1.0)

    return (
        tokens.get("input", 0.0) * p_in
        + tokens.get("cached", 0.0) * p_cache_read
        + tokens.get("output", 0.0) * p_out
        + tokens.get("reasoning", 0.0) * p_reasoning
        + tokens.get("cache_write", 0.0) * p_cache_write
    )


def _split_input(total_input: float, cache_hit_rate: float) -> tuple[float, float]:
    cached = total_input * cache_hit_rate
    return total_input - cached, cached


def _strategy_a(
    prices: EffectivePrices, canonical: CanonicalModel, tp: TaskProfile
) -> CostResult:
    counts = canonical.aa_token_counts or {}
    total_input = counts.get("input_tokens", 0.0)
    fresh, cached = _split_input(total_input, tp.cache_hit_rate)
    tokens = {
        "input": fresh,
        "cached": cached,
        "output": counts.get("answer_tokens", 0.0),
        "reasoning": counts.get("reasoning_tokens", 0.0),
    }
    return CostResult(
        cost_per_task=_cost_of(prices, tp, tokens),
        method="aa_pro",
        prices=prices,
        notes=["AA Pro per-task token counts re-priced at provider rates"],
    )


def _strategy_b(
    prices: EffectivePrices, canonical: CanonicalModel, tp: TaskProfile
) -> CostResult:
    p_in_aa = (canonical.aa_input or 0.0) / _MILLION
    p_out_aa = (canonical.aa_output or 0.0) / _MILLION
    ratio = tp.input_output_ratio or 4.0
    denominator = p_in_aa + p_out_aa / ratio
    if denominator <= 0:
        return _strategy_c(prices, tp)
    total_input = (canonical.aa_cost_per_task or 0.0) / denominator
    total_output = total_input / ratio
    fresh, cached = _split_input(total_input, tp.cache_hit_rate)
    tokens = {"input": fresh, "cached": cached, "output": total_output}
    return CostResult(
        cost_per_task=_cost_of(prices, tp, tokens),
        method="aa_free",
        prices=prices,
        notes=[
            "AA free-tier cost_per_task decomposed into effective tokens "
            f"(input:output {ratio:g}:1), re-priced with cache_hit_rate {tp.cache_hit_rate:g}"
        ],
    )


def _strategy_c(prices: EffectivePrices, tp: TaskProfile) -> CostResult:
    n = tp.requests_per_task
    tokens = {
        "input": tp.input * n,
        "cached": tp.cached * n,
        "output": tp.output * n,
        "reasoning": tp.reasoning * n,
        "cache_write": tp.cache_write * n,
    }
    return CostResult(
        cost_per_task=_cost_of(prices, tp, tokens),
        method="task_profile",
        prices=prices,
        notes=["No AA data; fixed task profile applied at provider rates"],
    )
