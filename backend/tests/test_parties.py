from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="jarvis-parties-"))
settings.data_dir = _TMP / "data"
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.exports_dir = _TMP / "exports"
settings.exports_dir.mkdir(parents=True, exist_ok=True)
settings.canvas_dir = _TMP / "data" / "canvas"
settings.canvas_dir.mkdir(parents=True, exist_ok=True)

from app import db  # noqa: E402
from app.masterdata import import_client_names_from_markdown  # noqa: E402
from app.quote import build_quote, quote_to_pdf, verify_quote  # noqa: E402


def setup_module(_module=None):
    db.init_db()


def _send_ready(session: str, *, customer: str) -> None:
    db.add_memory(session, "last_quote_drawing", "fixture-drawing.pdf")
    db.add_memory(session, "last_quote_delivery_days", "10")
    db.add_memory(session, "last_quote_rm_basis_date", "2026-01-15")
    build_quote(
        session_id=session,
        part_name="Bracket",
        material="EN8",
        customer=customer,
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


def _insert_customer_alias(*, customer_id: str, name: str, alias: str) -> None:
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO customers (id, name, gstin, currency, status)
            VALUES (?, ?, NULL, 'INR', 'active')
            """,
            (customer_id, name),
        )
        conn.execute(
            """
            INSERT INTO customer_aliases (customer_id, alias, source)
            VALUES (?, ?, 'test-fixture')
            """,
            (customer_id, alias),
        )


def test_masterdata_alias_passes_unknown_blocks(monkeypatch):
    monkeypatch.setattr(settings, "masterdata_enabled", True)
    _insert_customer_alias(
        customer_id="cust_test_fixture",
        name="Fixture Manufacturing Ltd",
        alias="FixCo",
    )
    session_ok = "s1-spell-alias-ok"
    _send_ready(session_ok, customer="FixCo")
    ok = verify_quote(session_id=session_ok, stage="send")
    spell_ok = {c["id"]: c for c in ok["checks"]}["customer_spelling"]
    assert spell_ok["pass"] is True
    assert spell_ok["source"] == "customer_aliases"

    session_bad = "s1-spell-unknown"
    _send_ready(session_bad, customer="Not A Real Customer ZZZ")
    bad = verify_quote(session_id=session_bad, stage="send")
    spell_bad = {c["id"]: c for c in bad["checks"]}["customer_spelling"]
    assert spell_bad["pass"] is False
    assert spell_bad["severity"] == "BLOCKER"
    assert bad["verdict"] == "block"


def test_import_client_names_idempotent(tmp_path):
    md = tmp_path / "client-names.md"
    md.write_text("# names\n- Alpha Co\n- Beta Ltd\n", encoding="utf-8")
    with db.connect() as conn:
        first = import_client_names_from_markdown(conn, md)
        second = import_client_names_from_markdown(conn, md)
        n_aliases = conn.execute("SELECT COUNT(*) AS n FROM customer_aliases").fetchone()["n"]
    assert first == 2
    assert second == 0
    assert n_aliases >= 2


def test_empty_markdown_imports_nothing(tmp_path):
    md = tmp_path / "empty.md"
    md.write_text("# Client name spellings (placeholder — no secrets)\n\nAdd owner-confirmed spellings here.\n", encoding="utf-8")
    with db.connect() as conn:
        added = import_client_names_from_markdown(conn, md)
    assert added == 0
