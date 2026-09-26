-- Description: chat-logged shop-floor events projected into the existing shop_state table
-- Dependencies: 0011

CREATE TABLE IF NOT EXISTS shop_events (
    id TEXT PRIMARY KEY,
    ts TEXT NOT NULL,
    kind TEXT NOT NULL,
    machine_id TEXT,
    machine_name TEXT,
    component_id TEXT,
    value REAL,
    unit TEXT,
    details TEXT,
    source TEXT,
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS shop_events_kind_ts ON shop_events(kind, ts);
