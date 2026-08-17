## Why

TECH-01 can initialize a runtime contract but cannot create the first published code snapshot that later runtime Skills require. TECH-02 needs a deterministic Bootstrap path that accepts scoped source input, stages extraction artifacts, reports conflicts, and publishes atomically.

## What Changes

- Add Bootstrap admission for a fixed source revision, include/exclude scope, and mutually exclusive extraction tasks.
- Add deterministic Python source extraction for the prototype, producing version-bound node and evidence artifacts in staging.
- Add artifact manifests, conflict reports, task-run records, and coverage gates that preserve failed staging work without moving the active snapshot.
- Add a Bootstrap service that validates artifacts, persists valid staged artifacts, and invokes the existing atomic publisher only after all gates pass.

## Capabilities

### New Capabilities

- `bootstrap-first-build`: First-build admission, staged source extraction, deterministic validation, conflict reporting, coverage gating, and atomic snapshot publication.

### Modified Capabilities

- None.

## Impact

- Affected code: bootstrap service and staging publisher, repository and schema migration, schema validation, CLI command, and foundation tests.
- The prototype supports local Python source fixtures only. It does not add MCP transport, external AI execution, Mining/confirm, lexical search, or incremental Sync.
