# model-pipeline Specification

## Purpose

Provides a reusable multi-phase pipeline that fetches LLM model catalogs from multiple providers, deduplicates them to canonical identities, scores them by intelligence and cost-efficiency, ranks them into tiers, and populates a LiteLLM router database — all without restarting the proxy or editing config files.

## Requirements

### Requirement: Multi-provider model fetching
The pipeline SHALL fetch available model lists and pricing data from configured LLM providers (CommandCode and OpenCode) using their respective API endpoints and pricing documentation pages. Each provider SHALL use a dedicated adapter implementing a common interface that returns normalized model records with identity, pricing, context window, and endpoint metadata.

#### Scenario: Fetch CommandCode models
- **WHEN** the pipeline runs the fetch phase with the CommandCode adapter configured
- **THEN** it retrieves the model list from `api.commandcode.ai/provider/v1/models` and pricing from `commandcode.ai/models`, returning normalized records with model ID, input/output/cache prices, context window, and supported endpoints

#### Scenario: Fetch OpenCode models
- **WHEN** the pipeline runs the fetch phase with the OpenCode adapter configured
- **THEN** it retrieves the model list from `opencode.ai/inference/go/v1/models` and pricing from the Go plan documentation page, returning normalized records with model ID, input/output/cache prices, context window, and endpoint type (Chat Completions, Responses, Messages, or Google)

#### Scenario: Pricing normalization
- **WHEN** a provider publishes context-tiered pricing (different prices at different context lengths)
- **THEN** the pipeline SHALL compute the average of the tier prices for cost calculation
- **WHEN** a provider publishes peak and off-peak pricing windows
- **THEN** the pipeline SHALL compute a weighted average based on the proportion of the configured active window that overlaps each pricing band
- **WHEN** a provider publishes discounted or promotional prices alongside list prices
- **THEN** the pipeline SHALL use the effective (discounted) price

#### Scenario: Structured scraping logs
- **WHEN** the pipeline fetches data from a provider
- **THEN** it SHALL save the raw fetched content (HTML or JSON) to disk alongside a structured log entry recording the URL, timestamp, HTTP status, parse result count, and any errors — enabling AI-assisted debugging if the provider's page structure changes

### Requirement: Canonical model deduplication
The pipeline SHALL map each provider model name to a canonical model identity from the Artificial Analysis model catalog. The canonical identity SHALL be a compound key of base model name and variant (parameter count, effort level, thinking mode, etc.) to prevent cross-matching between different variants (e.g., qwen3-4b vs qwen3-26b, mimo-2.6 vs mimo-2.6-high).

#### Scenario: Exact match (100% confidence)
- **WHEN** a provider model name matches a canonical model name exactly after normalization (lowercase, strip provider prefix, strip date/size suffixes)
- **THEN** the mapping is recorded with method "exact" and confidence 1.0

#### Scenario: Jev classifier for ambiguous names
- **WHEN** a provider model name does not match any canonical name exactly
- **THEN** the pipeline SHALL pre-filter the AA canonical list to a manageable candidate set (approximately 80 candidates) purely by name similarity (vendor name, model family, token overlap), WITHOUT excluding candidates on variant signals, and SHALL force-include the nearest canonical slug so the most obvious candidate is never lost to ranking noise
- **THEN** it SHALL call the Jev (TypeSafe) Choice classifier with the provider model name as state and the candidate list as choice options — each option description carrying that canonical's variant (parameter count, effort level) — plus an "unmapped" option
- **THEN** the classifier SHALL return the best-matching canonical name, a confidence score (0–1), and a full probability distribution

#### Scenario: Low-confidence mappings are still recorded
- **WHEN** Jev returns a mapping with confidence below the configured threshold
- **THEN** the mapping SHALL still be recorded in the output with the confidence value marked, NOT discarded — the human reviewer decides whether to accept or override it

#### Scenario: Variant disambiguation is delegated to Jev
- **WHEN** a provider model name contains variant signals (parameter count like "4b" or "26b", effort level like "high" or "max")
- **THEN** the pipeline SHALL NOT programmatically reject candidate matches on variant grounds; the Jev instructions SHALL state the exact-match rules (never merge different parameter sizes or effort levels; a bare provider name maps to the base/default variant) and the choice options SHALL carry each variant's description so Jev disambiguates
- **THEN** any residual ambiguity is surfaced through the confidence score and the human review gate, not by a hard programmatic filter

