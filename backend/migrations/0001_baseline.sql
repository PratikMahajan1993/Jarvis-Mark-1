-- Baseline schema (former init_db CREATE script + additive column patches).
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    tool TEXT NOT NULL,
    detail TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mission_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    mission_id TEXT NOT NULL,
    step INTEGER NOT NULL,
    role TEXT NOT NULL,
    detail TEXT NOT NULL,
    latency_ms INTEGER,
    status TEXT NOT NULL,
    tokens INTEGER,
    cost REAL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mission_steps_mission
    ON mission_steps(mission_id, step);
CREATE TABLE IF NOT EXISTS pending_actions (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    agent_id TEXT DEFAULT '',
    tool_name TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS preferences (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS emails (
    id TEXT PRIMARY KEY,
    sender TEXT NOT NULL,
    to_addr TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    unread INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    folder TEXT NOT NULL,
    thread_id TEXT,
    attachments TEXT
);
CREATE TABLE IF NOT EXISTS calendar_events (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    location TEXT,
    notes TEXT
);
CREATE TABLE IF NOT EXISTS inbox_files (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    path TEXT
);
CREATE TABLE IF NOT EXISTS thought_state (
    session_id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS working_set (
    session_id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hud_state (
    session_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS watches (
    session_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    after_id TEXT,
    status TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    focus TEXT NOT NULL,
    minimized INTEGER NOT NULL DEFAULT 1,
    expanded_at TEXT,
    status TEXT NOT NULL DEFAULT 'ready',
    model TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS conversations_updated ON conversations (updated_at);
CREATE TABLE IF NOT EXISTS canvas_boards (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    camera TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS canvas_items (
    id TEXT PRIMARY KEY,
    board_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    x REAL NOT NULL DEFAULT 0,
    y REAL NOT NULL DEFAULT 0,
    w REAL NOT NULL DEFAULT 0,
    h REAL NOT NULL DEFAULT 0,
    rotation REAL NOT NULL DEFAULT 0,
    z INTEGER NOT NULL DEFAULT 0,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS canvas_items_board ON canvas_items (board_id);
CREATE TABLE IF NOT EXISTS canvas_files (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    mime TEXT NOT NULL,
    path TEXT NOT NULL,
    width REAL NOT NULL DEFAULT 0,
    height REAL NOT NULL DEFAULT 0,
    page_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS work_snapshot (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    mail_synced_at TEXT,
    calendar_synced_at TEXT,
    mail_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS mail_sync_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    status TEXT NOT NULL DEFAULT 'idle',
    days INTEGER NOT NULL DEFAULT 0,
    synced_count INTEGER NOT NULL DEFAULT 0,
    skipped_count INTEGER NOT NULL DEFAULT 0,
    page_token TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL DEFAULT '',
    finished_at TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    customer TEXT NOT NULL,
    part_name TEXT NOT NULL,
    material TEXT NOT NULL,
    machine TEXT NOT NULL,
    cycle_min REAL,
    margin REAL,
    drawing_file TEXT,
    geometry_notes TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_material ON jobs (material);
CREATE INDEX IF NOT EXISTS jobs_material_lc ON jobs (lower(material));
CREATE TABLE IF NOT EXISTS rfqs (
    id TEXT PRIMARY KEY,
    mail_id TEXT,
    conversation_id TEXT,
    status TEXT NOT NULL,
    extract TEXT NOT NULL,
    similar_job_ids TEXT NOT NULL,
    pending_reply TEXT,
    deadline_iso TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS rfqs_status ON rfqs (status);
ALTER TABLE emails ADD COLUMN thread_id TEXT;
ALTER TABLE emails ADD COLUMN attachments TEXT;
ALTER TABLE inbox_files ADD COLUMN path TEXT;
ALTER TABLE jobs ADD COLUMN geometry_notes TEXT;
ALTER TABLE rfqs ADD COLUMN updated_at TEXT;
ALTER TABLE pending_actions ADD COLUMN agent_id TEXT DEFAULT '';
ALTER TABLE pending_actions ADD COLUMN tool_name TEXT DEFAULT '';
