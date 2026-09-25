-- Request to receive tracking for one session raw-material quote.
-- supplier_rm_quotes stays the priced master-data book. A request has no price yet.

CREATE TABLE rm_quote_requests (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  customer_id TEXT,
  material TEXT NOT NULL,
  supplier TEXT NOT NULL,
  supplier_email TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'requested' CHECK (status IN ('requested','received')),
  quoted_price_minor INTEGER,
  currency TEXT NOT NULL DEFAULT 'INR',
  quote_date TEXT,
  received_at TEXT,
  notes TEXT NOT NULL DEFAULT '',
  is_estimate INTEGER NOT NULL DEFAULT 0 CHECK (is_estimate IN (0, 1)),
  source_kind TEXT NOT NULL DEFAULT '' CHECK (source_kind IN ('','supplier_quote','estimate','owner_input')),
  source_ref TEXT NOT NULL DEFAULT '',
  pending_id TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX rm_quote_requests_session ON rm_quote_requests(session_id, created_at);
