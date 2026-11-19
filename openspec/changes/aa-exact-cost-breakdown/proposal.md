# Proposal

## Why

The `aa_free` cost path is wrong about how Artificial Analysis (AA) computes
`cost_per_task`. It assumes AA's benchmark has **no** cache hits, backs token
counts out of AA's total with a cache-blind denominator, and then re-prices 98 %
of that input at the provider's cache-read rate. AA does the opposite: since
Intelligence Index **v4.1** its published cost already includes cache-read and
cache-write pricing, combined with "live measurements of the model's typical
cache hit rate" (AA methodology, verified 2026-10-29).

Measured against AA's own numbers, the current formula lands **29 %–65 % below
AA (median −41 %)** across the 75 models AA scores, even when the provider's
prices are byte-for-byte identical to AA's. That distorts NMB ranking, Pareto
classification, and tier selection — the pipeline systematically prefers models
whose cache pricing it mishandles.

## What Changes

- **Use AA's published per-task cost breakdown** instead of inventing a cache
  split. AA publishes, per scored model, the per-task cost split into
  `nonCacheInput`, `cacheRead`, `cacheWrite`, `answer`, `reasoning` (USD). The
  pipeline SHALL fetch that breakdown, convert each component back into exact
  token counts using AA's own price for that component, and re-price those
  tokens at the provider's rates.
- **New cost method `aa_breakdown`**, ranked between `aa_pro` (token counts
  supplied directly) and the existing `aa_free` estimate.
- **Invariant:** when a provider's input / output / cache-read / cache-write
  prices equal AA's, the computed `cost_per_task` SHALL equal AA's published
  value. Divergent components change only their own share of the total.
- **Provider-agnostic by construction:** the strategy consumes the existing
  `ResolvedPricing` DTO, so CommandCode, OpenCode, and OpenRouter all get the
  same treatment (including their different cache-write support).
- **Fix the fallback too:** when no breakdown exists, the `aa_free` back-out
  denominator SHALL include the cache-read/cache-write terms, so the
  same-price invariant holds there as well.
- **Record the cost basis:** each deployment in `tier-output.json` SHALL carry
  AA's published cost, the derived per-task token counts, and the method used;
  the report SHALL show AA's number next to the re-priced one.
- **Config:** `cache_hit_rate` and `input_output_ratio` become fallback-only
  knobs; new optional `aa.breakdown_enabled`, `aa.breakdown_url` (template), and
  `aa.breakdown_max_pages` control the extra AA fetch.
- **Docs:** `WALKTHROUGH.md` §5 and the `config.example.yaml` comments are
  rewritten to match; the stale "AA has no cache hits" claim is removed.

Out of scope: subscription/credit-plan amortization (Go/GOAT-style plans),
Pro-tier AA access, and any change to NMB math, tier floors, or provider
adapters.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `model-pipeline`: the **Cost-per-task computation** requirement gains the
  breakdown-based method, the same-price invariant, and a corrected fallback;
  the **Configurable task profile and NMB parameters** requirement restricts
  the cache knobs to the fallback and adds the AA breakdown source knobs; the
  **Self-contained JSON output** requirement records the cost basis per
  deployment. A new **Artificial Analysis cost-breakdown retrieval** requirement
  covers the extra fetch, its cache artifact, logging, and fail-loud behavior.

## Impact

- **Code:** `src/model_pipeline/scoring/aa.py` (breakdown fetch + merge),
  `scoring/cost.py` (new strategy + fallback fix), `config.py`
  (`AaConfig` optional keys), `models.py` (deployment cost-basis fields),
  `emit/output.py` and `emit/report.py` (artifacts), `cli.py` (fetch/score
  wiring and summary).
- **Config:** `model-tier-populator/config.example.yaml` and the live
  `config.yaml` gain the optional `aa.*` keys (defaults keep old configs valid).
- **Artifacts:** new `output/aa_breakdown.json` cache; `tier-output.json`
  deployment records gain cost-basis fields; `tier-ranking.md` shows AA's
  reference cost.
- **External dependency:** one extra AA HTML page fetch per run (cached), from
  `https://artificialanalysis.ai/models/<slug>`. A page-shape change fails the
  phase loudly instead of silently changing the cost basis.
- **Ranking:** cost-per-task rises for most AA-covered models (median ~+70 %
  versus today), so tier selections and orders will change on the first run
  after this lands. Token limits, provider payloads, and populate behavior are
  untouched.
