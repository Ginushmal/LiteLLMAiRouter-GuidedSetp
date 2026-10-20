# Design

## Context

See `proposal.md` for motivation. The pipeline's phases are fetch (provider adapters →
normalized model records) → score (deployments + LiteLLM payloads) → populate
(`tier-output.json` → LiteLLM management API). Today only the provider's
`context_length` is captured and it is written as `model_info.max_input_tokens`; no
output limit is ever emitted.

Verified constraints that shape the approach:

- Provider `/models` APIs publish `context_length` (a combined window), never an output
  limit. CommandCode's pricing page "Caps" column carries plan markers, not limits.
- LiteLLM's model-info discovery fills a missing `max_output_tokens` with
  `context_length`, but configured `model_info` always wins over discovered values.
- The PUT model-update endpoint ignores `model_info` entirely; the PATCH
  `/model/{model_id}/update` endpoint merges `model_info` per-key and preserves fields
  the pipeline does not own.
- The client (OpenCode's model discovery) keeps one row per model name and reads
  `model_info.max_output_tokens` first when computing a completion budget.
- The models.dev catalog publishes `limit.output` per provider entry and covers all 92
  models the CommandCode provider API advertises (70 exact matches, 22 via normalized
  model-id match).

## Goals / Non-Goals

**Goals:**

- Every emitted deployment carries its real output limit and a correctly derived input
  limit, with the provider-published context window unchanged.
- Resolution is deterministic, source-auditable, and needs no per-model configuration.
- `populate` converges existing deployments onto the new limits, including rows created
  before this change.

**Non-Goals:**

- `custom_cost_map.json` (loaded by the running LiteLLM; separate change).
- Client-side limit overrides in OpenCode, or asking providers to publish output limits.
- Empirical probing of limits against live APIs (possible future addition).
- Controlling which deployment row a client picks to represent a tier — we guarantee
  every row is truthful, not that clients pick a particular one.

## Decisions

1. **models.dev is the only limit source.** No model identities in configuration, no
   cost-map reads. Alternatives rejected: per-model config overrides (models are injected
   via the API, hardcoding is policy), the cost map (out of scope and carries wrong
   values), live probing (costs quota, cannot test plan-gated models).

2. **Resolution order: provider entry → normalized model-id match.** The catalog's
   `canonical_model_id` lives *inside* an entry, so it cannot be read when the entry is
   missing; normalized-id matching reproduces the same coverage (verified 22/22).
   Normalization: case-insensitive, drop vendor prefix and serving-plan suffix, drop
   non-alphanumerics. A provider entry that exists but publishes no output limit is
   skipped, not trusted. When a fallback match is needed, the model vendor's own entry
   outranks a reseller's exact-id entry (xiaomi over vercel for `xiaomi/mimo-v2.5`), then
   exact ids come before normalized-only matches, then a stable order keeps runs
   reproducible. The mapping from pipeline provider to catalog provider id
   (e.g. `opencode` → `opencode-go`) is provider metadata in the pipeline config, not
   model data.

3. **Input limit = `context − output`; context stays provider-published.** The provider
   publishes a combined window, not an input limit. The relation reproduces the catalog's
   own input values exactly where both exist (1,050,000 − 128,000 = 922,000).

4. **Emit `max_output_tokens`, `max_tokens`, and `max_input_tokens`.** `max_tokens`
   mirrors the output limit (LiteLLM's own convention: `max_tokens` = output when known),
   which also blocks discovery's `max_tokens = context` fill from leaking into responses.

5. **Per-model truth only — no tier-wide envelope.** With truthful values, whichever row a
   client picks represents a real member's cap, so at least that member can serve the
   request and the fallback chain covers the rest. Advertise-the-weakest was considered
   and dropped: it under-sells capable members and is only needed when values are
   invented.

6. **Unresolved limits are left unset and flagged in the report; the model stays
   eligible.** Coverage is 100% today, so this is a rare path; silently shrinking tiers
   would be worse than an audible warning. Corrections for wrong catalog values go to
   models.dev itself (there is no local override mechanism by design).

7. **`populate` diffs pipeline-owned `model_info` fields and applies updates via PATCH.**
   Compared fields: `base_model`, `model_group`, `max_input_tokens`, `max_output_tokens`,
   `max_tokens`. Server-managed fields (ids, timestamps, member markers) are excluded so
   they never cause false diffs or get cleared.

8. **models.dev is fetched as a regular scrape artifact** (raw JSON saved, structured log
   entry), cached across runs like every other source, and refreshed only by the fetch
   phase.

9. **Deployment ids are URL-safe.** LiteLLM addresses a stored row by its id *in the
   request path* (`PATCH /model/{model_id}/update`), and the ASGI server decodes the path
   before routing, so an id containing `/` can never be addressed (the Admin UI cannot
   edit such a row either). `deployment_id` folds unsafe characters to `-`
   (`mp::pro-tier::commandcode::xiaomi-mimo-v2.6-pro`). Renaming the 12 existing
   slash-containing ids is handled by the ordinary diff as an add/delete pair.

## Risks / Trade-offs

- [Catalog values can be stale or wrong (entries where output equals the context look
  copied)] → provenance recorded per value; such entries are flagged in the report;
  under-reporting is the safe failure direction and corrections go upstream.
- [A model added by the marketplace before the catalog catches up resolves nowhere] →
  unresolved path (warn + unset + report entry), same as a catalog outage.
- [models.dev outage degrades resolution] → fetch degrades to "unresolved" per model and
  warns; scoring and population continue.
- [First rollout updates every existing deployment] → diff-driven one-shot pass; rollback
  is re-running populate against the previous `tier-output.json`, which converges back.
- [Client still picks one row per tier] → acceptable: with truthful rows no pick can
  produce a request size no member can serve (worst case one wasted fallback hop).

## Migration Plan

1. Implement with unit tests (resolution order, derivation, diff/PATCH behavior).
2. Re-run `score` to regenerate `tier-output.json` with limits and provenance.
3. Run `populate`; expect updates on pipeline-managed rows only. The first run also
   recreates the slash-containing ids under their URL-safe form, as add/delete pairs
   (adds are applied before deletes, so no model group is briefly empty).
4. Verify `GET /v1/model/info` reports the real limits, then refresh OpenCode's model
   discovery and confirm the next request carries a sane `max_completion_tokens`.
5. Rollback: populate from the previous `tier-output.json`.

## Open Questions

- Whether `output == context` catalog entries should be treated as unresolved instead of
  trusted (report-level flagging ships either way; the stricter rule can be decided after
  seeing how often it occurs).
