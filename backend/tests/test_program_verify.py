from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="jarvis-nc-verify-"))
settings.data_dir = _TMP / "data"
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.exports_dir = _TMP / "exports"
settings.exports_dir.mkdir(parents=True, exist_ok=True)

from app import db  # noqa: E402
from app.program_verify import (  # noqa: E402
    NOT_PROVEN_HEADER,
    ProgramVerifyError,
    promote,
    store_draft,
    verify_program,
)

MACHINE_ID = "mach_verify_m6"


def setup_module(_module=None):
    db.init_db()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO machines (
              id, name, machine_type, control_make, control_model,
              travel_x, travel_y, travel_z, status
            ) VALUES (?, 'Verify mill', 'VMC', 'FANUC', '0i-MF',
              500, 400, 300, 'running')
            """,
            (MACHINE_ID,),
        )


def _safe_program() -> str:
    return "\n".join(
        [
            "%",
            "O1001",
            NOT_PROVEN_HEADER,
            "G90 G21",
            "G00 X0 Y0 Z100",
            "G01 X10 F200",
            "M03",
            "M30",
            "%",
        ]
    )


def test_travel_envelope_fails_with_block_number():
    body = "\n".join(
        [
            "G90",
            "N10 G00 X600",
            "M30",
        ]
    )
    with db.connect() as conn:
        result = verify_program(MACHINE_ID, body, conn=conn)
    assert result["ok"] is False
    assert result["failures"]
    fail = result["failures"][0]
    assert fail["block"] == 10
    code_detail = f"{fail['code']} {fail['detail']}".lower()
    assert "travel" in code_detail or "envelope" in code_detail


def test_feed_envelope_fails_with_block_number():
    body = "\n".join(
        [
            "G90",
            "N20 G01 X1 F800",
            "M30",
        ]
    )
    with db.connect() as conn:
        result = verify_program(
            MACHINE_ID,
            body,
            feed_envelope=500,
            conn=conn,
        )
    assert result["ok"] is False
    fail = result["failures"][0]
    assert fail["block"] == 20
    assert "feed" in fail["code"].lower() or "feed" in fail["detail"].lower()


def test_rapid_below_clearance_plane_fails_with_block_number():
    body = "\n".join(
        [
            "G90",
            "N30 G00 Z10",
            "M30",
        ]
    )
    with db.connect() as conn:
        result = verify_program(
            MACHINE_ID,
            body,
            clearance_plane=50.0,
            conn=conn,
        )
    assert result["ok"] is False
    fail = result["failures"][0]
    assert fail["block"] == 30
    assert "rapid" in fail["code"].lower() or "clearance" in fail["code"].lower()


def test_m_code_not_in_whitelist_fails_with_block_number():
    body = "\n".join(
        [
            "G90",
            "N40 G00 X0 Z100",
            "N50 M42",
            "M30",
        ]
    )
    with db.connect() as conn:
        result = verify_program(
            MACHINE_ID,
            body,
            m_whitelist=[3, 5, 30],
            conn=conn,
        )
    assert result["ok"] is False
    m_fail = next(f for f in result["failures"] if "m" in f["code"].lower())
    assert m_fail["block"] == 50


def test_verify_program_does_not_write_exports():
    nc_dir = settings.exports_dir / "nc"
    nc_dir.mkdir(parents=True, exist_ok=True)
    before = list(nc_dir.glob("*"))
    with db.connect() as conn:
        verify_program(MACHINE_ID, _safe_program(), conn=conn)
    after = list(nc_dir.glob("*"))
    assert before == after


def test_store_draft_adds_not_proven_header():
    body = "\n".join(["%", "O2000", "G90", "M30", "%"])
    with db.connect() as conn:
        meta = store_draft(MACHINE_ID, body, conn=conn)
        row = conn.execute(
            "SELECT body, state FROM nc_programs WHERE id = ?",
            (meta["id"],),
        ).fetchone()
    assert NOT_PROVEN_HEADER in row["body"]
    assert row["state"] == "draft"


def test_promote_appends_version_without_mutating_draft():
    body = _safe_program()
    with db.connect() as conn:
        draft = store_draft(MACHINE_ID, body, conn=conn)
        draft_id = draft["id"]
        draft_version = draft["version"]
        draft_body_before = conn.execute(
            "SELECT body FROM nc_programs WHERE id = ?",
            (draft_id,),
        ).fetchone()["body"]

        promoted = promote(
            draft_id,
            feed_envelope=500,
            m_whitelist=[3, 30],
            clearance_plane=0,
            conn=conn,
        )

        draft_after = conn.execute(
            "SELECT body, state, version FROM nc_programs WHERE id = ?",
            (draft_id,),
        ).fetchone()
        promoted_row = conn.execute(
            "SELECT body, state, version FROM nc_programs WHERE id = ?",
            (promoted["id"],),
        ).fetchone()
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM nc_programs WHERE machine_id = ?",
            (MACHINE_ID,),
        ).fetchone()["n"]

    assert draft_after["body"] == draft_body_before
    assert draft_after["state"] == "draft"
    assert draft_after["version"] == draft_version
    assert promoted_row["state"] == "promoted"
    assert promoted_row["version"] == draft_version + 1
    assert promoted_row["body"] == draft_body_before
    assert count >= 2
    assert promoted["draft_unchanged"] is True


def test_promote_refuses_when_verify_fails():
    bad = "\n".join(["N1 G00 X9999", "M30"])
    with db.connect() as conn:
        draft = store_draft(MACHINE_ID, bad, conn=conn)
        try:
            promote(draft["id"], conn=conn)
            raised = False
        except ProgramVerifyError:
            raised = True
    assert raised is True


