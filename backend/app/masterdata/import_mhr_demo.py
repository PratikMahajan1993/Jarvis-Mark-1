"""Idempotent backfill from mhr-demo.md into machines + machine_hour_rates (demo floors)."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ..config import settings
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


class MhrDemoImportError(Exception):
    """Whole-file import rejected; no rows from this run are applied."""


@dataclass(frozen=True)
class MhrDemoRow:
    machine_type: str
    rupees_hr: float
    attested_by: str
    attested_on: str | None
    effective_from: str | None


def _machine_id_for_type(machine_type: str) -> str:
    digest = hashlib.sha256(machine_type.strip().lower().encode("utf-8")).hexdigest()[:16]
    return f"mach_{digest}"


def _rate_id_for_version(
    machine_type: str,
    effective_from: str,
    min_mhr_minor: int,
    attested_by: str,
) -> str:
    key = f"{machine_type.strip().lower()}:{effective_from}:{min_mhr_minor}:{attested_by.strip()}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return f"mhr_demo_{digest}"


def _rupees_per_hr_to_minor(rupees: float) -> int:
    return int(round(rupees * 100))


def _today_iso() -> str:
    return datetime.now(ZoneInfo(settings.tz)).date().isoformat()


def _normalize_date(value: str) -> str:
    """Accept YYYY-MM-DD or full ISO; return YYYY-MM-DD for comparisons."""
    text = value.strip()
    if not text:
        raise MhrDemoImportError("attested_on is empty")
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    raise MhrDemoImportError(f"Invalid attested_on date: {value!r}")


def _parse_header_map(parts: list[str]) -> dict[str, int] | None:
    if not parts:
        return None
    h0 = parts[0].lower()
    if "machine" not in h0 or "type" not in h0:
        return None
    col_map: dict[str, int] = {}
    for j, p in enumerate(parts):
        pl = p.lower()
        if "machine" in pl and "type" in pl:
            col_map["machine_type"] = j
        elif "mhr" in pl or "minimum" in pl:
            col_map["rate"] = j
        elif pl.replace(" ", "_") in {"attested_by", "attestedby"} or pl == "attested by":
            col_map["attested_by"] = j
        elif pl.replace(" ", "_") in {"attested_on", "attestedon"} or pl == "attested on":
            col_map["attested_on"] = j
        elif "effective_from" in pl.replace(" ", "_") or pl == "effective from":
            col_map["effective_from"] = j
    if "machine_type" not in col_map or "rate" not in col_map:
        return None
    return col_map


def parse_mhr_demo_rows(path: Path | None = None) -> list[MhrDemoRow]:
    """Parse markdown table rows; raises MhrDemoImportError on malformed data rows."""
    p = path or DEFAULT_MHR_DEMO_PATH
    if not p.is_file():
        return []
    col_map: dict[str, int] | None = None
    rows: list[MhrDemoRow] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if "|" not in line:
            continue
        parts = [part.strip() for part in line.split("|") if part.strip()]
        if len(parts) < 2:
            continue
        head = parts[0].lower()
        if head.startswith("-") or head == "---":
            continue
        if col_map is None:
            maybe = _parse_header_map(parts)
            if maybe is not None:
                col_map = maybe
                continue
        if col_map is None:
            if head in {"machine type", "machine type (demo)"}:
                continue
            rate = _parse_numeric(parts[1])
            if rate is None:
                raise MhrDemoImportError(f"Cannot parse MHR for machine row: {parts[0]!r}")
            canonical = parts[0].strip()
            if not canonical:
                raise MhrDemoImportError("Empty machine type in rate row")
            rows.append(
                MhrDemoRow(
                    machine_type=canonical,
                    rupees_hr=rate,
                    attested_by="",
                    attested_on=None,
                    effective_from=None,
                )
            )
            continue
        if head == parts[col_map["machine_type"]].lower() and "machine" in head:
            continue
        try:
            machine_type = parts[col_map["machine_type"]].strip()
        except IndexError as exc:
            raise MhrDemoImportError("Rate row missing machine type column") from exc
        if not machine_type:
            raise MhrDemoImportError("Empty machine type in rate row")
        try:
            rate_raw = parts[col_map["rate"]]
        except IndexError as exc:
            raise MhrDemoImportError(f"Rate row missing MHR for {machine_type!r}") from exc
        rate = _parse_numeric(rate_raw)
        if rate is None:
            raise MhrDemoImportError(f"Cannot parse MHR for {machine_type!r}: {rate_raw!r}")
        attested_by = ""
        attested_on: str | None = None
        effective_from: str | None = None
        if "attested_by" in col_map:
            try:
                attested_by = parts[col_map["attested_by"]].strip()
            except IndexError:
                attested_by = ""
        if "attested_on" in col_map:
            try:
                raw_on = parts[col_map["attested_on"]].strip()
            except IndexError:
                raw_on = ""
            if raw_on:
                attested_on = _normalize_date(raw_on)
        if "effective_from" in col_map:
            try:
                raw_ef = parts[col_map["effective_from"]].strip()
            except IndexError:
                raw_ef = ""
            if raw_ef:
                effective_from = _normalize_date(raw_ef)
        rows.append(
            MhrDemoRow(
                machine_type=machine_type,
                rupees_hr=rate,
                attested_by=attested_by,
                attested_on=attested_on,
                effective_from=effective_from,
            )
        )
    return rows


def parse_mhr_demo_table(path: Path | None = None) -> dict[str, float]:
    """Same machine-type → minimum INR/hr map as quote._parse_mhr_demo_mins."""
    return {row.machine_type: row.rupees_hr for row in parse_mhr_demo_rows(path)}


def _open_rate_row(conn: sqlite3.Connection, machine_type: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id, min_mhr_minor, attested_by, attested_at, shipped_seed_value_minor,
               effective_from
        FROM machine_hour_rates
        WHERE machine_type = ? COLLATE NOCASE
          AND effective_to IS NULL
        ORDER BY effective_from DESC
        LIMIT 1
        """,
        (machine_type.strip(),),
    ).fetchone()


