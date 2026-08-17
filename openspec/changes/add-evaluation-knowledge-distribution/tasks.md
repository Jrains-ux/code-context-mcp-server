## 1. Consumer-side persistence

- [x] 1.1 Add a versioned migration for evaluation, document, manifest, and distribution-attempt records.
- [x] 1.2 Add repository operations that persist and retrieve evaluation, document, manifest, and idempotent attempt state without mutating graph tables.

## 2. Evaluation and knowledge services

- [x] 2.1 Add failing tests for insufficient datasets and persisted version-bound evaluation metrics/failure cases.
- [x] 2.2 Implement deterministic black-box technical-query evaluation with snapshot consistency validation.
- [x] 2.3 Add failing tests for technical provenance, confirmed-only business documents, and manifest checksums.
- [x] 2.4 Implement deterministic technical/business knowledge generation from the active published snapshot.

## 3. Controlled distribution and CLI

- [x] 3.1 Add failing tests for local idempotent push and retryable unsupported-target failure without graph mutation.
- [x] 3.2 Implement local-only distribution attempts and retry state.
- [x] 3.3 Extend CLI commands and arguments for evaluation, knowledge generation, and controlled push.

## 4. Verification and delivery artifacts

- [x] 4.1 Run focused and full test suites plus strict OpenSpec validation.
- [x] 4.2 Produce the TECH-06 TDD report, test-file list, and local execution summary.
