# LiteLLM Study Roadmap

The master checklist of everything we intend to study about LiteLLM. It is hierarchical: **Tracks** are major areas, numbered items are study topics.

**How to use it**

- `[x]` = studied, verified, and logged in [LiteLLM-Learnings.md](./LiteLLM-Learnings.md) (and, if it involved a setup action, in [Setup-Guide.md](./Setup-Guide.md)).
- `[ ]` = not studied yet.
- **Tick the checkbox in the same session the topic is completed.** This file is the progress tracker for the whole project.
- Items marked **ENT** are Enterprise-only and out of scope for hands-on work (we note them so we know what we cannot use). Items marked **tier?** have not yet been confirmed OSS vs Enterprise - confirm at study time.

**Tier legend:** `OSS` = open-source (usable) · `ENT` = Enterprise-only (verified at <https://docs.litellm.ai/docs/enterprise>) · `tier?` = not yet verified

---

## Track 1 - Foundations `[COMPLETE]`

- [x] 1.1 What LiteLLM is / why use it / how it works
- [x] 1.2 Architecture & components (proxy, router, DB, Admin UI)
- [x] 1.3 Key environment variables (`MASTER_KEY`, `DATABASE_URL`, `LITELLM_SALT_KEY`, ...)
- [x] 1.4 Operating modes: A Quickstart - B Stateless - C Hybrid
- [x] 1.5 config.yaml vs database overlay (hybrid precedence)

## Track 2 - config.yaml & Deployment `[COMPLETE]`

- [x] 2.1 config.yaml structure (`model_list`, `litellm_settings`, `router_settings`, `general_settings`, `environment_variables`)
- [x] 2.2 Docker deployment: volumes, CLI arguments, Compose (hybrid mode)
- [x] 2.3 Health check endpoints
- [x] 2.4 Config reload (hot reload vs recreate)

## Track 3 - Model Configuration `[COMPLETE]`

- [x] 3.1 Provider format (`provider/model`, `api_base`, `api_key`, `api_version`)
- [x] 3.2 OpenAI-compatible custom providers
- [x] 3.3 `model_name` is just an alias

## Track 4 - Pricing & Cost `[COMPLETE]`

- [x] 4.1 LiteLLM's built-in cost map
- [x] 4.2 Display cost vs accounting cost
- [x] 4.3 `base_model` for automatic pricing
- [x] 4.4 Custom pricing per model (in config)
- [x] 4.5 Self-hosted custom cost map (`custom_cost_map.json`) + diagnostics

## Track 5 - Routing & Load Balancing `[BASICS DONE]`

- [x] 5.1 Routing strategies (`simple-shuffle`, ...)
- [x] 5.2 How layers compose (router-level vs per-model)
- [x] 5.3 `routing_groups` (per-model strategies)
- [x] 5.4 Routing groups as callable virtual models
- [x] 5.5 Deployment `order` + failover
- [x] 5.6 Fallbacks (different model groups)
- [ ] 5.7 Reliability knobs in action: `num_retries` / `allowed_fails` / `cooldown_time` / `timeout` / retry policy
- [ ] 5.8 Other strategies hands-on: `least-busy`, `usage-based-routing-v2`, `latency-based-routing`, `cost-based-routing` + `routing_strategy_weight`
- [ ] 5.9 Context-window fallbacks & content-policy fallbacks
- [ ] 5.10 Health checks / cooldown behavior under real failures

## Track 6 - Identity: Keys, Teams, Users `[CORE DONE]`

- [x] 6.1 Tenancy hierarchy
- [x] 6.2 Three kinds of key
- [x] 6.3 Roles
- [x] 6.4 Model access - how it combines
- [x] 6.5 Budgets - how they combine
- [x] 6.6 Config-driven defaults & upperbounds (`default_key_generate_params`, `upperbound_key_generate_params`, `default_team_params`)
- [x] 6.7 Key lifecycle basics (create via Admin UI / API)
- [x] 6.8 Admin UI - what the forms actually have
- [x] 6.9 Enterprise vs OSS (identity layer)
- [x] 6.10 Spend tracking (key / user / team)
- [ ] 6.11 **End-users vs internal users** - the `user` field on requests, `max_end_user_budget_id`
- [ ] 6.12 **Rate-limit layering** - tpm/rpm/max_parallel at key/team/user; per-model `model_rpm_limit`/`model_tpm_limit` (OSS)
- [ ] 6.13 **Access groups** - `model_info.access_groups`
- [ ] 6.14 **Key lifecycle ops** - update / block / unblock / delete / expiry (key rotation = ENT)
- [ ] 6.15 Organizations & fine-grained RBAC (ENT)

## Track 7 - Admin UI & Reporting `[PARTIAL]`

- [x] 7.1 Access, first-time setup, disable Admin UI
- [x] 7.2 Features overview
- [ ] 7.3 **Spend reporting** - Usage / Logs views, per-model breakdown
- [ ] 7.4 Budget durations / reset & budget alerts
- [ ] 7.5 AI Hub branded page (ENT)

## Track 8 - Proxy API Surface `[NOT STARTED]`

- [ ] 8.1 `/chat/completions` request/response shape
- [ ] 8.2 Streaming (SSE) + `stream_options.include_usage`
- [ ] 8.3 Tool / function calling
- [ ] 8.4 Structured output (`response_format`, json_schema)
- [ ] 8.5 `/embeddings`
- [ ] 8.6 `/rerank`
- [ ] 8.7 `/images`
- [ ] 8.8 `/audio/speech` + `/audio/transcriptions`
- [ ] 8.9 `/moderations`
- [ ] 8.10 Responses API (tier?)
- [ ] 8.11 Batches API (tier?)
- [ ] 8.12 Fine-tuning API (tier?)
- [ ] 8.13 Passthrough endpoints (Anthropic `/v1/messages`, generic)
- [ ] 8.14 Token counting & context-window enforcement
- [ ] 8.15 Provider-specific params + `drop_params`

## Track 9 - Python SDK `[NOT STARTED]`

- [ ] 9.1 `completion` / `acompletion`
- [ ] 9.2 Streaming + exception mapping
- [ ] 9.3 `embedding` / `image_generation` / `speech` / `transcription` / `rerank`
- [ ] 9.4 Custom logger / callbacks in SDK
- [ ] 9.5 Cost & usage tracking in SDK

## Track 10 - Observability & Logging `[NOT STARTED]`

- [ ] 10.1 Callback model - success/failure hooks, custom callbacks (OSS)
- [ ] 10.2 Langfuse integration
- [ ] 10.3 Prometheus metrics (+ Grafana)
- [ ] 10.4 OpenTelemetry
- [ ] 10.5 Object-storage logging: S3 / GCS / Azure Blob (GCS & Azure log export = ENT)
- [ ] 10.6 Other integrations: Helicone, Supabase, MLflow, ...
- [ ] 10.7 Team-based logging & per-team disable (ENT)
- [ ] 10.8 Alerting (budget / usage alerts)

## Track 11 - Guardrails `[NOT STARTED]`

- [ ] 11.1 Guardrail framework (pre/post-call hooks) (OSS)
- [ ] 11.2 Custom guardrails (OSS)
- [ ] 11.3 Presidio PII masking (OSS)
- [ ] 11.4 Built-ins needing a license (ENT): `llmguard_moderations`, `llamaguard_moderations`, `hide_secrets`, `openai_moderations`, `google_text_moderation`, `lakera_prompt_injection`, `aporia_prompt_injection`
- [ ] 11.5 Guardrails per key/team + enforced required params (ENT)

## Track 12 - Caching `[NOT STARTED]`

- [ ] 12.1 Response caching (Redis / disk), `ttl`, `namespace` (tier?)
- [ ] 12.2 Semantic caching (tier?)

## Track 13 - Prompt Management `[NOT STARTED]`

- [ ] 13.1 Prompt registry / templates (config + Admin UI) (tier?)

## Track 14 - Agent & MCP Gateway `[NOT STARTED]`

- [ ] 14.1 MCP gateway, per-key tool access (tier?)
- [ ] 14.2 A2A agents (tier?)
- [ ] 14.3 Agent gateway (ENT - see Enterprise Quickstart)

## Track 15 - Production & Security `[PARTIAL]`

- [x] 15.1 Architecture options
- [x] 15.2 Production checklist
- [x] 15.3 Redis requirements
- [x] 15.4 Kubernetes deployment (key parts)
- [ ] 15.5 Hands-on Helm/K8s deploy, `DISABLE_SCHEMA_UPDATE`, multi-pod migrations
- [ ] 15.6 High availability: multi-instance + shared DB/Redis
- [ ] 15.7 SSO (OIDC/SAML) for Admin UI (ENT - free for up to 5 users)
- [ ] 15.8 JWT / token auth (ENT)
- [ ] 15.9 Audit logs (ENT)
- [ ] 15.10 IP allowlists + public/private route controls (ENT)
- [ ] 15.11 Secret managers (ENT)
- [ ] 15.12 Key rotation (ENT)

## Track 16 - Pitfalls & Reference `[ONGOING]`

- [x] 16.1 Common pitfalls 1-17 documented
- [x] 16.2 Quick reference (Docker / API / cost-map diagnostics)
- [ ] 16.3 Keep appending as new pitfalls are found

---

## Recommended order from here

1. **Finish the identity/reporting story:** 6.11 end-users -> 6.12 rate limits -> 6.13 access groups -> 6.14 key lifecycle -> 7.3 spend reporting.
2. **Track 8 - Proxy API surface** (streaming, tools, embeddings): the layer used every day.
3. **Track 10 + Track 11** (observability + guardrails).
4. **Track 15 remainder** (production/security notes - mostly ENT awareness).

Document every confirmed finding in [LiteLLM-Learnings.md](./LiteLLM-Learnings.md) (and [Setup-Guide.md](./Setup-Guide.md) if it is a setup action), then tick the matching item(s) here.
