## Why
Phase C stores business mappings, but Bootstrap/Sync callers cannot submit candidate business artifacts through a deterministic Mining boundary and external clients cannot complete route selection.

## What Changes
- Add initial/incremental Mining candidate orchestration.
- Persist mining run status and candidate business mappings/routes.
- Expose Mining, business-context resolve, and context-select tools through the command and MCP adapters.

## Capabilities
### New Capabilities
- `business-mining-router`: candidate Mining and version-bound route selection.

### Modified Capabilities
- None.

## Impact
Adds migration `010_phase_d_mining.sql`, extends the business service and MCP command surface, and adds deterministic fixture tests. AI inference, automatic confirmation, Git diff, and snapshot publication remain out of scope.
