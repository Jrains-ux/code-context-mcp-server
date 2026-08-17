## Purpose

Provide reproducible consumer-side evaluation, version-bound knowledge artifacts, and observable local distribution without mutating published graph data or mappings.

## ADDED Requirements

### Requirement: Evaluation records version-bound black-box results
The system SHALL evaluate supplied samples against one active published snapshot, preserve dataset, golden-set, tool and configuration versions, and store aggregate metrics with individual failure cases.

#### Scenario: Successful evaluation records metrics
- **WHEN** an evaluation receives a sufficient dataset whose expected query results can be checked against the active snapshot
- **THEN** it returns a persisted evaluation run with its snapshot reference, metrics, and zero or more failure cases

#### Scenario: Insufficient evaluation is rejected
- **WHEN** an evaluation dataset has fewer than the configured minimum number of samples
- **THEN** the system returns `EVALUATION_INSUFFICIENT` and does not create a run claiming metrics

### Requirement: Knowledge artifacts consume published confirmed facts
The system SHALL generate technical documents from the active published snapshot and SHALL generate business documents only from confirmed mappings bound to that snapshot.

#### Scenario: Technical artifact includes immutable provenance
- **WHEN** a technical document is generated for an active published snapshot
- **THEN** its artifact and manifest record snapshot versions, evidence references, generator version, and a content checksum

#### Scenario: Unconfirmed business mapping is excluded
- **WHEN** a requested business document has no confirmed mapping for the active snapshot
- **THEN** the system does not create a formal business artifact for that mapping

### Requirement: Distribution is idempotent and graph-safe
The system SHALL record each distribution attempt against a document manifest and idempotency key, return the original result for repeated keys, and SHALL NOT modify nodes, edges, snapshots, or mappings.

#### Scenario: Local delivery succeeds once per idempotency key
- **WHEN** a valid manifest is pushed to the supported local target with a new idempotency key
- **THEN** the item is recorded as pushed and a repeat request returns the recorded result without another delivery attempt

#### Scenario: Unsupported target is retryable
- **WHEN** a manifest is pushed to an unsupported external target
- **THEN** the item is recorded as failed with retryable state and the graph and mappings remain unchanged
