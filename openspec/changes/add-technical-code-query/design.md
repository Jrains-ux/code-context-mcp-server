## Context

TECH-02 creates version-bound published nodes and edges. TECH-03 must expose them read-only with a lightweight local lexical index and bounded traversal.

## Goals / Non-Goals

**Goals:** published-only search, evidence/version result assembly, and budgeted graph expansion.

**Non-Goals:** business routing, automatic index repair, semantic expansion, query-result persistence, or any update path.

## Decisions

- Use an additive SQLite FTS5 table populated from published snapshot node payloads; no index is consulted for staging snapshots.
- Build/refresh index explicitly after successful publication in Bootstrap. Query raises `INDEX_UNAVAILABLE` if the published snapshot lacks indexed rows.
- Traverse existing edges with breadth-first expansion, respecting direction, edge types, depth, node budget, and edge budget. Never cross snapshot IDs.

## Risks / Trade-offs

- [FTS availability varies by SQLite build] → detect missing rows and return `INDEX_UNAVAILABLE`, never an empty success.
- [Prototype has few edges] → traversal contract and limits are still verified with fixture edges; richer edge extraction remains later work.
