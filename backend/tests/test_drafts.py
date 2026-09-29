import json
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


def test_draft_bad_key_rejected():
    r = client.put("/api/drafts/-bad", json={"body": {"x": 1}})
    assert r.status_code == 400
    r2 = client.post("/api/drafts/.hidden", json={"body": {"x": 1}})
    assert r2.status_code == 400


def test_draft_text_plain_post_roundtrip_overwrite():
    client.put("/api/drafts/eng-beacon", json={"body": {"rev": "A"}})
    r = client.post(
        "/api/drafts/eng-beacon",
        content=json.dumps({"body": {"rev": "B", "via": "beacon"}}),
        headers={"Content-Type": "text/plain"},
    )
    assert r.status_code == 200
    assert client.get("/api/drafts/eng-beacon").json()["body"] == {"rev": "B", "via": "beacon"}
