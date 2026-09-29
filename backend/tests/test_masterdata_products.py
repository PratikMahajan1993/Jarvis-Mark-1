"""Product create/supersede, duplicate refusal, NDA defaults, attest gate, playbook install."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings

PAGE = ROOT.parent / "frontend" / "src" / "components" / "masterdata" / "MasterDataScreen.tsx"


def setup_module(_module=None):
    tmp = Path(tempfile.mkdtemp(prefix="jarvis-md-products-"))
    settings.data_dir = tmp / "data"
    settings.exports_dir = tmp / "exports"
    settings.canvas_dir = settings.data_dir / "canvas"
    for path in (settings.data_dir, settings.exports_dir, settings.canvas_dir):
        path.mkdir(parents=True, exist_ok=True)
    from app import db
    from app.masterdata.seed_master_data import seed_master_data

    db.init_db()
    with db.connect() as conn:
        seed_master_data(conn)


def test_products_tab_on_masterdata_screen():
    text = PAGE.read_text(encoding="utf-8")
    assert "Products" in text
    assert "ProductTable" in text


def test_create_product_and_supersede():
    from app import db
    from app.masterdata.lifecycle import supersede_product
    from app.masterdata.writes import create_customer, create_product

    with db.connect() as conn:
        cust = create_customer(conn, {"name": "Priya Metals", "nda": "yes"}, notify=False)
        created = create_product(
            conn,
            {
                "name": "Shaft housing",
                "product_number": "PN-100",
                "customer_id": cust["id"],
                "uom": "ea",
                "monitor_stock": "yes",
            },
            notify=False,
        )
        assert created["ok"] is True
        row = conn.execute("SELECT * FROM products WHERE id = ?", (created["id"],)).fetchone()
        assert row["product_number"] == "PN-100"
        assert row["monitor_stock"] == 1
        assert row["status"] == "active"

        new_id = supersede_product(
            conn,
            created["id"],
            {
                "name": "Shaft housing v2",
                "product_number": "PN-100",
                "customer_id": cust["id"],
                "uom": "ea",
                "monitor_stock": "no",
            },
        )
        old = conn.execute("SELECT * FROM products WHERE id = ?", (created["id"],)).fetchone()
        successor = conn.execute("SELECT * FROM products WHERE id = ?", (new_id,)).fetchone()
    assert old["status"] == "superseded"
    assert old["effective_to"]
    assert old["superseded_by"] == new_id
    assert successor["name"] == "Shaft housing v2"
    assert successor["monitor_stock"] == 0
    assert successor["status"] == "active"


def test_duplicate_customer_supplier_product_refuse_existing():
    from app import db
    from app.masterdata.writes import DuplicateError, create_customer, create_product, create_supplier

    with db.connect() as conn:
        first = create_customer(conn, {"name": "Dup Co", "nda": "no"}, notify=False)
        try:
            create_customer(conn, {"name": "Dup Co", "nda": "yes"}, notify=False)
            raise AssertionError("expected DuplicateError")
        except DuplicateError as exc:
            assert exc.existing["id"] == first["id"]
            assert "already exists" in str(exc)

        sup = create_supplier(conn, {"name": "Dup Supply"}, notify=False)
        try:
            create_supplier(conn, {"name": "Dup Supply"}, notify=False)
            raise AssertionError("expected DuplicateError")
        except DuplicateError as exc:
            assert exc.existing["id"] == sup["id"]

        prod = create_product(
            conn,
            {
                "name": "Bracket",
                "product_number": "DUP-1",
                "customer_id": first["id"],
                "uom": "ea",
                "monitor_stock": "no",
            },
            notify=False,
        )
        try:
            create_product(
                conn,
                {
                    "name": "Other",
                    "product_number": "DUP-1",
                    "customer_id": first["id"],
                    "uom": "ea",
                    "monitor_stock": "yes",
                },
                notify=False,
            )
            raise AssertionError("expected DuplicateError")
        except DuplicateError as exc:
            assert exc.existing["id"] == prod["id"]


def test_nda_yes_denies_cloud_vision_and_no_clears_both():
    from app import db
    from app.masterdata.writes import create_customer

    with db.connect() as conn:
        yes = create_customer(conn, {"name": "NDA Yes LLC", "nda": "yes"}, notify=False)
        no = create_customer(conn, {"name": "NDA No LLC", "nda": "no"}, notify=False)
        yes_terms = conn.execute(
            "SELECT nda, allow_cloud_vision, default_scope FROM customer_terms WHERE customer_id = ?",
            (yes["id"],),
        ).fetchone()
        no_terms = conn.execute(
            "SELECT nda, allow_cloud_vision, default_scope FROM customer_terms WHERE customer_id = ?",
            (no["id"],),
        ).fetchone()
    assert yes_terms["nda"] == 1
    assert yes_terms["allow_cloud_vision"] == 0
    assert yes_terms["default_scope"] == "ask"
    assert no_terms["nda"] == 0
    assert no_terms["allow_cloud_vision"] == 0
    assert no_terms["default_scope"] == "ask"


def test_api_duplicate_returns_existing_not_sql_error(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setattr(settings, "hermes_enabled", False)

    with TestClient(app) as client:
        created = client.post("/api/masterdata/customers", json={"fields": {"name": "Api Dup", "nda": "no"}})
        assert created.status_code == 200
        dup = client.post("/api/masterdata/customers", json={"fields": {"name": "Api Dup", "nda": "yes"}})
        assert dup.status_code == 409
        detail = dup.json()["detail"]
        assert detail["duplicate"] is True
        assert detail["existing"]["name"] == "Api Dup"
        assert "UNIQUE" not in str(detail).upper()


def test_jarvis_mhr_attest_rate_refuses_non_owner(monkeypatch):
    from app.hermes import mcp_server

    monkeypatch.setattr(settings, "telegram_owner_user_ids", "111,222")
    refused = json.loads(mcp_server.jarvis_mhr_attest_rate("VMC", "Owner", telegram_user_id="999"))
    assert refused["ok"] is False
    assert "refused" in refused["error"].lower()

    monkeypatch.setattr(settings, "telegram_owner_user_ids", "")
    closed = json.loads(mcp_server.jarvis_mhr_attest_rate("VMC", "Owner", telegram_user_id="111"))
    assert closed["ok"] is False


def test_ensure_playbooks_installed_copies_masterdata(tmp_path, monkeypatch):
    from app.hermes.bridge import ensure_playbooks_installed

    monkeypatch.setattr(settings, "hermes_home", str(tmp_path / "hermes"))
    ok = ensure_playbooks_installed()
    assert ok is True
    quote = tmp_path / "hermes" / "skills" / "shop" / "quote" / "SKILL.md"
    master = tmp_path / "hermes" / "skills" / "shop" / "masterdata" / "SKILL.md"
    assert quote.is_file()
    assert master.is_file()
    text = master.read_text(encoding="utf-8")
    assert "shop-masterdata" in text
    assert "jarvis_masterdata_create_customer" in text
