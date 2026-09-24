# LiteLLM Setup Guide: Fresh Start with config.yaml

> This guide walks you through resetting your LiteLLM database and setting up everything from scratch using the config.yaml file, API commands, and docker-compose.

---

## Prerequisites

- Podman (or Docker) installed and running
- Your CommandCode Goat Subscription API key
- The files in this directory:
  - `docker-compose.quickstart.yml` (updated with config.yaml volume mount)
  - `config.yaml` (model definitions with pricing)
  - `.env` (environment variables)

---

## Step 1: Reset Database (Fresh Start)

This wipes all existing data (teams, users, keys, models) from the Admin UI.

```powershell
# Stop containers
podman compose -f docker-compose.quickstart.yml down

# Remove the postgres volume (this wipes all data)
podman volume rm litellm_postgres_data

# If the volume name is different, find it with:
podman volume ls
```

> **Note**: If you get "volume not found", the volume may have a different prefix. Run `podman volume ls` and look for a volume containing `postgres_data`.

---

## Step 2: Set Your API Key

Edit `.env` and replace the placeholder with your actual CommandCode API key:

```env
LITELLM_MASTER_KEY=sk-7a213531c3a92bfbe95e3ea0cb4be35d6b7b8315ac1369c854bc63cd648049fe
LITELLM_SALT_KEY=sk-b83301646edd9198fff63026c43ce2bba5b253760499691093a0f38e1f62038a

# CommandCode Goat Subscription API Key
# Get this from your CommandCode dashboard
COMMANDCODE_API_KEY=sk-your-actual-key-from-commandcode
```

> **IMPORTANT**: Do NOT change `LITELLM_SALT_KEY` after you've added models. It encrypts provider credentials in the database. Changing it makes them unreadable.

---

## Step 3: Start the Stack

```powershell
podman compose -f docker-compose.quickstart.yml up -d
```

Wait ~30 seconds for the database to initialize, then verify the proxy started:

```powershell
podman compose -f docker-compose.quickstart.yml logs litellm
```

You should see something like:
```
litellm  | INFO:     Uvicorn running on http://0.0.0.0:4000
```

Check health:
```powershell
curl http://localhost:4000/health/readiness
```

---

## Step 4: Create Team, User, and Virtual Key

### 4.1 Create Team "BA"

```powershell
$MASTER_KEY = "sk-7a213531c3a92bfbe95e3ea0cb4be35d6b7b8315ac1369c854bc63cd648049fe"

curl -X POST http://localhost:4000/team/new `
  -H "Authorization: Bearer $MASTER_KEY" `
  -H "Content-Type: application/json" `
  -d '{"team_id": "BA", "team_alias": "BA Team"}'
```

**Expected response**:
```json
{
  "team_id": "BA",
  "key": "sk-...",
  "team_alias": "BA Team"
}
```

### 4.2 Create Internal User "Boo"

```powershell
curl -X POST http://localhost:4000/user/new `
  -H "Authorization: Bearer $MASTER_KEY" `
  -H "Content-Type: application/json" `
  -d '{
    "user_id": "boo",
    "user_email": "booboo192939@gmail.com",
    "models": ["flash-tier", "pro-tier"]
  }'
```

**Expected response**:
```json
{
  "user_id": "boo",
  "key": "sk-...",
  "user_email": "booboo192939@gmail.com"
}
```

### 4.3 Create Virtual Key for Boo under BA Team

```powershell
curl -X POST http://localhost:4000/key/generate `
  -H "Authorization: Bearer $MASTER_KEY" `
  -H "Content-Type: application/json" `
  -d '{
    "user_id": "boo",
    "team_id": "BA",
    "duration": "30d",
    "models": ["flash-tier", "pro-tier"]
  }'
```

**Expected response**:
```json
{
  "key": "sk-abc123...",
  "key_name": "...",
  "user_id": "boo",
  "team_id": "BA",
  "expires": "2026-10-24T..."
}
```

> **SAVE THIS KEY** - it is only shown once. This is what your apps will use to make API calls.

### 4.4 (Optional) Add Budget to the Key

```powershell
# First, get the key hash from the response above
$KEY_HASH = "the-key-from-step-4.3"

curl -X POST http://localhost:4000/key/update `
  -H "Authorization: Bearer $MASTER_KEY" `
  -H "Content-Type: application/json" `
  -d "{
    \"key\": \"$KEY_HASH\",
    \"max_budget\": 50,
    \"budget_duration\": \"1mo\"
  }"
