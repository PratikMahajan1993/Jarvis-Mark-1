"""Offline draft Fanuc-ish turning programs from drawing extract JSON.

Tony can ask for a from-scratch CNC sketch later; auto-RFQ must never call this.
No LLM. Missing geometry is refused, never invented.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

_DIAMETER_KEYS = frozenset(
    {
        "diameter",
        "od",
        "outer_diameter",
        "outer_dia",
        "outer_diam",
        "stock_od",
        "stock_diameter",
        "o_d",
        "dia",
        "diam",
    }
)
_LENGTH_KEYS = frozenset(
    {
        "length",
        "overall_length",
        "stock_length",
        "oal",
        "part_length",
        "len",
        "finished_length",
    }
)
_BORE_KEYS = frozenset(
    {
        "bore",
        "id",
        "inner_diameter",
        "inner_dia",
        "inner_diam",
        "i_d",
        "bore_dia",
        "bore_diameter",
    }
)
_MATERIAL_KEYS = frozenset({"material", "matl", "mat", "stock_material"})
_UNITS_KEYS = frozenset({"units", "unit"})
_NEST_KEYS = frozenset(
    {
        "dimensions",
        "dims",
        "geometry",
        "part",
        "features",
        "measurements",
        "sizes",
        "extract",
        "values",
    }
)
_INCH_UNITS = frozenset({"in", "inch", "inches", "imperial"})
_MM_UNITS = frozenset({"mm", "millimeter", "millimeters", "millimetre", "millimetres", "metric"})
_NUMBER = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")
_BANNED_WORDS = re.compile(
    r"\b(?:g52|g68|g76|g81|g83|g84|g32|g51|g92|g96)\b",
    re.I,
)

# OD-only is allowed (radial pass at the face; no facing-to-length).
# Length-only is allowed (face Z0; no OD turn). Empty / non-numeric is not.
_OD_ONLY_OK = True
_LENGTH_ONLY_OK = True


def suggest_program(
    extract: dict,
    job: dict | None = None,
    write_path: Path | None = None,
) -> dict:
    """Return a draft turning program grounded in extract (+ optional job notes).

    Always ``draft=True``. Writes ``write_path`` only when generation succeeds.
    """
    dims = _read_dims(extract if isinstance(extract, dict) else {})
    notes = _read_job(job if isinstance(job, dict) else None)
    material = dims["material"] or notes["material"]
    inch = dims["inch"]
    diameter = dims["diameter"]
    length = dims["length"]
    bore = dims["bore"]

    missing = _missing_for(diameter, length)
    if missing:
        strategy = _refuse_strategy(missing, notes)
        return _payload(ok=False, strategy=strategy, nc="", missing=missing, path=None)

    nc = _build_nc(
        diameter=diameter,
        length=length,
        bore=bore,
        material=material,
        inch=inch,
        notes=notes,
        extra=dims["extra"],
    )
    strategy = _build_strategy(
        diameter=diameter,
        length=length,
        bore=bore,
        material=material,
        inch=inch,
        notes=notes,
    )
    path: str | None = None
    if write_path is not None:
        dest = Path(write_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(nc, encoding="utf-8")
        path = str(dest)
    return _payload(ok=True, strategy=strategy, nc=nc, missing=[], path=path)


def _payload(*, ok: bool, strategy: str, nc: str, missing: list[str], path: str | None) -> dict:
    return {
        "ok": ok,
        "draft": True,
        "strategy": strategy,
        "nc": nc,
        "missing": missing,
        "path": path,
    }


def _missing_for(diameter: float | None, length: float | None) -> list[str]:
    if diameter is not None and length is not None:
        return []
    if diameter is not None and _OD_ONLY_OK:
        return []
    if length is not None and _LENGTH_ONLY_OK:
        return []
    missing: list[str] = []
    if diameter is None:
        missing.append("diameter")
    if length is None:
        missing.append("length")
    if not missing:
        missing = ["diameter", "length"]
    return missing


def _read_dims(extract: dict[str, Any]) -> dict[str, Any]:
    found: dict[str, Any] = {
        "diameter": None,
        "length": None,
        "bore": None,
        "material": None,
        "inch": False,
        "extra": {},
    }
    units_token: str | None = None
    walk_units: list[str] = []

    def take_number(canonical: str, value: Any) -> None:
        if found[canonical] is not None:
            return
        number = _parse_number(value)
        if number is None:
            return
        found[canonical] = number
        inferred = _units_from_value(value)
        if inferred:
            walk_units.append(inferred)

    def take_material(value: Any) -> None:
        if found["material"]:
            return
        text = _plain(value)
        if text:
            found["material"] = text

    def visit(node: Any, depth: int) -> None:
        nonlocal units_token
        if depth > 5 or node is None:
            return
        if isinstance(node, dict):
            for raw_key, value in node.items():
                key = _norm_key(raw_key)
                if key in _UNITS_KEYS and units_token is None:
                    token = _plain(value).lower()
                    if token:
                        units_token = token
                elif key in _DIAMETER_KEYS:
                    take_number("diameter", value)
                elif key in _LENGTH_KEYS:
                    take_number("length", value)
                elif key in _BORE_KEYS:
                    take_number("bore", value)
                elif key in _MATERIAL_KEYS:
                    take_material(value)
                elif key in {"title", "name", "part_name", "drawing", "drawing_no"}:
                    text = _plain(value)
                    if text and "title" not in found["extra"]:
                        found["extra"]["title"] = text
                elif key in _NEST_KEYS or isinstance(value, (dict, list)):
                    visit(value, depth + 1)
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, dict):
                    label = item.get("name") or item.get("key") or item.get("label") or item.get("id") or ""
                    value = item.get("value", item.get("val", item.get("size", item.get("mm", item.get("inch")))))
                    key = _norm_key(str(label)) if label else ""
                    if key in _DIAMETER_KEYS:
                        take_number("diameter", value)
                    elif key in _LENGTH_KEYS:
                        take_number("length", value)
                    elif key in _BORE_KEYS:
                        take_number("bore", value)
                    elif key in _MATERIAL_KEYS:
                        take_material(value)
                    else:
                        visit(item, depth + 1)
                else:
                    visit(item, depth + 1)

    visit(extract, 0)
    inch = False
    if units_token:
        inch = _is_inch_token(units_token)
    elif walk_units:
        inch = any(token == "inch" for token in walk_units) and not any(
            token == "mm" for token in walk_units
        )
    found["inch"] = inch
    return found


def _read_job(job: dict[str, Any] | None) -> dict[str, str]:
    if not job:
        return {"machine": "", "material": "", "geometry_notes": "", "cycle_min": "", "work_offset": "G54"}
    machine = _plain(job.get("machine"))
    material = _plain(job.get("material"))
    geometry_notes = _plain(job.get("geometry_notes") or job.get("notes"))
    cycle_min = _plain(job.get("cycle_min"))
    offset = _plain(job.get("work_offset") or job.get("offset") or "G54").upper().replace(" ", "")
    if not re.fullmatch(r"G5[4-9](?:\.[1-3])?", offset):
        offset = "G54"
    return {
        "machine": machine,
        "material": material,
        "geometry_notes": geometry_notes,
        "cycle_min": cycle_min,
        "work_offset": offset,
    }


def _norm_key(raw: str) -> str:
    text = str(raw).strip().lower()
    text = text.replace("ø", " ").replace("Ø", " ")
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text


def _plain(value: Any) -> str:
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, (int, float)):
        if not _finite(float(value)):
            return ""
        return str(value)
    text = str(value).strip()
    return text


def _finite(value: float) -> bool:
    return math.isfinite(value)


def _parse_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if not _finite(number) or number <= 0:
            return None
        return number
    if isinstance(value, str):
        match = _NUMBER.search(value)
        if not match:
            return None
        try:
            number = float(match.group(0))
        except ValueError:
            return None
        if not _finite(number) or number <= 0:
            return None
        return number
    return None


def _units_from_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    low = value.strip().lower()
    if re.search(r"\b(in|inch|inches)\b", low):
        return "inch"
    if re.search(r"\b(mm|millimet(?:er|re)s?)\b", low):
        return "mm"
    return None


def _is_inch_token(token: str) -> bool:
    compact = token.strip().lower()
    if compact in _INCH_UNITS:
        return True
    if compact in _MM_UNITS:
        return False
    return compact.startswith("inch") or compact == "in"


def _fmt(value: float, inch: bool) -> str:
    decimals = 4 if inch else 3
    return f"{value:.{decimals}f}"


def _unit_label(inch: bool) -> str:
    return "inch" if inch else "mm"


def _clearance(inch: bool) -> tuple[float, float, float]:
    if inch:
        return 0.20, 0.10, 0.04
    return 5.0, 2.0, 1.0


def _feeds(inch: bool) -> tuple[float, float, int]:
    if inch:
        return 0.005, 0.007, 600
    return 0.12, 0.18, 600


def _paren(text: str) -> str:
    clean = re.sub(r"[()]", " ", text).strip()
    clean = _BANNED_WORDS.sub(" ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return f"({clean})"


def _refuse_strategy(missing: list[str], notes: dict[str, str]) -> str:
    need = " and ".join(missing)
    bits = [
        "Cannot draft a CNC program — missing trusted linear size(s): "
        + need
        + ". I will not invent geometry."
    ]
    if notes["machine"]:
        bits.append(f"Job machine {notes['machine']} was not used to fill dimensions.")
    bits.append("This module stays a draft sketch and is not for auto-RFQ.")
    return " ".join(bits)


def _build_strategy(
    *,
    diameter: float | None,
    length: float | None,
    bore: float | None,
    material: str,
    inch: bool,
    notes: dict[str, str],
) -> str:
    unit = _unit_label(inch)
    offset = notes["work_offset"]
    ops: list[str] = []
    if length is not None and diameter is not None:
        ops.append(
            f"face the bar first so {offset} Z0 is the finished end "
            f"(stock length {_fmt(length, inch)} {unit})"
        )
        ops.append(
            f"then OD-turn to {_fmt(diameter, inch)} {unit} over {_fmt(length, inch)} {unit} with T01"
        )
    elif diameter is not None:
        ops.append(
            f"OD-set to {_fmt(diameter, inch)} {unit} at the face plane with T01 — "
            "stock length is absent so there is no facing-to-length and no longitudinal pass"
        )
    elif length is not None:
        ops.append(
            f"face to Z0 (finished length {_fmt(length, inch)} {unit}); "
            "no OD turn because diameter is absent; X is not programmed from the drawing"
        )

    lead = "Draft turning sketch, not proven on the machine and not for auto-RFQ."
    if notes["machine"]:
        lead = (
            f"Draft turning on {notes['machine']}, not proven on the machine "
            "and not for auto-RFQ."
        )
    why = (
        "Facing before the OD pass sets the Z datum, then the diameter is cut "
        "to the extract size."
        if diameter is not None and length is not None
        else "Only the trusted size from the extract is programmed; the rest is left off."
    )
    parts = [lead, f"Work offset {offset}."]
    if ops:
        parts.append("Sequence: " + "; ".join(ops) + ".")
    parts.append(why)
    parts.append("Feeds and speeds are conservative comments plus modest G01 values, unproven.")
    if material:
        parts.append(f"Material {material}.")
    if bore is not None:
        parts.append(
            f"Bore {_fmt(bore, inch)} {unit} is on the extract but this draft does not add a boring cycle."
        )
    if notes["cycle_min"]:
        parts.append(f"Job cycle note: {notes['cycle_min']}.")
    if notes["geometry_notes"]:
        parts.append(f"Job geometry notes: {notes['geometry_notes']}.")
    return " ".join(parts)


def _build_nc(
    *,
    diameter: float | None,
    length: float | None,
    bore: float | None,
    material: str,
    inch: bool,
    notes: dict[str, str],
    extra: dict[str, str],
) -> str:
    unit = _unit_label(inch)
    x_clear, z_clear, x_over = _clearance(inch)
    face_f, od_f, rpm = _feeds(inch)
    offset = notes["work_offset"]
    lines: list[str] = [
        "%",
        "O1000",
        "(DRAFT)",
        "(Not proven on the machine)",
        "(Not for auto-RFQ)",
        "(Jarvis from-scratch turning sketch)",
    ]
    title = extra.get("title") or ""
    if title:
        lines.append(_paren(f"Part {title}"))
    if notes["machine"]:
        lines.append(_paren(f"Machine {notes['machine']}"))
    if material:
        lines.append(_paren(f"Material {material}"))
    if diameter is not None:
        lines.append(_paren(f"OD {_fmt(diameter, inch)} {unit}"))
    if length is not None:
        lines.append(_paren(f"Length {_fmt(length, inch)} {unit}"))
    if bore is not None:
        lines.append(_paren(f"Bore {_fmt(bore, inch)} {unit} noted — no boring cycle in this draft"))
    if notes["geometry_notes"]:
        lines.append(_paren(f"Job notes {notes['geometry_notes']}"))
    if notes["cycle_min"]:
        lines.append(_paren(f"Cycle note {notes['cycle_min']}"))
    lines.append(_paren(f"Work offset {offset}"))
    lines.append("(Feeds and speeds are conservative and unproven)")
    lines.append("G21" if not inch else "G20")
    lines.append("G90")
    lines.append("G40")
    lines.append("G28 U0 W0")
    lines.append("(Safety return to reference)")
    lines.append(offset)
    lines.append("T0101")
    lines.append("(OD turning tool — unproven)")
    lines.append(f"G97 S{rpm} M03")
    lines.append("(Spindle speed unproven)")

    if diameter is not None:
        x_app = diameter + x_clear
        x_cut = diameter
        x_face = -x_over
        if length is not None:
            lines.append(
                _paren(
                    f"Facing then OD turn using extract OD {_fmt(diameter, inch)} "
                    f"and length {_fmt(length, inch)}"
                )
            )
            lines.append(f"G00 X{_fmt(x_app, inch)} Z{_fmt(z_clear, inch)}")
            lines.append(f"G00 Z{_fmt(0.0, inch)}")
            lines.append(_paren(f"Facing across the end, feed {_fmt(face_f, inch)} unproven"))
            lines.append(f"G01 X{_fmt(x_face, inch)} F{_fmt(face_f, inch)}")
            lines.append(f"G00 Z{_fmt(z_clear, inch)}")
            lines.append(f"G00 X{_fmt(x_app, inch)}")
            lines.append(f"G00 X{_fmt(x_cut, inch)} Z{_fmt(0.0, inch)}")
            lines.append(_paren(f"OD turn to Z-{_fmt(length, inch)}, feed {_fmt(od_f, inch)} unproven"))
            lines.append(f"G01 Z-{_fmt(length, inch)} F{_fmt(od_f, inch)}")
            lines.append(f"G00 X{_fmt(x_app, inch)} Z{_fmt(z_clear, inch)}")
        else:
            lines.append("(OD at face plane only — length missing, no Z pass, no facing-to-length)")
            lines.append(f"G00 X{_fmt(x_app, inch)} Z{_fmt(z_clear, inch)}")
            lines.append(f"G00 Z{_fmt(0.0, inch)}")
            lines.append(_paren(f"Radial move to OD {_fmt(diameter, inch)}, feed {_fmt(od_f, inch)} unproven"))
            lines.append(f"G01 X{_fmt(x_cut, inch)} F{_fmt(od_f, inch)}")
            lines.append(f"G00 X{_fmt(x_app, inch)} Z{_fmt(z_clear, inch)}")
    else:
        assert length is not None
        lines.append("(Facing to establish Z0 — diameter missing, X not moved from drawing)")
        lines.append(
            _paren(
                f"Finished length {_fmt(length, inch)} {unit} — far end Z-{_fmt(length, inch)}, no OD turn"
            )
        )
        lines.append(f"G00 Z{_fmt(z_clear, inch)}")
        lines.append(_paren(f"Face to Z0, feed {_fmt(face_f, inch)} unproven"))
        lines.append(f"G01 Z{_fmt(0.0, inch)} F{_fmt(face_f, inch)}")
        lines.append(f"G00 Z{_fmt(z_clear, inch)}")

    lines.append("G28 U0 W0")
    lines.append("M05")
    lines.append("M30")
    lines.append("%")
    text = "\n".join(lines) + "\n"
    motion = "\n".join(line for line in lines if line and line[0] in "GMTOSgmtos%")
    if _BANNED_WORDS.search(motion):
        raise RuntimeError("draft NC contained a banned extra-feature word")
    return text
