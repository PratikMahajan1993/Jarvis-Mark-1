"""Supersede authoritative master rows. Never hard-delete them."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from ..config import settings
from ..db import utc_now


class LifecycleError(ValueError):
    """Supersede rejected."""


_RATE_TABLES = frozenset({"machine_hour_rates", "supplier_rm_quotes", "outsource_quotes"})


def _today() -> str:
    return datetime.now(ZoneInfo(settings.tz)).date().isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _audit(conn: sqlite3.Connection, detail: str) -> None:
    conn.execute(
        "INSERT INTO audit (session_id, tool, detail, status, created_at) VALUES (?, ?, ?, ?, ?)",
        ("masterdata", "supersede", detail[:400], "ok", utc_now()),
    )


def _row(conn: sqlite3.Connection, table: str, row_id: str) -> sqlite3.Row:
    found = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()
    if found is None:
        raise LifecycleError("Record was not found.")
    return found


def _end_date(conn: sqlite3.Connection, table: str, row_id: str, day: str, successor: str) -> None:
    if table in {"customers", "machines"}:
        conn.execute(
            f"""
            UPDATE {table}
            SET effective_to = ?, superseded_by = ?, status = 'superseded'
            WHERE id = ?
            """,
            (day, successor, row_id),
        )
        return
    conn.execute(
        f"""
        UPDATE {table}
        SET effective_to = ?, superseded_by = ?
        WHERE id = ?
        """,
        (day, successor, row_id),
    )


def supersede_customer(conn: sqlite3.Connection, old_id: str, new_customer_data: dict) -> str:
    old = _row(conn, "customers", old_id)
    name = (new_customer_data.get("name") or "").strip()
    if not name:
        raise LifecycleError("Customer name is required.")
    day = _today()
    new_id = _new_id("cust")
    # Free UNIQUE(name) without destroying the old row's other fields.
    conn.execute(
        "UPDATE customers SET name = ? WHERE id = ?",
        (f"{old['name']} [superseded {old_id}]", old_id),
    )
    conn.execute(
        """
        INSERT INTO customers (id, name, gstin, currency, status, effective_from)
        VALUES (?, ?, ?, ?, 'active', ?)
        """,
        (
            new_id,
            name,
            new_customer_data.get("gstin") or None,
            (new_customer_data.get("currency") or old["currency"] or "INR"),
            day,
        ),
    )
    _end_date(conn, "customers", old_id, day, new_id)
    terms = conn.execute("SELECT * FROM customer_terms WHERE customer_id = ?", (old_id,)).fetchone()
    scope = (new_customer_data.get("default_scope") or (terms["default_scope"] if terms else "ask") or "ask")
    if scope not in {"labour", "with_material", "ask"}:
        raise LifecycleError("default_scope must be labour, with_material, or ask.")
    pay = new_customer_data.get("payment_terms_days")
    if pay is None and terms is not None:
        pay = terms["payment_terms_days"]
    conn.execute(
        """
        INSERT INTO customer_terms (
          customer_id, default_scope, payment_terms_days, delivery_basis, nda,
          allow_cloud_vision, vision_consent_by, vision_consent_at, quote_validity_days
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id,
            scope,
            pay,
            (terms["delivery_basis"] if terms else None),
            int(new_customer_data.get("nda") if new_customer_data.get("nda") is not None else (terms["nda"] if terms else 0)),
            int(
                new_customer_data.get("allow_cloud_vision")
                if new_customer_data.get("allow_cloud_vision") is not None
                else (terms["allow_cloud_vision"] if terms else 0)
            ),
            (terms["vision_consent_by"] if terms else None),
            (terms["vision_consent_at"] if terms else None),
            int(terms["quote_validity_days"] if terms else 30),
        ),
    )
    _audit(conn, f"supersede customer {old_id} -> {new_id}")
    return new_id


