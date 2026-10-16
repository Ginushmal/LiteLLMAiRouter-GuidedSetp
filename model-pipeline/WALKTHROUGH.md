# model-pipeline — Walkthrough

A quick, visual tour of what the pipeline does and why. Read the
[README](README.md) first if you just want to run it.

---

## 1. The big picture

The goal: turn several messy provider catalogs into a clean, scored, tiered
model list and load it into LiteLLM.

```
                       +---------------------------------------------------+
   PROVIDERS           |              CANONICAL HUB                        |
   (adapters)          |         Artificial Analysis (AA)                  |
                       |  intelligence index + reference prices            |
  +-------------+      |                                                   |
  | CommandCode |--+   |  CanonicalModel:                                  |
  +-------------+  |   |    slug, name, intelligence, aa prices, cost/task |
  | OpenCode    |--+-->|                                                   |
  +-------------+  |   +---------------------------------------------------+
  | (more)      |  |              ^
  +-------------+  |              | name matching
                   |              |
   fetch_models()  |      +-------+--------+      the "hub" is the join key:
   fetch_pricing() |      |  DEDUP         |      every provider model maps to
                   |      |  exact -> Jev  |      ONE canonical identity
                   +----->|  (classifier)  |
                          +-------+--------+
                                  |
                                  v
                          Deployment = (canonical x provider x price)
                                  |
             +--------------------+---------------------+
             |                                          |
      +------v-------+                          +--------v-------+
      |  COST MODEL  |   $ per task             |  RANK          |
      |  (3 modes)   |                          |  Pareto        |
      +--------------+                          |  SOTA tiers    |
                                                |  NMB top-K     |
                                                +--------+-------+
                                                         v
                                                 tier-output.json
                                                         |
                                                 +-------v--------+
                                                 |  POPULATE      |
                                                 |  diff + apply  |
                                                 +-------+--------+
                                                         v
                                                 LiteLLM (DB)
                                                 ultra/pro/flash/flash-lite
```

---

## 2. The three phases

Each phase is a separate command that reads and writes files, so you can re-run
one without the others.

```
 PHASE 1: fetch
 ────────────────────────────────────────────────────────────────────────────
   providers  -->  models + prices  -->  dedup (exact -> Jev)  -->  mappings.csv
                       |
                       +--> output/models_snapshot.json   (so score is offline)
                       +--> output/suggested_config.yaml  (advisory)
                       +--> data/raw/*, data/logs/*       (scrape forensics)

   PAUSE for a human to review mappings.csv (fix low-confidence rows).

 PHASE 2: score
 ────────────────────────────────────────────────────────────────────────────
   mappings.csv + models_snapshot.json + aa_snapshot.json + config.yaml
        |
        +--> cost-per-task per deployment
        +--> Pareto frontier (advisory)
        +--> tier by SOTA-relative intelligence
        +--> NMB rank + top-K + backfill
        |
        +--> output/tier-output.json  (+ .md)

   PAUSE for a human to review the tier list.

 PHASE 3: populate
 ────────────────────────────────────────────────────────────────────────────
   tier-output.json  -->  diff vs GET /model/info  -->  add / update / delete
                                                     (idempotent)
```

Why split? So a DB wipe can be fixed by re-running only `populate`, and tuning a
score knob does not force a re-fetch.

---

## 3. The data model (the chain)

```
 RawModel                 CanonicalModel                 Deployment
 (one provider's view)    (one identity, from AA)        (a scored pair)
 ─────────────────        ──────────────────────         ──────────────────
 provider                 slug                           canonical_slug
 model_id                 name                           provider
 display_name             intelligence                   model_id
 endpoint_type            aa prices                      cost_per_task
 pricing {in,out,         aa cost_per_task               intelligence
   cache_read,cache_write}                               nmb, tier, order
                                                         litellm_params  <-- populate-ready
```

The canonical model is the join hub. Many provider deployments can point at the
same canonical (e.g. `glm-5.3-flash` exists on both CommandCode and OpenCode).

---

## 4. De-duplication (phase 1)

Provider names are messy: `openai/xiaomi/mimo-v2.6-pro`, `qwen3-8-max-0902`,
`claude-haiku-4-5-20251001`. AA names are their own thing. We map each provider
model to a canonical identity in two steps:

```
 provider name
      |
      v
 +--------------------------------------+
 | 1. EXACT match                       |   normalize_key():
 |    normalize + compare to AA slug    |     lowercase, drop provider prefix,
 |    ~90/115 resolve here, confidence 1|     drop "(...)", drop dates, alnum only
 +------------------+-------------------+
                    | no unique hit
                    v
 +--------------------------------------+
 | 2. JEV classifier                    |   TypeSafe "System One" model,
 |    state   = provider model name     |   reached via CommandCode
 |    criteria= shortlist of AA names   |   /provider/v1/systemone
 |    -> choice + confidence + probs    |   returns a calibrated choice
 +------------------+-------------------+
                    v
             mappings.csv
```

