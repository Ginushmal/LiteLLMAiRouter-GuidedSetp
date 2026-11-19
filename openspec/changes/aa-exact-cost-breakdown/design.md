# Design

## Context

See `proposal.md` — Why. Current state that shapes the approach:

- `scoring/cost.py` has three strategies selected by data availability (`aa_pro` →
  token counts, `aa_free` → total + prices, `task_profile` → fixed profile).
  `_strategy_b` (`aa_free`) backs tokens out with `P_in + P_out/ratio`, a
  denominator that contains **no cache term**, then re-prices 98 % of the input
  at the cache-read price.
- `scoring/aa.py::to_canonical` already stores `aa_cost_breakdown` (currently the
  raw `{total_cost, cost_per_task}` object) but nothing consumes it;
  `aa_token_counts` is always `None`.
- `ResolvedPricing` (`models.py`) is the provider seam every adapter feeds.
  `effective_prices()` applies AA fallbacks per component and records provenance.
- Both `fetch` and `score` call `AaClient.canonical_models()`; the AA API response
  is cached to `output/aa_snapshot.json`.

Verified against the live sources on 2026-10-29 (numbers drift — treat as evidence,
not constants):

| Check | Result |
|---|---|
| AA methodology (Intelligence Index v4.1) | cost metrics include cache hit rates and cache token pricing; "live measurements of the model's typical cache hit rate" |
| Free API `/api/v2/language/models/free` | exposes only `cost_per_task.total_cost` — no components |
| `/models` list page | embeds breakdowns for 28 models only |
| `/leaderboards/models` | exposes `intelligenceIndexCostPerTask` as a **number** (total only) |
| `/models/<slug>` detail page | embeds the full table: 716 model objects, **75** with `intelligenceIndexCostPerTask.cost` |
| Coverage | the 75 breakdown slugs equal the 75 API models that carry a cost total (no gaps) |
| Totals | page `cost.total` == API `cost_per_task.total_cost` for all 75 (max abs diff 4.9e-5) |
| Prices | page prices == API `pricing` on all but one model (one cache-read and one cache-write rounding difference) |
| Convertibility | 26 models publish a cache-write **cost** with no cache-write **price** (billed at input price); 2 models publish no input/output price |
| Rebuild | deriving tokens and re-pricing at AA's own prices reproduces AA's total exactly for 73/73 convertible models |
| Implied cache hit rate | 93.3 %–99.99 %, median 99.89 % — AA's benchmark is heavily cached |
| Current formula error (same prices) | −28.6 % to −64.8 %, median −41.4 % vs AA |

## Goals / Non-Goals

**Goals:**

- One exact, provider-neutral cost method that uses AA's own token shape and cache
  split, applied identically to CommandCode, OpenCode, and OpenRouter.
- A testable invariant: identical prices ⇒ AA's number; one differing component ⇒
  only that component's share changes.
- No silent behavior change: a source-shape change fails the phase; every model's
  method is recorded.

**Non-Goals:**

- Subscription/credit amortization, Pro-tier access, NMB/tier math, provider
  adapter changes, or a cache TTL for AA artifacts.

## Decisions

### D1 — Breakdown source: an AA model detail page

`AaClient` gains a breakdown fetch that loads `https://artificialanalysis.ai/models/{slug}`,
concatenates the Next.js flight chunks (`self.__next_f.push([1,"…"])`), recovers
model objects, and keeps those with `intelligenceIndexCostPerTask.cost` plus
`price1m*`/`cacheHitPrice`/`cacheWritePrice`.

- **Why not the API:** the free tier exposes only the total (verified).
- **Why not `/models` or the leaderboard:** 28 breakdowns / totals only (verified).
- **Anchor selection:** slugs come from the AA API snapshot, ordered by "has a cost
  total, then intelligence descending". Up to `aa.breakdown_max_pages` (default 3)
  pages are fetched and their breakdowns merged; fetching stops as soon as every
  API cost model has a breakdown. This is required because page coverage varies by
  slug — one verified detail page carried only 28 breakdowns while a current model
  page carried all 75.
- **Alternative rejected:** a hardcoded slug (rots when the model is retired);
  one page per scored model (45+ requests per run).

Parsed output is cached to `output/aa_breakdown.json` (`source` urls, `fetched_at`,
`models: {slug: {cost, prices}}`). It is cached indefinitely like
`aa_snapshot.json`; a stale cache is a known limitation, not a new one.

### D2 — Token derivation and re-pricing

For each model with a breakdown:

```
noncache_in  = cost.nonCacheInput / (aa_input / 1e6)
cache_read   = cost.cacheRead     / (aa_cache_read / 1e6)
cache_write  = cost.cacheWrite    / ((aa_cache_write or aa_input) / 1e6)
output       = (cost.answer + cost.reasoning) / (aa_output / 1e6)
```

- Answer and reasoning fold into one output count because both are billed at the
  output price; AA's split never changes the re-priced total (verified: every model
  prices reasoning at the output rate).
- `cache_write` falls back to the input price when AA publishes no write price —
  AA's own convention, confirmed by rebuilding all 26 such models to their exact
  totals.
