## 1. Mining
- [x] 1.1 Add explicit initial/incremental Mining run storage.
- [x] 1.2 Persist evidence-backed candidate business nodes, mappings, and route candidates.
- [x] 1.3 Reject invalid modes and evidence-free candidates.

## 2. BusinessRouter tools
- [x] 2.1 Expose `mine` through the command adapter.
- [x] 2.2 Expose `resolve_business_context` and `select_business_context` through the command adapter.
- [x] 2.3 Advertise the Phase D tools through MCP `tools/list` and dispatch them through `tools/call`.

## 3. Verification
- [x] 3.1 Add RED/GREEN tests for Mining persistence and route selection.
- [x] 3.2 Run full pytest, compileall, and git diff check.
