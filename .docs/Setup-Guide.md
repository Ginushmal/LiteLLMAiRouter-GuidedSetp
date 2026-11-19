# LiteLLM Setup Guide: From Zero to Teams & Keys

> The order this stack was actually built, step by step: config + Compose + Podman, then models + env, then the custom cost map, then routing (`order` + `routing_groups`), then identity (teams / users / keys).
>
> **No API calls are made by hand.** Everything is done through the four repo files and the **Admin UI**.
>
> **Concepts live in [LiteLLM-Learnings.md](./LiteLLM-Learnings.md).** This file is the *how*.

---

## What you end up with

Monolithic **Mode C (Hybrid)**: a database **and** a `config.yaml`.

| Piece | Configured in | Managed via |
|-------|---------------|-------------|
| Models & routing | `config.yaml` | config.yaml (bootstrap); UI additions are **additive** |
| Pricing | `custom_cost_map.json` (remote URL) | the file — keyed by **exact `litellm_params.model`** |
| Teams / Users / Keys | database | **Admin UI** |
| Budgets / rate limits / spend | database | **Admin UI** |
| Secrets | `.env` | the file |

### Files

| File | Role |
|------|------|
| `docker-compose.yml` | the two services (litellm + db) |
| `config.yaml` | models, routing, defaults — mounted to `/app/config.yaml` |
| `custom_cost_map.json` | full copy of LiteLLM's cost map + our CommandCode entries |
| `.env` | secrets (gitignored) |

---

# Part 1 — Bring the stack up

## Step 1 — Prerequisites

- **Podman** (Desktop or CLI) with `podman compose`, running
- A **CommandCode** Goat Subscription API key
- A **public Git repo** (for hosting the custom cost map — a raw URL LiteLLM can fetch)

---

## Step 2 — Create `docker-compose.yml`

Two services: `litellm` (the gateway) and `db` (Postgres). The gateway is made **config-driven** by three lines: the `volumes` mount, `STORE_MODEL_IN_DB`, and `command`.

```yaml
services:
  litellm:
    image: docker.litellm.ai/berriai/litellm:main-stable
    ports:
      - "4000:4000"
    volumes:
      - ./config.yaml:/app/config.yaml        # <- makes config.yaml the bootstrap
    environment:
      LITELLM_MASTER_KEY: ${LITELLM_MASTER_KEY:?set it in .env}
      LITELLM_SALT_KEY: ${LITELLM_SALT_KEY:?set it in .env}
      DATABASE_URL: postgresql://litellm:litellm@db:5432/litellm
      STORE_MODEL_IN_DB: "True"               # <- enables Admin UI model management + hybrid mode
      # JEV_API_KEY: ...                      # added in Step 6 (router classifier)
      # LITELLM_MODEL_COST_MAP_URL: ...       # added in Step 8
    depends_on:
      db:
        condition: service_healthy
    command: ["--config", "/app/config.yaml"]  # <- run with the mounted config

  db:
    image: postgres:16
    environment:
      POSTGRES_USER: litellm
      POSTGRES_PASSWORD: litellm
      POSTGRES_DB: litellm
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U litellm"]
      interval: 5s
      timeout: 5s
      retries: 10
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

`${VAR:?message}` means Compose **requires** the variable in `.env` and stops with that message if it is missing.

> Add the provider key and cost-map URL later (Steps 6 and 8) — this mirrors how we built it.

---

## Step 3 — Create `.env`

```env
LITELLM_MASTER_KEY=sk-<generate-me>
LITELLM_SALT_KEY=sk-<generate-me>
```

Generate the two LiteLLM keys (Git Bash / Linux / macOS):

```bash
printf 'LITELLM_MASTER_KEY=sk-%s\nLITELLM_SALT_KEY=sk-%s\n' "$(openssl rand -hex 32)" "$(openssl rand -hex 32)"
```

> ⚠️ **Never change `LITELLM_SALT_KEY`** after credentials are stored — it encrypts them and they become unreadable.
> ⚠️ `.env` is **gitignored**. Never paste real keys into tracked files.

---

## Step 4 — Run the stack in Podman

```powershell
podman compose -f docker-compose.yml up -d
```

Wait ~30s for Postgres, then confirm:

```powershell
podman compose -f docker-compose.yml logs litellm
```

Expect `Uvicorn running on http://0.0.0.0:4000`. Then open **http://localhost:4000/ui** and sign in with `LITELLM_MASTER_KEY`.

