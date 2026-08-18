# Design

- Evaluation accepts `mode=business`; it resolves the business route before querying node scope and reports route accuracy, precision, recall, and existing version-bound metrics.
- Knowledge generation accepts an optional impact node set. The published snapshot and evidence manifest remain the source of truth; unconfirmed mappings remain rejected.
- Distribution targets are explicitly registered with HTTPS endpoints and options. Push is idempotent and never mutates graph or mapping state; unknown targets fail retryably.
- Acceptance gates compare measured metrics against caller-provided thresholds and fail closed with `ACCEPTANCE_GATE_FAILED`.

