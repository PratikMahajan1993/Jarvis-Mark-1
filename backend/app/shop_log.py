"""Bound Google Sheets shop log. Reads are free; production writes wait on Shall I."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from . import db
from .connectors import google_auth
from .connectors import sheets
from .shop_excel import find_column

log = logging.getLogger(__name__)

DEFAULT_TAB = sheets.DEFAULT_TAB
_CACHE_OK_S = 45.0
_CACHE_ERR_S = 15.0
_cache: dict[str, Any] = {"at": 0.0, "ttl": 0.0, "snap": None}

_A1_TO = re.compile(
    r"\b(?:set|put|write|update)\s+(?:cell\s+)?([A-Za-z]+\d+)\s+(?:to|=)\s+(.+)$",
    re.I,
)
_IN_A1 = re.compile(
    r"\b(?:set|put|write|update)\s+(.+?)\s+(?:in|into|at)\s+(?:cell\s+)?([A-Za-z]+\d+)\b",
    re.I,
)
_MACHINE_OEE = re.compile(
    r"\b(?:set|put|write|update)\s+(.+?)\s+(?:oee|efficiency)\s+(?:to|=)\s+([0-9.]+%?)\b",
    re.I,
)
_NAMED = re.compile(
    r"""(?:named|called|titled)\s+["']?([^"'.,;]+)["']?"""
    r"""|["']([^"']+)["']""",
    re.I,
)


def reset_cache() -> None:
    _cache["at"] = 0.0
    _cache["ttl"] = 0.0
    _cache["snap"] = None


def binding() -> dict[str, str]:
    prefs = db.get_preferences()
    return {
        "spreadsheet_id": str(prefs.get("shop_spreadsheet_id") or "").strip(),
        "title": str(prefs.get("shop_spreadsheet_title") or "").strip(),
        "url": str(prefs.get("shop_spreadsheet_url") or "").strip(),
        "sheet_name": str(prefs.get("shop_sheet_name") or DEFAULT_TAB).strip() or DEFAULT_TAB,
    }


def save_binding(
    spreadsheet_id: str,
    title: str = "",
    url: str = "",
    sheet_name: str = "",
) -> dict[str, str]:
    sid = (spreadsheet_id or "").strip()
    tab = (sheet_name or "").strip() or DEFAULT_TAB
    link = (url or "").strip() or (sheets.spreadsheet_url(sid) if sid else "")
    db.update_preferences(
        {
            "shop_spreadsheet_id": sid,
            "shop_spreadsheet_title": (title or "").strip(),
            "shop_spreadsheet_url": link,
            "shop_sheet_name": tab,
        }
    )
    reset_cache()
    return binding()


def sheets_ready_speak() -> str:
    if not google_auth.connected():
        return "Google is not connected."
    if not google_auth.has_sheets():
        return "Reconnect Google in preferences (Add Sheets) so I can use the shop log."
    return ""


def _scene(title: str, speak: str, widgets: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "title": title,
        "subtitle": binding().get("title") or None,
        "widgets": widgets or [{"type": "quote", "text": speak, "cite": "Jarvis"}],
    }


def _empty_snap(reason: str) -> dict[str, Any]:
    bound = binding()
    return {
        "oee_percent": None,
        "reason": reason,
        "bottlenecks": [],
        "column": None,
        "sample_size": 0,
        "spreadsheet_id": bound.get("spreadsheet_id") or "",
        "url": bound.get("url") or "",
        "sheet": bound.get("sheet_name") or DEFAULT_TAB,
    }


def efficiency_snapshot(force: bool = False) -> dict[str, Any]:
    """Live OEE from the bound Sheet, or a missing-number payload. Never invents OEE."""
    now = time.monotonic()
    if not force and _cache["snap"] is not None and now - float(_cache["at"] or 0) < float(_cache["ttl"] or 0):
        return dict(_cache["snap"])
    blocked = sheets_ready_speak()
    if blocked:
        snap = _empty_snap("sheets not connected")
        _store_cache(snap, _CACHE_ERR_S)
        return snap
    bound = binding()
    spreadsheet_id = bound.get("spreadsheet_id") or ""
    if not spreadsheet_id:
        snap = _empty_snap("no shop sheet bound")
        _store_cache(snap, _CACHE_OK_S)
        return snap
    try:
        snap = sheets.efficiency_snapshot(spreadsheet_id, bound.get("sheet_name") or DEFAULT_TAB)
    except sheets.SheetNotFoundError as exc:
        snap = _empty_snap(str(exc))
        _store_cache(snap, _CACHE_ERR_S)
        return snap
    except Exception:
        snap = _empty_snap("shop sheet unavailable")
        _store_cache(snap, _CACHE_ERR_S)
        return snap
    _store_cache(snap, _CACHE_OK_S)
    return dict(snap)


def _store_cache(snap: dict[str, Any], ttl: float) -> None:
    _cache["snap"] = dict(snap)
    _cache["at"] = time.monotonic()
    _cache["ttl"] = ttl


def glance_efficiency_critical() -> dict[str, Any] | None:
    snap = efficiency_snapshot()
    oee = snap.get("oee_percent")
    if not isinstance(oee, (int, float)):
        return None
    bottlenecks = snap.get("bottlenecks") or []
    if oee >= 90 and not bottlenecks:
        return None
    labels = [str(item.get("label") or "").strip() for item in bottlenecks if item.get("label")]
    detail = ", ".join(labels[:3]) if labels else "Below 90 percent."
    tone = "red" if oee < 80 else "amber"
    return {
        "kind": "efficiency",
        "title": f"OEE {oee:.0f}%",
        "detail": detail[:220],
        "tone": tone,
        "sourceId": "shop-oee",
        "href": snap.get("url") or None,
    }


def _coerce_value(raw: str) -> Any:
    text = (raw or "").strip().strip(".,")
    if text.endswith("%"):
        text = text[:-1].strip()
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r"-?\d+\.\d+", text):
        return float(text)
    return text


def parse_updates(message: str, payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    text = (message or "").strip()
    match = _A1_TO.search(text)
    if match:
        return [{"cell": match.group(1).upper(), "value": _coerce_value(match.group(2))}]
    match = _IN_A1.search(text)
    if match:
        return [{"cell": match.group(2).upper(), "value": _coerce_value(match.group(1))}]
    match = _MACHINE_OEE.search(text)
    if match and payload:
        machine = match.group(1).strip().strip("\"'")
        value = _coerce_value(match.group(2))
        headers = payload.get("headers") or []
        label_header = find_column(headers, ("machine", "machine name", "name", "line", "station"))
        oee_header = find_column(headers, ("oee", "efficiency", "oee %"))
        header_index = {name: idx for idx, name in enumerate(headers) if name}
        if not label_header or not oee_header or oee_header not in header_index:
            return []
        needle = machine.lower()
        excel_row = 1
        for values in (payload.get("raw") or [])[1:]:
            excel_row += 1
            record = {headers[i]: values[i] if i < len(values) else None for i in range(len(headers))}
            label = str(record.get(label_header) or "").strip()
            if label.lower() == needle or needle in label.lower():
                return [{"row": excel_row, "col": header_index[oee_header] + 1, "value": value}]
    return []


def _bind_target(query: str) -> tuple[str, str]:
    blob = (query or "").strip()
    spreadsheet_id = sheets.spreadsheet_id_from(blob)
    if spreadsheet_id:
        return spreadsheet_id, ""
    named = _NAMED.search(blob)
    if named:
        return "", (named.group(1) or named.group(2) or "").strip()
    cleaned = re.sub(
        r"\b(?:bind|use|connect|link|open)\b|\b(?:the\s+)?(?:google\s+)?(?:shop\s+)?(?:log|sheet|spreadsheet|workbook)\b",
        " ",
        blob,
        flags=re.I,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,-")
    return "", cleaned


def bind(query: str, sheet_name: str = "", session_id: str = "default") -> dict[str, Any]:
    del session_id
    blocked = sheets_ready_speak()
    if blocked:
        return {"speak": blocked, "scene": _scene("Shop log", blocked), "data": {"bound": False}}
    spreadsheet_id, name = _bind_target(query)
    tab = (sheet_name or "").strip()
    if spreadsheet_id:
        try:
            title = sheets.get_title(spreadsheet_id)
            names = sheets.list_sheets(spreadsheet_id)
        except Exception as exc:
            info = sheets.google_error(exc, "I could not open that spreadsheet. Check the URL.")
            return {"speak": info["speak"], "scene": _scene("Shop log", info["speak"]), "data": {"bound": False, "error": str(exc)[:300]}}
        if tab and tab not in names:
            speak = f"Sheet {tab!r} is not in that workbook."
            return {"speak": speak, "scene": _scene("Shop log", speak), "data": {"bound": False, "tabs": names}}
        saved = save_binding(spreadsheet_id, title=title, sheet_name=tab or DEFAULT_TAB)
        speak = f"Using {saved['title'] or 'the shop log'}."
        return {
            "speak": speak,
            "scene": _scene("Shop log", speak, [{"type": "kpi", "label": "Sheet", "value": saved["title"] or saved["spreadsheet_id"]}]),
            "data": {**saved, "bound": True, "tabs": names},
        }
    if not name:
        speak = "Paste the Google Sheets URL, or say the workbook name."
        return {"speak": speak, "scene": _scene("Shop log", speak), "data": {"bound": False}}
    try:
        matches = sheets.find_by_name(name)
    except Exception:
        matches = []
    if not matches:
        speak = "I cannot see that workbook. Paste the Google Sheets URL."
        return {"speak": speak, "scene": _scene("Shop log", speak), "data": {"bound": False, "query": name}}
    if len(matches) > 1:
        speak = "Two sheets could match. Paste the URL."
        rows = [[row.get("title") or "", row.get("url") or ""] for row in matches[:5]]
        return {
            "speak": speak,
            "scene": _scene(
                "Shop log",
                speak,
                [{"type": "table", "title": "Matches", "columns": ["Name", "URL"], "rows": rows}],
            ),
            "data": {"bound": False, "matches": matches},
        }
    hit = matches[0]
    try:
        names = sheets.list_sheets(hit["spreadsheet_id"])
    except Exception:
        names = []
    saved = save_binding(
        hit["spreadsheet_id"],
        title=str(hit.get("title") or name),
        url=str(hit.get("url") or ""),
        sheet_name=tab or DEFAULT_TAB,
    )
    speak = f"Using {saved['title'] or name}."
    return {
        "speak": speak,
        "scene": _scene("Shop log", speak),
        "data": {**saved, "bound": True, "tabs": names},
    }


def ensure(title: str = "", session_id: str = "default") -> dict[str, Any]:
    del session_id
    blocked = sheets_ready_speak()
    if blocked:
        return {"speak": blocked, "scene": _scene("Shop log", blocked), "data": {"bound": False}}
    bound = binding()
    if bound.get("spreadsheet_id"):
        speak = f"Shop log is already {bound.get('title') or 'bound'}."
        return {"speak": speak, "scene": _scene("Shop log", speak), "data": {**bound, "bound": True, "created": False}}
    try:
        created = sheets.create_shop_spreadsheet(title or sheets.DEFAULT_TITLE)
    except Exception as exc:
        log.exception("shop log create failed")
        info = sheets.google_error(exc, "Google Sheets did not create the shop log.")
        speak = info["speak"]
        widgets = [{"type": "quote", "text": speak, "cite": "Jarvis"}]
        if info.get("url"):
            widgets.append({"type": "markdown", "title": "Enable Sheets API", "text": info["url"]})
        return {
            "speak": speak,
            "scene": {"title": "Shop log", "subtitle": None, "widgets": widgets},
            "data": {"bound": False, "error": str(exc)[:300]},
        }
    saved = save_binding(
        created["spreadsheet_id"],
        title=str(created.get("title") or sheets.DEFAULT_TITLE),
        url=str(created.get("url") or ""),
        sheet_name=str(created.get("sheet_name") or DEFAULT_TAB),
    )
    speak = f"Created {saved['title'] or 'Jarvis shop log'}. No OEE numbers yet — I will not invent them."
    return {
        "speak": speak,
        "scene": _scene(
            "Shop log",
            speak,
            [
                {"type": "kpi", "label": "Workbook", "value": saved["title"] or "Jarvis shop log"},
                {"type": "markdown", "text": saved.get("url") or ""},
            ],
        ),
        "data": {**saved, "bound": True, "created": True},
    }


def _oee_widgets(snap: dict[str, Any], payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    widgets: list[dict[str, Any]] = []
    oee = snap.get("oee_percent")
    if isinstance(oee, (int, float)):
        widgets.append({"type": "kpi", "label": "OEE", "value": f"{oee:.0f}%", "hint": snap.get("column") or ""})
    else:
        widgets.append(
            {
                "type": "quote",
                "text": "No OEE number on the sheet yet. I will not invent one.",
                "cite": "Jarvis",
            }
        )
    bottlenecks = snap.get("bottlenecks") or []
    if bottlenecks:
        widgets.append(
            {
                "type": "table",
                "title": "Below 90%",
                "columns": ["Machine", "OEE"],
                "rows": [[item.get("label") or "", f"{float(item.get('oee_percent') or 0):.0f}%"] for item in bottlenecks[:8]],
            }
        )
    rows = (payload or {}).get("rows") or []
    headers = [name for name in ((payload or {}).get("headers") or []) if name]
    if rows and headers:
        widgets.append(
            {
                "type": "table",
                "title": (payload or {}).get("sheet") or "Production",
                "columns": headers[:6],
                "rows": [[row.get(col) if row.get(col) is not None else "" for col in headers[:6]] for row in rows[:12]],
            }
        )
    return widgets


def read_sheet(sheet_name: str = "", session_id: str = "default") -> dict[str, Any]:
    del session_id
    blocked = sheets_ready_speak()
    if blocked:
        return {"speak": blocked, "scene": _scene("Shop log", blocked), "data": {"ok": False}}
    bound = binding()
    if not bound.get("spreadsheet_id"):
        speak = "No shop sheet yet. Say create a shop log, or paste a Google Sheets URL."
        return {"speak": speak, "scene": _scene("Shop log", speak), "data": {"ok": False}}
    tab = (sheet_name or bound.get("sheet_name") or DEFAULT_TAB).strip()
    try:
        payload = sheets.read_sheet(bound["spreadsheet_id"], tab)
        snap = sheets.efficiency_snapshot(bound["spreadsheet_id"], tab)
    except sheets.SheetNotFoundError as exc:
        speak = str(exc)
        return {"speak": speak, "scene": _scene("Shop log", speak), "data": {"ok": False}}
    except Exception as exc:
        info = sheets.google_error(exc, "The shop sheet did not load.")
        return {"speak": info["speak"], "scene": _scene("Shop log", info["speak"]), "data": {"ok": False, "error": str(exc)[:300]}}
    reset_cache()
    _store_cache(snap, _CACHE_OK_S)
    oee = snap.get("oee_percent")
    if isinstance(oee, (int, float)):
        speak = f"Shop OEE is {oee:.0f} percent."
        necks = snap.get("bottlenecks") or []
        if necks:
            labels = [str(item.get("label") or "").strip() for item in necks[:3] if item.get("label")]
            if labels:
                speak += " Watch " + ", ".join(labels) + "."
    else:
        speak = "No OEE number on the sheet. I will not invent one."
    return {
        "speak": speak,
        "scene": {
            "title": "Shop log",
            "subtitle": bound.get("title") or tab,
            "widgets": _oee_widgets(snap, payload),
        },
        "data": {"ok": True, "payload": payload, "efficiency": snap, **bound},
    }


def queue_write(
    session_id: str,
    message: str = "",
    updates: list[dict[str, Any]] | None = None,
    sheet_name: str = "",
) -> dict[str, Any]:
    blocked = sheets_ready_speak()
    if blocked:
        return {"speak": blocked, "scene": _scene("Shop log", blocked), "data": {"queued": False}}
    bound = binding()
    if not bound.get("spreadsheet_id"):
        speak = "No shop sheet yet. Say create a shop log, or paste a Google Sheets URL."
        return {"speak": speak, "scene": _scene("Shop log", speak), "data": {"queued": False}}
    tab = (sheet_name or bound.get("sheet_name") or DEFAULT_TAB).strip()
    cells = list(updates or [])
    payload = None
    if not cells:
        try:
            payload = sheets.read_sheet(bound["spreadsheet_id"], tab)
        except Exception:
            payload = None
        cells = parse_updates(message, payload)
    if not cells:
        speak = "Say the cell, or the machine and the OEE number."
        return {"speak": speak, "scene": _scene("Shop log", speak), "data": {"queued": False}}
    summary = ", ".join(
        str(item.get("cell") or f"r{item.get('row')}c{item.get('col')}") + f"={item.get('value')}"
        for item in cells
    )
    from .hermes.hitl import request_human_approval

    pending = request_human_approval(
        session_id=session_id,
        kind="sheets_write",
        title="Overwrite production numbers?",
        summary=summary[:180],
        payload={
            "spreadsheet_id": bound["spreadsheet_id"],
            "sheet_name": tab,
            "updates": cells,
            "url": bound.get("url") or "",
            "title": bound.get("title") or "",
        },
        action_id=f"sheet-{db.utc_now()}",
        tool_name="update_shop_sheet",
    )
    speak = "This overwrites production numbers. Shall I write it?"
    return {
        "speak": speak,
        "scene": _scene("Shop write", speak, [{"type": "markdown", "title": "Changes", "text": summary}]),
        "pending": pending,
        "data": {"queued": True, "updates": cells},
    }


def apply_write(payload: dict[str, Any]) -> dict[str, Any]:
    spreadsheet_id = str(payload.get("spreadsheet_id") or "").strip()
    sheet_name = str(payload.get("sheet_name") or DEFAULT_TAB).strip() or DEFAULT_TAB
    updates = payload.get("updates") or []
    if not spreadsheet_id:
        raise RuntimeError("No shop spreadsheet bound.")
    result = sheets.update_cells(spreadsheet_id, sheet_name, list(updates))
    reset_cache()
    return result