---

# Part 2 — Models and provider wiring

## Step 5 — Add models to `config.yaml`

Each entry in `model_list` is a **deployment**. Multiple entries with the **same `model_name`** form a load-balanced group.

```yaml
model_list:
  - model_name: flash-tier            # the name apps request
    litellm_params:
      model: openai/deepseek/deepseek-v4.1-flash   # openai/<provider-model> for OpenAI-compatible APIs
      api_base: https://api.commandcode.ai/provider/v1
      api_key: os.environ/COMMANDCODE_API_KEY      # secret stays in .env
      order: 1                                     # failover priority (Step 10)
    model_info:
      base_model: openai/deepseek/deepseek-v4.1-flash
```

Key rules:

| Item | Meaning |
|------|---------|
| `model_name` | what your apps send (`model: "flash-tier"`) |
| `openai/` prefix | use the OpenAI-compatible protocol; everything after it is sent to the provider |
| `api_base` | the provider's endpoint |
| `api_key: os.environ/…` | read the secret from the environment (never inline it) |
| same `model_name` | the entries are load-balanced together |
| `order` | failover priority (lower = tried first) |

This project defines **two groups** from five deployments:

| Group | Deployments |
|-------|-------------|
| `flash-tier` | DeepSeek V4.1 Flash (order 1), Qwen 3.8 Omni Flash (order 1), DeepSeek V4 Flash (order 2) |
| `pro-tier` | DeepSeek V4 Pro, Qwen 3.7 Plus |

### The `general_settings` block

```yaml
general_settings:
  store_model_in_db: true                     # Admin UI model management; DB-managed tier models
  store_prompts_in_spend_logs: true           # keep request/response payloads in spend logs
  forward_client_headers_to_llm_api: true     # forward client x-* headers upstream
```

The last line is what lets a client send OpenRouter's `x-session-id` header. OpenRouter uses that id as its **sticky-routing key**: it keeps a conversation on the same upstream provider, so the provider's prompt cache stays warm (verified: 1304-token prompt, 0 cached tokens on turn 1, 1280 on turn 2 through the gateway). The body field `session_id` works too, and OpenRouter prefers it over the header. LiteLLM strips `authorization`, `x-api-key` and `x-litellm-api-key` before forwarding, so enabling this does not leak client credentials - but it does forward *every* `x-*` header the client sends.

### Model metadata (media, tools, reasoning)

Add the model's capabilities to `model_info`. Clients read these from `/model/info` and use them to decide what to offer; the gateway itself does not gate images on the flag.

```yaml
    model_info:
      mode: chat
      supports_vision: true
      supports_pdf_input: true
      supports_audio_input: false
      supports_video_input: false
      supports_function_calling: true
      supports_response_schema: true
      modalities:
        input: [text, image, pdf]
        output: [text]
      supports_reasoning: true
      reasoning_effort_levels: [low, high, max]
      supports_low_reasoning_effort: true
      supports_high_reasoning_effort: true
      supports_max_reasoning_effort: true
```

| Field group | What it advertises |
|-------------|--------------------|
| `supports_vision` / `supports_pdf_input` / `supports_audio_input` / `supports_video_input` | Media input |
| `supports_audio_output` | Media output (audio) |
| `modalities.input` / `output` | Exact modality list (preferred over the individual flags) |
| `supports_function_calling` / `supports_response_schema` | Tools / structured output |
| `supports_reasoning` | Reasoning capability |
| `reasoning_effort_levels` + `supports_*_reasoning_effort` | Accepted effort levels |

