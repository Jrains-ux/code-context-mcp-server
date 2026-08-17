## Purpose

Build the first locally published code snapshot from a revision-bound scoped source input, while keeping incomplete or invalid artifacts in staging and preserving the previous active snapshot.

## ADDED Requirements

### Requirement: Admit a fixed source scope

The system SHALL accept a Bootstrap request only when project, source revision, configuration version, and a non-empty source scope are present. It MUST assign non-overlapping extraction tasks and persist the admitted manifest and task states.

#### Scenario: Scoped admission succeeds

- **WHEN** a maintainer supplies a source root, fixed revision, and a non-empty include scope
- **THEN** the system SHALL create an admitted manifest and queued extraction task records

#### Scenario: Missing revision is rejected

- **WHEN** a Bootstrap request omits its source revision
- **THEN** the system SHALL fail with `SOURCE_REVISION_REQUIRED` before staging artifacts

### Requirement: Stage extracted artifacts with evidence

The system SHALL extract supported local Python source files into staged nodes and evidence records that share the admitted source revision and configuration version. Each artifact MUST have a deterministic content hash and evidence reference.

#### Scenario: Python source extraction

- **WHEN** a scoped Python source file contains a module, class, or function
- **THEN** the staging result SHALL include version-bound node artifacts and immutable evidence records for its source locations

### Requirement: Reject conflicted or incomplete staging

The system SHALL create a conflict report for duplicate artifact canonical keys, missing evidence, revision mismatch, or a failed coverage gate. It MUST retain the staging snapshot and MUST NOT change the active snapshot when a gate fails.

#### Scenario: Duplicate canonical artifact

- **WHEN** staged artifacts share a canonical key
- **THEN** the system SHALL report `ARTIFACT_CONFLICT` and retain the snapshot in staging

#### Scenario: Coverage gate failure

- **WHEN** an admitted source scope yields no extractable artifacts
- **THEN** the system SHALL report `COVERAGE_GATE_FAILED` and retain the snapshot in staging

### Requirement: Publish only validated first builds

The system SHALL atomically publish a validated staging snapshot only when its expected parent matches the current active snapshot. A rejected parent or validation gate MUST leave the active snapshot unchanged.

#### Scenario: Valid first build publication

- **WHEN** admission, extraction, evidence, conflict, and coverage checks succeed with a matching expected parent
- **THEN** the system SHALL publish the staged snapshot and set it as the active snapshot

#### Scenario: Parent mismatch

- **WHEN** a Bootstrap publication specifies an expected parent that differs from the active snapshot
- **THEN** the system SHALL fail with `PUBLISH_PARENT_MISMATCH` and SHALL preserve the active snapshot
