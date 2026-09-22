"""Deterministic NC verification before promote; versioned draft store (no transmission)."""

from __future__ import annotations

import hashlib
import re
import uuid
from contextlib import nullcontext
from typing import Any, Mapping, Sequence

from . import db

NOT_PROVEN_HEADER = "(NOT PROVEN ON THE MACHINE)"

_WORD = re.compile(r"([A-Za-z])([-+]?(?:\d+(?:\.\d*)?|\.\d+))")
_N_BLOCK = re.compile(r"\bN(\d+)\b", re.I)
_M_CODE = re.compile(r"\bM(\d+)\b", re.I)
_G_CODE = re.compile(r"\bG(\d+(?:\.\d+)?)\b", re.I)
_CANNED_START = frozenset({81, 82, 83, 84, 85, 86, 87, 88, 89})

Failure = dict[str, Any]
VerifyResult = dict[str, Any]


class ProgramVerifyError(Exception):
    """Raised when store/promote preconditions fail."""


def _strip_comments(line: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "(":
            depth = 1
            i += 1
            while i < len(line) and depth:
                if line[i] == "(":
                    depth += 1
                elif line[i] == ")":
                    depth -= 1
                i += 1
            continue
        if ch == ";":
            break
        out.append(ch)
        i += 1
    return "".join(out)


def _parse_g_codes(text: str) -> list[int]:
    codes: list[int] = []
    for match in _G_CODE.finditer(text):
        raw = match.group(1)
        codes.append(int(float(raw)))
    return codes


def _axis_words(text: str) -> dict[str, float]:
    axes: dict[str, float] = {}
    for letter, value in _WORD.findall(text.upper()):
        if letter in "XYZABCUVW":
            axes[letter] = float(value)
        elif letter == "F":
            axes["F"] = float(value)
    return axes


def _block_number(line: str, fallback: int) -> int:
    match = _N_BLOCK.search(line)
    if match:
        return int(match.group(1))
    return fallback


def _max_feed(feed_envelope: float | Mapping[str, float] | None) -> float | None:
    if feed_envelope is None:
        return None
    if isinstance(feed_envelope, (int, float)):
        return float(feed_envelope)
    if "max_feed" in feed_envelope:
        return float(feed_envelope["max_feed"])
    return None


def _load_machine(conn, machine_id: str):
    row = conn.execute(
        """
        SELECT id, travel_x, travel_y, travel_z, control_make, control_model
        FROM machines WHERE id = ?
        """,
        (machine_id,),
    ).fetchone()
    return row


def verify_program(
    machine_id: str,
    body: str,
    *,
    feed_envelope: float | Mapping[str, float] | None = None,
    m_whitelist: Sequence[int | str] | None = None,
    clearance_plane: float | None = None,
    conn=None,
) -> VerifyResult:
    """Parse *body* against machine limits and optional envelopes. No I/O except DB read."""
    failures: list[Failure] = []
    whitelist: set[int] | None = None
    if m_whitelist is not None:
        whitelist = {int(str(m).upper().lstrip("M")) for m in m_whitelist}

    max_feed = _max_feed(feed_envelope)
    if clearance_plane is None and isinstance(feed_envelope, Mapping):
        if "clearance_z" in feed_envelope:
            clearance_plane = float(feed_envelope["clearance_z"])
        elif "clearance_plane" in feed_envelope:
            clearance_plane = float(feed_envelope["clearance_plane"])

    ctx = db.connect() if conn is None else nullcontext(conn)
    with ctx as active:
        conn = active
        machine = _load_machine(conn, machine_id)
        if machine is None:
            failures.append(
                {
                    "block": 0,
                    "code": "machine_missing",
                    "detail": f"No machines row for id {machine_id!r}",
                }
            )
            return {"ok": False, "failures": failures}

        travel: dict[str, float | None] = {
            "X": machine["travel_x"],
            "Y": machine["travel_y"],
            "Z": machine["travel_z"],
        }

        pos = {"X": 0.0, "Y": 0.0, "Z": 0.0}
        absolute = True
        motion_mode = 0  # G00 rapid
        cycle_active = False
        block_idx = 0

        for raw_line in body.splitlines():
            stripped = raw_line.strip()
            if not stripped or stripped in ("%",):
                continue
            if stripped.startswith("O") and stripped[1:].isdigit():
                continue

            block_idx += 1
            block = _block_number(raw_line, block_idx)
            code_line = _strip_comments(stripped)
            if not code_line.strip():
                continue

            g_codes = _parse_g_codes(code_line)
            for g in g_codes:
                if g == 90:
                    absolute = True
                elif g == 91:
                    absolute = False
                elif g in (0, 1, 2, 3):
                    motion_mode = g
                elif g in _CANNED_START:
                    cycle_active = True
                elif g == 80:
                    if not cycle_active:
                        failures.append(
                            {
                                "block": block,
                                "code": "cycle_unbalanced",
                                "detail": "G80 without an active canned cycle",
                            }
                        )
                    cycle_active = False

            axes = _axis_words(code_line)
            target = dict(pos)
            for axis in "XYZ":
                if axis in axes:
                    if absolute:
                        target[axis] = axes[axis]
                    else:
                        target[axis] = pos[axis] + axes[axis]

            is_rapid = motion_mode == 0 or 0 in g_codes
            is_cut = motion_mode in (1, 2, 3) or any(g in (1, 2, 3) for g in g_codes)

            for axis in "XYZ":
                if axis not in axes:
                    continue
                limit = travel.get(axis)
                if limit is None:
                    continue
                val = target[axis]
                if val < 0 or val > float(limit):
                    failures.append(
                        {
                            "block": block,
                            "code": "travel_envelope",
                            "detail": (
                                f"{axis}={val} outside machine travel 0..{limit} (rapid={is_rapid})"
                            ),
                        }
                    )

            if is_rapid and "Z" in axes and clearance_plane is not None:
                z_val = target["Z"]
                if z_val < float(clearance_plane):
                    failures.append(
                        {
                            "block": block,
                            "code": "rapid_clearance",
                            "detail": (
                                f"G00 Z={z_val} below clearance plane Z={clearance_plane}"
                            ),
                        }
                    )

            if "F" in axes and max_feed is not None and (is_cut or 1 in g_codes or 2 in g_codes or 3 in g_codes):
                feed = axes["F"]
                if feed > max_feed:
                    failures.append(
                        {
                            "block": block,
                            "code": "feed_envelope",
                            "detail": f"Feed F={feed} exceeds envelope max {max_feed}",
                        }
                    )

            if whitelist is not None:
                for m_match in _M_CODE.finditer(code_line):
                    m_num = int(m_match.group(1))
                    if m_num not in whitelist:
                        failures.append(
                            {
                                "block": block,
                                "code": "m_code_whitelist",
                                "detail": f"M{m_num} not in control whitelist",
                            }
                        )

            for axis in "XYZ":
                if axis in axes:
                    pos[axis] = target[axis]

        if cycle_active:
            failures.append(
                {
                    "block": block_idx or 1,
                    "code": "cycle_unbalanced",
                    "detail": "Canned cycle started but not cancelled before program end",
                }
            )

        return {"ok": len(failures) == 0, "failures": failures}


def _ensure_draft_header(body: str) -> str:
    if NOT_PROVEN_HEADER in body:
        return body
    lines = body.splitlines()
    insert_at = 0
    if lines and lines[0].strip() == "%":
        insert_at = 1
    lines.insert(insert_at, NOT_PROVEN_HEADER)
    return "\n".join(lines)


def _sha256(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _next_version(conn, machine_id: str) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(version), 0) AS v FROM nc_programs WHERE machine_id = ?",
        (machine_id,),
    ).fetchone()
    return int(row["v"]) + 1