**Admin UI:** Models + Endpoints → **Add Model** → **Advanced Settings** → **Model Info** (JSON). For an existing model: click the model ID → **Edit Settings** → **Model Info** → **Save Changes**. The form has no dedicated vision/PDF/reasoning dropdowns; this JSON field is the control.

> For an `anthropic/...` deployment, `supports_reasoning: true` is required for `reasoning_effort` to be forwarded. Without it, `drop_params: true` silently drops the field and the upstream receives no thinking budget.

---

## Step 6 — Wire secrets into Compose

The gateway container needs only its **own** settings: master key, salt key, the Jev classifier key, and the cost map URL. Provider API keys are **not** injected — `model-pipeline` publishes each deployment with its provider key as a raw value, and LiteLLM stores it encrypted with `LITELLM_SALT_KEY`.

```yaml
    environment:
      # ...
      TYPESAFE_API_KEY: ${JEV_API_KEY:?set it in .env}
      TYPESAFE_API_BASE: https://api.commandcode.ai/provider   # URL becomes {base}/v1/systemone
```

```env
JEV_API_KEY=sk-<one-commandcode-key>
```

> If you added a model **by hand** with `api_key: os.environ/SOME_VAR` (Step 5), that variable must still be present in the `litellm` service environment. Deployments published by the pipeline do not need it.

> Editing Compose/.env is a **container-spec change**, so apply it with `--force-recreate` (Step 7), not `restart`.

---

## Step 7 — Apply and confirm

```powershell
podman compose -f docker-compose.yml up -d --force-recreate litellm
```

In the Admin UI, open **Models + Endpoints** and confirm `flash-tier` and `pro-tier` are listed. (Missing? See Troubleshooting.)

---

# Part 3 — Pricing: the custom cost map

## Step 8 — Build the custom cost map

**Why:** CommandCode's models are not in LiteLLM's built-in pricing map, AND for a custom provider the reliable lookup key is the deployment's **exact `litellm_params.model`** (`openai/deepseek/deepseek-v4.1-flash`), provider prefix included.

1. **Start from the full upstream map** (`model_prices_and_context_window.json`) and edit *inside* it — do **not** create a small map.
2. **Add one entry per deployment**, keyed by the **exact `litellm_params.model`**:

   ```json
   "openai/deepseek/deepseek-v4.1-flash": {
     "input_cost_per_token": 1.5e-7,
     "output_cost_per_token": 6e-7,
     "max_tokens": 1000000,
     "mode": "chat",
     "litellm_provider": "openai"
   }
   ```

3. **Host the file publicly** (e.g. a `raw.githubusercontent.com` URL).
4. Point LiteLLM at it — add to `.env` **and** the `litellm` environment in Compose:

   ```env
   LITELLM_MODEL_COST_MAP_URL=https://raw.githubusercontent.com/<user>/<repo>/main/custom_cost_map.json
   ```

5. Apply:

   ```powershell
   podman compose -f docker-compose.yml up -d --force-recreate litellm
   ```

Cost-map rules:

| Rule | Detail |
|------|--------|
| **Full copy, not a merge** | LiteLLM replaces the whole map; a small map (under ~50 entries / under half the bundled one) is **silently discarded** |
| **Fetched once at startup** | changes require a **restart** to take effect |
| **Must be reachable** | the URL must be public (HTTP/HTTPS); on failure it silently falls back to the built-in map |

## Step 9 — Verify pricing

Send a prompt in the **Playground**, then open **Usage / Logs** and check the request's **spend**:

- **non-zero** → priced correctly.
- **$0** → the map has no entry for the **exact** `litellm_params.model` (or the map was rejected). See Troubleshooting.

