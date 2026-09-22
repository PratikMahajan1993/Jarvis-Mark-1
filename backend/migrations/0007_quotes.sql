-- Quotes, revisions, lines, proofs, events (§4.3 — S4).
CREATE TABLE quotes (
  id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id),
  rfq_ref TEXT, mail_id TEXT, conversation_id TEXT,
  status TEXT NOT NULL DEFAULT 'open'
);
CREATE TABLE quote_revisions (
  id TEXT PRIMARY KEY, quote_id TEXT NOT NULL REFERENCES quotes(id),
  revision INTEGER NOT NULL, part_revision_id TEXT REFERENCES part_revisions(id),
  routing_id TEXT REFERENCES routings(id),
  scope TEXT NOT NULL CHECK (scope IN ('labour','with_material')),
  scope_source TEXT NOT NULL,
  qty INTEGER NOT NULL, currency TEXT NOT NULL DEFAULT 'INR',
  total_minor INTEGER NOT NULL DEFAULT 0, margin_pct REAL,
  delivery_days INTEGER,
  delivery_entered_by TEXT, delivery_entered_at TEXT,
  notes TEXT,
  frozen INTEGER NOT NULL DEFAULT 0,
  pdf_artifact_id TEXT, pdf_sha256 TEXT,
  UNIQUE (quote_id, revision)
);
CREATE TABLE quote_lines (
  id TEXT PRIMARY KEY, quote_revision_id TEXT NOT NULL REFERENCES quote_revisions(id),
  seq INTEGER NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('material','machining','outsource','tooling','inspection','freight','other')),
  description TEXT NOT NULL,
  qty REAL NOT NULL, qty_unit TEXT NOT NULL,
  rate_minor INTEGER NOT NULL, amount_minor INTEGER NOT NULL,
  machine_id TEXT REFERENCES machines(id), time_min REAL,
  rate_source_kind TEXT NOT NULL,
  rate_source_id TEXT NOT NULL,
  is_estimate INTEGER NOT NULL DEFAULT 0, estimate_basis TEXT NOT NULL DEFAULT '',
  CHECK (rate_minor >= 0 AND qty > 0),
  UNIQUE (quote_revision_id, seq)
);
CREATE TABLE quote_proofs (
  id TEXT PRIMARY KEY, quote_revision_id TEXT NOT NULL REFERENCES quote_revisions(id),
  verdict TEXT NOT NULL,
  blockers INTEGER NOT NULL DEFAULT 0, warnings INTEGER NOT NULL DEFAULT 0,
  checklist_json TEXT NOT NULL, pdf_sha256 TEXT, created_at TEXT NOT NULL
);
CREATE TABLE quote_events (
  id TEXT PRIMARY KEY, quote_revision_id TEXT NOT NULL REFERENCES quote_revisions(id),
  event TEXT NOT NULL,
  detail TEXT, external_effect_id TEXT REFERENCES external_effects(id), created_at TEXT NOT NULL
);
