# Proposal

## Why

The pipeline currently covers two providers (CommandCode and OpenCode) whose pricing comes
partly from HTML documentation pages. OpenRouter publishes its entire catalog — models,
per-token prices, context windows, cache prices, and time-of-day pricing schedules — in one
JSON API (`https://openrouter.ai/api/v1/models`), so adding it needs no HTML scraping at all.
It is the largest catalog we can ingest (375 chat-servable models as of 2026-10-21), it
includes $0 `:free` endpoints for the same models, and its per-model pricing schedules are
the first data source that lets the pipeline rank models by *when* they are cheap (weekend /
off-peak), not just by an average rate.

## What Changes

- **New `openrouter` provider adapter** implementing the existing `ProviderAdapter` seam.
  `https://openrouter.ai/api/v1/models` is the single source for models **and** pricing;
  the adapter fetches JSON only (no `pricing_url` scrape) and is registered in
  `providers/registry.py` with a `providers.openrouter` config block.
- **Model filtering in the adapter** (config-driven `exclude:` still wins on top):
  - `:free` variants **included** — real AA intelligence via canonical mapping where one
    exists (10 of 17 as of 2026-10-21), $0 input/output cost as published; the 7 with no
    AA canonical identity drop as `no_intelligence` like any unmapped model.
  - `:batch` variants **excluded in the adapter** — they serve OpenRouter's Batch API, not
    chat traffic (same seam as the deferred `responses`/`google` endpoint protocols).
  - the router entries that are not models — `openrouter/free` ("Free Models
    Router"), `openrouter/auto`/`auto-beta`, `openrouter/fusion`,
    `openrouter/pareto-code`, `openrouter/bodybuilder`, and
    `typesafe/jev-router` — are excluded via `exclude.patterns`.
- **Pricing: per-model time-of-day schedules.** Each model's own `pricing.overrides[]`
  windows are used (global `peak_windows_utc` is never assumed — `tencent/hy3` peaks
  00:00–16:00 daily, unlike the DeepSeek windows). New policy key
  `pricing.time_price_mode: today | average | instant` (default `today`), plus an optional
  `as_of` timestamp (config key and `--as-of` CLI flag) to evaluate a schedule for an
  arbitrary instant:
  - `today` — weighted average over today's slice of `active_window_utc` (weekdays blend
    their peak bands; weekends come out flat off-peak);
  - `average` — today's behavior: weighted over the whole configured week
    (`active_window_utc` × `active_days`);
  - `instant` — no averaging: the price that applies at the run timestamp.
  `min_prompt_tokens` tier thresholds still collapse via `context_tier_policy` (they depend
  on request size, not time). **Behavior change:** `time_price_mode` governs every
  time-of-day collapse, so with the `today` default the prices recorded for existing
  peak/off-peak models (OpenCode's DeepSeek) change from a weekly weighted average to
  today's schedule slice.
- **Token limits** resolve from the models.dev catalog provider id `openrouter`
  (`models_dev_provider_ids: ["openrouter"]`, 389 exact id matches as of 2026-10-21) through
  the unchanged `limits.py` lookup order.
- **LiteLLM deployment shape**: `openai/` prefix + `api_base: https://openrouter.ai/api/v1`
  via the existing `_assemble` seam; `api_key_env: OPEN_ROUTER_API_KEY` is added to
  `docker-compose.yml` and `.env.example`.
- **Config and tests**: `providers.openrouter` block in `model-tier-populator/config.yaml`,
  adapter tests (model parsing, pricing/schedule parsing, deployment payload, `:batch` and
  `openrouter/free` exclusions), and pricing tests for the three time modes.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `model-pipeline`: the multi-provider fetching requirement gains a third provider adapter
  fed by a JSON API, and its pricing-normalization scenario generalizes from a single global
  peak/off-peak weighting to per-model schedules with three time-of-day price modes and an
  `as_of` evaluation instant; the config-driven pricing policy requirement grows the
  `time_price_mode` knob.

## Impact

- `model-tier-populator/src/model_pipeline/providers/openrouter.py` (new),
  `providers/registry.py`, `config.py` (`PricingConfig` + `ProviderConfig` usage),
  `pricing.py` (schedule evaluator generalizing `weighted_price`), CLI (`--as-of`).
- `model-tier-populator/config.yaml` — new `providers.openrouter` block and `pricing.time_price_mode` /
  `pricing.as_of` keys with the usual inline teaching comments.
- `docker-compose.yml`, `.env.example` — `OPEN_ROUTER_API_KEY` wiring.
- `model-tier-populator/tests/` — adapter and pricing-mode tests.
- Existing deployments in LiteLLM's DB are untouched by the addition itself; the
  `time_price_mode` default changes recorded prices for peak/off-peak models on the next
  run (populate converges them idempotently).
