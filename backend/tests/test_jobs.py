from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings

settings.data_dir = Path(tempfile.mkdtemp(prefix="jarvis-jobs-"))
settings.data_dir.mkdir(parents=True, exist_ok=True)

from app import db
from app import jobs


def _table_names() -> set[str]:
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    return {row["name"] for row in rows}


def _clear_jobs() -> None:
    with db.connect() as conn:
        conn.execute("DELETE FROM jobs")


def _clear_rfqs() -> None:
    with db.connect() as conn:
        conn.execute("DELETE FROM rfqs")


def test_init_db_creates_jobs_and_rfqs_tables():
    db.init_db()
    names = _table_names()
    assert "jobs" in names
    assert "rfqs" in names
    with db.connect() as conn:
        job_cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
        rfq_cols = {row[1] for row in conn.execute("PRAGMA table_info(rfqs)").fetchall()}
    for col in (
        "id",
        "customer",
        "part_name",
        "material",
        "machine",
        "cycle_min",
        "margin",
        "drawing_file",
        "geometry_notes",
        "created_at",
    ):
        assert col in job_cols, col
    for col in (
        "id",
        "mail_id",
        "conversation_id",
        "status",
        "extract",
        "similar_job_ids",
        "pending_reply",
        "deadline_iso",
        "created_at",
        "updated_at",
    ):
        assert col in rfq_cols, col


def test_seed_inserts_one_ace_job_and_is_idempotent():
    db.init_db()
    _clear_jobs()
    first = jobs.seed_demo_job()
    assert first is not None
    assert first["id"] == jobs.DEMO_JOB_ID
    assert first["customer"] == "Ace Designers"
    assert first["material"] == "18CrNiMo7-6"
    assert "turning cell" in first["machine"].lower()
    assert first["part_name"]
    assert first["cycle_min"] == 8.5
    assert first["margin"] == 22.0
    notes = first["geometry_notes"].lower()
    assert "od" in notes
    assert "face" in notes
    assert "bore" in notes
    assert "hold" in notes
    rows = jobs.list_jobs()
    assert len(rows) == 1
    second = jobs.seed_demo_job()
    assert second is None
    db.init_db()
    assert len(jobs.list_jobs()) == 1
    assert jobs.list_jobs()[0]["id"] == jobs.DEMO_JOB_ID


def test_init_db_seeds_when_jobs_table_is_empty():
    db.init_db()
    _clear_jobs()
    db.init_db()
    found = jobs.get_job(jobs.DEMO_JOB_ID)
    assert found is not None
    assert found["material"] == "18CrNiMo7-6"


def test_search_similar_finds_seed_by_material_case_insensitive():
    db.init_db()
    jobs.seed_demo_job()
    hits = jobs.search_similar("18CrNiMo7-6")
    assert hits
    assert any(row["id"] == jobs.DEMO_JOB_ID for row in hits)
    lowered = jobs.search_similar("18crnimo7-6")
    assert lowered
    assert lowered[0]["material"] == "18CrNiMo7-6"


def test_search_similar_empty_or_unknown_material_returns_empty():
    db.init_db()
    jobs.seed_demo_job()
    assert jobs.search_similar("") == []
    assert jobs.search_similar("   ") == []
    assert jobs.search_similar("Al 6061") == []
    assert jobs.search_similar("unobtanium-99") == []
    assert jobs.get_job("") is None
    assert jobs.get_job("missing-job") is None


def test_geometry_token_overlap_ranks_seeded_job():
    db.init_db()
    jobs.seed_demo_job()
    distractor = jobs.create_job(
        customer="Ace Designers",
        part_name="Cutoff slug",
        material="18CrNiMo7-6",
        machine="Ace Designers turning cell",
        cycle_min=2.0,
        margin=12.0,
        geometry_notes="Bar-feed cutoff only. No features, no holding change.",
    )
    ranked = jobs.search_similar("18CrNiMo7-6", "OD face bore holding")
    assert ranked
    assert ranked[0]["id"] == jobs.DEMO_JOB_ID
    ids = [row["id"] for row in ranked]
    assert distractor["id"] in ids
    seed_score = len(jobs._tokens("OD face bore holding") & jobs._tokens(ranked[0]["geometry_notes"]))
    other = next(row for row in ranked if row["id"] == distractor["id"])
    other_score = len(jobs._tokens("OD face bore holding") & jobs._tokens(other["geometry_notes"]))
    assert seed_score > other_score


def test_create_job_and_get_round_trip():
    db.init_db()
    row = jobs.create_job(
        customer="Ace Designers",
        part_name="Sleeve",
        material="EN8",
        machine="Ace Jobber",
        cycle_min=4.25,
        margin=18.0,
        drawing_file="sleeve.pdf",
        geometry_notes="Chuck on OD, face, bore.",
        job_id="sleeve-en8",
    )
    assert row["id"] == "sleeve-en8"
    fetched = jobs.get_job("sleeve-en8")
    assert fetched == row
    listed = {item["id"]: item for item in jobs.list_jobs()}
    assert listed["sleeve-en8"]["cycle_min"] == 4.25
    assert listed["sleeve-en8"]["margin"] == 18.0


