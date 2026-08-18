CREATE TABLE IF NOT EXISTS mining_runs (
    run_id TEXT PRIMARY KEY,
    mode TEXT NOT NULL CHECK (mode IN ('initial', 'incremental')),
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(snapshot_id),
    candidate_count INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('candidate', 'rejected')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
