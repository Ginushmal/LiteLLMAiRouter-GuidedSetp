# Proposal

## Why

OpenCode Go's live `/models` endpoint advertises 30 text models, but the pipeline extracts only 25. The five missing models are `responses`-native, and the adapter treats their native protocol as the only protocol even though OpenCode's gateway translates every text model to every API. Separately, the adapter discards the API's `name`, `canonical_id`, and `limit` fields, so `deepseek-v4.1-flash` maps to the stale September AA entry with no intelligence instead of the October 17 entry scored at 32.6 — and therefore never reaches the tier report or LiteLLM.

The API now publishes the identity, native protocol, context window, and output limit the pipeline needs. Using that payload fixes the missing models, the wrong DeepSeek variant, and the null `context_tokens` / `max_input_tokens` values without adding new provider integrations.

## What Changes

- OpenCode adapter reads the live `/models` payload as the primary source for `name`, `canonical_id`, `limit.context`, and `limit.output`; the Go plan docs remain the pricing source.
- `responses`-native and `generate-content`-native models are deployed through OpenCode's translated `chat/completions` path. `messages`-native models keep the native Anthropic path.
- Canonical deduplication tries a provider-supplied `canonical_hint` from `/models.canonical_id` before display-name and model-id matching. This maps `deepseek-v4.1-flash` to AA's `deepseek-v4-1-flash-1017` instead of `deepseek-v4-1-flash`.
- Token limit resolution prefers the provider-published context and output limits and falls back to models.dev. `max_input_tokens` is emitted for OpenCode deployments.
- Fetch reports a per-provider census: advertised, extracted, dropped for unsupported protocol, and dropped for missing pricing. Models are no longer dropped silently.
- OpenCode adapter tests use a checked-in fixture derived from the live `/models` payload, covering the 30-model catalog, DeepSeek 1017 mapping, limit propagation, and endpoint fallback.
- Provider docs and config comments drop the "responses/google deferred" claim and document the chat-translation path plus the existing `exclude.patterns` opt-out for privacy-gated contributor models.

**Non-goals:** native Responses/Google routing through LiteLLM, automatic detection of workspace privacy gates, merging docs-only models that are absent from `/models`, and changes to scoring, tier selection, or other providers.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `model-pipeline`: OpenCode model fetching, canonical exact matching, token-limit resolution, and fetch reporting.

## Impact

- `model-tier-populator/src/model_pipeline/providers/opencode.py` — read the live metadata and choose the deployment path.
- `model-tier-populator/src/model_pipeline/providers/base.py` — fetch census plumbing.
- `model-tier-populator/src/model_pipeline/models.py`, `emit/snapshot.py` — persist the canonical hint.
- `model-tier-populator/src/model_pipeline/dedup/mapper.py` — try the hint before display name/model id.
- `model-tier-populator/src/model_pipeline/limits.py` — prefer provider-published limits.
- `model-tier-populator/src/model_pipeline/cli.py` — print the census.
- `model-tier-populator/tests/test_opencode.py` — new regression coverage.
- `model-tier-populator/config.yaml`, `config.example.yaml`, `README.md`, `WALKTHROUGH.md` — corrected provider notes.
- No LiteLLM source, database schema, or management-API changes.
