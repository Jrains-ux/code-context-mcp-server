## Why

TECH-00 established the SQLite foundation and basic CLI, but the TECH-01 execution package still lacks a complete initialization control plane. A maintainer cannot persist a project manifest and its Skill/MCP contract, and `doctor` cannot fail closed when that configuration is absent or incompatible.

## What Changes

- Add a versioned project manifest model that records project identity, workspace, source revision, and declared Skill-to-tool permissions.
- Make `init` persist the manifest and synchronize the MCP tool registry from its declared permissions.
- Add deterministic manifest and registry validation to `doctor`, including a runtime-ready gate for later Bootstrap, Sync, and Query capabilities.
- Expose a machine-readable `health` command that reports schema, manifest, registry, store, and readiness checks.
- Provide a minimal fixture workflow that proves init, publish, and published-snapshot access can share one consistent database.

## Capabilities

### New Capabilities

- `initialization-control-plane`: Maintainer initialization, manifest persistence, registry synchronization, health reporting, and fail-closed runtime readiness validation.

### Modified Capabilities

- None.

## Impact

- Affected code: CLI commands, tool registry, permission policy, SQLite migration and repository helpers.
- Affected API: `code-context init`, `code-context doctor`, and the new `code-context health` JSON result shapes.
- No external services, remote repository operations, or runtime dependency on CodeGraphContext are introduced.
