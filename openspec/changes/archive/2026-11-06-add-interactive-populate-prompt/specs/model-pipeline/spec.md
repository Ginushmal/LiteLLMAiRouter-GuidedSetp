# Spec Delta

## ADDED Requirements

### Requirement: Interactive LiteLLM population preview

The pipeline SHALL provide an interactive populate mode that identifies the
configured LiteLLM target, shows the pending changes, and asks for one explicit
confirmation before writing anything.

#### Scenario: Target server is identified before the prompt

- **WHEN** the user starts populate in interactive mode and the configured target is reachable and authenticated
- **THEN** the pipeline SHALL print the configured base URL and host plus live server information (readiness status, database status, and LiteLLM version), together with the current total model count and the count of pipeline-managed models grouped by model group

#### Scenario: Pending diff is shown before confirmation

- **WHEN** the interactive preview reads `tier-output.json` and the current LiteLLM model list
- **THEN** it SHALL print the dry-run diff summary (added, updated, deleted, unchanged counts) and list every deployment id in the added, updated, and deleted sets
- **AND** it SHALL NOT create, update, or delete any LiteLLM model before the confirmation is accepted

#### Scenario: One confirmation with a safe default

- **WHEN** the preview has been printed
- **THEN** the pipeline SHALL ask exactly one question about applying the shown changes
- **AND** an empty answer, `n`, or `no` SHALL decline, leave LiteLLM unchanged, and exit successfully
- **AND** `y` or `yes` SHALL apply exactly the diff that was shown

#### Scenario: Accepted changes use the previewed plan

- **WHEN** the user accepts the prompt
- **THEN** the pipeline SHALL apply the same added, updated, and deleted sets that the preview displayed, and SHALL report the applied result and any errors

#### Scenario: Unreachable target or missing credentials never prompt

- **WHEN** the configured LiteLLM target cannot be reached, rejects the master key, or the master key is missing
- **THEN** the pipeline SHALL print the reason and the target URL, SHALL NOT ask for confirmation, and SHALL NOT change any model

#### Scenario: Missing tier list never prompts

- **WHEN** `tier-output.json` does not exist
- **THEN** the pipeline SHALL print the existing missing-artifact error and SHALL NOT contact LiteLLM or ask for confirmation

#### Scenario: Non-interactive populate is unchanged

- **WHEN** the user runs populate without the interactive mode
- **THEN** it SHALL keep applying the diff without a prompt, and `--dry-run` SHALL keep showing the diff without applying it
