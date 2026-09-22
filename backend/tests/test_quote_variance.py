from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="jarvis-qvar-"))
settings.data_dir = _TMP / "data"
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.exports_dir = _TMP / "exports"
settings.exports_dir.mkdir(parents=True, exist_ok=True)
settings.canvas_dir = _TMP / "data" / "canvas"
settings.canvas_dir.mkdir(parents=True, exist_ok=True)

from app import db  # noqa: E402
from app import quote_variance  # noqa: E402

REV_ID = "qrev_m1_test"
LINE_MAT = "qln_mat_m1"
LINE_MACH = "qln_mach_m1"
LINE_OUT = "qln_out_m1"
LINE_NO_ACT = "qln_no_act_m1"
SOURCE = "erp:job-42"


def setup_module(_module=None):
    db.init_db()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO customers (id, name, gstin, currency, status)
            VALUES ('cust_m1', 'M1 Customer', NULL, 'INR', 'active')
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO quotes (id, customer_id, status)
            VALUES ('quote_m1', 'cust_m1', 'open')
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO quote_revisions (
              id, quote_id, revision, scope, scope_source, qty, currency, total_minor, frozen
            ) VALUES (?, 'quote_m1', 1, 'with_material', 'test', 1, 'INR', 0, 0)
            """,
            (REV_ID,),
        )
        conn.execute("DELETE FROM quote_actuals")
        conn.execute("DELETE FROM quote_lines WHERE quote_revision_id = ?", (REV_ID,))
        conn.executemany(
            """
            INSERT INTO quote_lines (
              id, quote_revision_id, seq, kind, description,
              qty, qty_unit, rate_minor, amount_minor,
              machine_id, time_min, rate_source_kind, rate_source_id,
              is_estimate, estimate_basis
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, 'owner_input', 'test', 0, '')
            """,
            [
                (LINE_MAT, REV_ID, 1, "material", "RM block", 1, "pc", 10000, 10000, None),
                (LINE_MACH, REV_ID, 2, "machining", "VMC cycle", 1, "pc", 5000, 5000, 10.0),
                (LINE_OUT, REV_ID, 3, "outsource", "Heat treat", 1, "lot", 3000, 3000, None),
                (LINE_NO_ACT, REV_ID, 4, "material", "No actual yet", 1, "pc", 2000, 2000, None),
            ],
        )


def test_migration_creates_quote_actuals():
    with db.connect() as conn:
        names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "quote_actuals" in names


def test_line_variance_without_actual_asks():
    out = quote_variance.line_variance(LINE_NO_ACT)
    assert out.get("ask") is True
    assert "delta" not in out


def test_material_line_variance_and_rank():
    quote_variance.record_actual(
        LINE_MAT,
        material_minor_actual=12000,
        scrap_qty=0.5,
        source_ref=SOURCE,
        recorded_at="2026-03-01T10:00:00+00:00",
    )
    out = quote_variance.line_variance(LINE_MAT)
    assert out.get("ask") is not True
    assert out["quoted"]["amount_minor"] == 10000
    assert out["actual"]["material_minor_actual"] == 12000
    assert out["delta"]["amount_minor"] == 2000
    assert out["delta"]["scrap_qty"] == 0.5
    assert out["source_ref"] == SOURCE

    rank = quote_variance.rank_margin_erosion(limit=10)
    ids = [row["quote_line_id"] for row in rank]
    assert LINE_NO_ACT not in ids
    assert rank[0]["quote_line_id"] == LINE_MAT
    assert rank[0]["erosion_minor"] == 2000


def test_machining_variance_uses_cycle_time_ratio():
    quote_variance.record_actual(
        LINE_MACH,
        cycle_min_actual=15.0,
        source_ref="shop:log-1",
    )
    out = quote_variance.line_variance(LINE_MACH)
    assert out["delta"]["time_min"] == 5.0
    assert out["delta"]["amount_minor"] == 2500
    assert out["actual"]["cycle_min_actual"] == 15.0

    rank = quote_variance.rank_margin_erosion(limit=10)
    by_id = {row["quote_line_id"]: row for row in rank}
    assert by_id[LINE_MACH]["erosion_minor"] == 2500


def test_outsource_rank_between_material_and_machining():
    quote_variance.record_actual(
        LINE_OUT,
        outsource_minor_actual=4500,
        source_ref="vendor:inv-9",
    )
    rank = quote_variance.rank_margin_erosion(limit=10)
    erosions = [row["erosion_minor"] for row in rank]
    assert erosions == sorted(erosions, reverse=True)
    assert len(rank) == 3
    assert rank[0]["erosion_minor"] >= rank[1]["erosion_minor"] >= rank[2]["erosion_minor"]


def test_record_actual_unknown_line_raises():
    try:
        quote_variance.record_actual("missing-line", source_ref=SOURCE, material_minor_actual=1)
        raised = False
    except ValueError:
        raised = True
    assert raised