```

---

## Step 5: Test It

### Test with Flash Tier

```powershell
$VIRTUAL_KEY = "sk-the-key-from-step-4.3"

curl http://localhost:4000/v1/chat/completions `
  -H "Authorization: Bearer $VIRTUAL_KEY" `
  -H "Content-Type: application/json" `
  -d '{
    "model": "flash-tier",
    "messages": [{"role": "user", "content": "Hello! What model are you?"}]
  }'
```

### Test with Pro Tier

```powershell
curl http://localhost:4000/v1/chat/completions `
  -H "Authorization: Bearer $VIRTUAL_KEY" `
  -H "Content-Type: application/json" `
  -d '{
    "model": "pro-tier",
    "messages": [{"role": "user", "content": "Hello! What model are you?"}]
  }'
```

> **Note**: "pro-tier" will load-balance between DeepSeek V4 Pro and Qwen 3.7 Plus since both share the same `model_name`.

---

## Step 6: Verify Spend Tracking

```powershell
# Check key spend
curl "http://localhost:4000/key/info?key=$VIRTUAL_KEY" `
  -H "Authorization: Bearer $MASTER_KEY"

# Check user spend
curl "http://localhost:4000/user/info?user_id=boo" `
  -H "Authorization: Bearer $MASTER_KEY"

# Check team spend
curl "http://localhost:4000/team/info?team_id=BA" `
  -H "Authorization: Bearer $MASTER_KEY"
```

---

## Step 7: Access Admin UI

Open your browser to: **http://localhost:4000/ui**

Log in with your master key: `sk-7a213531c3a92bfbe95e3ea0cb4be35d6b7b8315ac1369c854bc63cd648049fe`

You should see:
- **Models**: flash-tier, pro-tier (loaded from config.yaml)
- **Virtual Keys**: The key you created for Boo
- **Teams**: BA Team
- **Users**: Boo

---

## Understanding the Setup

### What Lives Where

| Component | Configured In | Managed Via |
|-----------|--------------|-------------|
| Models + Pricing | `config.yaml` | config.yaml (bootstrap) + Admin UI (additive) |
| Teams | Database | API `/team/new` or Admin UI |
| Users | Database | API `/user/new` or Admin UI |
| Virtual Keys | Database | API `/key/generate` or Admin UI |
| Routing | `config.yaml` | config.yaml (Admin UI overrides if changed there) |

### Model Groups Explained

In `config.yaml`, models with the same `model_name` are automatically load-balanced:

```yaml
model_list:
  - model_name: pro-tier    # <-- Same name
    litellm_params:
      model: openai/deepseek-v4-pro
  - model_name: pro-tier    # <-- Same name
    litellm_params:
      model: openai/qwen3.7-plus
```

When an app requests `model: "pro-tier"`, LiteLLM will route to either DeepSeek V4 Pro or Qwen 3.7 Plus based on the routing strategy (default: simple-shuffle).

### Pricing Explained

The `model_info` section sets custom pricing for cost tracking:

```yaml
model_info:
  base_model: deepseek-v4.1-flash
  input_cost_per_token: 0.0000001   # $0.10 per million input tokens
  output_cost_per_token: 0.0000002  # $0.20 per million output tokens
```

- `base_model`: Used for pricing lookup (must match a known model or your custom definition)
- `input_cost_per_token`: Cost per input token in USD
- `output_cost_per_token`: Cost per output token in USD

**Calculation**: `$X per million tokens` = `X / 1,000,000` per token

Example: $0.10 per million = 0.10 / 1,000,000 = 0.0000001

---

## Troubleshooting

### "No pricing data found for this model"

This error occurs when `model_info` is missing or `base_model` doesn't match. Fix:
1. Ensure every model in config.yaml has `model_info` with `input_cost_per_token` and `output_cost_per_token`
2. Set `base_model` to a unique identifier for each model

### "Budgets not enforced"

Budgets require a database. Verify:
1. `DATABASE_URL` is set in docker-compose
2. `STORE_MODEL_IN_DB=True` is set
3. The database container is healthy

### Models not showing in Admin UI

