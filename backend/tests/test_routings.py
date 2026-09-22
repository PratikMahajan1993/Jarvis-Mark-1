from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="jarvis-routings-"))
settings.data_dir = _TMP / "data"
settings.data_dir.mkdir(parents=True, exist_ok=True)

from app import db  # noqa: E402
from app import jobs  # noqa: E402
from app.masterdata import routings  # noqa: E402


def setup_module(_module=None):
    db.init_db()


def _insert_machine(conn, *, machine_id: str = "mach_rt_test") -> None:
    conn.execute(
        """
        INSERT INTO machines (
          id, name, machine_type, control_make, control_model, status
        ) VALUES (?, 'Turn cell', 'Turning', 'demo', 'demo', 'running')
        """,
        (machine_id,),
    )


def _round_trip_fixture(conn, *, suffix: str):
    cust_id = f"cust_rt_{suffix}"
    mat_id = f"mat_rt_{suffix}"
    mach_id = f"mach_rt_{suffix}"
    comp_id = f"comp_rt_{suffix}"
    conn.execute(
        """
        INSERT INTO customers (id, name, gstin, currency, status)
        VALUES (?, ?, NULL, 'INR', 'active')
        """,
        (cust_id, f"Round Trip Co {suffix}"),
    )
    conn.execute(
        """
        INSERT INTO materials (id, grade, family, form)
        VALUES (?, ?, 'carbon', 'bar')
        """,
        (mat_id, f"EN8-{suffix}"),
    )
    _insert_machine(conn, machine_id=mach_id)
    component = routings.create_component(
        conn,
        component_id=comp_id,
        customer_id=cust_id,
        name="Test bracket",
        customer_part_no=f"BR-{suffix}",
    )
    revision = routings.create_part_revision(
        conn,
        revision_id=f"rev_rt_{suffix}",
        component_id=component["id"],
        revision="A",
        material_id=mat_id,
        drawing_no="DWG-001",
        blank_spec="Chuck OD, face, bore.",
    )
    routing = routings.create_routing(
        conn,
        routing_id=f"rt_rt_{suffix}",
        part_revision_id=revision["id"],
        version=1,
        source_kind="owner",
        status="accepted",
        accepted_at="2026-03-01T00:00:00+00:00",
    )
    op = routings.create_routing_operation(
        conn,
        operation_id=f"op_rt_{suffix}",
        routing_id=routing["id"],
        seq=10,
        operation="turning",
        machine_id=mach_id,
        cycle_min_est=12.5,
    )
    return component, revision, routing, op, f"EN8-{suffix}", f"Round Trip Co {suffix}"


def test_migration_creates_routing_tables():
    with db.connect() as conn:
        names = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    for table in (
        "components",
        "part_revisions",
        "outsource_vendors",
        "outsource_quotes",
        "routings",
        "routing_operations",
    ):
        assert table in names, table


def test_part_routing_round_trip():
    with db.connect() as conn:
        component, revision, routing, op, _grade, _cust = _round_trip_fixture(conn, suffix="a")
        bundle = routings.get_part_bundle(conn, component["id"])
        assert bundle is not None
        assert bundle["component"] == component
        assert bundle["part_revision"]["id"] == revision["id"]
        assert bundle["routing"]["id"] == routing["id"]
        assert len(bundle["operations"]) == 1
        assert bundle["operations"][0]["id"] == op["id"]
        assert bundle["operations"][0]["cycle_min_est"] == 12.5

        assert routings.get_component(conn, component["id"]) == component
        assert routings.get_part_revision(conn, revision["id"]) == revision
        assert routings.get_routing(conn, routing["id"]) == routing
        assert routings.list_routing_operations(conn, routing["id"]) == bundle["operations"]


def test_list_jobs_unchanged_when_masterdata_off(monkeypatch):
    monkeypatch.setattr(settings, "masterdata_enabled", False)
    with db.connect() as conn:
        conn.execute("DELETE FROM jobs")
    jobs.seed_demo_job()
    with db.connect() as conn:
        component, *_rest = _round_trip_fixture(conn, suffix="off")
    listed = jobs.list_jobs()
    assert len(listed) == 1
    assert listed[0]["id"] == jobs.DEMO_JOB_ID
    assert jobs.get_job(component["id"]) is None


def test_list_jobs_includes_component_when_masterdata_on(monkeypatch):
    monkeypatch.setattr(settings, "masterdata_enabled", True)
    with db.connect() as conn:
        conn.execute("DELETE FROM jobs")
        component, revision, routing, op, grade, cust_name = _round_trip_fixture(
            conn, suffix="on"
        )
    listed = {row["id"]: row for row in jobs.list_jobs()}
    assert component["id"] in listed
    job = listed[component["id"]]
    assert job["customer"] == cust_name
    assert job["part_name"] == "Test bracket"
    assert job["material"] == grade
    assert job["cycle_min"] == 12.5
    assert job["geometry_notes"] == "Chuck OD, face, bore."
    fetched = jobs.get_job(component["id"])
    assert fetched == job
