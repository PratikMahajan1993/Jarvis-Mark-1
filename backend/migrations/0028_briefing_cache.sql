-- Description: one-row cache for the 07:30 Asia/Kolkata morning brief
-- Dependencies: 0001

CREATE TABLE IF NOT EXISTS briefing_cache (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    local_date TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);
