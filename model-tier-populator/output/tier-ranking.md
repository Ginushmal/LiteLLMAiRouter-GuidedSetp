# Model pipeline — ranking report

_Generated: 2026-10-20T07:57:34+00:00_

**SOTA intelligence:** 57.6

**NMB** = lambda * intelligence - cost_per_task - mu * latency   (mu = rho × tier NMB spread ÷ median latency — see the tier table)

A model is eligible for **every** tier whose floor it meets:

| Tier | Model group | Floor (x SOTA) | lambda | rho | mu | top-K |
|------|-------------|----------------|--------|-----|----|-------|
| Ultra | `ultra-tier` | 46.08 (0.80x) | 1.0 | 0.0 | 0 | 10 |
| Pro | `pro-tier` | 34.56 (0.60x) | 0.2 | 0.0 | 0 | 10 |
| Flash | `flash-tier` | 20.16 (0.35x) | 0.001 | 0.0 | 0 | 10 |
| Flash Lite | `flash-lite-tier` | 0.00 (0.00x) | 0.0001 | 0.0 | 0 | 10 |

## Model index

Every scored model, where it was eligible, and where it was selected.

| Model | Intel | Best cost/task | Pareto | Eligible tiers | Pinned in | Excluded in | Selected in |
|-------|------:|---------------:|--------|----------------|-----------|-------------|-------------|
| Claude Opus 5.5 | 57.6 | $3.5068 | frontier | Ultra, Pro, Flash, Flash Lite | — | — | Ultra, Pro |
| Claude Sonnet 5.5 | 56 | $3.2013 | frontier | Ultra, Pro, Flash, Flash Lite | — | — | Ultra, Pro |
| Claude Fable 5.1 | 53.4 | $4.3896 | dominated | Ultra, Pro, Flash, Flash Lite | — | — | Ultra |
| GPT-6 Astra | 52.7 | $1.9806 | frontier | Ultra, Pro, Flash, Flash Lite | — | — | Ultra, Pro, Flash Lite |
| Gemini 4 Argon | 52.6 | $1.1668 | frontier | Ultra, Pro, Flash, Flash Lite | — | — | Ultra, Pro, Flash, Flash Lite |
| Muse Wonder | 52.4 | $2.6472 | dominated | Ultra, Pro, Flash, Flash Lite | — | — | Ultra |
| GPT-6.1 Sol | 51.8 | $0.4245 | frontier | Ultra, Pro, Flash, Flash Lite | — | — | Ultra, Pro, Flash, Flash Lite |
| Claude Opus 5 | 50.8 | $3.5619 | dominated | Ultra, Pro, Flash, Flash Lite | — | — | — |
| Claude Fable 5 | 49.6 | $5.3176 | dominated | Ultra, Pro, Flash, Flash Lite | — | — | — |
| Muse Spark 1.3 | 48.1 | $0.8568 | dominated | Ultra, Pro, Flash, Flash Lite | — | — | Ultra |
| GPT-6 Sol | 47.6 | $0.6352 | dominated | Ultra, Pro, Flash, Flash Lite | — | — | Pro |
| GPT-5.6 Sol | 47 | $1.7874 | dominated | Ultra, Pro, Flash, Flash Lite | — | — | — |
| Grok 4.7 | 46.4 | $2.1682 | dominated | Ultra, Pro, Flash, Flash Lite | — | — | — |
| MiMo V2.6 Pro | 46.3 | $0.0469 | frontier | Ultra, Pro, Flash, Flash Lite | — | — | Ultra, Pro, Flash, Flash Lite |
| Qwen 3.8 Max 0902 | 45.4 | $2.7583 | dominated | Pro, Flash, Flash Lite | — | — | — |
| GLM-5.3 | 44.8 | $1.1093 | dominated | Pro, Flash, Flash Lite | — | — | — |
| Grok 4.6 | 44.3 | $0.8612 | dominated | Pro, Flash, Flash Lite | — | — | — |
| Step 5 Preview | 43.7 | $0.4559 | dominated | Pro, Flash, Flash Lite | — | — | — |
| Kimi K3 | 43.6 | $1.2161 | dominated | Pro, Flash, Flash Lite | — | — | — |
| Claude Haiku 5.5 | 43.4 | $0.1294 | dominated | Pro, Flash, Flash Lite | — | — | — |
| GPT-5.6 Terra | 42.1 | $0.9052 | dominated | Pro, Flash, Flash Lite | — | — | — |
| GLM-5.3 Flash | 41.8 | $0.1623 | dominated | Pro, Flash, Flash Lite | — | — | — |
| Claude Opus 4.8 | 41.8 | $2.4812 | dominated | Pro, Flash, Flash Lite | — | — | — |
| Ling 3.1 Flash | 41.1 | $0.5518 | dominated | Pro, Flash, Flash Lite | — | — | — |
| Gemini 3.8 Flash | 40.9 | $1.5112 | dominated | Pro, Flash, Flash Lite | — | — | — |
| Claude Opus 4.7 | 40.7 | $0.2950 | dominated | Pro, Flash, Flash Lite | — | — | — |
| Qwen 3.8 Flash | 39.8 | $0.1898 | dominated | Pro, Flash, Flash Lite | — | — | — |
| Muse Spark 1.2 | 39.6 | $0.5203 | dominated | Pro, Flash, Flash Lite | — | — | — |
| DeepSeek V4.1 Flash (latest) | 39.5 | $0.0689 | dominated | Pro, Flash Lite | Flash | Flash | — |
| Gemini 3.7 Flash | 39.1 | $1.1252 | dominated | Pro, Flash, Flash Lite | — | — | — |
| GPT-5.4 | 39 | $0.1500 | dominated | Pro, Flash, Flash Lite | — | — | — |
| Grok 4.5 | 38.8 | $0.5108 | dominated | Pro, Flash, Flash Lite | — | — | — |
| Mistral Large 4 | 38.4 | $0.5703 | dominated | Pro, Flash, Flash Lite | — | — | — |
| GPT-5.5 | 38.4 | $1.7047 | dominated | Pro, Flash, Flash Lite | — | — | — |
| Claude Sonnet 5 | 38.2 | $3.0954 | dominated | Pro, Flash, Flash Lite | — | — | — |
| GPT-6 Luna | 38.1 | $0.0412 | frontier | Pro, Flash, Flash Lite | — | — | Pro, Flash, Flash Lite |
| MiMo V2.6 Flash | 37.9 | $0.0224 | frontier | Pro, Flash, Flash Lite | — | — | Pro, Flash, Flash Lite |
| GPT-5.6 Luna | 37.3 | $0.1154 | dominated | Pro, Flash, Flash Lite | — | — | — |
| DeepSeek V4 Pro (latest) | 36 | $0.1546 | dominated | Pro, Flash, Flash Lite | — | — | — |
| DeepSeek V4 Flash Vision (exp) | 34.8 | $0.0637 | dominated | Pro, Flash, Flash Lite | — | — | — |
| DeepSeek V4 Flash (latest) | 34.3 | $0.0445 | dominated | Flash, Flash Lite | — | — | — |
| Gemini 3.6 Flash | 34 | $1.9462 | dominated | Flash, Flash Lite | — | — | — |
| Qwen 3.8 27B | 33.7 | $0.6425 | dominated | Flash, Flash Lite | — | — | — |
| Muse Spark 1.1 | 33.7 | $0.7368 | dominated | Flash, Flash Lite | — | — | — |
| GLM-5.2 | 33.7 | $0.8145 | dominated | Flash, Flash Lite | — | — | — |
| Gemini 3.5 Flash | 32.6 | $2.3906 | dominated | Flash, Flash Lite | — | — | — |
| GPT-5.3 Codex | 32.5 | $0.1810 | dominated | Flash, Flash Lite | — | — | — |
| Muse Spark Open | 31.3 | $0.0699 | dominated | Flash, Flash Lite | — | — | — |
| Qwen 3.7 Max | 29.5 | $0.6333 | dominated | Flash, Flash Lite | — | — | — |
| MiniMax M3 | 29.2 | $0.3086 | dominated | Flash, Flash Lite | — | — | — |
| Qwen 3.6 Max Preview | 28.4 | $0.1138 | dominated | Flash, Flash Lite | — | — | — |
| GLM-5 | 27.9 | $0.0752 | dominated | Flash, Flash Lite | — | — | — |
| Qwen 3.6 Plus | 27 | $0.0425 | dominated | Flash, Flash Lite | — | — | — |
| Kimi K2.6 | 27 | $0.4823 | dominated | Flash, Flash Lite | — | — | — |
| GLM-5.1 | 26.1 | $0.6122 | dominated | Flash, Flash Lite | — | — | — |
| MiMo V2.5 Pro | 26 | $0.0190 | frontier | Flash, Flash Lite | — | — | Flash, Flash Lite |
| Kimi K2.7 Code | 25.8 | $0.3345 | dominated | Flash, Flash Lite | — | — | — |
| Inkling Small | 25.7 | $0.0609 | dominated | Flash, Flash Lite | — | — | — |
| Tencent Hy3 | 25.3 | $0.0476 | dominated | Flash, Flash Lite | — | — | — |
| Qwen 3.7 Plus | 25.2 | $0.1319 | dominated | Flash, Flash Lite | — | — | — |
| Inkling | 25 | $0.0707 | dominated | Flash, Flash Lite | — | — | — |
| Claude Sonnet 4.6 | 24.7 | $0.1770 | dominated | Flash, Flash Lite | — | — | — |
| GPT-5.4 Mini | 24.1 | $0.2896 | dominated | Flash, Flash Lite | — | — | — |
| Kimi K2.5 | 23.5 | $0.0439 | dominated | Flash, Flash Lite | — | — | — |
| Nemotron 3 Ultra | 22.9 | $0.3559 | dominated | Flash, Flash Lite | — | — | — |
| MiniMax M2.5 | 22.8 | $0.0167 | frontier | Flash, Flash Lite | — | — | Flash, Flash Lite |
| MiniMax M2.7 | 22.8 | $0.0242 | dominated | Flash, Flash Lite | — | — | — |
| Gemini 3.5 Flash Lite | 22.2 | $0.1376 | dominated | Flash, Flash Lite | — | — | — |
| MiMo V2.5 | 21.8 | $0.0069 | frontier | Flash, Flash Lite | — | — | Flash, Flash Lite |
| Step 3.7 Flash | 19.5 | $0.0168 | dominated | Flash Lite | — | — | — |
| LongCat 2.0 | 19.1 | $0.0307 | dominated | Flash Lite | — | — | — |
| Step 3.5 Flash | 17 | $0.0073 | dominated | Flash Lite | — | — | — |
| Gemini 3.1 Flash Lite | 15.6 | $0.0394 | dominated | Flash Lite | — | — | — |
| Claude Haiku 4.5 | 15.4 | $0.0590 | dominated | Flash Lite | — | — | — |

