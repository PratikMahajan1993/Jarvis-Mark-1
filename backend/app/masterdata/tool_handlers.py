"""Tool entry points for alias resolution, seed, and supersede."""

from __future__ import annotations

from typing import Any

from .. import db
from .aliases import (
    AliasError,
    add_customer_alias,
    add_machine_alias,
    add_vendor_alias,
    resolve_customer_alias,
    resolve_machine_alias,
    resolve_vendor_alias,
)
from .lifecycle import LifecycleError, supersede_customer, supersede_machine, supersede_material, supersede_rate, supersede_supplier
from .seed_master_data import seed_master_data


def masterdata_seed(**_: Any) -> dict[str, Any]:
    with db.connect() as conn:
        counts = seed_master_data(conn)
    return {"ok": True, "counts": counts}


def masterdata_resolve_alias(kind: str = "", alias: str = "", **_: Any) -> dict[str, Any]:
    text = (alias or "").strip()
    if not text:
        return {"ok": False, "need": "alias", "message": "Which name should I resolve? I will not guess."}
    with db.connect() as conn:
        if kind == "customer":
            canonical = resolve_customer_alias(conn, text)
        elif kind == "machine":
            canonical = resolve_machine_alias(conn, text)
        elif kind == "vendor":
            canonical = resolve_vendor_alias(conn, text)
        else:
            return {"ok": False, "need": "kind", "message": "kind must be customer, machine, or vendor."}
    if canonical is None:
        return {
            "ok": False,
            "need": "alias",
            "message": f"'{text}' is not an alias. Ask which canonical record it belongs to. Do not guess from a similar name.",
        }
    return {"ok": True, "canonical_id": canonical}


def masterdata_add_alias(
    kind: str = "",
    canonical_id: str = "",
    alias: str = "",
    source: str = "manual",
    **_: Any,
) -> dict[str, Any]:
    try:
        with db.connect() as conn:
            if kind == "customer":
                added = add_customer_alias(conn, canonical_id, alias, source)
            elif kind == "machine":
                added = add_machine_alias(conn, canonical_id, alias, source)
            elif kind == "vendor":
                added = add_vendor_alias(conn, canonical_id, alias, source)
            else:
                return {"ok": False, "need": "kind", "message": "kind must be customer, machine, or vendor."}
    except AliasError as exc:
        return {"ok": False, "need": "alias", "message": str(exc)}
    return {"ok": True, **added}


def masterdata_supersede(
    entity: str = "",
    old_id: str = "",
    effective_from: str = "",
    **fields: Any,
) -> dict[str, Any]:
    data = {key: value for key, value in fields.items() if key not in {"session_id"}}
    try:
        with db.connect() as conn:
            if entity == "customer":
                new_id = supersede_customer(conn, old_id, data)
            elif entity == "machine":
                new_id = supersede_machine(conn, old_id, data)
            elif entity == "material":
                new_id = supersede_material(conn, old_id, data)
            elif entity == "supplier":
                new_id = supersede_supplier(conn, old_id, data)
            elif entity in {"mhr", "rm", "outsource"}:
                table = {
                    "mhr": "machine_hour_rates",
                    "rm": "supplier_rm_quotes",
                    "outsource": "outsource_quotes",
                }[entity]
                new_id = supersede_rate(conn, table, old_id, data, effective_from)
            else:
                return {"ok": False, "need": "entity", "message": "Unknown master-data entity."}
    except LifecycleError as exc:
        return {"ok": False, "need": "supersede", "message": str(exc)}
    return {"ok": True, "id": new_id, "superseded": old_id}


def masterdata_options(**_: Any) -> dict[str, Any]:
    with db.connect() as conn:
        seed_master_data(conn)
        machines = [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, name, machine_type FROM machines
                WHERE effective_to IS NULL AND status != 'superseded'
                ORDER BY name COLLATE NOCASE
                """
            ).fetchall()
        ]
        materials = [
            dict(row)
            for row in conn.execute(
                "SELECT id, grade FROM materials WHERE effective_to IS NULL ORDER BY grade COLLATE NOCASE"
            ).fetchall()
        ]
        customers = [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, name FROM customers
                WHERE effective_to IS NULL AND status != 'superseded'
                ORDER BY name COLLATE NOCASE
                """
            ).fetchall()
        ]
    return {"ok": True, "machines": machines, "materials": materials, "customers": customers}


HANDLERS = {
    "masterdata_seed": masterdata_seed,
    "masterdata_resolve_alias": masterdata_resolve_alias,
    "masterdata_add_alias": masterdata_add_alias,
    "masterdata_supersede": masterdata_supersede,
    "masterdata_options": masterdata_options,
}

SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "masterdata_options",
            "description": "List active machines, materials, and customers from master data for quote dropdowns. Do not invent names.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "masterdata_resolve_alias",
            "description": "Resolve an alias to a canonical id by exact spelling only. If unresolved, ask — never guess a similar name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["customer", "machine", "vendor"]},
                    "alias": {"type": "string"},
                },
                "required": ["kind", "alias"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "masterdata_add_alias",
            "description": "Attach an exact alias to a canonical customer, machine, or supplier the owner named.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["customer", "machine", "vendor"]},
                    "canonical_id": {"type": "string"},
                    "alias": {"type": "string"},
                    "source": {"type": "string"},
                },
                "required": ["kind", "canonical_id", "alias"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "masterdata_seed",
            "description": "Idempotent master-data seed. Does not overwrite rows the owner already edited.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "masterdata_supersede",
            "description": "Replace an authoritative master row by inserting a new row and end-dating the old one. Never hard-delete.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity": {"type": "string"},
                    "old_id": {"type": "string"},
                    "effective_from": {"type": "string"},
                    "name": {"type": "string"},
                    "grade": {"type": "string"},
                    "min_mhr_minor": {"type": "integer"},
                },
                "required": ["entity", "old_id"],
            },
        },
    },
]
