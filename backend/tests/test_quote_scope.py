"""Customer scope default, order override, and ask when neither is known."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="jarvis-scope-"))
settings.data_dir = _TMP / "data"
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.exports_dir = _TMP / "exports"
settings.exports_dir.mkdir(parents=True, exist_ok=True)

from app import db
from app.quote import build_quote, get_customer_scope_default, resolve_quote_scope
from app.tools.registry import execute_tool


def setup_module(_module=None):
    db.init_db()


def _customer(name: str, default_scope: str) -> str:
    cid = f"cust-{name.lower()}"
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO customers (id, name, currency, status) VALUES (?, ?, 'INR', 'active')",
            (cid, name),
        )
        conn.execute(
            "INSERT INTO customer_aliases (customer_id, alias, source) VALUES (?, ?, 'test')",
            (cid, name),
        )
        conn.execute(
            """
            INSERT INTO customer_terms (customer_id, default_scope, nda, allow_cloud_vision, quote_validity_days)
            VALUES (?, ?, 0, 0, 30)
            """,
            (cid, default_scope),
        )
    return cid


def test_no_default_asks_and_does_not_build(monkeypatch):
    monkeypatch.setattr(settings, "masterdata_enabled", False)
    result = build_quote(session_id="scope-ask", part_name="Plate", customer="Nobody")
    assert result["ok"] is False
    assert result["need"] == "scope"
    assert result["message"] == "Labour-only or with material?"
    assert "artifact" not in result


def test_customer_default_fills_scope_and_override_wins(monkeypatch):
    monkeypatch.setattr(settings, "masterdata_enabled", True)
    cid = _customer("ScopeLabour Co", "labour")
    assert get_customer_scope_default(customer_id=cid) == "labour"
    filled = build_quote(session_id="scope-default", part_name="Plate", customer="ScopeLabour Co")
    assert filled["ok"] is True
    assert filled["scope"] == "labour"
    assert filled["scope_source"] == "customer"

    overridden = build_quote(
        session_id="scope-override",
        part_name="Plate",
        customer="ScopeLabour Co",
        scope="with_material",
        rm_price=100,
    )
    assert overridden["ok"] is True
    assert overridden["scope"] == "with_material"
    assert overridden["scope_source"] == "override"
    assert any("Raw material" in str(cell) for row in overridden["rows"] for cell in row)


def test_ask_on_terms_means_ask(monkeypatch):
    monkeypatch.setattr(settings, "masterdata_enabled", True)
    _customer("ScopeAsk Co", "ask")
    assert get_customer_scope_default(customer_name="ScopeAsk Co") is None
    result = resolve_quote_scope("scope-ask-terms", customer="ScopeAsk Co")
    assert result["ok"] is False
    assert result["need"] == "scope"


def test_tool_asks():
    result = execute_tool("quote_build", {"part_name": "Plate", "customer": "Blank"}, "scope-tool")
    assert result["ok"] is False
    assert result["data"]["need"] == "scope"
    assert "Labour-only" in result["speak"]
