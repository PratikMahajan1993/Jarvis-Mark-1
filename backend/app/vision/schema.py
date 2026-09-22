"""Vision gate tables — created via db.connect(), not init_db migrations."""

from __future__ import annotations

import sqlite3

_DDL = """
CREATE TABLE IF NOT EXISTS vision_quota_usage (
  id TEXT PRIMARY KEY,
  cycle_start TEXT NOT NULL,
  file_sha256 TEXT NOT NULL,
  customer_id TEXT,
  spent_by TEXT NOT NULL CHECK (spent_by IN ('owner_bench','owner_upload','owner_override')),
  arrival TEXT NOT NULL,
  pages INTEGER NOT NULL DEFAULT 1,
  state TEXT NOT NULL CHECK (state IN ('claimed','dispatched','failed','override')),
  turn_id TEXT,
  override_action_id TEXT,
  created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS vision_quota_unit ON vision_quota_usage(cycle_start, file_sha256);

CREATE TABLE IF NOT EXISTS disclosure_log (
  id TEXT PRIMARY KEY,
  file_sha256 TEXT NOT NULL,
  customer_id TEXT,
  provider TEXT NOT NULL,
  purpose TEXT NOT NULL,
  bytes INTEGER NOT NULL,
  turn_id TEXT,
  cycle_start TEXT,
  authorized_by TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS drawing_analysis_state (
  file_sha256 TEXT PRIMARY KEY,
  analysis_state TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""


def ensure_vision_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_DDL)
