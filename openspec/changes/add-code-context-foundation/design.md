## Context

The target repository is an empty Python project. TECH-00 defines a local MCP data plane with SQLite/FTS5 as the prototype storage direction, version-bound snapshots, staging/published separation, immutable evidence, and a seven-skill permission matrix. The implementation must leave later Bootstrap, Query, Sync, Evaluation, Knowledge, and Admin workflows attachable without introducing external services.

## Goals / Non-Goals

**Goals:**

- Make the storage foundation executable and testable from a clean checkout.
- Keep all records tied to `source_revision`, `index_revision`, and `config_version`.
- Enforce atomic publication and fail-closed validation in one local transaction.
- Provide a small registry and CLI for initialization and diagnosis.

**Non-Goals:**

- Parsing real source repositories or building a code graph.
- Implementing the MCP transport, external AI adapters, or runtime Skills.
- Implementing query, incremental update, business mining, evaluation, or knowledge distribution.
- Depending on the downloaded CodeGraphContext project.

## Decisions

1. **Python standard library first.** Use `sqlite3`, `argparse`, and JSON rather than adding dependencies while the repository is empty. This keeps the prototype runnable offline and preserves adapter boundaries for later replacements.
2. **Single SQLite database with migrations.** Store the foundation records in one file and apply numbered SQL migrations inside a transaction. This matches the prototype scope and makes fixtures deterministic.
3. **JSON payload columns for evolving typed data.** Keep stable identity/version columns relational and store kind-specific payloads as JSON. This avoids premature schema churn while preserving the TECH-00 model.
4. **Registry data is code-defined and persisted for diagnosis.** The permission matrix is a single source of truth in Python, mirrored into the database during migration, so doctor can detect drift.
5. **Publish is a guarded transaction.** Validate all staging artifact revisions before updating the active snapshot pointer; a failure leaves the previous published pointer unchanged.

## Risks / Trade-offs

- [Risk] SQLite write concurrency is limited. → Use one writer transaction and keep the storage adapter replaceable.
- [Risk] JSON payloads defer strict per-kind validation. → Validate required envelope/version fields now and keep kind-specific validators explicit for later packages.
- [Risk] The prototype has no real repository benchmark. → Keep performance claims out of the implementation and add only fixture-scale tests.

## Migration Plan

`init` creates the database and applies all numbered migrations. `migrate` applies pending migrations transactionally. Rollback for a failed migration is SQLite transaction rollback; rollback of a published snapshot is pointer restoration to the previous published snapshot.
