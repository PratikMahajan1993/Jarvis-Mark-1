"""HTTP routes for quote-variance erosion rank and toolwatch capture."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db  # noqa: E402
from app import quote_variance  # noqa: E402

REV_ID = "qrev_w5_test"
LINE_MAT = "qln_mat_w5"
SOURCE = "erp:job-w5"

MACHINE_ID = "mach_w5_turn"
MATERIAL_ID = "mat_w5_en1a"
TOOL_ID = "tool_w5_dnmg"
INSTANCE_A = "ti_w5_a"

CAPTURE_UTTERANCE = (
    "changed the insert on the turning cell, two forty pieces, edge chipped"
)
OPEN_JOB_MACHINE = "Ace Designers turning cell"


def setup_module(_module=None):
    db.init_db()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO customers (id, name, gstin, currency, status)
            VALUES ('cust_w5', 'W5 Customer', NULL, 'INR', 'active')
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO quotes (id, customer_id, status)
            VALUES ('quote_w5', 'cust_w5', 'open')
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO quote_revisions (
              id, quote_id, revision, scope, scope_source, qty, currency, total_minor, frozen
            ) VALUES (?, 'quote_w5', 1, 'with_material', 'test', 1, 'INR', 0, 0)
            """,
            (REV_ID,),
        )
        conn.execute("DELETE FROM quote_actuals")
        conn.execute("DELETE FROM quote_lines WHERE quote_revision_id = ?", (REV_ID,))
        conn.execute(
            """
            INSERT INTO quote_lines (
              id, quote_revision_id, seq, kind, description,
              qty, qty_unit, rate_minor, amount_minor,
              machine_id, time_min, rate_source_kind, rate_source_id,
              is_estimate, estimate_basis
            ) VALUES (?, ?, 1, 'material', 'RM block', 1, 'pc', 10000, 10000, NULL, NULL, 'owner_input', 'test', 0, '')
            """,
            (LINE_MAT, REV_ID),
        )


def _resolve_toolwatch_master_ids(conn) -> tuple[str, str, str]:
    machine_id = conn.execute(
        "SELECT id FROM machines WHERE name = ?",
        ("Ace Designers turning cell",),
    ).fetchone()["id"]
    material_id = conn.execute(
        "SELECT id FROM materials WHERE grade = ?",
        ("En1A",),
    ).fetchone()["id"]
    tool_id = conn.execute(
        "SELECT id FROM tools WHERE geometry = ?",
        ("DNMG 15 04 08",),
    ).fetchone()["id"]
    return machine_id, material_id, tool_id


def _seed_toolwatch_master() -> tuple[str, str, str]:
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
        return _resolve_toolwatch_master_ids(conn)


def _seed_active_tool_instance() -> str:
    machine_id, material_id, tool_id = _seed_toolwatch_master()
    with db.connect() as conn:
        conn.execute("DELETE FROM toolwatch_predictions")
        conn.execute("DELETE FROM tool_life_events")
        conn.execute("DELETE FROM tool_instances")
        conn.execute(
            """
            INSERT INTO tool_instances (
              id, tool_id, insert_grade, material_id, operation, machine_id,
              position, fitted_at, retired_at, pieces_since_fit
            ) VALUES (?, ?, 'GC4215', ?, 'turning', ?, 'turret_3', ?, NULL, 0)
            """,
            (
                INSTANCE_A,
                tool_id,
                material_id,
                machine_id,
                db.utc_now(),
            ),
        )
    return INSTANCE_A


def _client() -> TestClient:
    from app.main import app

    return TestClient(app)


def test_quote_variance_erosion_route_returns_real_actuals():
    quote_variance.record_actual(
        LINE_MAT,
        material_minor_actual=12000,
        scrap_qty=0.0,
        source_ref=SOURCE,
        recorded_at="2026-03-01T10:00:00+00:00",
    )
    with _client() as client:
        resp = client.get("/api/quote-variance/erosion", params={"limit": 20})
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == {"items"}
    assert isinstance(data["items"], list)
    ids = [row["quote_line_id"] for row in data["items"]]
    assert LINE_MAT in ids
    row = next(r for r in data["items"] if r["quote_line_id"] == LINE_MAT)
    assert row["erosion_minor"] == 2000


def test_toolwatch_capture_blank_utterance_asks_without_write():
    _seed_active_tool_instance()
    with _client() as client:
        resp = client.post(
            "/api/toolwatch/capture",
            json={"utterance": "   ", "open_job_machine": OPEN_JOB_MACHINE},
        )
    assert resp.status_code == 200
    assert resp.json() == {"ask": True}
    with db.connect() as conn:
        n = conn.execute("SELECT COUNT(*) AS n FROM tool_life_events").fetchone()["n"]
    assert n == 0


def test_toolwatch_capture_utterance_records_or_asks():
    inst = _seed_active_tool_instance()
    with _client() as client:
        resp = client.post(
            "/api/toolwatch/capture",
            json={
                "utterance": CAPTURE_UTTERANCE,
                "open_job_machine": OPEN_JOB_MACHINE,
                "tool_instance_id": inst,
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    if data.get("ask"):
        with db.connect() as conn:
            n = conn.execute("SELECT COUNT(*) AS n FROM tool_life_events").fetchone()["n"]
        assert n == 0
    else:
        assert data.get("ok") is True
        assert data.get("event_id")
        with db.connect() as conn:
            row = conn.execute(
                "SELECT id FROM tool_life_events WHERE id = ?",
                (data["event_id"],),
            ).fetchone()
        assert row is not None