## Ultra  ->  `ultra-tier`

_lambda 1.0, rho 0.0 → mu 0 (spread 9.86 ÷ median 110.2 s), floor 46.08, top-K 10 — 14 eligible scored models; 0 pinned; 3 backup fill(s)._


Scored models — ranked by NMB, frontier (primary) candidates first, then dominated (backup) candidates. Rows past the top-K are **cut**.

| # | Model | Provider(s) | Intel | Cost/task | Latency | Penalty | NMB | Pareto | Result |
|--:|-------|-------------|------:|----------:|--------:|--------:|----:|--------|--------|
| 1 | Claude Opus 5.5 | commandcode | 57.6 | $3.5068 | 666.4s | 0.00 | 54.09 | frontier | primary · order 1 |
| 2 | Claude Sonnet 5.5 | commandcode | 56 | $3.2013 | 437.3s | 0.00 | 52.80 | frontier | primary · order 2 |
| 3 | Gemini 4 Argon | commandcode | 52.6 | $1.1668 | unknown | — | 51.43 | frontier | primary · order 3 |
| 4 | GPT-6.1 Sol | commandcode | 51.8 | $0.4245 | 287.4s | 0.00 | 51.38 | frontier | primary · order 4 |
| 5 | GPT-6 Astra | commandcode | 52.7 | $1.9806 | 299.5s | 0.00 | 50.72 | frontier | primary · order 5 |
| 6 | MiMo V2.6 Pro | commandcode | 46.3 | $0.0469 | 58.5s | 0.00 | 46.25 | frontier | primary · order 6 |
| 7 | MiMo V2.6 Pro UltraSpeed | commandcode | 46.3 | $0.4690 | 58.5s | 0.00 | 45.83 | frontier | primary · order 7 |
| 8 | Muse Wonder | commandcode | 52.4 | $2.6472 | 57.7s | 0.00 | 49.75 | dominated | backup · order 8 |
| 9 | Claude Fable 5.1 | commandcode | 53.4 | $4.3896 | 267.2s | 0.00 | 49.01 | dominated | backup · order 9 |
| 10 | Muse Spark 1.3 | commandcode | 48.1 | $0.8568 | 73.6s | 0.00 | 47.24 | dominated | backup · order 10 |
| — | Claude Opus 5 | commandcode | 50.8 | $3.5619 | 81.1s | 0.00 | 47.24 | dominated | cut |
| — | GPT-6 Sol | commandcode | 47.6 | $0.6352 | 141.8s | 0.00 | 46.96 | dominated | cut |
| — | GPT-5.6 Sol | commandcode | 47 | $1.7874 | 106.7s | 0.00 | 45.21 | dominated | cut |
| — | Claude Fable 5 | commandcode | 49.6 | $5.3176 | 113.7s | 0.00 | 44.28 | dominated | cut |
| — | Grok 4.7 | commandcode | 46.4 | $2.1682 | 82.0s | 0.00 | 44.23 | dominated | cut |

