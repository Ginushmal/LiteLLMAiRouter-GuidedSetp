# Smart Router — Top Models per Tier

_Generated: 2026-10-09T09:34:21+00:00_

**SOTA intelligence (best GOAT-available model):** 56.0   **Cost metric for NMB:** blended

_Filter: GOAT-tier plans only (46 scored models); non-GOAT and unscored models excluded._

**Capability tier floors** (fractions of SOTA; each tier topped up to 5):

| Tier | Floor (xSOTA) | Floor score | Genuine pool | Backfilled | lambda ($/point) |
|------|---------------|-------------|--------------|------------|------------------|
| Ultra | 0.90x | 50.40 | 1 | 4 | 15.00 |
| Pro | 0.80x | 44.80 | 5 | 0 | 1.00 |
| Flash | 0.50x | 28.00 | 22 | 0 | 0.20 |
| Flash Lite | 0.00x | 0.00 | 18 | 0 | 0.05 |

> Tier is decided by CAPABILITY (intelligence vs SOTA using the floor fractions above): a Pro-capability model is never labelled Ultra. Within each tier, models are ranked by iterative NMB = (lambda x intelligence) - cost - (mu x latency): select the best, remove it, and repeat. A tier with fewer than 5 genuine members is backfilled with the best models from lower tiers, marked _(+Tier)_ = the tier that model truly belongs to. (* = global Pareto frontier.)

## Ultra tier

_Floor 50.40 (0.90x SOTA) - 1 genuine models - 4 backfilled._

| # | Model | Base name | Intel | Cod | Cost $/M (blend) | Cost/task | Input $/M | Output $/M | Cache rd $/M | Context | NMB | Plan |
|---|-------|-----------|-------|-----|------------------|-----------|-----------|------------|-------------|---------|-----|------|
| 1 | Claude Sonnet 5.5 * | `openai/claude-sonnet-5-5` | 56.0 | — | $4 | $0.2875 | $2 | $10 | $0.1 | 1M | 836.0 | GOAT and above |
| 2 | Muse Spark 1.3 * _(+Pro)_ | `openai/meta/muse-spark-1.3` | 48.1 | — | $2 | $0.171 | $1.25 | $4.25 | $0.15 | 1M | 719.5 | GOAT and above |
| 3 | MiMo V2.6 Pro * _(+Pro)_ | `openai/xiaomi/mimo-v2.6-pro` | 46.3 | — | $0.5437 | $0.04369 | $0.435 | $0.87 | $0.0036 | 1M | 693.9562 | Go and above |
| 4 | GPT-5.6 Sol _(+Pro)_ | `openai/gpt-5.6-sol` | 47.0 | — | $11.25 | $0.8225 | $5 | $30 | $0.5 | 1.1M | 693.75 | GOAT and above |
| 5 | Grok 4.7 _(+Pro)_ | `openai/xai/grok-4.7` | 46.4 | — | $3 | $0.3095 | $2 | $6 | $0.5 | 500K | 693.0 | GOAT and above |

## Pro tier

_Floor 44.80 (0.80x SOTA) - 5 genuine models - 0 backfilled._

| # | Model | Base name | Intel | Cod | Cost $/M (blend) | Cost/task | Input $/M | Output $/M | Cache rd $/M | Context | NMB | Plan |
|---|-------|-----------|-------|-----|------------------|-----------|-----------|------------|-------------|---------|-----|------|
| 1 | Muse Spark 1.3 * | `openai/meta/muse-spark-1.3` | 48.1 | — | $2 | $0.171 | $1.25 | $4.25 | $0.15 | 1M | 46.1 | GOAT and above |
| 2 | MiMo V2.6 Pro * | `openai/xiaomi/mimo-v2.6-pro` | 46.3 | — | $0.5437 | $0.04369 | $0.435 | $0.87 | $0.0036 | 1M | 45.7562 | Go and above |
| 3 | Grok 4.7 | `openai/xai/grok-4.7` | 46.4 | — | $3 | $0.3095 | $2 | $6 | $0.5 | 500K | 43.4 | GOAT and above |
| 4 | Qwen 3.8 Max 0902 | `openai/Qwen/Qwen3.8-Max-0902` | 45.4 | — | $3 | $0.2658 | $2 | $6 | $0.25 | 1M | 42.4 | Go and above |
| 5 | GPT-5.6 Sol | `openai/gpt-5.6-sol` | 47.0 | — | $11.25 | $0.8225 | $5 | $30 | $0.5 | 1.1M | 35.75 | GOAT and above |

## Flash tier

_Floor 28.00 (0.50x SOTA) - 22 genuine models - 0 backfilled._

