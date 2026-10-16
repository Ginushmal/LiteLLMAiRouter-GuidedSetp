# Tasks

## 1. Project Setup

- [x] 1.1 Create `model-pipeline/` sub-project directory with `pyproject.toml` (Python 3.10+, deps: `typesafe-sdk`, `httpx`, `rapidfuzz`) and verify `pip install -e .` succeeds
- [x] 1.2 Create the package structure (`src/model_pipeline/{providers,dedup,scoring,emit,populate}/`) and verify all `__init__.py` files are present
- [x] 1.3 Create `config.yaml` with task_profile, NMB parameters (tier_lambdas, latency_penalty_mu, tier_floors, top_k_per_tier), pricing policies (cache_hit_rate, input_output_ratio, peak_windows, active_window), and provider settings — each with inline comments explaining what/why/when/how — and verify the file parses as valid YAML

## 2. Provider Adapters

- [x] 2.1 Define the `ProviderAdapter` abstract interface with methods `fetch_models()`, `fetch_pricing()`, `available()`, and `to_litellm_deployment()` and verify it can be instantiated with a mock
- [x] 2.2 Implement the CommandCode adapter: fetch models from `api.commandcode.ai/provider/v1/models`, scrape pricing from `commandcode.ai/models` HTML table, and verify a test fetch returns >50 normalized model records
- [x] 2.3 Implement the OpenCode adapter: fetch models from `opencode.ai/inference/go/v1/models`, scrape pricing from the Go plan docs page, and verify a test fetch returns >25 normalized model records
- [x] 2.4 Implement pricing normalization: context-tier averaging, peak/off-peak weighted price (via `weighted_price()` function), and discounted price selection — verify with unit tests using known pricing data
- [x] 2.5 Implement `to_litellm_deployment()` for each provider: correct `litellm_params.model` prefix (`openai/`, `anthropic/`, `gemini/`), `api_base` path per endpoint format, and pricing fields — verify the generated params match the expected format for at least 3 model types per provider
- [x] 2.6 Implement structured scraping forensics: save raw fetched content to `data/raw/<provider>/` and write structured log entries to `data/logs/<provider>/` — verify log files are created with URL, timestamp, status, parse counts

## 3. Canonical Model Dedup

- [x] 3.1 Implement normalization and exact-match logic (lowercase, strip provider prefix, date suffix, size suffix) and verify it resolves known exact matches from both providers
- [x] 3.2 Implement variant-aware matching: parse variant signals (parameter count, effort level, size suffix) from provider model names and verify it rejects mismatches (e.g., qwen3-4b cannot map to qwen3-26b)
- [x] 3.3 Implement Jev pre-filtering: shortlist AA canonical candidates by vendor name, model family, and token overlap — verify the shortlist contains the correct canonical entry for known test cases
- [x] 3.4 Implement the Jev (TypeSafe) Choice classifier integration: `POST api.typesafe.ai/v1/systemone` with provider model name as state and candidate list as criteria — verify the response contains `choice`, `confidence`, and `probabilities`
- [x] 3.5 Implement the mappings CSV output: columns for provider name, model ID, AA slug, AA name, variant, method, confidence, override — verify the CSV is written and human-readable
- [x] 3.6 Implement override-aware mapping loading: when the score phase reads mappings.csv, manual override values take precedence over computed ones — verify with a test CSV containing overrides

## 4. Scoring and Ranking

- [x] 4.1 Implement cost-per-task strategy A (AA Pro per-token re-price with cache overlay) and verify it produces lower cost for providers with cheaper cache-read prices
- [x] 4.2 Implement cost-per-task strategy B (AA free-tier effective-token derivation with cache overlay): back out T_in/T_out from C_aa and prices using input:output ratio, re-price at provider rates — verify with known AA data and provider prices
- [x] 4.3 Implement cost-per-task strategy C (fixed task profile fallback) and verify it uses config token counts multiplied by provider prices
- [x] 4.4 Implement price provenance tracking: record which prices are direct provider prices vs fallbacks in the output — verify `prices_used` fields appear in the output
- [x] 4.5 Implement Pareto frontier at canonical level: aggregate by canonical (best cost), drop dominated models, expand back to deployments — verify with a test set where a dominated canonical is correctly excluded
- [x] 4.6 Implement SOTA-relative tier assignment: compute SOTA intelligence, apply tier floors as fractions — verify tier assignment with known intelligence scores
- [x] 4.7 Implement NMB computation per deployment (lambda * intelligence - cost_per_task - mu * latency) and iterative top-K selection with same-NMB grouping — verify that same-price deployments share an order and count as 1 toward K
- [x] 4.8 Implement consecutive-order assignment: NMB groups get orders 1, 2, 3, ... within each tier's model group — verify the order sequence is correct for a test dataset

## 5. Output Artifact

- [x] 5.1 Implement `tier-output.json` generation: self-contained JSON with per-deployment records (canonical name, provider, model ID, api_base, api_key ref, endpoint format, model group, order, prices with provenance, intelligence, cost_per_task, NMB, tier) — verify the JSON contains all fields needed for populate
- [x] 5.2 Implement the human-readable markdown summary (`tier-output.md`) mirroring the JSON structure — verify it renders correctly with tables per tier

## 6. LiteLLM Population

