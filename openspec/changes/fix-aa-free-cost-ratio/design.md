# Design

## Context

See proposal.md — Why. Facts verified in code and data:

- `scoring/cost.py::_strategy_b` computes `total_input = aa_cost / (p_in_aa + p_out_aa/R)` (no cache term), splits it with `cache_hit_rate`, and re-prices via `_cost_of`. At `h=0` this reproduces AA's cost to the cent; every increment of `h` subtracts cache savings AA already counted (AA methodology: cost per task multiplies "input, cached, and output token prices by tokens consumed"; Intelligence Index v5.0.1 adds cache-write and reasoning prices).
- AA free tier exposes only `cost_per_task.total_cost` plus input/output/cache-hit prices; token counts and the cost split are Pro-only (AA data-API reference). So token counts cannot be recovered faithfully from the free payload — any inversion is pinned by its own assumptions.
- `effective_prices()` already fills provider-missing components with AA's price and marks `aa_fallback`; `_cost_of` treats a missing `cache_read` as full input price. The ratio design must preserve both behaviors.
- Strategy selection (`cost_per_task()` dispatcher), strategy A (`aa_pro`), strategy C (`task_profile`), `CostResult`, and the method label `aa_free` are consumed by `scoring/pipeline.py` and the reports; none change.
- Existing tests: `test_strategy_b_prefers_cheaper_cache_read` (cheap vs pricey cache read must order correctly) and `test_price_provenance_marks_aa_fallback` must keep passing; `TP` uses `h=0.98`, `R=4.0`.
- Incident numbers (2026-11-18 artifacts): Kimi K3.1 Pro AA $3.6812 → ours $2.2382; Qwen4 Max AA $3.2681 → ours $1.5295. Provider prices equal AA's for both.

## Goals / Non-Goals

**Goals:**

- `aa_free` cost = AA cost × provider-blend / AA-blend, with the invariant "identical effective prices ⇒ exactly AA's cost" holding for every model and every `(h, R)`.
- Cache-read price differences remain visible and weighted by `h` (the existing cheaper-cache test keeps passing).
- Config comments describe what the knobs actually do.

**Non-Goals:**

- No change to strategies A/C, strategy selection, price scraping, provenance mechanics, NMB/tier logic, or artifact schemas.
- No attempt to model cache-write or reasoning token volumes on the free path — AA free data cannot support it; documented as a limitation, superseded automatically by strategy A when Pro data exists.
- No per-model measured cache hit rates (AA Commercial-only data); `h` stays a single configured workload assumption.

## Decisions

1. **Ratio of blends, not token inversion.**
   `blend(prices) = (1−h)·p_input + h·p_cache_read + p_output/R` (per 1M units cancel in the ratio). `cost = aa_cost × blend(effective provider prices) / blend(AA prices)`.
   Missing `cache_read` on either side falls back to that side's input price (mirrors `_cost_of`); missing components on the provider side are already AA-filled by `effective_prices()`, contributing ratio 1.0.
   *Why over fixing the inversion to be self-consistent (`I = C / blend_aa`):* algebraically identical result, but the ratio form makes the invariant structural (numerator = denominator ⇒ 1.0) instead of relying on two code paths staying in sync, and it deletes the fake token counts entirely rather than keeping plausible-looking but invented numbers.
   *Why over a fixed token profile for everything:* discards AA's per-model token efficiency, which is the whole point of the AA-based strategies.

2. **Zero/invalid AA blend falls back to strategy C.**
   If `blend(AA) <= 0` (e.g. AA prices all zero/absent), keep the existing `_strategy_c` fallback, same as today's `denominator <= 0` guard. Free provider prices (blend 0) legitimately yield cost 0 — the ratio handles that without special-casing.

3. **Keep the method label `aa_free` and update the note text.**
   Downstream artifacts/reports key off `cost_method`; renaming would churn the report for no behavioral gain. The `notes` entry becomes "AA cost re-priced by provider/AA blended-price ratio (cache_hit_rate h, input:output R)" so the artifact explains the math honestly.

4. **Tests pin the invariant and the incident.**
   - Invariant: for several `(h, R)` combos, provider prices == AA prices ⇒ cost == `aa_cost_per_task` (exact float equality is safe: numerator and denominator are the same expression).
   - Incident regression: Kimi ($2/$10/$0.20, AA cost 3.6812) and Qwen ($1.5/$4.5/$0.075, AA cost 3.2681) at `h=0.98, R=4` return AA's numbers, not $2.24/$1.53.
   - Cheaper-cache ordering (existing test) and aa-fallback provenance (existing test) unchanged.
   - Zero-AA-blend → strategy C; zero provider prices → cost 0.

## Risks / Trade-offs

- [Costs rise ~1.6–2.1x for aa_free models; tier picks change] → Intended correction; re-run `score` and review the ranking report diff before populate. Prices synced to LiteLLM are unaffected (only ranking/cost fields change).
- [Ratio hides per-model workload shape differences (single global h, R)] → Inherent to free-tier data; documented. The knobs now only weight price differences, which is the honest interpretation.
- [Cache-write price differences still unpriced on this path] → Documented limitation (proposal + learnings); strategy A charges writes when Pro token counts exist. Not silently ignored.
- [Float equality in the invariant test could be brittle if numerator/denominator are computed by different helpers] → Compute both blends with the same helper function so identical inputs produce bit-identical values.

## Migration Plan

1. Land `_strategy_b` change + tests; full suite green.
2. Re-run `score` (no re-fetch needed — snapshots are correct after the column-drift fix); review tier changes in `tier-ranking.md`.
3. Re-run `populate` to converge cost/NMB-derived ordering in LiteLLM (per-token prices unchanged).
4. Rollback: revert commit and re-run `score`; no data migration involved.