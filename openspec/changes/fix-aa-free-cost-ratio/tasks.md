# Tasks

## 1. Blended-price ratio in the aa_free strategy

- [x] 1.1 In `model-tier-populator/src/model_pipeline/scoring/cost.py`, add one shared blend helper `blend(input, output, cache_read, tp) = (1−h)·input + h·cache_read + output/R` with missing `cache_read` falling back to that side's input price (mirroring `_cost_of`). Verify: unit test asserting the helper's value for known inputs, including the missing-cache_read fallback.
- [x] 1.2 Replace `_strategy_b`'s token inversion + `_split_input` + `_cost_of` path with `cost = aa_cost_per_task × blend(effective provider prices) / blend(AA prices)`; keep the `blend(AA) <= 0 → _strategy_c` guard, the `aa_free` method label, and provenance mechanics; update the note text to describe the ratio ("AA cost re-priced by provider/AA blended-price ratio (cache_hit_rate h, input:output R)"). Verify: `uv run --with pytest pytest tests/test_scoring.py` passes, including the untouched `test_strategy_b_prefers_cheaper_cache_read` and `test_price_provenance_marks_aa_fallback`.
- [x] 1.3 Fix the `cache_hit_rate` and `input_output_ratio` comments in `model-tier-populator/config.yaml` and `config.example.yaml` to state that on the aa_free path they weight how provider-vs-AA price differences translate into cost (no token derivation), and preserve the surrounding teaching comments. Verify: re-read both blocks — no comment claims tokens are back-derived under a no-cache assumption.

## 2. Tests pinning the invariant and the incident

- [x] 2.1 Add the invariant test: for several `(h, R)` combinations (e.g. 0.0/4, 0.98/4, 0.5/2), provider prices equal to AA's ⇒ `cost_per_task == aa_cost_per_task` exactly (both blends computed by the same helper). Verify: test passes; deliberately breaking the numerator/denominator symmetry makes it fail.
- [x] 2.2 Add the incident regression: Kimi K3.1 Pro (AA cost 3.6812; $2/$10/$0.20) and Qwen4 Max (AA cost 3.2681; $1.5/$4.5/$0.075) at h=0.98, R=4 return AA's numbers — not the double-discounted $2.238/$1.529. Verify: assertions fail against the old `_strategy_b` and pass with the ratio.
- [x] 2.3 Add edge tests: AA blend zero/absent → falls back to `task_profile`; provider prices all zero (free model) → cost 0; provider cheaper than AA on input only → cost scales down proportionally to the blend ratio; cache-read difference effect grows with h. Verify: all pass.
- [x] 2.4 Run the full populator suite (`uv run --with pytest pytest` in `model-tier-populator/`). Verify: all tests pass, no regressions in NMB/tier/report tests that consume `aa_free` costs.

## 3. Regenerate artifacts and document

- [x] 3.1 Re-run `score` (no re-fetch — snapshots are correct after the column-drift fix). Verify: `output/tier-output.json` shows Kimi K3.1 Pro ≈ $3.6812 and Qwen4 Max ≈ $3.2681 at identical prices, `cost_methods` still counts `aa_free`, and review the tier changes in `tier-ranking.md` (expected: costs rise ~1.6–2.1x, picks may shift).
- [ ] 3.2 Re-run `populate` once the LiteLLM stack is up so ordering/cost-derived fields converge (per-token prices themselves unchanged). Verify: LiteLLM `GET /model/info` shows the new orders for affected model groups; per-token price fields identical to before.
- [x] 3.3 Log the double-discount pitfall and the ratio rule in `.docs/LiteLLM-Learnings.md` per the update-litellm-learnings skill (AA cost already embeds measured cache savings; re-price by blended-price ratio; identical prices ⇒ identical cost; free-tier cache-write limitation), and tick the matching ROADMAP item (add under Track 4 if absent). Verify: pitfall entry cites the 2026-11-18 numbers and the AA methodology/API-reference sources; ROADMAP item marked `[x]`.