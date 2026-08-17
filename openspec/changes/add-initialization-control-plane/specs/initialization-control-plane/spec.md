## Purpose

Provide a maintainer-operated, fail-closed initialization contract so later runtime Skills can rely on a validated project manifest, registry, schema, and published data store.

## ADDED Requirements

### Requirement: Initialize a project runtime contract

The system SHALL initialize a database with migrations, persist a project manifest containing a non-empty project identifier, workspace, source revision, configuration version, and declared Skill-to-tool permissions, and register exactly the manifest-declared enabled tools.

#### Scenario: Successful initialization

- **WHEN** a maintainer initializes a database with a valid manifest
- **THEN** the response SHALL report initialization success, the persisted manifest, and the synchronized registry

#### Scenario: Invalid manifest is rejected

- **WHEN** a maintainer initializes a database with a manifest that omits a required value or grants an unknown tool
- **THEN** the response SHALL fail with `SKILL_MANIFEST_INVALID` and SHALL not report the runtime as ready

### Requirement: Report health and fail closed

The system SHALL expose machine-readable health diagnostics for schema, manifest, registry, store, and runtime readiness. A runtime readiness check MUST fail unless every required check is healthy and at least one published snapshot exists.

#### Scenario: Ready runtime

- **WHEN** migrations, the persisted manifest, registry contract, and a published snapshot are valid
- **THEN** health SHALL report `ok: true` and `runtime_ready: true`

#### Scenario: Missing initialization contract

- **WHEN** a database has migrations but lacks a persisted manifest or its declared registry entries
- **THEN** health SHALL report `ok: false`, `runtime_ready: false`, and a stable diagnostic code

### Requirement: Preserve minimum-data compatibility

The system SHALL retain existing snapshot publication behavior while adding initialization metadata. A published snapshot produced after initialization SHALL remain available through the active snapshot pointer.

#### Scenario: Minimal fixture publication

- **WHEN** a valid initialized database publishes a consistent staging snapshot
- **THEN** the active snapshot pointer SHALL reference that published snapshot and health SHALL become runtime-ready
