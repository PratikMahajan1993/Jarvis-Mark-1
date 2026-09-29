import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402

settings.data_dir = Path(tempfile.mkdtemp())

from fastapi.testclient import TestClient  # noqa: E402

from app import db  # noqa: E402
from app.main import app  # noqa: E402

db.init_db()
client = TestClient(app)


def test_draft_roundtrip_and_overwrite():
    assert client.get("/api/drafts/eng-1").json()["body"] == {}
    client.put("/api/drafts/eng-1", json={"body": {"customer": "ACME"}})
    client.post("/api/drafts/eng-1", json={"body": {"customer": "ACME", "rev": "B"}})
    assert client.get("/api/drafts/eng-1").json()["body"] == {"customer": "ACME", "rev": "B"}


def test_draft_too_large_rejected():
    r = client.put("/api/drafts/big", json={"body": {"x": "y" * 70_000}})
    assert r.status_code == 413
