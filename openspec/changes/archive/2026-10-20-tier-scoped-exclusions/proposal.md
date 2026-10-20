# Proposal

## Why

Model exclusion in the model pipeline is currently all-or-nothing: `exclude.patterns` drops a model from every tier before ranking. There is no way to say "this model may serve Ultra and Pro but must never be offered in Flash or Flash Lite". Because tier eligibility is floor-based and nested (a capable model is automatically a candidate in every lower tier), that gap forces users to either accept the model in tiers where it does not belong or remove it from the catalog entirely — losing its intelligence score, pricing, and Pareto influence everywhere.

## What Changes

- Add an optional `exclude.tiers` mapping to `model-pipeline/config.yaml`, keyed by the tier display names already used by `nmb.tier_floors`, `tier_lambdas`, and `latency_rho` (`Ultra`, `Pro`, `Flash`, `Flash Lite`).
- Each tier maps to a list of exclusion patterns using the same case-insensitive substring matcher and the same five matched fields (provider, provider model ID, display name, canonical slug, canonical name) as the existing global `exclude.patterns`.
- Tier-scoped exclusions are additive to global patterns: global exclusions still remove a model from everything, and a tier-scoped entry never rescues a globally excluded model.
- Apply tier-scoped exclusions after cost and Pareto computation but before building a tier's eligible pool, so an excluded model remains fully scored and can still be selected in other tiers.
- Keep SOTA intelligence and tier floors global (computed before tier filtering), so excluding a model from one tier does not shift that tier's floor or the floors of other tiers.
- Validate tier names at config load and fail fast on an unknown tier (for example a typo or a stale name), rather than silently ignoring the entry.
- Report tier-scoped exclusions so the behavior is auditable: per-tier excluded entries in `tier-output.json`, a per-tier "excluded by config" note in `tier-ranking.md`, and an `Excluded in` column in the model index.
- No change to `exclude.patterns` behavior, to tier eligibility by intelligence floor, or to LiteLLM population.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `model-pipeline`: The "Excluding models by configuration" requirement changes from a single all-tier exclusion to two scopes — global patterns plus optional tier-scoped patterns — with explicit precedence, validation, and reporting behavior.

## Impact

- `model-pipeline/config.yaml` — new documented `exclude.tiers` block.
- `model-pipeline/src/model_pipeline/config.py` — parse and validate tier-scoped exclusion config.
- `model-pipeline/src/model_pipeline/scoring/pipeline.py` — apply tier-scoped exclusions when building each tier's eligible pool; carry per-tier exclusion data on `ScoredTier`/`ScoreResult`.
- `model-pipeline/src/model_pipeline/emit/output.py` — emit per-tier excluded entries in `tier-output.json` and `tier-output.md`.
- `model-pipeline/src/model_pipeline/emit/report.py` — show tier-scoped exclusions in the per-tier section and model index.
- `model-pipeline/tests/test_scoring.py` (and config-level tests if added) — cover tier-scoped matching, precedence, and validation.
- No LiteLLM proxy code or `litellm_settings` change: tiers are already separate model groups, so exclusion only changes which deployments are populated into a group.
