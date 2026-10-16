# Model pipeline — ranking report

_Generated: 2026-10-16T06:02:39+00:00_

**SOTA intelligence:** 57.6

**NMB** = lambda * intelligence - cost_per_task - mu * latency   (mu = 0.0)

A model is eligible for **every** tier whose floor it meets:

| Tier | Model group | Floor (x SOTA) | lambda | top-K |
|------|-------------|----------------|--------|-------|
| Ultra | `ultra-tier` | 46.08 (0.80x) | 1.0 | 5 |
| Pro | `pro-tier` | 34.56 (0.60x) | 0.2 | 5 |
| Flash | `flash-tier` | 20.16 (0.35x) | 0.005 | 5 |
| Flash Lite | `flash-lite-tier` | 0.00 (0.00x) | 0.0005 | 5 |

## Model index

Every scored model, where it was eligible, and where it was selected.

| Model | Intel | Best cost/task | Pareto | Eligible tiers | Selected in |
|-------|------:|---------------:|--------|----------------|-------------|
| Claude Opus 5.5 | 57.6 | $3.5068 | frontier | Ultra, Pro, Flash, Flash Lite | Ultra |
| Claude Sonnet 5.5 | 56 | $3.2013 | frontier | Ultra, Pro, Flash, Flash Lite | Ultra |
| Claude Fable 5.1 | 53.4 | $4.3896 | dominated | Ultra, Pro, Flash, Flash Lite | — |
| GPT-6 Astra | 52.7 | $1.9806 | frontier | Ultra, Pro, Flash, Flash Lite | Ultra |
| Gemini 4 Argon | 52.6 | $1.1668 | frontier | Ultra, Pro, Flash, Flash Lite | Ultra, Pro |
| Muse Wonder | 52.4 | $2.6472 | dominated | Ultra, Pro, Flash, Flash Lite | — |
| GPT-6.1 Sol | 51.8 | $0.4245 | frontier | Ultra, Pro, Flash, Flash Lite | Ultra, Pro |
| Claude Opus 5 | 50.8 | $3.5619 | dominated | Ultra, Pro, Flash, Flash Lite | — |
| Claude Fable 5 | 49.6 | $5.3176 | dominated | Ultra, Pro, Flash, Flash Lite | — |
| Muse Spark 1.3 | 48.1 | $0.8568 | dominated | Ultra, Pro, Flash, Flash Lite | — |
| GPT-6 Sol | 47.6 | $0.6352 | dominated | Ultra, Pro, Flash, Flash Lite | — |
| GPT-5.6 Sol | 47 | $1.7874 | dominated | Ultra, Pro, Flash, Flash Lite | — |
| Grok 4.7 | 46.4 | $2.1682 | dominated | Ultra, Pro, Flash, Flash Lite | — |
| MiMo V2.6 Pro | 46.3 | $0.0469 | frontier | Ultra, Pro, Flash, Flash Lite | Pro, Flash |
| Qwen 3.8 Max 0902 | 45.4 | $2.7583 | dominated | Pro, Flash, Flash Lite | — |
| GLM-5.3 | 44.8 | $1.1093 | dominated | Pro, Flash, Flash Lite | — |
| Grok 4.6 | 44.3 | $0.8612 | dominated | Pro, Flash, Flash Lite | — |
| Step 5 Preview | 43.7 | $0.4559 | dominated | Pro, Flash, Flash Lite | — |
| Kimi K3 | 43.6 | $1.2161 | dominated | Pro, Flash, Flash Lite | — |
| Claude Haiku 5.5 | 43.4 | $0.1294 | dominated | Pro, Flash, Flash Lite | — |
| GPT-5.6 Terra | 42.1 | $0.9052 | dominated | Pro, Flash, Flash Lite | — |
| GLM-5.3 Flash | 41.8 | $0.1623 | dominated | Pro, Flash, Flash Lite | — |
| Claude Opus 4.8 | 41.8 | $2.4812 | dominated | Pro, Flash, Flash Lite | — |
| Ling 3.1 Flash | 41.1 | $0.5518 | dominated | Pro, Flash, Flash Lite | — |
| Gemini 3.8 Flash | 40.9 | $1.5112 | dominated | Pro, Flash, Flash Lite | — |
| Claude Opus 4.7 | 40.7 | $0.2950 | dominated | Pro, Flash, Flash Lite | — |
| qwen3.8-flash | 39.8 | $0.1895 | dominated | Pro, Flash, Flash Lite | — |
| Muse Spark 1.2 | 39.6 | $0.5203 | dominated | Pro, Flash, Flash Lite | — |
| DeepSeek V4.1 Flash | 39.5 | $0.0689 | dominated | Pro, Flash, Flash Lite | — |
| Gemini 3.7 Flash | 39.1 | $1.1252 | dominated | Pro, Flash, Flash Lite | — |
| GPT-5.4 | 39 | $0.1500 | dominated | Pro, Flash, Flash Lite | — |
| Grok 4.5 | 38.8 | $0.5108 | dominated | Pro, Flash, Flash Lite | — |
| Mistral Large 4 | 38.4 | $0.5703 | dominated | Pro, Flash, Flash Lite | — |
| GPT-5.5 | 38.4 | $1.7047 | dominated | Pro, Flash, Flash Lite | — |
| Claude Sonnet 5 | 38.2 | $3.0954 | dominated | Pro, Flash, Flash Lite | — |
| GPT-6 Luna | 38.1 | $0.0412 | frontier | Pro, Flash, Flash Lite | Flash |
| MiMo V2.6 Flash | 37.9 | $0.0224 | frontier | Pro, Flash, Flash Lite | Flash, Flash Lite |
| GPT-5.6 Luna | 37.3 | $0.1154 | dominated | Pro, Flash, Flash Lite | — |
| DeepSeek V4 Pro (latest) | 36 | $0.1546 | dominated | Pro, Flash, Flash Lite | — |
| DeepSeek V4 Flash Vision (exp) | 34.8 | $0.0637 | dominated | Pro, Flash, Flash Lite | — |
| DeepSeek V4 Flash (latest) | 34.3 | $0.0445 | dominated | Flash, Flash Lite | — |
| Gemini 3.6 Flash | 34 | $1.9462 | dominated | Flash, Flash Lite | — |
| Qwen 3.8 27B | 33.7 | $0.6425 | dominated | Flash, Flash Lite | — |
| Muse Spark 1.1 | 33.7 | $0.7368 | dominated | Flash, Flash Lite | — |
| GLM-5.2 | 33.7 | $0.8145 | dominated | Flash, Flash Lite | — |
| Gemini 3.5 Flash | 32.6 | $2.3906 | dominated | Flash, Flash Lite | — |
| GPT-5.3 Codex | 32.5 | $0.1810 | dominated | Flash, Flash Lite | — |
| Muse Spark Open | 31.3 | $0.0699 | dominated | Flash, Flash Lite | — |
| Qwen 3.7 Max | 29.5 | $0.6333 | dominated | Flash, Flash Lite | — |
| MiniMax M3 | 29.2 | $0.3086 | dominated | Flash, Flash Lite | — |
| Qwen 3.6 Max Preview | 28.4 | $0.1138 | dominated | Flash, Flash Lite | — |
| GLM-5 | 27.9 | $0.0752 | dominated | Flash, Flash Lite | — |
| Qwen 3.6 Plus | 27 | $0.0425 | dominated | Flash, Flash Lite | — |
| Kimi K2.6 | 27 | $0.4823 | dominated | Flash, Flash Lite | — |
| GLM-5.1 | 26.1 | $0.6122 | dominated | Flash, Flash Lite | — |
| MiMo V2.5 Pro | 26 | $0.0190 | frontier | Flash, Flash Lite | Flash, Flash Lite |
| Kimi K2.7 Code | 25.8 | $0.3345 | dominated | Flash, Flash Lite | — |
| Inkling Small | 25.7 | $0.0609 | dominated | Flash, Flash Lite | — |
| Tencent Hy3 | 25.3 | $0.0476 | dominated | Flash, Flash Lite | — |
| Qwen 3.7 Plus | 25.2 | $0.1319 | dominated | Flash, Flash Lite | — |
| Inkling | 25 | $0.0707 | dominated | Flash, Flash Lite | — |
| Claude Sonnet 4.6 | 24.7 | $0.1770 | dominated | Flash, Flash Lite | — |
| GPT-5.4 Mini | 24.1 | $0.2896 | dominated | Flash, Flash Lite | — |
| Kimi K2.5 | 23.5 | $0.0439 | dominated | Flash, Flash Lite | — |
| Nemotron 3 Ultra | 22.9 | $0.3559 | dominated | Flash, Flash Lite | — |
| MiniMax M2.5 | 22.8 | $0.0167 | frontier | Flash, Flash Lite | Flash Lite |
| MiniMax M2.7 | 22.8 | $0.0242 | dominated | Flash, Flash Lite | — |
| hy3 | 22.7 | $0.0127 | frontier | Flash, Flash Lite | Flash Lite |
| Gemini 3.5 Flash Lite | 22.2 | $0.1376 | dominated | Flash, Flash Lite | — |
| MiMo V2.5 | 21.8 | $0.0069 | frontier | Flash, Flash Lite | Flash Lite |
| Step 3.7 Flash | 19.5 | $0.0168 | dominated | Flash Lite | — |
| LongCat 2.0 | 19.1 | $0.0307 | dominated | Flash Lite | — |
| Step 3.5 Flash | 17 | $0.0073 | dominated | Flash Lite | — |
| Gemini 3.1 Flash Lite | 15.6 | $0.0394 | dominated | Flash Lite | — |
| Claude Haiku 4.5 | 15.4 | $0.0590 | dominated | Flash Lite | — |

