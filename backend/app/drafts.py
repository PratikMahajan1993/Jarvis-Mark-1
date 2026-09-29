"""Draft autosave (X10). Stores owner fields only; never sends or queues anything external."""

from __future__ import annotations

import json
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError

from . import db

router = APIRouter()
MAX_BODY_BYTES = 64_000
DRAFT_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class DraftBody(BaseModel):
    body: dict[str, Any] = Field(default_factory=dict)


def save_draft(key: str, body: dict[str, Any]) -> dict[str, Any]:
    if not DRAFT_KEY_RE.fullmatch(key):
        raise HTTPException(400, "invalid draft key")
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


def _draft_body_from_raw(raw: bytes) -> dict[str, Any]:
    """Parse `{"body": {...}}` from a raw request body (JSON or text/plain JSON)."""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, "invalid JSON") from exc
    try:
        payload = DraftBody.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(400, "invalid draft payload") from exc
    return payload.body


@router.get("/api/drafts/{key}")
def api_get_draft(key: str) -> dict:
    return load_draft(key) or {"key": key, "body": {}, "updated_at": None}


@router.put("/api/drafts/{key}")
def api_put_draft(key: str, payload: DraftBody) -> dict:
    return save_draft(key, payload.body)


@router.post("/api/drafts/{key}")
async def api_post_draft(key: str, request: Request) -> dict:
    """POST twin of PUT so `navigator.sendBeacon` (pagehide) can save.

    Accepts application/json `DraftBody` and text/plain whose body is the same JSON object.
    """
    body = _draft_body_from_raw(await request.body())
    return save_draft(key, body)
