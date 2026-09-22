-- Components, part revisions, routings, outsource (§4.3 — S3 scope only).
CREATE TABLE components (
  id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(id),
  customer_part_no TEXT, our_part_no TEXT, name TEXT NOT NULL,
  UNIQUE (customer_id, customer_part_no)
);
CREATE TABLE part_revisions (
  id TEXT PRIMARY KEY, component_id TEXT NOT NULL REFERENCES components(id),
  revision TEXT NOT NULL, drawing_no TEXT,
  drawing_artifact_id TEXT, drawing_sha256 TEXT,
  material_id TEXT REFERENCES materials(id),
  blank_spec TEXT, finished_mass_kg REAL, units TEXT NOT NULL DEFAULT 'mm',
  analysis_state TEXT NOT NULL DEFAULT 'none',
  superseded_by TEXT REFERENCES part_revisions(id),
  UNIQUE (component_id, revision)
);
CREATE TABLE outsource_vendors (
  id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, processes TEXT NOT NULL, lead_days INTEGER
);
CREATE TABLE outsource_quotes (
  id TEXT PRIMARY KEY, vendor_id TEXT NOT NULL REFERENCES outsource_vendors(id),
  process TEXT NOT NULL, spec TEXT NOT NULL,
  unit_basis TEXT NOT NULL CHECK (unit_basis IN ('per_kg','per_piece','per_batch')),
  price_minor INTEGER NOT NULL, min_lot_minor INTEGER, currency TEXT NOT NULL DEFAULT 'INR',
  lead_days INTEGER, effective_from TEXT NOT NULL, effective_to TEXT,
  source_kind TEXT NOT NULL, source_ref TEXT NOT NULL DEFAULT ''
);
CREATE TABLE routings (
  id TEXT PRIMARY KEY, part_revision_id TEXT NOT NULL REFERENCES part_revisions(id),
  version INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'draft',
  source_kind TEXT NOT NULL,
  accepted_by TEXT, accepted_at TEXT, UNIQUE (part_revision_id, version)
);
CREATE TABLE routing_operations (
  id TEXT PRIMARY KEY, routing_id TEXT NOT NULL REFERENCES routings(id),
  seq INTEGER NOT NULL, operation TEXT NOT NULL,
  machine_id TEXT REFERENCES machines(id),
  outsource_vendor_id TEXT REFERENCES outsource_vendors(id),
  outsource_case TEXT,
  setup_min REAL, cycle_min_est REAL, cycle_min_actual REAL,
  est_method TEXT, est_confidence REAL, est_calibration_n INTEGER,
  tooling TEXT, fixture TEXT, program_ref TEXT, inspection TEXT,
  CHECK (machine_id IS NOT NULL OR outsource_vendor_id IS NOT NULL),
  UNIQUE (routing_id, seq)
);