> The price shown on the Models page is display-only. Always confirm with the request's spend.

---

# Part 4 — Routing

## Step 10 — Failover with `order`

`order` lives on each deployment in `litellm_params`. Lower = tried first. On failure at an order, after `num_retries` are exhausted, LiteLLM escalates to the next order. By default it does **not** automatically try another deployment that shares the same order; same-order sibling failover needs cooldown + retry, covered in the next subsection.

```yaml
model_list:
  - model_name: flash-tier
    litellm_params:
      model: openai/deepseek/deepseek-v4.1-flash
      order: 1
  - model_name: flash-tier
    litellm_params:
      model: openai/deepseek/deepseek-v4-flash
      order: 2        # tried after the order-1 attempts fail (not "both")
```

> **Gotcha:** with two deployments in order 1, the default `allowed_fails: 5` keeps a failing key healthy through several retries. `cost-based-routing` then re-picks the *same* deployment and escalates to order 2 — the order-1 sibling is skipped. To make the sibling get tried, set per-deployment `allowed_fails: 0` (next subsection). `enable_weighted_failover` is a separate option but only works with `simple-shuffle`.

### Auto-router tier order fallbacks

A direct call to a tier can advance to the next `order` automatically. Calls through `smart-router` first select a tier, but automatic order fallback may use the requested name (`smart-router`) rather than that selected tier. The following configured fallback pattern was tested successfully on the VPS running LiteLLM 1.103.0; `_target_order` in fallback entries is **undocumented**, so verify it again after LiteLLM upgrades.

The local `config.yaml` has this pattern for all four DB-managed tiers (`order` 2–5):

```yaml
router_settings:
  fallbacks:
    - pro-tier:
        - {model: pro-tier, _target_order: 2}
        - {model: pro-tier, _target_order: 3}
        - {model: pro-tier, _target_order: 4}
        - {model: pro-tier, _target_order: 5}
    - flash-tier:
        - {model: flash-tier, _target_order: 2}
        - {model: flash-tier, _target_order: 3}
        - {model: flash-tier, _target_order: 4}
        - {model: flash-tier, _target_order: 5}
    - ultra-tier:
        - {model: ultra-tier, _target_order: 2}
        - {model: ultra-tier, _target_order: 3}
        - {model: ultra-tier, _target_order: 4}
        - {model: ultra-tier, _target_order: 5}
    - flash-lite-tier:
        - {model: flash-lite-tier, _target_order: 2}
        - {model: flash-lite-tier, _target_order: 3}
        - {model: flash-lite-tier, _target_order: 4}
        - {model: flash-lite-tier, _target_order: 5}
```

Each entry retries the same tier but restricts selection to one order level. Keep the entries aligned with the order values actually present in the DB-managed tier deployments. After editing `config.yaml`, restart LiteLLM as described under **Applying changes**.

To verify after a LiteLLM upgrade, send a short request through `smart-router` and inspect **Usage / Logs**: confirm it succeeds and that the serving model is at a later order when the first deployment fails. In spend-log data, `attempted_fallbacks` should be greater than zero when a configured fallback was used.

> For a documented fallback to a different model group, use the standard `router_settings.fallbacks` form shown in LiteLLM's [Fallbacks documentation](https://docs.litellm.ai/docs/proxy/reliability). The `_target_order` dict form above is a tested, version-sensitive workaround, not an official documented interface.

### Same-order latency pool failover

Use this when several API keys serve the **same model** and you want the fastest healthy key, with a failed key replaced by another key of the same model before moving to a different model.

Every key shares the same `order`. Per-deployment `allowed_fails: 0` benches a failed key on the first counted failure; `num_retries` re-picks a healthy sibling; `cooldown_time` controls how long the failed key stays out.