## Pro  ->  `pro-tier`

_lambda 0.2, rho 0.0 → mu 0 (spread 6.37 ÷ median 58.5 s), floor 34.56, top-K 10 — 40 eligible scored models; 0 pinned; 1 backup fill(s)._


Scored models — ranked by NMB, frontier (primary) candidates first, then dominated (backup) candidates. Rows past the top-K are **cut**.

| # | Model | Provider(s) | Intel | Cost/task | Latency | Penalty | NMB | Pareto | Result |
|--:|-------|-------------|------:|----------:|--------:|--------:|----:|--------|--------|
| 1 | GPT-6.1 Sol | commandcode | 51.8 | $0.4245 | 287.4s | 0.00 | 9.94 | frontier | primary · order 1 |
| 2 | Gemini 4 Argon | commandcode | 52.6 | $1.1668 | unknown | — | 9.35 | frontier | primary · order 2 |
| 3 | MiMo V2.6 Pro | commandcode | 46.3 | $0.0469 | 58.5s | 0.00 | 9.21 | frontier | primary · order 3 |
| 4 | MiMo V2.6 Pro UltraSpeed | commandcode | 46.3 | $0.4690 | 58.5s | 0.00 | 8.79 | frontier | primary · order 4 |
| 5 | GPT-6 Astra | commandcode | 52.7 | $1.9806 | 299.5s | 0.00 | 8.56 | frontier | primary · order 5 |
| 6 | Claude Opus 5.5 | commandcode | 57.6 | $3.5068 | 666.4s | 0.00 | 8.01 | frontier | primary · order 6 |
| 7 | Claude Sonnet 5.5 | commandcode | 56 | $3.2013 | 437.3s | 0.00 | 8.00 | frontier | primary · order 7 |
| 8 | GPT-6 Luna | commandcode | 38.1 | $0.0412 | 107.2s | 0.00 | 7.58 | frontier | primary · order 8 |
| 9 | MiMo V2.6 Flash | commandcode | 37.9 | $0.0224 | 49.7s | 0.00 | 7.56 | frontier | primary · order 9 |
| 10 | GPT-6 Sol | commandcode | 47.6 | $0.6352 | 141.8s | 0.00 | 8.88 | dominated | backup · order 10 |
| — | Muse Spark 1.3 | commandcode | 48.1 | $0.8568 | 73.6s | 0.00 | 8.76 | dominated | cut |
| — | Claude Haiku 5.5 | commandcode | 43.4 | $0.1294 | 336.6s | 0.00 | 8.55 | dominated | cut |
| — | Step 5 Preview | commandcode | 43.7 | $0.4559 | 30.4s | 0.00 | 8.28 | dominated | cut |
| — | GLM-5.3 Flash | commandcode | 41.8 | $0.1623 | 43.0s | 0.00 | 8.20 | dominated | cut |
| — | Grok 4.6 | commandcode | 44.3 | $0.8612 | 46.2s | 0.00 | 8.00 | dominated | cut |
| — | GLM-5.3 FlashX | commandcode | 41.8 | $0.4057 | 43.0s | 0.00 | 7.95 | dominated | cut |
| — | GLM-5.3 | commandcode | 44.8 | $1.1093 | 45.5s | 0.00 | 7.85 | dominated | cut |
| — | Claude Opus 4.7 | commandcode | 40.7 | $0.2950 | 29.2s | 0.00 | 7.85 | dominated | cut |
| — | Muse Wonder | commandcode | 52.4 | $2.6472 | 57.7s | 0.00 | 7.83 | dominated | cut |
| — | DeepSeek V4.1 Flash (latest) | commandcode | 39.5 | $0.0689 | 15.5s | 0.00 | 7.83 | dominated | cut |
| — | DeepSeek V4.1 Flash Fast (latest) | commandcode | 39.5 | $0.0724 | 15.5s | 0.00 | 7.83 | dominated | cut |
| — | Qwen 3.8 Flash | commandcode | 39.8 | $0.1898 | 50.1s | 0.00 | 7.77 | dominated | cut |
| — | Ling 3.1 Flash | commandcode | 41.1 | $0.5518 | 13.7s | 0.00 | 7.67 | dominated | cut |
| — | GPT-5.4 | commandcode | 39 | $0.1500 | 171.2s | 0.00 | 7.65 | dominated | cut |
| — | GPT-5.6 Sol | commandcode | 47 | $1.7874 | 106.7s | 0.00 | 7.61 | dominated | cut |
| — | GPT-5.6 Terra | commandcode | 42.1 | $0.9052 | 137.0s | 0.00 | 7.51 | dominated | cut |
| — | Kimi K3 | commandcode | 43.6 | $1.2161 | 62.0s | 0.00 | 7.50 | dominated | cut |
| — | Muse Spark 1.2 | commandcode | 39.6 | $0.5203 | 21.9s | 0.00 | 7.40 | dominated | cut |
| — | GPT-5.6 Luna | commandcode | 37.3 | $0.1154 | 123.5s | 0.00 | 7.34 | dominated | cut |
| — | Grok 4.5 | commandcode | 38.8 | $0.5108 | 19.4s | 0.00 | 7.25 | dominated | cut |
| — | Grok 4.7 | commandcode | 46.4 | $2.1682 | 82.0s | 0.00 | 7.11 | dominated | cut |
| — | Mistral Large 4 | commandcode | 38.4 | $0.5703 | unknown | — | 7.11 | dominated | cut |
| — | DeepSeek V4 Pro (latest) | commandcode | 36 | $0.1546 | 28.8s | 0.00 | 7.05 | dominated | cut |
| — | DeepSeek V4 Flash Vision (exp) | commandcode | 34.8 | $0.0637 | 15.6s | 0.00 | 6.90 | dominated | cut |
| — | Gemini 3.7 Flash | commandcode | 39.1 | $1.1252 | 10.4s | 0.00 | 6.69 | dominated | cut |
| — | Gemini 3.8 Flash | commandcode | 40.9 | $1.5112 | 27.8s | 0.00 | 6.67 | dominated | cut |
| — | Claude Opus 5 | commandcode | 50.8 | $3.5619 | 81.1s | 0.00 | 6.60 | dominated | cut |
| — | Qwen 3.8 Max 0902 | commandcode | 45.4 | $2.7583 | 64.4s | 0.00 | 6.32 | dominated | cut |
| — | Claude Fable 5.1 | commandcode | 53.4 | $4.3896 | 267.2s | 0.00 | 6.29 | dominated | cut |
| — | GPT-5.5 | commandcode | 38.4 | $1.7047 | 51.9s | 0.00 | 5.98 | dominated | cut |
| — | Claude Opus 4.8 | commandcode | 41.8 | $2.4812 | 47.1s | 0.00 | 5.88 | dominated | cut |
| — | Claude Fable 5 | commandcode | 49.6 | $5.3176 | 113.7s | 0.00 | 4.60 | dominated | cut |
| — | Claude Sonnet 5 | commandcode | 38.2 | $3.0954 | 165.1s | 0.00 | 4.54 | dominated | cut |
| — | Qwen 3.8 Max Prime | commandcode | 45.4 | $5.5167 | 64.4s | 0.00 | 3.56 | dominated | cut |