## Ultra  ->  `ultra-tier`

_lambda 1.0, floor 46.08, top-K 5 — 14 eligible models; 0 backup fill(s)._

Ranked by NMB — frontier (primary) candidates first, then dominated (backup) candidates. Rows past the top-K are **cut**.

| # | Model | Provider(s) | Intel | Cost/task | NMB | Pareto | Result |
|--:|-------|-------------|------:|----------:|----:|--------|--------|
| 1 | Claude Opus 5.5 | commandcode | 57.6 | $3.5068 | 54.09 | frontier | primary · order 1 |
| 2 | Claude Sonnet 5.5 | commandcode | 56 | $3.2013 | 52.80 | frontier | primary · order 2 |
| 3 | Gemini 4 Argon | commandcode | 52.6 | $1.1668 | 51.43 | frontier | primary · order 3 |
| 4 | GPT-6.1 Sol | commandcode | 51.8 | $0.4245 | 51.38 | frontier | primary · order 4 |
| 5 | GPT-6 Astra | commandcode | 52.7 | $1.9806 | 50.72 | frontier | primary · order 5 |
| — | MiMo V2.6 Pro | commandcode | 46.3 | $0.0469 | 46.25 | frontier | cut |
| — | mimo-v2.6-pro | opencode | 46.3 | $0.0469 | 46.25 | frontier | cut |
| — | MiMo V2.6 Pro UltraSpeed | commandcode | 46.3 | $0.4690 | 45.83 | frontier | cut |
| — | Muse Wonder | commandcode | 52.4 | $2.6472 | 49.75 | dominated | cut |
| — | Claude Fable 5.1 | commandcode | 53.4 | $4.3896 | 49.01 | dominated | cut |
| — | Muse Spark 1.3 | commandcode | 48.1 | $0.8568 | 47.24 | dominated | cut |
| — | Claude Opus 5 | commandcode | 50.8 | $3.5619 | 47.24 | dominated | cut |
| — | GPT-6 Sol | commandcode | 47.6 | $0.6352 | 46.96 | dominated | cut |
| — | GPT-5.6 Sol | commandcode | 47 | $1.7874 | 45.21 | dominated | cut |
| — | Claude Fable 5 | commandcode | 49.6 | $5.3176 | 44.28 | dominated | cut |
| — | Grok 4.7 | commandcode | 46.4 | $2.1682 | 44.23 | dominated | cut |

## Pro  ->  `pro-tier`

_lambda 0.2, floor 34.56, top-K 5 — 40 eligible models; 0 backup fill(s)._

