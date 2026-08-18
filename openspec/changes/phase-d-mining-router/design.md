## Context
Phase C provides versioned business nodes and multi-evidence mappings. Phase D needs an explicit boundary for Mining output and a callable route-selection flow.

## Decisions
- Mining accepts already-derived candidate artifacts; it does not infer business meaning or publish snapshots.
- `initial` and `incremental` are explicit modes and are recorded in `mining_runs`.
- Every candidate requires evidence and is stored as `candidate` with a version-bound route.
- Business routing reads only the active published snapshot; ambiguous contexts return `needs_user_selection`.
- Route selection remains bound to the snapshot through the existing expiring route token.

## Risks / Trade-offs
- Candidate generation remains an upstream AI/Skill responsibility and is not implemented here.
- Mining writes candidate records into the supplied snapshot; publication and confirmation gates remain caller responsibilities.
- RDC iteration and requirement identifiers were unavailable and are recorded as `unknown`.