## Flash  ->  `flash-tier`

_lambda 0.001, rho 0.0 → mu 0 (spread 5.49 ÷ median 51.0 s), floor 20.16, top-K 10 — 68 eligible scored models; 1 pinned; 0 backup fill(s)._

_Excluded by config: deepseek-v4-1-flash._


**Pinned by config** — force-included ahead of NMB. They are removed from the scored pool, so their NMB is reference only:

| # | Model | Provider(s) | Intel | Cost/task | NMB | Pareto |
|--:|-------|-------------|------:|----------:|----:|--------|
| 1 | DeepSeek V4.1 Flash (latest) | commandcode | 39.5 | $0.0689 | -0.03 | dominated |

Scored models — ranked by NMB, frontier (primary) candidates first, then dominated (backup) candidates. Rows past the top-K are **cut**.

| # | Model | Provider(s) | Intel | Cost/task | Latency | Penalty | NMB | Pareto | Result |
|--:|-------|-------------|------:|----------:|--------:|--------:|----:|--------|--------|
| 2 | MiMo V2.6 Flash | commandcode | 37.9 | $0.0224 | 49.7s | 0.00 | 0.02 | frontier | primary · order 2 |
| 3 | MiMo V2.5 | commandcode | 21.8 | $0.0069 | 80.0s | 0.00 | 0.01 | frontier | primary · order 3 |
| 4 | MiMo V2.5 Pro | commandcode | 26 | $0.0190 | 68.0s | 0.00 | 0.01 | frontier | primary · order 4 |
| 5 | MiniMax M2.5 | commandcode | 22.8 | $0.0167 | 39.0s | 0.00 | 0.01 | frontier | primary · order 5 |
| 6 | MiMo V2.6 Pro | commandcode | 46.3 | $0.0469 | 58.5s | 0.00 | -0.00 | frontier | primary · order 6 |
| 7 | GPT-6 Luna | commandcode | 38.1 | $0.0412 | 107.2s | 0.00 | -0.00 | frontier | primary · order 7 |
| 8 | GPT-6.1 Sol | commandcode | 51.8 | $0.4245 | 287.4s | 0.00 | -0.37 | frontier | primary · order 8 |
| 9 | MiMo V2.6 Pro UltraSpeed | commandcode | 46.3 | $0.4690 | 58.5s | 0.00 | -0.42 | frontier | primary · order 9 |
| 10 | Gemini 4 Argon | commandcode | 52.6 | $1.1668 | unknown | — | -1.11 | frontier | primary · order 10 |
| — | GPT-6 Astra | commandcode | 52.7 | $1.9806 | 299.5s | 0.00 | -1.93 | frontier | cut |
| — | Claude Sonnet 5.5 | commandcode | 56 | $3.2013 | 437.3s | 0.00 | -3.15 | frontier | cut |
| — | Claude Opus 5.5 | commandcode | 57.6 | $3.5068 | 666.4s | 0.00 | -3.45 | frontier | cut |
| — | MiniMax M2.7 | commandcode | 22.8 | $0.0242 | 52.7s | 0.00 | -0.00 | dominated | cut |
| — | DeepSeek V4 Flash (latest) | commandcode | 34.3 | $0.0445 | 15.6s | 0.00 | -0.01 | dominated | cut |
| — | Qwen 3.6 Plus | commandcode | 27 | $0.0425 | 110.0s | 0.00 | -0.02 | dominated | cut |
| — | Kimi K2.5 | commandcode | 23.5 | $0.0439 | 59.7s | 0.00 | -0.02 | dominated | cut |
| — | Tencent Hy3 | commandcode | 25.3 | $0.0476 | 32.4s | 0.00 | -0.02 | dominated | cut |
| — | DeepSeek V4 Flash Fast | commandcode | 34.3 | $0.0611 | 15.6s | 0.00 | -0.03 | dominated | cut |
| — | DeepSeek V4 Flash Vision (exp) | commandcode | 34.8 | $0.0637 | 15.6s | 0.00 | -0.03 | dominated | cut |
| — | Inkling Small | commandcode | 25.7 | $0.0609 | 15.1s | 0.00 | -0.04 | dominated | cut |
| — | Muse Spark Open | commandcode | 31.3 | $0.0699 | unknown | — | -0.04 | dominated | cut |
| — | Inkling | commandcode | 25 | $0.0707 | 15.9s | 0.00 | -0.05 | dominated | cut |
| — | GLM-5 | commandcode | 27.9 | $0.0752 | 52.0s | 0.00 | -0.05 | dominated | cut |
| — | GPT-5.6 Luna | commandcode | 37.3 | $0.1154 | 123.5s | 0.00 | -0.08 | dominated | cut |
| — | Qwen 3.6 Max Preview | commandcode | 28.4 | $0.1138 | unknown | — | -0.09 | dominated | cut |
| — | Claude Haiku 5.5 | commandcode | 43.4 | $0.1294 | 336.6s | 0.00 | -0.09 | dominated | cut |
| — | Qwen 3.7 Plus | commandcode | 25.2 | $0.1319 | 46.9s | 0.00 | -0.11 | dominated | cut |
| — | GPT-5.4 | commandcode | 39 | $0.1500 | 171.2s | 0.00 | -0.11 | dominated | cut |
| — | Gemini 3.5 Flash Lite | commandcode | 22.2 | $0.1376 | 8.4s | 0.00 | -0.12 | dominated | cut |
| — | DeepSeek V4 Pro (latest) | commandcode | 36 | $0.1546 | 28.8s | 0.00 | -0.12 | dominated | cut |
| — | GLM-5.3 Flash | commandcode | 41.8 | $0.1623 | 43.0s | 0.00 | -0.12 | dominated | cut |
| — | GPT-5.3 Codex | commandcode | 32.5 | $0.1810 | 75.4s | 0.00 | -0.15 | dominated | cut |
| — | Qwen 3.8 Flash | commandcode | 39.8 | $0.1898 | 50.1s | 0.00 | -0.15 | dominated | cut |
| — | Claude Sonnet 4.6 | commandcode | 24.7 | $0.1770 | 12.2s | 0.00 | -0.15 | dominated | cut |
| — | Claude Opus 4.7 | commandcode | 40.7 | $0.2950 | 29.2s | 0.00 | -0.25 | dominated | cut |
| — | GPT-5.4 Mini | commandcode | 24.1 | $0.2896 | 111.4s | 0.00 | -0.27 | dominated | cut |
| — | MiniMax M3 | commandcode | 29.2 | $0.3086 | 26.5s | 0.00 | -0.28 | dominated | cut |
| — | Kimi K2.7 Code | commandcode | 25.8 | $0.3345 | 49.6s | 0.00 | -0.31 | dominated | cut |
| — | Nemotron 3 Ultra | commandcode | 22.9 | $0.3559 | 19.1s | 0.00 | -0.33 | dominated | cut |
| — | GLM-5.3 FlashX | commandcode | 41.8 | $0.4057 | 43.0s | 0.00 | -0.36 | dominated | cut |
| — | Step 5 Preview | commandcode | 43.7 | $0.4559 | 30.4s | 0.00 | -0.41 | dominated | cut |
| — | Kimi K2.6 | commandcode | 27 | $0.4823 | 96.7s | 0.00 | -0.46 | dominated | cut |
| — | Grok 4.5 | commandcode | 38.8 | $0.5108 | 19.4s | 0.00 | -0.47 | dominated | cut |
| — | Muse Spark 1.2 | commandcode | 39.6 | $0.5203 | 21.9s | 0.00 | -0.48 | dominated | cut |
| — | Ling 3.1 Flash | commandcode | 41.1 | $0.5518 | 13.7s | 0.00 | -0.51 | dominated | cut |
| — | Mistral Large 4 | commandcode | 38.4 | $0.5703 | unknown | — | -0.53 | dominated | cut |
| — | GLM-5.1 | commandcode | 26.1 | $0.6122 | 64.2s | 0.00 | -0.59 | dominated | cut |
| — | GPT-6 Sol | commandcode | 47.6 | $0.6352 | 141.8s | 0.00 | -0.59 | dominated | cut |
| — | Qwen 3.7 Max | commandcode | 29.5 | $0.6333 | 17.6s | 0.00 | -0.60 | dominated | cut |
| — | Qwen 3.8 27B | commandcode | 33.7 | $0.6425 | 64.9s | 0.00 | -0.61 | dominated | cut |
| — | Kimi K2.7 Code HighSpeed | commandcode | 25.8 | $0.6690 | 49.6s | 0.00 | -0.64 | dominated | cut |
| — | Muse Spark 1.1 | commandcode | 33.7 | $0.7368 | 49.2s | 0.00 | -0.70 | dominated | cut |
| — | GLM-5.2 | commandcode | 33.7 | $0.8145 | 34.3s | 0.00 | -0.78 | dominated | cut |
| — | Muse Spark 1.3 | commandcode | 48.1 | $0.8568 | 73.6s | 0.00 | -0.81 | dominated | cut |
| — | Grok 4.6 | commandcode | 44.3 | $0.8612 | 46.2s | 0.00 | -0.82 | dominated | cut |
| — | GPT-5.6 Terra | commandcode | 42.1 | $0.9052 | 137.0s | 0.00 | -0.86 | dominated | cut |
| — | GLM-5.3 | commandcode | 44.8 | $1.1093 | 45.5s | 0.00 | -1.06 | dominated | cut |
| — | Gemini 3.7 Flash | commandcode | 39.1 | $1.1252 | 10.4s | 0.00 | -1.09 | dominated | cut |
| — | Kimi K3 | commandcode | 43.6 | $1.2161 | 62.0s | 0.00 | -1.17 | dominated | cut |
| — | Gemini 3.8 Flash | commandcode | 40.9 | $1.5112 | 27.8s | 0.00 | -1.47 | dominated | cut |
| — | GPT-5.5 | commandcode | 38.4 | $1.7047 | 51.9s | 0.00 | -1.67 | dominated | cut |
| — | GPT-5.6 Sol | commandcode | 47 | $1.7874 | 106.7s | 0.00 | -1.74 | dominated | cut |
| — | GLM-5.2 Fast | commandcode | 33.7 | $1.8334 | 34.3s | 0.00 | -1.80 | dominated | cut |
| — | Gemini 3.6 Flash | commandcode | 34 | $1.9462 | 17.1s | 0.00 | -1.91 | dominated | cut |
| — | Grok 4.7 | commandcode | 46.4 | $2.1682 | 82.0s | 0.00 | -2.12 | dominated | cut |
| — | Gemini 3.5 Flash | commandcode | 32.6 | $2.3906 | 16.3s | 0.00 | -2.36 | dominated | cut |
| — | Claude Opus 4.8 | commandcode | 41.8 | $2.4812 | 47.1s | 0.00 | -2.44 | dominated | cut |
| — | Muse Wonder | commandcode | 52.4 | $2.6472 | 57.7s | 0.00 | -2.59 | dominated | cut |
| — | Qwen 3.8 Max 0902 | commandcode | 45.4 | $2.7583 | 64.4s | 0.00 | -2.71 | dominated | cut |
| — | Claude Sonnet 5 | commandcode | 38.2 | $3.0954 | 165.1s | 0.00 | -3.06 | dominated | cut |
| — | Claude Opus 5 | commandcode | 50.8 | $3.5619 | 81.1s | 0.00 | -3.51 | dominated | cut |
| — | Claude Fable 5.1 | commandcode | 53.4 | $4.3896 | 267.2s | 0.00 | -4.34 | dominated | cut |
| — | Claude Fable 5 | commandcode | 49.6 | $5.3176 | 113.7s | 0.00 | -5.27 | dominated | cut |
| — | Qwen 3.8 Max Prime | commandcode | 45.4 | $5.5167 | 64.4s | 0.00 | -5.47 | dominated | cut |

