# Design

## Context

See proposal.md — Why for the incident. Implementation constraints observed in the code:

- `parse_commandcode_pricing()` in `model-tier-populator/src/model_pipeline/providers/commandcode.py` finds the first `<table>`, iterates `<tr>` rows, extracts cells with `_CELL_RE` (which matches both `<td>` and `<th>`), skips rows with `< 7` cells, and reads prices from hard-coded `cells[3..6]`. The header row is currently skipped only incidentally (its name cell starts with "Model").
- The header cells look like `Input ↕` — text plus a sort-marker glyph; `clean_text()` already strips tags/entities and collapses whitespace, so header matching must tolerate trailing non-word glyphs.
- The current live table (raw fetch `20261118T060042Z_...html`) has 7 columns: `Model | Context | Input | Output | Cache read | Cache write | Caps`. All fetches through 2026-11-09 had 8 (with `Intelligence` after `Context`).
- The plan parser in the same file already models the desired failure posture: `parse_commandcode_plans()` raises `ValueError("... (schema change?)")` when its data disappears, `fetch_pricing()` records the error via `self._record(...)` and re-raises, and the fetch phase stops.
- Test fixtures in `tests/test_commandcode.py` (`_pricing_table()`) build **headerless** 8-cell rows — they encode the stale layout and would keep passing a positional parser. They must gain a real header row.
- `parse_money()` semantics (effective/last price, Free → 0.0, dash → None, `+ 1` ignored) are correct and shared with the OpenCode adapter; they are not part of this change.

## Goals / Non-Goals

**Goals:**

- Prices always land in the field named by their column header, for any column order/count that still publishes the required headers.
- A table that stops publishing recognizable price headers aborts the CommandCode fetch with a diagnostic error, recorded in the scraping log.
- Regression tests pin both observed real-world layouts (8-column and 7-column) using the actual header texts.

**Non-Goals:**

- No changes to `parse_money()`, `ResolvedPricing`, `fetch_pricing()`'s signature, plan gating, or any downstream phase.
- No hardening of the OpenCode adapter's positional parsing (separate change if its page ever drifts).
- No fuzzy/semantic header inference (e.g. guessing that an unnamed column is "Input"); unknown schemas fail, they are not guessed.

## Decisions

1. **Map columns from the header row, matched on normalized header text.**
   Parse the first row of the table as headers (`_CELL_RE` already captures `<th>`), `clean_text()` each, then match by lowercased alphanumeric prefix/containment against the required labels: `model`, `input`, `output`, `cache read`, `cache write`. Matching ignores sort glyphs (`↕`) and case. `cache read`/`cache write` are matched before/with priority over bare `input`/`output` containment so a "Cache read" header can never be mistaken for another column (exact normalized equality on the known labels, not substring soup).
   *Alternative considered:* keep positions but detect the column count (7 vs 8) and switch offsets. Rejected — it only handles this one historical drift; the next added/removed/reordered column breaks it again, silently or loudly.

2. **Required headers: Input, Output, Cache read, Cache write. Model column located by header too, with anchor fallback.**
   All four price headers must be found or the parser raises `ValueError` naming the missing labels and flagging a page schema change — same posture as `parse_commandcode_plans`. The name is still read from the row's first anchor (`_ANCHOR_RE`/`_HREF_RE` dual keying unchanged); the Model header index is used only to pick the name cell when present, falling back to cell 0. Cache columns are *required as headers* but their per-row values may still be dashes (→ None): "column exists" and "model has a cache price" are different facts.
   *Alternative considered:* treat cache headers as optional (some providers lack them). Rejected for CommandCode — its page has always published both; making them optional would re-open a silent-drift hole for exactly the fields this incident corrupted.

3. **Row validation follows the header mapping, not a magic count.**
   A data row must have at least as many cells as the highest mapped column index; shorter rows are skipped as before (they are separators/artifacts). The `< 7` constant disappears. The header row itself is excluded from data rows by identity (it is consumed as the header), removing the incidental "starts with Model" skip.

4. **Failure flows through the existing loud path.**
   `parse_commandcode_pricing()` raises; `fetch_pricing()` already wraps plan parsing in record-and-raise — extend the same treatment to the pricing parse call so the error lands in the structured scraping log with the raw HTML saved (the recorder already saves the response). No new error-handling machinery.

5. **Tests use the real header texts and both layouts.**
   Update `_pricing_table()` to emit a `<thead>` row with the current 7-column headers; add a variant with the historical 8-column headers (Intelligence included) and a reordered variant; assert identical `ResolvedPricing` for the same row across all three. Add failure tests: no header row, missing "Output" header, renamed headers. Where practical, add one fixture assertion against the saved raw 2026-11-18 HTML for Kimi K3.1 Pro ($2.00 / $10.00 / $0.20 / —) and Qwen 4 Max ($1.50 / $4.50 / $0.075 / $1.875) — the exact rows from the incident.

## Risks / Trade-offs

- [Header text itself changes (e.g. "Cache read" → "Cached input")] → Fetch fails loudly with the missing labels named; a human updates the label map. This is the intended trade: a stopped run is recoverable, silently wrong prices are not.
- [Multiple tables on the page; first `<table>` is not the pricing table] → Existing behavior already takes the first table; header matching makes a wrong-table pick fail loudly (headers not found) instead of parsing garbage — strictly safer than today.
- [Fixture rewrite could mask a regression by testing only the new layout] → Mitigated by keeping the historical 8-column layout as an explicit test variant and asserting cross-layout equality.
- [Corrupted artifacts already produced] → Code fix alone does not heal `output/*` or LiteLLM DB; the tasks include a re-run of fetch → score → populate (idempotent populate converges existing deployments).

## Migration Plan

1. Land parser + tests; run the test suite.
2. Re-run `fetch` (fresh page parse), review mappings gate as usual, `score`, then `populate` — existing idempotent diff-based populate updates the wrong prices on already-synced CommandCode deployments.
3. Rollback: revert the commit; note that reverting restores the *broken* positional parser against the current 7-column page, so rollback also requires not re-running fetch until the page or parser is fixed.