from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.config import settings
from app.drafts import load_draft, save_draft
from app.features.sheets import talk
from app.features.sheets.draft import list_templates
from app.tools.registry import HANDLERS, execute_tool


def _reset() -> None:
    db.init_db()
    with db.connect() as conn:
        conn.execute(
            "DELETE FROM drafts WHERE key = ? OR key LIKE ? OR key LIKE ?",
            ("sheets.current", "sheets.model.%", "sheets.template.%"),
        )


def _boom(*_args, **_kwargs):
    raise AssertionError("Google was called")


def _block_google(monkeypatch) -> None:
    monkeypatch.setattr(talk, "create_workbook", _boom)
    monkeypatch.setattr(talk, "get_workbook", _boom)
    monkeypatch.setattr(talk, "batch_update", _boom)
    monkeypatch.setattr(talk, "trash_workbook", _boom)


def _fake_sheet(*_args, **_kwargs):
    return {"sheets": [{"properties": {"sheetId": 0}}]}


_DESK_PASSWORD = "SheetPass1"


def _desk_password(monkeypatch) -> None:
    monkeypatch.setattr(settings, "sheet_build_password", _DESK_PASSWORD)


def _build_ready() -> dict:
    assert talk.tool_edit(action="set_title", title="Attendance")["ok"] is True
    assert talk.tool_edit(action="add_tab", title="October")["ok"] is True
    added = talk.tool_edit(
        action="add_block",
        kind="table",
        columns=[
            {"name": "Name", "kind": "text", "filled_by": "staff"},
            {"name": "Hours", "kind": "number", "filled_by": "staff"},
            {"name": "Rate", "kind": "number", "filled_by": "owner"},
            {"name": "Pay", "kind": "formula", "filled_by": "jarvis", "formula": "Hours * Rate"},
        ],
    )
    assert added["ok"] is True
    stored = talk.tool_edit(action="set_rows", rows=[{"Name": "Ada", "Hours": 8}])
    assert stored["ok"] is True
    return stored


def test_insert_after_a_named_column():
    _reset()
    talk.tool_edit(action="set_title", title="Attendance")
    talk.tool_edit(action="add_tab", title="October")
    talk.tool_edit(
        action="add_block",
        kind="table",
        columns=[{"name": "Quantity", "kind": "number"}, {"name": "Name", "kind": "text"}],
    )
    saved = talk.tool_edit(
        action="insert_column",
        anchor="Quantity",
        place="after",
        column={"name": "Rate", "kind": "number", "filled_by": "staff"},
    )
    assert saved["ok"] is True
    names = [column["name"] for column in saved["model"]["tabs"][0]["blocks"][0]["columns"]]
    assert names == ["Quantity", "Rate", "Name"]
    assert "Rate" in saved["outline"]
    assert saved["missing"] is None

    before = talk.tool_edit(
        action="insert_column",
        anchor="Name",
        place="before",
        column={"name": "Shift", "kind": "text"},
    )
    names = [column["name"] for column in before["model"]["tabs"][0]["blocks"][0]["columns"]]
    assert names == ["Quantity", "Rate", "Shift", "Name"]


def test_insert_after_a_missing_name_leaves_the_model_unchanged():
    _reset()
    talk.tool_edit(action="set_title", title="Attendance")
    talk.tool_edit(action="add_tab", title="October")
    talk.tool_edit(action="add_block", kind="table", columns=[{"name": "Quantity", "kind": "number"}])
    before = talk.tool_read()
    result = talk.tool_edit(
        action="insert_column",
        anchor="Rate",
        place="after",
        column={"name": "Amount", "kind": "number"},
    )
    after = talk.tool_read()
    assert result["ok"] is False
    assert result["unchanged"] is True
    assert "unchanged" in result["speak"].lower()
    assert result["model"] == before["model"]
    assert after["model"] == before["model"]
    assert after["updated_at"] == before["updated_at"]
    assert [column["name"] for column in after["model"]["tabs"][0]["blocks"][0]["columns"]] == ["Quantity"]


