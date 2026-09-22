-- Toolwatch v0 shop-log capture (M5 §3.1, §8.4). No machine_telemetry.

CREATE TABLE tools (
  id TEXT PRIMARY KEY,
  geometry TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE tool_instances (
  id TEXT PRIMARY KEY,
  tool_id TEXT NOT NULL REFERENCES tools(id),
  insert_grade TEXT NOT NULL,
  material_id TEXT NOT NULL REFERENCES materials(id),
  operation TEXT NOT NULL,
  machine_id TEXT NOT NULL REFERENCES machines(id),
  position TEXT NOT NULL DEFAULT '',
  fitted_at TEXT NOT NULL,
  retired_at TEXT,
  pieces_since_fit INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_tool_instances_machine_active
  ON tool_instances (machine_id, retired_at);

CREATE TABLE tool_life_events (
  id TEXT PRIMARY KEY,
  tool_instance_id TEXT NOT NULL REFERENCES tool_instances(id),
  changed_at TEXT NOT NULL,
  reason TEXT NOT NULL,
  pieces_made INTEGER NOT NULL,
  measured_wear_mm REAL
);

CREATE INDEX idx_tool_life_events_instance
  ON tool_life_events (tool_instance_id, changed_at);

CREATE TABLE toolwatch_predictions (
  id TEXT PRIMARY KEY,
  tool_instance_id TEXT NOT NULL REFERENCES tool_instances(id),
  predicted_remaining_pieces INTEGER,
  confidence TEXT NOT NULL,
  basis TEXT NOT NULL,
  model_version TEXT NOT NULL DEFAULT 'v0',
  computed_at TEXT NOT NULL
);

CREATE INDEX idx_toolwatch_predictions_instance
  ON toolwatch_predictions (tool_instance_id, computed_at);
