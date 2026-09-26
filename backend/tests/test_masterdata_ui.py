"""Master Data API contract used by the /masterdata page."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings

PAGE = ROOT.parent / "frontend" / "src" / "components" / "masterdata" / "MasterDataScreen.tsx"


def setup_module(_module=None):
    tmp = Path(tempfile.mkdtemp(prefix="jarvis-md-ui-"))
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


def test_page_exposes_six_tabs_and_replace():
    text = PAGE.read_text(encoding="utf-8")
    for label in ("Customers", "Machines", "Materials", "Suppliers", "MHR Floors", "Outsource Vendors"):
        assert label in text
    screen = (ROOT.parent / "frontend" / "src" / "app" / "masterdata" / "page.tsx").read_text(encoding="utf-8")
    assert "MasterDataScreen" in screen
    customer = (ROOT.parent / "frontend" / "src" / "components" / "masterdata" / "CustomerTable.tsx").read_text(encoding="utf-8")
    assert "Replace" in customer
    assert "Delete" not in customer


def test_crud_replace_refuses_delete_and_options(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setattr(settings, "hermes_enabled", False)

    with TestClient(app) as client:
        listed = client.get("/api/masterdata/customers")
        assert listed.status_code == 200
        names = {item["name"] for item in listed.json()["items"]}
        assert "Deepak" in names
        created = client.post("/api/masterdata/customers", json={"fields": {"name": "Harbour Works", "default_scope": "labour"}})
        assert created.status_code == 200
        new_id = created.json()["id"]
        replaced = client.patch(f"/api/masterdata/customers/{new_id}", json={"fields": {"name": "Harbour Works Pvt", "default_scope": "labour"}})
        assert replaced.status_code == 200
        after = client.get("/api/masterdata/customers").json()["items"]
        old = next(item for item in after if item["id"] == new_id)
        assert old["status"] == "superseded"
        denied = client.delete(f"/api/masterdata/customers/{new_id}")
        assert denied.status_code == 409
        options = client.get("/api/masterdata/options")
        assert options.status_code == 200
        assert any(row["grade"] == "EN8" for row in options.json()["materials"])
        deepak = next(item for item in after if item["name"] == "Deepak")
        alias = client.post(
            "/api/masterdata/aliases",
            json={"kind": "customer", "canonical_id": deepak["id"], "alias": "Dee-Deepak", "source": "manual"},
        )
        assert alias.status_code == 200
        resolved = client.get("/api/masterdata/resolve", params={"kind": "customer", "alias": "Dee-Deepak"})
        assert resolved.json()["canonical_id"] == deepak["id"]
        guess = client.get("/api/masterdata/resolve", params={"kind": "customer", "alias": "Deep"})
        assert guess.json()["canonical_id"] is None
