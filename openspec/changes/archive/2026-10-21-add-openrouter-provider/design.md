# Design

## Context

The pipeline's provider seam is `ProviderAdapter` (`model_pipeline/providers/base.py`):
`fetch_models()` → `RawModel`, `fetch_pricing()` → `ResolvedPricing`, `available()` for
protocol filtering, `to_litellm_deployment()` via the shared `_assemble`/`_price_params`
helpers. Provider-specific knowledge lives only in `providers/<name>.py`; the
`providers:` block in `config.yaml` is the control plane; `registry._REGISTRY` maps name
to adapter. Downstream (dedup → score → rank → populate) consumes the common DTOs and must
work unchanged.

Pricing collapse today: `pricing.py` exposes `weighted_price(peak, off_peak, peak_windows,
active_window, active_days)` and `normalize_context_tiers(...)`. `opencode.py` calls
`weighted_price` with the **global** `pricing.peak_windows_utc` because its docs publish
only "Peak"/"Off-Peak" labels, not hours. OpenRouter does publish hours — per model.

OpenRouter catalog facts (verified live against
`https://openrouter.ai/api/v1/models`, 2026-10-21; counts drift daily, nothing may be
hardcoded):

- 468 entries, all text-output. Ids carry a vendor segment (`deepseek/deepseek-v4.1-flash-1017`).
- 76 `:batch` variants (Batch API only), 17 `:free` variants, plus the `openrouter/free`
  "Free Models Router" entry (no intelligence possible).
- Prices are USD **per token** as strings (`"0.000005"` = $5/M); `prompt`/`completion`
  always present; `input_cache_read` 312 models, `input_cache_write` 94.
- `pricing.overrides[]`: 92 entries — 76 `min_prompt_tokens`-only, 10 time-window-only
  (belonging to 4 models: `deepseek/deepseek-v4.1-flash-1017`,
  `deepseek/deepseek-v4-pro-0813`, `tencent/hy3`, `tencent/hy4-preview`), 0 mixed.
  Time bands use `utc_start`/`utc_end` as HHMM numbers and tile the full week, so the
  schedule is complete no matter when the fetch runs. The top-level price is the price
  outside every band (verified: `tencent/hy3` base = its 16:00–00:00 band price).
  `tencent/hy3` peaks 00:00–16:00 **daily** — it does not match the global
  `peak_windows_utc` (01:00–04:00 & 06:00–10:00 Mon–Fri), so global windows must never be
  assumed for OpenRouter.
- models.dev publishes provider id `openrouter` with 389 exact id matches; `limits.py`'s
  existing lookup order (own provider exact id → normalized fallback, which already
  ignores vendor prefixes and serving-plan suffixes) resolves `:free` rows to their base
  model's limits.

## Goals / Non-Goals

**Goals:**

- OpenRouter adapter fed by the one JSON endpoint; zero HTML scraping for this provider.
- Per-model schedule evaluation with `time_price_mode: today | average | instant` and an
  `as_of` evaluation instant, reusable by any provider that publishes time windows.
- `:free` rows carry their published $0 prices and real canonical AA intelligence; nothing
  is invented anywhere.
- Downstream phases and the LiteLLM population format unchanged.

**Non-Goals:**

- Modelling OpenRouter free-tier rate limits (20 req/min; 50 req/day below $10 credits,
  1000/day above) into ranking or artifacts — documented caveat only.
- Non-chat OpenRouter surfaces (Batch API, `:batch` variants, `openrouter/free` router).
- Native LiteLLM `openrouter/` provider prefix, Responses-API support, provider
  preference/routing parameters (`:nitro`, `:floor` variants if they appear).
- Changing `limits.py`, the dedup/Jev path, or the ranking math.

## Decisions

1. **One JSON source.** `models_url: https://openrouter.ai/api/v1/models` serves as both
   `fetch_models()` and `fetch_pricing()`; `pricing_url` stays empty. The raw JSON is saved
   through the existing `_record()` seam, satisfying the structured-logs requirement
   (already scoped to "HTML or JSON"). *Alternative:* re-price from models.dev or scrape
   openrouter.ai pages — both add a second source of truth for the same numbers.

2. **Config block mirrors `commandcode`** (simplest adapter to copy):
   `api_base`/`models_url` = `https://openrouter.ai/api/v1`,
   `api_key_env: OPEN_ROUTER_API_KEY` (exact name already in `.env`; added to
   `docker-compose.yml` and `.env.example`),
   `models_dev_provider_ids: ["openrouter"]`, `supported_endpoints: ["chat"]`,
   `litellm: { chat_completions_api_base: https://openrouter.ai/api/v1 }`, no
   `extra_headers`. Deployments assemble as `openai/<provider-model-id>` + `api_base`
   through the existing `_assemble` seam, exactly like CommandCode's OpenAI-compatible
   rows. *Alternative:* LiteLLM's native `openrouter/` prefix — it needs new payload code
   in `_assemble` and may rewrite model names in ways we have not verified; `openai/` +
   explicit `api_base` is the verified shape.

