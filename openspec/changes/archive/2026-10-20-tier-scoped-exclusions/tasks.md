# Tasks

## 1. Config surface and validation

- [x] 1.1 Add `exclude_tier_patterns: dict[str, list[str]]` to `Config` and parse `exclude.tiers` in `model_pipeline/config.py` (absent = `{}`; a null or empty list is empty). Verify by loading `model-pipeline/config.yaml` and asserting the parsed map matches the file.
- [x] 1.2 Add a documented `exclude.tiers` block to `model-pipeline/config.yaml` under the existing `EXCLUSIONS` section, using tier display names (`Ultra`, `Pro`, `Flash`, `Flash Lite`), with comments covering additive behavior, global precedence, and the fact that tier-scoped exclusions do not change SOTA/Pareto. Verify the file parses and `load_config()` returns the new field.
- [x] 1.3 Validate `exclude.tiers` keys against `nmb.tier_floors` during config load and raise a `ValueError` that names the unknown tier and lists the valid names. Verify with a test that an unknown key (`"Ultraa"`) fails and that omitted/empty maps pass.

## 2. Scoring behavior

- [x] 2.1 Add `excluded_by_config: dict[str, list[str]]` (canonical slug -> `provider:model_id` tags) to `ScoredTier` in `model_pipeline/scoring/pipeline.py`. Verify the dataclass default is an empty map and existing construction sites still work.
- [x] 2.2 In `score()`, filter each tier's eligible pool with that tier's patterns using the existing `_excluded_by_config` matcher and all five model fields, before `calibrate_mu`, the primary/backup split, and `_select_and_rank`; record what was excluded on `ScoredTier`. Verify a tier-scoped pattern removes the model from that tier's ranking and deployments while leaving its ranking entries in other tiers intact.

## 3. Output and explainability

- [x] 3.1 Emit each tier's `excluded_by_config` in `tier-output.json` (inside the tier object) and print it under each tier heading in `tier-output.md`. Verify `populate` still parses the payload and reads `tiers[].deployments` unchanged.
- [x] 3.2 In `tier-ranking.md`, print an "Excluded by config" line in the affected tier section and add an `Excluded in` column to the model index, merging the per-tier exclusion slugs so a model excluded from its only eligible tier still appears. Verify a rendered report shows the model in both places and that globally excluded models still appear only under the existing global `excluded_by_config` section.

## 4. Tests

- [x] 4.1 Add a test that a tier-scoped pattern selects the named tier only: the model is absent from that tier's deployments/ranking and present in every other tier it qualifies for. Verify it fails when the filter is removed.
- [x] 4.2 Add tests for match scope: a canonical slug pattern excludes every provider deployment of that model from the tier, while a provider-only pattern excludes just that provider's deployments. Verify both assertions in the same test module.
- [x] 4.3 Add a test for precedence: a model matching both a global pattern and a tier pattern is absent everywhere and reported once under the global `excluded_by_config` reason. Verify no per-tier entry is produced for it.
- [x] 4.4 Add a test that SOTA intelligence and all tier floors are unchanged when the SOTA model is excluded from a single tier. Verify the resulting floors equal the values computed with no tier-scoped exclusion.
- [x] 4.5 Add a test that an absent `exclude.tiers` map or an empty tier list yields the same eligible pools and rankings as today. Verify against the current expectations for a tier.
- [x] 4.6 Add a test that `build_report` output contains the `Excluded in` column and the tier's exclusion line for an excluded model. Verify the strings are present in the generated Markdown.

## 5. Documentation

- [x] 5.1 Add `exclude.patterns` and `exclude.tiers` rows to the config reference table in `model-pipeline/WALKTHROUGH.md`, explaining the global-vs-tier distinction. Verify the table renders and the terms match `config.yaml`.

## 6. Verification

- [x] 6.1 Run the full test suite with `uv run --with pytest pytest tests/` from `model-pipeline/` and confirm every test passes.
- [x] 6.2 Verify the full score → emit path offline with a fixture (AGENTS.md forbids running `score` against live services as a test): call `score()` with deterministic fake inputs and a tier-scoped exclusion, then `build_payload`/`build_markdown`/`build_report`; confirm the exclusion appears for the intended tier only, a global pattern reports once, and `tiers[].deployments` still parses.