Ranked by NMB — frontier (primary) candidates first, then dominated (backup) candidates. Rows past the top-K are **cut**.

| # | Model | Provider(s) | Intel | Cost/task | NMB | Pareto | Result |
|--:|-------|-------------|------:|----------:|----:|--------|--------|
| 1 | GPT-6.1 Sol | commandcode | 51.8 | $0.4245 | 9.94 | frontier | primary · order 1 |
| 2 | Gemini 4 Argon | commandcode | 52.6 | $1.1668 | 9.35 | frontier | primary · order 2 |
| 3 | MiMo V2.6 Pro | commandcode | 46.3 | $0.0469 | 9.21 | frontier | primary · order 3 |
| 4 | mimo-v2.6-pro | opencode | 46.3 | $0.0469 | 9.21 | frontier | primary · order 4 |
| 5 | MiMo V2.6 Pro UltraSpeed | commandcode | 46.3 | $0.4690 | 8.79 | frontier | primary · order 5 |
| — | GPT-6 Astra | commandcode | 52.7 | $1.9806 | 8.56 | frontier | cut |
| — | Claude Opus 5.5 | commandcode | 57.6 | $3.5068 | 8.01 | frontier | cut |
| — | Claude Sonnet 5.5 | commandcode | 56 | $3.2013 | 8.00 | frontier | cut |
| — | GPT-6 Luna | commandcode | 38.1 | $0.0412 | 7.58 | frontier | cut |
| — | MiMo V2.6 Flash | commandcode, opencode | 37.9 | $0.0224 | 7.56 | frontier | cut |
| — | GPT-6 Sol | commandcode | 47.6 | $0.6352 | 8.88 | dominated | cut |
| — | Muse Spark 1.3 | commandcode | 48.1 | $0.8568 | 8.76 | dominated | cut |
| — | Claude Haiku 5.5 | commandcode | 43.4 | $0.1294 | 8.55 | dominated | cut |
| — | claude-haiku-5-5 | opencode | 43.4 | $0.3881 | 8.29 | dominated | cut |
| — | Step 5 Preview | commandcode | 43.7 | $0.4559 | 8.28 | dominated | cut |
| — | step-5-preview | opencode | 43.7 | $0.4859 | 8.25 | dominated | cut |
| — | GLM-5.3 Flash | commandcode, opencode | 41.8 | $0.1623 | 8.20 | dominated | cut |
| — | Grok 4.6 | commandcode | 44.3 | $0.8612 | 8.00 | dominated | cut |
| — | GLM-5.3 FlashX | commandcode | 41.8 | $0.4057 | 7.95 | dominated | cut |
| — | GLM-5.3 | commandcode, opencode | 44.8 | $1.1093 | 7.85 | dominated | cut |
| — | Claude Opus 4.7 | commandcode | 40.7 | $0.2950 | 7.85 | dominated | cut |
| — | Muse Wonder | commandcode | 52.4 | $2.6472 | 7.83 | dominated | cut |
| — | DeepSeek V4.1 Flash | commandcode | 39.5 | $0.0689 | 7.83 | dominated | cut |
| — | DeepSeek V4.1 Flash Fast | commandcode | 39.5 | $0.0724 | 7.83 | dominated | cut |
| — | deepseek-v4.1-flash | opencode | 39.5 | $0.1068 | 7.79 | dominated | cut |
| — | qwen3.8-flash | opencode | 39.8 | $0.1895 | 7.77 | dominated | cut |
| — | Qwen 3.8 Flash | commandcode | 39.8 | $0.1898 | 7.77 | dominated | cut |
| — | Ling 3.1 Flash | commandcode | 41.1 | $0.5518 | 7.67 | dominated | cut |
| — | GPT-5.4 | commandcode | 39 | $0.1500 | 7.65 | dominated | cut |
| — | GPT-5.6 Sol | commandcode | 47 | $1.7874 | 7.61 | dominated | cut |
| — | GPT-5.6 Terra | commandcode | 42.1 | $0.9052 | 7.51 | dominated | cut |
| — | Kimi K3 | commandcode, opencode | 43.6 | $1.2161 | 7.50 | dominated | cut |
| — | Muse Spark 1.2 | commandcode | 39.6 | $0.5203 | 7.40 | dominated | cut |
| — | GPT-5.6 Luna | commandcode | 37.3 | $0.1154 | 7.34 | dominated | cut |
| — | Grok 4.5 | commandcode | 38.8 | $0.5108 | 7.25 | dominated | cut |
| — | Grok 4.7 | commandcode | 46.4 | $2.1682 | 7.11 | dominated | cut |
| — | Mistral Large 4 | commandcode | 38.4 | $0.5703 | 7.11 | dominated | cut |
| — | DeepSeek V4 Pro (latest) | commandcode | 36 | $0.1546 | 7.05 | dominated | cut |
| — | deepseek-v4-pro | opencode | 36 | $0.2396 | 6.96 | dominated | cut |
| — | DeepSeek V4 Flash Vision (exp) | commandcode | 34.8 | $0.0637 | 6.90 | dominated | cut |
| — | Gemini 3.7 Flash | commandcode | 39.1 | $1.1252 | 6.69 | dominated | cut |
| — | Gemini 3.8 Flash | commandcode | 40.9 | $1.5112 | 6.67 | dominated | cut |
| — | Claude Opus 5 | commandcode | 50.8 | $3.5619 | 6.60 | dominated | cut |
| — | Qwen 3.8 Max 0902 | commandcode, opencode | 45.4 | $2.7583 | 6.32 | dominated | cut |
| — | Claude Fable 5.1 | commandcode | 53.4 | $4.3896 | 6.29 | dominated | cut |
| — | GPT-5.5 | commandcode | 38.4 | $1.7047 | 5.98 | dominated | cut |
| — | Claude Opus 4.8 | commandcode | 41.8 | $2.4812 | 5.88 | dominated | cut |
| — | Claude Fable 5 | commandcode | 49.6 | $5.3176 | 4.60 | dominated | cut |
| — | Claude Sonnet 5 | commandcode | 38.2 | $3.0954 | 4.54 | dominated | cut |
| — | Qwen 3.8 Max Prime | commandcode | 45.4 | $5.5167 | 3.56 | dominated | cut |

