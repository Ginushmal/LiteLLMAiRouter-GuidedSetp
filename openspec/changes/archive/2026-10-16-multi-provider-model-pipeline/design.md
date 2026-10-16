# Design

## Context

See `proposal.md` — Why. The current setup is a single-provider (CommandCode) LiteLLM instance with manually configured tiers in `config.yaml`. We are building a reusable Python pipeline that aggregates multi-provider catalogs and dynamically populates LiteLLM's database via its management API.

Key constraints from our exploration:
- LiteLLM's `store_model_in_db: true` is already enabled; `/model/new`, `/model/update`, `/model/delete`, `/model/info`, `/config/update` all work without restart.
- Artificial Analysis free tier provides intelligence scores, input/output pricing, and `cost_per_task.total_cost`. Pro tier (which we likely won't have) adds per-task token counts and cost breakdowns.
- Jev (TypeSafe) is a "System One" model with typed Choice/Score/Noul primitives — ideal for classification-style dedup. It accepts up to 255 options per Choice question.
- CommandCode and OpenCode both publish per-request token estimates (~800 fresh input, ~50K cached, ~200 output) representing a ~98% cache hit rate for agentic coding workloads.
- OpenCode models span four endpoint formats (Chat Completions, Responses, Messages, Google), requiring per-model `litellm_params` mapping.

## Goals / Non-Goals

**Goals:**
- Three independently invocable phases (`fetch`, `score`, `populate`) with file-based handoffs, allowing re-run of any phase in isolation.
- Provider-agnostic adapter interface with per-provider strategies for fetching, pricing normalization, and LiteLLM deployment parameter generation.
- Dedup that correctly handles model variants (parameter count, effort level) and never cross-matches them.
- Cost-per-task computation that captures model efficiency (from AA benchmark data) and cache effects (from provider docs).
- Idempotent populate that converges to desired state on re-run.
- All tuning parameters in a documented config file.

**Non-Goals:**
- Building on or extending the existing temp scripts (`smart_router.py`, `update_cost_map.mjs`).
- Managing the `custom_cost_map.json` for pipeline-managed models (inline pricing via the API replaces it).
- Filtering models by plan credit caps (the LiteLLM router handles routing around exhausted caps).
- Supporting more than two providers in the initial implementation (architecture allows adding more).
- Implementing the Jev complexity_router / Auto Router setup (that already exists in `config.yaml` and stays there).

## Decisions

### 1. Three-phase pipeline with file-based handoffs
**Decision**: Separate `fetch`, `score`, and `populate` into three CLI entry points connected by persistent artifacts (CSV and JSON files).

**Why**: The user explicitly wants to re-run populate after a DB wipe without recomputing, review mappings before scoring, and score with different parameters without re-fetching. File-based handoffs make every phase independently rerunnable and auditable.

**Alternatives considered**:
- Single monolithic command with intermediate caching — rejected because the user wants to halt for human review between phases and re-run individual phases.
- Database-backed handoffs — rejected because CSV/JSON files are simpler to review and edit manually.

### 2. Provider adapter interface with two fetches
**Decision**: The adapter interface has two separate methods: `fetch_models()` (from the API) and `fetch_pricing()` (from documentation/scraping). A third method `to_litellm_deployment()` generates provider-specific `litellm_params`.

**Why**: Pricing is not available from the `/models` API for either provider. CommandCode publishes prices in an HTML table; OpenCode publishes them in a documentation page. Each provider has different endpoint formats requiring different LiteLLM parameter mappings.

### 3. Jev Choice classifier with a loose, name-only pre-filter
**Decision**: Use Jev's Choice primitive for name matching. Pre-filter the AA canonical list to ~80 candidates **purely by name similarity** (vendor/family/token overlap), with no variant-based exclusion, and force-include the nearest canonical slug so the obvious candidate can never be lost to ranking noise. Variant disambiguation (parameter count, effort level) is delegated to Jev via explicit instructions and self-describing option text — each choice option carries its variant description. There is **no programmatic variant guard**. Serving tokens (`-fast`, `-highspeed`, `-ultraspeed`, `-turbo`) and version suffixes (`-next`, `-latest`) do not change a model's identity: they are resolved deterministically by a **relaxed exact match** — strip a trailing serving token from the provider name and retry, and strip `-next`/`-latest` from both sides — which runs **before** Jev, while a distinct AA entry that owns the token (e.g. `grok-4-fast`) still wins the full-name match first.

**Why**: The earlier pre-filter applied a *strict variant filter* before calling Jev, and it destroyed the shortlist. AA's display names almost always carry an effort parenthetical (`Claude Haiku 4.5 (Max, Default Fallback)`) while provider names are bare (`claude-haiku-4-5`), so strict effort-matching rejected the correct entry and Jev was left choosing among wrong options — e.g. `claude-haiku-4-5-20251001` was only offered `claude-3-haiku` / `claude-3-5-haiku` and correctly returned "unmapped". That was the main source of unmapped rows. Jev is far better at variant disambiguation than a brittle name parser, so the pre-filter's only job is to cast a wide, name-based net; Jev picks the exact variant given clear rules and variant-bearing options. The "unmapped" option still lets Jev reject models AA does not track, and low-confidence answers remain recorded for human review.

**Alternatives considered**:
- Strict variant pre-filter (previous) — dropped the correct candidate whenever AA annotated effort/params in the name; caused most unmapped rows.
- Post-Jev variant guard — rejected: with clear instructions and variant-bearing option text Jev handles it, and a hard guard would re-introduce the same false rejections.
- Embedding similarity — rejected as a primary approach; Jev is purpose-built and returns calibrated probabilities.
- Pure fuzzy matching (RapidFuzz) alone — rejected; fails on creative naming (e.g. "Muse Spark 1.3" vs "muse-spark-1.3-contributor").
- Passing all 700 AA models — rejected due to the 255-option limit.

### 4. Cost-per-task: tiered strategy with cache overlay
**Decision**: Three cost computation methods selected by AA data availability: (A) Pro-tier per-token re-price with cache, (B) free-tier effective-token derivation with cache, (C) fixed task-profile fallback. Cache is overlaid on (A) and (B) using a configurable cache hit rate derived from provider docs.

**Why**: AA's benchmark has no cache hits (unique prompts), but real agentic workloads have ~98% cache hit rates. Backing out effective token counts from AA's `cost_per_task` preserves model efficiency signals (smarter models use fewer tokens) while the cache overlay reflects real-world costs.

**The free-tier derivation formula** (the default path):
```
T_in  = C_aa / (p_in_aa + p_out_aa / r)    # back out input tokens
T_out = T_in / r                              # output tokens from ratio
C_provider = (1-h)*T_in*p_in_p + h*T_in*p_cache_p + T_out*p_out_p
```
Where `h` = cache hit rate (config), `r` = input:output token ratio (config), `C_aa` = AA's cost_per_task, `p_*_aa` = AA prices, `p_*_p` = provider prices.

### 5. Tier eligibility by intelligence floor; Pareto as primary-vs-backup
**Decision**: Tiers are capability *floors* (minimums), not bands — a model is eligible for every tier whose floor it meets, so a cheap capable model can serve both lower and higher tiers (multi-tier membership). Pareto splits candidates into PRIMARY (frontier) and BACKUP (dominated): a dominated model is never selected as a primary pick, but pads a tier that is short of top-K. NMB ranks the tier-eligible set; same-NMB groups share a LiteLLM order.

**Why**: Two failures of the earlier design drove this. (1) Capability *bands* excluded cheap smart models from the cheap tiers, so a "cheap" tier ended up full of dumb, overpriced models — the top of Flash Lite cost more than the top of Flash. Floors let cheap capable models (e.g. MiMo V2.6 Pro, ~$0.05/task, intelligence 46.3) enter the cheap tiers, so a lower tier is topped by cheap models and the inversion disappears. (2) Making Pareto purely advisory preserved its label but discarded its purpose — wasteful (both dumber and costlier) models re-entered the tiers as top picks. Splitting into primary/backup keeps Pareto's guarantee (no wasteful model ever wins a primary slot) while still allowing backups so tiers stay full.

**Alternatives considered**:
- Capability bands (previous) — caused the cost inversion: the cheapest models are also mid-intelligent, so they never reached the low tiers, which filled with dominated models.
- Hard Pareto (drop all dominated) — emptied the low tiers entirely (every low-intelligence model is dominated), losing failover options.
- Advisory Pareto (previous) — let wasteful models top a cheap tier.
- Lower-tier borrowing for backfill — superseded: with floors a tier has its own eligible set, so it fills from its own backups instead.

### 6. Consecutive-order failover (not same-order weighted failover)
**Decision**: Selected NMB groups get consecutive `order` values (1, 2, 3, ...). Same-NMB deployments share an order. Failover follows pure NMB rank.

**Why**: The user uses `cost-based-routing` in `router_settings`, which is incompatible with `enable_weighted_failover` (which requires `simple-shuffle`). Consecutive orders give deterministic failover: cheapest first, then next, matching the "same model before different model" preference when the NMB difference is small.

### 7. Inline pricing via LiteLLM API (no custom cost map)
**Decision**: Set pricing directly on each deployment via `litellm_params` fields when calling `/model/new` or `/model/update`. Do not write entries to `custom_cost_map.json` for pipeline-managed models.

**Why**: The LiteLLM management API accepts `input_cost_per_token`, `output_cost_per_token`, `cache_read_input_token_cost`, `cache_creation_input_token_cost` per deployment. This eliminates the dual source-of-truth problem (config file pricing vs cost map pricing) and the known `base_model` provider-prefix cost-lookup bug (#22257).

### 8. Scraping forensics: raw artifacts + structured logs
**Decision**: Every scrape saves the raw fetched content to `data/raw/<provider>/<timestamp>.<ext>` and writes a structured log entry (URL, timestamp, HTTP status, parse counts, errors) to `data/logs/<provider>/<date>.log`.

**Why**: The user explicitly wants an AI agent to be able to diagnose scraping failures by reading the raw artifacts and logs when provider page structures change.

### 9. Ranking explainability report
**Decision**: The `score` phase writes `output/tier-ranking.md`: a per-tier full ranking of every *eligible* model (ranked by that tier's NMB, with the NMB inputs — lambda, intelligence, cost-per-task — the Pareto state, and selected-or-cut status), a per-model index showing which tiers each model was eligible for and selected in, and a Pareto section that names, for each dominated model, a model that dominates it. The JSON's `tier-output.json` stays the machine artifact; this is the human one.

**Why**: The pipeline drops models for several non-obvious reasons (below a tier's intelligence floor, dominated by a cheaper+smarter model, or out-ranked on NMB past the top-K). Without the numbers a user cannot tell why an expected model was excluded. Showing the full ranked list per tier plus the Pareto dominator makes every exclusion auditable and turns "why isn't X in Pro?" into a lookup.

**Alternatives considered**:
- Only list the selected models (status quo) — rejected: it hides the cutoff and the reason for exclusion.
- JSON-only diagnostics — rejected: the point is human readability.

### 10. Config-driven model exclusions
**Decision**: A top-level `exclude.patterns` list drops matching models before ranking. Each pattern is matched case-insensitively as a **substring** against the deployment's provider, provider model ID, display name, canonical slug, and canonical name. Excluded models never enter a tier and are listed under `excluded_by_config` in the report.

**Why**: Some models are unwanted regardless of price/value — e.g. Meta "Muse Spark ... Contributor" variants, served cheaply in exchange for permission to train on your prompts. A substring match lets a user opt out of a whole class (`contributor`, `free`) with one entry, and an exact slug/id also works because it is itself a substring. Doing it in the pipeline (not in LiteLLM) keeps the exclusion visible in the artifacts and out of the tier DB entirely.

**Alternatives considered**:
- Per-provider enable/disable — too coarse (drops a whole provider, not a specific model).
- LiteLLM-side access control — rejected: the model would still be scored and occupy a tier slot; the user wants it gone from the ranking.

## Risks / Trade-offs

- **[AA free-tier rate limit (100 req/day)]** → Cache the AA snapshot to disk after fetch; score phase reads from cache. Daily schedule stays well within limits.
- **[Provider pricing page structure changes]** → Scraping breaks silently → Structured logs + raw artifacts enable AI-assisted diagnosis. Human review of mappings.csv catches anomalies (e.g., zero prices).
- **[Jev misclassification on close variants]** → Confidence score marked in CSV; human reviews low-confidence rows. Variant-aware matching rejects conflicts before Jev is called.
- **[AA free tier lacks per-task token counts]** → Effective-token derivation is approximate (assumes uniform input:output ratio across models). Acceptable for ranking purposes since the ratio is the same for all models; actual costs may differ.
- **[Context-tiered pricing ambiguity]** → Using the average may misrepresent costs for models with extreme tier gaps (e.g., 2x price difference). Trade-off accepted for simplicity; can switch to base-tier-only if needed.
- **[Peak/off-peak scheduling]** → The weighted average assumes uniform traffic across the active window. If usage is skewed toward peak hours, actual costs will be higher than estimated.
- **[Multiple endpoint formats at OpenCode]** → The per-model endpoint mapping table is maintained in the adapter config. If OpenCode adds new formats, the adapter needs updating.

## Migration Plan

1. Build the pipeline as a standalone `model-pipeline/` sub-project with its own `pyproject.toml`.
2. Run `fetch` phase → review `mappings.csv` → run `score` phase → review `tier-output.json` → run `populate` phase.
3. Verify LiteLLM shows the expected tier groups via Admin UI or `GET /model/info`.
4. The existing `config.yaml` `model_list` entries can coexist with DB-managed models (they'll show side-by-side). Once verified, the config `model_list` can be removed (config file retained for infrastructure settings).
5. Rollback: if populate produces incorrect results, re-run populate with a corrected `tier-output.json` or clear the LiteLLM DB and re-populate from a known-good artifact.

## Open Questions

- **AA Pro token count field names**: The exact JSON field names for per-task token counts (`artificial_analysis_intelligence_index_token_counts`) need to be confirmed at implementation time against the actual API response. The free-tier derivation path is the default, so this doesn't block implementation.
- **Jev pre-filter heuristic tuning**: The vendor/family/token-overlap heuristic for shortlisting AA candidates needs empirical testing against the actual model name distribution. Initial implementation will use a simple approach; can be refined based on mapping accuracy.
