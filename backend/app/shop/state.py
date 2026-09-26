"""Materialised shop_state from production_logs — numbers only from log rows."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .. import db

_SHOP_KEY_PREFIX = "machine:"
_NUMERIC_KINDS = frozenset({"oee", "oee_pct"})
_WHY_KINDS = frozenset({"why", "narrative"})


def _shop_key(machine_id: str) -> str:
    return f"{_SHOP_KEY_PREFIX}{machine_id}"


def _latest_logs_by_machine(conn) -> dict[str, list[Any]]:
    rows = conn.execute(
        """
        SELECT pl.*, dr.label AS downtime_label
        FROM production_logs pl
        LEFT JOIN downtime_reasons dr ON dr.code = pl.downtime_reason
        WHERE pl.machine_id IS NOT NULL
        ORDER BY pl.log_date DESC, pl.id DESC
        """
    ).fetchall()
    by_machine: dict[str, list[Any]] = {}
    for row in rows:
        mid = str(row["machine_id"])
        by_machine.setdefault(mid, []).append(row)
    return by_machine


def _numbers_in_logs(rows: list[Any]) -> set[str]:
    found: set[str] = set()
    for row in rows:
        for key in (
            "qty_ok",
            "qty_rework",
            "qty_scrap",
            "run_min",
            "downtime_min",
            "oee_pct",
        ):
            val = row[key]
            if val is None:
                continue
            if isinstance(val, float) and val.is_integer():
                found.add(str(int(val)))
            else:
                found.add(str(val))
            if key == "oee_pct" and isinstance(val, (int, float)):
                found.add(f"{float(val):g}")
    return found


def _build_narrative(rows: list[Any]) -> str:
    """Qualitative digest; any number must appear in the source log rows."""
    if not rows:
        return ""
    allowed = _numbers_in_logs(rows)
    parts: list[str] = []
    latest = rows[0]
    shift = str(latest["shift"] or "").strip()
    if shift:
        parts.append(f"Latest entry is the {shift} shift log.")
    downtime_label = latest["downtime_label"] if "downtime_label" in latest.keys() else None
    downtime_min = latest["downtime_min"]
    if downtime_label and downtime_min is not None:
        parts.append(f"Downtime was attributed to {downtime_label}.")
    elif downtime_label:
        parts.append(f"Last downtime reason recorded: {downtime_label}.")
    scrap = latest["qty_scrap"] or 0
    if scrap:
        scrap_s = str(int(scrap)) if float(scrap).is_integer() else str(scrap)
        if scrap_s in allowed:
            parts.append(f"Scrap quantity was {scrap_s} on the latest log.")
    operator = str(latest["operator"] or "").strip()
    if operator:
        parts.append(f"Operator on record: {operator}.")
    if not parts:
        parts.append("Production log exists but no narrative detail was captured.")
    text = " ".join(parts)
    for match in re.findall(r"\d+(?:\.\d+)?", text):
        if match not in allowed:
            raise ValueError("digest contains a number not present in production_logs")
    return text


def rebuild_shop_state() -> int:
    """Rebuild shop_state rows (one per machine_id present in production_logs)."""
    written = 0
    with db.connect() as conn:
        conn.execute("DELETE FROM shop_state WHERE key LIKE ?", (f"{_SHOP_KEY_PREFIX}%",))
        by_machine = _latest_logs_by_machine(conn)
        for machine_id, rows in by_machine.items():
            latest = rows[0]
            as_of = str(latest["log_date"])
            narrative = _build_narrative(rows)
            payload = {
                "machine_id": machine_id,
                "oee_pct": latest["oee_pct"],
                "source_ref": str(latest["source_ref"] or ""),
                "log_id": str(latest["id"]),
                "narrative": narrative,
            }
            derived_from = f"production_logs<={as_of}"
            conn.execute(
                """
                INSERT INTO shop_state (key, payload, as_of, derived_from)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                  payload = excluded.payload,
                  as_of = excluded.as_of,
                  derived_from = excluded.derived_from
                """,
                (
                    _shop_key(machine_id),
                    json.dumps(payload),
                    as_of,
                    derived_from,
                ),
            )
            written += 1
    return written


def _ask(message: str) -> dict[str, Any]:
    return {
        "kind": "ask",
        "speak": message,
        "as_of": None,
        "source_ref": None,
        "cites": None,
    }


def answer_shop(machine_id: str, kind: str) -> dict[str, Any]:
    """
    Numeric kinds read OEE from the projected log fields (never the digest).
    Why/narrative kinds return the stored digest with the same freshness stamp.
    """
    mid = (machine_id or "").strip()
    if not mid:
        return _ask("Which machine should I look up in the production log?")

    kind_norm = (kind or "").strip().lower()
    with db.connect() as conn:
        row = conn.execute(
            "SELECT payload, as_of, derived_from FROM shop_state WHERE key = ?",
            (_shop_key(mid),),
        ).fetchone()

    if row is None:
        return _ask("I have no production log rows for that machine yet, so I cannot cite an OEE.")

    payload = json.loads(row["payload"])
    as_of = row["as_of"]
    source_ref = payload.get("source_ref") or None

    if kind_norm in _WHY_KINDS:
        narrative = str(payload.get("narrative") or "").strip()
        if not narrative:
            return _ask("There is no narrative digest for that machine yet.")
        return {
            "kind": "narrative",
            "speak": narrative,
            "as_of": as_of,
            "source_ref": source_ref,
            "cites": "digest",
            "derived_from": row["derived_from"],
        }

    if kind_norm in _NUMERIC_KINDS or kind_norm == "":
        oee = payload.get("oee_pct")
        if oee is None:
            return _ask("The production log has no OEE figure for that machine — I will not invent one.")
        return {
            "kind": "numeric",
            "value": float(oee),
            "speak": str(float(oee)),
            "as_of": as_of,
            "source_ref": source_ref,
            "cites": "production_log",
            "log_id": payload.get("log_id"),
            "derived_from": row["derived_from"],
        }

    return _ask(f"I do not know how to answer shop questions of kind {kind!r} yet.")


_FLOOR_PREFIX = "floor:"
_FRESHNESS_KIND = {
    "machine": "machine_status",
    "vendor": "vendor_turnaround",
    "stock": "stock",
    "oee": "oee",
}


def _floor_key(kind: str, ident: str) -> str:
    return f"{_FLOOR_PREFIX}{kind}:{ident}"


def _load_payload(conn, key: str) -> dict[str, Any]:
    row = conn.execute("SELECT payload FROM shop_state WHERE key = ?", (key,)).fetchone()
    if row is None:
        return {}
    try:
        parsed = json.loads(row["payload"])
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _save_floor(
    conn,
    key: str,
    kind: str,
    data: dict[str, Any],
    as_of: str,
    event_id: str,
) -> None:
    data = dict(data)
    data["updated_at"] = as_of
    data["kind"] = kind
    conn.execute(
        """
        INSERT INTO shop_state (key, payload, as_of, derived_from)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
          payload = excluded.payload,
          as_of = excluded.as_of,
          derived_from = excluded.derived_from
        """,
        (key, json.dumps(data), as_of, f"shop_events:{event_id}"),
    )


def _apply_shop_event(conn, event: dict[str, Any], *, project_oee: bool = True) -> None:
    kind = str(event.get("kind") or "")
    ts = str(event.get("ts") or event.get("created_at") or "")
    event_id = str(event.get("id") or "")
    if kind in {"downtime", "oee", "scrap"} and event.get("machine_id"):
        mid = str(event["machine_id"])
        key = _floor_key("machine", mid)
        data = _load_payload(conn, key) or {"machine_id": mid}
        data["machine_id"] = mid
        if event.get("machine_name"):
            data["machine_name"] = event["machine_name"]
        if kind == "downtime":
            data["status"] = "down"
            data["last_downtime_min"] = event.get("value")
            data["last_downtime_reason"] = str(event.get("details") or "")
        elif kind == "oee":
            data["oee_pct"] = event.get("value")
            data.setdefault("status", "running")
        elif kind == "scrap":
            data["last_scrap"] = event.get("value")
            data["scrap_unit"] = str(event.get("unit") or "")
        _save_floor(conn, key, "machine", data, ts, event_id)
        if kind == "oee" and project_oee:
            _rebuild_oee_projection(conn, event_id, ts)
        return
    if kind == "vendor":
        try:
            detail = json.loads(str(event.get("details") or "{}"))
        except json.JSONDecodeError:
            detail = {}
        vendor = str(detail.get("vendor") or "").strip()
        if not vendor:
            return
        key = _floor_key("vendor", vendor.lower())
        data = _load_payload(conn, key) or {"vendor": vendor}
        data["vendor"] = vendor
        data["last_days"] = event.get("value")
        data["last_delivery"] = detail.get("last_delivery") or ""
        _save_floor(conn, key, "vendor", data, ts, event_id)
        return
    if kind == "stock" and event.get("component_id"):
        component_id = str(event["component_id"])
        try:
            detail = json.loads(str(event.get("details") or "{}"))
        except json.JSONDecodeError:
            detail = {}
        key = _floor_key("stock", component_id)
        data = {
            "component_id": component_id,
            "on_hand": detail.get("on_hand"),
            "allocated": detail.get("allocated"),
            "available": detail.get("available", event.get("value")),
            "unit": str(event.get("unit") or ""),
        }
        _save_floor(conn, key, "stock", data, ts, event_id)


def _rebuild_oee_projection(conn, event_id: str, ts: str) -> None:
    rows = conn.execute(
        """
        SELECT ts, machine_id, value FROM shop_events
        WHERE kind = 'oee'
        ORDER BY ts ASC, id ASC
        """
    ).fetchall()
    points = [
        {"ts": row["ts"], "machine_id": row["machine_id"], "oee_pct": row["value"]}
        for row in rows
    ]
    _save_floor(conn, _floor_key("oee", "trend"), "oee", {"points": points}, ts, event_id)


def log_shop_event(
    *,
    kind: str,
    machine_id: str = "",
    machine_name: str = "",
    component_id: str = "",
    value: float | None = None,
    unit: str = "",
    details: str = "",
    source: str = "manual",
) -> dict[str, Any]:
    event_kind = (kind or "").strip().lower()
    if event_kind not in {"downtime", "scrap", "oee", "stock", "vendor"}:
        return {"ok": False, "error": f"unknown shop event kind {kind!r}"}
    event_id = uuid.uuid4().hex
    ts = db.utc_now()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO shop_events (
              id, ts, kind, machine_id, machine_name, component_id,
              value, unit, details, source, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                ts,
                event_kind,
                machine_id or None,
                machine_name or None,
                component_id or None,
                value,
                unit or None,
                details or None,
                source or "manual",
                ts,
            ),
        )
        row = conn.execute("SELECT * FROM shop_events WHERE id = ?", (event_id,)).fetchone()
        _apply_shop_event(conn, dict(row))
    _enqueue_production(event_id, event_kind, machine_id, component_id, value, unit, details)
    return {"ok": True, "id": event_id, "kind": event_kind, "ts": ts, "source": source or "manual"}


def _enqueue_production(
    event_id: str,
    kind: str,
    machine_id: str,
    component_id: str,
    value: float | None,
    unit: str,
    details: str,
) -> None:
    text_bits = [f"Production {kind}"]
    if machine_id:
        text_bits.append(f"machine {machine_id}")
    if component_id:
        text_bits.append(f"component {component_id}")
    if value is not None:
        text_bits.append(f"value {value:g} {unit}".strip())
    if details:
        text_bits.append(details)
    text = " ".join(text_bits)
    try:
        from ..memory.ingest_queue import IngestPriority, IngestTask, try_enqueue

        try_enqueue(
            IngestTask(
                kind="production",
                payload={"text": text, "key": f"production:{event_id}"},
                priority=IngestPriority.NORMAL,
            )
        )
    except Exception:
        return


def log_downtime(
    machine_id: str,
    minutes: float,
    reason: str = "",
    machine_name: str = "",
) -> dict[str, Any]:
    mid = (machine_id or "").strip()
    if not mid:
        return {"ok": False, "error": "machine_id required"}
    return log_shop_event(
        kind="downtime",
        machine_id=mid,
        machine_name=machine_name,
        value=float(minutes),
        unit="min",
        details=(reason or "").strip(),
    )


def log_scrap(
    machine_id: str,
    qty: float,
    unit: str = "pcs",
    cause: str = "",
) -> dict[str, Any]:
    mid = (machine_id or "").strip()
    if not mid:
        return {"ok": False, "error": "machine_id required"}
    return log_shop_event(
        kind="scrap",
        machine_id=mid,
        value=float(qty),
        unit=unit or "pcs",
        details=(cause or "").strip(),
    )


def log_oee(machine_id: str, oee_pct: float) -> dict[str, Any]:
    mid = (machine_id or "").strip()
    if not mid:
        return {"ok": False, "error": "machine_id required"}
    return log_shop_event(kind="oee", machine_id=mid, value=float(oee_pct), unit="pct")


def log_stock(
    component_id: str,
    on_hand: float,
    allocated: float = 0,
    unit: str = "pcs",
) -> dict[str, Any]:
    cid = (component_id or "").strip()
    if not cid:
        return {"ok": False, "error": "component_id required"}
    available = float(on_hand) - float(allocated)
    return log_shop_event(
        kind="stock",
        component_id=cid,
        value=available,
        unit=unit or "pcs",
        details=json.dumps(
            {"on_hand": float(on_hand), "allocated": float(allocated), "available": available}
        ),
    )


def log_vendor_turnaround(
    vendor: str,
    days: float,
    last_delivery: str = "",
) -> dict[str, Any]:
    name = (vendor or "").strip()
    if not name:
        return {"ok": False, "error": "vendor required"}
    return log_shop_event(
        kind="vendor",
        value=float(days),
        unit="days",
        details=json.dumps({"vendor": name, "last_delivery": (last_delivery or "").strip()}),
    )


def _write_oee_trend_from_events(conn, events: list[dict[str, Any]]) -> None:
    """Write floor:oee:trend once from an already-loaded event list."""
    oee_events = [event for event in events if str(event.get("kind") or "") == "oee"]
    if not oee_events:
        return
    last = oee_events[-1]
    points = [
        {
            "ts": event.get("ts"),
            "machine_id": event.get("machine_id"),
            "oee_pct": event.get("value"),
        }
        for event in oee_events
    ]
    _save_floor(
        conn,
        _floor_key("oee", "trend"),
        "oee",
        {"points": points},
        str(last.get("ts") or last.get("created_at") or ""),
        str(last.get("id") or ""),
    )


def rebuild_shop_floor() -> int:
    """Rebuild floor:* shop_state rows from shop_events. Leaves production_log projections alone.

    Machine rows are applied from the in-memory event list. The oee/trend
    projection is written once after that loop, so it only contains events
    already applied.
    """
    written = 0
    with db.connect() as conn:
        conn.execute("DELETE FROM shop_state WHERE key LIKE ?", (f"{_FLOOR_PREFIX}%",))
        rows = conn.execute(
            "SELECT * FROM shop_events ORDER BY ts ASC, id ASC"
        ).fetchall()
        events = [dict(row) for row in rows]
        for event in events:
            _apply_shop_event(conn, event, project_oee=False)
            written += 1
        _write_oee_trend_from_events(conn, events)
    return written


def _stamp(payload: dict[str, Any], kind: str) -> dict[str, Any]:
    from ..knowledge.cards import is_stale

    updated = str(payload.get("updated_at") or "")
    body = dict(payload)
    body["stale"] = is_stale({"updated_at": updated}, _FRESHNESS_KIND.get(kind, kind))
    return body


def get_machine_status(machine_id: str) -> dict[str, Any]:
    mid = (machine_id or "").strip()
    if not mid:
        return _ask("Which machine should I look up?")
    with db.connect() as conn:
        row = conn.execute(
            "SELECT payload, as_of, derived_from FROM shop_state WHERE key = ?",
            (_floor_key("machine", mid),),
        ).fetchone()
    if row is None:
        return _ask("I have no shop-floor events for that machine yet.")
    payload = _stamp(json.loads(row["payload"]), "machine")
    return {
        "ok": True,
        "kind": "machine",
        "machine_id": mid,
        "as_of": row["as_of"],
        "derived_from": row["derived_from"],
        **payload,
    }


def get_vendor_turnaround(vendor: str) -> dict[str, Any]:
    name = (vendor or "").strip()
    if not name:
        return _ask("Which vendor should I look up?")
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT value, details, ts FROM shop_events WHERE kind = 'vendor' ORDER BY ts ASC"
        ).fetchall()
    matched: list[Any] = []
    for row in rows:
        try:
            detail = json.loads(str(row["details"] or "{}"))
        except json.JSONDecodeError:
            detail = {}
        if str(detail.get("vendor") or "").strip().lower() == name.lower():
            matched.append((row, detail))
    if not matched:
        return _ask("I have no turnaround events for that vendor yet.")
    days = [float(row["value"]) for row, _detail in matched if row["value"] is not None]
    latest_row, latest_detail = matched[-1]
    avg = sum(days) / len(days) if days else None
    payload = _stamp(
        {
            "vendor": name,
            "avg_days": avg,
            "last_days": latest_row["value"],
            "last_delivery": latest_detail.get("last_delivery") or "",
            "updated_at": latest_row["ts"],
            "samples": len(days),
        },
        "vendor",
    )
    return {"ok": True, "kind": "vendor", **payload}


def get_component_stock(component_id: str) -> dict[str, Any]:
    cid = (component_id or "").strip()
    if not cid:
        return _ask("Which component should I look up?")
    with db.connect() as conn:
        row = conn.execute(
            "SELECT payload, as_of FROM shop_state WHERE key = ?",
            (_floor_key("stock", cid),),
        ).fetchone()
    if row is None:
        return _ask("I have no stock events for that component yet.")
    payload = _stamp(json.loads(row["payload"]), "stock")
    return {"ok": True, "kind": "stock", "as_of": row["as_of"], **payload}


def get_oee_trend(days: int = 30) -> dict[str, Any]:
    window = max(1, int(days or 30))
    cutoff = (datetime.now(timezone.utc) - timedelta(days=window)).isoformat()
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT ts, machine_id, value FROM shop_events
            WHERE kind = 'oee' AND ts >= ?
            ORDER BY ts ASC
            """,
            (cutoff,),
        ).fetchall()
    points = [
        {"ts": row["ts"], "machine_id": row["machine_id"], "oee_pct": row["value"]}
        for row in rows
    ]
    updated = points[-1]["ts"] if points else ""
    payload = _stamp({"points": points, "updated_at": updated, "days": window}, "oee")
    if not points:
        return _ask("I have no OEE events in that window yet.")
    return {"ok": True, "kind": "oee", **payload}


def shop_floor_snapshot() -> dict[str, Any]:
    machines: list[dict[str, Any]] = []
    vendors: list[dict[str, Any]] = []
    stock: list[dict[str, Any]] = []
    oee: dict[str, Any] = {"points": [], "stale": True, "updated_at": ""}
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT key, payload, as_of FROM shop_state
            WHERE key LIKE ?
            ORDER BY key ASC
            """,
            (f"{_FLOOR_PREFIX}%",),
        ).fetchall()
    for row in rows:
        try:
            payload = json.loads(row["payload"])
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        kind = str(payload.get("kind") or "")
        stamped = _stamp(payload, kind)
        stamped["as_of"] = row["as_of"]
        if kind == "machine":
            machines.append(stamped)
        elif kind == "vendor":
            vendors.append(stamped)
        elif kind == "stock":
            stock.append(stamped)
        elif kind == "oee":
            oee = stamped
    return {
        "ok": True,
        "machines": machines,
        "vendors": vendors,
        "stock": stock,
        "oee": oee,
    }
