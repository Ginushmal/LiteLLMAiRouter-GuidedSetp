# Design

## Context

Verified in the current code and artifacts:

- `nmb()` implements `lambda * intelligence - cost_per_task - mu * latency`, but
  `rank_groups()` calls it with `latency=None`, so the penalty is always `0.0`. No latency
  exists anywhere in the pipeline today.
- `output/aa_snapshot.json` already contains AA's `performance` block
  (`median_end_to_end_response_time_seconds`, `median_time_to_first_token_seconds`,
  `median_output_tokens_per_second`), but `scoring/aa.py` maps only intelligence and
  pricing, so the block is dropped.
- Coverage: 369 of 700 AA rows carry latency; of the 15 canonical models selected in the
  current run, 14 do (missing: `gemini-4-argon`). Their end-to-end latency is
  min 39.0 s / median 93.6 s / max 666.4 s.
- Current tier NMB spreads (selected sets): Ultra 8.26, Pro 2.38, Flash 1.90,
  Flash Lite 1.96. NMB scales with `lambda`, so a single global `mu` cannot be meaningful
  across tiers — which is why the parameter is per-tier.
- `tier-output.json` writes `parameters["latency_penalty_mu"]` from the loop variable, so
  only the last tier's value survives, while `tier_lambdas` writes the whole mapping.

## Goals / Non-Goals

**Goals**

- The latency term in NMB is real and observable, with a per-tier weight.
- Every artifact and report states the latency, the weight used, and the resulting
  penalty, so a ranking change can be audited.
- Missing data cannot silently distort a ranking: no value means no penalty, shown as
  unknown.

**Non-Goals**

- Measuring provider-path latency ourselves (AA's benchmark value is the source).
- Changing lambdas, floors, Pareto logic, or top-K.
- Using latency as a hard eligibility filter.

## Decisions

1. **Metric: AA `median_end_to_end_response_time_seconds`.** The config comment describes
   `mu` as cost per second of response time, and end-to-end is what an agent waits for.
   TTFT is available but not used in this change (open question).

2. **One latency per canonical model, inherited by deployments.** AA measures the model,
   not the route to it. Deployments (provider × model) copy the canonical value so the
   artifact stays self-contained.

3. **Missing latency ⇒ zero penalty, visibly "unknown".** Consistent with the project's
   never-invent rule. The model remains eligible; the report and artifact say so. The
   alternative (assume a pessimistic latency) would fabricate a number and is rejected.

4. **The config value is a share (`rho`), not a dollar-per-second weight.** `rho` is
   the fraction of the tier's NMB spread a median-latency model may lose. It is
   scale-free: raw NMB spread is ~10 in Ultra but ~5.5 in Flash, so the same literal `mu`
   would mean different things. `mu` is derived at score time from
   `rho × spread ÷ median_latency`, so the config states the policy ("latency owns 40%
   of the Flash decision") and the pipeline converts it. `latency_rho` accepts a mapping
   keyed like `tier_lambdas`/`tier_floors`, or a scalar broadcast to every tier; a mapping
   missing a tier raises a `ValueError` naming the tier and the provided keys. Validation
   runs before the ranking loop so it fails fast.

5. **Artifacts record both the policy and its derivation.** `parameters.latency_rho` holds
   the configured mapping and `parameters.latency_penalty_mu` the derived mapping; each
   `ScoredTier` records `rho`, `mu`, `spread`, and `median_latency`; each deployment
   records `latency_seconds` (null when unknown). The report shows the per-tier
   `rho → mu` derivation and each model's latency and penalty.

6. **Calibration is explicit and reproducible.** For each tier the pipeline measures the
   pre-penalty NMB spread over the eligible groups (NMB with `mu = 0`), takes the median
   AA latency of the eligible deployments that publish one, and derives
   `mu = rho × spread ÷ median_latency`. If the tier has no spread or no latency, `mu = 0`
   (nothing to calibrate against). No latency value is invented for a model; it simply has
   no penalty.

   The share is the intuitive knob and is identical in meaning across tiers. Shipped
   values: Ultra 0.15, Pro 0.20, Flash 0.40, Flash Lite 0.50 — Flash tiers spend a larger
   slice of their decision on speed, as intended. The measured spread and median latency
   change with the data, so `mu` is recorded per run (it is not a constant).7. **Penalty is a ranking input, not a filter.** A 666 s outlier loses ~13 NMB in Ultra
   and is demoted; it is not removed. Removal stays a config exclusion.

## Risks / Trade-offs

- **AA latency is a benchmark figure**, not our provider's observed path → the penalty can
  rank a model by a latency we do not actually experience. Accepted for now; the report
  makes it auditable, and a future change can swap in measured latency.
- **One selected model has no latency** (`gemini-4-argon`) → it keeps a zero penalty and a
  slight advantage. The report marks it unknown; treating "unknown" as "average" was
  rejected (invents data).
- **Outliers** (666 s) may be measurement noise → the penalty demotes them. Because it is
  only a penalty, a genuinely good cheap model still ranks on intelligence/cost.
- **Tier churn**: rankings can change, so `populate` adds/deletes/reorders deployments on
  the first run. The existing diff is idempotent and handles it.
- **`mu` is data-dependent**: because it is derived from the current spread and median
  latency, a data update can shift the effective weight between runs. The artifact records
  `rho`, `mu`, `spread`, and `median_latency`, so the change is auditable; the *policy*
  (`rho`) stays constant.
- **Backward compatibility**: scalar `latency_rho` configs apply the share to every tier;
  mapping configs must list every tier (fail-fast error names the missing one).

## Migration Plan

1. Implement with tests (latency capture, penalty math, per-tier lookup, scalar broadcast,
   missing-tier error, artifact/report fields).
2. Run `score`; read the report's latency/penalty columns and the tier deltas; adjust `mu`
   using the calibration rule if the penalty share looks wrong.
3. Run `populate`; expect only the rows whose ranking changed to move.
4. Rollback: restore the previous `tier-output.json` and run `populate`.

## Open Questions

- Should TTFT be a second per-tier knob (perceived responsiveness) instead of, or
  alongside, end-to-end time?
- Should models without AA latency be treated conservatively (e.g. tier-median latency)
  rather than zero penalty?
- Should the pipeline eventually use provider-measured latency (per deployment) instead of
  the canonical model value?
