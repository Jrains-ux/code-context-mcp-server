## 1. Project and Migration Setup

- [x] 1.1 Create the Python project metadata and package layout required by the local CLI and storage modules.
- [x] 1.2 Add the initial SQLite migration for manifests, snapshots, nodes, edges, evidence, mappings, stale events, update operations, evaluation runs, route audit, and tool registry records.
- [x] 1.3 Add a fixture database configuration that can be created in a temporary workspace without external services.

## 2. Storage Foundation

- [x] 2.1 Implement `storage/schema.py` migration execution and schema health reporting.
- [x] 2.2 Implement `storage/repository.py` version-bound record persistence and retrieval for manifests, snapshots, nodes, edges, evidence, and mappings.
- [x] 2.3 Implement `bootstrap/staging.py` staging artifact validation and atomic snapshot publication with active-pointer preservation on failure.
- [x] 2.4 Implement immutable evidence insertion and stale mapping replacement linkage.

## 3. Runtime Contracts

- [x] 3.1 Implement `policies/permission.py` with the TECH-00 Skill-to-tool permission matrix and deterministic access checks.
- [x] 3.2 Implement `tools/registry.py` tool registration, persisted registry synchronization, and missing-contract diagnosis.
- [x] 3.3 Implement `validators/schema_validator.py` envelope, revision, and snapshot-state validation with stable error codes.
- [x] 3.4 Implement `tools/mcp_tools.py` local `init`, `migrate`, and `doctor` command handlers returning machine-readable results.

## 4. Verification

- [x] 4.1 Add unit tests for migration, versioned persistence, immutable evidence, and publish failure behavior.
- [x] 4.2 Add unit tests for permission filtering, registry drift diagnosis, and CLI health results.
- [x] 4.3 Run the complete test suite and verify a clean initialization and doctor flow in a temporary workspace.
