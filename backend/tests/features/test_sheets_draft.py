from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.features.sheets.draft import DraftError, empty_draft, get_draft, normalize_draft, put_draft


def _reset() -> None:
    db.init_db()
    with db.connect() as conn:
        conn.execute("DELETE FROM drafts WHERE key = ?", ("sheets.current",))


def test_empty_draft_when_nothing_is_stored():
    _reset()
    loaded = get_draft()
    assert loaded["draft"] == empty_draft()


def test_put_draft_keeps_headers_and_drops_formula_on_text():
    _reset()
    saved = put_draft(
        {
            "workbook_title": " Production data 2026 ",
            "tab_title": "Reports 2026-10",
            "columns": [
                {"name": "Date", "kind": "date", "filled_by": "staff", "formula": "ignored"},
                {"name": "Attainment", "kind": "formula", "filled_by": "jarvis", "formula": "actual/plan"},
            ],
        }
    )
    assert saved["draft"]["workbook_title"] == "Production data 2026"
    assert saved["draft"]["columns"][0]["formula"] == ""
    assert saved["draft"]["columns"][1]["formula"] == "actual/plan"
    assert get_draft()["draft"]["tab_title"] == "Reports 2026-10"


def test_duplicate_column_is_rejected():
    with pytest.raises(DraftError):
        normalize_draft({"columns": [{"name": "Qty"}, {"name": "qty"}]})
