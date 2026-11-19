# Tasks

## 1. AA cost-breakdown retrieval

- [ ] 1.1 Add a pure parser that turns an AA model-page payload into `{slug: {cost, prices}}` (concatenate Next.js flight chunks, recover model objects, keep those with `intelligenceIndexCostPerTask.cost` plus the four prices) and verify with a stored trimmed page fixture in `tests/fixtures/` — test asserts the expected slugs, component values, and that models without a breakdown are skipped
- [ ] 1.2 Add the breakdown fetch to `AaClient`: anchor slugs ordered from the AA API snapshot (has cost total, then intelligence desc), up to `breakdown_max_pages` pages merged, early stop when coverage is complete; verify with a fake HTTP client that one page is enough when coverage is complete and that a second page is fetched when it is not
- [ ] 1.3 Cache the parsed breakdown to `output/aa_breakdown.json` and record every page fetch through `ScrapeRecorder` (raw body + JSONL entry); verify a second call performs no network request and that a cached run works with `output/` missing
- [ ] 1.4 Fail loudly on a source-shape change (non-empty page, zero breakdowns) and on exhausted anchors; verify with tests asserting an exception carrying expected-vs-observed shape, plus a test that a model without a breakdown leaves the other models untouched
- [ ] 1.5 Add the optional `aa.breakdown_enabled`, `aa.breakdown_url`, and `aa.breakdown_max_pages` config keys with defaults; verify `test_config.py` loads a four-key `aa:` block unchanged and rejects unknown keys as before
- [ ] 1.6 Document the three new keys in `config.example.yaml` with the required WHAT/HOW/EFFECT/WHEN/HOW comments; verify by loading the example and running the config tests

## 2. Exact cost strategy (`aa_breakdown`)

- [ ] 2.1 Implement token derivation from the breakdown (non-cache input, cache-read, cache-write with AA-input fallback, output = answer + reasoning) and re-pricing through the existing `_cost_of`; verify unit tests cover each component and the folded output count
- [ ] 2.2 Add the new method to the precedence chain (`aa_pro` → `aa_breakdown` → `aa_free` → `task_profile`) and record it in `cost_method`; verify tests force each branch and assert the chosen method
- [ ] 2.3 Assert the same-price invariant with real captured values: re-pricing at AA's own prices reproduces AA's total within 1e-6 relative error for at least three fixture models; verify with a dedicated test
- [ ] 2.4 Assert component proportionality: when exactly one provider price differs, the computed delta equals `tokens × price_difference` for that component and the others are unchanged; verify with one test per component
- [ ] 2.5 Guard non-convertible data — missing or zero AA price with a non-zero component cost, missing component, negative component — and fall back to the next method instead of dividing or inventing; verify with tests per guard
- [ ] 2.6 Confirm cache-write derivation falls back to AA's input price when AA publishes no write price (the verified AA convention); verify with a fixture model that has a write cost and a null write price

## 3. Fallback correctness (`aa_free`)

- [ ] 3.1 Replace the cache-blind denominator with `(1−h)·P_in_aa + h·P_cache_read_aa + P_out_aa/ratio` and update the strategy's note text; verify the existing `aa_free` tests pass and a new same-price test reproduces AA's total
- [ ] 3.2 Verify the fallback still differs from the breakdown method on models where cache pricing matters (guards against accidentally preferring the fallback); test asserts `aa_breakdown` is selected whenever a breakdown exists

## 4. Provider parity (CommandCode, OpenCode, OpenRouter)

- [ ] 4.1 Add a table-driven test that builds each provider's real price shape — CommandCode with all four prices and a discounted row, OpenCode with cache-write `None` and a collapsed peak/off-peak price, OpenRouter with cache-read present and cache-write usually `None` — equal to AA's prices, and asserts all three reproduce AA's total
- [ ] 4.2 Add a provenance test per provider shape: a provider that omits cache components falls back to AA's price, is flagged `aa_fallback`, and the invariant still holds on the effective prices
- [ ] 4.3 Verify free models (provider price 0) re-price to 0 without touching the AA-side division; test asserts no exception and a zero cost

## 5. Artifacts and reporting

- [ ] 5.1 Extend `Deployment` with `aa_cost_per_task` and `tokens_per_task`, emit them in `to_dict()`, and add a top-level `aa_cost_basis` block (`fetched_at`, `source`, `models_with_breakdown`) to `tier-output.json`; verify with a payload test that every AA-derived deployment carries both fields
- [ ] 5.2 Add an "AA $/task" column to `tier-output.md` (em dash when AA publishes none) and state the method distribution in the ranking report header; verify with markdown/report assertions
- [ ] 5.3 Print breakdown coverage in the `fetch` and `score` summaries (models with a breakdown, pages fetched, cache hit); verify with CLI tests asserting the lines and the `cost_methods` output

## 6. Documentation

- [ ] 6.1 Rewrite `WALKTHROUGH.md` §5 to describe the three cost paths with the breakdown method first, the exact token derivation, the same-price invariant, and the corrected fallback formula; verify every formula in the section matches the code and the new tests
- [ ] 6.2 Update the `task_profile` comments in `config.example.yaml` and the live `model-tier-populator/config.yaml` so `cache_hit_rate` and `input_output_ratio` are documented as fallback-only, and remove the stale "AA has no cache hits" rationale; verify the configs still load
- [ ] 6.3 Update `model-tier-populator/README.md` where it names the cost strategies so `aa_breakdown` is listed; verify by searching the docs for `aa_free` occurrences and confirming each still describes the fallback accurately

## 7. Integration verification

- [ ] 7.1 Run `uv run --with pytest pytest tests/` and `uv run --with ruff ruff check src tests` from `model-tier-populator/`; verify all tests pass and ruff reports no findings
- [ ] 7.2 Run a live `uv run model-pipeline refresh` and verify `output/aa_breakdown.json` is written, `tier-output.json` shows `cost_methods.aa_breakdown` greater than zero, and one deployment's `aa_cost_per_task` equals its re-price at AA's prices within tolerance
- [ ] 7.3 Review the first live ranking diff against the previous `output/tier-output.json` and confirm the cost increases are explained by the AA reference column (no provider payload, token limit, or populate field changed)

## Workflow follow-up

- Archive the change after the project's review requirements are satisfied.
