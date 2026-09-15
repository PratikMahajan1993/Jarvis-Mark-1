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
            CREATE TABLE IF NOT EXISTS mission_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                mission_id TEXT NOT NULL,
                step INTEGER NOT NULL,
                role TEXT NOT NULL,
                detail TEXT NOT NULL,
                latency_ms INTEGER,
                status TEXT NOT NULL,
                tokens INTEGER,
                cost REAL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_mission_steps_mission
                ON mission_steps(mission_id, step);
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
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                focus TEXT NOT NULL,
                minimized INTEGER NOT NULL DEFAULT 1,
                expanded_at TEXT,
                status TEXT NOT NULL DEFAULT 'ready',
                model TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS conversations_updated ON conversations (updated_at);
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
            CREATE TABLE IF NOT EXISTS work_snapshot (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                mail_synced_at TEXT,
                calendar_synced_at TEXT,
                mail_count INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS mail_sync_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                status TEXT NOT NULL DEFAULT 'idle',
                days INTEGER NOT NULL DEFAULT 0,
                synced_count INTEGER NOT NULL DEFAULT 0,
                skipped_count INTEGER NOT NULL DEFAULT 0,
                page_token TEXT NOT NULL DEFAULT '',
                started_at TEXT NOT NULL DEFAULT '',
                finished_at TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                customer TEXT NOT NULL,
                part_name TEXT NOT NULL,
                material TEXT NOT NULL,
                machine TEXT NOT NULL,
                cycle_min REAL,
                margin REAL,
                drawing_file TEXT,
                geometry_notes TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS jobs_material ON jobs (material);
            CREATE INDEX IF NOT EXISTS jobs_material_lc ON jobs (lower(material));
            CREATE TABLE IF NOT EXISTS rfqs (
                id TEXT PRIMARY KEY,
                mail_id TEXT,
                conversation_id TEXT,
                status TEXT NOT NULL,
                extract TEXT NOT NULL,
                similar_job_ids TEXT NOT NULL,
                pending_reply TEXT,
                deadline_iso TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS rfqs_status ON rfqs (status);
            """
        )
        email_cols = {row[1] for row in conn.execute("PRAGMA table_info(emails)").fetchall()}
        if "thread_id" not in email_cols:
            conn.execute("ALTER TABLE emails ADD COLUMN thread_id TEXT")
        if "attachments" not in email_cols:
            conn.execute("ALTER TABLE emails ADD COLUMN attachments TEXT")
        inbox_cols = {row[1] for row in conn.execute("PRAGMA table_info(inbox_files)").fetchall()}
        if "path" not in inbox_cols:
            conn.execute("ALTER TABLE inbox_files ADD COLUMN path TEXT")
        job_cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
        if "geometry_notes" not in job_cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN geometry_notes TEXT")
        rfq_cols = {row[1] for row in conn.execute("PRAGMA table_info(rfqs)").fetchall()}
        if "updated_at" not in rfq_cols:
            conn.execute("ALTER TABLE rfqs ADD COLUMN updated_at TEXT")
        pending_cols = {row[1] for row in conn.execute("PRAGMA table_info(pending_actions)").fetchall()}
        if "agent_id" not in pending_cols:
            conn.execute("ALTER TABLE pending_actions ADD COLUMN agent_id TEXT DEFAULT ''")
        if "tool_name" not in pending_cols:
            conn.execute("ALTER TABLE pending_actions ADD COLUMN tool_name TEXT DEFAULT ''")
        existing = conn.execute("SELECT data FROM preferences WHERE id = 1").fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO preferences (id, data) VALUES (1, ?)",
                (json.dumps(DEFAULT_PREFS),),
            )
    from .jobs import seed_demo_job

    seed_demo_job()


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


def add_mission_step(
    *,
    session_id: str,
    mission_id: str,
    step: int,
    role: str,
    detail: str = "",
    latency_ms: int | None = None,
    status: str = "ok",
    tokens: int | None = None,
    cost: float | None = None,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO mission_steps
            (session_id, mission_id, step, role, detail, latency_ms, status, tokens, cost, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                mission_id,
                int(step),
                role,
                detail or "",
                latency_ms,
                status,
                tokens,
                cost,
                utc_now(),
            ),
        )


def list_mission_steps(
    limit: int = 50,
    *,
    mission_id: str | None = None,
    session_id: str | None = None,
) -> list[dict[str, Any]]:
    with connect() as conn:
        if mission_id:
            rows = conn.execute(
                """
                SELECT * FROM mission_steps
                WHERE mission_id = ?
                ORDER BY step ASC, id ASC
                LIMIT ?
                """,
                (mission_id, limit),
            ).fetchall()
        elif session_id:
            rows = conn.execute(
                """
                SELECT * FROM mission_steps
                WHERE session_id = ?
                ORDER BY id DESC LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM mission_steps
                ORDER BY id DESC LIMIT ?
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
    agent_id: str = "",
    tool_name: str = "",
) -> dict[str, Any]:
    with connect() as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(pending_actions)").fetchall()}
        if "agent_id" in cols and "tool_name" in cols:
            conn.execute(
                """
                INSERT INTO pending_actions
                (id, session_id, kind, title, summary, payload, status, created_at, agent_id, tool_name)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
                """,
                (
                    action_id,
                    session_id,
                    kind,
                    title,
                    summary,
                    json.dumps(payload),
                    utc_now(),
                    agent_id or "",
                    tool_name or "",
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO pending_actions
                (id, session_id, kind, title, summary, payload, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (action_id, session_id, kind, title, summary, json.dumps(payload), utc_now()),
            )
    result = {
        "id": action_id,
        "kind": kind,
        "title": title,
        "summary": summary,
        "payload": payload,
        "agent_id": agent_id or "",
        "tool_name": tool_name or "",
    }
    return _attach_blast_radius(result)


def _attach_blast_radius(data: dict[str, Any]) -> dict[str, Any]:
    from .hitl_meta import blast_radius_for

    payload = data.get("payload") or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = {}
    score, consequence = blast_radius_for(str(data.get("kind") or ""), payload if isinstance(payload, dict) else {})
    data["irreversibility"] = score
    data["consequence"] = consequence
    return data


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
    data.setdefault("agent_id", "")
    data.setdefault("tool_name", "")
    return _attach_blast_radius(data)


def set_pending_status(action_id: str, status: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE pending_actions SET status = ? WHERE id = ?",
            (status, action_id),
        )


def update_pending_payload(
    action_id: str,
    payload: dict[str, Any],
    *,
    title: str | None = None,
    summary: str | None = None,
) -> None:
    with connect() as conn:
        row = conn.execute(
            "SELECT title, summary FROM pending_actions WHERE id = ?",
            (action_id,),
        ).fetchone()
        if not row:
            return
        conn.execute(
            """
            UPDATE pending_actions
            SET payload = ?, title = ?, summary = ?
            WHERE id = ?
            """,
            (
                json.dumps(payload),
                title if title is not None else row["title"],
                summary if summary is not None else row["summary"],
                action_id,
            ),
        )


def list_pending(session_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM pending_actions
            WHERE session_id = ? AND status = 'pending'
            ORDER BY created_at DESC
            """,
            (session_id,),
        ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["payload"] = json.loads(item["payload"])
        item.setdefault("agent_id", "")
        item.setdefault("tool_name", "")
        items.append(_attach_blast_radius(item))
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
    attachments = record.get("attachments")
    if isinstance(attachments, str):
        packed = attachments
    elif attachments:
        packed = json.dumps(attachments)
    else:
        packed = ""
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
        "attachments": packed,
    }
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO emails
            (id, sender, to_addr, subject, body, unread, created_at, folder, thread_id, attachments)
            VALUES (:id, :sender, :to_addr, :subject, :body, :unread, :created_at, :folder, :thread_id, :attachments)
            """,
            row,
        )
    return hydrate_email(row)


def hydrate_email(row: dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    raw = item.get("attachments")
    if isinstance(raw, str):
        try:
            item["attachments"] = json.loads(raw) if raw else []
        except json.JSONDecodeError:
            item["attachments"] = []
    elif not isinstance(raw, list):
        item["attachments"] = []
    return item


def search_emails_local(query: str = "", unread_only: bool = False, limit: int = 8) -> list[dict[str, Any]]:
    sql = "SELECT * FROM emails WHERE folder = 'INBOX'"
    args: list[Any] = []
    if unread_only:
        sql += " AND unread = 1"
    hint = (query or "").strip()
    lowered = hint.lower()
    if lowered.startswith("from:"):
        name = hint.split(":", 1)[1].strip().strip('"')
        sql += " AND sender LIKE ?"
        args.append(f"%{name}%")
    elif hint:
        sql += " AND (subject LIKE ? OR sender LIKE ? OR body LIKE ?)"
        like = f"%{hint}%"
        args.extend([like, like, like])
    sql += " ORDER BY created_at DESC LIMIT ?"
    args.append(limit)
    with connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [hydrate_email(dict(row)) for row in rows]


def get_email_local(email_id: str) -> dict[str, Any] | None:
    if not email_id:
        return None
    with connect() as conn:
        row = conn.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone()
    return hydrate_email(dict(row)) if row else None


def unread_count_local() -> int:
    with connect() as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) AS n FROM emails WHERE unread = 1 AND folder = 'INBOX'"
            ).fetchone()["n"]
        )


def upsert_calendar_event(record: dict[str, Any]) -> dict[str, Any]:
    row = {
        "id": record["id"],
        "title": record.get("title") or "",
        "start_at": record.get("start_at") or "",
        "end_at": record.get("end_at") or "",
        "location": record.get("location") or "",
        "notes": record.get("notes") or "",
    }
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO calendar_events (id, title, start_at, end_at, location, notes)
            VALUES (:id, :title, :start_at, :end_at, :location, :notes)
            """,
            row,
        )
    return row


def replace_calendar_events(rows: list[dict[str, Any]]) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM calendar_events")
        for record in rows:
            conn.execute(
                """
                INSERT OR REPLACE INTO calendar_events (id, title, start_at, end_at, location, notes)
                VALUES (:id, :title, :start_at, :end_at, :location, :notes)
                """,
                {
                    "id": record["id"],
                    "title": record.get("title") or "",
                    "start_at": record.get("start_at") or "",
                    "end_at": record.get("end_at") or "",
                    "location": record.get("location") or "",
                    "notes": record.get("notes") or "",
                },
            )


def get_work_snapshot() -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM work_snapshot WHERE id = 1").fetchone()
    if not row:
        return {
            "mail_synced_at": "",
            "calendar_synced_at": "",
            "mail_count": 0,
            "status": "",
        }
    return dict(row)


def get_mail_sync_state() -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM mail_sync_state WHERE id = 1").fetchone()
    if not row:
        return {
            "status": "idle",
            "days": 0,
            "synced_count": 0,
            "skipped_count": 0,
            "page_token": "",
            "started_at": "",
            "finished_at": "",
            "error": "",
        }
    return dict(row)


def set_mail_sync_state(
    *,
    status: str | None = None,
    days: int | None = None,
    synced_count: int | None = None,
    skipped_count: int | None = None,
    page_token: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    current = get_mail_sync_state()
    row = {
        "status": status if status is not None else current.get("status") or "idle",
        "days": int(days if days is not None else current.get("days") or 0),
        "synced_count": int(synced_count if synced_count is not None else current.get("synced_count") or 0),
        "skipped_count": int(skipped_count if skipped_count is not None else current.get("skipped_count") or 0),
        "page_token": page_token if page_token is not None else current.get("page_token") or "",
        "started_at": started_at if started_at is not None else current.get("started_at") or "",
        "finished_at": finished_at if finished_at is not None else current.get("finished_at") or "",
        "error": error if error is not None else current.get("error") or "",
    }
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO mail_sync_state (id, status, days, synced_count, skipped_count, page_token, started_at, finished_at, error)
            VALUES (1, :status, :days, :synced_count, :skipped_count, :page_token, :started_at, :finished_at, :error)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                days = excluded.days,
                synced_count = excluded.synced_count,
                skipped_count = excluded.skipped_count,
                page_token = excluded.page_token,
                started_at = excluded.started_at,
                finished_at = excluded.finished_at,
                error = excluded.error
            """,
            row,
        )
    return row


