# Spec Delta

## ADDED Requirements

### Requirement: Provider key-list configuration and fetch fallback

The pipeline SHALL accept one environment-variable name per provider whose value is a JSON array of API keys. It SHALL use those keys in order when fetching the provider's model catalog, try the next key on authentication, payment, authorization, timeout, conflict, rate-limit, server, or transport failures, and fail the fetch phase only when every configured key fails. During population it SHALL publish every configured key, including a key that failed the fetch probe.

The existing single-key `api_key_env` setting SHALL remain supported as a one-key list.

#### Scenario: JSON key list is parsed

- **WHEN** a provider's configured key environment variable contains a JSON array of keys
- **THEN** the pipeline parses every entry, trims surrounding whitespace, rejects an empty result for an enabled provider, and never treats the raw value as one key

#### Scenario: Single-key configuration remains valid

- **WHEN** a provider is configured with the legacy `api_key_env` setting and no key-list setting
- **THEN** the pipeline treats it as a one-entry key list and behaves exactly as before

#### Scenario: Fetch falls back to the next key

- **WHEN** the provider's `/models` request returns `401`, `402`, `403`, `408`, `409`, `429`, a `5xx`, or fails at the transport layer
- **THEN** the pipeline retries the request with the next configured key, in list order

#### Scenario: Fetch does not fall back on a client error

- **WHEN** the provider's `/models` request returns `400` or `404`
- **THEN** the pipeline fails the request without trying another key, because the endpoint or request is wrong rather than the key

#### Scenario: All keys fail

- **WHEN** every configured key fails the `/models` request
- **THEN** the fetch phase fails loudly with a summary naming each key's slot and failure reason, and does not return an empty catalog as success

#### Scenario: At least one key works

- **WHEN** at least one configured key returns the provider's model catalog
- **THEN** the fetch phase succeeds with that catalog, records the failed slots in its report, and population still emits every configured key

#### Scenario: Duplicate or empty key entries

- **WHEN** the parsed key list contains duplicate keys or empty entries
- **THEN** the pipeline removes the duplicates and empty entries, emits a warning, and keeps the first occurrence's slot

#### Scenario: Keys never appear in logs or artifacts

- **WHEN** the pipeline records a fetch attempt or publishes a deployment
- **THEN** logs, `tier-output.json`, and reports identify the key only by its slot or fingerprint, never by the raw key value

### Requirement: Model capability metadata resolution

The pipeline SHALL resolve each model's capability metadata from the provider's own models.dev catalog entry, using the same provider-entry lookup as token limits but without the cross-provider fallback. It SHALL emit the LiteLLM `model_info` fields for supported input modalities, output modalities, tool calling, structured output, and reasoning. It SHALL NOT use another provider's catalog entry for capabilities and SHALL NOT infer a capability the provider's entry does not declare.

#### Scenario: Media input and output modalities

- **WHEN** the provider's catalog entry declares `text`, `image`, `pdf`, `audio`, or `video` in `modalities.input`, or `text`/`audio` in `modalities.output`
- **THEN** the pipeline emits `modalities.input`/`modalities.output`, sets `supports_vision` for `image`, `supports_pdf_input` for `pdf`, `supports_audio_input` for `audio`, and `supports_video_input` for `video`, and writes explicit `false` for a media type the input list omits
- **AND** when `modalities.output` is present, it sets `supports_audio_output` to `true` when `audio` is listed and explicit `false` when the output list omits it

#### Scenario: Modalities declaration is missing

- **WHEN** the provider's own entry has no `modalities` declaration
- **THEN** the pipeline writes no modality field and records a `modalities_missing` capability flag

#### Scenario: Tool calling and structured output

- **WHEN** the provider's catalog entry declares `tool_call` or `structured_output`
- **THEN** the pipeline emits `supports_function_calling` and `supports_response_schema` respectively, and emits explicit `false` when the entry declares the capability false

#### Scenario: Provider entry is missing

- **WHEN** the provider's own models.dev entry is missing
- **THEN** the pipeline omits every capability field, records `capabilities_source` as unresolved, adds an `unresolved` capability flag, and still publishes the deployment

#### Scenario: Another provider has the model