```yaml
model_list:
  - model_name: flash-tier
    litellm_params:
      model: openai/deepseek/deepseek-v4.1-flash
      api_base: https://api.commandcode.ai/provider/v1
      api_key: os.environ/COMMANDCODE_API_KEY_1
      order: 2
      num_retries: 4
    model_info:
      allowed_fails: 0
      cooldown_time: 300

  - model_name: flash-tier
    litellm_params:
      model: openai/deepseek/deepseek-v4.1-flash
      api_base: https://api.commandcode.ai/provider/v1
      api_key: os.environ/COMMANDCODE_API_KEY_2
      order: 2
      num_retries: 4
    model_info:
      allowed_fails: 0
      cooldown_time: 300

router_settings:
  routing_strategy: latency-based-routing
  routing_strategy_args:
    lowest_latency_buffer: 0      # 0 = strict lowest latency
  num_retries: 4
  retry_policy:
    DefaultRetries: 4             # covers 402
    RateLimitErrorRetries: 4
    InternalServerErrorRetries: 4
    AuthenticationErrorRetries: 4
    BadRequestErrorRetries: 1
    NotFoundErrorRetries: 0
```

| Event | What happens |
|-------|--------------|
| Normal request | Latency routing picks the fastest healthy key at order 2 |
| Key fails with `500`/`429` | Key is benched; the retry picks the next-fastest sibling |
| Key fails with `402` | Benched; with `DefaultRetries` the same request retries a sibling; without it, the next request does |
| Every order-2 key benched | Router escalates to order 3 (the next model) |
| Later request | Benched key is skipped until `cooldown_time` expires |

Sizing:

- `num_retries` is the retry budget for the **current order**, after the initial attempt. Set it to at least `keys - 1` to try every sibling.
- `cooldown_time` must exceed `keys × attempts_per_key × timeout`. With `allowed_fails: 0` and a 500 policy of 1, `attempts_per_key` is 2. A 20s timeout and a 30-minute cooldown cover roughly 45 keys.
- `enable_weighted_failover` is not needed for this path; it only works with `simple-shuffle`.

**Admin UI:** for each key, **Models + Endpoints → Add Model**, use the same public model name, then **Advanced Settings → LiteLLM Params**:

```json
{"order": 2, "num_retries": 4}
```

and **Advanced Settings → Model Info**:

```json
{"allowed_fails": 0, "cooldown_time": 300}
```

Add the model. Repeat for the next key. For an existing deployment: click the model ID → **Edit Settings** → edit the same two JSON fields → **Save Changes**. Apply the `router_settings` change with `restart litellm`.

## Step 11 — Per-model strategies with `routing_groups`

Give each group its own strategy. `group_name` also becomes a **callable model** (it shows up in the UI picker).

```yaml
router_settings:
  routing_strategy: simple-shuffle      # default for ungrouped models
  num_retries: 3
  timeout: 60
  allowed_fails: 5
  cooldown_time: 60
  routing_groups:
    - group_name: flash-cost-optimized
      models: [flash-tier]
      routing_strategy: cost-based-routing
    - group_name: pro-latency-optimized
      models: [pro-tier]
      routing_strategy: latency-based-routing
      routing_strategy_args:
        lowest_latency_buffer: 0.5
```

> The global `allowed_fails: 5` is the default for deployments that do not set their own. The same-order latency pool sets `model_info.allowed_fails: 0` per deployment, which overrides the global value for those keys.

Worked example (`flash-tier`):

1. Order 1 has two deployments → `cost-based-routing` picks the cheaper one.
2. If it fails, retries re-run cost-based → the **same** (cheaper) deployment is
   re-picked while it remains healthy (default `allowed_fails: 5`).
3. After retries are exhausted, escalate to order 2 (`deepseek-v4-flash`).
4. The order-1 sibling takes over on later requests once the failing deployment
   exceeds `allowed_fails`. With per-deployment `allowed_fails: 0`, the key is
   benched on the first failure and the retry picks the sibling in the same
   request.