def test_apply_refuses_a_telegram_user_who_is_not_the_owner(monkeypatch):
    _reset()
    _build_ready()
    _block_google(monkeypatch)
    monkeypatch.setattr(settings, "telegram_owner_user_ids", "111,222")
    result = talk.tool_apply(telegram_user_id="999")
    assert result["ok"] is False
    assert result["need"] == "owner"
    assert "refused" in result["error"].lower()

    monkeypatch.setattr(settings, "telegram_owner_user_ids", "")
    closed = talk.tool_apply(telegram_user_id="111")
    assert closed["ok"] is False
    assert closed["need"] == "owner"


def test_apply_allows_the_desk_and_an_owner_telegram_id(monkeypatch):
    _reset()
    _build_ready()
    monkeypatch.setattr(settings, "telegram_owner_user_ids", "111")
    calls: list[str] = []

    def _create(title, account=None):
        calls.append(f"create:{title}")
        return {"spreadsheetId": "new-file", "spreadsheetUrl": "https://docs.google.com/spreadsheets/d/new-file/edit"}

    monkeypatch.setattr(talk, "create_workbook", _create)
    monkeypatch.setattr(talk, "get_workbook", _fake_sheet)
    monkeypatch.setattr(talk, "batch_update", lambda *_a, **_k: calls.append("batch") or {"replies": []})
    monkeypatch.setattr(talk, "trash_workbook", _boom)
    owner = talk.tool_apply(telegram_user_id="111")
    assert owner["ok"] is True
    assert calls == ["create:Attendance", "batch"]


def test_apply_creates_a_new_file_in_one_batch(monkeypatch):
    _reset()
    ready = _build_ready()
    assert ready["model"]["tabs"][0]["blocks"][0]["columns"][3]["formula"] == "Hours * Rate"
    calls: list[tuple] = []

    monkeypatch.setattr(
        talk,
        "create_workbook",
        lambda title, account=None: calls.append(("create", title))
        or {"spreadsheetId": "new-file", "spreadsheetUrl": "https://docs.google.com/spreadsheets/d/new-file/edit"},
    )
    monkeypatch.setattr(talk, "get_workbook", _fake_sheet)
    monkeypatch.setattr(
        talk,
        "batch_update",
        lambda spreadsheet_id, requests, account=None: calls.append(("batch", spreadsheet_id, requests)) or {"replies": []},
    )
    monkeypatch.setattr(talk, "trash_workbook", _boom)
    _desk_password(monkeypatch)
    result = talk.tool_apply(password=_DESK_PASSWORD)
    assert result["ok"] is True
    assert result["spreadsheet_id"] == "new-file"
    assert result["url"].endswith("/new-file/edit")
    assert result["outline"]
    assert [item[0] for item in calls] == ["create", "batch"]
    assert calls[0] == ("create", "Attendance")
    assert calls[1][1] == "new-file"
    requests = calls[1][2]
    assert not any("addSheet" in item for item in requests)
    formulas = []
    numbers = []
    for item in requests:
        for row in (item.get("updateCells") or {}).get("rows") or []:
            for cell in row.get("values") or []:
                entered = cell.get("userEnteredValue") or {}
                if entered.get("formulaValue"):
                    formulas.append(entered["formulaValue"])
                if entered.get("numberValue") is not None:
                    numbers.append(entered["numberValue"])
    compact = [item.replace(" ", "") for item in formulas]
    assert compact[0] == "=B2*C2"
    assert len(compact) == 50
    assert numbers == [8]
    assert not hasattr(talk, "find_workbooks")
    assert not hasattr(talk, "add_tab")
    template = load_draft(f"sheets.template.{result['template_id']}")
    stored = template["body"]["model"]
    assert stored["tabs"][0]["blocks"][0]["rows"] == []
    assert stored["tabs"][0]["blocks"][0]["columns"][3]["formula"] == "Hours * Rate"
    assert list_templates()[0]["id"] == result["template_id"]


def test_apply_writes_nothing_when_the_model_is_incomplete(monkeypatch):
    _reset()
    _block_google(monkeypatch)
    missing_title = talk.tool_apply()
    assert missing_title["ok"] is False
    assert missing_title["missing"] == "title"

    talk.tool_edit(action="set_title", title="Attendance")
    missing_tab = talk.tool_apply()
    assert missing_tab["ok"] is False
    assert missing_tab["missing"] == "tab"


def test_apply_writes_nothing_when_the_batch_would_be_invalid(monkeypatch):
    _reset()
    _build_ready()
    talk.tool_edit(action="set_formula", name="Pay", formula="Nope * Hours")
    _block_google(monkeypatch)
    _desk_password(monkeypatch)
    result = talk.tool_apply(password=_DESK_PASSWORD)
    assert result["ok"] is False
    assert "Nope" in result["speak"]
    assert list_templates() == []


