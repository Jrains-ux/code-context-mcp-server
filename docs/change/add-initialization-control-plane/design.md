## Design summary

An additive `002` migration stores one canonical JSON-backed local manifest and its normalized declared permissions. `init` validates the declaration against the static allow-list, replaces the singleton manifest, and rebuilds the registry inside database transactions.

`health` and `doctor` report five deterministic aspects: schema, manifest, registry, active store, and derived runtime readiness. Runtime readiness requires every contract check plus an active published snapshot; an initialized but empty store returns `SERVICE_NOT_READY`.

This is deliberately local SQLite control-plane work. MCP transport, source parsing, Bootstrap, Query, Sync, Mining, Evaluation, Knowledge, and push remain out of scope.
