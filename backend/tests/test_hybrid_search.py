from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.rag import hybrid_search, ingest_text


def setup_module(_module=None):
    db.init_db()


def _chunk_count() -> int:
    with db.connect() as conn:
        return int(conn.execute("SELECT COUNT(*) AS n FROM rag_chunks").fetchone()["n"])


def test_exact_token_hits_unique_chunk():
    rare = "SPL4092BREV7"
    ingest_text(
        f"Quote notes for customer.\n\nPart {rare} needs H7 bore.",
        namespace="quotes",
        doc_kind="quote",
    )
    ingest_text(
        f"Jarvis summary mentioning {rare} should not surface.",
        namespace="quotes",
        doc_kind="quote",
        authored_by="jarvis",
    )
    ingest_text(
        "Unrelated production log about VMC-02 downtime.",
        namespace="production",
    )

    hits = hybrid_search(f"find part {rare}", limit=8)
    assert hits
    with db.connect() as conn:
        texts = {
            row["id"]: row["text"]
            for row in conn.execute(
                "SELECT id, text FROM rag_chunks WHERE id IN ({})".format(
                    ",".join("?" * len(hits))
                ),
                hits,
            ).fetchall()
        }
        jarvis_rows = conn.execute(
            """
            SELECT c.id FROM rag_chunks c
            JOIN rag_documents d ON d.id = c.document_id
            WHERE d.authored_by = 'jarvis'
            """
        ).fetchall()
    assert any(rare in texts[cid] for cid in hits)
    jarvis_ids = {row["id"] for row in jarvis_rows}
    assert not jarvis_ids.intersection(hits)


def test_reingest_same_sha_does_not_duplicate_chunks():
    text = "Bracket drawing\n\nDimension table for WIDGET-9912-Z."
    before = _chunk_count()
    first = ingest_text(text, namespace="drawings", uri="test://widget")
    second = ingest_text(text, namespace="drawings", uri="test://widget-again")
    after = _chunk_count()

    assert first["skipped"] is False
    assert first["chunks_written"] >= 1
    assert second["skipped"] is True
    assert second["chunks_written"] == 0
    assert second["document_id"] == first["document_id"]
    assert after == before + first["chunks_written"]
