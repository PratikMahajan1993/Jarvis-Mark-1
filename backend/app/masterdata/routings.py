"""Components, part revisions, routings — read/write and jobs dual-read projection."""

from __future__ import annotations

import sqlite3
import uuid
from typing import Any, TypedDict

from .. import db


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class Component(TypedDict):
    id: str
    customer_id: str
    customer_part_no: str
    our_part_no: str
    name: str


class PartRevision(TypedDict):
    id: str
    component_id: str
    revision: str
    drawing_no: str
    drawing_artifact_id: str
    drawing_sha256: str
    material_id: str
    blank_spec: str
    finished_mass_kg: float | None
    units: str
    analysis_state: str
    superseded_by: str


class Routing(TypedDict):
    id: str
    part_revision_id: str
    version: int
    status: str
    source_kind: str
    accepted_by: str
    accepted_at: str


class RoutingOperation(TypedDict):
    id: str
    routing_id: str
    seq: int
    operation: str
    machine_id: str
    outsource_vendor_id: str
    outsource_case: str
    setup_min: float | None
    cycle_min_est: float | None
    cycle_min_actual: float | None
    est_method: str
    est_confidence: float | None
    est_calibration_n: int | None
    tooling: str
    fixture: str
    program_ref: str
    inspection: str


class PartBundle(TypedDict):
    component: Component
    part_revision: PartRevision
    routing: Routing
    operations: list[RoutingOperation]


def _component_row(row: Any) -> Component:
    data = dict(row)
    return {
        "id": data.get("id") or "",
        "customer_id": data.get("customer_id") or "",
        "customer_part_no": data.get("customer_part_no") or "",
        "our_part_no": data.get("our_part_no") or "",
        "name": data.get("name") or "",
    }


def _part_revision_row(row: Any) -> PartRevision:
    data = dict(row)
    return {
        "id": data.get("id") or "",
        "component_id": data.get("component_id") or "",
        "revision": data.get("revision") or "",
        "drawing_no": data.get("drawing_no") or "",
        "drawing_artifact_id": data.get("drawing_artifact_id") or "",
        "drawing_sha256": data.get("drawing_sha256") or "",
        "material_id": data.get("material_id") or "",
        "blank_spec": data.get("blank_spec") or "",
        "finished_mass_kg": _as_float(data.get("finished_mass_kg")),
        "units": data.get("units") or "mm",
        "analysis_state": data.get("analysis_state") or "none",
        "superseded_by": data.get("superseded_by") or "",
    }


def _routing_row(row: Any) -> Routing:
    data = dict(row)
    version = data.get("version")
    return {
        "id": data.get("id") or "",
        "part_revision_id": data.get("part_revision_id") or "",
        "version": int(version) if version is not None else 0,
        "status": data.get("status") or "",
        "source_kind": data.get("source_kind") or "",
        "accepted_by": data.get("accepted_by") or "",
        "accepted_at": data.get("accepted_at") or "",
    }


def _routing_operation_row(row: Any) -> RoutingOperation:
    data = dict(row)
    cal_n = data.get("est_calibration_n")
    return {
        "id": data.get("id") or "",
        "routing_id": data.get("routing_id") or "",
        "seq": int(data.get("seq") or 0),
        "operation": data.get("operation") or "",
        "machine_id": data.get("machine_id") or "",
        "outsource_vendor_id": data.get("outsource_vendor_id") or "",
        "outsource_case": data.get("outsource_case") or "",
        "setup_min": _as_float(data.get("setup_min")),
        "cycle_min_est": _as_float(data.get("cycle_min_est")),
        "cycle_min_actual": _as_float(data.get("cycle_min_actual")),
        "est_method": data.get("est_method") or "",
        "est_confidence": _as_float(data.get("est_confidence")),
        "est_calibration_n": int(cal_n) if cal_n is not None else None,
        "tooling": data.get("tooling") or "",
        "fixture": data.get("fixture") or "",
        "program_ref": data.get("program_ref") or "",
        "inspection": data.get("inspection") or "",
    }


