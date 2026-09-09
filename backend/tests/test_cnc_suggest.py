from __future__ import annotations

import inspect
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.cnc_suggest import suggest_program

PISTON = {"diameter": 50, "length": 80, "material": "EN8", "units": "mm"}
BANNED = ("G52", "G68", "G76", "G81", "G83", "G84", "G32", "G51")


def _write_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="jarvis-cnc-"))


def _motion_lines(nc: str) -> list[str]:
    return [
        line
        for line in nc.splitlines()
        if line.startswith(("G00", "G01", "G0 ", "G1 ", "G20", "G21", "G28", "G40", "G54", "G90", "G97"))
        or line[:1] in "TM%"
    ]


def test_happy_path_piston_od_and_length():
    result = suggest_program(PISTON)
    assert result["ok"] is True
    assert result["draft"] is True
    assert result["missing"] == []
    assert result["path"] is None
    nc = result["nc"]
    assert nc.startswith("%")
    assert nc.rstrip().endswith("%")
    assert "O1000" in nc
    assert "G54" in nc
    assert "G01" in nc
    assert "M30" in nc
    assert "DRAFT" in nc
    assert "Not proven on the machine" in nc
    assert "Not for auto-RFQ" in nc
    assert "G21" in nc
    assert "G90" in nc
    assert "G28" in nc
    assert "50" in nc
    assert "80" in nc
    assert "EN8" in nc
    assert "Z-80.000" in nc
    assert "X50.000" in nc
    strategy = result["strategy"]
    assert "G54" in strategy
    assert "50" in strategy
    assert "80" in strategy
    assert "unproven" in strategy.lower()
    assert "auto-RFQ" in strategy or "auto-rfq" in strategy.lower()


def test_od_only_is_ok_without_inventing_length():
    result = suggest_program({"od": 42.5})
    assert result["ok"] is True, result
    assert result["missing"] == []
    nc = result["nc"]
    assert "42.500" in nc or "42.5" in nc
    assert "Z-" not in nc
    assert "no Z pass" in nc or "length missing" in nc.lower()
    job_polluted = suggest_program(
        {"outer_diameter": 42.5},
        job={"length": 999, "geometry_notes": "chuck grip 12 mm"},
    )
    assert job_polluted["ok"] is True
    assert "Z-999" not in job_polluted["nc"]
    z_words = [tok for tok in job_polluted["nc"].replace("(", " ").replace(")", " ").split() if tok.startswith("Z")]
    assert not any("999" in tok for tok in z_words)


def test_length_only_facing_is_ok_without_inventing_od():
    result = suggest_program({"overall_length": 120})
    assert result["ok"] is True, result
    nc = result["nc"]
    assert "120" in nc
    assert "G01" in nc
    assert "Z0.000" in nc
    motion = _motion_lines(nc)
    assert all("X" not in line.upper().replace("MISSING", "") for line in motion if line.startswith(("G00", "G01")))
    assert "no OD" in nc or "diameter missing" in nc.lower()
    job_polluted = suggest_program({"length": 120}, job={"diameter": 77, "od": 77})
    assert "X77" not in job_polluted["nc"]
    assert "77.000" not in job_polluted["nc"]
    assert "77" not in job_polluted["nc"]


def test_empty_extract_refuses():
    result = suggest_program({})
    assert result["ok"] is False
    assert result["draft"] is True
    assert result["nc"] == ""
    assert "diameter" in result["missing"]
    assert "length" in result["missing"]
    assert result["path"] is None
    assert "invent" in result["strategy"].lower() or "missing" in result["strategy"].lower()


def test_non_numeric_strings_refuse_and_do_not_write():
    dest = _write_dir() / "nope.nc"
    result = suggest_program(
        {"diameter": "TBD", "length": "see drawing", "od": "n/a"},
        write_path=dest,
    )
    assert result["ok"] is False
    assert result["nc"] == ""
    assert result["path"] is None
    assert not dest.exists()
    assert "diameter" in result["missing"] or "length" in result["missing"]


def test_boolean_and_zero_and_negative_are_not_trusted_sizes():
    for extract in (
        {"diameter": True, "length": True},
        {"diameter": 0, "length": 0},
        {"od": -10, "length": -5},
        {"diameter": float("nan")},
        {"length": float("inf")},
    ):
        result = suggest_program(extract)
        assert result["ok"] is False, extract
        assert result["nc"] == ""


