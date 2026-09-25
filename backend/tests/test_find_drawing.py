"""find_drawing_for_quote: one clear path, or ask. Never the newest file."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings

settings.data_dir = Path(tempfile.mkdtemp(prefix="jarvis-find-drawing-"))
settings.exports_dir = Path(tempfile.mkdtemp(prefix="jarvis-find-drawing-ex-"))
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.exports_dir.mkdir(parents=True, exist_ok=True)

from app import db
from app.conversations import create as create_conversation
from app.mail_attachments import remember_mail_context
from app.quote import find_drawing_for_quote
from app.tools.registry import execute_tool


def setup_module(_module=None):
    db.init_db()


def _pdf(name: str, folder: Path | None = None) -> Path:
    target = (folder or settings.exports_dir) / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"%PDF-1.4 drawing")
    return target


def _quiet_desk() -> None:
    for row in db.list_conversations():
        if row.get("category") != "drawing":
            continue
        focus = dict(row.get("focus") or {})
        focus["viewing"] = False
        db.update_conversation(row["id"], focus=focus, minimized=True)


def _drawing(filename: str, path: Path, *, viewing: bool = True, minimized: bool = False) -> dict:
    row = create_conversation(
        "drawing",
        Path(filename).stem,
        {"filename": filename, "local_name": filename, "local_path": str(path), "viewing": viewing},
        status="ready",
    )
    if minimized:
        db.update_conversation(row["id"], minimized=True)
    return row


def test_provided_path_wins_and_missing_path_does_not_guess():
    decoy = _pdf("newer-bracket.pdf")
    asked = _pdf("asked-plate.pdf")
    session = "find-provided"
    hit = find_drawing_for_quote(session, part_hint="newer", drawing_path=str(asked))
    assert hit["ok"] is True
    assert hit["path"] == str(asked.resolve())
    assert hit["source"] == "provided_path"
    assert decoy.name not in hit["path"]

    missing = find_drawing_for_quote(session, drawing_path=str(settings.exports_dir / "no-such.pdf"))
    assert missing["ok"] is False
    assert missing["need"] == "path"
    assert missing["candidates"] == []
    assert "not a file" in missing["message"]


def test_one_focused_drawing_is_used_not_the_newest_export():
    _quiet_desk()
    older = _pdf("focus-pinion.pdf")
    _pdf("focus-newest.pdf")
    row = _drawing("focus-pinion.pdf", older)
    hit = find_drawing_for_quote("find-focus-other")
    assert hit["ok"] is True
    assert hit["source"] == "focus"
    assert hit["path"] == str(older.resolve())
    assert row["id"]


def test_session_drawing_beats_another_open_sheet():
    own_file = _pdf("session-own.pdf")
    other_file = _pdf("session-other.pdf")
    own = _drawing("session-own.pdf", own_file)
    _drawing("session-other.pdf", other_file)
    hit = find_drawing_for_quote(own["session_id"])
    assert hit["ok"] is True
    assert hit["path"] == str(own_file.resolve())
    assert hit["source"] == "focus"


def test_several_focused_drawings_ask():
    _quiet_desk()
    a = _pdf("desk-a.pdf")
    b = _pdf("desk-b.pdf")
    _drawing("desk-a.pdf", a)
    _drawing("desk-b.pdf", b)
    hit = find_drawing_for_quote("find-ambiguous-desk")
    assert hit["ok"] is False
    assert hit["need"] == "path"
    names = {item["filename"] for item in hit["candidates"]}
    assert names == {"desk-a.pdf", "desk-b.pdf"}
    assert "path" not in hit or hit.get("path") in (None, "")


def test_named_search_one_hit_and_several_ask():
    _quiet_desk()
    only = _pdf("named-only-sprocket.pdf")
    hit = find_drawing_for_quote("find-named-one", part_hint="sprocket")
    assert hit["ok"] is True
    assert hit["path"] == str(only.resolve())
    assert hit["source"] == "named_search"

    _pdf("named-two-sprocket-left.pdf")
    many = find_drawing_for_quote("find-named-many", part_hint="sprocket")
    assert many["ok"] is False
    assert many["need"] == "path"
    assert len(many["candidates"]) >= 2


def test_one_open_mail_drawing_is_saved_several_ask(monkeypatch):
    _quiet_desk()
    saved = _pdf("mail-bracket.pdf", settings.exports_dir / "drawings")
    calls: list[dict] = []

    def fake_save(session_id, email_id="", attachment_ids=None, filenames=None, **kwargs):
        calls.append({"email_id": email_id, "attachment_ids": attachment_ids, "drive": kwargs.get("drive")})
        return {
            "ok": True,
            "attachments": [
                {
                    "filename": "mail-bracket.pdf",
                    "attachment_id": "att-1",
                    "local_path": str(saved),
                }
            ],
        }

    monkeypatch.setattr("app.mail_attachments.save_attachments", fake_save)
    mail = {
        "id": "mail-one-drawing",
        "sender": "buyer@example.com",
        "to_addr": "you@jarvis.local",
        "subject": "RFQ",
        "body": "Please quote",
        "folder": "INBOX",
        "attachments": [
            {"filename": "mail-bracket.pdf", "attachment_id": "att-1", "mime": "application/pdf"}
        ],
    }
    db.upsert_email(mail)
    session = "find-mail-one"
    remember_mail_context(session, mail, mail["attachments"])
    hit = find_drawing_for_quote(session)
    assert hit["ok"] is True
    assert hit["source"] == "mail_attachment"
    assert hit["path"] == str(saved.resolve())
    assert calls == [{"email_id": "mail-one-drawing", "attachment_ids": ["att-1"], "drive": False}]

    both = {
        "id": "mail-two-drawings",
        "sender": "buyer@example.com",
        "to_addr": "you@jarvis.local",
        "subject": "RFQ two",
        "body": "Please quote both",
        "folder": "INBOX",
        "attachments": [
            {"filename": "left.pdf", "attachment_id": "att-l", "mime": "application/pdf"},
            {"filename": "right.pdf", "attachment_id": "att-r", "mime": "application/pdf"},
        ],
    }
    db.upsert_email(both)
    session_two = "find-mail-two"
    remember_mail_context(session_two, both, both["attachments"])
    calls.clear()
    asked = find_drawing_for_quote(session_two)
    assert asked["ok"] is False
    assert asked["need"] == "path"
    assert {item["filename"] for item in asked["candidates"]} == {"left.pdf", "right.pdf"}
    assert calls == []


def test_nothing_in_hand_asks_without_scanning_for_a_guess(monkeypatch):
    _quiet_desk()

    def boom(*_args, **_kwargs):
        raise AssertionError("must not search mail when nothing identifies a drawing")

    monkeypatch.setattr("app.connectors.email.search_emails", boom)
    hit = find_drawing_for_quote("find-empty")
    assert hit["ok"] is False
    assert hit["need"] == "path"
    assert hit["candidates"] == []
    assert "inbox attachment" in hit["message"]


def test_tool_returns_ask_not_a_path():
    result = execute_tool("quote_find_drawing", {"drawing_path": "missing-sheet.pdf"}, "find-tool")
    assert result["ok"] is False
    assert result["data"]["need"] == "path"
    assert "not a file" in result["speak"]
