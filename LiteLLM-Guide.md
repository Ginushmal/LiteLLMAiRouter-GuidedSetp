# LiteLLM: Beginner to Expert Guide

> Based on the official documentation at https://docs.litellm.ai/docs/ and verified against your local `docker-compose.quickstart.yml` setup.

---

## Table of Contents

1. [What Is LiteLLM?](#1-what-is-litellm)
2. [Core Architecture](#2-core-architecture)
3. [The Three Operating Modes](#3-the-three-operating-modes)
4. [Understanding config.yaml](#4-understanding-configyaml)
5. [Docker Deployment Deep Dive](#5-docker-deployment-deep-dive)
6. [Your Current Setup Explained](#6-your-current-setup-explained)
7. [Virtual Keys & Spend Tracking](#7-virtual-keys--spend-tracking)
8. [The Hybrid Mode: config.yaml + Database](#8-the-hybrid-mode-configyaml--database)
9. [Admin UI](#9-admin-ui)
10. [Production Deployment](#10-production-deployment)
11. [config.yaml Reference](#11-configyaml-reference)
12. [Common Pitfalls & Corrections](#12-common-pitfalls--corrections)

---

## 1. What Is LiteLLM?

LiteLLM is an **AI Gateway / Proxy**. It sits between your applications and AI providers (OpenAI, Anthropic, Azure, Gemini, local models, etc.), providing:

- **Unified API**: One OpenAI-compatible API format for all providers
- **Cost tracking & budgets**: Track spend per key, user, team
- **API key security**: Developers use "Virtual Keys"; real provider keys stay hidden
- **Load balancing & fallback**: Route across multiple deployments/providers
- **Rate limiting**: Per-key, per-user, per-team rate limits

```
                           +---> OpenAI (Real key hidden)
                           |
[Your App] ---> [LiteLLM] -+---> Anthropic (Real key hidden)
 (Virtual        (Proxy)   |
  Key)                     +---> Azure OpenAI (Real key hidden)
                           |
                           +---> Local Model (Ollama, vLLM, etc.)
```

---

## 2. Core Architecture

### Components

| Component | Purpose |
|-----------|---------|
| **LiteLLM Proxy** | The gateway process (stateless, can run multiple replicas) |
| **PostgreSQL** | Stores keys, teams, users, spend logs, config (required for auth/tracking) |
| **Redis** | Rate limiting, router state, caching across instances (required for multi-instance) |
| **config.yaml** | Bootstrap configuration file (optional when using database) |
| **Admin UI** | Web interface at `/ui` for managing models, keys, spend (requires database) |

### Key Environment Variables

| Variable | Purpose |
|----------|---------|
| `LITELLM_MASTER_KEY` | The admin credential for the proxy. Required. Used for every request. |
| `LITELLM_SALT_KEY` | Encrypts provider credentials stored in the DB. **Set once, never change it.** |
| `DATABASE_URL` | PostgreSQL connection string |
| `STORE_MODEL_IN_DB` | When `"True"`, enables Admin UI model management + hybrid config |
| `DISABLE_SCHEMA_UPDATE` | Set `"true"` on proxy pods; migrations job handles schema |

---

## 3. The Three Operating Modes

### Mode A: Quickstart (Database + Admin UI, No config.yaml)

This is what your current `docker-compose.quickstart.yml` uses.

- Docker Compose spins up LiteLLM + PostgreSQL
- All configuration done via Admin UI at `http://localhost:4000/ui`
- Models, virtual keys, budgets all stored in the database
- **No config.yaml file needed**
- Full feature set: virtual keys, budgets, spend tracking, Admin UI

**When to use**: Team/company deployments where you want the visual UI and full feature set.

### Mode B: Stateless (config.yaml Only, No Database)

- Single Docker container with a mounted config.yaml
- No database, no Admin UI, no virtual keys, no spend tracking
- All configuration comes from the YAML file
- **Budgets are NOT enforced** (the docs explicitly state `max_budget` does nothing without a DB)
- **Virtual keys do NOT work** (requests with virtual keys fail)

**When to use**: Simple personal use, local development, or when you just need an OpenAI-compatible API wrapper.

```bash
docker run \
    -v $(pwd)/litellm_config.yaml:/app/config.yaml \
    -e OPENAI_API_KEY=sk-... \
    -e LITELLM_MASTER_KEY=sk-... \
    -p 4000:4000 \
    docker.litellm.ai/berriai/litellm:latest \
    --config /app/config.yaml
```

### Mode C: Hybrid (Database + config.yaml)

- Both a database AND a config.yaml file
- `STORE_MODEL_IN_DB=True` enabled
- config.yaml acts as **bootstrap**; database values override YAML on conflict
- Models from both sources are load-balanced together (not merged/overridden)

**When to use**: When you want YAML-based baseline config but also want the Admin UI for dynamic changes.

---

## 4. Understanding config.yaml

The config.yaml has **five top-level sections**:

```yaml
model_list:          # AI model definitions
litellm_settings:    # LiteLLM module settings (temperature, caching, etc.)
router_settings:     # Routing/load-balancing settings
general_settings:    # Server settings (master_key, store_model_in_db, etc.)
environment_variables:  # Environment variables (REDIS_HOST, etc.)
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

**Key rules**:
- `model_name` is what your apps request (e.g., `model: "gpt-4o"` in API calls)
- Multiple entries with the same `model_name` are load-balanced automatically
- Use `os.environ/<VAR_NAME>` to reference environment variables instead of hardcoding secrets

### litellm_settings

Module-level settings:

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

Controls how requests are routed across model deployments:

```yaml
router_settings:
  routing_strategy: least-busy    # or "simple-shuffle", "latency-based", etc.
  num_retries: 3                  # Auto-retry on failure
  timeout: 30                     # Request timeout in seconds
  allowed_fails: 5                # Cooldown after this many failures
  cooldown_time: 60               # Seconds to cooldown a failing deployment
```

### general_settings

Server-level settings:

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

## 5. Docker Deployment Deep Dive

### How Docker Volumes Work with config.yaml

The `-v` flag (or `volumes:` in compose) creates a bridge between your host file and the container:

```
Your Host Machine                    Docker Container
+---------------------+              +---------------------+
| /path/to/config.yaml| ===========> | /app/config.yaml    |
+---------------------+              +---------------------+
```

### How CLI Arguments Work with Docker

Arguments after the image name are passed to the entrypoint:

```bash
docker run <image> --config /app/config.yaml
# Behind the scenes runs: litellm --config /app/config.yaml
```

### Docker Compose with config.yaml (Hybrid Mode)

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

---

## 6. Your Current Setup Explained

Your `docker-compose.quickstart.yml` is **Mode A (Quickstart)**:

```yaml
services:
  litellm:
    image: docker.litellm.ai/berriai/litellm:main-stable
    ports:
      - "4000:4000"
    environment:
      LITELLM_MASTER_KEY: ${LITELLM_MASTER_KEY}   # From .env
      LITELLM_SALT_KEY: ${LITELLM_SALT_KEY}       # From .env
      DATABASE_URL: postgresql://litellm:litellm@db:5432/litellm
      STORE_MODEL_IN_DB: "True"
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:16
    # ... postgres config with healthcheck
```

**What this means**:
- No `command:` directive = no config.yaml is used
- `STORE_MODEL_IN_DB: "True"` = Admin UI can manage models
- All config is done via the Admin UI at `http://localhost:4000/ui`
- Your `.env` file holds the master key and salt key

**Important notes about your setup**:
- **Do NOT regenerate `LITELLM_SALT_KEY`** - it encrypts provider credentials in the DB. Changing it makes them unreadable.
- Pin the image tag (e.g., `v1.90.2`) instead of `main-stable` for production
- The `ghcr.io/berriai/litellm` registry is preferred over `docker.litellm.ai` for monolithic deployments

---

## 7. Virtual Keys & Spend Tracking

### What Are Virtual Keys?

Virtual keys are what you give to applications and teammates instead of raw provider API keys. Each key can have:

- Its own **budget** (spend limit)
- Its own **rate limits** (requests per minute/day)
- Its own **model access** (which models it can use)
- Automatic **spend tracking**

### How Spend Is Tracked

Spend is tracked at three levels:
- **Key spend**: Stored in `LiteLLM_VerificationTokenTable`
- **User spend**: Stored in `LiteLLM_UserTable` (when key has `user_id`)
- **Team spend**: Stored in `LiteLLM_TeamTable` (when key has `team_id`)

Cost is calculated using the model pricing from `model_prices_and_context_window.json`.

### Creating Virtual Keys

**Via Admin UI**: Go to "Virtual Keys" > "+ Create New Key" > set name, budget, models > Create

**Via API**:
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

### Checking Spend

```bash
# Key spend
curl 'http://localhost:4000/key/info?key=<virtual-key>' \
  -H 'Authorization: Bearer <master-key>'

# User spend
curl 'http://localhost:4000/user/info?user_id=<user-id>' \
  -H 'Authorization: Bearer <master-key>'
```

### Key Rotation

```bash
# Environment variables for automatic rotation
LITELLM_KEY_ROTATION_ENABLED=true
LITELLM_KEY_ROTATION_CHECK_INTERVAL_SECONDS=3600
LITELLM_KEY_ROTATION_GRACE_PERIOD=48h
```

---

## 8. The Hybrid Mode: config.yaml + Database

When `STORE_MODEL_IN_DB=True` is set, LiteLLM performs a **deep merge** of config.yaml and database settings.

### Merge Rules

1. **Database wins on conflict**: If a setting exists in both YAML and DB, the DB value wins
2. **YAML is bootstrap**: Settings in YAML that are never touched in the UI remain active
3. **Null/empty = no value**: DB values of `null` or empty lists do NOT overwrite YAML
4. **Only 4 sections merge**: `general_settings`, `router_settings`, `litellm_settings`, `environment_variables`
5. **model_list is special**: Database models are NOT merged with YAML models. They are **additive** - a model added via UI becomes an additional deployment load-balanced alongside YAML models

### Practical Implications

| Scenario | What Happens |
|----------|--------------|
| Set `routing_strategy: latency-based` in YAML, never touch in UI | YAML value is used |
| Set `routing_strategy: latency-based` in YAML, change to `simple-shuffle` in UI | DB value (`simple-shuffle`) wins |
| Change YAML back to `latency-based` and restart | Still uses `simple-shuffle` from DB |
| Add `gpt-4o` in YAML AND add `gpt-4o` via UI | Both deployments are load-balanced |
| `store_model_in_db` is off | YAML is fully authoritative, DB is never read for config |

### How to Reset a DB Override

If you want YAML to win again, delete the row from the `LiteLLM_Config` table for that setting, or change it back via the Admin UI.

---

## 9. Admin UI

### Access

Navigate to `http://localhost:4000/ui` and log in with your `LITELLM_MASTER_KEY`.

### Features

- **Model Management**: Add/remove/edit models (when `STORE_MODEL_IN_DB=True`)
- **Virtual Keys**: Create, edit, delete keys with budgets and rate limits
- **Spend Tracking**: View spend per key, user, team
- **Playground**: Test models directly from the UI
- **User Management**: Create users, assign teams

### Disable Admin UI

```yaml
# In environment
DISABLE_ADMIN_UI="True"
```

### First-Time Setup

1. Go to `/ui`
2. Log in with master key
3. Create your own admin account
4. Disable environment credential login (optional security step)

---

## 10. Production Deployment

### Architecture Options

| Mode | Components | When to Use |
|------|-----------|-------------|
| **Monolithic** | Single LiteLLM deployment | Simple setups, <1000 RPS |
| **Microservices** | Gateway + Backend + UI separated | High scale, separate scaling |

### Production Checklist

1. **Pin image version**: Use `ghcr.io/berriai/litellm:v1.90.2` not `:latest`
2. **Run 2+ replicas** behind a load balancer
3. **Set `DISABLE_SCHEMA_UPDATE=true`** on proxy pods; run migrations separately
4. **Use Redis** for multi-instance rate limiting and caching
5. **Use a managed PostgreSQL** (RDS, Cloud SQL, etc.) with IAM auth
6. **Store secrets** in cloud secret manager, not env vars
7. **Configure health probes**: liveness on `/health/liveliness`, readiness on `/health/readiness`
8. **For >1000 RPS**: Enable Redis transaction buffer, evaluate high-throughput profile

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

### Supporting Infrastructure

| Component | Purpose | Required When |
|-----------|---------|---------------|
| PostgreSQL | Keys, teams, users, spend, config | Always (for auth/tracking) |
| Redis | Rate limiting, router state, caching | Running >1 instance |
| Migrations Job | Schema migrations | Startup / upgrades |

---

## 11. config.yaml Reference

### Complete Example

```yaml
model_list:
  - model_name: gpt-4o
    litellm_params:
      model: openai/gpt-4o
      api_key: os.environ/OPENAI_API_KEY
      temperature: 0.7
      timeout: 30
      max_tokens: 4096
  - model_name: gpt-4o
    litellm_params:
      model: azure/gpt-4o
      api_key: os.environ/AZURE_API_KEY
      api_base: https://my-azure.openai.azure.com/
      api_version: "2024-02-15-preview"
  - model_name: claude-3-sonnet
    litellm_params:
      model: anthropic/claude-3-sonnet-20240229
      api_key: os.environ/ANTHROPIC_API_KEY

litellm_settings:
  drop_params: true
  set_verbose: false
  cache: true
  cache_params:
    type: redis
    host: os.environ/REDIS_HOST
    port: 6379
  max_budget: 1000
  budget_duration: "1mo"

router_settings:
  routing_strategy: least-busy
  num_retries: 3
  timeout: 30
  allowed_fails: 5
  cooldown_time: 60

general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  store_model_in_db: true
  database_url: os.environ/DATABASE_URL

environment_variables:
  REDIS_HOST: localhost
  REDIS_PORT: 6379
```

### Provider Model Format

| Provider | Format |
|----------|--------|
| OpenAI | `openai/<model>` |
| Azure OpenAI | `azure/<model>` |
| Anthropic | `anthropic/<model>` |
| Gemini | `gemini/<model>` |
| Bedrock | `bedrock/<model>` |
| Ollama | `ollama/<model>` |
| vLLM | `openai/<model>` with `api_base` set |

---

## 12. Common Pitfalls & Corrections

### Verified Claims from Prior Conversation

| Claim | Status | Notes |
|-------|--------|-------|
| "Mode B has no database, no UI" | **Correct** | Docs confirm: "no Admin UI model management, virtual keys, or spend tracking" |
| "Budgets don't work without database" | **Correct** | Docs: "`max_budget` is not a spend cap on this path... the global budget check never fires" |
| "Virtual keys need a database" | **Correct** | Docs: "virtual keys themselves need a database (requests carrying one fail)" |
| "Database wins on conflict in hybrid mode" | **Correct** | Docs: "deep merge in which the database value wins on any key that exists in both places" |
| "model_list is additive, not merged" | **Correct** | Docs: "database model never replaces a same-named YAML entry but becomes an additional deployment that gets load balanced" |
| "Docker volume mount for config.yaml" | **Correct** | `-v $(pwd)/config.yaml:/app/config.yaml` |
| "CLI args passed at end of docker run" | **Correct** | `--config /app/config.yaml` after image name |
| "YAML is bootstrap, DB is source of truth" | **Correct** | Docs: "Treat the YAML as bootstrap for these four sections" |

### Common Mistakes

1. **Regenerating LITELLM_SALT_KEY**: Makes all stored provider credentials unreadable. Set once, never change.

2. **Expecting budgets to work without a database**: They silently do nothing. You only get a one-time startup warning.

3. **Editing YAML expecting changes after UI modification**: Database overrides YAML. Change settings in the UI, or delete the DB row.

4. **Using `:latest` tag in production**: Pin a specific version for deterministic rollbacks.

5. **Not setting DISABLE_SCHEMA_UPDATE on proxy pods**: Can cause migration conflicts. Let the migrations job handle schema.

6. **Thinking model_list merges/overrides**: It doesn't. Same-named models from YAML and DB are load-balanced as separate deployments.

7. **Using docker.litellm.ai for monolithic deployments**: Use `ghcr.io/berriai/litellm` which bundles the Prisma toolchain.

---

## Quick Reference: Getting Started

```bash
# 1. Generate keys
printf 'LITELLM_MASTER_KEY=sk-%s\nLITELLM_SALT_KEY=sk-%s\n' \
  "$(openssl rand -hex 32)" "$(openssl rand -hex 32)" > .env

# 2. Start
docker compose -f docker-compose.quickstart.yml up -d

# 3. Access Admin UI
# Open http://localhost:4000/ui
# Log in with your LITELLM_MASTER_KEY

# 4. Add a model (via UI or API)
curl -X POST http://localhost:4000/model/new \
  -H "Authorization: Bearer sk-your-master-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "gpt-4o",
    "litellm_params": {
      "model": "openai/gpt-4o",
      "api_key": "sk-your-openai-key"
    }
  }'

# 5. Create a virtual key
curl -X POST http://localhost:4000/key/generate \
  -H "Authorization: Bearer sk-your-master-key" \
  -H "Content-Type: application/json" \
  -d '{"duration": "30d", "max_budget": 50}'

# 6. Make a request
curl http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer sk-your-virtual-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

---

## Further Reading

- [Docker Quick Start](https://docs.litellm.ai/docs/proxy/docker_quick_start)
- [config.yaml Reference](https://docs.litellm.ai/docs/proxy/configs)
- [Production Deployment](https://docs.litellm.ai/docs/proxy/deploy)
- [Virtual Keys](https://docs.litellm.ai/docs/proxy/virtual_keys)
- [Admin UI](https://docs.litellm.ai/docs/proxy/ui)
- [Config Settings Deep Dive](https://docs.litellm.ai/docs/proxy/config_settings)