- [x] 6.1 Implement the LiteLLM management API client: `GET /model/info`, `POST /model/new`, `POST /model/update`, `POST /model/delete`, `POST /config/update` — verify each endpoint returns expected response shapes
- [x] 6.2 Implement diff-based population: compare desired state (from `tier-output.json`) against current state (from `/model/info`), compute add/update/delete operations — verify idempotency (re-running produces zero changes)
- [x] 6.3 Implement per-provider deployment parameter generation in the populate phase: correct `litellm_params.model` prefix and `api_base` per endpoint format — verify at least 3 model types from each provider
- [x] 6.4 Implement inline pricing injection: set `input_cost_per_token`, `output_cost_per_token`, `cache_read_input_token_cost`, `cache_creation_input_token_cost` in `litellm_params` — verify pricing appears in `GET /model/info` after populate

## 7. Three-Phase CLI Integration

- [x] 7.1 Implement the `fetch` CLI command: runs provider adapters + dedup, writes `mappings.csv` and raw artifacts, halts for human review — verify the command runs and produces expected output files
- [x] 7.2 Implement the `score` CLI command: reads `mappings.csv` (with overrides) + AA data + config, computes rankings, writes `tier-output.json` and `tier-output.md` — verify the command runs using only file inputs
- [x] 7.3 Implement the `populate` CLI command: reads `tier-output.json`, diffs against LiteLLM, applies changes — verify the command runs and LiteLLM reflects the desired state
- [x] 7.4 Implement the suggested task-profile output: fetch phase writes `suggested_config.yaml` with provider-published token ratios for human review — verify the file is generated with input/cached/output estimates

## 8. Verification

- [x] 8.1 End-to-end test: run fetch → review mappings.csv → run score → review tier-output.json → run populate → verify LiteLLM shows expected tier groups via `GET /model/info`
- [x] 8.2 Idempotency test: re-run populate with same `tier-output.json` and verify zero changes are applied
- [x] 8.3 Recovery test: clear LiteLLM DB models, re-run populate from existing `tier-output.json`, verify models are restored without re-running fetch or score

## 9. Tiering rework — floor eligibility + Pareto primary/backup

- [x] 9.1 Change tier eligibility from intelligence bands to floors (a model qualifies for every tier whose floor it meets) and verify a cheap capable model is eligible for multiple tiers
- [x] 9.2 Allow multi-tier membership so a selected model can be emitted into several tier model groups; verify the same canonical can appear in more than one group
- [x] 9.3 Split Pareto into primary vs backup (frontier = primary, dominated = backup, never primary) and verify a dominated deployment never wins a primary slot
- [x] 9.4 Fill thin tiers from the tier's own backup (dominated) deployments instead of borrowing lower-tier groups; verify a short tier is filled and backups are marked
- [x] 9.5 Re-verify the cost inversion is fixed: no lower tier's top model costs more than the top model of the tier above it

## 10. Dedup rework — loose pre-filter + Jev variant handling

- [x] 10.1 Remove the variant filter from the shortlist builder: pre-filter purely by name similarity (widen to ~80 candidates) and always force-include the nearest canonical slug; verify a provider name whose AA entry carries an effort parenthetical is no longer dropped
- [x] 10.2 Enrich the Jev call: sharpen the instructions with exact-match variant rules (never merge parameter sizes or effort levels; a bare provider name maps to the base/default variant) and build choice option descriptions that carry each canonical's variant; verify the response contains choice/confidence/probabilities
- [x] 10.3 Keep `parse_variant` only for decorating option text; remove variant-based rejection from the matching path
- [x] 10.4 Re-run fetch and verify previously-unmapped rows that have a real AA entry (`claude-haiku-4-5`, `deepseek-v4-flash-fast`, `kimi-k2-7-code`, ...) now map, while models AA does not track (`fugu-ultra`, `space-bunny`, `glyph-cluster`, ...) stay unmapped

## 11. Serving / version suffix resolution

- [x] 11.1 Add a relaxed exact match: if the full provider name has no canonical slug, strip a trailing serving token (`-fast`, `-highspeed`, `-ultraspeed`, `-turbo`) and retry; verify `mimo-v2.6-pro-ultraspeed` resolves to `mimo-v2-6-pro`
- [x] 11.2 Treat `-next`/`-latest` as version suffixes stripped from both sides so `qwen3.8-flash` resolves to `qwen3-8-flash-next`; verify
- [x] 11.3 Verify a distinct AA entry that owns the token still wins the full-name match (`grok-4-fast` -> `grok-4-fast`, not `grok-4`)
- [x] 11.4 Add a Jev instruction line so residual serving-variant cases map consistently; re-run fetch and verify `glm-5.2-fast` and `mimo-v2.6-pro-ultraspeed` now map

## 12. Ranking explainability report

- [x] 12.1 Add a per-tier full ranking to the score result: every eligible model (frontier primary + dominated backup) ranked by NMB with status (primary selected with order / backup selected with order / cut)
- [x] 12.2 Add a Pareto dominator lookup: for each dominated canonical, name a canonical that beats it on BOTH intelligence and cost
- [x] 12.3 Render `output/tier-ranking.md`: header (floors, lambdas, top-K, NMB formula), a per-model index (intelligence, cost, Pareto state, eligible tiers, selected tiers), the per-tier full rankings, and the Pareto dominator table — verify it is written on `score`
- [x] 12.4 Verify a model excluded from a tier is explained (below the floor / dominated-with-dominator / out-ranked past top-K)

## 13. Combined run command

- [x] 13.1 Add a `run` subcommand (`fetch` -> `score` -> `populate`) that stops at the first failing phase, with `--dry-run` previewing the populate step; verify `uv run model-pipeline run --dry-run` completes the whole chain

## 14. Config-driven model exclusions

- [x] 14.1 Add `exclude.patterns` to config and drop matching models before ranking (case-insensitive substring against provider, provider model ID, display name, canonical slug/name); list them under `excluded_by_config`; verify `Muse Spark ... Contributor` is excluded and absent from every tier
