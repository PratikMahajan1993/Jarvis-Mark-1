from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.quote_run_log import record, seed_markdown


def test_quote_run_log_writes_jsonl_and_markdown(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    work_dir = tmp_path / "work"
    data_dir.mkdir()
    work_dir.mkdir()
    jsonl = data_dir / "quote_run.jsonl"
    md = work_dir / "QUOTE_RUN.md"
    monkeypatch.setattr(settings, "data_dir", data_dir)
    monkeypatch.setattr("app.quote_run_log._jsonl_path", jsonl)
    monkeypatch.setattr("app.quote_run_log._md_path", md)

    record(
        kind="chat_in",
        session_id="quote-session",
        fields={
            "message": "quote this drawing",
            "password": "secret-pass",
            "api_key": "sk-test",
        },
    )

    assert jsonl.is_file()
    lines = [json.loads(ln) for ln in jsonl.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1
    assert lines[0]["kind"] == "chat_in"
    assert lines[0]["fields"]["password"] == "<redacted>"
    assert lines[0]["fields"]["api_key"] == "<redacted>"
    assert lines[0]["fields"]["message"] == "quote this drawing"

    assert md.is_file()
    text = md.read_text(encoding="utf-8")
    assert "Quote run log" in text
    assert "quote-workflow debug log" in text.lower()
    assert "chat_in" in text
    assert "quote this drawing" in text
    assert "secret-pass" not in text
    assert "sk-test" not in text


def test_seed_markdown_creates_header(tmp_path, monkeypatch):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    md = work_dir / "QUOTE_RUN.md"
    monkeypatch.setattr("app.quote_run_log._md_path", md)

    seed_markdown()

    assert md.is_file()
    text = md.read_text(encoding="utf-8")
    assert text.startswith("# Quote run log")
    assert "Waiting for the first turn" in text
