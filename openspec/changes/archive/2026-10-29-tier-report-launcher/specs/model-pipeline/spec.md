# Spec Delta

## MODIFIED Requirements

### Requirement: Human review gate between phases
The pipeline SHALL execute as three independent invocations (fetch, score, populate) with clean artifact-based handoffs, plus a `refresh` verb that runs fetch then score without populate. Each phase reads its inputs from files on disk and writes its outputs to files on disk. Later phases can be re-run without re-running earlier phases.

#### Scenario: Three separate invocations
- **WHEN** the user invokes the pipeline
- **THEN** fetch, score, and populate are three separate commands that can be run independently, each reading from and writing to persistent artifacts

#### Scenario: Combined run
- **WHEN** the user wants an unattended run (e.g. on a schedule)
- **THEN** the pipeline SHALL provide a single `run` command that executes fetch, score, and populate in sequence and stops at the first phase that fails; this bypasses the human-review gates, which remain available through the individual commands

#### Scenario: Refresh run without populate
- **WHEN** the user wants the day's scored and tiered list without touching LiteLLM
- **THEN** the pipeline SHALL provide a single `refresh` command that executes fetch then score in sequence and stops at the first phase that fails, and SHALL NOT run populate; the human-review gates remain available through the individual commands

#### Scenario: Re-run populate without recompute
- **WHEN** the populate phase has been run and the LiteLLM database is subsequently cleared or corrupted
- **THEN** the user SHALL be able to re-run populate using the existing `tier-output.json` without re-running fetch or score

#### Scenario: Override-aware re-scoring
- **WHEN** the human reviewer edits the mappings CSV (changing a canonical assignment or overriding a confidence-scored row)
- **THEN** the score phase SHALL use the manual overrides in preference to the automatically computed mappings

### Requirement: Ranking explainability report

The pipeline SHALL produce human-readable reports that explain the ranking for every
scored model, so a user can see why a model did or did not land in a tier. The Markdown ranking report and the self-contained HTML tier report SHALL carry the same ranking coverage.

#### Scenario: Per-tier full ranking with NMB breakdown

- **WHEN** the score phase runs
- **THEN** it SHALL write a report listing, for each tier, every eligible model ranked by
  that tier's NMB alongside the NMB inputs (lambda, intelligence, cost_per_task, latency
  or "unknown", the tier's `rho` and derived `mu`, and the resulting latency penalty), the
  model's Pareto state, and whether it was selected (with its order) or cut

#### Scenario: Per-model index across tiers

- **WHEN** the report is generated
- **THEN** it SHALL include an index of every scored model showing its intelligence,
  cost-per-task, Pareto state, the tiers it was eligible for, and the tiers it was
  actually selected in

#### Scenario: Dominated models are explained

- **WHEN** a model is off the Pareto frontier
- **THEN** the report SHALL name a model that dominates it (smarter AND cheaper), so a
  user can see why the model was only ever a backup

#### Scenario: HTML report matches Markdown coverage

- **WHEN** the score phase completes
- **THEN** it SHALL also write the self-contained HTML tier report carrying the same tier cards, model index, per-tier rankings with cut line, dominators, exclusions, limit flags, pin warnings, and low-confidence mapping warning as the Markdown reports
