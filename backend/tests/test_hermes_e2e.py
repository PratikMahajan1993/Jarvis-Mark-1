from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.hermes.bridge import ensure_jarvis_mcp_registered, hermes_available, run_hermes_turn


@pytest.mark.skipif(not hermes_available(), reason="Hermes CLI not on PATH")
def test_hermes_live_pong():
    # Force enabled for this process
    object.__setattr__(settings, "hermes_enabled", True)
    ensure_jarvis_mcp_registered()
    result = run_hermes_turn("Reply with exactly: PONG and nothing else.", session_id="e2e-hermes")
    assert result.speak
    assert "PONG" in result.speak.upper() or result.speak.strip()


@pytest.mark.skipif(not hermes_available(), reason="Hermes CLI not on PATH")
def test_chat_route_uses_hermes_when_enabled():
    from fastapi.testclient import TestClient
    from app.main import app

    object.__setattr__(settings, "hermes_enabled", True)
    client = TestClient(app)
    response = client.post("/api/chat", json={"message": "Say hi in one short sentence.", "session_id": "e2e-chat"})
    assert response.status_code == 200
    data = response.json()
    assert data.get("speak") or data.get("reply")
    health = client.get("/api/health").json()
    assert "hermes" in health
