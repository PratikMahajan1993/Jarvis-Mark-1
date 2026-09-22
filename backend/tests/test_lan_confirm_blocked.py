"""LAN clients cannot mutate the API without allowlist + bearer token."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SESSION_ID = "lan-auth-test-session"


def test_lan_post_confirm_returns_401():
    from app.main import app

    with TestClient(app, client=("192.168.1.50", 50000)) as client:
        resp = client.post(
            "/api/confirm",
            json={
                "session_id": SESSION_ID,
                "action_id": f"missing-{uuid.uuid4().hex}",
                "approved": False,
            },
        )
    assert resp.status_code == 401


def test_local_testclient_post_confirm_not_401():
    from app.main import app

    with TestClient(app) as client:
        resp = client.post(
            "/api/confirm",
            json={
                "session_id": SESSION_ID,
                "action_id": f"missing-{uuid.uuid4().hex}",
                "approved": False,
            },
        )
    assert resp.status_code != 401
