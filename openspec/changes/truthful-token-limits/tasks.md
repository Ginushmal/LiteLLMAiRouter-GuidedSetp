# Tasks

## 1. models.dev fetch and resolution

- [x] 1.1 Add the pipeline-provider → models.dev provider-id mapping (provider metadata only, no model ids) to the pipeline config with the usual explanatory comments, and verify the config loads and the mapping is exposed to the adapters
- [x] 1.2 Add a models.dev fetcher that saves the raw catalog JSON and a structured log entry alongside the other scrape artifacts, and verify a fetch run produces both files (verified via the same `fetch_catalog` call the fetch phase makes: `data/raw/modelsdev/20261019T120641Z_https-models-dev-api-json.json` + `data/logs/modelsdev/2026-10-19.log`; the full `fetch` command currently aborts earlier on an unrelated OpenCode 401)
- [x] 1.3 Implement limit resolution (exact provider + model entry first, then normalized model-id match across the catalog, provider-specific entries preferred) and verify unit tests cover: provider entry wins, fallback match resolves when the provider entry is missing, an unrelated provider's entry is only used as last resort, and both lookups missing yields "unresolved"
- [x] 1.4 Verify resolution against the real catalog fixture: every model the CommandCode and OpenCode provider APIs advertise resolves to an output limit (CommandCode 92/92 from the live catalog; OpenCode 36/37 — `omen-alpha` exists nowhere in the catalog and correctly flags `unresolved`)

## 2. Limit derivation and emission

- [x] 2.1 Add context, input-limit, and output-limit fields (with provenance) to the normalized model record and the deployment payload, and verify unit tests round-trip them through the artifacts
- [x] 2.2 Implement input-limit derivation (`context − output`, provider-published context unchanged) and verify a test reproduces the known relation (1,050,000 − 128,000 = 922,000)
- [x] 2.3 Emit `model_info.max_output_tokens`, `model_info.max_tokens` (mirroring the output limit), and the derived `model_info.max_input_tokens` in the deployment assembly, and verify a payload test shows all three fields with correct values
- [x] 2.4 Record per-deployment limit provenance in `tier-output.json` and flag unresolved models (and catalog entries where output equals the context) in the report, and verify a generated report contains the flags for a deliberately unresolved fixture model

## 3. Populate convergence

- [x] 3.1 Extend the populate diff to compare pipeline-owned `model_info` fields (`base_model`, `model_group`, `max_input_tokens`, `max_output_tokens`, `max_tokens`) and verify tests show a limit change is detected while server-managed fields never cause a diff
- [x] 3.2 Add a PATCH-based update path to the LiteLLM client (the PUT model-update endpoint ignores `model_info`) and verify a test asserts the PATCH request carries only pipeline-owned `model_info` fields alongside the changed `litellm_params`
- [x] 3.3 Verify an update against a deployment whose stored row predates this change converges it to the desired limits without clearing unowned `model_info` fields (live DB: all 40 `mp::` rows carry `max_input_tokens`/`max_output_tokens`/`max_tokens` and still carry `member_auto_router` + `db_model`; PATCH merged per key)

## 4. Verification against the running instance

- [x] 4.1 Re-run the score phase and verify `tier-output.json` carries real limits per deployment (e.g. MiMo 131072, Gemini 4 Argon 65536) with provenance
- [x] 4.2 Run populate and verify exactly the pipeline-managed rows are updated, and `GET /v1/model/info` reports the real limits (no context-sized output values remain) (40/40 rows are `mp::`, 0 slash ids, 0 missing output limits, max advertised output 131072, none `out == in`)
- [x] 4.3 Re-run populate and verify it reports zero changes (idempotence holds with the new diff) (`added=0 updated=0 deleted=0 unchanged=40 errors=0`, twice)
- [x] 4.4 Refresh OpenCode's model discovery and verify the next request carries a `max_completion_tokens` within the advertised limit and succeeds without the oversized-completion failure (discovery now advertises 65536/128000/131072 per row; `POST /v1/chat/completions` `pro-tier` with `max_completion_tokens=131072` returned 200, served by `xiaomi/mimo-v2.6-pro`, `finish_reason=stop`)

## 5. Documentation

- [x] 5.1 Update `model-pipeline/WALKTHROUGH.md` with the limits flow and verify the walkthrough matches the implemented phases
- [x] 5.2 Log the LiteLLM learning (discovery mirrors `context_length` into `max_output_tokens`; configured `model_info` wins; PUT update ignores `model_info`) in `LiteLLM-Learnings.md` with its doc sources, and tick the matching `ROADMAP.md` item
