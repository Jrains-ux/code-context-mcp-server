CREATE TABLE IF NOT EXISTS sync_operations (
    operation_id TEXT PRIMARY KEY,
    baseline_ref INTEGER NOT NULL,
    target_source_revision TEXT NOT NULL,
    result_json TEXT NOT NULL
);
