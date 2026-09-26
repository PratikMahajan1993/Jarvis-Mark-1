"""REST API for the Master Data page. PATCH supersedes; DELETE is refused."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import db
from ..config import settings
from .aliases import (
    AliasError,
    add_customer_alias,
    add_machine_alias,
    add_vendor_alias,
    list_customer_aliases,
    list_machine_aliases,
    list_vendor_aliases,
    remove_customer_alias,
    remove_machine_alias,
    remove_vendor_alias,
    resolve_customer_alias,
    resolve_machine_alias,
    resolve_vendor_alias,
)
from .lifecycle import (
    LifecycleError,
    supersede_customer,
    supersede_machine,
    supersede_material,
    supersede_outsource_vendor,
    supersede_rate,
    supersede_supplier,
)
from .lookup import (
    machine_capability_as_of,
    material_id_for_grade,
    outsource_quote_as_of,
    supplier_rm_quote_as_of,
)
from .seed_master_data import seed_master_data

router = APIRouter(prefix="/api/masterdata", tags=["masterdata"])


class AliasBody(BaseModel):
    kind: str
    canonical_id: str
    alias: str
    source: str = "manual"


class EntityBody(BaseModel):
    fields: dict[str, Any] = Field(default_factory=dict)


def _today() -> str:
    return datetime.now(ZoneInfo(settings.tz)).date().isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _minor(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(round(float(value) * 100))


def _rows(conn, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _require(fields: dict[str, Any], *keys: str) -> None:
    missing = [key for key in keys if not str(fields.get(key) or "").strip()]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing {', '.join(missing)}")


@router.get("/options")
def masterdata_options() -> dict[str, Any]:
    """Machines, materials, and customers for quote dropdowns. Active rows only."""
    with db.connect() as conn:
        if settings.masterdata_enabled:
            seed_master_data(conn)
        return {
            "ok": True,
            "machines": _rows(
                conn,
                """
                SELECT id, name, machine_type FROM machines
                WHERE effective_to IS NULL AND status != 'superseded'
                ORDER BY name COLLATE NOCASE
                """,
            ),
            "materials": _rows(
                conn,
                """
                SELECT id, grade, family, form FROM materials
                WHERE effective_to IS NULL
                ORDER BY grade COLLATE NOCASE
                """,
            ),
            "customers": _rows(
                conn,
                """
                SELECT id, name FROM customers
                WHERE effective_to IS NULL AND status != 'superseded'
                ORDER BY name COLLATE NOCASE
                """,
            ),
        }


@router.post("/seed")
def masterdata_seed() -> dict[str, Any]:
    with db.connect() as conn:
        counts = seed_master_data(conn)
    return {"ok": True, "counts": counts}


@router.get("/customers")
def list_customers() -> dict[str, Any]:
    with db.connect() as conn:
        items = _rows(
            conn,
            """
            SELECT c.*, t.default_scope, t.payment_terms_days, t.nda, t.allow_cloud_vision,
                   t.vision_consent_by, t.vision_consent_at
            FROM customers c
            LEFT JOIN customer_terms t ON t.customer_id = c.id
            ORDER BY c.name COLLATE NOCASE
            """,
        )
    return {"ok": True, "items": items}


@router.post("/customers")
def create_customer(body: EntityBody) -> dict[str, Any]:
    fields = body.fields
    _require(fields, "name")
    scope = (fields.get("default_scope") or "ask").strip()
    if scope not in {"labour", "with_material", "ask"}:
        raise HTTPException(status_code=400, detail="default_scope must be labour, with_material, or ask")
    cid = _new_id("cust")
    with db.connect() as conn:
        try:
            conn.execute(
                """
                INSERT INTO customers (id, name, gstin, currency, status, effective_from)
                VALUES (?, ?, ?, ?, 'active', ?)
                """,
                (
                    cid,
                    fields["name"].strip(),
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
                    int(fields.get("nda") or 0),
                    int(fields.get("allow_cloud_vision") or 0),
                ),
            )
            conn.execute(
                "INSERT OR IGNORE INTO customer_aliases (customer_id, alias, source) VALUES (?, ?, 'manual')",
                (cid, fields["name"].strip()),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "id": cid}


@router.patch("/customers/{row_id}")
def replace_customer(row_id: str, body: EntityBody) -> dict[str, Any]:
    try:
        with db.connect() as conn:
            new_id = supersede_customer(conn, row_id, body.fields)
    except LifecycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "id": new_id, "superseded": row_id}


@router.get("/machines")
def list_machines() -> dict[str, Any]:
    with db.connect() as conn:
        items = _rows(conn, "SELECT * FROM machines ORDER BY name COLLATE NOCASE")
        for item in items:
            item["capabilities"] = _rows(
                conn,
                "SELECT * FROM machine_capabilities WHERE machine_id = ?",
                (item["id"],),
            )
    return {"ok": True, "items": items}


@router.post("/machines")
def create_machine(body: EntityBody) -> dict[str, Any]:
    fields = body.fields
    _require(fields, "name", "machine_type", "control_make", "control_model")
    mid = _new_id("mach")
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO machines (
              id, name, machine_type, control_make, control_model, axes,
              travel_x, travel_y, travel_z, max_rpm, spindle_kw, bar_capacity_mm, chuck_mm,
              rapid_x, rapid_y, rapid_z, status, effective_from
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'running', ?)
            """,
            (
                mid,
                fields["name"].strip(),
                fields["machine_type"].strip(),
                fields["control_make"].strip(),
                fields["control_model"].strip(),
                fields.get("axes"),
                fields.get("travel_x"),
                fields.get("travel_y"),
                fields.get("travel_z"),
                fields.get("max_rpm"),
                fields.get("spindle_kw"),
                fields.get("bar_capacity_mm"),
                fields.get("chuck_mm"),
                fields.get("rapid_x"),
                fields.get("rapid_y"),
                fields.get("rapid_z"),
                _today(),
            ),
        )
        process = (fields.get("capability_process") or "").strip()
        if process:
            conn.execute(
                """
                INSERT INTO machine_capabilities (machine_id, process, tolerance_floor_mm, finish_floor_ra)
                VALUES (?, ?, ?, ?)
                """,
                (mid, process, fields.get("tolerance_floor_mm"), fields.get("finish_floor_ra")),
            )
    return {"ok": True, "id": mid}


