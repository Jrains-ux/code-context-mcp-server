## ADDED Requirements

### Requirement: Version-bound business nodes
The system SHALL store business nodes with a snapshot reference, typed payload, canonical key, lifecycle status, and source/index/config revisions.

#### Scenario: Store a candidate business node
- **WHEN** a candidate business node is added to an existing snapshot
- **THEN** the node is persisted with the snapshot revisions and its structured payload

### Requirement: Multi-evidence mapping
The system SHALL preserve mapping anchors, multiple evidence references, review metadata, risk, confidence, and lifecycle status.

#### Scenario: Create a mapping with multiple evidence references
- **WHEN** a mapping is created with anchor nodes and two evidence references
- **THEN** both evidence references and the anchor list are retrievable from the mapping

### Requirement: Evidence-aware confirmation
The system SHALL confirm or reject a mapping with expected-version CAS and audit the complete evidence set and reviewer metadata.

#### Scenario: Confirm a candidate mapping
- **WHEN** a reviewer submits a valid expected version and multiple evidence references
- **THEN** the mapping transitions to the requested state and one audit record contains all evidence references and review metadata
