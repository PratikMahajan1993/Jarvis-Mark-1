"""Operations, attestation, formal PDF, and duplicate-send warning."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings

_TMP = Path(tempfile.mkdtemp(prefix="jarvis-phase1-"))
settings.data_dir = _TMP / "data"
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.exports_dir = _TMP / "exports"
settings.exports_dir.mkdir(parents=True, exist_ok=True)

from app import db
from app.quote import (
    build_quote,
    duplicate_delivery_warning,
    queue_quote_send,
    quote_to_pdf,
    verify_quote,
)
from app.quote_ops import add_quote_operation, attest_mhr_rate, reorder_quote_operations


def setup_module(_module=None):
    db.init_db()


def test_operations_price_only_when_given_and_outsource_blocks():
    session = "ops-1"
    added = add_quote_operation(session, template="heat_treat")
    assert added["ok"] is True
    assert added["operations"][0]["outsource"] == 1
    milled = add_quote_operation(session, template="milling", cycle_min="30", setup_inr="100")
    assert milled["ok"] is True
    order = reorder_quote_operations(session, [milled["operations"][-1]["id"], added["operations"][0]["id"]])
    assert [row["operation"] for row in order["operations"]] == ["Milling", "Heat treat"]
    built = build_quote(session_id=session, part_name="Plate", scope="labour", machining_rate="1200")
    assert built["ok"] is True
    milling = next(row for row in built["rows"] if row[0] == "Milling")
    assert float(milling[3]) == 700
    heat = next(row for row in built["rows"] if row[0] == "Heat treat")
    assert heat[3] == ""
    proof = verify_quote(session_id=session)
    failed = [c for c in proof["checks"] if c["id"] == "outsource_price" and not c["pass"]]
    assert failed
    assert "Heat treat" in failed[0]["evidence"]


def test_pdf_has_bold_total_and_empty_send_uses_formal_body():
    session = "pdf-1"
    build_quote(
        session_id=session,
        part_name="Pin",
        customer="Deepak",
        scope="labour",
        line_items=[{"item": "Pin", "material": "EN8", "qty": 2, "unit_price": 100, "notes": ""}],
    )
    pdf = quote_to_pdf(session_id=session, part_name="Pin")
    from pypdf import PdfReader

    text = "\n".join(page.extract_text() or "" for page in PdfReader(pdf["artifact"]["path"]).pages)
    assert "QUOTATION" in text
    assert "Total Quoted Cost" in text
    assert "INR 200.00" in text
    queued = queue_quote_send(session_id=session, to="deepak@example.com", subject="", body="", pdf_path=pdf["artifact"]["path"])
    assert queued["sent"] is False
    assert queued["pending"]["payload"]["blast_radius"] == 5
    assert "Total Quoted Cost" in queued["pending"]["payload"]["body"]
    assert queued["pending"]["payload"]["attachment_paths"]
    db.set_pending_status(queued["pending"]["id"], "rejected")


def test_duplicate_delivery_warns():
    from app.quote import delivery_hash

    digest = "abc123"
    token = delivery_hash("buyer@example.com", "Quotation — Pin", digest)
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO external_effects (id, action_id, provider, request_hash, state, created_at, delivery_hash)
            VALUES ('eff-dup', 'act-dup', 'gmail', 'hash-dup', 'sent', '2026-09-20T00:00:00+00:00', ?)
            """,
            (token,),
        )
    warning = duplicate_delivery_warning("buyer@example.com", "Quotation — Pin", digest)
    assert "buyer@example.com" in warning
    assert "2026-09-20" in warning


def test_attest_refuses_demo_seed(monkeypatch):
    monkeypatch.setattr(settings, "masterdata_enabled", True)
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO machine_hour_rates (
              id, machine_type, min_mhr_minor, currency, effective_from, source_kind, source_ref,
              attested_by, shipped_seed_value_minor
            ) VALUES ('mhr-1', 'Demo mill', 85000, 'INR', '2020-01-01', 'demo', 'seed', '', 85000)
            """
        )
    refused = attest_mhr_rate(rate_id="mhr-1", attested_by="Owner", floor_inr="850")
    assert refused["ok"] is False
    attested = attest_mhr_rate(rate_id="mhr-1", attested_by="Owner", floor_inr="900")
    assert attested["ok"] is True
    row = next(item for item in attested["rates"] if item["id"] == "mhr-1")
    assert row["status"] == "attested"
    assert row["attested_by"] == "Owner"
