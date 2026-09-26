"""Seed script inserts the shop baseline and stays idempotent."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import Settings, settings


def setup_module(_module=None):
    tmp = Path(tempfile.mkdtemp(prefix="jarvis-md-seed-"))
    settings.data_dir = tmp / "data"
    settings.exports_dir = tmp / "exports"
    settings.canvas_dir = settings.data_dir / "canvas"
    for path in (settings.data_dir, settings.exports_dir, settings.canvas_dir):
        path.mkdir(parents=True, exist_ok=True)
    from app import db

    db.init_db()


def test_masterdata_flag_defaults_on():
    assert Settings.model_fields["masterdata_enabled"].default is True
    assert settings.masterdata_enabled is True


def test_seed_inserts_shop_rows_and_is_idempotent():
    from app import db
    from app.masterdata.lookup import customer_name_is_known
    from app.masterdata.mhr_lookup import machine_hour_rate_as_of
    from app.masterdata.seed_master_data import seed_master_data

    with db.connect() as conn:
        first = seed_master_data(conn)
        second = seed_master_data(conn)
        rate = machine_hour_rate_as_of(conn, machine_type="Demo CNC vertical mill", as_of="2026-09-26")
        known = customer_name_is_known(conn, "Deepak")
        materials = conn.execute("SELECT grade FROM materials ORDER BY grade").fetchall()
        machines = conn.execute("SELECT COUNT(*) AS n FROM machines").fetchone()["n"]

    assert first["customers"] == 4
    assert first["machines"] == 5
    assert first["materials"] == 5
    assert first["suppliers"] == 2
    assert first["mhr"] == 3
    assert first["rm_quotes"] == 1
    assert first["outsource_vendors"] == 1
    assert all(value == 0 for value in second.values())
    assert rate is not None
    assert rate["min_mhr_minor"] == 85_000
    assert rate["attested_by"] == ""
    assert rate["shipped_seed_value_minor"] == 85_000
    assert known is True
    assert machines == 5
    assert {row["grade"] for row in materials} >= {"EN8", "EN24", "18CrNiMo7-6"}
