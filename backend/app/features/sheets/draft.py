"""One open workbook model, stored as JSON in the drafts table. Google is not written."""

from __future__ import annotations

import copy
import json
import re
from typing import Any

from app.core.features import publish
from app.drafts import load_draft, save_draft

from app import db

def model_key(session_id: str = "default") -> str:
    """One open model per session. Templates stay global."""
    text = str(session_id or "default").strip() or "default"
    safe = re.sub(r"[^A-Za-z0-9._:-]", "-", text)[:80].strip("-") or "default"
    return f"sheets.model.{safe}"
TEMPLATE_PREFIX = "sheets.template."
KINDS = ("text", "number", "date", "formula")
FILLED_BY = ("", "owner", "staff", "jarvis")
BLOCK_KINDS = ("title", "table", "section", "chart")
COLUMN_BLOCKS = ("table", "section")
MAX_TABS = 12
MAX_BLOCKS = 24
MAX_COLUMNS = 16
MAX_ROWS = 40
MAX_DROPDOWN = 20
MAX_TITLE = 80
MAX_NAME = 48
MAX_FORMULA = 200
MAX_TEXT = 200

_CELL_REF = re.compile(r"\b[A-Za-z]{1,3}\d+\b")
_BAD_TAB = re.compile(r"[\[\]*?:/\\]")


class ModelError(ValueError):
    """The workbook model was rejected."""


def empty_model() -> dict[str, Any]:
    return {"title": "", "new_file": True, "tabs": []}


