"""Desk operations that do not use a messenger: status, inspection, staff mail, drawings."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any, Callable

from . import db
from .config import settings

ORDER_STATUSES = (
    "Order received",
    "In process",
    "Halted",
    "Inspection",
    "Ready",
    "Dispatched",
)
DISPOSITIONS = ("accept", "reject", "rework")

_PRICE = re.compile(
    r"(₹|\binr\b|\brs\.?\b|\bprice\b|\brate\b|\bquote\b|\bmargin\b|\d+\.\d{2}\b)",
    re.I,
)
_DATE = re.compile(
    r"(\b\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?\b|\bdelivery\b|\bby\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b)",
    re.I,
)
_COMMIT = re.compile(
    r"(\bpurchase order\b|\bwe accept\b|\border confirmed\b|\bwe will deliver\b|\bpo\b\s*#)",
    re.I,
)
_VALIDITY = re.compile(
    r"\b(valid|still good|still ok)\b.{0,40}\brev(?:ision)?\b|\brev(?:ision)?\b.{0,40}\b(valid|program)\b",
    re.I,
)


def program_validity_refusal(message: str) -> str | None:
    text = (message or "").strip()
    if not text or not _VALIDITY.search(text):
        return None
    return (
        "Jarvis does not answer whether an old program is valid for a new revision. "
        "A person checks that on the machine."
    )


def review_staff_mail(body: str) -> dict[str, Any]:
    text = (body or "").strip()
    if not text:
        return {"ok": False, "held": True, "error": "Empty mail."}
    if _PRICE.search(text) or _DATE.search(text) or _COMMIT.search(text):
        return {
            "ok": False,
            "held": True,
            "ping_owner": True,
            "error": "Held. A staff mail may only ask a question. It cannot state a price, a date, or a commitment.",
        }
    return {"ok": True, "held": False, "body": text}


def set_order_status(
    *,
    job_ref: str,
    status: str,
    delivery_date: str = "",
    halted_reason: str = "",
    role: str = "",
) -> dict[str, Any]:
    if (role or "").strip().lower() != "owner":
        return {"ok": False, "error": "Only the owner sets customer-visible status."}
    label = (status or "").strip()
    if label not in ORDER_STATUSES:
        return {"ok": False, "error": f"Status must be one of: {', '.join(ORDER_STATUSES)}."}
    ref = (job_ref or "").strip()
    if not ref:
        return {"ok": False, "error": "Job reference is required."}
    now = db.utc_now()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO order_status (job_ref, status, delivery_date, halted_reason, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(job_ref) DO UPDATE SET
              status = excluded.status,
              delivery_date = excluded.delivery_date,
              halted_reason = excluded.halted_reason,
              updated_at = excluded.updated_at
            """,
            (ref, label, (delivery_date or "").strip() or None, (halted_reason or "").strip() or None, now),
        )
    return {"ok": True, "job_ref": ref, "status": label}


def customer_status_text(job_ref: str) -> dict[str, Any]:
    ref = (job_ref or "").strip()
    with db.connect() as conn:
        row = conn.execute("SELECT status, delivery_date, halted_reason FROM order_status WHERE job_ref = ?", (ref,)).fetchone()
    if not row or not (row["status"] or "").strip() or not (row["delivery_date"] or "").strip():
        return {"ok": True, "say": "I'll ask the shop.", "ping_owner": True}
    status = str(row["status"])
    if status == "Halted":
        reason = (row["halted_reason"] or "").strip()
        say = f"Halted. {reason}" if reason else "Halted"
    else:
        say = status
    return {
        "ok": True,
        "say": say,
        "status": status,
        "delivery_date": str(row["delivery_date"]),
        "ping_owner": False,
    }


def release_inspection(
    *,
    role: str,
    job_ref: str,
    measurements: dict[str, Any],
    disposition: str,
) -> dict[str, Any]:
    if (role or "").strip().lower() != "quality_inspector":
        return {"ok": False, "ping_owner": True, "error": "Only the quality inspector releases an inspection result."}
    disp = (disposition or "").strip().lower()
    if disp not in DISPOSITIONS:
        return {"ok": False, "error": "Disposition must be accept, reject, or rework."}
    blob = json.dumps(measurements or {}, sort_keys=True).lower()
    if re.search(r"\b(price|rate|margin|delivery|inr|₹)\b", blob):
        return {"ok": False, "error": "An inspection result carries measurements and a disposition, not a price or a delivery date."}
    ref = (job_ref or "").strip()
    if not ref:
        return {"ok": False, "error": "Job reference is required."}
    report_id = uuid.uuid4().hex[:12]
    folder = Path(settings.exports_dir) / "inspection"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{report_id}.txt"
    lines = [f"Job: {ref}", f"Disposition: {disp}", "Measurements:"]
    for key, value in sorted((measurements or {}).items()):
        lines.append(f"- {key}: {value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    before = customer_status_text(ref).get("status")
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO inspection_reports (id, job_ref, measurements_json, disposition, path, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (report_id, ref, json.dumps(measurements or {}), disp, str(path), db.utc_now()),
        )
    after = customer_status_text(ref).get("status")
    return {
        "ok": True,
        "id": report_id,
        "path": str(path),
        "status_unchanged": before == after,
    }


def send_drawing_to_person(
    *,
    role: str,
    product_number: str,
    to_email: str,
    channel: str,
    send_fn: Callable[[str, str, str], None] | None = None,
) -> dict[str, Any]:
    if (role or "").strip().lower() != "owner":
        return {"ok": False, "error": "Only the owner sends a drawing."}
    if (channel or "").strip().lower() != "email":
        return {"ok": False, "error": "Messenger drawing sends are parked. Email only."}
    email = (to_email or "").strip()
    if "@" not in email or email.lower().endswith("@group"):
        return {"ok": False, "error": "Name one person by email. A group is refused."}
    number = (product_number or "").strip()
    with db.connect() as conn:
        row = conn.execute(
            """
            SELECT status, effective_to FROM products
            WHERE product_number = ? AND effective_to IS NULL
            ORDER BY effective_from DESC LIMIT 1
            """,
            (number,),
        ).fetchone()
    if not row or str(row["status"] or "").lower() != "active":
        return {"ok": False, "error": "The component is not Active."}
    subject = f"Drawing {number}"
    body = f"Drawing for {number}, sent to {email}."
    if send_fn is not None:
        send_fn(email, subject, body)
    return {"ok": True, "channel": "email", "to": email, "subject": subject}


def write_setup_chart(nc_path: str, *, notes: str = "") -> str:
    src = Path(nc_path)
    dest = src.with_suffix(".setup.md")
    dest.parent.mkdir(parents=True, exist_ok=True)
    text = (
        f"# Setup chart\n\n"
        f"Program file: {src.name}\n\n"
        f"Holding and setup notes:\n{(notes or 'Owner to confirm workholding.').strip()}\n\n"
        f"This is not a program. It is not transmitted to a machine.\n"
    )
    dest.write_text(text, encoding="utf-8")
    return str(dest)
