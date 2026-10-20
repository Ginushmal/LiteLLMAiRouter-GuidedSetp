# Spec Delta

## ADDED Requirements

### Requirement: Token limit resolution
Before emitting deployments, the pipeline SHALL resolve each model's real output token limit from the public models.dev catalog, and SHALL derive the input limit from the provider-published context window and the resolved output limit. The pipeline SHALL NOT hardcode model identities in configuration and SHALL NOT invent a token limit when resolution fails.

#### Scenario: Provider catalog entry resolves the output limit
- **WHEN** the models.dev catalog contains an entry for the pipeline's provider and model ID
- **THEN** that entry's published output limit SHALL be used as the model's output limit

#### Scenario: Normalized model-id fallback
- **WHEN** the catalog has no entry for the pipeline's provider and model ID that publishes an output limit
- **THEN** the pipeline SHALL look for another catalog entry with the same model ID after normalization (case-insensitive, ignoring vendor prefixes, punctuation, and serving-plan suffixes) and use its output limit when it publishes one

#### Scenario: Limits are provider-specific
- **WHEN** the same model ID appears under several catalog providers with different output limits
- **THEN** the entry for the pipeline's own provider SHALL win, and an entry from another provider SHALL be used only when the pipeline's provider has no entry that publishes an output limit

#### Scenario: Input limit is derived from context and output
- **WHEN** the provider publishes a context window and an output limit has been resolved
- **THEN** the input limit SHALL be `context − output`, while the context window itself remains the provider-published value

#### Scenario: Unresolved limits are never invented
- **WHEN** neither catalog lookup yields an output limit for a model
- **THEN** the pipeline SHALL leave the limit unset, flag the model as unresolved in its report, and continue with the remaining models

## MODIFIED Requirements

### Requirement: Self-contained JSON output
The pipeline SHALL produce a self-contained JSON artifact (`tier-output.json`) containing all data needed for LiteLLM population, including per-deployment provider details, pricing, intelligence scores, NMB scores, order assignments, target model group names, and resolved token limits.

#### Scenario: Complete populate fields
- **WHEN** the score phase writes `tier-output.json`
- **THEN** each deployment record SHALL include: canonical model name, provider name, provider model ID, API base URL, API key environment variable reference, endpoint format, model group name (e.g., "pro-tier"), order number, input/output/cache prices with provenance, intelligence score, cost_per_task, NMB score, tier assignment, context window, input limit, and output limit

#### Scenario: Re-populatable artifact
- **WHEN** the populate phase reads `tier-output.json`
- **THEN** it SHALL have sufficient information to create, update, or delete LiteLLM model entries via the management API without any additional data from the fetch or score phases

#### Scenario: Token limit provenance is recorded
- **WHEN** a deployment record carries a resolved output limit
- **THEN** the artifact SHALL record where the value came from (the pipeline's own provider catalog entry or a fallback match in another provider's entry) so a reviewer can audit it

### Requirement: Idempotent LiteLLM population
The pipeline SHALL populate LiteLLM's database via its management API in an idempotent manner — re-running populate with the same input produces no duplicate entries and converges to the desired state. Convergence SHALL cover both `litellm_params` and the pipeline-owned `model_info` fields (token limits, base model, model group), not only `litellm_params`.

#### Scenario: Diff-based population
- **WHEN** the populate phase runs
- **THEN** it SHALL first query `GET /model/info` to retrieve the current state, diff the desired state from `tier-output.json` against the current state across `litellm_params` and pipeline-owned `model_info` fields, and apply only the necessary changes (create new models, update changed models, delete removed models)

#### Scenario: Model info changes converge
- **WHEN** an existing deployment's pipeline-owned `model_info` fields differ from the desired state (for example its resolved token limits changed, or the stored row predates this change and carries no output limit)
- **THEN** populate SHALL detect the difference and apply it so the stored deployment converges to the desired state

#### Scenario: Updates persist model info without clearing other fields
- **WHEN** an update is applied to an existing deployment
- **THEN** it SHALL go through a management endpoint that persists `model_info` changes (the PUT model-update endpoint ignores `model_info`), and the update SHALL NOT clear `model_info` fields the pipeline does not own

#### Scenario: Per-provider deployment parameters
- **WHEN** creating or updating a LiteLLM model entry
- **THEN** the pipeline SHALL use the correct `litellm_params.model` prefix (e.g., `openai/`, `anthropic/`, `gemini/`) and `api_base` path for the provider's endpoint format (Chat Completions, Responses, Messages, or Google)

#### Scenario: No custom cost map required
- **WHEN** populating LiteLLM with pipeline-managed models
- **THEN** pricing SHALL be set inline via `litellm_params` fields (`input_cost_per_token`, `output_cost_per_token`, etc.) or `model_info` fields, and the pipeline SHALL NOT require entries in `custom_cost_map.json` for these models
