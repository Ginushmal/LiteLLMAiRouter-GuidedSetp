# Tasks

## 1. Configuration and key-list parsing

- [x] 1.1 Add `api_keys_env` to the provider config and the failover bootstrap fields (`num_retries`, `allowed_fails`, `cooldown_time`) to the pipeline config, keeping `api_key_env` as a one-key fallback; verify the config loader tests cover both shapes
- [x] 1.2 Implement JSON key-list parsing with trimming, empty-entry removal, duplicate removal, legacy single-key fallback, and enabled-provider failures for missing/empty lists; verify unit tests for comma/quote-safe values, duplicates, empties, and the legacy key
- [x] 1.3 Update `config.example.yaml` with the new provider key-list shape and failover block, including the cooldown/walk-time formula comment; verify the example loads through the real config loader

## 2. Fetch key fallback

- [x] 2.1 Add a shared key-fallback GET helper to the provider adapter base, classifying `401/402/403/408/409/429/5xx` and transport errors as fallback cases and `400/404` as terminal; verify tests for each class and the all-keys-fail error summary
- [x] 2.2 Wire CommandCode and OpenCode model fetches through the helper; leave OpenRouter's public catalog unchanged; verify their adapter tests and that every HTTP attempt records only the slot and fingerprint
- [x] 2.3 Ensure the fetch phase succeeds when at least one key works, records failed slots, and still emits every configured key during population; verify the fetch/populate fixture tests

## 3. Capability resolver

- [x] 3.1 Add a provider-only capability resolver over the existing models.dev catalog, using exact then normalized provider lookups and no cross-provider fallback; verify tests for provider-entry hit, provider-entry miss with another provider present, and unresolved
- [x] 3.2 Map `modalities.input/output`, `tool_call`, `structured_output`, and `attachment` to the LiteLLM fields, including explicit false only when the provider entry declares false; verify tests for image, PDF, audio, video, text-only, tool, structured output, attachment-only, and non-text output
- [x] 3.3 Implement the reasoning policy: published effort values produce `reasoning_effort_levels` plus all seven per-level flags; `reasoning: true` with no effort values emits `supports_reasoning` and omits the flags with a `reasoning_levels_missing` flag; `reasoning: false` produces an empty list and all flags false; verify tests for each branch
- [x] 3.4 Carry `capabilities_source` and `capabilities_flags` on raw models and deployments into `tier-output.json`; verify the artifact tests assert the fields and that no capability is inferred from `attachment`

## 4. Multi-key expansion and credential identity

- [x] 4.1 Add credential slot and fingerprint fields to the deployment model and implement the id scheme: legacy id for the first key, `key-<n>` for additional keys, `sha256` prefix fingerprint; verify unit tests for id stability and fingerprint length/format
- [x] 4.2 Expand selected deployments after NMB selection into one payload per key with identical model, API base, prices, order, retry budget, and capability metadata; verify tests that Pareto/NMB/top-K and order assignments are unchanged by key count
- [x] 4.3 Deduplicate keys, warn on duplicates, and verify add/remove/reorder behavior produces only the expected slot create/delete/update operations

## 5. Failover defaults and suggested router config

- [x] 5.1 Emit `litellm_params.num_retries` and `model_info.allowed_fails`/`cooldown_time` from the pipeline bootstrap on every deployment; verify payload tests assert the exact values
- [x] 5.2 Generate `output/suggested_router_config.yaml` with `latency-based-routing`, `lowest_latency_buffer`, timeout, cooldown, and the `retry_policy` needed for 402, plus a comment describing the worst-case walk formula; verify the file is produced by a score run and parses as YAML
- [x] 5.3 Add `num_retries` to the compared parameter keys and `allowed_fails`/`cooldown_time` to the compared/writable model-info keys; verify drift tests detect and converge each value

## 6. Sync convergence

- [x] 6.1 Add every new capability, credential, and failover field to the sync comparison and write sets; verify a stored deployment with old metadata is updated to the desired values
- [x] 6.2 Implement fingerprint-driven in-place PATCH, including the raw key in the update body when the fingerprint changes, and preserve stored capability fields omitted by the current run; verify unit tests for rotation, unknown values, and no-op runs
- [x] 6.3 Add a rotation/add/remove integration test against the fake LiteLLM server and verify rotation preserves the deployment id and changes only the key and fingerprint

## 7. Reports and artifacts

- [x] 7.1 Add per-deployment credential slot/fingerprint, per-group credential count, and capability source/flags to `tier-output.json`; verify the output fixture asserts the new fields
- [x] 7.2 Show the key count and capability warnings in the Markdown and HTML reports without rendering any raw key; verify both rendering tests
- [x] 7.3 Add a leakage check that scans logs, `tier-output.json`, and reports for raw key values; verify it passes with a fixture containing fake keys

## 8. Verification and docs

- [x] 8.1 Run the full offline suite (`uv run --with pytest pytest tests/`) and Ruff (`uv run --with ruff ruff check src tests`); 241 tests pass, every changed/new file is Ruff-clean, and the repository's pre-existing 62 findings in untouched files are reported (no new findings introduced)
- [x] 8.2 Run the live smoke test: two fake keys at the same order, one returns `500`/`402`, verify the same request succeeds on the sibling and order escalation happens after both fail
- [x] 8.3 Run `populate --dry-run` against the local LiteLLM and inspect the added/updated/deleted sets; verify no writes occur
- [x] 8.4 Update the populator `README.md`, `WALKTHROUGH.md`, and `config.example.yaml` with the new key-list, failover, capability, and suggested-router behavior

## 9. Follow-up review fixes

- [x] 9.1 Emit `supports_audio_output` from `modalities.output` (true when `audio` is listed, explicit false when the output list omits it), add it to the sync comparison set, and cover it in the capability tests
- [x] 9.2 Verify `/model/info` `supported_openai_params` behavior on the live proxy, record the LiteLLM ≥ 1.109.1 prerequisite, and add a populate-time warning for existing reasoning rows whose stored list lacks `reasoning_effort`; never write a hardcoded list
- [x] 9.3 Decide and document the no-effort-level policy (`reasoning_effort_levels: []` with flags omitted), and align the explicit-false/modalities-missing rules between spec and design
- [x] 9.4 Document that LiteLLM's `reasoning_effort_rounding` defaults to `up` and is not set by the pipeline
- [x] 9.5 Re-run the offline suite and Ruff; record the live `/model/info` verification result in design.md
