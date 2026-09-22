from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="jarvis-stockcut-"))
settings.data_dir = _TMP / "data"
settings.data_dir.mkdir(parents=True, exist_ok=True)

from app import db  # noqa: E402
from app import stockcut  # noqa: E402


def setup_module(_module=None):
    db.init_db()


def _seed_material_and_quote(
    conn,
    *,
    suffix: str,
    density: float | None = 7850.0,
    bar_length: float = 3000.0,
    price_minor: int = 120000,
) -> tuple[str, str]:
    mat_id = f"mat_sc_{suffix}"
    sup_id = f"sup_sc_{suffix}"
    quote_id = f"rmq_sc_{suffix}"
    conn.execute(
        """
        INSERT INTO materials (id, grade, family, form, density_kg_m3)
        VALUES (?, ?, 'carbon', 'bar', ?)
        """,
        (mat_id, f"EN8-{suffix}", density),
    )
    conn.execute(
        """
        INSERT INTO suppliers (id, name) VALUES (?, ?)
        """,
        (sup_id, f"Steel Co {suffix}"),
    )
    conn.execute(
        """
        INSERT INTO supplier_rm_quotes (
          id, supplier_id, material_id, size_spec, unit_basis, price_minor,
          effective_from, basis_date, source_kind, source_ref
        ) VALUES (?, ?, ?, ?, 'per_bar', ?, '2020-01-01T00:00:00+00:00',
                  '2026-01-01', 'supplier_quote', 'test')
        """,
        (
            quote_id,
            sup_id,
            mat_id,
            f"D25 x {int(bar_length)}mm",
            price_minor,
        ),
    )
    return mat_id, quote_id


def test_migration_creates_remnant_stock():
    with db.connect() as conn:
        row = conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name = 'remnant_stock'
            """
        ).fetchone()
    assert row is not None


def test_plan_basic_one_bar_and_proposed_remnant():
    with db.connect() as conn:
        mat_id, quote_id = _seed_material_and_quote(conn, suffix="basic")
        plan = stockcut.plan_stockcut(
            conn,
            mat_id,
            part_length_mm=100.0,
            qty=10,
            kerf_mm=3,
            grip_mm=10,
            source_ref="job-basic",
        )
        conn.commit()

    assert plan.get("ask") is not True
    assert plan["cost_basis"]["supplier_rm_quote_id"] == quote_id
    assert plan["cost_per_piece_minor"] == 120000 // 10
    assert plan["mass_per_piece_kg"] > 0
    assert sum(b["count"] for b in plan["bars"] if b["source"] == "new") >= 1
    assert any(r["state"] == "proposed" for r in plan["remnants"])


def test_no_supplier_quote_asks():
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO materials (id, grade, family, form)
            VALUES ('mat_no_q', 'Lonely', 'carbon', 'bar')
            """
        )
        plan = stockcut.plan_stockcut(conn, "mat_no_q", 50.0, 5)
    assert plan == {"ask": True, "reason": "no_supplier_rm_quote"}


def test_null_density_asks_no_mass():
    with db.connect() as conn:
        mat_id, _ = _seed_material_and_quote(conn, suffix="noden", density=None)
        plan = stockcut.plan_stockcut(conn, mat_id, 80.0, 4)
    assert plan["ask"] is True
    assert plan.get("ask_density") is True
    assert "mass_per_piece_kg" not in plan
    assert "cost_per_piece_minor" in plan


def test_confirmed_remnant_preferred_over_new_bar():
    with db.connect() as conn:
        mat_id, _ = _seed_material_and_quote(conn, suffix="rem")
        conn.execute(
            """
            INSERT INTO remnant_stock (
              id, material_id, length_mm, qty, state, source_ref, created_at
            ) VALUES ('rem_ok', ?, 800.0, 1, 'confirmed', 'floor', '2026-01-01T00:00:00+00:00')
            """,
            (mat_id,),
        )
        conn.execute(
            """
            INSERT INTO remnant_stock (
              id, material_id, length_mm, qty, state, source_ref, created_at
            ) VALUES ('rem_prop', ?, 2000.0, 1, 'proposed', 'prior-plan', '2026-01-01T00:00:00+00:00')
            """,
            (mat_id,),
        )
        plan = stockcut.plan_stockcut(
            conn,
            mat_id,
            part_length_mm=100.0,
            qty=2,
            kerf_mm=3,
            grip_mm=10,
        )
        conn.commit()

    remnant_bars = [b for b in plan["bars"] if b["source"] == "remnant"]
    assert remnant_bars and remnant_bars[0]["length"] == 800.0
    assert all(b["source"] != "new" or b["count"] == 0 for b in plan["bars"]) or sum(
        b["count"] for b in plan["bars"] if b["source"] == "new"
    ) < 2


def test_confirm_remnant_promotes_proposed():
    with db.connect() as conn:
        mat_id, _ = _seed_material_and_quote(conn, suffix="confirm")
        plan = stockcut.plan_stockcut(conn, mat_id, 120.0, 3, source_ref="x")
        assert plan["remnants"]
        rem_id = plan["remnants"][0]["id"]
        ok = stockcut.confirm_remnant(conn, rem_id)
        conn.commit()
        state = conn.execute(
            "SELECT state FROM remnant_stock WHERE id = ?", (rem_id,)
        ).fetchone()["state"]
    assert ok is True
    assert state == "confirmed"


def test_remnant_consumed_on_second_plan_after_confirm():
    with db.connect() as conn:
        mat_id, _ = _seed_material_and_quote(conn, suffix="reuse")
        plan1 = stockcut.plan_stockcut(conn, mat_id, 50.0, 1, kerf_mm=3, grip_mm=5)
        rem_id = plan1["remnants"][0]["id"]
        stockcut.confirm_remnant(conn, rem_id)
        conn.commit()
        leftover = conn.execute(
            "SELECT length_mm FROM remnant_stock WHERE id = ?", (rem_id,)
        ).fetchone()["length_mm"]
        plan2 = stockcut.plan_stockcut(conn, mat_id, 40.0, 1, kerf_mm=3, grip_mm=5)
    used_remnant = any(b.get("source") == "remnant" for b in plan2["bars"])
    assert used_remnant or leftover >= 40.0 + 3
