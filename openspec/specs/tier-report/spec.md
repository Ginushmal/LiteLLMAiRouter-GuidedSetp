# tier-report Specification

## Purpose

Lets anyone with a browser read the scored, ranked, and tiered model list as a single self-contained page, with no LiteLLM instance, repo checkout, or API keys required.

## Requirements

### Requirement: Self-contained HTML tier report

The pipeline SHALL emit a single self-contained HTML file (`tier-report.html`) alongside the existing score outputs, rendering the same scored/ranked/tiered result with no external network dependencies.

#### Scenario: HTML emitted on every score

- **WHEN** the score phase completes successfully
- **THEN** it SHALL write `tier-report.html` into the output directory next to `tier-output.json`, `tier-output.md`, and `tier-ranking.md`

#### Scenario: Offline and shareable

- **WHEN** a user opens `tier-report.html` in a browser with no network access
- **THEN** the page SHALL render fully (content, styling, and interactivity inlined in the single file) with no CDN, font, or script fetch required

#### Scenario: Same source as Markdown reports

- **WHEN** the score phase builds its outputs
- **THEN** the HTML SHALL be rendered from the same in-memory scoring result as the Markdown reports, not by parsing the Markdown files

### Requirement: HTML covers the full ranking story

The HTML report SHALL carry every section needed to answer "why is model X in tier Y", matching the coverage of the two Markdown reports combined.

#### Scenario: Header and tier cards

- **WHEN** the HTML report is opened
- **THEN** it SHALL show generation time, SOTA intelligence, cost-method summary, and one card per tier with floor, lambda, mu derivation, pool size, deployment count, and backup count

#### Scenario: Deployment tables

- **WHEN** a tier card is viewed
- **THEN** it SHALL list that tier's deployments with model, provider, model ID, intelligence, cost-per-task, latency, NMB, kind (primary/backup/pinned), and API base

#### Scenario: Model index

- **WHEN** the model index section is viewed
- **THEN** it SHALL list every scored model with intelligence, best cost-per-task, Pareto state, eligible tiers, pinned tiers, excluded tiers, and selected tiers, and SHALL support sorting or filtering by those columns

#### Scenario: Per-tier full ranking with cut line

- **WHEN** a tier's full ranking section is viewed
- **THEN** it SHALL list every eligible model ranked by NMB with its NMB inputs, Pareto state, and selected/cut outcome, with a visible cut line at the top-K boundary

#### Scenario: Explanations and flags

- **WHEN** the explanations section is viewed
- **THEN** it SHALL show a Dominated by column in the model index (naming a model that beats each dominated model on both axes), exclusion reasons with counts, token-limit flags, and pin warnings

### Requirement: Low-confidence mappings stay visible

The HTML report SHALL surface data-quality warnings instead of silently presenting a possibly-misclassified ranking, grouped at the bottom of the page.

#### Scenario: Low-confidence banner

- **WHEN** the score ran with low-confidence mappings that were not overridden
- **THEN** the HTML SHALL show a visible warning block at the bottom of the page with the count and a pointer to review `mappings.csv`

### Requirement: Pareto frontier chart

The HTML report SHALL include an interactive cost-vs-intelligence scatter chart with the Pareto frontier drawn through it, so a user can see the efficient set at a glance.

#### Scenario: Axes use their natural directions

- **WHEN** the chart is viewed
- **THEN** cost SHALL increase to the right (log scale) and intelligence SHALL increase upward, with neither axis reversed, so cheaper-and-smarter models sit toward the top-left

#### Scenario: Every scored model is plotted

- **WHEN** the chart section is viewed
- **THEN** every scored model with an intelligence score and a cost SHALL appear as one point, positioned by best cost-per-task (horizontal, log scale) and intelligence (vertical)

#### Scenario: Frontier is drawn and labeled

- **WHEN** the chart is viewed
- **THEN** frontier models SHALL be visually distinct from dominated ones, connected along the frontier boundary, and labeled with their names in positions that do not overlap each other

#### Scenario: Hover details including the dominator

- **WHEN** a user hovers a point
- **THEN** an in-page panel SHALL identify the model, its intelligence, and its cost, and for a dominated model SHALL also name the model that dominates it with that model's intelligence and cost

#### Scenario: Free models

- **WHEN** a model's cost-per-task is $0
- **THEN** it SHALL be drawn as a distinctly marked point on the left edge of the chart instead of breaking the log scale

### Requirement: Top-pick row highlighting

The HTML report SHALL mark each tier's highest-priority deployment directly in the tables, so the recommended picks stand out without a separate summary.

#### Scenario: Order-1 rows are highlighted

- **WHEN** a tier's deployment table is viewed
- **THEN** every deployment at order 1 SHALL be visually highlighted and marked with a star, and lower orders SHALL not be

#### Scenario: Highlights match the ranking

- **WHEN** the highlighted rows are compared against the tier's per-tier ranking
- **THEN** the highlighted deployment SHALL be the same model recorded at order 1 in the ranking data

### Requirement: Dominator visibility

The model index SHALL answer why a dominated model is only a backup without a second table.

#### Scenario: Dominated by column

- **WHEN** a model is off the Pareto frontier
- **THEN** its model-index row SHALL name a model that dominates it (smarter AND cheaper) together with that dominator's intelligence and cost

#### Scenario: Frontier rows

- **WHEN** a model is on the Pareto frontier
- **THEN** its Dominated by cell SHALL be empty

#### Scenario: No duplicate dominator table

- **WHEN** the report is generated
- **THEN** it SHALL NOT contain a separate dominated-models table, because the model index already carries that information
