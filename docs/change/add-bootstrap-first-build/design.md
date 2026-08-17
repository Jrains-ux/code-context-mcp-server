## Design summary

The prototype adds an additive SQLite migration for artifact manifests, extraction task runs, and conflict reports. Bootstrap uses standard-library Python AST extraction to create module/class/function artifacts with source hashes and immutable evidence. All gates run before calling the established atomic publisher; rejected artifacts retain their staging snapshot and report while the active pointer remains unchanged.
