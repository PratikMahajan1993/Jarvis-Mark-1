CREATE TABLE IF NOT EXISTS external_effects (
  id TEXT PRIMARY KEY,
  action_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  state TEXT NOT NULL,
  provider_message_id TEXT,
  error TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  settled_at TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS external_effects_dedupe ON external_effects(provider, request_hash);

ALTER TABLE pending_actions ADD COLUMN claim_id TEXT;
ALTER TABLE pending_actions ADD COLUMN claimed_at TEXT;

CREATE TABLE IF NOT EXISTS confirm_idempotency (
  idempotency_key TEXT PRIMARY KEY,
  action_id TEXT NOT NULL,
  approved INTEGER NOT NULL,
  response_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
