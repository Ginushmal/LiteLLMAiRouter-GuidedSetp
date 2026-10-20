# Spec Delta

## ADDED Requirements

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
