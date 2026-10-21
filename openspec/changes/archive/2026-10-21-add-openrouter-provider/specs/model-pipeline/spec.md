# Spec Delta

## MODIFIED Requirements

### Requirement: Multi-provider model fetching
The pipeline SHALL fetch available model lists and pricing data from configured LLM providers (CommandCode, OpenCode, and OpenRouter) using their respective API endpoints, pricing documentation pages, or — where a provider publishes one — a single JSON catalog that carries both models and pricing. Each provider SHALL use a dedicated adapter implementing a common interface that returns normalized model records with identity, pricing, context window, and endpoint metadata.

#### Scenario: Fetch CommandCode models
- **WHEN** the pipeline runs the fetch phase with the CommandCode adapter configured
- **THEN** it retrieves the model list from `api.commandcode.ai/provider/v1/models` and pricing from `commandcode.ai/models`, returning normalized records with model ID, input/output/cache prices, context window, and supported endpoints

#### Scenario: Fetch OpenCode models
- **WHEN** the pipeline runs the fetch phase with the OpenCode adapter configured
- **THEN** it retrieves the model list from `opencode.ai/inference/go/v1/models` and pricing from the Go plan documentation page, returning normalized records with model ID, input/output/cache prices, context window, and endpoint type (Chat Completions, Responses, Messages, or Google)

#### Scenario: Fetch OpenRouter models
- **WHEN** the pipeline runs the fetch phase with the OpenRouter adapter configured
- **THEN** it SHALL retrieve both the model list and the pricing from the single JSON catalog at `openrouter.ai/api/v1/models`, with no separate pricing page, returning normalized records with model ID, the published per-token input/output/cache-read/cache-write prices, context window, and supported endpoints

#### Scenario: OpenRouter model eligibility
- **WHEN** the OpenRouter catalog contains `:batch` variants
- **THEN** the adapter SHALL exclude them before normalization, because they serve the OpenRouter Batch API and are not chat-servable deployments
- **WHEN** the catalog contains `:free` variants
- **THEN** the pipeline SHALL include them as deployments carrying their published zero prices and SHALL map them to the same canonical identity as their base model; when that canonical has no Artificial Analysis identity the model SHALL be dropped as unmapped, and its intelligence score SHALL NOT be invented
- **WHEN** the catalog contains router entries (`openrouter/free`, `openrouter/auto`,
  `openrouter/auto-beta`, `openrouter/fusion`, `openrouter/pareto-code`,
  `openrouter/bodybuilder`, `typesafe/jev-router`)
- **THEN** they SHALL be excluded by configuration, since they are load-balancing or
  task-routing entries rather than real models

#### Scenario: Pricing normalization
- **WHEN** a provider publishes context-tiered pricing (different prices at different context lengths)
- **THEN** the pipeline SHALL compute the average of the tier prices for cost calculation
- **WHEN** a provider publishes peak and off-peak pricing windows
- **THEN** the pipeline SHALL collapse them according to the configured time-of-day price mode, weighting by the proportion of the evaluation window that overlaps each of the model's own pricing bands
- **WHEN** a provider publishes both context-threshold and time-of-day prices for one model
- **THEN** the pipeline SHALL resolve the time dimension within each context tier first and then collapse the context tiers per the configured context-tier policy
- **WHEN** a provider publishes discounted or promotional prices alongside list prices
- **THEN** the pipeline SHALL use the effective (discounted) price

#### Scenario: Time-of-day price modes
- **WHEN** a model publishes time-of-day pricing and the configured mode is `today`
- **THEN** the pipeline SHALL compute the weighted price over today's slice of the configured active window using the model's own bands and day-of-week schedule — the mode is date-scoped, so the configured active days do not gate it, and a weekday-only schedule therefore resolves to plain off-peak on a weekend run — and SHALL record the evaluated date in the artifact
- **WHEN** the configured mode is `average`
- **THEN** the pipeline SHALL compute the weighted price over the whole configured week (the active window across the configured active days)
- **WHEN** the configured mode is `instant`
- **THEN** the pipeline SHALL record the single price that applies at the evaluation instant with no averaging
- **WHEN** a model publishes no time-of-day windows
- **THEN** every mode SHALL yield its flat published price

#### Scenario: Schedule evaluation instant
- **WHEN** an `as_of` timestamp is configured or supplied for a run
- **THEN** the `today` and `instant` modes SHALL evaluate schedules at that timestamp instead of the run time, and the artifact SHALL record the evaluation instant so a recorded price is never mistaken for a stable rate