def _row_state_key(row: MhrDemoRow) -> tuple[int, str, str | None]:
    minor = _rupees_per_hr_to_minor(row.rupees_hr)
    att_at = row.attested_on
    return minor, row.attested_by.strip(), att_at


def _open_state_key(open_row: sqlite3.Row) -> tuple[int, str, str | None]:
    att_by = (open_row["attested_by"] or "").strip()
    att_at = open_row["attested_at"]
    if att_at:
        att_at = str(att_at)[:10]
    return int(open_row["min_mhr_minor"]), att_by, att_at


def _validate_against_open(open_row: sqlite3.Row | None, file_row: MhrDemoRow) -> None:
    if open_row is None or not file_row.attested_on:
        return
    prev_at = open_row["attested_at"]
    if not prev_at:
        return
    prev_day = str(prev_at)[:10]
    if file_row.attested_on < prev_day:
        raise MhrDemoImportError(
            f"{file_row.machine_type!r}: attested_on {file_row.attested_on} "
            f"moves backwards from {prev_day}"
        )


def import_mhr_demo_from_markdown(
    conn: sqlite3.Connection,
    path: Path | None = None,
) -> int:
    """Apply demo MHR rows from markdown; idempotent. Returns new rate rows inserted."""
    file_rows = parse_mhr_demo_rows(path)
    if not file_rows:
        return 0

    pending: list[tuple[MhrDemoRow, sqlite3.Row | None]] = []
    for file_row in file_rows:
        open_row = _open_rate_row(conn, file_row.machine_type)
        _validate_against_open(open_row, file_row)
        if open_row is not None and _open_state_key(open_row) == _row_state_key(file_row):
            continue
        pending.append((file_row, open_row))

    if not pending:
        return 0

    conn.execute("BEGIN IMMEDIATE")
    inserted = 0
    try:
        for file_row, open_row in pending:
            open_row = _open_rate_row(conn, file_row.machine_type)
            _validate_against_open(open_row, file_row)
            if open_row is not None and _open_state_key(open_row) == _row_state_key(file_row):
                continue

            canonical = file_row.machine_type.strip()
            mid = _machine_id_for_type(canonical)
            conn.execute(
                """
                INSERT OR IGNORE INTO machines (
                  id, name, machine_type, control_make, control_model, status
                ) VALUES (?, ?, ?, 'demo', 'demo', 'running')
                """,
                (mid, canonical, canonical),
            )

            minor = _rupees_per_hr_to_minor(file_row.rupees_hr)
            att_by = file_row.attested_by.strip()
            att_at = file_row.attested_on
            today = _today_iso()

            if open_row is None:
                eff_from = file_row.effective_from or _DEMO_EFFECTIVE_FROM
                rid = _rate_id_for_version(canonical, eff_from, minor, att_by)
                conn.execute(
                    """
                    INSERT INTO machine_hour_rates (
                      id, machine_id, machine_type, min_mhr_minor, currency,
                      effective_from, effective_to, source_kind, source_ref,
                      attested_by, attested_at, shipped_seed_value_minor
                    ) VALUES (?, ?, ?, ?, 'INR', ?, NULL, 'demo', ?, ?, ?, ?)
                    """,
                    (
                        rid,
                        mid,
                        canonical,
                        minor,
                        eff_from,
                        _SOURCE_REF,
                        att_by,
                        att_at,
                        minor,
                    ),
                )
                inserted += 1
                continue

            conn.execute(
                """
                UPDATE machine_hour_rates
                SET effective_to = ?
                WHERE id = ?
                """,
                (today, open_row["id"]),
            )
            seed = open_row["shipped_seed_value_minor"]
            if seed is None:
                seed = int(open_row["min_mhr_minor"])
            eff_from = file_row.effective_from or today
            rid = _rate_id_for_version(canonical, eff_from, minor, att_by)
            conn.execute(
                """
                INSERT INTO machine_hour_rates (
                  id, machine_id, machine_type, min_mhr_minor, currency,
                  effective_from, effective_to, source_kind, source_ref,
                  attested_by, attested_at, shipped_seed_value_minor
                ) VALUES (?, ?, ?, ?, 'INR', ?, NULL, 'demo', ?, ?, ?, ?)
                """,
                (
                    rid,
                    mid,
                    canonical,
                    minor,
                    eff_from,
                    _SOURCE_REF,
                    att_by,
                    att_at,
                    seed,
                ),
            )
            inserted += 1
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    return inserted
