# Tasks

## 1. Latency capture

- [x] 1.1 Parse AA's `performance.median_end_to_end_response_time_seconds` into `CanonicalModel.latency_seconds` (None when AA publishes no performance block), and verify a unit test maps it and yields None for a record without performance
- [x] 1.2 Add `latency_seconds` to `Deployment`, inherit it from the canonical model in `_build_deployments`, and verify the field reaches the deployment record (test or a scored fixture)

## 2. Per-tier weight and ranking

- [x] 2.1 Make the latency weight configurable per tier: accept a scalar (broadcast to every tier) or a mapping keyed by tier names, expose one normalized accessor, and verify tests cover the mapping, the scalar broadcast, and a missing tier raising a `ValueError` that names the tier and the provided keys
- [x] 2.2 Use the latency in ranking: resolve `mu` per tier in `score()` and pass `members[0].latency_seconds` into `nmb()` (instead of `None`), and verify a test shows a slower model loses rank when `mu > 0`, keeps rank when `mu = 0`, and is unpenalized when latency is None
- [x] 2.3 Record the inputs: add `mu` to `ScoredTier`, write `latency_seconds` per deployment and the full `latency_penalty_mu` mapping into `tier-output.json` `parameters`, and verify the artifact contains one `mu` per tier plus a latency (or null) on every deployment

## 3. Report and configuration

- [x] 3.1 Extend the ranking report's per-tier section with each model's latency, the tier's `mu`, and the resulting penalty (and show the per-tier `mu` in the tier table/heading), and verify a report test asserts those values appear
- [x] 3.2 Set calibrated per-tier values in `config.yaml` (Ultra 0.02, Pro 0.005, Flash 0.004, Flash Lite 0.004) with a comment stating the calibration rule `mu ≈ share × tier NMB spread / median latency` and the measured inputs, and verify the config loads and the values appear in `parameters`

## 4. Verification

- [x] 4.1 Run the full test suite and verify every test passes
- [x] 4.2 Run `score` and verify the report shows meaningful latency/penalty values, the tier deltas are explainable, and no model is demoted purely by a data gap (unknown latency visible) (36/40 latencies present, `gemini-4-argon` unknown and ranked first in Ultra/Pro with no penalty; 2 swaps + reorders)
- [x] 4.3 Run `populate` against the running instance and verify only the rows whose ranking changed are added/moved/removed, then re-run it and verify zero changes (idempotence) (applied 2 added / 30 updated / 2 deleted / 8 unchanged / 0 errors; re-run: 0/0/0 unchanged=40)

## 5. Documentation

- [x] 5.1 Update `model-pipeline/WALKTHROUGH.md` with the latency term, the per-tier weight, the calibration rule, and the unknown-latency behavior, and verify it matches the implemented phases

## 6. Share-based calibration (revision)

- [x] 6.1 Replace the literal per-tier `mu` config with a share (`latency_rho`, ρ — scalar or per-tier mapping, missing tier fails with a named error) and verify the config tests cover mapping, broadcast, and the error
- [x] 6.2 Derive `mu` per tier as `rho × spread ÷ median_latency` (spread measured without the penalty) and verify tests reproduce a known spread/median and show `mu` scaling with the share and falling back to 0 without data
- [x] 6.3 Record `rho`, the derived `mu`, `spread`, and `median_latency` per tier in `tier-output.json`, show the derivation in `tier-ranking.md`, and verify the report test asserts the values
- [x] 6.4 Set the shipped shares (Ultra 0.15, Pro 0.20, Flash 0.40, Flash Lite 0.50), update `config.yaml`/`WALKTHROUGH.md`, and verify a score run records them and `populate` converges (derived mu 0.01342 / 0.02056 / 0.04222 / 0.05532; populate 1 added / 25 updated / 1 deleted, then 0 changes)