- **WHEN** the provider's own entry is missing but another provider's entry describes the same model
- **THEN** the pipeline SHALL NOT copy that entry's capability metadata and SHALL record the unresolved capability flag

#### Scenario: Reasoning with published effort levels

- **WHEN** the provider's entry declares `reasoning: true` and publishes one or more `reasoning_options` entries of type `effort`
- **THEN** the pipeline emits `supports_reasoning: true`, emits the published values as `reasoning_effort_levels` in canonical order, and emits the seven per-level flags with `true` for published levels and `false` for unpublished levels

#### Scenario: Reasoning without published effort levels

- **WHEN** the provider's entry declares `reasoning: true` but publishes no effort-valued `reasoning_options`
- **THEN** the pipeline emits `supports_reasoning: true`, emits `reasoning_effort_levels: []` (LiteLLM reports `supported_reasoning_efforts: []`, not `null`), omits the seven per-level flags so the harness may apply its own defaults, and records a `reasoning_levels_missing` capability flag

#### Scenario: Reasoning explicitly false

- **WHEN** the provider's entry declares `reasoning: false`
- **THEN** the pipeline emits `supports_reasoning: false`, emits an empty `reasoning_effort_levels`, and emits all seven per-level flags as `false`

#### Scenario: Non-chat output

- **WHEN** the provider's entry declares output modalities that do not include `text`
- **THEN** the pipeline does not publish the model as a chat deployment and records the reason in its report

#### Scenario: Attachment is not a media declaration

- **WHEN** the provider's entry declares `attachment: true` but does not declare a specific input modality
- **THEN** the pipeline SHALL NOT infer image, PDF, audio, or video support from `attachment` alone

#### Scenario: Capability provenance is recorded

- **WHEN** the score phase writes `tier-output.json`
- **THEN** every deployment records `capabilities_source` (for example `models.dev:commandcode` or `unresolved`) and `capabilities_flags`, so a reviewer can audit why a capability was emitted or omitted

### Requirement: Reasoning parameter advertisement

A published reasoning deployment SHALL be discoverable with `reasoning_effort` in the `supported_openai_params` returned by `/model/info`. The pipeline SHALL NOT write a hardcoded `supported_openai_params` list; it relies on the running LiteLLM to compute the list for deployments that have none stored. When an existing deployment's stored list lacks `reasoning_effort`, population SHALL warn the operator to recreate or refresh that row.

#### Scenario: New reasoning deployment

- **WHEN** a reasoning deployment is created on LiteLLM 1.109.1 or later without a stored `supported_openai_params`
- **THEN** `/model/info` returns the running version's computed list, including `reasoning_effort`

#### Scenario: Stale stored parameter list

- **WHEN** an existing reasoning deployment's stored `supported_openai_params` lacks `reasoning_effort`
- **THEN** population emits a warning naming the deployment and does not write a hardcoded replacement list

#### Scenario: Pipeline never pins the parameter list

- **WHEN** the pipeline builds a LiteLLM payload
- **THEN** it SHALL NOT set `model_info.supported_openai_params`

### Requirement: Multi-key deployment expansion and credential identity

After tier selection and before LiteLLM population, the pipeline SHALL expand each selected model/provider deployment into one deployment per configured provider key. Every sibling SHALL share the model name, model ID, API base, prices, order, retry budget, and capability metadata. Siblings SHALL differ only by their API key, `model_info.id`, and non-secret `api_key_fingerprint`.

A single-key provider SHALL keep the deployment's existing `model_info.id`. Additional keys SHALL use a stable `key-<n>` slot suffix where `n` is the key's one-based position in the provider's key list. Expansion SHALL NOT create additional Pareto, NMB, or top-K candidates.

#### Scenario: One key

- **WHEN** a selected model's provider has one configured key
- **THEN** the pipeline emits exactly one deployment, with the same `model_info.id` it used before key lists existed

#### Scenario: Multiple keys

- **WHEN** a selected model's provider has N configured keys
- **THEN** the pipeline emits N deployments with the same `model_name`, `order`, model, API base, prices, retry budget, and capability metadata; each has a unique `model_info.id` and its own `api_key_fingerprint`