@router.patch("/machines/{row_id}")
def replace_machine(row_id: str, body: EntityBody) -> dict[str, Any]:
    try:
        with db.connect() as conn:
            new_id = supersede_machine(conn, row_id, body.fields)
    except LifecycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "id": new_id, "superseded": row_id}


@router.get("/materials")
def list_materials() -> dict[str, Any]:
    with db.connect() as conn:
        items = _rows(conn, "SELECT * FROM materials ORDER BY grade COLLATE NOCASE")
        for item in items:
            item["equivalents"] = _rows(
                conn,
                "SELECT equivalent_grade, standard, confirmed_by FROM material_equivalents WHERE material_id = ?",
                (item["id"],),
            )
    return {"ok": True, "items": items}


@router.post("/materials")
def create_material(body: EntityBody) -> dict[str, Any]:
    fields = body.fields
    _require(fields, "grade", "family", "form")
    mid = _new_id("mat")
    with db.connect() as conn:
        try:
            conn.execute(
                """
                INSERT INTO materials (
                  id, grade, family, standard, density_kg_m3, machinability_index,
                  hardness_spec, form, notes, effective_from
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mid,
                    fields["grade"].strip(),
                    fields["family"].strip(),
                    fields.get("standard"),
                    fields.get("density_kg_m3"),
                    fields.get("machinability_index"),
                    fields.get("hardness_spec"),
                    fields["form"].strip(),
                    fields.get("notes") or "",
                    _today(),
                ),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        equiv = (fields.get("equivalent_grade") or "").strip()
        if equiv:
            confirmed = (fields.get("confirmed_by") or "").strip()
            if not confirmed:
                raise HTTPException(status_code=400, detail="confirmed_by is required for an equivalent")
            conn.execute(
                """
                INSERT INTO material_equivalents (material_id, equivalent_grade, standard, confirmed_by)
                VALUES (?, ?, ?, ?)
                """,
                (mid, equiv, fields.get("equivalent_standard"), confirmed),
            )
    return {"ok": True, "id": mid}


@router.patch("/materials/{row_id}")
def replace_material(row_id: str, body: EntityBody) -> dict[str, Any]:
    try:
        with db.connect() as conn:
            new_id = supersede_material(conn, row_id, body.fields)
    except LifecycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "id": new_id, "superseded": row_id}


@router.get("/suppliers")
def list_suppliers() -> dict[str, Any]:
    with db.connect() as conn:
        items = _rows(conn, "SELECT * FROM suppliers ORDER BY name COLLATE NOCASE")
    return {"ok": True, "items": items}


@router.post("/suppliers")
def create_supplier(body: EntityBody) -> dict[str, Any]:
    fields = body.fields
    _require(fields, "name")
    sid = _new_id("sup")
    with db.connect() as conn:
        try:
            conn.execute(
                """
                INSERT INTO suppliers (id, name, contact, lead_days, effective_from)
                VALUES (?, ?, ?, ?, ?)
                """,
                (sid, fields["name"].strip(), fields.get("contact"), fields.get("lead_days"), _today()),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "id": sid}


@router.patch("/suppliers/{row_id}")
def replace_supplier(row_id: str, body: EntityBody) -> dict[str, Any]:
    try:
        with db.connect() as conn:
            new_id = supersede_supplier(conn, row_id, body.fields)
    except LifecycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "id": new_id, "superseded": row_id}


@router.get("/mhr")
def list_mhr() -> dict[str, Any]:
    with db.connect() as conn:
        items = _rows(
            conn,
            """
            SELECT id, machine_id, machine_type, min_mhr_minor, target_mhr_minor, currency,
                   effective_from, effective_to, source_kind, source_ref,
                   attested_by, attested_at, shipped_seed_value_minor
            FROM machine_hour_rates
            ORDER BY machine_type COLLATE NOCASE, effective_from
            """,
        )
    for item in items:
        item["min_mhr_inr"] = int(item["min_mhr_minor"]) / 100
        target = item.get("target_mhr_minor")
        item["target_mhr_inr"] = int(target) / 100 if target is not None else None
        item["current"] = item.get("effective_to") in (None, "")
    return {"ok": True, "items": items}


@router.post("/mhr")
def create_mhr(body: EntityBody) -> dict[str, Any]:
    fields = body.fields
    _require(fields, "machine_type", "effective_from")
    minor = fields.get("min_mhr_minor")
    if minor is None:
        minor = _minor(fields.get("min_mhr_inr"))
    if minor is None:
        raise HTTPException(status_code=400, detail="min_mhr_inr is required")
    day = str(fields["effective_from"]).strip()[:10]
    machine_type = fields["machine_type"].strip()
    rid = _new_id("mhr")
    with db.connect() as conn:
        open_row = conn.execute(
            """
            SELECT id FROM machine_hour_rates
            WHERE machine_type = ? COLLATE NOCASE AND effective_to IS NULL
            LIMIT 1
            """,
            (machine_type,),
        ).fetchone()
        if open_row is not None:
            raise HTTPException(status_code=400, detail="An open rate exists. Replace it instead of adding another.")
        conn.execute(
            """
            INSERT INTO machine_hour_rates (
              id, machine_id, machine_type, min_mhr_minor, target_mhr_minor, currency,
              effective_from, effective_to, source_kind, source_ref,
              attested_by, attested_at, shipped_seed_value_minor
            ) VALUES (?, ?, ?, ?, ?, 'INR', ?, NULL, 'owner_input', 'masterdata-ui', ?, ?, NULL)
            """,
            (
                rid,
                fields.get("machine_id"),
                machine_type,
                int(minor),
                _minor(fields.get("target_mhr_inr")),
                day,
                (fields.get("attested_by") or "").strip(),
                fields.get("attested_at"),
            ),
        )
    return {"ok": True, "id": rid}


@router.patch("/mhr/{row_id}")
def replace_mhr(row_id: str, body: EntityBody) -> dict[str, Any]:
    fields = dict(body.fields)
    if fields.get("min_mhr_minor") is None and fields.get("min_mhr_inr") is not None:
        fields["min_mhr_minor"] = _minor(fields.get("min_mhr_inr"))
    if fields.get("target_mhr_minor") is None and fields.get("target_mhr_inr") is not None:
        fields["target_mhr_minor"] = _minor(fields.get("target_mhr_inr"))
    day = str(fields.get("effective_from") or _today())[:10]
    try:
        with db.connect() as conn:
            new_id = supersede_rate(conn, "machine_hour_rates", row_id, fields, day)
    except LifecycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "id": new_id, "superseded": row_id}


@router.get("/outsource-vendors")
def list_outsource_vendors() -> dict[str, Any]:
    with db.connect() as conn:
        items = _rows(conn, "SELECT * FROM outsource_vendors ORDER BY name COLLATE NOCASE")
        quotes = _rows(
            conn,
            """
            SELECT id, vendor_id, process, spec, unit_basis, price_minor, currency,
                   effective_from, effective_to, source_kind, source_ref
            FROM outsource_quotes
            ORDER BY process, effective_from
            """,
        )
    by_vendor: dict[str, list[dict[str, Any]]] = {}
    for quote in quotes:
        quote["price_inr"] = int(quote["price_minor"]) / 100
        quote["current"] = quote.get("effective_to") in (None, "")
        by_vendor.setdefault(str(quote["vendor_id"]), []).append(quote)
    for item in items:
        item["quotes"] = by_vendor.get(item["id"], [])
    return {"ok": True, "items": items}


@router.post("/outsource-vendors")
def create_outsource_vendor(body: EntityBody) -> dict[str, Any]:
    fields = body.fields
    _require(fields, "name", "processes")
    vid = _new_id("osv")
    with db.connect() as conn:
        try:
            conn.execute(
                """
                INSERT INTO outsource_vendors (id, name, processes, lead_days, effective_from)
                VALUES (?, ?, ?, ?, ?)
                """,
                (vid, fields["name"].strip(), fields["processes"].strip(), fields.get("lead_days"), _today()),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "id": vid}


@router.patch("/outsource-vendors/{row_id}")
def replace_outsource_vendor(row_id: str, body: EntityBody) -> dict[str, Any]:
    try:
        with db.connect() as conn:
            new_id = supersede_outsource_vendor(conn, row_id, body.fields)
    except LifecycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "id": new_id, "superseded": row_id}


@router.get("/rm-quotes")
def list_rm_quotes() -> dict[str, Any]:
    with db.connect() as conn:
        items = _rows(
            conn,
            """
            SELECT q.*, m.grade AS material_grade, s.name AS supplier_name
            FROM supplier_rm_quotes q
            JOIN materials m ON m.id = q.material_id
            JOIN suppliers s ON s.id = q.supplier_id
            ORDER BY m.grade, q.effective_from
            """,
        )
    for item in items:
        item["price_inr"] = int(item["price_minor"]) / 100
        item["current"] = item.get("effective_to") in (None, "")
    return {"ok": True, "items": items}


@router.post("/rm-quotes")
def create_rm_quote(body: EntityBody) -> dict[str, Any]:
    fields = body.fields
    _require(fields, "supplier_id", "material_id", "size_spec", "unit_basis", "effective_from", "basis_date")
    if fields["unit_basis"] not in {"per_kg", "per_bar", "per_piece", "per_metre"}:
        raise HTTPException(status_code=400, detail="unit_basis is not valid")
    price = fields.get("price_minor")
    if price is None:
        price = _minor(fields.get("price_inr"))
    if price is None:
        raise HTTPException(status_code=400, detail="price_inr is required")
    rid = _new_id("rmq")
    day = str(fields["effective_from"])[:10]
    with db.connect() as conn:
        open_row = conn.execute(
            """
            SELECT id FROM supplier_rm_quotes
            WHERE material_id = ? AND supplier_id = ? AND effective_to IS NULL
            LIMIT 1
            """,
            (fields["material_id"], fields["supplier_id"]),
        ).fetchone()
        if open_row is not None:
            raise HTTPException(status_code=400, detail="An open RM quote exists. Replace it.")
        conn.execute(
            """
            INSERT INTO supplier_rm_quotes (
              id, supplier_id, material_id, size_spec, unit_basis, price_minor, currency,
              effective_from, effective_to, basis_date, source_kind, source_ref,
              is_estimate, estimate_basis, attested_by, attested_at, shipped_seed_value_minor
            ) VALUES (?, ?, ?, ?, ?, ?, 'INR', ?, NULL, ?, 'owner_input', 'masterdata-ui', ?, ?, ?, ?, NULL)
            """,
            (
                rid,
                fields["supplier_id"],
                fields["material_id"],
                fields["size_spec"].strip(),
                fields["unit_basis"],
                int(price),
                day,
                str(fields["basis_date"])[:10],
                int(fields.get("is_estimate") or 0),
                fields.get("estimate_basis") or "",
                (fields.get("attested_by") or "").strip(),
                fields.get("attested_at"),
            ),
        )
    return {"ok": True, "id": rid}


@router.patch("/rm-quotes/{row_id}")
def replace_rm_quote(row_id: str, body: EntityBody) -> dict[str, Any]:
    fields = dict(body.fields)
    if fields.get("price_minor") is None and fields.get("price_inr") is not None:
        fields["price_minor"] = _minor(fields.get("price_inr"))
    day = str(fields.get("effective_from") or _today())[:10]
    try:
        with db.connect() as conn:
            new_id = supersede_rate(conn, "supplier_rm_quotes", row_id, fields, day)
    except LifecycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "id": new_id, "superseded": row_id}


@router.post("/outsource-quotes")
def create_outsource_quote(body: EntityBody) -> dict[str, Any]:
    fields = body.fields
    _require(fields, "vendor_id", "process", "spec", "unit_basis", "effective_from")
    if fields["unit_basis"] not in {"per_kg", "per_piece", "per_batch"}:
        raise HTTPException(status_code=400, detail="unit_basis is not valid")
    price = fields.get("price_minor")
    if price is None:
        price = _minor(fields.get("price_inr"))
    if price is None:
        raise HTTPException(status_code=400, detail="price_inr is required")
    qid = _new_id("osq")
    day = str(fields["effective_from"])[:10]
    with db.connect() as conn:
        open_row = conn.execute(
            """
            SELECT id FROM outsource_quotes
            WHERE vendor_id = ? AND process = ? COLLATE NOCASE AND effective_to IS NULL
            LIMIT 1
            """,
            (fields["vendor_id"], fields["process"].strip()),
        ).fetchone()
        if open_row is not None:
            raise HTTPException(status_code=400, detail="An open outsource quote exists. Replace it.")
        conn.execute(
            """
            INSERT INTO outsource_quotes (
              id, vendor_id, process, spec, unit_basis, price_minor, currency,
              lead_days, effective_from, effective_to, source_kind, source_ref
            ) VALUES (?, ?, ?, ?, ?, ?, 'INR', ?, ?, NULL, 'owner_input', 'masterdata-ui')
            """,
            (
                qid,
                fields["vendor_id"],
                fields["process"].strip(),
                fields["spec"].strip(),
                fields["unit_basis"],
                int(price),
                fields.get("lead_days"),
                day,
            ),
        )
    return {"ok": True, "id": qid}


@router.patch("/outsource-quotes/{row_id}")
def replace_outsource_quote(row_id: str, body: EntityBody) -> dict[str, Any]:
    fields = dict(body.fields)
    if fields.get("price_minor") is None and fields.get("price_inr") is not None:
        fields["price_minor"] = _minor(fields.get("price_inr"))
    day = str(fields.get("effective_from") or _today())[:10]
    try:
        with db.connect() as conn:
            new_id = supersede_rate(conn, "outsource_quotes", row_id, fields, day)
    except LifecycleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "id": new_id, "superseded": row_id}


@router.get("/aliases")
def list_aliases(kind: str, canonical_id: str = "") -> dict[str, Any]:
    with db.connect() as conn:
        items = _alias_list(conn, kind, canonical_id or None)
    return {"ok": True, "items": items}


@router.post("/aliases")
def create_alias(body: AliasBody) -> dict[str, Any]:
    try:
        with db.connect() as conn:
            if body.kind == "customer":
                added = add_customer_alias(conn, body.canonical_id, body.alias, body.source)
            elif body.kind == "machine":
                added = add_machine_alias(conn, body.canonical_id, body.alias, body.source)
            elif body.kind == "vendor":
                added = add_vendor_alias(conn, body.canonical_id, body.alias, body.source)
            else:
                raise HTTPException(status_code=400, detail="kind must be customer, machine, or vendor")
    except AliasError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, **added}


@router.delete("/aliases")
def delete_alias(kind: str, alias: str) -> dict[str, Any]:
    try:
        with db.connect() as conn:
            if kind == "customer":
                removed = remove_customer_alias(conn, alias)
            elif kind == "machine":
                removed = remove_machine_alias(conn, alias)
            elif kind == "vendor":
                removed = remove_vendor_alias(conn, alias)
            else:
                raise HTTPException(status_code=400, detail="kind must be customer, machine, or vendor")
    except AliasError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, **removed}


@router.get("/resolve")
def resolve_alias(kind: str, alias: str) -> dict[str, Any]:
    """Exact match only. An unresolved alias returns canonical_id null — never a guess."""
    with db.connect() as conn:
        if kind == "customer":
            canonical = resolve_customer_alias(conn, alias)
        elif kind == "machine":
            canonical = resolve_machine_alias(conn, alias)
        elif kind == "vendor":
            canonical = resolve_vendor_alias(conn, alias)
        else:
            raise HTTPException(status_code=400, detail="kind must be customer, machine, or vendor")
    return {"ok": True, "canonical_id": canonical, "resolved": canonical is not None}


@router.get("/as-of")
def as_of(kind: str, key: str, as_of: str) -> dict[str, Any]:
    with db.connect() as conn:
        if kind == "rm":
            mid = material_id_for_grade(conn, key) or key
            found = supplier_rm_quote_as_of(conn, mid, as_of)
        elif kind == "outsource":
            found = outsource_quote_as_of(conn, key, as_of)
        elif kind == "capability":
            machine_id, _, process = key.partition("|")
            found = machine_capability_as_of(conn, machine_id, process, as_of)
        else:
            raise HTTPException(status_code=400, detail="kind must be rm, outsource, or capability")
    if found is None:
        raise HTTPException(status_code=409, detail="BLOCKER: no row is effective on that date")
    return {"ok": True, "row": found}


@router.delete("/{entity}/{row_id}")
def refuse_delete(entity: str, row_id: str) -> dict[str, Any]:
    raise HTTPException(
        status_code=409,
        detail=f"Hard delete is not allowed for {entity} {row_id}. Use Replace to supersede the row.",
    )


def _alias_list(conn, kind: str, canonical_id: str | None) -> list[dict]:
    if kind == "customer":
        return list_customer_aliases(conn, canonical_id)
    if kind == "machine":
        return list_machine_aliases(conn, canonical_id)
    if kind == "vendor":
        return list_vendor_aliases(conn, canonical_id)
    raise HTTPException(status_code=400, detail="kind must be customer, machine, or vendor")
