"""execute_tool classifies handler failures without changing handler bodies."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.tools.registry import HANDLERS, execute_tool

PROBE = "_phase1_error_class_probe"


def setup_module(_module=None):
    db.init_db()


def _run(handler, args=None):
    HANDLERS[PROBE] = handler
    try:
        return execute_tool(PROBE, args or {}, "phase1-error-class")
    finally:
        HANDLERS.pop(PROBE, None)


def test_typeerror_is_validation_not_retryable():
    def handler(session_id: str, qty: int):
        return {"ok": True, "data": qty}

    result = _run(handler)
    assert result["ok"] is False
    assert result["error_class"] == "validation"
    assert result["retryable"] is False
    assert result["error"].startswith(f"Bad arguments for {PROBE}:")


def test_timeout_is_retryable():
    def handler(session_id: str):
        raise httpx.ReadTimeout("gateway slow")

    result = _run(handler)
    assert result["ok"] is False
    assert result["error_class"] == "retryable"
    assert result["retryable"] is True
    assert "gateway slow" in result["error"]


def test_http_error_is_retryable():
    def handler(session_id: str):
        raise httpx.ConnectError("connection refused")

    result = _run(handler)
    assert result["ok"] is False
    assert result["error_class"] == "retryable"
    assert result["retryable"] is True
    assert "connection refused" in result["error"]


def test_other_exception_is_fatal():
    def handler(session_id: str):
        raise RuntimeError("missing column")

    result = _run(handler)
    assert result["ok"] is False
    assert result["error_class"] == "fatal"
    assert result["retryable"] is False
    assert result["error"] == "missing column"
