"""Office-day suggested tasks + weather (foundation Phase 3)."""

from __future__ import annotations

import json
from typing import Any

import httpx

from . import db
from .config import settings
from .memory.ingest import ingest_drawing_summary, ingest_text


def _ensure_tasks_table() -> None:
    with db.connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS suggested_tasks (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                detail TEXT NOT NULL,
                actions TEXT NOT NULL,
                status TEXT NOT NULL,
                source_id TEXT,
                meta TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def fetch_weather(city: str = "Pune") -> dict[str, Any]:
    """Open-Meteo (no API key). Defaults to Pune coords. Fast fail for HUD."""
    # Pune approx; city label only for speak
    lat, lon = 18.5204, 73.8567
    try:
        with httpx.Client(timeout=3.0) as client:
            r = client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,weather_code,wind_speed_10m",
                    "timezone": settings.tz or "Asia/Kolkata",
                },
            )
            data = r.json() if r.status_code < 400 else {}
        cur = data.get("current") or {}
        temp = cur.get("temperature_2m")
        code = cur.get("weather_code")
        wind = cur.get("wind_speed_10m")
        label = _weather_label(code)
        speak = f"{city}: {temp}°C, {label}" if temp is not None else f"{city} weather unavailable"
        return {
            "ok": True,
            "city": city,
            "temperature_c": temp,
            "weather_code": code,
            "label": label,
            "wind_kmh": wind,
            "speak": speak,
        }
    except Exception as exc:
        return {"ok": False, "city": city, "speak": f"{city} weather unavailable", "error": str(exc)}


def _weather_label(code: Any) -> str:
    try:
        c = int(code)
    except (TypeError, ValueError):
        return "mixed skies"
    if c == 0:
        return "clear"
    if c in (1, 2, 3):
        return "partly cloudy"
    if c in (45, 48):
        return "foggy"
    if c in (51, 53, 55, 61, 63, 65, 80, 81, 82):
        return "rain"
    if c in (71, 73, 75, 85, 86):
        return "snow"
    if c in (95, 96, 99):
        return "storms"
    return "mixed skies"