#### Scenario: Per-model schedule windows
- **WHEN** a model's published overrides define their own time windows or day-of-week schedule
- **THEN** the pipeline SHALL use those windows rather than the globally configured peak windows
- **WHEN** a model's schedule leaves some hours uncovered
- **THEN** its base published price SHALL apply outside every published window

#### Scenario: Structured scraping logs
- **WHEN** the pipeline fetches data from a provider
- **THEN** it SHALL save the raw fetched content (HTML or JSON) to disk alongside a structured log entry recording the URL, timestamp, HTTP status, parse result count, and any errors - enabling AI-assisted debugging if the provider's page structure changes

### Requirement: Canonical model deduplication
The pipeline SHALL map each provider model name to a canonical model identity from the Artificial Analysis model catalog. The canonical identity SHALL be a compound key of base model name and variant (parameter count, effort level, thinking mode, etc.) to prevent cross-matching between different variants (e.g., qwen3-4b vs qwen3-26b, mimo-2.6 vs mimo-2.6-high).

#### Scenario: Exact match (100% confidence)
- **WHEN** a provider model name matches a canonical model name exactly after normalization (lowercase, strip provider prefix, strip date/size suffixes)
- **THEN** the mapping is recorded with method "exact" and confidence 1.0

#### Scenario: Jev classifier for ambiguous names
- **WHEN** a provider model name does not match any canonical name exactly
- **THEN** the pipeline SHALL pre-filter the AA canonical list to a manageable candidate set (approximately 80 candidates) purely by name similarity (vendor name, model family, token overlap), WITHOUT excluding candidates on variant signals, and SHALL force-include the nearest canonical slug so the most obvious candidate is never lost to ranking noise
- **THEN** it SHALL call the Jev (TypeSafe) Choice classifier with the provider model name as state and the candidate list as choice options - each option description carrying that canonical's variant (parameter count, effort level) - plus an "unmapped" option
- **THEN** the classifier SHALL return the best-matching canonical name, a confidence score (0-1), and a full probability distribution

#### Scenario: Low-confidence mappings are still recorded
- **WHEN** Jev returns a mapping with confidence below the configured threshold
- **THEN** the mapping SHALL still be recorded in the output with the confidence value marked, NOT discarded - the human reviewer decides whether to accept or override it

#### Scenario: Variant disambiguation is delegated to Jev
- **WHEN** a provider model name contains variant signals (parameter count like "4b" or "26b", effort level like "high" or "max")
- **THEN** the pipeline SHALL NOT programmatically reject candidate matches on variant grounds; the Jev instructions SHALL state the exact-match rules (never merge different parameter sizes or effort levels; a bare provider name maps to the base/default variant) and the choice options SHALL carry each variant's description so Jev disambiguates
- **THEN** any residual ambiguity is surfaced through the confidence score and the human review gate, not by a hard programmatic filter

#### Scenario: Serving and version suffixes do not change identity
- **WHEN** a provider model name differs from a canonical only by a trailing serving token (`-fast`, `-highspeed`, `-ultraspeed`, `-turbo`), or the canonical carries a version suffix (`-next`, `-latest`) the provider name lacks
- **THEN** the pipeline SHALL resolve it deterministically: strip a trailing serving token from the provider name and retry the exact match, and treat `-next`/`-latest` as version suffixes stripped from both sides
- **THEN** a canonical that lists the full name as a distinct entry (e.g. `grok-4-fast`) SHALL still win the full-name exact match first, so distinct fast/serving models are never merged into the base
- **WHEN** a provider model name carries a trailing serving-plan suffix after a colon (`:free`, `:batch`)
- **THEN** the pipeline SHALL strip the suffix before matching so the plan variant resolves to the same canonical identity as its base model, while the deployment record keeps the full provider model ID

#### Scenario: Mappings checkpoint CSV
- **WHEN** the fetch phase completes deduplication
- **THEN** it SHALL write all mappings to a CSV file with columns for provider name, provider model ID, canonical AA slug, canonical AA name, variant, match method, confidence score, and an empty "override" column for manual corrections
- **AND** the pipeline SHALL halt and wait for human review of this CSV before the score phase can proceed

### Requirement: Configurable task profile and NMB parameters

All task-profile token counts, NMB tuning parameters (tier lambdas, per-tier latency share
rho, tier floors, top-K count), and pricing policies (cache hit rate, input:output ratio,
peak/off-peak windows, time-of-day price mode, schedule evaluation instant) SHALL be defined
in a configuration file, not hardcoded in source code.

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

#### Scenario: Time-of-day pricing policy

- **WHEN** the config file is read
- **THEN** the time-of-day price mode SHALL come from configuration (`today` | `average` |
  `instant`) and the optional schedule evaluation instant SHALL be settable in
  configuration or per run, and both SHALL carry the inline comments required of every
  parameter
