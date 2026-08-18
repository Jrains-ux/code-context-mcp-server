CREATE TABLE IF NOT EXISTS distribution_targets (
    target TEXT PRIMARY KEY,
    endpoint TEXT NOT NULL,
    options_json TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1
);
