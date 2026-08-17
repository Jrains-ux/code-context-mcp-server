## Purpose
Update a published snapshot only through an explicit baseline-bound Sync operation while recording stale mappings and preserving the old active snapshot on failure.
## ADDED Requirements
### Requirement: Validate and apply Sync operations
The system SHALL require the active baseline snapshot and an operation identifier before staging an incremental update.
#### Scenario: Missing baseline
- **WHEN** a Sync operation has no active matching baseline
- **THEN** it SHALL return `BASELINE_REF_NOT_FOUND`
### Requirement: Preserve failed updates
The system SHALL append stale events before rebuilding and SHALL not replace the active snapshot when the rebuild cannot publish.
#### Scenario: Repeat operation
- **WHEN** the same operation identifier is submitted again
- **THEN** it SHALL return its original stored result
