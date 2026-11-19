# Spec Delta

## ADDED Requirements

### Requirement: Artificial Analysis cost-breakdown retrieval

The pipeline SHALL obtain Artificial Analysis's published per-task cost breakdown (non-cache
input, cache-read, cache-write, answer and reasoning, in dollars) for every model AA scores,
cache the parsed result as an artifact, persist the fetched page, and log the fetch like any
other scrape.

#### Scenario: Breakdown is retrieved and cached
- **WHEN** the fetch or score phase needs AA cost data and no cached breakdown artifact exists
- **THEN** the pipeline SHALL fetch AA's published breakdown once, write the parsed result to a cache artifact under the output directory, and reuse that artifact on later phases and runs without another network call

#### Scenario: Coverage matches AA's scored models
- **WHEN** AA's free models list marks a model as having a `cost_per_task` total
- **THEN** the pipeline SHALL make that model's published breakdown available to scoring, and models without a published total SHALL remain without a breakdown

#### Scenario: Source-shape change fails loudly
- **WHEN** a fetched breakdown page is non-empty but yields no usable breakdown for any model
- **THEN** the phase SHALL fail with a non-zero exit code, name the source and the expected shape, and leave the verbatim page in the raw-scrape directory plus a structured log entry, so the cost basis never degrades silently

#### Scenario: Breakdown retrieval can be disabled
- **WHEN** breakdown retrieval is disabled in configuration
- **THEN** no extra AA page is fetched, scoring SHALL use the fallback cost methods, and the run summary and artifacts SHALL report which methods were used

### Requirement: Published breakdown is authoritative

The pipeline SHALL treat AA's published breakdown as authoritative reference data: it SHALL
NOT infer a component AA did not publish, and SHALL NOT apply its own cache-hit assumption
to a model that has a published breakdown.

#### Scenario: A model without a breakdown does not affect the others
- **WHEN** AA publishes a total but no breakdown for a model, or publishes a breakdown but no input/output price to convert it into tokens
- **THEN** only that model SHALL fall back to the next available cost method, and every other model SHALL keep its breakdown-based cost

## MODIFIED Requirements

### Requirement: Cost-per-task computation
The pipeline SHALL compute a per-deployment cost-per-task that reflects both the model's token efficiency (from Artificial Analysis benchmark data) and the specific provider's pricing, including cache effects.

#### Scenario: AA published cost breakdown (exact re-price)
- **WHEN** AA publishes a per-task cost breakdown for the canonical model (non-cache input, cache-read, cache-write, answer, and reasoning components, in dollars)
- **THEN** the pipeline SHALL derive per-task token counts by dividing each component's cost by AA's own price for that component — using AA's input price when AA publishes no cache-write price — and SHALL re-price those counts at the provider's effective prices
- **AND** it SHALL NOT apply the configured cache-hit rate or input:output ratio to that model

#### Scenario: AA Pro tier (per-token re-price)
- **WHEN** AA Pro tier data is available (per-task token counts and cost breakdown)
- **THEN** the pipeline SHALL derive per-task token counts by type (input, reasoning, answer) from AA's benchmark data and re-price them at the provider's rates, optionally layering a configurable cache hit rate to discount input tokens via the provider's cache-read price

#### Scenario: AA free tier (effective-token derivation with cache)
- **WHEN** a model has AA's total cost-per-task and input/output prices but no published breakdown
- **THEN** the pipeline SHALL back out effective per-task input tokens with a cache-aware denominator — the configured cache-hit share priced at AA's cache-read price and the remainder at AA's input price, plus the output term from the configured input:output ratio — and re-price at the provider's effective rates
- **AND** the fallback SHALL NOT discount input at the cache-read price without also discounting it in the back-out denominator

#### Scenario: Fixed task-profile fallback
- **WHEN** no AA data is available for a model
- **THEN** the pipeline SHALL use a configurable task-profile token count set multiplied by the provider's prices