def test_failed_batch_trashes_the_new_file_and_saves_no_template(monkeypatch):
    _reset()
    _build_ready()
    calls: list[tuple] = []
    monkeypatch.setattr(
        talk,
        "create_workbook",
        lambda title, account=None: {"spreadsheetId": "new-file", "spreadsheetUrl": "https://example/new-file"},
    )
    monkeypatch.setattr(talk, "get_workbook", _fake_sheet)

    def _batch(*_args, **_kwargs):
        calls.append(("batch",))
        raise RuntimeError("rejected")

    def _trash(spreadsheet_id, account=None):
        calls.append(("trash", spreadsheet_id))

    monkeypatch.setattr(talk, "batch_update", _batch)
    monkeypatch.setattr(talk, "trash_workbook", _trash)
    _desk_password(monkeypatch)
    result = talk.tool_apply(password=_DESK_PASSWORD)
    assert result["ok"] is False
    assert "moved to trash" in result["speak"].lower()
    assert "rejected" not in result["speak"].lower()
    assert ("trash", "new-file") in calls
    assert list_templates() == []


def test_clone_drops_sample_values():
    _reset()
    save_draft(
        "sheets.template.attendance",
        {
            "id": "attendance",
            "model": {
                "title": "Attendance",
                "new_file": True,
                "tabs": [
                    {
                        "title": "October",
                        "blocks": [
                            {
                                "kind": "table",
                                "columns": [
                                    {"name": "Hours", "kind": "number", "filled_by": "staff"},
                                    {"name": "Pay", "kind": "formula", "formula": "Hours * 100"},
                                ],
                                "rows": [{"Hours": 8, "Pay": 800}],
                            }
                        ],
                    }
                ],
            },
        },
    )
    cloned = talk.tool_clone(template_id="attendance", title="November attendance")
    assert cloned["ok"] is True
    table = cloned["model"]["tabs"][0]["blocks"][0]
    assert cloned["model"]["title"] == "November attendance"
    assert cloned["model"]["new_file"] is True
    assert table["rows"] == []
    assert table["columns"][1]["formula"] == "Hours * 100"
    assert "8" not in json.dumps(table["rows"])


def test_execute_tool_reads_edits_and_refuses_the_old_apply(monkeypatch):
    _reset()
    _block_google(monkeypatch)
    edited = execute_tool(
        "sheet_model_edit",
        {"action": "set_title", "payload": "{\"title\": \"Attendance\"}"},
        "session-1",
    )
    assert edited["ok"] is True
    assert edited["model"]["title"] == "Attendance"
    read = execute_tool("sheet_model_read", {}, "session-1")
    assert read["model"]["title"] == "Attendance"
    applied = execute_tool("sheet_model_apply", {}, "session-1")
    assert applied["ok"] is False
    assert applied["missing"] == "tab"
    retired = execute_tool("sheet_draft_apply", {}, "session-1")
    assert retired["ok"] is False
    assert "Unknown tool" in retired["error"]
    assert "sheet_draft_apply" not in HANDLERS
    assert "sheet_model_apply" in HANDLERS


def test_mcp_apply_refuses_staff(monkeypatch):
    _reset()
    _build_ready()
    _block_google(monkeypatch)
    monkeypatch.setattr(settings, "telegram_owner_user_ids", "111")
    from app.hermes import mcp_server

    refused = json.loads(mcp_server.jarvis_sheet_model_apply(telegram_user_id="999"))
    assert refused["ok"] is False
    assert refused["need"] == "owner"
    assert "refused" in refused["error"].lower()


def test_apply_again_returns_the_first_file(monkeypatch):
    _reset()
    _build_ready()
    calls: list[str] = []
    monkeypatch.setattr(
        talk,
        "create_workbook",
        lambda title, account=None: calls.append("create")
        or {"spreadsheetId": "new-file", "spreadsheetUrl": "https://docs.google.com/spreadsheets/d/new-file/edit"},
    )
    monkeypatch.setattr(talk, "get_workbook", _fake_sheet)
    monkeypatch.setattr(talk, "batch_update", lambda *_a, **_k: calls.append("batch") or {"replies": []})
    monkeypatch.setattr(talk, "trash_workbook", _boom)
    _desk_password(monkeypatch)
    first = talk.tool_apply(password=_DESK_PASSWORD)
    second = talk.tool_apply(password=_DESK_PASSWORD)
    assert second["ok"] is True
    assert second["already_created"] is True
    assert second["url"] == first["url"]
    assert calls == ["create", "batch"]


