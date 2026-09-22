from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="jarvis-mhr-"))
settings.data_dir = _TMP / "data"
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.exports_dir = _TMP / "exports"
settings.exports_dir.mkdir(parents=True, exist_ok=True)
settings.canvas_dir = _TMP / "data" / "canvas"
settings.canvas_dir.mkdir(parents=True, exist_ok=True)

from app import db  # noqa: E402
from app.masterdata import (  # noqa: E402
    import_mhr_demo_from_markdown,
    min_mhr_minor_as_of,
    mhr_demo_floor_rupees_as_of,
)
from app.masterdata.import_mhr_demo import MhrDemoImportError  # noqa: E402
from app.masterdata.mhr_lookup import machine_hour_rate_as_of, mhr_rate_is_sendable_as_of  # noqa: E402
from app.quote import build_quote, quote_to_pdf, verify_quote  # noqa: E402


def setup_module(_module=None):
    db.init_db()


def _insert_temporal_fixture(conn) -> None:
    conn.execute(
        """
        INSERT INTO machines (
          id, name, machine_type, control_make, control_model, status
        ) VALUES ('mach_temporal', 'Temporal Mill', 'Temporal Mill', 'demo', 'demo', 'running')
        """
    )
    conn.execute(
        """
        INSERT INTO machine_hour_rates (
          id, machine_id, machine_type, min_mhr_minor, currency,
          effective_from, effective_to, source_kind, source_ref
        ) VALUES (
          'mhr_jan', 'mach_temporal', 'Temporal Mill', 100000, 'INR',
          '2026-01-01', '2026-03-01', 'demo', 'test-fixture'
        )
        """
    )
    conn.execute(
        """
        INSERT INTO machine_hour_rates (
          id, machine_id, machine_type, min_mhr_minor, currency,
          effective_from, effective_to, source_kind, source_ref
        ) VALUES (
          'mhr_mar', 'mach_temporal', 'Temporal Mill', 85000, 'INR',
          '2026-03-01', NULL, 'demo', 'test-fixture'
        )
        """
    )


def test_as_of_returns_march_floor_not_expired_row():
    with db.connect() as conn:
        _insert_temporal_fixture(conn)
        feb = min_mhr_minor_as_of(conn, machine_type="Temporal Mill", as_of="2026-02-15")
        mar = min_mhr_minor_as_of(conn, machine_type="Temporal Mill", as_of="2026-03-15")
        expired_boundary = min_mhr_minor_as_of(conn, machine_type="Temporal Mill", as_of="2026-03-01")
    assert feb == 100_000
    assert mar == 85_000
    assert expired_boundary == 85_000


def test_as_of_rupees_conversion():
    with db.connect() as conn:
        floor = mhr_demo_floor_rupees_as_of(conn, "Temporal Mill", "2026-03-20")
    assert floor == 850.0


def test_import_mhr_demo_idempotent(tmp_path):
    md = tmp_path / "mhr-demo.md"
    md.write_text(
        "# demo\n| Machine type | Minimum MHR (INR/hr) |\n| --- | --- |\n"
        "| Idempotent Test Mill | 720 |\n",
        encoding="utf-8",
    )
    with db.connect() as conn:
        first = import_mhr_demo_from_markdown(conn, md)
        second = import_mhr_demo_from_markdown(conn, md)
        minor = conn.execute(
            """
            SELECT min_mhr_minor FROM machine_hour_rates
            WHERE machine_type = 'Idempotent Test Mill'
            """
        ).fetchone()["min_mhr_minor"]
        n_rates = conn.execute(
            """
            SELECT COUNT(*) AS n FROM machine_hour_rates
            WHERE machine_type = 'Idempotent Test Mill'
            """
        ).fetchone()["n"]
    assert first == 1
    assert second == 0
    assert minor == 72_000
    assert n_rates == 1


def _send_ready(session: str, *, machine: str, rate: str) -> None:
    db.add_memory(session, "last_quote_drawing", "fixture-drawing.pdf")
    db.add_memory(session, "last_quote_delivery_days", "10")
    db.add_memory(session, "last_quote_rm_basis_date", "2026-01-15")
    db.add_memory(session, "last_quote_machine", machine)
    db.add_memory(session, "last_quote_machining_rate", rate)
    build_quote(
        session_id=session,
        part_name="Bracket",
        material="EN8",
        customer="Deepak",
        scope="with_material",
        rm_price="4200",
        line_items=[
            {
                "item": "Bracket",
                "material": "EN8",
                "qty": 2,
                "unit_price": 1500,
                "notes": "From drawing",
            }
        ],
    )
    quote_to_pdf(session_id=session, part_name="Bracket")


