"""Supersede inserts a successor and keeps attestation on the old row."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings


def setup_module(_module=None):
    tmp = Path(tempfile.mkdtemp(prefix="jarvis-md-super-"))
    settings.data_dir = tmp / "data"
    settings.exports_dir = tmp / "exports"
    settings.canvas_dir = settings.data_dir / "canvas"
    for path in (settings.data_dir, settings.exports_dir, settings.canvas_dir):
        path.mkdir(parents=True, exist_ok=True)
    from app import db
    from app.masterdata.seed_master_data import seed_master_data

    db.init_db()
    with db.connect() as conn:
        seed_master_data(conn)


def test_supersede_customer_end_dates_old_row():
    from app import db
    from app.masterdata.lifecycle import supersede_customer

    with db.connect() as conn:
        old = conn.execute("SELECT id, name FROM customers WHERE name = 'Deepak'").fetchone()
        new_id = supersede_customer(conn, old["id"], {"name": "Deepak Engineering", "default_scope": "labour"})
        retired = conn.execute("SELECT * FROM customers WHERE id = ?", (old["id"],)).fetchone()
        successor = conn.execute("SELECT * FROM customers WHERE id = ?", (new_id,)).fetchone()
        audit = conn.execute(
            "SELECT tool, status FROM audit WHERE tool = 'supersede' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert "superseded" in retired["name"]
    assert retired["status"] == "superseded"
    assert retired["effective_to"]
    assert retired["superseded_by"] == new_id
    assert successor["name"] == "Deepak Engineering"
    assert successor["status"] == "active"
    assert audit["status"] == "ok"


def test_supersede_rate_preserves_attestation():
    from app import db
    from app.masterdata.lifecycle import supersede_rate

    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO machine_hour_rates (
              id, machine_type, min_mhr_minor, currency, effective_from, source_kind, source_ref,
              attested_by, attested_at, shipped_seed_value_minor
            ) VALUES (
              'mhr_keep', 'Keep Mill', 70000, 'INR', '2026-01-01', 'owner_input', 'sheet-1',
              'Owner', '2026-01-02T00:00:00+00:00', 50000
            )
            """
        )
        new_id = supersede_rate(
            conn,
            "machine_hour_rates",
            "mhr_keep",
            {"min_mhr_minor": 91000, "attested_by": "Owner", "source_kind": "owner_input"},
            "2026-06-01",
        )
        old = conn.execute("SELECT * FROM machine_hour_rates WHERE id = 'mhr_keep'").fetchone()
        new = conn.execute("SELECT * FROM machine_hour_rates WHERE id = ?", (new_id,)).fetchone()
    assert old["attested_by"] == "Owner"
    assert old["attested_at"] == "2026-01-02T00:00:00+00:00"
    assert old["source_ref"] == "sheet-1"
    assert old["effective_to"] == "2026-06-01"
    assert old["min_mhr_minor"] == 70_000
    assert new["min_mhr_minor"] == 91_000
    assert new["shipped_seed_value_minor"] == 50_000
    assert new["effective_to"] is None
