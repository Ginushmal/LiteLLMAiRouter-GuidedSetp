# Proposal: Provider Model Mapping Overrides

## Why

Some providers name models ambiguously or serve updated model versions under generic/older model IDs (for example, CommandCode serves `deepseek-v4-1-flash-1017` under the name `deepseek/deepseek-v4.1-flash`, which the automated deduplication mapper naively matches to the older `deepseek-v4-1-flash` canonical slug).

Currently, correcting such discrepancies requires a two-step human review workflow: running `fetch`, manually editing `output/mappings.csv` to add an override, and then running `score`. However, re-running `fetch` or using the single-command `refresh` (`fetch` -> `score`) completely overwrites `mappings.csv`, erasing manual edits every time. Users need a persistent way in `config.yaml` to specify manual model mappings per provider that apply automatically across every fetch, score, and refresh run.

## What Changes

- Add an optional `model_mappings` dictionary to `ProviderConfig` (under `providers.<provider>.model_mappings` in `config.yaml`), mapping provider `model_id` strings to canonical Artificial Analysis slugs (e.g. `"deepseek/deepseek-v4.1-flash": "deepseek-v4-1-flash-1017"`).
- Update the deduplication mapper (`map_models` in `src/model_pipeline/dedup/mapper.py`) to check provider-configured `model_mappings` before attempting exact matching or Jev classification.
- When an override matches:
  - Resolve the canonical identity from the canonical models catalog.
  - Record the mapping with `method="override"`, `confidence=1.0`, and populate `override` and `canonical_slug` with the target slug.
  - Warn or raise an informative error if a configured target canonical slug does not exist in the Artificial Analysis catalog.
- Update `config.example.yaml` and `config.py` to document, validate, and load `model_mappings`.
- Ensure `write_mappings` persists the configured override into `output/mappings.csv` so the CSV accurately reflects the mapping source and confidence.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `model-pipeline`: Update the Canonical Model Deduplication requirement to support provider-configured model mapping overrides taking precedence over automated exact matching and Jev classification.

## Impact

- **Configuration**: `config.yaml` and `config.example.yaml` under `providers.<provider>` gain the optional `model_mappings` map.
- **Deduplication Engine**: `src/model_pipeline/config.py`, `src/model_pipeline/dedup/mapper.py`, and `src/model_pipeline/models.py`.
- **Workflow**: `fetch`, `score`, and `refresh` now automatically respect persistent mappings without requiring manual post-fetch CSV edits.
