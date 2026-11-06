# Spec Delta

## ADDED Requirements

### Requirement: Artificial Analysis catalog caching and freshness
The pipeline SHALL cache fetched Artificial Analysis canonical models on disk to minimize API calls and respect rate limits, but SHALL enforce a configurable time-to-live (TTL) to prevent indefinite staleness of model scores, latencies, and canonical identities.

#### Scenario: Reusing fresh snapshot cache
- **WHEN** `output/aa_snapshot.json` exists on disk and its file modification timestamp is within the configured `aa.cache_ttl_hours` (default 6 hours)
- **THEN** `AaClient` SHALL read the canonical models from disk and avoid calling the Artificial Analysis API

#### Scenario: Invalidation and refetch on TTL expiration
- **WHEN** `output/aa_snapshot.json` exists on disk but its file modification timestamp is older than `aa.cache_ttl_hours`
- **THEN** `AaClient` SHALL treat the cache as expired, fetch fresh canonical models from the Artificial Analysis API, and write the updated snapshot to `output/aa_snapshot.json`

#### Scenario: Configurable cache TTL in config
- **WHEN** `aa.cache_ttl_hours` is defined in `config.yaml`
- **THEN** the configuration loader SHALL parse it as a float/integer number of hours; if absent, it SHALL default to 6.0 hours

#### Scenario: Transparent cache source and age logging
- **WHEN** canonical models are loaded in `fetch`, `score`, `refresh`, or `run`
- **THEN** the pipeline console output SHALL explicitly report whether models were loaded from disk cache (including approximate cache age in hours/minutes) or fetched live from the API

### Requirement: CLI cache bypass flags
The pipeline CLI SHALL support flags to bypass the disk cache on demand during fetching and scoring operations.

#### Scenario: Bypassing cache via --no-cache or --refresh-aa
- **WHEN** the user runs `fetch`, `refresh`, or `run` with `--no-cache` or `--refresh-aa`
- **THEN** the pipeline SHALL bypass `output/aa_snapshot.json`, make live network requests to Artificial Analysis, and overwrite `output/aa_snapshot.json` with the newly fetched data

#### Scenario: Offline score behavior preserves cache by default
- **WHEN** the user runs `score` without cache-bypass flags
- **THEN** it SHALL use the existing `output/aa_snapshot.json` artifact to ensure offline re-scoring remains functional
