from __future__ import annotations

import html
import re
from typing import Any

_TABLE_HTML = re.compile(r"<table\b[^>]*>.*?</table>", re.I | re.S)
_TR = re.compile(r"<tr\b[^>]*>.*?</tr>", re.I | re.S)
_CELL = re.compile(r"<t[hd]\b[^>]*>(.*?)</t[hd]>", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")
_PIPE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_PIPE_SEP = re.compile(r"^\s*\|?\s*:?-{3,}")


def _strip_tags(value: str) -> str:
    text = _TAG.sub(" ", value or "")
    text = html.unescape(text)
    return re.sub(r"[ \t]+", " ", text).strip()


def html_table_to_markdown(table_html: str) -> str:
    rows: list[list[str]] = []
    for row_html in _TR.findall(table_html):
        cells = [_strip_tags(cell) for cell in _CELL.findall(row_html)]
        if any(cells):
            rows.append(cells)
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    header, body = rows[0], rows[1:]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in body)
    return "\n".join(lines)


def html_to_text(raw: str) -> str:
    chunks: list[str] = []
    cursor = 0
    for match in _TABLE_HTML.finditer(raw or ""):
        before = _strip_tags(raw[cursor : match.start()])
        if before:
            chunks.append(before)
        table = html_table_to_markdown(match.group(0))
        if table:
            chunks.append(table)
        cursor = match.end()
    tail = _strip_tags((raw or "")[cursor:])
    if tail:
        chunks.append(tail)
    return "\n\n".join(chunk for chunk in chunks if chunk).strip()


def _pipe_cells(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _is_sep(line: str) -> bool:
    if _PIPE_SEP.match(line):
        return True
    cells = _pipe_cells(line) if "|" in line else []
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells)


def split_body(text: str) -> list[dict[str, Any]]:
    lines = (text or "").replace("\r\n", "\n").split("\n")
    blocks: list[dict[str, Any]] = []
    prose: list[str] = []
    index = 0

    def flush_prose() -> None:
        chunk = "\n".join(prose).strip()
        prose.clear()
        if chunk:
            blocks.append({"kind": "prose", "text": chunk})

    while index < len(lines):
        line = lines[index]
        if _PIPE_ROW.match(line) and index + 1 < len(lines) and _is_sep(lines[index + 1]):
            flush_prose()
            header = _pipe_cells(line)
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and _PIPE_ROW.match(lines[index]):
                rows.append(_pipe_cells(lines[index]))
                index += 1
            width = max([len(header), *(len(row) for row in rows)], default=0)
            header = header + [""] * (width - len(header))
            rows = [row + [""] * (width - len(row)) for row in rows]
            if header and any(header):
                blocks.append({"kind": "table", "columns": header, "rows": rows})
            continue
        prose.append(line)
        index += 1
    flush_prose()
    return blocks


def widgets_from_body(text: str, title: str = "") -> list[dict[str, Any]]:
    widgets: list[dict[str, Any]] = []
    first_table = True
    for block in split_body(text):
        if block["kind"] == "table":
            widgets.append(
                {
                    "type": "table",
                    "title": title if first_table else "",
                    "columns": block["columns"],
                    "rows": block["rows"],
                }
            )
            first_table = False
            continue
        widgets.append({"type": "markdown", "title": title if not widgets else "", "text": block["text"]})
    if not widgets:
        widgets.append({"type": "markdown", "title": title, "text": text or ""})
    return widgets
