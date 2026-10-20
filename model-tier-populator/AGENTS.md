# AGENTS.md — model-pipeline

Engineering rules for the pipeline tool in this directory. The root `AGENTS.md`
still applies to claims about LiteLLM; this file governs how code here is built.
Run `README.md` + `WALKTHROUGH.md` are the behavior reference.

## Principles

- **Modular & vendor-agnostic.** Provider-specific knowledge (URLs, auth quirks,
  HTML shapes, endpoint protocols, LiteLLM payload rules) lives only in
  `providers/`. Nothing outside `providers/` may branch on a provider name.
- **Config is the control plane.** Operating the pipeline (providers on/off,
  URLs, pricing policy, tiers, exclusions, paths) must require `config.yaml`
  edits only. Policy = config; parsing mechanics = adapter code. Secrets are
  referenced by env-var name only, never inlined.
- **Phases communicate only through artifacts** (fetch → `output/`, score →
  `tier-output.json`, populate → LiteLLM). Never couple phases in memory.
- **Never invent data.** Missing price/limit/mapping stays missing and flagged
  (existing `provenance` / `limits_flags` pattern). Low-confidence mappings stay
  visible for human review — never auto-accept them.

## Changing a scraper when a provider changes its page

1. Diagnose from evidence: newest entry in `data/logs/<provider>/` and its raw
   body in `data/raw/<provider>/`. Never guess the new markup.
2. Add a failing parser test from the captured body, then fix **only** that
   provider's adapter. Parsers stay pure functions (text in → data out).
3. A non-empty page that parses to zero rows is a schema change, not an empty
   catalog: log it and fail the phase instead of returning `{}`.
4. Don't loosen dedup/scoring/limits to compensate for a broken scrape.

## Adding a provider

1. `config.yaml`: `providers:` block (models/pricing URLs, key env, LiteLLM api
   bases, `supported_endpoints`, `models_dev_provider_ids`).
2. `src/model_pipeline/providers/<name>.py` implementing `ProviderAdapter`.
3. Register it in `providers/registry.py`.
4. Tests: model parsing, pricing parsing, deployment payload, unsupported
   protocol excluded (never silently routed as chat).
5. Everything downstream (dedup, scoring, emit, populate) must work unchanged.
   If it doesn't, fix the adapter seam — don't special-case downstream.

## Logging & errors (so an AI agent can debug from artifacts)

Every run must be diagnosable from `data/logs/`, `data/raw/`, and `output/`
alone. Keep the existing `ScrapeRecorder` JSONL layout and field names.

- Save the raw body **before** parsing, so a failing parse is reproducible.
- Log one JSON line per call: timestamp, source/provider, url, status,
  `parsed_count`, and `error` (exception type + message, plus expected vs
  observed shape). Never log secrets or auth headers.
- Fail loudly at boundaries; never swallow exceptions. A phase that ends
  partially failed exits non-zero and says so — no silent empty success.
- End each phase with a summary (counts, warnings, next command).

## Verify after every change

This is a fully agent-coded tool — nothing is "done" unverified.

- Tests for every change; bug fixes get a regression test that failed before.
- Tests are offline (fixtures + fakes, see `tests/test_sync.py`). No live
  provider or LiteLLM calls; `populate --dry-run` only when a smoke check is
  needed.
- Run from `model-pipeline/`:
  ```bash
  uv run --with pytest pytest tests/
  uv run --with ruff ruff check src tests
  uv run model-pipeline --help
  ```
- Ruff is not pinned in `pyproject.toml` yet — run it ephemerally; if it can't
  run, say so, never claim "lint clean" without output.
- Never weaken or delete a failing test to get green.

## Talking to the developer

The developer knows the high-level architecture, logic, and requirements —
not code.

- Report at behavior/contract/risk level: what changed, why, what was verified.
- Don't paste code, diffs, or stack traces; don't discuss syntax, types, or
  library choices. Decide low-level implementation yourself.
- Ask only when a requirement or external contract is ambiguous; give 2–3
  options with consequences.
- State plainly when anything externally visible changes (config key, artifact
  field, CLI, log format).
- Never claim unverified results.
