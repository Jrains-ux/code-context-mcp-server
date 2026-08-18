## Context
The current database has technical nodes/evidence and a minimal `mappings` row. Phase C needs business artifacts and a mapping lifecycle without changing the technical graph contract.

## Decisions
- Store business nodes in the same snapshot/version model as technical artifacts.
- Store mapping anchors and evidence references as JSON projections, with `mapping_evidence` as the queryable relation.
- Keep `candidate`, `confirmed`, `rejected`, and `stale` as explicit mapping states.
- Keep confirmation CAS semantics and write one immutable audit record containing the complete evidence set and review metadata.
- Expose confirmation as an MCP `tools/call` tool while keeping Mining and Sync orchestration outside this change.

## Risks / Trade-offs
- JSON projections require application-level validation and are not yet a full concept catalog.
- Existing mappings remain compatible through additive migration defaults.
- No RDC iteration or requirement identifiers were available in this session; delivery metadata is therefore `unknown`.
