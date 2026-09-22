CREATE TABLE rag_documents (
  id TEXT PRIMARY KEY,
  uri TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  doc_kind TEXT NOT NULL,
  namespace TEXT NOT NULL,
  authored_by TEXT NOT NULL DEFAULT 'external',
  entity_type TEXT,
  entity_id TEXT,
  effective_date TEXT,
  retention TEXT NOT NULL DEFAULT 'keep',
  indexed_at TEXT,
  UNIQUE (sha256, namespace)
);

CREATE TABLE rag_chunks (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL REFERENCES rag_documents(id),
  ordinal INTEGER NOT NULL,
  section TEXT NOT NULL DEFAULT '',
  text TEXT NOT NULL,
  text_sha256 TEXT NOT NULL,
  token_count INTEGER NOT NULL DEFAULT 0,
  embedding_model TEXT NOT NULL,
  embedding_dim INTEGER NOT NULL,
  vector BLOB,
  indexed_at TEXT,
  UNIQUE (document_id, ordinal)
);

CREATE INDEX rag_chunks_sha ON rag_chunks(text_sha256);

CREATE VIRTUAL TABLE rag_fts USING fts5(text, content='rag_chunks', content_rowid='rowid');

CREATE TABLE rag_index_state (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  pending INTEGER NOT NULL DEFAULT 0,
  embedded INTEGER NOT NULL DEFAULT 0,
  model TEXT NOT NULL DEFAULT '',
  last_error TEXT NOT NULL DEFAULT '',
  updated_at TEXT
);

INSERT INTO rag_index_state (id, pending, embedded, model, last_error, updated_at)
VALUES (1, 0, 0, '', '', NULL);