def test_masterdata_missing_floor_blocks_send(monkeypatch):
    monkeypatch.setattr(settings, "masterdata_enabled", True)
    session = "s2-mhr-missing"
    _send_ready(session, machine="Unknown demo type", rate="900")
    result = verify_quote(session_id=session, stage="send")
    mhr = {c["id"]: c for c in result["checks"]}["mhr_demo_floor"]
    assert mhr["pass"] is False
    assert mhr["severity"] == "BLOCKER"
    assert result["verdict"] == "block"


def test_masterdata_expired_floor_blocks_send(monkeypatch):
    monkeypatch.setattr(settings, "masterdata_enabled", True)
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO machines (
              id, name, machine_type, control_make, control_model, status
            ) VALUES ('mach_exp', 'Expired Only', 'Expired Only', 'demo', 'demo', 'running')
            """
        )
        conn.execute(
            """
            INSERT INTO machine_hour_rates (
              id, machine_id, machine_type, min_mhr_minor, currency,
              effective_from, effective_to, source_kind, source_ref
            ) VALUES (
              'mhr_exp', 'mach_exp', 'Expired Only', 90000, 'INR',
              '2020-01-01', '2021-01-01', 'demo', 'test-fixture'
            )
            """
        )
    session = "s2-mhr-expired"
    _send_ready(session, machine="Expired Only", rate="950")
    result = verify_quote(session_id=session, stage="send")
    mhr = {c["id"]: c for c in result["checks"]}["mhr_demo_floor"]
    assert mhr["pass"] is False
    assert result["verdict"] == "block"


def test_masterdata_rate_below_imported_floor_blocks(monkeypatch):
    monkeypatch.setattr(settings, "masterdata_enabled", True)
    session = "s2-mhr-below"
    _send_ready(session, machine="Demo CNC vertical mill", rate="400")
    result = verify_quote(session_id=session, stage="send")
    mhr = {c["id"]: c for c in result["checks"]}["mhr_demo_floor"]
    assert mhr["pass"] is False
    assert mhr["source"] == "machine_hour_rates"
    assert result["verdict"] == "block"


def _attested_md(tmp_path, *, machine: str, rate: int, attested_by: str, attested_on: str) -> Path:
    md = tmp_path / "mhr-attested.md"
    md.write_text(
        "# demo\n"
        "| Machine type | Minimum MHR (INR/hr) | attested_by | attested_on |\n"
        "| --- | --- | --- | --- |\n"
        f"| {machine} | {rate} | {attested_by} | {attested_on} |\n",
        encoding="utf-8",
    )
    return md


def test_unattested_imported_floor_blocks_send_even_above_rate(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "masterdata_enabled", True)
    md = tmp_path / "mhr-unattested.md"
    md.write_text(
        "# demo\n| Machine type | Minimum MHR (INR/hr) |\n| --- | --- |\n"
        "| Attest Block Mill | 500 |\n",
        encoding="utf-8",
    )
    with db.connect() as conn:
        import_mhr_demo_from_markdown(conn, md)
    session = "s5-unattested"
    _send_ready(session, machine="Attest Block Mill", rate="900")
    result = verify_quote(session_id=session, stage="send")
    mhr = {c["id"]: c for c in result["checks"]}["mhr_demo_floor"]
    assert mhr["pass"] is False
    assert mhr["severity"] == "BLOCKER"
    assert "not owner-attested" in mhr["evidence"]
    assert result["verdict"] == "block"


def test_shipped_seed_value_blocks_send(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "masterdata_enabled", True)
    md = _attested_md(
        tmp_path,
        machine="Seed Block Mill",
        rate=600,
        attested_by="owner",
        attested_on="2026-01-10",
    )
    with db.connect() as conn:
        import_mhr_demo_from_markdown(conn, md)
        row = machine_hour_rate_as_of(conn, machine_type="Seed Block Mill", as_of="2026-03-01")
        assert row is not None
        assert row["min_mhr_minor"] == row["shipped_seed_value_minor"]
        assert not mhr_rate_is_sendable_as_of(row)
    session = "s5-seed-block"
    _send_ready(session, machine="Seed Block Mill", rate="900")
    result = verify_quote(session_id=session, stage="send")
    mhr = {c["id"]: c for c in result["checks"]}["mhr_demo_floor"]
    assert mhr["pass"] is False
    assert "shipped demo seed" in mhr["evidence"]
    assert result["verdict"] == "block"


def test_attested_different_value_passes_floor_check(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "masterdata_enabled", True)
    md = tmp_path / "mhr-two-step.md"
    md.write_text(
        "# demo\n| Machine type | Minimum MHR (INR/hr) |\n| --- | --- |\n"
        "| Real Rate Mill | 700 |\n",
        encoding="utf-8",
    )
    with db.connect() as conn:
        import_mhr_demo_from_markdown(conn, md)
    md.write_text(
        "# demo\n"
        "| Machine type | Minimum MHR (INR/hr) | attested_by | attested_on |\n"
        "| --- | --- | --- | --- |\n"
        "| Real Rate Mill | 820 | owner | 2026-02-01 |\n",
        encoding="utf-8",
    )
    with db.connect() as conn:
        import_mhr_demo_from_markdown(conn, md)
        as_of = datetime.now(ZoneInfo(settings.tz)).date().isoformat()
        row = machine_hour_rate_as_of(conn, machine_type="Real Rate Mill", as_of=as_of)
        assert mhr_rate_is_sendable_as_of(row)
        assert row["min_mhr_minor"] == 82_000
    session = "s5-attested-pass"
    _send_ready(session, machine="Real Rate Mill", rate="900")
    result = verify_quote(session_id=session, stage="send")
    mhr = {c["id"]: c for c in result["checks"]}["mhr_demo_floor"]
    assert mhr["pass"] is True
    assert "attested 2026-02-01" in mhr["evidence"]


def test_malformed_row_fails_import_leaves_table_unchanged(tmp_path):
    good = tmp_path / "good.md"
    good.write_text(
        "# demo\n| Machine type | Minimum MHR (INR/hr) |\n| --- | --- |\n"
        "| Malform Guard Mill | 640 |\n",
        encoding="utf-8",
    )
    with db.connect() as conn:
        import_mhr_demo_from_markdown(conn, good)
        before = conn.execute(
            "SELECT COUNT(*) AS n FROM machine_hour_rates WHERE machine_type = ?",
            ("Malform Guard Mill",),
        ).fetchone()["n"]
    bad = tmp_path / "bad.md"
    bad.write_text(
        "# demo\n| Machine type | Minimum MHR (INR/hr) |\n| --- | --- |\n"
        "| Malform Guard Mill | not-a-number |\n",
        encoding="utf-8",
    )
    with db.connect() as conn:
        try:
            import_mhr_demo_from_markdown(conn, bad)
        except MhrDemoImportError:
            pass
        else:
            raise AssertionError("expected import to fail closed")
        after = conn.execute(
            "SELECT COUNT(*) AS n FROM machine_hour_rates WHERE machine_type = ?",
            ("Malform Guard Mill",),
        ).fetchone()["n"]
        minor = conn.execute(
            "SELECT min_mhr_minor FROM machine_hour_rates WHERE machine_type = ?",
            ("Malform Guard Mill",),
        ).fetchone()["min_mhr_minor"]
    assert before == after == 1
    assert minor == 64_000


def test_backwards_attested_on_fails_import(tmp_path):
    md = tmp_path / "mhr-backwards.md"
    md.write_text(
        "# demo\n"
        "| Machine type | Minimum MHR (INR/hr) | attested_by | attested_on |\n"
        "| --- | --- | --- | --- |\n"
        "| Backwards Mill | 700 | owner | 2026-03-01 |\n",
        encoding="utf-8",
    )
    with db.connect() as conn:
        import_mhr_demo_from_markdown(conn, md)
    md.write_text(
        "# demo\n"
        "| Machine type | Minimum MHR (INR/hr) | attested_by | attested_on |\n"
        "| --- | --- | --- | --- |\n"
        "| Backwards Mill | 710 | owner | 2026-02-01 |\n",
        encoding="utf-8",
    )
    with db.connect() as conn:
        try:
            import_mhr_demo_from_markdown(conn, md)
        except MhrDemoImportError as exc:
            assert "backwards" in str(exc).lower()
        else:
            raise AssertionError("expected backwards attested_on to fail")
        row = machine_hour_rate_as_of(conn, machine_type="Backwards Mill", as_of="2026-04-01")
        assert row is not None
        assert row["min_mhr_minor"] == 70_000