## Flash  ->  `flash-tier`

_lambda 0.005, floor 20.16, top-K 5 — 70 eligible models; 0 backup fill(s)._

Ranked by NMB — frontier (primary) candidates first, then dominated (backup) candidates. Rows past the top-K are **cut**.

| # | Model | Provider(s) | Intel | Cost/task | NMB | Pareto | Result |
|--:|-------|-------------|------:|----------:|----:|--------|--------|
| 1 | MiMo V2.6 Pro | commandcode | 46.3 | $0.0469 | 0.18 | frontier | primary · order 1 |
| 2 | mimo-v2.6-pro | opencode | 46.3 | $0.0469 | 0.18 | frontier | primary · order 2 |
| 3 | MiMo V2.6 Flash | commandcode, opencode | 37.9 | $0.0224 | 0.17 | frontier | primary · order 3 |
| 4 | GPT-6 Luna | commandcode | 38.1 | $0.0412 | 0.15 | frontier | primary · order 4 |
| 5 | MiMo V2.5 Pro | commandcode | 26 | $0.0190 | 0.11 | frontier | primary · order 5 |
| — | mimo-v2.5-pro | opencode | 26 | $0.0190 | 0.11 | frontier | cut |
| — | MiMo V2.5 | commandcode, opencode | 21.8 | $0.0069 | 0.10 | frontier | cut |
| — | hy3 | opencode | 22.7 | $0.0127 | 0.10 | frontier | cut |
| — | MiniMax M2.5 | commandcode | 22.8 | $0.0167 | 0.10 | frontier | cut |
| — | GPT-6.1 Sol | commandcode | 51.8 | $0.4245 | -0.17 | frontier | cut |
| — | MiMo V2.6 Pro UltraSpeed | commandcode | 46.3 | $0.4690 | -0.24 | frontier | cut |
| — | Gemini 4 Argon | commandcode | 52.6 | $1.1668 | -0.90 | frontier | cut |
| — | GPT-6 Astra | commandcode | 52.7 | $1.9806 | -1.72 | frontier | cut |
| — | Claude Sonnet 5.5 | commandcode | 56 | $3.2013 | -2.92 | frontier | cut |
| — | Claude Opus 5.5 | commandcode | 57.6 | $3.5068 | -3.22 | frontier | cut |
| — | DeepSeek V4.1 Flash | commandcode | 39.5 | $0.0689 | 0.13 | dominated | cut |
| — | DeepSeek V4 Flash (latest) | commandcode | 34.3 | $0.0445 | 0.13 | dominated | cut |
| — | DeepSeek V4.1 Flash Fast | commandcode | 39.5 | $0.0724 | 0.13 | dominated | cut |
| — | DeepSeek V4 Flash Fast | commandcode | 34.3 | $0.0611 | 0.11 | dominated | cut |
| — | DeepSeek V4 Flash Vision (exp) | commandcode | 34.8 | $0.0637 | 0.11 | dominated | cut |
| — | Qwen 3.6 Plus | commandcode | 27 | $0.0425 | 0.09 | dominated | cut |
| — | deepseek-v4.1-flash | opencode | 39.5 | $0.1068 | 0.09 | dominated | cut |
| — | MiniMax M2.7 | commandcode, opencode | 22.8 | $0.0242 | 0.09 | dominated | cut |
| — | Claude Haiku 5.5 | commandcode | 43.4 | $0.1294 | 0.09 | dominated | cut |
| — | Muse Spark Open | commandcode | 31.3 | $0.0699 | 0.09 | dominated | cut |
| — | Tencent Hy3 | commandcode | 25.3 | $0.0476 | 0.08 | dominated | cut |
| — | Kimi K2.5 | commandcode | 23.5 | $0.0439 | 0.07 | dominated | cut |
| — | GPT-5.6 Luna | commandcode | 37.3 | $0.1154 | 0.07 | dominated | cut |
| — | Inkling Small | commandcode | 25.7 | $0.0609 | 0.07 | dominated | cut |
| — | GLM-5 | commandcode | 27.9 | $0.0752 | 0.06 | dominated | cut |
| — | Inkling | commandcode | 25 | $0.0707 | 0.05 | dominated | cut |
| — | GLM-5.3 Flash | commandcode, opencode | 41.8 | $0.1623 | 0.05 | dominated | cut |
| — | GPT-5.4 | commandcode | 39 | $0.1500 | 0.05 | dominated | cut |
| — | Qwen 3.6 Max Preview | commandcode | 28.4 | $0.1138 | 0.03 | dominated | cut |
| — | DeepSeek V4 Pro (latest) | commandcode | 36 | $0.1546 | 0.03 | dominated | cut |
| — | qwen3.8-flash | opencode | 39.8 | $0.1895 | 0.01 | dominated | cut |
| — | Qwen 3.8 Flash | commandcode | 39.8 | $0.1898 | 0.01 | dominated | cut |
| — | Qwen 3.7 Plus | commandcode | 25.2 | $0.1319 | -0.01 | dominated | cut |
| — | GPT-5.3 Codex | commandcode | 32.5 | $0.1810 | -0.02 | dominated | cut |
| — | Gemini 3.5 Flash Lite | commandcode | 22.2 | $0.1376 | -0.03 | dominated | cut |
| — | Claude Sonnet 4.6 | commandcode | 24.7 | $0.1770 | -0.05 | dominated | cut |
| — | deepseek-v4-pro | opencode | 36 | $0.2396 | -0.06 | dominated | cut |
| — | Claude Opus 4.7 | commandcode | 40.7 | $0.2950 | -0.09 | dominated | cut |
| — | qwen3.7-plus | opencode | 25.2 | $0.2426 | -0.12 | dominated | cut |
| — | MiniMax M3 | commandcode, opencode | 29.2 | $0.3086 | -0.16 | dominated | cut |
| — | GPT-5.4 Mini | commandcode | 24.1 | $0.2896 | -0.17 | dominated | cut |
| — | claude-haiku-5-5 | opencode | 43.4 | $0.3881 | -0.17 | dominated | cut |
| — | GLM-5.3 FlashX | commandcode | 41.8 | $0.4057 | -0.20 | dominated | cut |
| — | Kimi K2.7 Code | commandcode, opencode | 25.8 | $0.3345 | -0.21 | dominated | cut |
| — | Step 5 Preview | commandcode | 43.7 | $0.4559 | -0.24 | dominated | cut |
| — | Nemotron 3 Ultra | commandcode | 22.9 | $0.3559 | -0.24 | dominated | cut |
| — | step-5-preview | opencode | 43.7 | $0.4859 | -0.27 | dominated | cut |
| — | Grok 4.5 | commandcode | 38.8 | $0.5108 | -0.32 | dominated | cut |
| — | Muse Spark 1.2 | commandcode | 39.6 | $0.5203 | -0.32 | dominated | cut |
| — | Ling 3.1 Flash | commandcode | 41.1 | $0.5518 | -0.35 | dominated | cut |
| — | Kimi K2.6 | commandcode, opencode | 27 | $0.4823 | -0.35 | dominated | cut |
| — | Mistral Large 4 | commandcode | 38.4 | $0.5703 | -0.38 | dominated | cut |
| — | GPT-6 Sol | commandcode | 47.6 | $0.6352 | -0.40 | dominated | cut |
| — | Qwen 3.8 27B | commandcode | 33.7 | $0.6425 | -0.47 | dominated | cut |
| — | GLM-5.1 | commandcode | 26.1 | $0.6122 | -0.48 | dominated | cut |
| — | Qwen 3.7 Max | commandcode | 29.5 | $0.6333 | -0.49 | dominated | cut |
| — | Kimi K2.7 Code HighSpeed | commandcode | 25.8 | $0.6690 | -0.54 | dominated | cut |
| — | Muse Spark 1.1 | commandcode | 33.7 | $0.7368 | -0.57 | dominated | cut |
| — | Muse Spark 1.3 | commandcode | 48.1 | $0.8568 | -0.62 | dominated | cut |
| — | Grok 4.6 | commandcode | 44.3 | $0.8612 | -0.64 | dominated | cut |
| — | GLM-5.2 | commandcode, opencode | 33.7 | $0.8145 | -0.65 | dominated | cut |
| — | GPT-5.6 Terra | commandcode | 42.1 | $0.9052 | -0.69 | dominated | cut |
| — | GLM-5.3 | commandcode, opencode | 44.8 | $1.1093 | -0.89 | dominated | cut |
| — | Gemini 3.7 Flash | commandcode | 39.1 | $1.1252 | -0.93 | dominated | cut |
| — | Kimi K3 | commandcode, opencode | 43.6 | $1.2161 | -1.00 | dominated | cut |
| — | Gemini 3.8 Flash | commandcode | 40.9 | $1.5112 | -1.31 | dominated | cut |
| — | GPT-5.5 | commandcode | 38.4 | $1.7047 | -1.51 | dominated | cut |
| — | GPT-5.6 Sol | commandcode | 47 | $1.7874 | -1.55 | dominated | cut |
| — | GLM-5.2 Fast | commandcode | 33.7 | $1.8334 | -1.66 | dominated | cut |
| — | Gemini 3.6 Flash | commandcode | 34 | $1.9462 | -1.78 | dominated | cut |
| — | Grok 4.7 | commandcode | 46.4 | $2.1682 | -1.94 | dominated | cut |
| — | Gemini 3.5 Flash | commandcode | 32.6 | $2.3906 | -2.23 | dominated | cut |
| — | Claude Opus 4.8 | commandcode | 41.8 | $2.4812 | -2.27 | dominated | cut |
| — | Muse Wonder | commandcode | 52.4 | $2.6472 | -2.39 | dominated | cut |
| — | Qwen 3.8 Max 0902 | commandcode, opencode | 45.4 | $2.7583 | -2.53 | dominated | cut |
| — | Claude Sonnet 5 | commandcode | 38.2 | $3.0954 | -2.90 | dominated | cut |
| — | Claude Opus 5 | commandcode | 50.8 | $3.5619 | -3.31 | dominated | cut |
| — | Claude Fable 5.1 | commandcode | 53.4 | $4.3896 | -4.12 | dominated | cut |
| — | Claude Fable 5 | commandcode | 49.6 | $5.3176 | -5.07 | dominated | cut |
| — | Qwen 3.8 Max Prime | commandcode | 45.4 | $5.5167 | -5.29 | dominated | cut |

