## Context

See `proposal.md` for motivation. Existing consumer services locate an active `published` snapshot from SQLite, while Bootstrap and Sync own graph writes. TECH-06 must consume that state without joining the snapshot publication transaction or performing a remote push.

## Goals / Non-Goals

**Goals:**

- Persist repeatable evaluation inputs, metrics, and failure details with explicit version references.
- Produce deterministic technical and confirmed-business Markdown artifacts with manifest checksums.
- Record local and failed distribution attempts with idempotency and retry visibility.

**Non-Goals:**

- No mutation of graph content, snapshot state, or mapping state.
- No AI judgement, external service calls, remote document creation, or real Git/Feishu/RAG distribution.
- No performance or accuracy claim beyond values measured by supplied samples.

## Decisions

### Consumer-side SQLite records

Add separate evaluation, document, and distribution tables in migration 007. This keeps each run and document traceable while avoiding changes to graph tables. An in-memory-only report was rejected because TECH-06 requires repeatable, versioned reports and retry state.

### Deterministic evaluator and generator

The evaluator calls the existing technical query service for sample queries and compares returned node identifiers with golden expectations. The generator serializes metadata plus active-snapshot nodes or confirmed mapping facts. This is intentionally deterministic; an AI or template engine is deferred because it would need additional semantic and safety contracts.

### Explicit local distribution adapter

`local` is the only success target. Unsupported targets write a failed, retryable attempt rather than making a network call. A real external adapter was rejected because the user explicitly disallowed remote push and Feishu document creation.

### Snapshot consistency gate

All operations read the same active `published` snapshot at their start. A caller-supplied reference that differs from it fails with `SNAPSHOT_VERSION_MISMATCH`; missing active publication fails with `SNAPSHOT_NOT_PUBLISHED`.

## Risks / Trade-offs

- [Golden data has only query/node expectations] → Metrics cover deterministic technical search only; route/expand black-box suites can be added when fixture contracts are available.
- [Document text is basic Markdown] → Provenance and checksum are stable now; richer templates can remain consumer-side later.
- [No external adapter] → Failure/retry lifecycle is verified locally without violating the no-push boundary.

## Migration Plan

1. Apply migration 007 alongside the existing monotonic migrations.
2. Use the new CLI commands only after an active published snapshot exists.
3. Roll back by stopping consumer commands; no graph/mapping rollback is required because consumers do not mutate them.