Since `STORE_MODEL_IN_DB=True`, models from config.yaml are loaded at startup. If you don't see them:
1. Check config.yaml syntax (YAML is indentation-sensitive)
2. Restart the proxy: `podman compose -f docker-compose.quickstart.yml restart litellm`
3. Check logs: `podman compose -f docker-compose.quickstart.yml logs litellm`

### API key not working

1. Verify the key is correct: `curl http://localhost:4000/health -H "Authorization: Bearer $VIRTUAL_KEY"`
2. Check key expiration: Keys have a `duration` (e.g., "30d")
3. Check key models: Ensure the requested model is in the key's allowed models list

---

## Future Expansion

### Add a New Model

Add to `config.yaml`:

```yaml
  - model_name: new-model
    litellm_params:
      model: openai/new-model-name
      api_base: https://api.commandcode.ai/provider/v1
      api_key: os.environ/COMMANDCODE_API_KEY
    model_info:
      base_model: new-model-name
      input_cost_per_token: 0.0000003
      output_cost_per_token: 0.0000006
```

Then restart: `podman compose -f docker-compose.quickstart.yml restart litellm`

### Add Fallbacks

```yaml
# In config.yaml, uncomment and modify:
model_fallbacks:
  - pro-tier: ["flash-tier"]  # If pro-tier fails, try flash-tier
```

### Add Rate Limits

Per-team (when creating team):
```powershell
curl -X POST http://localhost:4000/team/new `
  -H "Authorization: Bearer $MASTER_KEY" `
  -H "Content-Type: application/json" `
  -d '{
    "team_id": "BA",
    "team_alias": "BA Team",
    "tpm_limit": 100000,
    "rpm_limit": 1000
  }'
```

Per-key (when creating key):
```powershell
curl -X POST http://localhost:4000/key/generate `
  -H "Authorization: Bearer $MASTER_KEY" `
  -H "Content-Type: application/json" `
  -d '{
    "user_id": "boo",
    "team_id": "BA",
    "tpm_limit": 50000,
    "rpm_limit": 500
  }'
```

### Add Caching

Requires Redis. Add to docker-compose:

```yaml
  redis:
    image: redis:7
    ports:
      - "6379:6379"
```

Uncomment in config.yaml:
```yaml
litellm_settings:
  cache: true
  cache_params:
    type: redis
    host: redis
    port: 6379
```

### Add Observability (Langfuse)

Uncomment in config.yaml:
```yaml
litellm_settings:
  success_callback: ["langfuse"]
  failure_callback: ["langfuse"]

environment_variables:
  LANGFUSE_SECRET_KEY: sk-lf-...
  LANGFUSE_PUBLIC_KEY: pk-lf-...
  LANGFUSE_HOST: https://cloud.langfuse.com
```

---

## Documentation References

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
| Caching | https://docs.litellm.ai/docs/caching/gpt_cache |
| Guardrails | https://docs.litellm.ai/docs/proxy/guardrails |
| Observability | https://docs.litellm.ai/docs/observability/callbacks |
| Production Deployment | https://docs.litellm.ai/docs/proxy/deploy |
| Admin UI | https://docs.litellm.ai/docs/proxy/ui |
| Model Management | https://docs.litellm.ai/docs/proxy/model_management |

---

## Quick Command Reference

```powershell
# Start
podman compose -f docker-compose.quickstart.yml up -d

# Stop
podman compose -f docker-compose.quickstart.yml down

# Restart proxy only
podman compose -f docker-compose.quickstart.yml restart litellm

# View logs
podman compose -f docker-compose.quickstart.yml logs -f litellm

# Health check
curl http://localhost:4000/health/readiness

# List models
curl http://localhost:4000/model/info -H "Authorization: Bearer $MASTER_KEY"

# List keys
curl http://localhost:4000/key/list -H "Authorization: Bearer $MASTER_KEY"

# List teams
curl http://localhost:4000/team/list -H "Authorization: Bearer $MASTER_KEY"

# List users
curl http://localhost:4000/user/list -H "Authorization: Bearer $MASTER_KEY"

# Delete a key
curl -X POST http://localhost:4000/key/delete -H "Authorization: Bearer $MASTER_KEY" -H "Content-Type: application/json" -d '{"keys": ["sk-key-to-delete"]}'

# Reset everything
podman compose -f docker-compose.quickstart.yml down && podman volume rm litellm_postgres_data && podman compose -f docker-compose.quickstart.yml up -d
```
