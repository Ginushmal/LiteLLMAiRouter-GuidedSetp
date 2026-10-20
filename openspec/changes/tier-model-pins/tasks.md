# Tasks

## 1. Config surface and validation

- [x] 1.1 Add `pin_slugs: dict[str, list[str]]` to `Config` and parse `pins.tiers` in `model_pipeline/config.py` (absent/null = `{}`; empty list = no pins; trim slugs; reject a bare string, a non-list value, or a non-string entry with a clear error naming the key). Verify with a loader test for a populated map, nulls, and each invalid shape.
- [x] 1.2 Validate `pins.tiers` keys against `nmb.tier_floors` at config load and raise an error naming the unknown tier and the valid names. Verify with a test for an unknown key (`"Ultraa"`), a valid tier, and an omitted map.
- [x] 1.3 Add a documented `pins` block to `model-pipeline/config.yaml` (display names, canonical slugs, config order = order numbers, floor bypass, top-K accounting, exclusion precedence, warnings) following the house WHAT/HOW/EFFECT/WHEN/HOW comment style. Verify the file parses and `load_config()` returns the configured map.

## 2. Pin resolution and ordering

- [x] 2.1 Add `Deployment.is_pinned: bool = False` and emit `is_pinned` from `Deployment.to_dict()`; add `ScoredTier.pinned: dict[str, int]` and `ScoreResult.pin_warnings: list[str]`. Verify existing tests and `ScoreResult` construction sites still pass.
- [x] 2.2 Implement pin resolution per tier: normalize slugs (trim, lowercase), dedupe within a tier with a warning, match against scored deployments by canonical slug, keep every deployment of the canonical that survives the tier's exclusion patterns, bypass the floor, and record warnings for unknown slugs, known models with no scored deployment (including globally excluded), and fully tier-excluded pins. Verify unit tests for each case and that ignored entries do not leave order gaps.
- [x] 2.3 Integrate pins into `score()`: resolve pins before selection, calibrate `mu` on the normal eligible pool (pins included), then remove pinned canonicals from the NMB selection pool, compute pinned NMB with that `mu`, select at most `max(0, top_k - pin_count)` scored groups, and warn when `pin_count >= top_k`. Verify a pinned below-floor model appears in the tier and a pinned frontier model does not consume a primary slot.
- [x] 2.4 Add a `start` parameter to `assign_orders` (default 1) and an `order_offset` to `_select_and_rank` so pinned orders 1..P and scored orders P+1..P+M are assigned once, without collisions. Verify all existing ordering tests pass unchanged and new tests cover a two-pin offset.

## 3. Reporting and warnings

- [x] 3.1 In `emit/output.py`, emit per-deployment `is_pinned` and per-tier `pinned` in `tier-output.json`, add `pin_warnings` to the payload, and render a `Pinned by config` line plus `Kind = pinned` rows and a warnings footer in `tier-output.md`. Verify `populate` still reads only `tiers[].deployments` and the payload remains additive.
- [x] 3.2 In `emit/report.py`, render a separate per-tier `Pinned by config` table (order, model, providers, intel, cost, NMB, Pareto), add a `Pinned in` column to the model index merged from pinned deployments (including models absent from the scored ranking), and add a `## Warnings` section. Verify the rendered report contains the pinned block, the column, and each warning.
- [x] 3.3 In `cli.py::cmd_score`, print each `pin_warnings` entry to stderr prefixed `warning:` and include the pinned count in each tier's summary line. Verify with the offline fixture that warnings appear on stderr and the summary separates pinned from scored deployments.

## 4. Tests

- [x] 4.1 Add tests for pin configuration parsing and validation: populated map, null/empty, bare string, non-list, non-string entry, unknown tier, and omitted map. Verify each expected exception and the valid cases.
- [x] 4.2 Add a test that a pin below the tier's intelligence floor is included at order 1 and does not change SOTA or any floor. Verify it fails if the floor filter still applies to pins.
- [x] 4.3 Add a test that all provider deployments of a pinned canonical share one order, while a provider removed by that tier's exclusion pattern is not included; a pin with no surviving deployment is skipped with a warning. Verify both the deployment set and the warning text.
- [x] 4.4 Add tests for precedence and diagnostics: global exclusion skips the pin, unknown slug warns, known model with no scored deployment warns, and a duplicate slug uses the first occurrence and warns. Verify no exception escapes and other pins still resolve.
- [x] 4.5 Add tests for order accounting: two pins force scored orders to start at 3, `top_k=3` with two pins selects one scored group, and `pin_count >= top_k` still includes all pins while warning that no scored picks were made. Verify exact orders and warnings.
- [x] 4.6 Add a test that the scored pool is unchanged by pins: with a non-zero latency `rho`, the tier's `mu`, each non-pinned model's NMB, relative order, Pareto state, and primary/backup status match a no-pin run; non-pinned models are renumbered after the pins while preserving their relative order. Verify against a baseline run.
- [x] 4.7 Add a test that an absent `pins` map and an empty tier list produce exactly the previous orders, deployments, pools, and NMB values. Verify against the current expectations.
- [x] 4.8 Add a test for artifact/report output: `tier-output.json` contains `is_pinned`, the tier `pinned` map, and `pin_warnings`; `tier-output.md` and `tier-ranking.md` contain the pinned block and the `Pinned in` column. Verify the exact strings/keys.

## 5. Documentation

- [x] 5.1 Add `pins.tiers` rows and a short ranking-section paragraph to `model-pipeline/WALKTHROUGH.md`, and update the `model-pipeline/README.md` configuration note, explaining canonical-slug matching, config order, floor bypass, top-K accounting, and exclusion precedence. Verify the terms match `config.yaml`.

## 6. Verification

- [x] 6.1 Run `uv run --with pytest pytest tests/` from `model-pipeline/` and confirm every test passes.
- [x] 6.2 Run `uv run --with ruff ruff check src tests` and confirm the change adds no new violations; record the pre-existing baseline count instead of claiming a clean repo.
- [x] 6.3 Run `uv run model-pipeline --help` and confirm the CLI still starts.
- [x] 6.4 Verify the full score → emit path offline with a fixture (AGENTS.md forbids running `score` against live services as a test): call `score()` with deterministic fake inputs and a pinned below-floor model, then `build_payload`/`build_markdown`/`build_report`; confirm pinned orders, scored offsets, warnings, and `tiers[].deployments` all parse as specified.
