from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="jarvis-backup-"))
settings.data_dir = _TMP / "data"
settings.exports_dir = _TMP / "exports"
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.exports_dir.mkdir(parents=True, exist_ok=True)

from app import backup, db  # noqa: E402


def _fresh_db() -> None:
    path = settings.db_path
    if path.exists():
        path.unlink()
    db.init_db()


def test_init_db_records_integrity_ok():
    _fresh_db()
    assert backup.last_integrity_status() == "ok"


def test_backup_and_restore_drill():
    """Rehearsed restore: backup → wipe live db → restore copy → boot check."""
    _fresh_db()
    session = "restore-drill"
    db.add_message(session, "user", "drill-marker")

    backup_dir = _TMP / "backups-drill"
    snapshot = backup.backup_database(backup_dir, keep=7)
    assert snapshot.is_file()

    with db.connect() as conn:
        assert backup.run_integrity_check(conn) == "ok"

    live = settings.db_path
    live.unlink()
    assert not live.exists()

    backup.restore_database_from_backup(snapshot)
    assert live.is_file()

    db.init_db()
    assert backup.last_integrity_status() == "ok"
    rows = db.recent_messages(session, limit=5)
    assert any(r["content"] == "drill-marker" for r in rows)


def test_backup_retention_prunes_old_files():
    _fresh_db()
    dest = _TMP / "backups-retention"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir()

    paths = [backup.backup_database(dest, keep=2) for _ in range(3)]
    remaining = sorted(dest.glob("jarvis-*.db"))
    assert len(remaining) == 2
    assert paths[-1] in remaining
    assert paths[-2] in remaining


def test_archive_sent_quote_temp_pdf():
    _fresh_db()
    archive_dir = _TMP / "quote-archive"
    pdf = _TMP / "fake-quote.pdf"
    pdf.write_bytes(b"%PDF-1.4 drill bytes")

    payload = {"quote_id": "q-drill", "customer": "Test Co", "total": 1234.5}
    result = backup.archive_sent_quote(pdf, payload, archive_dir)

    assert len(result["sha256"]) == 64
    archived_pdf = Path(result["pdf"])
    archived_json = Path(result["json"])
    assert archived_pdf.read_bytes() == pdf.read_bytes()
    loaded = json.loads(archived_json.read_text(encoding="utf-8"))
    assert loaded == payload

    with pytest.raises(backup.ArchiveExistsError):
        backup.archive_sent_quote(pdf, payload, archive_dir)
