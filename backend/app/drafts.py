"""Draft autosave (X10). Stores owner fields only; never sends or queues anything external."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import db

router = APIRouter()
MAX_BODY_BYTES = 64_000


class DraftBody(BaseModel):
    body: dict[str, Any] = Field(default_factory=dict)


def save_draft(key: str, body: dict[str, Any]) -> dict[str, Any]:
    raw = json.dumps(body)
    if len(raw.encode()) > MAX_BODY_BYTES:
        raise HTTPException(413, "draft too large")
    now = db.utc_now()
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO drafts(key, body, updated_at) VALUES(?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET body=excluded.body, updated_at=excluded.updated_at",
            (key, raw, now),
        )
    return {"key": key, "body": body, "updated_at": now}


def load_draft(key: str) -> dict[str, Any] | None:
    with db.connect() as conn:
        row = conn.execute("SELECT body, updated_at FROM drafts WHERE key = ?", (key,)).fetchone()
    if not row:
        return None
    return {"key": key, "body": json.loads(row[0]), "updated_at": row[1]}


@router.get("/api/drafts/{key}")
def api_get_draft(key: str) -> dict:
    return load_draft(key) or {"key": key, "body": {}, "updated_at": None}


@router.put("/api/drafts/{key}")
def api_put_draft(key: str, payload: DraftBody) -> dict:
    return save_draft(key, payload.body)


@router.post("/api/drafts/{key}")
def api_post_draft(key: str, payload: DraftBody) -> dict:
    """POST twin of PUT so `navigator.sendBeacon` (pagehide) can save."""
    return save_draft(key, payload.body)
