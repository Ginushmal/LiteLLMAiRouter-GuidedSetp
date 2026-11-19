# Spec Delta

## ADDED Requirements

### Requirement: OpenCode live catalog fidelity

The OpenCode adapter SHALL treat the live `/models` response as the authoritative catalog for model identity, native protocol, context window, and output limit. It SHALL include every live text model, including models whose native protocol is Responses or Google generateContent, because OpenCode's gateway translates every text model to every supported API. The documentation page SHALL remain the pricing source and SHALL NOT be used to synthesize models that are absent from `/models`.

#### Scenario: Live models carry API identity and limits

- **WHEN** the OpenCode `/models` response contains `name`, `canonical_id`, `limit.context`, and `limit.output` for a model
- **THEN** the adapter SHALL record `name` as the display name, `canonical_id` as the canonical hint, `limit.context` as the context window, and `limit.output` as the output limit for that model

#### Scenario: Responses-native models are fetched

- **WHEN** a model's `api` metadata lists only `responses`
- **THEN** the adapter SHALL include the model in the fetch result and SHALL deploy it through the gateway's `chat/completions` path instead of dropping it as unsupported

#### Scenario: Google-native models are fetched

- **WHEN** a model's `api` metadata lists `generate-content`
- **THEN** the adapter SHALL include the model in the fetch result and SHALL deploy it through the gateway's `chat/completions` path

#### Scenario: Messages-native models keep the native path

- **WHEN** a model's `api` metadata lists `messages`
- **THEN** the adapter SHALL deploy it with the Anthropic Messages prefix and base URL

#### Scenario: Deprecated docs-only models are not synthesized

- **WHEN** a model appears in the Go plan documentation table but not in the live `/models` response
- **THEN** the pipeline SHALL NOT create a model record for it

### Requirement: Provider-supplied canonical hints

The pipeline SHALL use a provider-supplied canonical identifier as the first exact-match candidate when mapping a provider model to an Artificial Analysis canonical identity. The hint SHALL be normalized with the same rules as display names and model IDs, and a hint that matches no canonical SHALL fall back to the existing display-name and model-ID matching without failing the run.

#### Scenario: Hint resolves a dated variant

- **WHEN** a provider model supplies canonical hint `deepseek/deepseek-v4.1-flash-1017` and the catalog contains both `deepseek-v4-1-flash` and `deepseek-v4-1-flash-1017`
- **THEN** the mapping SHALL select `deepseek-v4-1-flash-1017` with method `exact`

#### Scenario: Unknown hint falls back

- **WHEN** a provider model supplies a canonical hint that matches no catalog entry
- **THEN** the pipeline SHALL attempt the existing display-name and model-ID exact matches and SHALL NOT fail the run solely because of the hint

### Requirement: Fetch coverage census

The fetch phase SHALL report, per provider, how many models were advertised, extracted, dropped for an unsupported protocol, and dropped for missing pricing. A model dropped before deduplication SHALL appear in this census so its absence is visible in the console output and artifacts.

#### Scenario: Census reports extracted and dropped counts

- **WHEN** the OpenCode adapter advertises 30 models and extracts all of them
- **THEN** the fetch output SHALL report 30 advertised and 30 extracted, with zero unsupported and zero missing-pricing

#### Scenario: Unsupported protocol drop is visible

- **WHEN** a provider advertises a model whose native protocol is not supported and has no configured translation
- **THEN** the census SHALL count it under unsupported protocol and the model SHALL NOT be silently omitted

#### Scenario: Missing pricing drop is visible

- **WHEN** a provider advertises a model with no matching pricing row
- **THEN** the census SHALL count it under missing pricing and the model SHALL NOT be silently omitted

## MODIFIED Requirements

### Requirement: Token limit resolution

Before emitting deployments, the pipeline SHALL resolve each model's real output token limit from the provider's published limit when the provider publishes one, and otherwise from the public models.dev catalog. It SHALL derive the input limit from the provider-published context window and the resolved output limit. The pipeline SHALL NOT hardcode model identities in configuration and SHALL NOT invent a token limit when resolution fails.

#### Scenario: Provider-published output limit takes precedence

- **WHEN** the provider's `/models` response publishes an output limit for a model
- **THEN** that value SHALL be used as the model's output limit

#### Scenario: Provider catalog entry resolves the output limit

- **WHEN** the provider publishes no output limit and the models.dev catalog contains an entry for the pipeline's provider and model ID
- **THEN** that entry's published output limit SHALL be used as the model's output limit

#### Scenario: Normalized model-id fallback

- **WHEN** the catalog has no entry for the pipeline's provider and model ID that publishes an output limit
- **THEN** the pipeline SHALL look for another catalog entry with the same model ID after normalization (case-insensitive, ignoring vendor prefixes, punctuation, and serving-plan suffixes) and use its output limit when it publishes one

#### Scenario: Limits are provider-specific

- **WHEN** the same model ID appears under several catalog providers with different output limits
- **THEN** the entry for the pipeline's own provider SHALL win, and an entry from another provider SHALL be used only when the pipeline's provider has no entry that publishes an output limit

#### Scenario: Input limit is derived from context and output

- **WHEN** the provider publishes a context window and an output limit has been resolved
- **THEN** the input limit SHALL be `context - output`, while the context window itself remains the provider-published value

#### Scenario: Unresolved limits are never invented

- **WHEN** neither the provider nor any catalog lookup yields an output limit for a model
- **THEN** the pipeline SHALL leave the limit unset, flag the model as unresolved in its report, and continue with the remaining models
