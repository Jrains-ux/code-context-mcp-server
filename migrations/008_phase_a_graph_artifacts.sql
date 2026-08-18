ALTER TABLE nodes ADD COLUMN canonical_key TEXT;
ALTER TABLE nodes ADD COLUMN evidence_id INTEGER REFERENCES evidence(evidence_id);
ALTER TABLE edges ADD COLUMN evidence_id INTEGER REFERENCES evidence(evidence_id);
ALTER TABLE evidence ADD COLUMN parser TEXT NOT NULL DEFAULT 'legacy';
ALTER TABLE evidence ADD COLUMN confidence TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE evidence ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}';

CREATE UNIQUE INDEX IF NOT EXISTS nodes_snapshot_canonical_key
    ON nodes(snapshot_id, canonical_key)
    WHERE canonical_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS edges_snapshot_from_node
    ON edges(snapshot_id, from_node_id);
CREATE INDEX IF NOT EXISTS edges_snapshot_to_node
    ON edges(snapshot_id, to_node_id);
CREATE INDEX IF NOT EXISTS evidence_revision_lookup
    ON evidence(source_revision, index_revision, config_version);
