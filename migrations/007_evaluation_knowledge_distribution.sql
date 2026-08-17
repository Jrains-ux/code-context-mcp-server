ALTER TABLE evaluation_runs ADD COLUMN snapshot_id INTEGER REFERENCES snapshots(snapshot_id);
ALTER TABLE evaluation_runs ADD COLUMN source_revision TEXT;
ALTER TABLE evaluation_runs ADD COLUMN index_revision TEXT;
ALTER TABLE evaluation_runs ADD COLUMN config_version TEXT;
ALTER TABLE evaluation_runs ADD COLUMN tool_versions_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE evaluation_runs ADD COLUMN created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP;

CREATE TABLE IF NOT EXISTS failure_cases (
    failure_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES evaluation_runs(run_id),
    sample_json TEXT NOT NULL,
    expected_json TEXT NOT NULL,
    actual_json TEXT NOT NULL,
    code TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_artifacts (
    artifact_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    document_version TEXT NOT NULL,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(snapshot_id),
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS document_manifests (
    manifest_id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL REFERENCES document_artifacts(artifact_id),
    document_id TEXT NOT NULL,
    document_version TEXT NOT NULL,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(snapshot_id),
    source_revision TEXT NOT NULL,
    index_revision TEXT NOT NULL,
    config_version TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    generator_version TEXT NOT NULL,
    template_version TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS distribution_attempts (
    attempt_id TEXT PRIMARY KEY,
    manifest_id TEXT NOT NULL REFERENCES document_manifests(manifest_id),
    target TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    retryable INTEGER NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
