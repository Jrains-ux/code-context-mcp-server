## Purpose

Allow callers to search and traverse one published technical code snapshot with explicit version, evidence, and budget information while keeping all query operations read-only.

## ADDED Requirements

### Requirement: Search published code facts

The system SHALL search only the active published snapshot and return matching nodes with matched fields, evidence references, scores, and a source/index/config snapshot reference.

#### Scenario: Matching technical term

- **WHEN** a caller searches a technical identifier in a published snapshot
- **THEN** the response SHALL return matching nodes and their evidence references

#### Scenario: No published snapshot

- **WHEN** a caller searches without an active published snapshot
- **THEN** the system SHALL return `SNAPSHOT_NOT_PUBLISHED`

### Requirement: Bound graph expansion

The system SHALL expand edges only within the requested published snapshot and SHALL return truncation metadata when depth, node, or edge budgets limit traversal.

#### Scenario: Traversal exceeds edge budget

- **WHEN** expansion finds more edges than the requested edge budget
- **THEN** the response SHALL set `truncated` to true and SHALL not return more than that budget

### Requirement: Preserve query read-only behavior

The system MUST NOT create or modify nodes, edges, mappings, snapshots, or the active pointer while executing lexical search or relation expansion.

#### Scenario: Query after publication

- **WHEN** a caller runs search and expansion against a published snapshot
- **THEN** the active snapshot and graph record counts SHALL remain unchanged
