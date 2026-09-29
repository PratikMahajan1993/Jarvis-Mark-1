"""Create helpers for master-data rows. Duplicate names/numbers refuse with the existing row."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from ..config import settings
from ..core.features import publish
from ..db import utc_now


class DuplicateError(ValueError):
    """Active row already exists; ``existing`` is the current row as a dict."""

    def __init__(self, message: str, existing: dict[str, Any]):
        super().__init__(message)
        self.existing = existing


class CreateError(ValueError):
    """Create rejected (missing fields, unknown customer, etc.)."""


def _today() -> str:
    return datetime.now(ZoneInfo(settings.tz)).date().isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y"}


def _publish_changed(kind: str, name: str, row_id: str) -> None:
    publish(
        "masterdata.changed",
        {"kind": kind, "name": name, "id": row_id, "at": utc_now()},
    )


def _active_customer_by_name(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT c.*, t.default_scope, t.payment_terms_days, t.nda, t.allow_cloud_vision
        FROM customers c
        LEFT JOIN customer_terms t ON t.customer_id = c.id
        WHERE c.name = ? COLLATE NOCASE
          AND c.effective_to IS NULL
          AND COALESCE(c.status, '') != 'superseded'
        LIMIT 1
        """,
        (name,),
    ).fetchone()


def _active_supplier_by_name(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM suppliers
        WHERE name = ? COLLATE NOCASE
          AND effective_to IS NULL
        LIMIT 1
        """,
        (name,),
    ).fetchone()


def _active_product_by_number(conn: sqlite3.Connection, product_number: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT p.*, c.name AS customer_name
        FROM products p
        LEFT JOIN customers c ON c.id = p.customer_id
        WHERE p.product_number = ? COLLATE NOCASE
          AND p.effective_to IS NULL
          AND COALESCE(p.status, '') != 'superseded'
        LIMIT 1
        """,
        (product_number,),
    ).fetchone()


def create_customer(conn: sqlite3.Connection, fields: dict[str, Any], *, notify: bool = True) -> dict[str, Any]:
    name = (fields.get("name") or "").strip()
    if not name:
        raise CreateError("Customer name is required.")
    existing = _active_customer_by_name(conn, name)
    if existing is not None:
        raise DuplicateError(f"Customer '{name}' already exists.", dict(existing))

    # Create form: NDA yes → nda=1 and cloud vision denied; no → both denied. Scope stays ask.
    nda = 1 if _truthy(fields.get("nda")) else 0
    allow_cloud = 0
    scope = (fields.get("default_scope") or "ask").strip() or "ask"
    if scope not in {"labour", "with_material", "ask"}:
        raise CreateError("default_scope must be labour, with_material, or ask.")

    cid = _new_id("cust")
    conn.execute(
        """
        INSERT INTO customers (id, name, gstin, currency, status, effective_from)
        VALUES (?, ?, ?, ?, 'active', ?)
        """,
        (
            cid,
            name,
            fields.get("gstin") or None,
            (fields.get("currency") or "INR").strip() or "INR",
            _today(),
        ),
    )
    conn.execute(
        """
        INSERT INTO customer_terms (
          customer_id, default_scope, payment_terms_days, nda, allow_cloud_vision, quote_validity_days
        ) VALUES (?, ?, ?, ?, ?, 30)
        """,
        (
            cid,
            scope,
            fields.get("payment_terms_days"),
            nda,
            allow_cloud,
        ),
    )
    conn.execute(
        "INSERT OR IGNORE INTO customer_aliases (customer_id, alias, source) VALUES (?, ?, 'manual')",
        (cid, name),
    )
    if notify:
        _publish_changed("customer", name, cid)
    return {"ok": True, "id": cid, "name": name, "nda": nda, "allow_cloud_vision": allow_cloud}


def create_supplier(conn: sqlite3.Connection, fields: dict[str, Any], *, notify: bool = True) -> dict[str, Any]:
    name = (fields.get("name") or "").strip()
    if not name:
        raise CreateError("Supplier name is required.")
    existing = _active_supplier_by_name(conn, name)
    if existing is not None:
        raise DuplicateError(f"Supplier '{name}' already exists.", dict(existing))

    sid = _new_id("sup")
    conn.execute(
        """
        INSERT INTO suppliers (id, name, contact, lead_days, effective_from)
        VALUES (?, ?, ?, ?, ?)
        """,
        (sid, name, fields.get("contact"), fields.get("lead_days"), _today()),
    )
    if notify:
        _publish_changed("supplier", name, sid)
    return {"ok": True, "id": sid, "name": name}


def create_product(conn: sqlite3.Connection, fields: dict[str, Any], *, notify: bool = True) -> dict[str, Any]:
    name = (fields.get("name") or "").strip()
    product_number = (fields.get("product_number") or "").strip()
    customer_id = (fields.get("customer_id") or "").strip()
    customer_name = (fields.get("customer") or fields.get("customer_name") or "").strip()
    uom = (fields.get("uom") or "").strip()
    if not name:
        raise CreateError("Product name is required.")
    if not product_number:
        raise CreateError("Product number is required.")
    if not uom:
        raise CreateError("Unit of measure is required.")
    if "monitor_stock" not in fields or fields.get("monitor_stock") is None or str(fields.get("monitor_stock")).strip() == "":
        raise CreateError("monitor_stock yes/no is required.")

    if not customer_id and customer_name:
        cust = _active_customer_by_name(conn, customer_name)
        if cust is None:
            raise CreateError(f"Customer '{customer_name}' was not found. Create the customer first — do not invent one.")
        customer_id = str(cust["id"])
    if not customer_id:
        raise CreateError("Customer is required.")

    cust_row = conn.execute(
        """
        SELECT id, name FROM customers
        WHERE id = ? AND effective_to IS NULL AND COALESCE(status, '') != 'superseded'
        """,
        (customer_id,),
    ).fetchone()
    if cust_row is None:
        raise CreateError("Customer was not found or is superseded.")

    existing = _active_product_by_number(conn, product_number)
    if existing is not None:
        raise DuplicateError(f"Product number '{product_number}' already exists.", dict(existing))

    material_id = (fields.get("material_id") or "").strip() or None
    if material_id:
        mat = conn.execute(
            "SELECT id FROM materials WHERE id = ? AND effective_to IS NULL",
            (material_id,),
        ).fetchone()
        if mat is None:
            raise CreateError("material_id was not found among active materials.")

    monitor_stock = 1 if _truthy(fields.get("monitor_stock")) else 0
    pid = _new_id("prod")
    conn.execute(
        """
        INSERT INTO products (
          id, product_number, name, customer_id, uom, monitor_stock, material_id,
          status, effective_from
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?)
        """,
        (pid, product_number, name, customer_id, uom, monitor_stock, material_id, _today()),
    )
    if notify:
        _publish_changed("product", name, pid)
    return {
        "ok": True,
        "id": pid,
        "name": name,
        "product_number": product_number,
        "customer_id": customer_id,
        "customer_name": cust_row["name"],
        "monitor_stock": monitor_stock,
    }
