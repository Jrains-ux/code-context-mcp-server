## 1. Initialization contract persistence

- [x] 1.1 Add an idempotent SQLite migration for the singleton initialization manifest and manifest-declared tool registrations.
- [x] 1.2 Add repository and policy operations that validate, persist, load, and synchronize the manifest contract atomically.

## 2. CLI health gate

- [x] 2.1 Extend `init` with project, workspace, source revision, and configuration version inputs, preserving default local operation.
- [x] 2.2 Add `health` and enhance `doctor` to report schema, manifest, registry, store, and fail-closed runtime readiness diagnostics.

## 3. TDD verification

- [x] 3.1 Add failing-then-passing tests for valid initialization, invalid manifests, registry drift, and published-snapshot readiness.
- [x] 3.2 Run the complete Python test suite, compile checks, CLI fixture verification, and OpenSpec validation.

## 4. Execution records

- [x] 4.1 Copy the completed OpenSpec artifacts into the local change report and write the TECH-01 TDD execution summary.