## Flash Lite  ->  `flash-lite-tier`

_lambda 0.0005, floor 0.00, top-K 5 — 75 eligible models; 0 backup fill(s)._

Ranked by NMB — frontier (primary) candidates first, then dominated (backup) candidates. Rows past the top-K are **cut**.

| # | Model | Provider(s) | Intel | Cost/task | NMB | Pareto | Result |
|--:|-------|-------------|------:|----------:|----:|--------|--------|
| 1 | MiMo V2.5 | commandcode, opencode | 21.8 | $0.0069 | 0.00 | frontier | primary · order 1 |
| 2 | hy3 | opencode | 22.7 | $0.0127 | -0.00 | frontier | primary · order 2 |
| 3 | MiMo V2.6 Flash | commandcode, opencode | 37.9 | $0.0224 | -0.00 | frontier | primary · order 3 |
| 4 | MiniMax M2.5 | commandcode | 22.8 | $0.0167 | -0.01 | frontier | primary · order 4 |
| 5 | MiMo V2.5 Pro | commandcode | 26 | $0.0190 | -0.01 | frontier | primary · order 5 |
| — | mimo-v2.5-pro | opencode | 26 | $0.0190 | -0.01 | frontier | cut |
| — | GPT-6 Luna | commandcode | 38.1 | $0.0412 | -0.02 | frontier | cut |
| — | MiMo V2.6 Pro | commandcode | 46.3 | $0.0469 | -0.02 | frontier | cut |
| — | mimo-v2.6-pro | opencode | 46.3 | $0.0469 | -0.02 | frontier | cut |
| — | GPT-6.1 Sol | commandcode | 51.8 | $0.4245 | -0.40 | frontier | cut |
| — | MiMo V2.6 Pro UltraSpeed | commandcode | 46.3 | $0.4690 | -0.45 | frontier | cut |
| — | Gemini 4 Argon | commandcode | 52.6 | $1.1668 | -1.14 | frontier | cut |
| — | GPT-6 Astra | commandcode | 52.7 | $1.9806 | -1.95 | frontier | cut |
| — | Claude Sonnet 5.5 | commandcode | 56 | $3.2013 | -3.17 | frontier | cut |
| — | Claude Opus 5.5 | commandcode | 57.6 | $3.5068 | -3.48 | frontier | cut |
| — | Step 3.5 Flash | commandcode | 17 | $0.0073 | 0.00 | dominated | cut |
| — | Step 3.7 Flash | commandcode | 19.5 | $0.0168 | -0.01 | dominated | cut |
| — | MiniMax M2.7 | commandcode, opencode | 22.8 | $0.0242 | -0.01 | dominated | cut |
| — | LongCat 2.0 | commandcode, opencode | 19.1 | $0.0307 | -0.02 | dominated | cut |
| — | DeepSeek V4 Flash (latest) | commandcode | 34.3 | $0.0445 | -0.03 | dominated | cut |
| — | Qwen 3.6 Plus | commandcode | 27 | $0.0425 | -0.03 | dominated | cut |
| — | Gemini 3.1 Flash Lite | commandcode | 15.6 | $0.0394 | -0.03 | dominated | cut |
| — | Kimi K2.5 | commandcode | 23.5 | $0.0439 | -0.03 | dominated | cut |
| — | Tencent Hy3 | commandcode | 25.3 | $0.0476 | -0.03 | dominated | cut |
| — | DeepSeek V4 Flash Fast | commandcode | 34.3 | $0.0611 | -0.04 | dominated | cut |
| — | DeepSeek V4 Flash Vision (exp) | commandcode | 34.8 | $0.0637 | -0.05 | dominated | cut |
| — | Inkling Small | commandcode | 25.7 | $0.0609 | -0.05 | dominated | cut |
| — | DeepSeek V4.1 Flash | commandcode | 39.5 | $0.0689 | -0.05 | dominated | cut |
| — | Claude Haiku 4.5 | commandcode | 15.4 | $0.0590 | -0.05 | dominated | cut |
| — | DeepSeek V4.1 Flash Fast | commandcode | 39.5 | $0.0724 | -0.05 | dominated | cut |
| — | Muse Spark Open | commandcode | 31.3 | $0.0699 | -0.05 | dominated | cut |
| — | Inkling | commandcode | 25 | $0.0707 | -0.06 | dominated | cut |
| — | GLM-5 | commandcode | 27.9 | $0.0752 | -0.06 | dominated | cut |
| — | deepseek-v4.1-flash | opencode | 39.5 | $0.1068 | -0.09 | dominated | cut |
| — | GPT-5.6 Luna | commandcode | 37.3 | $0.1154 | -0.10 | dominated | cut |
| — | Qwen 3.6 Max Preview | commandcode | 28.4 | $0.1138 | -0.10 | dominated | cut |
| — | Claude Haiku 5.5 | commandcode | 43.4 | $0.1294 | -0.11 | dominated | cut |
| — | Qwen 3.7 Plus | commandcode | 25.2 | $0.1319 | -0.12 | dominated | cut |
| — | Gemini 3.5 Flash Lite | commandcode | 22.2 | $0.1376 | -0.13 | dominated | cut |
| — | GPT-5.4 | commandcode | 39 | $0.1500 | -0.13 | dominated | cut |
| — | DeepSeek V4 Pro (latest) | commandcode | 36 | $0.1546 | -0.14 | dominated | cut |
| — | GLM-5.3 Flash | commandcode, opencode | 41.8 | $0.1623 | -0.14 | dominated | cut |
| — | Claude Sonnet 4.6 | commandcode | 24.7 | $0.1770 | -0.16 | dominated | cut |
| — | GPT-5.3 Codex | commandcode | 32.5 | $0.1810 | -0.16 | dominated | cut |
| — | qwen3.8-flash | opencode | 39.8 | $0.1895 | -0.17 | dominated | cut |
| — | Qwen 3.8 Flash | commandcode | 39.8 | $0.1898 | -0.17 | dominated | cut |
| — | deepseek-v4-pro | opencode | 36 | $0.2396 | -0.22 | dominated | cut |
| — | qwen3.7-plus | opencode | 25.2 | $0.2426 | -0.23 | dominated | cut |
| — | Claude Opus 4.7 | commandcode | 40.7 | $0.2950 | -0.27 | dominated | cut |
| — | GPT-5.4 Mini | commandcode | 24.1 | $0.2896 | -0.28 | dominated | cut |
| — | MiniMax M3 | commandcode, opencode | 29.2 | $0.3086 | -0.29 | dominated | cut |
| — | Kimi K2.7 Code | commandcode, opencode | 25.8 | $0.3345 | -0.32 | dominated | cut |
| — | Nemotron 3 Ultra | commandcode | 22.9 | $0.3559 | -0.34 | dominated | cut |
| — | claude-haiku-5-5 | opencode | 43.4 | $0.3881 | -0.37 | dominated | cut |
| — | GLM-5.3 FlashX | commandcode | 41.8 | $0.4057 | -0.38 | dominated | cut |
| — | Step 5 Preview | commandcode | 43.7 | $0.4559 | -0.43 | dominated | cut |
| — | step-5-preview | opencode | 43.7 | $0.4859 | -0.46 | dominated | cut |
| — | Kimi K2.6 | commandcode, opencode | 27 | $0.4823 | -0.47 | dominated | cut |
| — | Grok 4.5 | commandcode | 38.8 | $0.5108 | -0.49 | dominated | cut |
| — | Muse Spark 1.2 | commandcode | 39.6 | $0.5203 | -0.50 | dominated | cut |
| — | Ling 3.1 Flash | commandcode | 41.1 | $0.5518 | -0.53 | dominated | cut |
| — | Mistral Large 4 | commandcode | 38.4 | $0.5703 | -0.55 | dominated | cut |
| — | GLM-5.1 | commandcode | 26.1 | $0.6122 | -0.60 | dominated | cut |
| — | GPT-6 Sol | commandcode | 47.6 | $0.6352 | -0.61 | dominated | cut |
| — | Qwen 3.7 Max | commandcode | 29.5 | $0.6333 | -0.62 | dominated | cut |
| — | Qwen 3.8 27B | commandcode | 33.7 | $0.6425 | -0.63 | dominated | cut |
| — | Kimi K2.7 Code HighSpeed | commandcode | 25.8 | $0.6690 | -0.66 | dominated | cut |
| — | Muse Spark 1.1 | commandcode | 33.7 | $0.7368 | -0.72 | dominated | cut |
| — | GLM-5.2 | commandcode, opencode | 33.7 | $0.8145 | -0.80 | dominated | cut |
| — | Muse Spark 1.3 | commandcode | 48.1 | $0.8568 | -0.83 | dominated | cut |
| — | Grok 4.6 | commandcode | 44.3 | $0.8612 | -0.84 | dominated | cut |
| — | GPT-5.6 Terra | commandcode | 42.1 | $0.9052 | -0.88 | dominated | cut |
| — | GLM-5.3 | commandcode, opencode | 44.8 | $1.1093 | -1.09 | dominated | cut |
| — | Gemini 3.7 Flash | commandcode | 39.1 | $1.1252 | -1.11 | dominated | cut |
| — | Kimi K3 | commandcode, opencode | 43.6 | $1.2161 | -1.19 | dominated | cut |
| — | Gemini 3.8 Flash | commandcode | 40.9 | $1.5112 | -1.49 | dominated | cut |
| — | GPT-5.5 | commandcode | 38.4 | $1.7047 | -1.69 | dominated | cut |
| — | GPT-5.6 Sol | commandcode | 47 | $1.7874 | -1.76 | dominated | cut |
| — | GLM-5.2 Fast | commandcode | 33.7 | $1.8334 | -1.82 | dominated | cut |
| — | Gemini 3.6 Flash | commandcode | 34 | $1.9462 | -1.93 | dominated | cut |
| — | Grok 4.7 | commandcode | 46.4 | $2.1682 | -2.15 | dominated | cut |
| — | Gemini 3.5 Flash | commandcode | 32.6 | $2.3906 | -2.37 | dominated | cut |
| — | Claude Opus 4.8 | commandcode | 41.8 | $2.4812 | -2.46 | dominated | cut |
| — | Muse Wonder | commandcode | 52.4 | $2.6472 | -2.62 | dominated | cut |
| — | Qwen 3.8 Max 0902 | commandcode, opencode | 45.4 | $2.7583 | -2.74 | dominated | cut |
| — | Claude Sonnet 5 | commandcode | 38.2 | $3.0954 | -3.08 | dominated | cut |
| — | Claude Opus 5 | commandcode | 50.8 | $3.5619 | -3.54 | dominated | cut |
| — | Claude Fable 5.1 | commandcode | 53.4 | $4.3896 | -4.36 | dominated | cut |
| — | Claude Fable 5 | commandcode | 49.6 | $5.3176 | -5.29 | dominated | cut |
| — | Qwen 3.8 Max Prime | commandcode | 45.4 | $5.5167 | -5.49 | dominated | cut |

