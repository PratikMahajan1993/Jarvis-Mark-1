from __future__ import annotations

import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.agent import (
    HitlPostProviderCrash,
    _POST_EXTERNAL_PROVIDER_HOOK,
    reconcile_external_effects_on_boot,
    resolve_pending,
)
from app.hermes.hitl import request_human_approval


def setup_module(_module=None):
    db.init_db()


def _queue_email_send(session: str, *, tag: str) -> dict:
    return request_human_approval(
        session_id=session,
        kind="email_compose",
        title="Send test mail",
        summary="Claim-once test",
        payload={
            "to": "ops@example.com",
            "subject": f"Claim once {tag}",
            "body": f"Hello from the claim-once test ({tag}).",
        },
        tool_name="draft_email",
    )


def test_five_concurrent_confirms_one_provider_call():
    session = f"claim-once-{uuid.uuid4().hex[:8]}"
    pending = _queue_email_send(session, tag="concurrent")
    calls: list[str] = []

    def fake_send(*_args, **_kwargs):
        calls.append("send")
        return {"id": "fake-sent-id", "thread_id": "t1"}

    with patch("app.connectors.email.send_email", side_effect=fake_send):
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [
                pool.submit(resolve_pending, pending["id"], True, session)
                for _ in range(5)
            ]
            results = [f.result() for f in as_completed(futures)]

    assert len(calls) == 1
    already = sum(1 for r in results if "already handled" in r.speak.lower())
    assert already == 4
    row = db.get_pending(pending["id"])
    assert row and row["status"] == "executed"


def test_fault_injection_parks_needs_human_and_skips_resend():
    session = f"fault-{uuid.uuid4().hex[:8]}"
    pending = _queue_email_send(session, tag="fault")
    send_calls: list[str] = []

    def fake_send(*_args, **_kwargs):
        send_calls.append("send")
        return {"id": "fake-sent-id", "thread_id": "t1"}

    def crash_before_status(_action_id: str) -> None:
        raise HitlPostProviderCrash("simulated crash before status write")

    import app.agent as agent_mod

    agent_mod._POST_EXTERNAL_PROVIDER_HOOK = crash_before_status
    try:
        with patch("app.connectors.email.send_email", side_effect=fake_send):
            try:
                resolve_pending(pending["id"], True, session)
            except HitlPostProviderCrash:
                pass
        reconcile_external_effects_on_boot()
        row = db.get_pending(pending["id"])
        assert row and row["status"] == "needs_human"
        assert len(send_calls) == 1

        with patch("app.connectors.email.send_email", side_effect=fake_send) as second:
            out = resolve_pending(pending["id"], True, session)
            assert "already handled" in out.speak.lower()
            assert second.call_count == 0
    finally:
        agent_mod._POST_EXTERNAL_PROVIDER_HOOK = None


def test_confirm_idempotency_key_replays_response():
    from fastapi.testclient import TestClient

    from app.config import settings
    from app.main import app

    session = f"idem-{uuid.uuid4().hex[:8]}"
    pending = _queue_email_send(session, tag="idem")
    idem = f"confirm-{uuid.uuid4().hex}"

    with patch("app.connectors.email.send_email", return_value={"id": "x", "thread_id": "t"}):
        with patch("app.voicebox.prefetch_tts", lambda *_a, **_k: None):
            with TestClient(app) as client:
                first = client.post(
                    "/api/confirm",
                    json={"session_id": session, "action_id": pending["id"], "approved": True},
                    headers={"Idempotency-Key": idem},
                )
                second = client.post(
                    "/api/confirm",
                    json={"session_id": session, "action_id": pending["id"], "approved": True},
                    headers={"Idempotency-Key": idem},
                )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    with db.connect() as conn:
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM confirm_idempotency WHERE idempotency_key = ?",
            (idem,),
        ).fetchone()["n"]
    assert n == 1
