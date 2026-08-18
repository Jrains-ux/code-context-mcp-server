ALTER TABLE sync_operations ADD COLUMN changes_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE sync_operations ADD COLUMN affected_node_ids_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE sync_operations ADD COLUMN closure_node_ids_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE sync_operations ADD COLUMN stale_mapping_ids_json TEXT NOT NULL DEFAULT '[]';
