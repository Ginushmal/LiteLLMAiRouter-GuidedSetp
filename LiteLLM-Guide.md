# LiteLLM Complete Guide

> Comprehensive reference covering architecture, deployment, configuration, routing, and production use. For beginners and quick reference.

---

## Table of Contents

1. [What is LiteLLM?](#1-what-is-litellm)
2. [Architecture & Components](#2-architecture--components)
3. [Operating Modes](#3-operating-modes)
4. [config.yaml Deep Dive](#4-configyaml-deep-dive)
5. [Docker Deployment](#5-docker-deployment)
6. [Model Configuration](#6-model-configuration)
7. [Pricing & Cost Tracking](#7-pricing--cost-tracking)
8. [Routing & Load Balancing](#8-routing--load-balancing)
9. [Virtual Keys, Teams & Users](#9-virtual-keys-teams--users)
10. [Admin UI](#10-admin-ui)
11. [Production Considerations](#11-production-considerations)
12. [Common Pitfalls & Bugs](#12-common-pitfalls--bugs)
13. [Quick Reference](#13-quick-reference)

---

## 1. What is LiteLLM?

LiteLLM is an **AI Gateway/Proxy** that sits between your applications and AI providers (OpenAI, Anthropic, Azure, Gemini, local models, etc.).

### Why Use It?

| Benefit | Description |
|---------|-------------|
| **Unified API** | One OpenAI-compatible format for all providers |
| **Cost Tracking** | Track spend per key, user, team |
| **API Key Security** | Developers use virtual keys; real provider keys stay hidden |
| **Load Balancing** | Route across multiple deployments/providers |
| **Rate Limiting** | Per-key, per-user, per-team limits |
| **Fallbacks** | Automatic failover when providers fail |

### How It Works

```
                           +---> OpenAI (Real key hidden)
                           |
[Your App] ---> [LiteLLM] -+---> Anthropic (Real key hidden)
 (Virtual        (Proxy)   |
  Key)                     +---> Azure OpenAI (Real key hidden)
                           |
                           +---> Local Model (Ollama, vLLM, etc.)
```

Your apps talk to LiteLLM using the standard OpenAI API format. LiteLLM translates and routes to the correct provider.

---

## 2. Architecture & Components

| Component | Purpose | Required? |
|-----------|---------|-----------|
| **LiteLLM Proxy** | The gateway process (stateless, can run multiple replicas) | Yes |
| **PostgreSQL** | Stores keys, teams, users, spend logs, config | Yes (for auth/tracking) |
| **Redis** | Rate limiting, router state, caching across instances | Only for 2+ instances |
| **config.yaml** | Bootstrap configuration file | Optional (when using DB) |
| **Admin UI** | Web interface at `/ui` for managing models, keys, spend | Requires database |

### Key Environment Variables

| Variable | Purpose |
|----------|---------|
| `LITELLM_MASTER_KEY` | Admin credential for the proxy. Required. |
| `LITELLM_SALT_KEY` | Encrypts provider credentials in DB. **Set once, never change.** |
| `DATABASE_URL` | PostgreSQL connection string |
| `STORE_MODEL_IN_DB` | When `"True"`, enables Admin UI model management + hybrid config |
| `DISABLE_SCHEMA_UPDATE` | Set `"true"` on proxy pods; migrations job handles schema |

---

## 3. Operating Modes

### Mode A: Quickstart (Database + Admin UI, No config.yaml)

- Docker Compose spins up LiteLLM + PostgreSQL
- All configuration done via Admin UI at `http://localhost:4000/ui`
- Models, virtual keys, budgets stored in database
- **No config.yaml needed**
- Full feature set: virtual keys, budgets, spend tracking, Admin UI

**When to use:** Team/company deployments with visual UI and full features.

### Mode B: Stateless (config.yaml Only, No Database)

- Single Docker container with mounted config.yaml
- No database, no Admin UI, no virtual keys, no spend tracking
- All configuration from YAML file
- **Budgets NOT enforced** (requires database)
- **Virtual keys do NOT work** (require database)

**When to use:** Simple personal use, local development, OpenAI-compatible API wrapper.

```bash
docker run \
    -v $(pwd)/config.yaml:/app/config.yaml \
    -e OPENAI_API_KEY=sk-... \
    -e LITELLM_MASTER_KEY=sk-... \
    -p 4000:4000 \
    docker.litellm.ai/berriai/litellm:latest \
    --config /app/config.yaml
```

### Mode C: Hybrid (Database + config.yaml)

- Both database AND config.yaml
- `STORE_MODEL_IN_DB=True` enabled
- config.yaml acts as **bootstrap**; database values override YAML on conflict
- Models from both sources load-balanced together (not merged/overridden)

**When to use:** YAML-based baseline config + Admin UI for dynamic changes.

### config.yaml vs Database Overlay (Hybrid Mode)

When `STORE_MODEL_IN_DB=True`:

| Setting | If changed in config.yaml | If changed in Admin UI |
|---------|--------------------------|------------------------|
| `model_list` | Reloaded on restart/reload | Additive - UI models load-balanced with YAML |
| `router_settings` | Applied on restart | **DB wins** - UI overrides YAML |
| `litellm_settings` | Applied on restart | **DB wins** - UI overrides YAML |
| `general_settings` | Applied on restart | **DB wins** - UI overrides YAML |

**Key rule:** Once you change a setting in Admin UI, editing the same setting in config.yaml and reloading will **not** override it. The DB value wins.

---

## 4. config.yaml Deep Dive

### Structure

```yaml
model_list:              # AI model definitions
litellm_settings:        # Module settings (temperature, caching, etc.)
router_settings:         # Routing/load-balancing settings
general_settings:        # Server settings (master_key, store_model_in_db)
environment_variables:   # Environment variables (REDIS_HOST, etc.)
```

### model_list

Defines which AI models are available:

```yaml
model_list:
  - model_name: gpt-4o              # Name your apps use
    litellm_params:
      model: openai/gpt-4o          # Provider/model format
      api_key: os.environ/OPENAI_API_KEY
  - model_name: gpt-4o-fallback     # Another deployment for load balancing
    litellm_params:
      model: azure/gpt-4o
      api_key: os.environ/AZURE_API_KEY
      api_base: https://my-azure.openai.azure.com/
```

**Key rules:**
- `model_name` = what your apps request (e.g., `model: "gpt-4o"` in API calls)
- Multiple entries with same `model_name` are load-balanced automatically
- Use `os.environ/<VAR_NAME>` to reference environment variables

### litellm_settings

```yaml
litellm_settings:
  drop_params: true          # Auto-drop unsupported params instead of erroring
  set_verbose: false         # Debug logging
  cache: true                # Enable response caching
  cache_params:
    type: redis
    host: "localhost"
    port: 6379
  max_budget: 100            # Global budget (ONLY works with database)
  budget_duration: "1mo"     # Budget reset period
```

### router_settings

```yaml
router_settings:
  routing_strategy: simple-shuffle    # or "least-busy", "latency-based-routing", etc.
  num_retries: 3                      # Auto-retry on failure
  timeout: 30                         # Request timeout in seconds
  allowed_fails: 5                    # Cooldown after this many failures
  cooldown_time: 60                   # Seconds to cooldown a failing deployment
```

### general_settings

```yaml
general_settings:
  master_key: sk-my-special-key     # Alternative to LITELLM_MASTER_KEY env var
  store_model_in_db: true           # Enable hybrid mode
  database_url: postgresql://...    # Alternative to DATABASE_URL env var
```

### environment_variables

```yaml
environment_variables:
  REDIS_HOST: localhost
  REDIS_PORT: 6379
  REDIS_PASSWORD: ""
```

---

## 5. Docker Deployment

### Docker Volumes with config.yaml

The `-v` flag (or `volumes:` in compose) bridges your host file to the container:

```
Your Host Machine                    Docker Container
+---------------------+              +---------------------+
| /path/to/config.yaml| ===========> | /app/config.yaml    |
+---------------------+              +---------------------+
```

### CLI Arguments with Docker

Arguments after the image name are passed to the entrypoint:

```bash
docker run <image> --config /app/config.yaml
# Behind the scenes runs: litellm --config /app/config.yaml
```

### Docker Compose Example (Hybrid Mode)

```yaml
services:
  litellm:
    image: ghcr.io/berriai/litellm:main-stable
    ports:
      - "4000:4000"
    volumes:
      - ./config.yaml:/app/config.yaml
    environment:
      - DATABASE_URL=postgresql://litellm:litellm@db:5432/litellm
      - STORE_MODEL_IN_DB=True
      - LITELLM_MASTER_KEY=${LITELLM_MASTER_KEY}
      - LITELLM_SALT_KEY=${LITELLM_SALT_KEY}
    depends_on:
      db:
        condition: service_healthy
    command: ["--config", "/app/config.yaml"]

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

### Health Check Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/health/liveliness` | Is the process alive? (liveness probe) |
| `/health/readiness` | Can it reach the database? (readiness probe) |

### Config Reload

**There is no `/config/reload` endpoint.** To reload config.yaml, restart the container:

```bash
podman compose -f docker-compose.quickstart.yml restart litellm
```

---

## 6. Model Configuration

### Provider Format

| Provider | Format |
|----------|--------|
| OpenAI | `openai/<model>` |
| Azure OpenAI | `azure/<model>` |
| Anthropic | `anthropic/<model>` |
| Gemini | `gemini/<model>` |
| Bedrock | `bedrock/<model>` |
| Ollama | `ollama/<model>` |
| vLLM | `openai/<model>` with `api_base` set |
| Custom OpenAI-compatible | `openai/<provider-model>` with `api_base` set |

### OpenAI-Compatible Custom Providers

For custom OpenAI-compatible endpoints (like CommandCode, vLLM, etc.):

```yaml
model_list:
  - model_name: my-custom-model
    litellm_params:
      model: openai/deepseek/deepseek-v4.1-flash  # openai/ prefix + provider model name
      api_base: https://api.commandcode.ai/provider/v1
      api_key: os.environ/CUSTOM_API_KEY
```

- `openai/` prefix tells LiteLLM to use OpenAI-compatible protocol
- Everything after `openai/` is sent as the model name to the provider
- `api_base` overrides the default OpenAI endpoint

### model_name is Just an Alias

`model_name` is the name your apps request. It is **NOT** access control or tiering.

```yaml
model_list:
  - model_name: pro-tier    # Apps request this
    litellm_params:
      model: openai/deepseek/deepseek-v4-pro
  - model_name: pro-tier    # Same name = load-balanced together
    litellm_params:
      model: openai/qwen/qwen3.7-plus
```

When an app requests `model: "pro-tier"`, LiteLLM load-balances between DeepSeek V4 Pro and Qwen 3.7 Plus.

---

## 7. Pricing & Cost Tracking

### LiteLLM's Built-in Cost Map

LiteLLM prices every request from a **cost map** — a JSON file mapping each model to per-token rates:
- **File:** `model_prices_and_context_window.json`
- **Source:** https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json

The proxy fetches it once at startup. `GET /model/cost_map/source` reports which map actually loaded.

### Display vs Accounting Cost (Important)

There are **two separate cost paths** that can disagree:

| Path | What it uses | Where you see it |
|------|--------------|------------------|
| **Display** | `model_info` / `base_model` resolution | Admin UI "Models + Endpoints" page |
| **Accounting** | cost-map lookup (candidate chain below) | Spend logs, budgets |

**A price visible in the UI does not guarantee request cost is calculated.** Always confirm with a spend log.

### Using base_model for Automatic Pricing

`base_model` tells LiteLLM which cost-map entry to use when the deployment name or the provider's response name differs:

```yaml
model_list:
  - model_name: my-deployment
    litellm_params:
      model: openai/deepseek/deepseek-v4.1-flash
    model_info:
      base_model: openrouter/deepseek/deepseek-v4.1-flash  # Maps to cost map entry
```

### How Cost Calculation Actually Works

The cost lookup is a **candidate chain** — LiteLLM tries names in order and uses the **first that resolves to a non-empty cost-map entry**:

```
1. selected_model   (derived from base_model / custom pricing)
2. response model   (the model name the provider returns)
3. model            (the deployment's litellm_params.model)
```

Two consequences that are easy to miss:

- **Empty entries are skipped.** An entry that exists but has no pricing (`{}`) is silently passed over.
- **Every candidate is looked up through the deployment's provider prefix.** `base_model`'s own provider prefix is *not* honored (LiteLLM bug #22257). So a `base_model` with a different provider than the deployment (deployment `openai/...`, base_model `openrouter/...`) gets re-prefixed to `openai/...` and can miss.

**Practical rule:** the most reliable way to price a custom deployment is to add a cost-map entry keyed by **exactly `litellm_params.model`**. Then candidate 3 always resolves and `base_model` becomes unnecessary.

### Custom Pricing (per model, in config)

If the model is NOT in the cost map, set explicit per-token prices:

```yaml
model_list:
  - model_name: my-model
    litellm_params:
      model: openai/custom-model
    model_info:
      input_cost_per_token: 0.00000015          # $0.15 per million input tokens
      output_cost_per_token: 0.0000006          # $0.60 per million output tokens
      cache_read_input_token_cost: 0.000000003  # $0.003 per million cache read tokens
```

**Calculation:** `$X per million tokens` = `X / 1,000,000` per token

### Custom Cost Map Source (self-hosted)

Host your own **full copy** of the map and point LiteLLM at it:

```bash
# Environment variable
LITELLM_MODEL_COST_MAP_URL="https://your-host.example.com/custom_cost_map.json"
```

| Rule | Detail |
|------|--------|
| **Full replacement, not a merge** | Start from the complete upstream file and edit inside it |
| **Validation (silent)** | Needs ≥ **50** entries *and* ≥ **half** the bundled backup, or it is **discarded** |
| **Tunable thresholds** | `MODEL_COST_MAP_MIN_MODEL_COUNT`, `MODEL_COST_MAP_MAX_SHRINK_RATIO` |
| **Fetch** | Once at startup, 5s timeout; changes require a restart |
| **On failure** | Falls back to the bundled backup **silently** (no crash) |
| **URL** | HTTP(S) only; `file://` not supported |
| **Offline alternative** | `LITELLM_LOCAL_MODEL_COST_MAP=True` uses the bundled backup |

**Keys must match `litellm_params.model` exactly**, provider prefix included.

> ⚠️ A small map containing only your models is **silently rejected** — LiteLLM keeps the default map. This is the most common reason a custom map "doesn't work."

**Docs:** https://docs.litellm.ai/docs/proxy/custom_model_cost_map · https://docs.litellm.ai/docs/proxy/custom_pricing


---

## 8. Routing & Load Balancing

### Routing Strategies

| Strategy | Picks | Best for |
|----------|-------|----------|
| `simple-shuffle` (default) | Weighted by `rpm`/`tpm`, else random | Production (recommended) |
| `least-busy` | Fewest active requests | High concurrency |
| `latency-based-routing` | Fastest responding | Latency-critical |
| `cost-based-routing` | Cheapest deployment | Cost-sensitive |
| `usage-based-routing` | Lowest TPM usage | Even rate-limit spread (needs Redis, slow) |

### How They Compose (Layered)

```
Request for "flash-tier"
        │
   1. Resolve model group      → all deployments with model_name: flash-tier
        │
   2. Split by `order`         → priority tiers (failover). Lower = tried first
        │
   3. Routing strategy         → pick ONE within the current tier
        │                        (simple-shuffle / cost-based / latency-based)
        │
   4. num_retries + cooldown   → failed deployment excluded, re-pick
        │
   5. Fallbacks                → if ALL tiers fail, switch to a DIFFERENT group
```

### routing_groups (Per-Model Strategies)

Override the global strategy for specific model groups:

```yaml
router_settings:
  routing_strategy: simple-shuffle  # Global default
  routing_groups:
    - group_name: flash-cost-optimized
      models: [flash-tier]
      routing_strategy: cost-based-routing
    - group_name: pro-latency-optimized
      models: [pro-tier]
      routing_strategy: latency-based-routing
      routing_strategy_args:
        lowest_latency_buffer: 0.5  # Consider any deployment within 50% of fastest
```

### Deployment Ordering (Failover via `order`)

`order` is a **deployment property** in `model_list[*].litellm_params`:

```yaml
model_list:
  - model_name: flash-tier
    litellm_params:
      model: openai/deepseek/deepseek-v4.1-flash
      order: 1        # Always tried first
  - model_name: flash-tier
    litellm_params:
      model: openai/deepseek/deepseek-v4-flash
      order: 2        # Only used when order:1 fails
```

**How it works:**
- Lower value = higher priority
- Deployments sharing the same `order` are picked by the routing strategy
- On failure at order N, escalates to order N+1

### Example: cost-based-routing + order

```yaml
model_list:
  - model_name: flash-tier
    litellm_params:
      model: openai/deepseek/deepseek-v4.1-flash
      order: 1
  - model_name: flash-tier
    litellm_params:
      model: openrouter/qwen/qwen3.8-omni-flash
      order: 1
  - model_name: flash-tier
    litellm_params:
      model: openai/deepseek/deepseek-v4-flash
      order: 2

router_settings:
  routing_groups:
    - group_name: flash-cost-optimized
      models: [flash-tier]
      routing_strategy: cost-based-routing
```

**Scenario 1: All endpoints working**
- Order 1: {V4.1, Qwen} → cost-based picks cheapest (say V4.1 at $0.15/M)
- **V4.1 Flash responds**

**Scenario 2: V4.1 is down**
- Order 1: {V4.1, Qwen} → cost-based picks V4.1 (cheaper)
- V4.1 fails → retries 3 times → all fail → V4.1 cooled down
- Re-pick from Order 1: {Qwen} → **Qwen Flash responds**

**Scenario 3: Both V4.1 and Qwen are down**
- Order 1: {V4.1, Qwen} → both fail and cool down
- Escalate to Order 2: {V4} → **V4 Flash responds**

### Fallbacks (Different Model Groups)

Switch to a different model group on total failure:

```yaml
model_fallbacks:
  - pro-tier: ["flash-tier"]  # If pro-tier fails completely, try flash-tier
```

---

## 9. Virtual Keys, Teams & Users

### Virtual Keys

Virtual keys are what you give to applications and teammates instead of raw provider API keys. Each key can have:
- Its own **budget** (spend limit)
- Its own **rate limits** (requests per minute/day)
- Its own **model access** (which models it can use)
- Automatic **spend tracking**

### Creating Virtual Keys

**Via Admin UI:** Go to "Virtual Keys" > "+ Create New Key" > set name, budget, models > Create

**Via API:**

```bash
curl -X POST http://localhost:4000/key/generate \
  -H "Authorization: Bearer sk-your-master-key" \
  -H "Content-Type: application/json" \
  -d '{
    "duration": "30d",
    "models": ["gpt-4o", "claude-3-sonnet"],
    "max_budget": 50,
    "budget_duration": "1mo"
  }'
```

### Teams

Create teams to group users and set shared budgets:

```bash
curl -X POST http://localhost:4000/team/new \
  -H "Authorization: Bearer $MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"team_id": "BA", "team_alias": "BA Team"}'
```

### Users

Create internal users:

```bash
curl -X POST http://localhost:4000/user/new \
  -H "Authorization: Bearer $MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "boo",
    "user_email": "booboo192939@gmail.com",
    "models": ["flash-tier", "pro-tier"]
  }'
```

### Assigning Keys to Teams/Users

```bash
curl -X POST http://localhost:4000/key/generate \
  -H "Authorization: Bearer $MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "boo",
    "team_id": "BA",
    "duration": "30d",
    "models": ["flash-tier", "pro-tier"]
  }'
```

### Spend Tracking

Spend is tracked at three levels:
- **Key spend:** Stored in `LiteLLM_VerificationTokenTable`
- **User spend:** Stored in `LiteLLM_UserTable` (when key has `user_id`)
- **Team spend:** Stored in `LiteLLM_TeamTable` (when key has `team_id`)

**Checking spend:**

```bash
# Key spend
curl "http://localhost:4000/key/info?key=<virtual-key>" \
  -H "Authorization: Bearer <master-key>"

# User spend
curl "http://localhost:4000/user/info?user_id=boo" \
  -H "Authorization: Bearer <master-key>"

# Team spend
curl "http://localhost:4000/team/info?team_id=BA" \
  -H "Authorization: Bearer <master-key>"
```

---

## 10. Admin UI

### Access

Navigate to `http://localhost:4000/ui` and log in with your `LITELLM_MASTER_KEY`.

### Features

- **Model Management:** Add/remove/edit models (when `STORE_MODEL_IN_DB=True`)
- **Virtual Keys:** Create, edit, delete keys with budgets and rate limits
- **Spend Tracking:** View spend per key, user, team
- **Playground:** Test models directly from the UI
- **User Management:** Create users, assign teams

### First-Time Setup

1. Go to `/ui`
2. Log in with master key
3. Create your own admin account
4. Disable environment credential login (optional security step)

### Disable Admin UI

```yaml
# In environment
DISABLE_ADMIN_UI="True"
```

---

## 11. Production Considerations

### Architecture Options

| Mode | Components | When to Use |
|------|-----------|-------------|
| **Monolithic** | Single LiteLLM deployment | Simple setups, <1000 RPS |
| **Microservices** | Gateway + Backend + UI separated | High scale, separate scaling |

### Production Checklist

1. **Pin image version:** Use `ghcr.io/berriai/litellm:v1.90.2` not `:latest`
2. **Run 2+ replicas** behind a load balancer
3. **Set `DISABLE_SCHEMA_UPDATE=true`** on proxy pods; run migrations separately
4. **Use Redis** for multi-instance rate limiting and caching
5. **Use a managed PostgreSQL** (RDS, Cloud SQL, etc.) with IAM auth
6. **Store secrets** in cloud secret manager, not env vars
7. **Configure health probes:** liveness on `/health/liveliness`, readiness on `/health/readiness`
8. **For >1000 RPS:** Enable Redis transaction buffer, evaluate high-throughput profile

### Redis Requirements

| Situation | Redis needed? |
|-----------|---------------|
| Single instance + `simple-shuffle` | ❌ No |
| **More than 1 proxy instance** | ✅ Yes — shares rate-limit counters, router state, cache |
| `usage-based-routing` strategy | ✅ Yes — tracks TPM/RPM (even single instance) |
| Response caching across instances | ✅ Yes |
| 1000+ RPS (spend transaction buffer) | ✅ Yes |

**Redis options:**
- `redis:7-alpine` — official image, works fine
- `valkey/valkey:7` — BSD-licensed fork (Linux Foundation), drop-in replacement

### Kubernetes Deployment (Key Parts)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: litellm-deployment
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: litellm
        image: ghcr.io/berriai/litellm:v1.90.2
        args: ["--config", "/app/config.yaml"]
        ports:
        - containerPort: 4000
        envFrom:
        - secretRef:
            name: litellm-secrets
        livenessProbe:
          httpGet:
            path: /health/liveliness
            port: 4000
        readinessProbe:
          httpGet:
            path: /health/readiness
            port: 4000
```

---

## 12. Common Pitfalls & Bugs

### 1. Regenerating LITELLM_SALT_KEY

**Problem:** Makes all stored provider credentials unreadable.  
**Solution:** Set once, never change.

### 2. Expecting budgets to work without a database

**Problem:** They silently do nothing. You only get a one-time startup warning.  
**Solution:** Use database (Mode A or C).

### 3. Editing YAML expecting changes after UI modification

**Problem:** Database overrides YAML.  
**Solution:** Change settings in the UI, or delete the DB row.

### 4. Using `:latest` tag in production

**Problem:** Non-deterministic rollbacks.  
**Solution:** Pin a specific version tag.

### 5. Not setting DISABLE_SCHEMA_UPDATE on proxy pods

**Problem:** Can cause migration conflicts.  
**Solution:** Let the migrations job handle schema.

### 6. Thinking model_list merges/overrides

**Problem:** It doesn't. Same-named models from YAML and DB are load-balanced as separate deployments.  
**Solution:** Understand that models are additive, not merged.

### 7. Using docker.litellm.ai for monolithic deployments

**Problem:** Missing Prisma toolchain.  
**Solution:** Use `ghcr.io/berriai/litellm` which bundles Prisma.

### 8. Stale browser localStorage after DB reset

**Problem:** Auth errors flooding console after resetting database.  
**Solution:** Clear browser storage for localhost:4000 or use incognito mode.

### 9. Duplicate router_settings blocks in YAML

**Problem:** Last key wins, first block silently ignored.  
**Solution:** Merge into one block or delete the duplicate.

### 10. Uncommented order example inside router_settings

**Problem:** YAML absorbs it into routing_groups as malformed entries.  
**Solution:** `order` belongs in `model_list[*].litellm_params`, not `router_settings`.

### 11. Inconsistent provider prefixes

**Problem:** Mixing `openrouter/` and `openai/` prefixes for same provider.  
**Solution:** Use consistent prefix matching your provider type.

### 12. Request cost is $0 even though the UI shows a price

**Problem:** Display and accounting use separate paths. A `base_model` whose provider differs from the deployment is re-prefixed during lookup and misses (bug #22257); empty cost-map entries are skipped silently.  
**Solution:** Add a cost-map entry keyed by the exact `litellm_params.model`. Confirm with a spend log, not the UI.

### 13. Custom cost map silently ignored

**Problem:** A custom map with fewer than 50 entries (or less than half the bundled backup) is discarded without an error, so LiteLLM keeps the default map.  
**Solution:** Fork the entire upstream map and edit inside it. Verify with `GET /model/cost_map/source` (`url` should be yours, `fallback_reason` null).

### 14. New environment variables not applied

**Problem:** `podman compose restart` reuses the old container spec, so new `.env` / compose env vars are not injected.  
**Solution:** Use `podman compose up -d --force-recreate <service>` to recreate the container.

---

## 13. Quick Reference

### Docker Commands

```bash
# Start
podman compose -f docker-compose.quickstart.yml up -d

# Stop
podman compose -f docker-compose.quickstart.yml down

# Restart proxy only (does NOT apply env-var / compose changes)
podman compose -f docker-compose.quickstart.yml restart litellm

# Apply env-var / compose changes (recreates the container)
podman compose -f docker-compose.quickstart.yml up -d --force-recreate litellm

# View logs
podman compose -f docker-compose.quickstart.yml logs -f litellm

# Health check
curl http://localhost:4000/health/readiness
```

### API Commands

```bash
# List models
curl http://localhost:4000/model/info -H "Authorization: Bearer $MASTER_KEY"

# List keys
curl http://localhost:4000/key/list -H "Authorization: Bearer $MASTER_KEY"

# List teams
curl http://localhost:4000/team/list -H "Authorization: Bearer $MASTER_KEY"

# List users
curl http://localhost:4000/user/list -H "Authorization: Bearer $MASTER_KEY"

# Create virtual key
curl -X POST http://localhost:4000/key/generate \
  -H "Authorization: Bearer $MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "boo", "team_id": "BA", "duration": "30d"}'

# Check spend
curl "http://localhost:4000/key/info?key=<virtual-key>" \
  -H "Authorization: Bearer $MASTER_KEY"

# Reset everything
podman compose -f docker-compose.quickstart.yml down && \
podman volume rm litellm_postgres_data && \
podman compose -f docker-compose.quickstart.yml up -d
```

### Cost Map Diagnostics

```bash
# Which cost map is loaded? (source, url, fallback_reason, model_count)
curl -s http://localhost:4000/model/cost_map/source -H "Authorization: Bearer $MASTER_KEY"

# Inspect the effective map for a model's pricing
curl -s http://localhost:4000/public/litellm_model_cost_map | \
  python -c "import sys,json; print(json.load(sys.stdin).get('openai/deepseek/deepseek-v4.1-flash'))"

# Check a request's actual cost (metadata.cost_breakdown, custom_llm_provider)
curl -s http://localhost:4000/spend/logs -H "Authorization: Bearer $MASTER_KEY"
```

### Documentation References

| Topic | URL |
|-------|-----|
| Docker Quick Start | https://docs.litellm.ai/docs/proxy/docker_quick_start |
| config.yaml Reference | https://docs.litellm.ai/docs/proxy/configs |
| Config Settings Deep Dive | https://docs.litellm.ai/docs/proxy/config_settings |
| Virtual Keys | https://docs.litellm.ai/docs/proxy/virtual_keys |
| Teams | https://docs.litellm.ai/docs/proxy/team_based_routing |
| Users & Budgets | https://docs.litellm.ai/docs/proxy/users |
| Load Balancing | https://docs.litellm.ai/docs/proxy/load_balancing |
| Routing Strategies | https://docs.litellm.ai/docs/routing |
| Fallbacks | https://docs.litellm.ai/docs/routing/fallbacks |
| Custom Pricing | https://docs.litellm.ai/docs/proxy/custom_pricing |
| Custom Cost Map | https://docs.litellm.ai/docs/proxy/custom_model_cost_map |
| Caching | https://docs.litellm.ai/docs/caching/gpt_cache |
| Guardrails | https://docs.litellm.ai/docs/proxy/guardrails |
| Observability | https://docs.litellm.ai/docs/observability/callbacks |
| Production Deployment | https://docs.litellm.ai/docs/proxy/deploy |
| Admin UI | https://docs.litellm.ai/docs/proxy/ui |
| Model Management | https://docs.litellm.ai/docs/proxy/model_management |

---

## Summary

**LiteLLM is an AI Gateway** that provides a unified API, cost tracking, key security, and load balancing across multiple AI providers.

**Three operating modes:**
- Mode A: Quickstart (DB + UI, no config)
- Mode B: Stateless (config only, no DB/UI)
- Mode C: Hybrid (DB + config)

**Key concepts:**
- `model_name` is an alias/group name for load balancing
- `order` provides failover priority (deployment property)
- `routing_groups` override strategy per model group
- Cost lookup is a candidate chain (base_model → response model → `litellm_params.model`); the reliable fix is to price the exact `litellm_params.model` key
- Display cost (UI) and accounted cost (spend logs) are separate paths — verify with a spend log
- Custom cost maps must be a **full copy** of the upstream map (small maps are silently rejected)
- Database required for budgets, virtual keys, spend tracking

**Production essentials:**
- Pin image versions
- Use Redis for 2+ instances
- Store secrets in secret manager
- Configure health probes
- Never regenerate LITELLM_SALT_KEY

---

*Guide created from hands-on exploration and official documentation verification. Last updated: 2026-09-25*
