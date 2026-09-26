"""Numbered migrations from 0024 follow the forward-only template."""

from __future__ import annotations

from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


def test_template_and_new_migrations_are_forward_only():
    template = (MIGRATIONS / "TEMPLATE.sql").read_text(encoding="utf-8")
    assert "-- Description:" in template
    assert "-- Dependencies:" in template
    numbered = []
    for path in MIGRATIONS.glob("*.sql"):
        prefix = path.name.split("_", 1)[0]
        if prefix.isdigit() and int(prefix) >= 24:
            numbered.append(path)
    assert numbered, "expected at least migration 0024"
    for path in numbered:
        text = path.read_text(encoding="utf-8")
        assert text.startswith("-- Description:"), path.name
        assert "-- Dependencies:" in text
        upper = text.upper()
        assert "DROP TABLE" not in upper
        assert "BEGIN IMMEDIATE" not in upper
        assert "COMMIT" not in upper
