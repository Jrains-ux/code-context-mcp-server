## 1. Git impact analysis
- [x] 1.1 Parse Git A/M/D/R output including rename paths.
- [x] 1.2 Locate affected nodes by source file and calculate graph dependency closure.

## 2. Stale governance
- [x] 2.1 Mark only affected anchored mappings stale after successful rebuild.
- [x] 2.2 Preserve mapping state when rebuild fails.
- [x] 2.3 Persist impact and stale result details for idempotent operations.

## 3. Verification
- [x] 3.1 Add RED/GREEN tests for diff parsing, closure filtering, and failure isolation.
- [x] 3.2 Run full pytest, compileall, and git diff check.
