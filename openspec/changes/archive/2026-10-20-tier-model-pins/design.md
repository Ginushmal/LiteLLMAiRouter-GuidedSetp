# Design

## Context

See `proposal.md` - Why. Relevant current behavior, verified in source:

- `scoring/pipeline.py::score` builds each tier's pool with `_tier_eligible` (floor + `exclude.tiers`), calibrates `mu` on that pool, splits primary/backup by Pareto state, then calls `_select_and_rank(..., top_k)`.
- `scoring/nmb.py::assign_orders` stamps consecutive orders starting at 1; `_select_and_rank` embeds those order values in the report rows.
- `Deployment` carries `order`, `nmb`, `is_backup`, and the payload fields; `to_dict` feeds `tier-output.json`.
- `emit/report.py::build_report` builds the model index from per-tier `ranking` rows and has an existing merge for `ScoredTier.excluded_by_config`.
- `emit/output.py` writes `tier-output.json` / `tier-output.md`; `populate/sync.py` reads only `tiers[].deployments`.
- `config.py` already has `_tier_pattern_map` / `_validate_tier_names` patterns for list-valued, tier-keyed config.
- The working tree already implements `exclude.tiers` (change `tier-scoped-exclusions`, complete but not yet archived); pin resolution must respect it.

## Goals / Non-Goals

**Goals:**

- Let an operator force named canonical models into a tier at orders 1..P in config order.
- Keep every non-pinned model's NMB value, relative ranking, Pareto state, and primary/backup status unchanged.
- Make pins and any pin problems visible in both readable outputs and the machine artifact.
- Warn and continue, never silently drop a configured pin.

**Non-Goals:**

- Provider-qualified pins (`provider:slug`); a pin always means the canonical model, across providers.
- A weights/percentage or "soft preference" mode.
- Changing tier floors, SOTA, Pareto, NMB grouping, or LiteLLM constraints.
- Auto-creating deployments for pinned slugs that have no scored deployment.
- Pins overriding global or tier exclusions.

## Decisions

### 1. Config shape: top-level `pins.tiers`, keyed by tier display names

```yaml
pins:
  tiers:
    Ultra:
      - "claude-opus-4-5"   # order 1
      - "gpt-5"             # order 2
    Pro:
      - "claude-sonnet-4-5"
    Flash: []
    Flash Lite: []
```

- Keys match `nmb.tier_floors` / `exclude.tiers` display names; unknown keys fail config load with the valid names listed.
- Values are lists of canonical slugs. A bare string is rejected (it would otherwise turn into single-character matches in other config blocks); non-string entries are rejected too.
- Slugs are trimmed and matched case-insensitively; no fuzzy or display-name matching.
- **Alternative considered:** `include.tiers`. Rejected because "include" reads like an allowlist ("only these models"), which is the opposite of this behavior.
- **Alternative considered:** provider-qualified pins (`provider:slug`). Deferred; the user's unit is the model, and the existing router's within-order strategy already picks among providers.

### 2. Pin authority: bypass floor, always included, consume top-K slots

- A pin is resolved from the scored deployment list, so it does not need to meet the tier's floor. This is a deliberate manual override; floors, SOTA, and Pareto are not recomputed.
- Pins are always included; they are not subject to NMB selection or the primary/backup preference.
- With `P` resolved pins and `top_k_per_tier = K`, scored selection uses `max(0, K - P)`. If `P >= K`, all pins are included, no scored groups are added, and a warning is emitted.
- **Alternative considered:** pins as extra slots on top of K. Rejected: `top_k_per_tier` is the tier's slot budget, and letting pins inflate it silently would make the budget meaningless.

### 3. One pin = one canonical, all provider deployments at the same order

- Resolution groups scored deployments by normalized `canonical_slug`; every deployment of the pinned canonical that survives that tier's exclusion patterns is included.
- All survivors share the pin order. Within an order, LiteLLM's configured routing strategy (currently `cost-based-routing`) chooses among providers; this preserves provider failover instead of pinning one deployment.
- If a tier's exclusion patterns remove some but not all provider deployments, the survivors are pinned; the pin is honored.
- **Alternative considered:** pin only the cheapest deployment and let other provider copies compete normally. Rejected: the model could then appear twice in the same tier at different orders, which is confusing for a manual guarantee.

### 4. Calibrate on the normal pool, then remove pins from NMB selection

Order of operations per tier:

