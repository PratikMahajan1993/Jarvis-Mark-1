-- Quote-to-actual variance ledger (M1): production actuals per quote line.
CREATE TABLE quote_actuals (
  id TEXT PRIMARY KEY,
  quote_line_id TEXT NOT NULL REFERENCES quote_lines(id),
  cycle_min_actual REAL,
  material_minor_actual INTEGER,
  outsource_minor_actual INTEGER,
  scrap_qty REAL,
  recorded_at TEXT NOT NULL,
  source_ref TEXT NOT NULL
);
CREATE INDEX quote_actuals_line_recorded ON quote_actuals(quote_line_id, recorded_at DESC);
