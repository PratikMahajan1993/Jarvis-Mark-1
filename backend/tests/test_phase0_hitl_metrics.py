from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.hitl_meta import blast_radius_for
from app.hermes.hitl import request_human_approval
from app.metrics import metrics_snapshot, new_mission_id, record_hermes_latency, record_mission_step


def setup_module(_module=None):
    db.init_db()


def test_blast_radius_email_is_high():
    score, consequence = blast_radius_for("email_send", {"to": "a@b.com"})
    assert score == 5
    assert "Gmail" in consequence or "email" in consequence.lower()


def test_pending_includes_blast_radius():
    pending = request_human_approval(
        session_id="phase0-blast",
        kind="email_send",
        title="Send: Hi",
        summary="To x@y.com",
        payload={"to": "x@y.com", "subject": "Hi", "body": "Hello"},
        tool_name="draft_email",
    )
    assert pending["irreversibility"] == 5
    assert pending["consequence"]
    row = db.get_pending(pending["id"])
    assert row is not None
    assert row["irreversibility"] == 5
    db.set_pending_status(pending["id"], "rejected")


def test_mission_and_metrics():
    mid = new_mission_id()
    record_mission_step(
        session_id="phase0-metrics",
        mission_id=mid,
        step=0,
        role="prompt",
        detail="hello",
    )
    record_hermes_latency(
        session_id="phase0-metrics",
        transport="gateway",
        casual=True,
        latency_ms=3200,
        ok=True,
    )
    steps = db.list_mission_steps(mission_id=mid)
    assert any(s["role"] == "prompt" for s in steps)
    snap = metrics_snapshot()
    assert "hermes_latency" in snap
    assert snap["targets"]["casual_warm_ms"] == 5000