```
1. normal pool      = floor-eligible, minus exclude.tiers   (_tier_eligible)
2. resolve pins     = canonical slugs -> scored deployments, floor ignored
3. mu               = calibrate_mu(normal pool)             <- pins included
4. scored pool      = normal pool minus every pinned canonical
5. rank/select      = NMB top-(K-P) over scored pool
6. pin deployments  = order 1..P, is_pinned=True, NMB computed with the same mu
7. final orders     = pins 1..P, then scored groups P+1..P+M
```

- Calibrating on the normal pool (which includes any pin that was already floor-eligible) is what guarantees the requirement "scored ranking is unchanged": `mu`, every non-pinned model's NMB, and their relative order are exactly what they were before pinning. Removing pins before calibration would shrink the pool, change `mu`, and silently reorder the scored models — the opposite of the intent.
- Pins are removed before the primary/backup split and the NMB ranking, so a pinned frontier model cannot consume a primary slot or affect the backup-fill count.
- Absolute scored orders are renumbered after the pin block: `assign_orders` gains a `start` parameter (default 1, so existing behavior is unchanged) and `_select_and_rank` gains an `order_offset` used for both stamped orders and report rows. The non-pinned models keep their relative NMB order.
- Pinned deployments get their NMB from `nmb(...)` with the calibrated `mu`, but they never enter NMB selection.
- `pool_size` keeps its meaning: floor-eligible models left in the scored pool. The tier reports `pinned_count` separately.

### 5. Precedence and warnings: exclusion wins, never abort the run

- Global exclusions run before pins are resolved; a globally excluded canonical has no deployment. Resolution reports it as "no scored deployment" (or "globally excluded" when the mapping tag is in the global excluded set).
- Tier exclusions are applied to every deployment of a pinned canonical; if none survive, the pin is skipped for that tier with a warning.
- Unknown slug vs known-without-deployment is distinguished using the canonical model list passed to `score()`.
- Duplicates in one tier's list: first wins, later occurrences are ignored with a warning.
- Resolved pins are compacted; an ignored entry does not leave an order gap.
- Warnings are collected in `ScoreResult.pin_warnings` (tier-prefixed, deterministic order), printed to stderr by `cmd_score`, rendered in `tier-ranking.md`, and emitted in `tier-output.json`. No new JSONL log is introduced: `score` currently reports to stdout, and the project contract says not to invent a second logging format on an unrelated change.

### 6. Reporting model

- `Deployment.is_pinned: bool` (additive) and `"is_pinned"` in `to_dict()`.
- `ScoredTier.pinned: dict[str, int]` (canonical slug -> order) and `pinned_count` derived from deployments.
- `tier-output.json`: per-deployment `is_pinned`, per-tier `pinned`, top-level `pin_warnings`.
- `tier-output.md`: a `Pinned by config` line under the tier summary, pinned rows first with `Kind = pinned`, warnings footer.
- `tier-ranking.md`: a separate "Pinned by config" table in the tier section (orders, model, providers, intel, cost, NMB, Pareto), then the unchanged NMB table for scored models. The model index gains a `Pinned in` column, merged from pinned deployments the same way `excluded_by_config` is merged, so a model absent from the scored ranking still appears. A `## Warnings` section lists pin warnings.
- The index's `Eligible tiers` column continues to describe the scored pool; `Pinned in` explains the manual exception. A short legend says pinned models are removed from the scored pool.

## Risks / Trade-offs

- [Pins force expensive models to the front of every request to that tier] → Intended; both reports show cost and NMB for each pin, and the docs state that order 1 is tried first.
- [`P >= K` leaves a tier with no scored picks] → Warned explicitly in stderr and the report; the pin guarantee wins over the budget.
- [Pins bypass the floor, so a weak model can enter a strong tier] → Explicit manual override; the report shows its intelligence next to the tier floor.
- [All providers of a pinned canonical share one order, unlike NMB's cost-group rule] → Documented; within-order routing still prefers the cheaper provider under the configured strategy, and failover is preserved.
- [Tier exclusion and pin contradict each other] → Exclusion wins with a loud warning; global exclusion is never overridden.
- [Known model but no scored deployment (missing price/intelligence)] → Warned, not invented or silently dropped.
- [Pin warnings could be missed] → Repeated in stderr, the ranking report, and `pin_warnings` in JSON.

## Migration Plan

- Purely additive and optional: omitting `pins` preserves current selection, orders, and artifacts except for new empty reporting fields.
- Apply: edit `model-pipeline/config.yaml`, run `uv run model-pipeline score`, review `output/tier-ranking.md`, then `uv run model-pipeline populate`.
- Rollback: remove the `pins` block and re-run `score` + `populate`; no database or LiteLLM config change is involved.
