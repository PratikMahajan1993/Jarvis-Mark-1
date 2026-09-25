-- Minimum record for a drawing dropped onto the orb. Bytes stay on disk.

CREATE TABLE dropped_drawings (
  id TEXT PRIMARY KEY,
  sha256 TEXT NOT NULL UNIQUE,
  filename TEXT NOT NULL,
  stored_name TEXT NOT NULL,
  path TEXT NOT NULL,
  mime TEXT NOT NULL,
  byte_size INTEGER NOT NULL,
  created_at TEXT NOT NULL
);
