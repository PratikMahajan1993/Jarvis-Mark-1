"""Quote operations and machine-hour attestation. Prices come from the owner or a rate row."""

from __future__ import annotations

import uuid
from typing import Any

from . import db
from .config import settings

_CASES = {"no_machine", "customer_asked", "capacity", "not_in_house"}
_TEMPLATES = {
    "turning": ("Turning", "", 0, ""),
    "milling": ("Milling", "", 0, ""),
    "edm": ("EDM", "", 0, ""),
    "heat_treat": ("Heat treat", "", 1, "not_in_house"),
    "plating": ("Plating", "", 1, "not_in_house"),
    "grinding": ("Grinding", "", 1, "not_in_house"),
}


def _rows(session_id: str) -> list[dict[str, Any]]:
    with db.connect() as conn:
        found = conn.execute(
            "SELECT * FROM quote_operations WHERE session_id = ? ORDER BY seq, id",
            (session_id,),
        ).fetchall()
    return [dict(row) for row in found]


def list_quote_operations(session_id: str) -> dict[str, Any]:
    return {"ok": True, "operations": _rows(session_id)}


def _next_seq(session_id: str) -> int:
    rows = _rows(session_id)
    if not rows:
        return 1
    return max(int(row["seq"]) for row in rows) + 1


