## 1. Bootstrap persistence and validation

- [x] 1.1 Add idempotent SQLite storage for bootstrap artifact manifests, task runs, and conflict reports.
- [x] 1.2 Add revision, canonical-key, evidence, coverage, and expected-parent validation helpers.

## 2. First-build implementation

- [x] 2.1 Implement scoped Bootstrap admission and mutually exclusive extraction task allocation.
- [x] 2.2 Implement deterministic Python AST artifact extraction and staged persistence.
- [x] 2.3 Implement Bootstrap validation, conflict reporting, and atomic publish orchestration.
- [x] 2.4 Add the local `bootstrap` CLI command with source and revision inputs.

## 3. TDD verification

- [x] 3.1 Add failing-then-passing tests for admission, extraction, conflicts, coverage, parent CAS, and active-snapshot preservation.
- [x] 3.2 Run the complete Python test suite, compile checks, Bootstrap CLI fixture, and OpenSpec validation.

## 4. Execution records

- [x] 4.1 Copy OpenSpec artifacts to the local change report and write the TECH-02 execution summary.