| # | Model | Base name | Intel | Cod | Cost $/M (blend) | Cost/task | Input $/M | Output $/M | Cache rd $/M | Context | NMB | Plan |
|---|-------|-----------|-------|-----|------------------|-----------|-----------|------------|-------------|---------|-----|------|
| 1 | GLM-5.3 Flash * | `openai/z-ai/glm-5.3-flash` | 41.8 | — | $0.2375 | $0.0225 | $0.15 | $0.5 | $0.03 | 1M | 8.1225 | Go and above |
| 2 | DeepSeek V4.1 Flash | `openai/deepseek/deepseek-v4.1-flash` | 39.5 | — | $0.2625 | $0.01897 | $0.15 | $0.6 | $0.003 | 1M | 7.6375 | Go and above |
| 3 | MiMo V2.6 Flash * | `openai/xiaomi/mimo-v2.6-flash` | 37.9 | — | $0.175 | $0.01435 | $0.14 | $0.28 | $0.0028 | 1M | 7.405 | Go and above |
| 4 | Step 5 Preview | `openai/stepfun/Step-5-Preview` | 43.7 | — | $1.425 | $0.1162 | $1 | $2.7 | $0.05 | 1M | 7.315 | Go and above |
| 5 | GPT-6 Luna | `openai/gpt-6-luna` | 37.3 | — | $0.2 | $0.01525 | $0.1 | $0.5 | $0.01 | 1.1M | 7.26 | Go and above |

## Flash Lite tier

_Floor 0.00 (0.00x SOTA) - 18 genuine models - 0 backfilled._

| # | Model | Base name | Intel | Cod | Cost $/M (blend) | Cost/task | Input $/M | Output $/M | Cache rd $/M | Context | NMB | Plan |
|---|-------|-----------|-------|-----|------------------|-----------|-----------|------------|-------------|---------|-----|------|
| 1 | Tencent Hy3 | `openai/tencent/hy3-paid` | 25.3 | — | $0.25 | $0.02359 | $0.14 | $0.58 | $0.035 | 262K | 1.015 | Go and above |
| 2 | Inkling Small | `openai/thinkingmachines/inkling-small` | 27.8 | — | $0.675 | $0.0694 | $0.5 | $1.2 | $0.1 | 1M | 0.715 | Go and above |
| 3 | Step 3.5 Flash * | `openai/stepfun/Step-3.5-Flash` | 17.0 | — | $0.1425 | $0.01385 | $0.09 | $0.3 | $0.02 | 262K | 0.7075 | Go and above |
| 4 | MiniMax M2.7 | `openai/MiniMaxAI/MiniMax-M2.7` | 22.8 | — | $0.525 | $0.0474 | $0.3 | $1.2 | $0.06 | 200K | 0.615 | Go and above |
| 5 | MiniMax M2.5 | `openai/MiniMaxAI/MiniMax-M2.5` | 22.8 | — | $0.525 | $0.04215 | $0.3 | $1.2 | $0.03 | 200K | 0.615 | Go and above |

## Not scored (excluded from ranking)

Claude Haiku 5.5, Glyph Cluster, Mistral Large 4, DeepSeek V4.1 Flash Fast, Ling 3.1 Flash, Jev, MiMo V2.6 Pro UltraSpeed, GLM-5.3 FlashX, Qwen 3.8 Omni Flash, Ling 3.0 Flash Sante, Muse Spark 1.3 Contributor, Tencent Hy4 Preview, Qwen 3.8 Flash, DeepSeek V4 Flash Fast, Muse Spark 1.2 Contributor, Qwen 3.7 Flash, Laguna S 2.1, GLM-5.2 Fast, Fugu Ultra, Kimi K2.7 Code HighSpeed

## Scored but not on the GOAT plan (excluded)

GPT-6.1 Sol, GPT-6 Sol, Claude Opus 5.5, GPT-6 Astra, Claude Fable 5.1, Claude Opus 5, Gemini 3.5 Flash Lite, Gemini 3.6 Flash, Muse Spark 1.1, GPT-5.6 Terra, Claude Sonnet 5, Claude Fable 5, Claude Opus 4.8, Gemini 3.5 Flash, Gemini 3.1 Flash Lite, GPT-5.5, Claude Opus 4.7, GPT-5.4 Mini, GPT-5.3 Codex, GPT-5.4, Claude Haiku 4.5, Claude Sonnet 4.6

---

Global Pareto frontier: **6** efficient, **40** dominated (advisory only). Latency penalty mu = 0.0 (CommandCode does not publish latency, so the term is inert by default).