**Variant safety.** Names that differ only by parameter count or effort are never
merged:

```
 Qwen3-4B      x  Qwen3-26B        (params differ -> rejected)
 mimo-2.6      x  mimo-2.6-high    (effort present on one side -> rejected)
```

Exact matching is by **AA slug** (unique per variant); the strict variant check
filters the candidate list handed to Jev.

**The review gate.** Every mapping is written to `mappings.csv` with a method and
confidence. Low-confidence rows are flagged; you can type a canonical slug into
the `override` column and `score` will honour it.

```
provider,model_id,canonical_slug,canonical_name,variant,method,confidence,low_confidence,override,probabilities
commandcode,claude-sonnet-5-5,claude-sonnet-5-5,Claude Sonnet 5.5 (Max...),,exact,1.0000,,,{"claude-sonnet-5-5":1.0}
commandcode,xiaomi/mimo-v2.6-pro-ultraspeed,mimo-v2-6-pro,MiMo V2.6 Pro,,jev,0.6700,yes,,{"mimo-v2-6-pro":0.7,...}
```

---

## 5. Cost-per-task (phase 2)

We do not compare raw per-token prices — we compare the **dollar cost of one
representative task**, because a smarter model needs fewer tokens and providers
price cache reads very differently.

```
 cost_per_task = fresh_input  x P_in
               + cached_input x P_cache_read      (cache hit rate ~98%)
               + output       x P_out
               + reasoning    x P_reasoning
               + cache_write  x P_cache_write
```

The **token counts** come from AA (so model efficiency is included); the
**prices** come from the provider being scored. Three ways to get the counts,
chosen automatically:

| Mode | When | How |
|------|------|-----|
| `aa_pro` | AA Pro token counts available | re-price AA's real per-task tokens |
| `aa_free` | default (free tier) | back out tokens from AA's `cost_per_task` and prices using `input:output` ratio |
| `task_profile` | AA has no data for the model | use the fixed task profile from `config.yaml` |

The free-tier back-out (`aa_free`):

```
 T_in  = aa_cost_per_task / (p_in_aa + p_out_aa / ratio)
 T_out = T_in / ratio
 cost  = (1-h)*T_in*P_in + h*T_in*P_cache + T_out*P_out      h = cache_hit_rate
```

Whenever a provider omits a price (e.g. no cache price), AA's price is used and
the artifact records it as `aa_fallback` so you can see where each number came from.

---

## 6. Ranking (phase 2)

### 6a. Pareto frontier — advisory

A model is *dominated* if another model is both smarter and cheaper. We mark
this but **do not drop** dominated models — a hard filter collapses the pool
(one cheap-and-decent model dominates almost everything), leaving empty tiers.

```
 intelligence
   ^
   |   * Opus          <- everyone on the top-left edge is "on the frontier"
   |     *  Sonnet          (nothing is both smarter AND cheaper)
   |        *   Astra
   |            *  Gemini
   |                 * GPT-6.1 Sol
   |                       * MiMo V2.6 Pro   <- dominates the whole shaded region
   |      . . . . . . . . . . . . . . . .       (smarter & cheaper than these)
   |     . dominated  .  .  .  .  .  .  .
   +----------------------------------------> cost
```

### 6b. Tiers — SOTA-relative

Floors are fractions of the current best intelligence, so tiers auto-scale:
`Ultra = 0.90·SOTA`, `Pro = 0.80·SOTA`, `Flash = 0.50·SOTA`, `Flash Lite = rest`.

### 6c. NMB top-K + backfill

Within a tier, rank by value:

```
 NMB = lambda * intelligence - cost_per_task - mu * latency
```

- Deployments of the **same canonical at the same cost** = **one group** → one
  LiteLLM `order` (they load-balance).
- **Different cost** = separate groups → separate orders (failover chain).
- Take the top-K **groups**; if a tier has fewer than K, backfill from the best
  remaining lower-tier groups (marked `backfilled_from`).

### Worked example

```
 Tier = Flash (K = 5)
 ---------------------------------------------------------------
 order 1: step-5-preview-free   OpenCode   $0.0000/task   <- group A
 order 2: Claude Haiku 5.5      CommandCode $0.1294/task  <- group B
 order 3: claude-haiku-5-5      OpenCode    $0.3881/task  <- group C (same model, pricier)
 order 4: Step 5 Preview        CommandCode $0.4559/task  <- group D
 order 5: GLM-5.3 Flash         CommandCode $0.1623/task  <- group E  \
 order 5: glm-5.3-flash         OpenCode    $0.1623/task  <- group E  / same cost = same order
```

