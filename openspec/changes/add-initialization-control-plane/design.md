## Context

The existing CLI always applies the baseline migration and can register the static permission matrix, but it does not retain the caller's project configuration or distinguish a migrated database from a runtime-ready one. See `proposal.md` for the change motivation and `specs/initialization-control-plane/spec.md` for the required observable behavior.

## Goals / Non-Goals

**Goals:**

- Persist one local project manifest and its declared Skill-to-tool permission contract.
- Use the persisted contract as the source for registry synchronization and health diagnostics.
- Fail closed until schema, manifest, registry, and a published snapshot are all healthy.
- Preserve the existing SQLite-only, local CLI workflow.

**Non-Goals:**

- Implement MCP stdio transport, source parsing, Bootstrap orchestration, Query, Sync, Mining, Evaluation, Knowledge, or push delivery.
- Add network services or a runtime dependency on CodeGraphContext.

## Decisions

- Use a second, idempotent SQLite migration for initialization metadata rather than alter the baseline migration. This preserves existing databases and records schema evolution; rewriting `001_initial.sql` would make upgrade behavior ambiguous.
- Store the manifest payload as canonical JSON with a single local manifest row. TECH-01 supports one local project database, so a singleton contract is sufficient and avoids a configuration-file dependency.
- Treat the declared manifest permissions as authoritative for the registry. The static `PermissionMatrix` remains the allow-list; initialization rejects declarations outside it, preventing a manifest from escalating privileges.
- Expose health through the same CLI dispatcher as `init`, `migrate`, and `doctor`. A JSON response is deterministic and script-friendly without committing to MCP transport before TECH-02.
- Require a published active snapshot for `runtime_ready`. This implements the TECH-01 fail-closed gate while preserving `doctor` as a detailed diagnostic command.

Alternatives considered: an external YAML manifest was rejected because it adds path/configuration drift; treating the static permission matrix as the full runtime contract was rejected because it cannot identify which project and revisions were initialized.

## Risks / Trade-offs

- [A user reinitializes a database with a different manifest] → initialization replaces the singleton manifest and registry atomically, and health returns the active values.
- [Later Skills need richer per-Skill configuration] → retain the full canonical `skills_json` payload so later packages can extend the contract without changing current health semantics.
- [No published snapshot exists immediately after init] → health remains explicitly not ready; this is intentional because TECH-02 owns initial ingestion and publication.

## Migration Plan

1. Apply the additive migration on new and existing local databases.
2. Initialize with the default local manifest or explicit CLI values.
3. Run `doctor`/`health`; it remains not runtime-ready until a later package publishes a snapshot.
4. Roll back by using a database created before the additive migration; the existing baseline schema and snapshot behavior remain intact.
