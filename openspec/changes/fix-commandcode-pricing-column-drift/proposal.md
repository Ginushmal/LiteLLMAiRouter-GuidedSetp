# Proposal

## Why

The CommandCode pricing scraper reads price cells by fixed column position, assuming the models page table is `Model | Context | Intelligence | Input | Output | Cache read | Cache write | Caps`. Between the 2026-11-09 and 2026-11-18 fetches, CommandCode removed the Intelligence column (verified in the saved raw HTML under `model-tier-populator/data/raw/commandcode/`), shifting every price one slot left. The parser silently stored **output prices as input, cache-read prices as output, cache-write prices as cache-read**, and dropped real input prices entirely — e.g. Kimi K3.1 Pro recorded as input $10.00 / output $0.20 instead of $2.00 / $10.00, and Qwen 4 Max as $4.50 / $0.075 instead of $1.50 / $4.50. Every CommandCode deployment in the latest run carries inverted economics, corrupting cost-per-task, NMB ranking, tier selection, and the prices destined for LiteLLM's spend tracking — with provenance still stamped `"provider"`, so nothing downstream flagged it.

## What Changes

- Replace positional cell indexing in `parse_commandcode_pricing()` with **header-driven column mapping**: read the table's header row, locate the Model / Input / Output / Cache read / Cache write columns by their header text, and read prices from those indices.
- **Fail loudly on schema drift**: if the header row is missing or any required price column cannot be located, raise an error naming the missing columns (mirroring the existing loud failure in `parse_commandcode_plans`), instead of silently producing shifted or empty prices.
- Keep all existing price-cell semantics unchanged: effective (last) dollar figure for discounted rows, `Free` → 0.0, dash → `None`, plan markers (`+ 1`) ignored, name/slug dual keying.
- Update the CommandCode test fixtures to emit real header rows and add regression coverage for both the historical 8-column layout and the current 7-column layout, plus the loud-failure paths.
- Update the adapter docstring, which currently documents the stale 8-column layout as fact.
- Operational follow-up (no code): re-run fetch → score → populate so corrected prices replace the corrupted artifacts and any already-synced LiteLLM deployments converge via the existing idempotent populate.

Out of scope: the OpenCode adapter uses the same positional-indexing pattern but its page has not drifted; hardening it is a separate change. No cross-provider sanity heuristics (e.g. "output < input" warnings) are added — header mapping plus loud failure removes the failure mode at its root.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `model-pipeline`: the "Multi-provider model fetching" requirement gains a new scenario specifying that HTML-table pricing extraction SHALL map columns by header text (not fixed position) and SHALL fail the fetch loudly when expected columns are absent, so a provider page layout change can never silently shift prices between fields.

## Impact

- **Code**: `model-tier-populator/src/model_pipeline/providers/commandcode.py` (`parse_commandcode_pricing`, module docstring); `model-tier-populator/tests/test_commandcode.py` (fixtures + new regression tests).
- **Behavior**: a CommandCode page whose table lacks recognizable price headers now aborts the fetch phase with a clear error (previously: silent corruption or silent empty pricing). Correct-layout pages parse identically to before.
- **Data**: `models_snapshot.json`, `tier-output.json`, reports, and suggested LiteLLM configs from the 2026-11-18 run contain wrong CommandCode prices and must be regenerated; if populate already ran, LiteLLM `input_cost_per_token` / `output_cost_per_token` / cache costs for CommandCode deployments are wrong until re-populated.
- **No API/interface changes**: `fetch_pricing()` signature, `ResolvedPricing` shape, and downstream consumers are untouched.