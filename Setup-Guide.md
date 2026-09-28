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
| `docker-compose.quickstart.yml` | the two services (litellm + db) |
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

## Step 2 — Create `docker-compose.quickstart.yml`

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
      # COMMANDCODE_API_KEY: ...              # added in Step 6
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
podman compose -f docker-compose.quickstart.yml up -d
```

Wait ~30s for Postgres, then confirm:

```powershell
podman compose -f docker-compose.quickstart.yml logs litellm
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

---

## Step 6 — Wire the provider key into Compose

`api_key: os.environ/COMMANDCODE_API_KEY` in `config.yaml` needs that variable inside the container. Add it to the `litellm` service environment, and to `.env`:

```yaml
    environment:
      # ...
      COMMANDCODE_API_KEY: ${COMMANDCODE_API_KEY:?set it in .env}
```

```env
COMMANDCODE_API_KEY=sk-<your-commandcode-key>
```

> Editing Compose/.env is a **container-spec change**, so apply it with `--force-recreate` (Step 7), not `restart`.

---

## Step 7 — Apply and confirm

```powershell
podman compose -f docker-compose.quickstart.yml up -d --force-recreate litellm
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
   podman compose -f docker-compose.quickstart.yml up -d --force-recreate litellm
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

`order` lives on each deployment in `litellm_params`. Lower = tried first; on failure, LiteLLM escalates to the next order.

```yaml
model_list:
  - model_name: flash-tier
    litellm_params:
      model: openai/deepseek/deepseek-v4.1-flash
      order: 1
  - model_name: flash-tier
    litellm_params:
      model: openai/deepseek/deepseek-v4-flash
      order: 2        # used only when order 1 is unavailable
```

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

Worked example (`flash-tier`):

1. Order 1 has two deployments → `cost-based-routing` picks the cheaper one.
2. If it fails (retries + cooldown), the other order-1 deployment is used.
3. If both fail, escalate to order 2 (`deepseek-v4-flash`).

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
| `config.yaml` (models, routing, defaults) | `podman compose -f docker-compose.quickstart.yml restart litellm` |
| `.env` / `docker-compose.quickstart.yml` | `podman compose -f docker-compose.quickstart.yml up -d --force-recreate litellm` |
| `custom_cost_map.json` (remote) | push, then `restart litellm` |

> `restart` reuses the existing container spec, so **new environment variables are not applied**.

---

## Troubleshooting

### Models not showing in the Admin UI
1. Validate `config.yaml` (indentation-sensitive; no duplicate top-level blocks).
2. `podman compose -f docker-compose.quickstart.yml restart litellm`
3. `podman compose -f docker-compose.quickstart.yml logs litellm`

### Request cost is $0
1. The deployment's **exact** `litellm_params.model` must have a map entry.
2. The custom map must be a **full copy** of upstream (small maps are silently rejected).
3. Confirm via the request's **spend**, not the listed price.

### A team key can call nothing
`key.models` and `team.models` don't overlap. Use the **same names** on both — a routing-group name and its member name are **not** interchangeable.

### New environment variable has no effect
`restart` doesn't inject new env vars. Use `up -d --force-recreate litellm`.

### Virtual key not working
1. Not blocked / not expired (Virtual Keys page).
2. Key's **models** allow-list includes the model.
3. If the key is in a team, the **team** must allow it too.

---

## Quick command reference

```powershell
# Start / stop
podman compose -f docker-compose.quickstart.yml up -d
podman compose -f docker-compose.quickstart.yml down

# Reload config.yaml
podman compose -f docker-compose.quickstart.yml restart litellm

# Apply .env / compose changes
podman compose -f docker-compose.quickstart.yml up -d --force-recreate litellm

# Logs
podman compose -f docker-compose.quickstart.yml logs -f litellm

# Full reset (wipes DB)
podman compose -f docker-compose.quickstart.yml down && `
  podman volume rm litellm_postgres_data && `
  podman compose -f docker-compose.quickstart.yml up -d
```

**Admin UI map (http://localhost:4000/ui):**

| Task | Where |
|------|-------|
| Models | Models + Endpoints |
| Teams | Teams |
| Users | Internal Users (+ Invite User) |
| Personal / team keys | Virtual Keys |
| Shared team keys | Virtual Keys → Service Account |
| Spend / logs | Usage / Logs |

---

## Roadmap: what to study next

1. **End-users vs internal users** — the `user` field on requests, `max_end_user_budget_id`.
2. **Rate-limit layering** — tpm/rpm/max_parallel at key/team/user; per-model `model_rpm_limit`/`model_tpm_limit` (OSS).
3. **Access groups** — `model_info.access_groups`.
4. **Key lifecycle** — update / block / unblock / delete / expiry (rotation is Enterprise).
5. **Spend reporting** — Usage / Logs views and per-model breakdown.

Document confirmed findings in [LiteLLM-Learnings.md](./LiteLLM-Learnings.md).
