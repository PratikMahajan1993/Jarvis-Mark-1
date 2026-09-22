-- Parties, materials, suppliers, RM quotes (§4.3 — S1 scope only).
CREATE TABLE customers (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  gstin TEXT,
  currency TEXT NOT NULL DEFAULT 'INR',
  status TEXT NOT NULL DEFAULT 'active'
);
CREATE TABLE customer_aliases (
  customer_id TEXT NOT NULL REFERENCES customers(id),
  alias TEXT NOT NULL,
  source TEXT NOT NULL,
  PRIMARY KEY (alias)
);
CREATE TABLE customer_terms (
  customer_id TEXT PRIMARY KEY REFERENCES customers(id),
  default_scope TEXT NOT NULL CHECK (default_scope IN ('labour','with_material','ask')),
  payment_terms_days INTEGER,
  delivery_basis TEXT,
  nda INTEGER NOT NULL DEFAULT 0,
  allow_cloud_vision INTEGER NOT NULL DEFAULT 0,
  vision_consent_by TEXT,
  vision_consent_at TEXT,
  quote_validity_days INTEGER NOT NULL DEFAULT 30
);
CREATE TABLE materials (
  id TEXT PRIMARY KEY,
  grade TEXT NOT NULL UNIQUE,
  family TEXT NOT NULL,
  standard TEXT,
  density_kg_m3 REAL,
  machinability_index REAL,
  hardness_spec TEXT,
  form TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE material_equivalents (
  material_id TEXT NOT NULL REFERENCES materials(id),
  equivalent_grade TEXT NOT NULL,
  standard TEXT,
  confirmed_by TEXT NOT NULL,
  PRIMARY KEY (material_id, equivalent_grade)
);
CREATE TABLE suppliers (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  contact TEXT,
  lead_days INTEGER
);
CREATE TABLE supplier_rm_quotes (
  id TEXT PRIMARY KEY,
  supplier_id TEXT NOT NULL REFERENCES suppliers(id),
  material_id TEXT NOT NULL REFERENCES materials(id),
  size_spec TEXT NOT NULL,
  unit_basis TEXT NOT NULL CHECK (unit_basis IN ('per_kg','per_bar','per_piece','per_metre')),
  price_minor INTEGER NOT NULL,
  currency TEXT NOT NULL DEFAULT 'INR',
  min_qty REAL,
  qty_break TEXT,
  effective_from TEXT NOT NULL,
  effective_to TEXT,
  basis_date TEXT NOT NULL,
  source_kind TEXT NOT NULL CHECK (source_kind IN ('supplier_quote','invoice','owner_input','estimate','demo')),
  source_ref TEXT NOT NULL DEFAULT '',
  is_estimate INTEGER NOT NULL DEFAULT 0,
  estimate_basis TEXT NOT NULL DEFAULT '',
  attested_by TEXT NOT NULL DEFAULT '',
  attested_at TEXT,
  shipped_seed_value_minor INTEGER
);
CREATE INDEX rm_quotes_lookup ON supplier_rm_quotes(material_id, effective_from, effective_to);
