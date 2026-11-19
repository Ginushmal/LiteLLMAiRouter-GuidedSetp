# Tasks

## 1. Data model and snapshot persistence

- [x] 1.1 Add `canonical_hint` and `native_protocol` to `RawModel` in `src/model_pipeline/models.py`, and document that `endpoint_type` is the deployment protocol while `native_protocol` records the provider's native API; verify the dataclass imports cleanly with `uv run python -c "from model_pipeline.models import RawModel; print(RawModel('p','m','M').canonical_hint)"`.
- [x] 1.2 Serialize and restore both fields in `src/model_pipeline/emit/snapshot.py`, defaulting missing values to empty strings for older snapshots; verify with a round-trip test that writes a model, reads it back, and asserts both fields survive.

## 2. OpenCode live catalog adapter

- [x] 2.1 Rewrite `OpenCodeAdapter.fetch_models` in `src/model_pipeline/providers/opencode.py` to read `id`, `name`, `canonical_id`, `limit.context`, `limit.output`, and `api`; set `display_name` from `name`, `canonical_hint` from `canonical_id`, `context_tokens`/`output_tokens` from `limit`, `native_protocol` from the `api` keys, and `endpoint_type` to `messages` for messages-native models and `chat` for all others; verify the adapter test covers all four native protocol categories and their deployment endpoints.
- [x] 2.2 Remove `parse_opencode_endpoints`, `_endpoint_type`, and the endpoint-table lookup from the adapter; verify the docs-pricing tests still pass and the adapter no longer imports endpoint-parsing helpers it does not use.
- [x] 2.3 Add `tests/fixtures/opencode_models.json` derived from the live `/models` payload (30 models, including chat, messages, responses, and generate-content examples) and add `tests/test_opencode.py`; verify it asserts 30 fetched models, DeepSeek's display name and canonical hint, non-null context/output limits, responses/google models using `chat`, and messages models using `messages`.
- [x] 2.4 Update the OpenCode provider comments in `config.yaml` and `config.example.yaml`, plus the provider table and gotchas in `README.md` and `WALKTHROUGH.md`, to state that responses/google-native models are served through chat translation and that docs-only deprecated models are not synthesized; verify no "responses/google deferred" claim remains and the new explanation is present.

## 3. Canonical hint mapping

- [x] 3.1 Update `map_models` in `src/model_pipeline/dedup/mapper.py` to try `m.canonical_hint`, then `m.display_name`, then `m.model_id` for the exact match; verify `tests/test_dedup.py` covers a hint that resolves `deepseek-v4.1-flash` to `deepseek-v4-1-flash-1017` while the display name alone would resolve to the older `deepseek-v4-1-flash`.
- [x] 3.2 Add a fallback test for an unknown hint; verify it falls through to the existing display-name/model-id match and still records method `exact` or `unmapped` as appropriate, without raising.
- [x] 3.3 Document the hint-first order in the dedup section of `WALKTHROUGH.md`; verify the document names `canonical_id` as the provider-supplied hint and explains that unmatched hints fall back.

## 4. Provider-first token limits

- [x] 4.1 Update `apply_limits` in `src/model_pipeline/limits.py` to keep a provider-published `output_tokens`, set `limits_source` to `provider:<provider>`, fall back to models.dev when the provider publishes none, derive `input_tokens` from `context - output`, and deduplicate the output-vs-context flags; verify `tests/test_limits.py` covers provider output precedence, models.dev fallback, input derivation, and the equal-context flag.
- [x] 4.2 Remove the stale "OpenCode publishes none" comment and update the token-limits section of `WALKTHROUGH.md` to describe provider-first precedence and the `provider:<name>` source; verify the document no longer claims OpenCode publishes no context window.

## 5. Fetch coverage census

- [x] 5.1 Add a `FetchCensus` dataclass and a `last_census` attribute in `src/model_pipeline/providers/base.py`, populate it in `ProviderAdapter.fetch_all` and `OpenRouterAdapter.fetch_all`, and record advertised/extracted/unsupported/no-pricing counts; verify `tests/test_opencode.py` asserts 30 advertised and 30 extracted for the fixture, and a second test asserts an unsupported or missing-pricing model is counted rather than silently dropped.
- [x] 5.2 Print one census line per provider in `cmd_fetch` and write `output/fetch-census.json`; verify a unit test for the formatting helper covers the zero-drop and drop cases, and the integration run confirms the JSON file lists OpenCode with 30/30.
- [x] 5.3 Mention the census artifact in `README.md`/`WALKTHROUGH.md`; verify the documented path matches the emitted file name.

## 6. Integration verification

- [x] 6.1 Run `uv run --with pytest pytest tests/ -q`; verify the full suite passes.
- [x] 6.2 Run `uv run model-pipeline refresh`; verify the console reports `opencode: 30 advertised, 30 extracted`, `output/models_snapshot.json` contains 30 opencode rows with non-null `context_tokens`, and `output/fetch-census.json` records zero unsupported and zero missing-pricing for OpenCode.
- [x] 6.3 Inspect `output/mappings.csv` and `output/tier-output.json`; verify `opencode:deepseek-v4.1-flash` maps to `deepseek-v4-1-flash-1017` and appears in the model index or a tier if it clears the floor, and that no `mimo-v2.5`/`mimo-v2.5-pro` rows were synthesized.
- [ ] 6.4 If the configured LiteLLM server is reachable, run `uv run model-pipeline populate --dry-run`; verify the diff includes the newly extracted OpenCode models and that existing OpenCode deployments gain `max_input_tokens` without unrelated field churn.

## Workflow follow-up

- Archive the change after review and a successful refresh/populate cycle.