def _text(value: Any, limit: int, field: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ModelError(f"{field} must be text")
    text = value.strip()
    if len(text) > limit:
        raise ModelError(f"{field} is too long")
    return text


def _tab_title(value: Any) -> str:
    title = _text(value, MAX_TITLE, "tab")
    if not title:
        raise ModelError("tab title is required")
    if _BAD_TAB.search(title):
        raise ModelError("tab title cannot include : \\ / ? * [ ]")
    return title


def normalize_column(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ModelError("each column must be an object")
    name = _text(item.get("name"), MAX_NAME, "column name")
    if not name:
        raise ModelError("column name is required")
    kind = str(item.get("kind") or "text").strip()
    if kind not in KINDS:
        raise ModelError("column kind must be text, number, date, or formula")
    filled = str(item.get("filled_by") or "").strip()
    if filled not in FILLED_BY:
        raise ModelError("filled_by must be owner, staff, jarvis, or empty")
    formula = _text(item.get("formula"), MAX_FORMULA, "formula")
    if kind != "formula":
        formula = ""
    elif formula and _CELL_REF.search(formula):
        raise ModelError("formula must name columns, not cells")
    dropdown_raw = item.get("dropdown") or []
    if isinstance(dropdown_raw, str):
        dropdown_raw = [part.strip() for part in dropdown_raw.split(",") if part.strip()]
    if not isinstance(dropdown_raw, list):
        raise ModelError("dropdown must be a list")
    if len(dropdown_raw) > MAX_DROPDOWN:
        raise ModelError("too many dropdown values")
    dropdown: list[str] = []
    for value in dropdown_raw:
        text = _text(value, MAX_NAME, "dropdown value")
        if text and text not in dropdown:
            dropdown.append(text)
    return {
        "name": name,
        "kind": kind,
        "filled_by": filled,
        "formula": formula,
        "dropdown": dropdown,
    }


def _columns(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise ModelError("columns must be a list")
    if len(raw) > MAX_COLUMNS:
        raise ModelError(f"at most {MAX_COLUMNS} columns")
    columns: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        column = normalize_column(item)
        key = column["name"].casefold()
        if key in seen:
            raise ModelError(f"duplicate column {column['name']}")
        seen.add(key)
        columns.append(column)
    return columns


def _rows(raw: Any, columns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not raw:
        return []
    if not isinstance(raw, list):
        raise ModelError("rows must be a list")
    if len(raw) > MAX_ROWS:
        raise ModelError("too many sample rows")
    names = {column["name"].casefold(): column["name"] for column in columns}
    rows: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ModelError("each sample row must be an object")
        kept: dict[str, Any] = {}
        for key, value in item.items():
            canonical = names.get(str(key).strip().casefold())
            if canonical is None:
                raise ModelError(f"sample row has no column {key}")
            if value is None or value == "":
                continue
            if isinstance(value, bool) or not isinstance(value, (str, int, float)):
                raise ModelError("sample values must be text or numbers")
            if isinstance(value, str):
                value = value.strip()
                if not value:
                    continue
                if len(value) > MAX_TEXT:
                    raise ModelError("sample value is too long")
            kept[canonical] = value
        if kept:
            rows.append(kept)
    return rows


def _chart_source(value: Any) -> int | str:
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            return int(text)
        if text:
            return text
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ModelError("chart source must be a block id")
    return value


def _block(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ModelError("each block must be an object")
    kind = str(raw.get("kind") or "").strip()
    if kind not in BLOCK_KINDS:
        raise ModelError("block kind must be title, table, section, or chart")
    if kind == "title":
        return {"kind": "title", "text": _text(raw.get("text"), MAX_TEXT, "title text")}
    if kind == "chart":
        return {
            "kind": "chart",
            "source": _chart_source(raw.get("source")),
            "title": _text(raw.get("title"), MAX_TITLE, "chart title"),
        }
    columns = _columns(raw.get("columns") or [])
    block: dict[str, Any] = {
        "kind": kind,
        "columns": columns,
        "rows": _rows(raw.get("rows") or [], columns),
    }
    if kind == "section":
        block["heading"] = _text(raw.get("heading"), MAX_TITLE, "heading")
    return block


def _assign_block_ids(blocks: list[dict[str, Any]]) -> None:
    used: set[str] = set()
    for block in blocks:
        current = str(block.get("id") or "").strip()
        if not re.fullmatch(r"b[1-9][0-9]*", current) or current in used:
            number = 1
            while f"b{number}" in used:
                number += 1
            current = f"b{number}"
        block["id"] = current
        used.add(current)
    for index, block in enumerate(blocks):
        if block["kind"] != "chart" or not isinstance(block["source"], int):
            continue
        source = block["source"]
        if source >= len(blocks):
            raise ModelError("chart must bind to a table or section on the same tab")
        block["source"] = blocks[source]["id"]


def _check_charts(blocks: list[dict[str, Any]]) -> None:
    by_id = {block["id"]: block for block in blocks}
    for block in blocks:
        if block["kind"] != "chart":
            continue
        target = by_id.get(block["source"])
        if target is None or target["id"] == block["id"] or target["kind"] not in COLUMN_BLOCKS:
            raise ModelError("chart must bind to a table or section on the same tab")


def _tab(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ModelError("each tab must be an object")
    blocks_raw = raw.get("blocks") or []
    if not isinstance(blocks_raw, list):
        raise ModelError("blocks must be a list")
    if len(blocks_raw) > MAX_BLOCKS:
        raise ModelError("too many blocks")
    blocks = [_block(item) for item in blocks_raw]
    _assign_block_ids(blocks)
    _check_charts(blocks)
    return {"title": _tab_title(raw.get("title")), "blocks": blocks}


def normalize_model(raw: Any) -> dict[str, Any]:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ModelError("model must be an object")
    if "workbook_title" in raw and "tabs" not in raw:
        raise ModelError("header-only sheet drafts are retired")
    tabs_raw = raw.get("tabs") or []
    if not isinstance(tabs_raw, list):
        raise ModelError("tabs must be a list")
    if len(tabs_raw) > MAX_TABS:
        raise ModelError("too many tabs")
    tabs = [_tab(item) for item in tabs_raw]
    seen: set[str] = set()
    for tab in tabs:
        key = tab["title"].casefold()
        if key in seen:
            raise ModelError(f"duplicate tab {tab['title']}")
        seen.add(key)
    model: dict[str, Any] = {"title": _text(raw.get("title"), MAX_TITLE, "title"), "new_file": True, "tabs": tabs}
    created = _created(raw.get("created"))
    if created:
        model["created"] = created
    return model


def _created(raw: Any) -> dict[str, str] | None:
    if not isinstance(raw, dict):
        return None
    spreadsheet_id = str(raw.get("spreadsheet_id") or "").strip()
    url = str(raw.get("url") or "").strip()
    if not spreadsheet_id or not url:
        return None
    return {
        "spreadsheet_id": spreadsheet_id,
        "url": url,
        "template_id": str(raw.get("template_id") or "").strip(),
        "fingerprint": str(raw.get("fingerprint") or "").strip(),
    }


def get_model(session_id: str = "default") -> dict[str, Any]:
    loaded = load_draft(model_key(session_id))
    if not loaded:
        return {"model": empty_model(), "updated_at": None, "error": None}
    body = loaded.get("body")
    try:
        model = normalize_model(body)
    except ModelError as exc:
        return {"model": None, "error": str(exc), "updated_at": loaded.get("updated_at")}
    return {"model": model, "updated_at": loaded.get("updated_at"), "error": None}


def put_model(raw: Any, session_id: str = "default") -> dict[str, Any]:
    model = normalize_model(raw)
    saved = save_draft(model_key(session_id), model)
    publish("sheets.changed", {"model": model, "session_id": session_id})
    return {"model": model, "updated_at": saved["updated_at"]}


def missing_piece(model: dict[str, Any]) -> str | None:
    if not str(model.get("title") or "").strip():
        return "title"
    tabs = model.get("tabs") or []
    if not tabs:
        return "tab"
    if not any(tab.get("blocks") for tab in tabs):
        return "block"
    return None


def next_question(missing: str | None) -> str:
    if missing is None:
        return "Say when to create it."
    if missing == "title":
        return "What should the workbook be called?"
    if missing == "tab":
        return "What should the first tab be called?"
    return "What should go on that tab?"


def outline(model: dict[str, Any]) -> str:
    lines = [str(model.get("title") or "").strip() or "(untitled)"]
    tabs = model.get("tabs") or []
    if not tabs:
        lines.append("- No tabs yet")
        return "\n".join(lines)
    for tab in tabs:
        lines.append(f"- Tab: {tab['title']}")
        blocks = tab.get("blocks") or []
        if not blocks:
            lines.append("  - Empty")
            continue
        for block in blocks:
            kind = block.get("kind")
            block_id = block.get("id") or "?"
            if kind == "title":
                lines.append(f"  - [{block_id}] Title: {block.get('text') or '(blank)'}")
            elif kind == "table":
                names = ", ".join(column["name"] for column in block.get("columns") or []) or "(no columns)"
                lines.append(f"  - [{block_id}] Table: {names}")
            elif kind == "section":
                names = ", ".join(column["name"] for column in block.get("columns") or []) or "(no columns)"
                heading = block.get("heading") or "(no heading)"
                lines.append(f"  - [{block_id}] Section: {heading} — {names}")
            elif kind == "chart":
                lines.append(f"  - [{block_id}] Chart: {block.get('source')}")
    return "\n".join(lines)


def structure_only(model: dict[str, Any]) -> dict[str, Any]:
    """Drop sample rows. Labels, columns, formulas, and dropdowns stay."""
    clean = normalize_model(model)
    clean.pop("created", None)
    for tab in clean["tabs"]:
        for block in tab["blocks"]:
            if block["kind"] in COLUMN_BLOCKS:
                block["rows"] = []
    clean["new_file"] = True
    return clean


def _copy(model: dict[str, Any]) -> dict[str, Any]:
    return normalize_model(copy.deepcopy(model))


def _tab_index(model: dict[str, Any], tab: Any) -> int:
    tabs = model["tabs"]
    label = str(tab or "").strip()
    if not label:
        if len(tabs) == 1:
            return 0
        raise ModelError("which tab?")
    for index, item in enumerate(tabs):
        if item["title"].casefold() == label.casefold():
            return index
    raise ModelError(f"no tab {label}")


def _block_index(tab: dict[str, Any], block: Any, *, columns: bool) -> int:
    blocks = tab["blocks"]
    if block is None or block == "":
        if not columns:
            raise ModelError("which block?")
        found = [index for index, item in enumerate(blocks) if item["kind"] in COLUMN_BLOCKS]
        if len(found) == 1:
            return found[0]
        if not found:
            raise ModelError("there is no table on this tab")
        raise ModelError("which block?")
    label = block.strip() if isinstance(block, str) else ""
    if re.fullmatch(r"b[1-9][0-9]*", label):
        for index, item in enumerate(blocks):
            if item.get("id") == label:
                return index
        raise ModelError("that block is not on the tab")
    if isinstance(block, str) and block.strip().isdigit():
        block = int(block.strip())
    if isinstance(block, bool) or not isinstance(block, int):
        raise ModelError("block must be an index")
    if block < 0 or block >= len(blocks):
        raise ModelError("that block is not on the tab")
    return block


def _column_index(block: dict[str, Any], name: str) -> int | None:
    wanted = name.casefold()
    for index, column in enumerate(block.get("columns") or []):
        if column["name"].casefold() == wanted:
            return index
    return None


def _set_title(model: dict[str, Any], **fields: Any) -> tuple[dict[str, Any], str, bool]:
    updated = _copy(model)
    title = _text(fields.get("title"), MAX_TITLE, "title")
    if not title:
        raise ModelError("a title is required")
    updated["title"] = title
    return updated, f"Title set to {title}.", True


def _add_tab(model: dict[str, Any], **fields: Any) -> tuple[dict[str, Any], str, bool]:
    updated = _copy(model)
    title = _tab_title(fields.get("title") or fields.get("name"))
    if any(tab["title"].casefold() == title.casefold() for tab in updated["tabs"]):
        raise ModelError(f"duplicate tab {title}")
    if len(updated["tabs"]) >= MAX_TABS:
        raise ModelError("too many tabs")
    updated["tabs"].append({"title": title, "blocks": []})
    return updated, f"Added tab {title}.", True


def _rename_tab(model: dict[str, Any], **fields: Any) -> tuple[dict[str, Any], str, bool]:
    updated = _copy(model)
    index = _tab_index(updated, fields.get("tab"))
    title = _tab_title(fields.get("title"))
    if any(i != index and tab["title"].casefold() == title.casefold() for i, tab in enumerate(updated["tabs"])):
        raise ModelError(f"duplicate tab {title}")
    previous = updated["tabs"][index]["title"]
    updated["tabs"][index]["title"] = title
    return updated, f"Renamed tab {previous} to {title}.", True


def _remove_tab(model: dict[str, Any], **fields: Any) -> tuple[dict[str, Any], str, bool]:
    updated = _copy(model)
    index = _tab_index(updated, fields.get("tab"))
    title = updated["tabs"][index]["title"]
    del updated["tabs"][index]
    return updated, f"Removed tab {title}.", True


def _add_block(model: dict[str, Any], **fields: Any) -> tuple[dict[str, Any], str, bool]:
    updated = _copy(model)
    index = _tab_index(updated, fields.get("tab"))
    spec = fields.get("block") if isinstance(fields.get("block"), dict) else {}
    kind = str(fields.get("kind") or spec.get("kind") or "").strip()
    raw: dict[str, Any] = {"kind": kind}
    if kind == "title":
        raw["text"] = fields.get("text", spec.get("text", ""))
    elif kind == "chart":
        raw["source"] = fields.get("source", spec.get("source"))
        raw["title"] = fields.get("chart_title", spec.get("title", fields.get("title", "")))
    elif kind == "section":
        raw["heading"] = fields.get("heading", spec.get("heading", ""))
        raw["columns"] = fields.get("columns", spec.get("columns", []))
        raw["rows"] = fields.get("rows", spec.get("rows", []))
    else:
        raw["columns"] = fields.get("columns", spec.get("columns", []))
        raw["rows"] = fields.get("rows", spec.get("rows", []))
    block = _block(raw)
    tab = updated["tabs"][index]
    if len(tab["blocks"]) >= MAX_BLOCKS:
        raise ModelError("too many blocks")
    tab["blocks"].append(block)
    _assign_block_ids(tab["blocks"])
    _check_charts(tab["blocks"])
    return updated, f"Added a {kind} on {tab['title']}.", True


def _new_column(fields: dict[str, Any]) -> dict[str, Any]:
    column = fields.get("column")
    if isinstance(column, dict):
        return normalize_column(column)
    return normalize_column(
        {
            "name": fields.get("name"),
            "kind": fields.get("kind") or "text",
            "filled_by": fields.get("filled_by") or "",
            "formula": fields.get("formula") or "",
            "dropdown": fields.get("dropdown") or [],
        }
    )


def _insert_column(model: dict[str, Any], **fields: Any) -> tuple[dict[str, Any], str, bool]:
    anchor = str(fields.get("anchor") or "").strip()
    if fields.get("after") and not anchor:
        anchor = str(fields.get("after")).strip()
        place = "after"
    elif fields.get("before") and not anchor:
        anchor = str(fields.get("before")).strip()
        place = "before"
    else:
        place = str(fields.get("place") or "after").strip().lower()
    if place not in ("before", "after"):
        raise ModelError("place must be before or after")
    if not anchor:
        raise ModelError("name the column to insert beside")
    updated = _copy(model)
    tab = updated["tabs"][_tab_index(updated, fields.get("tab"))]
    try:
        block = tab["blocks"][_block_index(tab, fields.get("block"), columns=True)]
    except ModelError as exc:
        if str(exc) == "there is no table on this tab":
            return model, f"{anchor} is not on this table. I left the model unchanged.", False
        raise
    if block["kind"] not in COLUMN_BLOCKS:
        return model, f"{anchor} is not on this table. I left the model unchanged.", False
    found = _column_index(block, anchor)
    if found is None:
        return model, f"{anchor} is not on this table. I left the model unchanged.", False
    column = _new_column(fields)
    names = [item["name"].casefold() for item in block["columns"]]
    if column["name"].casefold() in names:
        raise ModelError(f"duplicate column {column['name']}")
    if len(block["columns"]) >= MAX_COLUMNS:
        raise ModelError(f"at most {MAX_COLUMNS} columns")
    at = found if place == "before" else found + 1
    block["columns"].insert(at, column)
    anchor_at = found + 1 if place == "before" else found
    shown = block["columns"][anchor_at]["name"]
    return updated, f"Added {column['name']} {place} {shown}.", True


def _target_column(
    model: dict[str, Any], fields: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], int] | None:
    updated = _copy(model)
    tab = updated["tabs"][_tab_index(updated, fields.get("tab"))]
    block = tab["blocks"][_block_index(tab, fields.get("block"), columns=True)]
    if block["kind"] not in COLUMN_BLOCKS:
        return None
    return updated, block, -1


def _rename_column(model: dict[str, Any], **fields: Any) -> tuple[dict[str, Any], str, bool]:
    name = str(fields.get("name") or "").strip()
    new_name = _text(fields.get("new_name"), MAX_NAME, "column name")
    if not name or not new_name:
        raise ModelError("name the column and the new name")
    located = _target_column(model, fields)
    if located is None:
        return model, f"{name} is not on this table. I left the model unchanged.", False
    updated, block, _index = located
    index = _column_index(block, name)
    if index is None:
        return model, f"{name} is not on this table. I left the model unchanged.", False
    if any(i != index and column["name"].casefold() == new_name.casefold() for i, column in enumerate(block["columns"])):
        raise ModelError(f"duplicate column {new_name}")
    previous = block["columns"][index]["name"]
    block["columns"][index]["name"] = new_name
    pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(previous)}(?![A-Za-z0-9])", re.IGNORECASE)
    for column in block["columns"]:
        if column.get("formula"):
            column["formula"] = pattern.sub(new_name, column["formula"])
    for row in block["rows"]:
        if previous in row:
            row[new_name] = row.pop(previous)
    return updated, f"Renamed {previous} to {new_name}.", True


def _remove_column(model: dict[str, Any], **fields: Any) -> tuple[dict[str, Any], str, bool]:
    name = str(fields.get("name") or "").strip()
    if not name:
        raise ModelError("name the column to remove")
    located = _target_column(model, fields)
    if located is None:
        return model, f"{name} is not on this table. I left the model unchanged.", False
    updated, block, _index = located
    index = _column_index(block, name)
    if index is None:
        return model, f"{name} is not on this table. I left the model unchanged.", False
    removed = block["columns"][index]["name"]
    del block["columns"][index]
    for row in block["rows"]:
        row.pop(removed, None)
    return updated, f"Removed {removed}.", True


def _set_kind(model: dict[str, Any], **fields: Any) -> tuple[dict[str, Any], str, bool]:
    name = str(fields.get("name") or "").strip()
    kind = str(fields.get("kind") or "").strip()
    if kind not in KINDS:
        raise ModelError("column kind must be text, number, date, or formula")
    located = _target_column(model, fields)
    if located is None or not name:
        return model, f"{name or 'That column'} is not on this table. I left the model unchanged.", False
    updated, block, _index = located
    index = _column_index(block, name)
    if index is None:
        return model, f"{name} is not on this table. I left the model unchanged.", False
    column = block["columns"][index]
    column["kind"] = kind
    if kind != "formula":
        column["formula"] = ""
    return updated, f"Set {column['name']} to {kind}.", True


def _set_filler(model: dict[str, Any], **fields: Any) -> tuple[dict[str, Any], str, bool]:
    name = str(fields.get("name") or "").strip()
    filled = str(fields.get("filled_by") or "").strip()
    if filled not in FILLED_BY:
        raise ModelError("filled_by must be owner, staff, jarvis, or empty")
    located = _target_column(model, fields)
    if located is None or not name:
        return model, f"{name or 'That column'} is not on this table. I left the model unchanged.", False
    updated, block, _index = located
    index = _column_index(block, name)
    if index is None:
        return model, f"{name} is not on this table. I left the model unchanged.", False
    block["columns"][index]["filled_by"] = filled
    return updated, f"Set {block['columns'][index]['name']} to be filled by {filled or 'nobody'}.", True


def _set_formula(model: dict[str, Any], **fields: Any) -> tuple[dict[str, Any], str, bool]:
    name = str(fields.get("name") or "").strip()
    formula = _text(fields.get("formula"), MAX_FORMULA, "formula")
    if formula and _CELL_REF.search(formula):
        raise ModelError("formula must name columns, not cells")
    located = _target_column(model, fields)
    if located is None or not name:
        return model, f"{name or 'That column'} is not on this table. I left the model unchanged.", False
    updated, block, _index = located
    index = _column_index(block, name)
    if index is None:
        return model, f"{name} is not on this table. I left the model unchanged.", False
    column = block["columns"][index]
    column["kind"] = "formula"
    column["formula"] = formula
    return updated, f"Set {column['name']} to {formula or 'an empty formula'}.", True


def _set_dropdown(model: dict[str, Any], **fields: Any) -> tuple[dict[str, Any], str, bool]:
    name = str(fields.get("name") or "").strip()
    located = _target_column(model, fields)
    if located is None or not name:
        return model, f"{name or 'That column'} is not on this table. I left the model unchanged.", False
    updated, block, _index = located
    index = _column_index(block, name)
    if index is None:
        return model, f"{name} is not on this table. I left the model unchanged.", False
    values = fields.get("values", fields.get("dropdown", []))
    column = dict(block["columns"][index])
    column["dropdown"] = values
    block["columns"][index] = normalize_column(column)
    shown = ", ".join(block["columns"][index]["dropdown"]) or "nothing"
    return updated, f"Set {block['columns'][index]['name']} dropdown to {shown}.", True


def _set_text(model: dict[str, Any], **fields: Any) -> tuple[dict[str, Any], str, bool]:
    updated = _copy(model)
    tab = updated["tabs"][_tab_index(updated, fields.get("tab"))]
    index = _block_index(tab, fields.get("block"), columns=False)
    block = tab["blocks"][index]
    if block["kind"] == "title":
        block["text"] = _text(fields.get("text"), MAX_TEXT, "title text")
        return updated, "Set the title text.", True
    if block["kind"] == "section":
        block["heading"] = _text(fields.get("text", fields.get("heading")), MAX_TITLE, "heading")
        return updated, "Set the section heading.", True
    raise ModelError("that block has no text to set")


def _set_rows(model: dict[str, Any], **fields: Any) -> tuple[dict[str, Any], str, bool]:
    updated = _copy(model)
    tab = updated["tabs"][_tab_index(updated, fields.get("tab"))]
    block = tab["blocks"][_block_index(tab, fields.get("block"), columns=True)]
    if block["kind"] not in COLUMN_BLOCKS:
        raise ModelError("sample rows belong on a table or section")
    block["rows"] = _rows(fields.get("rows") or [], block["columns"])
    return updated, "Stored the sample rows the owner stated.", True


_ACTIONS = {
    "set_title": _set_title,
    "add_tab": _add_tab,
    "rename_tab": _rename_tab,
    "remove_tab": _remove_tab,
    "add_block": _add_block,
    "insert_column": _insert_column,
    "rename_column": _rename_column,
    "remove_column": _remove_column,
    "set_kind": _set_kind,
    "set_filler": _set_filler,
    "set_formula": _set_formula,
    "set_dropdown": _set_dropdown,
    "set_text": _set_text,
    "set_rows": _set_rows,
}


def edit_model(model: dict[str, Any], action: str, **fields: Any) -> tuple[dict[str, Any], str, bool]:
    """Return the next model, a short note, and whether the model changed."""
    name = str(action or "").strip()
    handler = _ACTIONS.get(name)
    if handler is None:
        raise ModelError(f"unknown edit {name or '(blank)'}")
    updated, note, changed = handler(model, **fields)
    if changed:
        updated.pop("created", None)
    return updated, note, changed


def fingerprint(model: dict[str, Any]) -> str:
    """Identity of the model ignoring a previous create."""
    import hashlib

    body = normalize_model(model)
    body.pop("created", None)
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _slug(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")
    return (slug or "workbook")[:48]


def list_templates() -> list[dict[str, str]]:
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT key, body FROM drafts WHERE key LIKE ? ORDER BY key",
            (f"{TEMPLATE_PREFIX}%",),
        ).fetchall()
    found: list[dict[str, str]] = []
    for row in rows:
        try:
            body = json.loads(row["body"])
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(body, dict):
            continue
        model = body.get("model") if isinstance(body.get("model"), dict) else {}
        template_id = str(body.get("id") or row["key"].removeprefix(TEMPLATE_PREFIX))
        found.append({"id": template_id, "title": str(model.get("title") or "")})
    return found


def save_template(model: dict[str, Any]) -> dict[str, str]:
    structure = structure_only(model)
    base = _slug(structure["title"])
    template_id = base
    for number in range(2, 51):
        if load_draft(f"{TEMPLATE_PREFIX}{template_id}") is None:
            break
        template_id = f"{base}-{number}"
    else:
        raise ModelError("too many templates with that title")
    save_draft(f"{TEMPLATE_PREFIX}{template_id}", {"id": template_id, "model": structure})
    return {"id": template_id, "title": structure["title"]}


def cloned_model(template_id: str, title: str) -> dict[str, Any]:
    key = f"{TEMPLATE_PREFIX}{str(template_id or '').strip()}"
    loaded = load_draft(key)
    if not loaded:
        raise ModelError(f"no template {template_id}")
    body = loaded.get("body") or {}
    source = body.get("model") if isinstance(body, dict) and isinstance(body.get("model"), dict) else body
    model = structure_only(source)
    new_title = _text(title, MAX_TITLE, "title")
    if not new_title:
        raise ModelError("a new title is required")
    model["title"] = new_title
    model["new_file"] = True
    return model
