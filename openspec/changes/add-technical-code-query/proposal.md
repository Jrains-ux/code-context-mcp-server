## Why

Published Bootstrap facts cannot yet be consumed by technical callers. TECH-03 provides read-only code search and graph expansion without modifying the published snapshot.

## What Changes

- Add a published-snapshot lexical index and technical node search.
- Add version-bound relation expansion with depth and node/edge budgets.
- Return evidence references, matched fields, snapshot references, and truncation state.

## Capabilities

### New Capabilities

- `technical-code-query`: Read-only lexical node search and relationship traversal over one published snapshot.

### Modified Capabilities

- None.

## Impact

Adds SQLite index data, query service and CLI commands. It does not implement business routing, Mining, Sync, or writes to graph facts during queries.
