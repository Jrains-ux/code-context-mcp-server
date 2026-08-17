## Context

TECH-01 provides a local initialized runtime contract and an atomic snapshot pointer. TECH-02 must turn a fixed local source scope into the first consistent published graph without granting Bootstrap direct storage writes outside deterministic validation.

## Goals / Non-Goals

**Goals:**

- Admit a revision-bound source scope and persist task ownership.
- Extract a deterministic, minimal Python code graph into a staging snapshot.
- Store artifact manifests and conflict reports for every attempt.
- Enforce hash, evidence, revision, coverage, and expected-parent gates before publication.

**Non-Goals:**

- Parse non-Python languages, run external AI agents, or invoke Mining `initial`; Mining remains a TECH-04 concern under the supplied execution breakdown.
- Provide MCP stdio transport, search/index querying, business concepts, confirmation, or incremental updates.

## Decisions

- Add an additive migration for Bootstrap metadata rather than modifying existing baseline tables. This keeps existing local databases readable and preserves prior snapshots.
- Treat a Python module, class, and function as the prototype's supported node set. `ast` is part of the standard library and produces reproducible source locations without external parser dependencies.
- Use a canonical key of `file_path:qualified_name:kind`; duplicates, missing evidence, and revision divergence form explicit conflict reports rather than overwriting artifacts.
- Use one database transaction to persist accepted staged nodes/evidence and publish only after all validators pass. Failed gates keep the staging snapshot and report records for inspection.
- Require an explicit expected parent for publication. `None` is valid only when no active snapshot exists; any other mismatch fails closed.

## Risks / Trade-offs

- [Python-only extraction is incomplete for mixed-language repositories] → the manifest records scope and parser version; later packages can add language adapters without changing Bootstrap gates.
- [AST extraction misses semantic relationships] → only structural code facts are emitted; semantic mining and business mapping remain explicitly out of scope.
- [A failed build leaves local staging rows] → this is intentional auditability; later Admin lifecycle work can add staging cleanup.

## Migration Plan

1. Apply the additive migration to new or existing local context databases.
2. Bootstrap an isolated source fixture with a fixed revision and scope.
3. Inspect retained conflict reports if a gate rejects the attempt.
4. Rollback consists of retaining the previous active pointer; failed staging never replaces it.