For a strict "cheapest → next → backup" chain, give each deployment its own
`order` (1/2/3, ranked by cost).

After adding/changing this block: `restart litellm`.

---

# Part 5 — Identity defaults (in `config.yaml`)

## Step 12 — Set key/team defaults and upperbounds

These live under `litellm_settings`. They do **not** create teams/users/keys — they set what future ones inherit.

```yaml
litellm_settings:
  default_key_generate_params:        # fill missing fields on new keys
    models: ["flash-cost-optimized"]
    max_budget: 10
    budget_duration: "30d"
    duration: "90d"

  upperbound_key_generate_params:     # hard ceilings — over-limit is REJECTED
    max_budget: 100
    budget_duration: "30d"

  default_team_params:                # applied to every new team
    max_budget: 200
    budget_duration: "30d"
```

- `default_*` **fills gaps**; `upperbound_*` **rejects** requests above the ceiling (it is not a clamp).
- A key created with blank fields in the UI inherits these automatically.
- Apply with `restart litellm`.

---

# Part 6 — Identity in the Admin UI

## Step 13 — Log in

**http://localhost:4000/ui** → sign in with `LITELLM_MASTER_KEY`.

## Step 14 — Create Teams (Teams)

Create one team per tier and set:

- **Models** — the team's allowed list (pick the names the UI offers, e.g. `flash-cost-optimized`)
- **Max budget** + **budget duration** — the shared pool
- **Rate limits** — rpm / tpm / max_parallel_requests
- **Team-member budget** — default per-person cap

> **OSS note:** you cannot assign a team member as admin — that's Enterprise (*"Assigning admins is an enterprise-only feature."*). The proxy admin administers every team.

## Step 15 — Create Users (Internal Users → + Invite User)

| Field | Notes |
|-------|-------|
| User Email | becomes the `user_id` |
| Global Proxy Role | `Internal User` (can create keys) or `Internal User (View Only)` |
| Team | adds the user to a team with role **`user`** |
| Personal Key Creation → Models | optional |

There is **no budget field on the invite form.** After inviting, open the user's **edit page** to set **Max Budget (USD)** / Reset Budget / Personal Models.

> A user's **personal budget is ignored** for keys that belong to a team — use the **team-member budget** instead.

## Step 16 — Create Virtual Keys (Virtual Keys)

On the Create Key form, set user, team, models, budget, duration. Notes:

- Budget is **capped** by `upperbound_key_generate_params` (here $100) — over it is rejected.
- A **blank models** field inherits `default_key_generate_params.models`.
- The key value is **shown once** — copy it.
- A team key can only reach **`key.models ∩ team.models`**.

| Kind | How |
|------|-----|
| Personal | Create Key with a user, no team |
| Team-member | Create Key with user **and** team |
| **Service account** | **Virtual Keys → Service Account page** → a team key with `user_id: null` that survives user deletion |

## Step 17 — Test and verify spend

- Send a prompt in the **Playground** to confirm a model responds.
- Open **Usage / Logs** and (after app traffic with a key) check that spend lands on the **key**, the **user**, and the **team**.

---

## Applying changes: restart vs. recreate

| Change | Command |
|--------|---------|
| `config.yaml` (models, routing, defaults) | `podman compose -f docker-compose.yml restart litellm` |
| `.env` / `docker-compose.yml` | `podman compose -f docker-compose.yml up -d --force-recreate litellm` |
| `custom_cost_map.json` (remote) | push, then `restart litellm` |

> `restart` reuses the existing container spec, so **new environment variables are not applied**.

---

## Troubleshooting

### Models not showing in the Admin UI
1. Validate `config.yaml` (indentation-sensitive; no duplicate top-level blocks).
2. `podman compose -f docker-compose.yml restart litellm`
3. `podman compose -f docker-compose.yml logs litellm`

