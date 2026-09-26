from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.hermes import bridge as hb


def _mock_gateway(monkeypatch, *, responses_payload: dict | None = None, responses_timeout: bool = False):
    calls: list[tuple[str, dict]] = []

    class FakeResponse:
        def __init__(self, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload
            self.text = json.dumps(payload)
            self.content = self.text.encode()

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self, timeout=None):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, headers=None, json=None):
            calls.append((url, {"headers": headers or {}, "json": json or {}}))
            if responses_timeout:
                raise httpx.TimeoutException("timed out")
            if "/v1/runs" not in url or url.endswith("/events"):
                raise AssertionError(f"unexpected URL {url}")
            return FakeResponse(202, {"run_id": "run_quote", "status": "started"})

        def stream(self, method, url, headers=None):
            calls.append((url, {"headers": headers or {}, "json": {}}))
            empty = responses_payload is not None and not _extract_text(responses_payload)
            text = "" if empty else "On it."

            class FakeStream:
                status_code = 200

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return False

                def iter_lines(self):
                    if text:
                        yield 'data: {"event":"message.delta","delta":"On it."}'
                    yield 'data: {"event":"run.completed","output":' + json.dumps(text) + "}"

            return FakeStream()

    monkeypatch.setattr(hb, "hermes_gateway_url", lambda: "http://hermes.test")
    monkeypatch.setattr(hb.settings, "hermes_api_key", "test-key")
    monkeypatch.setattr(hb.settings, "hermes_timeout_sec", 30.0)
    monkeypatch.setattr(hb.httpx, "Client", FakeClient)
    return calls


@pytest.fixture
def isolated_sessions(tmp_path, monkeypatch):
    monkeypatch.setattr(hb.settings, "data_dir", tmp_path)
    return tmp_path


def _extract_text(payload: dict) -> str:
    output = payload.get("output")
    if isinstance(output, list):
        for item in output:
            if isinstance(item, dict):
                content = item.get("content")
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("text"):
                            return str(part["text"])
    return ""


def test_quote_start_uses_jarvis_quote_title(isolated_sessions, monkeypatch):
    calls = _mock_gateway(monkeypatch)
    speak, label, _ms = hb._run_via_gateway("start quote workflow", "default", casual=False)
    assert speak == "On it."
    url, req = calls[0]
    assert url.endswith("/v1/runs")
    assert req["json"]["input"] == "start quote workflow"
    assert "messages" not in req["json"]
    assert req["json"]["model_options"]["reasoning_effort"] == "medium"
    assert "session_id" not in req["json"]

    data = json.loads((isolated_sessions / "hermes_sessions.json").read_text(encoding="utf-8"))
    title = data.get("quote:default")
    assert str(title).startswith("jarvis-quote-")
    assert title != "jarvis-default"
    assert data.get("default") is None
    assert data.get(f"hermes:{title}") == label


def test_two_quote_starts_get_distinct_titles(isolated_sessions, monkeypatch):
    def run_start():
        _mock_gateway(monkeypatch)
        hb._run_via_gateway("create a new quote", "default", casual=False)
        data = json.loads((isolated_sessions / "hermes_sessions.json").read_text(encoding="utf-8"))
        return str(data.get("quote:default") or "")

    t1 = run_start()
    t2 = run_start()
    assert t1.startswith("jarvis-quote-")
    assert t2.startswith("jarvis-quote-")
    assert t1 != t2


def test_quote_follow_up_reuses_title(isolated_sessions, monkeypatch):
    _mock_gateway(monkeypatch)
    hb._run_via_gateway("start quote workflow", "default", casual=False)
    stored = json.loads((isolated_sessions / "hermes_sessions.json").read_text())["quote:default"]
    calls = _mock_gateway(monkeypatch)
    hb._run_via_gateway(
        "labour only, customer supplies the material",
        "default",
        casual=False,
    )
    post = next(req for url, req in calls if url.endswith("/v1/runs"))
    data = json.loads((isolated_sessions / "hermes_sessions.json").read_text(encoding="utf-8"))
    assert post["json"]["session_id"] == data.get(f"hermes:{stored}")
    assert post["json"]["input"] == "labour only, customer supplies the material"
    assert "messages" not in post["json"]


def test_mail_turn_does_not_use_quote_title(isolated_sessions, monkeypatch):
    _mock_gateway(monkeypatch)
    hb._run_via_gateway("start quote workflow", "default", casual=False)
    calls = _mock_gateway(monkeypatch)
    hb._run_via_gateway("check my unread mail", "default", casual=False)
    post = calls[0][1]["json"]
    assert post["input"] == "check my unread mail"
    data = json.loads((isolated_sessions / "hermes_sessions.json").read_text(encoding="utf-8"))
    quote_title = data.get("quote:default")
    assert str(quote_title).startswith("jarvis-quote-")
    assert post.get("session_id") != data.get(f"hermes:{quote_title}")


def test_calendar_create_after_quote_uses_default_title(isolated_sessions, monkeypatch):
    _mock_gateway(monkeypatch)
    hb._run_via_gateway("start quote workflow", "default", casual=False)
    calls = _mock_gateway(monkeypatch)
    hb._run_via_gateway("book a call with Rahul at 4pm", "default", casual=False)
    post = calls[0][1]["json"]
    assert post["input"] == "book a call with Rahul at 4pm"
    assert post.get("model_options", {}).get("reasoning_effort") == "low"
    data = json.loads((isolated_sessions / "hermes_sessions.json").read_text(encoding="utf-8"))
    quote_title = data.get("quote:default")
    assert post.get("session_id") != data.get(f"hermes:{quote_title}")


def test_load_hermes_session_unaffected_by_quote_key(isolated_sessions):
    path = isolated_sessions / "hermes_sessions.json"
    path.write_text(
        json.dumps(
            {
                "default": "cli-resume-id-abc",
                "quote:default": "jarvis-quote-deadbeefcafe",
            }
        ),
        encoding="utf-8",
    )
    assert hb._load_hermes_session("default") == "cli-resume-id-abc"


def test_responses_timeout_does_not_call_chat(isolated_sessions, monkeypatch):
    calls = _mock_gateway(monkeypatch, responses_timeout=True)
    with pytest.raises(RuntimeError, match=r"Hermes timed out after"):
        hb._run_via_gateway("start quote workflow", "default", casual=False)
    assert calls
    assert "/v1/runs" in calls[0][0]
    assert all("/v1/chat/completions" not in u for u, _ in calls)
    assert all("/v1/responses" not in u for u, _ in calls)


def test_empty_responses_raises_without_chat(isolated_sessions, monkeypatch):
    calls = _mock_gateway(monkeypatch, responses_payload={"id": "resp_empty", "output": []})
    with pytest.raises(RuntimeError, match="no speakable text"):
        hb._run_via_gateway("start quote workflow", "default", casual=False)
    assert calls
    assert all("/v1/chat/completions" not in u for u, _ in calls)
    assert all("/v1/responses" not in u for u, _ in calls)
