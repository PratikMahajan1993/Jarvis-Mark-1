"""Idempotent shop master-data seed.

Rates are the floors already published in ``mhr-demo.md``, stored as demo seed
rows. They stay unattested (``attested_by`` empty and ``shipped_seed_value_minor``
equal to the floor) so they cannot price a send until the owner replaces them.
Customer commercial terms are ``ask`` — this seed does not invent GSTIN, payment
days, or attested shop rates. Material densities are published nominal values.
"""

from __future__ import annotations

import hashlib
import sqlite3

_EFFECTIVE_FROM = "2020-01-01"
_SOURCE_REF = "seed_master_data"

# Floors copied from playbooks/quote/files/mhr-demo.md (INR/hr → minor units).
_MHR_FLOORS: tuple[tuple[str, int], ...] = (
    ("Demo CNC vertical mill", 85_000),
    ("Demo engine lathe", 62_000),
    ("Demo wire EDM", 110_000),
)

# Axis count is the class of the named machine, not a measured travel.
_MACHINES: tuple[tuple[str, str, int], ...] = (
    ("Demo CNC vertical mill", "Demo CNC vertical mill", 3),
    ("Demo engine lathe", "Demo engine lathe", 2),
    ("Demo wire EDM", "Demo wire EDM", 2),
    ("CNC turning centre", "CNC turning centre", 2),
    ("Vertical machining centre", "Vertical machining centre", 3),
)

_CUSTOMERS: tuple[str, ...] = (
    "Deepak",
    "Rajesh",
    "Priya Mehta",
    "Apex Components Pvt Ltd",
)

# grade, family, standard, density_kg_m3, form
_MATERIALS: tuple[tuple[str, str, str, float, str], ...] = (
    ("EN8", "carbon steel", "BS 970 080M40", 7850.0, "bar"),
    ("EN24", "alloy steel", "BS 970 817M40", 7840.0, "bar"),
    ("18CrNiMo7-6", "alloy steel", "EN 10084", 7850.0, "bar"),
    ("SS304", "stainless", "ASTM A276 304", 8000.0, "bar"),
    ("Al 6061-T6", "aluminium", "ASTM B211 6061-T6", 2700.0, "bar"),
)

_SUPPLIERS: tuple[str, ...] = (
    "RM stockist (seed)",
    "Tooling supply (seed)",
)

# Name already used as the RM line amount in quote proof fixtures (INR → minor).
_EN8_DEMO_RM_MINOR = 420_000


