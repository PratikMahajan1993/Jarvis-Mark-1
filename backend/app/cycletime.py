"""Parametric cycletime Engine A + calibration store (§3.4 — M2)."""

from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from . import db

_MILLING_CLASSES = frozenset({"milling", "mill", "vmc", "hmc"})
_TURNING_CLASSES = frozenset({"turning", "turn", "lathe"})


def _normalize_operation_class(operation: str) -> str:
    key = (operation or "").strip().lower()
    if key in _MILLING_CLASSES:
        return "milling"
    if key in _TURNING_CLASSES:
        return "turning"
    return key


def _parse_tooling(tooling: str) -> dict[str, Any]:
    raw = (tooling or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _lookup_tool_material_params(
    conn: sqlite3.Connection,
    *,
    material_id: str,
    operation_class: str,
    tool_geometry: str,
    as_of: str | None = None,
) -> sqlite3.Row | None:
    if not material_id or not operation_class or not tool_geometry:
        return None
    as_of_val = (as_of or db.utc_now()).strip()
    return conn.execute(
        """
        SELECT * FROM tool_material_params
        WHERE material_id = ? AND operation_class = ? AND tool_geometry = ?
          AND effective_from <= ?
        ORDER BY effective_from DESC
        LIMIT 1
        """,
        (material_id, operation_class, tool_geometry, as_of_val),
    ).fetchone()


def _calibration_sample_count(
    conn: sqlite3.Connection,
    *,
    machine_id: str,
    material_id: str,
    operation_class: str,
) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS n FROM cycletime_actuals
        WHERE machine_id = ? AND material_id = ? AND operation_class = ?
        """,
        (machine_id, material_id, operation_class),
    ).fetchone()
    return int(row["n"]) if row else 0


def _calibration_ratio(
    conn: sqlite3.Connection,
    *,
    machine_id: str,
    material_id: str,
    operation_class: str,
) -> float | None:
    est = conn.execute(
        """
        SELECT AVG(minutes) AS mean_min FROM cycletime_estimates
        WHERE machine_id = ? AND material_id = ? AND operation_class = ?
        """,
        (machine_id, material_id, operation_class),
    ).fetchone()
    act = conn.execute(
        """
        SELECT AVG(measured_min) AS mean_min FROM cycletime_actuals
        WHERE machine_id = ? AND material_id = ? AND operation_class = ?
        """,
        (machine_id, material_id, operation_class),
    ).fetchone()
    mean_est = est["mean_min"] if est else None
    mean_act = act["mean_min"] if act else None
    if mean_est is None or mean_act is None:
        return None
    try:
        est_f = float(mean_est)
        act_f = float(mean_act)
    except (TypeError, ValueError):
        return None
    if est_f <= 0:
        return None
    return act_f / est_f


def _parametric_cut_minutes(
    *,
    operation_class: str,
    cut_length_mm: float,
    row: sqlite3.Row,
) -> float | None:
    if cut_length_mm <= 0:
        return None
    if operation_class == "milling":
        fz = row["fz_mm"]
        z = row["z"]
        n = row["n_rpm"]
        if fz is None or z is None or n is None:
            return None
        feed_mm_min = float(fz) * int(z) * float(n)
        if feed_mm_min <= 0:
            return None
        return cut_length_mm / feed_mm_min
    if operation_class == "turning":
        f_rev = row["f_mm_rev"]
        n = row["n_rpm"]
        if f_rev is None or n is None:
            return None
        feed_mm_min = float(f_rev) * float(n)
        if feed_mm_min <= 0:
            return None
        return cut_length_mm / feed_mm_min
    return None


def _store_estimate(
    conn: sqlite3.Connection,
    *,
    machine_id: str,
    material_id: str,
    operation_class: str,
    parametric_minutes: float,
    confidence: str,
    calibration_n: int,
    basis: dict[str, Any],
) -> str:
    new_id = uuid.uuid4().hex[:12]
    conn.execute(
        """
        INSERT INTO cycletime_estimates (
          id, machine_id, material_id, operation_class, method, minutes,
          confidence, calibration_n, basis_json, created_at
        ) VALUES (?, ?, ?, ?, 'parametric', ?, ?, ?, ?, ?)
        """,
        (
            new_id,
            machine_id,
            material_id,
            operation_class,
            parametric_minutes,
            confidence,
            calibration_n,
            json.dumps(basis, sort_keys=True),
            db.utc_now(),
        ),
    )
    return new_id


def estimate_parametric(
    conn: sqlite3.Connection,
    *,
    machine_id: str,
    material_id: str,
    operation_class: str,
    tool_geometry: str,
    cut_length_mm: float,
    air_moves_min: float = 0.0,
    approach_retract_min: float = 0.0,
    tool_change_min: float = 0.0,
    dwell_min: float = 0.0,
    setup_load_unload_min: float = 0.0,
    as_of: str | None = None,
    store: bool = True,
) -> dict[str, Any]:
    """Parametric per-op estimate from tool_material_params; never invents feeds."""
    op_class = _normalize_operation_class(operation_class)
    if not machine_id or not material_id or not op_class or not tool_geometry:
        return {
            "ask": True,
            "reason": "machine_id, material_id, operation_class, and tool_geometry are required",
        }
    if cut_length_mm <= 0:
        return {"ask": True, "reason": "cut_length_mm must be positive"}

    params = _lookup_tool_material_params(
        conn,
        material_id=material_id,
        operation_class=op_class,
        tool_geometry=tool_geometry,
        as_of=as_of,
    )
    if params is None:
        return {
            "ask": True,
            "reason": "no tool_material_params row for material, operation, and tool geometry",
        }

    t_cut = _parametric_cut_minutes(
        operation_class=op_class,
        cut_length_mm=cut_length_mm,
        row=params,
    )
    if t_cut is None:
        return {
            "ask": True,
            "reason": "tool_material_params row is missing feed/speed fields for this operation class",
        }

    overhead = (
        max(0.0, float(air_moves_min))
        + max(0.0, float(approach_retract_min))
        + max(0.0, float(tool_change_min))
        + max(0.0, float(dwell_min))
        + max(0.0, float(setup_load_unload_min))
    )
    parametric_minutes = t_cut + overhead

    calibration_n = _calibration_sample_count(
        conn,
        machine_id=machine_id,
        material_id=material_id,
        operation_class=op_class,
    )

    basis: dict[str, Any] = {
        "operation_class": op_class,
        "tool_geometry": tool_geometry,
        "cut_length_mm": cut_length_mm,
        "t_cut_min": t_cut,
        "overhead_min": overhead,
        "tool_material_params_id": params["id"],
        "source_ref": params["source_ref"],
    }

    if calibration_n == 0:
        confidence = "uncalibrated"
        minutes = parametric_minutes
        result: dict[str, Any] = {
            "minutes": minutes,
            "method": "parametric",
            "confidence": confidence,
            "calibration_n": 0,
            "label": "uncalibrated",
            "parametric_minutes": parametric_minutes,
            "basis": basis,
        }
    else:
        confidence = "calibrated"
        ratio = _calibration_ratio(
            conn,
            machine_id=machine_id,
            material_id=material_id,
            operation_class=op_class,
        )
        minutes = parametric_minutes * ratio if ratio is not None else parametric_minutes
        result = {
            "minutes": minutes,
            "method": "parametric",
            "confidence": confidence,
            "calibration_n": calibration_n,
            "parametric_minutes": parametric_minutes,
            "basis": basis,
        }
        if ratio is not None:
            result["calibration_ratio"] = ratio

    if store:
        _store_estimate(
            conn,
            machine_id=machine_id,
            material_id=material_id,
            operation_class=op_class,
            parametric_minutes=parametric_minutes,
            confidence=confidence,
            calibration_n=calibration_n,
            basis=basis,
        )
    return result


def record_actual(
    conn: sqlite3.Connection,
    *,
    routing_operation_id: str,
    measured_min: float,
    pieces: float | None = None,
    operator_note: str = "",
    source_ref: str | None = None,
) -> dict[str, Any]:
    """Append a measured cycle-time sample; does not edit quotes or routings."""
    op_id = (routing_operation_id or "").strip()
    if not op_id:
        return {"ask": True, "reason": "routing_operation_id is required"}
    try:
        measured = float(measured_min)
    except (TypeError, ValueError):
        return {"ask": True, "reason": "measured_min must be numeric"}
    if measured < 0:
        return {"ask": True, "reason": "measured_min must be non-negative"}

    row = conn.execute(
        """
        SELECT ro.*, pr.material_id AS part_material_id
        FROM routing_operations ro
        JOIN routings r ON r.id = ro.routing_id
        JOIN part_revisions pr ON pr.id = r.part_revision_id
        WHERE ro.id = ?
        """,
        (op_id,),
    ).fetchone()
    if row is None:
        return {"ask": True, "reason": "routing_operation_id not found"}

    machine_id = (row["machine_id"] or "").strip()
    material_id = (row["part_material_id"] or "").strip()
    operation_class = _normalize_operation_class(row["operation"] or "")
    if not machine_id:
        return {"ask": True, "reason": "operation has no machine_id (outsource ops cannot record actuals here)"}
    if not material_id:
        return {"ask": True, "reason": "part revision has no material_id"}

    new_id = uuid.uuid4().hex[:12]
    ref = (source_ref or "").strip() or f"routing_operation:{op_id}"
    conn.execute(
        """
        INSERT INTO cycletime_actuals (
          id, machine_id, material_id, operation_class, measured_min, pieces,
          operator_note, recorded_at, source_ref
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id,
            machine_id,
            material_id,
            operation_class,
            measured,
            pieces,
            operator_note or None,
            db.utc_now(),
            ref,
        ),
    )
    return {
        "id": new_id,
        "machine_id": machine_id,
        "material_id": material_id,
        "operation_class": operation_class,
        "measured_min": measured,
        "pieces": pieces,
    }


