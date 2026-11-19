# Design

## Context

See `proposal.md` for motivation. The current pipeline:

- Stores one `api_key_env` per provider and sends `os.environ/<VAR>` in every deployment.
- Emits only pricing and token-limit fields in `model_info`.
- Groups same-price deployments under one `order` but does not emit the per-deployment fields LiteLLM needs to fail over inside that order.
- Compares and writes only the price, order, base-model, model-group, and token-limit fields during population.

LiteLLM 1.109.1 (verified live) provides the missing behavior:

- `model_info.reasoning_effort_levels` and the per-level reasoning flags drive `GET /model_group/info` and client enrichment.
- `model_info.allowed_fails` and `model_info.cooldown_time` bench a failing deployment; `litellm_params.num_retries` then re-selects a healthy sibling at the same `order`.
- `ORDER` fallback escalates to the next `order` only after the current order's pool is exhausted.

The OpenCode `opencode-models-discovery` plugin (latest 2.1.2) reads `/model/info` and builds variants from seven `supports_*_reasoning_effort` flags. It ignores `reasoning_effort_levels`; the seven flags are therefore required for exact harness behavior.

## Goals / Non-Goals

**Goals:**

- Emit correct multimodal, tool, structured-output, and reasoning metadata from the provider's own models.dev entry.
- Support one environment variable per provider containing a JSON array of keys, with fetch fallback and no per-key config.
- Expand selected deployments across provider keys after ranking, preserving NMB/top-K behavior.
- Emit the cooldown and retry defaults that make same-order latency pools fail over.
- Keep the pipeline idempotent, including key rotation and capability drift.
- Surface credential counts and capability warnings in artifacts and reports.

**Non-Goals:**

- Editing the root LiteLLM `config.yaml` automatically. The pipeline emits a suggested block only.
- Managing per-key `api_base`, `extra_headers`, or `plan`. One base, one plan, and one parameter set per provider.
- Changing LiteLLM proxy code.
- Adding capabilities that models.dev does not publish.
- Cross-provider capability fallback.
- Per-key NMB scoring or top-K accounting.

## Decisions

### 1. One JSON key list per provider

Provider config gains `api_keys_env: <ENV_NAME>`; the environment value is a JSON array:

```env
COMMANDCODE_APIS=["sk-a","sk-b","sk-c"]
OPENCODE_APIS=["sk-x","sk-y"]
```

- Parse with `json.loads`; fall back to comma-splitting only when the value is not a JSON array, for convenience.
- Trim entries, remove empties and duplicates, and warn.
- Keep `api_key_env` as a one-entry list for backward compatibility.
- An enabled provider with a missing or empty list fails the fetch phase; a disabled provider is skipped.
- Raw keys are passed to `/model/new`; the proxy does not need the provider variables in its own container. The populator reads them from `.env` through the existing `Config.load_env()`.

Alternative considered: a list of environment-variable names (`api_key_envs`). Rejected because adding a key would require a config edit, which the user explicitly wants to avoid.

### 2. Adapter-level fetch fallback

Add a shared helper on `ProviderAdapter` that performs a GET with key fallback:

```text
for slot, key in enumerate(keys, 1):
    try the request
    on 401/402/403/408/409/429/5xx/transport: record slot + status, continue
    on success: return response
raise RuntimeError with every slot's failure reason
```

- CommandCode and OpenCode use it for `/models`. OpenRouter's catalog is public; its key list is only used for population.
- Do not fall back on `400` or `404`.
- Record only the slot and fingerprint, never the raw key.
- Publish every configured key, including a slot that failed fetch: a temporarily exhausted key can be topped up later, and `allowed_fails: 0` benches a broken key on first use.

Alternative considered: publish only slots that passed the fetch probe. Rejected because a `402` or transient failure would remove a key that may recover before the next refresh.

### 3. Provider-only capability resolver

Add `capabilities.py` (or extend `limits.py`) that indexes the same models.dev catalog. Resolution order:

1. provider's own entry, exact model ID;
2. provider's own entry, normalized model ID;
3. otherwise unresolved — no cross-provider fallback.

Mapping:

| models.dev | LiteLLM `model_info` |
|---|---|
| `modalities.input` contains `image` | `supports_vision: true` |
| `pdf` | `supports_pdf_input: true` |
| `audio` | `supports_audio_input: true` |
| `video` | `supports_video_input: true` |
| `modalities.input` | `modalities.input` (exact list) |
| `modalities.output` | `modalities.output`; must contain `text` for a chat deployment |
| `modalities.output` contains `audio` | `supports_audio_output: true` (explicit `false` when the output list omits it) |
| `tool_call` | `supports_function_calling` |
| `structured_output` | `supports_response_schema` |
| `reasoning` | `supports_reasoning` |
| `reasoning_options[type=effort].values` | `reasoning_effort_levels` + seven per-level flags |
| `attachment` | ignored |

Unknown fields are omitted. When a `modalities.input` or `modalities.output` list is present, each media type the list omits is a declared `false` (for example, an input list of `text` and `image` writes `supports_audio_input: false`). When `modalities` is missing entirely, no modality field is written and `modalities_missing` is flagged. A missing provider entry records `capabilities_source: unresolved` and an `unresolved` flag.

