-- Description: write-ahead log so LanceDB mirror failures are retried without failing the SQLite upsert
-- Dependencies: 0010

CREATE TABLE IF NOT EXISTS lance_wal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation TEXT NOT NULL,
    namespace TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    payload TEXT,
    created_at TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT
);

CREATE INDEX IF NOT EXISTS idx_lance_wal_pending ON lance_wal(attempts, created_at);
