## ADDED Requirements

### Requirement: Explicit Mining mode
The system SHALL accept only `initial` or `incremental` Mining modes and record each run outcome.

#### Scenario: Accept an initial candidate run
- **WHEN** a valid candidate list is submitted with mode `initial`
- **THEN** the system records a candidate mining run and returns its run identifier

### Requirement: Evidence-backed candidate persistence
The system SHALL reject candidates without evidence and persist valid candidates as non-confirmed mappings.

#### Scenario: Reject an evidence-free candidate
- **WHEN** a candidate has no evidence references
- **THEN** Mining returns `EVIDENCE_REQUIRED` and does not create a confirmed mapping

### Requirement: Version-bound business routing
The system SHALL resolve business terms only from the active published snapshot and require explicit selection for ambiguity.

#### Scenario: Select an ambiguous context
- **WHEN** a term resolves to more than one context
- **THEN** the system returns `needs_user_selection`, and a valid route token plus context returns only that context's node scope
