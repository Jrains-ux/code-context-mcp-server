## Purpose
Route business terms to explicit published-snapshot contexts and confirm mappings only with evidence and version checks.
## ADDED Requirements
### Requirement: Route and select business contexts
The system SHALL return a route token and `needs_user_selection` when a published business term has multiple candidates.
#### Scenario: Ambiguous business term
- **WHEN** a term has multiple published contexts
- **THEN** selection SHALL require a matching route token and candidate context
### Requirement: Confirm mappings safely
The system SHALL require evidence and matching expected version before changing a candidate mapping to confirmed or rejected.
#### Scenario: Evidence-backed confirmation
- **WHEN** a candidate mapping has matching CAS version and evidence
- **THEN** confirmation SHALL update state and append an audit record
