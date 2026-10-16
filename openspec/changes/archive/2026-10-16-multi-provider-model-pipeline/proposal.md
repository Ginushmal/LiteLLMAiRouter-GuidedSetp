# Proposal

## Why

The current LiteLLM setup uses a single provider (CommandCode) with model tiers manually defined in `config.yaml`. Updating tiers, prices, or model membership requires editing the file and restarting the container. We need a reusable, schedulable Python pipeline that fetches models from multiple providers (CommandCode GOAT, OpenCode Go), deduplicates them to canonical names, scores them by intelligence and cost-efficiency, and populates LiteLLM's database dynamically via its management API — with no restarts and no config file edits.

## What Changes

- **New Python sub-project** (`model-pipeline/`) — a standalone, reusable package (not a one-off script) with three independently invocable phases: `fetch`, `score`, `populate`.
- **Provider adapters** (Strategy pattern) for CommandCode and OpenCode that fetch model lists and pricing from each provider's API and documentation pages, handle context-tiered/peak-off-peak/discounted pricing, and generate correct LiteLLM deployment parameters per provider endpoint format.
- **Canonical model dedup** mapping provider model names to Artificial Analysis canonical identities using exact matching first, then the Jev (TypeSafe) Choice classifier for ambiguous cases. Mapping results are persisted to a human-reviewable CSV checkpoint.
- **Cost-per-task computation** that captures model efficiency (from AA's benchmark data) and provider-specific pricing with cache adjustment. Three strategies: AA Pro per-token re-price, AA free-tier effective-token derivation with cache, and fixed task-profile fallback.
- **Model ranking** using Pareto frontier (canonical level), SOTA-relative tier assignment, and NMB (Net Monetary Benefit) top-K selection at the deployment level with same-price grouping.
- **Self-contained JSON output** (`tier-output.json`) carrying all fields needed for LiteLLM population — serving as a re-populatable checkpoint.
- **Idempotent LiteLLM population** via the management API (`/model/new`, `/model/update`, `/model/delete`, `/config/update`) that diffs desired state against current state and applies only changes.
- **Structured scraping logs** and saved raw artifacts for every fetch, enabling AI-assisted debugging when provider page structures change.

## Capabilities

### New Capabilities
- `model-pipeline`: End-to-end pipeline for fetching LLM provider catalogs, deduplicating model names to canonical identities, computing intelligence-weighted cost scores, ranking models into tiers, and populating a LiteLLM router via its management API.

### Modified Capabilities

(none — this is a greenfield capability)

## Impact

- **New sub-project**: `model-pipeline/` directory with its own `pyproject.toml`, Python 3.10+ package.
- **External APIs**: Artificial Analysis Data API (free tier), TypeSafe Jev API (`api.typesafe.ai/v1/systemone`), CommandCode Provider API (`api.commandcode.ai/provider/v1`), OpenCode Go API (`opencode.ai/inference/go/v1`).
- **LiteLLM integration**: Uses existing management API endpoints (already verified working with `store_model_in_db: true`). No changes to `config.yaml`, `docker-compose.yml`, or `.env` required. The existing `custom_cost_map.json` becomes unnecessary for pipeline-managed models (pricing is injected per-deployment via the API).
- **Dependencies**: `typesafe-sdk` (Python), `httpx` or `requests`, optional `rapidfuzz` for pre-filter heuristics.
- **Existing temp scripts** (`smart_router.py`, `update_cost_map.mjs`) remain as references but are not modified or extended.
