"""Runs desk: fake Hermes SSE, cancel, Authorize, queued quote send, local extract."""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.briefing import build_briefing, read_morning_cache, store_morning_brief
from app.config import settings
from app.extract_text import DRAWING_REFUSAL, ExtractError, extract_local_text
from app.hermes import bridge as hb
from app.hermes.live import LiveRun, request_stop
from app.hermes.runs import approval_action, consume_hermes_run, reasoning_effort_for, stop_hermes_run
from app.quote import queue_quote_send


def _fake_client(lines: list[str], posts: list[tuple[str, dict]]):
    class FakeResponse:
        status_code = 202
        text = '{"run_id":"run_fake","status":"started"}'
        content = text.encode()

        def json(self):
            return {"run_id": "run_fake", "status": "started"}

    class FakeStream:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def iter_lines(self):
            yield from lines

    class FakeClient:
        def __init__(self, timeout=None):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, headers=None, json=None):
            posts.append((url, json or {}))
            return FakeResponse()

        def stream(self, method, url, headers=None):
            return FakeStream()

    return FakeClient


def test_tool_line_before_final_sentence_and_reasoning_is_not_spoken(monkeypatch):
    posts: list[tuple[str, dict]] = []
    lines = [
        ": keepalive",
        'data: {"event":"reasoning.available","text":"hidden chain of thought"}',
        'data: {"event":"tool.started","tool":"jarvis_search_emails","preview":"inbox"}',
        'data: {"event":"message.delta","delta":"The inbox is clear."}',
        'data: {"event":"run.completed","output":"The inbox is clear."}',
        ": stream closed",
    ]
    monkeypatch.setattr("app.hermes.runs.httpx.Client", _fake_client(lines, posts))
    monkeypatch.setattr("app.hermes.runs.settings.hermes_api_key", "test-key")
    speak, session, _ms, events = consume_hermes_run(
        base_url="http://hermes.test",
        message="check my unread mail",
        session_id="stored-session",
        instructions="batch with execute_code",
        casual=False,
        timeout=30,
    )
    assert posts[0][0].endswith("/v1/runs")
    body = posts[0][1]
    assert body["input"] == "check my unread mail"
    assert body["session_id"] == "stored-session"
    assert "messages" not in body
    assert body["model_options"]["reasoning_effort"] == "low"
    names = [event["event"] for event in events]
    assert names.index("tool.started") < names.index("message.delta")
    assert events[0]["message"] == "reading mail"
    assert speak == "The inbox is clear."
    assert "hidden chain" not in speak
    assert session == "stored-session"


def test_cancel_calls_stop(monkeypatch):
    calls: list[str] = []

    class FakeResponse:
        status_code = 200
        text = '{"status":"stopping"}'

        def json(self):
            return {"status": "stopping"}

    class FakeClient:
        def __init__(self, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, headers=None, json=None):
            calls.append(url)
            return FakeResponse()

    monkeypatch.setattr("app.hermes.runs.httpx.Client", FakeClient)
    monkeypatch.setattr("app.hermes.runs.settings.hermes_gateway_url", "http://hermes.test")
    monkeypatch.setattr("app.hermes.runs.settings.hermes_api_key", "test-key")
    run = LiveRun(jarvis_id="jr_1", session_id="default", hermes_run_id="run_abc")
    result = request_stop(run)
    assert result["status"] == "stopping"
    assert run.cancelled.is_set()
    assert calls == ["http://hermes.test/v1/runs/run_abc/stop"]
    assert stop_hermes_run("run_abc").get("status") == "stopping"


def test_approval_event_is_an_authorize_card():
    action = approval_action(
        {"event": "approval.request", "request_id": "req-9", "command": "run the batch"},
        "jr_desk",
    )
    assert action["kind"] == "hermes_approval"
    assert action["title"] == "Authorize Hermes"
    assert action["payload"]["run_id"] == "jr_desk"
    assert action["payload"]["request_id"] == "req-9"
    assert "run the batch" in action["summary"]


def test_reasoning_effort_tiers():
    assert reasoning_effort_for("hey", casual=True) == "minimal"
    assert reasoning_effort_for("check my unread mail", casual=False) == "low"
    assert reasoning_effort_for("start quote workflow", casual=False) == "medium"


