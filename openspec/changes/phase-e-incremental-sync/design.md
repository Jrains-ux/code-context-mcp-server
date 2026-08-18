## Context
The existing Sync implementation marks all mappings stale before rebuilding. That loses unaffected mapping availability and can leave stale state after a failed rebuild.

## Decisions
- Use the baseline snapshot's `source_revision` and the requested target revision for `git diff --name-status`.
- Treat rename entries as both old and new paths when locating affected nodes.
- Compute an undirected graph dependency closure from affected technical nodes.
- Match mappings by their anchor node IDs; only matched non-stale mappings become stale.
- Run Bootstrap before changing mapping state. A rebuild failure leaves mappings and the active snapshot unchanged.
- Persist changes, affected nodes, closure, and stale mapping IDs with the operation result.

## Risks / Trade-offs
- Dynamic dependencies outside the persisted graph are not discoverable and remain a Phase F/semantic-analysis concern.
- The Sync service returns impact data for the external Sync Skill to invoke incremental Mining explicitly.
- RDC iteration and requirement identifiers were unavailable and are recorded as `unknown`.
