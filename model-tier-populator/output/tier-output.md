# Model pipeline — tier suggestions

_Generated: 2026-10-20T07:57:34+00:00_

**SOTA intelligence:** 57.6

**Cost methods:** aa_free=38, task_profile=2


## Ultra  ->  `ultra-tier`

_Floor 46.08 (0.80x SOTA) · lambda 1.0 · rho 0.0 → mu 0.0 · pool 14 · 10 deployments · backups 3_

| # | Model | Provider | Model ID | Intel | Cost/task $ | Latency | NMB | Kind | API base |
|---|-------|----------|----------|-------|-------------|--------:|-----|------|----------|
| 1 | Claude Opus 5.5 | commandcode | `claude-opus-5-5` | 57.6 | 3.506781 | 666.4s | 54.093219 | primary | `https://api.commandcode.ai/provider` |
| 2 | Claude Sonnet 5.5 | commandcode | `claude-sonnet-5-5` | 56 | 3.201301 | 437.3s | 52.798699 | primary | `https://api.commandcode.ai/provider` |
| 3 | Gemini 4 Argon | commandcode | `google/gemini-4-argon` | 52.6 | 1.166758 | unknown | 51.433242 | primary | `https://api.commandcode.ai/provider/v1` |
| 4 | GPT-6.1 Sol | commandcode | `gpt-6.1-sol` | 51.8 | 0.424542 | 287.4s | 51.375458 | primary | `https://api.commandcode.ai/provider/v1` |
| 5 | GPT-6 Astra | commandcode | `gpt-6-astra` | 52.7 | 1.980560 | 299.5s | 50.719440 | primary | `https://api.commandcode.ai/provider/v1` |
| 6 | MiMo V2.6 Pro | commandcode | `xiaomi/mimo-v2.6-pro` | 46.3 | 0.046896 | 58.5s | 46.253104 | primary | `https://api.commandcode.ai/provider/v1` |
| 7 | MiMo V2.6 Pro UltraSpeed | commandcode | `xiaomi/mimo-v2.6-pro-ultraspeed` | 46.3 | 0.468962 | 58.5s | 45.831038 | primary | `https://api.commandcode.ai/provider/v1` |
| 8 | Muse Wonder | commandcode | `meta/muse-wonder-1.0` | 52.4 | 2.647204 | 57.7s | 49.752796 | backup | `https://api.commandcode.ai/provider/v1` |
| 9 | Claude Fable 5.1 | commandcode | `claude-fable-5-1` | 53.4 | 4.389621 | 267.2s | 49.010379 | backup | `https://api.commandcode.ai/provider` |
| 10 | Muse Spark 1.3 | commandcode | `meta/muse-spark-1.3` | 48.1 | 0.856756 | 73.6s | 47.243244 | backup | `https://api.commandcode.ai/provider/v1` |


## Pro  ->  `pro-tier`

_Floor 34.56 (0.60x SOTA) · lambda 0.2 · rho 0.0 → mu 0.0 · pool 40 · 10 deployments · backups 1_

| # | Model | Provider | Model ID | Intel | Cost/task $ | Latency | NMB | Kind | API base |
|---|-------|----------|----------|-------|-------------|--------:|-----|------|----------|
| 1 | GPT-6.1 Sol | commandcode | `gpt-6.1-sol` | 51.8 | 0.424542 | 287.4s | 9.935458 | primary | `https://api.commandcode.ai/provider/v1` |
| 2 | Gemini 4 Argon | commandcode | `google/gemini-4-argon` | 52.6 | 1.166758 | unknown | 9.353242 | primary | `https://api.commandcode.ai/provider/v1` |
| 3 | MiMo V2.6 Pro | commandcode | `xiaomi/mimo-v2.6-pro` | 46.3 | 0.046896 | 58.5s | 9.213104 | primary | `https://api.commandcode.ai/provider/v1` |
| 4 | MiMo V2.6 Pro UltraSpeed | commandcode | `xiaomi/mimo-v2.6-pro-ultraspeed` | 46.3 | 0.468962 | 58.5s | 8.791038 | primary | `https://api.commandcode.ai/provider/v1` |
| 5 | GPT-6 Astra | commandcode | `gpt-6-astra` | 52.7 | 1.980560 | 299.5s | 8.559440 | primary | `https://api.commandcode.ai/provider/v1` |
| 6 | Claude Opus 5.5 | commandcode | `claude-opus-5-5` | 57.6 | 3.506781 | 666.4s | 8.013219 | primary | `https://api.commandcode.ai/provider` |
| 7 | Claude Sonnet 5.5 | commandcode | `claude-sonnet-5-5` | 56 | 3.201301 | 437.3s | 7.998699 | primary | `https://api.commandcode.ai/provider` |
| 8 | GPT-6 Luna | commandcode | `gpt-6-luna` | 38.1 | 0.041222 | 107.2s | 7.578778 | primary | `https://api.commandcode.ai/provider/v1` |
| 9 | MiMo V2.6 Flash | commandcode | `xiaomi/mimo-v2.6-flash` | 37.9 | 0.022447 | 49.7s | 7.557553 | primary | `https://api.commandcode.ai/provider/v1` |
| 10 | GPT-6 Sol | commandcode | `gpt-6-sol` | 47.6 | 0.635178 | 141.8s | 8.884822 | backup | `https://api.commandcode.ai/provider/v1` |


## Flash  ->  `flash-tier`

_Floor 20.16 (0.35x SOTA) · lambda 0.001 · rho 0.0 → mu 0.0 · pool 68 · 10 deployments · backups 0_

_Excluded by config: deepseek-v4-1-flash._

_Pinned by config: deepseek-v4-1-flash (order 1)._