Reasoning policy:

- Effort values published: emit `reasoning_effort_levels` in canonical order (`none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`) and emit all seven flags, `true` for published levels and `false` otherwise.
- `reasoning: true` with no effort values: emit `supports_reasoning: true`, emit `reasoning_effort_levels: []` (LiteLLM reports `supported_reasoning_efforts: []`, not `null`), omit the seven flags (OpenCode applies its default `low/medium/high`), and record `reasoning_levels_missing`.
- `reasoning: false`: emit `supports_reasoning: false`, empty `reasoning_effort_levels`, all flags `false`.

The seven flags are:

```json
"supports_none_reasoning_effort": false,
"supports_minimal_reasoning_effort": false,
"supports_low_reasoning_effort": true,
"supports_medium_reasoning_effort": true,
"supports_high_reasoning_effort": true,
"supports_xhigh_reasoning_effort": false,
"supports_max_reasoning_effort": false
```

`supports_medium_reasoning_effort` and `supports_high_reasoning_effort` are not LiteLLM fields; they pass through `model_info` and are read by the OpenCode plugin. LiteLLM's own resolver treats medium/high as unconditional and honors the other five plus `reasoning_effort_levels`.

Alternative considered: cross-provider fallback like token limits. Rejected because a model's media or reasoning support can differ by serving provider; copying another provider's entry would over-advertise.

### 4. Expand after selection, not before

Keep `RawModel` and `Deployment` as one model/provider unit through fetch, dedup, scoring, and selection. At emit/populate time, expand each selected deployment into one payload per provider key.

- Same `model_name`, `order`, `model`, `api_base`, prices, `num_retries`, and capability metadata.
- Unique `model_info.id` and `model_info.api_key_fingerprint`.
- No extra Pareto/NMB/top-K candidates.

Credential identity:

- Single-key provider: keep the existing `mp::<group>::<provider>::<model>` id.
- Additional keys: `mp::<group>::<provider>::key-<n>::<model>` where `n` is the one-based position in the JSON list.
- `api_key_fingerprint = sha256(raw_key)[:16]`.
- A key change at a slot changes only the fingerprint, so population PATCHes in place.
- Appending/removing keys adds/deletes slot deployments without changing the other slots.
- Reordering shifts slots; fingerprints change and are PATCHed in place. This is documented as positional slot identity.

Alternative considered: fingerprint in the id. Rejected because rotation would create a new deployment and split spend history. The chosen slot + fingerprint preserves history for the common rotation case.

### 5. Emit failover and retry defaults per deployment

The populator config gains a failover block:

```yaml
litellm:
  num_retries: 32
  allowed_fails: 0
  cooldown_time: 1800
```

Every deployment emits:

```json
"litellm_params": { "num_retries": 32 },
"model_info": { "allowed_fails": 0, "cooldown_time": 1800 }
```

The values are bootstrap defaults; the populator does not compute `keys - 1`, because the user wants a large safe value. The cooldown must exceed the worst-case walk:

```text
max_keys_per_order × attempts_per_key × timeout
```

With `allowed_fails: 0` and `InternalServerErrorAllowedFails: 1`, `attempts_per_key` is 2. The suggested router block records the relation in comments.

The root config is not edited. The pipeline writes `output/suggested_router_config.yaml` with:

```yaml
router_settings:
  routing_strategy: latency-based-routing
  routing_strategy_args:
    lowest_latency_buffer: 0
  timeout: 20
  cooldown_time: 1800
  allowed_fails: 5
  retry_policy:
    DefaultRetries: 32
    RateLimitErrorRetries: 32
    InternalServerErrorRetries: 32
    AuthenticationErrorRetries: 32
    BadRequestErrorRetries: 1
    NotFoundErrorRetries: 0
```

`retry_policy` is required because `402` is non-retryable by default. `model_group_retry_policy` remains available for exact per-group counts.

Alternative considered: compute `keys - 1` per group. Rejected because the key count is unknown at config time and varies by provider; a large safe value plus cooldown is simpler, and the extra budget is unused once the pool is exhausted.

### 6. Sync ownership and key rotation

Add to `_COMPARED_INFO_KEYS` and `_WRITABLE_INFO_KEYS`:

- `supports_vision`, `supports_pdf_input`, `supports_audio_input`, `supports_video_input`, `supports_audio_output`
- `modalities`
- `supports_function_calling`, `supports_response_schema`
- `supports_reasoning`, `reasoning_effort_levels`, all seven per-level flags
- `allowed_fails`, `cooldown_time`, `api_key_fingerprint`

Add to `_COMPARED_PARAM_KEYS`:

- `num_retries`

`api_key` remains excluded because `/model/info` masks it. The fingerprint is the rotation signal: when it differs, the update body includes the raw key and the new fingerprint, so the PATCH updates in place. Unknown capability fields are omitted from the PATCH body and therefore preserved.

Alternative considered: compare `api_key` directly. Not possible; the management API masks it.

### 6b. `supported_openai_params` is never hardcoded

Verified on the live proxy (LiteLLM **1.109.1**):

