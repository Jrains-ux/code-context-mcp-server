## ADDED Requirements

### Requirement: Git change classification
The system SHALL classify Git modified, added, deleted, and renamed paths between a baseline and target revision.

#### Scenario: Parse a rename
- **WHEN** Git reports a rename from `old.py` to `new.py`
- **THEN** the change contains status `R`, old path `old.py`, and current path `new.py`

### Requirement: Dependency-aware stale marking
The system SHALL calculate affected graph nodes and dependency closure, and stale only mappings anchored in that closure.

#### Scenario: Preserve an unaffected mapping
- **WHEN** a changed file maps to one anchor and another mapping anchors an unchanged node
- **THEN** only the first mapping becomes stale

### Requirement: Rebuild failure isolation
The system SHALL preserve the active snapshot and mapping states when rebuilding the target revision fails.

#### Scenario: Bootstrap fails
- **WHEN** Git impact analysis succeeds but target Bootstrap fails
- **THEN** the operation fails without marking mappings stale
