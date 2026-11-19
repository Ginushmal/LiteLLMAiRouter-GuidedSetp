# Tasks

## 1. Header-driven pricing parser

- [x] 1.1 In `model-tier-populator/src/model_pipeline/providers/commandcode.py`, add header parsing to `parse_commandcode_pricing()`: consume the table's first row as headers, normalize with `clean_text()` + lowercase, and map the Model / Input / Output / Cache read / Cache write labels to column indices (tolerating sort glyphs like `↕`). Verify: unit test asserting the index map for both the 7-column and 8-column header rows.
- [x] 1.2 Raise `ValueError` naming the missing labels and flagging a page schema change when the header row is absent or any of Input / Output / Cache read / Cache write cannot be located; remove the `< 7` cell-count constant and the incidental "starts with Model" header skip, validating data rows against the highest mapped index instead. Verify: failure tests for no-header, missing-Output, and renamed-header tables all raise with the missing label in the message.
- [x] 1.3 Read prices and the model name from the mapped indices (name cell via Model header index with cell-0 fallback; keep anchor/href dual keying, `parse_money` semantics, Free/discount normalization flags unchanged). Verify: existing pricing-join tests still pass unmodified in their assertions.
- [x] 1.4 Wrap the `parse_commandcode_pricing()` call in `fetch_pricing()` with the same record-and-raise treatment already used for plan parsing, so a schema failure lands in the structured scraping log with the raw HTML saved. Verify: adapter-level test with a broken page asserts the error is recorded and propagated.
- [x] 1.5 Update the module docstring's row-layout description to state that columns are located by header text and list the required headers. Verify: docstring no longer documents a fixed positional layout.

## 2. Regression tests

- [x] 2.1 Update `_pricing_table()` in `model-tier-populator/tests/test_commandcode.py` to emit a real header row with the current live headers (`Model | Context | Input | Output | Cache read | Cache write | Caps`, with sort glyphs). Verify: full `tests/test_commandcode.py` suite passes.
- [x] 2.2 Add layout-variant tests: same price row rendered under the historical 8-column headers (with Intelligence), the current 7-column headers, and a reordered header variant all produce identical `ResolvedPricing`. Verify: new cross-layout equality test passes.
- [x] 2.3 Add an incident regression test using the saved raw page `data/raw/commandcode/20261118T060042Z_https-commandcode-ai-models.html` (or an inline fixture reproducing its exact rows): Kimi K3.1 Pro parses to input 2.00 / output 10.00 / cache_read 0.20 / cache_write None, and Qwen 4 Max to 1.50 / 4.50 / 0.075 / 1.875. Verify: test fails against the old positional parser and passes with the fix.
- [x] 2.4 Run the whole populator test suite (`uv run pytest` in `model-tier-populator/`). Verify: all tests pass, no regressions in plan gating, pricing join, or other adapters.

## 3. Data recovery and documentation

- [x] 3.1 Re-run the pipeline fetch phase against the live page, pass the mappings review gate, then score. Verify: `output/models_snapshot.json` shows Kimi K3.1 Pro at input 2.00 / output 10.00 and Qwen 4 Max at 1.50 / 4.50 with provider provenance, and tier reports no longer show the inverted cost-per-task values.
- [ ] 3.2 Re-run populate so already-synced CommandCode deployments converge to the corrected prices. Verify: LiteLLM `GET /model/info` shows the corrected `input_cost_per_token` / `output_cost_per_token` / cache costs for the affected deployments (e.g. Kimi K3.1 Pro input 2e-6, output 1e-5).
- [x] 3.3 Log the incident and the header-mapping rule in `LiteLLM-Learnings.md` per the update-litellm-learnings skill (positional HTML scraping silently shifted prices when CommandCode dropped its Intelligence column; scraping must map by header and fail loudly). Verify: learnings doc contains the entry with the raw-fetch evidence dates.