Failover: `order 1 -> 2 -> 3 -> 4 -> 5`. If a whole tier fails, LiteLLM falls
through to the group's configured fallbacks.

---

## 7. Populate (phase 3)

```
 tier-output.json                         GET /model/info
   desired deployments        vs           current deployments
        |                                        |
        +----------------+-----------------------+
                         v
         match by model_info.id  (e.g. mp::flash-tier::commandcode::claude-haiku-5-5)
                         v
        +----------+----------+----------+
        |  new?    | changed? |  gone?   |
        |  /model/new | /model/update | /model/delete |
        +----------+----------+----------+
                         v
                     LiteLLM DB
```

Pricing is injected inline (`input_cost_per_token`, `output_cost_per_token`,
`cache_read_input_token_cost`, `cache_creation_input_token_cost`), so no custom
cost map is needed for these models. Only models whose id starts with `mp::` are
touched — file-based `config.yaml` models are left alone.

---

## 8. Config reference (quick)

All in [`config.yaml`](config.yaml). The ones you will actually tune:

| Setting | Meaning |
|---------|---------|
| `nmb.tier_floors` | tier entry thresholds as fractions of SOTA |
| `nmb.tier_lambdas` | willingness to pay per intelligence point, per tier |
| `nmb.top_k_per_tier` | groups kept per tier |
| `nmb.latency_penalty_mu` | dollars lost per second of latency (0 = off) |
| `task_profile.cache_hit_rate` | share of input tokens that are cache reads |
| `task_profile.input_output_ratio` | used by the `aa_free` cost back-out |
| `pricing.context_tier_policy` | `average` / `base` / `high` |
| `pricing.active_window_utc` + `peak_windows_utc` | peak/off-peak price weighting |
| `litellm.tier_model_groups` | tier name -> LiteLLM model group |

---

## 9. Code map

```
src/model_pipeline/
  cli.py                 fetch | score | populate
  config.py              config.yaml + .env loading
  models.py              RawModel, CanonicalModel, Mapping, Deployment
  http.py                HTTP client + scrape forensics (raw + logs)
  pricing.py             context-tier / peak-off-peak normalization
  textutil.py            name normalization, price parsing

  providers/
    base.py              ProviderAdapter interface + shared payload assembly
    commandcode.py       CommandCode adapter (API + HTML pricing)
    opencode.py          OpenCode adapter (API + docs tables)
    registry.py          names -> adapters

  dedup/
    normalize.py         exact matching (slug-preferred)
    variant.py           param/effort variant safety
    prefilter.py         candidate shortlist for Jev
    jev.py               Jev (TypeSafe) client
    mapper.py            exact -> Jev orchestration
    mappings_csv.py      mappings.csv read/write (+ overrides)

  scoring/
    aa.py                Artificial Analysis client + snapshot cache
    cost.py              cost-per-task (3 strategies) + provenance
    pareto.py            advisory Pareto frontier
    tiers.py             SOTA-relative tiering
    nmb.py               NMB ranking + grouping
    pipeline.py          ties it together -> ScoreResult

  emit/
    output.py            tier-output.json + .md
    snapshot.py          models_snapshot.json
    suggested_config.py  suggested task-profile from provider docs

  populate/
    litellm_client.py    management API client
    sync.py              diff-based, idempotent apply
```

---

## 10. Adding a provider

1. Add a block under `providers:` in `config.yaml` (api base, models URL, pricing
   URL, key env, `litellm` api bases, `supported_endpoints`).
2. Write `providers/<name>.py` implementing `ProviderAdapter`
   (`fetch_models`, `fetch_pricing`, `to_litellm_deployment`).
3. Register it in `providers/registry.py`.

Everything downstream (dedup, scoring, populate) works unchanged.

---

## 11. Gotchas worth knowing

- **CommandCode Claude needs `api_base: .../provider`** (LiteLLM appends
  `/v1/messages`). Do **not** add an `Authorization` header — LiteLLM sends two
  credentials and CC rejects them.
- **OpenCode needs `x-opencode-session`** on every request — injected via
  `extra_headers` (one static value for gateway traffic).
- **OpenCode `responses`/`google` models are deferred** (grok / gpt-luna / muse /
  gemini) — they need Responses-API / Gemini wiring, so they are excluded.
- **Artificial Analysis free tier** is at `/api/v2/language/models/free`
  (the plain `/language/models` requires Pro). Snapshot is cached; limit 100/day.
- **Scraping forensics**: every fetch dumps the raw HTML/JSON to `data/raw/` and
  a JSON-lines log to `data/logs/`, so a broken parse is diagnosable from the
  artifacts alone.
- **Idempotency**: `populate` compares only the fields it sets and ignores the
  masked `api_key`, so a re-run reports `unchanged=N`.