def add_quote_operation(
    session_id: str,
    *,
    operation: str = "",
    template: str = "",
    machine_type: str = "",
    outsource: bool = False,
    outsource_case: str = "",
    outsource_vendor: str = "",
    outsource_price_inr: Any = "",
    special_tooling: str = "",
    setup_inr: Any = "",
    cycle_min: Any = "",
    notes: str = "",
) -> dict[str, Any]:
    name = (operation or "").strip()
    case = (outsource_case or "").strip().lower()
    is_out = bool(outsource)
    if template:
        preset = _TEMPLATES.get(template.strip().lower().replace(" ", "_"))
        if preset is None:
            return {"ok": False, "need": "operation", "message": "Unknown operation template."}
        if not name:
            name = preset[0]
        if not machine_type:
            machine_type = preset[1]
        if template and not outsource and not operation:
            is_out = bool(preset[2])
            if not case:
                case = preset[3]
    if not name:
        return {"ok": False, "need": "operation", "message": "Need an operation name."}
    if case and case not in _CASES:
        return {"ok": False, "need": "outsource_case", "message": "Outsource case must be one of the four recorded cases."}
    if is_out and not case:
        case = ""
    op_id = f"op-{uuid.uuid4().hex[:12]}"
    price_minor = _minor(outsource_price_inr)
    setup_minor = _minor(setup_inr)
    cycle = _float(cycle_min)
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO quote_operations (
              id, session_id, seq, operation, machine_type, outsource, outsource_case,
              outsource_vendor, outsource_price_minor, special_tooling, setup_minor,
              cycle_min, cycle_unit, currency, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'min', 'INR', ?)
            """,
            (
                op_id,
                session_id,
                _next_seq(session_id),
                name,
                (machine_type or "").strip(),
                1 if is_out else 0,
                case,
                (outsource_vendor or "").strip(),
                price_minor,
                (special_tooling or "").strip(),
                setup_minor,
                cycle,
                (notes or "").strip(),
            ),
        )
    return {"ok": True, "id": op_id, "operations": _rows(session_id)}


def update_quote_operation(session_id: str, operation_id: str, **fields: Any) -> dict[str, Any]:
    current = next((row for row in _rows(session_id) if row["id"] == operation_id), None)
    if current is None:
        return {"ok": False, "need": "operation", "message": "That operation is not on this quote."}
    allowed = {
        "operation": "operation",
        "machine_type": "machine_type",
        "outsource": "outsource",
        "outsource_case": "outsource_case",
        "outsource_vendor": "outsource_vendor",
        "special_tooling": "special_tooling",
        "notes": "notes",
        "outsource_received": "outsource_received",
    }
    sets: list[str] = []
    values: list[Any] = []
    for key, column in allowed.items():
        if key not in fields:
            continue
        value = fields[key]
        if key in {"outsource", "outsource_received"}:
            value = 1 if value else 0
        if key == "outsource_case":
            value = str(value or "").strip().lower()
            if value and value not in _CASES:
                return {"ok": False, "need": "outsource_case", "message": "Outsource case must be one of the four recorded cases."}
        sets.append(f"{column} = ?")
        values.append(value)
    if "outsource_price_inr" in fields:
        sets.append("outsource_price_minor = ?")
        values.append(_minor(fields["outsource_price_inr"]))
    if "setup_inr" in fields:
        sets.append("setup_minor = ?")
        values.append(_minor(fields["setup_inr"]))
    if "cycle_min" in fields:
        sets.append("cycle_min = ?")
        values.append(_float(fields["cycle_min"]))
    if not sets:
        return {"ok": True, "operations": _rows(session_id)}
    values.extend([operation_id, session_id])
    with db.connect() as conn:
        conn.execute(
            f"UPDATE quote_operations SET {', '.join(sets)} WHERE id = ? AND session_id = ?",
            values,
        )
    return {"ok": True, "operations": _rows(session_id)}


def delete_quote_operation(session_id: str, operation_id: str) -> dict[str, Any]:
    with db.connect() as conn:
        conn.execute(
            "DELETE FROM quote_operations WHERE id = ? AND session_id = ?",
            (operation_id, session_id),
        )
    _renumber(session_id)
    return {"ok": True, "operations": _rows(session_id)}


def reorder_quote_operations(session_id: str, ordered_ids: list[str]) -> dict[str, Any]:
    current = _rows(session_id)
    known = {row["id"] for row in current}
    if set(ordered_ids) != known or len(ordered_ids) != len(known):
        return {"ok": False, "need": "order", "message": "Reorder must list every operation on this quote once."}
    with db.connect() as conn:
        for index, op_id in enumerate(ordered_ids, start=1):
            conn.execute(
                "UPDATE quote_operations SET seq = ? WHERE id = ? AND session_id = ?",
                (index, op_id, session_id),
            )
    return {"ok": True, "operations": _rows(session_id)}


def _renumber(session_id: str) -> None:
    rows = _rows(session_id)
    with db.connect() as conn:
        for index, row in enumerate(rows, start=1):
            conn.execute("UPDATE quote_operations SET seq = ? WHERE id = ?", (index, row["id"]))


def outsource_checks(session_id: str) -> list[dict[str, Any]]:
    from .quote import _check

    checks: list[dict[str, Any]] = []
    for row in _rows(session_id):
        if not int(row.get("outsource") or 0):
            continue
        name = str(row.get("operation") or "operation")
        case = str(row.get("outsource_case") or "")
        price = row.get("outsource_price_minor")
        vendor = str(row.get("outsource_vendor") or "").strip()
        missing = []
        if case not in _CASES:
            missing.append("case")
        if price is None or int(price) <= 0:
            missing.append("price")
        if not vendor:
            missing.append("vendor")
        if missing:
            checks.append(
                _check(
                    "outsource_price",
                    False,
                    f"Outsource price/vendor missing for operation {name}",
                    "quote_operations",
                )
            )
        else:
            checks.append(
                _check(
                    "outsource_price",
                    True,
                    f"{name}: {vendor}, {case}",
                    "quote_operations",
                )
            )
            if settings.masterdata_enabled:
                from datetime import datetime
                from zoneinfo import ZoneInfo

                from .masterdata.lookup import outsource_quote_as_of

                as_of = datetime.now(ZoneInfo(settings.tz)).date().isoformat()
                with db.connect() as conn:
                    found = outsource_quote_as_of(conn, name, as_of)
                if found is None:
                    checks.append(
                        _check(
                            "outsource_quote_as_of",
                            False,
                            f"No outsource quote for {name} as of {as_of}",
                            "outsource_quotes",
                        )
                    )
                else:
                    checks.append(
                        _check(
                            "outsource_quote_as_of",
                            True,
                            f"Outsource quote {found['id']} as of {as_of}",
                            "outsource_quotes",
                        )
                    )
    return checks


def operation_line_items(session_id: str, machining_rate: Any = "") -> list[dict[str, Any]]:
    """Sheet lines from recorded operations. Missing prices stay blank."""
    from .quote import _parse_numeric

    rate = _parse_numeric(machining_rate)
    items: list[dict[str, Any]] = []
    for row in _rows(session_id):
        name = str(row.get("operation") or "Operation")
        if int(row.get("outsource") or 0):
            minor = row.get("outsource_price_minor")
            price: Any = ""
            if minor is not None and int(minor) > 0:
                price = int(minor) / 100
            items.append(
                {
                    "item": name,
                    "material": str(row.get("outsource_vendor") or ""),
                    "qty": 1,
                    "unit_price": price,
                    "notes": _outsource_note(row),
                    "outsource": True,
                }
            )
            continue
        cycle = row.get("cycle_min")
        setup = row.get("setup_minor")
        notes = []
        if row.get("machine_type"):
            notes.append(str(row["machine_type"]))
        if cycle is not None:
            notes.append(f"{cycle} min")
        if setup is not None:
            notes.append(f"setup ₹{int(setup) / 100:g}")
        if row.get("special_tooling"):
            notes.append(str(row["special_tooling"]))
        price = ""
        if rate is not None and rate > 0:
            amount = 0.0
            if setup is not None:
                amount += int(setup) / 100
            if cycle is not None:
                amount += (float(cycle) / 60.0) * rate
            if amount > 0:
                price = round(amount, 2)
        items.append(
            {
                "item": name,
                "material": str(row.get("machine_type") or ""),
                "qty": 1,
                "unit_price": price,
                "notes": "; ".join(notes),
            }
        )
    return items


def _outsource_note(row: dict[str, Any]) -> str:
    parts = [str(row.get("outsource_case") or ""), str(row.get("notes") or ""), str(row.get("special_tooling") or "")]
    return "; ".join(part for part in parts if part)


def list_mhr_rates() -> dict[str, Any]:
    if not settings.masterdata_enabled:
        from .quote import MHR_DEMO_PATH, _parse_numeric

        rates = []
        if MHR_DEMO_PATH.is_file():
            for line in MHR_DEMO_PATH.read_text(encoding="utf-8").splitlines():
                if "|" not in line:
                    continue
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) < 2:
                    continue
                head = parts[0].lower()
                if head in {"machine type", "---", "machine type (demo)"} or head.startswith("-"):
                    continue
                rate = _parse_numeric(parts[1])
                if rate is None:
                    continue
                rates.append(
                    {
                        "id": "",
                        "machine_type": parts[0].strip(),
                        "floor_inr": rate,
                        "attested_by": "",
                        "attested_at": "",
                        "status": "demo_seed",
                    }
                )
        return {"ok": True, "rates": rates}
    from .masterdata.mhr_lookup import sync_mhr_demo_if_enabled

    with db.connect() as conn:
        sync_mhr_demo_if_enabled(conn)
        found = conn.execute(
            """
            SELECT id, machine_type, min_mhr_minor, currency, attested_by, attested_at, shipped_seed_value_minor
            FROM machine_hour_rates
            ORDER BY machine_type
            """
        ).fetchall()
    rates = []
    for row in found:
        attested = str(row["attested_by"] or "").strip()
        seed = row["shipped_seed_value_minor"]
        same_seed = seed is not None and int(row["min_mhr_minor"]) == int(seed)
        if attested and not same_seed:
            status = "attested"
        elif not attested and same_seed:
            status = "demo_seed"
        else:
            status = "needs_attestation"
        rates.append(
            {
                "id": row["id"],
                "machine_type": row["machine_type"] or "",
                "floor_inr": int(row["min_mhr_minor"]) / 100,
                "currency": row["currency"] or "INR",
                "attested_by": attested,
                "attested_at": row["attested_at"] or "",
                "status": status,
            }
        )
    return {"ok": True, "rates": rates}


def attest_mhr_rate(*, rate_id: str = "", machine_type: str = "", attested_by: str = "", floor_inr: Any = "") -> dict[str, Any]:
    who = (attested_by or "").strip()
    if not who:
        return {"ok": False, "need": "attested_by", "message": "Need the owner's name to attest a rate."}
    if not settings.masterdata_enabled:
        return {"ok": False, "need": "masterdata", "message": "Machine-hour rates are not in the database until master data is on."}
    from .quote import _parse_numeric

    new_minor = None
    parsed = _parse_numeric(floor_inr)
    if parsed is not None:
        new_minor = int(round(parsed * 100))
    with db.connect() as conn:
        if rate_id:
            row = conn.execute("SELECT * FROM machine_hour_rates WHERE id = ?", (rate_id,)).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM machine_hour_rates WHERE machine_type = ? COLLATE NOCASE ORDER BY effective_from DESC LIMIT 1",
                ((machine_type or "").strip(),),
            ).fetchone()
        if row is None:
            return {"ok": False, "need": "rate", "message": "That machine is not in the rate table."}
        seed = row["shipped_seed_value_minor"]
        value = new_minor if new_minor is not None else int(row["min_mhr_minor"])
        if seed is not None and value == int(seed):
            return {
                "ok": False,
                "need": "rate",
                "message": "That is still the shipped demo seed. Attest a rate that differs from the seed.",
            }
        conn.execute(
            """
            UPDATE machine_hour_rates
            SET min_mhr_minor = ?, attested_by = ?, attested_at = ?, source_kind = 'owner_input'
            WHERE id = ?
            """,
            (value, who, db.utc_now(), row["id"]),
        )
    return {"ok": True, "rates": list_mhr_rates()["rates"]}


def _minor(value: Any) -> int | None:
    from .quote import _parse_numeric

    parsed = _parse_numeric(value)
    if parsed is None:
        return None
    if parsed < 0:
        return None
    return int(round(parsed * 100))


def _float(value: Any) -> float | None:
    from .quote import _parse_numeric

    parsed = _parse_numeric(value)
    return parsed
