"""As-of lookups for MHR, raw material, and outsource. A missing row is a BLOCKER."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings


def setup_module(_module=None):
    tmp = Path(tempfile.mkdtemp(prefix="jarvis-md-temporal-"))
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


def test_rm_and_outsource_as_of_windows_and_missing_blocker():
    from app import db
    from app.masterdata.lookup import (
        machine_capability_as_of,
        material_id_for_grade,
        outsource_quote_as_of,
        supplier_rm_quote_as_of,
    )
    from app.masterdata.mhr_lookup import min_mhr_minor_as_of
    from app.quote import build_quote, verify_quote

    with db.connect() as conn:
        assert min_mhr_minor_as_of(conn, machine_type="Demo CNC vertical mill", as_of="2026-09-26") == 85_000
        assert min_mhr_minor_as_of(conn, machine_type="No Such Mill", as_of="2026-09-26") is None
        en8 = material_id_for_grade(conn, "EN8")
        assert en8
        early = supplier_rm_quote_as_of(conn, en8, "2019-01-01")
        current = supplier_rm_quote_as_of(conn, en8, "2026-09-26")
        assert early is None
        assert current is not None
        assert current["price_minor"] == 420_000
        supplier = current["supplier_id"]
        conn.execute(
            """
            INSERT INTO supplier_rm_quotes (
              id, supplier_id, material_id, size_spec, unit_basis, price_minor, currency,
              effective_from, effective_to, basis_date, source_kind, source_ref
            ) VALUES (
              'rmq_later', ?, ?, 'round bar', 'per_kg', 500000, 'INR',
              '2026-10-01', NULL, '2026-10-01', 'owner_input', 'test'
            )
            """,
            (supplier, en8),
        )
        conn.execute(
            "UPDATE supplier_rm_quotes SET effective_to = '2026-10-01' WHERE id = ?",
            (current["id"],),
        )
        october = supplier_rm_quote_as_of(conn, en8, "2026-10-15")
        assert october is not None
        assert october["price_minor"] == 500_000
        assert supplier_rm_quote_as_of(conn, "missing-material", "2026-10-15") is None
        assert outsource_quote_as_of(conn, "heat_treat", "2026-09-26") is None
        vendor = conn.execute("SELECT id FROM outsource_vendors LIMIT 1").fetchone()["id"]
        conn.execute(
            """
            INSERT INTO outsource_quotes (
              id, vendor_id, process, spec, unit_basis, price_minor, currency,
              effective_from, source_kind, source_ref
            ) VALUES ('osq1', ?, 'heat_treat', 'harden', 'per_piece', 120000, 'INR', '2026-01-01', 'owner_input', 'test')
            """,
            (vendor,),
        )
        found = outsource_quote_as_of(conn, "heat_treat", "2026-09-26")
        assert found is not None and found["price_minor"] == 120_000
        machine = conn.execute("SELECT id FROM machines LIMIT 1").fetchone()["id"]
        assert machine_capability_as_of(conn, machine, "milling", "2026-09-26") is None
        conn.execute(
            "INSERT INTO machine_capabilities (machine_id, process, tolerance_floor_mm) VALUES (?, 'milling', 0.02)",
            (machine,),
        )
        cap = machine_capability_as_of(conn, machine, "milling", "2026-09-26")
        assert cap is not None and cap["tolerance_floor_mm"] == 0.02

    build_quote(
        session_id="temporal-missing-rm",
        part_name="Pin",
        material="Unobtanium",
        customer="Deepak",
        scope="with_material",
        rm_price="100",
    )
    from app import db as app_db

    app_db.add_memory("temporal-missing-rm", "last_quote_rm_basis_date", "2026-09-01")
    result = verify_quote(session_id="temporal-missing-rm", stage="draft")
    check = {item["id"]: item for item in result["checks"]}["rm_quote_as_of"]
    assert check["pass"] is False
    assert check["severity"] == "BLOCKER"


def test_mhr_machine_or_type_and_ambiguous_is_none():
    from app import db
    from app.masterdata.mhr_lookup import machine_hour_rate_as_of, min_mhr_minor_as_of

    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO machines (
              id, name, machine_type, control_make, control_model, status
            ) VALUES
              ('mach_twin_a', 'Twin A', 'Twin Mill', 'demo', 'demo', 'running'),
              ('mach_twin_b', 'Twin B', 'Twin Mill', 'demo', 'demo', 'running'),
              ('mach_solo', 'Solo Mill', 'Solo Mill', 'demo', 'demo', 'running')
            """
        )
        conn.executemany(
            """
            INSERT INTO machine_hour_rates (
              id, machine_id, machine_type, min_mhr_minor, currency,
              effective_from, effective_to, source_kind, source_ref
            ) VALUES (?, ?, ?, ?, 'INR', ?, NULL, 'owner_input', 'test')
            """,
            [
                ("mhr_twin_a", "mach_twin_a", "Twin Mill", 111_100, "2020-01-01"),
                ("mhr_twin_b", "mach_twin_b", "Twin Mill", 222_200, "2024-01-01"),
                ("mhr_type_only", None, "Type Floor Mill", 50_000, "2020-01-01"),
                ("mhr_solo", "mach_solo", "Solo Mill", 77_000, "2020-01-01"),
                ("mhr_mixed_type", None, "Mixed Mill", 40_000, "2020-01-01"),
                ("mhr_mixed_machine", "mach_solo", "Mixed Mill", 90_000, "2025-01-01"),
            ],
        )
        assert min_mhr_minor_as_of(conn, machine_type="Twin Mill", as_of="2026-09-26") is None
        assert (
            machine_hour_rate_as_of(
                conn,
                machine_type="Twin Mill",
                as_of="2026-09-26",
                machine_id="mach_twin_a",
            )["min_mhr_minor"]
            == 111_100
        )
        assert (
            machine_hour_rate_as_of(
                conn,
                machine_type="Twin Mill",
                as_of="2026-09-26",
                machine_id="mach_twin_b",
            )["min_mhr_minor"]
            == 222_200
        )
        assert (
            min_mhr_minor_as_of(conn, machine_type="Type Floor Mill", as_of="2026-09-26")
            == 50_000
        )
        assert min_mhr_minor_as_of(conn, machine_type="Solo Mill", as_of="2026-09-26") == 77_000
        assert (
            min_mhr_minor_as_of(
                conn,
                machine_type="Solo Mill",
                as_of="2026-09-26",
                machine_id="mach_solo",
            )
            == 77_000
        )
        # Type floor wins over one later machine-specific row. Several machines do not.
        assert min_mhr_minor_as_of(conn, machine_type="Mixed Mill", as_of="2026-09-26") == 40_000
        assert (
            min_mhr_minor_as_of(
                conn,
                machine_type="Mixed Mill",
                as_of="2026-09-26",
                machine_id="mach_solo",
            )
            == 90_000
        )
        conn.execute(
            "UPDATE machine_hour_rates SET effective_to = '2026-01-01' WHERE id = 'mhr_twin_a'"
        )
        assert (
            machine_hour_rate_as_of(
                conn,
                machine_type="Twin Mill",
                as_of="2026-09-26",
                machine_id="mach_twin_a",
            )
            is None
        )


