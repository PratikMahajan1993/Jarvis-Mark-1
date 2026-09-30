-- Description: Google account registry + listened production sheets + local tab snapshots
-- Dependencies: 0030_products
--
-- Tokens stay as files under data/ (gitignored). This table only records which
-- label maps to which filename. Listening never writes the Google sheet.

CREATE TABLE google_accounts (
  id TEXT PRIMARY KEY,
  label TEXT NOT NULL UNIQUE CHECK (label IN ('shop', 'staff')),
  token_filename TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  email_hint TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);

INSERT OR IGNORE INTO google_accounts (id, label, token_filename, status, email_hint, created_at)
VALUES
  ('gacc_shop', 'shop', 'google_token.json', 'active', '', '1970-01-01T00:00:00+00:00'),
  ('gacc_staff', 'staff', 'google_token_staff.json', 'active', '', '1970-01-01T00:00:00+00:00');

CREATE TABLE listened_sheets (
  id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES google_accounts(id),
  spreadsheet_id TEXT NOT NULL,
  spreadsheet_url TEXT NOT NULL DEFAULT '',
  tab_name TEXT NOT NULL,
  display_name TEXT NOT NULL,
  column_map_json TEXT NOT NULL DEFAULT '{}',
  last_ok_at TEXT,
  last_error TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  effective_from TEXT NOT NULL,
  effective_to TEXT,
  superseded_by TEXT
);

CREATE UNIQUE INDEX listened_sheets_active_link_tab
  ON listened_sheets(spreadsheet_id, tab_name)
  WHERE effective_to IS NULL AND COALESCE(status, '') != 'superseded';

CREATE INDEX listened_sheets_account ON listened_sheets(account_id);

CREATE TABLE sheet_snapshots (
  listened_sheet_id TEXT PRIMARY KEY REFERENCES listened_sheets(id),
  read_at TEXT NOT NULL,
  headers_json TEXT NOT NULL,
  rows_json TEXT NOT NULL
);
