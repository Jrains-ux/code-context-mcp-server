## Why

TECH-01 completes the initialization control plane that TECH-00 left as a static baseline: a local project must retain its manifest and fail closed until runtime prerequisites are valid.

## What Changes

- Persist a project manifest and declared Skill-to-tool permission contract.
- Synchronize the MCP registry from the manifest on initialization.
- Add fail-closed `health` and enhanced `doctor` diagnostics.
- Support explicit CLI project, workspace, source-revision, and configuration-version inputs.

## Impact

SQLite migration, initialization repository, CLI dispatcher, registry diagnostics, and foundation tests are updated. No network service or later execution-package behavior is included.
