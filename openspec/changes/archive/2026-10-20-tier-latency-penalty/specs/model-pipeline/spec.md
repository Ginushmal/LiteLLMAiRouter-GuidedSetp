# Spec Delta

## ADDED Requirements

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

## MODIFIED Requirements

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
