# Proposal

## Why

The one-click launcher stops at the refreshed HTML report. Applying the new tier
list to LiteLLM still requires a separate terminal command, so it is easy to
forget the populate step or to apply it without first seeing which server will
change and what the diff will do. That risk is highest for the configured
production endpoint.

## What Changes

- Add an opt-in interactive mode to `populate` that, before applying anything:
  - identifies the configured target with the base URL/host and live server
    info (readiness, database status, LiteLLM version), and
  - shows the dry-run diff (added / updated / deleted counts and the affected
    deployment ids).
- Ask exactly one confirmation question after the preview. Default is **No**;
  declining leaves LiteLLM untouched and exits successfully.
- Reuse the existing diff/apply implementation so the preview and the applied
  change can never disagree.
- Update the launcher so that, after `refresh` succeeds and the report opens, it
  runs the interactive populate preview. `refresh` itself remains
  LiteLLM-independent.
- If the target is unreachable, the master key is missing, or no
  `tier-output.json` exists, print the reason, do not prompt, and keep the
  console open.
- Leave non-interactive `populate`, `populate --dry-run`, `run`, and the current
  exit-code behavior unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `model-pipeline`: LiteLLM population gains an interactive preview-and-confirm
  mode that reports the target server and pending diff before applying.
- `refresh-launcher`: after a successful refresh and report open, the launcher
  offers an optional interactive populate step instead of always stopping at the
  report.

## Impact

- **Code**: `src/model_pipeline/cli.py` (interactive flow),
  `src/model_pipeline/populate/litellm_client.py` (live server info),
  `src/model_pipeline/populate/sync.py` (reusable plan/apply split),
  `refresh-and-open.bat` (launcher step).
- **Docs**: `README.md`, `WALKTHROUGH.md`, and the launcher comments.
- **Tests**: CLI prompt behavior, server-info rendering, plan/apply parity, and
  launcher flow.
- **Config**: no schema change; the target continues to come from
  `litellm.base_url` and `litellm.master_key_env`.
- **Behavior**: double-clicking the launcher may now touch LiteLLM, but only
  after an explicit confirmation.
