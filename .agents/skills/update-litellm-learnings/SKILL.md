---
name: Update LiteLLM Learnings
description: Update the project's learning docs — LiteLLM-Learnings.md (concept reference) and Setup-Guide.md (step-by-step setup) — with new concepts, features, corrections, or setup changes. Use when the user asks to add, update, or extend either guide.
---
# Update LiteLLM Docs

When the user asks to update, extend, or correct the project's learning docs, follow these instructions.

Read `AGENTS.md` first. The non-negotiables apply here too: **never assume**, verify every claim against the official docs (source code only when the docs are insufficient), stay within the **open-source** tier, and never present Enterprise-only features as usable.

## Target Files

| File | Role |
|------|------|
| `D:\Softwares\LiteLLMAiRouter\LiteLLM-Learnings.md` | **Learnings / concept reference** — how/why LiteLLM works |
| `D:\Softwares\LiteLLMAiRouter\Setup-Guide.md` | **Step-by-step setup** — files + Admin UI, no hand-written API calls |

A learning usually lands in **both**: the concept goes into `LiteLLM-Learnings.md`, and any new setup step / command goes into `Setup-Guide.md`.

## Shared Rules (both files)

- Every claim must be verified against official docs — never assume or hallucinate.
- When the docs are ambiguous or silent, say so explicitly.
- Use **tables** for comparisons and reference data; **code blocks** for every config/API/CLI example.
- Concise, direct, no fluff.
- Never mix Enterprise-only features in as if they were available in the open-source build.

---

## Updating `LiteLLM-Learnings.md` (Concept Reference)

### Writing Style

The guide must satisfy TWO audiences simultaneously:

1. **Beginners** — Someone who has never heard of LiteLLM should be able to read it top-to-bottom and fully understand all concepts.
2. **Quick Reference** — Someone who already knows the material (the project owner) should be able to jump to any section via headers/tables and quickly re-understand a specific concept.

### Structural Rules

- **Use tables** for comparisons, feature lists, and reference data (not paragraphs of prose)
- **Use code blocks** for every config example, API call, and CLI command
- **Use diagrams** (ASCII art) for architecture and flow explanations
- **Use numbered sections** with clear headers so the Table of Contents stays navigable
- **Keep each section self-contained** — a reader should be able to jump to any section without needing prior context
- **Include "When to use"** guidance for every feature/mode/option presented
- **Include worked examples** for complex behaviors (e.g., routing scenarios with step-by-step flow)
- **Add "Common Pitfalls"** entries when we discover bugs, gotchas, or non-obvious behavior
- **Link to official docs** at the end of each section and in the Quick Reference table

### Adding a New Topic

1. **Determine the section** — does it fit under an existing section, or need a new numbered section?
   - Sub-topic of an existing section (e.g. a new routing strategy) → add it there
   - Major new concept (e.g. Guardrails, Observability) → create a new numbered section
2. **Update the Table of Contents** — add the new section with the correct anchor link
3. **Write the section** following the structural rules above:
   - one-line summary of what it is
   - tables for feature lists/comparisons
   - code blocks for config/CLI examples
   - "When to use" guidance
   - a worked example if the concept is behavioral
   - end with a link to the relevant official doc page
4. **Update the Quick Reference** — add new endpoints/commands/doc links
5. **Update the Summary** — add a bullet if it's a major concept

### Correcting Existing Content

1. **Verify against official docs first** — fetch the relevant page and confirm the correction
2. **Make the minimal change** needed
3. **Note what changed** in your response to the user

### Adding a Common Pitfall

1. Add it to the "Common Pitfalls & Bugs" section
2. Use the format:
   ```
   ### N. [Short title]

   **Problem:** [What goes wrong]
   **Solution:** [How to fix/avoid it]
   ```

---

## Updating `Setup-Guide.md` (Files + Admin UI Runbook)

### What it is

The runnable "do this, then this" guide to stand the stack up from scratch, **in the order the stack was actually built**. It covers the four repo files (`config.yaml`, `docker-compose.quickstart.yml`, `.env`, `custom_cost_map.json`) **and the Admin UI**.

**Core rule: no hand-written API/endpoint calls.** A reader must be able to follow it using only the files and the Admin UI — no `curl`, no hand-crafted HTTP requests. The only shell commands allowed are Podman/Compose commands to run and inspect the stack.

It is the practical counterpart to `LiteLLM-Learnings.md`: keep the *why* in the learnings doc, keep the *do* here.

### Style Rules

- **Chronological, numbered steps** grouped into Parts matching how the stack is built (order below).
- **No API URL calls** — files + Admin UI only. Allowed shell = Podman/Compose (`up`, `down`, `restart`, `up -d --force-recreate`, `logs`, `volume rm`).
- **One action per step** — show the exact file edit, UI navigation, or Podman command.
- Concrete, verified actions over explanation.
- Keep the reference tables accurate (env vars, files, quick commands, Admin UI map).
- Troubleshooting stays short: symptom → cause → fix.

### How to Update It

1. **Verify on the running stack first** — make the file edit, use the UI, run the Podman command. Never document an unverified action.
2. **Edit the relevant step in place** — don't add a parallel/duplicate section.
3. **Keep the Part order intact:**
   `What you end up with → Part 1 bring up the stack (prereqs → compose → .env → run) → Part 2 models + env → Part 3 custom cost map → Part 4 routing (order + routing_groups) → Part 5 identity defaults in config → Part 6 identity in the Admin UI → Applying changes (restart vs recreate) → Troubleshooting → Quick command reference → Roadmap`
