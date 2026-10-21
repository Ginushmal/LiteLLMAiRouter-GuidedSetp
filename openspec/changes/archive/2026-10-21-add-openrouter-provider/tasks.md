# Tasks

## 1. Pricing schedule evaluator (shared math)

- [x] 1.1 Implement `time_price(bands, base_price, mode, active_window, active_days, as_of)` in `model_pipeline/pricing.py` — `instant` picks the band containing the evaluation instant else the base price, `today` weights over `active_window_utc` on the evaluation date using that date's weekday, `average` weights over `active_window_utc` × `active_days` — and verify new `tests/test_pricing.py` cases cover all three modes, a weekday-vs-weekend run of the same schedule, and the base-price fallback outside every band
- [x] 1.2 Re-express `weighted_price` as a two-band wrapper over `time_price` and verify the existing `test_weighted_price_*` cases pass unchanged
- [x] 1.3 Implement the collapse order (time dimension resolved within each `min_prompt_tokens` context tier first, then tiers collapsed via `context_tier_policy`) and verify a mixed-dimension test case passes

## 2. Config control plane and wiring

- [x] 2.1 Add `pricing.time_price_mode` (default `today`, enum `today|average|instant`) and `pricing.as_of` (nullable ISO 8601 with timezone; naive timestamps rejected) to `PricingConfig` in `model_pipeline/config.py`, and verify `tests/test_config.py` covers valid values, an invalid mode, and a naive timestamp rejection
- [x] 2.2 Add the `providers.openrouter` block to `model-tier-populator/config.yaml` (`api_base`/`models_url` = `https://openrouter.ai/api/v1`, `api_key_env: OPEN_ROUTER_API_KEY`, `models_dev_provider_ids: ["openrouter"]`, `supported_endpoints: ["chat"]`, `litellm.chat_completions_api_base`) and document `time_price_mode`/`as_of` with the inline-comment rule, then verify the CLI loads the config without error (`uv run model-pipeline --help` from `model-tier-populator/`)
- [x] 2.3 Wire `OPEN_ROUTER_API_KEY` into `docker-compose.yml` (litellm service `environment:`) and `.env.example`, and verify both use exactly the variable name the config block references
- [x] 2.4 Add the `--as-of` CLI override for fetch/score runs (overriding `pricing.as_of`) and verify `tests/test_cli.py` covers flag-over-config precedence

## 3. OpenRouter provider adapter

- [x] 3.1 Implement `providers/openrouter.py` fetching models **and** pricing from `https://openrouter.ai/api/v1/models` (raw JSON saved through the existing recorder seam) and register it in `providers/registry.py`, then verify new `tests/test_openrouter.py` cases cover model parsing and per-token price-string parsing (`"0.000005"` → $5/M semantics preserved as per-token float)
- [x] 3.2 Implement eligibility filtering — exclude `:batch` variants (Batch API, not chat-servable), include `:free` variants with their published $0 prices, leave `openrouter/free` to `exclude.patterns` — and verify one test per case in `tests/test_openrouter.py`
- [x] 3.3 Parse `pricing.overrides[]` into per-model schedules (`min_prompt_tokens` tiers; time bands with HHMM `utc_start`/`utc_end` and day coverage; base price outside every band) and verify tests collapse `tencent/hy3`-style daily windows and `deepseek`-style weekday windows correctly in all three modes, using each model's own bands rather than `peak_windows_utc`
- [x] 3.4 Assemble LiteLLM deployments via the `_assemble` seam (`openai/` prefix + `api_base: https://openrouter.ai/api/v1`, inline per-token prices, `api_key_env` reference) and verify the deployment-payload test asserts `litellm_params.model`, `api_base`, and price fields
- [x] 3.5 Update `model-tier-populator/README.md` where it describes providers and pricing policy to mention OpenRouter and the time-of-day price modes, and verify the documented config keys match `config.yaml` exactly

## 4. Canonical mapping and limits for plan suffixes

- [x] 4.1 Extend the serving-suffix normalization to strip trailing `:free`/`:batch` plan suffixes before matching (deployment record keeps the full provider model ID) and verify `tests/test_dedup.py` maps `minimax-m3-1-flash:free` to the base canonical with method "exact"
- [x] 4.2 Verify a `:free` model resolves its output limit through the normalized fallback to the base model's models.dev entry with a `tests/test_limits.py` case (no `limits.py` behavior change expected)

## 5. Integration verification

- [x] 5.1 Run the full verification suite from `model-tier-populator/` — `uv run --with pytest pytest tests/`, `uv run --with ruff ruff check src tests`, `uv run model-pipeline --help` — and verify all pass with no new lint findings
- [x] 5.2 Run an end-to-end fetch against the live catalog and verify the mappings CSV shows `:free` rows mapped to base canonicals (unmapped ones marked, never invented), `:batch` and the router entries absent from the tier list, and the artifact records the applied `time_price_mode` and evaluation instant

## Workflow follow-up

- After implementation review, archive the change (`openspec archive`) so the delta merges into `openspec/specs/model-pipeline/spec.md`.
- Confirm the populated LiteLLM rows live under the pipeline's `mp::` ID prefix only, leaving manual gateway rows untouched.
