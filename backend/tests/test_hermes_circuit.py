"""Hermes circuit breaker and the casual gateway timeout cap."""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.hermes import bridge as hb
from app.hermes.circuit_breaker import CLOSED, OPEN, CircuitBreaker, gateway_circuit


@pytest.fixture(autouse=True)
def _reset_gateway_circuit():
    gateway_circuit.reset()
    previous = gateway_circuit._now
    yield
    gateway_circuit._now = previous
    gateway_circuit.reset()


def test_opens_after_three_consecutive_failures_and_success_resets():
    breaker = CircuitBreaker(now=lambda: 0.0)
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CLOSED
    breaker.record_success()
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CLOSED
    breaker.record_failure()
    assert breaker.state == OPEN
    assert breaker.failures == 3


def test_closed_health_success_does_not_clear_request_failures():
    breaker = CircuitBreaker(now=lambda: 0.0)
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.before_health_probe() is True
    breaker.after_health_probe(True)
    assert breaker.state == CLOSED
    assert breaker.failures == 2
    breaker.record_failure()
    assert breaker.state == OPEN


def test_half_open_allows_one_probe():
    clock = {"t": 0.0}
    breaker = CircuitBreaker(now=lambda: clock["t"])
    for _ in range(3):
        breaker.record_failure()
    assert breaker.before_health_probe() is False

    clock["t"] = 59.0
    assert breaker.before_health_probe() is False

    clock["t"] = 60.0
    results: list[bool] = []
    barrier = threading.Barrier(8)

    def _worker() -> None:
        barrier.wait()
        results.append(breaker.before_health_probe())

    threads = [threading.Thread(target=_worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results.count(True) == 1

    breaker.after_health_probe(False)
    assert breaker.state == OPEN
    assert breaker.before_health_probe() is False

    clock["t"] = 120.0
    assert breaker.before_health_probe() is True
    breaker.after_health_probe(True)
    assert breaker.state == CLOSED
    assert breaker.failures == 0


def test_open_circuit_skips_health_and_uses_hermes_miss(monkeypatch):
    clock = {"t": 1000.0}
    gateway_circuit._now = lambda: clock["t"]
    for _ in range(3):
        gateway_circuit.record_failure()
    calls: list[str] = []

    class FakeClient:
        def __init__(self, timeout=None):
            calls.append(f"init:{timeout}")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url):
            calls.append(url)
            raise AssertionError("health probe should be skipped")

    monkeypatch.setattr(hb.settings, "hermes_enabled", True)
    monkeypatch.setattr(hb.settings, "hermes_prefer_gateway", True)
    monkeypatch.setattr(hb.settings, "hermes_api_key", "test-key")
    monkeypatch.setattr(hb.settings, "hermes_gateway_url", "http://hermes.test")
    monkeypatch.setattr(hb.httpx, "Client", FakeClient)

    assert hb.hermes_gateway_reachable() is False
    with pytest.raises(RuntimeError, match="soft fallback to legacy chat"):
        hb.run_hermes_turn("hello", "circuit-session", casual=True)
    assert calls == []


def test_half_open_probe_is_the_health_check(monkeypatch):
    clock = {"t": 50.0}
    gateway_circuit._now = lambda: clock["t"]
    for _ in range(3):
        gateway_circuit.record_failure()
    probes: list[str] = []

    class FakeResponse:
        status_code = 503

    class FakeClient:
        def __init__(self, timeout=None):
            probes.append(f"timeout:{timeout}")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url):
            probes.append(url)
            return FakeResponse()

    monkeypatch.setattr(hb.settings, "hermes_api_key", "test-key")
    monkeypatch.setattr(hb.settings, "hermes_gateway_url", "http://hermes.test")
    monkeypatch.setattr(hb.httpx, "Client", FakeClient)

    assert hb.hermes_gateway_reachable() is False
    assert probes == []

    clock["t"] = 110.0
    assert hb.hermes_gateway_reachable() is False
    assert probes == ["timeout:1.5", "http://hermes.test/health"]
    assert gateway_circuit.state == OPEN

    assert hb.hermes_gateway_reachable() is False
    assert len(probes) == 2

    clock["t"] = 170.0
    FakeResponse.status_code = 200
    assert hb.hermes_gateway_reachable() is True
    assert gateway_circuit.state == CLOSED
    assert probes[-1] == "http://hermes.test/health"


class _GatewayResponse:
    def __init__(self, payload: dict):
        self.status_code = 200
        self._payload = payload
        self.content = b"{}"
        self.text = "{}"

    def json(self):
        return self._payload


def test_casual_gateway_timeout_caps_at_12s_tool_ops_stay_30(monkeypatch):
    timeouts: list[float] = []

    class FakeClient:
        def __init__(self, timeout=None):
            timeouts.append(float(timeout))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, headers=None, json=None):
            if "/v1/runs" not in url:
                raise AssertionError(url)
            effort = ((json or {}).get("model_options") or {}).get("reasoning_effort")
            self._speak = "Hello." if effort == "minimal" else "On it."
            return _GatewayResponse({"run_id": "run_cap", "status": "started"})

        def stream(self, method, url, headers=None):
            speak = self._speak

            class _Stream:
                status_code = 200

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return False

                def iter_lines(self):
                    payload = json.dumps({"event": "message.delta", "delta": speak})
                    yield f"data: {payload}"
                    done = json.dumps({"event": "run.completed", "output": speak})
                    yield f"data: {done}"

            return _Stream()

    monkeypatch.setattr(hb.settings, "hermes_timeout_sec", 30.0)
    monkeypatch.setattr(hb.settings, "hermes_api_key", "test-key")
    monkeypatch.setattr(hb, "hermes_gateway_url", lambda: "http://hermes.test")
    monkeypatch.setattr(hb.db, "recent_messages", lambda session_id, limit=16: [])
    monkeypatch.setattr(
        hb, "hermes_conversation_title", lambda message, session_id: "jarvis-default"
    )
    monkeypatch.setattr(hb.httpx, "Client", FakeClient)

    speak, _label, _ms = hb._run_via_gateway("hello there", "casual-cap", casual=True)
    assert speak == "Hello."
    speak, _label, _ms = hb._run_via_gateway("check my unread mail", "tool-ops", casual=False)
    assert speak == "On it."
    assert timeouts == [hb.CASUAL_GATEWAY_TIMEOUT_SEC, 30.0]
    assert hb.CASUAL_GATEWAY_TIMEOUT_SEC == 12.0
    assert hb.settings.hermes_timeout_sec == 30.0


def test_gateway_timeout_counts_as_failure_without_shortening_tool_ops(monkeypatch):
    seen: list[float] = []

    class FakeClient:
        def __init__(self, timeout=None):
            seen.append(float(timeout))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, headers=None, json=None):
            raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(hb.settings, "hermes_timeout_sec", 30.0)
    monkeypatch.setattr(hb, "hermes_gateway_url", lambda: "http://hermes.test")
    monkeypatch.setattr(
        hb, "hermes_conversation_title", lambda message, session_id: "jarvis-quote-test"
    )
    monkeypatch.setattr(hb.httpx, "Client", FakeClient)

    with pytest.raises(RuntimeError, match="timed out after 30s"):
        hb._run_via_gateway("start quote workflow", "quote-cap", casual=False)
    assert seen == [30.0]
    assert gateway_circuit.failures == 1
    assert gateway_circuit.state == CLOSED
