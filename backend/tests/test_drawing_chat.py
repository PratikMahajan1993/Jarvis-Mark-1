from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.conversations import (
    asks_to_close_drawing,
    begin_drawing_chat,
    chat_drawing,
    close_drawing_view,
    create,
    is_drawing_session,
    leaves_drawing_for_shop,
    wants_drawing_window,
)


def setup_module(_module=None):
    db.init_db()


def test_drawing_chat_refuses_cloud_without_consent(monkeypatch):
    created = create(
        "drawing",
        "Bracket",
        {"filename": "bracket.pdf", "local_name": "bracket.pdf"},
        status="ready",
    )
    session = created["session_id"]

    def _boom(*_args, **_kwargs):
        raise AssertionError("cloud vision must not run without consent")

    monkeypatch.setattr("app.conversations._chat_drawing_media", _boom)
    result = chat_drawing(session, "What is the bore?")
    assert result.drawing_chat is not None
    assert result.drawing_chat.open is True
    assert "will not send" in result.speak.lower()
    assert "invent" in result.speak.lower()
    assert is_drawing_session(session)


def test_close_drawing_ends_the_viewing():
    created = create(
        "drawing",
        "Plate",
        {"filename": "plate.pdf", "local_name": "plate.pdf"},
        status="ready",
    )
    session = created["session_id"]
    assert asks_to_close_drawing("please close the drawing")
    closed = close_drawing_view(session)
    assert closed.drawing_chat is not None
    assert closed.drawing_chat.open is False
    assert is_drawing_session(session) is False


def test_open_from_the_desk_uses_the_newest_drawing(monkeypatch):
    created = create(
        "drawing",
        "Housing",
        {"filename": "housing.pdf", "local_name": "housing.pdf", "local_path": "D:/drawings/housing.pdf"},
        status="ready",
    )
    monkeypatch.setattr("app.conversations._chat_drawing_media", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("no cloud")))
    result = begin_drawing_chat("open the drawing", "default")
    assert result.drawing_chat is not None
    assert result.drawing_chat.open is True
    assert result.drawing_chat.session_id == created["session_id"]
    assert result.drawing_chat.filename == "housing.pdf"
    assert result.ui_action == {"action": "focus_drawing", "conversation_id": created["id"]}
    assert is_drawing_session(created["session_id"])
    assert "will not send" in result.speak.lower()


def test_shop_words_leave_the_drawing_window():
    assert wants_drawing_window("look at the drawing")
    assert wants_drawing_window("open the drawing") is True
    assert wants_drawing_window("quote this drawing") is False
    assert leaves_drawing_for_shop("send the quote") is True


def test_drop_reuses_the_same_bytes(monkeypatch, tmp_path):
    calls = {"n": 0}

    def _fake(*_args, **_kwargs):
        calls["n"] += 1
        return {"content": "A round bore is visible."}

    monkeypatch.setattr("app.conversations._chat_drawing_media", _fake)
    from app.conversations import ingest_dropped_drawing
    from app.config import settings
    import hashlib

    raw = b"%PDF-1.4 same-drawing-bytes"
    first = ingest_dropped_drawing("housing.pdf", raw)
    second = ingest_dropped_drawing("housing-copy.pdf", raw)
    assert first.drawing_chat is not None and second.drawing_chat is not None
    assert first.drawing_chat.open and second.drawing_chat.open
    assert first.drawing_chat.conversation_id == second.drawing_chat.conversation_id
    assert calls["n"] == 2
    assert "unattested test look" in first.reply.lower()
    folder = settings.exports_dir / "drawings"
    assert (folder / f"{hashlib.sha256(raw).hexdigest()}.pdf").is_file()
    with db.connect() as conn:
        rows = conn.execute("SELECT filename, byte_size FROM dropped_drawings").fetchall()
    assert len(rows) == 1
    assert rows[0]["filename"] == "housing.pdf"
    assert rows[0]["byte_size"] == len(raw)
    assert tmp_path is not None
    created = create(
        "drawing",
        "Cover",
        {"filename": "cover.pdf", "local_name": "cover.pdf"},
        status="ready",
    )
    monkeypatch.setattr(
        "app.conversations._chat_drawing_media",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("no cloud")),
    )
    from app.agent import run_agent

    result = run_agent("open the drawing", "default")
    assert result.drawing_chat is not None
    assert result.drawing_chat.open is True
    assert result.drawing_chat.session_id == created["session_id"]
    assert result.ui_action["action"] == "focus_drawing"
    monkeypatch.setattr("app.conversations.resolve_drawing_for_chat", lambda *_a, **_k: None)
    result = begin_drawing_chat("open the drawing", "empty-desk-session")
    assert result.drawing_chat is not None
    assert result.drawing_chat.open is False
    assert "which drawing" in result.speak.lower()
