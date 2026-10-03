"""Compile a workbook model into one Sheets batchUpdate. Does not call Google."""

from __future__ import annotations

import re
from typing import Any

from app.connectors.sheets_toolkit.client import SheetsToolkitError, grid_range
from app.features.sheets.draft import normalize_model

_FUNCTIONS = frozenset({"SUM", "ROUND", "ABS", "IF", "AND", "OR", "MIN", "MAX", "AVERAGE", "INT", "MOD"})
_CELL_REF = re.compile(r"\b[A-Za-z]{1,3}\d+\b")
_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_FILL_ROWS = 50


class CompileError(ValueError):
    """The model cannot become a valid batch, so nothing should be written."""


def column_letter(index: int) -> str:
    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
        raise CompileError("column index must be >= 0")
    number = index + 1
    letters = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def compile_formula(expression: str, columns: list[dict[str, Any]], row_number: int) -> str:
    """Turn column names into an A1 formula for one 1-based row."""
    text = str(expression or "").strip()
    if text.startswith("="):
        text = text[1:].strip()
    if not text:
        raise CompileError("formula is empty")
    if _CELL_REF.search(text):
        raise CompileError("formula must name columns, not cells")
    if isinstance(row_number, bool) or not isinstance(row_number, int) or row_number < 1:
        raise CompileError("formula row must be >= 1")
    pairs = [(column["name"], column_letter(index)) for index, column in enumerate(columns) if column.get("name")]
    pairs.sort(key=lambda item: len(item[0]), reverse=True)
    placeholders: list[tuple[str, str]] = []
    replaced = text
    for index, (name, letter) in enumerate(pairs):
        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])", re.IGNORECASE)
        token = f"__COL{index}__"
        if pattern.search(replaced):
            replaced = pattern.sub(token, replaced)
            placeholders.append((token, f"{letter}{row_number}"))
    for token, ref in placeholders:
        replaced = replaced.replace(token, ref)
    for word in _WORD.findall(replaced):
        if word.upper() in _FUNCTIONS:
            continue
        if re.fullmatch(r"[A-Za-z]{1,3}\d+", word):
            continue
        raise CompileError(f"{word} is not a column on this table")
    if not placeholders and not re.fullmatch(r"[\d\s.+\-*/(),]+", replaced):
        raise CompileError("formula does not name a column on this table")
    return "=" + replaced


def _range(sheet_id: int, start_row: int, end_row: int, start_column: int, end_column: int) -> dict[str, int]:
    try:
        return grid_range(sheet_id, start_row, end_row, start_column, end_column)
    except SheetsToolkitError as exc:
        raise CompileError(str(exc)) from exc


def _blank() -> dict[str, Any]:
    return {}


def _text_cell(value: str) -> dict[str, Any]:
    return {"userEnteredValue": {"stringValue": value}}


def _number_cell(value: int | float) -> dict[str, Any]:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return {"userEnteredValue": {"numberValue": value}}


def _formula_cell(formula: str) -> dict[str, Any]:
    return {"userEnteredValue": {"formulaValue": formula}}


