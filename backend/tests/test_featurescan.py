from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.featurescan import draft_routing_from_step, parse_step_text

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "hole_d10.step"


def _ensure_db() -> None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='feature_process_rules'"
        ).fetchone()
    if not row:
        db.init_db()


def test_migration_seeds_feature_process_rules():
    _ensure_db()
    with db.connect() as conn:
        n = conn.execute("SELECT COUNT(*) AS c FROM feature_process_rules").fetchone()["c"]
        row = conn.execute(
            "SELECT operations_json FROM feature_process_rules WHERE id = ?",
            ("fpr_hole_free_lt12",),
        ).fetchone()
    assert n >= 9
    ops = json.loads(row["operations_json"])
    assert ops == ["Centre drill", "Drill"]


def test_hole_d10_routing_from_rule_table():
    _ensure_db()
    draft = draft_routing_from_step(FIXTURE)
    assert draft["source_kind"] == "geometry_true"
    assert draft["operations"] == ["Centre drill", "Drill"]
    entity_types = {item.get("entity_type") for item in draft["unclassified"]}
    assert "PLANE" in entity_types


def test_unrecognised_entity_in_unclassified():
    parsed = parse_step_text(FIXTURE.read_text(encoding="utf-8"))
    types = {u["entity_type"] for u in parsed.unclassified if u.get("type") == "step_entity"}
    assert "PLANE" in types
    assert "CARTESIAN_POINT" not in types
    assert "CYLINDRICAL_SURFACE" not in types


def test_routing_follows_db_rules_not_hardcoded():
    _ensure_db()
    with db.connect() as conn:
        conn.execute(
            """
            UPDATE feature_process_rules
            SET operations_json = ?
            WHERE id = ?
            """,
            (json.dumps(["Spotface", "Peck drill"]), "fpr_hole_free_lt12"),
        )
    try:
        draft = draft_routing_from_step(FIXTURE)
        assert draft["operations"] == ["Spotface", "Peck drill"]
    finally:
        with db.connect() as conn:
            conn.execute(
                """
                UPDATE feature_process_rules
                SET operations_json = ?
                WHERE id = ?
                """,
                (json.dumps(["Centre drill", "Drill"]), "fpr_hole_free_lt12"),
            )