def create_component(
    conn: sqlite3.Connection,
    *,
    customer_id: str,
    name: str,
    customer_part_no: str = "",
    our_part_no: str = "",
    component_id: str | None = None,
) -> Component:
    new_id = (component_id or "").strip() or uuid.uuid4().hex[:12]
    conn.execute(
        """
        INSERT INTO components (id, customer_id, customer_part_no, our_part_no, name)
        VALUES (?, ?, ?, ?, ?)
        """,
        (new_id, customer_id, customer_part_no or None, our_part_no or None, name),
    )
    row = conn.execute("SELECT * FROM components WHERE id = ?", (new_id,)).fetchone()
    if not row:
        raise RuntimeError(f"Failed to read component {new_id} after insert")
    return _component_row(row)


def create_part_revision(
    conn: sqlite3.Connection,
    *,
    component_id: str,
    revision: str,
    material_id: str = "",
    drawing_no: str = "",
    drawing_artifact_id: str = "",
    drawing_sha256: str = "",
    blank_spec: str = "",
    finished_mass_kg: float | None = None,
    units: str = "mm",
    analysis_state: str = "none",
    revision_id: str | None = None,
) -> PartRevision:
    new_id = (revision_id or "").strip() or uuid.uuid4().hex[:12]
    conn.execute(
        """
        INSERT INTO part_revisions (
          id, component_id, revision, drawing_no, drawing_artifact_id, drawing_sha256,
          material_id, blank_spec, finished_mass_kg, units, analysis_state
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id,
            component_id,
            revision,
            drawing_no or None,
            drawing_artifact_id or None,
            drawing_sha256 or None,
            material_id or None,
            blank_spec or None,
            finished_mass_kg,
            units or "mm",
            analysis_state or "none",
        ),
    )
    row = conn.execute("SELECT * FROM part_revisions WHERE id = ?", (new_id,)).fetchone()
    if not row:
        raise RuntimeError(f"Failed to read part revision {new_id} after insert")
    return _part_revision_row(row)


def create_routing(
    conn: sqlite3.Connection,
    *,
    part_revision_id: str,
    version: int,
    source_kind: str,
    status: str = "draft",
    accepted_by: str = "",
    accepted_at: str = "",
    routing_id: str | None = None,
) -> Routing:
    new_id = (routing_id or "").strip() or uuid.uuid4().hex[:12]
    conn.execute(
        """
        INSERT INTO routings (
          id, part_revision_id, version, status, source_kind, accepted_by, accepted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id,
            part_revision_id,
            int(version),
            status or "draft",
            source_kind,
            accepted_by or None,
            accepted_at or None,
        ),
    )
    row = conn.execute("SELECT * FROM routings WHERE id = ?", (new_id,)).fetchone()
    if not row:
        raise RuntimeError(f"Failed to read routing {new_id} after insert")
    return _routing_row(row)