def _stored_cell(column: dict[str, Any], value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        raise CompileError("sample values must be text or numbers")
    if isinstance(value, (int, float)):
        return _number_cell(value)
    text = str(value).strip()
    if column.get("kind") == "number":
        try:
            number: int | float = float(text) if "." in text else int(text)
        except ValueError:
            return _text_cell(text)
        return _number_cell(number)
    return _text_cell(text)


def _write_row(sheet_id: int, row: int, cells: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "updateCells": {
            "range": _range(sheet_id, row, row + 1, 0, len(cells)),
            "rows": [{"values": cells}],
            "fields": "userEnteredValue",
        }
    }


def _bold(sheet_id: int, row: int, start_column: int, end_column: int) -> dict[str, Any]:
    return {
        "repeatCell": {
            "range": _range(sheet_id, row, row + 1, start_column, end_column),
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
            "fields": "userEnteredFormat.textFormat.bold",
        }
    }


def _merge(sheet_id: int, row: int, width: int) -> dict[str, Any] | None:
    if width < 2:
        return None
    return {
        "mergeCells": {
            "range": _range(sheet_id, row, row + 1, 0, width),
            "mergeType": "MERGE_ALL",
        }
    }


def _number_format(sheet_id: int, start_row: int, column: int, kind: str) -> dict[str, Any]:
    pattern = "yyyy-mm-dd" if kind == "date" else "#,##0.##"
    number_type = "DATE" if kind == "date" else "NUMBER"
    return {
        "repeatCell": {
            "range": _range(sheet_id, start_row, start_row + _FILL_ROWS, column, column + 1),
            "cell": {"userEnteredFormat": {"numberFormat": {"type": number_type, "pattern": pattern}}},
            "fields": "userEnteredFormat.numberFormat",
        }
    }


def _dropdown(sheet_id: int, start_row: int, column: int, values: list[str]) -> dict[str, Any]:
    return {
        "setDataValidation": {
            "range": _range(sheet_id, start_row, start_row + _FILL_ROWS, column, column + 1),
            "rule": {
                "condition": {
                    "type": "ONE_OF_LIST",
                    "values": [{"userEnteredValue": value} for value in values],
                },
                "strict": True,
                "showCustomUi": True,
            },
        }
    }


def _label_row(sheet_id: int, row: int, text: str, width: int) -> list[dict[str, Any]]:
    cells = [_text_cell(text)] + [_blank() for _ in range(width - 1)]
    requests = [_write_row(sheet_id, row, cells), _bold(sheet_id, row, 0, 1)]
    merged = _merge(sheet_id, row, width)
    if merged:
        requests.append(merged)
    return requests


def _sample_rows(block: dict[str, Any]) -> list[dict[str, Any]]:
    rows = block.get("rows") or []
    if not isinstance(rows, list):
        raise CompileError("rows must be a list")
    return [row for row in rows if isinstance(row, dict)]


def _has_formula(columns: list[dict[str, Any]]) -> bool:
    return any(column.get("kind") == "formula" and str(column.get("formula") or "").strip() for column in columns)


def _data_cells(
    columns: list[dict[str, Any]],
    sample: dict[str, Any],
    row_number: int,
) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    for column in columns:
        name = column["name"]
        if name in sample and sample[name] not in ("", None):
            cells.append(_stored_cell(column, sample[name]))
            continue
        formula = str(column.get("formula") or "").strip()
        if column.get("kind") == "formula" and formula:
            cells.append(_formula_cell(compile_formula(formula, columns, row_number)))
            continue
        cells.append(_blank())
    return cells


def _chart_request(
    sheet_id: int,
    anchor_row: int,
    header_row: int,
    end_row: int,
    columns: list[dict[str, Any]],
    title: str,
) -> dict[str, Any]:
    series: list[dict[str, Any]] = []
    for index, column in enumerate(columns):
        if index == 0 or column.get("kind") not in ("number", "formula"):
            continue
        series.append(
            {
                "series": {
                    "sourceRange": {
                        "sources": [_range(sheet_id, header_row, end_row, index, index + 1)],
                    }
                },
                "targetAxis": "LEFT_AXIS",
            }
        )
    if not series:
        raise CompileError("chart needs a number column beside its first column")
    if end_row - header_row < 2:
        raise CompileError("chart needs a header and a data range")
    return {
        "addChart": {
            "chart": {
                "spec": {
                    "title": title or "Chart",
                    "basicChart": {
                        "chartType": "COLUMN",
                        "legendPosition": "BOTTOM_LEGEND",
                        "headerCount": 1,
                        "domains": [
                            {
                                "domain": {
                                    "sourceRange": {
                                        "sources": [_range(sheet_id, header_row, end_row, 0, 1)],
                                    }
                                }
                            }
                        ],
                        "series": series,
                    },
                },
                "position": {
                    "overlayPosition": {
                        "anchorCell": {
                            "sheetId": sheet_id,
                            "rowIndex": anchor_row,
                            "columnIndex": 0,
                        }
                    }
                },
            }
        }
    }


def _layout_tab(sheet_id: int, tab: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
    blocks = tab.get("blocks") or []
    width = 1
    for block in blocks:
        if block.get("kind") in ("table", "section"):
            width = max(width, len(block.get("columns") or []) or 1)
    requests: list[dict[str, Any]] = []
    ranges: dict[int, dict[str, Any]] = {}
    row = 0
    frozen = 0
    for index, block in enumerate(blocks):
        kind = block.get("kind")
        if kind == "title":
            text = str(block.get("text") or "").strip()
            if text:
                requests.extend(_label_row(sheet_id, row, text, width))
                row += 1
            continue
        if kind in ("table", "section"):
            columns = block.get("columns") or []
            if kind == "section":
                heading = str(block.get("heading") or "").strip()
                if heading:
                    requests.extend(_label_row(sheet_id, row, heading, max(width, len(columns) or 1)))
                    row += 1
            if not columns:
                row += 1
                continue
            header = [_text_cell(column["name"]) for column in columns]
            requests.append(_write_row(sheet_id, row, header))
            requests.append(_bold(sheet_id, row, 0, len(columns)))
            header_row = row
            if frozen == 0:
                frozen = header_row + 1
            row += 1
            data_start = row
            samples = _sample_rows(block)
            write_count = _FILL_ROWS if _has_formula(columns) else len(samples)
            for offset in range(write_count):
                sample = samples[offset] if offset < len(samples) else {}
                requests.append(
                    _write_row(
                        sheet_id,
                        data_start + offset,
                        _data_cells(columns, sample, data_start + offset + 1),
                    )
                )
            ranges[block.get("id")] = {
                "header_row": header_row,
                "end_row": data_start + _FILL_ROWS,
                "columns": columns,
            }
            for column_index, column in enumerate(columns):
                if column.get("kind") in ("number", "date"):
                    requests.append(_number_format(sheet_id, data_start, column_index, column["kind"]))
                dropdown = column.get("dropdown") or []
                if dropdown:
                    requests.append(_dropdown(sheet_id, data_start, column_index, list(dropdown)))
            row = data_start + max(write_count, _FILL_ROWS) + 1
            continue
        if kind == "chart":
            continue
        raise CompileError("unknown block")
    for index, block in enumerate(blocks):
        if block.get("kind") != "chart":
            continue
        source = ranges.get(block.get("source"))
        if source is None:
            raise CompileError("chart must bind to a table or section on the same tab")
        title = str(block.get("title") or "").strip() or "Chart"
        requests.append(
            _chart_request(
                sheet_id,
                row,
                source["header_row"],
                source["end_row"],
                source["columns"],
                title,
            )
        )
        row += 1
    return frozen, requests


def _sheet_request(sheet_id: int, title: str, frozen: int, *, first: bool) -> dict[str, Any]:
    if first:
        properties: dict[str, Any] = {"sheetId": sheet_id, "title": title}
        fields = "title"
        if frozen:
            properties["gridProperties"] = {"frozenRowCount": frozen}
            fields = "title,gridProperties.frozenRowCount"
        return {"updateSheetProperties": {"properties": properties, "fields": fields}}
    properties = {"sheetId": sheet_id, "title": title, "index": sheet_id}
    if frozen:
        properties["gridProperties"] = {"frozenRowCount": frozen}
    return {"addSheet": {"properties": properties}}


def compile_model(model: dict[str, Any], first_sheet_id: int = 0) -> list[dict[str, Any]]:
    """Build one atomic batch for a new file. The first tab uses the sheet id Google assigned."""
    if isinstance(first_sheet_id, bool) or not isinstance(first_sheet_id, int) or first_sheet_id < 0:
        raise CompileError("first sheet id must be >= 0")
    model = normalize_model(model)
    if model.get("new_file") is not True:
        raise CompileError("apply creates a new file")
    tabs = model.get("tabs") or []
    if not tabs:
        raise CompileError("a tab is required")
    requests: list[dict[str, Any]] = []
    content: list[dict[str, Any]] = []
    for index, tab in enumerate(tabs):
        title = str(tab.get("title") or "").strip()
        if not title:
            raise CompileError("tab title is required")
        sheet_id = first_sheet_id + index
        frozen, tab_requests = _layout_tab(sheet_id, tab)
        requests.append(_sheet_request(sheet_id, title, frozen, first=index == 0))
        content.extend(tab_requests)
    requests.extend(content)
    if not requests or any(not isinstance(item, dict) or len(item) != 1 for item in requests):
        raise CompileError("the batch is empty")
    return requests