#### Scenario: Serving and version suffixes do not change identity
- **WHEN** a provider model name differs from a canonical only by a trailing serving token (`-fast`, `-highspeed`, `-ultraspeed`, `-turbo`), or the canonical carries a version suffix (`-next`, `-latest`) the provider name lacks
- **THEN** the pipeline SHALL resolve it deterministically: strip a trailing serving token from the provider name and retry the exact match, and treat `-next`/`-latest` as version suffixes stripped from both sides
- **THEN** a canonical that lists the full name as a distinct entry (e.g. `grok-4-fast`) SHALL still win the full-name exact match first, so distinct fast/serving models are never merged into the base

#### Scenario: Mappings checkpoint CSV
- **WHEN** the fetch phase completes deduplication
- **THEN** it SHALL write all mappings to a CSV file with columns for provider name, provider model ID, canonical AA slug, canonical AA name, variant, match method, confidence score, and an empty "override" column for manual corrections
- **AND** the pipeline SHALL halt and wait for human review of this CSV before the score phase can proceed

### Requirement: Human review gate between phases
The pipeline SHALL execute as three independent invocations (fetch, score, populate) with clean artifact-based handoffs. Each phase reads its inputs from files on disk and writes its outputs to files on disk. Later phases can be re-run without re-running earlier phases.

#### Scenario: Three separate invocations
- **WHEN** the user invokes the pipeline
- **THEN** fetch, score, and populate are three separate commands that can be run independently, each reading from and writing to persistent artifacts

#### Scenario: Combined run
- **WHEN** the user wants an unattended run (e.g. on a schedule)
- **THEN** the pipeline SHALL provide a single `run` command that executes fetch, score, and populate in sequence and stops at the first phase that fails; this bypasses the human-review gates, which remain available through the individual commands

#### Scenario: Re-run populate without recompute
- **WHEN** the populate phase has been run and the LiteLLM database is subsequently cleared or corrupted
- **THEN** the user SHALL be able to re-run populate using the existing `tier-output.json` without re-running fetch or score

#### Scenario: Override-aware re-scoring
- **WHEN** the human reviewer edits the mappings CSV (changing a canonical assignment or overriding a confidence-scored row)
- **THEN** the score phase SHALL use the manual overrides in preference to the automatically computed mappings

### Requirement: Cost-per-task computation
The pipeline SHALL compute a per-deployment cost-per-task that reflects both the model's token efficiency (from Artificial Analysis benchmark data) and the specific provider's pricing, including cache effects.

#### Scenario: AA Pro tier (per-token re-price)
- **WHEN** AA Pro tier data is available (per-task token counts and cost breakdown)
- **THEN** the pipeline SHALL derive per-task token counts by type (input, reasoning, answer) from AA's benchmark data and re-price them at the provider's rates, optionally layering a configurable cache hit rate to discount input tokens via the provider's cache-read price

#### Scenario: AA free tier (effective-token derivation with cache)
- **WHEN** only AA free tier data is available (total cost_per_task and prices, without token breakdown)
- **THEN** the pipeline SHALL back out effective per-task token counts from AA's cost_per_task and prices using a configurable input:output token ratio, then re-price at the provider's rates with cache adjustment

#### Scenario: Fixed task-profile fallback
- **WHEN** no AA data is available for a model
- **THEN** the pipeline SHALL use a configurable task-profile token count set multiplied by the provider's prices

#### Scenario: Price provenance tracking
- **WHEN** the pipeline computes cost-per-task using fallback prices (e.g., AA prices when the provider does not expose cache-read pricing)
- **THEN** the output SHALL record which prices are direct provider prices and which are fallbacks, so the human reviewer can identify estimates

### Requirement: Model ranking and tier assignment
The pipeline SHALL rank deployments using Pareto frontier analysis at the canonical model level (frontier models as primary candidates, dominated models as backup), assign tier eligibility by SOTA-relative intelligence floors so a model qualifies for every tier at or below its capability, and select top-K deployments per tier using NMB (Net Monetary Benefit) with same-NMB grouping. It SHALL support model exclusion at two scopes: global patterns that remove a model before ranking, and optional tier-scoped patterns that remove a model from one tier only.

