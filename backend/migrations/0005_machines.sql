-- Machines, temporal MHR floors, capabilities (§4.3 — S2 scope only).
CREATE TABLE machines (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, machine_type TEXT NOT NULL,
  control_make TEXT NOT NULL, control_model TEXT NOT NULL,
  axes INTEGER, travel_x REAL, travel_y REAL, travel_z REAL,
  max_rpm INTEGER, spindle_kw REAL, bar_capacity_mm REAL, chuck_mm REAL,
  rapid_x REAL, rapid_y REAL, rapid_z REAL, accel_g REAL,
  accuracy_class TEXT, status TEXT NOT NULL DEFAULT 'running'
);
CREATE TABLE machine_hour_rates (
  id TEXT PRIMARY KEY,
  machine_id TEXT REFERENCES machines(id), machine_type TEXT,
  min_mhr_minor INTEGER NOT NULL, target_mhr_minor INTEGER,
  currency TEXT NOT NULL DEFAULT 'INR',
  effective_from TEXT NOT NULL, effective_to TEXT,
  source_kind TEXT NOT NULL CHECK (source_kind IN ('owner_input','costing_sheet','demo')),
  source_ref TEXT NOT NULL DEFAULT '',
  attested_by TEXT NOT NULL DEFAULT '', attested_at TEXT,
  shipped_seed_value_minor INTEGER,
  CHECK (machine_id IS NOT NULL OR machine_type IS NOT NULL)
);
CREATE TABLE machine_capabilities (
  machine_id TEXT NOT NULL REFERENCES machines(id), process TEXT NOT NULL,
  tolerance_floor_mm REAL, finish_floor_ra REAL,
  max_part_x REAL, max_part_y REAL, max_part_z REAL, max_part_kg REAL,
  PRIMARY KEY (machine_id, process)
);
