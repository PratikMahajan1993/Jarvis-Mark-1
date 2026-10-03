from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.drafts import save_draft
from app.features.sheets.draft import (
    ModelError,
    edit_model,
    empty_model,
    get_model,
    model_key,
    normalize_model,
    outline,
    put_model,
    structure_only,
)


def _reset() -> None:
    db.init_db()
    with db.connect() as conn:
        conn.execute(
            "DELETE FROM drafts WHERE key = ? OR key LIKE ? OR key LIKE ?",
            ("sheets.current", "sheets.model.%", "sheets.template.%"),
        )


def test_empty_model_when_nothing_is_stored():
    _reset()
    loaded = get_model()
    assert loaded["model"] == empty_model()
    assert loaded["model"]["new_file"] is True


def test_header_only_draft_is_retired_and_not_loaded():
    _reset()
    with pytest.raises(ModelError):
        normalize_model({"workbook_title": "Production data 2026", "tab_title": "Reports", "columns": []})
    save_draft(
        model_key("default"),
        {
            "workbook_title": "Production data 2026",
            "tab_title": "Reports",
            "columns": [{"name": "Date"}],
        },
    )
    loaded = get_model()
    assert loaded["model"] is None
    assert "retired" in loaded["error"]


def test_put_model_keeps_formula_text_and_sample_rows():
    _reset()
    saved = put_model(
        {
            "title": " Attendance ",
            "tabs": [
                {
                    "title": "October",
                    "blocks": [
                        {
                            "kind": "table",
                            "columns": [
                                {"name": "Hours", "kind": "number", "filled_by": "staff"},
                                {
                                    "name": "Pay",
                                    "kind": "formula",
                                    "filled_by": "jarvis",
                                    "formula": "Hours * Rate",
                                },
                            ],
                            "rows": [{"Hours": 8}],
                        }
                    ],
                }
            ],
        }
    )
    columns = saved["model"]["tabs"][0]["blocks"][0]["columns"]
    assert saved["model"]["title"] == "Attendance"
    assert saved["model"]["new_file"] is True
    assert columns[0]["formula"] == ""
    assert columns[1]["formula"] == "Hours * Rate"
    assert saved["model"]["tabs"][0]["blocks"][0]["rows"] == [{"Hours": 8}]
    assert "Attendance" in outline(saved["model"])


def test_formula_cannot_store_a_cell_reference():
    with pytest.raises(ModelError):
        normalize_model(
            {
                "title": "Attendance",
                "tabs": [
                    {
                        "title": "October",
                        "blocks": [
                            {
                                "kind": "table",
                                "columns": [{"name": "Pay", "kind": "formula", "formula": "B2*C2"}],
                            }
                        ],
                    }
                ],
            }
        )


def test_duplicate_column_is_rejected():
    with pytest.raises(ModelError):
        normalize_model(
            {
                "title": "Attendance",
                "tabs": [
                    {
                        "title": "October",
                        "blocks": [
                            {"kind": "table", "columns": [{"name": "Qty"}, {"name": "qty"}]}
                        ],
                    }
                ],
            }
        )


def test_structure_only_drops_sample_rows():
    model = normalize_model(
        {
            "title": "Attendance",
            "tabs": [
                {
                    "title": "October",
                    "blocks": [
                        {
                            "kind": "title",
                            "text": "October attendance",
                        },
                        {
                            "kind": "table",
                            "columns": [
                                {"name": "Hours", "kind": "number"},
                                {"name": "Pay", "kind": "formula", "formula": "Hours * 100"},
                            ],
                            "rows": [{"Hours": 8}],
                        },
                    ],
                }
            ],
        }
    )
    cleaned = structure_only(model)
    table = cleaned["tabs"][0]["blocks"][1]
    assert table["rows"] == []
    assert table["columns"][1]["formula"] == "Hours * 100"
    assert cleaned["tabs"][0]["blocks"][0]["text"] == "October attendance"