def _stable_id(prefix: str, key: str) -> str:
    digest = hashlib.sha256(key.strip().lower().encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _insert(conn: sqlite3.Connection, sql: str, params: tuple) -> int:
    cur = conn.execute(sql, params)
    return 1 if cur.rowcount else 0


def seed_master_data(conn: sqlite3.Connection) -> dict[str, int]:
    """Insert shop seed rows. Safe to call again; existing ids are left untouched."""
    counts = {
        "customers": 0,
        "machines": 0,
        "materials": 0,
        "suppliers": 0,
        "mhr": 0,
        "rm_quotes": 0,
        "outsource_vendors": 0,
    }
    for name in _CUSTOMERS:
        cid = _stable_id("cust", name)
        counts["customers"] += _insert(
            conn,
            """
            INSERT OR IGNORE INTO customers (id, name, gstin, currency, status, effective_from)
            VALUES (?, ?, NULL, 'INR', 'active', ?)
            """,
            (cid, name, _EFFECTIVE_FROM),
        )
        _insert(
            conn,
            """
            INSERT OR IGNORE INTO customer_aliases (customer_id, alias, source)
            VALUES (?, ?, ?)
            """,
            (cid, name, _SOURCE_REF),
        )
        conn.execute(
            """
            UPDATE customer_aliases
            SET source = ?
            WHERE customer_id = ? AND alias = ? COLLATE NOCASE AND source = 'quote_build'
            """,
            (_SOURCE_REF, cid, name),
        )
        _insert(
            conn,
            """
            INSERT OR IGNORE INTO customer_terms (
              customer_id, default_scope, payment_terms_days, nda,
              allow_cloud_vision, quote_validity_days
            ) VALUES (?, 'ask', NULL, 0, 0, 30)
            """,
            (cid,),
        )

    for name, machine_type, axes in _MACHINES:
        mid = _stable_id("mach", machine_type)
        counts["machines"] += _insert(
            conn,
            """
            INSERT OR IGNORE INTO machines (
              id, name, machine_type, control_make, control_model, axes, status, effective_from
            ) VALUES (?, ?, ?, 'owner-pending', 'owner-pending', ?, 'running', ?)
            """,
            (mid, name, machine_type, axes, _EFFECTIVE_FROM),
        )

    for machine_type, minor in _MHR_FLOORS:
        mid = _stable_id("mach", machine_type)
        rid = _stable_id("mhr", f"{machine_type}:{_EFFECTIVE_FROM}:{minor}")
        counts["mhr"] += _insert(
            conn,
            """
            INSERT OR IGNORE INTO machine_hour_rates (
              id, machine_id, machine_type, min_mhr_minor, currency,
              effective_from, effective_to, source_kind, source_ref,
              attested_by, attested_at, shipped_seed_value_minor
            ) VALUES (?, ?, ?, ?, 'INR', ?, NULL, 'demo', ?, '', NULL, ?)
            """,
            (rid, mid, machine_type, minor, _EFFECTIVE_FROM, _SOURCE_REF, minor),
        )

    for grade, family, standard, density, form in _MATERIALS:
        mat_id = _stable_id("mat", grade)
        counts["materials"] += _insert(
            conn,
            """
            INSERT OR IGNORE INTO materials (
              id, grade, family, standard, density_kg_m3, form, effective_from
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (mat_id, grade, family, standard, density, form, _EFFECTIVE_FROM),
        )

    supplier_ids: dict[str, str] = {}
    for name in _SUPPLIERS:
        sid = _stable_id("sup", name)
        supplier_ids[name] = sid
        counts["suppliers"] += _insert(
            conn,
            """
            INSERT OR IGNORE INTO suppliers (id, name, contact, lead_days, effective_from)
            VALUES (?, ?, NULL, NULL, ?)
            """,
            (sid, name, _EFFECTIVE_FROM),
        )

    en8 = _stable_id("mat", "EN8")
    stockist = supplier_ids["RM stockist (seed)"]
    rm_id = _stable_id("rmq", f"EN8:{_EFFECTIVE_FROM}")
    counts["rm_quotes"] += _insert(
        conn,
        """
        INSERT OR IGNORE INTO supplier_rm_quotes (
          id, supplier_id, material_id, size_spec, unit_basis, price_minor, currency,
          effective_from, effective_to, basis_date, source_kind, source_ref,
          is_estimate, estimate_basis, attested_by, attested_at, shipped_seed_value_minor
        ) VALUES (
          ?, ?, ?, 'round bar', 'per_kg', ?, 'INR',
          ?, NULL, ?, 'demo', ?,
          1, 'placeholder seed — owner must replace before send', '', NULL, ?
        )
        """,
        (rm_id, stockist, en8, _EN8_DEMO_RM_MINOR, _EFFECTIVE_FROM, _EFFECTIVE_FROM, _SOURCE_REF, _EN8_DEMO_RM_MINOR),
    )

    vendor_id = _stable_id("osv", "Heat treat vendor (seed)")
    counts["outsource_vendors"] += _insert(
        conn,
        """
        INSERT OR IGNORE INTO outsource_vendors (id, name, processes, lead_days, effective_from)
        VALUES (?, 'Heat treat vendor (seed)', 'heat_treat,grinding', NULL, ?)
        """,
        (vendor_id, _EFFECTIVE_FROM),
    )
    return counts
