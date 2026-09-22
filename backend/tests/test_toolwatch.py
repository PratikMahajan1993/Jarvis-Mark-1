from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="jarvis-toolwatch-"))
settings.data_dir = _TMP / "data"
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.exports_dir = _TMP / "exports"
settings.exports_dir.mkdir(parents=True, exist_ok=True)
settings.canvas_dir = _TMP / "data" / "canvas"
settings.canvas_dir.mkdir(parents=True, exist_ok=True)

from app import db  # noqa: E402
from app import toolwatch  # noqa: E402

MACHINE_ID = "mach_m5_turn"
MATERIAL_ID = "mat_en1a"
TOOL_ID = "tool_dnmg150408"
INSTANCE_A = "ti_m5_a"
_HIST_SEQ = 0


def setup_module(_module=None):
    db.init_db()


def _seed_master() -> None:
    with db.connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO machines (
              id, name, machine_type, control_make, control_model, status
            ) VALUES (?, 'Ace Designers turning cell', 'Lathe', 'demo', 'demo', 'running')
            """,
            (MACHINE_ID,),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO materials (
              id, grade, family, form, notes
            ) VALUES (?, 'En1A', 'free-cutting steel', 'bar', '')
            """,
            (MATERIAL_ID,),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO tools (id, geometry, description)
            VALUES (?, 'DNMG 15 04 08', 'turning insert')
            """,
            (TOOL_ID,),
        )


def _seed_active_instance(*, pieces_since_fit: int = 0) -> str:
    _seed_master()
    with db.connect() as conn:
        conn.execute("DELETE FROM toolwatch_predictions")
        conn.execute("DELETE FROM tool_life_events")
        conn.execute("DELETE FROM tool_instances")
        conn.execute(
            """
            INSERT INTO tool_instances (
              id, tool_id, insert_grade, material_id, operation, machine_id,
              position, fitted_at, retired_at, pieces_since_fit
            ) VALUES (?, ?, 'GC4215', ?, 'turning', ?, 'turret_3', ?, NULL, ?)
            """,
            (
                INSTANCE_A,
                TOOL_ID,
                MATERIAL_ID,
                MACHINE_ID,
                db.utc_now(),
                pieces_since_fit,
            ),
        )
    return INSTANCE_A


def _record_prior_life(pieces: int) -> None:
    """Retire a synthetic instance after logging one change (builds tuple history)."""
    global _HIST_SEQ
    _HIST_SEQ += 1
    with db.connect() as conn:
        inst_id = f"ti_hist_{_HIST_SEQ}"
        conn.execute(
            """
            INSERT INTO tool_instances (
              id, tool_id, insert_grade, material_id, operation, machine_id,
              position, fitted_at, retired_at, pieces_since_fit
            ) VALUES (?, ?, 'GC4215', ?, 'turning', ?, 'turret_3', ?, ?, 0)
            """,
            (
                inst_id,
                TOOL_ID,
                MATERIAL_ID,
                MACHINE_ID,
                db.utc_now(),
                db.utc_now(),
            ),
        )
        conn.execute(
            """
            INSERT INTO tool_life_events (
              id, tool_instance_id, changed_at, reason, pieces_made, measured_wear_mm
            ) VALUES (?, ?, ?, 'wear', ?, NULL)
            """,
            (f"tle_{_HIST_SEQ}", inst_id, db.utc_now(), pieces),
        )


def test_parse_two_forty_and_open_job_machine():
    _seed_master()
    utterance = "changed the insert on the turning cell, two forty pieces, edge chipped"
    parsed = toolwatch.parse_tool_change_utterance(
        utterance,
        open_job_machine="Ace Designers turning cell",
    )
    assert parsed.get("ok") is True
    assert parsed["pieces_made"] == 240
    assert parsed["reason"].casefold() == "edge chipped"
    assert parsed["machine_id"] == MACHINE_ID


def test_capture_ask_when_pieces_missing():
    _seed_active_instance()
    out = toolwatch.capture_tool_change_from_utterance(
        "changed the insert on turning cell, edge chipped",
        open_job_machine="Ace Designers turning cell",
    )
    assert out.get("ask") is True
    with db.connect() as conn:
        n = conn.execute("SELECT COUNT(*) AS n FROM tool_life_events").fetchone()["n"]
    assert n == 0


def test_capture_writes_event():
    inst = _seed_active_instance()
    out = toolwatch.capture_tool_change_from_utterance(
        "changed the insert on the turning cell, two forty pieces, edge chipped",
        open_job_machine="Ace Designers turning cell",
        tool_instance_id=inst,
    )
    assert out.get("ok") is True
    assert out.get("event_id")
    assert out.get("new_tool_instance_id")
    with db.connect() as conn:
        row = conn.execute(
            "SELECT pieces_made, reason FROM tool_life_events WHERE id = ?",
            (out["event_id"],),
        ).fetchone()
    assert row["pieces_made"] == 240
    assert row["reason"] == "edge chipped"


def test_status_insufficient_history_exact_text():
    _seed_active_instance(pieces_since_fit=100)
    for pieces in (200, 220):
        _record_prior_life(pieces)
    st = toolwatch.jarvis_toolwatch_status(tool_instance_id=INSTANCE_A)
    assert st.get("ok") is True
    assert st["status"] == toolwatch.INSUFFICIENT_HISTORY_TEXT
    assert "remaining" not in st


def test_status_median_alerts_80_and_95():
    _seed_active_instance(pieces_since_fit=85)
    for pieces in (100, 100, 100):
        _record_prior_life(pieces)
    st80 = toolwatch.jarvis_toolwatch_status(tool_instance_id=INSTANCE_A)
    assert st80.get("median_life_pieces") == 100
    assert st80.get("remaining") == 15
    assert st80.get("alert") == "80"

    with db.connect() as conn:
        conn.execute(
            "UPDATE tool_instances SET pieces_since_fit = ? WHERE id = ?",
            (96, INSTANCE_A),
        )
    st95 = toolwatch.jarvis_toolwatch_status(tool_instance_id=INSTANCE_A)
    assert st95.get("alert") == "95"
    assert st95.get("remaining") == 4


def test_record_change_retires_and_spawns_instance():
    inst = _seed_active_instance()
    out = toolwatch.jarvis_toolwatch_record_change(inst, "chatter", 180)
    assert out["ok"] is True
    with db.connect() as conn:
        old = conn.execute(
            "SELECT retired_at FROM tool_instances WHERE id = ?", (inst,)
        ).fetchone()
        new = conn.execute(
            "SELECT retired_at, pieces_since_fit FROM tool_instances WHERE id = ?",
            (out["new_tool_instance_id"],),
        ).fetchone()
    assert old["retired_at"]
    assert new["retired_at"] is None
    assert new["pieces_since_fit"] == 0
