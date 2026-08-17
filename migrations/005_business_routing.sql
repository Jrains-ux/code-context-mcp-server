CREATE TABLE IF NOT EXISTS business_routes (
    route_id INTEGER PRIMARY KEY AUTOINCREMENT,
    term TEXT NOT NULL,
    biz_id TEXT NOT NULL,
    context_id TEXT NOT NULL,
    summary TEXT NOT NULL,
    node_scope_json TEXT NOT NULL,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(snapshot_id),
    UNIQUE(term, biz_id, context_id, snapshot_id)
);
CREATE TABLE IF NOT EXISTS route_tokens (
    token TEXT PRIMARY KEY,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(snapshot_id),
    candidates_json TEXT NOT NULL,
    expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS confirmation_audit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    mapping_id INTEGER NOT NULL REFERENCES mappings(mapping_id),
    decision TEXT NOT NULL,
    evidence_id INTEGER NOT NULL REFERENCES evidence(evidence_id),
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