#### Scenario: Pareto frontier at canonical level (primary vs backup)
- **WHEN** ranking models
- **THEN** the pipeline SHALL aggregate deployments per canonical model (using the best-cost deployment), mark each canonical as on the frontier or dominated (a canonical is dominated when another canonical beats it on BOTH intelligence AND best cost), treat frontier canonicals as PRIMARY candidates and dominated canonicals as BACKUP candidates, and SHALL NOT select a dominated deployment as a primary pick

#### Scenario: Tier eligibility by intelligence floor (multi-tier membership)
- **WHEN** assigning tier eligibility
- **THEN** a canonical model SHALL be eligible for a tier when its intelligence is at least that tier's floor (a fraction of the current SOTA intelligence score), floors SHALL auto-rescale when the SOTA value changes, and a model that is eligible for several tiers SHALL be considered in each of them (so a cheap, capable model can serve both a lower and a higher tier)

#### Scenario: NMB top-K with same-NMB grouping
- **WHEN** selecting the top-K deployments per tier
- **THEN** deployments SHALL be ranked by their individual NMB score (lambda * intelligence - cost_per_task - mu * latency) over the tier-eligible set, deployments with the same canonical model and the same NMB score SHALL be grouped under a single order and counted as one toward K, and deployments with different NMB scores SHALL each compete independently

#### Scenario: Backup fill for thin tiers
- **WHEN** a tier has fewer than the configured top-K groups after primary (frontier) selection
- **THEN** the pipeline SHALL fill the remaining slots from the tier's own backup (dominated) deployments by NMB, and each backup deployment SHALL be recorded as a backup so it is distinguishable from a primary pick

