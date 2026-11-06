# Tasks

## 1. Reusable populate plan

- [x] 1.1 Split the diff in `populate/sync.py` into a planning step (desired/current maps plus added/updated/deleted/unchanged sets) and an apply step that consumes that plan; verify the existing sync tests still pass and that `sync()` keeps its current behavior.
- [x] 1.2 Add a unit test proving the planning step reports the same sets the apply step uses and performs no HTTP writes; verify with `uv run --with pytest pytest tests/test_sync.py`.

## 2. Live server information

- [x] 2.1 Add a `server_details()` method to `LiteLLMClient` that reads `GET /health/readiness/details` and falls back to `GET /health/readiness` when details are unavailable; verify with fake-HTTP unit tests for the details response, the fallback, and a non-200 response.
- [x] 2.2 Add a test proving the displayed target uses `litellm.base_url` and never prints the master-key value; verify the fake client receives only the env-var name.

## 3. Interactive populate mode

- [x] 3.1 Add `--interactive` to the `populate` subcommand and print the target (base URL/host, readiness, database, LiteLLM version), current total and pipeline-managed model counts per model group, and the full dry-run diff with every added/updated/deleted deployment id.
- [x] 3.2 Implement the single confirmation: only `y`/`yes` apply; empty, `n`/`no`, EOF, or other input decline and exit `0`; non-terminal stdin skips the prompt without writing anything.
- [x] 3.3 Apply exactly the previewed plan after confirmation and print the applied summary; verify a fake-apply test shows the same added/updated/deleted sets as the preview.
- [x] 3.4 Handle unreachable server, rejected master key, missing master key, and missing `tier-output.json` without prompting or writing; verify each path with unit tests and assert no write calls occurred.
- [x] 3.5 Keep non-interactive `populate`, `populate --dry-run`, and `run` behavior unchanged; verify existing CLI tests pass and add a parser test for `populate --interactive`.

## 4. Launcher flow

- [x] 4.1 After `start "" "output\tier-report.html"`, run `uv run model-pipeline populate --interactive`; on a non-zero exit print a short note and `pause` so the error stays visible; verify the script text contains the call and that the refresh-failure branch still exits before opening the report or populating.
- [x] 4.2 Update the launcher header comment to describe refresh, report open, and the optional confirmed populate; verify the comment matches the actual command order.

## 5. Documentation

- [x] 5.1 Update `README.md` quick start and output notes to describe `populate --interactive` and the launcher's new optional step; verify the commands documented match the CLI help.
- [x] 5.2 Update `WALKTHROUGH.md` phase 3 and the launcher description to show the preview/confirm flow and that `refresh` still never contacts LiteLLM; verify the diagram/claims match the implemented behavior.

## 6. Final verification

- [x] 6.1 Run `uv run --with pytest pytest tests/`, `uv run --with ruff ruff check src tests`, and `uv run model-pipeline --help`; verify all pass and the help text lists the interactive flag.
- [x] 6.2 Run a manual smoke test of `populate --interactive` against a non-production or local target if available, or `populate --dry-run` plus the interactive preview with a declined prompt; verify no LiteLLM writes occur when declining.
