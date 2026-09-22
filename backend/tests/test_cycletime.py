from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="jarvis-cycletime-"))
settings.data_dir = _TMP / "data"
settings.data_dir.mkdir(parents=True, exist_ok=True)

from app import db  # noqa: E402
from app.cycletime import (  # noqa: E402
    estimate_parametric,
    jarvis_cycletime_estimate,
    jarvis_cycletime_record_actual,
    record_actual,
)
from app.masterdata import routings  # noqa: E402


def setup_module(_module=None):
    db.init_db()


def _seed_material_and_params(conn, *, suffix: str) -> tuple[str, str]:
    mat_id = f"mat_ct_{suffix}"
    conn.execute(
        """
        INSERT INTO materials (id, grade, family, form)
        VALUES (?, ?, 'aluminum', 'plate')
        """,
        (mat_id, f"6061-{suffix}"),
    )
    conn.execute(
        """
        INSERT INTO tool_material_params (
          id, material_id, operation_class, tool_geometry,
          fz_mm, z, n_rpm, f_mm_rev, source_ref, effective_from
        ) VALUES (?, ?, 'milling', '12mm_4fl', 0.08, 4, 8000, NULL, 'test-fixture', '2020-01-01')
        """,
        (f"tmp_mill_{suffix}", mat_id),
    )
    conn.execute(
        """
        INSERT INTO tool_material_params (
          id, material_id, operation_class, tool_geometry,
          fz_mm, z, n_rpm, f_mm_rev, source_ref, effective_from
        ) VALUES (?, ?, 'turning', 'cnmg_12', NULL, NULL, 1200, 0.25, 'test-fixture', '2020-01-01')
        """,
        (f"tmp_turn_{suffix}", mat_id),
    )
    return mat_id, f"6061-{suffix}"


def _insert_machine(conn, machine_id: str = "mach_ct") -> None:
    conn.execute(
        """
        INSERT INTO machines (
          id, name, machine_type, control_make, control_model, status
        ) VALUES (?, 'VMC', 'VMC', 'demo', 'demo', 'running')
        """,
        (machine_id,),
    )


def test_migration_creates_cycletime_tables():
    with db.connect() as conn:
        names = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    for table in ("tool_material_params", "cycletime_estimates", "cycletime_actuals"):
        assert table in names, table


def test_missing_tool_material_params_asks_without_minutes():
    with db.connect() as conn:
        mat_id, _ = _seed_material_and_params(conn, suffix="ask")
        conn.execute("DELETE FROM tool_material_params WHERE material_id = ?", (mat_id,))
        _insert_machine(conn)
        out = estimate_parametric(
            conn,
            machine_id="mach_ct",
            material_id=mat_id,
            operation_class="milling",
            tool_geometry="12mm_4fl",
            cut_length_mm=800.0,
            store=False,
        )
    assert out.get("ask") is True
    assert "minutes" not in out


def test_milling_parametric_formula():
    with db.connect() as conn:
        mat_id, _ = _seed_material_and_params(conn, suffix="mill")
        _insert_machine(conn, "mach_mill")
        out = estimate_parametric(
            conn,
            machine_id="mach_mill",
            material_id=mat_id,
            operation_class="milling",
            tool_geometry="12mm_4fl",
            cut_length_mm=2560.0,
            store=False,
        )
    # F = 0.08 * 4 * 8000 = 2560 mm/min -> 2560/2560 = 1.0 min cut
    assert out.get("ask") is not True
    assert out["minutes"] == 1.0
    assert out["method"] == "parametric"
    assert out["confidence"] == "uncalibrated"
    assert out["label"] == "uncalibrated"
    assert out["calibration_n"] == 0


def test_turning_parametric_formula():
    with db.connect() as conn:
        mat_id, _ = _seed_material_and_params(conn, suffix="turn")
        _insert_machine(conn, "mach_turn")
        out = estimate_parametric(
            conn,
            machine_id="mach_turn",
            material_id=mat_id,
            operation_class="turning",
            tool_geometry="cnmg_12",
            cut_length_mm=300.0,
            store=False,
        )
    # F = 0.25 * 1200 = 300 mm/min -> 300/300 = 1.0 min
    assert out["minutes"] == 1.0
    assert out["method"] == "parametric"


def test_incomplete_feed_speed_row_asks():
    with db.connect() as conn:
        mat_id, _ = _seed_material_and_params(conn, suffix="bad")
        conn.execute(
            """
            INSERT INTO tool_material_params (
              id, material_id, operation_class, tool_geometry,
              fz_mm, z, n_rpm, f_mm_rev, source_ref, effective_from
            ) VALUES ('tmp_bad', ?, 'milling', 'broken', NULL, 4, 8000, NULL, 'x', '2020-01-01')
            """,
            (mat_id,),
        )
        _insert_machine(conn, "mach_bad")
        out = estimate_parametric(
            conn,
            machine_id="mach_bad",
            material_id=mat_id,
            operation_class="milling",
            tool_geometry="broken",
            cut_length_mm=100.0,
            store=False,
        )
    assert out.get("ask") is True
    assert "minutes" not in out


