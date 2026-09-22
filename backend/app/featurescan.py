"""Geometry-true STEP feature scan → routing draft (minimal ASCII reader, no OCC)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import db

_SUPPORTED_ENTITIES = frozenset({"CARTESIAN_POINT", "CIRCLE", "CYLINDRICAL_SURFACE"})


@dataclass
class ParsedStep:
    points: dict[int, tuple[float, float, float]] = field(default_factory=dict)
    circles: dict[int, float] = field(default_factory=dict)
    cylindrical_surfaces: dict[int, float] = field(default_factory=dict)
    unclassified: list[dict[str, Any]] = field(default_factory=list)


def _split_step_args(inner: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in inner:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def _parse_cartesian_point(args: list[str]) -> tuple[float, float, float] | None:
    if len(args) < 2:
        return None
    coord = args[1]
    m = re.match(
        r"\(\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*,"
        r"\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*,"
        r"\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*\)",
        coord,
    )
    if not m:
        return None
    return float(m.group(1)), float(m.group(2)), float(m.group(3))


def _parse_radius_arg(args: list[str]) -> float | None:
    if len(args) < 3:
        return None
    raw = args[-1].strip()
    try:
        return float(raw)
    except ValueError:
        return None


def _iter_step_entities(text: str):
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("#"):
            continue
        head = re.match(r"#(\d+)\s*=\s*(\w+)\s*\(", line)
        if not head:
            continue
        ent_id = int(head.group(1))
        ent_type = head.group(2).upper()
        start = head.end()
        depth = 1
        idx = start
        while idx < len(line) and depth:
            ch = line[idx]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            idx += 1
        if depth != 0 or idx >= len(line) or line[idx : idx + 2] != ";":
            continue
        yield ent_id, ent_type, line[start : idx - 1]


def parse_step_text(text: str) -> ParsedStep:
    parsed = ParsedStep()
    for ent_id, ent_type, inner in _iter_step_entities(text):
        args = _split_step_args(inner)

        if ent_type not in _SUPPORTED_ENTITIES:
            parsed.unclassified.append(
                {
                    "type": "step_entity",
                    "entity_id": f"#{ent_id}",
                    "entity_type": ent_type,
                }
            )
            continue

        if ent_type == "CARTESIAN_POINT":
            pt = _parse_cartesian_point(args)
            if pt is None:
                parsed.unclassified.append(
                    {
                        "type": "step_entity",
                        "entity_id": f"#{ent_id}",
                        "entity_type": ent_type,
                        "reason": "unparsed_geometry",
                    }
                )
            else:
                parsed.points[ent_id] = pt
        elif ent_type == "CIRCLE":
            radius = _parse_radius_arg(args)
            if radius is None:
                parsed.unclassified.append(
                    {
                        "type": "step_entity",
                        "entity_id": f"#{ent_id}",
                        "entity_type": ent_type,
                        "reason": "unparsed_geometry",
                    }
                )
            else:
                parsed.circles[ent_id] = radius
        elif ent_type == "CYLINDRICAL_SURFACE":
            radius = _parse_radius_arg(args)
            if radius is None:
                parsed.unclassified.append(
                    {
                        "type": "step_entity",
                        "entity_id": f"#{ent_id}",
                        "entity_type": ent_type,
                        "reason": "unparsed_geometry",
                    }
                )
            else:
                parsed.cylindrical_surfaces[ent_id] = radius

    return parsed


def _features_from_geometry(parsed: ParsedStep) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    seen_diameters: set[float] = set()

    for ent_id, radius in parsed.cylindrical_surfaces.items():
        diameter = round(radius * 2.0, 6)
        if diameter in seen_diameters:
            continue
        seen_diameters.add(diameter)
        features.append(
            {
                "type": "feature",
                "feature_kind": "hole",
                "diameter_mm": diameter,
                "tolerance": "free",
                "source_entity_id": f"#{ent_id}",
            }
        )

    for ent_id, radius in parsed.circles.items():
        diameter = round(radius * 2.0, 6)
        if diameter in seen_diameters:
            continue
        seen_diameters.add(diameter)
        features.append(
            {
                "type": "feature",
                "feature_kind": "hole",
                "diameter_mm": diameter,
                "tolerance": "free",
                "source_entity_id": f"#{ent_id}",
            }
        )

    return features


def _load_rules() -> list[dict[str, Any]]:
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT id, feature_kind, predicate_json, operations_json
            FROM feature_process_rules
            ORDER BY id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def _predicate_matches(feature: dict[str, Any], rule_kind: str, predicate: dict[str, Any]) -> bool:
    if feature.get("feature_kind") != rule_kind:
        return False

    if rule_kind == "hole":
        tol = feature.get("tolerance")
        if "tolerance" in predicate and predicate["tolerance"] != tol:
            return False
        if "tolerance_in" in predicate and tol not in predicate["tolerance_in"]:
            return False
        dia = feature.get("diameter_mm")
        if dia is None:
            return False
        if "diameter_mm_lt" in predicate and not (dia < float(predicate["diameter_mm_lt"])):
            return False
        if "diameter_mm_gt" in predicate and not (dia > float(predicate["diameter_mm_gt"])):
            return False
        return True

    if rule_kind == "bore":
        dia = feature.get("diameter_mm")
        if dia is None:
            return False
        if "diameter_mm_gt" in predicate and not (dia > float(predicate["diameter_mm_gt"])):
            return False
        if "finish_or_tolerance" in predicate and not feature.get("finish_or_tolerance"):
            return False
        return bool(predicate)

    if not predicate:
        return True

    for key, expected in predicate.items():
        if feature.get(key) != expected:
            return False
    return True


def _match_rule(feature: dict[str, Any], rules: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates: list[tuple[int, dict[str, Any]]] = []
    for rule in rules:
        if rule["feature_kind"] != feature.get("feature_kind"):
            continue
        try:
            predicate = json.loads(rule["predicate_json"])
        except json.JSONDecodeError:
            continue
        if not isinstance(predicate, dict):
            continue
        if _predicate_matches(feature, rule["feature_kind"], predicate):
            candidates.append((len(json.dumps(predicate, sort_keys=True)), rule))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def draft_routing_from_step(path: str | Path) -> dict[str, Any]:
    """Return routing draft from a STEP file using ``feature_process_rules``."""
    step_path = Path(path)
    parsed = parse_step_text(step_path.read_text(encoding="utf-8", errors="replace"))
    features = _features_from_geometry(parsed)
    rules = _load_rules()

    operations: list[str] = []
    unclassified: list[dict[str, Any]] = list(parsed.unclassified)

    for feature in features:
        rule = _match_rule(feature, rules)
        if not rule:
            unclassified.append({**feature, "reason": "no_matching_rule"})
            continue
        try:
            ops = json.loads(rule["operations_json"])
        except json.JSONDecodeError:
            unclassified.append({**feature, "reason": "invalid_rule_operations"})
            continue
        if not isinstance(ops, list):
            unclassified.append({**feature, "reason": "invalid_rule_operations"})
            continue
        for op in ops:
            if isinstance(op, str):
                operations.append(op)

    return {
        "operations": operations,
        "unclassified": unclassified,
        "source_kind": "geometry_true",
    }
