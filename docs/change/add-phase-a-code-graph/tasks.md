## 1. Graph artifact ingestion

- [x] 1.1 Add graph artifact value objects and a Python parser adapter for module, class, and function nodes.
- [x] 1.2 Extract contains, imports, and statically resolvable calls edges with source locations and evidence metadata.
- [x] 1.3 Add failing-then-passing tests for parser node and edge artifacts.

## 2. Snapshot persistence and publication

- [x] 2.1 Add additive, idempotent storage changes required for graph artifact metadata and graph query performance.
- [x] 2.2 Persist parser node/edge artifacts, evidence, and FTS rows as one validated staging unit.
- [x] 2.3 Extend Bootstrap results and tests to prove published snapshots contain nodes, edges, and indexes while rejected staging leaves the active snapshot unchanged.

## 3. Graph query paths

- [x] 3.1 Extend expansion inputs with direction, edge type, and node scope constraints.
- [x] 3.2 Reconstruct bounded BFS paths from traversed graph edges and return truncation metadata.
- [x] 3.3 Add failing-then-passing tests for edge filtering, scope filtering, path reconstruction, and budget truncation.

## 4. JSON-RPC stdio transport

- [x] 4.1 Add a line-oriented JSON-RPC 2.0 stdio dispatcher for supported graph operations.
- [x] 4.2 Add CLI entry routing and parameter validation without duplicating service logic.
- [x] 4.3 Add failing-then-passing unit and subprocess tests for valid and invalid stdio requests.

## 5. Verification and local handoff

- [x] 5.1 Run the complete Python test suite and strict OpenSpec validation.
- [x] 5.2 Copy OpenSpec artifacts to local change documentation and record TDD RED/GREEN evidence and test files.