#### Scenario: Selection is unchanged

- **WHEN** the same models are selected with one key versus several keys
- **THEN** the Pareto state, NMB scores, selected groups, and order assignments are identical; only the emitted deployment count changes

#### Scenario: Fingerprint identifies the key without exposing it

- **WHEN** the pipeline emits a deployment
- **THEN** `model_info.api_key_fingerprint` contains a non-secret digest prefix of the raw key, and no raw key appears in the artifact or report

#### Scenario: Key rotation updates in place

- **WHEN** the key at a slot changes between runs
- **THEN** the slot's deployment keeps its `model_info.id`, its fingerprint changes, and population PATCHes the existing deployment with the new key

#### Scenario: Key added or removed

- **WHEN** a key is appended to or removed from the provider's key list
- **THEN** the pipeline creates or deletes the corresponding slot deployment without changing the other slots' identities

#### Scenario: Duplicate keys

- **WHEN** two entries in the key list contain the same key
- **THEN** the pipeline publishes one deployment for that key and warns about the duplicate

### Requirement: Same-order latency pool failover

The pipeline SHALL emit every deployment of a same-NMB group with the same `order` so LiteLLM's latency routing can choose among them. It SHALL emit per-deployment `model_info.allowed_fails` and `cooldown_time`, and `litellm_params.num_retries` from configured bootstrap values, so a failed key is cooled down and the same request retries another sibling at the same order before the next order is attempted.

#### Scenario: Same-order siblings form one pool

- **WHEN** a tier selects a model with several provider keys at the same NMB
- **THEN** every sibling carries the same `order` and the same model group name

#### Scenario: Failed key is retried on a sibling

- **WHEN** a request fails on one same-order key and that key's failure count exceeds `allowed_fails`
- **THEN** the key enters cooldown and the router's retry selects another healthy sibling at the same order

#### Scenario: All siblings exhausted

- **WHEN** every same-order sibling has failed or is in cooldown
- **THEN** the router escalates to the next order, and the next model is tried only after the current order's pool is exhausted

#### Scenario: Bootstrap values are emitted

- **WHEN** the populate payload is assembled
- **THEN** each deployment carries the configured `allowed_fails`, `cooldown_time`, and `num_retries` values, and those values are part of the pipeline's owned comparison fields

#### Scenario: Single-deployment group

- **WHEN** a model group has only one deployment
- **THEN** the pipeline still emits the configured failover values, and LiteLLM's single-deployment safety behavior remains authoritative

### Requirement: Population convergence and provenance

The pipeline SHALL compare and write capability, credential, cooldown, and retry fields on existing deployments. It SHALL PATCH a deployment in place when its `api_key_fingerprint` changes, and SHALL preserve stored capability fields that the current run cannot resolve.

`tier-output.json` SHALL record each deployment's key slot and fingerprint, each group's credential count, and each deployment's capability source and flags. The readable reports SHALL show a compact key count and the capability warnings without exposing any key.

#### Scenario: Capability drift converges

- **WHEN** a stored deployment's capability fields differ from the current desired values
- **THEN** population PATCHes the deployment with the new fields

#### Scenario: Unknown capability is preserved

- **WHEN** a capability cannot be resolved on the current run
- **THEN** the pipeline omits it from the PATCH body and the stored value is not cleared

#### Scenario: Fingerprint drift converges

- **WHEN** a stored deployment's `api_key_fingerprint` differs from the desired fingerprint
- **THEN** population PATCHes that deployment in place with the new key and fingerprint

#### Scenario: Failover and retry drift converges

- **WHEN** `allowed_fails`, `cooldown_time`, or `num_retries` differ from the desired configuration
- **THEN** population detects the difference and PATCHes the deployment

#### Scenario: Artifact carries credential and capability provenance

- **WHEN** the score phase writes `tier-output.json`
- **THEN** each deployment records its key slot and fingerprint, each group records its credential count, and each deployment records `capabilities_source` and `capabilities_flags`

#### Scenario: Reports expose counts and warnings, not keys

- **WHEN** the Markdown or HTML report renders a multi-key group
- **THEN** it shows the key count and any capability warnings, and no raw API key
