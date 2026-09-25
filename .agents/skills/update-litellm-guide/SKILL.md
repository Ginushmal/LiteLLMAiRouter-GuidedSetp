---
name: Update LiteLLM Guide
description: Update the LiteLLM-Guide.md document with new concepts, features, or corrections as we learn them. Use when the user asks to add, update, or extend the guide.
---
# Update LiteLLM Guide

When the user asks to update, extend, or add new topics to `LiteLLM-Guide.md`, follow these instructions.

## Target File

`D:\Softwares\LiteLLMAiRouter\LiteLLM-Guide.md`

## Writing Style Requirements

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

### Tone

- Concise, direct, no fluff
- Technical but accessible
- Every claim must be verified against official docs — never assume or hallucinate
- When docs are ambiguous, say so explicitly

## How to Extend the Guide

### Adding a New Topic

1. **Determine the section** — Does it fit under an existing section, or does it need a new numbered section?
   - If it's a sub-topic of an existing section (e.g., a new routing strategy), add it there
   - If it's a major new concept (e.g., Guardrails, Observability, SSO), create a new numbered section

2. **Update the Table of Contents** — Add the new section with correct anchor link

3. **Write the section** following the structural rules above:
   - Start with a one-line summary of what this is
   - Use tables for feature lists and comparisons
   - Use code blocks for all config/CLI examples
   - Include "When to use" guidance
   - Include a worked example if the concept is behavioral
   - End with a link to the relevant official doc page

4. **Update the Quick Reference** — If the new topic has API endpoints, CLI commands, or doc links, add them to section 13

5. **Update the Summary** — Add a bullet to the Summary section at the bottom if it's a major concept

### Correcting Existing Content

1. **Verify against official docs first** — Fetch the relevant doc page and confirm the correction
2. **Make the minimal change** needed
3. **Note what changed** in your response to the user

### Adding a Common Pitfall

1. Add it to section 12 (Common Pitfalls & Bugs)
2. Use the format:
   ```
   ### N. [Short title]
   
   **Problem:** [What goes wrong]
   **Solution:** [How to fix/avoid it]
   ```

## Verification Checklist

Before finishing any update, verify:

- [ ] All claims verified against official LiteLLM docs (fetched, not assumed)
- [ ] Table of Contents updated if new sections added
- [ ] Quick Reference section updated if new endpoints/commands/docs added
- [ ] Summary section updated if major concept added
- [ ] Code examples are syntactically valid YAML/bash
- [ ] No broken anchor links in Table of Contents
- [ ] Consistent formatting with existing sections (tables, code blocks, headers)
- [ ] Section is self-contained (readable without prior context)

## Official Doc Sources

Always fetch and verify against these official sources before writing:

**IMPORTANT: Self-Updating Doc List** — When running this skill to update the guide, if you fetch and use any NEW official documentation pages that aren't listed below, add them to this table as a side effect. This keeps the reference list current as we explore more of LiteLLM. Only add pages that were actually useful and relevant to the guide content.

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
| Cost Map (JSON) | https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json |
| Cost Calculator (source, for exact lookup behavior) | https://raw.githubusercontent.com/BerriAI/litellm/main/litellm/cost_calculator.py |

## Current Guide Structure

The guide currently has these sections (for reference when deciding where to add new content):

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
