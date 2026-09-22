"""Quote-to-actual variance: numbers only from quote_lines + quote_actuals rows."""

from __future__ import annotations

import uuid
from typing import Any

from . import db

_KIND_MATERIAL = "material"
_KIND_MACHINING = "machining"
_KIND_OUTSOURCE = "outsource"


def _latest_actual(conn, quote_line_id: str):
    return conn.execute(
        """
        SELECT *
        FROM quote_actuals
        WHERE quote_line_id = ?
        ORDER BY recorded_at DESC, id DESC
        LIMIT 1
        """,
        (quote_line_id,),
    ).fetchone()


def _quoted_payload(line) -> dict[str, Any]:
    kind = str(line["kind"])
    out: dict[str, Any] = {
        "kind": kind,
        "amount_minor": int(line["amount_minor"]),
        "qty": float(line["qty"]),
    }
    if line["time_min"] is not None:
        out["time_min"] = float(line["time_min"])
    return out


def _actual_payload(actual) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if actual["cycle_min_actual"] is not None:
        out["cycle_min_actual"] = float(actual["cycle_min_actual"])
    if actual["material_minor_actual"] is not None:
        out["material_minor_actual"] = int(actual["material_minor_actual"])
    if actual["outsource_minor_actual"] is not None:
        out["outsource_minor_actual"] = int(actual["outsource_minor_actual"])
    if actual["scrap_qty"] is not None:
        out["scrap_qty"] = float(actual["scrap_qty"])
    return out


def _machining_actual_minor(line, actual) -> int | None:
    quoted_time = line["time_min"]
    cycle = actual["cycle_min_actual"]
    if quoted_time is None or cycle is None:
        return None
    qt = float(quoted_time)
    if qt <= 0:
        return None
    quoted_amt = int(line["amount_minor"])
    return int(round(quoted_amt * float(cycle) / qt))


def _actual_amount_minor(line, actual) -> int | None:
    kind = str(line["kind"])
    if kind == _KIND_MATERIAL:
        if actual["material_minor_actual"] is None:
            return None
        return int(actual["material_minor_actual"])
    if kind == _KIND_OUTSOURCE:
        if actual["outsource_minor_actual"] is None:
            return None
        return int(actual["outsource_minor_actual"])
    if kind == _KIND_MACHINING:
        return _machining_actual_minor(line, actual)
    return None


def _delta_for_line(line, actual) -> dict[str, Any]:
    kind = str(line["kind"])
    delta: dict[str, Any] = {}
    quoted_amt = int(line["amount_minor"])
    actual_amt = _actual_amount_minor(line, actual)
    if actual_amt is not None:
        delta["amount_minor"] = actual_amt - quoted_amt

    if kind == _KIND_MACHINING and line["time_min"] is not None and actual["cycle_min_actual"] is not None:
        delta["time_min"] = float(actual["cycle_min_actual"]) - float(line["time_min"])

    if actual["scrap_qty"] is not None:
        delta["scrap_qty"] = float(actual["scrap_qty"])

    return delta


def _erosion_minor(line, actual) -> int:
    quoted_amt = int(line["amount_minor"])
    actual_amt = _actual_amount_minor(line, actual)
    if actual_amt is None:
        return 0
    return max(0, actual_amt - quoted_amt)


def record_actual(
    quote_line_id: str,
    *,
    cycle_min_actual: float | None = None,
    material_minor_actual: int | None = None,
    outsource_minor_actual: int | None = None,
    scrap_qty: float | None = None,
    source_ref: str,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    ref = (source_ref or "").strip()
    if not ref:
        raise ValueError("source_ref is required")
    lid = (quote_line_id or "").strip()
    if not lid:
        raise ValueError("quote_line_id is required")

    row_id = f"qact_{uuid.uuid4().hex[:12]}"
    ts = recorded_at or db.utc_now()

    with db.connect() as conn:
        line = conn.execute(
            "SELECT id FROM quote_lines WHERE id = ?",
            (lid,),
        ).fetchone()
        if not line:
            raise ValueError(f"unknown quote_line_id: {lid}")

        conn.execute(
            """
            INSERT INTO quote_actuals (
              id, quote_line_id,
              cycle_min_actual, material_minor_actual, outsource_minor_actual,
              scrap_qty, recorded_at, source_ref
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row_id,
                lid,
                cycle_min_actual,
                material_minor_actual,
                outsource_minor_actual,
                scrap_qty,
                ts,
                ref,
            ),
        )
        inserted = conn.execute(
            "SELECT * FROM quote_actuals WHERE id = ?",
            (row_id,),
        ).fetchone()

    return dict(inserted)


def line_variance(quote_line_id: str) -> dict[str, Any]:
    lid = (quote_line_id or "").strip()
    if not lid:
        return {"quote_line_id": lid, "ask": True}

    with db.connect() as conn:
        line = conn.execute(
            "SELECT * FROM quote_lines WHERE id = ?",
            (lid,),
        ).fetchone()
        if not line:
            return {"quote_line_id": lid, "ask": True}

        actual = _latest_actual(conn, lid)
        if actual is None:
            return {"quote_line_id": lid, "ask": True}

        quoted = _quoted_payload(line)
        actual_map = _actual_payload(actual)
        delta = _delta_for_line(line, actual)

    return {
        "quote_line_id": lid,
        "quoted": quoted,
        "actual": actual_map,
        "delta": delta,
        "source_ref": str(actual["source_ref"]),
        "recorded_at": str(actual["recorded_at"]),
    }


def rank_margin_erosion(limit: int = 20) -> list[dict[str, Any]]:
    cap = max(1, int(limit))
    with db.connect() as conn:
        lines = conn.execute(
            """
            SELECT ql.*
            FROM quote_lines ql
            WHERE ql.kind IN ('material', 'machining', 'outsource')
            """
        ).fetchall()

        ranked: list[dict[str, Any]] = []
        for line in lines:
            actual = _latest_actual(conn, str(line["id"]))
            if actual is None:
                continue
            erosion = _erosion_minor(line, actual)
            if erosion <= 0:
                continue
            delta = _delta_for_line(line, actual)
            ranked.append(
                {
                    "quote_line_id": str(line["id"]),
                    "quote_revision_id": str(line["quote_revision_id"]),
                    "kind": str(line["kind"]),
                    "description": str(line["description"]),
                    "erosion_minor": erosion,
                    "quoted_amount_minor": int(line["amount_minor"]),
                    "actual_amount_minor": _actual_amount_minor(line, actual),
                    "delta": delta,
                    "source_ref": str(actual["source_ref"]),
                    "recorded_at": str(actual["recorded_at"]),
                }
            )

    ranked.sort(
        key=lambda row: (
            -int(row["erosion_minor"]),
            str(row["quote_line_id"]),
        ),
    )
    return ranked[:cap]
