CREATE TABLE IF NOT EXISTS artifact_manifests (
    artifact_id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(snapshot_id),
    canonical_key TEXT NOT NULL,
    kind TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    evidence_id INTEGER NOT NULL REFERENCES evidence(evidence_id),
    payload_json TEXT NOT NULL,
    UNIQUE(snapshot_id, canonical_key)
);

CREATE TABLE IF NOT EXISTS task_runs (
    task_id TEXT PRIMARY KEY,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(snapshot_id),
    scope TEXT NOT NULL,
    source_revision TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conflict_reports (
    conflict_id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(snapshot_id),
    code TEXT NOT NULL,
    detail_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
