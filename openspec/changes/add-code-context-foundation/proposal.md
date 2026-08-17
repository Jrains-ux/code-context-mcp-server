## Why

The repository is empty, while the prototype direction requires a deterministic MCP data plane before Bootstrap, Query, and Sync can be built. This change establishes the smallest runnable foundation with versioned storage, publish safety, and runtime contract validation.

## What Changes

- Add a Python package for SQLite-backed snapshot metadata and core graph/evidence records.
- Add migrations for manifests, snapshots, nodes, edges, evidence, mappings, route audit, and tool registry data.
- Add deterministic validation for version consistency, publish state transitions, and immutable evidence.
- Add a tool registry with the TECH-00 permission matrix and a local `init`, `migrate`, and `doctor` CLI.
- Add focused tests and a minimal fixture for initialization, persistence, and publish failure behavior.

## Capabilities

### New Capabilities

- `snapshot-foundation`: Versioned SQLite storage, core records, staging/published snapshots, and atomic publication checks.
- `runtime-contracts`: MCP tool registry, permission matrix, and local initialization/health-check commands.

### Modified Capabilities

None.

## Impact

- New Python source package under `src/code_context/`.
- New SQLite migration and fixture files under `migrations/` and `tests/fixtures/`.
- New project metadata and CLI entry point under `pyproject.toml`.
- No external service, database server, or CodeGraphContext runtime dependency.
