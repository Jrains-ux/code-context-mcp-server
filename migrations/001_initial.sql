PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS manifests (
    manifest_id TEXT PRIMARY KEY,
    source_root TEXT NOT NULL,
    source_revision TEXT NOT NULL,
    scope_json TEXT NOT NULL,
    exclude_json TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    config_version TEXT NOT NULL,
    workspace_clean INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_revision TEXT NOT NULL,
    index_revision TEXT NOT NULL,
    config_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('staging', 'candidate', 'published', 'rejected', 'stale', 'rebuilding')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS active_snapshot (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(snapshot_id)
);

CREATE TABLE IF NOT EXISTS nodes (
    node_id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(snapshot_id),
    kind TEXT NOT NULL,
    sub_kind TEXT,
    source_revision TEXT NOT NULL,
    index_revision TEXT NOT NULL,
    config_version TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    stale INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS edges (
    edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(snapshot_id),
    from_node_id INTEGER NOT NULL REFERENCES nodes(node_id),
    to_node_id INTEGER NOT NULL REFERENCES nodes(node_id),
    edge_type TEXT NOT NULL,
    source_revision TEXT NOT NULL,
    index_revision TEXT NOT NULL,
    config_version TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    stale INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_revision TEXT NOT NULL,
    index_revision TEXT NOT NULL,
    config_version TEXT NOT NULL,
    file_path TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    snippet_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER IF NOT EXISTS evidence_immutable
BEFORE UPDATE ON evidence
BEGIN
    SELECT RAISE(ABORT, 'evidence is immutable');
END;

CREATE TABLE IF NOT EXISTS mappings (
    mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
    biz_id TEXT NOT NULL,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(snapshot_id),
    status TEXT NOT NULL,
    expected_version INTEGER,
    review_required INTEGER NOT NULL DEFAULT 0,
    evidence_id INTEGER REFERENCES evidence(evidence_id),
    replacement_evidence_id INTEGER REFERENCES evidence(evidence_id)
);

CREATE TABLE IF NOT EXISTS stale_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    mapping_id INTEGER NOT NULL REFERENCES mappings(mapping_id),
    dependency_type TEXT NOT NULL,
    old_revision TEXT NOT NULL,
    new_revision TEXT NOT NULL,
    reason TEXT NOT NULL,
    replacement_ref TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS update_operations (
    operation_id TEXT PRIMARY KEY,
    baseline_ref TEXT,
    source_revision TEXT NOT NULL,
    indexed_source_revision TEXT,
    current_index_revision TEXT,
    config_version TEXT NOT NULL,
    status TEXT NOT NULL,
    coverage_json TEXT,
    conflicts_json TEXT
);

CREATE TABLE IF NOT EXISTS evaluation_runs (
    run_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    golden_set_version TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    threshold_status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS route_audit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_token TEXT NOT NULL,
    selected_context_id TEXT,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(snapshot_id),
    action TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tool_registry (
    tool_name TEXT PRIMARY KEY,
    skill TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1
);
