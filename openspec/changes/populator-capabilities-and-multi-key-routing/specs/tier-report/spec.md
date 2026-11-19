# Spec Delta

## ADDED Requirements

### Requirement: Capability and credential visibility

The HTML report SHALL show a per-group credential count and every capability-resolution warning produced by the scoring phase, alongside the existing data-quality warnings. It SHALL identify credentials only by count or non-secret slot/fingerprint and SHALL NOT render any raw API key.

#### Scenario: Multi-key group shows its key count

- **WHEN** a reported model group contains deployments from more than one configured provider key
- **THEN** the tier card and the relevant model rows show the number of keys behind the group

#### Scenario: Capability warnings are grouped with data-quality warnings

- **WHEN** a deployment has an unresolved capability source, missing reasoning levels, a non-chat output modality, or another capability flag
- **THEN** the warning appears in the existing data-quality warnings section and names the affected model or group

#### Scenario: No credential is exposed

- **WHEN** the report renders a key count or fingerprint
- **THEN** it does not contain a raw API key or any recoverable key material