- A new deployment with no stored `model_info.supported_openai_params` returns a running-version computed list from `/model/info`; for `openai/...` that list has 32 entries including `reasoning_effort`.
- A deployment with a stored `supported_openai_params` returns that stored list verbatim from both `/model/info` and `/model_group/info`.
- PATCHing `supported_openai_params` to `null` does not clear it; setting `[]` stores an empty list. Neither restores the computed list.

Decision: the pipeline never writes `supported_openai_params`. New rows get the running proxy's computed list. An existing row whose stored list predates the running LiteLLM (for example, the old 32-entry list ending in `user` without `reasoning_effort`) keeps that stale advertisement. `sync.param_warnings()` reports such rows and tells the operator to recreate or refresh them. No hardcoded list is ever sent.

The observable contract is: a published reasoning deployment is discoverable with `reasoning_effort` in `/model/info`. The version prerequisite is LiteLLM ≥ 1.109.1 (verified live); older proxies may compute an older parameter set.

LiteLLM's `reasoning_effort_rounding` defaults to `up`. The pipeline does not set it, so a client asking `medium` on a `low/high/max` model gets `high`. This is documented as a LiteLLM default, not a pipeline setting.

### 7. Reports and artifacts

`tier-output.json` gains:

- per-deployment `credential_slot`, `api_key_fingerprint`
- per-group `credential_count`
- per-deployment `capabilities_source`, `capabilities_flags`

The Markdown and HTML reports show:

- a compact key count on multi-key groups;
- capability warnings (`unresolved`, `reasoning_levels_missing`, `non_chat_output`, contradictions) in the existing warnings section;
- no raw keys.

### 8. Testing

Offline:

- JSON list parsing (commas/quotes in keys, duplicates, empties, legacy single key).
- Fetch fallback for each status class, including all-fail and no-fallback-on-400/404.
- Capability mapping for every modality, tool/structured output, reasoning effort/toggle/false, missing provider entry, and contradictory data.
- Multi-key expansion: one key, N keys, same order, unique ids, fingerprints, post-selection count.
- Sync drift: capabilities, `allowed_fails`, `cooldown_time`, `num_retries`, fingerprint rotation, unknown preservation.
- Report rendering: key count and warnings, no key leakage.

Live smoke:

- Start LiteLLM with two fake keys at the same order and `allowed_fails: 0`.
- One key fails `500`/`402`; confirm the same request succeeds on the sibling.
- Confirm order escalation after both keys fail.
- Confirm `attempted_fallbacks`/spend logs and no key in logs.

## Risks / Trade-offs

- **Positional slot churn** → Keep key lists stable and append/remove at the end; document that reordering PATCHes every shifted slot. A future keyed list (`{label, key}`) could remove this limitation.
- **Aggressive cooldown** → `allowed_fails: 0` benches a key after one counted failure. The per-exception profile keeps one 500 retry (`InternalServerErrorAllowedFails: 1`) while `402`/`429`/`401` bench immediately.
- **Large `num_retries` + short cooldown** → Can cycle after the first key's cooldown expires. Keep `cooldown_time` above the worst-case pool walk and use the timeout formula.
- **Capability gaps** → Provider-only resolution may omit capabilities that another provider publishes. This is deliberate; the artifact flags it so the operator can add a manual override later.
- **Raw keys in the populate request** → The populator's HTTP client does not log request bodies, and the proxy encrypts keys at rest. Use HTTPS for a remote gateway and keep `.env` gitignored.
- **OpenCode plugin-specific flags** → The seven-flag contract is the plugin's current implementation. If a future plugin version reads `reasoning_effort_levels`, the extra flags remain harmless.
- **LiteLLM version dependency** → `reasoning_effort_levels`, the computed `reasoning_effort` parameter, and the cooldown behavior described here are verified on 1.109.1. An older proxy may ignore unknown fields, compute an older parameter set, or keep old rows' stored `supported_openai_params`; populate warns about those rows.
- **More deployments** → Each key adds a row and a potential retry attempt. NMB/top-K are unchanged; only runtime failover breadth grows.
- **Provider-level plan assumption** → A key on a different plan may not serve every published model. The user accepted one plan per provider; a future per-key plan can be added.

## Migration Plan

1. Add `api_keys_env` (or keep the existing `api_key_env`) and the failover bootstrap block to the populator config.
2. Run `fetch`, `score`, and `populate --dry-run`; review the capability fields, credential counts, and the new `output/suggested_router_config.yaml`.
3. Apply the suggested router block to the root `config.yaml` and restart/reload the proxy.
4. Apply populate. Existing single-key deployment ids are preserved; additional keys create new slot deployments.
5. Verify with a request that one key failure retries a sibling, and that all-sibling failure escalates to the next order.
6. Rollback: remove the extra keys and re-run populate (slot deployments are deleted), then restore the previous router settings.

## Open Questions

- Verify the auto-router order fallback on the live proxy (the 1.108 source uses `get_pre_routing_selection`); keep the manual `_target_order` fallbacks until then.
- Decide later whether to fork the OpenCode plugin to read `reasoning_effort_levels`; emitting the seven flags works today.
