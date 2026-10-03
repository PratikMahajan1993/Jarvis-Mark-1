from __future__ import annotations

import pytest

from app.features.sheets.compile import CompileError, _FILL_ROWS, column_letter, compile_formula, compile_model


def _table_model() -> dict:
    return {
        "title": "Attendance",
        "new_file": True,
        "tabs": [
            {
                "title": "October",
                "blocks": [
                    {
                        "kind": "table",
                        "columns": [
                            {"name": "Name", "kind": "text", "filled_by": "staff", "formula": "", "dropdown": []},
                            {"name": "Hours", "kind": "number", "filled_by": "staff", "formula": "", "dropdown": []},
                            {"name": "Rate", "kind": "number", "filled_by": "owner", "formula": "", "dropdown": []},
                            {
                                "name": "Pay",
                                "kind": "formula",
                                "filled_by": "jarvis",
                                "formula": "Hours * Rate",
                                "dropdown": [],
                            },
                        ],
                        "rows": [{"Name": "Ada", "Hours": 8}],
                    }
                ],
            }
        ],
    }


def _numbers(requests: list[dict]) -> list:
    found = []
    for item in requests:
        cells = item.get("updateCells")
        if not cells:
            continue
        for row in cells.get("rows") or []:
            for cell in row.get("values") or []:
                value = (cell.get("userEnteredValue") or {}).get("numberValue")
                if value is not None:
                    found.append(value)
    return found


def _formulas(requests: list[dict]) -> list[str]:
    found = []
    for item in requests:
        cells = item.get("updateCells")
        if not cells:
            continue
        for row in cells.get("rows") or []:
            for cell in row.get("values") or []:
                formula = (cell.get("userEnteredValue") or {}).get("formulaValue")
                if formula:
                    found.append(formula)
    return found


def test_column_letter_and_formula_use_names():
    assert column_letter(0) == "A"
    assert column_letter(1) == "B"
    columns = [{"name": "Name"}, {"name": "H"}, {"name": "Hours"}]
    assert compile_formula("Hours * 100", columns, 2).replace(" ", "") == "=C2*100"
    with pytest.raises(CompileError):
        compile_formula("B2*C2", [{"name": "Hours"}], 2)


def test_compile_writes_stored_numbers_and_named_formulas_only():
    requests = compile_model(_table_model())
    formulas = [item.replace(" ", "") for item in _formulas(requests)]
    assert formulas[0] == "=B2*C2"
    assert formulas[-1] == f"=B{_FILL_ROWS + 1}*C{_FILL_ROWS + 1}"
    assert len(formulas) == _FILL_ROWS
    assert _numbers(requests) == [8]
    sheet = next(item["updateSheetProperties"] for item in requests if "updateSheetProperties" in item)
    assert sheet["properties"]["sheetId"] == 0
    assert sheet["properties"]["title"] == "October"
    assert sheet["properties"]["gridProperties"]["frozenRowCount"] == 1
    assert not any("addSheet" in item for item in requests)


def test_second_tab_is_a_new_sheet_on_the_same_new_file():
    model = _table_model()
    model["tabs"].append(
        {
            "title": "November",
            "blocks": [{"kind": "title", "text": "Next month"}],
        }
    )
    requests = compile_model(model)
    added = [item["addSheet"] for item in requests if "addSheet" in item]
    assert len(added) == 1
    assert added[0]["properties"]["sheetId"] == 1
    assert added[0]["properties"]["title"] == "November"
    assert "spreadsheetId" not in str(requests)


def test_dropdown_and_chart_are_in_the_batch():
    model = _table_model()
    model["tabs"][0]["blocks"][0]["columns"][0]["dropdown"] = ["Present", "Absent"]
    model["tabs"][0]["blocks"].append({"kind": "chart", "source": 0, "title": "Hours"})
    requests = compile_model(model)
    rules = [item["setDataValidation"] for item in requests if "setDataValidation" in item]
    assert rules
    assert rules[0]["rule"]["condition"]["type"] == "ONE_OF_LIST"
    assert [item["userEnteredValue"] for item in rules[0]["rule"]["condition"]["values"]] == [
        "Present",
        "Absent",
    ]
    chart = next(item["addChart"]["chart"] for item in requests if "addChart" in item)
    assert chart["spec"]["title"] == "Hours"
    assert chart["position"]["overlayPosition"]["anchorCell"]["sheetId"] == 0


def test_compile_uses_the_sheet_id_google_assigned():
    requests = compile_model(_table_model(), first_sheet_id=42)
    sheet = next(item["updateSheetProperties"] for item in requests if "updateSheetProperties" in item)
    assert sheet["properties"]["sheetId"] == 42


def test_chart_without_sample_rows_still_compiles():
    model = _table_model()
    model["tabs"][0]["blocks"][0]["rows"] = []
    model["tabs"][0]["blocks"].append({"kind": "chart", "source": 0, "title": "Hours"})
    requests = compile_model(model)
    assert any("addChart" in item for item in requests)


def test_unresolved_formula_is_an_invalid_batch():
    model = _table_model()
    model["tabs"][0]["blocks"][0]["columns"][3]["formula"] = "Nope * Hours"
    with pytest.raises(CompileError, match="Nope"):
        compile_model(model)


def test_chart_without_a_number_column_is_invalid():
    model = {
        "title": "Notes",
        "new_file": True,
        "tabs": [
            {
                "title": "Page",
                "blocks": [
                    {"kind": "table", "columns": [{"name": "Note", "kind": "text"}], "rows": []},
                    {"kind": "chart", "source": 0, "title": ""},
                ],
            }
        ],
    }
    with pytest.raises(CompileError):
        compile_model(model)
