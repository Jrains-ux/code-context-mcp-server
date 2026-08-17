## Purpose

Defines the local runtime contracts needed to validate installed skills, expose permitted MCP tools, and diagnose whether the foundation can safely run.

## ADDED Requirements

### Requirement: Runtime initialization
The system SHALL provide local `init` and `migrate` operations that create or upgrade the storage schema and report failure without claiming success.

#### Scenario: Initialize an empty workspace
- **WHEN** the maintainer runs initialization against an empty workspace
- **THEN** the schema is created and a machine-readable success result is returned

#### Scenario: Migration fails
- **WHEN** a migration cannot be applied
- **THEN** the command returns a failure result and does not report the workspace as initialized

### Requirement: Tool permission registry
The system SHALL register the TECH-00 MCP tools and expose only the tools allowed for the requested runtime skill.

#### Scenario: List permitted tools
- **WHEN** a runtime skill requests its tool list
- **THEN** the registry returns the allowed tools and excludes tools not permitted for that skill

### Requirement: Health diagnosis
The system SHALL provide a `doctor` operation that reports storage, schema, registry, and version-contract failures with actionable error codes.

#### Scenario: Healthy workspace
- **WHEN** all required checks pass
- **THEN** doctor returns a successful health result

#### Scenario: Missing runtime contract
- **WHEN** a required tool registration or permission entry is missing
- **THEN** doctor returns a failed health result identifying the missing contract
