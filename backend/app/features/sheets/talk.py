"""Hermes workbook-model tools. Google is called only by apply, and only for a new file."""

from __future__ import annotations

import hmac
import json
import re
from typing import Any

from app.config import settings
from app.connectors.sheets_toolkit.client import SheetsToolkitError, batch_update, spreadsheet_url
from app.connectors.sheets_toolkit.workbook import create_workbook, get_workbook, trash_workbook
from app.features.sheets.compile import CompileError, compile_model
from app.features.sheets.draft import (
    ModelError,
    cloned_model,
    edit_model,
    empty_model,
    fingerprint,
    get_model,
    list_templates,
    missing_piece,
    next_question,
    outline,
    put_model,
    save_template,
)

_REFUSAL = "Sheet create refused: Telegram user is not an owner (or TELEGRAM_OWNER_USER_IDS is empty)."
_PASSWORD = re.compile(r"^[A-Za-z0-9]+$")


def owner_may_create(telegram_user_id: str = "", actor: str = "") -> tuple[bool, str]:
    """Desk owner may create. Staff, and a Telegram id outside TELEGRAM_OWNER_USER_IDS, may not."""
    who = str(actor or "").strip().casefold()
    if who == "staff":
        return False, "Sheet create refused: only the owner may create a sheet."
    caller = str(telegram_user_id or "").strip()
    if not caller:
        return True, ""
    owners = [part.strip() for part in (settings.telegram_owner_user_ids or "").split(",") if part.strip()]
    if not owners or caller not in owners:
        return False, _REFUSAL
    return True, ""


def desk_password_ok(password: str) -> tuple[bool, str]:
    """Desk creates require SHEET_BUILD_PASSWORD. The password is never returned."""
    configured = str(settings.sheet_build_password or "").strip()
    if not configured or not _PASSWORD.fullmatch(configured):
        return False, "The sheet password is not configured."
    given = str(password or "").strip()
    if not given:
        return False, "Ask for the sheet password. It is alphanumeric."
    if not _PASSWORD.fullmatch(given):
        return False, "The sheet password must be alphanumeric."
    if not hmac.compare_digest(given, configured):
        return False, "That sheet password was refused."
    return True, ""


def _reply(model: dict[str, Any], *, note: str = "", updated_at: str | None = None, **extra: Any) -> dict[str, Any]:
    missing = missing_piece(model)
    question = next_question(missing)
    speak = f"{note} {question}".strip() if note else question
    out: dict[str, Any] = {
        "ok": True,
        "model": model,
        "outline": outline(model),
        "missing": missing,
        "speak": speak,
    }
    if updated_at is not None:
        out["updated_at"] = updated_at
    out.update(extra)
    return out


def _fail(model: dict[str, Any], message: str, **extra: Any) -> dict[str, Any]:
    out = {
        "ok": False,
        "error": message,
        "model": model,
        "outline": outline(model),
        "missing": missing_piece(model),
        "speak": message,
    }
    out.update(extra)
    return out


