# Design

## Context

See `proposal.md` for motivation. The current OpenCode adapter was written against an older `/models` response that returned IDs only: it reads `id`, scrapes the Go plan endpoint table for the native protocol, and sets `display_name` to the model ID. The live response now exposes 30 models with `name`, `canonical_id`, `api`, `limit.context`, `limit.output`, and `cost`.

Three concrete mismatches drive this design:

- `ProviderAdapter.fetch_all` drops models whose `endpoint_type` is not in the configured `supported_endpoints`; OpenCode's `responses`-native models are therefore discarded even though the gateway translates every text model to every API.
- `RawModel` has no canonical hint, so `map_models` exact-matches the model ID `deepseek-v4.1-flash` to AA's older `deepseek-v4-1-flash` entry (intelligence `null`) instead of the scored `deepseek-v4-1-flash-1017` entry.
- `OpenCodeAdapter.fetch_models` never sets `context_tokens`; `apply_limits` then overwrites `output_tokens` from models.dev and derives `input_tokens` only when context exists, leaving all OpenCode limits except output unset.

The Go plan documentation table still lists two models (`mimo-v2.5`, `mimo-v2.5-pro`) that are absent from `/models`; live probes return HTTP 410 with replacements. The docs table is therefore not a catalog source.

## Goals / Non-Goals

**Goals:**

- Extract all 30 live OpenCode text models with a deterministic mapping from native protocol to LiteLLM deployment protocol.
- Map OpenCode models to the AA variant named by the provider's own `canonical_id` before falling back to display name or model ID.
- Persist provider-published context and output limits, derive input limits, and record provenance.
- Make every pre-dedup drop visible in a per-provider census.
- Cover the behavior with offline adapter, mapper, and limits tests.

**Non-Goals:**

- Native Responses or Google generateContent routing through LiteLLM. The gateway's chat translation is the deployment path.
- Detecting workspace privacy gates automatically. Gated models remain in the catalog; `exclude.patterns` is the opt-out.
- Synthesizing models from the docs page when `/models` omits them.
- Changes to scoring, tier selection, other providers, or LiteLLM itself.

## Decisions

### 1. `/models` is the live catalog; the docs page is pricing-only

The adapter reads `id`, `name`, `canonical_id`, `limit.context`, `limit.output`, and the `api` keys from the JSON response. It no longer calls `parse_opencode_endpoints`; that parser and `_endpoint_type` are removed, because the docs endpoint table describes native protocols and is stale for deprecated models.

The docs page remains the pricing source: it is the only place that publishes the Go plan's per-model prices and peak/off-peak bands. The existing `parse_opencode_pricing` is unchanged and records its raw HTML for forensics.

Alternative considered: drive the model list from the docs endpoint table. Rejected because the table includes two deprecated models and is not the serving contract.

### 2. `endpoint_type` is the deployment protocol; `native_protocol` preserves the API metadata

`RawModel.endpoint_type` already determines the LiteLLM prefix and `api_base`. The adapter therefore sets:

- `messages` when the native `api` map contains `messages`;
- `chat` for every other native protocol (`chat-completions`, `responses`, `generate-content`).

A new `RawModel.native_protocol` records the native value (`chat`, `messages`, `responses`, `google`) for diagnostics and the snapshot. `to_litellm_deployment` needs no change: it already routes `messages` to the Anthropic prefix and base, and everything else to the chat prefix and base. `supported_endpoints` stays `["chat", "messages"]`, so the generic availability filter now passes all 30 models.

Alternative considered: keep `endpoint_type` native and override `available`/`to_litellm_deployment` in the OpenCode adapter. Rejected because it spreads provider-specific translation logic across two methods and weakens the documented meaning of `endpoint_type`.

The translation depends on OpenCode's documented guarantee that every text model works through every API. If that guarantee changes, the affected deployments fail visibly at request time; no silent fallback is added.

### 3. Canonical hints are tried before display name and model ID

Add `RawModel.canonical_hint` (default `""`) and persist it in `models_snapshot.json`. `map_models` changes its exact-match order to:

```
canonical_hint -> display_name -> model_id
```

The hint is normalized with the same `normalize_key` used for names, so a vendor-prefixed value such as `deepseek/deepseek-v4.1-flash-1017` resolves to `deepseekv41flash1017`. A hint that matches nothing is ignored and the existing candidates are tried; it never fails the run. The mapping method remains `exact` because this is still an exact normalized match.