def test_calibration_applies_ratio_when_samples_exist():
    with db.connect() as conn:
        mat_id, _ = _seed_material_and_params(conn, suffix="cal")
        _insert_machine(conn, "mach_cal")
        conn.execute(
            """
            INSERT INTO cycletime_estimates (
              id, machine_id, material_id, operation_class, method, minutes,
              confidence, calibration_n, basis_json, created_at
            ) VALUES ('est1', 'mach_cal', ?, 'milling', 'parametric', 10.0,
              'uncalibrated', 0, '{}', '2026-01-01T00:00:00+00:00')
            """,
            (mat_id,),
        )
        conn.execute(
            """
            INSERT INTO cycletime_actuals (
              id, machine_id, material_id, operation_class, measured_min, pieces,
              operator_note, recorded_at, source_ref
            ) VALUES ('act1', 'mach_cal', ?, 'milling', 12.0, 1, NULL,
              '2026-01-02T00:00:00+00:00', 'test')
            """,
            (mat_id,),
        )
        out = estimate_parametric(
            conn,
            machine_id="mach_cal",
            material_id=mat_id,
            operation_class="milling",
            tool_geometry="12mm_4fl",
            cut_length_mm=2560.0,
            store=False,
        )
    assert out["confidence"] == "calibrated"
    assert out["calibration_n"] == 1
    assert out["minutes"] == 1.2
    assert "label" not in out


def test_record_actual_inserts_row():
    with db.connect() as conn:
        mat_id, _ = _seed_material_and_params(conn, suffix="rec")
        _insert_machine(conn, "mach_rec")
        cust_id = "cust_ct_rec"
        conn.execute(
            "INSERT INTO customers (id, name, currency, status) VALUES (?, ?, 'INR', 'active')",
            (cust_id, "Co rec test"),
        )
        comp = routings.create_component(conn, customer_id=cust_id, name="Part")
        rev = routings.create_part_revision(
            conn, component_id=comp["id"], revision="A", material_id=mat_id
        )
        rt = routings.create_routing(
            conn, part_revision_id=rev["id"], version=1, source_kind="owner"
        )
        op = routings.create_routing_operation(
            conn,
            routing_id=rt["id"],
            seq=10,
            operation="milling",
            machine_id="mach_rec",
            tooling=json.dumps(
                {"tool_geometry": "12mm_4fl", "cut_length_mm": 100}
            ),
        )
        saved = record_actual(conn, routing_operation_id=op["id"], measured_min=5.5, pieces=10)
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM cycletime_actuals WHERE id = ?",
            (saved["id"],),
        ).fetchone()["n"]
    assert n == 1
    assert saved["measured_min"] == 5.5


def test_jarvis_estimate_routing_uncalibrated_label():
    suffix = "rt"
    with db.connect() as conn:
        mat_id, _ = _seed_material_and_params(conn, suffix=suffix)
        _insert_machine(conn, "mach_rt")
        cust_id = "cust_ct_rt"
        conn.execute(
            "INSERT INTO customers (id, name, currency, status) VALUES (?, ?, 'INR', 'active')",
            (cust_id, f"Co rt {suffix}"),
        )
        comp = routings.create_component(conn, customer_id=cust_id, name="Bracket")
        rev = routings.create_part_revision(
            conn, component_id=comp["id"], revision="A", material_id=mat_id
        )
        rt = routings.create_routing(
            conn, part_revision_id=rev["id"], version=1, source_kind="owner"
        )
        routings.create_routing_operation(
            conn,
            routing_id=rt["id"],
            seq=10,
            operation="milling",
            machine_id="mach_rt",
            setup_min=15.0,
            tooling=json.dumps(
                {"tool_geometry": "12mm_4fl", "cut_length_mm": 2560.0}
            ),
        )

    out = jarvis_cycletime_estimate(routing_id=rt["id"])
    assert out.get("ask") is not True
    assert out["method"] == "parametric"
    assert out["confidence"] == "uncalibrated"
    assert out["label"] == "uncalibrated"
    assert out["calibration_n"] == 0
    assert out["setup_min"] == 15.0
    assert out["total_min"] == 16.0
    assert len(out["operations"]) == 1
    assert out["operations"][0]["label"] == "uncalibrated"


def test_program_path_without_routing_asks():
    out = jarvis_cycletime_estimate(program_path="/tmp/part.nc")
    assert out.get("ask") is True


def test_jarvis_record_actual_wrapper():
    with db.connect() as conn:
        mat_id, _ = _seed_material_and_params(conn, suffix="wrap")
        _insert_machine(conn, "mach_wrap")
        cust_id = "cust_ct_wrap"
        conn.execute(
            "INSERT INTO customers (id, name, currency, status) VALUES (?, ?, 'INR', 'active')",
            (cust_id, "Co wrap test"),
        )
        comp = routings.create_component(conn, customer_id=cust_id, name="Part")
        rev = routings.create_part_revision(
            conn, component_id=comp["id"], revision="A", material_id=mat_id
        )
        rt = routings.create_routing(
            conn, part_revision_id=rev["id"], version=1, source_kind="owner"
        )
        op = routings.create_routing_operation(
            conn,
            routing_id=rt["id"],
            seq=10,
            operation="turning",
            machine_id="mach_wrap",
            tooling=json.dumps({"tool_geometry": "cnmg_12", "cut_length_mm": 300}),
        )

    saved = jarvis_cycletime_record_actual(op["id"], measured_min=2.0, pieces=1)
    assert saved.get("ask") is not True
    assert saved["operation_class"] == "turning"
