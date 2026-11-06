# Proposal

## Why

The model pipeline relies on Artificial Analysis (AA) to provide canonical model identities, intelligence scores, and baseline cost benchmarks. To protect the free tier's 100 requests/day rate limit, `AaClient` caches API responses to `output/aa_snapshot.json`.

However, the current caching implementation checks only if the cache file exists, with no expiration time (TTL) or cache invalidation mechanism. Once written, subsequent runs of `fetch`, `refresh`, and `run` indefinitely read the stale snapshot from disk and never query Artificial Analysis, preventing newly released models or score updates from being discovered unless `output/` is manually deleted.

Introducing a configurable cache TTL (defaulting to 6 hours) and a CLI flag (`--no-cache` / `--refresh-aa`) ensures the pipeline automatically keeps canonical data fresh while still respecting rate limits and allowing users to force a fresh fetch on demand.

## What Changes

- Add configurable cache TTL (`cache_ttl_hours: 6`) under the `aa:` block in `config.yaml` and `config.example.yaml`.
- Update `AaClient.fetch_raw()` to verify file modification age against `cache_ttl_hours`; if the cache is older than the TTL, treat it as expired and fetch fresh data from the Artificial Analysis API.
- Add `--no-cache` (aliased or complemented by `--refresh-aa`) flag to `fetch`, `refresh`, and `run` CLI commands in `cli.py` to bypass disk caching and force an API fetch.
- Update `AaClient` and `cli.py` console logs to clearly report whether canonical models were loaded from cache (including file age) or fetched live from the API.
- Add unit tests in `test_aa.py` and `test_cli.py` verifying cache freshness, TTL expiration, and flag behavior.

## Capabilities

### Modified Capabilities
- `model-pipeline`: Update the canonical model fetching and caching requirements to specify time-to-live (TTL) expiration rules and on-demand cache bypass via CLI flags.

## Impact

- Affected files in `model-tier-populator`:
  - `src/model_pipeline/config.py`: Add `cache_ttl_hours` field to `AaConfig`.
  - `src/model_pipeline/scoring/aa.py`: Add TTL verification and cache age logging in `fetch_raw()`.
  - `src/model_pipeline/cli.py`: Add `--no-cache` / `--refresh-aa` CLI arguments to `fetch`, `refresh`, and `run` parsers and pass `use_cache` accordingly.
  - `config.example.yaml` & `config.yaml`: Document `cache_ttl_hours: 6`.
  - `tests/test_aa.py` & `tests/test_cli.py`: Add test cases for TTL expiration and CLI flag handling.
- Zero breaking changes to existing pipeline outputs (`tier-output.json`, `mappings.csv`).
