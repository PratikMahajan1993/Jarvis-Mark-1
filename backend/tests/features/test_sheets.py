from pathlib import Path

from app.config import settings
from app.features.sheets import FEATURE
from app.hermes.bridge import ensure_playbooks_installed
from app.tools.registry import HANDLERS

ROOT = Path(__file__).resolve().parents[2]


def test_sheets_registered():
    names = [tool.name for tool in FEATURE.tools]
    assert FEATURE.id == "sheets"
    assert names == [
        "sheet_model_read",
        "sheet_model_edit",
        "sheet_template_list",
        "sheet_template_clone",
        "sheet_model_apply",
    ]
    assert "sheet_draft_apply" not in names
    assert "sheet_draft_apply" not in HANDLERS
    assert "sheet_model_apply" in HANDLERS


def test_sheets_playbook_is_installed_with_the_others(tmp_path, monkeypatch):
    skill = ROOT / "app" / "hermes" / "playbooks" / "sheets" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    assert text.startswith("---")
    front = text.split("---", 2)[1]
    assert "name: shop-sheets" in front
    for phrase in (
        "TELEGRAM_OWNER_USER_IDS",
        "jarvis_sheet_model_read",
        "jarvis_sheet_model_edit",
        "jarvis_sheet_model_apply",
        "jarvis_sheet_template_clone",
        "raw Sheets toolkit",
    ):
        assert phrase in text

    monkeypatch.setattr(settings, "hermes_home", str(tmp_path / "hermes"))
    assert ensure_playbooks_installed() is True
    dest = tmp_path / "hermes" / "skills" / "shop" / "sheets" / "SKILL.md"
    installed = dest.read_text(encoding="utf-8")
    assert "shop-sheets" in installed
    quote = tmp_path / "hermes" / "skills" / "shop" / "quote" / "SKILL.md"
    master = tmp_path / "hermes" / "skills" / "shop" / "masterdata" / "SKILL.md"
    assert quote.is_file()
    assert master.is_file()
