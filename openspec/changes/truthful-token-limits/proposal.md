# Proposal: truthful-token-limits

## Why

Every pipeline-managed deployment is advertised with a context-sized output limit
(1,048,576 / 1,050,000) instead of its real one (e.g. 131,072 for MiMo). The pipeline
never states an output cap, so LiteLLM's model-info discovery fills the gap with
`context_length`. Clients reading `/v1/model/info` (notably OpenCode's model discovery)
then request completions no real model can produce — 256,000 tokens — and every usable
deployment rejects the request, so the whole fallback chain dies and the tier is
unusable. This was verified end-to-end against the running instance.

## What Changes

- Resolve each model's real **output token limit** from the public models.dev catalog:
  exact provider + model entry first, then a normalized-model-id match across the
  catalog. Model identities are never hardcoded in configuration.
- Derive the **input limit** as `context − output`, where the context window keeps
  coming from the provider's `/models` API (the provider publishes context, not input).
- Emit the resolved limits into each deployment's `model_info`
  (`max_output_tokens`, `max_tokens`, corrected `max_input_tokens`), so `/v1/model/info`
  reports real values and clients compute sane completion budgets.
- When a limit cannot be resolved, leave it unset and **warn loudly** — never invent a
  number.
- Make `populate` converge on `model_info` changes: the diff compares limit fields, and
  updates are applied through the PATCH model endpoint (the PUT endpoint ignores
  `model_info` entirely, so limit changes currently cannot land on existing rows).

Non-goals (explicitly out of scope):

- `custom_cost_map.json` — the running LiteLLM loads it via `LITELLM_MODEL_COST_MAP_URL`;
  removing or fixing it is a separate change.
- Client-side limit overrides in OpenCode.
- Asking the upstream provider to publish output limits in `/models` (the real long-term
  fix; tracked separately).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `model-pipeline`: adds a token-limit resolution requirement (models.dev-backed output
  limit, derived input limit, provenance, no invented values); the self-contained JSON
  output must carry the resolved limits; idempotent population must converge on
  `model_info` fields, not only `litellm_params`.

## Impact

- **model-pipeline source**: a new limits resolution step (models.dev fetch, cached as a
  scrape artifact like other sources), new fields on the normalized model records and
  deployment payload, populate diff + a PATCH-capable LiteLLM client, tests, and the
  walkthrough doc.
- **LiteLLM**: no change needed — configured `model_info` outranks discovered values
  (verified in the running proxy's source).
- **New external dependency**: `https://models.dev/api.json` (public, unauthenticated)
  becomes a fetch source of the pipeline.
- **Running instance**: after populate, `/v1/model/info` reports real limits per
  deployment and clients stop over-requesting output tokens.
