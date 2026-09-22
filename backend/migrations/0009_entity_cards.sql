CREATE TABLE entity_cards (
  id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '',
  summary_embedding_id TEXT,
  fact_count INTEGER NOT NULL DEFAULT 0,
  confirmed_count INTEGER NOT NULL DEFAULT 0,
  open_questions TEXT NOT NULL DEFAULT '[]',
  updated_at TEXT NOT NULL,
  UNIQUE (entity_type, entity_id)
);
CREATE TABLE entity_facts (
  id TEXT PRIMARY KEY,
  card_id TEXT NOT NULL REFERENCES entity_cards(id),
  field TEXT NOT NULL,
  value TEXT NOT NULL, unit TEXT NOT NULL DEFAULT '',
  numeric_value REAL,
  source_kind TEXT NOT NULL CHECK (source_kind IN
    ('owner_confirmed','customer_mail','title_block','vision_suggestion','measured','computed','jarvis_inference')),
  source_ref TEXT NOT NULL DEFAULT '',
  confidence REAL NOT NULL DEFAULT 0,
  state TEXT NOT NULL DEFAULT 'candidate'
    CHECK (state IN ('candidate','confirmed','rejected','superseded')),
  confirmed_by TEXT, confirmed_at TEXT,
  confirmed_from TEXT,
  superseded_by TEXT REFERENCES entity_facts(id),
  expires_at TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX entity_facts_card ON entity_facts(card_id, state, field);
