-- Description: record embedding model id, dimension, and provider on each memory vector
-- Dependencies: 0010

CREATE TABLE IF NOT EXISTS memory_docs (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    key TEXT NOT NULL,
    text TEXT NOT NULL,
    meta TEXT NOT NULL,
    vector TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    embed_model_id TEXT,
    embed_dim INTEGER,
    embed_provider TEXT,
    UNIQUE(namespace, key)
);

ALTER TABLE memory_docs ADD COLUMN embed_model_id TEXT;
ALTER TABLE memory_docs ADD COLUMN embed_dim INTEGER;
ALTER TABLE memory_docs ADD COLUMN embed_provider TEXT;
