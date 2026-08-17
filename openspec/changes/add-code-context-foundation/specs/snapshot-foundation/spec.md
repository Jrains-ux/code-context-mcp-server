## Purpose

Provides a version-consistent, auditable foundation for storing and publishing code-context snapshots without exposing partially validated data to readers.

## ADDED Requirements

### Requirement: Versioned snapshot records
The system SHALL store manifests, snapshots, nodes, edges, evidence, and mappings with source, index, and configuration version references.

#### Scenario: Persist a versioned record
- **WHEN** a valid record is written with source, index, and configuration revisions
- **THEN** the record is retrievable with the same version references

### Requirement: Atomic snapshot publication
The system SHALL publish a staging snapshot only when its required artifacts are version-consistent and valid, and SHALL keep the previous published snapshot active when validation fails.

#### Scenario: Publish a valid staging snapshot
- **WHEN** all required artifacts share the staging snapshot revisions and pass validation
- **THEN** the snapshot becomes published atomically

#### Scenario: Reject inconsistent artifacts
- **WHEN** any required artifact has a different revision or invalid state
- **THEN** publication fails with a deterministic validation error and no active published snapshot is changed

### Requirement: Immutable evidence
The system SHALL preserve evidence records after creation and SHALL require a new evidence reference when a mapping is replaced after becoming stale.

#### Scenario: Prevent evidence mutation
- **WHEN** a caller attempts to update an existing evidence record
- **THEN** the operation is rejected

#### Scenario: Replace stale mapping evidence
- **WHEN** a stale mapping is confirmed with replacement evidence
- **THEN** the replacement is stored as a new evidence record linked to the mapping