def count_gmail_emails_local() -> int:
    with connect() as conn:
        return int(
            conn.execute("SELECT COUNT(*) AS n FROM emails WHERE id LIKE 'gmail-%'").fetchone()["n"]
        )


def list_gmail_emails_local(*, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM emails
            WHERE id LIKE 'gmail-%'
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (max(1, limit), max(0, offset)),
        ).fetchall()
    return [hydrate_email(dict(row)) for row in rows]


def set_work_snapshot(
    *,
    mail_synced_at: str | None = None,
    calendar_synced_at: str | None = None,
    mail_count: int | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    current = get_work_snapshot()
    row = {
        "mail_synced_at": mail_synced_at if mail_synced_at is not None else current.get("mail_synced_at") or "",
        "calendar_synced_at": calendar_synced_at if calendar_synced_at is not None else current.get("calendar_synced_at") or "",
        "mail_count": int(mail_count if mail_count is not None else current.get("mail_count") or 0),
        "status": status if status is not None else current.get("status") or "",
    }
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO work_snapshot (id, mail_synced_at, calendar_synced_at, mail_count, status)
            VALUES (1, :mail_synced_at, :calendar_synced_at, :mail_count, :status)
            ON CONFLICT(id) DO UPDATE SET
                mail_synced_at = excluded.mail_synced_at,
                calendar_synced_at = excluded.calendar_synced_at,
                mail_count = excluded.mail_count,
                status = excluded.status
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


MAX_CONVERSATIONS = 12
# Concurrent "running" desk conversations (discussions / jobs / drawings).
MAX_EXPANDED = 3


def _conversation_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    try:
        focus = json.loads(data.get("focus") or "{}")
    except json.JSONDecodeError:
        focus = {}
    data["focus"] = focus if isinstance(focus, dict) else {}
    data["minimized"] = bool(int(0 if data.get("minimized") is None else data.get("minimized")))
    return data


def list_conversations(include_archived: bool = False) -> list[dict[str, Any]]:
    with connect() as conn:
        if include_archived:
            rows = conn.execute(
                "SELECT * FROM conversations ORDER BY updated_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM conversations WHERE status != 'archived' ORDER BY updated_at DESC"
            ).fetchall()
    return [_conversation_row(row) for row in rows]


def get_conversation(conversation_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    return _conversation_row(row) if row else None


def get_conversation_by_session(session_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM conversations WHERE session_id = ?", (session_id,)).fetchone()
    return _conversation_row(row) if row else None


def create_conversation(
    conversation_id: str,
    session_id: str,
    category: str,
    title: str,
    focus: dict[str, Any] | None = None,
    status: str = "warming",
) -> dict[str, Any]:
    now = utc_now()
    payload = json.dumps(focus or {})
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO conversations
            (id, session_id, category, title, focus, minimized, expanded_at, status, model, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?, '', ?, ?)
            """,
            (conversation_id, session_id, category, title, payload, now, status, now, now),
        )
    _enforce_expanded(conversation_id)
    _archive_overflow()
    found = get_conversation(conversation_id)
    return found or {}


def update_conversation(conversation_id: str, **fields: Any) -> dict[str, Any] | None:
    current = get_conversation(conversation_id)
    if not current:
        return None
    focus = fields["focus"] if "focus" in fields else current["focus"]
    if isinstance(focus, dict):
        focus_text = json.dumps(focus)
    else:
        focus_text = str(focus or "{}")
    minimized = current["minimized"]
    if "minimized" in fields:
        minimized = bool(fields["minimized"])
    expanded_at = current.get("expanded_at")
    if "minimized" in fields:
        expanded_at = None if minimized else utc_now()
    status = fields.get("status", current.get("status") or "ready")
    title = fields.get("title", current.get("title") or "")
    model = fields.get("model", current.get("model") or "")
    now = utc_now()
    with connect() as conn:
        conn.execute(
            """
            UPDATE conversations
            SET title = ?, focus = ?, minimized = ?, expanded_at = ?, status = ?, model = ?, updated_at = ?
            WHERE id = ?
            """,
            (title, focus_text, 1 if minimized else 0, expanded_at, status, model, now, conversation_id),
        )
    if "minimized" in fields and not minimized:
        _enforce_expanded(conversation_id)
    return get_conversation(conversation_id)


def touch_conversation(conversation_id: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (utc_now(), conversation_id),
        )


def _enforce_expanded(keep_id: str) -> None:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id FROM conversations
            WHERE status != 'archived' AND minimized = 0
            ORDER BY expanded_at DESC
            """
        ).fetchall()
    ids = [row["id"] for row in rows]
    if keep_id in ids:
        ids = [keep_id] + [ident for ident in ids if ident != keep_id]
    extra = ids[MAX_EXPANDED:]
    if not extra:
        return
    with connect() as conn:
        conn.executemany(
            "UPDATE conversations SET minimized = 1, expanded_at = NULL WHERE id = ?",
            [(ident,) for ident in extra],
        )


def _archive_overflow() -> None:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id FROM conversations
            WHERE status != 'archived'
            ORDER BY updated_at DESC
            """
        ).fetchall()
    extra = [row["id"] for row in rows[MAX_CONVERSATIONS:]]
    if not extra:
        return
    with connect() as conn:
        conn.executemany(
            "UPDATE conversations SET status = 'archived', minimized = 1 WHERE id = ?",
            [(ident,) for ident in extra],
        )


def safe_export_path(name: str) -> Path:
    clean = Path(name).name
    if not clean or clean in {".", ".."}:
        raise ValueError("Invalid file name")
    target = (settings.exports_dir / clean).resolve()
    if settings.exports_dir.resolve() not in target.parents and target != settings.exports_dir.resolve():
        raise ValueError("Exports must stay inside the workspace folder")
    return target