| # | Model | Provider | Model ID | Intel | Cost/task $ | Latency | NMB | Kind | API base |
|---|-------|----------|----------|-------|-------------|--------:|-----|------|----------|
| 1 | DeepSeek V4.1 Flash (latest) | commandcode | `deepseek/deepseek-v4.1-flash` | 39.5 | 0.068925 | 15.5s | -0.029425 | pinned | `https://api.commandcode.ai/provider/v1` |
| 2 | MiMo V2.6 Flash | commandcode | `xiaomi/mimo-v2.6-flash` | 37.9 | 0.022447 | 49.7s | 0.015453 | primary | `https://api.commandcode.ai/provider/v1` |
| 3 | MiMo V2.5 | commandcode | `xiaomi/mimo-v2.5` | 21.8 | 0.006871 | 80.0s | 0.014929 | primary | `https://api.commandcode.ai/provider/v1` |
| 4 | MiMo V2.5 Pro | commandcode | `xiaomi/mimo-v2.5-pro` | 26 | 0.019047 | 68.0s | 0.006953 | primary | `https://api.commandcode.ai/provider/v1` |
| 5 | MiniMax M2.5 | commandcode | `MiniMaxAI/MiniMax-M2.5` | 22.8 | 0.016650 | 39.0s | 0.006150 | primary | `https://api.commandcode.ai/provider/v1` |
| 6 | MiMo V2.6 Pro | commandcode | `xiaomi/mimo-v2.6-pro` | 46.3 | 0.046896 | 58.5s | -0.000596 | primary | `https://api.commandcode.ai/provider/v1` |
| 7 | GPT-6 Luna | commandcode | `gpt-6-luna` | 38.1 | 0.041222 | 107.2s | -0.003122 | primary | `https://api.commandcode.ai/provider/v1` |
| 8 | GPT-6.1 Sol | commandcode | `gpt-6.1-sol` | 51.8 | 0.424542 | 287.4s | -0.372742 | primary | `https://api.commandcode.ai/provider/v1` |
| 9 | MiMo V2.6 Pro UltraSpeed | commandcode | `xiaomi/mimo-v2.6-pro-ultraspeed` | 46.3 | 0.468962 | 58.5s | -0.422662 | primary | `https://api.commandcode.ai/provider/v1` |
| 10 | Gemini 4 Argon | commandcode | `google/gemini-4-argon` | 52.6 | 1.166758 | unknown | -1.114158 | primary | `https://api.commandcode.ai/provider/v1` |


## Flash Lite  ->  `flash-lite-tier`

_Floor 0.00 (0.00x SOTA) · lambda 0.0001 · rho 0.0 → mu 0.0 · pool 74 · 10 deployments · backups 0_

| # | Model | Provider | Model ID | Intel | Cost/task $ | Latency | NMB | Kind | API base |
|---|-------|----------|----------|-------|-------------|--------:|-----|------|----------|
| 1 | MiMo V2.5 | commandcode | `xiaomi/mimo-v2.5` | 21.8 | 0.006871 | 80.0s | -0.004691 | primary | `https://api.commandcode.ai/provider/v1` |
| 2 | MiniMax M2.5 | commandcode | `MiniMaxAI/MiniMax-M2.5` | 22.8 | 0.016650 | 39.0s | -0.014370 | primary | `https://api.commandcode.ai/provider/v1` |
| 3 | MiMo V2.5 Pro | commandcode | `xiaomi/mimo-v2.5-pro` | 26 | 0.019047 | 68.0s | -0.016447 | primary | `https://api.commandcode.ai/provider/v1` |
| 4 | MiMo V2.6 Flash | commandcode | `xiaomi/mimo-v2.6-flash` | 37.9 | 0.022447 | 49.7s | -0.018657 | primary | `https://api.commandcode.ai/provider/v1` |
| 5 | GPT-6 Luna | commandcode | `gpt-6-luna` | 38.1 | 0.041222 | 107.2s | -0.037412 | primary | `https://api.commandcode.ai/provider/v1` |
| 6 | MiMo V2.6 Pro | commandcode | `xiaomi/mimo-v2.6-pro` | 46.3 | 0.046896 | 58.5s | -0.042266 | primary | `https://api.commandcode.ai/provider/v1` |
| 7 | GPT-6.1 Sol | commandcode | `gpt-6.1-sol` | 51.8 | 0.424542 | 287.4s | -0.419362 | primary | `https://api.commandcode.ai/provider/v1` |
| 8 | MiMo V2.6 Pro UltraSpeed | commandcode | `xiaomi/mimo-v2.6-pro-ultraspeed` | 46.3 | 0.468962 | 58.5s | -0.464332 | primary | `https://api.commandcode.ai/provider/v1` |
| 9 | Gemini 4 Argon | commandcode | `google/gemini-4-argon` | 52.6 | 1.166758 | unknown | -1.161498 | primary | `https://api.commandcode.ai/provider/v1` |
| 10 | GPT-6 Astra | commandcode | `gpt-6-astra` | 52.7 | 1.980560 | 299.5s | -1.975290 | primary | `https://api.commandcode.ai/provider/v1` |


## Excluded

**excluded_by_config** (2): commandcode:meta/muse-spark-1.2-contributor, commandcode:meta/muse-spark-1.3-contributor

**unmapped** (10): commandcode:minimax/minimax-m3.1-flash, commandcode:minimax/minimax-m3.1-flash:free, commandcode:Qwen/Qwen3.8-Omni-Flash, commandcode:Qwen/Qwen3.7-Flash, commandcode:tencent/hy4-preview, commandcode:sakana/fugu-ultra, commandcode:nvidia/nemotron-3.5-super-vl, commandcode:stealth/glyph-cluster:free, commandcode:reflection/beam:free, commandcode:poolside/laguna-s-2.1-free