def create_routing_operation(
    conn: sqlite3.Connection,
    *,
    routing_id: str,
    seq: int,
    operation: str,
    machine_id: str = "",
    outsource_vendor_id: str = "",
    outsource_case: str = "",
    setup_min: float | None = None,
    cycle_min_est: float | None = None,
    cycle_min_actual: float | None = None,
    est_method: str = "",
    est_confidence: float | None = None,
    est_calibration_n: int | None = None,
    tooling: str = "",
    fixture: str = "",
    program_ref: str = "",
    inspection: str = "",
    operation_id: str | None = None,
) -> RoutingOperation:
    if not (machine_id or "").strip() and not (outsource_vendor_id or "").strip():
        raise ValueError("routing operation requires machine_id or outsource_vendor_id")
    new_id = (operation_id or "").strip() or uuid.uuid4().hex[:12]
    conn.execute(
        """
        INSERT INTO routing_operations (
          id, routing_id, seq, operation, machine_id, outsource_vendor_id, outsource_case,
          setup_min, cycle_min_est, cycle_min_actual, est_method, est_confidence,
          est_calibration_n, tooling, fixture, program_ref, inspection
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id,
            routing_id,
            int(seq),
            operation,
            machine_id or None,
            outsource_vendor_id or None,
            outsource_case or None,
            setup_min,
            cycle_min_est,
            cycle_min_actual,
            est_method or None,
            est_confidence,
            est_calibration_n,
            tooling or None,
            fixture or None,
            program_ref or None,
            inspection or None,
        ),
    )
    row = conn.execute("SELECT * FROM routing_operations WHERE id = ?", (new_id,)).fetchone()
    if not row:
        raise RuntimeError(f"Failed to read routing operation {new_id} after insert")
    return _routing_operation_row(row)


def get_component(conn: sqlite3.Connection, component_id: str) -> Component | None:
    if not component_id:
        return None
    row = conn.execute("SELECT * FROM components WHERE id = ?", (component_id,)).fetchone()
    return _component_row(row) if row else None


def get_part_revision(conn: sqlite3.Connection, revision_id: str) -> PartRevision | None:
    if not revision_id:
        return None
    row = conn.execute("SELECT * FROM part_revisions WHERE id = ?", (revision_id,)).fetchone()
    return _part_revision_row(row) if row else None


def get_routing(conn: sqlite3.Connection, routing_id: str) -> Routing | None:
    if not routing_id:
        return None
    row = conn.execute("SELECT * FROM routings WHERE id = ?", (routing_id,)).fetchone()
    return _routing_row(row) if row else None


def list_routing_operations(conn: sqlite3.Connection, routing_id: str) -> list[RoutingOperation]:
    if not routing_id:
        return []
    rows = conn.execute(
        "SELECT * FROM routing_operations WHERE routing_id = ? ORDER BY seq",
        (routing_id,),
    ).fetchall()
    return [_routing_operation_row(row) for row in rows]


def get_part_bundle(conn: sqlite3.Connection, component_id: str) -> PartBundle | None:
    component = get_component(conn, component_id)
    if not component:
        return None
    rev_row = conn.execute(
        """
        SELECT * FROM part_revisions
        WHERE component_id = ? AND (superseded_by IS NULL OR superseded_by = '')
        ORDER BY revision DESC
        LIMIT 1
        """,
        (component_id,),
    ).fetchone()
    if not rev_row:
        return None
    part_revision = _part_revision_row(rev_row)
    rt_row = conn.execute(
        """
        SELECT * FROM routings
        WHERE part_revision_id = ?
        ORDER BY version DESC
        LIMIT 1
        """,
        (part_revision["id"],),
    ).fetchone()
    if not rt_row:
        return None
    routing = _routing_row(rt_row)
    operations = list_routing_operations(conn, routing["id"])
    return {
        "component": component,
        "part_revision": part_revision,
        "routing": routing,
        "operations": operations,
    }


def _job_from_bundle(conn: sqlite3.Connection, bundle: PartBundle) -> dict[str, Any]:
    component = bundle["component"]
    part_revision = bundle["part_revision"]
    routing = bundle["routing"]
    operations = bundle["operations"]

    cust = conn.execute(
        "SELECT name FROM customers WHERE id = ?",
        (component["customer_id"],),
    ).fetchone()
    customer_name = cust["name"] if cust else ""

    material = ""
    if part_revision["material_id"]:
        mat = conn.execute(
            "SELECT grade FROM materials WHERE id = ?",
            (part_revision["material_id"],),
        ).fetchone()
        if mat:
            material = mat["grade"] or ""

    machine = ""
    cycle_min: float | None = None
    if operations:
        first = operations[0]
        if first["machine_id"]:
            mach = conn.execute(
                "SELECT name FROM machines WHERE id = ?",
                (first["machine_id"],),
            ).fetchone()
            if mach:
                machine = mach["name"] or ""
        total = 0.0
        has_cycle = False
        for op in operations:
            est = op["cycle_min_est"]
            if est is not None:
                total += est
                has_cycle = True
        if has_cycle:
            cycle_min = total

    drawing_file = part_revision["drawing_artifact_id"] or part_revision["drawing_no"] or ""
    created_at = routing["accepted_at"] or ""

    return {
        "id": component["id"],
        "customer": customer_name,
        "part_name": component["name"],
        "material": material,
        "machine": machine,
        "cycle_min": cycle_min,
        "margin": None,
        "drawing_file": drawing_file,
        "geometry_notes": part_revision["blank_spec"] or "",
        "created_at": created_at,
    }


def job_for_component_id(component_id: str) -> dict[str, Any] | None:
    if not component_id:
        return None
    with db.connect() as conn:
        bundle = get_part_bundle(conn, component_id)
        if not bundle:
            return None
        return _job_from_bundle(conn, bundle)


def list_jobs_from_masterdata(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT id FROM components ORDER BY name").fetchall()
    jobs: list[dict[str, Any]] = []
    for row in rows:
        bundle = get_part_bundle(conn, row["id"])
        if bundle:
            jobs.append(_job_from_bundle(conn, bundle))
    return jobs
