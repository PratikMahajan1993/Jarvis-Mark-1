-- Description: owner draft autosave (Engineering, baton)
-- Dependencies: 0001

CREATE TABLE IF NOT EXISTS drafts (
    key TEXT PRIMARY KEY,
    body TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL
);
