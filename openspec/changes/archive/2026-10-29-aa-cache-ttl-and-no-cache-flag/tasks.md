# Tasks

## 1. Configuration & Data Model

- [x] 1.1 Add `cache_ttl_hours: float = 6.0` to `AaConfig` in `src/model_pipeline/config.py` and ensure `load_config` loads it with a default of 6.0 hours. Verify with `pytest tests/test_config.py`.
- [x] 1.2 Update `config.example.yaml` and `config.yaml` to include and document `cache_ttl_hours: 6` under the `aa:` configuration block.

## 2. TTL Expiration & Transparent Logging in AaClient

- [x] 2.1 Implement TTL verification in `AaClient.fetch_raw()` in `src/model_pipeline/scoring/aa.py` using `cache_path.stat().st_mtime` compared to current time, invalidating the cache when age exceeds `cfg.aa.cache_ttl_hours * 3600`.
- [x] 2.2 Add informative stdout logging in `AaClient` indicating whether models were loaded from disk cache (including approximate cache age) or fetched fresh from the API.

## 3. CLI Arguments for Cache Bypass

- [x] 3.1 Add `--no-cache` and `--refresh-aa` flags to the `fetch`, `refresh`, and `run` parsers in `src/model_pipeline/cli.py:build_parser()`.
- [x] 3.2 Update `cmd_fetch()` in `src/model_pipeline/cli.py` to evaluate the CLI flag and pass `use_cache=not (args.no_cache or getattr(args, "refresh_aa", False))` to `AaClient.canonical_models()`.

## 4. Testing & Verification

- [x] 4.1 Add unit tests in `tests/test_aa.py` covering: cache hit within TTL, cache expiration beyond TTL triggering an API call, and explicit `use_cache=False` bypass.
- [x] 4.2 Add CLI parser tests in `tests/test_cli.py` verifying `--no-cache` and `--refresh-aa` flags on `fetch`, `refresh`, and `run`.
- [x] 4.3 Run all tests with `uv run --with pytest pytest tests/` and verify that the full test suite passes.
