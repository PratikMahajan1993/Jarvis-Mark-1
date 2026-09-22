-- Versioned NC program store (M6): drafts and owner-promoted rows only (no transmit).

CREATE TABLE nc_programs (
  id TEXT PRIMARY KEY,
  machine_id TEXT NOT NULL REFERENCES machines(id),
  version INTEGER NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('draft', 'promoted')),
  body TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL,
  promoted_at TEXT,
  UNIQUE (machine_id, version)
);

CREATE INDEX idx_nc_programs_machine ON nc_programs (machine_id, version DESC);
