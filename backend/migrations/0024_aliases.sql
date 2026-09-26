-- Description: machine and vendor aliases, plus supersede columns on authoritative master rows
-- Dependencies: 0004_parties, 0005_machines, 0006_routings

ALTER TABLE customers ADD COLUMN effective_from TEXT;
ALTER TABLE customers ADD COLUMN effective_to TEXT;
ALTER TABLE customers ADD COLUMN superseded_by TEXT;

ALTER TABLE machines ADD COLUMN effective_from TEXT;
ALTER TABLE machines ADD COLUMN effective_to TEXT;
ALTER TABLE machines ADD COLUMN superseded_by TEXT;

ALTER TABLE materials ADD COLUMN effective_from TEXT;
ALTER TABLE materials ADD COLUMN effective_to TEXT;
ALTER TABLE materials ADD COLUMN superseded_by TEXT;

ALTER TABLE suppliers ADD COLUMN effective_from TEXT;
ALTER TABLE suppliers ADD COLUMN effective_to TEXT;
ALTER TABLE suppliers ADD COLUMN superseded_by TEXT;

ALTER TABLE outsource_vendors ADD COLUMN effective_from TEXT;
ALTER TABLE outsource_vendors ADD COLUMN effective_to TEXT;
ALTER TABLE outsource_vendors ADD COLUMN superseded_by TEXT;

CREATE TABLE IF NOT EXISTS machine_aliases (
  machine_id TEXT NOT NULL REFERENCES machines(id),
  alias TEXT NOT NULL,
  source TEXT NOT NULL,
  PRIMARY KEY (alias)
);

CREATE TABLE IF NOT EXISTS vendor_aliases (
  vendor_id TEXT NOT NULL REFERENCES suppliers(id),
  alias TEXT NOT NULL,
  source TEXT NOT NULL,
  PRIMARY KEY (alias)
);