3. **`:batch` excluded in the adapter, router entries excluded in config.** A `:batch`
   variant structurally cannot serve chat traffic — provider knowledge, so it is filtered
   in `openrouter.py` alongside the `available()` endpoint filter. The router entries
   (`openrouter/free`, `auto`/`auto-beta`, `fusion`, `pareto-code`, `bodybuilder`,
   `typesafe/jev-router`) *are* chat-servable, but they are load balancers/task routers
   rather than models, so whether they belong in the gateway is a policy call made through
   `exclude.patterns`, which the operator can change. Both stay consistent with "config is
   the control plane": the adapter filters what no config could want; config filters what a
   human might.

4. **`:free` included, mapped by stripping the serving-plan suffix.**
   `minimax-m3-1-flash:free` → canonical `minimax-m3-1-flash` (the dedup requirement's
   serving-suffix rule). Price is the published $0/$0; intelligence comes from the shared
   canonical's AA data; the 7 `:free` models whose base has no AA identity drop as
   `no_intelligence` like any unmapped model. A `:free` row and its paid sibling are the
   same canonical but different `(canonical, cost_per_task)` groups, so each can hold its
   own top-K slot — intentional: the $0 row ranks first and the paid sibling is natural
   failover when the free endpoint 429s (order-based fallbacks in the root `config.yaml`
   already do this).

5. **Schedule model: per-model bands, collapsed time-first.** Each model's
   `pricing.overrides[]` becomes `(min_prompt_tokens?, utc_start?, utc_end?, days?, price)`
   entries plus the base price. Collapse order (per the spec):
   1. within each context tier (base tier + one per distinct `min_prompt_tokens`),
      resolve the time dimension by mode;
   2. collapse the resulting tier prices with `context_tier_policy`.
   Time resolution: `instant` = the band containing the evaluation instant else the base
   price; `today` = weighted over `active_window_utc` on the evaluation date using that
   date's weekday and the model's own bands (unaffected by `active_days`); `average` =
   weighted over `active_window_utc` × `active_days` (today's behavior, generalized).
   One evaluator `time_price(bands, base, mode, window, days, as_of)` in `pricing.py`;
   `weighted_price` becomes a two-band wrapper over it so `opencode.py` picks up the modes
   with no adapter rewrite. *Alternative:* keep `weighted_price` separate and give
   OpenRouter its own evaluator — rejected: two weighting implementations would drift.

6. **`as_of` is config + CLI, timestamps must be timezone-aware.**
   `pricing.as_of: null` (ISO 8601 with `Z`/offset) and `--as-of` on the run override it;
   naive local timestamps are rejected. When unset, the run timestamp is used. The
   artifact records the evaluation instant and the applied mode in each pricing's
   `normalization` metadata so a recorded price can never be mistaken for a stable rate.

7. **Defaults: `time_price_mode: today`, `as_of: null`.** `today` matches the daily-run
   workflow (day's expected price, not dependent on the run second); `instant` for "what
   does it cost right now", `average` for stable cross-day comparisons.

## Risks / Trade-offs

- [`today`/`instant` are snapshots; a skipped run leaves yesterday's rates] → daily runs
  are the operating assumption; the artifact stamps the evaluation instant; `average`
  remains available for stable numbers.
- [`:free` endpoints rate-limit (20 req/min; 50–1000 req/day depending on purchased
  credits)] → not modelled; the $0 rows may 429 under load, and existing order-based
  failover in the root `config.yaml` routes traffic to the next order. Documented in the
  config comments.
- [A canonical can appear twice in one tier (free + paid group), consuming two top-K
  slots] → intentional (different cost groups = different failover quality); tune
  `top_k_per_tier` if it crowds out diversity.
- [Default `today` changes recorded prices for OpenCode's peak/off-peak models] → converges
  on the next populate run (diff-based); rollback is `time_price_mode: average`.
- [Catalog churn: models appear/disappear daily] → diff-based populate converges; nothing
  hardcodes identities; the mappings CSV is the human checkpoint before score.
- [Per-token price strings are tiny floats] → parse with the same float handling as the
  existing adapters and keep prices in per-token units end to end; no unit conversion.

## Migration Plan

1. Add the `providers.openrouter` block, `pricing.time_price_mode`/`pricing.as_of`, and the
   `OPEN_ROUTER_API_KEY` wiring (`docker-compose.yml`, `.env.example`).
2. Run fetch → review `mappings.csv` (7 `:free` rows expected as unmapped) → score →
   populate. Populate touches only `mp::`-prefixed rows, so existing manual gateway rows
   are untouched.
3. Rollback: `enabled: false` for the provider and/or `time_price_mode: average`; rerun
   populate to converge prices back. No DB or artifact schema migration.

## Open Questions

- Whether to surface OpenRouter free-tier rate limits as artifact metadata (so ranking
  could later de-weight rate-limited rows) — deferrable, does not affect this change.