def test_rfq_crud_and_status_filter():
    db.init_db()
    _clear_rfqs()
    created = jobs.create_rfq(
        mail_id="mail-1",
        conversation_id="conv-1",
        status="intake",
        extract={"material": "18CrNiMo7-6", "ops": ["turn", "bore"]},
        similar_job_ids=[jobs.DEMO_JOB_ID],
        pending_reply="",
        deadline_iso="2026-09-12T10:00:00+05:30",
    )
    assert created["status"] == "intake"
    fetched = jobs.get_rfq(created["id"])
    assert fetched is not None
    assert fetched["mail_id"] == "mail-1"
    assert fetched["conversation_id"] == "conv-1"
    updated = jobs.update_rfq(
        created["id"],
        status="reasoned",
        pending_reply="Need grind stock on OD.",
        similar_job_ids=[jobs.DEMO_JOB_ID, "sleeve-en8"],
    )
    assert updated is not None
    assert updated["status"] == "reasoned"
    assert updated["pending_reply"] == "Need grind stock on OD."
    assert updated["similar_job_ids"] == [jobs.DEMO_JOB_ID, "sleeve-en8"]
    assert updated["updated_at"] >= updated["created_at"]
    other = jobs.create_rfq(status="dismissed", mail_id="mail-2")
    intake_or_reasoned = jobs.list_rfqs(status="reasoned")
    assert [row["id"] for row in intake_or_reasoned] == [created["id"]]
    dismissed = jobs.list_rfqs(status="dismissed")
    assert [row["id"] for row in dismissed] == [other["id"]]
    all_rows = jobs.list_rfqs()
    assert {row["id"] for row in all_rows} >= {created["id"], other["id"]}
    assert jobs.get_rfq("") is None
    assert jobs.get_rfq("missing-rfq") is None
    assert jobs.update_rfq("missing-rfq", status="sent") is None


def test_illegal_rfq_status_rejected():
    db.init_db()
    try:
        jobs.create_rfq(status="shipped")
        raise AssertionError("create_rfq accepted illegal status")
    except ValueError as exc:
        assert "shipped" in str(exc)
    row = jobs.create_rfq(status="pending")
    try:
        jobs.update_rfq(row["id"], status="quoted")
        raise AssertionError("update_rfq accepted illegal status")
    except ValueError as exc:
        assert "quoted" in str(exc)
    try:
        jobs.list_rfqs(status="nope")
        raise AssertionError("list_rfqs accepted illegal status")
    except ValueError:
        pass
    try:
        jobs.update_rfq(row["id"], not_a_column="x")
        raise AssertionError("update_rfq accepted unknown field")
    except ValueError as exc:
        assert "not_a_column" in str(exc)
    still = jobs.get_rfq(row["id"])
    assert still is not None
    assert still["status"] == "pending"


def test_extract_json_round_trips():
    db.init_db()
    payload = {
        "material": "18CrNiMo7-6",
        "ops": ["face", "OD", "bore"],
        "holding": "soft jaws",
        "qty": 40,
    }
    created = jobs.create_rfq(extract=payload, similar_job_ids=["ace-pinion-blank"])
    fetched = jobs.get_rfq(created["id"])
    assert fetched is not None
    assert fetched["extract"] == payload
    assert fetched["similar_job_ids"] == ["ace-pinion-blank"]
    patched = jobs.update_rfq(
        created["id"],
        extract=json.dumps({"material": "EN36C", "qty": 12}),
        similar_job_ids='["other"]',
    )
    assert patched is not None
    assert patched["extract"] == {"material": "EN36C", "qty": 12}
    assert patched["similar_job_ids"] == ["other"]
    with db.connect() as conn:
        raw = conn.execute(
            "SELECT extract, similar_job_ids FROM rfqs WHERE id = ?",
            (created["id"],),
        ).fetchone()
    assert json.loads(raw["extract"]) == {"material": "EN36C", "qty": 12}
    assert json.loads(raw["similar_job_ids"]) == ["other"]


def test_invalid_rfq_json_rejected():
    db.init_db()
    try:
        jobs.create_rfq(extract="{not-json")
        raise AssertionError("create_rfq accepted invalid JSON")
    except ValueError as exc:
        assert "JSON" in str(exc)


def test_jobs_material_lower_index_exists():
    db.init_db()
    with db.connect() as conn:
        names = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'").fetchall()}
    assert "jobs_material_lc" in names


def test_jobs_table_uses_row_factory():
    db.init_db()
    with db.connect() as conn:
        assert conn.row_factory is sqlite3.Row
        row = conn.execute("SELECT COUNT(*) AS n FROM jobs").fetchone()
        assert row["n"] >= 0


if __name__ == "__main__":
    tests = [
        test_init_db_creates_jobs_and_rfqs_tables,
        test_seed_inserts_one_ace_job_and_is_idempotent,
        test_init_db_seeds_when_jobs_table_is_empty,
        test_search_similar_finds_seed_by_material_case_insensitive,
        test_search_similar_empty_or_unknown_material_returns_empty,
        test_geometry_token_overlap_ranks_seeded_job,
        test_create_job_and_get_round_trip,
        test_rfq_crud_and_status_filter,
        test_illegal_rfq_status_rejected,
        test_extract_json_round_trips,
        test_invalid_rfq_json_rejected,
        test_jobs_material_lower_index_exists,
        test_jobs_table_uses_row_factory,
    ]
    for test in tests:
        test()
        print("ok", test.__name__)
    print(f"passed {len(tests)}")