def store_draft(
    machine_id: str,
    body: str,
    *,
    conn=None,
    program_id: str | None = None,
) -> dict[str, Any]:
    """Persist append-only draft row; header must carry NOT PROVEN marker."""
    stamped = _ensure_draft_header(body)
    if NOT_PROVEN_HEADER not in stamped:
        raise ProgramVerifyError("Draft header missing NOT PROVEN marker")

    ctx = db.connect() if conn is None else nullcontext(conn)
    with ctx as active:
        conn = active
        machine = _load_machine(conn, machine_id)
        if machine is None:
            raise ProgramVerifyError(f"No machines row for id {machine_id!r}")

        pid = program_id or str(uuid.uuid4())
        version = _next_version(conn, machine_id)
        now = db.utc_now()
        digest = _sha256(stamped)
        conn.execute(
            """
            INSERT INTO nc_programs (
              id, machine_id, version, state, body, sha256, created_at, promoted_at
            ) VALUES (?, ?, ?, 'draft', ?, ?, ?, NULL)
            """,
            (pid, machine_id, version, stamped, digest, now),
        )
        return {
            "id": pid,
            "machine_id": machine_id,
            "version": version,
            "state": "draft",
            "sha256": digest,
        }


def promote(
    program_id: str,
    *,
    feed_envelope: float | Mapping[str, float] | None = None,
    m_whitelist: Sequence[int | str] | None = None,
    clearance_plane: float | None = None,
    conn=None,
) -> dict[str, Any]:
    """Verify then append promoted version; draft row is never updated in place."""
    ctx = db.connect() if conn is None else nullcontext(conn)
    with ctx as active:
        conn = active
        row = conn.execute(
            "SELECT * FROM nc_programs WHERE id = ?",
            (program_id,),
        ).fetchone()
        if row is None:
            raise ProgramVerifyError(f"Unknown nc_programs id {program_id!r}")
        if row["state"] != "draft":
            raise ProgramVerifyError("Only draft programs can be promoted")

        check = verify_program(
            row["machine_id"],
            row["body"],
            feed_envelope=feed_envelope,
            m_whitelist=m_whitelist,
            clearance_plane=clearance_plane,
            conn=conn,
        )
        if not check["ok"]:
            raise ProgramVerifyError(
                f"verify_program failed: {check['failures']}"
            )

        new_id = str(uuid.uuid4())
        version = _next_version(conn, row["machine_id"])
        now = db.utc_now()
        digest = _sha256(row["body"])
        conn.execute(
            """
            INSERT INTO nc_programs (
              id, machine_id, version, state, body, sha256, created_at, promoted_at
            ) VALUES (?, ?, ?, 'promoted', ?, ?, ?, ?)
            """,
            (
                new_id,
                row["machine_id"],
                version,
                row["body"],
                digest,
                now,
                now,
            ),
        )
        draft_after = conn.execute(
            "SELECT body, state FROM nc_programs WHERE id = ?",
            (program_id,),
        ).fetchone()
        return {
            "id": new_id,
            "draft_id": program_id,
            "machine_id": row["machine_id"],
            "version": version,
            "state": "promoted",
            "draft_unchanged": draft_after["body"] == row["body"]
            and draft_after["state"] == "draft",
        }
