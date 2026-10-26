# Tasks

## 1. HTML report renderer

- [x] 1.1 Implement `emit/html_report.py`: pure `build_html(result, low_confidence_rows) -> str` rendering header (generated_at, SOTA, cost methods), tier cards with deployment tables, model index, per-tier full rankings with cut line, Pareto dominators, exclusions, token-limit flags, pin warnings, and the low-confidence mapping banner — all values HTML-escaped; verify `uv run --with pytest pytest tests/` passes new tests asserting each section exists and hostile model names (`<`, `&`) are escaped
- [x] 1.2 Inline the model-index sort/filter JS and page CSS (no external references) and verify a test asserts the output contains no `http://`/`https://` resource references (links to data sources in text are fine) and that tier ranking tables are wrapped in collapsible `<details>`

## 2. Score wiring and banner parity

- [x] 2.1 Wire `cmd_score` to write `output/tier-report.html` from the same `ScoreResult` as the Markdown reports, passing `low_confidence_rows(mappings)`, and verify a CLI test asserts the file appears after `score` next to `tier-output.json`
- [x] 2.2 Add the low-confidence count + `mappings.csv` pointer banner to the HTML and the Markdown ranking report and verify tests assert both readable outputs show the count when unoverridden low-confidence rows exist and show nothing when none do

## 3. Refresh verb

- [x] 3.1 Add the `refresh` CLI verb (fetch then score, never populate, stop at first non-zero exit, pass `--as-of` through) and verify a CLI test with fakes asserts `refresh` runs both phases, writes `tier-report.html`, never calls the LiteLLM client, and returns the failing phase's exit code without running the second phase when the first fails
- [x] 3.2 Verify `uv run model-pipeline --help` lists `refresh` with accurate help text

## 4. Launcher

- [x] 4.1 Add `refresh-and-open.bat` at the populator root: `cd /d "%~dp0"`, set `SSL_CERT_FILE` when `certs\ca-bundle.pem` exists, run `uv run model-pipeline refresh`, `start "" output\tier-report.html` only on success, `pause` + non-zero exit on failure, and verify by running it on this machine: it opens the report on success and leaves the console open without opening a browser when a key is removed from `.env`

## 5. LiteLLM independence and docs

- [x] 5.1 Add a regression test that runs `score` with no LiteLLM env vars set (fake providers/AA) and verify it completes, pinning that fetch/score/refresh never require `LITELLM_MASTER_KEY` or a running proxy
- [x] 5.2 Update `README.md` (outputs table, quick start with `refresh`, launcher section) and `WALKTHROUGH.md` (HTML report + refresh phase description), and `config.example.yaml` `litellm:` comments noting it is labels-only outside `populate`; verify the documented `refresh` command runs as written

## 6. Integration verification

- [x] 6.1 Run `uv run --with pytest pytest tests/` and `uv run --with ruff ruff check src tests` from `model-tier-populator/` and verify both are green (or report the ruff output honestly if it cannot run)
- [x] 6.2 Do one live `uv run model-pipeline refresh` and open `output/tier-report.html` manually; verify the page's numbers match `tier-output.md` and `tier-ranking.md` from the same run and the file opens offline

## 7. Report visuals

- [x] 7.1 Implement the interactive Pareto frontier SVG scatter (cost on the X axis increasing right with a log scale, intelligence on Y increasing upward, frontier boundary, de-cluttered labels, hover detail panel including the dominator, distinct $0 markers on the left edge) and verify tests assert every scored model is plotted, labels never overlap, the axes are not inverted, and hover data names the dominator
- [x] 7.2 Highlight each tier's order-1 deployment rows (star + row highlight) and verify tests assert exactly the order-1 rows are marked and lower orders are not
- [x] 7.3 Move the dominator information into the model index as a "Dominated by" column and remove the separate dominated-models table, and verify tests assert the dominator is named with its intelligence and cost while the old table is gone
- [x] 7.4 Move the low-confidence and pin warnings into one Warnings section at the bottom of the page and verify tests assert the section appears after all ranked content and is absent when there is nothing to warn about
- [x] 7.5 Re-run `uv run model-pipeline score` and verify the live `tier-report.html` shows the chart, highlighted top picks, and Dominated by column with values matching `tier-output.json`

## Workflow follow-up

- After implementation and review, archive the change (`/openspec-archive-change`) so the specs land in `openspec/specs/`.
