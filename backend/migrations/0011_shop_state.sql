-- Shop floor event log + materialised shop_state projection (K6).

CREATE TABLE downtime_reasons (
  code TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  category TEXT NOT NULL
);

CREATE TABLE production_logs (
  id TEXT PRIMARY KEY,
  shift TEXT NOT NULL,
  log_date TEXT NOT NULL,
  machine_id TEXT REFERENCES machines(id),
  qty_ok INTEGER NOT NULL DEFAULT 0,
  qty_rework INTEGER NOT NULL DEFAULT 0,
  qty_scrap INTEGER NOT NULL DEFAULT 0,
  scrap_cause TEXT,
  run_min REAL,
  downtime_min REAL,
  downtime_reason TEXT REFERENCES downtime_reasons(code),
  oee_pct REAL,
  source_ref TEXT NOT NULL DEFAULT '',
  operator TEXT
);

CREATE TABLE shop_state (
  key TEXT PRIMARY KEY,
  payload TEXT NOT NULL,
  as_of TEXT NOT NULL,
  derived_from TEXT NOT NULL
);