def test_ace_designers_machine_appears_in_strategy():
    result = suggest_program(
        PISTON,
        job={
            "machine": "Ace Designers",
            "material": "EN24",
            "geometry_notes": "keep fillet, no thread in this sketch",
            "cycle_min": "12",
        },
    )
    assert result["ok"] is True
    assert "Ace Designers" in result["strategy"]
    assert "Ace Designers" in result["nc"]
    assert "12" in result["strategy"]
    assert "keep fillet" in result["strategy"]
    assert "G54" in result["strategy"]
    assert "EN8" in result["nc"]


def test_write_path_creates_utf8_nc_and_parents():
    dest = _write_dir() / "nested" / "piston.nc"
    result = suggest_program(PISTON, write_path=dest)
    assert result["ok"] is True
    assert result["path"] == str(dest)
    assert dest.is_file()
    text = dest.read_text(encoding="utf-8")
    assert text == result["nc"]
    assert "M30" in text


def test_refuse_does_not_create_file_or_parents_side_effect_on_file():
    dest = _write_dir() / "should_not_exist.nc"
    result = suggest_program({}, write_path=dest)
    assert result["ok"] is False
    assert result["path"] is None
    assert not dest.exists()


def test_units_inch_vs_mm():
    mm = suggest_program({"diameter": 50, "length": 80, "units": "mm"})
    inch = suggest_program({"od": 2.0, "overall_length": 3.5, "units": "inch"})
    assert mm["ok"] and inch["ok"]
    assert "G21" in mm["nc"]
    assert "G20" not in mm["nc"]
    assert "G20" in inch["nc"]
    assert "G21" not in inch["nc"]
    inferred = suggest_program({"diameter": "2.0 inch", "length": "3.5 in"})
    assert inferred["ok"] is True
    assert "G20" in inferred["nc"]


def test_nc_has_no_invented_extra_features():
    result = suggest_program(
        {
            "outer_diameter": 50,
            "overall_length": 80,
            "bore": 20,
            "material": "aluminium",
        },
        job={"geometry_notes": "customer asked for G68 rotation and a G52 shift"},
    )
    nc = result["nc"].upper()
    for code in BANNED:
        assert code not in nc, code
    assert "G81" not in nc
    assert "20" in result["nc"]
    assert "boring cycle" in result["nc"].lower() or "bore" in result["strategy"].lower()


def test_flexible_keys_and_nested_dimension_list():
    nested = suggest_program(
        {
            "part": {
                "title": "Piston",
                "dimensions": [
                    {"name": "Outer diameter", "value": "50 mm"},
                    {"name": "overall_length", "value": 80},
                    {"label": "ID", "val": 18},
                ],
            }
        }
    )
    assert nested["ok"] is True
    assert "50" in nested["nc"]
    assert "80" in nested["nc"]
    assert "Piston" in nested["nc"]
    aliases = suggest_program({"stock_od": 33, "oal": 90, "unit": "mm"})
    assert aliases["ok"] is True
    assert "33" in aliases["nc"]
    assert "90" in aliases["nc"]


def test_draft_flag_always_true():
    assert suggest_program(PISTON)["draft"] is True
    assert suggest_program({})["draft"] is True


def test_module_is_offline_no_llm_imports():
    import app.cnc_suggest as mod

    source = inspect.getsource(mod)
    low = source.lower()
    assert "gemini" not in low
    assert "ollama" not in low
    assert "openai" not in low
    assert "requests" not in source
    assert "httpx" not in source
    assert "gemini_client" not in mod.__dict__
    assert "ollama_client" not in mod.__dict__


def test_job_cannot_supply_missing_geometry():
    result = suggest_program(
        {"material": "EN8"},
        job={"diameter": 50, "length": 80, "machine": "Ace Designers", "od": 50},
    )
    assert result["ok"] is False
    assert result["nc"] == ""
    assert "Ace Designers" in result["strategy"]


def test_string_numeric_dims_are_trusted():
    result = suggest_program({"od": "Ø50.0 mm", "length": "80 mm"})
    assert result["ok"] is True
    assert "50.000" in result["nc"]
    assert "80.000" in result["nc"]
    assert "G21" in result["nc"]