## Flash Lite  ->  `flash-lite-tier`

_lambda 0.0001, rho 0.0 → mu 0 (spread 5.51 ÷ median 49.6 s), floor 0.00, top-K 10 — 74 eligible scored models; 0 pinned; 0 backup fill(s)._


Scored models — ranked by NMB, frontier (primary) candidates first, then dominated (backup) candidates. Rows past the top-K are **cut**.

| # | Model | Provider(s) | Intel | Cost/task | Latency | Penalty | NMB | Pareto | Result |
|--:|-------|-------------|------:|----------:|--------:|--------:|----:|--------|--------|
| 1 | MiMo V2.5 | commandcode | 21.8 | $0.0069 | 80.0s | 0.00 | -0.00 | frontier | primary · order 1 |
| 2 | MiniMax M2.5 | commandcode | 22.8 | $0.0167 | 39.0s | 0.00 | -0.01 | frontier | primary · order 2 |
| 3 | MiMo V2.5 Pro | commandcode | 26 | $0.0190 | 68.0s | 0.00 | -0.02 | frontier | primary · order 3 |
| 4 | MiMo V2.6 Flash | commandcode | 37.9 | $0.0224 | 49.7s | 0.00 | -0.02 | frontier | primary · order 4 |
| 5 | GPT-6 Luna | commandcode | 38.1 | $0.0412 | 107.2s | 0.00 | -0.04 | frontier | primary · order 5 |
| 6 | MiMo V2.6 Pro | commandcode | 46.3 | $0.0469 | 58.5s | 0.00 | -0.04 | frontier | primary · order 6 |
| 7 | GPT-6.1 Sol | commandcode | 51.8 | $0.4245 | 287.4s | 0.00 | -0.42 | frontier | primary · order 7 |
| 8 | MiMo V2.6 Pro UltraSpeed | commandcode | 46.3 | $0.4690 | 58.5s | 0.00 | -0.46 | frontier | primary · order 8 |
| 9 | Gemini 4 Argon | commandcode | 52.6 | $1.1668 | unknown | — | -1.16 | frontier | primary · order 9 |
| 10 | GPT-6 Astra | commandcode | 52.7 | $1.9806 | 299.5s | 0.00 | -1.98 | frontier | primary · order 10 |
| — | Claude Sonnet 5.5 | commandcode | 56 | $3.2013 | 437.3s | 0.00 | -3.20 | frontier | cut |
| — | Claude Opus 5.5 | commandcode | 57.6 | $3.5068 | 666.4s | 0.00 | -3.50 | frontier | cut |
| — | Step 3.5 Flash | commandcode | 17 | $0.0073 | 20.9s | 0.00 | -0.01 | dominated | cut |
| — | Step 3.7 Flash | commandcode | 19.5 | $0.0168 | 15.7s | 0.00 | -0.01 | dominated | cut |
| — | MiniMax M2.7 | commandcode | 22.8 | $0.0242 | 52.7s | 0.00 | -0.02 | dominated | cut |
| — | LongCat 2.0 | commandcode | 19.1 | $0.0307 | 38.8s | 0.00 | -0.03 | dominated | cut |
| — | Gemini 3.1 Flash Lite | commandcode | 15.6 | $0.0394 | 5.7s | 0.00 | -0.04 | dominated | cut |
| — | Qwen 3.6 Plus | commandcode | 27 | $0.0425 | 110.0s | 0.00 | -0.04 | dominated | cut |
| — | DeepSeek V4 Flash (latest) | commandcode | 34.3 | $0.0445 | 15.6s | 0.00 | -0.04 | dominated | cut |
| — | Kimi K2.5 | commandcode | 23.5 | $0.0439 | 59.7s | 0.00 | -0.04 | dominated | cut |
| — | Tencent Hy3 | commandcode | 25.3 | $0.0476 | 32.4s | 0.00 | -0.05 | dominated | cut |
| — | Claude Haiku 4.5 | commandcode | 15.4 | $0.0590 | 6.2s | 0.00 | -0.06 | dominated | cut |
| — | DeepSeek V4 Flash Fast | commandcode | 34.3 | $0.0611 | 15.6s | 0.00 | -0.06 | dominated | cut |
| — | Inkling Small | commandcode | 25.7 | $0.0609 | 15.1s | 0.00 | -0.06 | dominated | cut |
| — | DeepSeek V4 Flash Vision (exp) | commandcode | 34.8 | $0.0637 | 15.6s | 0.00 | -0.06 | dominated | cut |
| — | DeepSeek V4.1 Flash (latest) | commandcode | 39.5 | $0.0689 | 15.5s | 0.00 | -0.06 | dominated | cut |
| — | Muse Spark Open | commandcode | 31.3 | $0.0699 | unknown | — | -0.07 | dominated | cut |
| — | Inkling | commandcode | 25 | $0.0707 | 15.9s | 0.00 | -0.07 | dominated | cut |
| — | DeepSeek V4.1 Flash Fast (latest) | commandcode | 39.5 | $0.0724 | 15.5s | 0.00 | -0.07 | dominated | cut |
| — | GLM-5 | commandcode | 27.9 | $0.0752 | 52.0s | 0.00 | -0.07 | dominated | cut |
| — | Qwen 3.6 Max Preview | commandcode | 28.4 | $0.1138 | unknown | — | -0.11 | dominated | cut |
| — | GPT-5.6 Luna | commandcode | 37.3 | $0.1154 | 123.5s | 0.00 | -0.11 | dominated | cut |
| — | Claude Haiku 5.5 | commandcode | 43.4 | $0.1294 | 336.6s | 0.00 | -0.13 | dominated | cut |
| — | Qwen 3.7 Plus | commandcode | 25.2 | $0.1319 | 46.9s | 0.00 | -0.13 | dominated | cut |
| — | Gemini 3.5 Flash Lite | commandcode | 22.2 | $0.1376 | 8.4s | 0.00 | -0.14 | dominated | cut |
| — | GPT-5.4 | commandcode | 39 | $0.1500 | 171.2s | 0.00 | -0.15 | dominated | cut |
| — | DeepSeek V4 Pro (latest) | commandcode | 36 | $0.1546 | 28.8s | 0.00 | -0.15 | dominated | cut |
| — | GLM-5.3 Flash | commandcode | 41.8 | $0.1623 | 43.0s | 0.00 | -0.16 | dominated | cut |
| — | Claude Sonnet 4.6 | commandcode | 24.7 | $0.1770 | 12.2s | 0.00 | -0.17 | dominated | cut |
| — | GPT-5.3 Codex | commandcode | 32.5 | $0.1810 | 75.4s | 0.00 | -0.18 | dominated | cut |
| — | Qwen 3.8 Flash | commandcode | 39.8 | $0.1898 | 50.1s | 0.00 | -0.19 | dominated | cut |
| — | GPT-5.4 Mini | commandcode | 24.1 | $0.2896 | 111.4s | 0.00 | -0.29 | dominated | cut |
| — | Claude Opus 4.7 | commandcode | 40.7 | $0.2950 | 29.2s | 0.00 | -0.29 | dominated | cut |
| — | MiniMax M3 | commandcode | 29.2 | $0.3086 | 26.5s | 0.00 | -0.31 | dominated | cut |
| — | Kimi K2.7 Code | commandcode | 25.8 | $0.3345 | 49.6s | 0.00 | -0.33 | dominated | cut |
| — | Nemotron 3 Ultra | commandcode | 22.9 | $0.3559 | 19.1s | 0.00 | -0.35 | dominated | cut |
| — | GLM-5.3 FlashX | commandcode | 41.8 | $0.4057 | 43.0s | 0.00 | -0.40 | dominated | cut |
| — | Step 5 Preview | commandcode | 43.7 | $0.4559 | 30.4s | 0.00 | -0.45 | dominated | cut |
| — | Kimi K2.6 | commandcode | 27 | $0.4823 | 96.7s | 0.00 | -0.48 | dominated | cut |
| — | Grok 4.5 | commandcode | 38.8 | $0.5108 | 19.4s | 0.00 | -0.51 | dominated | cut |
| — | Muse Spark 1.2 | commandcode | 39.6 | $0.5203 | 21.9s | 0.00 | -0.52 | dominated | cut |
| — | Ling 3.1 Flash | commandcode | 41.1 | $0.5518 | 13.7s | 0.00 | -0.55 | dominated | cut |
| — | Mistral Large 4 | commandcode | 38.4 | $0.5703 | unknown | — | -0.57 | dominated | cut |
| — | GLM-5.1 | commandcode | 26.1 | $0.6122 | 64.2s | 0.00 | -0.61 | dominated | cut |
| — | Qwen 3.7 Max | commandcode | 29.5 | $0.6333 | 17.6s | 0.00 | -0.63 | dominated | cut |
| — | GPT-6 Sol | commandcode | 47.6 | $0.6352 | 141.8s | 0.00 | -0.63 | dominated | cut |
| — | Qwen 3.8 27B | commandcode | 33.7 | $0.6425 | 64.9s | 0.00 | -0.64 | dominated | cut |
| — | Kimi K2.7 Code HighSpeed | commandcode | 25.8 | $0.6690 | 49.6s | 0.00 | -0.67 | dominated | cut |
| — | Muse Spark 1.1 | commandcode | 33.7 | $0.7368 | 49.2s | 0.00 | -0.73 | dominated | cut |
| — | GLM-5.2 | commandcode | 33.7 | $0.8145 | 34.3s | 0.00 | -0.81 | dominated | cut |
| — | Muse Spark 1.3 | commandcode | 48.1 | $0.8568 | 73.6s | 0.00 | -0.85 | dominated | cut |
| — | Grok 4.6 | commandcode | 44.3 | $0.8612 | 46.2s | 0.00 | -0.86 | dominated | cut |
| — | GPT-5.6 Terra | commandcode | 42.1 | $0.9052 | 137.0s | 0.00 | -0.90 | dominated | cut |
| — | GLM-5.3 | commandcode | 44.8 | $1.1093 | 45.5s | 0.00 | -1.10 | dominated | cut |
| — | Gemini 3.7 Flash | commandcode | 39.1 | $1.1252 | 10.4s | 0.00 | -1.12 | dominated | cut |
| — | Kimi K3 | commandcode | 43.6 | $1.2161 | 62.0s | 0.00 | -1.21 | dominated | cut |
| — | Gemini 3.8 Flash | commandcode | 40.9 | $1.5112 | 27.8s | 0.00 | -1.51 | dominated | cut |
| — | GPT-5.5 | commandcode | 38.4 | $1.7047 | 51.9s | 0.00 | -1.70 | dominated | cut |
| — | GPT-5.6 Sol | commandcode | 47 | $1.7874 | 106.7s | 0.00 | -1.78 | dominated | cut |
| — | GLM-5.2 Fast | commandcode | 33.7 | $1.8334 | 34.3s | 0.00 | -1.83 | dominated | cut |
| — | Gemini 3.6 Flash | commandcode | 34 | $1.9462 | 17.1s | 0.00 | -1.94 | dominated | cut |
| — | Grok 4.7 | commandcode | 46.4 | $2.1682 | 82.0s | 0.00 | -2.16 | dominated | cut |
| — | Gemini 3.5 Flash | commandcode | 32.6 | $2.3906 | 16.3s | 0.00 | -2.39 | dominated | cut |
| — | Claude Opus 4.8 | commandcode | 41.8 | $2.4812 | 47.1s | 0.00 | -2.48 | dominated | cut |
| — | Muse Wonder | commandcode | 52.4 | $2.6472 | 57.7s | 0.00 | -2.64 | dominated | cut |
| — | Qwen 3.8 Max 0902 | commandcode | 45.4 | $2.7583 | 64.4s | 0.00 | -2.75 | dominated | cut |
| — | Claude Sonnet 5 | commandcode | 38.2 | $3.0954 | 165.1s | 0.00 | -3.09 | dominated | cut |
| — | Claude Opus 5 | commandcode | 50.8 | $3.5619 | 81.1s | 0.00 | -3.56 | dominated | cut |
| — | Claude Fable 5.1 | commandcode | 53.4 | $4.3896 | 267.2s | 0.00 | -4.38 | dominated | cut |
| — | Claude Fable 5 | commandcode | 49.6 | $5.3176 | 113.7s | 0.00 | -5.31 | dominated | cut |
| — | Qwen 3.8 Max Prime | commandcode | 45.4 | $5.5167 | 64.4s | 0.00 | -5.51 | dominated | cut |

