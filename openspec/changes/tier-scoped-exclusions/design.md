# Design

## Context

See `proposal.md` - Why. The relevant current state, verified in source:

- `model_pipeline/scoring/pipeline.py::_build_deployments` drops globally excluded mappings before any cost rank is computed, so globally excluded models never reach Pareto, SOTA floors, or NMB.
- Tier membership is floor-based and nested (`scoring/tiers.py::eligible_tiers`): a model is eligible for every tier whose floor it meets. Every model is eligible for Flash Lite because its floor is `0.0`.
- The per-tier loop in `pipeline.py::score` copies each deployment with `dataclasses.replace`, calibrates `mu` on the tier-eligible set, splits primary/backup by Pareto state, ranks with `_select_and_rank`, then builds the LiteLLM payload.
- `exclude.patterns` is loaded in `config.py` as a flat list in `Config.exclude_patterns`; matching is the case-insensitive substring helper `_excluded_by_config`.
- Reporting has two outputs: `emit/output.py` (`tier-output.json` + `tier-output.md`) and `emit/report.py` (`tier-ranking.md`, whose model index is built only from per-tier rankings).
- `populate/sync.py` reads only `tiers[].deployments` from the JSON, so new metadata fields cannot affect population.

## Goals / Non-Goals

**Goals:**

- Let one model be excluded from a named tier while staying scored and selectable in every other tier.
- Keep the existing global exclusion behavior and precedence intact.
- Make every tier-scoped exclusion visible in the ranking report and machine output.
- Fail fast on unknown tier names so a typo cannot silently do nothing.

**Non-Goals:**

- Per-tier Pareto frontiers or per-tier SOTA. Both stay catalog-wide.
- Per-tier `top_k`, per-tier lattices, or any other ranking-parameter change.
- An "include/exclude exception" mechanism (global exclusion cannot be overridden per tier).
- Changing how tiers map to LiteLLM model groups or how `populate` works.

## Decisions

### 1. Config shape: `exclude.tiers`, keyed by tier display names

```yaml
exclude:
  patterns:                 # global, unchanged
    - "contributor"
  tiers:                    # optional, per-tier
    Ultra:
      - "some-flagship"
    Pro:
      - "opencode"
    Flash: []
    Flash Lite: []
```

- Tier keys are the same display names used by `nmb.tier_floors`, `tier_lambdas`, and `latency_rho` (confirmed with the user). The mapping to LiteLLM group names remains solely in `litellm.tier_model_groups`.
- Each value is a list of patterns, including the empty list. No scalar shorthand; this mirrors `patterns`.
- **Alternative considered:** a flat `exclude.rules: [{patterns, tiers}]` list. It scales to many scoped rules but makes the common one-model/one-tier case noisy and harder to scan.
- **Alternative considered:** an `exclude.by_tier` key. Same behavior, less consistent naming.
- **Alternative considered:** keying by LiteLLM group name (`pro-tier`). Rejected because it duplicates the naming axis and diverges from every other tier-keyed config block.

### 2. Apply the filter inside the tier loop, after cost and Pareto

Tier-scoped matching runs when a tier's eligible pool is built, not in `_build_deployments`:

```
_build_deployments
  -> global patterns drop (unchanged)
  -> cost_per_task
  -> Pareto + SOTA floors (global, before tier filtering)
  -> for each tier:
       eligible = intel >= floor  AND  not tier-excluded
       calibrate mu on eligible
       rank / select / payload
```

- The filter must not run earlier because cost, Pareto state, and intelligence are still needed for the model's other tiers.
- It must not run later (e.g. only at emit) because an excluded model would still affect the tier's `mu` calibration and could displace a legitimate candidate in `top_k`.
- Matching reuses `_excluded_by_config` and its five fields. A `Deployment` already carries provider, model ID, display name, canonical slug, and canonical name, so no extra index is needed at this stage.
- A canonical match excludes all provider deployments of that model from the tier; a provider-only match excludes only that provider's deployments.

### 3. Keep SOTA, floors, and Pareto global

- Per-tier SOTA would make the floor depend on which models were excluded from that tier. Excluding the smartest model from Ultra would then *lower* Ultra's floor and admit more models — the opposite of the user's intent, and it would make the same floor fraction mean different things per tier.
- Pareto is a property of the catalog. Recomputing it per tier changes primary/backup classification, which is a separate behavioral change with its own report semantics. Left out of scope.
- Note the consequence: excluding a model from all four tiers via `tiers` is not equivalent to a global pattern; the model still influences SOTA/Pareto. This is intentional and documented in the config comments.

### 4. Calibrate `mu` on the post-exclusion pool

`calibrate_mu` runs after the tier filter, so spread and median latency describe the candidates actually ranked. With `latency_rho` currently `0.0` for every tier this has no effect today, but it keeps the metric honest if rho is raised later.

### 5. Validation: unknown tier names fail fast

Config loading compares `exclude.tiers` keys against `nmb.tier_floors` keys and raises a `ValueError` naming the unknown tier and listing the valid ones, mirroring `NmbConfig.rho_for`. Missing `exclude.tiers` and empty lists are valid and mean "no tier-scoped filtering". A stale tier name after a future rename therefore cannot silently disable an exclusion.

### 6. Reporting model

Carry per-tier exclusions on the scored result rather than inventing report-only state:

- `ScoredTier.excluded_by_config: dict[str, list[str]]` — canonical slug mapped to the `provider:model_id` tags excluded from that tier.
- `tier-output.json` gains the same field inside each tier object; `tier-output.md` prints it under the tier heading.
- `tier-ranking.md` prints an "Excluded by config" line in the tier section and adds an `Excluded in` column to the model index. The index currently only sees ranked models, so the excluded slugs must be merged in explicitly (a model excluded from its only eligible tier would otherwise vanish from the index).
- Global `excluded_by_config` stays exactly as it is; global patterns are not repeated per tier.
- **Alternative considered:** namespaced keys in the flat `excluded` map (for example `excluded_by_config:Pro`). Minimal change, but the per-tier reason would be buried at the bottom of the report and invisible in the model index, which defeats the report's "why isn't X in tier Y?" purpose.

## Risks / Trade-offs

- [Excluding the SOTA model from the top tier leaves a high floor and a thinner pool] → The report already shows floor, pool size, and per-tier exclusions; the user can lower the floor if the tier becomes too thin. No automatic floor adjustment by design.
- [Users treat "exclude from all tiers" as equivalent to a global exclude] → Config comments state the difference explicitly (tier-scoped rules leave SOTA/Pareto intact), and the report still lists the model as scored and eligible elsewhere.
- [Tier names drift from `nmb.tier_floors` keys] → Config load fails with the valid names listed.
- [A model excluded from its only eligible tier disappears from the model index] → The index explicitly merges `ScoredTier.excluded_by_config` entries and shows the tier under `Excluded in`.
- [Per-tier exclusion changes `mu` and therefore NMB ordering in that tier] → Expected: the pool is different. The report prints the tier's calibrated `mu` so the change is auditable.
- [Extra config surface invites over-tight curation] → The config block is documented as optional and the report keeps every exclusion visible.

## Migration Plan

- Purely additive and optional: omitting `exclude.tiers` preserves current output byte-for-byte apart from the new empty reporting fields.
- Apply: edit `model-pipeline/config.yaml`, run `uv run model-pipeline score`, review `output/tier-ranking.md`, then `uv run model-pipeline populate`.
- Rollback: remove the `exclude.tiers` block and re-run `score` + `populate`; no database migration and no LiteLLM config change are involved.
