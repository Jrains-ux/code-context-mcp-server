## Why
Phase D can produce and route business candidates, but Sync still invalidates every mapping and rebuilds without reading Git changes or calculating dependency impact.

## What Changes
- Parse Git A/M/D/R changes between the active snapshot revision and target revision.
- Calculate affected graph nodes and dependency closure.
- Mark only affected mappings stale after a successful rebuild and preserve old mappings on failure.
- Persist incremental Sync impact details for idempotent replay.

## Capabilities
### New Capabilities
- `incremental-sync`: Git-aware impact analysis and stale mapping governance.

### Modified Capabilities
- None.

## Impact
Adds migration `011_phase_e_incremental_sync.sql`, modifies `SyncService`, and adds regression tests. Git diff is deterministic; Mining invocation and snapshot publication remain explicit caller responsibilities.
