CREATE TABLE turn_events (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  turn_id    TEXT NOT NULL,
  state      TEXT NOT NULL,
  stage      TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
CREATE INDEX turn_events_turn_id_id ON turn_events(turn_id, id);
