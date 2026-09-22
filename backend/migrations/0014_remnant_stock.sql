-- 1D bar nest proposed/confirmed remnants (M3 stockcut).

CREATE TABLE remnant_stock (
  id TEXT PRIMARY KEY,
  material_id TEXT NOT NULL REFERENCES materials(id),
  length_mm REAL NOT NULL,
  qty INTEGER NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('proposed', 'confirmed')),
  source_ref TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX remnant_stock_material ON remnant_stock(material_id, state);