def _json_object(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text or text[0] not in "[{":
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ModelError("that was not valid JSON") from exc


def _fields_from(payload: Any, fields: dict[str, Any]) -> dict[str, Any]:
    merged = dict(fields)
    if isinstance(payload, str) and payload.strip():
        parsed = json.loads(payload)
        if not isinstance(parsed, dict):
            raise ModelError("payload must be a JSON object")
        merged = {**parsed, **merged}
    elif isinstance(payload, dict):
        merged = {**payload, **merged}
    for key in ("column", "columns", "rows", "values", "dropdown", "block"):
        if key in merged:
            merged[key] = _json_object(merged[key])
    return merged


def _session(session_id: str) -> str:
    return str(session_id or "default").strip() or "default"


def _open_has_work(model: dict[str, Any]) -> bool:
    return bool(str(model.get("title") or "").strip() or model.get("tabs") or model.get("created"))


def _load(session_id: str) -> dict[str, Any]:
    state = get_model(session_id)
    if state.get("error"):
        return {"error": state["error"], "model": empty_model(), "updated_at": state.get("updated_at")}
    return state


def tool_read(session_id: str = "", **_: Any) -> dict[str, Any]:
    state = _load(_session(session_id))
    if state.get("error"):
        return _fail(state["model"], state["error"])
    return _reply(state["model"], updated_at=state.get("updated_at"))


def tool_edit(session_id: str = "", action: str = "", payload: Any = None, **fields: Any) -> dict[str, Any]:
    session = _session(session_id)
    state = _load(session)
    if state.get("error"):
        return _fail(state["model"], state["error"])
    current = state["model"]
    try:
        parsed = _fields_from(payload, fields)
        updated, note, changed = edit_model(current, action, **parsed)
    except ModelError as exc:
        return _fail(current, str(exc))
    except json.JSONDecodeError:
        return _fail(current, "payload must be a JSON object")
    if not changed:
        return _fail(current, note, unchanged=True)
    saved = put_model(updated, session)
    return _reply(saved["model"], note=note, updated_at=saved.get("updated_at"))


def tool_list(session_id: str = "", **_: Any) -> dict[str, Any]:
    del session_id
    templates = list_templates()
    if not templates:
        speak = "No sheet templates yet."
    else:
        speak = "Saved templates: " + ", ".join(item["title"] or item["id"] for item in templates) + "."
    return {"ok": True, "templates": templates, "speak": speak}


def tool_clone(
    session_id: str = "",
    template_id: str = "",
    title: str = "",
    discard: Any = False,
    **_: Any,
) -> dict[str, Any]:
    session = _session(session_id)
    state = _load(session)
    if state.get("error"):
        return _fail(state["model"], state["error"])
    current = state["model"]
    replace = discard is True or str(discard).strip().lower() in ("1", "true", "yes")
    if _open_has_work(current) and not replace:
        return _fail(current, "The open model already has work. Pass discard to replace it.")
    try:
        model = cloned_model(template_id, title)
        saved = put_model(model, session)
    except ModelError as exc:
        return _fail(current, str(exc))
    return _reply(
        saved["model"],
        note=f"Opened {saved['model']['title']} from template {template_id}.",
        updated_at=saved.get("updated_at"),
    )


def _first_sheet_id(meta: dict[str, Any]) -> int:
    sheets = meta.get("sheets") or []
    if not sheets:
        raise CompileError("Google did not return a sheet id.")
    sheet_id = (sheets[0].get("properties") or {}).get("sheetId")
    if isinstance(sheet_id, bool) or not isinstance(sheet_id, int) or sheet_id < 0:
        raise CompileError("Google did not return a sheet id.")
    return sheet_id


def tool_apply(
    session_id: str = "",
    telegram_user_id: str = "",
    actor: str = "",
    password: str = "",
    account: str | None = None,
    **_: Any,
) -> dict[str, Any]:
    """Create a new spreadsheet and write it in one batch. Staff may not create."""
    session = _session(session_id)
    state = _load(session)
    if state.get("error"):
        return _fail(empty_model(), state["error"])
    model = state["model"]
    allowed, reason = owner_may_create(telegram_user_id, actor)
    if not allowed:
        return _fail(model, reason, need="owner")
    missing = missing_piece(model)
    if missing:
        return {
            "ok": False,
            "error": f"missing {missing}",
            "missing": missing,
            "model": model,
            "outline": outline(model),
            "speak": next_question(missing),
        }
    if not str(telegram_user_id or "").strip():
        ok_password, password_reason = desk_password_ok(password)
        if not ok_password:
            return _fail(model, password_reason, need="password")
    stamp = fingerprint(model)
    created = model.get("created") or {}
    if created.get("fingerprint") == stamp and created.get("url") and created.get("spreadsheet_id"):
        return {
            "ok": True,
            "model": model,
            "outline": outline(model),
            "missing": None,
            "spreadsheet_id": created["spreadsheet_id"],
            "url": created["url"],
            "template_id": created.get("template_id") or "",
            "already_created": True,
            "speak": f"Already created {model['title']}. {created['url']}",
        }
    try:
        compile_model(model, 0)
    except CompileError as exc:
        return _fail(model, str(exc))
    try:
        made = create_workbook(model["title"], account=account)
    except SheetsToolkitError as exc:
        return _fail(model, str(exc))
    spreadsheet_id = str((made or {}).get("spreadsheetId") or "").strip()
    if not spreadsheet_id:
        return _fail(model, "Google did not return a new file.")
    url = str((made or {}).get("spreadsheetUrl") or "").strip() or spreadsheet_url(spreadsheet_id)
    try:
        meta = get_workbook(spreadsheet_id, account=account)
        requests = compile_model(model, _first_sheet_id(meta))
        batch_update(spreadsheet_id, requests, account)
    except Exception:
        trashed = False
        try:
            trash_workbook(spreadsheet_id, account=account)
            trashed = True
        except Exception:
            trashed = False
        if trashed:
            return _fail(model, "The sheet was not written. The empty file was moved to trash.")
        return _fail(model, f"The sheet was not written. The empty file is still at {url}.")
    template = save_template(model)
    model = dict(model)
    model["created"] = {
        "spreadsheet_id": spreadsheet_id,
        "url": url,
        "template_id": template["id"],
        "fingerprint": stamp,
    }
    put_model(model, session)
    return {
        "ok": True,
        "model": model,
        "outline": outline(model),
        "missing": None,
        "spreadsheet_id": spreadsheet_id,
        "url": url,
        "template_id": template["id"],
        "speak": f"Created {model['title']}. {url}",
    }
