# Design

## Context

`AaClient` in `src/model_pipeline/scoring/aa.py` interacts with Artificial Analysis to pull the canonical model catalog. To prevent hitting the free-tier 100 requests/day limit, it serializes responses into `output/aa_snapshot.json`.

Currently, `fetch_raw()` reuses `output/aa_snapshot.json` indefinitely as long as `self.cache_path.exists()` is true. `cmd_fetch`, `cmd_refresh`, and `cmd_run` do not pass `use_cache=False`, so cached data is never refreshed unless the user manually deletes the file or folder.

See `proposal.md` for motivation and `specs/model-pipeline/spec.md` for requirements.

## Goals / Non-Goals

**Goals:**
- Provide automated cache expiration by checking file modification age against a configurable TTL (`cache_ttl_hours: 6.0`).
- Provide an on-demand bypass via `--no-cache` / `--refresh-aa` flags in `fetch`, `refresh`, and `run`.
- Clearly communicate in stdout whether the cache was used (with age) or live API calls were made.
- Maintain backward compatibility with existing tests and offline `score` usage.

**Non-Goals:**
- Caching other providers' outputs (`models_snapshot.json`, `mappings.csv`), which are already re-generated on every `fetch`.
- Changing the schema or structure of `output/aa_snapshot.json` (it remains a raw JSON array of model rows).

## Decisions

### Decision 1: Use filesystem modification time (`st_mtime`) for cache age
- **Rationale**: Measuring `time.time() - self.cache_path.stat().st_mtime` avoids creating secondary metadata files (like `aa_snapshot.meta.json`).
- **Alternative Considered**: Embedding a metadata header (e.g. `{"cached_at": ..., "data": [...]}`). Rejected because `output/aa_snapshot.json` is consumed as a raw list of models across multiple modules and unit tests. Altering its top-level JSON structure would cause widespread regressions.

### Decision 2: Configurable `cache_ttl_hours` with 6-hour default
- **Rationale**: 6 hours provides a balance between staying well under 100 requests/day (at most 4 fetches per day if run continuously) and ensuring model scores or new models are picked up within the same workday.
- **Implementation**:
  - Add `cache_ttl_hours: float = 6.0` to `AaConfig` in `src/model_pipeline/config.py`.
  - In `config.py`, read `data["aa"].get("cache_ttl_hours", 6.0)`.
  - Document `cache_ttl_hours: 6` in `config.example.yaml` and `config.yaml`.

### Decision 3: CLI arguments `--no-cache` and `--refresh-aa`
- **Rationale**: Providing `--no-cache` follows standard CLI conventions, while `--refresh-aa` provides domain-specific clarity.
- **Implementation**:
  - In `cli.py:build_parser()`, add `--no-cache` (with `--refresh-aa` alias or destination) to `fetch`, `refresh`, and `run`.
  - In `cmd_fetch()`, evaluate `use_cache = not (getattr(args, "no_cache", False) or getattr(args, "refresh_aa", False))`.
  - Forward `args` from `refresh` and `run` to `cmd_fetch`.

### Decision 4: Transparent CLI status output
- **Implementation**:
  - When loading from cache: `print(f"  using cached Artificial Analysis snapshot ({age_str} old, ttl: {ttl}h)...")`.
  - When fetching from API: `print("  fetching fresh Artificial Analysis canonical models from API...")`.

## Risks / Trade-offs

- **[Risk] Multiple subcommands in `refresh` or `run` re-fetching:**
  - *Mitigation*: In `refresh` (which executes `fetch` then `score`), `fetch` fetches and writes the fresh `aa_snapshot.json`. Then `score` runs immediately after and reuses the newly written cache because it is fresh (age < 1 minute).
- **[Risk] Offline test environments failing due to expired cache:**
  - *Mitigation*: `test_refresh.py` and `test_score.py` mock `AaClient` with `_StubAaClient`, while `test_aa.py` unit tests will be updated to explicitly verify TTL expiry and mock timestamp comparisons.
