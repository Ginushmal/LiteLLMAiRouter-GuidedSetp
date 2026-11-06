# Spec Delta

## MODIFIED Requirements

### Requirement: Canonical model deduplication
The pipeline SHALL map each provider model name to a canonical model identity from the Artificial Analysis model catalog. The canonical identity SHALL be a compound key of base model name and variant (parameter count, effort level, thinking mode, etc.) to prevent cross-matching between different variants (e.g., qwen3-4b vs qwen3-26b, mimo-2.6 vs mimo-2.6-high). Provider configuration model mappings SHALL take absolute precedence over automated matching.

#### Scenario: Provider configuration model mapping overrides
- **WHEN** a provider's configuration defines `model_mappings` and a provider model ID matches a configured key
- **THEN** the pipeline SHALL map the model directly to the configured canonical slug before exact matching or Jev classification, record the method as "override" with confidence 1.0, and populate both `canonical_slug` and `override` fields with the target canonical slug
- **AND** when the target canonical slug does not exist in the canonical catalog, the pipeline SHALL report a warning and record the model as unmapped rather than inventing an identity

#### Scenario: Exact match (100% confidence)
- **WHEN** a provider model name matches a canonical model name exactly after normalization (lowercase, strip provider prefix, strip date/size suffixes) and has no configured override
- **THEN** the mapping is recorded with method "exact" and confidence 1.0

#### Scenario: Jev classifier for ambiguous names
- **WHEN** a provider model name does not match any configured override or canonical name exactly
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
- **WHEN** a provider model name carries a trailing serving-plan suffix after a colon (`:free`, `:batch`)
- **THEN** the pipeline SHALL strip the suffix before matching so the plan variant resolves to the same canonical identity as its base model, while the deployment record keeps the full provider model ID

#### Scenario: Mappings checkpoint CSV
- **WHEN** the fetch phase completes deduplication
- **THEN** it SHALL write all mappings to a CSV file with columns for provider name, provider model ID, canonical AA slug, canonical AA name, variant, match method, confidence score, and an "override" column carrying any configuration or manual corrections
- **AND** the pipeline SHALL halt and wait for human review of this CSV before the score phase can proceed
