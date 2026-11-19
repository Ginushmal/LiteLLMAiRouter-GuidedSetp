# Proposal

## Why

Auto-populated LiteLLM deployments currently carry only pricing and token-limit metadata. Clients that read `/model/info` — including the OpenCode model-discovery plugin — therefore see text-only models with no reasoning effort levels, even when the provider supports images, PDFs, audio, video, or reasoning. The pipeline also supports only one API key per provider, so a model group cannot fail over across several accounts or keys of the same model.

LiteLLM 1.109.1 (verified live) already provides the metadata fields and the routing behavior needed to fix both gaps. The pipeline must emit those fields, duplicate each selected model across its provider's keys, and give the operator the failover defaults that make same-order latency routing work.

## What Changes

- **Provider key lists.** Replace the single `api_key_env` with `api_keys_env`: one environment variable holding a JSON array of raw keys. The old `api_key_env` remains supported as a one-key fallback.
- **Fetch key fallback.** Fetch a provider's `/models` with the keys in order. Try the next key on `401/402/403/408/409/429/5xx` and transport errors; do not fall back on `400/404`. Only fail the phase when every key fails. Publish every configured key, including one that failed during fetch, so a topped-up key works without a re-run.
- **Capability metadata.** Resolve capabilities from the provider's own models.dev entry only (no cross-provider fallback): `modalities`, `reasoning`, `reasoning_options`, `tool_call`, and `structured_output`. Emit `supports_vision`, `supports_pdf_input`, `supports_audio_input`, `supports_video_input`, `supports_audio_output`, `modalities`, `supports_function_calling`, `supports_response_schema`, `supports_reasoning`, `reasoning_effort_levels`, and the seven per-level reasoning flags used by LiteLLM and the OpenCode discovery plugin.
- **No invented metadata.** Omit unknown capability fields; write explicit `false` only when the catalog says false. Record `capabilities_source` and `capabilities_flags` in `tier-output.json` and surface warnings in the reports.
- **Unpublished reasoning levels.** A model with `reasoning: true` but no published effort values emits `supports_reasoning: true` and omits the per-level flags, so the OpenCode plugin applies its default `low/medium/high` variants. It is flagged `reasoning_levels_missing`; the advertised LiteLLM group reports no known levels.
- **Multi-key expansion.** After NMB selection, duplicate each selected model/provider deployment once per provider key. All siblings share `model_name`, `order`, `model`, `api_base`, costs, `num_retries`, and capability metadata. They differ only by `api_key`, `model_info.id`, and `api_key_fingerprint`. Expansion happens after selection, so additional keys do not affect Pareto/NMB/top-K.
- **Credential identity.** Single-key deployments keep their existing `model_info.id`. Additional keys receive a stable `key-<n>` slot suffix. `model_info.api_key_fingerprint` (SHA-256 prefix, non-secret) lets the sync PATCH the deployment in place when the key at that slot rotates.
- **Failover defaults.** Emit `model_info.allowed_fails` and `cooldown_time`, and `litellm_params.num_retries` from a pipeline bootstrap value, on every deployment. Add these fields to the sync comparison/write sets so changes converge.
- **Suggested router configuration.** Emit a reviewable `output/suggested_router_config.yaml` block with the required `routing_strategy: latency-based-routing`, `timeout`, `cooldown_time`, `retry_policy` (including `402`), and retry counts. The pipeline never edits the root `config.yaml`.
- **Spec alignment.** Extend the same-NMB ordering requirement with a same-order latency pool/failover requirement, and add scenarios for key-list fetch fallback, capability metadata, and multi-key expansion.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `model-pipeline`: provider key-list configuration and fetch fallback; capability metadata resolution and emission; multi-key expansion after selection; failover defaults (`allowed_fails`, `cooldown_time`, `num_retries`); sync convergence for the new fields and key rotation; artifact/report fields; routing requirement wording.
- `tier-report`: show per-group key counts and capability provenance/warnings in the HTML report, matching the Markdown report.

## Impact

- **Configuration:** `model-tier-populator/config.yaml` gains `api_keys_env` per provider and a failover block with the `num_retries`, `allowed_fails`, `cooldown_time`, and timeout bootstrap values. Existing `api_key_env` configurations keep working.
- **Provider adapters:** `providers/base.py`, `commandcode.py`, `opencode.py`, and `openrouter.py` gain key-list fetch fallback and capability-aware deployment assembly. OpenRouter's catalog remains public; its key list is only used for populate.
- **Pipeline:** `models.py`, `limits.py` or a new capability resolver, `scoring/pipeline.py`, `emit/output.py`, `populate/sync.py`, `emit/report.py`, and `emit/html_report.py` carry the new fields and the multi-key expansion.
- **Artifacts:** `tier-output.json` gains credential counts/aliases, fingerprints, capability provenance, and capability flags. `output/suggested_router_config.yaml` is new.
- **LiteLLM:** no proxy code changes. Operators apply the suggested router block to the root `config.yaml`; the proxy must use LiteLLM 1.109.1 or later for the computed `reasoning_effort` parameter, `reasoning_effort_levels`, and cooldown behavior.
- **Tests:** offline fixtures for capability parsing (missing/contradictory data), multi-key expansion, fetch fallback, and sync drift/key rotation; a live smoke test with two fake keys to verify same-request sibling failover and order escalation.
- **Docs:** the LiteLLM learnings and setup guides are updated separately with the user-facing concepts and Admin UI steps; no populator internals belong there.
