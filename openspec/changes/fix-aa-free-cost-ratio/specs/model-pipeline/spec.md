# Spec Delta

## MODIFIED Requirements

### Requirement: Cost-per-task computation
The pipeline SHALL compute a per-deployment cost-per-task that reflects both the model's token efficiency (from Artificial Analysis benchmark data) and the specific provider's pricing, including cache effects.

#### Scenario: AA Pro tier (per-token re-price)
- **WHEN** AA Pro tier data is available (per-task token counts and cost breakdown)
- **THEN** the pipeline SHALL derive per-task token counts by type (input, reasoning, answer) from AA's benchmark data and re-price them at the provider's rates, optionally layering a configurable cache hit rate to discount input tokens via the provider's cache-read price

#### Scenario: AA free tier (effective-token derivation with cache)
- **WHEN** only AA free tier data is available (total cost_per_task and prices, without token breakdown)
- **THEN** the pipeline SHALL re-price AA's cost_per_task by the ratio of the provider's blended per-token price to AA's blended per-token price, where the blend weights fresh input, cache-read input, and output by the same configured cache hit rate and input:output ratio on both sides — because AA's published cost already embeds its measured cache savings, the pipeline SHALL NOT apply a cache discount a second time by deriving token counts under a no-cache assumption

#### Scenario: Identical prices reproduce AA's cost exactly
- **WHEN** a provider's effective prices (after fallback filling) equal AA's published prices for a model
- **THEN** the computed cost-per-task SHALL equal AA's published cost_per_task, for any configured cache hit rate and input:output ratio

#### Scenario: Cache-read price differences move the cost
- **WHEN** two providers publish identical input and output prices but different cache-read prices for the same model
- **THEN** the provider with the cheaper cache-read price SHALL receive the lower cost-per-task, and the difference SHALL grow with the configured cache hit rate

#### Scenario: Fixed task-profile fallback
- **WHEN** no AA data is available for a model
- **THEN** the pipeline SHALL use a configurable task-profile token count set multiplied by the provider's prices

#### Scenario: Price provenance tracking
- **WHEN** the pipeline computes cost-per-task using fallback prices (e.g., AA prices when the provider does not expose cache-read pricing)
- **THEN** the output SHALL record which prices are direct provider prices and which are fallbacks, so the human reviewer can identify estimates