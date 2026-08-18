## Context

See proposal.md for motivation. Current Bootstrap scans Python files and stores only module/class/function nodes; `edges` is an unused persistence capability, FTS indexes node fields, and `expand` returns no paths. The project intentionally uses Python standard library and local SQLite.

## Goals / Non-Goals

**Goals:**

- Create a stable graph-artifact boundary between source parsing and storage.
- Persist structural, import, and resolvable call edges with immutable evidence.
- Preserve published snapshot isolation while adding path reconstruction and stdio access.

**Non-Goals:**

- Business Mining, business routing, Git diff synchronization, vector search, and non-Python parser implementations.
- Remote services or a replacement for SQLite/FTS5.

## Decisions

1. **Use typed artifacts before repository writes.** A parser returns deterministic node and edge artifacts with canonical keys and locations. This separates language parsing from snapshot persistence; an alternative of writing during AST visiting would make later language adapters duplicate storage policy.
2. **Use AST structural resolution only.** Phase A emits contains edges from lexical nesting, imports edges from import statements, and calls edges only when a local/import alias can be statically identified. It does not claim dynamic Python dispatch is resolved.
3. **Batch graph writes in one staging transaction.** Repository bulk persistence writes evidence, artifacts, nodes, and edges before the publisher switches the active pointer, then refreshes FTS in the same unit. This replaces per-record commits that can leave partially written staging data.
4. **Reconstruct paths during bounded BFS.** Query keeps a predecessor map keyed by node ID and emits node-ID paths; this is cheaper and more explainable than storing paths.
5. **Use a small JSON-RPC stdio adapter.** The adapter validates protocol envelopes and delegates only allowlisted operations to `mcp_tools.run`; it does not duplicate domain logic or add an MCP framework dependency.

## Risks / Trade-offs

- [Python dynamic dispatch cannot be resolved statically] → emit only high-confidence edges and retain evidence/quality metadata.
- [New schema migration changes existing SQLite files] → migration is additive and idempotent; existing snapshots remain readable.
- [FTS refresh failure after pointer switch] → build index inside the publication transaction so publication fails closed.
- [JSON-RPC method naming may differ between clients] → expose the Phase A command names as a documented allowlist and return stable invalid-method errors.

## Migration Plan

1. Apply additive graph-artifact migration.
2. Run existing migration and Bootstrap fixtures; ensure older snapshots remain queryable.
3. Bootstrap a new snapshot and verify nodes, edges, FTS, and paths share its revision.
4. Roll back by retaining the prior active snapshot; failed staging snapshots are not selected.