def test_execute_code_instructions_batch_shop_work():
    text = hb._instructions(False, "default", "what is on the shop sheet")
    assert "execute_code" in text
    assert "queue Authorize" in text
    skill = (ROOT / "app" / "hermes" / "playbooks" / "quote" / "SKILL.md").read_text(encoding="utf-8")
    assert "execute_code" in skill
    assert "does not send" in skill


def test_quote_send_is_queued_not_sent(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    db.init_db()
    sent: list[str] = []

    def _no_send(*_args, **_kwargs):
        sent.append("sent")
        raise AssertionError("quote send must not call the mailer")

    monkeypatch.setattr("app.connectors.email.send_email", _no_send)
    pdf = tmp_path / "quote.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    result = queue_quote_send(
        session_id="quote-hitl",
        to="buyer@example.com",
        subject="Quotation — Bracket",
        body="Total Quoted Cost: 10",
        pdf_path=str(pdf),
    )
    assert result["queued"] is True
    assert result["sent"] is False
    assert sent == []
    pending = db.list_pending("quote-hitl")
    assert len(pending) == 1
    assert pending[0]["kind"] == "quote_send"
    assert pending[0]["status"] == "pending"


def test_extraction_does_not_call_a_model(tmp_path, monkeypatch):
    called: list[str] = []

    def _boom(*_args, **_kwargs):
        called.append("model")
        raise AssertionError("extraction must not call a model")

    monkeypatch.setattr("app.gemini_client.chat", _boom, raising=False)
    monkeypatch.setattr("app.gemini_client.chat_casual", _boom, raising=False)
    note = tmp_path / "note.txt"
    note.write_text("Plain note for the casual card.", encoding="utf-8")
    assert extract_local_text(note, "note.txt") == "Plain note for the casual card."
    docx = tmp_path / "note.docx"
    xml = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>"
        "<w:body><w:p><w:r><w:t>Word line</w:t></w:r></w:p></w:body></w:document>"
    )
    with zipfile.ZipFile(docx, "w") as archive:
        archive.writestr("word/document.xml", xml)
    assert extract_local_text(docx, "note.docx") == "Word line"

    def _empty_pages(_path):
        return ["", "   "]

    monkeypatch.setattr("app.extract_text._pdf_pages_pdftotext", _empty_pages)
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    with pytest.raises(ExtractError, match="no text layer") as scanned:
        extract_local_text(pdf, "scan.pdf")
    assert scanned.value.drawing is True
    assert "orb" in DRAWING_REFUSAL

    png = tmp_path / "part.png"
    png.write_bytes(b"\x89PNG\r\n")
    with pytest.raises(ExtractError) as drawing:
        extract_local_text(png, "part.png")
    assert drawing.value.drawing is True
    assert called == []


def test_morning_cache_and_live_brief_when_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    db.init_db()
    facts = {
        "slot": "Morning",
        "name": "Sir",
        "priority_mail": [],
        "next_event": None,
        "unread_total": 0,
        "date_subtitle": "Saturday",
        "weather_speak": "",
    }
    monkeypatch.setattr("app.briefing.gather_briefing_facts", lambda: facts)
    assert read_morning_cache() is None
    live = build_briefing()
    assert "Morning" in live["speak"]
    stored = store_morning_brief()
    cached = read_morning_cache()
    assert cached is not None
    assert cached["cached"] is True
    assert cached["speak"] == stored["speak"]


def test_reason_rfq_refuses_without_drawing_anchor():
    from app.rfq import reason_rfq_has_anchor
    from app.tools.registry import _reason_rfq

    assert reason_rfq_has_anchor(message="what's in this RFQ") is False
    assert reason_rfq_has_anchor(mail_id="mail-1") is True
    assert reason_rfq_has_anchor(message=r"D:\drawings\part.pdf") is True
    result = _reason_rfq("sess", message="what's in this RFQ")
    assert result["ok"] is True
    assert result["data"]["refused"] is True
    assert "Which drawing" in result["speak"]


def test_runs_timeout_is_a_runtime_error(monkeypatch):
    class FakeClient:
        def __init__(self, timeout=None):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, headers=None, json=None):
            raise httpx.TimeoutException("timed out")

    monkeypatch.setattr("app.hermes.runs.httpx.Client", FakeClient)
    with pytest.raises(RuntimeError, match="timed out after 30s"):
        consume_hermes_run(
            base_url="http://hermes.test",
            message="start quote workflow",
            session_id=None,
            instructions="",
            casual=False,
            timeout=30,
        )
