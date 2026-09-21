from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agent import _run_agent
from app.gemini_client import _casual_payload
from app.semantic_router import try_obvious_casual


def test_obvious_casual_greeting_skips_router_gemini():
    hit = try_obvious_casual("Hey Jarvis, how's your evening?")
    assert hit is not None
    assert hit.intent == "casual_chat"

    called = {"n": 0}

    async def _boom(*_a, **_k):
        called["n"] += 1
        raise RuntimeError("router gemini should not run")

    with patch("app.semantic_router.classify_intent", side_effect=_boom):
        import asyncio
        from app.semantic_router import classify_intent

        result = try_obvious_casual("Hey Jarvis, how's your evening?")
        assert result.intent == "casual_chat"
        assert called["n"] == 0


def test_casual_payload_no_tools_thinking_budget_zero():
    body = _casual_payload([{"role": "user", "content": "Hi"}], temperature=0.9, max_output_tokens=120)
    assert "tools" not in body
    assert body["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 0}
    assert body["generationConfig"]["maxOutputTokens"] == 120


def test_casual_chat_route_skips_hermes():
    from app import db

    db.init_db()
    session = "test-casual-no-hermes-pytest"
    from app.semantic_router import IntentClassification

    route = IntentClassification(intent="casual_chat", target_agent="RES.01", confidence=0.99)

    with patch("app.hermes.bridge.run_hermes_turn") as hermes:
        with patch("app.gemini_client.chat_casual") as casual:
            casual.return_value = {"role": "assistant", "content": "Evening, Sir — crisp and quiet.", "tool_calls": []}
            with patch("app.brain.health", return_value={"model_ready": True, "provider": "gemini"}):
                with patch("app.brain.provider", return_value="gemini"):
                    resp = _run_agent("Hey there", session, route=route)
    hermes.assert_not_called()
    assert "Evening" in (resp.speak or "")
