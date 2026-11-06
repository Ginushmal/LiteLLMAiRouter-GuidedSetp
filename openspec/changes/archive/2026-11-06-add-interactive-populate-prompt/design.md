# Design

## Context

See `proposal.md` for motivation. The current implementation already has the
pieces this flow needs:

- `populate` loads `tier-output.json`, calls the diff-based sync, and applies
  unless `--dry-run` is passed.
- The diff compares `litellm_params` and the pipeline-owned `model_info` fields
  against `GET /model/info`, matched by `mp::` deployment id.
- `refresh` runs fetch then score and never contacts LiteLLM; the launcher
  (`refresh-and-open.bat`) calls it and then opens `output/tier-report.html`.

The running target (verified live) is LiteLLM **1.103.0**. It exposes:

- `GET /health/readiness` → `{"status": ..., "db": ...}` (unauthenticated)
- `GET /health/readiness/details` → the same plus `litellm_version`, `cache`,
  callbacks, and logging flags (master key required)
- `GET /model/info` → the current deployments already used by the diff

No config schema change is needed: the target is `litellm.base_url` and
`litellm.master_key_env` in `config.yaml`.

## Goals / Non-Goals

**Goals:**

- Show the target server and the full pending diff before any write.
- Make the safe choice (no changes) the default.
- Guarantee the applied change is exactly the previewed change.
- Keep `refresh` LiteLLM-free and keep all existing non-interactive commands
  unchanged.
- Provide a clear failure path when the server or credentials are unavailable.

**Non-Goals:**

- Adding a friendly server-name setting or any new config key.
- Changing the diff rules, id format, or apply semantics.
- Adding scheduling, retries, or automatic re-preview after a failure.
- Making the launcher apply changes without confirmation.

## Decisions

### Decision: Extend `populate` with `--interactive` instead of adding a new verb

`populate` already owns the artifact check, client setup, diff, apply, and exit
codes. A flag composes with the existing command and keeps `run`, `populate`,
and `populate --dry-run` untouched. A new `publish` verb was considered but
would duplicate the command surface and docs for one behavior.

### Decision: Split the diff into a reusable plan and an apply step

The current `sync()` computes and applies in one pass. Interactive mode needs to
print the plan before applying it. The sync module will expose:

1. a planning step that accepts the payload and the current model list and
   returns the desired/current maps plus the added, updated, deleted, and
   unchanged sets;
2. an apply step that takes that plan and performs the writes, returning the
   existing sync report.

`sync()` keeps its current behavior by planning and then applying immediately.
Interactive mode plans once, prints it, and applies that same plan after
confirmation. Calling `sync(apply=False)` and then `sync(apply=True)` was
rejected: it would fetch the current state twice and could preview one diff and
apply another if the server changes in between.

### Decision: Read live server info from the management API, with fallback

The preview prints the configured base URL and host, then queries
`/health/readiness/details`. If that endpoint is unavailable, it falls back to
`/health/readiness` and shows the version as unknown; readiness failures never
block the preview. Model counts and per-group counts come from the same
`GET /model/info` response used by the diff, so the preview adds no extra model
enumeration. The master key and its environment-variable name are never printed.

### Decision: One prompt, default No

After the preview, the flow asks one question. Only `y` or `yes`
(case-insensitive) apply; empty input, `n`, `no`, EOF, or anything else decline
and exit `0`. If stdin is not a terminal, the flow does not prompt: it prints
that the preview is read-only and exits without changes, so automation cannot
hang. The launcher runs in a real console, so the normal double-click path is
interactive.

### Decision: The launcher runs the interactive step after opening the report

The launcher keeps its current refresh and open behavior, then invokes
`populate --interactive`. Keeping one launcher preserves the one-click entry
point. `SSL_CERT_FILE` is already set at the top of the script for the
self-signed endpoint and therefore also covers this step. A non-zero exit from
the interactive step keeps the window open with `pause`, matching the existing
"fails loudly" launcher rule. Refresh still runs before any LiteLLM contact, so
the existing LiteLLM-independence guarantee is unchanged.

## Risks / Trade-offs

- **Readiness-details drift across LiteLLM versions** → fall back to the
  low-detail readiness endpoint and render version as unknown; the preview still
  proceeds.
- **Server changes between preview and apply** → the apply uses the planned
  sets, so the user sees exactly what was planned; if a write then fails, the
  existing per-deployment error reporting surfaces it and the exit code is
  non-zero.
- **Deletion surprise** → pipelines deletes any `mp::` row not present in the
  new tier list. The preview lists these ids explicitly, and the default answer
  is No.
- **Prompt blocks unattended runs** → interactive mode is opt-in and detects a
  non-terminal stdin; non-interactive `populate` and `run` keep their current
  behavior.
- **Credential exposure** → only the environment-variable name is printed, never
  the key value or an authorization header.
- **Production writes from a double-click** → the target URL is shown first and
  the default is No; declining exits without changing LiteLLM.

## Migration Plan

1. Ship the code and launcher changes together.
2. Update `README.md` and `WALKTHROUGH.md` so the launcher documentation says it
   now offers an optional populate.
3. No config migration; existing `config.yaml` files work unchanged.
4. Rollback: remove the interactive call from the launcher and run
   `populate`/`populate --dry-run` directly; the CLI additions are additive.
