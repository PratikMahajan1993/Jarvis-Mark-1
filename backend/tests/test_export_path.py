"""Export paths stay inside the exports directory and refuse symlinks."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings
from app.db import safe_export_path


def test_safe_export_path_keeps_basename_inside_exports(tmp_path, monkeypatch) -> None:
    exports = tmp_path / "exports"
    exports.mkdir()
    monkeypatch.setattr(settings, "exports_dir", exports)

    target = safe_export_path(r"..\..\secret.txt")
    assert target == (exports / "secret.txt").resolve()
    assert target.is_relative_to(exports.resolve())
    assert target != exports.resolve()
    assert not target.is_dir()


def test_safe_export_path_rejects_a_directory(tmp_path, monkeypatch) -> None:
    exports = tmp_path / "exports"
    (exports / "notes").mkdir(parents=True)
    monkeypatch.setattr(settings, "exports_dir", exports)

    with pytest.raises(ValueError):
        safe_export_path("notes")


def test_safe_export_path_rejects_symlink_before_resolve(tmp_path, monkeypatch) -> None:
    exports = tmp_path / "exports"
    exports.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("nope", encoding="utf-8")
    link = exports / "link.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        real_is_symlink = Path.is_symlink

        def _is_symlink(self: Path) -> bool:
            if self == link:
                return True
            return real_is_symlink(self)

        monkeypatch.setattr(Path, "is_symlink", _is_symlink)

    monkeypatch.setattr(settings, "exports_dir", exports)
    with pytest.raises(ValueError):
        safe_export_path("link.txt")
