"""Customer email replies for tagged drawing assumptions — email only, no WhatsApp."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from . import db
from .quote import ASSUMPTION_DRAWING_CELLS, init_drawing_cells, _save_session_drawing_cells

Classification = Literal["accept", "change", "unclear"]

_ACCEPT_RE = re.compile(
    r"\b(accept|accepted|agree|agreed|approve|approved|confirm|confirmed|ok|okay|fine with|proceed)\b",
    re.I,
)
_CHANGE_RE = re.compile(
    r"\b(change|should be|instead|correct(?:ion)?|update to|make it|use|revise to|rather)\b",
    re.I,
)
_VALUE_AFTER_RE = re.compile(
    r"(?:should be|change to|update to|make it|instead(?: use)?|use|revise to)\s*[:\-]?\s*(.+)",
    re.I,
)


def _normalize_value(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _values_match(stored: str, candidate: str) -> bool:
    a = _normalize_value(stored).casefold()
    b = _normalize_value(candidate).casefold()
    if not a or not b:
        return False
    return a == b or a in b or b in a


def classify_assumption_reply(body: str, stored_value: str) -> Classification:
    text = (body or "").strip()
    if not text:
        return "unclear"
    stored = _normalize_value(stored_value)
    extracted = ""
    m = _VALUE_AFTER_RE.search(text)
    if m:
        extracted = _normalize_value(m.group(1).strip(" .\"'"))
    if extracted and stored and not _values_match(stored, extracted):
        return "change"
    if _CHANGE_RE.search(text) and extracted and not _values_match(stored, extracted):
        return "change"
    if _CHANGE_RE.search(text) and not _ACCEPT_RE.search(text):
        # Changed wording without a parseable value — still unclear unless body differs wildly
        if extracted:
            return "change"
        return "unclear"
    if _ACCEPT_RE.search(text):
        if extracted and not _values_match(stored, extracted):
            return "change"
        return "accept"
    if stored and _values_match(stored, text):
        return "accept"
    return "unclear"


def _append_mail_log(revision_id: str, entry: dict[str, Any]) -> None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT assumption_mail_log_json FROM quote_revisions WHERE id = ?",
            (revision_id,),
        ).fetchone()
        log: list[dict[str, Any]] = []
        if row and row["assumption_mail_log_json"]:
            try:
                parsed = json.loads(str(row["assumption_mail_log_json"]))
                if isinstance(parsed, list):
                    log = parsed
            except json.JSONDecodeError:
                log = []
        log.append(entry)
        conn.execute(
            "UPDATE quote_revisions SET assumption_mail_log_json = ? WHERE id = ?",
            (json.dumps(log[-20:]), revision_id),
        )


def handle_customer_assumption_reply(
    session_id: str,
    cell: str,
    body: str,
    *,
    channel: str = "email",
) -> dict[str, Any]:
    """Apply customer reply to one assumption-tagged cell. WhatsApp never clears tags."""
    key = (cell or "").strip().lower()
    if key not in ASSUMPTION_DRAWING_CELLS:
        return {"ok": False, "error": f"cell {cell!r} is not assumption-capable"}

    ch = (channel or "").strip().lower()
    if ch not in {"email", "mail"}:
        return {
            "ok": True,
            "ignored": True,
            "reason": "only_email_clears_assumption_tags",
            "classification": "unclear",
        }

    init = init_drawing_cells(session_id)
    if not init.get("ok"):
        return init
    cells = dict(init["cells"])
    current = cells[key]
    if current.get("state") != "assumption":
        return {"ok": False, "error": f"{key} is not tagged assumption"}

    stored_value = str(current.get("value") or "")
    classification = classify_assumption_reply(body, stored_value)

    from .masterdata.quotes import revision_id_from_session

    revision_id = revision_id_from_session(session_id)

    if classification == "accept":
        cells[key] = {"state": "confirmed", "value": stored_value}
        _save_session_drawing_cells(session_id, cells)
        return {"ok": True, "classification": "accept", "cell": key, "cells": cells}

    if classification == "change":
        extracted = stored_value
        m = _VALUE_AFTER_RE.search(body or "")
        if m:
            extracted = _normalize_value(m.group(1).strip(" .\"'"))
        elif not _values_match(stored_value, body):
            extracted = _normalize_value(body)
        # Slice 5: counter-proposal stays proposed (not assumption) so send still blocks until owner confirms.
        cells[key] = {"state": "proposed", "value": extracted or stored_value}
        _save_session_drawing_cells(session_id, cells)
        return {"ok": True, "classification": "change", "cell": key, "cells": cells}

    mem_key = f"assumption_reply_unread_{key}"
    db.add_memory(session_id, mem_key, (body or "")[:2000])
    if revision_id:
        _append_mail_log(
            revision_id,
            {
                "cell": key,
                "classification": "unclear",
                "body_preview": (body or "")[:500],
                "at": db.utc_now(),
            },
        )
    return {
        "ok": True,
        "classification": "unclear",
        "cell": key,
        "cells": cells,
        "recorded": True,
    }
