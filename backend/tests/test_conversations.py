from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings

settings.data_dir = Path(tempfile.mkdtemp(prefix="jarvis-conv-"))
settings.data_dir.mkdir(parents=True, exist_ok=True)

from app import db
from app.conversation_voice import match_query, parse_window_command
from app.conversations import (
    _is_media_reject,
    _looks_text_extract,
    _media_variants,
    create,
    expand,
    list_desk,
    list_public,
    minimize,
    public_row,
    start_discussion,
    start_or_resume_workflow,
)


def test_create_and_expand_cap():
    db.init_db()
    first = create("drawing", "Piston", {"filename": "piston.pdf"})
    second = create("drawing", "Housing", {"filename": "housing.pdf"})
    third = create("discussion", "Soft jaws", {})
    fourth = create("workflow", "RFQ Bracket", {"resume_key": "t1"})
    assert first["session_id"].startswith("conv-")
    items = {row["id"]: row for row in list_public()}
    expanded = [row for row in items.values() if not row["minimized"] and row["status"] != "archived"]
    assert len(expanded) <= 3, [row["title"] for row in expanded]
    assert items[fourth["id"]]["minimized"] is False
    assert items[first["id"]]["minimized"] is True
    assert items[second["id"]]["minimized"] is False
    assert items[third["id"]]["minimized"] is False


def test_minimize_then_expand():
    db.init_db()
    row = create("drawing", "Piston", {"local_name": "DPIS.pdf"})
    closed = minimize(row["id"])
    assert closed and closed["minimized"] is True
    opened = expand(row["id"])
    assert opened and opened["minimized"] is False


def test_window_voice():
    assert parse_window_command("hide conversations")["action"] == "hide_dock"
    assert parse_window_command("show the dock")["action"] == "show_dock"
    mini = parse_window_command("minimize the drawing")
    assert mini and mini["action"] == "minimize"
    opened = parse_window_command("open the piston chat")
    assert opened and opened["action"] == "expand"
    rows = [{"title": "Piston", "category": "drawing", "focus": {"filename": "DPIS.pdf"}}]
    assert match_query("piston", rows)["title"] == "Piston"
    assert parse_window_command("check my mail") is None


def test_media_reject_and_raster_preference():
    assert _is_media_reject(Exception("INVALID_ARGUMENT: Unable to process input pdf"))
    assert not _is_media_reject(Exception("quota exceeded"))
    assert _looks_text_extract("extracted text from the pdf, no image")
    assert not _looks_text_extract("Title block Piston, front view, section A-A")
    row = {
        "id": "x",
        "focus": {"filename": "missing.pdf", "prefer_raster": True},
    }
    variants = _media_variants(row)
    assert variants
    assert variants[0][1] != "image/png"


def test_public_row_has_session():
    db.init_db()
    row = create("drawing", "Piston", {"filename": "piston.pdf"})
    packed = public_row(db.get_conversation(row["id"]))
    assert packed["session_id"] == row["session_id"]
    assert packed["category"] == "drawing"
    assert packed["kind_label"] == "Drawing"


def test_desk_discussion_and_workflow_resume():
    db.init_db()
    talk = start_discussion("Machining strategies")
    assert talk["category"] == "discussion"
    assert talk["session_id"].startswith("conv-")
    assert talk["kind_label"] == "Discussion"

    job = start_or_resume_workflow(
        title="RFQ · Bracket",
        focus={"task_id": "t1"},
        resume_key="task:t1",
    )
    assert job["category"] == "workflow"
    again = start_or_resume_workflow(
        title="RFQ · Bracket v2",
        focus={"task_id": "t1", "extra": 1},
        resume_key="task:t1",
    )
    assert again["id"] == job["id"]
    assert again["focus"].get("extra") == 1

    create("mail", "Should hide", {})
    desk = list_desk()
    ids = {row["id"] for row in desk}
    assert talk["id"] in ids
    assert job["id"] in ids
    assert all(row["category"] in {"discussion", "workflow", "drawing"} for row in desk)


if __name__ == "__main__":
    tests = [
        test_create_and_expand_cap,
        test_minimize_then_expand,
        test_window_voice,
        test_media_reject_and_raster_preference,
        test_public_row_has_session,
        test_desk_discussion_and_workflow_resume,
    ]
    for test in tests:
        test()
        print("ok", test.__name__)
    print(f"passed {len(tests)}")