- A component with a missing/zero AA price and a non-zero cost, or a negative
  component, makes that model non-convertible: fall back, never divide or guess.
- Re-pricing reuses the existing `_cost_of(prices, tp, tokens)` with
  `{input: noncache_in, cached: cache_read, cache_write, output}` and
  `effective_prices()` for provider prices + AA fallback provenance. No cache-hit
  rate, ratio, or reasoning multiplier is applied.

### D3 — Method precedence

`cost_per_task()` selects: `aa_pro` (counts) → `aa_breakdown` (new) → `aa_free`
(fixed) → `task_profile`. The chosen method is already written to
`cost_method` and counted in `cost_methods`.

### D4 — Fix the `aa_free` fallback denominator

Replace `P_in + P_out/ratio` with

```
(1 - h) * P_in_aa + h * P_cache_read_aa + P_out_aa / ratio        h = cache_hit_rate
```

so the same cache split used at re-price time is also present in the back-out.
This makes the same-price invariant hold on the fallback path too. Cache-write is
not modelled here (no write share exists in the task profile); that limitation is
confined to the fallback and documented in `WALKTHROUGH.md`.

### D5 — Configuration (backward compatible)

`AaConfig` gains optional fields with defaults, so an existing four-key `aa:` block
still loads:

```yaml
aa:
  breakdown_enabled: true                      # skip the extra page fetch when false
  breakdown_url: https://artificialanalysis.ai/models/{slug}
  breakdown_max_pages: 3                       # anchor pages tried before failing
```

`task_profile.cache_hit_rate` / `input_output_ratio` comments change to
"fallback only". The `aa:` block stays strict: unknown keys are still rejected,
and the three new keys are documented in `config.example.yaml` and the live
`config.yaml`.

### D6 — Artifacts and reporting

- `CanonicalModel.aa_cost_breakdown` now holds the parsed `cost` dict (components),
  and `aa_cost_per_task` holds the total; both already exist on the model.
- `Deployment` gains `aa_cost_per_task: float | None` and
  `tokens_per_task: dict | None`; `to_dict()` emits them as `aa_cost_per_task` and
  `tokens_per_task` alongside the existing `cost_method` and `effective_prices`.
- `tier-output.json` adds a top-level `aa_cost_basis` block (`fetched_at`,
  `source`, `models_with_breakdown`) next to `cost_methods`.
- `tier-output.md` gains an "AA $/task" column (`—` when AA has none); the ranking
  report header states the method distribution.

### D7 — Failure policy

- Page fetch error → try the next anchor slug; all anchors exhausted → raise.
- Non-empty page with zero breakdowns → raise with expected vs observed shape,
  leaving the raw body and a JSONL log entry (per the repo's scraper rules).
- Breakdown disabled → skip the fetch; methods fall back and the summary says so.
- A model without a breakdown is isolated: only its own method degrades.

### D8 — Provider parity is a test, not a branch

No provider-specific code. The parity tests construct `ResolvedPricing` in the
shapes each adapter actually emits and assert the invariant:

| Provider | Shape that must work |
|---|---|
| CommandCode | all four prices present; discounted rows already resolved to the effective price |
| OpenCode | cache-write `None` on most models (billed at provider input); cache-read present; peak/off-peak already collapsed to one price |
| OpenRouter | cache-read present on many, cache-write usually `None`; context-tier and time-of-day prices already collapsed |

Free models (price 0) re-price to 0 — the derivation divides by AA's price, never
by the provider's.

## Risks / Trade-offs

- **AA restructures its page** → parser isolated behind one module, fixture test
  from a captured page, raw body + log kept, phase fails loudly instead of
  silently reverting to the old estimate.
- **Page payload is large (~4 MB) and coverage varies by slug** → cached after the
  first run; ≤3 pages; coverage check stops early when complete.
- **First run changes rankings** (costs rise ~70 % for AA-covered models) → expected
  and visible in `cost_methods`, the AA reference column, and the report.
- **2 of 75 models are not convertible** (no AA input/output price) → they fall back
  to `aa_free` and are listed with their method; no invented numbers.
- **AA could publish a zero cache price with a non-zero cache cost** → guarded as
  non-convertible instead of dividing by zero.
- **Cache never expires** → same behavior as the existing AA snapshot; a future
  `--refresh-aa` flag can address it without changing this design.

## Migration Plan

1. Ship the code and config defaults; existing `aa:` blocks keep working.
2. Run `model-pipeline refresh` (or `score` alone if `output/aa_breakdown.json`
   already exists). First run fetches and caches the breakdown.
3. Verify: `cost_methods` shows `aa_breakdown` for AA-scored deployments; spot-check
   one model by re-pricing at AA's prices and comparing to `aa_cost_per_task`.
4. Rollback: set `aa.breakdown_enabled: false`. Costs revert to the fallback path
   (with the corrected denominator), and the summary reports it.

## Open Questions

- Does AA's Pro API expose per-task token counts? If it does, it would supersede
  the page scrape; the `aa_pro` strategy remains first in precedence and can absorb
  it without a spec change.