## Pareto frontier

**11** efficient models on the frontier; **63** dominated (another model is both smarter and cheaper).

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
| Qwen 3.8 Flash | 39.8 | $0.1898 | MiMo V2.6 Pro | 46.3 | $0.0469 |
| Muse Spark 1.2 | 39.6 | $0.5203 | GPT-6.1 Sol | 51.8 | $0.4245 |
| DeepSeek V4.1 Flash (latest) | 39.5 | $0.0689 | MiMo V2.6 Pro | 46.3 | $0.0469 |
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

**excluded_by_config** (2): commandcode:meta/muse-spark-1.2-contributor, commandcode:meta/muse-spark-1.3-contributor

**unmapped** (10): commandcode:minimax/minimax-m3.1-flash, commandcode:minimax/minimax-m3.1-flash:free, commandcode:Qwen/Qwen3.8-Omni-Flash, commandcode:Qwen/Qwen3.7-Flash, commandcode:tencent/hy4-preview, commandcode:sakana/fugu-ultra, commandcode:nvidia/nemotron-3.5-super-vl, commandcode:stealth/glyph-cluster:free, commandcode:reflection/beam:free, commandcode:poolside/laguna-s-2.1-free


## Token limits

Output limits come from the models.dev catalog; input limits are `context - output` (the provider's context window stays authoritative). Nothing is invented — anything missing or suspicious is listed here.

**output_equals_context** (13) — catalog entry reports output == its own context window (likely copied): commandcode:moonshotai/Kimi-K2.5, commandcode:moonshotai/Kimi-K2.6, commandcode:moonshotai/Kimi-K2.7-Code, commandcode:moonshotai/Kimi-K2.7-Code-Highspeed, commandcode:stealth/glyph-cluster:free, commandcode:stepfun/Step-3.5-Flash, commandcode:stepfun/Step-3.7-Flash, commandcode:stepfun/Step-5-Preview, commandcode:thinkingmachines/inkling, commandcode:thinkingmachines/inkling-small, commandcode:xai/grok-4.5, commandcode:xai/grok-4.6, commandcode:xai/grok-4.7

**output_not_below_context** (12) — output limit is not smaller than the provider's context window: commandcode:moonshotai/Kimi-K2.5, commandcode:moonshotai/Kimi-K2.6, commandcode:moonshotai/Kimi-K2.7-Code, commandcode:moonshotai/Kimi-K2.7-Code-Highspeed, commandcode:stealth/glyph-cluster:free, commandcode:stepfun/Step-3.7-Flash, commandcode:stepfun/Step-5-Preview, commandcode:thinkingmachines/inkling, commandcode:thinkingmachines/inkling-small, commandcode:xai/grok-4.5, commandcode:xai/grok-4.6, commandcode:xai/grok-4.7

