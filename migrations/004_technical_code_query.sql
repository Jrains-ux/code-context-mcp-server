CREATE VIRTUAL TABLE IF NOT EXISTS node_fts USING fts5(
    node_id UNINDEXED,
    snapshot_id UNINDEXED,
    name,
    qualified_name,
    file_path,
    content_hash
);