def test_staff_actor_cannot_create(monkeypatch):
    _reset()
    _build_ready()
    _block_google(monkeypatch)
    result = talk.tool_apply(actor="staff")
    assert result["ok"] is False
    assert result["need"] == "owner"


def test_sessions_do_not_share_an_open_model():
    _reset()
    talk.tool_edit(session_id="desk", action="set_title", title="Attendance")
    other = talk.tool_read(session_id="telegram-9")
    assert other["model"]["title"] == ""
    assert talk.tool_read(session_id="desk")["model"]["title"] == "Attendance"


def test_rename_rewrites_formulas_that_use_the_old_name():
    _reset()
    talk.tool_edit(action="set_title", title="Attendance")
    talk.tool_edit(action="add_tab", title="October")
    talk.tool_edit(
        action="add_block",
        kind="table",
        columns=[
            {"name": "Hours", "kind": "number"},
            {"name": "Pay", "kind": "formula", "formula": "Hours * Rate"},
        ],
    )
    renamed = talk.tool_edit(action="rename_column", name="Hours", new_name="Time")
    formula = renamed["model"]["tabs"][0]["blocks"][0]["columns"][1]["formula"]
    assert formula == "Time * Rate"


def test_clone_refuses_to_replace_an_open_model():
    _reset()
    talk.tool_edit(action="set_title", title="Attendance")
    save_draft(
        "sheets.template.attendance",
        {
            "id": "attendance",
            "model": {
                "title": "Attendance",
                "new_file": True,
                "tabs": [{"title": "October", "blocks": [{"kind": "title", "text": "Keep"}]}],
            },
        },
    )
    refused = talk.tool_clone(template_id="attendance", title="November")
    assert refused["ok"] is False
    assert "discard" in refused["speak"].lower()
    replaced = talk.tool_clone(template_id="attendance", title="November", discard=True)
    assert replaced["ok"] is True
    assert replaced["model"]["title"] == "November"


def test_desk_create_requires_the_configured_password(monkeypatch):
    _reset()
    _build_ready()
    _block_google(monkeypatch)
    monkeypatch.setattr(settings, "sheet_build_password", "")
    missing = talk.tool_apply()
    assert missing["need"] == "password"
    assert "not configured" in missing["speak"].lower()

    _desk_password(monkeypatch)
    asked = talk.tool_apply()
    assert asked["need"] == "password"
    assert "ask for the sheet password" in asked["speak"].lower()
    wrong = talk.tool_apply(password="WrongPass1")
    assert wrong["need"] == "password"
    assert "refused" in wrong["speak"].lower()
    symbols = talk.tool_apply(password="no spaces")
    assert symbols["need"] == "password"
    assert "alphanumeric" in symbols["speak"].lower()


def test_failed_batch_names_the_empty_file_when_trash_fails(monkeypatch):
    _reset()
    _build_ready()
    monkeypatch.setattr(
        talk,
        "create_workbook",
        lambda title, account=None: {"spreadsheetId": "new-file", "spreadsheetUrl": "https://example/new-file"},
    )
    monkeypatch.setattr(talk, "get_workbook", _fake_sheet)
    monkeypatch.setattr(talk, "batch_update", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("rejected")))

    def _trash(*_args, **_kwargs):
        raise RuntimeError("trash denied")

    monkeypatch.setattr(talk, "trash_workbook", _trash)
    _desk_password(monkeypatch)
    result = talk.tool_apply(password=_DESK_PASSWORD)
    assert result["ok"] is False
    assert "https://example/new-file" in result["speak"]
    assert "rejected" not in result["speak"]
    assert "trash denied" not in result["speak"]


def test_password_is_redacted_from_tool_logs():
    from app.tools.registry import _redact_tool_args

    cleaned = _redact_tool_args({"password": _DESK_PASSWORD, "actor": ""})
    assert cleaned["password"] == "[redacted]"
    assert _DESK_PASSWORD not in str(cleaned)
