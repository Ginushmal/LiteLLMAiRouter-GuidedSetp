# Tasks

## 1. Configuration Schema & Loading

- [x] 1.1 Add `model_mappings` to `ProviderConfig` in `src/model_pipeline/config.py`, normalising string pairs and defaulting to an empty dict, and verify with tests in `tests/test_config.py`.
- [x] 1.2 Document `model_mappings` in `config.example.yaml` under `providers` with usage comments and example mapping for CommandCode DeepSeek models, verifying config loads cleanly.

## 2. Deduplication Engine Overrides

- [x] 2.1 Update `map_models` in `src/model_pipeline/dedup/mapper.py` to check provider `model_mappings` before exact matching and Jev classification, setting `method="override"`, `confidence=1.0`, and stamping `canonical_slug` and `override`.
- [x] 2.2 Add catalog slug validation in `map_models` to verify that target slugs exist in the loaded canonical models, warning to stderr and falling back to unmapped on unknown slugs.
- [x] 2.3 Add comprehensive unit tests in `tests/test_dedup.py` verifying override precedence over exact matches, handling of unknown slugs, and CSV output propagation via `pytest`.

## 3. Verification & Integration

- [x] 3.1 Run the full test suite (`pytest`) in `model-tier-populator` and verify all tests pass with zero regressions.
- [x] 3.2 Configure the CommandCode `deepseek/deepseek-v4.1-flash` -> `deepseek-v4-1-flash-1017` override in `config.yaml` and verify `map_models` outputs the expected mapping row.
