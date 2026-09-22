"""Drawing identity cascade — sha256, text fingerprint, revision diff (manifest §4B.2)."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Literal

from .. import db
from .cards import card_primary_id

DrawingIdentityKind = Literal["exact", "propose", "revision_change", "new"]

# Near-duplicate text fingerprint hash is stored on part_revisions.drawing_artifact_id (K2).
_FINGERPRINT_COLUMN = "drawing_artifact_id"


def normalize_fingerprint_text(text: str) -> str:
    return " ".join((text or "").lower().split())


def text_fingerprint(text: str) -> str:
    normalized = normalize_fingerprint_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@dataclass
class DrawingIdentityResult:
    kind: DrawingIdentityKind
    part_revision_id: str | None = None
    matched_part_revision_id: str | None = None
    prior_part_revision_id: str | None = None
    changed_fields: list[str] = field(default_factory=list)
    change_details: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "part_revision_id": self.part_revision_id,
            "matched_part_revision_id": self.matched_part_revision_id,
            "prior_part_revision_id": self.prior_part_revision_id,
            "changed_fields": list(self.changed_fields),
            "change_details": list(self.change_details),
        }


def _confirmed_fact_map(conn: sqlite3.Connection, part_revision_id: str) -> dict[str, str]:
    card_id = card_primary_id("part_revision", part_revision_id)
    rows = conn.execute(
        """
        SELECT field, value
        FROM entity_facts
        WHERE card_id = ? AND state = 'confirmed'
        ORDER BY field ASC
        """,
        (card_id,),
    ).fetchall()
    return {str(row["field"]): str(row["value"]) for row in rows}


def _diff_confirmed_facts(
    conn: sqlite3.Connection,
    prior_revision_id: str,
    current_revision_id: str,
) -> tuple[list[str], list[dict[str, str]]]:
    prior = _confirmed_fact_map(conn, prior_revision_id)
    current = _confirmed_fact_map(conn, current_revision_id)
    fields = sorted(set(prior) | set(current))
    changed: list[str] = []
    details: list[dict[str, str]] = []
    for fld in fields:
        old_val = prior.get(fld)
        new_val = current.get(fld)
        if old_val == new_val:
            continue
        changed.append(fld)
        details.append(
            {
                "field": fld,
                "prior_value": old_val or "",
                "current_value": new_val or "",
            }
        )
    return changed, details


def format_revision_change_summary(result: DrawingIdentityResult) -> str:
    if not result.changed_fields:
        return "Revision change detected; no confirmed field differences on the cards yet."
    names = ", ".join(result.changed_fields)
    return f"Revision change: confirmed fields changed since the prior revision: {names}."


def resolve_drawing_identity(
    *,
    drawing_sha256: str,
    fingerprint_text: str | None = None,
    customer_id: str | None = None,
    drawing_no: str | None = None,
    revision: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> DrawingIdentityResult:
    """
    Identity cascade without OCR or cloud vision.
    Order: exact sha256 → text fingerprint → revision diff → new.
    """
    digest = (drawing_sha256 or "").strip().lower()
    if not digest:
        return DrawingIdentityResult(kind="new")

    def _resolve(connection: sqlite3.Connection) -> DrawingIdentityResult:
        exact = connection.execute(
            """
            SELECT id FROM part_revisions
            WHERE drawing_sha256 = ?
            LIMIT 1
            """,
            (digest,),
        ).fetchone()
        if exact:
            rid = str(exact["id"])
            return DrawingIdentityResult(
                kind="exact",
                part_revision_id=rid,
                matched_part_revision_id=rid,
            )

        fp_text = (fingerprint_text or "").strip()
        if fp_text:
            fp_hash = text_fingerprint(fp_text)
            near = connection.execute(
                f"""
                SELECT id, drawing_sha256 FROM part_revisions
                WHERE {_FINGERPRINT_COLUMN} = ?
                  AND (drawing_sha256 IS NULL OR LOWER(drawing_sha256) != ?)
                LIMIT 1
                """,
                (fp_hash, digest),
            ).fetchone()
            if near:
                rid = str(near["id"])
                return DrawingIdentityResult(
                    kind="propose",
                    matched_part_revision_id=rid,
                )

        cid = (customer_id or "").strip()
        dno = (drawing_no or "").strip()
        rev = (revision or "").strip()
        if cid and dno and rev:
            current = connection.execute(
                """
                SELECT pr.id
                FROM part_revisions pr
                JOIN components c ON c.id = pr.component_id
                WHERE c.customer_id = ? AND pr.drawing_no = ? AND pr.revision = ?
                LIMIT 1
                """,
                (cid, dno, rev),
            ).fetchone()
            if current:
                current_id = str(current["id"])
                prior = connection.execute(
                    """
                    SELECT pr.id
                    FROM part_revisions pr
                    JOIN components c ON c.id = pr.component_id
                    WHERE c.customer_id = ? AND pr.drawing_no = ? AND pr.revision != ?
                    ORDER BY pr.revision ASC
                    LIMIT 1
                    """,
                    (cid, dno, rev),
                ).fetchone()
                if prior:
                    prior_id = str(prior["id"])
                    changed, details = _diff_confirmed_facts(connection, prior_id, current_id)
                    return DrawingIdentityResult(
                        kind="revision_change",
                        part_revision_id=current_id,
                        prior_part_revision_id=prior_id,
                        changed_fields=changed,
                        change_details=details,
                    )

        return DrawingIdentityResult(kind="new")

    if conn is not None:
        return _resolve(conn)
    with db.connect() as connection:
        return _resolve(connection)
