# Proposal

## Why

Tier membership is decided entirely by the NMB top-K ranking. A model the operator explicitly trusts can be cut, ranked below models they trust less, or fall below the tier's intelligence floor, with no supported way to say "this model must be in this tier". Exclusions can only remove models; there is no manual inclusion control. Pins close that gap while leaving the scored ranking untouched for every non-pinned model.

## What Changes

- Add an optional top-level `pins.tiers` mapping to `model-pipeline/config.yaml`, keyed by the tier display names already used by `nmb.*` and `exclude.tiers` (`Ultra`, `Pro`, `Flash`, `Flash Lite`).
- Each entry is an ordered list of **canonical model slugs**. Slugs are matched exactly (trimmed, case-insensitive) against the pipeline's canonical identities, not against provider model IDs.
- A resolved pin is always included in its tier, at the top of the order chain: pins occupy orders `1..P` in the order they are defined in the config. If a pinned canonical has deployments on several providers, all surviving deployments share that pin order (load-balanced by the router).
- Pins bypass the tier's intelligence floor and bypass normal NMB selection. They are not primary or backup picks; they are a separate `pinned` block.
- A pin does not participate in NMB selection, but the tier's latency calibration still uses the normal floor-eligible pool (pins included). The NMB values, relative NMB order, primary/backup classification, and Pareto state of every non-pinned model are therefore identical to a run without pins. Non-pinned models keep their relative order and are renumbered consecutively after the pin block.
- Pins consume top-K slots: with `P` resolved pins and `top_k_per_tier = K`, at most `max(0, K - P)` NMB-selected slots are filled. If `P >= K`, all pins are included, no scored picks are made, and a warning is emitted.
- Exclusion wins over pinning. A slug removed by a global exclusion pattern, or by that tier's `exclude.tiers` patterns, is skipped with a warning and the run continues. Unknown slugs, known models with no scored deployment, and duplicate entries in one tier's list also produce warnings and are ignored; other pins are unaffected.
- Reporting: `tier-output.json` marks each deployment with `is_pinned`, records each tier's resolved pins, and carries the pin warnings. Both readable outputs (`tier-output.md` and `tier-ranking.md`) show a "Pinned by config" block with the configured order, and the ranking report's model index gains a `Pinned in` column and a `## Warnings` section. The `score` CLI prints the warnings to stderr.
- No change to `exclude` behavior, tier floors, SOTA, Pareto, NMB grouping for non-pinned models, or LiteLLM population.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `model-pipeline`: Adds a "Tier model pinning" requirement covering manual inclusion, pin ordering and top-K accounting, floor bypass, exclusion precedence, warning behavior, scored-ranking invariance, and reporting. Existing non-pinned ranking behavior is unchanged.

## Impact

- `model-pipeline/config.yaml` — new documented `pins.tiers` block.
- `model-pipeline/src/model_pipeline/config.py` — parse and validate pinned slugs and tier names.
- `model-pipeline/src/model_pipeline/models.py` — additive `is_pinned` flag on deployments.
- `model-pipeline/src/model_pipeline/scoring/pipeline.py` — resolve pins per tier, remove them from the scored pool before calibration, assign pin orders and offset the scored orders, collect warnings.
- `model-pipeline/src/model_pipeline/scoring/nmb.py` — order assignment accepts a starting offset.
- `model-pipeline/src/model_pipeline/emit/output.py` and `emit/report.py` — pinned blocks, `is_pinned` in JSON, `Pinned in` index column, warnings.
- `model-pipeline/src/model_pipeline/cli.py` — print pin warnings to stderr and include the pinned count in the tier summary.
- `model-pipeline/tests/` — config parsing/validation and scoring/reporting tests.
- `model-pipeline/README.md`, `WALKTHROUGH.md`, `config.yaml` comments — document the new control.
- No LiteLLM proxy, database, or `custom_cost_map.json` change; the JSON additions are backward-compatible and `populate` reads only `tiers[].deployments`.