def supersede_machine(conn: sqlite3.Connection, old_id: str, new_machine_data: dict) -> str:
    old = _row(conn, "machines", old_id)
    name = (new_machine_data.get("name") or old["name"] or "").strip()
    machine_type = (new_machine_data.get("machine_type") or old["machine_type"] or "").strip()
    if not name or not machine_type:
        raise LifecycleError("Machine name and type are required.")
    day = _today()
    new_id = _new_id("mach")
    conn.execute(
        """
        INSERT INTO machines (
          id, name, machine_type, control_make, control_model, axes,
          travel_x, travel_y, travel_z, max_rpm, spindle_kw, bar_capacity_mm, chuck_mm,
          rapid_x, rapid_y, rapid_z, accel_g, accuracy_class, status, effective_from
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'running', ?)
        """,
        (
            new_id,
            name,
            machine_type,
            (new_machine_data.get("control_make") or old["control_make"]),
            (new_machine_data.get("control_model") or old["control_model"]),
            new_machine_data.get("axes", old["axes"]),
            new_machine_data.get("travel_x", old["travel_x"]),
            new_machine_data.get("travel_y", old["travel_y"]),
            new_machine_data.get("travel_z", old["travel_z"]),
            new_machine_data.get("max_rpm", old["max_rpm"]),
            new_machine_data.get("spindle_kw", old["spindle_kw"]),
            new_machine_data.get("bar_capacity_mm", old["bar_capacity_mm"]),
            new_machine_data.get("chuck_mm", old["chuck_mm"]),
            new_machine_data.get("rapid_x", old["rapid_x"]),
            new_machine_data.get("rapid_y", old["rapid_y"]),
            new_machine_data.get("rapid_z", old["rapid_z"]),
            new_machine_data.get("accel_g", old["accel_g"]),
            new_machine_data.get("accuracy_class", old["accuracy_class"]),
            day,
        ),
    )
    _end_date(conn, "machines", old_id, day, new_id)
    _audit(conn, f"supersede machine {old_id} -> {new_id}")
    return new_id


def supersede_material(conn: sqlite3.Connection, old_id: str, new_material_data: dict) -> str:
    old = _row(conn, "materials", old_id)
    grade = (new_material_data.get("grade") or "").strip()
    if not grade:
        raise LifecycleError("Material grade is required.")
    day = _today()
    new_id = _new_id("mat")
    conn.execute(
        "UPDATE materials SET grade = ? WHERE id = ?",
        (f"{old['grade']} [superseded {old_id}]", old_id),
    )
    form = (new_material_data.get("form") or old["form"] or "bar").strip()
    family = (new_material_data.get("family") or old["family"] or "").strip()
    conn.execute(
        """
        INSERT INTO materials (
          id, grade, family, standard, density_kg_m3, machinability_index,
          hardness_spec, form, notes, effective_from
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id,
            grade,
            family,
            new_material_data.get("standard", old["standard"]),
            new_material_data.get("density_kg_m3", old["density_kg_m3"]),
            new_material_data.get("machinability_index", old["machinability_index"]),
            new_material_data.get("hardness_spec", old["hardness_spec"]),
            form,
            new_material_data.get("notes", old["notes"]) or "",
            day,
        ),
    )
    _end_date(conn, "materials", old_id, day, new_id)
    _audit(conn, f"supersede material {old_id} -> {new_id}")
    return new_id


def supersede_supplier(conn: sqlite3.Connection, old_id: str, new_supplier_data: dict) -> str:
    old = _row(conn, "suppliers", old_id)
    name = (new_supplier_data.get("name") or "").strip()
    if not name:
        raise LifecycleError("Supplier name is required.")
    day = _today()
    new_id = _new_id("sup")
    conn.execute(
        "UPDATE suppliers SET name = ? WHERE id = ?",
        (f"{old['name']} [superseded {old_id}]", old_id),
    )
    conn.execute(
        """
        INSERT INTO suppliers (id, name, contact, lead_days, effective_from)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            new_id,
            name,
            new_supplier_data.get("contact", old["contact"]),
            new_supplier_data.get("lead_days", old["lead_days"]),
            day,
        ),
    )
    _end_date(conn, "suppliers", old_id, day, new_id)
    _audit(conn, f"supersede supplier {old_id} -> {new_id}")
    return new_id


