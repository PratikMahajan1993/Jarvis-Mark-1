"""1D bar stock cutting — first-fit-decreasing, remnant-aware (M3)."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any

import sqlite3

from . import db

_DEFAULT_KERF_MM = 3.0
_DEFAULT_FACING_MM = 0.0
_DEFAULT_GRIP_MM = 5.0
_MIN_USABLE_REMNANT_MM = 1.0


@dataclass
class _StockOption:
    quote_id: str
    stock_length_mm: float
    price_minor: int
    unit_basis: str
    size_spec: str
    diameter_mm: float | None


@dataclass
class _Bin:
    remaining_mm: float
    stock_length_mm: float
    source: str  # "new" | "remnant"
    remnant_id: str | None = None
    pieces: int = 0


def _parse_float_param(value: str | float | int | None, default: float) -> float:
    if value is None or value == "":
        return default
    return float(value)


def _piece_cut_length_mm(
    part_length_mm: float,
    *,
    facing_mm: float,
    kerf_mm: float,
) -> float:
    """Finished length plus both faces and one parting kerf per piece."""
    return part_length_mm + (2.0 * facing_mm) + kerf_mm


def _parse_size_spec(size_spec: str) -> tuple[float | None, float | None]:
    """Return (stock_length_mm, diameter_mm) when parseable."""
    text = (size_spec or "").strip().lower().replace("×", "x")
    diameter: float | None = None
    length: float | None = None

    dia_match = re.search(
        r"(?:dia|ø|od|d)\s*[:.]?\s*(\d+(?:\.\d+)?)\s*(?:mm)?",
        text,
    )
    if dia_match:
        diameter = float(dia_match.group(1))
    else:
        round_match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:mm)?\s*x\s*(\d+(?:\.\d+)?)", text)
        if round_match:
            diameter = float(round_match.group(1))
            length = float(round_match.group(2))

    if length is None:
        len_match = re.search(r"(?:length|len|l)\s*[:.]?\s*(\d+(?:\.\d+)?)\s*(?:mm)?", text)
        if len_match:
            length = float(len_match.group(1))
    if length is None:
        trail = re.search(r"(\d{3,5})\s*(?:mm?\b|$)", text)
        if trail:
            length = float(trail.group(1))
    return length, diameter


def _load_material(conn: sqlite3.Connection, material_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT id, density_kg_m3 FROM materials WHERE id = ?",
        (material_id,),
    ).fetchone()


def _load_stock_options(
    conn: sqlite3.Connection,
    material_id: str,
    *,
    as_of: str,
) -> list[_StockOption]:
    rows = conn.execute(
        """
        SELECT id, size_spec, unit_basis, price_minor
        FROM supplier_rm_quotes
        WHERE material_id = ?
          AND effective_from <= ?
          AND (effective_to IS NULL OR effective_to > ?)
        ORDER BY effective_from DESC
        """,
        (material_id, as_of, as_of),
    ).fetchall()
    options: list[_StockOption] = []
    seen_lengths: set[tuple[str, float]] = set()
    for row in rows:
        length_mm, diameter_mm = _parse_size_spec(row["size_spec"])
        if length_mm is None or length_mm <= 0:
            continue
        key = (row["id"], length_mm)
        if key in seen_lengths:
            continue
        seen_lengths.add(key)
        options.append(
            _StockOption(
                quote_id=row["id"],
                stock_length_mm=length_mm,
                price_minor=int(row["price_minor"]),
                unit_basis=row["unit_basis"],
                size_spec=row["size_spec"],
                diameter_mm=diameter_mm,
            )
        )
    return options


def _load_confirmed_remnants(
    conn: sqlite3.Connection,
    material_id: str,
) -> list[tuple[str, float]]:
    """List of (remnant_id, length_mm) expanded by qty."""
    rows = conn.execute(
        """
        SELECT id, length_mm, qty
        FROM remnant_stock
        WHERE material_id = ? AND state = 'confirmed'
        ORDER BY length_mm ASC
        """,
        (material_id,),
    ).fetchall()
    out: list[tuple[str, float]] = []
    for row in rows:
        n = max(0, int(row["qty"]))
        for _ in range(n):
            out.append((row["id"], float(row["length_mm"])))
    return out


def _usable_on_stock(stock_length_mm: float, grip_mm: float) -> float:
    return max(0.0, stock_length_mm - grip_mm)


def _fits_in_bin(b: _Bin, piece_mm: float, kerf_mm: float) -> bool:
    need = piece_mm + (kerf_mm if b.pieces > 0 else 0.0)
    return b.remaining_mm >= need


def _consume_in_bin(b: _Bin, piece_mm: float, kerf_mm: float) -> None:
    if b.pieces > 0:
        b.remaining_mm -= kerf_mm
    b.remaining_mm -= piece_mm
    b.pieces += 1


def _open_new_bar(
    bins: list[_Bin],
    *,
    piece_mm: float,
    grip_mm: float,
    stock_options: list[_StockOption],
) -> None:
    best = min(stock_options, key=lambda o: o.price_minor / o.stock_length_mm)
    usable = _usable_on_stock(best.stock_length_mm, grip_mm)
    if piece_mm > usable:
        raise ValueError("piece_longer_than_stock")
    bins.append(
        _Bin(
            remaining_mm=usable - piece_mm,
            stock_length_mm=best.stock_length_mm,
            source="new",
            pieces=1,
        )
    )


def _run_ffd(
    *,
    qty: int,
    piece_mm: float,
    kerf_mm: float,
    grip_mm: float,
    stock_options: list[_StockOption],
    remnant_lengths: list[tuple[str, float]],
) -> list[_Bin]:
    pieces = sorted([piece_mm] * qty, reverse=True)
    remnant_pool = list(remnant_lengths)
    bins: list[_Bin] = []

    for piece in pieces:
        placed = False
        open_bins = sorted(
            bins,
            key=lambda b: (0 if b.source == "remnant" else 1, b.remaining_mm),
        )
        for b in open_bins:
            if _fits_in_bin(b, piece, kerf_mm):
                _consume_in_bin(b, piece, kerf_mm)
                placed = True
                break

        if not placed and remnant_pool:
            candidates = [
                (i, rid, rlen)
                for i, (rid, rlen) in enumerate(remnant_pool)
                if rlen >= piece
            ]
            if candidates:
                pick = min(candidates, key=lambda x: x[2])
                idx, rem_id, rem_len = pick
                remnant_pool.pop(idx)
                bins.append(
                    _Bin(
                        remaining_mm=rem_len - piece,
                        stock_length_mm=rem_len,
                        source="remnant",
                        remnant_id=rem_id,
                        pieces=1,
                    )
                )
                placed = True

        if not placed:
            if not stock_options:
                raise ValueError("no_stock_option")
            _open_new_bar(
                bins,
                piece_mm=piece,
                grip_mm=grip_mm,
                stock_options=stock_options,
            )

    return [b for b in bins if b.pieces > 0]


def _summarize_bars(bins: list[_Bin]) -> list[dict[str, Any]]:
    counts: dict[tuple[float, str], int] = {}
    for b in bins:
        key = (b.stock_length_mm, b.source)
        counts[key] = counts.get(key, 0) + 1
    return [
        {"length": length, "count": count, "source": source}
        for (length, source), count in sorted(counts.items(), key=lambda x: (-x[0][0], x[0][1]))
    ]


def _yield_pct(*, qty: int, piece_mm: float, bins: list[_Bin]) -> float:
    useful = qty * piece_mm
    consumed = 0.0
    for b in bins:
        if b.source == "remnant":
            consumed += b.stock_length_mm - b.remaining_mm
        else:
            consumed += b.stock_length_mm
    if consumed <= 0:
        return 0.0
    return round(100.0 * useful / consumed, 2)


def _bar_unit_cost_minor(option: _StockOption, *, density_kg_m3: float | None) -> int | None:
    basis = option.unit_basis
    if basis == "per_bar":
        return option.price_minor
    if basis == "per_metre":
        metres = option.stock_length_mm / 1000.0
        return int(round(option.price_minor * metres))
    if basis == "per_kg":
        if density_kg_m3 is None or option.diameter_mm is None:
            return None
        area_m2 = 3.141592653589793 * (option.diameter_mm / 2000.0) ** 2
        mass_kg = area_m2 * (option.stock_length_mm / 1000.0) * density_kg_m3
        return int(round(option.price_minor * mass_kg))
    return None


def _mass_per_piece_kg(
    *,
    piece_mm: float,
    density_kg_m3: float,
    diameter_mm: float | None,
) -> float | None:
    if diameter_mm is None:
        return None
    area_m2 = 3.141592653589793 * (diameter_mm / 2000.0) ** 2
    volume_m3 = area_m2 * (piece_mm / 1000.0)
    return round(volume_m3 * density_kg_m3, 6)


def _insert_proposed_remnants(
    conn: sqlite3.Connection,
    *,
    material_id: str,
    bins: list[_Bin],
    grip_mm: float,
    source_ref: str,
    piece_mm: float,
) -> list[dict[str, Any]]:
    now = db.utc_now()
    by_length: dict[float, int] = {}
    for b in bins:
        leftover = b.remaining_mm
        if b.source == "new":
            leftover = b.remaining_mm
        if leftover < max(_MIN_USABLE_REMNANT_MM, piece_mm * 0.05):
            continue
        if leftover < piece_mm:
            continue
        by_length[leftover] = by_length.get(leftover, 0) + 1

    written: list[dict[str, Any]] = []
    for length_mm, count in sorted(by_length.items(), key=lambda x: -x[0]):
        rem_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO remnant_stock (
              id, material_id, length_mm, qty, state, source_ref, created_at
            ) VALUES (?, ?, ?, ?, 'proposed', ?, ?)
            """,
            (rem_id, material_id, length_mm, count, source_ref, now),
        )
        written.append(
            {
                "id": rem_id,
                "length_mm": length_mm,
                "qty": count,
                "state": "proposed",
            }
        )
    return written


