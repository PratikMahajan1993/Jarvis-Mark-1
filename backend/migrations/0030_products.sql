-- Description: products (item made for a customer) — no BOM or stock ledger
-- Dependencies: 0004_parties, 0024_aliases

CREATE TABLE products (
  id TEXT PRIMARY KEY,
  product_number TEXT NOT NULL,
  name TEXT NOT NULL,
  customer_id TEXT NOT NULL REFERENCES customers(id),
  uom TEXT NOT NULL,
  monitor_stock INTEGER NOT NULL DEFAULT 0,
  material_id TEXT REFERENCES materials(id),
  status TEXT NOT NULL DEFAULT 'active',
  effective_from TEXT NOT NULL,
  effective_to TEXT,
  superseded_by TEXT
);

CREATE UNIQUE INDEX products_active_number
  ON products(product_number)
  WHERE effective_to IS NULL AND COALESCE(status, '') != 'superseded';

CREATE INDEX products_customer ON products(customer_id);
