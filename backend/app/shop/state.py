"""Materialised shop_state from production_logs — numbers only from log rows."""

from __future__ import annotations

import json
import re
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
