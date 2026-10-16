# Model pipeline — tier suggestions

_Generated: 2026-10-16T06:02:39+00:00_

**SOTA intelligence:** 57.6

**Cost methods:** aa_free=21, task_profile=2


## Ultra  ->  `ultra-tier`

_Floor 46.08 (0.80x SOTA) · lambda 1.0 · pool 14 · 5 deployments · backups 0_

| # | Model | Provider | Model ID | Intel | Cost/task $ | NMB | Kind | API base |
|---|-------|----------|----------|-------|-------------|-----|------|----------|
| 1 | Claude Opus 5.5 | commandcode | `claude-opus-5-5` | 57.6 | 3.506781 | 54.093219 | primary | `https://api.commandcode.ai/provider` |
| 2 | Claude Sonnet 5.5 | commandcode | `claude-sonnet-5-5` | 56 | 3.201301 | 52.798699 | primary | `https://api.commandcode.ai/provider` |
| 3 | Gemini 4 Argon | commandcode | `google/gemini-4-argon` | 52.6 | 1.166758 | 51.433242 | primary | `https://api.commandcode.ai/provider/v1` |
| 4 | GPT-6.1 Sol | commandcode | `gpt-6.1-sol` | 51.8 | 0.424542 | 51.375458 | primary | `https://api.commandcode.ai/provider/v1` |
| 5 | GPT-6 Astra | commandcode | `gpt-6-astra` | 52.7 | 1.980560 | 50.719440 | primary | `https://api.commandcode.ai/provider/v1` |


## Pro  ->  `pro-tier`

_Floor 34.56 (0.60x SOTA) · lambda 0.2 · pool 40 · 5 deployments · backups 0_

| # | Model | Provider | Model ID | Intel | Cost/task $ | NMB | Kind | API base |
|---|-------|----------|----------|-------|-------------|-----|------|----------|
| 1 | GPT-6.1 Sol | commandcode | `gpt-6.1-sol` | 51.8 | 0.424542 | 9.935458 | primary | `https://api.commandcode.ai/provider/v1` |
| 2 | Gemini 4 Argon | commandcode | `google/gemini-4-argon` | 52.6 | 1.166758 | 9.353242 | primary | `https://api.commandcode.ai/provider/v1` |
| 3 | MiMo V2.6 Pro | commandcode | `xiaomi/mimo-v2.6-pro` | 46.3 | 0.046896 | 9.213104 | primary | `https://api.commandcode.ai/provider/v1` |
| 4 | mimo-v2.6-pro | opencode | `mimo-v2.6-pro` | 46.3 | 0.046901 | 9.213099 | primary | `https://opencode.ai/inference/go/v1` |
| 5 | MiMo V2.6 Pro UltraSpeed | commandcode | `xiaomi/mimo-v2.6-pro-ultraspeed` | 46.3 | 0.468962 | 8.791038 | primary | `https://api.commandcode.ai/provider/v1` |


## Flash  ->  `flash-tier`

_Floor 20.16 (0.35x SOTA) · lambda 0.005 · pool 70 · 6 deployments · backups 0_

| # | Model | Provider | Model ID | Intel | Cost/task $ | NMB | Kind | API base |
|---|-------|----------|----------|-------|-------------|-----|------|----------|
| 1 | MiMo V2.6 Pro | commandcode | `xiaomi/mimo-v2.6-pro` | 46.3 | 0.046896 | 0.184604 | primary | `https://api.commandcode.ai/provider/v1` |
| 2 | mimo-v2.6-pro | opencode | `mimo-v2.6-pro` | 46.3 | 0.046901 | 0.184599 | primary | `https://opencode.ai/inference/go/v1` |
| 3 | MiMo V2.6 Flash | commandcode | `xiaomi/mimo-v2.6-flash` | 37.9 | 0.022447 | 0.167053 | primary | `https://api.commandcode.ai/provider/v1` |
| 3 | mimo-v2.6-flash | opencode | `mimo-v2.6-flash` | 37.9 | 0.022447 | 0.167053 | primary | `https://opencode.ai/inference/go/v1` |
| 4 | GPT-6 Luna | commandcode | `gpt-6-luna` | 38.1 | 0.041222 | 0.149278 | primary | `https://api.commandcode.ai/provider/v1` |
| 5 | MiMo V2.5 Pro | commandcode | `xiaomi/mimo-v2.5-pro` | 26 | 0.019047 | 0.110953 | primary | `https://api.commandcode.ai/provider/v1` |


## Flash Lite  ->  `flash-lite-tier`

_Floor 0.00 (0.00x SOTA) · lambda 0.0005 · pool 75 · 7 deployments · backups 0_

| # | Model | Provider | Model ID | Intel | Cost/task $ | NMB | Kind | API base |
|---|-------|----------|----------|-------|-------------|-----|------|----------|
| 1 | MiMo V2.5 | commandcode | `xiaomi/mimo-v2.5` | 21.8 | 0.006871 | 0.004029 | primary | `https://api.commandcode.ai/provider/v1` |
| 1 | mimo-v2.5 | opencode | `mimo-v2.5` | 21.8 | 0.006871 | 0.004029 | primary | `https://opencode.ai/inference/go/v1` |
| 2 | hy3 | opencode | `hy3` | 22.7 | 0.012740 | -0.001390 | primary | `https://opencode.ai/inference/go/v1` |
| 3 | MiMo V2.6 Flash | commandcode | `xiaomi/mimo-v2.6-flash` | 37.9 | 0.022447 | -0.003497 | primary | `https://api.commandcode.ai/provider/v1` |
| 3 | mimo-v2.6-flash | opencode | `mimo-v2.6-flash` | 37.9 | 0.022447 | -0.003497 | primary | `https://opencode.ai/inference/go/v1` |
| 4 | MiniMax M2.5 | commandcode | `MiniMaxAI/MiniMax-M2.5` | 22.8 | 0.016650 | -0.005250 | primary | `https://api.commandcode.ai/provider/v1` |
| 5 | MiMo V2.5 Pro | commandcode | `xiaomi/mimo-v2.5-pro` | 26 | 0.019047 | -0.006047 | primary | `https://api.commandcode.ai/provider/v1` |


## Excluded

**excluded_by_config** (3): commandcode:meta/muse-spark-1.2-contributor, commandcode:meta/muse-spark-1.3-contributor, opencode:gemini-4-argon-contributor

**unmapped** (12): commandcode:Qwen/Qwen3.8-Omni-Flash, commandcode:Qwen/Qwen3.7-Flash, commandcode:tencent/hy4-preview, commandcode:sakana/fugu-ultra, commandcode:nvidia/nemotron-3.5-super-vl, commandcode:stealth/glyph-cluster:free, commandcode:stealth/cat-jam:free, commandcode:poolside/laguna-s-2.1-free, opencode:hy4-preview, opencode:space-bunny, opencode:longcat-2.5-preview-free, opencode:cat-jam-free
