## Why
Phase A/B provides a versioned technical graph, but business requirements cannot yet be represented or confirmed with more than one evidence reference.

## What Changes
- Add version-bound business nodes to published snapshots.
- Extend mappings with requirement, anchor, evidence, review, risk, confidence, and audit metadata.
- Preserve all mapping evidence during confirmation and expose confirmation through the MCP tool surface.

## Capabilities
### New Capabilities
- `business-mapping`: business node and multi-evidence mapping lifecycle.

### Modified Capabilities
- `business-routing-confirmation`: confirmation records all evidence and review metadata.

## Impact
Adds migration `009_phase_c_business_mapping.sql` and modifies the repository, confirmation service, MCP command adapter, and existing tests. Mining, Git Sync, catalog publication, and semantic retrieval remain out of scope.
