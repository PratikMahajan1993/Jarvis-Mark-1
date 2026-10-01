-- Description: owner-typed order status and inspector reports
-- Dependencies: 0035

CREATE TABLE IF NOT EXISTS order_status (
  job_ref TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  delivery_date TEXT,
  halted_reason TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inspection_reports (
  id TEXT PRIMARY KEY,
  job_ref TEXT NOT NULL,
  measurements_json TEXT NOT NULL,
  disposition TEXT NOT NULL,
  path TEXT NOT NULL,
  created_at TEXT NOT NULL
);
