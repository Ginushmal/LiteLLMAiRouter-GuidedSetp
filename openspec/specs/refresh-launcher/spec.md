# refresh-launcher Specification

## Purpose

Gives any user a one-click shortcut that refreshes the day's provider data, re-scores it, and opens the tier report, without touching LiteLLM or requiring bootstrap setup.

## Requirements

### Requirement: Refresh verb without populate

The pipeline SHALL provide a `refresh` verb that runs fetch then score in sequence and never contacts LiteLLM.

#### Scenario: Refresh runs fetch then score

- **WHEN** the user runs the `refresh` verb
- **THEN** the pipeline SHALL execute the fetch phase followed by the score phase, including writing `tier-report.html`, and SHALL NOT run the populate phase

#### Scenario: Refresh stops on first failure

- **WHEN** either the fetch or the score phase fails during `refresh`
- **THEN** the pipeline SHALL stop, exit non-zero, and SHALL NOT run any later phase

#### Scenario: Refresh supports schedule override

- **WHEN** the user passes a schedule evaluation instant to `refresh`
- **THEN** it SHALL apply to both phases exactly as the existing per-phase override does

### Requirement: One-click launcher opens the fresh report

The populator SHALL ship a double-click launcher that refreshes the data and opens the resulting HTML report in the default browser.

#### Scenario: Double-click refreshes and opens

- **WHEN** the user double-clicks the launcher on a machine with the repo, runtime, config, and provider keys present
- **THEN** it SHALL run the `refresh` verb from the populator directory and open `tier-report.html` in the default browser

#### Scenario: Failure never shows stale data

- **WHEN** the refresh run fails for any reason
- **THEN** the launcher SHALL keep the console open showing the error and SHALL NOT open the browser, so a stale report is never presented as current

#### Scenario: No bootstrap behavior

- **WHEN** the launcher runs on a machine missing the runtime, config, or required keys
- **THEN** it SHALL fail with the underlying tool error left visible on screen and SHALL NOT attempt to install software, copy config templates, or prompt for secrets

### Requirement: LiteLLM-independent refresh

Fetch, score, and refresh SHALL NOT require a running LiteLLM instance or LiteLLM credentials.

#### Scenario: Refresh without LiteLLM

- **WHEN** no LiteLLM server is reachable and no LiteLLM master key is configured
- **THEN** `fetch`, `score`, and `refresh` SHALL still complete, treating the LiteLLM config block as tier-label mapping only

#### Scenario: Populate still requires LiteLLM

- **WHEN** the user runs `populate`
- **THEN** the existing LiteLLM connectivity and credential requirements SHALL still apply unchanged

### Requirement: Optional populate step after a successful refresh

The one-click launcher SHALL offer to populate the configured LiteLLM server
after a successful refresh and report open, without making that offer when the
refresh fails.

#### Scenario: Successful refresh offers the populate preview

- **WHEN** the launcher's refresh completes successfully and the tier report has been opened
- **THEN** the launcher SHALL start the interactive populate preview for the server configured in `config.yaml`
- **AND** the preview SHALL show the target server information and the pending diff before asking whether to apply it

#### Scenario: Declining leaves LiteLLM untouched

- **WHEN** the user declines the launcher's populate prompt
- **THEN** LiteLLM SHALL remain unchanged and the launcher SHALL finish successfully

#### Scenario: Failed refresh never offers populate

- **WHEN** the refresh run fails
- **THEN** the launcher SHALL keep the existing behavior: show the error, keep the console open, open no report, and SHALL NOT start the populate preview

#### Scenario: Populate connectivity failure is visible

- **WHEN** the interactive populate step cannot reach LiteLLM or its master key is missing
- **THEN** the launcher SHALL show the reason and keep the console open so the failure is not missed

#### Scenario: Refresh stays LiteLLM-independent

- **WHEN** the launcher runs its refresh step
- **THEN** the refresh step SHALL NOT contact LiteLLM, and only the optional populate step after the report may do so