def supersede_outsource_vendor(conn: sqlite3.Connection, old_id: str, new_vendor_data: dict) -> str:
    old = _row(conn, "outsource_vendors", old_id)
    name = (new_vendor_data.get("name") or "").strip()
    processes = (new_vendor_data.get("processes") or old["processes"] or "").strip()
    if not name or not processes:
        raise LifecycleError("Vendor name and processes are required.")
    day = _today()
    new_id = _new_id("osv")
    conn.execute(
        "UPDATE outsource_vendors SET name = ? WHERE id = ?",
        (f"{old['name']} [superseded {old_id}]", old_id),
    )
    conn.execute(
        """
        INSERT INTO outsource_vendors (id, name, processes, lead_days, effective_from)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            new_id,
            name,
            processes,
            new_vendor_data.get("lead_days", old["lead_days"]),
            day,
        ),
    )
    _end_date(conn, "outsource_vendors", old_id, day, new_id)
    _audit(conn, f"supersede outsource vendor {old_id} -> {new_id}")
    return new_id


def supersede_rate(
    conn: sqlite3.Connection,
    table: str,
    old_id: str,
    new_rate_data: dict,
    effective_from: str,
) -> str:
    if table not in _RATE_TABLES:
        raise LifecycleError("Unknown rate table.")
    day = (effective_from or "").strip()[:10]
    if len(day) != 10:
        raise LifecycleError("effective_from must be YYYY-MM-DD.")
    old = _row(conn, table, old_id)
    if str(old["effective_from"]) > day:
        raise LifecycleError("New effective_from is before the row it replaces.")
    # Only the window moves. Attestation and provenance on the old row stay.
    conn.execute(
        f"UPDATE {table} SET effective_to = ? WHERE id = ?",
        (day, old_id),
    )
    if table == "machine_hour_rates":
        new_id = _insert_mhr(conn, old, new_rate_data, day)
    elif table == "supplier_rm_quotes":
        new_id = _insert_rm(conn, old, new_rate_data, day)
    else:
        new_id = _insert_outsource_quote(conn, old, new_rate_data, day)
    _audit(conn, f"supersede {table} {old_id} -> {new_id}")
    return new_id


def _insert_mhr(conn: sqlite3.Connection, old: sqlite3.Row, data: dict, day: str) -> str:
    new_id = _new_id("mhr")
    minor = data.get("min_mhr_minor")
    if minor is None and data.get("min_mhr") is not None:
        minor = int(round(float(data["min_mhr"]) * 100))
    if minor is None:
        minor = int(old["min_mhr_minor"])
    target = data.get("target_mhr_minor", old["target_mhr_minor"])
    conn.execute(
        """
        INSERT INTO machine_hour_rates (
          id, machine_id, machine_type, min_mhr_minor, target_mhr_minor, currency,
          effective_from, effective_to, source_kind, source_ref,
          attested_by, attested_at, shipped_seed_value_minor
        ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?)
        """,
        (
            new_id,
            data.get("machine_id", old["machine_id"]),
            data.get("machine_type", old["machine_type"]),
            int(minor),
            target,
            data.get("currency", old["currency"]) or "INR",
            day,
            data.get("source_kind", old["source_kind"]) or "owner_input",
            data.get("source_ref", old["source_ref"]) or "",
            data.get("attested_by", "") or "",
            data.get("attested_at"),
            old["shipped_seed_value_minor"],
        ),
    )
    return new_id


def _insert_rm(conn: sqlite3.Connection, old: sqlite3.Row, data: dict, day: str) -> str:
    new_id = _new_id("rmq")
    price = data.get("price_minor")
    if price is None and data.get("price") is not None:
        price = int(round(float(data["price"]) * 100))
    if price is None:
        price = int(old["price_minor"])
    conn.execute(
        """
        INSERT INTO supplier_rm_quotes (
          id, supplier_id, material_id, size_spec, unit_basis, price_minor, currency,
          min_qty, qty_break, effective_from, effective_to, basis_date,
          source_kind, source_ref, is_estimate, estimate_basis,
          attested_by, attested_at, shipped_seed_value_minor
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id,
            data.get("supplier_id", old["supplier_id"]),
            data.get("material_id", old["material_id"]),
            data.get("size_spec", old["size_spec"]),
            data.get("unit_basis", old["unit_basis"]),
            int(price),
            data.get("currency", old["currency"]) or "INR",
            data.get("min_qty", old["min_qty"]),
            data.get("qty_break", old["qty_break"]),
            day,
            data.get("basis_date", day),
            data.get("source_kind", old["source_kind"]),
            data.get("source_ref", old["source_ref"]) or "",
            int(data.get("is_estimate", old["is_estimate"]) or 0),
            data.get("estimate_basis", old["estimate_basis"]) or "",
            data.get("attested_by", "") or "",
            data.get("attested_at"),
            old["shipped_seed_value_minor"],
        ),
    )
    return new_id


def _insert_outsource_quote(conn: sqlite3.Connection, old: sqlite3.Row, data: dict, day: str) -> str:
    new_id = _new_id("osq")
    price = data.get("price_minor", old["price_minor"])
    conn.execute(
        """
        INSERT INTO outsource_quotes (
          id, vendor_id, process, spec, unit_basis, price_minor, min_lot_minor, currency,
          lead_days, effective_from, effective_to, source_kind, source_ref
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
        """,
        (
            new_id,
            data.get("vendor_id", old["vendor_id"]),
            data.get("process", old["process"]),
            data.get("spec", old["spec"]),
            data.get("unit_basis", old["unit_basis"]),
            int(price),
            data.get("min_lot_minor", old["min_lot_minor"]),
            data.get("currency", old["currency"]) or "INR",
            data.get("lead_days", old["lead_days"]),
            day,
            data.get("source_kind", old["source_kind"]),
            data.get("source_ref", old["source_ref"]) or "",
        ),
    )
    return new_id
