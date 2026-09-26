from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.shop import state
from app.tools.registry import HANDLERS


def setup_module(_module=None):
    db.init_db()


def _wipe(machine_id: str, component_id: str, vendor: str) -> None:
    with db.connect() as conn:
        conn.execute("DELETE FROM shop_events WHERE machine_id = ?", (machine_id,))
        conn.execute("DELETE FROM shop_events WHERE component_id = ?", (component_id,))
        conn.execute(
            "DELETE FROM shop_events WHERE kind = 'vendor' AND details LIKE ?",
            (f"%{vendor}%",),
        )
        conn.execute("DELETE FROM shop_state WHERE key LIKE ?", (f"floor:machine:{machine_id}",))
        conn.execute("DELETE FROM shop_state WHERE key LIKE ?", (f"floor:stock:{component_id}",))
        conn.execute("DELETE FROM shop_state WHERE key LIKE ?", (f"floor:vendor:{vendor.lower()}",))
        conn.execute("DELETE FROM shop_state WHERE key = ?", ("floor:oee:trend",))


def test_events_project_and_rebuild():
    machine = "M-phase2"
    component = "BRKT-phase2"
    vendor = "AcmePhase2"
    _wipe(machine, component, vendor)
    assert "log_downtime" in HANDLERS
    logged = state.log_downtime(machine, 12, reason="tool change", machine_name="Lathe 1")
    assert logged["ok"] is True
    assert logged["source"] == "manual"
    status = state.get_machine_status(machine)
    assert status["ok"] is True
    assert status["last_downtime_min"] == 12
    assert status["last_downtime_reason"] == "tool change"
    assert status["stale"] is False

    stock = state.log_stock(component, on_hand=10, allocated=4)
    assert stock["ok"] is True
    on_hand = state.get_component_stock(component)
    assert on_hand["on_hand"] == 10
    assert on_hand["allocated"] == 4
    assert on_hand["available"] == 6

    state.log_vendor_turnaround(vendor, 4, last_delivery="2026-09-01")
    state.log_vendor_turnaround(vendor, 6, last_delivery="2026-09-20")
    turn = state.get_vendor_turnaround(vendor)
    assert turn["ok"] is True
    assert turn["avg_days"] == 5
    assert turn["last_delivery"] == "2026-09-20"

    state.log_oee(machine, 81)
    trend = state.get_oee_trend(days=30)
    assert trend["ok"] is True
    assert trend["points"][-1]["oee_pct"] == 81

    with db.connect() as conn:
        conn.execute("DELETE FROM shop_state WHERE key LIKE 'floor:%'")
    assert state.get_machine_status(machine).get("kind") == "ask"
    assert state.rebuild_shop_floor() >= 1
    restored = state.get_machine_status(machine)
    assert restored["last_downtime_min"] == 12
    _wipe(machine, component, vendor)


def test_rebuild_writes_oee_trend_once_from_snapshot(monkeypatch):
    machine_a = "M-oee-a"
    machine_b = "M-oee-b"
    extra_machine = "M-oee-extra"
    _wipe(machine_a, "unused-a", "unused-vendor-a")
    _wipe(machine_b, "unused-b", "unused-vendor-b")
    _wipe(extra_machine, "unused-x", "unused-vendor-x")
    state.log_oee(machine_a, 70)
    state.log_oee(machine_b, 81)

    trend_writes: list[list] = []
    real_save = state._save_floor

    def spy_save(conn, key, kind, data, as_of, event_id):
        if key == "floor:oee:trend":
            trend_writes.append(list(data.get("points") or []))
        return real_save(conn, key, kind, data, as_of, event_id)

    inserted = {"done": False}
    real_apply = state._apply_shop_event

    def wrapping(conn, event, **kwargs):
        real_apply(conn, event, **kwargs)
        if not inserted["done"] and str(event.get("machine_id") or "") == machine_a:
            inserted["done"] = True
            conn.execute(
                """
                INSERT INTO shop_events (
                  id, ts, kind, machine_id, machine_name, component_id,
                  value, unit, details, source, created_at
                ) VALUES (?, ?, 'oee', ?, NULL, NULL, ?, 'pct', NULL, 'manual', ?)
                """,
                (
                    "oee-extra-mid-rebuild",
                    "2099-01-01T00:00:00+00:00",
                    extra_machine,
                    99,
                    "2099-01-01T00:00:00+00:00",
                ),
            )

    monkeypatch.setattr(state, "_save_floor", spy_save)
    monkeypatch.setattr(state, "_apply_shop_event", wrapping)
    try:
        assert state.rebuild_shop_floor() >= 2
        assert inserted["done"] is True
        assert len(trend_writes) == 1
        projected_ids = {point["machine_id"] for point in trend_writes[0]}
        assert machine_a in projected_ids
        assert machine_b in projected_ids
        assert extra_machine not in projected_ids
        snap = state.shop_floor_snapshot()
        assert extra_machine not in {point["machine_id"] for point in snap["oee"]["points"]}
        assert state.get_machine_status(machine_a)["oee_pct"] == 70
        assert state.get_machine_status(machine_b)["oee_pct"] == 81
        assert state.get_machine_status(extra_machine).get("kind") == "ask"
    finally:
        with db.connect() as conn:
            conn.execute("DELETE FROM shop_events WHERE id = ?", ("oee-extra-mid-rebuild",))
        _wipe(machine_a, "unused-a", "unused-vendor-a")
        _wipe(machine_b, "unused-b", "unused-vendor-b")
        _wipe(extra_machine, "unused-x", "unused-vendor-x")
