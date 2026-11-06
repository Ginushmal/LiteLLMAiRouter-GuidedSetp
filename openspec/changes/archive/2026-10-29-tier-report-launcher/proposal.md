# Proposal

## Why

Running the model-tier populator today ends in two Markdown files and a LiteLLM `populate` step. A user who only wants "what are the best models on my provider today" has no one-click path: they must run `fetch` + `score` manually, read raw Markdown, and ignore `populate`. A double-click shortcut that refreshes data and opens a readable page in the browser makes the scored/ranked/tiered list usable by anyone, including people with no LiteLLM instance.

## What Changes

- Add a `refresh` pipeline verb that runs `fetch` then `score` only (never `populate`), stopping on the first failure.
- Make `score` also emit a self-contained `output/tier-report.html` built from the same `ScoreResult` that produces `tier-output.md` / `tier-ranking.md` (not by parsing Markdown), covering tiers, model index, per-tier rankings with cut line, Pareto/dominators, exclusions, limits, pins, and warnings including low-confidence mappings.
- Add a `refresh-and-open.bat` launcher at the populator root that runs `refresh` and opens `tier-report.html` in the default browser only on success; on failure it keeps the console open and never opens a stale report.
- Make `fetch`/`score`/`refresh` runnable without a LiteLLM server or master key; the `litellm:` config block remains as tier-label mapping only.
- Explicit non-goals: no `.exe`/PyInstaller packaging, no uv/config/key bootstrapping in the `.bat`, no in-page config editing, no LiteLLM calls in the refresh path.

## Capabilities

### New Capabilities

- `tier-report`: self-contained offline HTML rendering of the scored/ranked/tiered result, viewable in any browser with no repo, keys, or server.
- `refresh-launcher`: one-click refresh-then-open flow (`refresh` verb + `.bat` launcher) with fail-loud behavior.

### Modified Capabilities

- `model-pipeline`: `score` gains an HTML output artifact alongside the existing JSON/Markdown; pipeline gains a `fetch -> score` combined verb that excludes `populate`; fetch/score no longer require LiteLLM connectivity or secrets.

## Impact

- `model-tier-populator/src/model_pipeline/`: new `emit/html_report.py`, `score` wiring, new `refresh` CLI verb, `.bat` launcher at populator root.
- `output/`: new `tier-report.html` artifact on every `score`/`refresh`/`run`.
- Docs: `README.md` / `WALKTHROUGH.md` gain refresh + HTML sections; `config.example.yaml` `litellm:` comments clarify labels-only use for non-LiteLLM users.
- No change to scoring/NMB/Pareto logic, `tier-output.json` contract, or `populate` behavior.