### Request cost is $0
1. The deployment's **exact** `litellm_params.model` must have a map entry.
2. The custom map must be a **full copy** of upstream (small maps are silently rejected).
3. Confirm via the request's **spend**, not the listed price.

### A team key can call nothing
`key.models` and `team.models` don't overlap. Use the **same names** on both — a routing-group name and its member name are **not** interchangeable.

### New environment variable has no effect
`restart` doesn't inject new env vars. Use `up -d --force-recreate litellm`.

### `smart-router` does not try later tier orders
Direct tier calls may use automatic `order` failover, while the auto-router path needs the tier-keyed fallback entries in `config.yaml`. The `_target_order` form is undocumented; check it again after LiteLLM upgrades. LiteLLM 1.108's source resolves the order group from the pre-routing selection, which likely fixes this; retest before removing the entries.

### Same-order sibling is not tried
The failed key was not benched. Set per-deployment `allowed_fails: 0` in **Model Info**, keep all keys at the same `order`, and set `num_retries` to at least `keys - 1`. For `402`, add `retry_policy.DefaultRetries`; otherwise the first request fails and only later requests avoid the key. See Step 10, “Same-order latency pool failover.”

### Reasoning effort does nothing on an Anthropic deployment
`supports_reasoning` is missing. Set `model_info.supports_reasoning: true` and the effort levels; otherwise `drop_params` silently removes `reasoning_effort` and no thinking budget reaches the provider.

### Client shows a model as text-only
`model_info.supports_vision` / `modalities.input` is missing. Clients read `/model/info`; add the media flags or the exact `modalities` list in **Model Info**. On LiteLLM 1.108 the gateway forwards images regardless, so the client is the gate.

### Virtual key not working
1. Not blocked / not expired (Virtual Keys page).
2. Key's **models** allow-list includes the model.
3. If the key is in a team, the **team** must allow it too.

---

## Quick command reference

```powershell
# Start / stop
podman compose -f docker-compose.yml up -d
podman compose -f docker-compose.yml down

# Reload config.yaml
podman compose -f docker-compose.yml restart litellm

# Apply .env / compose changes
podman compose -f docker-compose.yml up -d --force-recreate litellm

# Logs
podman compose -f docker-compose.yml logs -f litellm

# Full reset (wipes DB)
podman compose -f docker-compose.yml down && `
  podman volume rm litellm_postgres_data && `
  podman compose -f docker-compose.yml up -d
```

**Admin UI map (http://localhost:4000/ui):**

| Task | Where |
|------|-------|
| Models | Models + Endpoints |
| Add a model / key | Models + Endpoints → Add Model |
| Edit model metadata, `order`, retries | Models + Endpoints → click the model ID → Edit Settings |
| Reusable provider keys | Models + Endpoints → LLM Credentials |
| Teams | Teams |
| Users | Internal Users (+ Invite User) |
| Personal / team keys | Virtual Keys |
| Shared team keys | Virtual Keys → Service Account |
| Spend / logs | Usage / Logs |

---

## Roadmap: what to study next

The full study checklist lives in [ROADMAP.md](./ROADMAP.md) — every topic, done and pending, is tracked there. Immediate next steps:

1. **End-users vs internal users** — the `user` field on requests, `max_end_user_budget_id`. (ROADMAP 6.11)
2. **Rate-limit layering** — tpm/rpm/max_parallel at key/team/user; per-model `model_rpm_limit`/`model_tpm_limit` (OSS). (ROADMAP 6.12)
3. **Access groups** — `model_info.access_groups`. (ROADMAP 6.13)
4. **Key lifecycle** — update / block / unblock / delete / expiry (rotation is Enterprise). (ROADMAP 6.14)
5. **Spend reporting** — Usage / Logs views and per-model breakdown. (ROADMAP 7.3)

Document confirmed findings in [LiteLLM-Learnings.md](./LiteLLM-Learnings.md), then tick the matching items in [ROADMAP.md](./ROADMAP.md).