4. **Sync the reference tables** whenever config changes.
5. **Mirror new gotchas into Troubleshooting** — keep them aligned with `LiteLLM-Learnings.md`'s Common Pitfalls.
6. **If a config file changed**, update every place the guide quotes it (compose, `config.yaml`, `.env`, cost map).
7. **Update the Roadmap** only if a studied topic suggests a concrete next step.
8. **Note what changed** in your response.

### Do NOT

- Do **not** add hand-written API/endpoint calls (`curl`, raw HTTP). Steps are **files + Admin UI** (+ Podman commands) only.
- Do not include **Enterprise-only** steps.
- Do not document an action you have not confirmed works.
- Do not let `Setup-Guide.md` drift from the actual files — **re-read them** when in doubt.

---

## Verification Checklist

Before finishing any update, verify:

- [ ] All claims verified against official LiteLLM docs (fetched, not assumed)
- [ ] Feature is available in the **open-source** tier (not Enterprise-only)
- [ ] **LiteLLM-Learnings.md:** Table of Contents updated if sections added
- [ ] **LiteLLM-Learnings.md:** Quick Reference and Summary updated if applicable
- [ ] **LiteLLM-Learnings.md:** pitfalls reflect confirmed root causes
- [ ] **Setup-Guide.md:** no hand-written API/endpoint calls (files + Admin UI + Podman only)
- [ ] **Setup-Guide.md:** every new action was actually performed and works
- [ ] **Setup-Guide.md:** step numbering and Part order intact
- [ ] **Setup-Guide.md:** reference tables (env vars, files, commands, UI map) still accurate
- [ ] Code examples are syntactically valid YAML/bash
- [ ] Consistent formatting with existing sections (tables, code blocks, headers)
- [ ] Sections are self-contained (readable without prior context)

## Official Doc Sources

Always fetch and verify against these official sources before writing:

**IMPORTANT: Self-Updating Doc List** — When running this skill, if you fetch and use any NEW official documentation page (or source file) that isn't listed below, add it to this table as a side effect. Only add sources that were actually useful and relevant. This keeps the reference list current as we explore more of LiteLLM.

| Topic | URL |
|-------|-----|
| Docker Quick Start | https://docs.litellm.ai/docs/proxy/docker_quick_start |
| config.yaml Reference | https://docs.litellm.ai/docs/proxy/configs |
| Config Settings | https://docs.litellm.ai/docs/proxy/config_settings |
| Routing | https://docs.litellm.ai/docs/routing |
| Load Balancing | https://docs.litellm.ai/docs/proxy/load_balancing |
| Virtual Keys | https://docs.litellm.ai/docs/proxy/virtual_keys |
| Users & Budgets | https://docs.litellm.ai/docs/proxy/users |
| Custom Pricing | https://docs.litellm.ai/docs/proxy/custom_pricing |
| Custom Cost Map | https://docs.litellm.ai/docs/proxy/custom_model_cost_map |
| Production Deployment | https://docs.litellm.ai/docs/proxy/deploy |
| Admin UI | https://docs.litellm.ai/docs/proxy/ui |
| Model Management | https://docs.litellm.ai/docs/proxy/model_management |
| Service Accounts | https://docs.litellm.ai/docs/proxy/service_accounts |
| Access Control (RBAC) | https://docs.litellm.ai/docs/proxy/access_control |
| Model Access (restrict by key/team) | https://docs.litellm.ai/docs/proxy/model_access |
| Model Access Groups | https://docs.litellm.ai/docs/proxy/model_access_groups |
| Key-Based Auth (model resolution) | https://docs.litellm.ai/docs/proxy/key_auth_arch |
| Internal User Self-Serve | https://docs.litellm.ai/docs/proxy/self_serve |
| Multi-Tenant Architecture | https://docs.litellm.ai/docs/proxy/multi_tenant_architecture |
| Cost Map (JSON) | https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json |
| Cost Calculator (source, for exact lookup behavior) | https://raw.githubusercontent.com/BerriAI/litellm/main/litellm/cost_calculator.py |

## Current Structure

### `LiteLLM-Learnings.md`

1. What is LiteLLM?
2. Architecture & Components
3. Operating Modes
4. config.yaml Deep Dive
5. Docker Deployment
6. Model Configuration
7. Pricing & Cost Tracking
8. Routing & Load Balancing
9. Virtual Keys, Teams & Users
10. Admin UI
11. Production Considerations
12. Common Pitfalls & Bugs
13. Quick Reference

### `Setup-Guide.md`

Chronological runbook — files + Admin UI only (no hand-written API calls):

1. What you end up with (stack + files)
2. Part 1 — Bring the stack up (prerequisites → `docker-compose.quickstart.yml` → `.env` → run in Podman)
3. Part 2 — Models + provider wiring (`config.yaml` `model_list` + Compose env)
4. Part 3 — Custom cost map (build the file + verify pricing in the UI)
5. Part 4 — Routing (`order` failover + `routing_groups`)
6. Part 5 — Identity defaults in `config.yaml` (default/upperbound key + team params)
7. Part 6 — Identity in the Admin UI (teams → users → keys → test/spend)
8. Applying changes: restart vs. recreate
9. Troubleshooting
10. Quick command reference (Podman + Admin UI map)
11. Roadmap: what to study next
