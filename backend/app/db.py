import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .config import settings
from .schemas import Preferences

DEFAULT_PREFS = Preferences().model_dump()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS artifacts (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                name TEXT NOT NULL,
                path TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                tool TEXT NOT NULL,
                detail TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pending_actions (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS preferences (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS emails (
                id TEXT PRIMARY KEY,
                sender TEXT NOT NULL,
                to_addr TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                unread INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                folder TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS calendar_events (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                start_at TEXT NOT NULL,
                end_at TEXT NOT NULL,
                location TEXT,
                notes TEXT
            );
            CREATE TABLE IF NOT EXISTS inbox_files (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS thought_state (
                session_id TEXT PRIMARY KEY,
                data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS working_set (
                session_id TEXT PRIMARY KEY,
                data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS hud_state (
                session_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS watches (
                session_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                after_id TEXT,
                status TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS canvas_boards (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                camera TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS canvas_items (
                id TEXT PRIMARY KEY,
                board_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                x REAL NOT NULL DEFAULT 0,
                y REAL NOT NULL DEFAULT 0,
                w REAL NOT NULL DEFAULT 0,
                h REAL NOT NULL DEFAULT 0,
                rotation REAL NOT NULL DEFAULT 0,
                z INTEGER NOT NULL DEFAULT 0,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS canvas_items_board ON canvas_items (board_id);
            CREATE TABLE IF NOT EXISTS canvas_files (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                mime TEXT NOT NULL,
                path TEXT NOT NULL,
                width REAL NOT NULL DEFAULT 0,
                height REAL NOT NULL DEFAULT 0,
                page_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            """
        )
        email_cols = {row[1] for row in conn.execute("PRAGMA table_info(emails)").fetchall()}
        if "thread_id" not in email_cols:
            conn.execute("ALTER TABLE emails ADD COLUMN thread_id TEXT")
        inbox_cols = {row[1] for row in conn.execute("PRAGMA table_info(inbox_files)").fetchall()}
        if "path" not in inbox_cols:
            conn.execute("ALTER TABLE inbox_files ADD COLUMN path TEXT")
        existing = conn.execute("SELECT data FROM preferences WHERE id = 1").fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO preferences (id, data) VALUES (1, ?)",
                (json.dumps(DEFAULT_PREFS),),
            )


def add_message(session_id: str, role: str, content: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, utc_now()),
        )


def recent_messages(session_id: str, limit: int = 16) -> list[dict[str, str]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT role, content FROM messages
            WHERE session_id = ?
            ORDER BY id DESC LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
    return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]


def add_memory(session_id: str, key: str, value: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO memories (session_id, key, value, created_at) VALUES (?, ?, ?, ?)",
            (session_id, key, value, utc_now()),
        )


def list_memories(session_id: str, limit: int = 20) -> list[dict[str, str]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT key, value, created_at FROM memories
            WHERE session_id = ?
            ORDER BY id DESC LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def add_artifact(artifact_id: str, kind: str, name: str, path: str) -> dict[str, str]:
    created = utc_now()
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO artifacts (id, kind, name, path, created_at) VALUES (?, ?, ?, ?, ?)",
            (artifact_id, kind, name, path, created),
        )
    return {
        "id": artifact_id,
        "kind": kind,
        "name": name,
        "path": path,
        "created_at": created,
    }


def list_artifacts(limit: int = 40) -> list[dict[str, str]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, kind, name, path, created_at FROM artifacts ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_artifact(artifact_id: str) -> dict[str, str] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, kind, name, path, created_at FROM artifacts WHERE id = ?",
            (artifact_id,),
        ).fetchone()
    return dict(row) if row else None


def get_artifact_by_name(name: str) -> dict[str, str] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, kind, name, path, created_at FROM artifacts WHERE name = ? ORDER BY created_at DESC LIMIT 1",
            (name,),
        ).fetchone()
    return dict(row) if row else None


def get_working_set(session_id: str) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute(
            "SELECT data FROM working_set WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    if not row:
        return {}
    try:
        data = json.loads(row["data"])
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save_working_set(session_id: str, data: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO working_set (session_id, data) VALUES (?, ?)
            ON CONFLICT(session_id) DO UPDATE SET data = excluded.data
            """,
            (session_id, json.dumps(data)),
        )


def save_hud_state(session_id: str, data: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO hud_state (session_id, data, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at
            """,
            (session_id, json.dumps(data), utc_now()),
        )


def get_hud_state(session_id: str) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT data FROM hud_state WHERE session_id = ?", (session_id,)).fetchone()
    if not row:
        return {}
    try:
        data = json.loads(row["data"])
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def add_audit(session_id: str, tool: str, detail: str, status: str = "ok") -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO audit (session_id, tool, detail, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, tool, detail, status, utc_now()),
        )


def list_audit(limit: int = 50) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, created_at, session_id, tool, detail, status
            FROM audit ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def add_pending(
    action_id: str,
    session_id: str,
    kind: str,
    title: str,
    summary: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO pending_actions
            (id, session_id, kind, title, summary, payload, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (action_id, session_id, kind, title, summary, json.dumps(payload), utc_now()),
        )
    return {
        "id": action_id,
        "kind": kind,
        "title": title,
        "summary": summary,
        "payload": payload,
    }


def get_pending(action_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM pending_actions WHERE id = ?",
            (action_id,),
        ).fetchone()
    if not row:
        return None
    data = dict(row)
    data["payload"] = json.loads(data["payload"])
    return data


def set_pending_status(action_id: str, status: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE pending_actions SET status = ? WHERE id = ?",
            (status, action_id),
        )


def list_pending(session_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, kind, title, summary, payload FROM pending_actions
            WHERE session_id = ? AND status = 'pending'
            ORDER BY created_at DESC
            """,
            (session_id,),
        ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["payload"] = json.loads(item["payload"])
        items.append(item)
    return items


def get_preferences() -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT data FROM preferences WHERE id = 1").fetchone()
    data = json.loads(row["data"]) if row else DEFAULT_PREFS
    return {**DEFAULT_PREFS, **data}


def update_preferences(patch: dict[str, Any]) -> dict[str, Any]:
    current = get_preferences()
    current.update({key: value for key, value in patch.items() if value is not None})
    with connect() as conn:
        conn.execute(
            "UPDATE preferences SET data = ? WHERE id = 1",
            (json.dumps(current),),
        )
    return current


def add_inbox_file(file_id: str, name: str, text: str, path: str = "") -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO inbox_files (id, name, text, path, created_at) VALUES (?, ?, ?, ?, ?)",
            (file_id, name, text[:20000], path, utc_now()),
        )


def list_inbox_files(limit: int = 12) -> list[dict[str, str]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, name, text, path, created_at FROM inbox_files ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_inbox_file(file_id: str) -> dict[str, str] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, name, text, path, created_at FROM inbox_files WHERE id = ?",
            (file_id,),
        ).fetchone()
    return dict(row) if row else None


def upsert_email(record: dict[str, Any]) -> dict[str, Any]:
    row = {
        "id": record["id"],
        "sender": record.get("sender") or "",
        "to_addr": record.get("to_addr") or "",
        "subject": record.get("subject") or "",
        "body": record.get("body") or "",
        "unread": int(record.get("unread") or 0),
        "created_at": record.get("created_at") or utc_now(),
        "folder": record.get("folder") or "INBOX",
        "thread_id": record.get("thread_id") or "",
    }
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO emails
            (id, sender, to_addr, subject, body, unread, created_at, folder, thread_id)
            VALUES (:id, :sender, :to_addr, :subject, :body, :unread, :created_at, :folder, :thread_id)
            """,
            row,
        )
    return row


def set_watch(session_id: str, kind: str, thread_id: str, after_id: str = "", status: str = "waiting", data: dict[str, Any] | None = None) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO watches (session_id, kind, thread_id, after_id, status, data, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                kind = excluded.kind,
                thread_id = excluded.thread_id,
                after_id = excluded.after_id,
                status = excluded.status,
                data = excluded.data,
                created_at = excluded.created_at
            """,
            (session_id, kind, thread_id, after_id, status, json.dumps(data or {}), utc_now()),
        )


def _watch_row(row: Any) -> dict[str, Any]:
    item = dict(row)
    try:
        item["payload"] = json.loads(item.get("data") or "{}")
    except json.JSONDecodeError:
        item["payload"] = {}
    return item


def get_watch(session_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM watches WHERE session_id = ?", (session_id,)).fetchone()
    return _watch_row(row) if row else None


def list_watches() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM watches ORDER BY created_at DESC").fetchall()
    return [_watch_row(row) for row in rows]


def list_waiting_watches() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM watches WHERE status = 'waiting'").fetchall()
    return [_watch_row(row) for row in rows]


def _thought_state(session_id: str) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute(
            "SELECT data FROM thought_state WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    if not row:
        return {"items": [], "focus": None}
    try:
        data = json.loads(row["data"])
    except json.JSONDecodeError:
        return {"items": [], "focus": None}
    if not isinstance(data, dict):
        return {"items": [], "focus": None}
    return {"items": data.get("items") or [], "focus": data.get("focus", None)}


def _save_thought_state(session_id: str, state: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO thought_state (session_id, data) VALUES (?, ?)
            ON CONFLICT(session_id) DO UPDATE SET data = excluded.data
            """,
            (session_id, json.dumps(state)),
        )


def clear_thoughts(session_id: str) -> None:
    _save_thought_state(session_id, {"items": [], "focus": None})


def set_thoughts(session_id: str, items: list[dict[str, Any]], focus: str | None = None) -> None:
    _save_thought_state(session_id, {"items": items, "focus": focus})


def set_focus_pending(session_id: str, focus: str | None) -> None:
    state = _thought_state(session_id)
    state["focus"] = focus
    _save_thought_state(session_id, state)


def pop_thought(session_id: str) -> dict[str, Any] | None:
    state = _thought_state(session_id)
    items = list(state.get("items") or [])
    if not items:
        return None
    first = items.pop(0)
    state["items"] = items
    _save_thought_state(session_id, state)
    return first


def thought_count(session_id: str) -> int:
    return len(_thought_state(session_id).get("items") or [])


def get_focus_pending(session_id: str) -> str | None:
    return _thought_state(session_id).get("focus", None)


def list_focused_pending(session_id: str) -> list[dict[str, Any]]:
    items = list_pending(session_id)
    focus = get_focus_pending(session_id)
    if focus is None:
        return items
    if focus == "":
        return []
    return [item for item in items if item["id"] == focus]


DEFAULT_CAMERA = {"x": 0.0, "y": 0.0, "z": 1.0}


def _canvas_board(row: sqlite3.Row) -> dict[str, Any]:
    board = dict(row)
    try:
        camera = json.loads(board.get("camera") or "{}")
    except json.JSONDecodeError:
        camera = {}
    board["camera"] = {**DEFAULT_CAMERA, **(camera if isinstance(camera, dict) else {})}
    return board


def upsert_canvas_board(
    board_id: str,
    name: str = "Canvas",
    camera: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = utc_now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO canvas_boards (id, name, camera, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                camera = excluded.camera,
                updated_at = excluded.updated_at
            """,
            (board_id, name, json.dumps({**DEFAULT_CAMERA, **(camera or {})}), now, now),
        )
    return {
        "id": board_id,
        "name": name,
        "camera": {**DEFAULT_CAMERA, **(camera or {})},
        "created_at": now,
        "updated_at": now,
    }


def get_canvas_board(board_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM canvas_boards WHERE id = ?", (board_id,)).fetchone()
    return _canvas_board(row) if row else None


def list_canvas_boards(limit: int = 40) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM canvas_boards ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_canvas_board(row) for row in rows]


def list_canvas_items(board_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, kind, x, y, w, h, rotation, z, data FROM canvas_items
            WHERE board_id = ? ORDER BY z ASC, created_at ASC
            """,
            (board_id,),
        ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        try:
            extra = json.loads(item.pop("data") or "{}")
        except json.JSONDecodeError:
            extra = {}
        items.append({**item, **(extra if isinstance(extra, dict) else {})})
    return items


def replace_canvas_items(board_id: str, items: list[dict[str, Any]]) -> int:
    """Whole-board save. The HUD debounces edits, so one replace beats a stream
    of per-item updates."""
    now = utc_now()
    rows = [
        (
            item["id"],
            board_id,
            item.get("kind") or "note",
            float(item.get("x") or 0),
            float(item.get("y") or 0),
            float(item.get("w") or 0),
            float(item.get("h") or 0),
            float(item.get("rotation") or 0),
            int(item.get("z") or 0),
            json.dumps(item.get("data") or {}),
            now,
            now,
        )
        for item in items
    ]
    with connect() as conn:
        conn.execute("DELETE FROM canvas_items WHERE board_id = ?", (board_id,))
        conn.executemany(
            """
            INSERT INTO canvas_items
            (id, board_id, kind, x, y, w, h, rotation, z, data, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    return len(rows)


def add_canvas_item(
    board_id: str,
    kind: str,
    x: float,
    y: float,
    w: float,
    h: float,
    data: dict[str, Any] | None = None,
    rotation: float = 0.0,
    z: int = 0,
    item_id: str | None = None,
) -> dict[str, Any]:
    """Single entry point for putting something on a board. A future
    `add_to_canvas` tool calls this and nothing else needs to change."""
    now = utc_now()
    new_id = item_id or uuid.uuid4().hex[:12]
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO canvas_items
            (id, board_id, kind, x, y, w, h, rotation, z, data, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (new_id, board_id, kind, x, y, w, h, rotation, z, json.dumps(data or {}), now, now),
        )
    return {
        "id": new_id,
        "kind": kind,
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "rotation": rotation,
        "z": z,
        **(data or {}),
    }


def add_canvas_file(
    file_id: str,
    name: str,
    mime: str,
    path: str,
    width: float = 0.0,
    height: float = 0.0,
    page_count: int = 0,
) -> dict[str, Any]:
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO canvas_files
            (id, name, mime, path, width, height, page_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (file_id, name, mime, path, width, height, page_count, utc_now()),
        )
    return {
        "file_id": file_id,
        "name": name,
        "mime": mime,
        "width": width,
        "height": height,
        "page_count": page_count,
    }


def get_canvas_file(file_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM canvas_files WHERE id = ?", (file_id,)).fetchone()
    return dict(row) if row else None


def safe_export_path(name: str) -> Path:
    clean = Path(name).name
    if not clean or clean in {".", ".."}:
        raise ValueError("Invalid file name")
    target = (settings.exports_dir / clean).resolve()
    if settings.exports_dir.resolve() not in target.parents and target != settings.exports_dir.resolve():
        raise ValueError("Exports must stay inside the workspace folder")
    return target