def plan_stockcut(
    conn: sqlite3.Connection,
    material_id: str,
    part_length_mm: float,
    qty: int,
    kerf_mm: str | float = "",
    facing_mm: str | float = "",
    grip_mm: str | float = "",
    *,
    use_remnants: bool = True,
    as_of: str | None = None,
    source_ref: str = "stockcut",
) -> dict[str, Any]:
    """Plan 1D bar nest; may INSERT proposed remnants. Never treats proposed as stock."""
    if qty <= 0 or part_length_mm <= 0:
        raise ValueError("invalid_qty_or_length")

    kerf = _parse_float_param(kerf_mm, _DEFAULT_KERF_MM)
    facing = _parse_float_param(facing_mm, _DEFAULT_FACING_MM)
    grip = _parse_float_param(grip_mm, _DEFAULT_GRIP_MM)
    piece_mm = _piece_cut_length_mm(part_length_mm, facing_mm=facing, kerf_mm=kerf)
    as_of_val = as_of or db.utc_now()

    material = _load_material(conn, material_id)
    if material is None:
        raise ValueError("unknown_material")

    stock_options = _load_stock_options(conn, material_id, as_of=as_of_val)
    if not stock_options:
        return {"ask": True, "reason": "no_supplier_rm_quote"}

    remnant_lengths: list[tuple[str, float]] = []
    if use_remnants:
        remnant_lengths = _load_confirmed_remnants(conn, material_id)

    try:
        bins = _run_ffd(
            qty=qty,
            piece_mm=piece_mm,
            kerf_mm=kerf,
            grip_mm=grip,
            stock_options=stock_options,
            remnant_lengths=remnant_lengths,
        )
    except ValueError as exc:
        if str(exc) == "piece_longer_than_stock":
            return {"ask": True, "reason": "piece_longer_than_stock"}
        raise

    proposed = _insert_proposed_remnants(
        conn,
        material_id=material_id,
        bins=bins,
        grip_mm=grip,
        source_ref=source_ref,
        piece_mm=piece_mm,
    )

    density = material["density_kg_m3"]
    primary = min(stock_options, key=lambda o: o.price_minor / o.stock_length_mm)
    _, dia = _parse_size_spec(primary.size_spec)

    result: dict[str, Any] = {
        "bars": _summarize_bars(bins),
        "yield_pct": _yield_pct(qty=qty, piece_mm=piece_mm, bins=bins),
        "remnants": proposed,
        "piece_cut_length_mm": piece_mm,
    }

    if density is None:
        result["ask"] = True
        result["ask_density"] = True
    else:
        mass = _mass_per_piece_kg(
            piece_mm=piece_mm,
            density_kg_m3=float(density),
            diameter_mm=dia,
        )
        if mass is None:
            result["ask"] = True
            result["ask_mass"] = True
        else:
            result["mass_per_piece_kg"] = mass

    new_bar_count = sum(1 for b in bins if b.source == "new")
    unit_cost = _bar_unit_cost_minor(primary, density_kg_m3=density)
    if unit_cost is None:
        result["ask"] = True
        result["ask_price"] = True
    else:
        total_minor = new_bar_count * unit_cost
        result["cost_per_piece_minor"] = int(round(total_minor / qty)) if qty else 0
        result["cost_basis"] = {
            "supplier_rm_quote_id": primary.quote_id,
            "unit_basis": primary.unit_basis,
            "size_spec": primary.size_spec,
            "new_bars": new_bar_count,
            "total_material_minor": total_minor,
        }

    return result


def confirm_remnant(conn: sqlite3.Connection, remnant_id: str) -> bool:
    cur = conn.execute(
        """
        UPDATE remnant_stock
        SET state = 'confirmed'
        WHERE id = ? AND state = 'proposed'
        """,
        (remnant_id,),
    )
    return cur.rowcount > 0
