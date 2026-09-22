CREATE TABLE turns (
  id                TEXT PRIMARY KEY,
  session_id        TEXT NOT NULL,
  idempotency_key   TEXT NOT NULL UNIQUE,
  state             TEXT NOT NULL,
  stage             TEXT NOT NULL DEFAULT '',
  input             TEXT NOT NULL,
  route             TEXT NOT NULL DEFAULT '',
  output_json       TEXT NOT NULL DEFAULT '',
  pending_action_id TEXT,
  mission_id        TEXT,
  lease_owner       TEXT NOT NULL DEFAULT '',
  heartbeat_at      TEXT,
  lease_expires_at  TEXT,
  attempt           INTEGER NOT NULL DEFAULT 1,
  error             TEXT NOT NULL DEFAULT '',
  created_at        TEXT NOT NULL,
  updated_at        TEXT NOT NULL
);
CREATE INDEX turns_open ON turns(session_id, state);
CREATE INDEX turns_lease ON turns(state, lease_expires_at);
