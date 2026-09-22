"""Idempotent backfill from mhr-demo.md into machines + machine_hour_rates (demo floors)."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from ..quote import _parse_numeric

DEFAULT_MHR_DEMO_PATH = (
    Path(__file__).resolve().parent.parent
    / "hermes"
    / "playbooks"
    / "quote"
    / "files"
    / "mhr-demo.md"
)

_DEMO_EFFECTIVE_FROM = "2020-01-01"
_SOURCE_REF = "mhr-demo.md"


def _machine_id_for_type(machine_type: str) -> str:
    digest = hashlib.sha256(machine_type.strip().lower().encode("utf-8")).hexdigest()[:16]
    return f"mach_{digest}"


def _rate_id_for_type(machine_type: str) -> str:
    digest = hashlib.sha256(f"demo:{machine_type.strip().lower()}".encode("utf-8")).hexdigest()[:16]
    return f"mhr_demo_{digest}"


def _rupees_per_hr_to_minor(rupees: float) -> int:
    # mhr-demo.md lists whole INR/hr; store as minor units (paise) = rupees × 100.
    return int(round(rupees * 100))


def parse_mhr_demo_table(path: Path | None = None) -> dict[str, float]:
    """Same machine-type → minimum INR/hr map as quote._parse_mhr_demo_mins."""
    p = path or DEFAULT_MHR_DEMO_PATH
    if not p.is_file():
        return {}
    mins: dict[str, float] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if "|" not in line:
            continue
        parts = [part.strip() for part in line.split("|") if part.strip()]
        if len(parts) < 2:
            continue
        head = parts[0].lower()
        if head in {"machine type", "---", "machine type (demo)"} or head.startswith("-"):
            continue
        rate = _parse_numeric(parts[1])
        if rate is not None:
            mins[parts[0].strip()] = rate
    return mins


def import_mhr_demo_from_markdown(
    conn: sqlite3.Connection,
    path: Path | None = None,
) -> int:
    """Insert demo machines and open-ended rates; idempotent. Returns new rate rows inserted."""
    floors = parse_mhr_demo_table(path)
    if not floors:
        return 0
    inserted = 0
    for machine_type, rupees_hr in floors.items():
        canonical = machine_type.strip()
        if not canonical:
            continue
        mid = _machine_id_for_type(canonical)
        conn.execute(
            """
            INSERT OR IGNORE INTO machines (
              id, name, machine_type, control_make, control_model, status
            ) VALUES (?, ?, ?, 'demo', 'demo', 'running')
            """,
            (mid, canonical, canonical),
        )
        rid = _rate_id_for_type(canonical)
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO machine_hour_rates (
              id, machine_id, machine_type, min_mhr_minor, currency,
              effective_from, effective_to, source_kind, source_ref
            ) VALUES (?, ?, ?, ?, 'INR', ?, NULL, 'demo', ?)
            """,
            (
                rid,
                mid,
                canonical,
                _rupees_per_hr_to_minor(rupees_hr),
                _DEMO_EFFECTIVE_FROM,
                _SOURCE_REF,
            ),
        )
        if cur.rowcount:
            inserted += 1
    return inserted