## Pareto frontier

**12** efficient models on the frontier; **63** dominated (another model is both smarter and cheaper).

Dominated models — and a model that beats them on both axes:

| Model | Intel | Cost/task | Beaten by | Its intel | Its cost |
|-------|------:|----------:|-----------|----------:|---------:|
| Claude Fable 5.1 | 53.4 | $4.3896 | Claude Opus 5.5 | 57.6 | $3.5068 |
| Muse Wonder | 52.4 | $2.6472 | GPT-6 Astra | 52.7 | $1.9806 |
| Claude Opus 5 | 50.8 | $3.5619 | Claude Opus 5.5 | 57.6 | $3.5068 |
| Claude Fable 5 | 49.6 | $5.3176 | Claude Opus 5.5 | 57.6 | $3.5068 |
| Muse Spark 1.3 | 48.1 | $0.8568 | GPT-6.1 Sol | 51.8 | $0.4245 |
| GPT-6 Sol | 47.6 | $0.6352 | GPT-6.1 Sol | 51.8 | $0.4245 |
| GPT-5.6 Sol | 47 | $1.7874 | Gemini 4 Argon | 52.6 | $1.1668 |
| Grok 4.7 | 46.4 | $2.1682 | GPT-6 Astra | 52.7 | $1.9806 |
| Qwen 3.8 Max 0902 | 45.4 | $2.7583 | GPT-6 Astra | 52.7 | $1.9806 |
| GLM-5.3 | 44.8 | $1.1093 | GPT-6.1 Sol | 51.8 | $0.4245 |
| Grok 4.6 | 44.3 | $0.8612 | GPT-6.1 Sol | 51.8 | $0.4245 |
| Step 5 Preview | 43.7 | $0.4559 | GPT-6.1 Sol | 51.8 | $0.4245 |
| Kimi K3 | 43.6 | $1.2161 | Gemini 4 Argon | 52.6 | $1.1668 |
| Claude Haiku 5.5 | 43.4 | $0.1294 | MiMo V2.6 Pro | 46.3 | $0.0469 |
| GPT-5.6 Terra | 42.1 | $0.9052 | GPT-6.1 Sol | 51.8 | $0.4245 |
| Claude Opus 4.8 | 41.8 | $2.4812 | GPT-6 Astra | 52.7 | $1.9806 |
| GLM-5.3 Flash | 41.8 | $0.1623 | MiMo V2.6 Pro | 46.3 | $0.0469 |
| Ling 3.1 Flash | 41.1 | $0.5518 | GPT-6.1 Sol | 51.8 | $0.4245 |
| Gemini 3.8 Flash | 40.9 | $1.5112 | Gemini 4 Argon | 52.6 | $1.1668 |
| Claude Opus 4.7 | 40.7 | $0.2950 | MiMo V2.6 Pro | 46.3 | $0.0469 |
| qwen3.8-flash | 39.8 | $0.1895 | MiMo V2.6 Pro | 46.3 | $0.0469 |
| Muse Spark 1.2 | 39.6 | $0.5203 | GPT-6.1 Sol | 51.8 | $0.4245 |
| DeepSeek V4.1 Flash | 39.5 | $0.0689 | MiMo V2.6 Pro | 46.3 | $0.0469 |
| Gemini 3.7 Flash | 39.1 | $1.1252 | GPT-6.1 Sol | 51.8 | $0.4245 |
| GPT-5.4 | 39 | $0.1500 | MiMo V2.6 Pro | 46.3 | $0.0469 |
| Grok 4.5 | 38.8 | $0.5108 | GPT-6.1 Sol | 51.8 | $0.4245 |
| GPT-5.5 | 38.4 | $1.7047 | Gemini 4 Argon | 52.6 | $1.1668 |
| Mistral Large 4 | 38.4 | $0.5703 | GPT-6.1 Sol | 51.8 | $0.4245 |
| Claude Sonnet 5 | 38.2 | $3.0954 | GPT-6 Astra | 52.7 | $1.9806 |
| GPT-5.6 Luna | 37.3 | $0.1154 | MiMo V2.6 Pro | 46.3 | $0.0469 |
| DeepSeek V4 Pro (latest) | 36 | $0.1546 | MiMo V2.6 Pro | 46.3 | $0.0469 |
| DeepSeek V4 Flash Vision (exp) | 34.8 | $0.0637 | MiMo V2.6 Pro | 46.3 | $0.0469 |
| DeepSeek V4 Flash (latest) | 34.3 | $0.0445 | GPT-6 Luna | 38.1 | $0.0412 |
| Gemini 3.6 Flash | 34 | $1.9462 | Gemini 4 Argon | 52.6 | $1.1668 |
| GLM-5.2 | 33.7 | $0.8145 | GPT-6.1 Sol | 51.8 | $0.4245 |
| Qwen 3.8 27B | 33.7 | $0.6425 | GPT-6.1 Sol | 51.8 | $0.4245 |
| Muse Spark 1.1 | 33.7 | $0.7368 | GPT-6.1 Sol | 51.8 | $0.4245 |
| Gemini 3.5 Flash | 32.6 | $2.3906 | GPT-6 Astra | 52.7 | $1.9806 |
| GPT-5.3 Codex | 32.5 | $0.1810 | MiMo V2.6 Pro | 46.3 | $0.0469 |
| Muse Spark Open | 31.3 | $0.0699 | MiMo V2.6 Pro | 46.3 | $0.0469 |
| Qwen 3.7 Max | 29.5 | $0.6333 | GPT-6.1 Sol | 51.8 | $0.4245 |
| MiniMax M3 | 29.2 | $0.3086 | MiMo V2.6 Pro | 46.3 | $0.0469 |
| Qwen 3.6 Max Preview | 28.4 | $0.1138 | MiMo V2.6 Pro | 46.3 | $0.0469 |
| GLM-5 | 27.9 | $0.0752 | MiMo V2.6 Pro | 46.3 | $0.0469 |
| Kimi K2.6 | 27 | $0.4823 | GPT-6.1 Sol | 51.8 | $0.4245 |
| Qwen 3.6 Plus | 27 | $0.0425 | GPT-6 Luna | 38.1 | $0.0412 |
| GLM-5.1 | 26.1 | $0.6122 | GPT-6.1 Sol | 51.8 | $0.4245 |
| Kimi K2.7 Code | 25.8 | $0.3345 | MiMo V2.6 Pro | 46.3 | $0.0469 |
| Inkling Small | 25.7 | $0.0609 | MiMo V2.6 Pro | 46.3 | $0.0469 |
| Tencent Hy3 | 25.3 | $0.0476 | MiMo V2.6 Pro | 46.3 | $0.0469 |
| Qwen 3.7 Plus | 25.2 | $0.1319 | MiMo V2.6 Pro | 46.3 | $0.0469 |
| Inkling | 25 | $0.0707 | MiMo V2.6 Pro | 46.3 | $0.0469 |
| Claude Sonnet 4.6 | 24.7 | $0.1770 | MiMo V2.6 Pro | 46.3 | $0.0469 |
| GPT-5.4 Mini | 24.1 | $0.2896 | MiMo V2.6 Pro | 46.3 | $0.0469 |
| Kimi K2.5 | 23.5 | $0.0439 | GPT-6 Luna | 38.1 | $0.0412 |
| Nemotron 3 Ultra | 22.9 | $0.3559 | MiMo V2.6 Pro | 46.3 | $0.0469 |
| MiniMax M2.7 | 22.8 | $0.0242 | MiMo V2.6 Flash | 37.9 | $0.0224 |
| Gemini 3.5 Flash Lite | 22.2 | $0.1376 | MiMo V2.6 Pro | 46.3 | $0.0469 |
| Step 3.7 Flash | 19.5 | $0.0168 | MiniMax M2.5 | 22.8 | $0.0166 |
| LongCat 2.0 | 19.1 | $0.0307 | MiMo V2.6 Flash | 37.9 | $0.0224 |
| Step 3.5 Flash | 17 | $0.0073 | MiMo V2.5 | 21.8 | $0.0069 |
| Gemini 3.1 Flash Lite | 15.6 | $0.0394 | MiMo V2.6 Flash | 37.9 | $0.0224 |
| Claude Haiku 4.5 | 15.4 | $0.0590 | MiMo V2.6 Pro | 46.3 | $0.0469 |

## Excluded (could not be scored)

**excluded_by_config** (3): commandcode:meta/muse-spark-1.2-contributor, commandcode:meta/muse-spark-1.3-contributor, opencode:gemini-4-argon-contributor

**unmapped** (12): commandcode:Qwen/Qwen3.8-Omni-Flash, commandcode:Qwen/Qwen3.7-Flash, commandcode:tencent/hy4-preview, commandcode:sakana/fugu-ultra, commandcode:nvidia/nemotron-3.5-super-vl, commandcode:stealth/glyph-cluster:free, commandcode:stealth/cat-jam:free, commandcode:poolside/laguna-s-2.1-free, opencode:hy4-preview, opencode:space-bunny, opencode:longcat-2.5-preview-free, opencode:cat-jam-free