#### Scenario: Cost method precedence
- **WHEN** more than one cost method is applicable to a model
- **THEN** the pipeline SHALL prefer AA's per-token counts, then AA's published breakdown, then the AA total-based fallback, then the fixed task profile, and SHALL record the method it used

#### Scenario: Identical prices reproduce AA's number
- **WHEN** the provider's effective input, output, cache-read, and cache-write prices all equal AA's corresponding prices for the same model
- **THEN** the computed cost per task SHALL equal AA's published cost per task within floating-point tolerance, regardless of which AA-based method was used

#### Scenario: Divergent components change only their share
- **WHEN** exactly one provider price component differs from AA's corresponding price
- **THEN** the change in computed cost per task SHALL equal that component's per-task token count multiplied by the price difference, and every other component's contribution SHALL be unchanged

#### Scenario: Breakdown data is never invented
- **WHEN** AA publishes a cost total but no price for a component needed to convert it into tokens, or a breakdown component is missing or negative
- **THEN** the pipeline SHALL NOT guess the missing value; it SHALL fall back to the next applicable method for that model and record the fallback

#### Scenario: Price provenance tracking
- **WHEN** the pipeline computes cost-per-task using fallback prices (e.g., AA prices when the provider does not expose cache-read pricing)
- **THEN** the output SHALL record which prices are direct provider prices and which are fallbacks, so the human reviewer can identify estimates

### Requirement: Configurable task profile and NMB parameters

All task-profile token counts, NMB tuning parameters (tier lambdas, per-tier latency share
rho, tier floors, top-K count), and pricing policies (cache hit rate, input:output ratio,
peak/off-peak windows, time-of-day price mode, schedule evaluation instant) SHALL be
defined in a configuration file, not hardcoded in source code.

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

#### Scenario: Time-of-day pricing policy

- **WHEN** the config file is read
- **THEN** the time-of-day price mode SHALL come from configuration (`today` | `average` |
  `instant`) and the optional schedule evaluation instant SHALL be settable in
  configuration or per run, and both SHALL carry the inline comments required of every
  parameter

#### Scenario: Cache assumptions are fallback-only

- **WHEN** the config defines a cache-hit rate or an input:output ratio
- **THEN** those values SHALL affect only models whose cost is derived without AA's published breakdown, and they SHALL NOT alter a breakdown-based cost

#### Scenario: Breakdown source is configurable

- **WHEN** the config file is read
- **THEN** the breakdown source URL and an enable/disable switch SHALL come from configuration, SHALL be optional with documented defaults so an existing config without them still loads, and SHALL carry the inline comments required of every parameter

### Requirement: Self-contained JSON output
The pipeline SHALL produce a self-contained JSON artifact (`tier-output.json`) containing all data needed for LiteLLM population, including per-deployment provider details, pricing, intelligence scores, NMB scores, order assignments, target model group names, and resolved token limits.

#### Scenario: Complete populate fields
- **WHEN** the score phase writes `tier-output.json`
- **THEN** each deployment record SHALL include: canonical model name, provider name, provider model ID, API base URL, API key environment variable reference, endpoint format, model group name (e.g., "pro-tier"), order number, input/output/cache prices with provenance, intelligence score, cost_per_task, NMB score, tier assignment, context window, input limit, and output limit

#### Scenario: Cost basis is recorded
- **WHEN** a deployment's cost was derived from AA data
- **THEN** its record SHALL include the cost method, AA's published cost-per-task total for reference, and the per-task token counts used for re-pricing, so a reviewer can recompute the number without re-running the fetch phase

#### Scenario: Re-populatable artifact
- **WHEN** the populate phase reads `tier-output.json`
- **THEN** it SHALL have sufficient information to create, update, or delete LiteLLM model entries via the management API without any additional data from the fetch or score phases

#### Scenario: Token limit provenance is recorded
- **WHEN** a deployment record carries a resolved output limit
- **THEN** the artifact SHALL record where the value came from (the pipeline's own provider catalog entry or a fallback match in another provider's entry) so a reviewer can audit it
