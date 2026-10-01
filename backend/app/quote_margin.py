"""Owner-only margin hint from won jobs — stored costs only, never writes sell price."""

from __future__ import annotations

import json
import statistics
from typing import Any

from . import db

PRIMARY_PROCESSES = frozenset({"turning", "milling", "turn-mill", "grinding"})
TOLERANCE_CLASSES = frozenset({"standard", "tight"})
_COST_KEYS = ("machining_minor", "material_minor", "outsource_minor", "tooling_minor")


def _parse_breakdown(raw: str | None) -> dict[str, int] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    out: dict[str, int] = {}
    for key in _COST_KEYS:
        if key not in data:
            return None
        try:
            out[key] = int(data[key])
        except (TypeError, ValueError):
            return None
        if out[key] < 0:
            return None
    return out


def _breakdown_from_lines(revision_id: str, conn) -> dict[str, int] | None:
    rows = conn.execute(
        """
        SELECT kind, SUM(amount_minor) AS amt
        FROM quote_lines
        WHERE quote_revision_id = ?
        GROUP BY kind
        """,
        (revision_id,),
    ).fetchall()
    kind_to_key = {
        "machining": "machining_minor",
        "material": "material_minor",
        "outsource": "outsource_minor",
        "tooling": "tooling_minor",
    }
    required_kinds = frozenset(kind_to_key)
    seen = {str(r["kind"]) for r in rows}
    if not required_kinds.issubset(seen):
        return None
    sums = {k: 0 for k in _COST_KEYS}
    for row in rows:
        kind = str(row["kind"])
        key = kind_to_key.get(kind)
        if key:
            sums[key] = int(row["amt"] or 0)
    return sums


def _total_cost_minor(breakdown: dict[str, int]) -> int:
    return sum(breakdown[k] for k in _COST_KEYS)


def margin_ratio(sell_minor: int, breakdown: dict[str, int]) -> float | None:
    if sell_minor <= 0:
        return None
    cost = _total_cost_minor(breakdown)
    if cost >= sell_minor:
        return None
    return (sell_minor - cost) / sell_minor


def _norm_process(value: str | None) -> str:
    return (value or "").strip().lower().replace("_", "-")


def _norm_tolerance(value: str | None) -> str:
    return (value or "").strip().lower()


def set_revision_margin_context(
    revision_id: str,
    *,
    primary_process: str,
    tolerance_class: str,
    cost_breakdown: dict[str, int],
) -> None:
    proc = _norm_process(primary_process)
    tol = _norm_tolerance(tolerance_class)
    if proc not in PRIMARY_PROCESSES:
        raise ValueError(f"invalid primary_process {primary_process!r}")
    if tol not in TOLERANCE_CLASSES:
        raise ValueError(f"invalid tolerance_class {tolerance_class!r}")
    breakdown = _parse_breakdown(json.dumps(cost_breakdown))
    if breakdown is None:
        raise ValueError("cost_breakdown must include all cost components as non-negative ints")
    with db.connect() as conn:
        conn.execute(
            """
            UPDATE quote_revisions
            SET primary_process = ?, tolerance_class = ?, cost_breakdown_json = ?
            WHERE id = ?
            """,
            (proc, tol, json.dumps(breakdown), revision_id),
        )


def mark_quote_revision_won(revision_id: str) -> None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT quote_id FROM quote_revisions WHERE id = ?",
            (revision_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"revision {revision_id} not found")
        conn.execute(
            "UPDATE quotes SET status = 'won' WHERE id = ?",
            (str(row["quote_id"]),),
        )


def _matching_won_margins(conn, primary_process: str, tolerance_class: str) -> list[float]:
    rows = conn.execute(
        """
        SELECT qr.total_minor, qr.cost_breakdown_json
        FROM quote_revisions qr
        JOIN quotes q ON q.id = qr.quote_id
        WHERE q.status = 'won'
          AND LOWER(COALESCE(qr.primary_process, '')) = ?
          AND LOWER(COALESCE(qr.tolerance_class, '')) = ?
          AND qr.cost_breakdown_json IS NOT NULL
          AND qr.cost_breakdown_json != ''
        ORDER BY qr.revision DESC
        """,
        (primary_process, tolerance_class),
    ).fetchall()
    margins: list[float] = []
    for row in rows:
        breakdown = _parse_breakdown(str(row["cost_breakdown_json"]))
        if not breakdown:
            continue
        ratio = margin_ratio(int(row["total_minor"] or 0), breakdown)
        if ratio is not None:
            margins.append(ratio)
    return margins


def compute_margin_hint(session_id: str, *, route: str = "owner") -> dict[str, Any]:
    """Return hint text or silence. Never mutates sell price or triggers speech."""
    if (route or "").strip().lower() == "staff":
        return {"ok": True, "silent": True}

    from .masterdata.quotes import revision_id_from_session

    revision_id = revision_id_from_session(session_id)
    if not revision_id:
        return {"ok": True, "silent": True}

    with db.connect() as conn:
        rev = conn.execute(
            """
            SELECT total_minor, primary_process, tolerance_class, cost_breakdown_json
            FROM quote_revisions WHERE id = ?
            """,
            (revision_id,),
        ).fetchone()
        if not rev:
            return {"ok": True, "silent": True}

        proc = _norm_process(rev["primary_process"])
        tol = _norm_tolerance(rev["tolerance_class"])
        if proc not in PRIMARY_PROCESSES or tol not in TOLERANCE_CLASSES:
            return {"ok": True, "silent": True}

        breakdown = _parse_breakdown(str(rev["cost_breakdown_json"] or ""))
        if breakdown is None:
            breakdown = _breakdown_from_lines(revision_id, conn)
        if breakdown is None:
            return {"ok": True, "silent": True}

        sell_minor = int(rev["total_minor"] or 0)
        current = margin_ratio(sell_minor, breakdown)
        if current is None:
            return {"ok": True, "silent": True}

        won_margins = _matching_won_margins(conn, proc, tol)
        if len(won_margins) < 3:
            return {"ok": True, "silent": True}

        median = statistics.median(won_margins)
        delta = current - median
        direction = "higher" if delta < -0.015 else "lower" if delta > 0.015 else None
        if direction is None:
            return {"ok": True, "silent": True}

        pct = lambda r: f"{r * 100:.1f}%"
        hint = (
            f"Three won {proc} / {tol} jobs averaged {pct(median)} margin "
            f"(machining + material + outsource + tooling from stored rows). "
            f"This quote is {pct(current)} — consider a {direction} margin."
        )
        return {
            "ok": True,
            "silent": False,
            "hint_text": hint,
            "current_margin_ratio": current,
            "median_won_margin_ratio": median,
            "sell_minor": sell_minor,
        }