#### Scenario: Consecutive-order failover
- **WHEN** emitting the selected deployments for a LiteLLM model group
- **THEN** each NMB group SHALL receive a consecutive order value (1, 2, 3, ...) where lower orders are tried first, same-NMB deployments share an order (load-balanced by LiteLLM's routing strategy), and the failover chain follows pure NMB ranking

#### Scenario: Excluding models by configuration
- **WHEN** a model matches a configured global exclusion pattern, matched case-insensitively as a substring against the provider, provider model ID, display name, canonical slug, and canonical name
- **THEN** the pipeline SHALL drop it before ranking so it never appears in any tier, and SHALL list it in the report under an `excluded_by_config` reason

#### Scenario: Tier-scoped exclusion
- **WHEN** a model matches an exclusion pattern configured for one named tier and does not match a global pattern
- **THEN** the pipeline SHALL keep it scored (intelligence, cost-per-task, Pareto state) and eligible for every other tier it qualifies for, SHALL NOT include it in that tier's eligible pool, SHALL NOT populate it into that tier's model group, and SHALL list it as excluded by configuration for that tier in both the ranking report and the machine-readable output
- **AND** tier-scoped patterns SHALL use the same case-insensitive substring matching against the same five model fields as global patterns

#### Scenario: Tier-scoped exclusion matches the whole canonical model
- **WHEN** a tier-scoped pattern matches a canonical model's slug or name
- **THEN** every provider deployment of that canonical model SHALL be excluded from that tier, and a pattern that matches only one provider SHALL exclude only that provider's deployments from that tier

#### Scenario: Global patterns take precedence over tier scope
- **WHEN** a model matches both a global pattern and a tier-scoped pattern
- **THEN** the global exclusion SHALL win, the model SHALL be absent from every tier, and it SHALL be reported once under the global `excluded_by_config` reason rather than per tier

#### Scenario: Tier-scoped exclusion does not change SOTA or floors
- **WHEN** a model is excluded from one or more tiers by tier-scoped patterns
- **THEN** its intelligence SHALL still count toward the SOTA value used to derive tier floors, and no tier floor SHALL change solely because of a tier-scoped exclusion

#### Scenario: Absent or empty tier-scoped configuration
- **WHEN** no tier-scoped exclusion map is configured, or a tier's list is empty
- **THEN** that tier's eligible pool SHALL be exactly the pool produced by floor eligibility and global exclusion, with no additional filtering

#### Scenario: Unknown tier name is rejected
- **WHEN** the exclusion configuration names a tier that is not present in the configured tier set
- **THEN** configuration loading SHALL fail with an error that names the unknown tier and lists the valid tier names, and no scoring SHALL run

### Requirement: Tier model pinning

Notwithstanding NMB-based tier selection, the pipeline SHALL allow a named tier to force-include a configured ordered list of canonical models (pins) ahead of ranked models. Pins SHALL be matched by canonical slug, SHALL occupy the lowest order values in configuration order, and SHALL NOT alter the NMB ranking of non-pinned models.

#### Scenario: Pinned models occupy the first orders
- **WHEN** a tier configures pins `["model-a", "model-b"]` and both slugs resolve to scored models
- **THEN** `model-a` SHALL receive order 1 and `model-b` order 2, and every NMB-selected model in that tier SHALL receive a higher order in its unchanged relative NMB order

#### Scenario: Pin bypasses the intelligence floor
- **WHEN** a pinned canonical model's intelligence is below the tier's configured floor
- **THEN** the pipeline SHALL still include it in that tier, without changing the SOTA intelligence value or any tier floor

#### Scenario: Pin bypasses NMB selection
- **WHEN** a pinned model would not be selected by the tier's NMB top-K ranking
- **THEN** the pipeline SHALL include it as a pinned deployment, distinct from primary and backup picks, and SHALL NOT let its pin displace a non-pinned model from its relative NMB position

#### Scenario: Pins consume top-K slots
- **WHEN** a tier resolves `P` pins and `top_k_per_tier` is `K`
- **THEN** at most `max(0, K - P)` NMB-selected groups SHALL be included in that tier
- **AND WHEN** `P >= K`, all resolved pins SHALL still be included, no NMB-selected groups SHALL be added, and a warning SHALL be reported

#### Scenario: All provider deployments of a pinned canonical share its order
- **WHEN** a pinned slug resolves to deployments on more than one provider
- **THEN** every deployment of that canonical that is not excluded from the tier SHALL be included at the same pin order and load-balanced by the router

#### Scenario: Global exclusion wins over a pin
- **WHEN** a pinned slug matches a global exclusion pattern and therefore has no scored deployment
- **THEN** the pin SHALL be ignored, a warning SHALL be reported, and the rest of the scoring run SHALL continue

#### Scenario: Tier exclusion wins over a pin
- **WHEN** a pin's deployments are all removed from the tier by that tier's exclusion patterns
- **THEN** the pin SHALL be ignored for that tier, a warning SHALL be reported, and the model MAY still be pinned in other tiers

#### Scenario: Unknown slug is warned and ignored
- **WHEN** a configured pin slug matches no canonical model
- **THEN** it SHALL be ignored with a warning and the remaining pins and scored selection SHALL be unaffected

#### Scenario: Known model without a scored deployment is warned and ignored
- **WHEN** a configured pin slug matches a canonical model that has no scored deployment (for example missing pricing or intelligence)
- **THEN** it SHALL be ignored with a warning and the rest of the run SHALL continue

#### Scenario: Duplicate pin uses the first occurrence
- **WHEN** the same slug appears more than once in one tier's pin list
- **THEN** the first occurrence SHALL determine its order, later occurrences SHALL be ignored, and a warning SHALL be reported

#### Scenario: Scored ranking is unchanged by pins
- **WHEN** pins are configured for a tier
- **THEN** the tier's latency calibration SHALL use the same floor-eligible pool it would use without pins, and the NMB value, relative NMB order, primary/backup classification, and Pareto state of every non-pinned model SHALL be unchanged
- **AND** pinned models SHALL be removed from NMB selection only, and the non-pinned models SHALL be renumbered consecutively after the pin block while preserving their relative order

#### Scenario: Pins are visible in the artifacts
- **WHEN** a tier has resolved pins
- **THEN** each pinned deployment SHALL be marked as pinned in `tier-output.json`, the tier's resolved pin order SHALL be recorded there, and both readable outputs SHALL show a "Pinned by config" block listing the pinned models and their orders
- **AND** the ranking report's model index SHALL show the tiers each model was pinned in

#### Scenario: Pin warnings are reported
- **WHEN** any pin cannot be honored, is duplicated, or the pin count reaches the top-K limit
- **THEN** the warning SHALL be written to the score command's error output, included in the ranking report, and carried in the machine-readable artifact, and the run SHALL continue

#### Scenario: Invalid pin configuration is rejected
- **WHEN** `pins.tiers` names a tier that is not configured, or a tier's value is not a list of slugs
- **THEN** configuration loading SHALL fail with an error naming the offending key and, for an unknown tier, the valid tier names

#### Scenario: Absent or empty pin configuration
- **WHEN** `pins.tiers` is absent, or a tier's pin list is empty
- **THEN** that tier SHALL be selected and ordered exactly as it was before pinning existed

### Requirement: Latency-aware NMB ranking

The pipeline SHALL include a latency term in NMB ranking, weighted by a per-tier share of the
tier's NMB spread, using each canonical model's published Artificial Analysis median
end-to-end response time, and SHALL record the latency, the share, the derived weight, and
the calibration inputs in its artifacts.

#### Scenario: Latency is captured with canonical data

- **WHEN** the score phase loads canonical models from the AA data
- **THEN** each canonical model SHALL carry AA's `median_end_to_end_response_time_seconds`
  when published, deployments SHALL inherit that value unchanged, and the value SHALL be
  recorded in `tier-output.json` (null when AA publishes none)

#### Scenario: Per-tier latency penalty

- **WHEN** a tier's eligible deployments are ranked
- **THEN** NMB SHALL be `lambda × intelligence − cost_per_task − mu × latency_seconds`, where
  `mu = rho[tier] × spread ÷ median_latency`, `spread` is the difference between the highest
  and lowest NMB of the tier's eligible groups measured without the latency term, and
  `median_latency` is the median AA latency of the tier's eligible deployments that publish one

#### Scenario: Missing latency is not invented

- **WHEN** AA publishes no latency for a model
- **THEN** its latency penalty SHALL be zero, the model SHALL remain eligible, and the
  artifact and report SHALL show its latency as unknown

#### Scenario: Latency, share, and derived weight are recorded

- **WHEN** `tier-output.json` is written
- **THEN** each deployment SHALL record its `latency_seconds`, each tier SHALL record the
  configured `rho`, the derived `mu`, and the calibration inputs (`spread`,
  `median_latency`), and the top-level `parameters` SHALL record the full per-tier
  `latency_rho` mapping plus the derived `mu` mapping

### Requirement: Ranking explainability report

The pipeline SHALL produce a human-readable report that explains the ranking for every
scored model, so a user can see why a model did or did not land in a tier.

#### Scenario: Per-tier full ranking with NMB breakdown

- **WHEN** the score phase runs
- **THEN** it SHALL write a report listing, for each tier, every eligible model ranked by
  that tier's NMB alongside the NMB inputs (lambda, intelligence, cost_per_task, latency
  or "unknown", the tier's `rho` and derived `mu`, and the resulting latency penalty), the
  model's Pareto state, and whether it was selected (with its order) or cut

#### Scenario: Per-model index across tiers

- **WHEN** the report is generated
- **THEN** it SHALL include an index of every scored model showing its intelligence,
  cost-per-task, Pareto state, the tiers it was eligible for, and the tiers it was
  actually selected in

#### Scenario: Dominated models are explained

- **WHEN** a model is off the Pareto frontier
- **THEN** the report SHALL name a model that dominates it (smarter AND cheaper), so a
  user can see why the model was only ever a backup

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

### Requirement: Configurable task profile and NMB parameters

All task-profile token counts, NMB tuning parameters (tier lambdas, per-tier latency share
rho, tier floors, top-K count), and pricing policies (cache hit rate, input:output ratio,
peak/off-peak windows) SHALL be defined in a configuration file, not hardcoded in source
code.

#### Scenario: Task profile from provider data

- **WHEN** the fetch phase scrapes provider documentation for per-request token estimates
- **THEN** it SHALL output suggested task-profile values to a separate file for the human
  to review and update in the config, rather than using them directly

#### Scenario: NMB parameter documentation

- **WHEN** the config file is read
- **THEN** each parameter SHALL have an inline comment explaining what it is, how it
  works, its effect on ranking, when to change it, and how to change it

#### Scenario: Per-tier latency share

- **WHEN** the latency policy is configured
- **THEN** it SHALL be a per-tier share `rho` keyed by the same tier names as the lambdas
  and floors, a single numeric value SHALL be accepted as a default applied to every tier,
  and a missing tier key SHALL fail with an error naming the tier and the configured keys
  rather than silently ranking that tier without a penalty