The adapter sets `display_name` from the API `name` as well. That makes reports readable and gives the mapper a second chance (`DeepSeek V4.1 Flash 1017` normalizes to the same key). Pricing lookup already falls back from `display_name` to `model_id`, so the DeepSeek 1017 name does not break the price join.

Alternative considered: rely only on the API `name`. It fixes DeepSeek, but the `canonical_id` is the provider's explicit identity and is more precise when a display name carries marketing text. Keeping both costs one field.

### 4. Provider-published limits take precedence over models.dev

`OpenCodeAdapter.fetch_models` sets `context_tokens` and `output_tokens` from `limit`. `apply_limits` becomes provider-first:

- If `model.output_tokens` is already set, keep it, set `limits_source = "provider:<name>"`, and compute `input_tokens = context - output`.
- Otherwise use the existing models.dev resolution and source.
- If neither source yields output, leave the limit unset and flag `unresolved`.
- If output equals or exceeds context, keep input unset and add the existing output-vs-context flag; deduplicate flags.

The models.dev fallback and normalized lookup chain are unchanged. The only behavioral change is precedence and the new `provider:<name>` provenance value.

Alternative considered: keep models.dev as the output authority and only add context from the provider. Rejected because it ignores the provider's own output cap and leaves the same class of silent staleness.

### 5. Census is per-adapter state populated by `fetch_all`

Add a `FetchCensus` dataclass in `providers/base.py`:

```
provider, advertised, extracted,
unsupported_protocol: list[str], no_pricing: list[str]
```

`ProviderAdapter.fetch_all` populates `self.last_census` while it joins pricing and applies `available`. `OpenRouterAdapter.fetch_all` populates the same attribute in its own loop. The CLI prints one line per provider and writes `output/fetch-census.json`; the existing `fetch_all() -> list[RawModel]` signature is unchanged so current callers and tests keep working.

Alternative considered: return `(models, census)` or a result object. Rejected as a larger interface change for a diagnostic that is consumed immediately after the call. The hidden state is documented and overwritten on each fetch.

### 6. Deprecated docs-only models are not synthesized

The adapter iterates only `data` from `/models`. It does not parse the docs endpoint table for model IDs. The README/WALKTHROUGH note the verified 410 responses and tell readers that the live endpoint is the catalog.

### 7. Privacy-gated models are documented, not detected

Muse Spark 1.2/1.3 and Iceman Contributor Free return a specific 400 until the workspace enables "Allow paid endpoints that train on request data". The pipeline has no workspace-level privacy API, and probing every model on every run is out of scope. The change documents the gate and adds `exclude.patterns` examples (`contributor`, `iceman`) to the config template. Users who enable the setting can keep the models.

## Risks / Trade-offs

- **`endpoint_type` semantics change** -> Document it on `RawModel` and keep `native_protocol` in the snapshot. Any code that assumed `endpoint_type` meant native must read `native_protocol`.
- **Chat translation is an external guarantee** -> If OpenCode stops translating a native protocol, the deployment fails at request time. The census and provider docs make the dependency explicit; native routing is a follow-up.
- **Pricing still comes from HTML** -> The docs page can change shape. The existing raw-HTML forensic log remains; a future change can parse the API `cost` blocks instead.
- **Gated models can be selected** -> Muse Spark 1.3 may clear the Pro floor and fail until the gate is enabled. Mitigation: document the gate and the `contributor`/`iceman` exclude patterns; do not silently drop models.
- **`last_census` is mutable state** -> It is only read immediately after `fetch_all`. Tests assert it; no other code should cache it.
- **DeepSeek tier composition changes** -> The corrected 32.6 score can move models between Pro/Flash. The existing mappings review gate and dry-run populate remain the checkpoints.

## Migration Plan

1. Run `fetch` (or `refresh`) to regenerate `models_snapshot.json` with `canonical_hint` and `native_protocol`.
2. Review `mappings.csv`; `deepseek-v4.1-flash` should now map to `deepseek-v4-1-flash-1017` with method `exact`.
3. Run `score`; DeepSeek should appear in the model index and any tier it qualifies for.
4. Run `populate --dry-run`, then `populate`; existing deployments gain `max_input_tokens` and the new models are added.
5. Rollback is code-only: old snapshots load with empty hints/protocols, and no LiteLLM schema changes are involved.

## Open Questions

None. The deferred items (native routing, automatic privacy-gate detection, API-cost parsing) are explicit non-goals, not blockers.
