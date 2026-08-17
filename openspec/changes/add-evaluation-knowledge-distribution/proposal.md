## Why

The prototype has published snapshots, technical query, business confirmation, and incremental sync, but has no durable way to evaluate black-box behaviour, generate snapshot-bound knowledge, or track controlled distribution. TECH-06 completes the consumer-side lifecycle without allowing those consumers to mutate graph or mapping state.

## What Changes

- Add repeatable evaluation runs bound to a published snapshot and supplied dataset/golden-set versions.
- Persist evaluation metrics and failure cases, rejecting undersized datasets instead of claiming results.
- Generate technical and business document artifacts only from the active published snapshot; business artifacts require confirmed mappings.
- Persist document manifests with content checksums and add idempotent, local-only distribution attempts with retryable failures.
- Expose deterministic CLI commands for evaluation, knowledge generation, and local distribution while keeping all external targets disabled.

## Capabilities

### New Capabilities

- `evaluation-knowledge-distribution`: Version-bound black-box evaluation, confirmed-fact knowledge artifact generation, and controlled local distribution records.

### Modified Capabilities

- None.

## Impact

- Adds SQLite migration and consumer-side repositories/services under `src/code_context`.
- Extends the CLI with `evaluate`, `knowledge-generate`, and `knowledge-push` commands.
- Adds integration-style unit coverage in `tests/test_foundation.py` and local change documentation.
- Does not contact GitLab, Feishu Wiki, RAGFlow, or any remote system; the only supported adapter target is explicitly local.
