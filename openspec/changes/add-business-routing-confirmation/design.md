## Context
TECH-04 consumes published snapshots and does not create business concepts automatically.
## Goals / Non-Goals
**Goals:** deterministic candidate routing, token selection, evidence/CAS confirmation.
**Non-Goals:** Mining, automatic confirmation, Sync, or query-time graph writes.
## Decisions
Route tokens bind candidates to the current active snapshot and expire. Confirmation updates mapping state only with evidence and expected-version CAS.
## Risks / Trade-offs
Business candidates must be supplied by a future Mining workflow; this package intentionally does not infer them.
