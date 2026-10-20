# Spec Delta

## MODIFIED Requirements

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
