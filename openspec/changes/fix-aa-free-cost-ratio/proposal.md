# Proposal

## Why

The `aa_free` cost strategy double-discounts caching. AA's published `cost_per_task` already includes its measured cache-hit savings (verified against AA's methodology and Intelligence Index pages), but the pipeline inverts that cost into token counts **as if all input were billed at full price**, then re-prices those tokens with the configured `cache_hit_rate` (0.98) applied on top. With provider prices identical to AA's, the result should equal AA's cost exactly — instead Kimi K3.1 Pro comes out at $2.24 vs AA's $3.68 (61%) and Qwen4 Max at $1.53 vs $3.27 (47%), verified against the 2026-11-18 artifacts. The understatement is larger for models with deeper cache discounts, so it also biases NMB ranking and tier picks toward deep-cache providers.

## What Changes

- Replace the token-count inversion in the `aa_free` strategy (`scoring/cost.py::_strategy_b`) with a **blended-price ratio**: `cost = aa_cost_per_task × blend(provider prices) / blend(AA prices)`, where `blend = (1−h)·input + h·cache_read + output/R` uses the same configured cache hit rate `h` and input:output ratio `R` on both sides.
- **Invariant**: when provider prices equal AA's, the computed cost equals AA's `cost_per_task` exactly; provider price differences (including cache-read differences) are the only thing that moves the number.
- Missing-price fallback semantics stay: a component the provider omits uses AA's price for that component (provenance `aa_fallback`), which makes that component's ratio contribution 1.0.
- Keep strategies A (`aa_pro`, real token counts) and C (`task_profile`) unchanged; strategy selection is unchanged.
- Fix the misleading `config.yaml` / `config.example.yaml` comments: `cache_hit_rate` and `input_output_ratio` weight how provider-vs-AA price differences translate into cost; they no longer describe a token derivation that ignores them.
- Document the known free-tier limitation in the learnings doc: AA free tier exposes no cache-write token data, so cache-*write* price differences remain unpriced on this path (only the fixed-profile fallback charges writes); AA Pro token counts (strategy A) supersede this path when available.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `model-pipeline`: the "Cost-per-task computation" requirement's **AA free tier** scenario changes from "back out effective token counts … re-price with cache adjustment" to the blended-price-ratio re-pricing, with an explicit same-prices-same-cost invariant scenario. All other scenarios of that requirement are unchanged.

## Impact

- **Code**: `model-tier-populator/src/model_pipeline/scoring/cost.py` (`_strategy_b` only); `model-tier-populator/tests/test_scoring.py` (new invariant + ratio tests); `config.yaml` / `config.example.yaml` comments.
- **Behavior**: `aa_free` costs rise to AA-consistent levels (Kimi ≈ $3.68, Qwen ≈ $3.27 at identical prices). Cost-per-task, NMB scores, Pareto state, and tier selections change on the next `score` run — expected, this is the correction.
- **Data**: `tier-output.json` / reports must be regenerated via `score` (no re-fetch needed); populate re-run afterwards converges LiteLLM (prices themselves are unchanged — only ranking/cost fields).
- **Docs**: `.docs/LiteLLM-Learnings.md` pitfall entry for the double-discount; ROADMAP tick.
- **No interface changes**: `cost_per_task()` signature, `CostResult`, method name `aa_free`, and downstream consumers untouched.