def upsert_task(
    *,
    task_id: str,
    kind: str,
    title: str,
    detail: str,
    actions: list[dict[str, str]],
    source_id: str = "",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _ensure_tasks_table()
    now = db.utc_now()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO suggested_tasks
            (id, kind, title, detail, actions, status, source_id, meta, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                detail = excluded.detail,
                actions = excluded.actions,
                meta = excluded.meta,
                updated_at = excluded.updated_at,
                status = CASE WHEN suggested_tasks.status = 'dismissed' THEN suggested_tasks.status ELSE 'open' END
            """,
            (
                task_id,
                kind,
                title,
                detail,
                json.dumps(actions),
                source_id,
                json.dumps(meta or {}),
                now,
                now,
            ),
        )
    return get_task(task_id) or {}


def get_task(task_id: str) -> dict[str, Any] | None:
    _ensure_tasks_table()
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM suggested_tasks WHERE id = ?", (task_id,)).fetchone()
    if not row:
        return None
    return _row(row)


def list_tasks(*, include_dismissed: bool = False) -> list[dict[str, Any]]:
    _ensure_tasks_table()
    with db.connect() as conn:
        if include_dismissed:
            rows = conn.execute(
                "SELECT * FROM suggested_tasks ORDER BY updated_at DESC LIMIT 40"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM suggested_tasks WHERE status = 'open' ORDER BY updated_at DESC LIMIT 20"
            ).fetchall()
    return [_row(r) for r in rows]


def set_task_status(task_id: str, status: str) -> dict[str, Any] | None:
    _ensure_tasks_table()
    with db.connect() as conn:
        conn.execute(
            "UPDATE suggested_tasks SET status = ?, updated_at = ? WHERE id = ?",
            (status, db.utc_now(), task_id),
        )
    return get_task(task_id)


def _row(row: Any) -> dict[str, Any]:
    data = dict(row)
    try:
        data["actions"] = json.loads(data.get("actions") or "[]")
    except json.JSONDecodeError:
        data["actions"] = []
    try:
        data["meta"] = json.loads(data.get("meta") or "{}")
    except json.JSONDecodeError:
        data["meta"] = {}
    return data


def refresh_suggested_tasks(session_id: str = "default") -> dict[str, Any]:
    """Build office-day cards from RFQ intake + shop OEE stub. Never raises to callers."""
    try:
        return _refresh_suggested_tasks_inner(session_id)
    except Exception as exc:
        try:
            weather = fetch_weather()
        except Exception:
            weather = {"speak": "", "ok": False}
        return {
            "ok": False,
            "error": str(exc)[:300],
            "tasks": list_tasks(),
            "weather": weather,
            "refreshed": 0,
        }


def _refresh_suggested_tasks_inner(session_id: str = "default") -> dict[str, Any]:
    """Build office-day cards from RFQ intake + shop OEE stub."""
    from .rfq import detect_inbound_drawings, to_public
    from . import jobs

    try:
        detect_inbound_drawings()
    except Exception:
        pass
    created = 0
    for row in jobs.list_rfqs():
        if row.get("status") not in ("intake", "pending", "reasoned"):
            continue
        public = to_public(row)
        mail_id = str(row.get("mail_id") or "")
        title = public.get("catch") or public.get("title") or "Inbound drawing RFQ"
        if not title or title == "Drawing RFQ":
            title = "Drawing RFQ awaiting quote"
        # Enrich with mail subject when possible
        detail = public.get("catch") or "Drawings received — ready for engineering review."
        try:
            from .connectors import email as email_conn

            mail = email_conn.get_email(mail_id) if mail_id else None
            if mail:
                sender = mail.get("sender") or "Customer"
                subject = mail.get("subject") or "RFQ"
                title = f"{sender} mailed with drawings: {subject}"[:160]
                detail = (mail.get("body") or detail)[:400]
                # Do NOT auto-save attachments or Drive-upload on HUD refresh (HITL/privacy).
                # Engineering action / explicit save tools own that path.
                try:
                    ingest_text(
                        f"RFQ mail {title}\n{detail}",
                        namespace="jobs",
                        key=f"rfq-mail:{mail_id or public.get('id')}",
                        meta={"kind": "rfq", "mail_id": mail_id},
                    )
                except Exception:
                    pass
        except Exception:
            pass
        upsert_task(
            task_id=f"rfq-{public['id']}",
            kind="rfq",
            title=title,
            detail=detail,
            actions=[
                {"id": "engineering", "label": "Start engineering review & quote"},
                {"id": "calendar", "label": "Only create calendar deadline"},
                {"id": "todo", "label": "Mark read & add to to-do"},
            ],
            source_id=str(public.get("id") or ""),
            meta={"mail_id": mail_id, "rfq_id": public.get("id")},
        )
        created += 1

    # Production downtime stub from shop sheet when available
    prod_detail = "Night shift production summary is ready when shop log is bound."
    prod_title = "Review night-shift production"
    try:
        from .shop_log import read_sheet

        sheet = read_sheet(session_id=session_id)
        data = sheet.get("data") if isinstance(sheet, dict) else None
        if isinstance(data, dict) and data:
            prod_title = "Production overnight — review OEE / downtime"
            oee = data.get("oee") or data.get("OEE") or data.get("efficiency")
            bits: list[str] = []
            if isinstance(oee, dict):
                pct = oee.get("oee_percent") or oee.get("percent")
                if pct is not None:
                    try:
                        bits.append(f"Overall OEE ~{float(pct):.0f}%")
                    except (TypeError, ValueError):
                        bits.append(f"Overall OEE: {pct}")
                bottlenecks = oee.get("bottlenecks") or []
                if isinstance(bottlenecks, list) and bottlenecks:
                    names = []
                    for b in bottlenecks[:3]:
                        if isinstance(b, dict):
                            names.append(str(b.get("label") or b.get("name") or "machine"))
                        else:
                            names.append(str(b))
                    if names:
                        bits.append("Bottlenecks: " + ", ".join(names))
            elif oee is not None:
                bits.append(f"OEE/efficiency: {oee}")
            downtime = data.get("downtime") or data.get("bottleneck") or data.get("machines")
            if downtime is not None and not isinstance(downtime, (dict, list)):
                bits.append(f"Downtime: {downtime}")
            prod_detail = "; ".join(bits)[:400] if bits else "Shop log bound — open for details."
    except Exception:
        pass
    upsert_task(
        task_id="prod-overnight",
        kind="production",
        title=prod_title,
        detail=prod_detail,
        actions=[
            {"id": "review", "label": "Review production log"},
            {"id": "meeting", "label": "Create 4pm downtime meeting"},
            {"id": "weekly", "label": "Mark for weekly production review"},
            {"id": "chat", "label": "Open chat for custom tasks"},
        ],
        source_id="shop",
        meta={},
    )
    weather = fetch_weather()
    return {"ok": True, "tasks": list_tasks(), "weather": weather, "refreshed": created}
