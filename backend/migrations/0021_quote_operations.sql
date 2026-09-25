-- Session machining strategy. Money is integer minor units. Cycle time is minutes.

CREATE TABLE quote_operations (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  operation TEXT NOT NULL,
  machine_type TEXT NOT NULL DEFAULT '',
  outsource INTEGER NOT NULL DEFAULT 0 CHECK (outsource IN (0, 1)),
  outsource_case TEXT NOT NULL DEFAULT '' CHECK (
    outsource_case IN ('', 'no_machine', 'customer_asked', 'capacity', 'not_in_house')
  ),
  outsource_vendor TEXT NOT NULL DEFAULT '',
  outsource_price_minor INTEGER,
  outsource_received INTEGER NOT NULL DEFAULT 0 CHECK (outsource_received IN (0, 1)),
  special_tooling TEXT NOT NULL DEFAULT '',
  setup_minor INTEGER,
  cycle_min REAL,
  cycle_unit TEXT NOT NULL DEFAULT 'min',
  currency TEXT NOT NULL DEFAULT 'INR',
  notes TEXT NOT NULL DEFAULT ''
);
CREATE INDEX quote_operations_session ON quote_operations(session_id, seq);

ALTER TABLE external_effects ADD COLUMN delivery_hash TEXT;
