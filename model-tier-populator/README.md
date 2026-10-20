# model-pipeline

A reusable pipeline that keeps a [LiteLLM](https://docs.litellm.ai/) router
stocked with an **up-to-date, provider-specific tier list of models**.

It fetches the model catalogs of multiple LLM providers, de-duplicates them to a
single canonical identity, scores each model by intelligence and cost-efficiency,
ranks them into tiers, and pushes the result into LiteLLM's database via its
management API — no config edits, no restarts.

```
  providers            canonical hub        score & rank        populate
  ─────────            ─────────────        ────────────        ────────
  CommandCode  ──┐                          Pareto (advisory)   LiteLLM
  OpenCode     ──┼──▶ Artificial Analysis ──▶ SOTA tiers   ──▶  /model/new
  (more later)   │    (intelligence+price)   NMB top-K          (idempotent)
                 └──▶ Jev classifier                     
                      (name matching)
```

Tiers map to LiteLLM model groups that a complexity router can route to:

| Tier | LiteLLM model group |
|------|---------------------|
| Ultra | `ultra-tier` |
| Pro | `pro-tier` |
| Flash | `flash-tier` |
| Flash Lite | `flash-lite-tier` |

## Why

Editing `config.yaml` and restarting LiteLLM to change models is slow and manual.
This pipeline makes the tier list **programmatic, repeatable, and schedulable**,
and keeps it in the database where it can be updated without a restart.

## How it works (three independent phases)

```
  fetch  ──▶  output/mappings.csv   (review gate)   ──▶  score  ──▶  output/tier-output.json   (review gate)  ──▶  populate
```

Each phase reads/writes files, so any phase can be re-run on its own:

- **fetch** — pull provider catalogs + prices, map each model to an Artificial
  Analysis canonical identity (exact match first, then the Jev classifier), and
  write `mappings.csv` for a human to review/fix.
- **score** — compute a cost-per-task per model, mark the Pareto frontier, assign
  SOTA-relative tiers, rank by NMB, and write `tier-output.json`.
- **populate** — diff the desired tier list against LiteLLM's current models and
  apply only the changes. Re-running is safe (idempotent).

## Requirements

- Python 3.10+ and [`uv`](https://docs.astral.sh/uv/)
- A running LiteLLM proxy with `store_model_in_db: true` (already set in this repo)
- Keys in the **repo-root `.env`** (`D:\Softwares\LiteLLMAiRouter\.env`):

  | Key | Used for |
  |-----|----------|
  | `COMMANDCODE_API_KEY` | CommandCode models + the Jev classifier |
  | `OPENCODE_API_KEY` | OpenCode models |
  | `ARTIFICIAL_ANALYSIS_API_KEY` | canonical identity + intelligence scores |
  | `LITELLM_MASTER_KEY` | LiteLLM management API |

  The LiteLLM container must also receive `OPENCODE_API_KEY` (already added to
  `docker-compose.yml`).

## Quick start

Run from the `model-pipeline/` directory:

```bash
uv sync                                   # install deps (once)

uv run model-pipeline fetch               # 1. fetch + dedup  -> output/mappings.csv
#   review output/mappings.csv ; fix any 'override' cells for low-confidence rows

uv run model-pipeline score               # 2. rank           -> output/tier-output.json
#   review output/tier-output.json

uv run model-pipeline populate --dry-run  # 3a. preview the diff
uv run model-pipeline populate            # 3b. apply to LiteLLM
```

## Outputs (`output/`)

| File | What it is |
|------|------------|
| `mappings.csv` | provider model -> canonical model, with method + confidence + `override` column |
| `models_snapshot.json` | fetched provider models + normalized prices (lets `score` run offline) |
| `aa_snapshot.json` | cached Artificial Analysis models list |
| `suggested_config.yaml` | task-profile values suggested from provider docs (advisory) |
| `tier-output.json` | **the tier list** — self-contained; all `populate` needs |
| `tier-output.md` | same result as a readable table |

## Configuration

Everything is in [`config.yaml`](config.yaml) — task profile, NMB tuning
(tier lambdas/floors, top-K), pricing policy, providers, exclusions, pins, and the
tier→model-group mapping. Each setting has an inline comment explaining what it
is and when to change it. Nothing is hardcoded in the source.

`exclude` has two scopes: `patterns` drops a model from every tier before
ranking, while `tiers` drops it from one named tier only and leaves it available
to the others. Global patterns always win.

`pins.tiers` is the opposite control: an ordered list of canonical slugs
force-included at the top of a tier, ahead of NMB selection. Pins bypass the
tier's intelligence floor, consume top-K slots, and never override an exclusion.
Unknown, duplicate, or excluded slugs produce warnings and are skipped.

## Provider support

| Provider | chat | messages | responses | google |
|----------|:----:|:--------:|:---------:|:------:|
| CommandCode | yes | yes | — | — |
| OpenCode | yes | yes | deferred | deferred |

"Deferred" protocols (OpenCode `responses`/`google`) need extra LiteLLM wiring,
so those models are excluded from tiers for now.

## Docs

- **[WALKTHROUGH.md](WALKTHROUGH.md)** — architecture, phases, data model, and
  the scoring/NMB algorithm in detail.
- Run `uv run --with pytest pytest tests/` for the unit tests.
