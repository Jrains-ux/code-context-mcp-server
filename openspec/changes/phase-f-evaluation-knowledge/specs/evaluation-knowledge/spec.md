## ADDED Requirements

### Requirement: business golden-set evaluation
The evaluator MUST report route status and node-scope precision and recall for business samples.

#### Scenario: business golden set
- Given a published snapshot and business route candidates
- When a business sample is evaluated
- Then route status and node-scope precision/recall are reported and bound to the snapshot.

### Requirement: impact-scoped knowledge
Knowledge generation MUST support a caller-provided impact node set.

#### Scenario: impact knowledge
- Given a published snapshot and an impact node set
- When knowledge is generated
- Then only the requested impact nodes are rendered and evidence/version metadata is retained.

### Requirement: configured distribution
Distribution MUST accept only explicitly configured HTTPS targets and preserve idempotency.

#### Scenario: configured distribution
- Given an explicitly configured HTTPS target
- When a manifest is pushed with an idempotency key
- Then the push succeeds without mutating graph state and repeats return the original result.
