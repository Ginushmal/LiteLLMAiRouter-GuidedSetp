# AGENTS.md

## What This Project Is

This is an **exploration and study project** for LiteLLM. The goal is to understand how LiteLLM works — step by step — and to turn its convoluted official documentation into something simple, accurate, and hands-on.

We work like this:

1. Read the **official docs** (and the **official source repo** when needed).
2. Run LiteLLM locally (Podman/Docker) and observe real behavior.
3. Log hands-on learnings in **`LiteLLM-Learnings.md`** — our own plain-language concept note.
4. Turn that into a step-by-step setup runbook in **`Setup-Guide.md`** — using only the repo files and the Admin UI (no hand-written API calls).

This is **not** a production app repo. Do not "fix the app" for its own sake — study it, understand it, and document it.

## The Golden Rule: Never Assume

Assume you know **nothing** about LiteLLM. It is a large, fast-moving project and its docs are often incomplete, scattered, or out of date.

- **Do not state anything as fact unless you have verified it** against the official docs or the official source code.
- When a hypothesis about how something works comes to mind, **verify it before saying it** — never present a guess as an answer.
- **Only tell the user a conclusion once it is confirmed.** Investigate → test → then report.
- **Do not hallucinate** endpoints, config keys, environment variables, defaults, or file paths. If you are unsure, say so and go look it up.
- When the docs are ambiguous or silent, **say that explicitly** instead of filling the gap with a plausible-sounding answer.
- For claims about *our running instance*, verify by calling the actual API/UI, reading container logs, or querying the DB — never by reasoning from memory.

## Source-of-Truth Hierarchy

1. **Official docs first** — https://docs.litellm.ai/docs/
2. **Official source code** — https://github.com/BerriAI/litellm
   Use the code **only** when:
   - the docs are confusing or contradictory, **or**
   - you cannot find the answer in the docs, **or**
   - the docs contradict what we actually observe in the running system, **or**
   - you are dealing with a bug that the docs alone cannot explain.
3. **Our running instance** — actual behavior (API responses, logs, DB) overrides theory. When docs and observation disagree, trust the observation, then explain the discrepancy (often a bug — cite the GitHub issue/source).

Never cite a doc or source you did not actually fetch and read.

## Scope: Open Source Only

This project runs and studies the **open-source, self-hosted LiteLLM** (the `litellm` package / Docker image). LiteLLM also has **Enterprise-only** features, and the docs present both tiers side by side.

- Before guiding the user through any feature, **confirm it is available in the open-source version.**
- If a requested task requires an **Enterprise** feature, **say so plainly and stop** — do not hand over steps for something we cannot do, and never present Enterprise features as if they were available to us.
- **Never assume a feature is OSS just because it appears in the docs** — the docs cover both tiers.
- How to check: the docs mark Enterprise features, and the official repo separates OSS code (`litellm/`) from Enterprise code (`enterprise/`). When unsure, verify against the docs/source and state your finding explicitly before guiding.

## The Two Documents

### `LiteLLM-Learnings.md` — Concept Reference
The "how/why it works" note. Structured, comprehensive, but concise. Must serve two readers: a beginner reading top-to-bottom, and an expert jumping straight to a section.

Update it using the skill at:
`.agents/skills/update-litellm-learnings/SKILL.md`

That skill also holds a **self-updating list of official doc sources** — add any new, useful doc page (or source file) there when you use it.

### `Setup-Guide.md` — Step-by-Step Setup
The practical "do this, then this" runbook to stand the stack up, **in the order it was built**. It uses **only the four repo files (`config.yaml`, `docker-compose.quickstart.yml`, `.env`, `custom_cost_map.json`) and the Admin UI — no hand-written API/endpoint calls**; the only shell commands are Podman/Compose. Keep it simple and runnable, and update it whenever the setup steps or config change.

## Working Files

| File | Purpose |
|------|---------|
| `LiteLLM-Learnings.md` | Concept reference (our learning notes) |
| `Setup-Guide.md` | Step-by-step setup runbook (files + Admin UI; no hand-written API calls) |
| `config.yaml` | Model/routing config, heavily commented for learning |
| `docker-compose.quickstart.yml` | Local stack (LiteLLM + Postgres) |
| `custom_cost_map.json` | Self-hosted cost map (full fork of upstream + our prices) |
| `.env` | Secrets — **gitignored, never commit** |
| `.agents/skills/update-litellm-learnings/SKILL.md` | Skill for updating the learnings doc |

## Behavior Expectations

- Be concise and direct. No fluff.
- Keep every claim traceable to a fetched doc, a read source file, or an observed result.
- Prefer "I verified X in `<doc/source>`" over "I think X".
- When investigating, form a hypothesis → **test it** → report only the confirmed reason.
- Don't change or fix the user's config/setup unless explicitly asked — investigate and report first.
- When you do fix something, first understand and confirm the **root cause**, then log the learning in `LiteLLM-Learnings.md`.
- The comments in `config.yaml` are intentional teaching material — preserve them.

## Reference Links

- Official docs: https://docs.litellm.ai/docs/
- Official repo: https://github.com/BerriAI/litellm
- Upstream cost map: https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json