def test_quote_verify_passes_revision_machine_id_into_mhr_floor():
    from app import db
    from app.quote import build_quote, verify_quote

    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO machines (
              id, name, machine_type, control_make, control_model, status
            ) VALUES
              ('mach_quote_a', 'Quote Twin A', 'Quote Twin Mill', 'demo', 'demo', 'running'),
              ('mach_quote_b', 'Quote Twin B', 'Quote Twin Mill', 'demo', 'demo', 'running')
            """
        )
        conn.executemany(
            """
            INSERT INTO machine_hour_rates (
              id, machine_id, machine_type, min_mhr_minor, currency,
              effective_from, source_kind, source_ref
            ) VALUES (?, ?, 'Quote Twin Mill', ?, 'INR', '2020-01-01', 'owner_input', 'test')
            """,
            [
                ("mhr_quote_a", "mach_quote_a", 111_100),
                ("mhr_quote_b", "mach_quote_b", 222_200),
            ],
        )

    build_quote(
        session_id="temporal-mhr-machine",
        part_name="Pin",
        material="EN8",
        customer="Deepak",
        scope="labour",
        machine="Quote Twin Mill",
        machining_rate="1500",
    )
    revision_id = db.list_memories("temporal-mhr-machine", limit=20)
    rev = next(m["value"] for m in revision_id if m.get("key") == "last_quote_revision_id")
    with db.connect() as conn:
        conn.execute(
            "UPDATE quote_lines SET machine_id = 'mach_quote_a' WHERE quote_revision_id = ?",
            (rev,),
        )
    picked = {item["id"]: item for item in verify_quote(session_id="temporal-mhr-machine")["checks"]}
    assert "1111.0" in picked["mhr_demo_floor"]["evidence"]
    assert "no effective MHR floor" not in picked["mhr_demo_floor"]["evidence"]

    with db.connect() as conn:
        conn.execute(
            "UPDATE quote_lines SET machine_id = NULL WHERE quote_revision_id = ?",
            (rev,),
        )
    ambiguous = {item["id"]: item for item in verify_quote(session_id="temporal-mhr-machine")["checks"]}
    assert ambiguous["mhr_demo_floor"]["pass"] is False
    assert ambiguous["mhr_demo_floor"]["severity"] == "BLOCKER"
    assert "no effective MHR floor" in ambiguous["mhr_demo_floor"]["evidence"]
