# Spec Delta

## ADDED Requirements

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