def jarvis_cycletime_estimate(
    routing_id: str = "",
    program_path: str = "",
    machine_id: str = "",
) -> dict[str, Any]:
    """Estimate cycle times for a routing (parametric Engine A only in M2)."""
    if (program_path or "").strip() and not (routing_id or "").strip():
        return {
            "ask": True,
            "reason": "G-code backplot (Engine B) is not available; provide routing_id",
        }
    rid = (routing_id or "").strip()
    if not rid:
        return {"ask": True, "reason": "routing_id is required"}

    with db.connect() as conn:
        routing = conn.execute("SELECT * FROM routings WHERE id = ?", (rid,)).fetchone()
        if routing is None:
            return {"ask": True, "reason": "routing_id not found"}

        rev = conn.execute(
            "SELECT * FROM part_revisions WHERE id = ?",
            (routing["part_revision_id"],),
        ).fetchone()
        material_id = (rev["material_id"] or "").strip() if rev else ""
        if not material_id:
            return {"ask": True, "reason": "part revision has no material_id"}

        ops_rows = conn.execute(
            "SELECT * FROM routing_operations WHERE routing_id = ? ORDER BY seq",
            (rid,),
        ).fetchall()

        machine_override = (machine_id or "").strip()
        per_ops: list[dict[str, Any]] = []
        setup_total = 0.0
        cycle_total = 0.0
        any_ask = False
        min_cal_n: int | None = None
        any_uncalibrated = False

        for op in ops_rows:
            if op["outsource_vendor_id"] and not op["machine_id"]:
                continue
            op_machine = machine_override or (op["machine_id"] or "").strip()
            if not op_machine:
                any_ask = True
                per_ops.append(
                    {
                        "routing_operation_id": op["id"],
                        "seq": op["seq"],
                        "ask": True,
                        "reason": "machine_id missing on operation",
                    }
                )
                continue

            tooling = _parse_tooling(op["tooling"] or "")
            tool_geometry = str(tooling.get("tool_geometry") or "").strip()
            cut_length = tooling.get("cut_length_mm")
            if not tool_geometry or cut_length is None:
                any_ask = True
                per_ops.append(
                    {
                        "routing_operation_id": op["id"],
                        "seq": op["seq"],
                        "ask": True,
                        "reason": "tooling JSON must include tool_geometry and cut_length_mm",
                    }
                )
                continue
            try:
                cut_f = float(cut_length)
            except (TypeError, ValueError):
                any_ask = True
                per_ops.append(
                    {
                        "routing_operation_id": op["id"],
                        "seq": op["seq"],
                        "ask": True,
                        "reason": "cut_length_mm must be numeric",
                    }
                )
                continue

            est = estimate_parametric(
                conn,
                machine_id=op_machine,
                material_id=material_id,
                operation_class=op["operation"] or "",
                tool_geometry=tool_geometry,
                cut_length_mm=cut_f,
                air_moves_min=float(tooling.get("air_moves_min") or 0),
                approach_retract_min=float(tooling.get("approach_retract_min") or 0),
                tool_change_min=float(tooling.get("tool_change_min") or 0),
                dwell_min=float(tooling.get("dwell_min") or 0),
                setup_load_unload_min=float(tooling.get("setup_load_unload_min") or 0),
            )
            if est.get("ask"):
                any_ask = True
                per_ops.append(
                    {
                        "routing_operation_id": op["id"],
                        "seq": op["seq"],
                        **est,
                    }
                )
                continue

            op_setup = op["setup_min"]
            if op_setup is not None:
                setup_total += float(op_setup)

            minutes = float(est["minutes"])
            cycle_total += minutes
            cal_n = int(est["calibration_n"])
            min_cal_n = cal_n if min_cal_n is None else min(min_cal_n, cal_n)
            if est.get("confidence") == "uncalibrated":
                any_uncalibrated = True

            entry: dict[str, Any] = {
                "routing_operation_id": op["id"],
                "seq": op["seq"],
                "minutes": minutes,
                "method": est["method"],
                "confidence": est["confidence"],
                "calibration_n": cal_n,
            }
            if est.get("label"):
                entry["label"] = est["label"]
            per_ops.append(entry)

        if any_ask:
            return {
                "ask": True,
                "reason": "one or more operations could not be estimated",
                "operations": per_ops,
            }

        overall_confidence = "uncalibrated" if any_uncalibrated else "calibrated"
        result: dict[str, Any] = {
            "routing_id": rid,
            "operations": per_ops,
            "setup_min": setup_total,
            "total_min": setup_total + cycle_total,
            "method": "parametric",
            "confidence": overall_confidence,
            "calibration_n": min_cal_n if min_cal_n is not None else 0,
        }
        if any_uncalibrated:
            result["label"] = "uncalibrated"
        return result


def jarvis_cycletime_record_actual(
    routing_operation_id: str,
    measured_min: float,
    pieces: float | None = None,
    operator_note: str = "",
) -> dict[str, Any]:
    with db.connect() as conn:
        return record_actual(
            conn,
            routing_operation_id=routing_operation_id,
            measured_min=measured_min,
            pieces=pieces,
            operator_note=operator_note,
        )
