-- Parametric cycletime Engine A + calibration store (§3.4 — M2 scope).
CREATE TABLE tool_material_params (
  id TEXT PRIMARY KEY,
  material_id TEXT NOT NULL REFERENCES materials(id),
  operation_class TEXT NOT NULL,
  tool_geometry TEXT NOT NULL,
  fz_mm REAL,
  z INTEGER,
  n_rpm REAL,
  f_mm_rev REAL,
  source_ref TEXT NOT NULL,
  effective_from TEXT NOT NULL,
  UNIQUE (material_id, operation_class, tool_geometry, effective_from)
);
CREATE INDEX idx_tool_material_params_lookup
  ON tool_material_params (material_id, operation_class, tool_geometry, effective_from);

CREATE TABLE cycletime_estimates (
  id TEXT PRIMARY KEY,
  machine_id TEXT NOT NULL,
  material_id TEXT NOT NULL REFERENCES materials(id),
  operation_class TEXT NOT NULL,
  method TEXT NOT NULL,
  minutes REAL NOT NULL,
  confidence TEXT NOT NULL,
  calibration_n INTEGER NOT NULL,
  basis_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_cycletime_estimates_cal
  ON cycletime_estimates (machine_id, material_id, operation_class);

CREATE TABLE cycletime_actuals (
  id TEXT PRIMARY KEY,
  machine_id TEXT NOT NULL,
  material_id TEXT NOT NULL REFERENCES materials(id),
  operation_class TEXT NOT NULL,
  measured_min REAL NOT NULL,
  pieces REAL,
  operator_note TEXT,
  recorded_at TEXT NOT NULL,
  source_ref TEXT NOT NULL
);
CREATE INDEX idx_cycletime_actuals_cal
  ON cycletime_actuals (machine_id, material_id, operation_class);
