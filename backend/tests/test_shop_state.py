from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="jarvis-shop-state-"))
settings.data_dir = _TMP / "data"
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.exports_dir = _TMP / "exports"
settings.exports_dir.mkdir(parents=True, exist_ok=True)
settings.canvas_dir = _TMP / "data" / "canvas"
settings.canvas_dir.mkdir(parents=True, exist_ok=True)

from app import db  # noqa: E402
from app.shop import state  # noqa: E402

MACHINE_ID = "mach_k6_turn"
LOG_DATE = "2026-09-21T06:00:00+00:00"
SOURCE_REF = "sheet:12"


def setup_module(_module=None):
    db.init_db()


def _seed_machine_and_log(*, oee_pct: float | None = 72.0) -> None:
    with db.connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO machines (
              id, name, machine_type, control_make, control_model, status
            ) VALUES (?, 'Turn 1', 'Lathe', 'demo', 'demo', 'running')
            """,
            (MACHINE_ID,),
        )
        conn.execute("DELETE FROM production_logs WHERE machine_id = ?", (MACHINE_ID,))
        conn.execute("DELETE FROM shop_state WHERE key = ?", (f"machine:{MACHINE_ID}",))
        conn.execute(
            """
            INSERT INTO production_logs (
              id, shift, log_date, machine_id, oee_pct, source_ref, operator
            ) VALUES (?, 'night', ?, ?, ?, ?, 'Alex')
            """,
            ("log-k6-1", LOG_DATE, MACHINE_ID, oee_pct, SOURCE_REF),
        )


def test_migration_creates_shop_tables():
    with db.connect() as conn:
        names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "production_logs" in names
    assert "downtime_reasons" in names
    assert "shop_state" in names


def test_numeric_oee_cites_log_row():
    _seed_machine_and_log(oee_pct=72.0)
    assert state.rebuild_shop_state() == 1
    out = state.answer_shop(MACHINE_ID, "oee")
    assert out["kind"] == "numeric"
    assert out["value"] == 72.0
    assert out["source_ref"] == SOURCE_REF
    assert out["as_of"] == LOG_DATE
    assert out["cites"] == "production_log"


def test_why_answer_uses_digest_same_stamp():
    _seed_machine_and_log(oee_pct=72.0)
    state.rebuild_shop_state()
    out = state.answer_shop(MACHINE_ID, "why")
    assert out["kind"] == "narrative"
    assert out["cites"] == "digest"
    assert out["as_of"] == LOG_DATE
    assert out["source_ref"] == SOURCE_REF
    assert "night" in out["speak"].lower()
    assert "Alex" in out["speak"]
    with db.connect() as conn:
        payload = json.loads(
            conn.execute(
                "SELECT payload FROM shop_state WHERE key = ?",
                (f"machine:{MACHINE_ID}",),
            ).fetchone()["payload"]
        )
    assert payload["narrative"] == out["speak"]


def test_no_log_rows_asks_without_invented_percent():
    with db.connect() as conn:
        conn.execute("DELETE FROM production_logs WHERE machine_id = ?", (MACHINE_ID,))
        conn.execute("DELETE FROM shop_state WHERE key = ?", (f"machine:{MACHINE_ID}",))
    assert state.rebuild_shop_state() == 0
    out = state.answer_shop(MACHINE_ID, "oee")
    assert out["kind"] == "ask"
    assert "value" not in out
    blob = json.dumps(out)
    assert not re.search(r"\d+\s*%", blob)
    assert "invent" in out["speak"].lower() or "no production log" in out["speak"].lower()


def test_numeric_without_oee_column_value_asks():
    _seed_machine_and_log(oee_pct=None)
    state.rebuild_shop_state()
    out = state.answer_shop(MACHINE_ID, "oee")
    assert out["kind"] == "ask"
    assert "invent" in out["speak"].lower()
