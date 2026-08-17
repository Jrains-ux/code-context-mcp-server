## Context

Sync reuses the established Bootstrap staging flow but must be explicit, baseline-bound, and idempotent.

## Goals / Non-Goals

**Goals:** validate active baseline, persist operation results, append stale events, and publish only through expected-parent staging.

**Non-Goals:** Git-provider A/M/D/R integration, automatic Query updates, or incremental Mining semantics.

## Decisions

- Persist the first result under `operation_id`; duplicate requests return it unchanged.
- Mark prior mappings stale and append `stale_events` before building the replacement snapshot.
- Reuse Bootstrap with the active snapshot as expected parent, so failure retains the existing active pointer.

## Risks / Trade-offs

The local prototype scans caller-provided scope rather than integrating a Git diff adapter. Provider-level diff and dependency closure remain future work.
