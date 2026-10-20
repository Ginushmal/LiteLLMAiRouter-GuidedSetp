# Proposal

## Why

The NMB formula already subtracts `mu × latency`, but the pipeline never supplies a
latency value: `rank_groups` passes `None`, and the Artificial Analysis performance block
(which carries `median_end_to_end_response_time_seconds`) is discarded during
canonicalization. Per-tier `mu` was added to the config, but it is dead weight — every
value produces identical rankings. Meanwhile `tier-output.json` records only the last
tier's `mu`, so the artifact misreports the parameter it claims to have used.

## What Changes

- Capture each canonical model's AA **median end-to-end response time** and carry it
  through scoring into `tier-output.json` (missing value stays `null`).
- Make the latency term real: NMB subtracts `mu[tier] × latency_seconds` per tier.
  A model with no published latency gets no penalty and stays eligible.
- Record the whole per-tier `mu` mapping in the artifact, each tier's `mu`, and each
  deployment's latency; show latency + penalty in the ranking report.
- Validate the parameter: per-tier mapping keyed like `tier_lambdas`, a scalar accepted
  as a default for every tier, and a missing tier failing with a clear error instead of a
  `KeyError` at the ranking loop.
- **Recalibrate the shipped values.** Measured on the current run: selected models have a
  median AA end-to-end latency of **93.6 s** (39–666 s), against tier NMB spreads of
  **8.3 / 2.4 / 1.9 / 2.0**. `mu = 2…5` would subtract 190–470 NMB and reduce ranking to
  "fastest wins". The change ships values roughly two orders of magnitude smaller and
  documents the calibration rule (`mu ≈ share × tier NMB spread / median latency`).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `model-pipeline`: ranking uses the latency input the NMB requirement already names;
  NMB parameters become explicitly per-tier; artifacts and the report carry latency and
  per-tier weights.

## Impact

- Code: `scoring/aa.py`, `models.py` (`CanonicalModel`, `Deployment`),
  `scoring/nmb.py`, `scoring/pipeline.py`, `emit/output.py`, `emit/report.py`,
  `config.py`.
- Config: `model-pipeline/config.yaml` (`nmb.latency_penalty_mu` mapping + calibrated
  values and comments).
- Artifacts: `tier-output.json` grows `latency_seconds` per deployment, `mu` per tier,
  and a full `latency_penalty_mu` mapping in `parameters`; the report gains latency,
  `mu`, and penalty columns.
- Downstream: rankings can change, so `populate` will add/remove/reorder deployments —
  the existing diff handles it; no schema or endpoint change.
- Tests: new coverage for latency capture, penalty math, per-tier lookup, scalar
  broadcast, missing-tier error, artifact/report fields.
- Docs: `model-pipeline/WALKTHROUGH.md` (NMB section) and the config comments.
- No new dependency — AA data is already cached in `output/aa_snapshot.json`.
