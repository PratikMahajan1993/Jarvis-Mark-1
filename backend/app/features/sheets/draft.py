"""One sheet draft. The picture on the desk is drawn from this. Google is not written."""

from __future__ import annotations

from typing import Any

from app.core.features import publish
from app.drafts import load_draft, save_draft

DRAFT_KEY = "sheets.current"
KINDS = ("text", "number", "date", "formula")
FILLED_BY = ("", "owner", "staff", "jarvis")
MAX_COLUMNS = 16
MAX_TITLE = 80
MAX_NAME = 48
MAX_FORMULA = 200


class DraftError(ValueError):
    """The draft shape was rejected."""


def empty_draft() -> dict[str, Any]:
    return {"workbook_title": "", "tab_title": "", "columns": []}


def _text(value: Any, limit: int, field: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise DraftError(f"{field} must be text")
    text = value.strip()
    if len(text) > limit:
        raise DraftError(f"{field} is too long")
    return text


def normalize_draft(raw: Any) -> dict[str, Any]:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise DraftError("draft must be an object")
    columns_raw = raw.get("columns") or []
    if not isinstance(columns_raw, list):
        raise DraftError("columns must be a list")
    if len(columns_raw) > MAX_COLUMNS:
        raise DraftError(f"at most {MAX_COLUMNS} columns")
    columns: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in columns_raw:
        if not isinstance(item, dict):
            raise DraftError("each column must be an object")
        name = _text(item.get("name"), MAX_NAME, "column name")
        if not name:
            raise DraftError("column name is required")
        key = name.casefold()
        if key in seen:
            raise DraftError(f"duplicate column {name}")
        seen.add(key)
        kind = str(item.get("kind") or "text").strip()
        if kind not in KINDS:
            raise DraftError("column kind must be text, number, date, or formula")
        filled = str(item.get("filled_by") or "").strip()
        if filled not in FILLED_BY:
            raise DraftError("filled_by must be owner, staff, jarvis, or empty")
        formula = _text(item.get("formula"), MAX_FORMULA, "formula")
        if kind != "formula":
            formula = ""
        columns.append({"name": name, "kind": kind, "filled_by": filled, "formula": formula})
    return {
        "workbook_title": _text(raw.get("workbook_title"), MAX_TITLE, "workbook"),
        "tab_title": _text(raw.get("tab_title"), MAX_TITLE, "tab"),
        "columns": columns,
    }


def get_draft() -> dict[str, Any]:
    loaded = load_draft(DRAFT_KEY)
    body = (loaded or {}).get("body") if loaded else None
    try:
        draft = normalize_draft(body)
    except DraftError:
        draft = empty_draft()
    return {"draft": draft, "updated_at": (loaded or {}).get("updated_at")}


def put_draft(raw: Any) -> dict[str, Any]:
    draft = normalize_draft(raw)
    saved = save_draft(DRAFT_KEY, draft)
    publish("sheets.changed", {"draft": draft})
    return {"draft": draft, "updated_at": saved["updated_at"]}
