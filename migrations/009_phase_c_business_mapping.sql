CREATE TABLE IF NOT EXISTS business_nodes (
    business_node_id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(snapshot_id),
    node_type TEXT NOT NULL,
    canonical_key TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('candidate', 'confirmed', 'rejected', 'stale')),
    source_revision TEXT NOT NULL,
    index_revision TEXT NOT NULL,
    config_version TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(snapshot_id, canonical_key)
);

ALTER TABLE mappings ADD COLUMN requirement_id TEXT;
ALTER TABLE mappings ADD COLUMN anchor_node_ids_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE mappings ADD COLUMN evidence_refs_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE mappings ADD COLUMN review_mode TEXT;
ALTER TABLE mappings ADD COLUMN risk_level TEXT;
ALTER TABLE mappings ADD COLUMN confidence REAL;
ALTER TABLE mappings ADD COLUMN review_batch_id TEXT;
ALTER TABLE mappings ADD COLUMN updated_by TEXT;
ALTER TABLE mappings ADD COLUMN created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE mappings ADD COLUMN updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP;

CREATE TABLE IF NOT EXISTS mapping_evidence (
    mapping_id INTEGER NOT NULL REFERENCES mappings(mapping_id),
    evidence_id INTEGER NOT NULL REFERENCES evidence(evidence_id),
    role TEXT NOT NULL DEFAULT 'supporting',
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(mapping_id, evidence_id)
);

ALTER TABLE confirmation_audit ADD COLUMN evidence_refs_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE confirmation_audit ADD COLUMN review_mode TEXT;
ALTER TABLE confirmation_audit ADD COLUMN updated_by TEXT;
