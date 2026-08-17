## Why
Published code facts need an explicit, auditable incremental update path.
## What Changes
- Add operation-id idempotent Sync baseline validation, stale events, and incremental staging publication.
## Capabilities
### New Capabilities
- `incremental-sync`: Explicit baseline-bound update that retains old published snapshots on failure.
### Modified Capabilities
- None.
## Impact
Local SQLite Sync operation metadata and a Sync service; Query remains read-only.
